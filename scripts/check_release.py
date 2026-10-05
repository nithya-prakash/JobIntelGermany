"""Fail if the tree contains files that must never be published (restricted ad text, data)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".venv", ".git", "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache"}
LOCAL_ONLY = {ROOT / "data/raw", ROOT / "data/processed"}
BAD_SUFFIXES = {".parquet", ".duckdb", ".zip", ".db", ".sqlite"}
BAD_KEYS = {"description", "snippets", "requirements", "responsibilities", "benefits", "text"}
MAX_BYTES = 1_000_000


def _text_keys(value: object) -> set[str]:
    """Keys that hold prose (long strings or string lists); field-name counts are ignored."""
    found: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            long_str = isinstance(item, str) and len(item) > 200
            str_list = isinstance(item, list) and item and all(isinstance(i, str) for i in item)
            if key in BAD_KEYS and (long_str or str_list):
                found.add(key)
            found |= _text_keys(item)
    elif isinstance(value, list):
        for item in value:
            found |= _text_keys(item)
    return found


def scan(root: Path = ROOT) -> list[str]:
    problems: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or SKIP_DIRS & set(path.relative_to(root).parts):
            continue
        if any(local in path.parents for local in LOCAL_ONLY if root == ROOT):
            continue
        rel = path.relative_to(root)
        if path.suffix in BAD_SUFFIXES:
            problems.append(f"{rel}: data/binary file type {path.suffix}")
        elif path.stat().st_size > MAX_BYTES:
            problems.append(f"{rel}: larger than {MAX_BYTES} bytes")
        elif path.suffix in {".json", ".jsonl"}:
            text = path.read_text(encoding="utf-8")
            try:
                docs = (
                    [json.loads(x) for x in text.splitlines() if x.strip()]
                    if path.suffix == ".jsonl"
                    else [json.loads(text)]
                )
            except json.JSONDecodeError:
                continue
            keys = set().union(*(_text_keys(d) for d in docs)) if docs else set()
            if keys:
                problems.append(f"{rel}: contains prose-bearing keys {sorted(keys)}")
    return problems


def main() -> None:
    problems = scan()
    for problem in problems:
        print("RELEASE BLOCKER:", problem)
    print(f"release check: {'FAILED' if problems else 'passed'} ({len(problems)} problems)")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
