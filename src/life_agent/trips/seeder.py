# src/life_agent/trips/seeder.py
"""Seed tier-4 reservations from the Kayak ICS feed.

kitinerary returns [] for Kayak's prose VEVENTs, but it *accepts raw JSON-LD and enriches it*.
So the seeder hand-writes only RECOGNITION (regex the SUMMARY/DESCRIPTION into minimal
schema.org JSON-LD) and feeds that through extract() for ENRICHMENT — the airport/timezone
database does the hard part, and ICS-derived records emerge in the identical shape as
email-derived ones. Two quirks: hotels are split into `Check in`/`Check out` VEVENTs sharing
a booking id (UID prefixes `0-`/`1-`) to re-pair; every event embeds `!<tripId>`, and the
all-day container carries the trip's name and dates.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from life_agent.trips import commands, store
from life_agent.trips.extract import extract

_TRIP_RE = re.compile(r"/trips/(![A-Za-z0-9]+)")
_IATA_RE = re.compile(r"\(([A-Z]{3})\)")
_HOTEL_UID_RE = re.compile(r"^([01])-(.+)$")


def parse_vevents(ics_text: str) -> list[dict[str, Any]]:
    """Minimal stdlib VEVENT parse — unfold continuation lines, split KEY[;params]:VALUE."""
    unfolded = re.sub(r"\r?\n[ \t]", "", ics_text)
    out: list[dict[str, Any]] = []
    for block in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", unfolded, re.S):
        ev: dict[str, Any] = {}
        for line in block.strip().splitlines():
            if ":" not in line:
                continue
            key, val = line.split(":", 1)
            name = key.split(";", 1)[0].strip().upper()
            ev[name] = val.strip().replace("\\n", "\n").replace("\\,", ",")
        if ev:
            out.append(ev)
    return out


def _trip_id(ev: dict[str, Any]) -> str | None:
    for field in (ev.get("DESCRIPTION", ""), ev.get("URL", ""), ev.get("UID", "")):
        m = _TRIP_RE.search(field)
        if m:
            return m.group(1)
    m = re.match(r"^(![A-Za-z0-9]+)", ev.get("UID", ""))
    return m.group(1) if m else None


def _ics_dt(v: str) -> str:
    """ICS DTSTART (YYYYMMDD or YYYYMMDDTHHMMSSZ) -> ISO-8601."""
    v = v.strip()
    if re.fullmatch(r"\d{8}", v):
        return f"{v[0:4]}-{v[4:6]}-{v[6:8]}"
    m = re.fullmatch(r"(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z?", v)
    if m:
        y, mo, d, h, mi, s = m.groups()
        return f"{y}-{mo}-{d}T{h}:{mi}:{s}Z" if v.endswith("Z") else f"{y}-{mo}-{d}T{h}:{mi}:{s}"
    return v


def _is_container(ev: dict[str, Any]) -> bool:
    return ev.get("UID", "").startswith("!")


def _recognise_flight(ev: dict[str, Any]) -> dict[str, Any] | None:
    iatas = _IATA_RE.findall(ev.get("SUMMARY", "") + " " + ev.get("DESCRIPTION", ""))
    if len(iatas) < 2:
        return None
    return {"@context": "http://schema.org", "@type": "FlightReservation",
            "reservationFor": {"@type": "Flight",
                "departureAirport": {"@type": "Airport", "iataCode": iatas[0]},
                "arrivalAirport": {"@type": "Airport", "iataCode": iatas[1]},
                "departureDay": _ics_dt(ev.get("DTSTART", ""))[:10]}}


def pair_and_recognise(vevents: list[dict[str, Any]]) -> list[tuple[dict[str, Any], str | None, datetime]]:
    """Return (minimal_jsonld, trip_id, context_date) for each recognised reservation.

    Container events become trip labels (handled by import_ics), not reservations. Hotel
    check-in/check-out VEVENTs are re-paired by their shared UID suffix into one lodging."""
    hotels: dict[str, dict[str, Any]] = {}
    out: list[tuple[dict[str, Any], str | None, datetime]] = []
    for ev in vevents:
        if _is_container(ev):
            continue
        tid = _trip_id(ev)
        cd = datetime.fromisoformat(_ics_dt(ev.get("DTSTART", "1970-01-01"))[:10])
        m = _HOTEL_UID_RE.match(ev.get("UID", ""))
        if m:
            side, key = m.groups()
            slot = hotels.setdefault(key, {"trip": tid, "cd": cd})
            when = _ics_dt(ev.get("DTSTART", ""))
            slot["checkin" if side == "0" else "checkout"] = when
            slot["name"] = (ev.get("DESCRIPTION") or ev.get("SUMMARY", "")).split("\n")[0]
            continue
        flight = _recognise_flight(ev)
        if flight:
            out.append((flight, tid, cd))
    for slot in hotels.values():
        name = (slot.get("name") or "").replace("Check in to ", "").replace("Check out from ", "").strip()
        out.append(({"@context": "http://schema.org", "@type": "LodgingReservation",
                     "reservationFor": {"@type": "LodgingBusiness", "name": name},
                     "checkinTime": slot.get("checkin"), "checkoutTime": slot.get("checkout")},
                    slot.get("trip"), slot.get("cd")))
    return out


def import_ics(path: Path) -> dict[str, int]:
    import json
    vevents = parse_vevents(path.read_text(encoding="utf-8"))
    n_res = 0
    trip_ids: set[str] = set()
    for minimal, tid, cd in pair_and_recognise(vevents):
        enriched = extract(json.dumps([minimal]).encode(), cd) or [minimal]
        for jsonld in enriched:
            source_id = f"ics:{path.name}:{n_res}"
            commands.observe(jsonld, fidelity="kayak-ics", source_id=source_id,
                             received_at=cd.isoformat(),
                             source_meta={"path": str(path), "kind": "kayak-ics"})
            n_res += 1
        if tid:
            trip_ids.add(tid)
    # Trip labels from the container events.
    for ev in vevents:
        if _is_container(ev):
            with store.get_db() as conn:
                store.upsert_trip(conn, ev["UID"].split("@")[0],
                                  name=ev.get("SUMMARY"),
                                  start_date=_ics_dt(ev.get("DTSTART", ""))[:10] or None,
                                  end_date=_ics_dt(ev.get("DTEND", ""))[:10] or None)
    return {"reservations": n_res, "trips": len({e["UID"].split("@")[0]
            for e in vevents if _is_container(e)})}
