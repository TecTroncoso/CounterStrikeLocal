#!/usr/bin/env python3
"""Build valve.zip from a local Counter-Strike 1.6 (GoldSrc) installation.

The browser client needs the base engine assets (``valve/``) plus the
Counter-Strike specific assets (``cstrike/``) available inside the WASM
filesystem before the engine starts.  The upstream project shipped a
pre-built ``valve.zip``; this script regenerates an equivalent archive from
a local install so the whole payload can be rebuilt from assets the user
already owns.

The resulting archive is consumed by ``scripts/split-valve-parts.py``.
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARCHIVE = ROOT / "valve.zip"
DEFAULT_INSTALL = Path(r"C:\games\Counter-Strike 1.6")

# Subfolders of the install that are shipped inside the archive.
GAME_DIRS = ("valve", "cstrike")

# Installed "HD" texture pack: hundreds of MB of optional high resolution
# replacements.  The engine runs fine without it and it would dominate the
# archive size, so it stays out of the payload.
SKIP_DIRS = {"cstrike_hd", "htmlcache", "crashes", "platform"}

# The browser client loads the game and client logic from the WebAssembly side
# modules in vendor/; the native .so/.dll/.dylib copies of a desktop install
# are never opened.  They are ~32 MiB uncompressed (and a good part of the
# compressed archive), so they are excluded by default.  Use --keep-native if
# the same archive is going to feed a native build.
SKIP_SUFFIXES = {".so", ".dll", ".dylib", ".pdb"}


def human(size: float) -> str:
    for unit in ("B", "KiB", "MiB", "GiB"):
        if size < 1024 or unit == "GiB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GiB"


def collect(install: Path, keep_native: bool = False) -> list[tuple[Path, str]]:
    """Return (absolute path, archive name) pairs for every file to pack."""
    entries: list[tuple[Path, str]] = []
    for game_dir in GAME_DIRS:
        base = install / game_dir
        if not base.is_dir():
            raise SystemExit(f"Pasta não encontrada: {base}")
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(install)
            if SKIP_DIRS.intersection(relative.parts):
                continue
            if not keep_native and path.suffix.lower() in SKIP_SUFFIXES:
                continue
            entries.append((path, relative.as_posix()))
    return entries


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--install",
        type=Path,
        default=DEFAULT_INSTALL,
        help=f"raiz da instalação do Counter-Strike 1.6 (padrão: {DEFAULT_INSTALL})",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_ARCHIVE,
        help=f"caminho do valve.zip gerado (padrão: {DEFAULT_ARCHIVE})",
    )
    parser.add_argument(
        "--level",
        type=int,
        default=6,
        choices=range(0, 10),
        help="nível de compressão deflate (0-9, padrão: 6)",
    )
    parser.add_argument(
        "--keep-native",
        action="store_true",
        help="inclui .so/.dll/.dylib (não usados pelo cliente web)",
    )
    args = parser.parse_args()

    install = args.install.resolve()
    if not install.is_dir():
        raise SystemExit(f"Instalação não encontrada: {install}")

    entries = collect(install, keep_native=args.keep_native)
    if not entries:
        raise SystemExit("Nenhum arquivo encontrado para empacotar")

    raw_size = sum(path.stat().st_size for path, _ in entries)
    print(f"Instalação : {install}")
    print(f"Arquivos  : {len(entries)}")
    print(f"Bruto     : {human(raw_size)}")

    out = args.out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    compression = zipfile.ZIP_STORED if args.level == 0 else zipfile.ZIP_DEFLATED
    with zipfile.ZipFile(out, "w", compression=compression, compresslevel=args.level or None) as archive:
        for index, (path, arcname) in enumerate(entries, start=1):
            archive.write(path, arcname)
            if index % 500 == 0 or index == len(entries):
                print(f"  [{index}/{len(entries)}] {arcname}", flush=True)

    packed_size = out.stat().st_size
    print(f"Gerado    : {out}")
    print(f"Comprimido: {human(packed_size)} (razão {packed_size / raw_size:.1%})")


if __name__ == "__main__":
    sys.exit(main())
