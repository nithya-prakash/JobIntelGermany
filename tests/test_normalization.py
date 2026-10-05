from datetime import date

import pytest

from german_job_market.normalization import RecordRejected, normalize_record, sanitize_text


def test_contact_details_are_redacted_and_counted() -> None:
    cleaned, counts = sanitize_text("Write to hiring@example.de or call +49 30 12345678")
    assert cleaned == "Write to [EMAIL REDACTED] or call [PHONE REDACTED]"
    assert counts.emails == 1
    assert counts.phone_numbers == 1


def test_normalization_maps_source_fields_and_dates_deterministically() -> None:
    source = {
        "title": "Data Engineer &amp; Analyst",
        "firm": "Example GmbH",
        "oj_id": "https://jobs.example/123",
        "about_work": '["Berlin", "Erschienen: vor 2 Tagen"]',
        "date_scrape": "2023-05-14",
        "info_1": "Python, SQL; contact mail@example.de",
    }
    first, redactions = normalize_record(source)
    second, _ = normalize_record(source)

    assert first.title == "Data Engineer & Analyst"
    assert first.location == "Berlin"
    assert first.collection_date == date(2023, 5, 14)
    assert first.publication_date is None
    assert first.description == "Python, SQL; contact [EMAIL REDACTED]"
    assert first.job_id == second.job_id
    assert redactions.emails == 1


def test_missing_title_is_rejected_without_leaking_source_text() -> None:
    with pytest.raises(RecordRejected, match="missing_title"):
        normalize_record({"info_1": "unusable text"})
