"""Command line for Phase 2 skill extraction and evaluation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from german_job_market.skill_pipeline import evaluate_extraction, run_extraction
from german_job_market.skills import load_taxonomy


def _project_root() -> Path:
    for candidate in (Path.cwd(), *Path.cwd().parents):
        if (candidate / "configs/source.toml").is_file():
            return candidate
    return Path(__file__).resolve().parents[2]


def main() -> None:
    root = _project_root()
    parser = argparse.ArgumentParser(description="Run the Phase 2 skill baseline.")
    commands = parser.add_subparsers(dest="command", required=True)

    extract = commands.add_parser("extract", help="extract skills from every source posting")
    extract.add_argument("--input", type=Path, default=root / "data/processed/jobs.parquet")
    extract.add_argument("--output", type=Path, default=root / "data/processed/job_skills.parquet")
    extract.add_argument(
        "--report", type=Path, default=root / "reports/phase2/skill_extraction.json"
    )
    extract.add_argument("--taxonomy", type=Path, default=root / "configs/skill_taxonomy.toml")
    extract.add_argument("--batch-size", type=int, default=2048)

    evaluate = commands.add_parser("evaluate", help="score the matcher on the labeled sample")
    evaluate.add_argument("--input", type=Path, default=root / "data/processed/jobs.parquet")
    evaluate.add_argument("--gold", type=Path, default=root / "data/evaluation/skill_gold_v1.jsonl")
    evaluate.add_argument("--report", type=Path, default=root / "reports/phase2/skill_eval.json")
    evaluate.add_argument("--taxonomy", type=Path, default=root / "configs/skill_taxonomy.toml")

    args = parser.parse_args()
    taxonomy = load_taxonomy(args.taxonomy)
    if args.command == "extract":
        result = run_extraction(args.input, args.output, taxonomy, args.report, args.batch_size)
    else:
        result = evaluate_extraction(args.input, args.gold, taxonomy, args.report)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
