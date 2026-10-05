"""Batch extraction and closed-set evaluation for the Phase 2 skill baseline."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from german_job_market.skills import SkillTaxonomy, extract_posting_skills


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _report_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.name


def run_extraction(
    input_path: Path,
    output_path: Path,
    taxonomy: SkillTaxonomy,
    report_path: Path,
    batch_size: int = 2048,
) -> dict[str, Any]:
    """Extract skill IDs for every posting and write a compact Parquet sidecar."""
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    if not input_path.is_file():
        raise FileNotFoundError(input_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    parquet_file = pq.ParquetFile(input_path)
    expected = {"job_id", "title", "description"}
    missing_columns = expected.difference(parquet_file.schema_arrow.names)
    if missing_columns:
        raise ValueError(f"input is missing required columns: {sorted(missing_columns)}")

    output_schema = pa.schema(
        [
            pa.field("job_id", pa.string(), nullable=False),
            pa.field("skill_ids", pa.list_(pa.string())),
        ]
    )
    counts: Counter[str] = Counter()
    records = 0
    records_with_skills = 0
    with pq.ParquetWriter(output_path, output_schema, compression="zstd") as writer:
        for batch in parquet_file.iter_batches(
            batch_size=batch_size, columns=["job_id", "title", "description"]
        ):
            values = batch.to_pydict()
            job_ids = values["job_id"]
            titles = values["title"]
            descriptions = values["description"]
            skill_rows = [
                extract_posting_skills(title, description, taxonomy)
                for title, description in zip(titles, descriptions, strict=True)
            ]
            for skill_row in skill_rows:
                counts.update(skill_row)
                records_with_skills += bool(skill_row)
            writer.write_table(
                pa.Table.from_arrays(
                    [
                        pa.array(job_ids, type=pa.string()),
                        pa.array(skill_rows, type=pa.list_(pa.string())),
                    ],
                    schema=output_schema,
                )
            )
            records += len(job_ids)

    skill_by_id = taxonomy.by_id
    report: dict[str, Any] = {
        "phase": 2,
        "task": "bilingual_rule_based_skill_extraction",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "taxonomy_version": taxonomy.version,
        "taxonomy_sha256": taxonomy.fingerprint,
        "taxonomy_size": len(taxonomy.skills),
        "input": _report_path(input_path),
        "input_sha256": file_sha256(input_path),
        "output": _report_path(output_path),
        "output_sha256": file_sha256(output_path),
        "records_processed": records,
        "records_with_skills": records_with_skills,
        "skill_assignments": sum(counts.values()),
        "unique_skills_observed": len(counts),
        "top_skills_by_posting_count": [
            {"skill_id": skill_id, "label": skill_by_id[skill_id].label, "count": count}
            for skill_id, count in counts.most_common(20)
        ],
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def _metrics(gold: set[tuple[str, str]], predicted: set[tuple[str, str]]) -> dict[str, float | int]:
    true_positive = len(gold & predicted)
    false_positive = len(predicted - gold)
    false_negative = len(gold - predicted)
    precision = (
        true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    )
    recall = (
        true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
    )
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
    return {
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "gold_count": len(gold),
        "predicted_count": len(predicted),
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def load_gold(path: Path, taxonomy: SkillTaxonomy) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    valid_ids = set(taxonomy.by_id)
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        record = json.loads(line)
        job_id = record.get("job_id")
        language = record.get("primary_language")
        skill_ids = record.get("skill_ids")
        if not isinstance(job_id, str) or not job_id:
            raise ValueError(f"gold line {line_number} has no job_id")
        if job_id in seen:
            raise ValueError(f"duplicate job_id in gold set: {job_id}")
        if language not in {"de", "en"}:
            raise ValueError(f"gold line {line_number} primary_language must be de or en")
        if not isinstance(skill_ids, list) or not all(
            isinstance(value, str) for value in skill_ids
        ):
            raise ValueError(f"gold line {line_number} skill_ids must be a string list")
        unknown_ids = set(skill_ids).difference(valid_ids)
        if unknown_ids:
            raise ValueError(
                f"gold line {line_number} contains unknown skill ids: {sorted(unknown_ids)}"
            )
        if len(skill_ids) != len(set(skill_ids)):
            raise ValueError(f"gold line {line_number} contains duplicate skill ids")
        seen.add(job_id)
        records.append({"job_id": job_id, "primary_language": language, "skill_ids": skill_ids})
    if not records:
        raise ValueError("gold set is empty")
    return records


def evaluate_extraction(
    input_path: Path,
    gold_path: Path,
    taxonomy: SkillTaxonomy,
    report_path: Path,
) -> dict[str, Any]:
    """Evaluate document-skill assignments against a curated closed-set label file."""
    gold_records = load_gold(gold_path, taxonomy)
    job_ids = [record["job_id"] for record in gold_records]
    connection = duckdb.connect()
    try:
        rows = connection.execute(
            """SELECT job_id, title, description FROM read_parquet(?)
               WHERE job_id IN (SELECT unnest(?))""",
            [str(input_path), job_ids],
        ).fetchall()
    finally:
        connection.close()

    documents = {row[0]: (row[1], row[2]) for row in rows}
    missing_ids = set(job_ids).difference(documents)
    if missing_ids:
        raise ValueError(f"gold IDs absent from source data: {sorted(missing_ids)}")

    gold_pairs: set[tuple[str, str]] = set()
    predicted_pairs: set[tuple[str, str]] = set()
    language_by_job = {record["job_id"]: record["primary_language"] for record in gold_records}
    for record in gold_records:
        job_id = record["job_id"]
        gold_pairs.update((job_id, skill_id) for skill_id in record["skill_ids"])
        title, description = documents[job_id]
        predicted_pairs.update(
            (job_id, skill_id) for skill_id in extract_posting_skills(title, description, taxonomy)
        )

    skill_by_id = taxonomy.by_id
    by_category: dict[str, dict[str, Any]] = {}
    categories = sorted({skill.category for skill in taxonomy.skills})
    for category in categories:
        gold_category = {
            (job_id, skill_id)
            for job_id, skill_id in gold_pairs
            if skill_by_id[skill_id].category == category
        }
        predicted_category = {
            (job_id, skill_id)
            for job_id, skill_id in predicted_pairs
            if skill_by_id[skill_id].category == category
        }
        if gold_category or predicted_category:
            by_category[category] = _metrics(gold_category, predicted_category)

    by_language = {
        language: _metrics(
            {pair for pair in gold_pairs if language_by_job[pair[0]] == language},
            {pair for pair in predicted_pairs if language_by_job[pair[0]] == language},
        )
        for language in ("de", "en")
    }
    report: dict[str, Any] = {
        "phase": 2,
        "task": "bilingual_rule_based_skill_extraction_evaluation",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "taxonomy_version": taxonomy.version,
        "taxonomy_sha256": taxonomy.fingerprint,
        "input_sha256": file_sha256(input_path),
        "gold_sha256": file_sha256(gold_path),
        "evaluation_unit": "posting-skill pair; one positive per skill per posting",
        "sample_size": len(gold_records),
        "language_record_counts": {
            language: sum(value == language for value in language_by_job.values())
            for language in ("de", "en")
        },
        "overall": _metrics(gold_pairs, predicted_pairs),
        "false_positive_pairs": [
            {"job_id": job_id, "skill_id": skill_id}
            for job_id, skill_id in sorted(predicted_pairs - gold_pairs)
        ],
        "false_negative_pairs": [
            {"job_id": job_id, "skill_id": skill_id}
            for job_id, skill_id in sorted(gold_pairs - predicted_pairs)
        ],
        "by_category": by_category,
        "by_primary_language": by_language,
        "annotation_limit": (
            "Small curated sample; labels require independent human review before external "
            "performance claims."
        ),
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report
