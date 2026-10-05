import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from german_job_market.matching import evaluate_benchmark, rank_jobs, ranking_metrics
from german_job_market.skills import load_taxonomy

ROOT = Path(__file__).resolve().parents[1]


def _write_matching_fixture(
    directory: Path, sidecar_ids: list[str] | None = None
) -> tuple[Path, Path]:
    jobs_path = directory / "jobs.parquet"
    skills_path = directory / "skills.parquet"
    job_ids = ["a", "b", "c", "d", "e"]
    pq.write_table(
        pa.table(
            {
                "job_id": job_ids,
                "title": ["Full stack" for _ in job_ids],
                "description": ["You will work with Python, SQL and Java daily." for _ in job_ids],
                "source_url": [f"https://example.test/{job_id}" for job_id in job_ids],
                "company": [None for _ in job_ids],
                "location": [None for _ in job_ids],
                "remote_type": [None for _ in job_ids],
                "employment_type": [None for _ in job_ids],
            }
        ),
        jobs_path,
    )
    skills = [
        ["python", "sql", "java"],
        ["python"],
        ["sql", "java"],
        ["python", "sql"],
        ["java"],
    ]
    pq.write_table(
        pa.table(
            {
                "job_id": sidecar_ids or job_ids,
                "skill_ids": pa.array(skills, type=pa.list_(pa.string())),
            }
        ),
        skills_path,
    )
    return jobs_path, skills_path


def test_skill_overlap_ranks_jobs_and_explains_gaps(tmp_path: Path) -> None:
    jobs_path, skills_path = _write_matching_fixture(tmp_path)
    taxonomy = load_taxonomy(ROOT / "configs/skill_taxonomy.toml")

    result = rank_jobs(["python", "sql"], jobs_path, skills_path, taxonomy, top_k=3)

    assert [job["job_id"] for job in result["ranked_jobs"]] == ["d", "a", "b"]
    assert result["ranked_jobs"][0]["match_score"] == 1.0
    assert result["ranked_jobs"][1]["score_components"]["harmonic_f1"] == 0.8
    gap = result["ranked_jobs"][1]["not_found_in_candidate_profile"][0]
    assert gap["skill_id"] == "java"
    assert gap["corpus_posting_count"] == 3
    assert gap["occurrences_in_ad"] == 1
    assert "Java" in gap["snippets"][0]
    assert result["ranked_jobs"][1]["requirement_status"] == "unverified"
    assert result["ranked_jobs"][2]["candidate_skills_not_in_job"][0]["skill_id"] == "sql"
    assert "probability of hiring" in result["score_interpretation"]
    assert result["scan_summary"]["postings_scanned"] == 5


def test_matching_rejects_duplicate_sidecar_ids(tmp_path: Path) -> None:
    jobs_path, skills_path = _write_matching_fixture(
        tmp_path, sidecar_ids=["a", "a", "c", "d", "e"]
    )
    taxonomy = load_taxonomy(ROOT / "configs/skill_taxonomy.toml")

    with pytest.raises(ValueError, match="not one-to-one"):
        rank_jobs(["python"], jobs_path, skills_path, taxonomy)


def test_manual_ranking_metrics_use_binary_relevance() -> None:
    metrics = ranking_metrics(["a", "b", "c"], ["b", "c"], k=2)
    assert metrics["precision_at_k"] == 0.5
    assert metrics["recall_at_k"] == 0.5
    assert metrics["mrr"] == 0.5
    assert round(metrics["ndcg_at_k"], 6) == 0.386853


def test_benchmark_evaluator_reports_macro_metrics(tmp_path: Path) -> None:
    jobs_path, skills_path = _write_matching_fixture(tmp_path)
    benchmark_path = tmp_path / "judged.jsonl"
    benchmark_path.write_text(
        json.dumps(
            {
                "query_id": "fixture-query",
                "candidate_skill_ids": ["python", "sql"],
                "relevant_job_ids": ["d", "a"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    taxonomy = load_taxonomy(ROOT / "configs/skill_taxonomy.toml")

    result = evaluate_benchmark(benchmark_path, jobs_path, skills_path, taxonomy, k=3)

    assert result["queries_evaluated"] == 1
    assert result["per_query_metrics"][0]["query_id"] == "fixture-query"
    assert result["macro_metrics"]["precision_at_k"] == round(2 / 3, 6)
    assert result["macro_metrics"]["recall_at_k"] == 1.0
    assert result["macro_metrics"]["mrr"] == 1.0
    assert result["macro_metrics"]["ndcg_at_k"] == 1.0
