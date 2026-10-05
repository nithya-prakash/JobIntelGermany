# LLM fine-tuning data readiness

The current candidate task is structured skill extraction from a job posting. The only adjudication file is `../skill_gold_v1.jsonl`: 17 postings, with agent-assisted labels that have not been independently or double coded. It is a small challenge sample, not a train/validation/test dataset.

Phase 2 also produced `data/processed/job_skills.parquet` by applying the rule-based extractor to the posting corpus. These are weak labels from the baseline, not independent ground truth. All 17 gold postings are present in that sidecar. Training on those rows and then reporting performance on the curated sample would leak evaluation examples; training on the full sidecar would teach the model to imitate the rules.

Before fine-tuning, independently review and expand the labels, create a job-ID-grouped split before model or prompt selection, and retain an untouched test set. Compare against the current measured rule-based baseline. Record dataset/taxonomy/model revisions, QLoRA configuration, seeds, and per-language/per-category extraction metrics. Do not publish source ad text or CV data without rights and privacy review.

Run the readiness report with `.venv/bin/gjmi-skills evaluate --report reports/phase8/extraction_baseline.json` followed by `.venv/bin/gjmi-llm audit`. The audit does not download or train a model.
