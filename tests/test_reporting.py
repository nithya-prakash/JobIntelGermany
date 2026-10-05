from datetime import date
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from german_job_market.reporting import build_weekly_report
from german_job_market.skills import load_taxonomy

ROOT = Path(__file__).resolve().parents[1]


def test_weekly_cohort_report_marks_gaps_and_uses_skill_shares(tmp_path: Path) -> None:
    jobs_path = tmp_path / "jobs.parquet"
    skills_path = tmp_path / "skills.parquet"
    json_path = tmp_path / "weekly.json"
    markdown_path = tmp_path / "weekly.md"
    taxonomy = load_taxonomy(ROOT / "configs/skill_taxonomy.toml")

    jobs = pa.table(
        {
            "job_id": ["a", "b", "c"],
            "title": ["Data Engineer", "Data Analyst", "Developer"],
            "collection_date": pa.array(
                [date(2023, 1, 2), date(2023, 1, 3), date(2023, 1, 16)],
                type=pa.date32(),
            ),
            "publication_date": pa.array([None, None, None], type=pa.date32()),
            "federal_state": [None, None, None],
            "remote_type": [None, None, None],
            "salary_min": pa.array([None, None, None], type=pa.float64()),
            "salary_max": pa.array([None, None, None], type=pa.float64()),
            "language_requirements": pa.array([None, None, None], type=pa.list_(pa.string())),
            "location": ["Berlin", "Hamburg", "München"],
        }
    )
    skills = pa.table(
        {
            "job_id": ["a", "b", "c"],
            "skill_ids": pa.array(
                [["python", "sql"], ["python"], ["sql"]],
                type=pa.list_(pa.string()),
            ),
        }
    )
    pq.write_table(jobs, jobs_path)
    pq.write_table(skills, skills_path)

    report = build_weekly_report(
        jobs_path,
        skills_path,
        taxonomy,
        json_path,
        markdown_path,
        publisher_described_period="fixture period",
    )

    assert report["summary"]["postings"] == 3
    assert report["summary"]["observed_weeks"] == 2
    assert report["summary"]["calendar_weeks"] == 3
    assert report["missing_week_starts"] == ["2023-01-09"]
    assert report["market_growth_inference_allowed"] is False
    assert report["sidecar_integrity"]["duplicate_job_ids"] == 0
    assert report["sidecar_integrity"]["duplicate_skill_rows"] == 0
    assert report["sidecar_integrity"]["unknown_skill_ids"] == []
    assert report["weeks"][0]["top_skills"][0]["skill_id"] == "python"
    assert report["weeks"][0]["top_skills"][0]["share_pct"] == 100.0
    last_week = report["weeks"][2]
    assert last_week["compared_with_week"] == "2023-01-02"
    assert last_week["calendar_weeks_since_comparison"] == 2
    assert last_week["largest_share_increases"][0]["skill_id"] == "sql"
    assert last_week["largest_share_increases"][0]["share_delta_percentage_points"] == 50.0
    assert report["field_coverage"]["publication_date"]["count"] == 0
    assert json_path.is_file() and markdown_path.is_file()
    assert "not weekly vacancy-demand estimates" in markdown_path.read_text(encoding="utf-8")
