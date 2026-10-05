"""Command line for Phase 11 benchmark infrastructure."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from german_job_market import benchmark as b
from german_job_market import benchmark_pages as pages
from german_job_market.skills import load_taxonomy


def _root() -> Path:
    for c in (Path.cwd(), *Path.cwd().parents):
        if (c / "configs/source.toml").is_file():
            return c
    return Path(__file__).resolve().parents[2]


def main() -> None:
    r = _root()
    parser = argparse.ArgumentParser(description="Phase 11 evaluation benchmarks.")
    parser.add_argument(
        "command",
        choices=[
            "skill-sample",
            "skill-score",
            "match-pool",
            "match-score",
            "annotate-check",
            "annotate-import",
            "skill-pilot",
            "annotate-page",
            "judge-page",
        ],
    )
    parser.add_argument("--jobs", type=Path, default=r / "data/processed/jobs.parquet")
    parser.add_argument("--skills", type=Path, default=r / "data/processed/job_skills.parquet")
    parser.add_argument("--taxonomy", type=Path, default=r / "configs/skill_taxonomy.toml")
    parser.add_argument("--csv", type=Path, help="annotate-import: job_id,skill,label CSV")
    parser.add_argument("--annotator", help="annotate-import: annotator name")
    parser.add_argument("--seed", type=int, default=b.SEED)
    a = parser.parse_args()
    t = load_taxonomy(a.taxonomy)
    ev, local = r / "data/evaluation", r / "data/processed/eval_v2"
    if a.command == "skill-pilot":
        out = b.build_pilot(ev / "skill_v2/manifest.jsonl", ev / "skill_v2/pilot.jsonl")
    elif a.command == "annotate-page":
        pilot = ev / "skill_v2/pilot.jsonl"
        ids = {m["job_id"] for m in b._read_jsonl(pilot)} if pilot.is_file() else None
        n = pages.write_annotate_page(
            local / "skill_reading_pack.jsonl", ids, t, local / "annotate.html"
        )
        out = {"page": str(local / "annotate.html"), "postings": n, "pilot_only": ids is not None}
    elif a.command == "judge-page":
        n = pages.write_judge_page(
            b._read_jsonl(ev / "matching/queries.jsonl"),
            b._read_jsonl(ev / "matching/pool_sheet.jsonl"),
            local / "match_reading_pack.jsonl",
            local / "judge.html",
        )
        out = {"page": str(local / "judge.html"), "pooled_pairs": n}
    elif a.command == "annotate-import":
        if not a.csv or not a.annotator:
            parser.error("annotate-import needs --csv and --annotator")
        out = b.import_annotation_csv(
            a.csv, a.annotator, ev / "skill_v2/manifest.jsonl", ev / "skill_v2/annotations", t
        )
    elif a.command == "annotate-check":
        out = b.check_annotations(ev / "skill_v2/manifest.jsonl", ev / "skill_v2/annotations", t)
    elif a.command == "skill-sample":
        out = b.build_skill_sample(
            a.jobs,
            a.skills,
            ev / "skill_gold_v1.jsonl",
            t,
            ev / "skill_v2/manifest.jsonl",
            local / "skill_reading_pack.jsonl",
            a.seed,
        )
    elif a.command == "skill-score":
        out = b.score_skill_benchmark(
            ev / "skill_v2/manifest.jsonl",
            ev / "skill_v2/annotations",
            a.jobs,
            t,
            r / "reports/phase11/skill_benchmark_v2.json",
            a.seed,
        )
    elif a.command == "match-pool":
        out = b.build_match_pool(
            ev / "matching/queries.jsonl",
            a.jobs,
            a.skills,
            t,
            ev / "matching/pool_sheet.jsonl",
            ev / "matching/pool_provenance.json",
            local / "match_reading_pack.jsonl",
            seed=a.seed,
        )
    else:
        out = b.score_matching_benchmark(
            ev / "matching/queries.jsonl",
            ev / "matching/pool_sheet.jsonl",
            ev / "matching/pool_provenance.json",
            t,
            r / "reports/phase11/matching_benchmark.json",
            seed=a.seed,
        )
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
