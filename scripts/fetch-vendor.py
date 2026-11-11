#!/usr/bin/env python3
"""Download the third-party runtime files used by the browser client.

The engine, the CS 1.6 client library and the ZIP unpacker are not part of
this repository: they are fetched from the public CDNs and stored under
``vendor/`` so the page works without network access.

Usage::

    python scripts/fetch-vendor.py [--force]

Every file is verified against its SHA-256 checksum; a file that is already
present and valid is not downloaded again.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor"

XASH3D_VERSION = "1.2.1"
CS16_CLIENT_VERSION = "0.1.2"
JSZIP_VERSION = "3.10.1"

XASH3D_CDN = f"https://cdn.jsdelivr.net/npm/xash3d-fwgs@{XASH3D_VERSION}/dist"
CS16_CLIENT_CDN = f"https://cdn.jsdelivr.net/npm/cs16-client@{CS16_CLIENT_VERSION}/dist"
JSZIP_CDN = f"https://cdn.jsdelivr.net/npm/jszip@{JSZIP_VERSION}/dist"

# (destination relative to vendor/, url, sha256)
FILES = [
    (
        "xash3d-fwgs/generated/xash.js",
        f"{XASH3D_CDN}/generated/xash.js",
        "b3cbe61b927abcc96ba9e2da17c867477a392645029a16cc4b4b51ed596c7358",
    ),
    (
        "xash3d-fwgs/xash.wasm",
        f"{XASH3D_CDN}/xash.wasm",
        "a517d46bcc34a475b0a6ba09ab533b290000a2de64e0dcfe28229fe73b1a7e55",
    ),
    (
        "xash3d-fwgs/filesystem_stdio.wasm",
        f"{XASH3D_CDN}/filesystem_stdio.wasm",
        "18daf7355d9b5225570b39d8c0086a4a5b90b4769afa3f9c3350c6b672e7604e",
    ),
    (
        "xash3d-fwgs/libref_webgl2.wasm",
        f"{XASH3D_CDN}/libref_webgl2.wasm",
        "490b685fd4ad8cb91ca798636d20727a593723be8b00899ca451196889f7c868",
    ),
    (
        "cs16-client/cstrike/cl_dlls/client_emscripten_wasm32.wasm",
        f"{CS16_CLIENT_CDN}/cstrike/cl_dlls/client_emscripten_wasm32.wasm",
        "3a8b26a14ce562ab3bcfbf2a8f57c2822ae04c2a134caedbb03355003ea5ecf7",
    ),
    (
        "cs16-client/cstrike/cl_dlls/menu_emscripten_wasm32.wasm",
        f"{CS16_CLIENT_CDN}/cstrike/cl_dlls/menu_emscripten_wasm32.wasm",
        "d5802742d32b9295efa7479114798c832248c758ee4474af0dafaa2773d7d086",
    ),
    (
        "cs16-client/cstrike/dlls/cs_emscripten_wasm32.wasm",
        f"{CS16_CLIENT_CDN}/cstrike/dlls/cs_emscripten_wasm32.wasm",
        "9c838823ddec4f65986a0f8e715d7b22f01e2e9dc9de59fe03752bcdebdc0b97",
    ),
    (
        "cs16-client/cstrike/extras.pk3",
        f"{CS16_CLIENT_CDN}/cstrike/extras.pk3",
        "49d5e00ce50ed01aace3a1c2035a2959c3f7e4457ca2b6c31d01e4cd2a7a5d69",
    ),
    (
        "jszip/jszip.min.js",
        f"{JSZIP_CDN}/jszip.min.js",
        "acc7e41455a80765b5fd9c7ee1b8078a6d160bbbca455aeae854de65c947d59e",
    ),
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="download every file again, even when it is already valid",
    )
    args = parser.parse_args()

    failures = 0
    for relative, url, checksum in FILES:
        target = VENDOR / relative
        if target.exists() and not args.force:
            if sha256(target) == checksum:
                print(f"ok      {relative}")
                continue
            print(f"redo    {relative} (checksum mismatch)")

        target.parent.mkdir(parents=True, exist_ok=True)
        print(f"fetch   {url}")
        try:
            with urllib.request.urlopen(url, timeout=120) as response:
                data = response.read()
        except OSError as error:
            print(f"ERROR   {relative}: {error}", file=sys.stderr)
            failures += 1
            continue

        if hashlib.sha256(data).hexdigest() != checksum:
            print(f"ERROR   {relative}: checksum mismatch", file=sys.stderr)
            failures += 1
            continue

        target.write_bytes(data)
        print(f"saved   {relative} ({len(data)} bytes)")

    if failures:
        print(f"\n{failures} file(s) could not be fetched.", file=sys.stderr)
        return 1

    print("\nAll runtime files are in place.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
