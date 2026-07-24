"""Hermetic contract tests for the trips timeline server (reach.trips.server).

Redirects the trips read-model to tmp_path and exercises dispatch() directly (no socket, no
keyring, no model), plus loopback smoke tests for the transport. Reservations are synthetic.
"""
from __future__ import annotations

import threading
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from life_agent.reach.trips.server import WebServer, dispatch
from life_agent.trips import events as ev
from life_agent.trips import store


def _flight(dep: str, arr: str, dep_time: str, conf: str = "EXMPL0") -> dict[str, Any]:
    return {"@type": "FlightReservation", "reservationNumber": conf,
            "reservationFor": {"flightNumber": "EX1",
                "departureAirport": {"iataCode": dep}, "arrivalAirport": {"iataCode": arr},
                "departureTime": dep_time}}


@pytest.fixture(autouse=True)
def temp_trips(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "trips.db")
    store.init_db()


def _seed(*reservations: dict[str, Any]) -> None:
    events = [ev.observed(f"id{i}", r, fidelity="kayak-api", source_id=f"k{i}",
                          received_at="2019-08-01T00:00:00")
              for i, r in enumerate(reservations)]
    with store.get_db() as conn:
        store.rebuild(conn, events)


def test_index_is_html() -> None:
    status, payload = dispatch("GET", "/", b"")
    assert status == 200
    assert isinstance(payload, str)
    assert "<!DOCTYPE html>" in payload and "<title>Trips</title>" in payload


def test_ready() -> None:
    assert dispatch("GET", "/ready", b"") == (200, {"status": "ok"})


def test_timeline_returns_reservations() -> None:
    _seed(_flight("LIS", "AMS", "2019-08-12T09:30:00Z"))
    status, payload = dispatch("GET", "/api/timeline", b"")
    assert status == 200
    assert [r["dep_iata"] for r in payload["reservations"]] == ["LIS"]


def test_now_next_shape() -> None:
    status, payload = dispatch("GET", "/api/now_next", b"")
    assert status == 200
    assert set(payload) == {"now", "next"}


def test_search_filters() -> None:
    _seed(_flight("LIS", "AMS", "2019-08-12T09:30:00Z"),
          _flight("JFK", "SFO", "2020-01-01T09:30:00Z"))
    status, payload = dispatch("GET", "/api/search?q=JFK", b"")
    assert status == 200
    assert [r["dep_iata"] for r in payload["reservations"]] == ["JFK"]


def test_search_without_query_is_empty() -> None:
    _seed(_flight("LIS", "AMS", "2019-08-12T09:30:00Z"))
    status, payload = dispatch("GET", "/api/search", b"")
    assert status == 200
    assert payload["reservations"] == []


def test_calendar_ics_is_vcalendar() -> None:
    _seed(_flight("LIS", "AMS", "2019-08-12T09:30:00Z"))
    status, payload = dispatch("GET", "/calendar.ics", b"")
    assert status == 200
    assert isinstance(payload, str)
    assert payload.startswith("BEGIN:VCALENDAR")
    assert "SUMMARY:LIS→AMS" in payload


def test_unknown_get_is_404() -> None:
    assert dispatch("GET", "/nope", b"")[0] == 404


def test_post_is_405() -> None:
    status, payload = dispatch("POST", "/api/timeline", b"")
    assert status == 405
    assert "error" in payload


# --- transport: real loopback ----------------------------------------------------------

@pytest.fixture
def live(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "trips.db")
    store.init_db()
    server = WebServer(host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()


def test_http_index_served_as_html(live: str) -> None:
    with urllib.request.urlopen(live + "/", timeout=5) as resp:
        ctype = resp.headers.get("Content-Type", "")
        body = resp.read().decode()
    assert resp.status == 200
    assert ctype.startswith("text/html")
    assert "<!DOCTYPE html>" in body


def test_http_calendar_served_as_ical(live: str) -> None:
    with urllib.request.urlopen(live + "/calendar.ics", timeout=5) as resp:
        ctype = resp.headers.get("Content-Type", "")
        body = resp.read().decode()
    assert resp.status == 200
    assert ctype.startswith("text/calendar")
    assert body.startswith("BEGIN:VCALENDAR")
