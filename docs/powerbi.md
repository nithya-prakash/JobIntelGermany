# Power BI report

`python -m german_job_market.bi_export` (DuckDB over `jobs.parquet` and `job_skills.parquet`, so run `gjmi` and `gjmi-skills extract` first) writes Parquet tables to `data/processed/bi/` (gitignored, like all
derived data). Power BI Desktop → Get data → Parquet → select the five files.

| Table | Grain |
|---|---|
| `fact_job` | one row per ad: `job_id`, `city`, `location_raw`, `collection_date`, `skill_count`, `has_skills` |
| `bridge_job_skill` | one row per (ad, skill) |
| `dim_skill` | taxonomy skill: `skill_id`, `label`, `category` |
| `agg_skill_by_city` | cities with ≥200 ads × skill: `jobs_with_skill`, `share_of_city_jobs` |
| `agg_skill_pairs` | skill pairs found together in ≥20 ads |

Relationships: `dim_skill[skill_id]` 1→* `bridge_job_skill[skill_id]`; `fact_job[job_id]` 1→*
`bridge_job_skill[job_id]`; `dim_skill[skill_id]` 1→* `agg_skill_by_city[skill_id]`.

```DAX
Jobs = DISTINCTCOUNT(bridge_job_skill[job_id])
Skill Share = DIVIDE([Jobs], CALCULATE(COUNTROWS(fact_job), ALL(bridge_job_skill)))
Ads With Skills % = DIVIDE(CALCULATE(COUNTROWS(fact_job), fact_job[has_skills] = TRUE()), COUNTROWS(fact_job))
```

## Read before publishing a report
- Snapshot is the Stepstone 2023 Mendeley dataset, not live data. `collection_date` is when it was scraped, not a trend over years.
- About 38% of ads have no recognised skill; skill counts describe the taxonomy (63 skills), not all skills.
- Skill extraction is rule/LLM-assisted with a measured test F1 of 0.765 (see `reports/phase11`); treat shares as approximate.
- Federal state, salary, employment type and experience level are empty in this snapshot, so there are no state or salary visuals.
- `city` is blank for 53,764 ads: ~51k where the scraper captured the banner text "Sei einer der ersten Bewerber" and ~2.6k with no location at all; `location_raw` keeps the original value.
- Ad text (title, description, requirements) is excluded: the rights review of ad text is not done.
