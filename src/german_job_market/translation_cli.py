"""Command line audit for translation evaluation readiness."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from german_job_market.translation import audit_translation_pairs


def _project_root() -> Path:
    for candidate in (Path.cwd(), *Path.cwd().parents):
        if (candidate / "configs/source.toml").is_file():
            return candidate
    return Path(__file__).resolve().parents[2]


def main() -> None:
    root = _project_root()
    parser = argparse.ArgumentParser(
        description="Audit aligned translation evaluation pairs; no model is run."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    audit = commands.add_parser("audit", help="validate local translation pair data")
    audit.add_argument(
        "--pairs", type=Path, default=root / "data/evaluation/translation/pairs.jsonl"
    )
    audit.add_argument(
        "--json-report", type=Path, default=root / "reports/phase7/translation_readiness.json"
    )
    audit.add_argument(
        "--markdown-report", type=Path, default=root / "reports/phase7/translation_readiness.md"
    )
    args = parser.parse_args()
    report = audit_translation_pairs(args.pairs, args.json_report, args.markdown_report)
    print(
        json.dumps(
            {
                "json_report": str(args.json_report),
                "markdown_report": str(args.markdown_report),
                "status": report["status"],
                "pairs": report["pairs"],
                "evaluation": report["evaluation"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
