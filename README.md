# German Job Market Intelligence

[![CI](https://github.com/nithya-prakash/JobIntelGermany/actions/workflows/ci.yml/badge.svg)](https://github.com/nithya-prakash/JobIntelGermany/actions/workflows/ci.yml)
![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)
![License MIT](https://img.shields.io/badge/license-MIT-green)

A reproducible, privacy-conscious research pipeline over 342,058 German job ads: it normalizes a published snapshot, extracts skills with an explainable bilingual (German/English) lexicon, reports historical skill trends, and ranks postings against a skill profile. It also includes honest readiness audits for the parts that cannot be built yet. This is a local research prototype, not a production platform.

## Headline results

| What | Result | Read with |
| --- | --- | --- |
| Ingestion | 342,452 rows read, 394 duplicates removed, 342,058 written, 4,408 phone numbers redacted; identical hashes on a clean rebuild | Single historical source |
| Skill extraction (taxonomy 0.2.2, 63 skills) | Test split: precision 0.949, recall 0.640, F1 0.765 (106 ads) | Gold labels are LLM-annotated and LLM-adjudicated, with one human annotator (kappa 0.51) |
| Matching vs random baseline | P@10 0.853 vs 0.143; MRR 0.950 vs 0.308 | 30 synthetic skill-list queries, one judge, pool-relative recall |

The score is taxonomy overlap, not suitability or hiring probability. Details and caveats: [`docs/phase_log.md`](docs/phase_log.md), [`docs/project_audit.md`](docs/project_audit.md).

## Quickstart

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/). The download is about 325 MB.

```bash
uv sync --no-editable --extra dev
.venv/bin/python scripts/download_dataset.py     # pinned Mendeley archive, ignored by Git
.venv/bin/gjmi                                   # normalize -> Parquet + DuckDB
.venv/bin/gjmi-skills extract                    # skill sidecar
.venv/bin/gjmi-demo                              # open http://127.0.0.1:8765
```

With `--no-editable`, code changes need `uv sync --no-editable --extra dev --reinstall-package german-job-market-intelligence`.

## Data

Mendeley Data dataset [10.17632/wnt24rfrwz.2](https://doi.org/10.17632/wnt24rfrwz.2), German Stepstone ads collected 2023, listed as CC BY 4.0. Attribution: Kapa, Matthias. "Scraping German Online Job Advertisements to Analyse AI Skill Demand." Mendeley Data, v2. This project uses only that published snapshot and does not scrape any site. Raw and processed data are git-ignored; the upstream rights chain for the ad text has not been independently reviewed, so do not publish ad text or the generated Parquet. See [`docs/data_rights.md`](docs/data_rights.md).

## What is in it

| Area | Status |
| --- | --- |
| Ingestion, redaction, dedup, Parquet/DuckDB | Implemented |
| Skill extraction (63-skill bilingual taxonomy) | Implemented, narrow baseline |
| Weekly skill-share report | Implemented, descriptive only |
| Skill co-occurrence vectors | Exploratory; clusters unstable |
| Candidate/job matching and skill gaps | Implemented, pilot-benchmarked |
| Local web demo (`gjmi-demo`) | Implemented, local only |
| Evaluation tooling (`gjmi-eval`) | Implemented |
| Salary, translation, LLM fine-tuning, serving | Readiness audits only; blocked by missing labels or models |
| Responsible AI / EU AI Act risk assessment | Preliminary documentation |

## How it works

Ingestion streams the archive, validates a Pydantic schema, redacts email and phone patterns, deduplicates by URL and writes Parquet. Extraction uses a token trie with longest-match resolution, a case-sensitive alias list for ambiguous tokens and an `exclusions` list for false friends (for example `communication protocols`). Matching scores each posting by the harmonic mean of candidate-skill precision and job-skill coverage. Everything is deterministic and CPU-local.

## Usage

```bash
.venv/bin/gjmi-match match --profile profile.json --top-k 10   # {"skill_ids": ["python", "sql"]}
.venv/bin/gjmi-match match --cv my_cv.txt                       # CV text processed in memory
.venv/bin/gjmi-skills evaluate                                  # pilot v1 (deprecated as an accuracy claim)
.venv/bin/gjmi-eval skill-score                                 # v2 benchmark
.venv/bin/gjmi-eval match-score                                 # matching benchmark
```

## Limitations

- One historical source, focused on AI-skill demand; collection dates are not posting dates, so this is not a current market census.
- Extraction recall is about 0.64 on the test split; it cannot tell `required` from `mentioned` contexts and cannot match words without boundaries (`NLPFundierte`).
- Benchmark labels are not independently human-reviewed, and the matching queries are synthetic.
- "Skills not in your profile" is not a verified requirement list. Do not use this for employment decisions.
- The demo has no authentication, rate limiting or retention policy and must stay local.

## Repository layout

`src/german_job_market/` code · `configs/` taxonomy · `data/evaluation/` labels and manifests (no ad text) · `reports/` measured outputs · `docs/` phase log, audit, data rights, responsible AI · `scripts/` download and release checks · `tests/`

## Checks

```bash
.venv/bin/python -m pytest && .venv/bin/ruff check . && .venv/bin/mypy src scripts && .venv/bin/python scripts/check_release.py
```

## Roadmap

Independent human review of labels and real candidate queries; data-rights review; salary labels, a translation reference set and a model for fine-tuning and serving; semantic embeddings.

## License

MIT. Data attribution above; dataset terms apply to the data.
