#!/usr/bin/env python3
"""Rebuild ``valve.zip`` from the committed ``valve-parts/`` chunks.

The repository stores the game archive split into 8 MiB parts because GitHub
rejects files larger than 100 MiB in a normal push and Cloudflare Pages
rejects anything above 25 MiB.  The parts are byte-for-byte the archive, so
the single file can always be reconstructed locally:

    python scripts/join-valve-parts.py

The SHA-256 of the result is checked against ``valve-parts/manifest.json``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARTS_DIR = ROOT / "valve-parts"
MANIFEST = PARTS_DIR / "manifest.json"
DEFAULT_OUT = ROOT / "valve.zip"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"archivo de salida (padrão: {DEFAULT_OUT})",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="comprobar las partes sin escribir el archivo",
    )
    args = parser.parse_args()

    if not MANIFEST.is_file():
        raise SystemExit(f"Manifiesto não encontrado: {MANIFEST}")

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    parts = manifest.get("parts", [])
    if not parts:
        raise SystemExit("El manifiesto no contiene partes")

    out_path = args.out.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = out_path.with_name(out_path.name + ".tmp")
    if temp_path.exists():
        temp_path.unlink()

    digest = hashlib.sha256()
    total = 0
    with temp_path.open("wb") as target:
        for part in parts:
            path = PARTS_DIR / part["file"]
            if not path.is_file():
                temp_path.unlink(missing_ok=True)
                raise SystemExit(f"Falta la parte: {path}")
            data = path.read_bytes()
            if len(data) != part["size"]:
                temp_path.unlink(missing_ok=True)
                raise SystemExit(f"Tamaño inesperado en {part['file']}")
            digest.update(data)
            target.write(data)
            total += len(data)

    archive_sha = digest.hexdigest()
    if total != manifest["archiveSize"]:
        temp_path.unlink(missing_ok=True)
        raise SystemExit("O tamanho total não corresponde ao manifesto")
    if archive_sha != manifest["archiveSha256"]:
        temp_path.unlink(missing_ok=True)
        raise SystemExit(f"SHA-256 inesperado: {archive_sha}")

    if args.verify_only:
        temp_path.unlink(missing_ok=True)
        print(f"Partes correctas: {total} bytes, sha256 {archive_sha}")
        return

    temp_path.replace(out_path)
    print(f"Gerado: {out_path} ({total} bytes)")
    print(f"sha256: {archive_sha}")


if __name__ == "__main__":
    sys.exit(main())
