"""Hermetic contract tests for the GTD webapp (``life_agent.reach.web.server``).

The webapp is a direct-manipulation reach channel over the event-sourced GTD store: it serves one
page and a small JSON API that routes writes through ``tasks.commands`` and reads through
``tasks.store.get_board``. These pin its contract WITHOUT a model, a live corpus, or the keyring —
the GTD ledger + read-model are redirected to ``tmp_path`` (the exact ``temp_gtd`` fixture the
other GTD tests use) and ``dispatch``/``get_board`` are exercised directly, plus one real loopback
smoke test for the transport.
"""
from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from life_agent.reach.web.server import WebServer, dispatch
from life_agent.tasks import commands, store

UID = 42


@pytest.fixture(autouse=True)
def temp_gtd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "tasks.db")
    monkeypatch.setattr(commands, "LEDGER_PATH", tmp_path / "events.jsonl")
    store.init_db()


def _call(method: str, path: str, body: dict[str, Any] | None = None) -> tuple[int, Any]:
    raw = json.dumps(body).encode("utf-8") if body is not None else b""
    return dispatch(UID, method, path, raw)


def _add(text: str, list_name: str = "inbox", **kw: Any) -> int:
    """Seed a task via the API and return its read-model id (parsed from the board)."""
    status, payload = _call("POST", "/api/tasks", {"text": text, "list": list_name, **kw})
    assert status == 200, payload
    tasks = [t for col in payload["board"]["lists"].values() for t in col if t["text"] == text]
    assert tasks, f"just-added task {text!r} not on the board"
    return int(tasks[-1]["id"])


# --- store.get_board (the raw read the API serves) -------------------------------------

def test_get_board_buckets_lists_today_and_counts() -> None:
    commands.add(UID, "a", "inbox")
    commands.add(UID, "b", "next")
    tid = commands.add(UID, "c", "next")  # returns a reply string, not an id
    del tid
    board = store.get_board(UID)
    assert set(board["lists"]) == {"inbox", "next", "scheduled", "someday"}  # all keys seeded
    assert [t["text"] for t in board["lists"]["inbox"]] == ["a"]
    assert {t["text"] for t in board["lists"]["next"]} == {"b", "c"}
    assert board["lists"]["scheduled"] == [] and board["lists"]["someday"] == []
    assert board["counts"] == {"inbox": 1, "next": 2, "scheduled": 0, "someday": 0, "today": 0}


def test_get_board_is_today_is_bool_and_populates_today() -> None:
    tid = _add("focus")
    _call("POST", f"/api/tasks/{tid}/today", {"is_today": True})
    board = store.get_board(UID)
    task = board["lists"]["inbox"][0]
    assert task["is_today"] is True                       # coerced from stored INT to JSON bool
    assert [t["text"] for t in board["today"]] == ["focus"]
    assert board["counts"]["today"] == 1


def test_get_board_preserves_unknown_list_bucket() -> None:
    # A row whose list is outside VALID_LISTS (a legacy/migrated value) must not be dropped —
    # get_board keeps it under its own key so the UI can still surface it.
    from life_agent.tasks import events as ev
    with store.get_db() as conn:
        store.apply(conn, ev.asserted(ev.new_identity(), payload={
            "user_id": UID, "text": "legacy", "list": "archive", "due_date": None,
            "is_today": 0, "origin": "human"}))
    board = store.get_board(UID)
    assert [t["text"] for t in board["lists"]["archive"]] == ["legacy"]
    assert board["counts"]["archive"] == 1


def test_get_board_excludes_completed() -> None:
    tid = _add("gone")
    _call("POST", f"/api/tasks/{tid}/complete")
    board = store.get_board(UID)
    assert board["lists"]["inbox"] == []
    assert board["counts"]["inbox"] == 0


# --- GET routes ------------------------------------------------------------------------

def test_index_is_html() -> None:
    status, payload = _call("GET", "/")
    assert status == 200
    assert isinstance(payload, str)
    assert "<!DOCTYPE html>" in payload and "GTD" in payload


def test_ready() -> None:
    assert _call("GET", "/ready") == (200, {"status": "ok"})


def test_board_endpoint_matches_get_board() -> None:
    _add("x")
    status, payload = _call("GET", "/api/board")
    assert status == 200
    assert payload == store.get_board(UID)


# --- mutations: each returns the freshly re-read board ---------------------------------

def test_add_returns_reply_and_board() -> None:
    status, payload = _call("POST", "/api/tasks", {"text": "buy milk", "list": "next"})
    assert status == 200
    assert payload["reply"].startswith("Added")
    assert [t["text"] for t in payload["board"]["lists"]["next"]] == ["buy milk"]


def test_add_requires_text() -> None:
    status, _ = _call("POST", "/api/tasks", {"list": "inbox"})
    assert status == 400


def test_add_invalid_list_is_400() -> None:
    status, payload = _call("POST", "/api/tasks", {"text": "t", "list": "bogus"})
    assert status == 400
    assert "error" in payload


def test_add_invalid_date_is_400() -> None:
    status, _ = _call("POST", "/api/tasks", {"text": "t", "due_date": "not-a-date"})
    assert status == 400


def test_complete_removes_from_board() -> None:
    tid = _add("done me")
    status, payload = _call("POST", f"/api/tasks/{tid}/complete")
    assert status == 200
    assert payload["board"]["lists"]["inbox"] == []


def test_delete_removes_from_board() -> None:
    tid = _add("del me")
    status, payload = _call("POST", f"/api/tasks/{tid}/delete")
    assert status == 200
    assert payload["board"]["counts"]["inbox"] == 0


def test_move_changes_list() -> None:
    tid = _add("mover")
    status, payload = _call("POST", f"/api/tasks/{tid}/move", {"list": "someday"})
    assert status == 200
    assert payload["board"]["lists"]["inbox"] == []
    assert [t["text"] for t in payload["board"]["lists"]["someday"]] == ["mover"]


def test_move_invalid_list_is_400() -> None:
    tid = _add("mover")
    status, _ = _call("POST", f"/api/tasks/{tid}/move", {"list": "nope"})
    assert status == 400


def test_today_toggle() -> None:
    tid = _add("star me")
    _, on = _call("POST", f"/api/tasks/{tid}/today", {"is_today": True})
    assert on["board"]["counts"]["today"] == 1
    _, off = _call("POST", f"/api/tasks/{tid}/today", {"is_today": False})
    assert off["board"]["counts"]["today"] == 0


def test_due_sets_and_clears() -> None:
    tid = _add("with due", list_name="scheduled")
    _, set_ = _call("POST", f"/api/tasks/{tid}/due",
                    {"list": "scheduled", "due_date": "2026-08-01"})
    assert set_["board"]["lists"]["scheduled"][0]["due_date"] == "2026-08-01"
    _, cleared = _call("POST", f"/api/tasks/{tid}/due", {"list": "scheduled", "due_date": None})
    assert cleared["board"]["lists"]["scheduled"][0]["due_date"] is None


def test_today_clear_all() -> None:
    a, b = _add("a"), _add("b")
    _call("POST", f"/api/tasks/{a}/today", {"is_today": True})
    _call("POST", f"/api/tasks/{b}/today", {"is_today": True})
    status, payload = _call("POST", "/api/today/clear")
    assert status == 200
    assert payload["board"]["counts"]["today"] == 0


# --- errors ----------------------------------------------------------------------------

def test_unknown_task_is_404() -> None:
    status, payload = _call("POST", "/api/tasks/9999/complete")
    assert status == 404
    assert "error" in payload


def test_non_integer_task_id_is_400() -> None:
    status, _ = _call("POST", "/api/tasks/abc/complete")
    assert status == 400


def test_malformed_json_is_400() -> None:
    status, _ = dispatch(UID, "POST", "/api/tasks", b"{not json")
    assert status == 400


def test_unknown_get_is_404() -> None:
    status, _ = _call("GET", "/nope")
    assert status == 404


def test_unknown_post_is_404() -> None:
    status, _ = _call("POST", "/api/nope", {})
    assert status == 404


def test_unknown_task_action_is_404() -> None:
    tid = _add("t")
    status, _ = _call("POST", f"/api/tasks/{tid}/frobnicate")
    assert status == 404


def test_bad_method_is_405() -> None:
    status, payload = dispatch(UID, "DELETE", "/api/board", b"")
    assert status == 405
    assert "error" in payload


# --- transport: real loopback HTTP -----------------------------------------------------

@pytest.fixture
def live(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "tasks.db")
    monkeypatch.setattr(commands, "LEDGER_PATH", tmp_path / "events.jsonl")
    store.init_db()
    server = WebServer(UID, host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()


def _http(base: str, method: str, path: str,
          body: dict[str, Any] | None = None) -> tuple[int, str, Any]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw = resp.read()
            ctype = resp.headers.get("Content-Type", "")
            parsed = json.loads(raw) if ctype.startswith("application/json") else raw.decode()
            return resp.status, ctype, parsed
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type", ""), json.loads(e.read() or b"null")


def test_http_index_served_as_html(live: str) -> None:
    status, ctype, body = _http(live, "GET", "/")
    assert status == 200
    assert ctype.startswith("text/html")
    assert "<!DOCTYPE html>" in body


def test_http_add_then_board_roundtrip(live: str) -> None:
    status, ctype, payload = _http(live, "POST", "/api/tasks", {"text": "over the wire"})
    assert status == 200
    assert ctype.startswith("application/json")
    assert payload["reply"].startswith("Added")
    _, _, board = _http(live, "GET", "/api/board")
    assert [t["text"] for t in board["lists"]["inbox"]] == ["over the wire"]


def test_http_malformed_body_is_400(live: str) -> None:
    req = urllib.request.Request(live + "/api/tasks", data=b"{bad", method="POST")
    try:
        urllib.request.urlopen(req, timeout=5)
        raise AssertionError("expected HTTP 400")
    except urllib.error.HTTPError as e:
        assert e.code == 400


def test_http_bad_content_length_does_not_crash(live: str) -> None:
    # A non-numeric Content-Length must not escape as a traceback (the "never crashes the loop"
    # contract): it reads as a 0-length body, dispatch returns a normal 4xx, the server stays up.
    import socket
    from urllib.parse import urlsplit

    u = urlsplit(live)
    sock = socket.create_connection((u.hostname, u.port), timeout=5)
    sock.sendall(b"POST /api/tasks HTTP/1.0\r\nHost: x\r\nContent-Length: abc\r\n\r\n")
    resp = sock.recv(4096).decode(errors="replace")
    sock.close()
    assert resp.startswith("HTTP/")  # a real HTTP response, not a dropped connection
    assert _http(live, "GET", "/ready")[0] == 200  # loop survived
