"""Command line entry point for Phase 1 ingestion."""

from __future__ import annotations

import argparse
import json
import logging
import tomllib
from pathlib import Path
from typing import Any

from german_job_market.ingestion import ingest_archive
from german_job_market.quality import build_report


def _project_root() -> Path:
    for candidate in (Path.cwd(), *Path.cwd().parents):
        if (candidate / "configs/source.toml").is_file():
            return candidate
    return Path(__file__).resolve().parents[2]


PROJECT_ROOT = _project_root()


def load_source_metadata(path: Path) -> dict[str, Any]:
    with path.open("rb") as source_file:
        return tomllib.load(source_file)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest the pinned German job-posting snapshot.")
    parser.add_argument("--archive", type=Path, default=PROJECT_ROOT / "data/raw/stepstone-v2.zip")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "data/processed/jobs.parquet")
    parser.add_argument("--duckdb", type=Path, default=PROJECT_ROOT / "data/processed/jobs.duckdb")
    parser.add_argument("--report", type=Path, default=PROJECT_ROOT / "reports/phase1/quality.json")
    parser.add_argument("--batch-size", type=int, default=1024)
    parser.add_argument(
        "--log-level", choices=("DEBUG", "INFO", "WARNING", "ERROR"), default="INFO"
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    metadata = load_source_metadata(PROJECT_ROOT / "configs/source.toml")
    stats = ingest_archive(args.archive, args.output, batch_size=args.batch_size)
    report = build_report(
        archive=args.archive,
        parquet_path=args.output,
        duckdb_path=args.duckdb,
        stats=stats,
        source_metadata=metadata,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
