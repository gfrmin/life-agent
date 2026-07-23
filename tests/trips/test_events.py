"""The append-only ledger: constructors, round-trip serialisation, fidelity ranking."""
from __future__ import annotations

from pathlib import Path

from life_agent.trips import events as ev


def test_fidelity_rank_orders_manual_over_kayak() -> None:
    assert ev.FIDELITY_RANK["manual"] < ev.FIDELITY_RANK["email-kitinerary"]
    assert ev.FIDELITY_RANK["email-kitinerary"] < ev.FIDELITY_RANK["kayak-api"]
    assert ev.FIDELITY_RANK["kayak-api"] < ev.FIDELITY_RANK["kayak-ics"]


def test_observed_carries_fidelity_and_source() -> None:
    e = ev.observed("id1", {"@type": "FlightReservation"},
                    fidelity="kayak-api", source_id="evt-9", received_at="2019-08-05T10:00:00")
    assert e.type == "observed"
    assert e.fidelity == "kayak-api"
    assert e.source_id == "evt-9"
    assert e.payload == {"@type": "FlightReservation"}
    assert e.event_id  # auto-derived, non-empty


def test_round_trip_through_ledger(tmp_path: Path) -> None:
    ledger = tmp_path / "events.jsonl"
    events = [
        ev.observed("id1", {"@type": "FlightReservation"},
                    fidelity="kayak-api", source_id="e1", received_at="2019-08-05T10:00:00"),
        ev.superseded("id1", "id2"),
        ev.cancelled("id2", reason="airline cancelled", source_id="mail-1"),
        ev.amended("id2", {"seatNumber": "12A"}),
    ]
    ev.append(ledger, events)
    loaded = ev.load(ledger)
    assert [e.type for e in loaded] == ["observed", "superseded", "cancelled", "amended"]
    assert loaded[1].superseded_by == "id2"
    assert loaded[3].payload["fields"] == {"seatNumber": "12A"}


def test_load_missing_ledger_is_empty(tmp_path: Path) -> None:
    assert ev.load(tmp_path / "nope.jsonl") == []
