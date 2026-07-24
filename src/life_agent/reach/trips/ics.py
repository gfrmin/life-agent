# src/life_agent/reach/trips/ics.py
"""Hand-written iCalendar (RFC 5545) serialisation of the trips projection.

A reach surface is a dumb transport over the read-model, and that is the decisive reason to NOT
reuse the kitinerary subprocess here: the extract() seam returns [] on ANY failure and never
raises, so routing it into a calendar feed would silently hand the phone an EMPTY calendar exactly
when it is offline (airplane mode) and cannot be debugged. A pure function over the already-
flattened projection columns cannot fail that way, needs no 60s-timeout subprocess in the single-
threaded serve loop, and re-derives nothing (store.py already extracted start/end/title/confirm/
iata from the verbatim JSON-LD). The cost we accept — owning folding, escaping, and the naive-vs-
offset datetime rule — is small and fully unit-tested.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

PRODID = "-//life-agent//trips//EN"


def _escape(text: str) -> str:
    """Escape a TEXT value per RFC 5545 §3.3.11 (backslash first; then ; and ,; CR and CRLF folded
    to LF; finally newline to the literal \\n)."""
    return (text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
                .replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\\n"))


def _fold(line: str) -> str:
    """Fold one content line to ≤75 octets, continuations prefixed with a space (RFC 5545 §3.1).

    Measured in UTF-8 octets but split only on character boundaries, so a multi-byte glyph is
    never cut across a fold (each physical line stays valid UTF-8)."""
    if len(line.encode("utf-8")) <= 75:
        return line
    chunks: list[str] = []
    cur = ""
    budget = 75  # continuation lines carry a leading space, so they get 74
    for ch in line:
        if len((cur + ch).encode("utf-8")) > budget:
            chunks.append(cur)
            cur, budget = ch, 74
        else:
            cur += ch
    chunks.append(cur)
    return "\r\n ".join(chunks)


def _dt(value: str | None) -> str | None:
    """Render an ISO datetime as an iCalendar DATE-TIME.

    Offset-aware → UTC 'YYYYMMDDTHHMMSSZ'. Naive → floating 'YYYYMMDDTHHMMSS' (no Z, no TZID),
    which sidesteps VTIMEZONE entirely. None/unparseable → None (the caller skips the field)."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    return dt.strftime("%Y%m%dT%H%M%S")


def _dtstamp(value: str | None) -> str:
    """DTSTAMP (RFC 5545 §3.8.7.2) — always UTC DATE-TIME. Derived from reservation's stable
    ``received_at`` so the feed stays byte-identical across fetches (no spurious re-syncs);
    naive ``received_at`` is treated as UTC. Falls back to a fixed epoch when absent/unparseable."""
    if value:
        try:
            dt = datetime.fromisoformat(value)
        except ValueError:
            dt = None
        if dt is not None:
            if dt.tzinfo is not None:
                dt = dt.astimezone(UTC)
            return dt.strftime("%Y%m%dT%H%M%SZ")
    return "19700101T000000Z"


def _summary(r: dict[str, Any]) -> str:
    dep, arr = r.get("dep_iata"), r.get("arr_iata")
    if dep and arr:
        route = f"{dep}→{arr}"  # DEP→ARR
        prov = r.get("provider")
        return f"{route} {prov}" if prov else route
    return r.get("title") or r.get("provider") or "Reservation"


def _vevent(r: dict[str, Any]) -> list[str] | None:
    start = _dt(r.get("start_iso"))
    if start is None:
        return None  # a reservation with no usable start cannot be a calendar event
    lines = [
        "BEGIN:VEVENT",
        f"UID:{r['identity']}",  # identity is content-keyed alphanumeric — no escaping needed
        f"DTSTAMP:{_dtstamp(r.get('received_at'))}",
        f"DTSTART:{start}",
    ]
    end = _dt(r.get("end_iso"))
    if end is not None:
        lines.append(f"DTEND:{end}")
    lines.append(f"SUMMARY:{_escape(_summary(r))}")
    location = r.get("arr_iata") or r.get("title")
    if location:
        lines.append(f"LOCATION:{_escape(str(location))}")
    if r.get("confirmation"):
        lines.append(f"DESCRIPTION:{_escape(str(r['confirmation']))}")
    if r.get("cancelled"):
        lines.append("STATUS:CANCELLED")
    lines.append("END:VEVENT")
    return lines


def to_ics(reservations: list[dict[str, Any]]) -> str:
    """Serialise reservations to one VCALENDAR string (CRLF line endings, folded)."""
    body = ["BEGIN:VCALENDAR", "VERSION:2.0", f"PRODID:{PRODID}", "CALSCALE:GREGORIAN"]
    for r in reservations:
        vevent = _vevent(r)
        if vevent is not None:
            body.extend(vevent)
    body.append("END:VCALENDAR")
    return "".join(_fold(line) + "\r\n" for line in body)
