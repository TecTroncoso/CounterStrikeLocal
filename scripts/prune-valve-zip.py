#!/usr/bin/env python3
"""Remove unused native binaries from an existing valve.zip.

The browser client loads the game and client logic from the WebAssembly side
modules under ``vendor/``.  The native ``.so``, ``.dll``, ``.dylib`` and
``.pdb`` copies of a desktop install are never opened: they add ~32 MiB
uncompressed (and ~12 MiB in the compressed archive) to every download.

``build-valve-zip.py`` already excludes them when it builds an archive from a
game installation.  This script is the alternative for when the installation
is no longer available: it rewrites the existing ``valve.zip`` without those
files.  The archive is recompressed at level 9, which also saves a few MiB.

Run ``scripts/split-valve-parts.py`` afterwards to regenerate ``valve-parts/``.
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARCHIVE = ROOT / "valve.zip"
DROP_SUFFIXES = {".so", ".dll", ".dylib", ".pdb"}


def human(size: float) -> str:
    for unit in ("B", "KiB", "MiB", "GiB"):
        if size < 1024 or unit == "GiB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GiB"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--archive",
        type=Path,
        default=DEFAULT_ARCHIVE,
        help=f"valve.zip de entrada (padrão: {DEFAULT_ARCHIVE})",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="arquivo de saída (padrão: substitui o de entrada)",
    )
    parser.add_argument(
        "--level",
        type=int,
        default=9,
        choices=range(0, 10),
        help="nível de compressão deflate (0-9, padrão: 9)",
    )
    args = parser.parse_args()

    source_path = args.archive.resolve()
    if not source_path.is_file():
        raise SystemExit(f"Arquivo não encontrado: {source_path}")

    out_path = args.out.resolve() if args.out else source_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = out_path.with_name(out_path.name + ".tmp")
    if temp_path.exists():
        temp_path.unlink()

    dropped: list[tuple[str, int, int]] = []
    kept = 0
    raw_before = 0
    raw_kept = 0

    print(f"Entrada : {source_path} ({human(source_path.stat().st_size)})")
    with zipfile.ZipFile(source_path) as source, zipfile.ZipFile(
        temp_path,
        "w",
        compression=zipfile.ZIP_DEFLATED if args.level else zipfile.ZIP_STORED,
        compresslevel=args.level or None,
    ) as target:
        entries = source.infolist()
        for index, info in enumerate(entries, start=1):
            if info.is_dir():
                continue

            raw_before += info.file_size
            if Path(info.filename).suffix.lower() in DROP_SUFFIXES:
                dropped.append((info.filename, info.file_size, info.compress_size))
                continue

            # Preserve the original name, timestamp and permissions.  The
            # data is re-read (which also validates its CRC) and recompressed.
            new_info = zipfile.ZipInfo(info.filename, date_time=info.date_time)
            new_info.compress_type = (
                zipfile.ZIP_DEFLATED if args.level else zipfile.ZIP_STORED
            )
            new_info.external_attr = info.external_attr
            new_info.create_system = info.create_system
            new_info.comment = info.comment

            with source.open(info) as stream:
                target.writestr(new_info, stream.read())

            raw_kept += info.file_size
            kept += 1
            if index % 500 == 0 or index == len(entries):
                print(f"  [{index}/{len(entries)}] {info.filename}", flush=True)

    # Validate before replacing the only copy.  testzip() decompresses every
    # entry, so a truncated or corrupt source archive cannot slip through.
    print("Verificando o arquivo gerado...", flush=True)
    try:
        with zipfile.ZipFile(temp_path) as check:
            bad = check.testzip()
            if bad:
                raise SystemExit(f"Entrada corrompida no arquivo gerado: {bad}")
            remaining = [
                info.filename
                for info in check.infolist()
                if Path(info.filename).suffix.lower() in DROP_SUFFIXES
            ]
            if remaining:
                raise SystemExit(
                    "Ainda há binários nativos no arquivo gerado: "
                    + ", ".join(remaining[:5])
                )
            output_entries = len(check.infolist())
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise

    old_size = source_path.stat().st_size
    temp_path.replace(out_path)
    new_size = out_path.stat().st_size

    print()
    print(f"Removidos : {len(dropped)} arquivos, {human(sum(item[1] for item in dropped))} brutos")
    for name, raw, compressed in dropped:
        print(f"  {human(raw):>9}  {human(compressed):>9}  {name}")
    print(f"Arquivos  : {output_entries} (antes {len(entries)})")
    print(f"Bruto     : {human(raw_kept)} (antes {human(raw_before)})")
    print(f"Gerado    : {out_path} ({human(new_size)}, antes {human(old_size)})")
    print(f"Ahorro    : {human(old_size - new_size)}")
    print()
    print("Ahora ejecuta: python scripts/split-valve-parts.py")


if __name__ == "__main__":
    sys.exit(main())
