"""Audit whether job-level salary records can support prediction."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import duckdb

_SUPPORTED_CURRENCIES = ("EUR",)
_SUPPORTED_PERIODS = (
    "annual",
    "annum",
    "month",
    "monthly",
    "per month",
    "per year",
    "year",
    "yearly",
)


def _required_row(result: Any) -> tuple[Any, ...]:
    row = result.fetchone()
    if row is None:
        raise ValueError("expected query to return one row")
    return cast(tuple[Any, ...], row)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _audit_skill_sidecar(jobs_path: Path) -> dict[str, Any]:
    sidecar_path = jobs_path.parent / "job_skills.parquet"
    if not sidecar_path.is_file():
        return {
            "available": False,
            "reason": "job_skills.parquet was not found beside jobs.parquet",
        }

    connection = duckdb.connect()
    try:
        columns = {
            row[0]
            for row in connection.execute(
                "DESCRIBE SELECT * FROM read_parquet(?)", [str(sidecar_path)]
            ).fetchall()
        }
        if missing := {"job_id", "skill_ids"}.difference(columns):
            raise ValueError(f"skill sidecar missing required columns: {sorted(missing)}")
        row = _required_row(
            connection.execute(
                """SELECT count(*) AS rows,
                          count(*) FILTER (
                              WHERE skill_ids IS NOT NULL AND array_length(skill_ids) > 0
                          ) AS postings_with_skills,
                          coalesce(sum(coalesce(array_length(skill_ids), 0)), 0)
                              AS skill_assignments,
                          count(DISTINCT skills.job_id) FILTER (
                              WHERE skill_ids IS NOT NULL AND array_length(skill_ids) > 0
                                AND jobs.job_id IS NOT NULL
                          ) AS matched_postings_with_skills,
                          count(DISTINCT skills.job_id) FILTER (
                              WHERE skill_ids IS NOT NULL AND array_length(skill_ids) > 0
                                AND jobs.job_id IS NULL
                          ) AS unmatched_postings_with_skills
                   FROM read_parquet(?) AS skills
                   LEFT JOIN read_parquet(?) AS jobs USING (job_id)""",
                [str(sidecar_path), str(jobs_path)],
            )
        )
    finally:
        connection.close()
    return {
        "available": True,
        "path": sidecar_path.name,
        "sha256": _sha256(sidecar_path),
        "rows": int(row[0]),
        "postings_with_skills": int(row[1]),
        "skill_assignments": int(row[2]),
        "matched_postings_with_skills": int(row[3]),
        "unmatched_postings_with_skills": int(row[4]),
    }


def _markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    coverage = report["field_coverage"]
    skills = report["skill_sidecar"]
    lines = [
        "# German Job Market Intelligence — salary data readiness",
        "",
        f"Generated: {report['generated_at_utc']}",
        "",
        "> **Status:** no salary prediction model was trained. No job-level salary "
        "labels are present in the pinned posting corpus.",
        "",
        "## Label audit",
        "",
        f"- Postings audited: {summary['postings']:,}",
        f"- Postings with either salary bound: {summary['rows_with_salary_any']:,}",
        f"- Complete min/max salary intervals: {summary['complete_interval_rows']:,}",
        f"- Valid EUR intervals with a recognized period: "
        f"{summary['valid_eur_period_interval_rows']:,}",
        f"- Partial intervals: {summary['partial_interval_rows']:,}",
        f"- Invalid numeric intervals: {summary['invalid_numeric_interval_rows']:,}",
        f"- Unsupported currency or period: {summary['unsupported_unit_rows']:,}",
        "",
        "| Field | Populated records |",
        "| --- | ---: |",
    ]
    for field in (
        "salary_min",
        "salary_max",
        "salary_currency",
        "salary_period",
        "title",
        "location",
        "federal_state",
        "experience_level",
        "employment_type",
        "remote_type",
        "normalized_skills",
    ):
        label = "normalized_skills (posting table)" if field == "normalized_skills" else field
        lines.append(f"| {label} | {coverage[field]['count']:,} / {coverage[field]['total']:,} |")
    lines.extend(
        [
            "",
            "## Training and explainability",
            "",
            f"- Model trained: {report['model']['trained']}",
            f"- Model metrics: {report['model']['metrics']}",
            f"- SHAP explanation available: {report['model']['shap_available']}",
            f"- Blockers: {'; '.join(report['model']['training_blockers']) or 'none recorded'}",
            "",
            "The dataset has no job-level salary labels, so MAE, RMSE, R², error "
            "distributions, and SHAP values are not applicable. This is a measured "
            "data limitation; no substitute values or synthetic training rows were created.",
            "",
            "## Skill feature sidecar",
            "",
        ]
    )
    if skills["available"]:
        lines.extend(
            [
                f"Phase 2 skill sidecar: {skills['rows']:,} rows; "
                f"{skills['matched_postings_with_skills']:,} matched postings with skills; "
                f"{skills['skill_assignments']:,} assignments.",
                "These annotations are stored separately from the canonical posting table.",
                "",
            ]
        )
    else:
        lines.extend([f"Unavailable: {skills['reason']}.", ""])
    lines.extend(
        [
            "## Source compatibility",
            "",
            "The BA Entgeltatlas reports aggregate gross monthly median wages for "
            "full-time social-insurance employees by occupational aggregates and region. "
            "It does not supply salary labels for the individual advertisements in this corpus. "
            "Joining those medians to ads would require a validated job-title-to-KldB mapping "
            "and would change the prediction target from advertised salary to an occupational "
            "employment median. The BA also suppresses some small cells and caps high values; "
            "these are material target limitations.",
            "",
            "## Reproduction",
            "",
            "Run `.venv/bin/gjmi-salary audit` after reproducing Phase 1.",
            "",
        ]
    )
    return "\n".join(lines)


def audit_salary_data(
    jobs_path: Path,
    json_path: Path,
    markdown_path: Path,
) -> dict[str, Any]:
    """Measure label coverage and currency/period validity without fitting a model."""
    if not jobs_path.is_file():
        raise FileNotFoundError(jobs_path)
    connection = duckdb.connect()
    try:
        columns = {
            row[0]
            for row in connection.execute(
                "DESCRIBE SELECT * FROM read_parquet(?)", [str(jobs_path)]
            ).fetchall()
        }
        required_columns = {
            "job_id",
            "salary_min",
            "salary_max",
            "salary_currency",
            "salary_period",
            "title",
            "location",
            "federal_state",
            "experience_level",
            "employment_type",
            "remote_type",
            "normalized_skills",
        }
        if missing := required_columns.difference(columns):
            raise ValueError(f"job input missing required columns: {sorted(missing)}")

        row = _required_row(
            connection.execute(
                """SELECT count(*) AS total,
                          count(salary_min) AS salary_min,
                          count(salary_max) AS salary_max,
                          count(salary_currency) AS salary_currency,
                          count(salary_period) AS salary_period,
                          count(*) FILTER (WHERE salary_min IS NOT NULL OR salary_max IS NOT NULL)
                              AS any_salary_bound,
                          count(*) FILTER (WHERE salary_min IS NOT NULL AND salary_max IS NOT NULL)
                              AS complete_intervals,
                          count(*) FILTER (
                              WHERE (salary_min IS NULL) != (salary_max IS NULL)
                          ) AS partial_intervals,
                          count(*) FILTER (
                              WHERE salary_min IS NOT NULL AND salary_max IS NOT NULL
                                AND (salary_min < 0 OR salary_max < 0 OR salary_min > salary_max)
                          ) AS invalid_numeric_intervals,
                          count(*) FILTER (
                              WHERE salary_min IS NOT NULL AND salary_max IS NOT NULL
                                AND (
                                  upper(trim(coalesce(salary_currency, ''))) NOT IN (?)
                                  OR lower(trim(coalesce(salary_period, ''))) NOT IN (
                                      ?, ?, ?, ?, ?, ?, ?, ?
                                  )
                                )
                          ) AS unsupported_units,
                          count(*) FILTER (
                              WHERE salary_min IS NOT NULL AND salary_max IS NOT NULL
                                AND salary_min >= 0 AND salary_max >= salary_min
                                AND upper(trim(coalesce(salary_currency, ''))) = ?
                                AND lower(trim(coalesce(salary_period, ''))) IN (
                                    ?, ?, ?, ?, ?, ?, ?, ?
                                )
                          ) AS valid_intervals,
                          count(*) FILTER (WHERE title IS NOT NULL AND trim(title) <> '')
                              AS title,
                          count(*) FILTER (WHERE location IS NOT NULL AND trim(location) <> '')
                              AS location,
                          count(*) FILTER (
                              WHERE federal_state IS NOT NULL AND trim(federal_state) <> ''
                          ) AS federal_state,
                          count(*) FILTER (
                              WHERE experience_level IS NOT NULL AND trim(experience_level) <> ''
                          ) AS experience_level,
                          count(*) FILTER (
                              WHERE employment_type IS NOT NULL AND trim(employment_type) <> ''
                          ) AS employment_type,
                          count(*) FILTER (
                              WHERE remote_type IS NOT NULL AND trim(remote_type) <> ''
                          ) AS remote_type,
                          count(*) FILTER (
                              WHERE normalized_skills IS NOT NULL
                                AND array_length(normalized_skills) > 0
                          ) AS normalized_skills
                   FROM read_parquet(?)""",
                [
                    *_SUPPORTED_CURRENCIES,
                    *_SUPPORTED_PERIODS,
                    _SUPPORTED_CURRENCIES[0],
                    *_SUPPORTED_PERIODS,
                    str(jobs_path),
                ],
            )
        )
    finally:
        connection.close()

    total = int(row[0])
    field_names = [
        "salary_min",
        "salary_max",
        "salary_currency",
        "salary_period",
        "title",
        "location",
        "federal_state",
        "experience_level",
        "employment_type",
        "remote_type",
        "normalized_skills",
    ]
    field_positions = {
        "salary_min": 1,
        "salary_max": 2,
        "salary_currency": 3,
        "salary_period": 4,
        "title": 11,
        "location": 12,
        "federal_state": 13,
        "experience_level": 14,
        "employment_type": 15,
        "remote_type": 16,
        "normalized_skills": 17,
    }
    field_coverage = {
        field: {"count": int(row[field_positions[field]]), "total": total} for field in field_names
    }
    skill_sidecar = _audit_skill_sidecar(jobs_path)
    valid_interval_count = int(row[10])
    training_blockers = []
    if valid_interval_count == 0:
        training_blockers.append("no valid job-level salary intervals are available")
    if total == 0:
        training_blockers.append("input dataset contains no postings")

    report: dict[str, Any] = {
        "phase": 6,
        "audit_type": "job_level_salary_label_readiness",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "inputs": {"jobs_path": jobs_path.name, "jobs_sha256": _sha256(jobs_path)},
        "accepted_units": {
            "currencies": list(_SUPPORTED_CURRENCIES),
            "periods": list(_SUPPORTED_PERIODS),
            "target_policy": "bounds only; no midpoint label is inferred",
        },
        "summary": {
            "postings": total,
            "rows_with_salary_any": int(row[5]),
            "complete_interval_rows": int(row[6]),
            "partial_interval_rows": int(row[7]),
            "invalid_numeric_interval_rows": int(row[8]),
            "unsupported_unit_rows": int(row[9]),
            "valid_eur_period_interval_rows": valid_interval_count,
        },
        "field_coverage": field_coverage,
        "skill_sidecar": skill_sidecar,
        "model": {
            "trained": False,
            "metrics": None,
            "shap_available": False,
            "training_blockers": training_blockers,
            "reason": "This phase audits label readiness only; it does not train a model.",
        },
        "alternative_source_assessment": {
            "source": "German Federal Employment Agency Entgeltatlas",
            "compatible_as_job_level_training_labels": False,
            "reason": (
                "It provides aggregate occupation/region employment medians, not advertised "
                "salary labels linked to these postings; a validated KldB mapping and a changed "
                "target definition would be required."
            ),
        },
    }
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(_markdown(report), encoding="utf-8")
    return report
