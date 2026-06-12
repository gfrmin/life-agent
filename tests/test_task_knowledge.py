"""Tests for ``life_agent.tasks.knowledge`` — the ledger→knowledge projection.

The mutable→knowledge mirror of ``tasks/project.py`` (system-design.md §5): a pure
fold of the GTD event ledger rendered as one markdown document, stamped with the
ledger head it folds, so ask-time staleness is a cheap comparison. Deterministic by
construction: no clock, no randomness — every date comes from an event.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from life_agent.tasks import events as ev
from life_agent.tasks import knowledge

# ---------------------------------------------------------------------------
# Fixture ledger: add → move → today-flag → complete → drop
# ---------------------------------------------------------------------------


def _fixture_events() -> list[ev.Event]:
    t = "2026-06-01T10:00:00"
    return [
        ev.asserted(
            "id-milk", {"user_id": 1, "text": "buy milk", "list": "inbox"}, tx_time=t
        ),
        ev.asserted(
            "id-dentist",
            {"user_id": 1, "text": "call dentist @health", "list": "next"},
            tx_time=t,
        ),
        ev.asserted(
            "id-visa",
            {"user_id": 1, "text": "renew visa", "list": "scheduled", "due_date": "2026-06-20"},
            tx_time=t,
        ),
        ev.amended("id-dentist", {"is_today": 1}, tx_time="2026-06-02T08:00:00"),
        ev.asserted(
            "id-report", {"user_id": 1, "text": "write report", "list": "next"}, tx_time=t
        ),
        ev.disposed("id-report", "done", tx_time="2026-06-08T17:30:00"),
        ev.asserted(
            "id-junk", {"user_id": 1, "text": "junk task", "list": "inbox"}, tx_time=t
        ),
        ev.disposed("id-junk", "dropped", tx_time="2026-06-09T09:00:00"),
    ]


# ---------------------------------------------------------------------------
# render()
# ---------------------------------------------------------------------------


def test_render_current_state_per_list() -> None:
    text = knowledge.render(_fixture_events(), ledger_sha="0" * 64)
    # Open tasks appear under their lists, with due dates and the today flag.
    assert "buy milk" in text
    assert "call dentist @health" in text
    assert "renew visa" in text
    assert "2026-06-20" in text
    assert "#inbox" in text and "#next" in text and "#scheduled" in text
    # The today flag survives the fold.
    assert "today" in text.lower()
    # "What's next?" is the question this document exists for: #next renders
    # before the (large, unspecific) #inbox so the head chunk answers it.
    assert text.index("### #next") < text.index("### #inbox")
    # Task ids are never bracketed — "[2]" reads as a citation marker to the
    # synthesis/citation-guard layer (dangling-citation false positives).
    assert "[2]" not in text and "task 2" in text


def test_render_history_section() -> None:
    text = knowledge.render(_fixture_events(), ledger_sha="0" * 64)
    # Completed and dropped tasks live in history with their event dates...
    assert "write report" in text
    assert "2026-06-08" in text
    assert "junk task" in text
    # ...and a completed task is not listed as an open task.
    current = text.split("## History")[0]
    assert "write report" not in current


def test_render_stamp_and_determinism() -> None:
    events = _fixture_events()
    sha = "ab" * 32
    one = knowledge.render(events, ledger_sha=sha)
    two = knowledge.render(events, ledger_sha=sha)
    assert one == two  # byte-identical: no clock, no randomness
    assert f"as of event {len(events)}" in one
    assert f"ledger sha256 {sha}" in one
    # The stamp carries BOTH freshness axes: the ledger content AND the
    # renderer version — a renderer change must invalidate the projection
    # exactly like a ledger change (the projection is f(events, renderer)).
    assert knowledge.parse_stamp(one) == (sha, knowledge.RENDER_VERSION)


def test_render_empty_ledger() -> None:
    text = knowledge.render([], ledger_sha="e" * 64)
    assert "as of event 0" in text
    assert knowledge.parse_stamp(text) == ("e" * 64, knowledge.RENDER_VERSION)


def test_parse_stamp_absent() -> None:
    assert knowledge.parse_stamp("# not a state doc\n") is None


# ---------------------------------------------------------------------------
# write_state()
# ---------------------------------------------------------------------------


def test_write_state_round_trip(tmp_path: Path) -> None:
    ledger = tmp_path / "events.jsonl"
    out = tmp_path / "state.md"
    ev.append(ledger, _fixture_events())
    expected_sha = hashlib.sha256(ledger.read_bytes()).hexdigest()

    sha = knowledge.write_state(ledger, out)
    assert sha == expected_sha
    text = out.read_text(encoding="utf-8")
    assert knowledge.parse_stamp(text) == (expected_sha, knowledge.RENDER_VERSION)
    assert "buy milk" in text

    # Idempotent: a second call rewrites nothing (same content, same stamp).
    before = out.stat().st_mtime_ns
    assert knowledge.write_state(ledger, out) == expected_sha
    assert out.stat().st_mtime_ns == before

    # A new event moves the head: content and stamp change.
    ev.append(
        ledger,
        [ev.asserted("id-new", {"user_id": 1, "text": "new task"}, tx_time="2026-06-10T12:00:00")],
    )
    sha2 = knowledge.write_state(ledger, out)
    assert sha2 != expected_sha
    assert "new task" in out.read_text(encoding="utf-8")


def test_write_state_missing_ledger(tmp_path: Path) -> None:
    """No ledger = an empty GTD — still a valid (empty) state document."""
    ledger = tmp_path / "events.jsonl"
    out = tmp_path / "state.md"
    sha = knowledge.write_state(ledger, out)
    assert sha == hashlib.sha256(b"").hexdigest()
    assert "as of event 0" in out.read_text(encoding="utf-8")
