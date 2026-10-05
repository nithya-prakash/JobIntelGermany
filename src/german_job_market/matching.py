"""Skills-only candidate-to-job retrieval with explicit overlap explanations."""

from __future__ import annotations

import heapq
import json
import math
from pathlib import Path
from typing import Any, cast

import duckdb

from german_job_market.skills import SkillTaxonomy, extract_skill_spans


def _required_row(result: Any) -> tuple[Any, ...]:
    row = result.fetchone()
    if row is None:
        raise ValueError("expected query to return one row")
    return cast(tuple[Any, ...], row)


def _ranking_key(record: dict[str, Any]) -> tuple[float, float, str]:
    return (
        -record["score_components"]["harmonic_f1"],
        -record["score_components"]["job_skill_coverage"],
        record["job_id"],
    )


def _attach_gap_evidence(
    ranked: list[dict[str, Any]], jobs_path: Path, taxonomy: SkillTaxonomy, width: int = 60
) -> None:
    """Add occurrence counts and up to two short context snippets per unmatched job skill."""
    connection = duckdb.connect()
    try:
        rows = connection.execute(
            "SELECT job_id, title, description FROM read_parquet(?) "
            "WHERE job_id IN (SELECT unnest(?))",
            [str(jobs_path), [record["job_id"] for record in ranked]],
        ).fetchall()
    finally:
        connection.close()
    texts = {row[0]: " ".join(v for v in (row[1], row[2]) if v) for row in rows}
    for record in ranked:
        text = texts.get(record["job_id"], "")
        spans = extract_skill_spans(text, taxonomy)
        for item in record["not_found_in_candidate_profile"]:
            found = spans.get(item["skill_id"], [])
            item["occurrences_in_ad"] = len(found)
            item["snippets"] = [
                text[max(0, a - width) : b + width].replace("\n", " ").strip() for a, b in found[:2]
            ]


def rank_jobs(
    candidate_skill_ids: list[str],
    jobs_path: Path,
    skills_path: Path,
    taxonomy: SkillTaxonomy,
    top_k: int = 10,
    exclude_job_ids: set[str] | None = None,
    input_mode: str = "structured_skill_ids",
) -> dict[str, Any]:
    """Rank jobs with harmonic mean of candidate precision and job skill coverage."""
    if top_k < 1:
        raise ValueError("top_k must be at least 1")
    for path in (jobs_path, skills_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    if not candidate_skill_ids:
        raise ValueError("candidate has no recognized skills")

    unknown_candidate_ids = sorted(set(candidate_skill_ids).difference(taxonomy.by_id))
    if unknown_candidate_ids:
        raise ValueError(f"candidate has skill IDs missing from taxonomy: {unknown_candidate_ids}")
    candidate_ids = set(candidate_skill_ids)
    candidate_order = [skill.id for skill in taxonomy.skills if skill.id in candidate_ids]
    excluded_ids = exclude_job_ids or set()
    skill_by_id = taxonomy.by_id

    connection = duckdb.connect()
    try:
        job_columns = {
            row[0]
            for row in connection.execute(
                "DESCRIBE SELECT * FROM read_parquet(?)", [str(jobs_path)]
            ).fetchall()
        }
        if missing := {
            "job_id",
            "title",
            "source_url",
            "company",
            "location",
            "remote_type",
            "employment_type",
        }.difference(job_columns):
            raise ValueError(f"job input missing required columns: {sorted(missing)}")
        skill_columns = {
            row[0]
            for row in connection.execute(
                "DESCRIBE SELECT * FROM read_parquet(?)", [str(skills_path)]
            ).fetchall()
        }
        if not {"job_id", "skill_ids"}.issubset(skill_columns):
            raise ValueError("skill input must have job_id and skill_ids columns")

        job_rows = int(
            _required_row(
                connection.execute("SELECT count(*) FROM read_parquet(?)", [str(jobs_path)])
            )[0]
        )
        sidecar_rows, unique_sidecar_ids = _required_row(
            connection.execute(
                "SELECT count(*), count(DISTINCT job_id) FROM read_parquet(?)",
                [str(skills_path)],
            )
        )
        if int(sidecar_rows) != job_rows or int(unique_sidecar_ids) != int(sidecar_rows):
            raise ValueError("job/skill sidecar is not one-to-one")

        result = connection.execute(
            """SELECT j.job_id, j.title, j.source_url, j.company, j.location,
                      j.remote_type, j.employment_type, s.skill_ids
               FROM read_parquet(?) AS j
               JOIN read_parquet(?) AS s USING(job_id)
               """,
            [str(jobs_path), str(skills_path)],
        )
        reader = result.to_arrow_reader(batch_size=8192)
        counts = {
            "postings_scanned": 0,
            "postings_with_skills": 0,
            "postings_with_candidate_overlap": 0,
            "postings_excluded_by_id": 0,
        }
        corpus_skill_counts = {skill_id: 0 for skill_id in skill_by_id}
        unknown_job_skills: set[str] = set()

        def matching_records() -> Any:
            for batch in reader:
                for row in batch.to_pylist():
                    counts["postings_scanned"] += 1
                    job_id = row["job_id"]
                    if job_id in excluded_ids:
                        counts["postings_excluded_by_id"] += 1
                        continue
                    raw_skill_ids = row["skill_ids"] or []
                    unknown_job_skills.update(
                        skill_id for skill_id in raw_skill_ids if skill_id not in skill_by_id
                    )
                    job_skill_ids = set(raw_skill_ids).intersection(skill_by_id)
                    if not job_skill_ids:
                        continue
                    counts["postings_with_skills"] += 1
                    for skill_id in job_skill_ids:
                        corpus_skill_counts[skill_id] += 1
                    matched_ids = candidate_ids.intersection(job_skill_ids)
                    if not matched_ids:
                        continue
                    counts["postings_with_candidate_overlap"] += 1
                    precision = len(matched_ids) / len(candidate_ids)
                    coverage = len(matched_ids) / len(job_skill_ids)
                    harmonic_f1 = (
                        2 * precision * coverage / (precision + coverage)
                        if precision + coverage
                        else 0.0
                    )
                    missing_ids = job_skill_ids.difference(candidate_ids)
                    matched_skills = [
                        {"skill_id": skill_id, "label": skill_by_id[skill_id].label}
                        for skill_id in candidate_order
                        if skill_id in matched_ids
                    ]
                    gap_skills = [
                        {
                            "skill_id": skill_id,
                            "label": skill_by_id[skill_id].label,
                            "corpus_posting_count": corpus_skill_counts[skill_id],
                        }
                        for skill_id in sorted(
                            missing_ids,
                            key=lambda value: (-corpus_skill_counts[value], value),
                        )
                    ]
                    unmatched_candidate = [
                        {"skill_id": skill_id, "label": skill_by_id[skill_id].label}
                        for skill_id in candidate_order
                        if skill_id not in job_skill_ids
                    ]
                    yield {
                        "job_id": job_id,
                        "title": row["title"],
                        "company": row["company"],
                        "source_url": row["source_url"],
                        "location": row["location"],
                        "remote_type": row["remote_type"],
                        "employment_type": row["employment_type"],
                        "match_score": round(harmonic_f1, 6),
                        "score_components": {
                            "candidate_skill_precision": round(precision, 6),
                            "job_skill_coverage": round(coverage, 6),
                            "harmonic_f1": round(harmonic_f1, 6),
                            "matched_skill_count": len(matched_ids),
                            "candidate_skill_count": len(candidate_ids),
                            "job_skill_count": len(job_skill_ids),
                        },
                        "matched_skills": matched_skills,
                        "not_found_in_candidate_profile": gap_skills,
                        "requirement_status": "unverified",
                        "candidate_skills_not_in_job": unmatched_candidate,
                        "evidence_basis": (
                            "Phase 2 lexicon matches over job title and combined "
                            "advertisement text; "
                            "the source does not separate requirements from responsibilities."
                        ),
                    }

        ranked = heapq.nsmallest(top_k, matching_records(), key=_ranking_key)
        if counts["postings_scanned"] != job_rows:
            raise ValueError(
                "job/skill sidecar IDs do not cover every job "
                f"(jobs={job_rows}, joined_rows={counts['postings_scanned']})"
            )
        if unknown_job_skills:
            raise ValueError(
                f"job sidecar has skill IDs missing from taxonomy: {sorted(unknown_job_skills)}"
            )
    finally:
        connection.close()

    for rank, record in enumerate(ranked, start=1):
        record["rank"] = rank
        record["not_found_in_candidate_profile"].sort(
            key=lambda item: (
                -corpus_skill_counts[item["skill_id"]],
                item["skill_id"],
            )
        )
        for missing_skill in record["not_found_in_candidate_profile"]:
            missing_skill["corpus_posting_count"] = corpus_skill_counts[missing_skill["skill_id"]]

    _attach_gap_evidence(ranked, jobs_path, taxonomy)

    return {
        "matching_method": "canonical_skill_overlap_harmonic_f1",
        "score_interpretation": (
            "Harmonic mean of candidate skill precision and job skill coverage. "
            "This is taxonomy overlap, not probability of hiring or overall suitability."
        ),
        "candidate": {
            "input_mode": input_mode,
            "skill_ids": candidate_order,
            "skills": [
                {"skill_id": skill_id, "label": skill_by_id[skill_id].label}
                for skill_id in candidate_order
            ],
        },
        "scan_summary": counts,
        "market_skill_frequencies": {
            skill_id: corpus_skill_counts[skill_id] for skill_id in candidate_order
        },
        "ranked_jobs": ranked,
        "limitations": [
            "The seed taxonomy is finite; exact lexicon matches miss unlisted or "
            "context-dependent skills.",
            "The source combines ad sections, so matched terms are not verified "
            "as required qualifications.",
            "No location, seniority, language, salary, or human relevance labels "
            "are used in ranking.",
            "Market skill counts are historical corpus frequencies, not current "
            "demand or learning recommendations.",
        ],
    }


def ranking_metrics(
    ranked_job_ids: list[str], relevant_job_ids: list[str], k: int
) -> dict[str, float]:
    """Calculate binary-relevance Precision@K, Recall@K, MRR, and NDCG@K."""
    if k < 1:
        raise ValueError("k must be at least 1")
    relevant = set(relevant_job_ids)
    if not relevant:
        raise ValueError("at least one manually judged relevant job is required")
    top_k = ranked_job_ids[:k]
    hits = [job_id in relevant for job_id in top_k]
    hit_count = sum(hits)
    reciprocal_rank = next(
        (1.0 / rank for rank, is_relevant in enumerate(hits, start=1) if is_relevant), 0.0
    )
    dcg = sum(
        1.0 / math.log2(rank + 1) for rank, is_relevant in enumerate(hits, start=1) if is_relevant
    )
    ideal_relevant_count = min(len(relevant), k)
    ideal_dcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_relevant_count + 1))
    return {
        "precision_at_k": hit_count / k,
        "recall_at_k": hit_count / len(relevant),
        "mrr": reciprocal_rank,
        "ndcg_at_k": dcg / ideal_dcg if ideal_dcg else 0.0,
    }


def evaluate_benchmark(
    benchmark_path: Path,
    jobs_path: Path,
    skills_path: Path,
    taxonomy: SkillTaxonomy,
    k: int = 10,
) -> dict[str, Any]:
    """Evaluate manually judged candidate/job relevance queries from JSONL."""
    if not benchmark_path.is_file():
        raise FileNotFoundError(benchmark_path)
    query_metrics: list[dict[str, float]] = []
    query_ids: set[str] = set()
    query_id_order: list[str] = []
    with benchmark_path.open(encoding="utf-8") as benchmark_file:
        for line_number, line in enumerate(benchmark_file, start=1):
            if not line.strip():
                continue
            try:
                query = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"invalid JSON on benchmark line {line_number}") from error
            if not isinstance(query, dict):
                raise ValueError(f"benchmark line {line_number} must be a JSON object")
            query_id = query.get("query_id")
            candidate_skill_ids = query.get("candidate_skill_ids")
            relevant_job_ids = query.get("relevant_job_ids")
            if (
                not isinstance(query_id, str)
                or not query_id
                or query_id in query_ids
                or not isinstance(candidate_skill_ids, list)
                or not all(isinstance(value, str) for value in candidate_skill_ids)
                or not isinstance(relevant_job_ids, list)
                or not all(isinstance(value, str) for value in relevant_job_ids)
                or not relevant_job_ids
            ):
                raise ValueError(f"invalid or duplicate benchmark query on line {line_number}")
            query_ids.add(query_id)
            query_id_order.append(query_id)
            result = rank_jobs(
                candidate_skill_ids,
                jobs_path,
                skills_path,
                taxonomy,
                top_k=k,
                input_mode="manually_judged_benchmark_profile",
            )
            query_metrics.append(
                ranking_metrics(
                    [record["job_id"] for record in result["ranked_jobs"]],
                    relevant_job_ids,
                    k,
                )
            )

    if not query_metrics:
        raise ValueError("benchmark contains no judged queries")
    metric_names = list(query_metrics[0])
    return {
        "benchmark": benchmark_path.name,
        "queries_evaluated": len(query_metrics),
        "k": k,
        "relevance_source": "manually judged candidate/job pairs",
        "macro_metrics": {
            name: round(sum(metrics[name] for metrics in query_metrics) / len(query_metrics), 6)
            for name in metric_names
        },
        "per_query_metrics": [
            {"query_id": query_id, **metrics}
            for query_id, metrics in zip(query_id_order, query_metrics, strict=True)
        ],
    }
