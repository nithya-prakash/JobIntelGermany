# German Job Market Intelligence — repository audit

**Audit date:** 4 October 2026  
**Audit type:** engineering, data, evaluation, privacy, and scope review  
**Conclusion:** credible research prototype and data-engineering portfolio foundation; **not a complete or production-ready job-market AI platform**.

## Executive assessment

The strongest part of this repository is its measured, local data foundation. The ingestion output is schema-checked, hashed, deduplicated, and stored in Parquet/DuckDB. The deterministic skill extractor and reporting pipeline are inspectable, and the project generally labels its outputs with important limits rather than inventing results. The current local snapshot is internally consistent with the saved reports.

The project brief describes a much broader platform than the code currently delivers. Matching has no human relevance benchmark; the “embedding” phase is distributional co-occurrence rather than semantic text embedding; salary and translation are data-readiness audits only; fine-tuning and serving were correctly blocked; and there is no API, dashboard, hosted deployment, recurring scheduler, or user-management layer. The system should be described as a set of local research pipelines and readiness assessments, not an end-to-end AI product.

The main risks before public or consequential use are: the upstream rights chain for copied job-ad text has not been independently established; the corpus is historical and narrow; the skill evaluation is small and not independently reviewed; candidate/job rankings have no relevance validation; and CV processing has no service-level privacy/security controls. These do not invalidate a local portfolio prototype, but they limit what it can claim and where it should be used.

## What was audited

- Source, configuration, CLI, tests, documentation, and saved reports under `src/`, `scripts/`, `configs/`, `tests/`, `reports/`, `data/`, and `docs/`.
- Local normalized dataset and skill sidecar by read-only DuckDB queries.
- Project checks: pytest, Ruff, and mypy.
- Dataset publisher page and current official EU AI Act materials. Links appear under [Sources](#sources).

The source archive is not present in `data/raw/`; the processed Parquet and DuckDB files are local and ignored by Git. I did not download data or rerun commands that overwrite generated reports. This workspace has no `.git` directory, so commit history and a Git diff could not be audited.

## Implementation coverage

| Area | Status | Audit finding |
| --- | --- | --- |
| Phase 1: ingestion and storage | Implemented | Streaming JSON-in-ZIP ingestion, normalization, deduplication, Pydantic schema, Parquet, DuckDB, quality report. Local output verified against saved hashes. |
| Phase 2: skill extraction | Implemented, narrow baseline | Deterministic 63-skill bilingual seed taxonomy. No contextual inference or broad occupational ontology. Evaluation covers 17 purposively selected ads and 128 positive skill labels. |
| Phase 3: intelligence report | Implemented as historical description | Aggregates extraction results by collection week. The source's collection batches are irregular; it explicitly disallows interpreting these as current vacancy-demand trends. |
| Phase 4: embeddings and clustering | Exploratory substitute | 63-dimensional PPMI co-occurrence vectors over the seed taxonomy; no sentence embeddings for postings, titles, or CVs. Selected two clusters have sizes 61 and 2; split-half ARI is -0.0161, so cluster stability is not demonstrated. |
| Phase 5: candidate matching and gaps | Implemented, pilot-validated (single judge) | Local skills-only candidate-to-job ranking with transparent overlap components. No human relevance benchmark or ranking metric is available. The “missing” skills are not verified requirements. |
| Phase 6: salary prediction and SHAP | Readiness audit only | No valid salary labels in the local corpus; no model, MAE/RMSE/R², or SHAP output exists. |
| Phase 7: translation | Readiness audit only | Checks for aligned evaluation input; no translation model, BLEU, chrF, COMET, or human evaluation result exists. |
| Phase 8: fine-tuning | Readiness gate only | No LLM was trained. The 17-document label set is too small/unreviewed and overlaps the weak-label sidecar; training would contaminate evaluation. |
| Phase 9: serving and quantization | Readiness gate only | No model artifact or compatible local serving backend; latency, throughput, memory, and quantization comparisons are unmeasured. |
| Phase 10: responsible AI | Preliminary documentation | Risk register identifies current controls and gaps. It is not a legal classification, privacy assessment, or conformity assessment. |
| API, application, and operations | Not implemented | No API/UI, authentication, authorization, scheduling, model registry, deployment packaging, operational monitoring, or user support path was found. |

## Verified data and evaluation results

Read-only inspection of the local Parquet files found:

- **342,058** job rows and **342,058** distinct job IDs.
- Collection dates from **2023-04-04 to 2023-07-23**. The source publisher describes collection as May–June 2023; the discrepancy is documented in the project and should remain visible.
- **0** populated salary minimum/maximum bounds.
- The skill sidecar has **342,058** rows, **342,058** distinct IDs, **179,607** postings with at least one skill, and **295,664** skill assignments. A full outer join found no missing or orphan sidecar IDs.
- The current `jobs.parquet` and `job_skills.parquet` SHA-256 hashes match the values in their Phase 1/2 reports.
- An additional pattern scan found no email or German phone-pattern matches across the retained scalar text fields. A broader scan that included machine IDs and URLs matched number-like strings in those metadata fields; those are not evidence of contact details. Pattern scans cannot establish anonymization or detect every personal identifier.
- The skill gold set contains **17** ads (8 German, 9 English) and **128** labeled skill pairs; every gold ad overlaps the weak-label sidecar. The project records this as a blocker for fine-tuning and notes that the labels need independent review.

The saved skill evaluation reports F1 **0.9922** on this small closed-set sample. Treat this only as a pilot result for those selected examples—not as corpus-wide or production extraction performance. Its purposive sampling and agent-assisted, unreviewed labels are material limitations.

## Findings and priority

### High priority before making product or market claims

**A1 — Dataset scope does not support broad or current market claims.** The retained corpus is a single-source historical snapshot focused on AI-skill demand. The 11 observed collection weeks out of 16 have weekly sizes from 360 to 98,769 (274.36×); collection dates are not publication dates. The existing weekly report correctly avoids “fastest-growing/current demand” claims. Keep that language boundary in dashboards, presentations, and interview material.

**A2 — Extraction quality evidence is too narrow for generalization.** *Update 5 Oct 2026:* a 180-ad stratified benchmark now exists (LLM-annotated and LLM-adjudicated, one human annotator, kappa 0.51; README Phase 14). Extractor (taxonomy 0.2.1, after alias fixes; 0.1.0 scored F1 0.715, test 0.714): all P 0.946 / R 0.669 / F1 0.784; test P 0.949 / R 0.640 / F1 0.765. Precision is strong, recall is the weakness. The pilot-v1 F1 is 0.988 (was 0.9922). The two gold sets disagree on whether employer-culture mentions (e.g. "team spirit") count; a candidate-requirement-only labeling rule is still needed. It is still not human-reviewed ground truth. The original finding follows. The 63-entry taxonomy and 17-ad gold sample do not establish recall for skills outside the taxonomy or accuracy across German job families. The high pilot score is sensitive to sample design and annotation quality. Have independent annotators review a larger, stratified sample; report per-skill/category/language uncertainty and hard negative contexts; separate development and test postings before tuning.

**A3 — Candidate/job ranking has only a single-judge pilot benchmark.** *Update 5 Oct 2026:* 30 queries were graded by one judge; at k=10 the matcher scored P@10 0.853, MRR 0.950, NDCG@10 0.907 vs random 0.143 / 0.308 / 0.139 (see README Phase 13). Recall is pool-relative, the judge is not independent, the queries are synthetic skill lists rather than real candidates, and per-split results (dev P@10 0.893, test 0.813, 15 queries each) are descriptive only, so this is not a validation. The original finding follows. The matcher uses exact taxonomy overlap and a harmonic mean of candidate-skill precision and job-skill coverage. It does not assess requirements versus incidental mentions, experience, language, location preference, seniority, or candidate relevance. Do not use it to make employment decisions or describe its score as suitability. Build consented/anonymized candidate queries and independently judged relevance labels before comparing ranking metrics.

**A4 — Rights to redistribute the ad text remain unresolved.** The dataset page identifies version 2 as CC BY 4.0 and says it contains raw online job advertisements. That publisher declaration is not independent evidence that the publisher could license every third-party ad or that downstream redistribution of the normalized 320 MB text export is cleared. The repository already warns against publishing the data. Keep raw and processed job text out of public artifacts until the rights chain and permitted use are reviewed; preserve attribution and exact snapshot provenance.

**A5 — CV privacy controls stop at a local CLI boundary.** The CLI reads a CV file locally and extracts skills in process memory; the code does not implement uploads or persistence. There is no authentication, authorization, retention/deletion process, secure-erasure guarantee, or incident response for a service. Direct-contact regular expressions are limited controls, not anonymization. Do not accept real CVs in a hosted service without a separate privacy/security design, data-protection review, retention rules, access controls, and appropriate user notices.

### Medium priority / future-scope blockers

**A6 — “Missing skill” output can overstate evidence.** The implementation infers a gap when no taxonomy match appears in combined job-ad text; it cannot distinguish a requirement from a responsibility or incidental mention. Use wording such as “not found in this text,” and add source spans, correction, and uncertainty behavior before presenting this to users as advice.

**A7 — Cluster quality is not demonstrated.** PPMI co-occurrence is a transparent, low-cost representation, but it does not meet the original semantic-embedding goal. The high in-sample silhouette of 0.6517 is outweighed by negative split-half ARI (-0.0161) and a highly imbalanced selected partition. Keep clusters diagnostic; do not name them job families or emerging technologies without independent validation.

**A8 — Requested prediction and generative features are not delivered.** Salary, translation, LLM fine-tuning, and model serving are readiness audits, not implemented models. The reports appropriately contain null/unmeasured metrics. Keep them described as “not implemented/blocked” and do not turn readiness reports into product-feature claims.

**A9 — No deployment governance or recourse is present.** There is no human review/override workflow, complaint or appeal channel, model/data monitoring, audit owner, rollback plan, or authentication. The current tool is a local prototype; those omissions become release blockers if it is used in recruitment or another consequential setting.

**A10 — Legal status must be re-evaluated per intended use.** The current matcher is candidate-side job search, while employer-side screening could fall within the AI Act's employment/recruitment use cases. The Commission says Annex III high-risk rules are scheduled to apply from 2 December 2027 and Article 50 transparency obligations apply from 2 August 2026. Those dates do not classify this prototype or establish compliance. FRIA duties are scoped to specified deployer/use categories, not a blanket requirement for every private recruiter. Obtain qualified, use-specific advice before employer use or handling real candidate data.

**A11 — Reproduction is local-state dependent.** The outputs required by later phases are in `data/processed/`, which `.gitignore` excludes; the raw archive is absent and must be downloaded again. The dataset-download script checks the ZIP CRC and expected JSON member count and records a checksum manifest, but clean reproduction requires network access and access to the publisher snapshot. The current local outputs’ checksums were verified; a full clean rebuild was not run as part of this audit.

**A12 — Repository release hygiene is incomplete.** No `LICENSE`, CI workflow, Docker setup, or pinned runtime container was found. The lockfile supports repeatable dependency resolution, but no Git metadata is available in this workspace for branch/commit review. Choose a code license and add CI/clean-environment validation before presenting it as a maintained public repository.

## Engineering check results

Executed on macOS, Python **3.14.7**:

| Check | Result |
| --- | --- |
| `.venv/bin/python -m pytest` | **25 passed** in 0.81 seconds |
| `.venv/bin/ruff check .` | Passed |
| `.venv/bin/mypy src scripts` | Passed, 24 source files |
| Local snapshot read-only count/hash/sidecar checks | Passed for reported counts, output hashes, and one-to-one IDs |

These checks verify the tested local code paths and saved data artifacts. The full ingestion/download and all reporting commands were not rerun during this read-only audit. There is no integration test that provisions an empty environment, downloads the source, runs every phase, and compares outputs end to end.

## Recommended order of work

1. **Freeze claims and usage boundary:** candidate-side local search only; publish no job-text export; preserve the historical/lexicon limitations in every report.
2. **Resolve dataset rights and release hygiene:** review the ad-text rights chain, decide code license, and create a clean-environment/CI path.
3. **Improve evaluation before features:** independently review annotations, broaden the skill gold set, and build a consented, blinded candidate/job relevance benchmark with candidate-separated splits.
4. **Fix evidence presentation:** change “missing skill” semantics and retain posting evidence spans; document user correction and recourse needs.
5. **Only then consider models:** salary labels, translation references, LLM data splits, fine-tuning, and serving benchmarks each need their own measured go/no-go gate.
6. **Before deployment:** implement security, privacy, human oversight, incident response, monitoring, and a use-specific legal assessment.

## Reproduction commands

From the repository root, with `uv` installed and network access to the pinned dataset host:

```bash
uv sync --no-editable --extra dev
.venv/bin/python scripts/download_dataset.py
.venv/bin/gjmi
.venv/bin/gjmi-skills extract
.venv/bin/gjmi-skills evaluate
.venv/bin/gjmi-report
.venv/bin/gjmi-embed
.venv/bin/gjmi-salary audit
.venv/bin/gjmi-translate audit
.venv/bin/gjmi-llm readiness
.venv/bin/gjmi-serve readiness
.venv/bin/python -m pytest
.venv/bin/ruff check .
.venv/bin/mypy src scripts
```

Matching requires a profile or local CV file and a generated skill sidecar. It has no default real-candidate benchmark. Data download and regeneration write ignored local artifacts and may take time; the commands above were not rerun as part of this audit.

## Sources

- [Mendeley Data, dataset v2](https://data.mendeley.com/datasets/wnt24rfrwz/2): publisher page describes the Stepstone ad corpus, May–June 2023 collection period, raw job advertisements, and CC BY 4.0 label. The page's license statement does not settle third-party rights in every advertisement.
- [European Commission: AI Act regulatory framework](https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai) and [Article 50 transparency FAQ](https://digital-strategy.ec.europa.eu/en/faqs/transparency-obligations-under-article-50-ai-act), checked 4 October 2026.
- [AI Act consolidated text](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:02024R1689-20260727): classification, employment/recruitment use cases, deployer duties, human oversight, and FRIA scope.
- [GDPR text](https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng): relevant to any future processing of candidate CVs and automated decision-making; no legal conclusion is made here.

This is an engineering audit for a portfolio project. It is not legal advice, a security certification, a conformity assessment, or proof of production readiness.

## Phase 11 follow-up (4 October 2026)

Addressed A6 (gap output renamed `not_found_in_candidate_profile`, marked `requirement_status: "unverified"`; each gap now also carries `occurrences_in_ad` and up to two context snippets; the tool still does not classify requirement strength) and built, but did not populate, the A2/A3 benchmarks: a 180-posting seeded manifest and `gjmi-eval` scorers. Both benchmarks report `no_labels` until independent human annotation/judgments exist; A2 and A3 remain open.

Also partly addressed A12: an MIT `LICENSE` (code only; ad-text rights from A4 remain unresolved) and a GitHub Actions workflow (`.github/workflows/ci.yml`: ruff, mypy, pytest) were added. The workflow has not yet run on GitHub, and local ruff/mypy/pytest passed (30 tests). Still open from A12: Git metadata, Docker/pinned container, and a clean-environment end-to-end rebuild.

## Phase 12 follow-up (4 October 2026)

A4: `docs/data_rights.md` and `scripts/check_release.py` (CI-enforced) define and guard the publication boundary; the upstream rights question itself remains unresolved. A12: Python pinned to 3.14 in CI and `.python-version`; a clean temp-copy run (no `.venv`, no processed data) passed the release check, ruff, mypy and 37 tests. Still open: Git metadata (not initialized by request), CI has not run on GitHub, Docker, and a clean-download full pipeline rebuild. A2/A3: annotation and judging tooling (80-posting pilot, offline HTML pages, 0-3 scale, source-job leakage guard) is ready, but no human labels exist and no new metrics are reported.
