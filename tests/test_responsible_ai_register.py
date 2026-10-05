"""Contract checks for the human-reviewed Phase 10 risk register."""

import json
from pathlib import Path
from typing import Any


def test_responsible_ai_register_has_complete_reviewable_risks() -> None:
    root = Path(__file__).resolve().parents[1]
    path = root / "reports/phase10/responsible_ai_risk_register.json"
    report: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))

    assert report["phase"] == 10
    assert report["reviewed_on"] == "2026-10-04"
    assert "not legal advice" in report["legal_status"]
    assert "Qualitative" in report["ratings_note"]

    risks = report["risks"]
    required_fields = {
        "id",
        "risk_level",
        "requirement",
        "system_behavior",
        "evidence",
        "gap",
        "risk",
        "mitigation",
    }
    assert len(risks) >= 10
    assert len({risk["id"] for risk in risks}) == len(risks)
    for risk in risks:
        assert required_fields.issubset(risk)
        assert risk["risk_level"] in {"low", "medium", "high"}
        assert risk["evidence"]
        required_text = ("requirement", "system_behavior", "gap", "risk", "mitigation")
        assert all(risk[field] for field in required_text)

    assert report["official_sources"]
