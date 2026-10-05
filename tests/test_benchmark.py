from pathlib import Path

import pytest

from german_job_market.benchmark import (
    _cohen_kappa,
    build_pilot,
    check_annotations,
    graded_metrics,
    import_annotation_csv,
    score_matching_benchmark,
    score_skill_benchmark,
    validate_match_queries,
)
from german_job_market.skills import load_taxonomy

ROOT = Path(__file__).resolve().parents[1]
TAX = load_taxonomy(ROOT / "configs/skill_taxonomy.toml")


def test_skill_scorer_reports_no_labels(tmp_path: Path) -> None:
    manifest = tmp_path / "m.jsonl"
    manifest.write_text('{"job_id":"a","split":"dev","stratum":"x"}\n')
    out = score_skill_benchmark(
        manifest, tmp_path / "ann", tmp_path / "j.parquet", TAX, tmp_path / "r.json"
    )
    assert out["status"] == "no_labels"
    assert "results" not in out


def test_matching_scorer_refuses_without_labels(tmp_path: Path) -> None:
    out = score_matching_benchmark(
        tmp_path / "q", tmp_path / "s", tmp_path / "p", TAX, tmp_path / "r.json"
    )
    assert out["status"] == "no_labels"


def test_candidate_cannot_cross_splits() -> None:
    qs = [
        {"query_id": "1", "candidate_id": "c", "split": "dev", "candidate_skill_ids": ["python"]},
        {"query_id": "2", "candidate_id": "c", "split": "test", "candidate_skill_ids": ["python"]},
    ]
    with pytest.raises(ValueError, match="both splits"):
        validate_match_queries(qs, TAX)


def test_graded_metrics_and_kappa() -> None:
    m = graded_metrics(["a", "b", "c"], {"a": 0, "b": 2, "c": 1}, 3)
    assert m["mrr"] == 0.5
    assert m["precision_at_k"] == pytest.approx(1 / 3)  # only grade >= 2 counts
    assert 0 < m["ndcg_at_k"] < 1
    same = {"j": {"python"}}
    assert _cohen_kappa(same, same, 63) == 1.0


def test_annotate_check_progress_and_errors(tmp_path: Path) -> None:
    manifest = tmp_path / "m.jsonl"
    manifest.write_text(
        '{"job_id":"a","split":"dev","stratum":"x"}\n{"job_id":"b","split":"test","stratum":"x"}\n'
    )
    ann = tmp_path / "ann"
    ann.mkdir()
    (ann / "me.jsonl").write_text('{"job_id":"a","skills":{"python":"required"}}\n')
    out = check_annotations(manifest, ann, TAX)
    assert out["files"]["me"]["remaining_by_split"] == {"dev": 0, "test": 1}
    (ann / "bad.jsonl").write_text('{"job_id":"b","skills":{"nope":"required"}}\n')
    with pytest.raises(ValueError, match="unknown skill ids"):
        check_annotations(manifest, ann, TAX)


def test_csv_import_roundtrip_and_rejects(tmp_path: Path) -> None:
    manifest = tmp_path / "m.jsonl"
    manifest.write_text('{"job_id":"a","split":"dev","stratum":"x"}\n')
    ann = tmp_path / "ann"
    good = tmp_path / "g.csv"
    good.write_text("job_id,skill,label\na,python,required\na,sql,Mentioned\n")
    assert import_annotation_csv(good, "me", manifest, ann, TAX)["jobs"] == 1
    assert check_annotations(manifest, ann, TAX)["files"]["me"]["annotated"] == 1
    bad = tmp_path / "b.csv"
    bad.write_text("job_id,skill,label\nzzz,python,required\n")
    with pytest.raises(ValueError, match="not in manifest"):
        import_annotation_csv(bad, "you", manifest, ann, TAX)
    assert not (ann / "you.jsonl").exists()


def test_pilot_is_deterministic_and_stratified(tmp_path: Path) -> None:
    manifest = tmp_path / "m.jsonl"
    manifest.write_text(
        "".join(f'{{"job_id":"j{i}","split":"dev","stratum":"s{i % 2}"}}\n' for i in range(10))
    )
    a = build_pilot(manifest, tmp_path / "p1.jsonl", per_stratum=2)
    build_pilot(manifest, tmp_path / "p2.jsonl", per_stratum=2)
    assert a["pilot_size"] == 4
    assert (tmp_path / "p1.jsonl").read_text() == (tmp_path / "p2.jsonl").read_text()


def test_grade_scale_is_0_to_3(tmp_path: Path) -> None:
    import json

    q = tmp_path / "q.jsonl"
    q.write_text(
        '{"query_id":"1","candidate_id":"c","split":"dev","candidate_skill_ids":["python"]}\n'
    )
    s = tmp_path / "s.jsonl"
    s.write_text(json.dumps({"query_id": "1", "job_id": "a", "grade": 4, "judge": "x"}) + "\n")
    p = tmp_path / "p.json"
    p.write_text('{"1": {"matcher": ["a"], "random": []}}')
    with pytest.raises(ValueError, match="0, 1, 2, 3"):
        score_matching_benchmark(q, s, p, TAX, tmp_path / "r.json")


def test_source_job_leakage_is_rejected(tmp_path: Path) -> None:
    import json

    q = tmp_path / "q.jsonl"
    q.write_text(
        '{"query_id":"1","candidate_id":"c","split":"dev","candidate_skill_ids":["python"],'
        '"source_job_id":"a"}\n'
    )
    s = tmp_path / "s.jsonl"
    s.write_text(json.dumps({"query_id": "1", "job_id": "a", "grade": 1, "judge": "x"}) + "\n")
    p = tmp_path / "p.json"
    p.write_text('{"1": {"matcher": ["a"], "random": []}}')
    with pytest.raises(ValueError, match="leakage"):
        score_matching_benchmark(q, s, p, TAX, tmp_path / "r.json")
