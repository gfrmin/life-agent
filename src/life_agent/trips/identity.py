"""Content-keyed reservation identity — keyed on the booked thing, NOT its provenance.

Mirrors tasks.events.assertion_identity: two observations of the same booking (Kayak export
vs the airline's own email) share an identity and dedupe. Confirmation number and vendor
eventId are deliberately excluded — a confirmation number is neither necessary (58% coverage)
nor sufficient (one reference covers an outbound + a return); eventId is pure provenance.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

_WS = re.compile(r"\s+")
_SEP = "\x1f"

_FLIGHTLIKE = frozenset({"FlightReservation", "TrainReservation", "BusReservation"})


def res_type(jsonld: dict[str, Any]) -> str:
    """The schema.org reservation @type, e.g. 'FlightReservation'."""
    t = jsonld.get("@type", "")
    return t if isinstance(t, str) else ""


def _norm(s: Any) -> str:
    return _WS.sub(" ", str(s or "")).strip()


def _reservation_for(jsonld: dict[str, Any]) -> list[dict[str, Any]]:
    """`reservationFor` may be one object or a list of segments; always return a list."""
    rf = jsonld.get("reservationFor")
    if isinstance(rf, list):
        return [s for s in rf if isinstance(s, dict)]
    if isinstance(rf, dict):
        return [rf]
    return []


def _endpoint(place: Any) -> str:
    """A segment endpoint's identifier: an IATA code for a flight, or a station/stop name
    for a train/bus — whichever the reservation carries."""
    if not isinstance(place, dict):
        return ""
    return _norm(place.get("iataCode") or place.get("name"))


def _segment_key(seg: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        _endpoint(seg.get("departureAirport") or seg.get("departureStation") or seg.get("departureBusStop")),
        _endpoint(seg.get("arrivalAirport") or seg.get("arrivalStation") or seg.get("arrivalBusStop")),
        _norm(seg.get("departureTime")),
        _norm(seg.get("flightNumber") or seg.get("trainNumber") or seg.get("busNumber")),
    )


def content_key(jsonld: dict[str, Any]) -> tuple[Any, ...]:
    """The identity-bearing tuple for a reservation. Defensive: missing fields become ''
    rather than raising, because the degenerate cases (a segment with no flight number, a
    hotel with no property id) are real and must still key stably."""
    t = res_type(jsonld)
    if t in _FLIGHTLIKE:
        segs = tuple(_segment_key(s) for s in _reservation_for(jsonld))
        return (segs,)
    if t == "LodgingReservation":
        lodging = _reservation_for(jsonld)
        place = lodging[0] if lodging else {}
        pid = _norm(place.get("@id") or place.get("identifier") or place.get("name"))
        return (pid, _norm(jsonld.get("checkinTime")), _norm(jsonld.get("checkoutTime")))
    # Everything else (restaurant, event, generic): title + start + end.
    place0 = (_reservation_for(jsonld) or [{}])[0]
    title = _norm(place0.get("name") or jsonld.get("name"))
    return (title, _norm(jsonld.get("startTime")), _norm(jsonld.get("endTime")))


def reservation_identity(jsonld: dict[str, Any]) -> str:
    """Stable sha256 identity over (res_type, content_key). Determinism comes from fixed
    tuple field order in content_key; sort_keys=True future-proofs against dict-valued keys."""
    payload = _SEP.join([res_type(jsonld), json.dumps(content_key(jsonld), sort_keys=True)])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
