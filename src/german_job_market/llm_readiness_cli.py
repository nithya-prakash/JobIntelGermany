"""Command line for the LLM fine-tuning readiness audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from german_job_market.llm_readiness import audit_finetuning_readiness


def _project_root() -> Path:
    for candidate in (Path.cwd(), *Path.cwd().parents):
        if (candidate / "configs/source.toml").is_file():
            return candidate
    return Path(__file__).resolve().parents[2]


def main() -> None:
    root = _project_root()
    parser = argparse.ArgumentParser(
        description="Audit LLM fine-tuning feasibility; no model is trained or downloaded."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    audit = commands.add_parser("audit", help="measure labels, leakage, baseline, and runtime")
    audit.add_argument("--gold", type=Path, default=root / "data/evaluation/skill_gold_v1.jsonl")
    audit.add_argument(
        "--weak-labels", type=Path, default=root / "data/processed/job_skills.parquet"
    )
    audit.add_argument(
        "--baseline", type=Path, default=root / "reports/phase8/extraction_baseline.json"
    )
    audit.add_argument(
        "--json-report", type=Path, default=root / "reports/phase8/llm_readiness.json"
    )
    audit.add_argument(
        "--markdown-report", type=Path, default=root / "reports/phase8/llm_readiness.md"
    )
    args = parser.parse_args()
    report = audit_finetuning_readiness(
        args.gold, args.weak_labels, args.baseline, args.json_report, args.markdown_report
    )
    print(
        json.dumps(
            {
                "json_report": str(args.json_report),
                "markdown_report": str(args.markdown_report),
                "decision": report["decision"],
                "gold_labels": report["gold_labels"],
                "weak_label_overlap": report["weak_label_overlap"],
                "baseline": report["baseline"],
                "blockers": report["blockers"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
