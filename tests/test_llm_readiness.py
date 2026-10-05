import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from german_job_market.llm_readiness import audit_finetuning_readiness


def test_readiness_audit_blocks_leaked_unreviewed_small_sample(tmp_path: Path) -> None:
    gold_path = tmp_path / "gold.jsonl"
    records = [
        {"job_id": f"job-{i}", "primary_language": "de", "skill_ids": ["python"]} for i in range(3)
    ]
    gold_path.write_text("\n".join(json.dumps(record) for record in records) + "\n")
    sidecar_path = tmp_path / "weak.parquet"
    pq.write_table(
        pa.table({"job_id": ["job-0", "job-1", "other"], "skill_ids": [[], [], []]}),
        sidecar_path,
    )
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(
        json.dumps(
            {
                "task": "rule_based",
                "sample_size": 3,
                "language_record_counts": {"de": 3, "en": 0},
                "overall": {"precision": 0.8, "recall": 0.9, "f1": 0.847},
                "by_primary_language": {},
                "annotation_limit": "review required",
            }
        )
    )

    report = audit_finetuning_readiness(
        gold_path,
        sidecar_path,
        baseline_path,
        tmp_path / "report.json",
        tmp_path / "report.md",
    )

    assert report["gold_labels"]["records"] == 3
    assert report["gold_labels"]["positive_skill_labels"] == 3
    assert report["weak_label_overlap"]["gold_job_ids_present"] == 2
    assert report["baseline"]["overall"]["f1"] == 0.847
    assert report["decision"] == "blocked_no_finetuning"
    assert report["train_validation_test_split"] is None
    assert report["fine_tuned_model"] == {"trained": False, "metrics": None}
    assert any("leaks evaluation examples" in blocker for blocker in report["blockers"])


def test_readiness_audit_handles_missing_inputs_without_fabricating_baseline(
    tmp_path: Path,
) -> None:
    report = audit_finetuning_readiness(
        tmp_path / "missing.jsonl",
        tmp_path / "missing.parquet",
        tmp_path / "missing-baseline.json",
        tmp_path / "report.json",
        tmp_path / "report.md",
    )

    assert report["gold_labels"]["records"] == 0
    assert report["weak_label_overlap"]["file_found"] is False
    assert report["baseline"] is None
    assert report["fine_tuned_model"]["trained"] is False
    assert "no measured rule-based baseline report is available" in report["blockers"]
