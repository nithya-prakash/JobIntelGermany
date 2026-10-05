"""Audit whether the current skill labels can support LLM fine-tuning."""

from __future__ import annotations

import importlib.util
import json
import platform
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

_RUNTIME_PACKAGES = ("torch", "transformers", "peft", "trl", "bitsandbytes")


def _load_gold(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if path.is_file():
        with path.open(encoding="utf-8") as source:
            records = [json.loads(line) for line in source if line.strip()]
    job_ids = [record.get("job_id") for record in records]
    if any(not isinstance(job_id, str) or not job_id for job_id in job_ids):
        raise ValueError("gold labels require a non-empty job_id on every record")
    if len(job_ids) != len(set(job_ids)):
        raise ValueError("gold labels contain duplicate job_id values")
    languages = [record.get("primary_language") for record in records]
    if any(language not in {"de", "en"} for language in languages):
        raise ValueError("gold labels require primary_language 'de' or 'en'")
    skill_counts: list[int] = []
    for record in records:
        skills = record.get("skill_ids")
        if not isinstance(skills, list) or any(not isinstance(skill, str) for skill in skills):
            raise ValueError("gold labels require skill_ids as a string array")
        skill_counts.append(len(skills))
    summary = {
        "file_found": path.is_file(),
        "records": len(records),
        "positive_skill_labels": sum(skill_counts),
        "language_record_counts": {
            language: sum(value == language for value in languages) for language in ("de", "en")
        },
        "annotation_status": (
            "agent-assisted; not independently or double coded"
            if path.is_file()
            else "not available"
        ),
    }
    return records, summary


def _audit_weak_label_overlap(sidecar_path: Path, job_ids: list[str]) -> dict[str, Any]:
    if not sidecar_path.is_file():
        return {"file_found": False, "rows": 0, "distinct_job_ids": 0, "gold_job_ids_present": 0}
    if not job_ids:
        connection = duckdb.connect()
        try:
            row = connection.execute(
                "SELECT count(*), count(DISTINCT job_id) FROM read_parquet(?)",
                [str(sidecar_path)],
            ).fetchone()
        finally:
            connection.close()
        assert row is not None
        return {
            "file_found": True,
            "rows": int(row[0]),
            "distinct_job_ids": int(row[1]),
            "gold_job_ids_present": 0,
        }

    connection = duckdb.connect()
    try:
        row = connection.execute(
            """SELECT count(*), count(DISTINCT job_id),
                      count(DISTINCT job_id) FILTER (
                          WHERE job_id IN (SELECT unnest(?))
                      )
               FROM read_parquet(?)""",
            [job_ids, str(sidecar_path)],
        ).fetchone()
    finally:
        connection.close()
    assert row is not None
    return {
        "file_found": True,
        "rows": int(row[0]),
        "distinct_job_ids": int(row[1]),
        "gold_job_ids_present": int(row[2]),
    }


def _baseline_summary(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    report = json.loads(path.read_text(encoding="utf-8"))
    return {
        "task": report.get("task"),
        "sample_size": report.get("sample_size"),
        "language_record_counts": report.get("language_record_counts"),
        "overall": report.get("overall"),
        "by_primary_language": report.get("by_primary_language"),
        "annotation_limit": report.get("annotation_limit"),
    }


def _markdown(report: dict[str, Any]) -> str:
    labels = report["gold_labels"]
    overlap = report["weak_label_overlap"]
    runtime = report["runtime"]
    baseline = report["baseline"]
    available_packages = (
        ", ".join(name for name, available in runtime["packages"].items() if available) or "none"
    )
    lines = [
        "# German Job Market Intelligence — LLM fine-tuning readiness",
        "",
        f"Generated: {report['generated_at_utc']}",
        "",
        f"**Decision:** {report['decision']}. No model was fine-tuned.",
        "",
        "## Labeled data",
        "",
        f"- Curated postings: {labels['records']:,}",
        f"- Positive posting-skill labels: {labels['positive_skill_labels']:,}",
        f"- German / English postings: {labels['language_record_counts']['de']} / "
        f"{labels['language_record_counts']['en']}",
        f"- Annotation status: {labels['annotation_status']}",
        "",
        "The label file is a small challenge sample, not a train/validation/test dataset. "
        "No split was created and no test set was used for model selection.",
        "",
        "## Existing baseline",
        "",
    ]
    if baseline is None:
        lines.append("No baseline report was available.")
    else:
        overall = baseline["overall"]
        lines.extend(
            [
                f"Rule-based baseline on the same sample: precision {overall['precision']:.4f}, "
                f"recall {overall['recall']:.4f}, F1 {overall['f1']:.4f}.",
                f"Sample size: {baseline['sample_size']}; labels need independent human review.",
            ]
        )
    lines.extend(
        [
            "",
            "## Leakage and runtime checks",
            "",
            f"- Gold postings also in Phase 2 weak-label sidecar: "
            f"{overlap['gold_job_ids_present']} / {labels['records']}.",
            f"- Python runtime: {runtime['platform']}.",
            f"- Fine-tuning packages available: {available_packages}.",
            "",
            "Using the full weak-label sidecar for training would include the curated evaluation "
            "postings. Those labels were generated by the existing rule-based extractor, so this "
            "would both contaminate evaluation and teach the LLM to imitate the baseline.",
            "",
            "## Decision blockers",
            "",
        ]
    )
    lines.extend(f"- {blocker}" for blocker in report["blockers"])
    lines.extend(
        [
            "",
            "Fine-tuned model metrics are not applicable: no model, split, or training run "
            "was created.",
            "",
            "## Reproduction",
            "",
            "```bash",
            ".venv/bin/gjmi-skills evaluate --report reports/phase8/extraction_baseline.json",
            ".venv/bin/gjmi-llm audit",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def audit_finetuning_readiness(
    gold_path: Path,
    weak_labels_path: Path,
    baseline_path: Path,
    json_path: Path,
    markdown_path: Path,
) -> dict[str, Any]:
    """Measure data and local runtime readiness; never trains or downloads a model."""
    gold_records, gold_summary = _load_gold(gold_path)
    weak_overlap = _audit_weak_label_overlap(
        weak_labels_path, [record["job_id"] for record in gold_records]
    )
    baseline = _baseline_summary(baseline_path)
    packages = {name: importlib.util.find_spec(name) is not None for name in _RUNTIME_PACKAGES}
    blockers = [
        f"the {gold_summary['records']}-posting challenge sample does not support a "
        "credible held-out comparison",
        "gold annotations have not been independently reviewed",
        "no pre-registered train/validation/test split exists",
    ]
    if weak_overlap["gold_job_ids_present"]:
        blockers.append(
            "curated evaluation postings overlap the weak-label sidecar; using it for training "
            "leaks evaluation examples"
        )
    missing_packages = [name for name, available in packages.items() if not available]
    if missing_packages:
        blockers.append(f"fine-tuning runtime packages are missing: {', '.join(missing_packages)}")
    if baseline is None:
        blockers.append("no measured rule-based baseline report is available")
    report: dict[str, Any] = {
        "phase": 8,
        "audit_type": "llm_finetuning_readiness",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "inputs": {
            "gold_path": gold_path.name,
            "weak_labels_path": weak_labels_path.name,
            "baseline_path": baseline_path.name,
        },
        "decision": "blocked_no_finetuning",
        "gold_labels": gold_summary,
        "weak_label_overlap": weak_overlap,
        "runtime": {"platform": platform.platform(), "packages": packages},
        "baseline": baseline,
        "train_validation_test_split": None,
        "fine_tuned_model": {"trained": False, "metrics": None},
        "blockers": blockers,
    }
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(_markdown(report), encoding="utf-8")
    return report
