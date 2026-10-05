"""Download the versioned public Mendeley Data snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
import tomllib
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(output: Path, overwrite: bool = False) -> None:
    with (ROOT / "configs/source.toml").open("rb") as source_file:
        metadata = tomllib.load(source_file)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and not overwrite:
        raise FileExistsError(f"{output} exists; pass --overwrite to replace it")
    url = metadata["download_url"].format(
        dataset_id=metadata["dataset_id"], version=metadata["version"]
    )
    temporary = output.with_name(f".{output.name}.part")
    request = urllib.request.Request(
        url, headers={"User-Agent": "german-job-market-intelligence/0.1"}
    )
    try:
        with (
            urllib.request.urlopen(request, timeout=90) as response,
            temporary.open("wb") as target,
        ):
            while chunk := response.read(1024 * 1024):
                target.write(chunk)
        with zipfile.ZipFile(temporary) as archive:
            json_files = [name for name in archive.namelist() if name.lower().endswith(".json")]
            if len(json_files) != 1:
                raise ValueError(
                    f"Expected one JSON file in downloaded archive; found {len(json_files)}"
                )
            if archive.testzip() is not None:
                raise ValueError("Downloaded archive failed its ZIP CRC check")
        temporary.replace(output)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise

    manifest = {
        **metadata,
        "downloaded_at_utc": datetime.now(UTC).isoformat(),
        "archive_filename": output.name,
        "archive_bytes": output.stat().st_size,
        "archive_sha256": sha256(output),
    }
    manifest_path = output.parent / "source_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "data/raw/stepstone-v2.zip")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    download(args.output, overwrite=args.overwrite)


if __name__ == "__main__":
    main()
