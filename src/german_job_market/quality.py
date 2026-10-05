"""Independent Parquet quality checks using DuckDB."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from german_job_market.ingestion import IngestionStats, sha256_file
from german_job_market.schema import PARQUET_SCHEMA

EMAIL_PATTERN = r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}"
PHONE_PATTERN = r"(?:\+49|0049|0)(?:[\s()./-]*\d){7,12}"


def inspect_output(parquet_path: Path, duckdb_path: Path) -> dict[str, Any]:
    """Create a lightweight DuckDB view and compute output checks from the written Parquet."""
    database = duckdb.connect(str(duckdb_path))
    try:
        path_literal = str(parquet_path.resolve()).replace("'", "''")
        database.execute(
            f"CREATE OR REPLACE VIEW jobs AS SELECT * FROM read_parquet('{path_literal}')"
        )
        schema_rows = database.execute("DESCRIBE SELECT * FROM jobs").fetchall()
        actual_fields = [row[0] for row in schema_rows]
        expected_fields = PARQUET_SCHEMA.names
        if actual_fields != expected_fields:
            raise ValueError(f"Parquet schema mismatch: {actual_fields}")

        row_result = database.execute("SELECT count(*) FROM jobs").fetchone()
        if row_result is None:
            raise ValueError("DuckDB returned no row count")
        row_count = row_result[0]
        coverage_result = database.execute(
            "SELECT " + ", ".join(f"count({field})" for field in expected_fields) + " FROM jobs"
        ).fetchone()
        if coverage_result is None:
            raise ValueError("DuckDB returned no field coverage")
        coverage = {
            field: {"non_null": count, "fraction": (count / row_count if row_count else 0.0)}
            for field, count in zip(expected_fields, coverage_result, strict=True)
        }
        privacy_result = database.execute(
            """SELECT
                 count(*) FILTER (WHERE regexp_matches(
                   concat_ws(' ', title, company, location, description), ?, 'i')),
                 count(*) FILTER (WHERE regexp_matches(
                   concat_ws(' ', title, company, location, description), ?, 'i'))
               FROM jobs""",
            [EMAIL_PATTERN, PHONE_PATTERN],
        ).fetchone()
        if privacy_result is None:
            raise ValueError("DuckDB returned no privacy scan results")
        emails, phones = privacy_result
        date_result = database.execute(
            "SELECT min(collection_date), max(collection_date) FROM jobs"
        ).fetchone()
        if date_result is None:
            raise ValueError("DuckDB returned no collection-date range")
        date_min, date_max = date_result
        return {
            "rows": row_count,
            "schema_fields": actual_fields,
            "field_coverage": coverage,
            "remaining_email_pattern_rows": emails,
            "remaining_phone_pattern_rows": phones,
            "collection_date_min": date_min.isoformat() if date_min else None,
            "collection_date_max": date_max.isoformat() if date_max else None,
            "parquet_sha256": sha256_file(parquet_path),
        }
    finally:
        database.close()


def build_report(
    *,
    archive: Path,
    parquet_path: Path,
    duckdb_path: Path,
    stats: IngestionStats,
    source_metadata: dict[str, Any],
) -> dict[str, Any]:
    checks = inspect_output(parquet_path, duckdb_path)
    if checks["rows"] != stats.output_records:
        raise ValueError("DuckDB row count does not match the ingestion count")
    if checks["remaining_email_pattern_rows"] or checks["remaining_phone_pattern_rows"]:
        raise ValueError("Direct email/phone patterns remain in normalized text")
    if checks["field_coverage"]["title"]["non_null"] != stats.output_records:
        raise ValueError("A normalized output record has an empty title")

    return {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "source": source_metadata,
        "input_archive": {
            "filename": archive.name,
            "bytes": archive.stat().st_size,
            "sha256": sha256_file(archive),
        },
        "ingestion": stats.to_dict(),
        "quality_checks": checks,
        "privacy": {
            "raw_source_record_retained": False,
            "unrecognized_source_fields_retained": False,
            "email_matches_redacted": stats.pii_redactions.emails,
            "phone_matches_redacted": stats.pii_redactions.phone_numbers,
            "remaining_email_pattern_rows": checks["remaining_email_pattern_rows"],
            "remaining_phone_pattern_rows": checks["remaining_phone_pattern_rows"],
        },
        "outputs": {
            "parquet": str(parquet_path),
            "duckdb": str(duckdb_path),
            "duckdb_view": "jobs",
        },
    }
