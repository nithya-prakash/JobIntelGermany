from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from german_job_market.salary import audit_salary_data


def _write_salary_fixture(
    path: Path,
    salary_min: list[float | None],
    salary_max: list[float | None],
    currencies: list[str | None],
    periods: list[str | None],
) -> None:
    count = len(salary_min)
    pq.write_table(
        pa.table(
            {
                "job_id": [f"job-{index}" for index in range(count)],
                "salary_min": pa.array(salary_min, type=pa.float64()),
                "salary_max": pa.array(salary_max, type=pa.float64()),
                "salary_currency": currencies,
                "salary_period": periods,
                "title": ["Engineer"] * count,
                "location": [None] * count,
                "federal_state": [None] * count,
                "experience_level": [None] * count,
                "employment_type": [None] * count,
                "remote_type": [None] * count,
                "normalized_skills": pa.array(
                    [[] for _ in range(count)], type=pa.list_(pa.string())
                ),
            }
        ),
        path,
    )


def test_salary_audit_blocks_training_when_labels_are_absent(tmp_path: Path) -> None:
    jobs_path = tmp_path / "jobs.parquet"
    _write_salary_fixture(jobs_path, [None, None], [None, None], [None, None], [None, None])

    report = audit_salary_data(jobs_path, tmp_path / "salary.json", tmp_path / "salary.md")

    assert report["summary"]["postings"] == 2
    assert report["summary"]["valid_eur_period_interval_rows"] == 0
    assert report["field_coverage"]["title"]["count"] == 2
    assert report["field_coverage"]["salary_min"]["count"] == 0
    assert report["model"]["trained"] is False
    assert report["model"]["metrics"] is None
    assert report["model"]["shap_available"] is False
    assert report["model"]["training_blockers"] == [
        "no valid job-level salary intervals are available"
    ]


def test_salary_audit_separates_valid_partial_and_invalid_intervals(tmp_path: Path) -> None:
    jobs_path = tmp_path / "mixed-jobs.parquet"
    _write_salary_fixture(
        jobs_path,
        [3000.0, None, 4000.0, -1.0],
        [4500.0, 3000.0, 5000.0, 1000.0],
        ["EUR", "EUR", "USD", "EUR"],
        ["monthly", "month", "annual", "month"],
    )

    report = audit_salary_data(jobs_path, tmp_path / "salary.json", tmp_path / "salary.md")

    assert report["summary"]["rows_with_salary_any"] == 4
    assert report["summary"]["complete_interval_rows"] == 3
    assert report["summary"]["partial_interval_rows"] == 1
    assert report["summary"]["invalid_numeric_interval_rows"] == 1
    assert report["summary"]["unsupported_unit_rows"] == 1
    assert report["summary"]["valid_eur_period_interval_rows"] == 1
    assert report["model"]["trained"] is False


def test_salary_audit_reports_separate_skill_sidecar(tmp_path: Path) -> None:
    jobs_path = tmp_path / "jobs.parquet"
    _write_salary_fixture(jobs_path, [None, None], [None, None], [None, None], [None, None])
    pq.write_table(
        pa.table(
            {
                "job_id": ["job-0", "job-1", "orphan"],
                "skill_ids": [["python", "sql"], [], ["python"]],
            }
        ),
        tmp_path / "job_skills.parquet",
    )

    report = audit_salary_data(jobs_path, tmp_path / "salary.json", tmp_path / "salary.md")

    assert report["field_coverage"]["normalized_skills"]["count"] == 0
    assert report["skill_sidecar"]["rows"] == 3
    assert report["skill_sidecar"]["postings_with_skills"] == 2
    assert report["skill_sidecar"]["skill_assignments"] == 3
    assert report["skill_sidecar"]["matched_postings_with_skills"] == 1
    assert report["skill_sidecar"]["unmatched_postings_with_skills"] == 1
    assert "1 matched postings with skills" in (tmp_path / "salary.md").read_text()
