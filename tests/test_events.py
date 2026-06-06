"""Tests for the act-layer event ledger (``life_agent.tasks.events``).

Covers the three things the design rests on: a content+grounding **assertion
identity** that is stable across re-derivation and excludes provenance; an
append-only **log** that tolerates garbage; and a pure **fold** where a close
(disposed/superseded) always wins, so a cleared item never resurrects and replay
is order-independent.
"""

from __future__ import annotations

from pathlib import Path

from life_agent.tasks import events as ev

# --- assertion identity -------------------------------------------------------


def test_identity_is_deterministic_and_distinguishes_content() -> None:
    a = ev.assertion_identity("task", "send the signed lease", "Send the lease")
    b = ev.assertion_identity("task", "send the signed lease", "Send the lease")
    c = ev.assertion_identity("task", "send the signed lease", "Pay the deposit")
    assert a == b  # same inputs → same identity
    assert a != c  # different claim content → different identity


def test_identity_is_whitespace_normalised() -> None:
    # Re-derivation that only reflows whitespace must NOT change identity.
    tight = ev.assertion_identity("task", "send the signed lease", "Send the lease")
    loose = ev.assertion_identity("task", "  send   the\nsigned  lease ", "Send  the   lease")
    assert tight == loose


def test_identity_ignores_provenance_by_construction() -> None:
    # Identity takes only (type, span, content) — there is no model/prompt input,
    # so a prompt/model bump that re-extracts the same text yields the same id.
    same = ev.assertion_identity("task", "the quote", "the action")
    again = ev.assertion_identity("task", "the quote", "the action")
    assert same == again
    assert len(same) == 64  # sha256 hex


# --- event construction + round-trip ------------------------------------------


def test_event_id_is_derived_when_omitted() -> None:
    e = ev.asserted("id1", {"x": 1}, tx_time="2026-06-06T00:00:00")
    assert e.event_id  # filled in
    e2 = ev.asserted("id1", {"x": 1}, tx_time="2026-06-06T00:00:00")
    assert e.event_id == e2.event_id  # deterministic for same (type, id, tx_time)


def test_append_then_load_round_trips(tmp_path: Path) -> None:
    ledger = tmp_path / "tasks" / "events.jsonl"
    ev.append(ledger, [ev.asserted("a", {"task_text": "do a"}, tx_time="2026-06-06T00:00:01")])
    ev.append(ledger, [ev.disposed("a", reason="cleared", tx_time="2026-06-06T00:00:02")])
    loaded = ev.load(ledger)
    assert [e.type for e in loaded] == ["asserted", "disposed"]
    assert loaded[0].payload == {"task_text": "do a"}
    assert loaded[1].reason == "cleared"


def test_load_missing_is_empty(tmp_path: Path) -> None:
    assert ev.load(tmp_path / "nope.jsonl") == []


def test_load_tolerates_garbage_lines(tmp_path: Path) -> None:
    ledger = tmp_path / "events.jsonl"
    good = ev._to_json(ev.asserted("ok", {}, tx_time="2026-06-06T00:00:00"))
    ledger.write_text(good + "\nnot json\n{}\n", encoding="utf-8")
    loaded = ev.load(ledger)
    assert len(loaded) == 1
    assert loaded[0].identity == "ok"


# --- fold: the projection -----------------------------------------------------


def test_fold_opens_asserted() -> None:
    open_ = ev.fold([ev.asserted("a", {"task_text": "A"}), ev.asserted("b", {"task_text": "B"})])
    assert set(open_) == {"a", "b"}
    assert open_["a"].payload["task_text"] == "A"


def test_fold_close_always_wins_regardless_of_order() -> None:
    # disposed closes 'a' even if the asserted appears AFTER it in the list.
    events = [ev.disposed("a", reason="cleared"), ev.asserted("a", {"task_text": "A"})]
    assert ev.fold(events) == {}


def test_fold_does_not_resurrect_a_cleared_assertion() -> None:
    # assert → dispose → re-assert (re-derivation): stays closed (no resurrection).
    events = [
        ev.asserted("a", {"task_text": "A"}, tx_time="2026-06-06T00:00:01"),
        ev.disposed("a", reason="cleared", tx_time="2026-06-06T00:00:02"),
        ev.asserted("a", {"task_text": "A"}, tx_time="2026-06-06T00:00:03"),
    ]
    assert "a" not in ev.fold(events)


def test_fold_superseded_closes_the_old() -> None:
    events = [
        ev.asserted("old", {"task_text": "v1"}),
        ev.superseded("old", "new"),
        ev.asserted("new", {"task_text": "v2"}),
    ]
    open_ = ev.fold(events)
    assert "old" not in open_
    assert "new" in open_


def test_known_identities_includes_closed_ones() -> None:
    # `fold` (open) drops a disposed id, but `known_identities` keeps it — that is what
    # stops a cleared assertion from being re-filed (resurrected) on the next run.
    events = [
        ev.asserted("a", {"task_text": "A"}),
        ev.disposed("a", reason="cleared"),
        ev.asserted("b", {"task_text": "B"}),
    ]
    assert set(ev.fold(events)) == {"b"}
    assert ev.known_identities(events) == {"a", "b"}
