"""Command line for auditing salary label readiness."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from german_job_market.salary import audit_salary_data


def _project_root() -> Path:
    for candidate in (Path.cwd(), *Path.cwd().parents):
        if (candidate / "configs/source.toml").is_file():
            return candidate
    return Path(__file__).resolve().parents[2]


def main() -> None:
    root = _project_root()
    parser = argparse.ArgumentParser(
        description="Audit salary label readiness; no model is trained."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    audit = commands.add_parser("audit", help="measure salary coverage and unit validity")
    audit.add_argument("--jobs", type=Path, default=root / "data/processed/jobs.parquet")
    audit.add_argument(
        "--json-report", type=Path, default=root / "reports/phase6/salary_readiness.json"
    )
    audit.add_argument(
        "--markdown-report", type=Path, default=root / "reports/phase6/salary_readiness.md"
    )
    args = parser.parse_args()
    report = audit_salary_data(args.jobs, args.json_report, args.markdown_report)
    print(
        json.dumps(
            {
                "json_report": str(args.json_report),
                "markdown_report": str(args.markdown_report),
                "summary": report["summary"],
                "model": report["model"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
