#!/usr/bin/env python3
"""Serve the atlas locally (needs only the packages in requirements.txt).

    python tools/serve.py            # http://127.0.0.1:8004/
    python tools/serve.py --port 9000

Serves the repo root; "/" redirects to the viewer. Binds to 127.0.0.1 only.
.nii.gz files are sent as-is (no Content-Encoding) — NiiVue decompresses them.
Painting mode saves through POST /api/save (localhost pages only); saving imports
numpy and nibabel (tools/save_case.py), so start it from a venv with requirements.txt installed.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import functools
import http.server
import json
import re
import threading
import zlib
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from save_case import SaveError, case_token, save_case

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PORT = 8004  # 8000 is protocol_manager's MkDocs
MAX_BODY = 64 * 1024 * 1024  # request body, bytes
MAX_LABELS_BYTES = 512 * 1024 * 1024  # labels after gunzip
CASE_ID = re.compile(r"[A-Za-z0-9_-]+")
SAVE_LOCK = threading.Lock()  # one save at a time


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def gunzip_capped(data: bytes, limit: int) -> bytes:
    d = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        out = d.decompress(data, limit + 1)
        if len(out) > limit:
            raise ApiError(400, f"labels too large (over {limit} bytes unzipped)")
        if d.unconsumed_tail:
            raise ApiError(400, "labels too large")
        if not d.eof:
            raise ApiError(400, "labels_gz_b64 is not a complete gzip stream")
    except zlib.error as e:
        raise ApiError(400, f"labels_gz_b64 is not valid gzip: {e}")
    return out


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".gz": "application/octet-stream",
        ".nii": "application/octet-stream",
        ".js": "text/javascript",
        ".json": "application/json",
    }

    # ---- API: /api/token (GET), /api/save (POST); localhost pages only ----

    def _json(self, status: int, obj) -> None:
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _check_origin(self) -> None:
        port = self.server.server_address[1]
        hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        if self.headers.get("Host") not in hosts:
            raise ApiError(403, "Host not allowed")
        origin = self.headers.get("Origin")
        if origin is not None and origin not in {f"http://{h}" for h in hosts}:
            raise ApiError(403, "Origin not allowed")

    def _api(self, fn) -> None:
        try:
            self._check_origin()
            self._json(200, fn())
        except ApiError as e:
            self.close_connection = True  # a request body may be unread
            self._json(e.status, {"error": str(e)})
        except SaveError as e:
            self._json(e.status, {"error": str(e)})
        except Exception as e:  # save_case checks first, so the case is unchanged
            self.close_connection = True
            self._json(500, {"error": f"{type(e).__name__}: {e}"})

    def _api_token(self):
        q = parse_qs(urlsplit(self.path).query)
        cid = (q.get("case") or [""])[0]
        case = Path(self.directory) / "data" / cid
        if not CASE_ID.fullmatch(cid) or not case.is_dir():
            raise ApiError(404, "no such case")
        return {"token": case_token(case)}

    def _api_save(self):
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json":
            raise ApiError(403, "Content-Type must be application/json")
        length = self.headers.get("Content-Length")
        if length is None:
            raise ApiError(411, "Content-Length required")
        if not length.isdigit():
            raise ApiError(400, "bad Content-Length")
        if int(length) > MAX_BODY:
            raise ApiError(413, f"body over {MAX_BODY} bytes")
        raw = self.rfile.read(int(length))
        try:
            req = json.loads(raw)
            cid, token = req["case_id"], req["token"]
            values, checked, points = req["values"], req["checked"], req["points"]
            b64 = req["labels_gz_b64"]
        except (ValueError, KeyError, TypeError) as e:
            raise ApiError(400, f"bad request JSON: {type(e).__name__}: {e}")
        if not (isinstance(cid, str) and isinstance(token, str) and isinstance(b64, str)
                and isinstance(values, dict) and isinstance(checked, list)
                and isinstance(points, list)):
            raise ApiError(400, "bad request field types")
        if not CASE_ID.fullmatch(cid):
            raise ApiError(400, "bad case_id")
        try:
            gz = base64.b64decode(b64, validate=True)
        except (binascii.Error, ValueError):
            raise ApiError(400, "labels_gz_b64 is not valid base64")
        labels = gunzip_capped(gz, MAX_LABELS_BYTES)
        with SAVE_LOCK:
            return save_case(Path(self.directory), cid, token=token, labels=labels,
                             values=values, checked=checked, points=points)

    def do_POST(self):
        if urlsplit(self.path).path == "/api/save":
            self._api(self._api_save)
        else:
            self.send_error(404)

    def do_GET(self):
        if urlsplit(self.path).path == "/api/token":
            self._api(self._api_token)
            return
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


def make_server(root, port: int) -> http.server.ThreadingHTTPServer:
    handler = functools.partial(Handler, directory=str(root))
    return http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = ap.parse_args()
    with make_server(ROOT, args.port) as httpd:
        print(f"Atlas: http://127.0.0.1:{args.port}/   (Ctrl+C to stop)")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
