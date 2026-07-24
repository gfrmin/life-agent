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


def test_help_exits_zero(capsys) -> None:
    assert cli.main(["--help"]) == 0
    assert cli.main(["-h"]) == 0


def test_ingest_mail_uses_query_override_and_reports(capsys, monkeypatch) -> None:
    from life_agent.trips import mailbox
    seen: dict = {}

    def fake_ingest(q, **kw):
        seen["q"] = q
        seen["kw"] = kw
        return mailbox.Stats(selected=3, forwards_resolved=1, messages_with_yield=1,
                             reservations=2)

    monkeypatch.setattr(mailbox, "ingest_query", fake_ingest)
    assert cli.main(["ingest-mail", "--query", "folder:Trips", "--dry-run", "--limit", "5"]) == 0
    assert seen["q"] == "folder:Trips"
    assert seen["kw"]["dry_run"] is True
    assert seen["kw"]["limit"] == 5
    out = capsys.readouterr().out
    assert "2" in out and "would" in out.lower()


def test_ingest_mail_falls_back_to_configured_query(capsys, monkeypatch) -> None:
    from life_agent.trips import mailbox
    monkeypatch.setattr(mailbox, "configured_query", lambda: "CONFIGURED")
    seen: dict = {}
    monkeypatch.setattr(mailbox, "ingest_query",
                        lambda q, **kw: seen.update(q=q) or mailbox.Stats())
    assert cli.main(["ingest-mail"]) == 0
    assert seen["q"] == "CONFIGURED"


def test_ingest_dateless_file_errors_without_context_date(tmp_path, capsys, monkeypatch) -> None:
    f = tmp_path / "dateless.eml"
    f.write_bytes(b"Message-ID: <nodate@x>\r\nSubject: Booking\r\n\r\nbody\r\n")
    monkeypatch.setattr(cli, "extract", lambda payload, ctx: [{"@type": "FlightReservation"}])
    assert cli.main(["ingest", str(f)]) == 2
    assert capsys.readouterr().err.strip() != ""
    assert store.timeline() == []


def test_ingest_dateless_file_with_context_date_override(tmp_path, capsys, monkeypatch) -> None:
    f = tmp_path / "dateless.eml"
    f.write_bytes(b"Message-ID: <nodate@x>\r\nSubject: Booking\r\n\r\nbody\r\n")
    monkeypatch.setattr(cli, "extract", lambda payload, ctx: [_flight_jsonld()])
    assert cli.main(["ingest", str(f), "--context-date", "2019-08-12"]) == 0
    rows = store.timeline()
    assert rows
    with store.get_db() as conn:
        received = {r["received_at"] for r in conn.execute("SELECT received_at FROM source")}
    assert any(r and r.startswith("2019-08-12") for r in received)


def test_ingest_invalid_context_date_errors(tmp_path, capsys, monkeypatch) -> None:
    f = tmp_path / "dateless.eml"
    f.write_bytes(b"Message-ID: <nodate@x>\r\nSubject: Booking\r\n\r\nbody\r\n")
    monkeypatch.setattr(cli, "extract", lambda payload, ctx: [_flight_jsonld()])
    assert cli.main(["ingest", str(f), "--context-date", "not-a-date"]) == 2


def _flight_jsonld() -> dict:
    return {"@type": "FlightReservation",
            "reservationFor": {"flightNumber": "EX1",
                "departureAirport": {"iataCode": "LIS"},
                "arrivalAirport": {"iataCode": "AMS"},
                "departureTime": "2019-08-12T09:30:00Z"}}


def test_ingest_mail_missing_config_returns_nonzero(capsys, monkeypatch) -> None:
    from life_agent.trips import mailbox

    def boom() -> str:
        raise mailbox.IngestConfigError("no trips.ingest.query")

    monkeypatch.setattr(mailbox, "configured_query", boom)
    assert cli.main(["ingest-mail"]) == 2
    assert "query" in capsys.readouterr().err.lower()
