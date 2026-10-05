# Skill benchmark v2 (infrastructure only — no labels yet)

`manifest.jsonl` lists 180 postings (seed 20261004; no ad text): 30 each of de/en × sidecar-hit/empty (language is a stopword heuristic used only for sampling) plus 60 postings containing ambiguous tokens (Go, R, Spring, Excel). Dev/test (74/106) is a hash split on `job_id`. The 17 pilot (v1) ads are excluded. Regenerate with `gjmi-eval skill-sample` (byte-identical for the same corpus and seed).

Annotators read `data/processed/eval_v2/skill_reading_pack.jsonl` (local, ignored; extractor output is deliberately not shown) and write `annotations/<name>.jsonl`, one line per posting: `{"job_id": "...", "annotator": "...", "skills": {"python": "required", "sql": "mentioned"}}`; absent skills are omitted. Disagreements are resolved into `annotations/adjudicated.jsonl`, the scoring gold. `gjmi-eval skill-score` reports `no_labels` without it, `single_annotator_unreviewed` with fewer than two annotators sharing >= 20 postings, and `multi_annotator_reviewed` otherwise. Tune only on `dev`; score `test` once per taxonomy version.

Spreadsheet route: fill a CSV with columns `job_id,skill,label` (one row per present skill; label `required` or `mentioned`; a row with a job_id and blank skill marks a reviewed posting with no skills), then run `gjmi-eval annotate-import --csv your.csv --annotator yourname`. Invalid files are rejected and not written.

Pilot: `gjmi-eval skill-pilot` writes `pilot.jsonl` (80 IDs, 16 per stratum). `gjmi-eval annotate-page` builds a local offline annotation page from it (progress is stored in the browser; export a CSV when done). `annotate-check` reports `pilot_remaining`. Scores on a partial set carry a `partial_coverage_note` and describe only the labelled postings.
