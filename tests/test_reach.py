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
    # jarvis answers through ask_client.answer: drive, then render
    from life_agent.core import ask_client, executor

    monkeypatch.setattr(ask_client, "drive",
                        lambda q, **k: ask_client.DriveResult({"q": q}, "ab-cafe"))
    monkeypatch.setattr(executor, "render_view",
                        lambda view: f"ANSWER to {view['q']}")
    jarvis.LAST_DECISION_ID = None
    reply = jarvis.handle_action(
        {"action": "question", "question": "what is my Israeli tax ID?"}, USER)
    assert "ANSWER to what is my Israeli tax ID?" in reply
    assert "g" in reply and "b" in reply            # the one-bit verdict is invited
    assert jarvis.LAST_DECISION_ID == "ab-cafe"     # the id the next g/b binds to


def test_handle_question_without_decision_invites_no_verdict(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # a down stack: drive returns the DOWN fact; jarvis replies the contract string
    from life_agent.core import ask_client

    monkeypatch.setattr(ask_client, "drive",
                        lambda q, **k: ask_client.DriveResult(None, None, down=True))
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
# (a vocabulary nothing enforces will quietly diverge — these tests are what make the
# table the single source.)


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


# --- daily briefing: contract sections, truncation naming, owner targeting ----------


def test_digest_renders_overdue_and_due_today(monkeypatch: pytest.MonkeyPatch) -> None:
    import datetime as _dt

    yesterday = (_dt.date.today() - _dt.timedelta(days=1)).isoformat()
    today = _dt.date.today().isoformat()
    commands.add(USER, "File the appeal", list_name="scheduled", due_date=yesterday)
    commands.add(USER, "Pay the deposit", list_name="scheduled", due_date=today)
    out = reach_digest.build_digest(USER)
    assert out is not None
    assert reach_digest.SECTIONS["overdue"] in out and "File the appeal" in out
    assert reach_digest.SECTIONS["due_today"] in out and "Pay the deposit" in out


def test_digest_names_the_up_next_truncation() -> None:
    # invariant 3 (interaction contract): nothing vanishes silently — the sixth and
    # seventh #next tasks are not shown, so the digest must SAY they exist
    for i in range(7):
        commands.add(USER, f"Next thing {i}", list_name="next")
    out = reach_digest.build_digest(USER)
    assert out is not None
    assert "Next thing 4" in out and "Next thing 5" not in out
    assert reach_digest.SECTIONS["next_more"].format(n=2) in out


def test_digest_shows_all_next_without_truncation_line() -> None:
    commands.add(USER, "Only next", list_name="next")
    out = reach_digest.build_digest(USER)
    assert out is not None and "more in #next" not in out


def test_digest_main_targets_the_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    # the owner convention (JARVIS_USER_ID env/keyring, else the store's sole user) —
    # not a 30-day distinct-user scan
    commands.add(USER, "A task", is_today=True)
    sent: list[tuple[int, str]] = []
    monkeypatch.setattr(reach_digest.telegram, "send_message",
                        lambda uid, text: sent.append((uid, text)))
    monkeypatch.setenv("JARVIS_USER_ID", str(USER))
    reach_digest.main()
    assert [uid for uid, _ in sent] == [USER]
    assert "A task" in sent[0][1]


def _write_scans_status(waiting: int, *, age_hours: float = 0) -> None:
    import datetime as _dt
    import os

    updated = _dt.datetime.now(_dt.UTC) - _dt.timedelta(hours=age_hours)
    Path(os.environ["SCANS_REVIEW_STATUS"]).write_text(json.dumps(
        {"waiting": waiting, "url": "https://review-box.example.test:8444",
         "updated": updated.isoformat()}))


def test_digest_names_scans_waiting_for_review() -> None:
    _write_scans_status(3)
    out = reach_digest.build_digest(USER)
    # scans alone are reason enough to send a digest, with nothing else to say
    assert out is not None and "3 waiting for review at https://review-box.example.test:8444" in out


def test_digest_is_silent_about_scans_when_none_stale_or_absent() -> None:
    assert reach_digest.build_digest(USER) is None  # no status file (conftest)
    _write_scans_status(0)
    assert reach_digest.build_digest(USER) is None
    _write_scans_status(5, age_hours=72)  # scans-review not running: say nothing stale
    assert reach_digest.build_digest(USER) is None


def test_digest_sections_drift_gate() -> None:
    # every push-mode section in the table renders in a fully-populated digest —
    # the contract's §push enumeration, enforced (its only conformance test)
    import datetime as _dt

    yesterday = (_dt.date.today() - _dt.timedelta(days=1)).isoformat()
    today = _dt.date.today().isoformat()
    commands.add(USER, "Focus", is_today=True)
    commands.add(USER, "Late", list_name="scheduled", due_date=yesterday)
    commands.add(USER, "Due", list_name="scheduled", due_date=today)
    for i in range(6):
        commands.add(USER, f"N{i}", list_name="next")
    commands.add(USER, "Inbox thing")
    _write_scans_status(2)
    out = reach_digest.build_digest(USER)
    assert out is not None
    for key, template in reach_digest.SECTIONS.items():
        head = template.split("{")[0].strip()
        assert head and head in out, key


# --- the jarvis heartbeat: env-gated, rate-limited, never fatal ------------------------
#
# "Active (running)" cannot distinguish a polling jarvis from a hung one (2026-08-30: a
# locked keyring hung the poller for 15+ minutes while systemd reported healthy). The
# heartbeat pings a dead-man check after each successful poll cycle; the monitor pages on
# silence. Absence of JARVIS_HEARTBEAT_URL disables it (the usual convention), and a
# monitoring outage must never take reach down with it.

class _BeatResp:
    def __enter__(self) -> _BeatResp:
        return self

    def __exit__(self, *a: object) -> bool:
        return False


def test_heartbeat_absent_env_is_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JARVIS_HEARTBEAT_URL", raising=False)
    monkeypatch.setattr(jarvis, "_last_beat", None)
    calls: list[str] = []
    monkeypatch.setattr(jarvis, "urlopen",
                        lambda url, timeout=0: calls.append(url) or _BeatResp())
    jarvis._heartbeat()
    assert calls == []


def test_heartbeat_pings_then_rate_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JARVIS_HEARTBEAT_URL", "http://monitor.invalid/ping/x")
    monkeypatch.setattr(jarvis, "_last_beat", None)
    calls: list[str] = []
    monkeypatch.setattr(jarvis, "urlopen",
                        lambda url, timeout=0: calls.append(url) or _BeatResp())
    jarvis._heartbeat()
    jarvis._heartbeat()  # immediately again: inside the min interval, no second ping
    assert calls == ["http://monitor.invalid/ping/x"]


def test_heartbeat_failure_never_raises_and_rate_limits_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JARVIS_HEARTBEAT_URL", "http://monitor.invalid/ping/x")
    monkeypatch.setattr(jarvis, "_last_beat", None)
    calls: list[str] = []

    def _boom(url: str, timeout: float = 0) -> _BeatResp:
        calls.append(url)
        raise OSError("monitor unreachable")

    monkeypatch.setattr(jarvis, "urlopen", _boom)
    jarvis._heartbeat()  # must not raise
    jarvis._heartbeat()  # attempt-rate-limited: no immediate retry spam
    assert calls == ["http://monitor.invalid/ping/x"]


def test_poll_loop_beats_after_each_successful_cycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Stop(BaseException):
        """Escapes poll_loop's retry net (deliberately BaseException, like SystemExit)."""

    batches = iter([[], []])

    def fake_poll(offset: int, timeout: int = 0) -> list[dict[str, Any]]:
        try:
            return next(batches)
        except StopIteration:
            raise _Stop from None

    monkeypatch.setattr(telegram, "poll_updates", fake_poll)
    monkeypatch.setattr(jarvis, "_user_id", lambda: 1)
    monkeypatch.setattr(store, "init_db", lambda: None)
    beats: list[int] = []
    monkeypatch.setattr(jarvis, "_heartbeat", lambda: beats.append(1))
    with pytest.raises(_Stop):
        jarvis.poll_loop()
    assert len(beats) == 2  # one beat per completed cycle, none for the aborted third


# --- a task by its number, by rule: no model between a tap and its record (#221) ----


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("done 12", {"action": "complete", "task_id": 12}),
        ("Done #12", {"action": "complete", "task_id": 12}),
        ("  DONE   3 ", {"action": "complete", "task_id": 3}),
        ("done#4", {"action": "complete", "task_id": 4}),
        ("later 7", {"action": "later", "task_id": 7}),
        ("Later #7", {"action": "later", "task_id": 7}),
    ],
)
def test_a_task_by_its_number_is_read_by_rule(text: str, expected: dict[str, Any]) -> None:
    assert jarvis.quick_command(text) == expected


@pytest.mark.parametrize(
    "text",
    ["done buy milk", "done 3 4", "done", "later", "later x", "undone 3", "done 3.", "3 done",
     "done -3", "later tomorrow", "done 3 please"],
)
def test_anything_else_is_left_to_the_model(text: str) -> None:
    assert jarvis.quick_command(text) is None


def test_later_takes_a_task_off_today_and_brings_it_back_tomorrow() -> None:
    import datetime as _dt

    commands.add(USER, "Ring the bank", is_today=True)
    today = _dt.date(2026, 11, 25)
    assert commands.later(USER, 1, today=today) == (
        "Later: [1] Ring the bank, back tomorrow (2026-11-26)"
    )
    with store.get_db() as conn:
        row = conn.execute("SELECT list, due_date, is_today FROM tasks WHERE id = 1").fetchone()
    assert (row["list"], row["due_date"], row["is_today"]) == ("scheduled", "2026-11-26", 0)
    assert commands.later(USER, 99) == "Task not found."
    # a task already done is not brought back by "later"
    commands.add(USER, "Already done")
    commands.complete(USER, 2)
    assert commands.later(USER, 2) == "Task not found."


def test_a_task_put_off_until_later_is_in_tomorrows_report_as_due(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import datetime as _dt

    commands.add(USER, "Ring the bank", is_today=True)
    commands.later(USER, 1)
    out = reach_digest.build_digest(USER)
    assert out is None or "Ring the bank" not in out  # not on today's report any more

    class _Tomorrow(_dt.date):
        @classmethod
        def today(cls) -> _dt.date:
            return _dt.date.today() + _dt.timedelta(days=1)

    monkeypatch.setattr(reach_digest, "date", _Tomorrow)
    out = reach_digest.build_digest(USER)
    assert out is not None
    assert reach_digest.SECTIONS["due_today"] in out and "[1] Ring the bank" in out


def test_handle_later() -> None:
    commands.add(USER, "Ring the bank")
    assert "back tomorrow" in jarvis.handle_action({"action": "later", "task_id": 1}, USER)
    assert "task number" in jarvis.handle_action({"action": "later"}, USER)


def _one_message(monkeypatch: pytest.MonkeyPatch, text: str) -> list[str]:
    """Run poll_loop over one message from the owner; return what jarvis replied."""

    class _Stop(BaseException):
        pass

    batches = iter([[{"update_id": 1, "message": {"from": {"id": USER}, "chat": {"id": 9},
                                                   "text": text}}]])

    def fake_poll(offset: int, timeout: int = 0) -> list[dict[str, Any]]:
        try:
            return next(batches)
        except StopIteration:
            raise _Stop from None

    replies: list[str] = []
    monkeypatch.setattr(telegram, "poll_updates", fake_poll)
    monkeypatch.setattr(telegram, "send_message", lambda chat, reply: replies.append(reply))
    monkeypatch.setattr(telegram, "send_chat_action", lambda *_: None)
    monkeypatch.setattr(jarvis, "_user_id", lambda: USER)
    monkeypatch.setattr(jarvis, "_heartbeat", lambda: None)
    with pytest.raises(_Stop):
        jarvis.poll_loop()
    return replies


def test_done_and_later_by_number_never_ask_the_model(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_model(_text: str) -> dict[str, Any]:
        raise AssertionError("the model was asked")

    monkeypatch.setattr(jarvis, "parse_intent", no_model)
    commands.add(USER, "Finish me")
    commands.add(USER, "Put me off")
    assert _one_message(monkeypatch, "done 1") == ["Completed: Finish me"]
    assert _one_message(monkeypatch, "later #2")[0].startswith("Later: [2] Put me off")
    assert store.resolve_by_id(store.get_db(), USER, 1, active_only=True) is None


def test_anything_else_still_goes_to_the_model(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    def model(text: str) -> dict[str, Any]:
        seen.append(text)
        return {"action": "add", "text": "Buy milk"}

    monkeypatch.setattr(jarvis, "parse_intent", model)
    assert _one_message(monkeypatch, "buy milk")[0].startswith("Added")
    assert seen == ["buy milk"]


# --- the morning report fails loudly (#221) ---------------------------------------


def test_a_morning_report_that_could_not_be_sent_fails_the_run_after_the_mirror(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    commands.add(USER, "A task", is_today=True)
    monkeypatch.setenv("JARVIS_USER_ID", str(USER))

    def down(_uid: int, _text: str) -> None:
        raise OSError("telegram unreachable")

    mirrored: list[str] = []
    monkeypatch.setattr(reach_digest.telegram, "send_message", down)
    monkeypatch.setattr(reach_digest.door, "mirror",
                        lambda text: mirrored.append(text) or "handed in")
    with pytest.raises(SystemExit) as stopped:
        reach_digest.main()
    assert stopped.value.code == 1
    assert len(mirrored) == 1 and "A task" in mirrored[0]  # the door still had its chance
    assert "Failed to send digest" in capsys.readouterr().err


def test_a_morning_report_that_went_ends_well(monkeypatch: pytest.MonkeyPatch) -> None:
    commands.add(USER, "A task", is_today=True)
    monkeypatch.setenv("JARVIS_USER_ID", str(USER))
    monkeypatch.setattr(reach_digest.telegram, "send_message", lambda *_: None)
    monkeypatch.setattr(reach_digest.door, "mirror", lambda text: "no door configured")
    reach_digest.main()  # returns: no SystemExit
