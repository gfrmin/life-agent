"""GTD webapp — a direct-manipulation reach channel over the event-sourced GTD store.

NLU (the CLI ask path, the Telegram bot) is sometimes the wrong tool for what is really direct
manipulation — "complete this", "move that to next", "mark today", "set a due date". This is a
button surface for exactly that: a tiny stdlib ``http.server`` that serves one self-contained
page and a small JSON API. It is a **reach channel** (same category as ``reach.telegram`` — a
dumb transport, no truth of its own), which is why it lives under ``reach/`` rather than beside
the answer-brain ``bridge`` (that one serves the *body*, not the owner).

Every write goes through the existing command seam (``tasks.commands``) so it lands in the
append-only ledger exactly like a Telegram command; reads go through ``tasks.store.get_board``.
The webapp never touches SQLite or the ledger directly. After each mutation it returns the freshly
re-read board, so the page re-renders from one authoritative source with no client-side state to
sync.

**Single-threaded, HTTP/1.0** (the ``BaseHTTPRequestHandler`` default — we deliberately do NOT
override ``protocol_version`` to 1.1): connection-per-request means a polling browser never holds
a keep-alive connection open and stalls the single accept loop. Requests are millisecond SQLite
reads/writes; serialising them is imperceptible for a personal single-user app, and it sidesteps
intra-process write races entirely. Cross-process concurrency with ``jarvis.service`` /
``mail-to-tasks`` is the pre-existing, safe case (the ledger is truth; folds are idempotent under
WAL).

**No auth.** ``LIFE_AGENT_WEB_HOST`` defaults to ``0.0.0.0`` (owner runs it on a firewalled host,
reachable from the phone/laptop over Tailscale). The network boundary is the only gate — same
posture as the bridge. Do not expose this publicly without adding authentication. The owner id is
never hard-coded: it is resolved at boot from ``JARVIS_USER_ID`` (env / gnome-keyring), like
jarvis.
"""
from __future__ import annotations

import os
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, HTTPServer
from json import JSONDecodeError, dumps, loads
from pathlib import Path
from typing import Any, cast

from life_agent.core import secret
from life_agent.tasks import commands, store

HOST = os.environ.get("LIFE_AGENT_WEB_HOST", "0.0.0.0")
PORT = int(os.environ.get("LIFE_AGENT_WEB_PORT", "8797"))  # adjacent to bridge 8798 / daemon 8799

Payload = dict[str, Any]
_INDEX = Path(__file__).parent / "index.html"


class WebError(Exception):
    """A request the webapp rejects with a 4xx — malformed body, missing field, bad task id,
    unknown route. Carries the status; ``dispatch`` maps it to a JSON error (a bad request never
    crashes the loop)."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


# --- request helpers -------------------------------------------------------------------

def _parse_body(body: bytes) -> Payload:
    """Parse a JSON object body; an empty body is an empty object (some POSTs carry no fields)."""
    if not body:
        return {}
    try:
        payload = loads(body)
    except (JSONDecodeError, UnicodeDecodeError) as e:
        raise WebError(400, f"malformed JSON body: {e}") from e
    if not isinstance(payload, dict):
        raise WebError(400, "request body must be a JSON object")
    return payload


def _req_str(p: Payload, key: str) -> str:
    v = p.get(key)
    if not isinstance(v, str) or not v:
        raise WebError(400, f"field {key!r} must be a non-empty string")
    return v


def _task_id(seg: str) -> int:
    try:
        return int(seg)
    except ValueError as e:
        raise WebError(400, f"invalid task id {seg!r}") from e


@lru_cache(maxsize=1)
def _index_html() -> str:
    """The self-contained page, read once and cached (edit-then-restart, like any static asset)."""
    return _INDEX.read_text(encoding="utf-8")


# --- command results -------------------------------------------------------------------

# ``commands.*`` return a human string. Map its shape to a status: a missing task is 404, a
# validation failure (bad list / bad date) is 400, anything else is a successful mutation whose
# response carries the freshly re-read board so the page re-renders from one source of truth.
def _apply(user_id: int, reply: str) -> tuple[int, Payload]:
    if reply.startswith("Task not found"):
        return 404, {"error": reply}
    if reply.startswith("Invalid"):
        return 400, {"error": reply}
    return 200, {"reply": reply, "board": store.get_board(user_id)}


def _add(user_id: int, p: Payload) -> tuple[int, Payload]:
    text = _req_str(p, "text")
    list_name = p.get("list") or "inbox"
    return _apply(user_id, commands.add(
        user_id, text, str(list_name), p.get("due_date"), bool(p.get("is_today", False))))


def _task_action(user_id: int, tid: int, verb: str, p: Payload) -> tuple[int, Payload]:
    if verb == "complete":
        return _apply(user_id, commands.complete(user_id, task_id=tid))
    if verb == "delete":
        return _apply(user_id, commands.delete(user_id, tid))
    if verb == "today":
        return _apply(user_id, commands.mark_today(user_id, tid, bool(p.get("is_today", True))))
    if verb in ("move", "due"):
        # `due` reuses `move`: it amends {list, due_date} together, so the client sends the task's
        # current list plus the new (or null → cleared) date. One command, no new event type.
        return _apply(user_id, commands.move(user_id, tid, _req_str(p, "list"), p.get("due_date")))
    raise WebError(404, f"no action {verb!r} on a task")


# --- routing ---------------------------------------------------------------------------

def dispatch(user_id: int, method: str, path: str,
             body: bytes) -> tuple[int, Payload | str]:
    """Route one request to ``(status, payload)``. A ``str`` payload is HTML (the page); a dict is
    JSON. Holds no state; every 4xx is returned (never raised past here) so a bad request never
    crashes the loop."""
    try:
        if method == "GET":
            if path == "/":
                return 200, _index_html()
            if path == "/ready":
                return 200, {"status": "ok"}
            if path == "/api/board":
                return 200, store.get_board(user_id)
            raise WebError(404, f"no GET endpoint {path!r}")
        if method == "POST":
            p = _parse_body(body)
            if path == "/api/tasks":
                return _add(user_id, p)
            if path == "/api/today/clear":
                return _apply(user_id, commands.clear_today(user_id))
            segs = path.strip("/").split("/")
            if len(segs) == 4 and segs[0] == "api" and segs[1] == "tasks":
                return _task_action(user_id, _task_id(segs[2]), segs[3], p)
            raise WebError(404, f"no POST endpoint {path!r}")
        raise WebError(405, f"method {method!r} not allowed")
    except WebError as e:
        return e.status, {"error": e.message}


# --- the HTTP service ------------------------------------------------------------------

class _Handler(BaseHTTPRequestHandler):
    # protocol_version left at the HTTP/1.0 default on purpose (see module docstring).

    def _respond(self, status: int, payload: Payload | str) -> None:
        if isinstance(payload, str):
            data = payload.encode("utf-8")
            ctype = "text/html; charset=utf-8"
        else:
            data = dumps(payload).encode("utf-8")
            ctype = "application/json"
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _handle(self, method: str) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        user_id = cast("WebServer", self.server).user_id
        try:
            status, payload = dispatch(user_id, method, self.path, body)
        except Exception as e:
            # A seam failure is RETURNED as 500 with its message — never swallowed, never crashes
            # the long-lived loop.
            status, payload = 500, {"error": f"{type(e).__name__}: {e}"}
        self._respond(status, payload)

    def do_GET(self) -> None:
        self._handle("GET")

    def do_POST(self) -> None:
        self._handle("POST")

    def log_message(self, format: str, *args: Any) -> None:
        return  # quiet: a personal backend, not an access log


class WebServer(HTTPServer):
    """Single-threaded by design (see module docstring): connection-per-request over HTTP/1.0, so
    a polling browser never stalls the accept loop and intra-process writes never race."""

    def __init__(self, user_id: int, host: str = HOST, port: int = PORT) -> None:
        super().__init__((host, port), _Handler)
        self.user_id = user_id


def build_user_id() -> int:
    """The owner's id, resolved at boot from ``JARVIS_USER_ID`` (env / gnome-keyring) — never
    hard-coded (this is a public repo; the id is PII)."""
    return int(secret("JARVIS_USER_ID"))


def main() -> None:
    store.init_db()  # idempotent; the read-model normally already exists (jarvis created it)
    server = WebServer(build_user_id())
    print(f"life-agent GTD webapp → http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
