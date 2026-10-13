"""Star-schema export of the processed dataset for Power BI.

    python -m german_job_market.bi_export      # writes data/processed/bi/ (gitignored)

Tables: fact_job, bridge_job_skill, dim_skill, agg_skill_by_city,
agg_skill_pairs. Deliberately excludes ad free text (title, description,
requirements ...): the rights review of ad text is not done, so only derived,
non-textual fields leave the pipeline. Most structured columns (federal state,
salary, employment type, ...) are empty in this snapshot and are not exported.
"""
import tomllib
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "processed" / "bi"
TAXONOMY = ROOT / "configs" / "skill_taxonomy.toml"
# Scraper artefact: a UI banner captured in the location field (see docs).
LOCATION_JUNK = ("Sei einer der ersten Bewerber",)
MIN_CITY_JOBS = 200
MIN_PAIR_JOBS = 20


def _create_tables(
    con: duckdb.DuckDBPyConnection, data_dir: Path, taxonomy_path: Path
) -> None:
    skills = tomllib.loads(taxonomy_path.read_text(encoding="utf-8"))["skills"]
    con.execute("CREATE TABLE dim_skill (skill_id VARCHAR, label VARCHAR, category VARCHAR)")
    con.executemany(
        "INSERT INTO dim_skill VALUES (?, ?, ?)",
        [(s["id"], s["label"], s["category"]) for s in skills],
    )
    jobs, job_skills = data_dir / "jobs.parquet", data_dir / "job_skills.parquet"
    junk = ", ".join("?" for _ in LOCATION_JUNK)
    con.execute(
        f"""
        CREATE TABLE fact_job AS
        SELECT j.job_id,
               j.location AS location_raw,
               j.collection_date,
               CASE WHEN j.location IN ({junk}) THEN NULL ELSE j.location END AS city,
               CAST(coalesce(len(s.skill_ids), 0) AS BIGINT) AS skill_count,
               coalesce(len(s.skill_ids), 0) > 0 AS has_skills
        FROM read_parquet(?) j
        LEFT JOIN read_parquet(?) s USING (job_id)
        """,
        [*LOCATION_JUNK, str(jobs), str(job_skills)],
    )
    con.execute(
        """
        CREATE TABLE bridge_job_skill AS
        SELECT job_id, unnest(skill_ids) AS skill_id FROM read_parquet(?)
        """,
        [str(job_skills)],
    )
    con.execute(
        """
        CREATE TABLE agg_skill_by_city AS
        WITH cities AS (
            SELECT city, count(*) AS city_jobs FROM fact_job
            WHERE city IS NOT NULL GROUP BY city HAVING count(*) >= ?
        )
        SELECT f.city, b.skill_id, count(*) AS jobs_with_skill, c.city_jobs,
               round(count(*) / c.city_jobs, 4) AS share_of_city_jobs
        FROM bridge_job_skill b
        JOIN fact_job f USING (job_id)
        JOIN cities c ON c.city = f.city
        GROUP BY f.city, b.skill_id, c.city_jobs
        ORDER BY f.city, b.skill_id
        """,
        [MIN_CITY_JOBS],
    )
    con.execute(
        """
        CREATE TABLE agg_skill_pairs AS
        WITH distinct_skills AS (SELECT DISTINCT job_id, skill_id FROM bridge_job_skill)
        SELECT a.skill_id AS skill_a, b.skill_id AS skill_b, count(*) AS jobs_with_both
        FROM distinct_skills a
        JOIN distinct_skills b ON a.job_id = b.job_id AND a.skill_id < b.skill_id
        GROUP BY a.skill_id, b.skill_id HAVING count(*) >= ?
        ORDER BY jobs_with_both DESC, skill_a, skill_b
        """,
        [MIN_PAIR_JOBS],
    )


def export(
    data_dir: Path = ROOT / "data" / "processed",
    out: Path = OUT,
    taxonomy_path: Path = TAXONOMY,
) -> dict[str, int]:
    out.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    with duckdb.connect() as con:
        _create_tables(con, data_dir, taxonomy_path)
        for name in (
            "fact_job",
            "bridge_job_skill",
            "dim_skill",
            "agg_skill_by_city",
            "agg_skill_pairs",
        ):
            con.execute(f"COPY {name} TO ? (FORMAT parquet)", [str(out / f"{name}.parquet")])
            row = con.execute(f"SELECT count(*) FROM {name}").fetchone()
            counts[name] = int(row[0]) if row else 0
    return counts


if __name__ == "__main__":
    print(export())
