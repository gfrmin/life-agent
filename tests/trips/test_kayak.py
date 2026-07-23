# tests/trips/test_kayak.py
"""The Kayak export importer: the tier-3 coverage floor, full history on day one."""
from __future__ import annotations

from pathlib import Path

from life_agent.trips import kayak, store

_FIX = Path(__file__).parent / "fixtures"


def test_flight_event_maps_to_schema_org_with_segments() -> None:
    event = {"type": "flight", "eventId": "CKNpOC",
             "legs": [{"segments": [
                 {"departureAirportCode": "LIS", "arrivalAirportCode": "AMS",
                  "departureTimestamp": "2019-08-12T09:30:00", "departureTimeZone": "Europe/Lisbon",
                  "marketingCarrierCode": "TP", "flightNumber": "123"}]}]}
    jsonld = kayak.event_to_jsonld(event)
    assert jsonld["@type"] == "FlightReservation"
    seg = jsonld["reservationFor"]
    seg0 = seg[0] if isinstance(seg, list) else seg
    assert seg0["departureAirport"]["iataCode"] == "LIS"


def test_import_projects_full_history_at_kayak_fidelity() -> None:
    stats = kayak.import_export(_FIX / "kayak-export.json")
    assert stats["reservations"] >= 3
    rows = store.timeline()
    assert rows and all(r["fidelity"] == "kayak-api" for r in rows)


def test_reimport_is_idempotent() -> None:
    kayak.import_export(_FIX / "kayak-export.json")
    first = len(store.timeline())
    kayak.import_export(_FIX / "kayak-export.json")  # again
    assert len(store.timeline()) == first  # observe() dedupes by (identity, source_id)


def test_kayak_and_email_of_same_flight_dedupe_to_one_row() -> None:
    """The whole point: a Kayak flight and its own confirmation email are ONE identity."""
    from life_agent.trips import commands
    kayak.import_export(_FIX / "kayak-export.json")
    before = len(store.timeline())
    # Re-observe the first flight's content as an email at higher fidelity.
    row = next(r for r in store.timeline() if r["res_type"] == "FlightReservation")
    import json
    commands.observe(json.loads(row["jsonld"]), fidelity="email-kitinerary",
                     source_id="mail-x", received_at="2019-09-01T00:00:00")
    after = store.timeline()
    assert len(after) == before  # no new row
    upgraded = store.get_reservation(row["identity"])
    assert upgraded["fidelity"] == "email-kitinerary"
