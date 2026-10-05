# Data handling

`raw/` contains downloaded source snapshots and is ignored by Git. Do not publish or commit raw job-ad text. The Phase 1 output contains only canonical fields; unrecognized source fields are dropped, and email/phone patterns are redacted. This run found phone-number patterns in the source, so its raw archive is removed after validation; re-download it to reproduce. The report records the pinned dataset DOI, published license, archive checksum, and measured QA results without copying ad text.

Phase 2 writes `processed/job_skills.parquet`, also ignored by Git. It contains only `job_id` and the list of taxonomy skill IDs; join it to `processed/jobs.parquet` locally when needed. The evaluation labels contain IDs and labels only, not copied job-ad text.
