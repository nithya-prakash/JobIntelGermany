"""Canonical Phase 1 job-posting schema."""

from datetime import date

import pyarrow as pa
from pydantic import BaseModel, ConfigDict, Field


class JobRecord(BaseModel):
    """A validated posting with only fields retained by the Phase 1 pipeline."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    job_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    source_url: str | None = None
    title: str = Field(min_length=1)
    company: str | None = None
    location: str | None = None
    federal_state: str | None = None
    remote_type: str | None = None
    employment_type: str | None = None
    experience_level: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    salary_period: str | None = None
    description: str | None = None
    requirements: str | None = None
    responsibilities: str | None = None
    benefits: str | None = None
    language_requirements: list[str] | None = None
    extracted_skills: list[str] | None = None
    normalized_skills: list[str] | None = None
    embedding: list[float] | None = None
    publication_date: date | None = None
    collection_date: date | None = None


PARQUET_SCHEMA = pa.schema(
    [
        pa.field("job_id", pa.string(), nullable=False),
        pa.field("source", pa.string(), nullable=False),
        pa.field("source_url", pa.string()),
        pa.field("title", pa.string(), nullable=False),
        pa.field("company", pa.string()),
        pa.field("location", pa.string()),
        pa.field("federal_state", pa.string()),
        pa.field("remote_type", pa.string()),
        pa.field("employment_type", pa.string()),
        pa.field("experience_level", pa.string()),
        pa.field("salary_min", pa.float64()),
        pa.field("salary_max", pa.float64()),
        pa.field("salary_currency", pa.string()),
        pa.field("salary_period", pa.string()),
        pa.field("description", pa.string()),
        pa.field("requirements", pa.string()),
        pa.field("responsibilities", pa.string()),
        pa.field("benefits", pa.string()),
        pa.field("language_requirements", pa.list_(pa.string())),
        pa.field("extracted_skills", pa.list_(pa.string())),
        pa.field("normalized_skills", pa.list_(pa.string())),
        pa.field("embedding", pa.list_(pa.float64())),
        pa.field("publication_date", pa.date32()),
        pa.field("collection_date", pa.date32()),
    ]
)
