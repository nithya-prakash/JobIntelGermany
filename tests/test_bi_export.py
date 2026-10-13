from pathlib import Path

import duckdb
import pytest

from german_job_market import bi_export as bi

TAXONOMY = bi.ROOT / "configs" / "skill_taxonomy.toml"


def _write_inputs(data_dir: Path) -> None:
    con = duckdb.connect()
    con.execute(
        """COPY (SELECT * FROM (VALUES
            ('a', 'Berlin', '2023-04-04'),
            ('b', 'Berlin', '2023-04-04'),
            ('c', 'Sei einer der ersten Bewerber', '2023-04-04')
        ) t(job_id, location, collection_date))
        TO ? (FORMAT parquet)""",
        [str(data_dir / "jobs.parquet")],
    )
    con.execute(
        """COPY (SELECT * FROM (VALUES
            ('a', ['python', 'sql']),
            ('b', CAST([] AS VARCHAR[])),
            ('c', ['python'])
        ) t(job_id, skill_ids))
        TO ? (FORMAT parquet)""",
        [str(data_dir / "job_skills.parquet")],
    )


@pytest.fixture
def exported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, list[dict[str, object]]]:
    monkeypatch.setattr(bi, "MIN_CITY_JOBS", 2)
    monkeypatch.setattr(bi, "MIN_PAIR_JOBS", 1)
    _write_inputs(tmp_path)
    out = tmp_path / "bi"
    counts = bi.export(tmp_path, out, TAXONOMY)
    assert counts["fact_job"] == 3
    con = duckdb.connect()
    tables: dict[str, list[dict[str, object]]] = {}
    for name in counts:
        cur = con.execute(f"SELECT * FROM read_parquet('{out / name}.parquet')")
        cols = [d[0] for d in cur.description]
        tables[name] = [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]
    return tables


def test_fact_job_flags_scraper_artefact_and_counts_skills(exported):
    fact = {r["job_id"]: r for r in exported["fact_job"]}
    assert fact["a"]["city"] == "Berlin"
    assert fact["c"]["city"] is None
    assert fact["c"]["location_raw"] == "Sei einer der ersten Bewerber"
    assert [fact[j]["skill_count"] for j in "abc"] == [2, 0, 1]
    assert [fact[j]["has_skills"] for j in "abc"] == [True, False, True]


def test_bridge_drops_jobs_without_skills(exported):
    pairs = sorted((r["job_id"], r["skill_id"]) for r in exported["bridge_job_skill"])
    assert pairs == [("a", "python"), ("a", "sql"), ("c", "python")]


def test_agg_skill_by_city_applies_min_job_threshold(exported):
    agg = exported["agg_skill_by_city"]
    assert {r["city"] for r in agg} == {"Berlin"}
    python = next(r for r in agg if r["skill_id"] == "python")
    assert python["share_of_city_jobs"] == 0.5
    assert python["city_jobs"] == 2


def test_agg_skill_pairs(exported):
    assert exported["agg_skill_pairs"] == [
        {"skill_a": "python", "skill_b": "sql", "jobs_with_both": 1}
    ]


def test_export_has_documented_columns(exported):
    assert set(exported["fact_job"][0]) == {
        "job_id", "location_raw", "collection_date", "city", "skill_count", "has_skills"
    }
    assert set(exported["dim_skill"][0]) == {"skill_id", "label", "category"}
    assert set(exported) == {
        "fact_job", "bridge_job_skill", "dim_skill", "agg_skill_by_city", "agg_skill_pairs"
    }


def test_dim_skill_reads_real_taxonomy(exported):
    ids = [r["skill_id"] for r in exported["dim_skill"]]
    assert {"python", "java"} <= set(ids) and len(ids) == len(set(ids))
