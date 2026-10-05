import hashlib
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from german_job_market.skill_embeddings import (
    _adjusted_rand_index,
    _embedding_vectors,
    _partition_at,
    _silhouette_score,
    build_skill_embeddings,
)
from german_job_market.skills import load_taxonomy

ROOT = Path(__file__).resolve().parents[1]


def test_ppmi_and_clustering_metrics_on_hand_calculated_inputs() -> None:
    vectors = _embedding_vectors(
        frequencies=[3, 3, 2],
        cooccurrences=[[3, 3, 0], [3, 3, 1], [0, 1, 2]],
        posting_count=4,
    )
    assert vectors[0][1] > 0
    assert vectors[1][2] == 0
    assert vectors[0][0] == 0

    distances = [
        [0.0, 0.1, 0.9, 0.9],
        [0.1, 0.0, 0.9, 0.9],
        [0.9, 0.9, 0.0, 0.1],
        [0.9, 0.9, 0.1, 0.0],
    ]
    clusters = _partition_at(distances, target_clusters=2)
    assert clusters == [[0, 1], [2, 3]]
    assert _silhouette_score(distances, clusters) > 0.8
    assert _adjusted_rand_index([0, 0, 1, 1], [1, 1, 0, 0]) == 1.0
    assert _adjusted_rand_index([0, 0, 1, 1], [0, 1, 0, 1]) < 0.0


def test_embedding_pipeline_writes_reproducible_fixture_report(tmp_path: Path) -> None:
    skills_path = tmp_path / "skills.parquet"
    json_path = tmp_path / "embedding.json"
    markdown_path = tmp_path / "embedding.md"
    taxonomy = load_taxonomy(ROOT / "configs/skill_taxonomy.toml")
    fixture_skills = [
        ["python", "machine_learning"],
        ["python", "machine_learning"],
        ["python", "machine_learning"],
        ["python", "machine_learning"],
        ["sql", "postgresql"],
        ["sql", "postgresql"],
        ["sql", "postgresql"],
        ["sql", "postgresql"],
        ["python", "sql"],
        ["machine_learning", "postgresql"],
        ["java", "spring"],
        ["java", "spring"],
        ["java", "spring"],
        ["java", "spring"],
        ["spring", "git"],
        ["spring", "git"],
        ["spring", "git"],
        ["spring", "git"],
    ]
    pq.write_table(
        pa.table(
            {
                "job_id": [f"job-{index:02d}" for index in range(len(fixture_skills))],
                "skill_ids": pa.array(fixture_skills, type=pa.list_(pa.string())),
            }
        ),
        skills_path,
    )

    report = build_skill_embeddings(skills_path, taxonomy, json_path, markdown_path)

    assert report["phase"] == 4
    assert report["summary"]["postings"] == len(fixture_skills)
    assert report["summary"]["embedded_skills"] >= 6
    expected_splits = [0, 0]
    for index in range(len(fixture_skills)):
        job_id = f"job-{index:02d}"
        expected_splits[hashlib.sha256(job_id.encode()).digest()[0] % 2] += 1
    assert report["evaluation"]["split_postings"] == expected_splits
    assert report["market_growth_inference_allowed"] is False
    assert len(report["clusters"]) == report["evaluation"]["selected_cluster_count"]
    assert json_path.is_file() and markdown_path.is_file()
    assert "not contextual language-model embeddings" in markdown_path.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("job_ids", "skill_ids", "error"),
    [
        (["duplicate", "duplicate"], [["python"], ["sql"]], "duplicate job_id"),
        (["unknown"], [["made_up_skill"]], "missing from taxonomy"),
    ],
)
def test_embedding_pipeline_rejects_invalid_skill_sidecar(
    tmp_path: Path,
    job_ids: list[str],
    skill_ids: list[list[str]],
    error: str,
) -> None:
    skills_path = tmp_path / "invalid-skills.parquet"
    pq.write_table(
        pa.table(
            {
                "job_id": job_ids,
                "skill_ids": pa.array(skill_ids, type=pa.list_(pa.string())),
            }
        ),
        skills_path,
    )
    taxonomy = load_taxonomy(ROOT / "configs/skill_taxonomy.toml")

    with pytest.raises(ValueError, match=error):
        build_skill_embeddings(
            skills_path,
            taxonomy,
            tmp_path / "invalid.json",
            tmp_path / "invalid.md",
        )
