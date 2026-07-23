# tests/trips/test_commands.py
"""The write seam: append event -> rebuild projection. Idempotent by (identity, source_id)."""
from __future__ import annotations

from life_agent.trips import commands, store
from life_agent.trips import events as ev


def _flight() -> dict:
    return {"@type": "FlightReservation",
            "reservationFor": {"flightNumber": "EX1",
                "departureAirport": {"iataCode": "LIS"}, "arrivalAirport": {"iataCode": "AMS"},
                "departureTime": "2019-08-12T09:30:00Z"}}


def test_observe_projects_a_reservation() -> None:
    ident = commands.observe(_flight(), fidelity="kayak-api", source_id="k1",
                             received_at="2019-08-01T00:00:00")
    assert store.get_reservation(ident) is not None
    assert len(ev.load(commands.LEDGER_PATH)) == 1


def test_observe_is_idempotent_on_identity_and_source() -> None:
    for _ in range(3):
        commands.observe(_flight(), fidelity="kayak-api", source_id="k1",
                         received_at="2019-08-01T00:00:00")
    assert len(ev.load(commands.LEDGER_PATH)) == 1  # same identity+source -> one event
    assert len(store.timeline()) == 1


def test_same_flight_two_sources_are_two_events_one_row() -> None:
    commands.observe(_flight(), fidelity="kayak-api", source_id="kayak",
                     received_at="2019-08-01T00:00:00")
    ident = commands.observe(_flight(), fidelity="email-kitinerary", source_id="mail",
                             received_at="2019-08-02T00:00:00")
    assert len(ev.load(commands.LEDGER_PATH)) == 2
    assert len(store.timeline()) == 1
    assert store.get_reservation(ident)["fidelity"] == "email-kitinerary"  # email wins


def test_cancel_marks_cancelled() -> None:
    ident = commands.observe(_flight(), fidelity="email-kitinerary", source_id="m1",
                             received_at="2019-08-01T00:00:00")
    commands.cancel(ident, "airline cancelled", source_id="m2")
    assert store.get_reservation(ident)["cancelled"] is True
