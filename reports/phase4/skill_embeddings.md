# German Job Market Intelligence — skill embeddings and clusters

Generated: 2026-10-04T17:40:15.990033+00:00

> **Interpretation:** the vectors encode which taxonomy skills co-occur in this historical corpus. They are exploratory distributional representations, not contextual language-model embeddings or validated job-family labels.

## Method and measured coverage

- Postings processed: 342,058
- Postings with at least one taxonomy skill: 179,607
- Taxonomy skills: 63
- Skills with non-zero distributional vectors: 63
- Skills excluded for insufficient co-occurrence evidence: 0
- Average-linkage clusters selected: 2
- Cluster sizes: 61, 2
- Cosine silhouette: 0.6517
- Deterministic split-half adjusted Rand index: -0.0161

For each skill, the vector contains positive pointwise mutual information (PPMI) with every other taxonomy skill. Similarity is cosine similarity. Average-linkage hierarchical clustering is cut at the cluster count with the best mean silhouette among 2–10 clusters (bounded by the number of embedded skills). Split-half ARI is a perturbation-stability check, not evidence of market generalization. ARI values near 0 indicate little partition agreement; silhouette alone is not enough to interpret cluster membership.

## Exploratory clusters

### Cluster 1 (61 skills)

Agile, Apache Airflow, Analytical Thinking, Angular, Artificial Intelligence, Amazon Web Services, Microsoft Azure, CI/CD, Communication, C++, C#, CSS, Databricks, Deep Learning, Django, Docker, .NET, Flask, Google Cloud Platform, Git, GitHub, GitLab, Apache Hadoop, Helm, HTML, Java, JavaScript, Jenkins, Jira, Kotlin, Kubernetes, Linux, Machine Learning, MongoDB, MySQL, Natural Language Processing, Node.js, NumPy, OpenShift, Oracle Database, pandas, PHP, PostgreSQL, Problem Solving, Python, PyTorch, React, REST API, Scala, scikit-learn, Scrum, Snowflake, Apache Spark, Spring Framework, SQL, TensorFlow, Terraform, TypeScript, UML, Vue.js, Windows Presentation Foundation

### Cluster 2 (2 skills)

SAP, Teamwork

## Most frequent co-occurrences

| Skill pair | Shared postings |
| --- | ---: |
| Communication + Teamwork | 17,133 |
| SAP + Teamwork | 9,878 |
| SAP + Communication | 8,924 |
| Teamwork + Analytical Thinking | 3,415 |
| Communication + Analytical Thinking | 3,252 |
| Agile + Communication | 2,604 |
| SAP + Analytical Thinking | 2,211 |
| Communication + Problem Solving | 2,006 |
| Agile + Teamwork | 1,952 |
| Agile + Scrum | 1,781 |
| Python + SQL | 1,767 |
| SQL + Teamwork | 1,510 |
| Python + C++ | 1,481 |
| Java + SQL | 1,479 |
| HTML + CSS | 1,470 |
| Teamwork + Problem Solving | 1,339 |
| Python + Teamwork | 1,333 |
| Python + Communication | 1,331 |
| Python + Java | 1,310 |
| JavaScript + HTML | 1,283 |
| SQL + Communication | 1,260 |
| Java + Spring Framework | 1,237 |
| Docker + Kubernetes | 1,227 |
| Linux + Teamwork | 1,158 |
| Artificial Intelligence + Teamwork | 1,155 |
| JavaScript + CSS | 1,111 |
| Java + CI/CD | 1,096 |
| Python + Linux | 1,095 |
| Java + Teamwork | 1,088 |
| Artificial Intelligence + Communication | 1,065 |

## Limits

This represents the Phase 2 seed taxonomy only. Skills absent from that vocabulary cannot appear, and extraction false positives or misses affect the co-occurrences. The source is a historical, single-source corpus with irregular collection batches. No job-description or title semantic vectors, temporal embedding comparison, or validated occupational clusters are produced in this phase.

## Reproduction

Run `.venv/bin/gjmi-embed` after reproducing Phases 1 and 2.
