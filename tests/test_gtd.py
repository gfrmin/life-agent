"""Tests for the event-sourced GTD (`life_agent.tasks.commands` + `store`).

Ports the former `jarvis/db.py` behavioral contract — every reply string and query
preserved — onto the event-sourced implementation, then adds the properties event-sourcing
buys: a rebuild from the ledger reproduces the incrementally-applied projection, `apply` is
idempotent, and identity is origin-aware (human = unique, email = content-addressed dedup).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from life_agent.tasks import commands, store
from life_agent.tasks import events as ev

USER = 12345


@pytest.fixture(autouse=True)
def temp_gtd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "tasks.db")
    monkeypatch.setattr(commands, "LEDGER_PATH", tmp_path / "events.jsonl")
    store.init_db()


def _rows() -> list[tuple]:
    with store.get_db() as conn:
        return [
            tuple(r)
            for r in conn.execute(
                "SELECT id, identity, user_id, text, list, due_date, is_today, "
                "origin, created_at, completed_at FROM tasks ORDER BY id"
            ).fetchall()
        ]


# --- ported behavioral contract (jarvis/db.py parity) -------------------------


class TestAdd:
    def test_add_to_inbox(self) -> None:
        r = commands.add(USER, "Buy milk")
        assert "Added" in r and "Buy milk" in r and "#inbox" in r

    def test_add_with_due_date(self) -> None:
        r = commands.add(USER, "Call dentist", "scheduled", "2026-05-01")
        assert "#scheduled" in r and "2026-05-01" in r

    def test_add_invalid_list(self) -> None:
        assert "Invalid list" in commands.add(USER, "x", "badlist")

    def test_add_invalid_date(self) -> None:
        assert "Invalid date" in commands.add(USER, "x", "scheduled", "not-a-date")

    def test_add_preserves_tags(self) -> None:
        assert "@errands" in commands.add(USER, "Buy milk @errands")


class TestComplete:
    def test_complete_by_id(self) -> None:
        commands.add(USER, "Task one")
        r = commands.complete(USER, task_id=1)
        assert "Completed" in r and "Task one" in r

    def test_complete_by_text(self) -> None:
        commands.add(USER, "Buy groceries")
        assert "Completed" in commands.complete(USER, text_match="groceries")

    def test_complete_not_found(self) -> None:
        assert "not found" in commands.complete(USER, task_id=999)

    def test_complete_no_args(self) -> None:
        assert "Specify" in commands.complete(USER)

    def test_complete_id_zero(self) -> None:
        assert "not found" in commands.complete(USER, task_id=0)


class TestDelete:
    def test_delete(self) -> None:
        commands.add(USER, "To delete")
        assert "Deleted" in commands.delete(USER, 1)

    def test_delete_not_found(self) -> None:
        assert "not found" in commands.delete(USER, 999)


class TestMove:
    def test_move_to_next(self) -> None:
        commands.add(USER, "A task")
        assert "#next" in commands.move(USER, 1, "next")

    def test_move_with_date(self) -> None:
        commands.add(USER, "Schedule me")
        r = commands.move(USER, 1, "scheduled", "2026-06-01")
        assert "#scheduled" in r and "2026-06-01" in r

    def test_move_invalid_list(self) -> None:
        commands.add(USER, "A task")
        assert "Invalid list" in commands.move(USER, 1, "bad")

    def test_move_not_found(self) -> None:
        assert "not found" in commands.move(USER, 999, "next")


class TestToday:
    def test_mark_today(self) -> None:
        commands.add(USER, "Focus task")
        assert "Marked for today" in commands.mark_today(USER, 1)

    def test_get_today(self) -> None:
        commands.add(USER, "Task A")
        commands.mark_today(USER, 1)
        r = store.get_today_tasks(USER)
        assert "Task A" in r and "★" in r

    def test_clear_today(self) -> None:
        commands.add(USER, "Task A")
        commands.mark_today(USER, 1)
        assert "Cleared" in commands.clear_today(USER)
        assert "No tasks" in store.get_today_tasks(USER)


class TestReads:
    def test_all(self) -> None:
        commands.add(USER, "A")
        commands.add(USER, "B", "next")
        r = store.get_tasks(USER)
        assert "A" in r and "B" in r

    def test_filtered(self) -> None:
        commands.add(USER, "Inbox item")
        commands.add(USER, "Next item", "next")
        r = store.get_tasks(USER, "inbox")
        assert "Inbox item" in r and "Next item" not in r

    def test_empty(self) -> None:
        assert "No tasks" in store.get_tasks(USER)

    def test_by_tag(self) -> None:
        commands.add(USER, "Task @work")
        commands.add(USER, "Task @home")
        r = store.get_tasks_by_tag(USER, "work")
        assert "@work" in r and "@home" not in r

    def test_counts(self) -> None:
        commands.add(USER, "A")
        commands.add(USER, "B", "next")
        r = store.get_task_counts(USER)
        assert "#inbox: 1" in r and "#next: 1" in r

    def test_completed_week(self) -> None:
        commands.add(USER, "Done task")
        commands.complete(USER, task_id=1)
        assert "Done task" in store.get_completed_this_week(USER)


class TestMultiUser:
    def test_isolation(self) -> None:
        commands.add(111, "User A task")
        commands.add(222, "User B task")
        a, b = store.get_tasks(111), store.get_tasks(222)
        assert "User A task" in a and "User B task" not in a
        assert "User B task" in b and "User A task" not in b


# --- event-sourcing properties ------------------------------------------------


def test_rebuild_equals_incremental() -> None:
    # Drive a mix of all event types, snapshot the projection, then rebuild it purely
    # from the ledger — the read-model is a deterministic function of the events.
    commands.add(USER, "A")
    commands.add(USER, "B", "next", "2026-06-01")
    commands.mark_today(USER, 1)
    commands.complete(USER, task_id=2)
    commands.add(USER, "C")
    commands.delete(USER, 3)
    before = _rows()

    events = ev.load(commands.LEDGER_PATH)
    with store.get_db() as conn:
        store.rebuild(conn, events)
    assert _rows() == before


def test_apply_is_idempotent() -> None:
    e = ev.asserted("idX", {"user_id": USER, "text": "T", "list": "inbox"})
    with store.get_db() as conn:
        store.apply(conn, e)
        store.apply(conn, e)
        n = conn.execute("SELECT count(*) FROM tasks WHERE identity = 'idX'").fetchone()[0]
    assert n == 1


def test_complete_emits_disposed_done() -> None:
    commands.add(USER, "T")
    commands.complete(USER, task_id=1)
    events = ev.load(commands.LEDGER_PATH)
    assert [e.type for e in events] == ["asserted", "disposed"]
    assert events[1].reason == "done"


def test_human_typing_same_task_twice_makes_two() -> None:
    commands.add(USER, "Call mum")
    commands.add(USER, "Call mum")
    with store.get_db() as conn:
        n = conn.execute("SELECT count(*) FROM tasks WHERE text = 'Call mum'").fetchone()[0]
    assert n == 2  # unique human identity each time


def test_email_same_identity_dedups() -> None:
    ident = ev.assertion_identity("task", "the quote", "Pay invoice")
    commands.add(USER, "Pay invoice", identity=ident, origin="email")
    commands.add(USER, "Pay invoice", identity=ident, origin="email")
    with store.get_db() as conn:
        n = conn.execute("SELECT count(*) FROM tasks WHERE identity = ?", (ident,)).fetchone()[0]
    assert n == 1  # content identity dedups the re-derivation
