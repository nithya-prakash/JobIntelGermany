"""Source-specific normalization and direct-contact sanitization."""

from __future__ import annotations

import hashlib
import html
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from german_job_market.schema import JobRecord

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?:\+49|0049|0)(?:[\s()./-]*\d){7,12}")
HTML_TAG_RE = re.compile(r"<[^>]{1,300}>")


@dataclass(frozen=True)
class RedactionCounts:
    emails: int = 0
    phone_numbers: int = 0

    def __add__(self, other: RedactionCounts) -> RedactionCounts:
        return RedactionCounts(
            emails=self.emails + other.emails,
            phone_numbers=self.phone_numbers + other.phone_numbers,
        )


class RecordRejected(ValueError):
    """Raised when a source record cannot satisfy required canonical fields."""


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    text = html.unescape(value)
    text = HTML_TAG_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def sanitize_text(value: Any) -> tuple[str | None, RedactionCounts]:
    text = clean_text(value)
    if text is None:
        return None, RedactionCounts()
    emails = len(EMAIL_RE.findall(text))
    text = EMAIL_RE.sub("[EMAIL REDACTED]", text)
    phones = len(PHONE_RE.findall(text))
    text = PHONE_RE.sub("[PHONE REDACTED]", text)
    return text or None, RedactionCounts(emails=emails, phone_numbers=phones)


def parse_date(value: Any) -> date | None:
    text = clean_text(value)
    if text is None:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%Y/%m/%d"):
        try:
            return (
                date.fromisoformat(text)
                if fmt == "%Y-%m-%d"
                else datetime.strptime(text, fmt).date()
            )
        except ValueError:
            continue
    return None


def _first(raw: dict[str, Any], names: tuple[str, ...]) -> Any:
    for name in names:
        if raw.get(name) is not None:
            return raw[name]
    return None


def _location(raw: dict[str, Any]) -> Any:
    direct = _first(raw, ("location", "city", "place"))
    if direct is not None:
        return direct
    value = raw.get("about_work")
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return value
    if isinstance(value, list) and value:
        return value[0]
    if isinstance(value, dict):
        return value.get("location") or value.get("city")
    return None


def _content_key(
    title: str, company: str | None, location: str | None, description: str | None
) -> str:
    values = (title, company or "", location or "", description or "")
    return hashlib.sha256("\x1f".join(values).encode("utf-8")).hexdigest()


def normalize_record(
    raw: dict[str, Any], source: str = "stepstone-mendeley"
) -> tuple[JobRecord, RedactionCounts]:
    title, title_counts = sanitize_text(_first(raw, ("title", "job_title", "position")))
    if title is None:
        raise RecordRejected("missing_title")

    company, company_counts = sanitize_text(_first(raw, ("company", "employer", "firm")))
    location, location_counts = sanitize_text(_location(raw))
    description, description_counts = sanitize_text(
        _first(raw, ("description", "job_description", "description_text", "info_1"))
    )
    source_url = clean_text(_first(raw, ("source_url", "url", "oj_id")))
    if source_url:
        job_id = hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:24]
    else:
        job_id = _content_key(title, company, location, description)[:24]

    redactions = title_counts + company_counts + location_counts + description_counts
    record = JobRecord(
        job_id=job_id,
        source=source,
        source_url=source_url,
        title=title,
        company=company,
        location=location,
        description=description,
        # date_scrape records collection time, not the vacancy's publication date.
        collection_date=parse_date(_first(raw, ("collection_date", "date_scrape", "fetched_at"))),
        # This source has no verified publication-date field. Relative labels are not converted.
        publication_date=parse_date(
            _first(raw, ("publication_date", "posted_date", "date_posted"))
        ),
    )
    return record, redactions


def deduplication_key(record: JobRecord) -> str:
    if record.source_url:
        return f"url:{record.source_url.casefold()}"
    return (
        f"content:{_content_key(record.title, record.company, record.location, record.description)}"
    )
