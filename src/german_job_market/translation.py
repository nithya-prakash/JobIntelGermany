"""Audit locally supplied German-English translation evaluation pairs."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_DIRECTIONS = {"de-en", "en-de"}
_TEXT_FIELDS = ("source", "reference", "hypothesis")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_record(value: Any) -> tuple[str, str] | str:
    if not isinstance(value, dict):
        return "record_not_object"
    segment_id = value.get("segment_id")
    if not isinstance(segment_id, str) or not segment_id.strip():
        return "missing_segment_id"
    direction = value.get("direction")
    if not isinstance(direction, str) or direction not in _DIRECTIONS:
        return "unsupported_direction"
    for field in _TEXT_FIELDS:
        text = value.get(field)
        if not isinstance(text, str) or not text.strip():
            return f"missing_{field}"
    return segment_id, direction


def _markdown(report: dict[str, Any]) -> str:
    pairs = report["pairs"]
    lines = [
        "# German Job Market Intelligence — translation evaluation readiness",
        "",
        f"Generated: {report['generated_at_utc']}",
        "",
        f"**Status:** {report['status']}.",
        "",
        "## Pair audit",
        "",
        f"- Pair file found: {pairs['file_found']}",
        f"- Records read: {pairs['records_read']:,}",
        f"- Valid aligned source/reference/hypothesis records: {pairs['valid_records']:,}",
        f"- Invalid records: {pairs['invalid_records']:,}",
        f"- German → English records: {pairs['direction_counts']['de-en']:,}",
        f"- English → German records: {pairs['direction_counts']['en-de']:,}",
        f"- Duplicate segment IDs: {pairs['duplicate_segment_ids']:,}",
        "",
        "## Evaluation",
        "",
        "- Translation model run: False",
        "- BLEU: None",
        "- chrF: None",
        f"- Reason: {report['evaluation']['reason']}",
        "",
        "Scores require independently translated references and hypotheses from a named model. "
        "This audit does not treat monolingual ads as translation pairs or produce sample scores.",
        "",
        "## Reproduction",
        "",
        "Run `.venv/bin/gjmi-translate audit` after adding a licensed JSONL pair file.",
        "",
    ]
    if pairs["invalid_reasons"]:
        lines.extend(
            ["Invalid record counts: " + json.dumps(pairs["invalid_reasons"], sort_keys=True), ""]
        )
    return "\n".join(lines)


def audit_translation_pairs(
    pairs_path: Path,
    json_path: Path,
    markdown_path: Path,
) -> dict[str, Any]:
    """Validate paired translation data without retaining text in reports."""
    records_read = 0
    blank_lines = 0
    valid_records = 0
    invalid_records = 0
    duplicate_segment_ids = 0
    direction_counts: Counter[str] = Counter()
    invalid_reasons: Counter[str] = Counter()
    seen_ids: set[str] = set()

    file_found = pairs_path.is_file()
    if file_found:
        with pairs_path.open(encoding="utf-8") as source:
            for line in source:
                if not line.strip():
                    blank_lines += 1
                    continue
                records_read += 1
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    invalid_records += 1
                    invalid_reasons["invalid_json"] += 1
                    continue
                validation = _validate_record(value)
                if isinstance(validation, str):
                    invalid_records += 1
                    invalid_reasons[validation] += 1
                    continue
                segment_id, direction = validation
                if segment_id in seen_ids:
                    duplicate_segment_ids += 1
                    invalid_records += 1
                    invalid_reasons["duplicate_segment_id"] += 1
                    continue
                seen_ids.add(segment_id)
                valid_records += 1
                direction_counts[direction] += 1

    if valid_records == 0:
        status = "not_evaluable"
        reason = (
            "no valid aligned source, independent reference, and model hypothesis "
            "records are available"
        )
    elif invalid_records:
        status = "input_needs_review"
        reason = "some records failed validation; only clean benchmark input can be evaluated"
    else:
        status = "pairs_validated_scoring_not_implemented"
        reason = (
            "pairs are structurally valid; translation generation and metric calculation "
            "are outside this audit"
        )

    report: dict[str, Any] = {
        "phase": 7,
        "audit_type": "translation_evaluation_pair_readiness",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "inputs": {
            "pairs_path": pairs_path.name,
            "sha256": _sha256(pairs_path) if file_found else None,
        },
        "status": status,
        "pairs": {
            "file_found": file_found,
            "records_read": records_read,
            "blank_lines": blank_lines,
            "valid_records": valid_records,
            "invalid_records": invalid_records,
            "duplicate_segment_ids": duplicate_segment_ids,
            "direction_counts": {
                direction: direction_counts[direction] for direction in sorted(_DIRECTIONS)
            },
            "invalid_reasons": dict(sorted(invalid_reasons.items())),
        },
        "evaluation": {
            "model_run": False,
            "metrics": None,
            "reason": reason,
        },
    }
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(_markdown(report), encoding="utf-8")
    return report
