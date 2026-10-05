"""Generate the Phase 3 historical collection-cohort report."""

from __future__ import annotations

import argparse
import json
import tomllib
from pathlib import Path
from typing import Any

from german_job_market.reporting import build_weekly_report
from german_job_market.skills import load_taxonomy


def _project_root() -> Path:
    for candidate in (Path.cwd(), *Path.cwd().parents):
        if (candidate / "configs/source.toml").is_file():
            return candidate
    return Path(__file__).resolve().parents[2]


def main() -> None:
    root = _project_root()
    parser = argparse.ArgumentParser(
        description="Generate historical collection-week skill comparisons."
    )
    parser.add_argument("--jobs", type=Path, default=root / "data/processed/jobs.parquet")
    parser.add_argument("--skills", type=Path, default=root / "data/processed/job_skills.parquet")
    parser.add_argument("--taxonomy", type=Path, default=root / "configs/skill_taxonomy.toml")
    parser.add_argument("--source", type=Path, default=root / "configs/source.toml")
    parser.add_argument(
        "--json-report", type=Path, default=root / "reports/phase3/weekly_intelligence.json"
    )
    parser.add_argument(
        "--markdown-report", type=Path, default=root / "reports/phase3/weekly_intelligence.md"
    )
    args = parser.parse_args()

    with args.source.open("rb") as source_file:
        source_metadata: dict[str, Any] = tomllib.load(source_file)
    report = build_weekly_report(
        jobs_path=args.jobs,
        skills_path=args.skills,
        taxonomy=load_taxonomy(args.taxonomy),
        json_path=args.json_report,
        markdown_path=args.markdown_report,
        publisher_described_period=source_metadata.get("publisher_described_collection_period"),
    )
    print(
        json.dumps(
            {
                "json_report": str(args.json_report),
                "markdown_report": str(args.markdown_report),
                "summary": report["summary"],
                "market_growth_inference_allowed": report["market_growth_inference_allowed"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
