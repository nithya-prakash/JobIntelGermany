"""Distributional embeddings and exploratory clustering for canonical skills."""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pyarrow.parquet as pq

from german_job_market.skills import SkillTaxonomy


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _embedding_vectors(
    frequencies: list[int], cooccurrences: list[list[int]], posting_count: int
) -> list[list[float]]:
    vectors = [[0.0 for _ in frequencies] for _ in frequencies]
    if not posting_count:
        return vectors
    for left, left_count in enumerate(frequencies):
        if not left_count:
            continue
        for right, right_count in enumerate(frequencies):
            if left == right or not right_count:
                continue
            pair_count = cooccurrences[left][right]
            if pair_count:
                pmi = math.log((pair_count * posting_count) / (left_count * right_count))
                vectors[left][right] = max(0.0, pmi)
    return vectors


def _cosine_distance_matrix(vectors: list[list[float]]) -> list[list[float]]:
    norms = [math.sqrt(sum(value * value for value in vector)) for vector in vectors]
    distances = [[0.0 for _ in vectors] for _ in vectors]
    for left in range(len(vectors)):
        for right in range(left + 1, len(vectors)):
            denominator = norms[left] * norms[right]
            similarity = (
                sum(a * b for a, b in zip(vectors[left], vectors[right], strict=True)) / denominator
                if denominator
                else 0.0
            )
            distance = min(1.0, max(0.0, 1.0 - similarity))
            distances[left][right] = distance
            distances[right][left] = distance
    return distances


def _partition_at(distances: list[list[float]], target_clusters: int) -> list[list[int]]:
    """Build an average-linkage cut with deterministic tie-breaking."""
    count = len(distances)
    if not 1 <= target_clusters <= count:
        raise ValueError("target cluster count must be between 1 and item count")
    clusters: dict[int, list[int]] = {index: [index] for index in range(count)}
    active = list(range(count))
    pair_distances = {
        (left, right): distances[left][right]
        for left in range(count)
        for right in range(left + 1, count)
    }
    next_cluster_id = count

    while len(active) > target_clusters:
        left, right = min(
            itertools.combinations(sorted(active), 2),
            key=lambda pair: (pair_distances[pair], pair[0], pair[1]),
        )
        left_size = len(clusters[left])
        right_size = len(clusters[right])
        others = [cluster_id for cluster_id in active if cluster_id not in {left, right}]
        for other in others:
            left_key = (min(left, other), max(left, other))
            right_key = (min(right, other), max(right, other))
            pair_distances[(min(next_cluster_id, other), max(next_cluster_id, other))] = (
                left_size * pair_distances[left_key] + right_size * pair_distances[right_key]
            ) / (left_size + right_size)
        pair_distances = {
            key: value
            for key, value in pair_distances.items()
            if left not in key and right not in key
        }
        clusters[next_cluster_id] = sorted(clusters[left] + clusters[right])
        del clusters[left]
        del clusters[right]
        active = sorted(others + [next_cluster_id])
        next_cluster_id += 1

    return sorted((clusters[cluster_id] for cluster_id in active), key=lambda group: group[0])


def _silhouette_score(distances: list[list[float]], clusters: list[list[int]]) -> float:
    if len(clusters) < 2:
        return 0.0
    owner = {member: cluster_id for cluster_id, group in enumerate(clusters) for member in group}
    scores: list[float] = []
    for item in range(len(distances)):
        own_cluster = owner[item]
        own_members = [member for member in clusters[own_cluster] if member != item]
        if not own_members:
            scores.append(0.0)
            continue
        within = sum(distances[item][member] for member in own_members) / len(own_members)
        nearest_other = min(
            sum(distances[item][member] for member in group) / len(group)
            for cluster_id, group in enumerate(clusters)
            if cluster_id != own_cluster
        )
        denominator = max(within, nearest_other)
        scores.append((nearest_other - within) / denominator if denominator else 0.0)
    return sum(scores) / len(scores) if scores else 0.0


def _labels(clusters: list[list[int]], item_count: int) -> list[int]:
    labels = [-1] * item_count
    for cluster_id, members in enumerate(clusters):
        for member in members:
            labels[member] = cluster_id
    return labels


def _adjusted_rand_index(first: list[int], second: list[int]) -> float:
    if len(first) != len(second):
        raise ValueError("partitions must describe the same items")
    if not first:
        return 1.0
    first_ids = sorted(set(first))
    second_ids = sorted(set(second))
    cells = [[0 for _ in second_ids] for _ in first_ids]
    first_index = {label: index for index, label in enumerate(first_ids)}
    second_index = {label: index for index, label in enumerate(second_ids)}
    for first_label, second_label in zip(first, second, strict=True):
        cells[first_index[first_label]][second_index[second_label]] += 1

    def choose_two(value: int) -> float:
        return value * (value - 1) / 2

    cell_sum = sum(choose_two(value) for row in cells for value in row)
    first_sum = sum(choose_two(sum(row)) for row in cells)
    second_sum = sum(
        choose_two(sum(cells[row][column] for row in range(len(cells))))
        for column in range(len(second_ids))
    )
    total_pairs = choose_two(len(first))
    if total_pairs == 0:
        return 1.0
    expected = first_sum * second_sum / total_pairs
    maximum = 0.5 * (first_sum + second_sum)
    denominator = maximum - expected
    return (cell_sum - expected) / denominator if denominator else 1.0


def _partition_with_best_silhouette(
    distances: list[list[float]],
) -> tuple[int, list[list[int]], float]:
    item_count = len(distances)
    if item_count < 2:
        raise ValueError("at least two embedded skills are required for clustering")
    if item_count == 2:
        return 2, [[0], [1]], 0.0
    max_clusters = min(10, item_count - 1)
    candidates = [
        (clusters, _silhouette_score(distances, clusters))
        for cluster_count in range(2, max_clusters + 1)
        if (clusters := _partition_at(distances, cluster_count))
    ]
    best_clusters, score = max(candidates, key=lambda candidate: (candidate[1], -len(candidate[0])))
    return len(best_clusters), best_clusters, score


def _markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    evaluation = report["evaluation"]
    lines = [
        "# German Job Market Intelligence — skill embeddings and clusters",
        "",
        f"Generated: {report['generated_at_utc']}",
        "",
        "> **Interpretation:** the vectors encode which taxonomy skills co-occur in this "
        "historical corpus. They are exploratory distributional representations, not "
        "contextual language-model embeddings or validated job-family labels.",
        "",
        "## Method and measured coverage",
        "",
        f"- Postings processed: {summary['postings']:,}",
        f"- Postings with at least one taxonomy skill: {summary['postings_with_skills']:,}",
        f"- Taxonomy skills: {summary['taxonomy_skills']}",
        f"- Skills with non-zero distributional vectors: {summary['embedded_skills']}",
        f"- Skills excluded for insufficient co-occurrence evidence: {summary['excluded_skills']}",
        f"- Average-linkage clusters selected: {evaluation['selected_cluster_count']}",
        f"- Cluster sizes: {', '.join(str(size) for size in evaluation['cluster_sizes'])}",
        f"- Cosine silhouette: {evaluation['cosine_silhouette']:.4f}",
        f"- Deterministic split-half adjusted Rand index: {evaluation['split_half_ari']:.4f}",
        "",
        "For each skill, the vector contains positive pointwise mutual information (PPMI) "
        "with every other taxonomy skill. Similarity is cosine similarity. Average-linkage "
        "hierarchical clustering is cut at the cluster count with the best mean silhouette "
        "among 2–10 clusters (bounded by the number of embedded skills). Split-half ARI is "
        "a perturbation-stability check, not evidence of market generalization. ARI values "
        "near 0 indicate little partition agreement; silhouette alone is not enough to "
        "interpret cluster membership.",
        "",
        "## Exploratory clusters",
        "",
    ]
    for cluster in report["clusters"]:
        labels = ", ".join(skill["label"] for skill in cluster["skills"])
        lines.extend(
            [
                f"### Cluster {cluster['cluster_id']} ({cluster['skill_count']} skills)",
                "",
                labels,
                "",
            ]
        )
    lines.extend(
        [
            "## Most frequent co-occurrences",
            "",
            "| Skill pair | Shared postings |",
            "| --- | ---: |",
        ]
    )
    for pair in report["top_cooccurrences"]:
        lines.append(f"| {pair['left_label']} + {pair['right_label']} | {pair['postings']:,} |")
    lines.extend(
        [
            "",
            "## Limits",
            "",
            "This represents the Phase 2 seed taxonomy only. Skills absent from that vocabulary "
            "cannot appear, and extraction false positives or misses affect the co-occurrences. "
            "The source is a historical, single-source corpus with irregular collection batches. "
            "No job-description or title semantic vectors, temporal embedding comparison, or "
            "validated occupational clusters are produced in this phase.",
            "",
            "## Reproduction",
            "",
            "Run `.venv/bin/gjmi-embed` after reproducing Phases 1 and 2.",
            "",
        ]
    )
    return "\n".join(lines)


def build_skill_embeddings(
    skills_path: Path,
    taxonomy: SkillTaxonomy,
    json_path: Path,
    markdown_path: Path,
) -> dict[str, Any]:
    """Create PPMI skill vectors and exploratory average-linkage clusters."""
    if not skills_path.is_file():
        raise FileNotFoundError(skills_path)
    skill_ids = [skill.id for skill in taxonomy.skills]
    skill_index = {skill_id: index for index, skill_id in enumerate(skill_ids)}
    skill_count = len(skill_ids)
    split_frequencies = [[0] * skill_count for _ in range(2)]
    split_cooccurrences = [[[0] * skill_count for _ in range(skill_count)] for _ in range(2)]
    split_postings = [0, 0]
    split_postings_with_skills = [0, 0]
    seen_job_ids: set[str] = set()
    unknown_skill_ids: set[str] = set()
    posting_count = 0
    postings_with_skills = 0

    parquet_file = pq.ParquetFile(skills_path)
    if not {"job_id", "skill_ids"}.issubset(parquet_file.schema_arrow.names):
        raise ValueError("skill input must have job_id and skill_ids columns")

    for batch in parquet_file.iter_batches(columns=["job_id", "skill_ids"], batch_size=4096):
        for row in batch.to_pylist():
            job_id = row["job_id"]
            if not isinstance(job_id, str) or not job_id:
                raise ValueError("job_id must be a non-empty string")
            if job_id in seen_job_ids:
                raise ValueError(f"duplicate job_id in skill sidecar: {job_id}")
            seen_job_ids.add(job_id)
            split = hashlib.sha256(job_id.encode("utf-8")).digest()[0] % 2
            posting_count += 1
            split_postings[split] += 1
            raw_skill_ids = row["skill_ids"] or []
            unknown_skill_ids.update(
                skill_id for skill_id in raw_skill_ids if skill_id not in skill_index
            )
            indices = sorted(
                {skill_index[skill_id] for skill_id in raw_skill_ids if skill_id in skill_index}
            )
            if indices:
                postings_with_skills += 1
                split_postings_with_skills[split] += 1
            for index in indices:
                split_frequencies[split][index] += 1
            for left, right in itertools.combinations(indices, 2):
                split_cooccurrences[split][left][right] += 1
                split_cooccurrences[split][right][left] += 1

    if not posting_count:
        raise ValueError("skill sidecar contains no postings")
    if unknown_skill_ids:
        raise ValueError(f"skill IDs missing from taxonomy: {sorted(unknown_skill_ids)}")
    if not all(split_postings):
        raise ValueError("deterministic split produced an empty half")

    full_frequencies = [
        split_frequencies[0][index] + split_frequencies[1][index] for index in range(skill_count)
    ]
    full_cooccurrences = [
        [split_cooccurrences[0][i][j] + split_cooccurrences[1][i][j] for j in range(skill_count)]
        for i in range(skill_count)
    ]
    vectors = _embedding_vectors(full_frequencies, full_cooccurrences, posting_count)
    embedded_indices = [
        index for index, vector in enumerate(vectors) if any(value > 0 for value in vector)
    ]
    excluded_ids = [
        skill_ids[index] for index in range(skill_count) if index not in embedded_indices
    ]
    if len(embedded_indices) < 2:
        raise ValueError("fewer than two skills have enough co-occurrence evidence to embed")

    embedded_vectors = [vectors[index] for index in embedded_indices]
    distances = _cosine_distance_matrix(embedded_vectors)
    selected_cluster_count, clusters, silhouette = _partition_with_best_silhouette(distances)
    half_labels: list[list[int]] = []
    for split in range(2):
        half_vectors = _embedding_vectors(
            split_frequencies[split], split_cooccurrences[split], split_postings[split]
        )
        half_distances = _cosine_distance_matrix(
            [half_vectors[index] for index in embedded_indices]
        )
        half_partition = _partition_at(half_distances, selected_cluster_count)
        half_labels.append(_labels(half_partition, len(embedded_indices)))
    split_stability = _adjusted_rand_index(half_labels[0], half_labels[1])
    embedded_position = {
        taxonomy_index: position for position, taxonomy_index in enumerate(embedded_indices)
    }

    skill_records = []
    for position, index in enumerate(embedded_indices):
        skill = taxonomy.skills[index]
        related = sorted(
            (
                {
                    "skill_id": skill_ids[other],
                    "label": taxonomy.skills[other].label,
                    "cosine_similarity": round(
                        1.0 - distances[position][embedded_position[other]], 6
                    ),
                    "cooccurring_postings": full_cooccurrences[index][other],
                }
                for other in embedded_indices
                if other != index
            ),
            key=lambda item: (
                -cast(float, item["cosine_similarity"]),
                str(item["skill_id"]),
            ),
        )[:5]
        skill_records.append(
            {
                "skill_id": skill.id,
                "label": skill.label,
                "category": skill.category,
                "postings": full_frequencies[index],
                "vector_ppmi": [round(value, 6) for value in vectors[index]],
                "top_related_skills": related,
            }
        )

    cluster_records = []
    for cluster_id, members in enumerate(clusters, start=1):
        cluster_skills = []
        for member in members:
            skill_index_in_taxonomy = embedded_indices[member]
            skill = taxonomy.skills[skill_index_in_taxonomy]
            cluster_skills.append(
                {
                    "skill_id": skill.id,
                    "label": skill.label,
                    "category": skill.category,
                    "postings": full_frequencies[skill_index_in_taxonomy],
                }
            )
        cluster_records.append(
            {
                "cluster_id": cluster_id,
                "skill_count": len(cluster_skills),
                "skills": sorted(cluster_skills, key=lambda item: str(item["skill_id"])),
            }
        )

    pair_records = []
    for left in range(skill_count):
        for right in range(left + 1, skill_count):
            count = full_cooccurrences[left][right]
            if count:
                pair_records.append(
                    {
                        "left_skill_id": skill_ids[left],
                        "left_label": taxonomy.skills[left].label,
                        "right_skill_id": skill_ids[right],
                        "right_label": taxonomy.skills[right].label,
                        "postings": count,
                    }
                )
    pair_records.sort(
        key=lambda item: (
            -cast(int, item["postings"]),
            str(item["left_skill_id"]),
            str(item["right_skill_id"]),
        )
    )

    report: dict[str, Any] = {
        "phase": 4,
        "embedding_kind": "positive_pointwise_mutual_information_skill_cooccurrence",
        "similarity_metric": "cosine",
        "clustering_algorithm": "average_linkage_hierarchical",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "market_growth_inference_allowed": False,
        "interpretation": (
            "Exploratory distributional skill vectors derived from this corpus and the Phase 2 "
            "taxonomy; they are not contextual text embeddings or validated job-family clusters."
        ),
        "inputs": {
            "skills_path": skills_path.name,
            "skills_sha256": _sha256(skills_path),
            "taxonomy_version": taxonomy.version,
            "taxonomy_sha256": taxonomy.fingerprint,
        },
        "summary": {
            "postings": posting_count,
            "postings_with_skills": postings_with_skills,
            "taxonomy_skills": skill_count,
            "embedded_skills": len(embedded_indices),
            "excluded_skills": len(excluded_ids),
            "excluded_skill_ids": excluded_ids,
            "embedding_dimensions": skill_count,
            "unique_skill_pairs_observed": len(pair_records),
        },
        "evaluation": {
            "selection_metric": "mean cosine silhouette, maximized over 2 through 10 clusters",
            "selected_cluster_count": selected_cluster_count,
            "cluster_sizes": [len(cluster) for cluster in clusters],
            "cosine_silhouette": round(silhouette, 6),
            "split_method": "sha256(job_id) first byte modulo 2",
            "split_postings": split_postings,
            "split_postings_with_skills": split_postings_with_skills,
            "split_half_ari": round(split_stability, 6),
            "stability_interpretation": "partition agreement between deterministic random halves",
        },
        "skills": skill_records,
        "clusters": cluster_records,
        "top_cooccurrences": pair_records[:30],
        "limits": [
            "No pretrained model was used; "
            "job-description and title semantic embeddings are not produced.",
            "A finite seed taxonomy and its extraction errors "
            "bound all observed skill relationships.",
            "Silhouette and split-half ARI are internal exploratory diagnostics, "
            "not external validation.",
            "Silhouette alone can favor imbalanced cuts; check split-half stability "
            "before interpreting cluster memberships.",
            "The corpus is historical and collection volume is irregular; "
            "no current-market inference is supported.",
        ],
    }
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(_markdown(report), encoding="utf-8")
    return report
