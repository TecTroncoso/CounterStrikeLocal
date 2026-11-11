#!/usr/bin/env python3
"""Split valve.zip into GitHub-friendly binary parts and write a manifest."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "valve.zip"
OUTPUT_DIR = ROOT / "valve-parts"
PART_PREFIX = "valve.part-"
PART_SIZE = 8 * 1024 * 1024


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    if not ARCHIVE.is_file():
        raise SystemExit(f"Arquivo não encontrado: {ARCHIVE}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for old_part in OUTPUT_DIR.glob(f"{PART_PREFIX}*"):
        old_part.unlink()

    parts: list[dict[str, int | str]] = []
    with ARCHIVE.open("rb") as source:
        index = 0
        while True:
            data = source.read(PART_SIZE)
            if not data:
                break
            part_path = OUTPUT_DIR / f"{PART_PREFIX}{index:03d}"
            part_path.write_bytes(data)
            parts.append(
                {
                    "file": part_path.name,
                    "size": len(data),
                    "sha256": sha256_bytes(data),
                }
            )
            index += 1

    manifest = {
        "source": "https://github.com/TecTroncoso/CounterStrikeLocal/tree/main/valve-parts",
        "archive": ARCHIVE.name,
        "archiveSize": ARCHIVE.stat().st_size,
        "archiveSha256": sha256_file(ARCHIVE),
        "partSize": PART_SIZE,
        "partCount": len(parts),
        "parts": parts,
    }
    (OUTPUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({key: manifest[key] for key in (
        "archiveSize", "archiveSha256", "partSize", "partCount"
    )}, indent=2))


if __name__ == "__main__":
    main()
