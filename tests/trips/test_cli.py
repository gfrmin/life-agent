# tests/trips/test_cli.py
"""The CLI wires importers + queries; dispatch is testable without a process."""
from __future__ import annotations

from pathlib import Path

from life_agent.trips import cli, store

_FIX = Path(__file__).parent / "fixtures"


def test_import_kayak_then_list(capsys) -> None:
    assert cli.main(["import-kayak", str(_FIX / "kayak-export.json")]) == 0
    assert cli.main(["list"]) == 0
    out = capsys.readouterr().out
    assert "LIS" in out or "reservation" in out.lower()


def test_ingest_single_email_upgrades(capsys, monkeypatch) -> None:
    # Seed a Kayak flight, then ingest an email of the same flight -> upgrades in place.
    from life_agent.trips import kayak
    kayak.import_export(_FIX / "kayak-export.json")
    n = len(store.timeline())
    # Stub extract for hermeticity: echo a reservation matching the first flight's content.
    row = next(r for r in store.timeline() if r["res_type"] == "FlightReservation")
    import json
    monkeypatch.setattr(cli, "extract", lambda payload, ctx: [json.loads(row["jsonld"])])
    (tmp := _FIX / "any.eml")  # path only; extract is stubbed
    assert cli.main(["ingest", str(tmp if tmp.exists() else _FIX / "flight.eml")]) == 0
    assert len(store.timeline()) == n  # upgraded, not added
    assert store.get_reservation(row["identity"])["fidelity"] == "email-kitinerary"


def test_search_subcommand(capsys) -> None:
    from life_agent.trips import kayak
    kayak.import_export(_FIX / "kayak-export.json")
    assert cli.main(["search", "AMS"]) == 0
    assert "AMS" in capsys.readouterr().out


def test_unknown_command_returns_nonzero() -> None:
    assert cli.main(["frobnicate"]) != 0
