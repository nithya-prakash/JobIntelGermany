"""Command line for local, skills-only matching and labeled evaluation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from german_job_market.matching import evaluate_benchmark, rank_jobs
from german_job_market.skills import extract_skill_ids, load_taxonomy


def _project_root() -> Path:
    for candidate in (Path.cwd(), *Path.cwd().parents):
        if (candidate / "configs/skill_taxonomy.toml").is_file():
            return candidate
    return Path(__file__).resolve().parents[2]


def _read_profile(path: Path) -> list[str]:
    with path.open(encoding="utf-8") as profile_file:
        profile: Any = json.load(profile_file)
    if not isinstance(profile, dict):
        raise ValueError("candidate profile must be a JSON object")
    skill_ids = profile.get("skill_ids")
    if not isinstance(skill_ids, list) or not all(isinstance(item, str) for item in skill_ids):
        raise ValueError("candidate profile must contain a string array named skill_ids")
    return skill_ids


def main() -> None:
    root = _project_root()
    parser = argparse.ArgumentParser(description="Local skills-only candidate/job retrieval.")
    commands = parser.add_subparsers(dest="command", required=True)

    match = commands.add_parser("match", help="rank postings for a structured profile or CV")
    profile_source = match.add_mutually_exclusive_group(required=True)
    profile_source.add_argument("--profile", type=Path, help="JSON with canonical skill_ids")
    profile_source.add_argument("--cv", type=Path, help="local UTF-8 CV text; processed in memory")
    match.add_argument("--jobs", type=Path, default=root / "data/processed/jobs.parquet")
    match.add_argument("--skills", type=Path, default=root / "data/processed/job_skills.parquet")
    match.add_argument("--taxonomy", type=Path, default=root / "configs/skill_taxonomy.toml")
    match.add_argument("--top-k", type=int, default=10)
    match.add_argument("--exclude-job-id", action="append", default=[])

    evaluate = commands.add_parser(
        "evaluate", help="score manually judged queries from a JSONL benchmark"
    )
    evaluate.add_argument("--benchmark", type=Path, required=True)
    evaluate.add_argument("--jobs", type=Path, default=root / "data/processed/jobs.parquet")
    evaluate.add_argument("--skills", type=Path, default=root / "data/processed/job_skills.parquet")
    evaluate.add_argument("--taxonomy", type=Path, default=root / "configs/skill_taxonomy.toml")
    evaluate.add_argument("--k", type=int, default=10)

    args = parser.parse_args()
    taxonomy = load_taxonomy(args.taxonomy)
    if args.command == "match":
        if args.profile is not None:
            candidate_skill_ids = _read_profile(args.profile)
            input_mode = "structured_skill_ids"
        else:
            cv_text = args.cv.read_text(encoding="utf-8")
            candidate_skill_ids = extract_skill_ids(cv_text, taxonomy)
            del cv_text
            input_mode = "local_cv_lexicon_extraction"
        result = rank_jobs(
            candidate_skill_ids=candidate_skill_ids,
            jobs_path=args.jobs,
            skills_path=args.skills,
            taxonomy=taxonomy,
            top_k=args.top_k,
            exclude_job_ids=set(args.exclude_job_id),
            input_mode=input_mode,
        )
    else:
        result = evaluate_benchmark(
            benchmark_path=args.benchmark,
            jobs_path=args.jobs,
            skills_path=args.skills,
            taxonomy=taxonomy,
            k=args.k,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
