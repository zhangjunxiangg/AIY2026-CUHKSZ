#!/usr/bin/env python3
"""Temporarily serve only the fixed latest auxiliary-camera files."""

from __future__ import annotations

import argparse
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlparse


ALLOWED_FILES = {
    "aux-camera-latest-color.jpg",
    "aux-camera-latest-depth.png",
    "aux-camera-latest-depth-preview.pgm",
    "aux-camera-latest.json",
}


class LatestOnlyHandler(SimpleHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        decoded = unquote(parsed.path)
        candidate = PurePosixPath(decoded)
        if len(candidate.parts) != 2 or candidate.name not in ALLOWED_FILES:
            self.send_error(404)
            return
        self.path = "/" + candidate.name
        super().do_GET()

    def list_directory(self, path: str):  # type: ignore[no-untyped-def]
        self.send_error(403)
        return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--bind", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--ttl", type=int, required=True)
    args = parser.parse_args()
    if not 60 <= args.ttl <= 3600:
        raise SystemExit("ttl must be within 60..3600 seconds")

    handler = lambda *values, **options: LatestOnlyHandler(  # noqa: E731
        *values,
        directory=str(args.directory),
        **options,
    )
    server = ThreadingHTTPServer((args.bind, args.port), handler)
    server.timeout = 1.0
    deadline = time.monotonic() + args.ttl
    while time.monotonic() < deadline:
        server.handle_request()
    server.server_close()


if __name__ == "__main__":
    main()
