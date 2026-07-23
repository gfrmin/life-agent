# tests/trips/test_kayak.py
"""The Kayak export importer: the tier-3 coverage floor, full history on day one."""
from __future__ import annotations

from pathlib import Path

from life_agent.trips import kayak, store

_FIX = Path(__file__).parent / "fixtures"


def test_flight_event_maps_to_schema_org_with_segments() -> None:
    event = {"eventType": "flight", "eventId": "CKNpOC",
             "legs": [{"segments": [
                 {"departureLocation": {"airportCode": "LIS"},
                  "arrivalLocation": {"airportCode": "AMS"},
                  "departureDate": "2019-08-12T09:30:00", "departureTimezone": "Europe/Lisbon",
                  "airlineCode": "TP", "flightNumber": "123"}]}]}
    jsonld = kayak.event_to_jsonld(event)
    assert jsonld["@type"] == "FlightReservation"
    seg = jsonld["reservationFor"]
    seg0 = seg[0] if isinstance(seg, list) else seg
    assert seg0["departureAirport"]["iataCode"] == "LIS"
    # Bare flight number + separate airline dict, matching kitinerary's own shape (NOT
    # concatenated "TP123" — a concatenated number would never match the email's identity).
    assert seg0["flightNumber"] == "123"
    assert seg0["airline"]["iataCode"] == "TP"


def test_import_projects_full_history_at_kayak_fidelity() -> None:
    stats = kayak.import_export(_FIX / "kayak-export.json")
    assert stats["reservations"] >= 3
    rows = store.timeline()
    assert rows and all(r["fidelity"] == "kayak-api" for r in rows)
    assert any(r["confirmation"] is None for r in rows)  # sparse-confirmation case still imports


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


def test_kayak_and_kitinerary_shaped_email_dedupe_across_formats() -> None:
    """The real upgrade path: a Kayak naive-timestamp+IANA-zone flight and a kitinerary
    QDateTime-dict record of the SAME instant must share ONE identity and upgrade to email."""
    from life_agent.trips import commands
    kayak_event = {"eventType": "flight", "eventId": "XDEDUP", "legs": [{"segments": [
        {"departureLocation": {"airportCode": "LIS"},
         "arrivalLocation": {"airportCode": "AMS"},
         "departureDate": "2019-08-12T09:30:00", "departureTimezone": "Europe/Lisbon",
         "airlineCode": "EX", "flightNumber": "123"}]}]}
    kid = commands.observe(kayak.event_to_jsonld(kayak_event), fidelity="kayak-api",
                           source_id="k-dedup", received_at="2019-08-01T00:00:00")
    # Real kitinerary output shape: a BARE flight number + a separate `airline` dict (NOT
    # "EX123" concatenated) — this is what a hand-written "EX123" test would have hidden.
    email_jsonld = {"@type": "FlightReservation", "reservationFor": {"@type": "Flight",
        "flightNumber": "123",
        "airline": {"@type": "Airline", "iataCode": "EX", "name": "Example Air"},
        "departureAirport": {"@type": "Airport", "iataCode": "LIS"},
        "arrivalAirport": {"@type": "Airport", "iataCode": "AMS"},
        "departureTime": {"@type": "QDateTime", "@value": "2019-08-12T09:30:00+01:00",
                          "timezone": "Europe/Lisbon"}}}
    eid = commands.observe(email_jsonld, fidelity="email-kitinerary",
                           source_id="mail-dedup", received_at="2019-09-01T00:00:00")
    assert eid == kid                                   # same identity across formats
    assert len(store.timeline()) == 1                   # one row, not two
    assert store.get_reservation(kid)["fidelity"] == "email-kitinerary"  # upgraded
