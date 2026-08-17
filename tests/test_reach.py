"""Tests for the Telegram reach (`life_agent.reach`).

Hermetic: the GTD dispatch runs against a temp event-sourced store; the NLU model call and the
Telegram transport are exercised with a fake ``urlopen`` (no network, no model). Confirms the
loop's logic — intent → command/projection → reply — without any live I/O.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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


def test_handle_list_with_tag_routes_to_tag_view() -> None:
    commands.add(USER, "Email accountant @work")
    commands.add(USER, "Water plants")
    reply = jarvis.handle_action({"action": "list", "tag": "work"}, USER)
    assert "Email accountant" in reply
    assert "Water plants" not in reply


# --- the question intent (interaction-contract: asking about your life is *know*) --------
# Jarvis routes a life/document question to the executor read-path (core/ask_client), replies
# with the cited credence-grammar answer, and binds the owner's ONE-BIT verdict to the logged
# decision (reaction-loop economics: g/b, never prose). The transport stays dumb — it carries
# the question and the bit; the decision and the fold live behind the bridge.


def test_handle_question_routes_to_the_know_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    from life_agent.core import ask_client

    monkeypatch.setattr(ask_client, "answer",
                        lambda q, **k: (f"ANSWER to {q}", "ab-cafe"))
    jarvis.LAST_DECISION_ID = None
    reply = jarvis.handle_action(
        {"action": "question", "question": "what is my Israeli tax ID?"}, USER)
    assert "ANSWER to what is my Israeli tax ID?" in reply
    assert "g" in reply and "b" in reply            # the one-bit verdict is invited
    assert jarvis.LAST_DECISION_ID == "ab-cafe"     # the id the next g/b binds to


def test_handle_question_without_decision_invites_no_verdict(
        monkeypatch: pytest.MonkeyPatch) -> None:
    from life_agent.core import ask_client

    monkeypatch.setattr(ask_client, "answer", lambda q, **k: ("No answer asserted — …", None))
    jarvis.LAST_DECISION_ID = "stale"
    reply = jarvis.handle_action({"action": "question", "question": "q?"}, USER)
    assert "grade" not in reply.lower()
    assert jarvis.LAST_DECISION_ID is None          # a stale binding never survives


def test_handle_question_empty_asks_back() -> None:
    assert "know" in jarvis.handle_action({"action": "question", "question": "  "}, USER)


def test_verdict_valence_maps_the_one_bit() -> None:
    assert jarvis.verdict_valence("g") == "good"
    assert jarvis.verdict_valence("GOOD") == "good"
    assert jarvis.verdict_valence("b") == "bad"
    assert jarvis.verdict_valence("bad") == "bad"
    assert jarvis.verdict_valence("done 3") is None
    assert jarvis.verdict_valence("great job") is None


# --- INTENTS: one table feeds prompt and help; drift gates enforce it ----------
# (docs/interaction-contract.md invariant 4: a vocabulary nothing enforces will
# quietly diverge — these tests are what make the table the single source.)


def test_every_intent_dispatches() -> None:
    # An action named in INTENTS that handle_action doesn't route hits the
    # unknown-fallback and fails here (no params: each handler asks or no-ops).
    for action, _schema, _help in jarvis.INTENTS:
        reply = jarvis.handle_action({"action": action}, USER)
        assert "not sure" not in reply, action


def test_prompt_renders_every_intent_schema() -> None:
    for action, schema, _help in jarvis.INTENTS:
        assert f'"action": "{action}"' in jarvis.SYSTEM_PROMPT, action
        assert schema in jarvis.SYSTEM_PROMPT, action


def test_help_renders_every_intent_example() -> None:
    help_text = jarvis.handle_action({"action": "help"}, USER)
    for action, _schema, help_line in jarvis.INTENTS:
        assert help_line in help_text, action


def test_prompt_mentions_the_tag_rule() -> None:
    # The list intent's tag form must be exemplified in Rules, or a small local
    # model never emits it (the path itself is wired in handle_action).
    assert "@work" in jarvis.SYSTEM_PROMPT


def test_prompt_teaches_the_unmark_form_help_promises() -> None:
    # Help advertises "untoday 3" — the Rules must teach the model that form,
    # or help promises a capability the NLU never emits (invariant 4's spirit,
    # between the help table and the hand-written Rules prose).
    assert "untoday" in jarvis.SYSTEM_PROMPT
    assert "is_today false" in jarvis.SYSTEM_PROMPT


def test_prompt_today_substitution_survives_literal_braces() -> None:
    # Schema lines contain literal {} — {today} is substituted by .replace, and
    # the rendered prompt must carry the date and no leftover placeholder.
    rendered = jarvis.render_prompt("2026-06-11")
    assert "2026-06-11" in rendered
    assert "{today}" not in rendered
    assert '{"action": "add"' in rendered  # literal braces intact


# --- NLU (mocked model call) --------------------------------------------------


def test_parse_intent(monkeypatch: pytest.MonkeyPatch) -> None:
    import life_agent.core.llm as llm

    seen: dict[str, Any] = {}

    def fake_complete(system: str, user: str, **kw: Any) -> Any:
        seen["system"], seen["user"], seen["model"] = system, user, kw.get("model")
        return type("R", (), {"text": json.dumps({"action": "add", "text": "Buy milk"})})()

    monkeypatch.setattr(llm, "anthropic_complete", fake_complete)
    assert jarvis.parse_intent("buy milk") == {"action": "add", "text": "Buy milk"}
    assert seen["user"] == "buy milk" and seen["model"] == jarvis.NLU_MODEL
    assert "add" in seen["system"]  # the INTENTS vocabulary rides the system prompt


def test_parse_intent_strips_code_fences(monkeypatch: pytest.MonkeyPatch) -> None:
    import life_agent.core.llm as llm

    fenced = "```json\n" + json.dumps({"action": "counts"}) + "\n```"
    monkeypatch.setattr(llm, "anthropic_complete",
                        lambda *a, **k: type("R", (), {"text": fenced})())
    assert jarvis.parse_intent("stats") == {"action": "counts"}


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
