"""Phase 11: reviewable benchmark infrastructure for skill extraction and job matching.

This module creates samples, blank annotation packs, validators and scorers. It never creates
labels: without human-supplied files every scorer reports that nothing was measured.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import random
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from german_job_market.matching import rank_jobs
from german_job_market.skill_pipeline import _metrics, file_sha256, load_gold
from german_job_market.skills import SkillTaxonomy, extract_posting_skills

SEED = 20261004
SPLIT_DEV_FRACTION = 0.4
BOOTSTRAP_ITERATIONS = 1000
MIN_MATCH_QUERIES = 20
TARGET_MATCH_QUERIES = "30-50"
GRADES = (0, 1, 2, 3)  # 0 irrelevant, 1 weak, 2 good, 3 excellent
RELEVANT_GRADE = 2  # binary metrics count grade >= 2 as relevant
PILOT_PER_STRATUM = 16
MIN_DOUBLE_ANNOTATED_JOBS = 20
AMBIGUOUS_PATTERN = r"\b(Go|R|Spring|Excel)\b"
LABELS = {"required", "mentioned"}
_DE = {"und", "der", "die", "das", "mit", "für", "von", "sie", "wir", "ihre", "oder", "ein"}
_EN = {"and", "the", "with", "for", "you", "we", "your", "or", "of", "to", "a", "our"}


def _hash(seed: int, key: str) -> str:
    return hashlib.sha256(f"{seed}:{key}".encode()).hexdigest()


def heuristic_language(text: str) -> str:
    """Stopword-count guess used only for stratified sampling, never as a reported label."""
    words = re.findall(r"[a-zäöüß]+", text[:1500].lower())
    de, en = sum(w in _DE for w in words), sum(w in _EN for w in words)
    return "de" if de > en else "en"


def _split(seed: int, job_id: str) -> str:
    bucket = int(_hash(seed, "split:" + job_id)[:8], 16) / 0xFFFFFFFF
    return "dev" if bucket < SPLIT_DEV_FRACTION else "test"


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in records),
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def build_skill_sample(
    jobs_path: Path,
    skills_path: Path,
    pilot_gold_path: Path,
    taxonomy: SkillTaxonomy,
    manifest_path: Path,
    pack_path: Path,
    seed: int = SEED,
    per_cell: int = 30,
    n_ambiguous: int = 60,
) -> dict[str, Any]:
    """Seeded stratified sample. Manifest holds no ad text; the reading pack stays local."""
    pilot_ids = {r["job_id"] for r in load_gold(pilot_gold_path, taxonomy)}
    con = duckdb.connect()
    try:
        rows = con.execute(
            """SELECT j.job_id, len(s.skill_ids) > 0, left(j.description, 1500)
               FROM read_parquet(?) j JOIN read_parquet(?) s USING (job_id)
               WHERE j.description IS NOT NULL AND length(j.description) > 300
               ORDER BY md5(? || j.job_id) LIMIT 8000""",
            [str(jobs_path), str(skills_path), str(seed)],
        ).fetchall()
        ambiguous = {
            r[0]
            for r in con.execute(
                """SELECT job_id FROM read_parquet(?)
                   WHERE regexp_matches(description, ?)
                   ORDER BY md5(? || job_id) LIMIT 600""",
                [str(jobs_path), AMBIGUOUS_PATTERN, str(seed)],
            ).fetchall()
        }
    finally:
        con.close()

    chosen: dict[str, dict[str, Any]] = {}
    cells: dict[tuple[str, bool], int] = {}
    for job_id, has_skill, prefix in rows:
        if job_id in pilot_ids or job_id in chosen:
            continue
        key = (heuristic_language(prefix), bool(has_skill))
        if cells.get(key, 0) < per_cell:
            cells[key] = cells.get(key, 0) + 1
            chosen[job_id] = {
                "stratum": f"{key[0]}_{'sidecar_hit' if key[1] else 'sidecar_empty'}",
                "heuristic_language": key[0],
            }
    added = 0
    for job_id in sorted(ambiguous, key=lambda value: _hash(seed, value)):
        if added >= n_ambiguous:
            break
        if job_id not in pilot_ids and job_id not in chosen:
            chosen[job_id] = {"stratum": "ambiguous_token", "heuristic_language": "unknown"}
            added += 1
    manifest = [
        {"job_id": job_id, "split": _split(seed, job_id), **info}
        for job_id, info in sorted(chosen.items())
    ]
    _write_jsonl(manifest_path, manifest)

    con = duckdb.connect()
    try:
        pack = con.execute(
            "SELECT job_id, title, description FROM read_parquet(?) "
            "WHERE job_id IN (SELECT unnest(?)) ORDER BY job_id",
            [str(jobs_path), [m["job_id"] for m in manifest]],
        ).fetchall()
    finally:
        con.close()
    _write_jsonl(
        pack_path,
        [{"job_id": a, "title": b, "description": c, "skills": {}} for a, b, c in pack],
    )
    strata: dict[str, int] = {}
    for m in manifest:
        strata[m["stratum"]] = strata.get(m["stratum"], 0) + 1
    return {
        "seed": seed,
        "sample_size": len(manifest),
        "strata": strata,
        "splits": {s: sum(m["split"] == s for m in manifest) for s in ("dev", "test")},
        "pilot_ids_excluded": len(pilot_ids),
        "manifest_sha256": file_sha256(manifest_path),
    }


def _load_annotations(
    path: Path, manifest_ids: set[str], taxonomy: SkillTaxonomy
) -> dict[str, set[str]]:
    """Return job_id -> set of present skill IDs; raise on any structural problem."""
    result: dict[str, set[str]] = {}
    for n, rec in enumerate(_read_jsonl(path), start=1):
        job_id, skills = rec.get("job_id"), rec.get("skills")
        if job_id not in manifest_ids:
            raise ValueError(f"{path.name} line {n}: job_id not in manifest (leakage guard)")
        if job_id in result:
            raise ValueError(f"{path.name} line {n}: duplicate job_id {job_id}")
        if not isinstance(skills, dict):
            raise ValueError(f"{path.name} line {n}: skills must be an object")
        bad = [k for k in skills if k not in taxonomy.by_id]
        if bad:
            raise ValueError(f"{path.name} line {n}: unknown skill ids {bad}")
        if any(v not in LABELS for v in skills.values()):
            raise ValueError(f"{path.name} line {n}: labels must be one of {sorted(LABELS)}")
        result[job_id] = set(skills)
    return result


def check_annotations(
    manifest_path: Path, annotations_dir: Path, taxonomy: SkillTaxonomy
) -> dict[str, Any]:
    """Validate every annotation file and report per-file progress against the manifest."""
    manifest = {m["job_id"]: m for m in _read_jsonl(manifest_path)}
    files: dict[str, Any] = {}
    for path in sorted(annotations_dir.glob("*.jsonl")):
        done = _load_annotations(path, set(manifest), taxonomy)
        files[path.stem] = {
            "valid": True,
            "annotated": len(done),
            "remaining": len(manifest) - len(done),
            "_done": sorted(done),
            "remaining_by_split": {
                s: sum(1 for j, m in manifest.items() if m["split"] == s and j not in done)
                for s in ("dev", "test")
            },
        }
    pilot_path = manifest_path.with_name("pilot.jsonl")
    pilot = {m["job_id"] for m in _read_jsonl(pilot_path)} if pilot_path.is_file() else set()
    for info in files.values():
        finished = set(info.pop("_done"))
        if pilot:
            info["pilot_remaining"] = len(pilot - finished)
    return {"manifest_jobs": len(manifest), "pilot_jobs": len(pilot), "files": files}


def build_pilot(
    manifest_path: Path, pilot_path: Path, per_stratum: int = PILOT_PER_STRATUM
) -> dict[str, Any]:
    """Deterministic stratified pilot subset of the manifest (IDs only)."""
    by_stratum: dict[str, list[dict[str, Any]]] = {}
    for m in _read_jsonl(manifest_path):
        by_stratum.setdefault(m["stratum"], []).append(m)
    chosen = [
        m
        for stratum in sorted(by_stratum)
        for m in sorted(by_stratum[stratum], key=lambda r: _hash(SEED, "pilot:" + r["job_id"]))[
            :per_stratum
        ]
    ]
    _write_jsonl(pilot_path, sorted(chosen, key=lambda r: r["job_id"]))
    return {"pilot_size": len(chosen), "per_stratum": per_stratum}


def import_annotation_csv(
    csv_path: Path,
    annotator: str,
    manifest_path: Path,
    annotations_dir: Path,
    taxonomy: SkillTaxonomy,
) -> dict[str, Any]:
    """Convert job_id,skill,label rows to annotation JSONL; blank skill = reviewed, none found."""
    if not re.fullmatch(r"[A-Za-z0-9_-]+", annotator) or annotator == "adjudicated":
        raise ValueError("annotator must be alphanumeric and not 'adjudicated'")
    records: dict[str, dict[str, str]] = {}
    with csv_path.open(encoding="utf-8", newline="") as handle:
        for n, row in enumerate(csv.DictReader(handle), start=2):
            job_id = (row.get("job_id") or "").strip()
            skill = (row.get("skill") or "").strip()
            label = (row.get("label") or "").strip().lower()
            skills = records.setdefault(job_id, {})
            if skill:
                if skill in skills:
                    raise ValueError(f"line {n}: duplicate {job_id}/{skill}")
                skills[skill] = label
    out = annotations_dir / f"{annotator}.jsonl"
    _write_jsonl(
        out,
        [{"job_id": j, "annotator": annotator, "skills": records[j]} for j in sorted(records)],
    )
    try:  # validate against manifest/taxonomy; remove the file if invalid
        _load_annotations(out, {m["job_id"] for m in _read_jsonl(manifest_path)}, taxonomy)
    except ValueError:
        out.unlink()
        raise
    return {"written": str(out), "jobs": len(records)}


def _cohen_kappa(a: dict[str, set[str]], b: dict[str, set[str]], n_skills: int) -> float | None:
    shared = sorted(set(a) & set(b))
    if not shared:
        return None
    total = len(shared) * n_skills
    both = sum(len(a[j] & b[j]) for j in shared)
    only_a = sum(len(a[j] - b[j]) for j in shared)
    only_b = sum(len(b[j] - a[j]) for j in shared)
    observed = 1 - (only_a + only_b) / total
    pa, pb = (both + only_a) / total, (both + only_b) / total
    expected = pa * pb + (1 - pa) * (1 - pb)
    return None if expected == 1 else (observed - expected) / (1 - expected)


def _micro(counts: list[tuple[int, int, int]]) -> dict[str, float]:
    tp, fp, fn = (sum(c[i] for c in counts) for i in range(3))
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return {"precision": p, "recall": r, "f1": 2 * p * r / (p + r) if p + r else 0.0}


def _bootstrap(counts: list[tuple[int, int, int]], seed: int) -> dict[str, list[float]]:
    rng = random.Random(seed)
    draws = [_micro(rng.choices(counts, k=len(counts))) for _ in range(BOOTSTRAP_ITERATIONS)]
    out: dict[str, list[float]] = {}
    for key in ("precision", "recall", "f1"):
        values = sorted(d[key] for d in draws)
        out[key] = [values[int(0.025 * len(values))], values[int(0.975 * len(values)) - 1]]
    return out


def score_skill_benchmark(
    manifest_path: Path,
    annotations_dir: Path,
    jobs_path: Path,
    taxonomy: SkillTaxonomy,
    report_path: Path,
    seed: int = SEED,
) -> dict[str, Any]:
    """Score the extractor against adjudicated labels; report 'no_labels' if none exist."""
    manifest = {m["job_id"]: m for m in _read_jsonl(manifest_path)}
    ids = set(manifest)
    report: dict[str, Any] = {
        "phase": 11,
        "task": "skill_extraction_benchmark_v2",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "seed": seed,
        "manifest_sha256": file_sha256(manifest_path),
        "taxonomy_sha256": taxonomy.fingerprint,
        "sample_size": len(manifest),
    }
    gold_file = annotations_dir / "adjudicated.jsonl"
    if not gold_file.is_file():
        report.update(
            status="no_labels",
            note="No adjudicated.jsonl found. Nothing was measured; no metric is reported.",
        )
        _finish(report, report_path)
        return report
    gold = _load_annotations(gold_file, ids, taxonomy)
    annotators = {
        p.stem: _load_annotations(p, ids, taxonomy)
        for p in sorted(annotations_dir.glob("*.jsonl"))
        if p.name != "adjudicated.jsonl"
    }
    kappas: dict[str, float | None] = {}
    names = sorted(annotators)
    for i, x in enumerate(names):
        for y in names[i + 1 :]:
            kappas[f"{x}__{y}"] = _cohen_kappa(annotators[x], annotators[y], len(taxonomy.by_id))
    overlap = max(
        (
            len(set(annotators[x]) & set(annotators[y]))
            for i, x in enumerate(names)
            for y in names[i + 1 :]
        ),
        default=0,
    )
    reviewed = len(names) >= 2 and overlap >= MIN_DOUBLE_ANNOTATED_JOBS
    report["status"] = "multi_annotator_reviewed" if reviewed else "single_annotator_unreviewed"
    report["inter_annotator_cohen_kappa"] = kappas
    report["double_annotated_jobs"] = overlap

    con = duckdb.connect()
    try:
        docs = {
            r[0]: (r[1], r[2])
            for r in con.execute(
                "SELECT job_id, title, description FROM read_parquet(?) "
                "WHERE job_id IN (SELECT unnest(?))",
                [str(jobs_path), sorted(gold)],
            ).fetchall()
        }
    finally:
        con.close()
    per_job: dict[str, tuple[int, int, int]] = {}
    pairs: dict[str, tuple[set[tuple[str, str]], set[tuple[str, str]]]] = {}
    for job_id, truth in gold.items():
        pred = set(extract_posting_skills(*docs[job_id], taxonomy))
        per_job[job_id] = (len(truth & pred), len(pred - truth), len(truth - pred))
        for split in ("all", manifest[job_id]["split"], "stratum:" + manifest[job_id]["stratum"]):
            g, p = pairs.setdefault(split, (set(), set()))
            g.update((job_id, s) for s in truth)
            p.update((job_id, s) for s in pred)
    report["labelled_jobs"] = len(gold)
    if len(gold) < len(manifest):
        report["partial_coverage_note"] = (
            "Only a subset of the manifest is labelled; results describe that subset only."
        )
    report["coverage_of_manifest"] = len(gold) / len(manifest)
    report["results"] = {}
    for split, (g, p) in sorted(pairs.items()):
        members = [
            j
            for j in gold
            if split == "all"
            or manifest[j]["split"] == split
            or "stratum:" + manifest[j]["stratum"] == split
        ]
        report["results"][split] = {
            "jobs": len(members),
            **_metrics(g, p),
            "bootstrap_95ci": _bootstrap([per_job[j] for j in members], seed),
        }
    by_cat: dict[str, dict[str, Any]] = {}
    for cat in sorted({s.category for s in taxonomy.skills}):
        g = {x for x in pairs["all"][0] if taxonomy.by_id[x[1]].category == cat}
        p = {x for x in pairs["all"][1] if taxonomy.by_id[x[1]].category == cat}
        if g or p:
            by_cat[cat] = _metrics(g, p)
    report["by_category_all_labelled"] = by_cat
    report["caveat"] = (
        "Test split must be scored once per taxonomy version; repeated tuning on it voids it."
    )
    _finish(report, report_path)
    return report


def _finish(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def validate_match_queries(queries: list[dict[str, Any]], taxonomy: SkillTaxonomy) -> None:
    splits: dict[str, str] = {}
    seen: set[str] = set()
    for q in queries:
        if q["query_id"] in seen:
            raise ValueError(f"duplicate query_id {q['query_id']}")
        seen.add(q["query_id"])
        if q["split"] not in {"dev", "test"}:
            raise ValueError(f"{q['query_id']}: split must be dev or test")
        if splits.setdefault(q["candidate_id"], q["split"]) != q["split"]:
            raise ValueError(f"candidate {q['candidate_id']} appears in both splits")
        if q.get("source_job_id") is not None and not isinstance(q["source_job_id"], str):
            raise ValueError(f"{q['query_id']}: source_job_id must be a string")
        bad = [s for s in q["candidate_skill_ids"] if s not in taxonomy.by_id]
        if bad:
            raise ValueError(f"{q['query_id']}: unknown skill ids {bad}")


def build_match_pool(
    queries_path: Path,
    jobs_path: Path,
    skills_path: Path,
    taxonomy: SkillTaxonomy,
    sheet_path: Path,
    provenance_path: Path,
    pack_path: Path,
    k: int = 10,
    seed: int = SEED,
) -> dict[str, Any]:
    """Pool matcher top-K with seeded random jobs; sheet is blinded and shuffled."""
    queries = _read_jsonl(queries_path)
    validate_match_queries(queries, taxonomy)
    con = duckdb.connect()
    try:
        all_ids = [
            r[0]
            for r in con.execute(
                "SELECT job_id FROM read_parquet(?) ORDER BY md5(? || job_id) LIMIT 5000",
                [str(jobs_path), str(seed)],
            ).fetchall()
        ]
    finally:
        con.close()
    sheet: list[dict[str, Any]] = []
    prov: dict[str, dict[str, list[str]]] = {}
    for q in queries:
        ranked = rank_jobs(
            q["candidate_skill_ids"],
            jobs_path,
            skills_path,
            taxonomy,
            top_k=k,
            exclude_job_ids={q["source_job_id"]} if q.get("source_job_id") else None,
            input_mode="manually_judged_benchmark_profile",
        )["ranked_jobs"]
        matcher = [r["job_id"] for r in ranked]
        rng = random.Random(_hash(seed, q["query_id"]))
        banned = set(matcher) | ({q["source_job_id"]} if q.get("source_job_id") else set())
        baseline = [j for j in rng.sample(all_ids, k + k + 1) if j not in banned][:k]
        prov[q["query_id"]] = {"matcher": matcher, "random": baseline}
        pool = sorted(set(matcher + baseline), key=lambda j: _hash(seed, q["query_id"] + j))
        sheet += [
            {"query_id": q["query_id"], "job_id": j, "grade": None, "judge": None} for j in pool
        ]
    _write_jsonl(sheet_path, sheet)
    provenance_path.write_text(json.dumps(prov, indent=1, sort_keys=True) + "\n")
    con = duckdb.connect()
    try:
        rows = con.execute(
            "SELECT job_id, title, company, left(description, 3000) FROM read_parquet(?) "
            "WHERE job_id IN (SELECT unnest(?))",
            [str(jobs_path), sorted({r["job_id"] for r in sheet})],
        ).fetchall()
    finally:
        con.close()
    _write_jsonl(
        pack_path,
        [{"job_id": a, "title": b, "company": c, "description": d} for a, b, c, d in rows],
    )
    return {"queries": len(queries), "pooled_pairs": len(sheet), "k": k}


def graded_metrics(ranked: list[str], grades: dict[str, int], k: int) -> dict[str, float]:
    top = ranked[:k]
    gains = [grades.get(j, 0) for j in top]
    dcg = sum((2**g - 1) / math.log2(i + 2) for i, g in enumerate(gains))
    ideal = sorted(grades.values(), reverse=True)[:k]
    idcg = sum((2**g - 1) / math.log2(i + 2) for i, g in enumerate(ideal))
    relevant_total = sum(g >= RELEVANT_GRADE for g in grades.values())
    hits = [g >= RELEVANT_GRADE for g in gains]
    return {
        "precision_at_k": sum(hits) / k,
        "recall_at_k_pooled": sum(hits) / relevant_total if relevant_total else 0.0,
        "mrr": next((1 / (i + 1) for i, h in enumerate(hits) if h), 0.0),
        "ndcg_at_k": dcg / idcg if idcg else 0.0,
    }


def score_matching_benchmark(
    queries_path: Path,
    sheet_path: Path,
    provenance_path: Path,
    taxonomy: SkillTaxonomy,
    report_path: Path,
    k: int = 10,
    seed: int = SEED,
) -> dict[str, Any]:
    """Compare matcher vs random baseline on human grades; refuse if too few judged queries."""
    report: dict[str, Any] = {
        "phase": 11,
        "task": "matching_benchmark",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "k": k,
        "minimum_queries": MIN_MATCH_QUERIES,
        "target_queries": TARGET_MATCH_QUERIES,
        "relevant_grade_for_binary_metrics": RELEVANT_GRADE,
    }
    if not (queries_path.is_file() and sheet_path.is_file() and provenance_path.is_file()):
        report.update(status="no_labels", note="Queries, judged sheet or provenance missing.")
        _finish(report, report_path)
        return report
    queries = {q["query_id"]: q for q in _read_jsonl(queries_path)}
    validate_match_queries(list(queries.values()), taxonomy)
    prov = json.loads(provenance_path.read_text())
    grades: dict[str, dict[str, int]] = {}
    incomplete: set[str] = set()
    for row in _read_jsonl(sheet_path):
        if row["query_id"] not in queries:
            raise ValueError(f"unknown query_id {row['query_id']}")
        if row["grade"] is None:
            incomplete.add(row["query_id"])
        elif row["grade"] in GRADES:
            grades.setdefault(row["query_id"], {})[row["job_id"]] = row["grade"]
        else:
            raise ValueError("grade must be 0, 1, 2, 3 or null")
    for qid, q in queries.items():
        src = q.get("source_job_id")
        if src and any(src in jobs for jobs in prov.get(qid, {}).values()):
            raise ValueError(f"{qid}: source_job_id appears in its own ranking (leakage)")
    complete = sorted(q for q in grades if q not in incomplete)
    report["queries_total"] = len(queries)
    report["queries_fully_judged"] = len(complete)
    if len(complete) < MIN_MATCH_QUERIES:
        report.update(
            status="insufficient_labels",
            note=f"Need >= {MIN_MATCH_QUERIES} fully judged queries; no metric is reported.",
        )
        _finish(report, report_path)
        return report
    report["status"] = "scored"
    report["systems"] = {}
    for system in ("matcher", "random"):
        per_q = [graded_metrics(prov[q][system], grades[q], k) for q in complete]
        agg: dict[str, Any] = {}
        for metric in per_q[0]:
            vals = [m[metric] for m in per_q]
            rng = random.Random(seed)
            boots = sorted(
                sum(rng.choices(vals, k=len(vals))) / len(vals) for _ in range(BOOTSTRAP_ITERATIONS)
            )
            agg[metric] = {
                "mean": sum(vals) / len(vals),
                "bootstrap_95ci": [
                    boots[int(0.025 * len(boots))],
                    boots[int(0.975 * len(boots)) - 1],
                ],
            }
        report["systems"][system] = agg
    report["caveat"] = (
        "Recall is relative to pooled, judged jobs only. Queries are split by candidate; "
        "score the test split once."
    )
    _finish(report, report_path)
    return report
