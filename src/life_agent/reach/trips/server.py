# src/life_agent/reach/trips/server.py
"""Trips timeline — a read-only reach channel over the trips projection.

Same shape and rationale as life_agent/reach/web/server.py (read its docstring): a tiny single-
threaded, HTTP/1.0 stdlib http.server serving one self-contained page plus a small JSON API,
reachable only over Tailscale (the network boundary is the only gate — no auth). Two differences
from the GTD sibling:

* **Read-only.** Trips mutations (observe/cancel/amend/supersede) come from ingest, never a
  button, so there is no command seam and no POST routes — only GET reads over trips.store.
* **No user_id.** The trips ledger is single-owner (the reservation row has no user column), so
  store.timeline()/now_next()/search() take no id and nothing is resolved from the keyring.

It also publishes GET /calendar.ics — a subscribable feed (ics.to_ics over the current timeline)
so the itinerary lands in the phone's native calendar and works offline / in airplane mode, where
the Tailscale origin is unreachable.
"""
from __future__ import annotations

import os
import traceback
from datetime import datetime
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, HTTPServer
from json import dumps
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from life_agent.reach.trips.ics import to_ics
from life_agent.trips import store

HOST = os.environ.get("LIFE_AGENT_TRIPS_WEB_HOST", "0.0.0.0")
# after GTD 8797 / bridge 8798 / daemon 8799
PORT = int(os.environ.get("LIFE_AGENT_TRIPS_WEB_PORT", "8800"))

Payload = dict[str, Any]
_INDEX = Path(__file__).parent / "index.html"


class WebError(Exception):
    """A request the server rejects with a 4xx. Carries the status; dispatch maps it to a JSON
    error so a bad request never crashes the accept loop."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


class Ical(str):
    """Marker str subclass so the handler sends text/calendar (not text/html) for the feed."""


@lru_cache(maxsize=1)
def _index_html() -> str:
    """The self-contained page, read once and cached (edit-then-restart, like any static asset)."""
    return _INDEX.read_text(encoding="utf-8")


def dispatch(method: str, path: str, body: bytes) -> tuple[int, Payload | str]:
    """Route one request to (status, payload). A str payload is HTML (the page) or iCal (the feed,
    an Ical instance); a dict is JSON. Holds no state; every 4xx is returned, never raised past
    here, so a bad request never crashes the loop. `body` is unused (read-only surface) but kept
    for parity with the GTD dispatch signature."""
    try:
        if method != "GET":
            raise WebError(405, f"method {method!r} not allowed")
        parts = urlsplit(path)
        route = parts.path
        if route == "/":
            return 200, _index_html()
        if route == "/ready":
            return 200, {"status": "ok"}
        if route == "/api/timeline":
            return 200, {"reservations": store.timeline()}
        if route == "/api/now_next":
            return 200, store.now_next(datetime.now().isoformat())
        if route == "/api/search":
            q = parse_qs(parts.query).get("q", [""])[0]
            return 200, {"reservations": store.search(q) if q else []}
        if route == "/calendar.ics":
            return 200, Ical(to_ics(store.timeline()))
        raise WebError(404, f"no GET endpoint {route!r}")
    except WebError as e:
        return e.status, {"error": e.message}


class _Handler(BaseHTTPRequestHandler):
    # protocol_version left at the HTTP/1.0 default on purpose (see reach/web/server.py docstring).

    def _respond(self, status: int, payload: Payload | str) -> None:
        if isinstance(payload, Ical):
            data, ctype = payload.encode("utf-8"), "text/calendar; charset=utf-8"
        elif isinstance(payload, str):
            data, ctype = payload.encode("utf-8"), "text/html; charset=utf-8"
        else:
            data, ctype = dumps(payload).encode("utf-8"), "application/json"
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        try:
            status, payload = dispatch("GET", self.path, b"")
        except Exception:
            # A seam failure (locked/corrupt DB, disk full) is logged to the journal and returned
            # as a GENERIC 500 — the raw exception (which may embed the KB path or SQL) is never
            # leaked to the client, which is unauthenticated on the tailnet.
            traceback.print_exc()
            status, payload = 500, {"error": "internal error"}
        self._respond(status, payload)

    def do_POST(self) -> None:
        self._respond(405, {"error": "method 'POST' not allowed"})  # read-only surface

    def log_message(self, format: str, *args: Any) -> None:
        return  # quiet: a personal backend, not an access log


class WebServer(HTTPServer):
    """Single-threaded by design (see reach/web/server.py): connection-per-request over HTTP/1.0,
    so a polling browser never stalls the accept loop."""

    def __init__(self, host: str = HOST, port: int = PORT) -> None:
        super().__init__((host, port), _Handler)


def main() -> None:
    store.init_db()  # idempotent; the read-model normally already exists (the trips CLI created it)
    server = WebServer()
    print(f"life-agent trips timeline → http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
