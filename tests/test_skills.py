from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from german_job_market.skill_pipeline import evaluate_extraction, run_extraction
from german_job_market.skills import extract_skill_ids, load_taxonomy

ROOT = Path(__file__).resolve().parents[1]


def test_bilingual_aliases_and_token_boundaries() -> None:
    taxonomy = load_taxonomy(ROOT / "configs/skill_taxonomy.toml")

    found = extract_skill_ids(
        "Python-Kenntnisse, maschinelles Lernen, JavaScript, Java, C++ und Teamfähigkeit.",
        taxonomy,
    )

    assert set(found) == {"python", "machine_learning", "javascript", "java", "cpp", "teamwork"}
    assert "java" not in extract_skill_ids("JavaScript developer", taxonomy)
    assert "git" not in extract_skill_ids("digital strategy", taxonomy)
    assert "rest_api" not in extract_skill_ids("Den Rest lernen Sie bei uns.", taxonomy)
    assert "rest_api" in extract_skill_ids("Expose the REST endpoint.", taxonomy)


def test_full_batch_extraction_and_labeled_evaluation(tmp_path: Path) -> None:
    taxonomy = load_taxonomy(ROOT / "configs/skill_taxonomy.toml")
    input_path = tmp_path / "jobs.parquet"
    output_path = tmp_path / "skills.parquet"
    extract_report = tmp_path / "extract.json"
    eval_report = tmp_path / "eval.json"
    gold_path = tmp_path / "gold.jsonl"

    source = pa.table(
        {
            "job_id": ["german-1", "english-1"],
            "title": ["Java Entwickler", "Frontend Software Engineer"],
            "description": [
                "Python-Kenntnisse und Teamfähigkeit erwünscht.",
                "Build with React and Kubernetes; JavaScript experience preferred.",
            ],
        }
    )
    pq.write_table(source, input_path)
    gold_path.write_text(
        '{"job_id":"german-1","primary_language":"de","skill_ids":["java","python","teamwork"]}\n'
        '{"job_id":"english-1","primary_language":"en","skill_ids":["react","kubernetes","javascript"]}\n',
        encoding="utf-8",
    )

    extraction = run_extraction(input_path, output_path, taxonomy, extract_report, batch_size=1)
    result = evaluate_extraction(input_path, gold_path, taxonomy, eval_report)

    assert extraction["records_processed"] == 2
    assert extraction["records_with_skills"] == 2
    assert extraction["skill_assignments"] == 6
    with duckdb.connect() as connection:
        rows = connection.execute(
            "SELECT job_id, skill_ids FROM read_parquet(?) ORDER BY job_id", [str(output_path)]
        ).fetchall()
    assert rows == [
        ("english-1", ["javascript", "react", "kubernetes"]),
        ("german-1", ["python", "java", "teamwork"]),
    ]
    assert result["overall"]["precision"] == 1.0
    assert result["overall"]["recall"] == 1.0
    assert result["sample_size"] == 2
    assert result["by_primary_language"]["de"]["f1"] == 1.0
    assert result["by_primary_language"]["en"]["f1"] == 1.0


def test_extract_skill_spans_returns_character_offsets() -> None:
    from german_job_market.skills import extract_skill_spans, load_taxonomy

    taxonomy = load_taxonomy(Path(__file__).resolve().parents[1] / "configs/skill_taxonomy.toml")
    text = "We use Python and SQL."
    spans = extract_skill_spans(text, taxonomy)
    assert text[slice(*spans["python"][0])] == "Python"
    assert text[slice(*spans["sql"][0])] == "SQL"


def test_exclusion_phrase_blocks_false_friend() -> None:
    from pathlib import Path

    from german_job_market.skills import extract_skill_ids, load_taxonomy

    taxonomy = load_taxonomy(Path("configs/skill_taxonomy.toml"))
    text = "Knowledge of communication protocols"
    assert "communication" not in extract_skill_ids(text, taxonomy)
    assert "communication" in extract_skill_ids("Strong communication skills", taxonomy)
