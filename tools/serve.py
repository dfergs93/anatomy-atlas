#!/usr/bin/env python3
"""Serve the atlas locally (standard library only).

    python tools/serve.py            # http://127.0.0.1:8000/
    python tools/serve.py --port 9000

Serves the repo root; "/" redirects to the viewer. Binds to 127.0.0.1 only.
For departmental use, put the repo behind a proper web server instead.
.nii.gz files are sent as-is (no Content-Encoding) — NiiVue decompresses them.
Author-mode save endpoint: Phase D.
"""
from __future__ import annotations

import argparse
import functools
import http.server
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".gz": "application/octet-stream",
        ".nii": "application/octet-stream",
        ".js": "text/javascript",
        ".json": "application/json",
    }

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.send_response(302)
            self.send_header("Location", "/viewer/")
            self.end_headers()
            return
        super().do_GET()

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, fmt, *args):
        if args and str(args[1])[0] in "45":  # only log errors
            super().log_message(fmt, *args)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    handler = functools.partial(Handler, directory=str(ROOT))
    with http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler) as httpd:
        print(f"Atlas: http://127.0.0.1:{args.port}/   (Ctrl+C to stop)")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
