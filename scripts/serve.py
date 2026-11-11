#!/usr/bin/env python3
"""Static file server for the browser client.

Usage::

    python scripts/serve.py [--port 8080] [--host 127.0.0.1]

Serving over HTTP (instead of opening index.html from disk) is mandatory:
the engine is loaded through ``fetch``/WebAssembly, and browsers refuse
those requests on ``file://`` origins.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import mimetypes
import socketserver
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# WebAssembly must be served with the ``application/wasm`` MIME type or the
# browser refuses to stream-compile it.
mimetypes.add_type("application/wasm", ".wasm")
mimetypes.add_type("application/octet-stream", ".pk3")


class Handler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path: str) -> str:
        """Resolve a request inside ROOT and refuse dotfiles.

        The README suggests ``--host 0.0.0.0`` to play from a phone on the
        same Wi-Fi.  Without this check that would also publish ``.env``
        (which holds the Cloudflare token) and ``.git``.  Dotfiles are never
        needed by the game, so they are mapped to a path that does not exist
        and the normal 404 handling takes over.
        """
        resolved = Path(super().translate_path(path)).resolve()
        root = ROOT.resolve()
        try:
            relative = resolved.relative_to(root)
        except ValueError:
            return str(root / "__forbidden__")
        if any(part.startswith(".") for part in relative.parts):
            return str(root / "__forbidden__")
        return str(resolved)

    def end_headers(self) -> None:
        # Mirror the Cloudflare `_headers` rules that matter during local
        # development: the manifest and the entry points must be revalidated
        # so a regenerated archive is picked up without a hard reload.
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html", "/config.js", "/loopback-net.js") or path.endswith(
            "/manifest.json"
        ):
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


class Server(socketserver.ThreadingTCPServer):
    """Server that survives the client.

    The browser opens several connections at once (one per 8 MiB part) and
    keeps them alive, so the queue of pending connections has to be bigger
    than the default five, and the worker threads must not keep the process
    alive on shutdown.
    """

    allow_reuse_address = True
    daemon_threads = True
    request_queue_size = 64


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    handler = functools.partial(Handler, directory=str(ROOT))
    # The client fetches several 8 MiB parts at once, so the server has to
    # handle connections concurrently.
    with Server((args.host, args.port), handler) as server:
        print(f"Servindo {ROOT} em http://{args.host}:{args.port}/", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nEncerrando.", flush=True)


if __name__ == "__main__":
    main()
