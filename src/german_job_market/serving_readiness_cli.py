"""Command line for LLM serving readiness checks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from german_job_market.serving_readiness import audit_serving_readiness


def _project_root() -> Path:
    for candidate in (Path.cwd(), *Path.cwd().parents):
        if (candidate / "configs/source.toml").is_file():
            return candidate
    return Path(__file__).resolve().parents[2]


def main() -> None:
    root = _project_root()
    parser = argparse.ArgumentParser(
        description="Audit model-serving readiness; no model is downloaded or run."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    audit = commands.add_parser("audit", help="check model artifact and local serving backend")
    audit.add_argument(
        "--phase8-report", type=Path, default=root / "reports/phase8/llm_readiness.json"
    )
    audit.add_argument("--model", type=Path, default=root / "models/finetuned-skill-extractor")
    audit.add_argument(
        "--json-report", type=Path, default=root / "reports/phase9/serving_readiness.json"
    )
    audit.add_argument(
        "--markdown-report", type=Path, default=root / "reports/phase9/serving_readiness.md"
    )
    args = parser.parse_args()
    report = audit_serving_readiness(
        args.phase8_report, args.model, args.json_report, args.markdown_report
    )
    print(
        json.dumps(
            {
                "json_report": str(args.json_report),
                "markdown_report": str(args.markdown_report),
                "decision": report["decision"],
                "model_artifact": report["model_artifact"],
                "runtime": report["runtime"],
                "benchmark_results": report["benchmark_results"],
                "blockers": report["blockers"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
