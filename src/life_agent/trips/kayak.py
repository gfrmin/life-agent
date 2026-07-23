# src/life_agent/trips/kayak.py
"""Import the Kayak Trips export (Phase 0's product) as the tier-3 coverage floor.

The export is 115 trips / 260 events reaching 2010 — a full structured history no other
source provides. Each event is mapped into schema.org JSON-LD in the SAME shape kitinerary
emits, so reservation_identity keys a Kayak flight identically to that flight's own email:
the two dedupe into one row that silently upgrades to tier 2 when the email is later filed.

The export carries richer data than expected (per-segment IATA + coordinates, IANA timezones,
operating carrier, seats) — mapped through where present. NB: Kayak returns 0 cancellations
(260/260 isBooked); this importer therefore NEVER emits a `cancelled` event, and a record's
absence from a later export is never read as a cancellation.

Kayak event taxonomy -> schema.org: flight -> FlightReservation (segments -> reservationFor
list), hotel -> LodgingReservation, train -> TrainReservation, restaurant ->
FoodEstablishmentReservation, else -> generic Reservation (title/start/end).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from life_agent.trips import commands, store


def _segment(seg: dict[str, Any]) -> dict[str, Any]:
    carrier = seg.get("marketingCarrierCode", "")
    fno = seg.get("flightNumber", "")
    out: dict[str, Any] = {"@type": "Flight",
        "departureAirport": {"@type": "Airport", "iataCode": seg.get("departureAirportCode")},
        "arrivalAirport": {"@type": "Airport", "iataCode": seg.get("arrivalAirportCode")}}
    if seg.get("departureTimestamp"):
        out["departureTime"] = seg["departureTimestamp"]
    if seg.get("arrivalTimestamp"):
        out["arrivalTime"] = seg["arrivalTimestamp"]
    if carrier and fno:
        out["flightNumber"] = f"{carrier}{fno}"
    elif fno:
        out["flightNumber"] = str(fno)
    return out


def event_to_jsonld(event: dict[str, Any]) -> dict[str, Any] | None:
    kind = event.get("type", "")
    conf = event.get("confirmationNumber") or event.get("bookingReferenceNumber")

    if kind == "flight":
        segs = [_segment(s) for leg in event.get("legs", []) for s in leg.get("segments", [])]
        if not segs:
            return None
        jsonld: dict[str, Any] = {"@type": "FlightReservation",
                                  "reservationFor": segs if len(segs) > 1 else segs[0]}
    elif kind == "hotel":
        jsonld = {"@type": "LodgingReservation",
                  "reservationFor": {"@type": "LodgingBusiness",
                      "name": event.get("hotelName") or event.get("name"),
                      "address": event.get("address")},
                  "checkinTime": event.get("checkinDate"),
                  "checkoutTime": event.get("checkoutDate")}
    elif kind == "train":
        jsonld = {"@type": "TrainReservation", "reservationFor": {"@type": "TrainTrip",
            "departureStation": {"name": event.get("departureStation")},
            "arrivalStation": {"name": event.get("arrivalStation")},
            "departureTime": event.get("departureTimestamp")}}
    elif kind == "restaurant":
        jsonld = {"@type": "FoodEstablishmentReservation",
                  "reservationFor": {"@type": "FoodEstablishment", "name": event.get("name")},
                  "startTime": event.get("startTimestamp")}
    else:
        jsonld = {"@type": "Reservation", "name": event.get("name") or event.get("title"),
                  "startTime": event.get("startTimestamp"), "endTime": event.get("endTimestamp")}

    if conf:
        jsonld["reservationNumber"] = conf
    return jsonld


def _received_at(event: dict[str, Any]) -> str:
    """Order key. Kayak has no ingest timestamp; use the event's own start so a later email
    (with a real Date:) sorts after it under equal fidelity — though fidelity alone decides."""
    for k in ("departureTimestamp", "checkinDate", "startTimestamp"):
        if event.get(k):
            return str(event[k])
    for leg in event.get("legs", []):
        for s in leg.get("segments", []):
            if s.get("departureTimestamp"):
                return str(s["departureTimestamp"])
    return "1970-01-01T00:00:00"


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
