"""The one impure edge: a deterministic subprocess wrapper over kitinerary-extractor."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from life_agent.trips import extract as ex

_FIX = Path(__file__).parent / "fixtures"


def test_missing_binary_returns_empty_never_raises(monkeypatch) -> None:
    monkeypatch.setattr(ex, "BINARY", "/fake/kitinerary")
    assert ex.extract(b"anything", datetime(2019, 8, 5)) == []


def test_garbage_input_returns_empty(monkeypatch) -> None:
    # A real binary on non-email bytes yields []; if absent, the missing-binary path also gives [].
    assert ex.extract(b"\x00\x01not an email", datetime(2019, 8, 5)) == []


@pytest.mark.system
def test_real_email_yields_flight_reservation() -> None:
    payload = (_FIX / "flight.eml").read_bytes()
    out = ex.extract(payload, datetime(2019, 8, 5))
    assert any(o.get("@type") == "FlightReservation" for o in out)


@pytest.mark.system
def test_raw_jsonld_is_enriched() -> None:
    """kitinerary accepts raw JSON-LD and enriches IATA -> timezone/geo (the seeder trick)."""
    import json
    stub = json.dumps([{
        "@context": "http://schema.org",
        "@type": "FlightReservation",
        "reservationFor": {"@type": "Flight",
            "departureAirport": {"@type": "Airport", "iataCode": "LIS"},
            "arrivalAirport": {"@type": "Airport", "iataCode": "AMS"},
            "departureDay": "2019-08-12"}}]).encode()
    out = ex.extract(stub, datetime(2019, 8, 5))
    assert out, "expected at least one enriched reservation"
