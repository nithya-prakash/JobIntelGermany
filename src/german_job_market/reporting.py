"""Historical, collection-cohort reporting with explicit limits on trend claims."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import duckdb

from german_job_market.skills import SkillTaxonomy


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.name


def _pct(numerator: int, denominator: int) -> float:
    return round(100 * numerator / denominator, 4) if denominator else 0.0


def _required_row(result: Any) -> tuple[Any, ...]:
    row = result.fetchone()
    if row is None:
        raise ValueError("expected query to return one row")
    return cast(tuple[Any, ...], row)


def _deltas(
    current: dict[str, int],
    current_total: int,
    previous: dict[str, int],
    previous_total: int,
    taxonomy: SkillTaxonomy,
    limit: int = 5,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    for skill in taxonomy.skills:
        now = current.get(skill.id, 0)
        before = previous.get(skill.id, 0)
        now_share = now / current_total if current_total else 0.0
        before_share = before / previous_total if previous_total else 0.0
        delta = now_share - before_share
        if delta:
            rows.append(
                {
                    "skill_id": skill.id,
                    "label": skill.label,
                    "current_postings": now,
                    "previous_postings": before,
                    "current_share_pct": round(now_share * 100, 4),
                    "previous_share_pct": round(before_share * 100, 4),
                    "share_delta_percentage_points": round(delta * 100, 4),
                }
            )
    increases = sorted(
        (row for row in rows if row["share_delta_percentage_points"] > 0),
        key=lambda row: (-row["share_delta_percentage_points"], row["skill_id"]),
    )[:limit]
    decreases = sorted(
        (row for row in rows if row["share_delta_percentage_points"] < 0),
        key=lambda row: (row["share_delta_percentage_points"], row["skill_id"]),
    )[:limit]
    return increases, decreases


def _markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    coverage = report["field_coverage"]
    described_period = report["publisher_described_collection_period"] or "not supplied"
    lines = [
        "# German Job Market Intelligence — collection-cohort report",
        "",
        f"Generated: {report['generated_at_utc']}",
        "",
        "> **Interpretation:** these are historical skill matches grouped by collection date. "
        "They are not weekly vacancy-demand estimates or current market trends.",
        "",
        "## Data snapshot",
        "",
        f"- Postings: {summary['postings']:,}",
        f"- Collection dates: {summary['collection_date_min']} to {summary['collection_date_max']}",
        f"- Publisher-described period: {described_period}",
        f"- Observed collection weeks: {summary['observed_weeks']} of {summary['calendar_weeks']}",
        f"- Weeks without records: {', '.join(report['missing_week_starts']) or 'none'}",
        f"- Postings with at least one matched skill: {summary['postings_with_skill_matches']:,}",
        f"- Posting-skill assignments: {summary['skill_assignments']:,}",
        f"- Observed weekly posting counts: "
        f"{summary['min_weekly_postings']:,}–{summary['max_weekly_postings']:,}",
        "",
        f"The source describes its collection period as {described_period}, while the retained "
        f"`collection_date` values span {summary['collection_date_min']} to "
        f"{summary['collection_date_max']}. Collection volume is irregular and "
        "publication dates are absent. "
        "Week-to-week changes below are descriptive comparisons of scrape cohorts only.",
        "",
        "## Weekly collection cohorts",
        "",
        "Shares are the fraction of postings in a collection week matched to a skill. "
        "Changes compare "
        "with the previous observed week, even when calendar weeks are missing.",
        "",
        "| Week starting | Postings | Top matched skills | "
        "Largest share increases vs prior observed week |",
        "| --- | ---: | --- | --- |",
    ]
    for week in report["weeks"]:
        if not week["has_observations"]:
            lines.append(f"| {week['week_start']} | 0 | — | No observations |")
            continue
        top = (
            "; ".join(
                f"{item['label']} ({item['postings']:,}; {item['share_pct']:.2f}%)"
                for item in week["top_skills"][:3]
            )
            or "No taxonomy matches"
        )
        increases = week["largest_share_increases"]
        delta_text = (
            "; ".join(
                f"{item['label']} ({item['share_delta_percentage_points']:+.3f} pp)"
                for item in increases[:3]
            )
            if increases
            else "—"
        )
        lines.append(f"| {week['week_start']} | {week['postings']:,} | {top} | {delta_text} |")

    lines.extend(
        [
            "",
            "## Data availability",
            "",
            "| Field or analysis | Present records | Availability |",
            "| --- | ---: | --- |",
        ]
    )
    for field in (
        "publication_date",
        "federal_state",
        "remote_type",
        "salary_min",
        "salary_max",
        "language_requirements",
    ):
        coverage_item = coverage[field]
        lines.append(
            f"| {field} | {coverage_item['count']:,} / {coverage_item['total']:,} | "
            f"{'available' if coverage_item['count'] else 'unavailable'} |"
        )
    lines.extend(
        [
            "",
            "Geographic trends are omitted: federal-state labels are empty; although location is "
            f"populated for {coverage['location']['count']:,} postings, those values are free text "
            "and have not been mapped to regions. Salary, remote-work, and language-requirement "
            "trends are omitted because their structured fields have no populated values. "
            "Job-family counts are also omitted: the "
            "source has titles but no validated job-family labels.",
            "",
            "## Reproduction",
            "",
            "Run `.venv/bin/gjmi-report` after reproducing Phase 1 and generating the "
            "Phase 2 skill sidecar.",
            "The machine-readable output includes checksums, coverage counts, missing weeks, "
            "skill shares.",
            "",
        ]
    )
    return "\n".join(lines)


def build_weekly_report(
    jobs_path: Path,
    skills_path: Path,
    taxonomy: SkillTaxonomy,
    json_path: Path,
    markdown_path: Path,
    publisher_described_period: str | None = None,
) -> dict[str, Any]:
    """Aggregate skill matches by collection week without implying market demand."""
    for path in (jobs_path, skills_path):
        if not path.is_file():
            raise FileNotFoundError(path)

    connection = duckdb.connect()
    try:
        job_columns = {
            row[0]
            for row in connection.execute(
                "DESCRIBE SELECT * FROM read_parquet(?)", [str(jobs_path)]
            ).fetchall()
        }
        skill_columns = {
            row[0]
            for row in connection.execute(
                "DESCRIBE SELECT * FROM read_parquet(?)", [str(skills_path)]
            ).fetchall()
        }
        required_jobs = {
            "job_id",
            "title",
            "collection_date",
            "publication_date",
            "federal_state",
            "remote_type",
            "salary_min",
            "salary_max",
            "language_requirements",
            "location",
        }
        if missing := required_jobs.difference(job_columns):
            raise ValueError(f"job input missing required columns: {sorted(missing)}")
        if not {"job_id", "skill_ids"}.issubset(skill_columns):
            raise ValueError("skill input must have job_id and skill_ids columns")

        coverage_row = _required_row(
            connection.execute(
                """SELECT count(*) AS total,
                      count(collection_date) AS collection_date,
                      count(publication_date) AS publication_date,
                      count(federal_state) AS federal_state,
                      count(remote_type) AS remote_type,
                      count(salary_min) AS salary_min,
                      count(salary_max) AS salary_max,
                      count(language_requirements) AS language_requirements,
                      count(location) AS location,
                      min(collection_date) AS collection_min,
                      max(collection_date) AS collection_max
               FROM read_parquet(?)""",
                [str(jobs_path)],
            )
        )
        total = int(coverage_row[0])
        field_names = [
            "collection_date",
            "publication_date",
            "federal_state",
            "remote_type",
            "salary_min",
            "salary_max",
            "language_requirements",
            "location",
        ]
        field_coverage = {
            name: {"count": int(coverage_row[index + 1]), "total": total}
            for index, name in enumerate(field_names)
        }
        collection_min = coverage_row[9]
        collection_max = coverage_row[10]
        if collection_min is None or collection_max is None:
            raise ValueError("no collection dates are available for weekly aggregation")

        sidecar_row = _required_row(
            connection.execute(
                """SELECT count(*) AS total,
                      count(*) FILTER (WHERE len(skill_ids) > 0) AS with_skills,
                      coalesce(sum(len(skill_ids)), 0) AS assignments
               FROM read_parquet(?)""",
                [str(skills_path)],
            )
        )
        sidecar_rows = int(sidecar_row[0])
        duplicate_job_ids = int(
            _required_row(
                connection.execute(
                    """SELECT count(*) - count(DISTINCT job_id)
                   FROM read_parquet(?)""",
                    [str(jobs_path)],
                )
            )[0]
        )
        duplicate_skill_rows = int(
            _required_row(
                connection.execute(
                    """SELECT count(*) - count(DISTINCT job_id)
                   FROM read_parquet(?)""",
                    [str(skills_path)],
                )
            )[0]
        )
        orphan_sidecar_ids = int(
            _required_row(
                connection.execute(
                    """SELECT count(*) FROM read_parquet(?) AS s
                   LEFT JOIN read_parquet(?) AS j USING(job_id)
                   WHERE j.job_id IS NULL""",
                    [str(skills_path), str(jobs_path)],
                )
            )[0]
        )
        unmatched_job_ids = int(
            _required_row(
                connection.execute(
                    """SELECT count(*) FROM read_parquet(?) AS j
                   LEFT JOIN read_parquet(?) AS s USING(job_id)
                   WHERE s.job_id IS NULL""",
                    [str(jobs_path), str(skills_path)],
                )
            )[0]
        )
        if (
            sidecar_rows != total
            or orphan_sidecar_ids
            or unmatched_job_ids
            or duplicate_job_ids
            or duplicate_skill_rows
        ):
            raise ValueError(
                "job/skill sidecar IDs do not form a one-to-one match "
                f"(jobs={total}, sidecar={sidecar_rows}, orphan_sidecar={orphan_sidecar_ids}, "
                f"unmatched_jobs={unmatched_job_ids}, duplicate_jobs={duplicate_job_ids}, "
                f"duplicate_skill_rows={duplicate_skill_rows})"
            )

        distinct_skill_ids = {
            row[0]
            for row in connection.execute(
                "SELECT DISTINCT unnest(skill_ids) FROM read_parquet(?)", [str(skills_path)]
            ).fetchall()
        }
        unknown_skill_ids = sorted(distinct_skill_ids.difference(taxonomy.by_id))
        if unknown_skill_ids:
            raise ValueError(f"sidecar has skill IDs missing from taxonomy: {unknown_skill_ids}")

        weekly_rows = connection.execute(
            """SELECT CAST(date_trunc('week', collection_date) AS DATE) AS week_start,
                      count(*) AS postings
               FROM read_parquet(?)
               WHERE collection_date IS NOT NULL
               GROUP BY 1 ORDER BY 1""",
            [str(jobs_path)],
        ).fetchall()
        skill_rows = connection.execute(
            """SELECT CAST(date_trunc('week', j.collection_date) AS DATE) AS week_start,
                      u.skill_id,
                      count(*) AS postings
               FROM read_parquet(?) AS j
               JOIN read_parquet(?) AS s USING(job_id),
                    UNNEST(s.skill_ids) AS u(skill_id)
               WHERE j.collection_date IS NOT NULL
               GROUP BY 1, 2 ORDER BY 1, 2""",
            [str(jobs_path), str(skills_path)],
        ).fetchall()
    finally:
        connection.close()

    weekly_counts = {row[0]: int(row[1]) for row in weekly_rows}
    skills_by_week: dict[date, dict[str, int]] = {}
    for week_start, skill_id, count in skill_rows:
        skills_by_week.setdefault(week_start, {})[skill_id] = int(count)

    first_week = min(weekly_counts)
    last_week = max(weekly_counts)
    all_weeks: list[date] = []
    week_start = first_week
    while week_start <= last_week:
        all_weeks.append(week_start)
        week_start += timedelta(days=7)

    weeks: list[dict[str, Any]] = []
    previous_observed_week: date | None = None
    for week_start in all_weeks:
        postings = weekly_counts.get(week_start, 0)
        skill_counts = skills_by_week.get(week_start, {})
        observed = postings > 0
        week_report: dict[str, Any] = {
            "week_start": week_start.isoformat(),
            "has_observations": observed,
            "postings": postings,
            "skill_assignments": sum(skill_counts.values()),
            "top_skills": [
                {
                    "skill_id": skill_id,
                    "label": taxonomy.by_id[skill_id].label,
                    "postings": count,
                    "share_pct": _pct(count, postings),
                }
                for skill_id, count in sorted(
                    skill_counts.items(), key=lambda item: (-item[1], item[0])
                )[:10]
            ],
            "compared_with_week": None,
            "calendar_weeks_since_comparison": None,
            "largest_share_increases": [],
            "largest_share_decreases": [],
        }
        if observed and previous_observed_week is not None:
            increases, decreases = _deltas(
                skill_counts,
                postings,
                skills_by_week.get(previous_observed_week, {}),
                weekly_counts[previous_observed_week],
                taxonomy,
            )
            week_report["compared_with_week"] = previous_observed_week.isoformat()
            week_report["calendar_weeks_since_comparison"] = (
                week_start - previous_observed_week
            ).days // 7
            week_report["largest_share_increases"] = increases
            week_report["largest_share_decreases"] = decreases
        if observed:
            previous_observed_week = week_start
        weeks.append(week_report)

    missing_weeks = [week["week_start"] for week in weeks if not week["has_observations"]]
    weekly_volumes = list(weekly_counts.values())
    all_skill_counts: dict[str, int] = {}
    for values in skills_by_week.values():
        for skill_id, count in values.items():
            all_skill_counts[skill_id] = all_skill_counts.get(skill_id, 0) + count

    report: dict[str, Any] = {
        "phase": 3,
        "report_type": "historical_collection_cohorts",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "publisher_described_collection_period": publisher_described_period,
        "temporal_basis": "collection_date (source field date_scrape)",
        "market_growth_inference_allowed": False,
        "trend_interpretation": (
            "Weekly values and share deltas describe this dataset's collection cohorts only. "
            "They are not estimates of weekly vacancy demand or current German labor-market trends."
        ),
        "inputs": {
            "jobs_path": _display_path(jobs_path),
            "jobs_sha256": _sha256(jobs_path),
            "skills_path": _display_path(skills_path),
            "skills_sha256": _sha256(skills_path),
            "taxonomy_version": taxonomy.version,
            "taxonomy_sha256": taxonomy.fingerprint,
            "taxonomy_size": len(taxonomy.skills),
        },
        "summary": {
            "postings": total,
            "postings_with_collection_dates": field_coverage["collection_date"]["count"],
            "postings_with_skill_matches": int(sidecar_row[1]),
            "skill_assignments": int(sidecar_row[2]),
            "collection_date_min": collection_min.isoformat(),
            "collection_date_max": collection_max.isoformat(),
            "observed_weeks": len(weekly_counts),
            "calendar_weeks": len(all_weeks),
            "missing_weeks": len(missing_weeks),
            "min_weekly_postings": min(weekly_volumes),
            "max_weekly_postings": max(weekly_volumes),
            "max_to_min_weekly_volume_ratio": round(max(weekly_volumes) / min(weekly_volumes), 2),
            "unique_skills_observed": len(all_skill_counts),
            "top_skills_by_posting_count": [
                {
                    "skill_id": skill_id,
                    "label": taxonomy.by_id[skill_id].label,
                    "postings": count,
                    "share_of_all_postings_pct": _pct(count, total),
                }
                for skill_id, count in sorted(
                    all_skill_counts.items(), key=lambda item: (-item[1], item[0])
                )[:20]
            ],
        },
        "field_coverage": field_coverage,
        "sidecar_integrity": {
            "jobs_rows": total,
            "skill_rows": sidecar_rows,
            "orphan_skill_rows": orphan_sidecar_ids,
            "jobs_without_skill_rows": unmatched_job_ids,
            "duplicate_job_ids": duplicate_job_ids,
            "duplicate_skill_rows": duplicate_skill_rows,
            "unknown_skill_ids": unknown_skill_ids,
        },
        "missing_week_starts": missing_weeks,
        "weeks": weeks,
        "unavailable_analyses": {
            "publication_week_trends": "publication_date has no populated values",
            "geographic_trends": "federal_state has no populated values",
            "remote_work_trends": "remote_type has no populated values",
            "salary_trends": "salary_min and salary_max have no populated values",
            "job_family_volume": "no validated job-family field is available",
            "language_requirements": "language_requirements has no populated values",
        },
    }

    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(_markdown(report), encoding="utf-8")
    return report
