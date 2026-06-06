"""Tests for the Telegram reach (`life_agent.reach`).

Hermetic: the GTD dispatch runs against a temp event-sourced store; the Ollama NLU and the
Telegram transport are exercised with a fake ``urlopen`` (no network, no model). Confirms the
loop's logic — intent → command/projection → reply — without any live I/O.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from life_agent.reach import digest as reach_digest
from life_agent.reach import jarvis, telegram
from life_agent.tasks import commands, store

USER = 12345


@pytest.fixture(autouse=True)
def temp_gtd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "tasks.db")
    monkeypatch.setattr(commands, "LEDGER_PATH", tmp_path / "events.jsonl")
    store.init_db()


class _FakeResp:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> _FakeResp:
        return self

    def __exit__(self, *_: object) -> bool:
        return False


# --- handle_action dispatch (intent → event-sourced GTD) ----------------------


def test_handle_add_files_a_task() -> None:
    reply = jarvis.handle_action({"action": "add", "text": "Buy milk"}, USER)
    assert "Added" in reply
    assert "Buy milk" in store.get_tasks(USER)


def test_handle_add_empty_text() -> None:
    assert "didn't catch" in jarvis.handle_action({"action": "add", "text": "  "}, USER)


def test_handle_list_filters() -> None:
    commands.add(USER, "Inbox item")
    assert "Inbox item" in jarvis.handle_action({"action": "list", "list": "inbox"}, USER)


def test_handle_complete() -> None:
    commands.add(USER, "Finish me")
    assert "Completed" in jarvis.handle_action({"action": "complete", "task_id": 1}, USER)


def test_handle_delete_without_id() -> None:
    assert "task number" in jarvis.handle_action({"action": "delete"}, USER)


def test_handle_counts() -> None:
    commands.add(USER, "A")
    assert "#inbox: 1" in jarvis.handle_action({"action": "counts"}, USER)


def test_handle_chat_and_help_and_unknown() -> None:
    assert "hi there" in jarvis.handle_action({"action": "chat", "response": "hi there"}, USER)
    assert "Jarvis" in jarvis.handle_action({"action": "help"}, USER)
    assert "not sure" in jarvis.handle_action({"action": "frobnicate"}, USER)


# --- NLU (mocked Ollama) ------------------------------------------------------


def test_parse_with_ollama(monkeypatch: pytest.MonkeyPatch) -> None:
    inner = json.dumps({"action": "add", "text": "Buy milk"})
    payload = json.dumps({"message": {"content": inner}}).encode()
    monkeypatch.setattr(jarvis, "urlopen", lambda *a, **k: _FakeResp(payload))
    assert jarvis.parse_with_ollama("buy milk") == {"action": "add", "text": "Buy milk"}


# --- transport (mocked HTTP) --------------------------------------------------


def test_telegram_request_builds_url_and_returns_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(telegram, "secret", lambda _name: "TOK")
    captured: dict[str, str] = {}

    def fake_urlopen(req: object, timeout: int = 0) -> _FakeResp:
        captured["url"] = req.full_url  # type: ignore[attr-defined]
        return _FakeResp(json.dumps({"ok": True, "result": [1, 2]}).encode())

    monkeypatch.setattr(telegram, "urlopen", fake_urlopen)
    assert telegram.telegram_request("getUpdates", {"offset": 0}) == [1, 2]
    assert "getUpdates" in captured["url"] and "TOK" in captured["url"]


# --- digest (over the projection) ---------------------------------------------


def test_digest_summarises_today_and_inbox() -> None:
    commands.add(USER, "Inbox thing")
    commands.add(USER, "Focus thing")
    commands.mark_today(USER, 2)
    d = reach_digest.build_digest(USER)
    assert d is not None
    assert "Focus thing" in d
    assert "inbox" in d.lower()


def test_digest_is_none_when_empty() -> None:
    assert reach_digest.build_digest(USER) is None
