"""Streaming ingestion of the pinned Mendeley JSON-in-ZIP snapshot."""

from __future__ import annotations

import hashlib
import json
import logging
import zipfile
from collections import Counter
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import IO, Any

import ijson
import pyarrow as pa
import pyarrow.parquet as pq

from german_job_market.normalization import (
    RecordRejected,
    RedactionCounts,
    deduplication_key,
    normalize_record,
)
from german_job_market.schema import PARQUET_SCHEMA, JobRecord

LOGGER = logging.getLogger(__name__)


@dataclass
class IngestionStats:
    records_read: int = 0
    valid_before_deduplication: int = 0
    invalid_records: int = 0
    duplicates_dropped: int = 0
    output_records: int = 0
    rejected_reasons: Counter[str] = field(default_factory=Counter)
    pii_redactions: RedactionCounts = field(default_factory=RedactionCounts)
    field_non_null: Counter[str] = field(default_factory=Counter)
    semantic_sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["rejected_reasons"] = dict(sorted(self.rejected_reasons.items()))
        result["pii_redactions"] = asdict(self.pii_redactions)
        result["field_non_null"] = dict(sorted(self.field_non_null.items()))
        return result


def _open_source_records(archive: Path) -> tuple[IO[bytes], zipfile.ZipFile | None]:
    if zipfile.is_zipfile(archive):
        zip_handle = zipfile.ZipFile(archive)
        candidates = [name for name in zip_handle.namelist() if name.lower().endswith(".json")]
        if len(candidates) != 1:
            zip_handle.close()
            raise ValueError(f"Expected one JSON source file in archive; found {len(candidates)}")
        return zip_handle.open(candidates[0]), zip_handle
    return archive.open("rb"), None


def iter_source_records(archive: Path) -> Iterator[dict[str, Any]]:
    """Yield top-level JSON array items without expanding the large source file to disk."""
    source_handle, zip_handle = _open_source_records(archive)
    try:
        for item in ijson.items(source_handle, "item"):
            if isinstance(item, dict):
                yield item
            else:
                yield {"_invalid_source_type": type(item).__name__}
    finally:
        source_handle.close()
        if zip_handle is not None:
            zip_handle.close()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _update_semantic_hash(digest: Any, record: JobRecord) -> None:
    serialized = json.dumps(
        record.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    digest.update(serialized.encode("utf-8"))
    digest.update(b"\n")


def ingest_archive(
    archive: Path,
    output: Path,
    *,
    source: str = "stepstone-mendeley",
    batch_size: int = 1024,
) -> IngestionStats:
    """Normalize, sanitize, deduplicate, and write records to an atomic Parquet snapshot."""
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    if not archive.is_file():
        raise FileNotFoundError(archive)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = output.with_name(f".{output.name}.tmp")
    stats = IngestionStats()
    seen: set[str] = set()
    digest = hashlib.sha256()
    batch: list[dict[str, Any]] = []
    writer: pq.ParquetWriter | None = None

    try:
        writer = pq.ParquetWriter(temporary_output, PARQUET_SCHEMA, compression="zstd")
        for raw in iter_source_records(archive):
            stats.records_read += 1
            try:
                record, redactions = normalize_record(raw, source=source)
            except (RecordRejected, ValueError, TypeError):
                stats.invalid_records += 1
                reason = "invalid_source_record"
                if not raw.get("title") and not raw.get("job_title") and not raw.get("position"):
                    reason = "missing_title"
                stats.rejected_reasons[reason] += 1
                continue

            stats.valid_before_deduplication += 1
            stats.pii_redactions += redactions
            key = deduplication_key(record)
            if key in seen:
                stats.duplicates_dropped += 1
                continue
            seen.add(key)

            row = record.model_dump(mode="python")
            for field_name, value in row.items():
                if value is not None:
                    stats.field_non_null[field_name] += 1
            _update_semantic_hash(digest, record)
            batch.append(row)
            stats.output_records += 1

            if len(batch) >= batch_size:
                table = pa.Table.from_pylist(batch, schema=PARQUET_SCHEMA)
                if writer is None:
                    raise RuntimeError("Parquet writer was not initialized")
                writer.write_table(table)
                batch.clear()

        if batch:
            if writer is None:
                raise RuntimeError("Parquet writer was not initialized")
            writer.write_table(pa.Table.from_pylist(batch, schema=PARQUET_SCHEMA))
        if writer is not None:
            writer.close()
            writer = None
        if stats.records_read == 0:
            raise ValueError("Source yielded no JSON records")
        temporary_output.replace(output)
    except Exception:
        if writer is not None:
            writer.close()
        temporary_output.unlink(missing_ok=True)
        raise

    stats.semantic_sha256 = digest.hexdigest()
    LOGGER.info(
        "ingestion_complete",
        extra={
            "records_read": stats.records_read,
            "output_records": stats.output_records,
            "invalid_records": stats.invalid_records,
            "duplicates_dropped": stats.duplicates_dropped,
        },
    )
    return stats
