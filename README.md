# German Job Market Intelligence

Phases 1–10 establish a reproducible, privacy-conscious data foundation, a measured bilingual skill-extraction baseline, historical cohort reporting, exploratory distributional skill vectors, skills-only candidate/job matching, salary and translation readiness audits, an LLM fine-tuning readiness gate, an inference-serving readiness gate, and a preliminary responsible-AI risk assessment. The system ingests one fixed research snapshot, validates a canonical schema, removes direct email and phone patterns from retained text, deduplicates records, and writes Parquet plus a DuckDB view. Phase 2 adds a versioned seed taxonomy and deterministic extraction; Phase 4 analyzes skill co-occurrences without downloading a language model.

## Phase 1 source

The pinned input is Mendeley Data dataset **10.17632/wnt24rfrwz.2**, listed as CC BY 4.0. Its publisher describes German Stepstone job advertisements collected in May–June 2023. This is a historical, single-source corpus focused on AI-skill demand; it is not a current or representative census of German vacancies. The pipeline uses only the published snapshot and does not scrape Stepstone or the BA portal.

Attribution: Kapa, Matthias. “Scraping German Online Job Advertisements to Analyse AI Skill Demand.” Mendeley Data, version 2, DOI [10.17632/wnt24rfrwz.2](https://doi.org/10.17632/wnt24rfrwz.2), CC BY 4.0.

## Reproduce Phase 1

Python 3.12 or newer is required.

```bash
uv sync --no-editable --extra dev
.venv/bin/python scripts/download_dataset.py
.venv/bin/gjmi
.venv/bin/python -m pytest
.venv/bin/ruff check .
.venv/bin/mypy src scripts
```

The source archive is downloaded under `data/raw/` and ignored by Git. It can contain full job-ad text, so do not publish or commit it. The normalized dataset is written to `data/processed/jobs.parquet`, a read-only DuckDB view is created at `data/processed/jobs.duckdb`, and measured results are written to `reports/phase1/quality.json`. Open DuckDB from the project root and query `SELECT * FROM jobs LIMIT 10`.

The pipeline records collection dates separately from publication dates; relative date strings are not guessed. Fields absent from the source remain null. The source archive checksum, exact output schema, field coverage, rejected-row reasons, duplicate count, direct-contact redactions, and semantic output hash are included in the report.

## Measured Phase 1 run

Run on 4 October 2026 against the pinned v2 archive. These are observed pipeline results, not model metrics:

| Check | Result |
| --- | ---: |
| Source rows read | 342,452 |
| Invalid rows | 0 |
| Duplicate source URLs removed | 394 |
| Normalized rows written | 342,058 |
| Phone-number matches redacted | 4,408 |
| Email matches redacted | 0 |
| Output rows with an email/phone pattern remaining | 0 |
| Collection date coverage | 342,058 / 342,058 |

The published page describes a May–June 2023 collection period, but the records’ `date_scrape` values span **2023-04-04 through 2023-07-23**. This discrepancy is retained in the quality report; `date_scrape` is treated as collection date and is not presented as posting date. A complete second run produced the same row count and identical semantic and Parquet SHA-256 hashes. See [`reports/phase1/quality.json`](reports/phase1/quality.json) for field coverage and checksums.

## Phase 2: skill extraction

`configs/skill_taxonomy.toml` defines 63 canonical skills, categories, and German/English aliases. The taxonomy is a curated seed—not a claim of complete market coverage or an ESCO mapping. A token trie performs case-aware matching, uses longest aliases to resolve overlaps, and emits each canonical ID once per posting. The approach is CPU-local and deliberately explainable; it does not infer unlisted skills or use context-sensitive NER.

The batch pipeline reads the existing Parquet in Arrow batches and writes only `job_id` plus `skill_ids` to the ignored local sidecar `data/processed/job_skills.parquet`. It does not duplicate job text. On 4 October 2026, the full run processed 342,058 postings: 212,218 had at least one match (taxonomy 0.2.2), with 357,681 posting-skill assignments across all 63 taxonomy entries. The top raw posting counts were Teamwork 106,901, Communication 90,982, and SAP 38,405. These are raw lexicon matches, not validated skill-demand statistics; soft-skill phrases and employer/product names can cause context errors.

The measured closed-set evaluation uses 17 actual postings (8 German, 9 English), purposively selected for skill coverage. It has 128 labeled posting-skill pairs. Agent-assisted manual labels have not been independently reviewed; the sample is too small and too enriched for technology jobs to represent corpus-wide performance.

| Evaluation slice | Gold pairs | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: |
| Overall | 128 | 0.9922 | 0.9922 | 0.9922 |
| German ads | 57 | 1.0000 | 0.9825 | 0.9912 |
| English ads | 71 | 0.9861 | 1.0000 | 0.9930 |
| Machine learning / AI category | 4 | 1.0000 | 0.7500 | 0.8571 |
| Soft skills category | 19 | 0.9500 | 1.0000 | 0.9744 |

The pilot found one false positive: “communication protocols” was labeled as the soft skill Communication. It missed NLP in `NLPFundierte`, where the source text has no word boundary. Exact counts and per-category scores are in [`reports/phase2/skill_eval.json`](reports/phase2/skill_eval.json); sample design and annotation limits are in [`data/evaluation/README.md`](data/evaluation/README.md). The benchmark must be independently reviewed before presenting its score as a portfolio claim.

### Reproduce Phase 2

After reproducing Phase 1 and preparing `data/processed/jobs.parquet`, run:

```bash
.venv/bin/gjmi-skills extract
.venv/bin/gjmi-skills evaluate
```

The extract report records source/taxonomy/output checksums, row and match counts, and the most frequent raw matches in [`reports/phase2/skill_extraction.json`](reports/phase2/skill_extraction.json). To query output with DuckDB, read `data/processed/job_skills.parquet` and join it to the jobs table on `job_id`.

## Phase 3: historical intelligence report

Phase 3 groups the retained skill matches by `collection_date` (the source's `date_scrape`) and produces adjacent-week comparisons of skill share. It validates that the skill sidecar is one-to-one with the jobs table, checks skill IDs against the taxonomy, and includes source checksums, field coverage, and missing calendar weeks in the machine-readable output.

Run after reproducing Phases 1 and 2:

```bash
.venv/bin/gjmi-report
```

On 4 October 2026, the report processed all **342,058** postings. Collection dates span **2023-04-04 through 2023-07-23**; 11 of 16 calendar weeks contain records, with five missing weeks. Weekly cohort sizes range from **360 to 98,769** (274.36×). The skill sidecar contains **179,607** postings with a match and **295,664** posting-skill assignments. These describe this source's collection process, not changes in German job demand. In particular, the report compares skill shares with the previous observed cohort, even across missing weeks.

Data gaps block other requested trend dimensions: publication-date, federal-state, remote-type, salary, and language-requirement values are absent. A free-text location is present for 339,422 postings, but it has not been mapped to regions. The report also flags that the publisher describes a May–June 2023 collection period while record collection dates span April–July 2023. Consequently, it does not infer growth or current market trends, salary trends, geographic trends, remote-work trends, or job-family volume. Skill counts are lexicon matches from Phase 2 and inherit that phase's coverage and context-error limitations.

Outputs: [`reports/phase3/weekly_intelligence.md`](reports/phase3/weekly_intelligence.md) and [`reports/phase3/weekly_intelligence.json`](reports/phase3/weekly_intelligence.json). The JSON records checksums, per-week skill shares and deltas, coverage, missing weeks, and sidecar integrity checks.

## Phase 4: skill co-occurrence embeddings

The project environment has no installed sentence-embedding model or ML runtime, and downloading a multi-lingual model would add a large, hardware-sensitive dependency. Phase 4 therefore builds a deliberately narrower, interpretable representation: each of the 63 taxonomy skills is represented by its positive pointwise mutual information (PPMI) with every other taxonomy skill across postings. Cosine similarity feeds deterministic average-linkage clustering. The CLI uses the existing Arrow/Parquet stack and adds no dependency.

Reproduce after Phases 1 and 2:

```bash
.venv/bin/gjmi-embed
```

The 4 October 2026 run processed **342,058** postings, yielding 63 vectors of 63 dimensions and **1,697** observed skill pairs. Average-linkage clustering selected 2 clusters (sizes **61 and 2**) with a cosine silhouette of **0.6517**. However, deterministic split-half adjusted Rand index was **-0.0161**, indicating near-zero agreement between the two halves. The high in-sample silhouette did not translate into stable groups; treat cluster membership as a diagnostic output, not meaningful job families. The most frequent co-occurrence was Communication + Teamwork in 17,133 postings; this is a corpus count of lexicon matches, not a market-demand estimate.

Outputs: [`reports/phase4/skill_embeddings.md`](reports/phase4/skill_embeddings.md) and [`reports/phase4/skill_embeddings.json`](reports/phase4/skill_embeddings.json). JSON includes every PPMI vector, nearest skill associations, cluster membership, input checksum, silhouette, and split-half stability. This phase does **not** create semantic embeddings for job descriptions, titles, or CVs; the representation is limited to the Phase 2 vocabulary and inherits its extraction errors. Historical, irregular source collection further limits interpretation.

## Phase 5: candidate/job matching and skill gaps

`gjmi-match match` accepts either a structured profile containing canonical `skill_ids` or a local UTF-8 CV file. CV text is read in memory and passed through the Phase 2 German/English lexicon; the raw text is neither written to an output file nor included in results. The structured profile option avoids sending candidate text into the pipeline entirely.

For each job with at least one overlapping taxonomy skill, the matcher reports matched skills, candidate skills not found in the posting, job skills not found in the candidate profile (`not_found_in_candidate_profile`, each marked `requirement_status: "unverified"` because the ad text does not separate requirements from incidental mentions), and each such skill's raw corpus posting count. It ranks with the harmonic mean of candidate-skill precision and job-skill coverage. Both components are shown; this score describes finite-vocabulary overlap, not probability of hiring or overall candidate suitability. Ties use higher job-skill coverage, then stable job ID order. Location, experience, language, salary, and remote preferences are not scored because the source fields are absent or not validated. Since ad sections are combined, matched skills are evidence of a phrase match, not confirmed requirements. No generic learning path is generated without learning-resource data.

Use a structured profile JSON file with a `skill_ids` string array:

```bash
.venv/bin/gjmi-match match --profile path/to/your_profile.json --top-k 10
```

Or provide a local text CV (its contents are not retained by this CLI):

```bash
.venv/bin/gjmi-match match --cv path/to/your_cv.txt --top-k 10
```

On 4 October 2026, an end-to-end smoke run used three skill IDs from a real posting as a **query proxy**, excluded that source posting, and scanned the 342,058-posting corpus. It returned ranked postings and gap evidence. This is a pipeline smoke check only, not a candidate profile or a ranking-quality result.

No human-judged candidate/job relevance benchmark is available, so no Precision@K, Recall@K, MRR, or NDCG score is claimed. The evaluator accepts manually labeled JSONL queries when available; its schema and annotation guidance are in [`data/evaluation/matching/README.md`](data/evaluation/matching/README.md). It reports macro Precision@K, Recall@K, MRR, and NDCG@K without creating benchmark labels.

## Phase 6: salary label readiness

The pinned posting corpus has no salary target labels. The audit measured 342,058 postings, with **0** populated salary bounds, currencies, or pay periods, and therefore **0** valid job-level intervals. Its separate Phase 2 skills sidecar contains 179,607 postings with skill matches and 295,664 assignments, but features cannot replace a missing target. Phase 6 adds a reproducible audit for salary bounds, interval validity, currency and pay-period coverage, and feature coverage. It does not train a regression model, calculate salary metrics, or create SHAP explanations when labels are absent. No midpoint salary is inferred from bounds.

Run after reproducing Phase 1:

```bash
.venv/bin/gjmi-salary audit
```

The BA Entgeltatlas is a plausible official *context source*, but not a direct job-ad training set: it reports monthly gross median earnings for full-time social-insurance employees by occupation aggregates and region. BA documentation explains that results refer to occupational aggregates rather than individual jobs, suppresses some cells below 500 people, and reports earnings at or above the contribution ceiling as `>8,050 EUR` for the 2025 data. Joining those figures to this corpus would require a validated posting-title-to-KldB mapping and would change the target to an employment-population median. See the [Entgeltatlas](https://web.arbeitsagentur.de/entgeltatlas/), its [methodology](https://www.arbeitsagentur.de/hilfe-entgeltatlas), and the BA's [data use terms](https://statistik.arbeitsagentur.de/DE/Statischer-Content/Statistiken/Fachstatistiken/Logbuch.pdf); BA statistical data and tables may be reused with source attribution, without alteration.

The full-data audit result is in [`reports/phase6/salary_readiness.md`](reports/phase6/salary_readiness.md) and [`reports/phase6/salary_readiness.json`](reports/phase6/salary_readiness.json). Skill features are reported separately because Phase 2 stores them in `job_skills.parquet`, not in the canonical posting table. A model and SHAP are deferred until the project has actual, consistently unitized job-level salary labels and a defensible feature/target definition.

## Phase 8: LLM fine-tuning readiness

The current fine-tuning decision is blocked. The candidate structured-skill extraction task has 17 labeled postings (8 German, 9 English) and 128 positive posting-skill labels; labels are agent-assisted and require independent human review. The measured rule-based baseline on that sample has precision **0.9922**, recall **0.9922**, and F1 **0.9922**, but this is not representative performance evidence. All 17 gold postings also occur in the Phase 2 weak-label sidecar, so training from it would contaminate evaluation and reproduce the rule-based labels. This environment has no PyTorch, Transformers, PEFT, TRL, or bitsandbytes runtime. No split or fine-tuned model was created. The reproducible audit is [`reports/phase8/llm_readiness.md`](reports/phase8/llm_readiness.md); data requirements and leakage notes are in [`data/evaluation/llm/README.md`](data/evaluation/llm/README.md).

## Phase 9: model-serving readiness

Phase 8 produced no model artifact, so there is no selected model to serve or quantize. The local macOS Apple Silicon environment also has no `vllm`, `mlx`, `mlx_lm`, or `llmcompressor` runtime. Phase 9 adds a readiness audit only; latency, throughput, tokens/sec, memory, inference cost, and FP16/BF16/8-bit/4-bit comparisons are unmeasured. The upstream vLLM project documents Apple Silicon through a separate [vLLM-Metal path](https://github.com/vllm-project/vllm/blob/main/docs/getting_started/quickstart.md) using MLX-compatible models, but it is not installed here. See [`reports/phase9/serving_readiness.md`](reports/phase9/serving_readiness.md).

## Phase 10: Responsible AI and EU AI Act risk assessment

Phase 10 documents observed technical controls and gaps for the current candidate-side local matching CLI. It covers scope creep into employer screening, proxy and fairness risks, misleading skill-gap explanations, CV privacy, human oversight, monitoring, transparency, GDPR automated-decision boundaries, and conditional AI Act requirements. It makes no quantitative fairness claim, legal classification, or compliance claim. The human-readable assessment is [`docs/responsible_ai.md`](docs/responsible_ai.md); the structured risk register is [`reports/phase10/responsible_ai_risk_register.json`](reports/phase10/responsible_ai_risk_register.json).

## Phase 7: translation evaluation readiness

The job corpus contains separate advertisements, not German-English aligned translation pairs, and the repository has no translation hypotheses or translation model. Phase 7 adds a local input audit for independently referenced `de-en` and `en-de` translation pairs. It reports pair counts, invalid records, duplicate IDs, direction coverage, and a checksum; it does not retain text in reports or claim BLEU/chrF scores. Run `.venv/bin/gjmi-translate audit`. The input contract and dataset guidance are in [`data/evaluation/translation/README.md`](data/evaluation/translation/README.md), with the measured audit in [`reports/phase7/translation_readiness.md`](reports/phase7/translation_readiness.md) and [`reports/phase7/translation_readiness.json`](reports/phase7/translation_readiness.json). FLORES+ may support a general-domain benchmark, but does not establish quality on job ads; job-domain evaluation needs licensed text and independent human translations.

## Scope and limits

Phase 2 extracts only its finite seed vocabulary. It does not cover certifications, education, experience, language requirements, or a broad occupational skill ontology. Phase 4 adds distributional skill vectors, but not contextual job-description or CV embeddings; its clusters were unstable across split halves. Phase 5 matches only on exact taxonomy IDs and has no human-judged ranking benchmark. Phase 6 does not produce salary predictions or SHAP explanations because there are no job-level salary labels. Phase 7 does not measure translation quality because no aligned reference set or model output is available. Phase 8 does not fine-tune an LLM because the labeled set is small, unreviewed, contaminated by overlap with weak labels, and unsupported by a local fine-tuning runtime. Phase 9 does not benchmark model serving or quantization because no selected model or compatible serving backend is available. Phase 3 reporting is descriptive and limited to historical collection cohorts. The source has one combined ad-text field, and its publication-date semantics are not established. Employer names are retained as organization metadata; email and phone patterns are redacted from retained strings. Source snapshots and generated datasets stay local and out of version control. The dataset host’s CC BY 4.0 declaration is recorded, but the upstream rights chain for scraped ad text has not been independently adjudicated; do not publish the generated Parquet without that review.

## Phase 11: evaluation infrastructure

Phase 11 adds `gjmi-eval` (`skill-sample`, `skill-score`, `annotate-check`, `annotate-import`, `match-pool`, `match-score`). It produced a seeded 180-posting stratified skill-benchmark manifest ([`data/evaluation/skill_v2/`](data/evaluation/skill_v2/README.md)) and blank-label workflows for skill extraction and CV/job matching ([`data/evaluation/matching/`](data/evaluation/matching/README.md)). **No v2 or relevance labels exist yet, so no new extraction or ranking metric is reported**; the scorers output `no_labels` until humans supply them. Annotators can fill a `job_id,skill,label` CSV and convert it with `gjmi-eval annotate-import --csv FILE --annotator NAME` (invalid files are rejected), then track progress with `gjmi-eval annotate-check`. The 0.9922 F1 remains a pilot result on 17 ads. Each such gap now also carries `occurrences_in_ad` and up to two short context `snippets` from the ad, so a reader can see whether the text says required, preferred or incidental (the tool does not classify this). Phase 5 gap output is now named `not_found_in_candidate_profile` with `requirement_status: "unverified"`.

## License

Code is released under the [MIT License](LICENSE). This covers the code only, not the job-ad data: the upstream rights to the ad text are unresolved (see `docs/project_audit.md`), and the data is not included.

## Phase 12: release boundary and annotation readiness

- **Data rights:** see [`docs/data_rights.md`](docs/data_rights.md). Ad text, Parquet/DuckDB files, reading packs and `gjmi-match` snippets must not be published; `scripts/check_release.py` (run in CI) is a guard, not a compliance proof.
- **Reproducing:** without the data, `uv sync --no-editable --extra dev`, then `scripts/check_release.py`, ruff, mypy and pytest. On 4 October 2026 this was run in a clean temp copy (no `.venv`, no `data/processed`) with Python 3.14.7: all passed (37 tests). The full data pipeline was **not** re-run from a clean download.
- **Pilot annotation (A2):** `gjmi-eval skill-pilot` selects an 80-posting stratified pilot (16 per stratum) of the 180-posting manifest. `gjmi-eval annotate-page` writes a local offline page (`data/processed/eval_v2/annotate.html`, git-ignored, no extractor hints) that exports a `job_id,skill,label` CSV for `annotate-import`.
- **Matching judgments (A3):** grades are 0 irrelevant, 1 weak, 2 good, 3 excellent; binary metrics count grade >= 2. A query may carry `source_job_id`, which is excluded from its ranking and baseline and rejected by the scorer if present. `gjmi-eval judge-page` writes a local judging page that exports `pool_sheet.jsonl`. At least 20 fully judged queries are required (target 30-50).
- **Status:** the 80-ad skill pilot is labeled by one annotator (all labels `required`, `adjudicated.jsonl` is an identical copy), so no new extraction metric is reported. Git has not been initialized.

## Phase 13: first matching benchmark (pilot)

On 5 October 2026, 30 queries x 20 pooled jobs (matcher top 10 plus 10 seeded random) were graded 0-3 by a single judge; `reports/phase11/matching_benchmark.json` holds the scored output. At k=10 (grade >= 2 counts as relevant, 95% bootstrap CIs):

| System | P@10 | Pooled recall@10 | MRR | NDCG@10 |
| --- | ---: | ---: | ---: | ---: |
| Skills-overlap matcher | 0.853 (0.80-0.91) | 0.867 | 0.950 | 0.907 |
| Random baseline | 0.143 (0.10-0.19) | 0.133 | 0.308 | 0.139 |

The matcher clearly beats random on this pool. Limits: one non-independent judge; the `judge` field is unset; recall is relative to the pool, which includes the matcher's own top 10; dev and test splits were not scored separately; query provenance (consented vs synthetic) is not recorded here. This is a pilot, not evidence of suitability or of performance on real candidates.


## Phase 14: skill benchmark v2 (LLM-annotated, scored 5 Oct 2026)

All 180 manifest ads were labeled by a language-model annotator (`llm`) that read the ad text without extractor output or the other annotator's labels, then adjudicated against `nithya` (80 shared ads) on the full text: 207 disputed pairs, 191 resolved toward `llm`, 12 toward `nithya`, 4 to neither. `adjudicated.jsonl` is that result. Cohen's kappa between the two raw annotators is **0.514**. The earlier `adjudicated.jsonl` (a copy of `nithya`) was replaced.

Extractor vs adjudicated gold (180 ads, 287 pairs): precision 0.953, **recall 0.571**, F1 0.715. Test split only (106 ads, scored once): P 0.952, R 0.571, F1 0.714. The extractor found nothing in the 60 "sidecar-empty" ads, where gold has 37 pairs, so recall is limited by alias coverage, not just precision. Details are in `reports/phase11/skill_benchmark_v2.json`.

Limits: gold is **LLM-produced and LLM-adjudicated**, with one human annotator whose labels were mostly overruled (mainly soft skills inferred from loose wording), so this is not human-reviewed ground truth; judgment rules (for example, "Lösungsorientierung" is not Problem Solving) shaped the result; about 15 long ads were first truncated and re-read in full. The 0.9922 F1 on 17 ads (Phase 2) should not be quoted next to these numbers; it used a small, technology-enriched sample.

### Phase 14 update: alias fix (taxonomy 0.2.0)

Dev-split misses were all soft skills (teamwork, communication, analytical thinking, problem solving). Only specific phrases were added (e.g. `team-oriented`, `Teamplayer`, `Kommunikationskompetenz`, `kommunikativ`, `analytically`, `Problemlösung`); bare `Kommunikation` and `analysieren` were deliberately not added because they would hurt precision. The sidecar was re-extracted with 0.2.0. Against the same adjudicated gold: all 180 ads P 0.940 / R 0.704 / F1 0.805; dev P 0.933 / R 0.741 / F1 0.826; test (first and only score for 0.2.0) P 0.944 / R 0.680 / F1 0.791, up from F1 0.714. Pilot v1 F1 is now 0.973 (was 0.9922) on 17 ads. Caveats are unchanged: the gold is LLM-annotated, and the aliases were chosen from dev-split misses. Phase 2 sidecar counts above predate 0.2.0.

Follow-up (taxonomy 0.2.1): the Phase 2 pilot dropped to 0.973 under 0.2.0 because `Teamgeist`/`Team spirit` mostly appear in employer culture blurbs, which pilot v1 did not label as Teamwork (5 of its 6 new false positives; the sixth, `Analytisches Denkvermögen`, is a v1 gold omission). Those two aliases were removed. Pilot v1 F1 is 0.988; v2 against the adjudicated gold: all P 0.946 / R 0.669 / F1 0.784, dev F1 0.812, test (first score for 0.2.1) P 0.949 / R 0.640 / F1 0.765. The two gold sets disagree on whether culture-blurb mentions count, so the choice trades v2 recall for v1 precision. Phase 2 counts above were refreshed for 0.2.2.

Taxonomy 0.2.2 adds an `exclusions` list (longest-match phrases dropped from output, e.g. `communication protocols`), fixing that known false positive; scores are unchanged on the benchmarks. `NLPFundierte` (no word boundary) remains a known miss of the token-based matcher.

Matching follow-up: the 30 queries are **synthetic skill lists** (`queries.jsonl`), not real or consented candidates, and the `judge` field is now set to `nithya`. Per split (15 queries each, below the scorer's 20-query minimum, so descriptive only; `reports/phase11/matching_by_split.json`): dev P@10 0.893 / MRR 0.933, test P@10 0.813 / MRR 0.967.

Clean rebuild (5 Oct 2026): in a fresh copy with no `.venv`, `data/raw` or `data/processed`, the pinned archive was re-downloaded (324,758,596 bytes, SHA-256 `505d0a3e...998fd32f`), and `gjmi` and `gjmi-skills extract` were re-run. The Phase 1 report matched the saved one on all 94 compared fields (counts, hashes, coverage; only output paths differ), and the Phase 2 output hash matched the local sidecar after it was regenerated with the current code. pytest (38), ruff, mypy and `check_release.py` passed. Gotcha: with `--no-editable`, a code change requires `uv sync --no-editable --extra dev --reinstall-package german-job-market-intelligence`; an earlier 0.2.2 extraction had silently used the stale installed copy without the exclusion fix, so Phase 2 counts were corrected (212,218 postings with a skill; 357,681 assignments).

Label-rule check: v2 gold already separates `required` (257 pairs) from `mentioned` (30), so no relabel was needed. Scoring against `required` only (`reports/phase11/skill_benchmark_v2_by_label_rule.json`): dev P 0.871 / R 0.740 / F1 0.800; test P 0.847 / R 0.637 / F1 0.727. Precision drops because the extractor also fires on `mentioned` contexts and does not distinguish them, a known limit. The 14 `communication` and 10 `teamwork` dev misses are bare `Kommunikation` and `Team` in duty phrases; adding them as aliases would mainly add false positives, so no further aliases were added. **Pilot v1 (17 ads) is deprecated** as an accuracy claim (small, technology-enriched, omits `Analytisches Denkvermögen`); use the v2 numbers.
## Demo: local matcher

```bash
.venv/bin/gjmi-demo            # then open http://127.0.0.1:8765
```

A stdlib-only web page (binds to 127.0.0.1 only) where you tick skills or paste CV/skills text and see the top 10 postings by skill overlap, with matched skills and ad skills missing from your profile. It needs the local `data/processed/` files from the pipeline, shows titles, companies and locations but no ad text, and processes pasted text in memory only. Scores are taxonomy overlap, not suitability; the "not in your profile" column is not a verified requirement list. Each query scans the full corpus (several seconds). Local use only: there is no authentication, rate limiting or retention policy.
