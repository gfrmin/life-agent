# tests/trips/test_seeder.py
"""ICS seeder: recognise SUMMARY/DESCRIPTION -> minimal JSON-LD -> extract() enriches."""
from __future__ import annotations

from pathlib import Path

from life_agent.trips import seeder, store

_FIX = Path(__file__).parent / "fixtures"


def test_parse_vevents_reads_all_four() -> None:
    vevents = seeder.parse_vevents((_FIX / "trip.ics").read_text())
    assert len(vevents) == 4


def test_hotels_repair_into_one_stay() -> None:
    vevents = seeder.parse_vevents((_FIX / "trip.ics").read_text())
    recognised = seeder.pair_and_recognise(vevents)
    lodging = [j for j, _tid, _cd in recognised if j.get("@type") == "LodgingReservation"]
    assert len(lodging) == 1
    assert lodging[0]["checkinTime"].startswith("2019-08-12")
    assert lodging[0]["checkoutTime"].startswith("2019-08-15")


def test_trip_container_becomes_a_label_not_a_reservation() -> None:
    vevents = seeder.parse_vevents((_FIX / "trip.ics").read_text())
    recognised = seeder.pair_and_recognise(vevents)
    # 1 flight + 1 lodging = 2 reservations; the !TRIPX container is not one of them.
    assert len(recognised) == 2
    assert all(j.get("@type") != "TripReservation" for j, _t, _c in recognised)


def test_import_ics_lands_at_ics_fidelity(monkeypatch) -> None:
    # Stub extract() to echo its input JSON-LD (avoid depending on the live binary here).
    import json as _json
    monkeypatch.setattr(seeder, "extract",
        lambda payload, ctx: _json.loads(payload.decode()))
    stats = seeder.import_ics(_FIX / "trip.ics")
    assert stats["reservations"] == 2 and stats["trips"] == 1
    rows = store.timeline()
    assert all(r["fidelity"] == "kayak-ics" for r in rows)
