# src/life_agent/trips/kayak.py
"""Import the Kayak Trips export (Phase 0's product) as the tier-3 coverage floor.

The export is 115 trips / 260 events reaching 2010 — a full structured history no other
source provides. Each event is mapped into schema.org JSON-LD in the SAME shape kitinerary
emits, so reservation_identity keys a Kayak flight identically to that flight's own email:
the two dedupe into one row that silently upgrades to tier 2 when the email is later filed.

Real export field names (profiled from the operator's actual export — an earlier version of
this module was written against an ASSUMED shape that didn't match; the acceptance test against
the real file caught it: every event fell to the generic branch, collapsing all 260 events to
one identical content key):
  - discriminator: `event["eventType"]` in {"flight", "hotel", "train", "custom", "restaurant"}
    (NOT `event["type"]`).
  - confirmation: `event["confirmationNumber"]` or
    `event["bookingDetail"]["bookingReferenceNumber"]`.
  - every event has `eventId` and `startDate` (naive local ISO); flights/trains also carry
    `startTimezone`/`endTimezone` (IANA) at the event level and per-segment
    `departureTimezone`/`arrivalTimezone`.
  - flight/train segments: `event["legs"][i]["segments"][j]`, each with `departureLocation` /
    `arrivalLocation` dicts (`airportCode`, `airportName`, `name` = city), `departureDate` /
    `arrivalDate` (naive local ISO), `departureTimezone` / `arrivalTimezone` (IANA). Flight
    segments add `airlineCode` + `flightNumber` — mapped as a BARE `flightNumber` plus a
    separate `airline: {iataCode}` dict (NOT concatenated), matching kitinerary's own shape
    (kitinerary emits `flightNumber="123"` and `airline={"iataCode":"EX",...}` separately; an
    earlier version of this module concatenated them into `"EX123"`, which meant a Kayak flight
    and its own email NEVER shared an identity — `identity._segment_key` keys on `flightNumber`
    verbatim, so a mismatched format silently broke the email-upgrade path for every real
    flight). Train segments have `carrier`, no flight number.
  - hotel: `hotelName`, `startDate` (check-in) / `endDate` (check-out), `address` dict
    (`longAddress`, `coordinates.{lat,lng}`), `confirmationNumber`.
  - custom: `eventTitle`, `startDate`/`endDate`.
  - restaurant: `placeDescription` is the name (`location.name` is typically empty), `startDate`.
  - trip level: `trip["tripId"]` is present; trip name/dates are NOT top-level in the real
    export, so `upsert_trip` is called with `name`/`start_date`/`end_date` all `None` —
    cosmetic only, deferred to Phase 1.

Per-segment timezones are resolved here: a Kayak segment's naive local timestamp + separate
IANA zone are combined into an offset-aware ISO string so identity keys it to the same instant
kitinerary derives from the email (see `_resolve_dt`). Coordinates, seats, and operating carrier
remain deferred to kitinerary enrichment on the email-upgrade path. NB: Kayak returns 0
cancellations (260/260 isBooked); this importer therefore NEVER emits a `cancelled` event, and a
record's absence from a later export is never read as a cancellation.

Kayak event taxonomy -> schema.org: flight -> FlightReservation (segments -> reservationFor
list), train -> TrainReservation (segments -> reservationFor list), hotel ->
LodgingReservation, restaurant -> FoodEstablishmentReservation, else (custom/unknown) ->
generic Reservation (title/start/end) — the else branch never returns None, so nothing is
silently dropped even for an eventType this module doesn't yet know about.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from life_agent.trips import commands, store


def _resolve_dt(ts: str | None, tz: str | None) -> str | None:
    """Combine a naive Kayak timestamp with its IANA zone into an offset-aware ISO string, so
    identity keys it to the same instant kitinerary derives from the email. Already-aware
    timestamps and missing/unknown zones are returned unchanged. Never raises."""
    if not ts:
        return ts
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return ts
    if dt.tzinfo is not None or not tz:
        return ts
    try:
        return dt.replace(tzinfo=ZoneInfo(tz)).isoformat()
    except Exception:
        return ts


def _segment(seg: dict[str, Any]) -> dict[str, Any]:
    dep = seg.get("departureLocation") or {}
    arr = seg.get("arrivalLocation") or {}
    out: dict[str, Any] = {"@type": "Flight",
        "departureAirport": {"@type": "Airport", "iataCode": dep.get("airportCode"),
                             "name": dep.get("airportName") or dep.get("name")},
        "arrivalAirport": {"@type": "Airport", "iataCode": arr.get("airportCode"),
                           "name": arr.get("airportName") or arr.get("name")}}
    dt = _resolve_dt(seg.get("departureDate"), seg.get("departureTimezone"))
    at = _resolve_dt(seg.get("arrivalDate"), seg.get("arrivalTimezone"))
    if dt:
        out["departureTime"] = dt
    if at:
        out["arrivalTime"] = at
    fn = seg.get("flightNumber") or ""
    if fn:
        out["flightNumber"] = str(fn)                       # bare number, matching kitinerary
    ac = seg.get("airlineCode")
    if ac:
        out["airline"] = {"@type": "Airline", "iataCode": ac}   # carrier separate, like kitinerary
    return out


def _station_segment(seg: dict[str, Any]) -> dict[str, Any]:
    dep = seg.get("departureLocation") or {}
    arr = seg.get("arrivalLocation") or {}
    dep_name = dep.get("name") or dep.get("airportName")
    arr_name = arr.get("name") or arr.get("airportName")
    out: dict[str, Any] = {"@type": "TrainTrip",
        "departureStation": {"@type": "TrainStation", "name": dep_name},
        "arrivalStation": {"@type": "TrainStation", "name": arr_name}}
    dt = _resolve_dt(seg.get("departureDate"), seg.get("departureTimezone"))
    at = _resolve_dt(seg.get("arrivalDate"), seg.get("arrivalTimezone"))
    if dt:
        out["departureTime"] = dt
    if at:
        out["arrivalTime"] = at
    return out


def event_to_jsonld(event: dict[str, Any]) -> dict[str, Any] | None:
    kind = event.get("eventType", "")
    booking = event.get("bookingDetail") or {}
    conf = event.get("confirmationNumber") or booking.get("bookingReferenceNumber")
    if kind == "flight":
        segs = [_segment(s) for leg in event.get("legs", []) for s in leg.get("segments", [])]
        if not segs:
            return None
        jsonld: dict[str, Any] = {"@type": "FlightReservation",
                                  "reservationFor": segs if len(segs) > 1 else segs[0]}
    elif kind == "train":
        segs = [_station_segment(s)
                for leg in event.get("legs", []) for s in leg.get("segments", [])]
        if not segs:
            return None
        jsonld = {"@type": "TrainReservation", "reservationFor": segs if len(segs) > 1 else segs[0]}
    elif kind == "hotel":
        addr = event.get("address") or {}
        jsonld = {"@type": "LodgingReservation",
                  "reservationFor": {"@type": "LodgingBusiness", "name": event.get("hotelName"),
                                     "address": addr.get("longAddress")},
                  "checkinTime": event.get("startDate"), "checkoutTime": event.get("endDate")}
    elif kind == "restaurant":
        location = event.get("location") or {}
        name = event.get("placeDescription") or location.get("name")
        jsonld = {"@type": "FoodEstablishmentReservation",
                  "reservationFor": {"@type": "FoodEstablishment", "name": name},
                  "startTime": event.get("startDate")}
    else:  # custom / unknown -> generic (never None, so nothing is silently dropped)
        name = event.get("eventTitle") or event.get("name") or event.get("placeDescription")
        jsonld = {"@type": "Reservation", "name": name,
                  "startTime": event.get("startDate"), "endTime": event.get("endDate")}
    if conf:
        jsonld["reservationNumber"] = conf
    return jsonld


def _received_at(event: dict[str, Any]) -> str:
    return str(event.get("startDate") or "1970-01-01T00:00:00")


def import_export(path: Path) -> dict[str, int]:
    data = json.loads(path.read_text(encoding="utf-8"))
    trips = data.get("trips", data if isinstance(data, list) else [])
    n_res = n_skip = 0
    trip_ids: set[str] = set()
    for trip in trips:
        tid = trip.get("tripId") or trip.get("id")
        if tid:
            trip_ids.add(tid)
            with store.get_db() as conn:
                store.upsert_trip(conn, tid, name=trip.get("name"),
                                  start_date=trip.get("startDate"), end_date=trip.get("endDate"))
        for event in trip.get("events", []):
            jsonld = event_to_jsonld(event)
            if jsonld is None:
                n_skip += 1
                continue
            source_id = f"kayak:{event.get('eventId', n_res)}"
            commands.observe(jsonld, fidelity="kayak-api", source_id=source_id,
                             received_at=_received_at(event),
                             source_meta={"kind": "kayak-api"})
            n_res += 1
    return {"trips": len(trip_ids), "reservations": n_res, "skipped": n_skip}
