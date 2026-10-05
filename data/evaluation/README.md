# Phase 2 skill labels

`skill_gold_v1.jsonl` contains 17 posting IDs from the local Phase 1 snapshot, with a manually curated set of canonical skill IDs and a primary text-language label: 8 German and 9 English postings. It stores no job-ad text. The evaluator joins these IDs to the local Parquet snapshot at run time.

The sample was purposively selected to cover a range of taxonomy categories and is enriched for technology roles and explicit skill mentions. It is not random or representative of all 342,058 postings. Metrics describe this small challenge sample only.

The label unit is binary posting-skill presence across the title and combined ad text. A label means the posting uses the concept as a tool, technology, method, or competency; a mere unrelated word occurrence is not a positive. Only concepts in `configs/skill_taxonomy.toml` are annotated. Unsupported skills, including ambiguous one-letter languages such as R, are outside the evaluation vocabulary.

These are agent-assisted manual annotations based on the actual source postings, not independent or double-coded human labels. A human reviewer should verify the labels before using the scores as portfolio performance claims. Language refers to the primary language of the ad body; mixed-language ads are possible.

The source text remains in ignored local data. Recreate it with the Phase 1 download and ingestion steps before running `gjmi-skills evaluate` from a clean checkout.
