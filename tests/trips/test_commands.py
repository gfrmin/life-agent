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
    assert len(ev.load(commands.LEDGER_PATH)) == 2  # observed + cancelled, append-only
    assert store.get_reservation(ident)["cancelled"] is True


def test_amend_appends_and_merges_into_projection() -> None:
    ident = commands.observe(_flight(), fidelity="kayak-api", source_id="k1",
                             received_at="2019-08-01T00:00:00")
    returned = commands.amend(ident, {"reservationFor": {"seatNumber": "12A"}})
    assert returned == ident
    assert len(ev.load(commands.LEDGER_PATH)) == 2  # observed + amended
    import json
    merged = json.loads(store.get_reservation(ident)["jsonld"])
    assert merged["reservationFor"]["seatNumber"] == "12A"      # amended field merged
    assert merged["reservationFor"]["flightNumber"] == "EX1"    # sibling preserved


def test_supersede_links_old_to_new_and_updates_current() -> None:
    old = commands.observe(_flight(), fidelity="email-kitinerary", source_id="m1",
                           received_at="2019-08-01T00:00:00")
    new_jsonld = {"@type": "FlightReservation",
                  "reservationFor": {"flightNumber": "EX9",
                      "departureAirport": {"iataCode": "LIS"},
                      "arrivalAirport": {"iataCode": "AMS"},
                      "departureTime": "2019-08-12T18:00:00Z"}}
    new = commands.observe(new_jsonld, fidelity="email-kitinerary", source_id="m2",
                           received_at="2019-08-02T00:00:00")
    commands.supersede(old, new)
    assert len(ev.load(commands.LEDGER_PATH)) == 3  # two observed + one superseded
    assert store.get_reservation(old)["superseded_by"] == new  # ancestor retained + linked
    current = {r["identity"] for r in store.timeline()}
    assert current == {new}  # only the successor is current


def test_observe_persists_source_metadata_across_rebuild() -> None:
    commands.observe(_flight(), fidelity="email-kitinerary", source_id="mail-1",
                     received_at="2019-08-02T00:00:00",
                     source_meta={"message_id": "<abc@example.com>", "kind": "email"})
    with store.get_db() as conn:
        row = conn.execute(
            "SELECT message_id, kind FROM source WHERE source_id = ?", ("mail-1",)).fetchone()
    assert row is not None
    assert row["message_id"] == "<abc@example.com>"  # survived the rebuild in observe()
    assert row["kind"] == "email"
