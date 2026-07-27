#!/usr/bin/env python3
"""Serve IPO Ledger static files and refresh data on demand via /api/*."""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORT = 8765
# Skip re-scrape if the same dataset was refreshed this recently (seconds).
# Covers double-load / hard refresh; navigating after this still gets fresh data.
MIN_REFRESH_AGE = 45

DATASETS = {
    "listed": {"script": "scrape.py", "json": "data.json"},
    "queue": {"script": "scrape_queue.py", "json": "queue-data.json"},
    "calendar": {"script": "scrape_calendar.py", "json": "calendar-data.json"},
}

_locks = {name: threading.Lock() for name in DATASETS}
_last_ok: dict[str, float] = {}


def read_payload(name: str) -> dict:
    path = ROOT / DATASETS[name]["json"]
    return json.loads(path.read_text(encoding="utf-8"))


def refresh_dataset(name: str, force: bool = False) -> dict:
    meta = DATASETS[name]
    path = ROOT / meta["json"]
    with _locks[name]:
        age = time.time() - _last_ok.get(name, 0)
        if (
            not force
            and path.exists()
            and name in _last_ok
            and age < MIN_REFRESH_AGE
        ):
            return read_payload(name)

        proc = subprocess.run(
            [sys.executable, meta["script"]],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=180,
        )
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "scrape failed").strip()
            # Fall back to last good file if present
            if path.exists():
                payload = read_payload(name)
                payload["_refresh_error"] = err[-500:]
                return payload
            raise RuntimeError(err[-500:] or f"{meta['script']} failed")

        _last_ok[name] = time.time()
        return read_payload(name)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, status: int, message: str) -> None:
        self._send_json({"error": message}, status=status)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        qs = parse_qs(parsed.query)
        force = qs.get("force", ["0"])[0] in ("1", "true", "yes")

        if path.startswith("/api/"):
            name = path[len("/api/") :]
            if name not in DATASETS:
                self._send_error_json(404, f"unknown dataset: {name}")
                return
            try:
                payload = refresh_dataset(name, force=force)
                self._send_json(payload)
            except Exception as err:  # noqa: BLE001
                self._send_error_json(502, str(err))
            return

        super().do_GET()


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"IPO Ledger → http://{HOST}:{PORT}/")
    print("  /api/listed  /api/queue  /api/calendar  (refresh on request)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
