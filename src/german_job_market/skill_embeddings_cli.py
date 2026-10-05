"""Generate skill co-occurrence embeddings and exploratory clusters."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from german_job_market.skill_embeddings import build_skill_embeddings
from german_job_market.skills import load_taxonomy


def _project_root() -> Path:
    for candidate in (Path.cwd(), *Path.cwd().parents):
        if (candidate / "configs/skill_taxonomy.toml").is_file():
            return candidate
    return Path(__file__).resolve().parents[2]


def main() -> None:
    root = _project_root()
    parser = argparse.ArgumentParser(
        description="Create distributional skill vectors and exploratory clusters."
    )
    parser.add_argument("--skills", type=Path, default=root / "data/processed/job_skills.parquet")
    parser.add_argument("--taxonomy", type=Path, default=root / "configs/skill_taxonomy.toml")
    parser.add_argument(
        "--json-report", type=Path, default=root / "reports/phase4/skill_embeddings.json"
    )
    parser.add_argument(
        "--markdown-report", type=Path, default=root / "reports/phase4/skill_embeddings.md"
    )
    args = parser.parse_args()

    report = build_skill_embeddings(
        skills_path=args.skills,
        taxonomy=load_taxonomy(args.taxonomy),
        json_path=args.json_report,
        markdown_path=args.markdown_report,
    )
    print(
        json.dumps(
            {
                "json_report": str(args.json_report),
                "markdown_report": str(args.markdown_report),
                "summary": report["summary"],
                "evaluation": report["evaluation"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
