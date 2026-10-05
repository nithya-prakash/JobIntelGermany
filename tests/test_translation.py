import json
from pathlib import Path

from german_job_market.translation import audit_translation_pairs


def test_translation_audit_reports_missing_benchmark_without_scores(tmp_path: Path) -> None:
    report = audit_translation_pairs(
        tmp_path / "missing.jsonl", tmp_path / "translation.json", tmp_path / "translation.md"
    )

    assert report["status"] == "not_evaluable"
    assert report["pairs"]["file_found"] is False
    assert report["pairs"]["valid_records"] == 0
    assert report["evaluation"]["metrics"] is None
    markdown = (tmp_path / "translation.md").read_text()
    assert "BLEU: None" in markdown
    assert "chrF: None" in markdown


def test_translation_audit_validates_directions_duplicates_and_text_privacy(
    tmp_path: Path,
) -> None:
    pairs_path = tmp_path / "pairs.jsonl"
    records = [
        {
            "segment_id": "de-1",
            "direction": "de-en",
            "source": "German source text",
            "reference": "English reference text",
            "hypothesis": "English model output",
        },
        {
            "segment_id": "de-1",
            "direction": "de-en",
            "source": "Duplicate source text",
            "reference": "Duplicate reference text",
            "hypothesis": "Duplicate hypothesis text",
        },
        {
            "segment_id": "bad",
            "direction": "fr-en",
            "source": "X",
            "reference": "Y",
            "hypothesis": "Z",
        },
        {"segment_id": "de-2", "direction": "de-en", "source": "Only source"},
    ]
    pairs_path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8"
    )

    report = audit_translation_pairs(
        pairs_path, tmp_path / "translation.json", tmp_path / "translation.md"
    )

    assert report["status"] == "input_needs_review"
    assert report["pairs"]["records_read"] == 4
    assert report["pairs"]["valid_records"] == 1
    assert report["pairs"]["invalid_records"] == 3
    assert report["pairs"]["duplicate_segment_ids"] == 1
    assert report["pairs"]["direction_counts"] == {"de-en": 1, "en-de": 0}
    assert report["pairs"]["invalid_reasons"] == {
        "duplicate_segment_id": 1,
        "missing_reference": 1,
        "unsupported_direction": 1,
    }
    serialized_report = json.dumps(report)
    assert "English reference text" not in serialized_report
    assert "German source text" not in serialized_report
