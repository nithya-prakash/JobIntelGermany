# Candidate/job relevance benchmark

No manually judged candidate-to-job relevance benchmark is currently included. The public job-posting corpus contains no candidate profiles or human relevance judgments, so Phase 5 reports no Precision@K, Recall@K, MRR, or NDCG result.

The evaluator accepts one JSON object per line with these fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `query_id` | string | Stable, anonymized query identifier, unique in the file |
| `candidate_skill_ids` | array of strings | Canonical IDs from `configs/skill_taxonomy.toml` |
| `relevant_job_ids` | array of strings | Job IDs judged relevant by a human reviewer |

Create profiles only from consented, anonymized evaluation material. Do not store raw CV text or direct identifiers in this benchmark. A reviewer should judge relevance without seeing the system score, record the review rubric and reviewer, and distinguish missing evidence in the combined source text from a confirmed candidate gap. Keep candidates separated across development and test splits; do not tune thresholds against test judgments.

After collecting labels, evaluate with:

```bash
.venv/bin/gjmi-match evaluate --benchmark path/to/manually_judged.jsonl --k 10
```

The command reports macro Precision@K, Recall@K, MRR, and NDCG@K over the supplied queries. The metrics are meaningful only when the labels are independently reviewed and the benchmark has enough representative queries. No benchmark rows or metric values are fabricated here.

## Phase 11 workflow (no labels exist yet)

1. Write `queries.jsonl` (`query_id`, `candidate_id`, `split` dev|test, `candidate_skill_ids`) from real, consented candidates. A candidate may not span splits.
2. `gjmi-eval match-pool` writes a blinded, shuffled `pool_sheet.jsonl` (matcher top-10 plus 10 seeded random jobs per query), `pool_provenance.json`, and a local reading pack.
3. A human fills `grade` (0 irrelevant, 1 relevant, 2 highly relevant) and `judge`.
4. `gjmi-eval match-score` reports P@10, pooled Recall@10, MRR and graded NDCG@10 vs the random baseline with bootstrap CIs, and refuses with fewer than 20 fully judged queries.

Update: grades are 0-3 (0 irrelevant, 1 weak, 2 good, 3 excellent). Binary metrics treat grade >= 2 as relevant. Optional `source_job_id` in a query is excluded from its pool and rejected by the scorer if present. `gjmi-eval judge-page` writes a local judging page; export the result over `pool_sheet.jsonl`. Minimum 20 fully judged queries, target 30-50.
