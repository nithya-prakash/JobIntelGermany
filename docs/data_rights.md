# Data rights and release boundary

**Upstream dataset:** "Scraping German Online Job Advertisements to Analyse AI Skill Demand" (Mendeley Data, v2, DOI 10.17632/wnt24rfrwz.2, creator Matthias Kapa). The publisher page labels it CC BY 4.0 and describes raw online job advertisements. That declaration is the only rights evidence this project has. It does not establish that every third-party ad may be redistributed, and no legal conclusion is drawn here. Obtain qualified advice before any redistribution.

## May be committed
Code, configs, tests, documentation, aggregate reports (counts, metrics, hashes), the skill taxonomy, and evaluation files that contain only job IDs, skill IDs, labels and grades (`data/evaluation/**`, excluding local packs).

## Must not be committed or published
- Anything under `data/raw/` or `data/processed/` (ad text, Parquet, DuckDB), including the local reading packs and annotation/judging HTML pages in `data/processed/eval_v2/`.
- Output from `gjmi-match` that includes `snippets` (short quotes from ads).
- Any file with ad titles, descriptions, requirements, responsibilities or benefits.

`scripts/check_release.py` (also run in CI) fails on database/Parquet/ZIP files, files over 1 MB, and JSON/JSONL prose fields. It is a guard, not a proof of compliance.

## What users must obtain themselves
Download the dataset from the publisher (`scripts/download_dataset.py`), then run the pipeline locally. Keep attribution to the creator and the exact snapshot (DOI above).

## Not covered
Personal data: ads may contain identifiers that regex redaction does not remove. CVs must stay local. The MIT license covers this repository's code only.
