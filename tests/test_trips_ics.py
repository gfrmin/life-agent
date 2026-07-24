"""Pure-function tests for the hand-written iCalendar serialiser (reach.trips.ics).

Reservations are synthetic by construction — hand-built dicts in the shape store.timeline()
returns. No real itinerary data, no socket, no subprocess.
"""
from __future__ import annotations

from typing import Any

from life_agent.reach.trips.ics import to_ics


def _res(**kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "identity": "abc123", "res_type": "FlightReservation", "title": None,
        "start_iso": "2019-08-12T09:30:00Z", "end_iso": None, "confirmation": None,
        "provider": None, "dep_iata": None, "arr_iata": None, "cancelled": False,
    }
    base.update(kw)
    return base


def test_offset_datetime_becomes_utc_z() -> None:
    out = to_ics([_res(start_iso="2019-08-12T09:30:00+02:00")])
    assert "DTSTART:20190812T073000Z" in out  # +02:00 -> 07:30 UTC


def test_zulu_datetime_stays_utc_z() -> None:
    out = to_ics([_res(start_iso="2019-08-12T09:30:00Z")])
    assert "DTSTART:20190812T093000Z" in out


def test_naive_datetime_is_floating() -> None:
    out = to_ics([_res(start_iso="2019-08-12T09:30:00")])
    assert "DTSTART:20190812T093000\r\n" in out  # no trailing Z
    assert "20190812T093000Z" not in out


def test_end_time_becomes_dtend() -> None:
    out = to_ics([_res(end_iso="2019-08-12T12:00:00Z")])
    assert "DTEND:20190812T120000Z" in out


def test_flight_summary_is_route_and_provider() -> None:
    out = to_ics([_res(dep_iata="LIS", arr_iata="AMS", provider="KLM")])
    assert "SUMMARY:LIS→AMS KLM" in out  # LIS→AMS KLM


def test_hotel_summary_falls_back_to_title() -> None:
    out = to_ics([_res(res_type="LodgingReservation", title="Hotel Ritz",
                       start_iso="2019-08-12T15:00:00", dep_iata=None, arr_iata=None)])
    assert "SUMMARY:Hotel Ritz" in out


def test_cancelled_emits_status() -> None:
    assert "STATUS:CANCELLED" in to_ics([_res(cancelled=True)])


def test_active_has_no_status_line() -> None:
    assert "STATUS:" not in to_ics([_res(cancelled=False)])


def test_confirmation_becomes_description() -> None:
    assert "DESCRIPTION:XY7Z9" in to_ics([_res(confirmation="XY7Z9")])


def test_uid_is_the_identity() -> None:
    assert "UID:deadbeef" in to_ics([_res(identity="deadbeef")])


def test_reservation_without_start_is_skipped() -> None:
    out = to_ics([_res(start_iso=None)])
    assert "BEGIN:VEVENT" not in out
    assert out.startswith("BEGIN:VCALENDAR")


def test_text_special_chars_are_escaped() -> None:
    out = to_ics([_res(res_type="FoodEstablishmentReservation",
                       title="Dinner, then; drinks", dep_iata=None, arr_iata=None)])
    assert "SUMMARY:Dinner\\, then\\; drinks" in out


def test_long_summary_folds_to_75_octets() -> None:
    out = to_ics([_res(title="A" * 200, dep_iata=None, arr_iata=None)])
    for line in out.split("\r\n"):
        assert len(line.encode("utf-8")) <= 75


def test_calendar_wrapper_and_crlf() -> None:
    out = to_ics([_res()])
    assert out.startswith("BEGIN:VCALENDAR\r\n")
    assert out.rstrip("\r\n").endswith("END:VCALENDAR")
    assert "VERSION:2.0" in out
    assert "PRODID:-//life-agent//trips//EN" in out
    assert "CALSCALE:GREGORIAN" in out


def test_empty_input_is_a_valid_empty_calendar() -> None:
    out = to_ics([])
    assert out.startswith("BEGIN:VCALENDAR\r\n")
    assert "BEGIN:VEVENT" not in out
    assert out.rstrip("\r\n").endswith("END:VCALENDAR")
