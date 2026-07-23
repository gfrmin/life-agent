# tests/trips/test_store.py
"""The read projection: a rebuildable SQLite view of fold(ledger)."""
from __future__ import annotations

from life_agent.trips import events as ev
from life_agent.trips import store


def _flight(fno: str, dep: str, arr: str, dep_time: str) -> dict:
    return {"@type": "FlightReservation", "reservationNumber": "EXMPL0",
            "reservationFor": {"flightNumber": fno,
                "departureAirport": {"iataCode": dep}, "arrivalAirport": {"iataCode": arr},
                "departureTime": dep_time}}


def test_rebuild_projects_current_reservations() -> None:
    events = [ev.observed("id1", _flight("EX1", "LIS", "AMS", "2019-08-12T09:30:00+01:00"),
                          fidelity="kayak-api", source_id="k1", received_at="2019-08-01T00:00:00")]
    with store.get_db() as conn:
        store.rebuild(conn, events)
    rows = store.timeline()
    assert len(rows) == 1
    assert rows[0]["dep_iata"] == "LIS" and rows[0]["arr_iata"] == "AMS"
    assert rows[0]["confirmation"] == "EXMPL0"


def test_superseded_rows_are_excluded_from_timeline() -> None:
    events = [
        ev.observed("old", _flight("EX1", "LIS", "AMS", "2019-08-12T09:30:00Z"),
                    fidelity="email-kitinerary", source_id="m1", received_at="2019-08-01T00:00:00"),
        ev.observed("new", _flight("EX9", "LIS", "AMS", "2019-08-12T18:00:00Z"),
                    fidelity="email-kitinerary", source_id="m2", received_at="2019-08-02T00:00:00"),
        ev.superseded("old", "new"),
    ]
    with store.get_db() as conn:
        store.rebuild(conn, events)
    idents = {r["identity"] for r in store.timeline()}
    assert idents == {"new"}
    assert store.get_reservation("old")["superseded_by"] == "new"  # retained, queryable


def test_search_matches_iata_and_confirmation() -> None:
    events = [ev.observed("id1", _flight("EX1", "LIS", "AMS", "2019-08-12T09:30:00Z"),
                          fidelity="kayak-api", source_id="k1", received_at="2019-08-01T00:00:00")]
    with store.get_db() as conn:
        store.rebuild(conn, events)
    assert store.search("AMS")
    assert store.search("EXMPL0")
    assert store.search("nowhere") == []


def test_multisegment_flight_projects_origin_and_final_destination() -> None:
    j = {"@type": "FlightReservation", "reservationFor": [
        {"flightNumber": "EX1", "departureAirport": {"iataCode": "LIS"},
         "arrivalAirport": {"iataCode": "CDG"}, "departureTime": "2019-08-12T09:00:00Z",
         "arrivalTime": "2019-08-12T12:00:00Z"},
        {"flightNumber": "EX2", "departureAirport": {"iataCode": "CDG"},
         "arrivalAirport": {"iataCode": "JFK"}, "departureTime": "2019-08-12T14:00:00Z",
         "arrivalTime": "2019-08-12T18:00:00Z"}]}
    events = [ev.observed("id1", j, fidelity="kayak-api", source_id="k1",
                          received_at="2019-08-01T00:00:00")]
    with store.get_db() as conn:
        store.rebuild(conn, events)
    row = store.get_reservation("id1")
    assert row["dep_iata"] == "LIS"
    assert row["arr_iata"] == "JFK"   # final destination, not the CDG connection
