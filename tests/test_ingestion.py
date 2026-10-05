import json
import zipfile
from pathlib import Path

import pyarrow.parquet as pq

from german_job_market.ingestion import ingest_archive
from german_job_market.quality import inspect_output


def test_zip_ingestion_sanitizes_deduplicates_and_writes_canonical_parquet(tmp_path: Path) -> None:
    # Small controlled fixture for transformation behavior; project metrics come only from the
    # separately executed published dataset snapshot.
    records = [
        {
            "title": "Analyst",
            "firm": "Example GmbH",
            "oj_id": "https://example.test/job/1",
            "about_work": '["Hamburg"]',
            "date_scrape": "2023-05-10",
            "info_1": "Contact: jobs@example.de, +49 40 12345678",
        },
        {
            "title": "Duplicate analyst",
            "firm": "Example GmbH",
            "oj_id": "https://example.test/job/1",
            "about_work": '["Hamburg"]',
            "info_1": "Duplicate row",
        },
        {"firm": "No title"},
    ]
    archive_path = tmp_path / "source.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("fixture/records.json", json.dumps(records))

    output = tmp_path / "jobs.parquet"
    stats = ingest_archive(archive_path, output, batch_size=1)
    table = pq.read_table(output)
    row = table.to_pylist()[0]

    assert stats.records_read == 3
    assert stats.output_records == 1
    assert stats.duplicates_dropped == 1
    assert stats.invalid_records == 1
    assert stats.pii_redactions.emails == 1
    assert stats.pii_redactions.phone_numbers == 1
    assert "[EMAIL REDACTED]" in row["description"]
    assert "[PHONE REDACTED]" in row["description"]
    assert "email" not in row
    assert "phone" not in row
    assert "contact" not in row
    assert row["collection_date"].isoformat() == "2023-05-10"

    checks = inspect_output(output, tmp_path / "jobs.duckdb")
    assert checks["rows"] == 1
    assert checks["remaining_email_pattern_rows"] == 0
    assert checks["remaining_phone_pattern_rows"] == 0
    assert checks["field_coverage"]["title"]["fraction"] == 1.0
