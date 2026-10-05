import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("check_release", ROOT / "scripts/check_release.py")
assert spec and spec.loader
check_release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_release)


def test_guard_flags_data_files_and_prose(tmp_path: Path) -> None:
    (tmp_path / "x.parquet").write_bytes(b"0")
    (tmp_path / "r.json").write_text(json.dumps({"snippets": ["quoted ad text"]}))
    (tmp_path / "ok.json").write_text(json.dumps({"description": 5, "gold": ["python"]}))
    problems = check_release.scan(tmp_path)
    assert len(problems) == 2


def test_repository_tree_is_clean() -> None:
    assert check_release.scan() == []
