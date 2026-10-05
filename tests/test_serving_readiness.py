import json
from pathlib import Path

from german_job_market.serving_readiness import audit_serving_readiness


def test_serving_audit_blocks_when_phase8_has_no_model(tmp_path: Path) -> None:
    phase8_path = tmp_path / "phase8.json"
    phase8_path.write_text(json.dumps({"fine_tuned_model": {"trained": False, "metrics": None}}))

    report = audit_serving_readiness(
        phase8_path,
        tmp_path / "missing-model",
        tmp_path / "serving.json",
        tmp_path / "serving.md",
    )

    assert report["decision"] == "blocked_no_benchmark"
    assert report["model_artifact"]["exists"] is False
    assert report["benchmark_results"] is None
    assert "Phase 8 did not produce a fine-tuned model artifact" in report["blockers"]
    markdown = (tmp_path / "serving.md").read_text()
    assert "not measured" in markdown


def test_serving_audit_handles_missing_phase8_report(tmp_path: Path) -> None:
    report = audit_serving_readiness(
        tmp_path / "missing-phase8.json",
        tmp_path / "missing-model",
        tmp_path / "serving.json",
        tmp_path / "serving.md",
    )

    assert report["phase8_model"]["trained"] is False
    assert report["decision"] == "blocked_no_benchmark"
