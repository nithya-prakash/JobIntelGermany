# German Job Market Intelligence — collection-cohort report

Generated: 2026-10-04T17:14:36.497577+00:00

> **Interpretation:** these are historical skill matches grouped by collection date. They are not weekly vacancy-demand estimates or current market trends.

## Data snapshot

- Postings: 342,058
- Collection dates: 2023-04-04 to 2023-07-23
- Publisher-described period: May 2023 through June 2023
- Observed collection weeks: 11 of 16
- Weeks without records: 2023-04-24, 2023-05-08, 2023-05-15, 2023-05-22, 2023-05-29
- Postings with at least one matched skill: 179,607
- Posting-skill assignments: 295,664
- Observed weekly posting counts: 360–98,769

The source describes its collection period as May 2023 through June 2023, while the retained `collection_date` values span 2023-04-04 to 2023-07-23. Collection volume is irregular and publication dates are absent. Week-to-week changes below are descriptive comparisons of scrape cohorts only.

## Weekly collection cohorts

Shares are the fraction of postings in a collection week matched to a skill. Changes compare with the previous observed week, even when calendar weeks are missing.

| Week starting | Postings | Top matched skills | Largest share increases vs prior observed week |
| --- | ---: | --- | --- |
| 2023-04-03 | 98,769 | Teamwork (22,831; 23.12%); Communication (17,913; 18.14%); SAP (10,241; 10.37%) | — |
| 2023-04-10 | 22,893 | Teamwork (5,432; 23.73%); Communication (4,226; 18.46%); SAP (2,606; 11.38%) | SAP (+1.015 pp); Teamwork (+0.612 pp); Communication (+0.324 pp) |
| 2023-04-17 | 28,885 | Teamwork (7,040; 24.37%); Communication (7,014; 24.28%); SAP (3,090; 10.70%) | Communication (+5.823 pp); Teamwork (+0.645 pp); Artificial Intelligence (+0.198 pp) |
| 2023-04-24 | 0 | — | No observations |
| 2023-05-01 | 26,675 | Teamwork (6,547; 24.54%); Communication (5,183; 19.43%); SAP (3,225; 12.09%) | SAP (+1.392 pp); Agile (+0.369 pp); SQL (+0.296 pp) |
| 2023-05-08 | 0 | — | No observations |
| 2023-05-15 | 0 | — | No observations |
| 2023-05-22 | 0 | — | No observations |
| 2023-05-29 | 0 | — | No observations |
| 2023-06-05 | 66,432 | Teamwork (16,050; 24.16%); Communication (12,285; 18.49%); SAP (7,747; 11.66%) | Problem Solving (+0.213 pp); Analytical Thinking (+0.112 pp); SQL (+0.070 pp) |
| 2023-06-12 | 360 | Teamwork (90; 25.00%); Communication (76; 21.11%); SAP (35; 9.72%) | Communication (+2.619 pp); Python (+2.610 pp); C++ (+1.508 pp) |
| 2023-06-19 | 29,849 | Teamwork (7,402; 24.80%); Communication (5,561; 18.63%); SAP (3,458; 11.59%) | SAP (+1.863 pp); Agile (+1.468 pp); SQL (+0.902 pp) |
| 2023-06-26 | 4,387 | Teamwork (1,069; 24.37%); Communication (881; 20.08%); SAP (520; 11.85%) | SQL (+1.661 pp); Java (+1.620 pp); Communication (+1.452 pp) |
| 2023-07-03 | 28,569 | Teamwork (6,925; 24.24%); Communication (5,259; 18.41%); SAP (3,303; 11.56%) | UML (+0.056 pp); Deep Learning (+0.042 pp); PostgreSQL (+0.037 pp) |
| 2023-07-10 | 4,102 | Teamwork (1,055; 25.72%); Communication (788; 19.21%); SAP (532; 12.97%) | Teamwork (+1.480 pp); SAP (+1.408 pp); CI/CD (+0.860 pp) |
| 2023-07-17 | 31,137 | Teamwork (7,457; 23.95%); Communication (5,686; 18.26%); SAP (3,648; 11.72%) | Microsoft Azure (+0.119 pp); Analytical Thinking (+0.115 pp); Google Cloud Platform (+0.093 pp) |

## Data availability

| Field or analysis | Present records | Availability |
| --- | ---: | --- |
| publication_date | 0 / 342,058 | unavailable |
| federal_state | 0 / 342,058 | unavailable |
| remote_type | 0 / 342,058 | unavailable |
| salary_min | 0 / 342,058 | unavailable |
| salary_max | 0 / 342,058 | unavailable |
| language_requirements | 0 / 342,058 | unavailable |

Geographic trends are omitted: federal-state labels are empty; although location is populated for 339,422 postings, those values are free text and have not been mapped to regions. Salary, remote-work, and language-requirement trends are omitted because their structured fields have no populated values. Job-family counts are also omitted: the source has titles but no validated job-family labels.

## Reproduction

Run `.venv/bin/gjmi-report` after reproducing Phase 1 and generating the Phase 2 skill sidecar.
The machine-readable output includes checksums, coverage counts, missing weeks, skill shares.
