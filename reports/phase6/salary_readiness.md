# German Job Market Intelligence — salary data readiness

Generated: 2026-10-04T18:45:32.419972+00:00

> **Status:** no salary prediction model was trained. No job-level salary labels are present in the pinned posting corpus.

## Label audit

- Postings audited: 342,058
- Postings with either salary bound: 0
- Complete min/max salary intervals: 0
- Valid EUR intervals with a recognized period: 0
- Partial intervals: 0
- Invalid numeric intervals: 0
- Unsupported currency or period: 0

| Field | Populated records |
| --- | ---: |
| salary_min | 0 / 342,058 |
| salary_max | 0 / 342,058 |
| salary_currency | 0 / 342,058 |
| salary_period | 0 / 342,058 |
| title | 342,058 / 342,058 |
| location | 339,422 / 342,058 |
| federal_state | 0 / 342,058 |
| experience_level | 0 / 342,058 |
| employment_type | 0 / 342,058 |
| remote_type | 0 / 342,058 |
| normalized_skills (posting table) | 0 / 342,058 |

## Training and explainability

- Model trained: False
- Model metrics: None
- SHAP explanation available: False
- Blockers: no valid job-level salary intervals are available

The dataset has no job-level salary labels, so MAE, RMSE, R², error distributions, and SHAP values are not applicable. This is a measured data limitation; no substitute values or synthetic training rows were created.

## Skill feature sidecar

Phase 2 skill sidecar: 342,058 rows; 179,607 matched postings with skills; 295,664 assignments.
These annotations are stored separately from the canonical posting table.

## Source compatibility

The BA Entgeltatlas reports aggregate gross monthly median wages for full-time social-insurance employees by occupational aggregates and region. It does not supply salary labels for the individual advertisements in this corpus. Joining those medians to ads would require a validated job-title-to-KldB mapping and would change the prediction target from advertised salary to an occupational employment median. The BA also suppresses some small cells and caps high values; these are material target limitations.

## Reproduction

Run `.venv/bin/gjmi-salary audit` after reproducing Phase 1.
