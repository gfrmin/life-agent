# Trips Reach Surfaces Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the imported trips projection two read-only reach surfaces — a web timeline and a subscribable ICS calendar feed — so the itinerary is usable on any device and offline, making Kayak Trips redundant.

**Architecture:** A new `life_agent.reach.trips` package, parallel to the GTD `reach.web`. A pure `ics.to_ics(reservations) -> str` hand-writes RFC-5545 VEVENTs from the projection's already-flattened columns (no kitinerary subprocess — a reach surface is a dumb transport, and the `extract()` seam's "return `[]` on any failure, never raise" contract would silently hand the phone an empty calendar mid-flight). A single-threaded stdlib `http.server` serves one self-contained `index.html` plus a small GET-only JSON API over `trips.store`, and publishes the feed at `/calendar.ics`.

**Tech Stack:** Python 3.13 stdlib only (`http.server`, `datetime`, `urllib.parse`, `json`, `functools.lru_cache`); pytest; vanilla HTML/CSS/JS (no framework). Reads through the existing `life_agent.trips.store` query API.

## Global Constraints

- **Python `>=3.13,<3.14`**; ruff (line-length 100) and mypy must stay clean on all new files.
- **Reach, not truth** — surfaces read only through `trips.store`'s existing functions (`timeline`, `now_next`, `search`); they never touch the ledger or SQLite directly, and never write.
- **Read-only** — no POST/mutation routes; trips mutations come from ingest, not the web.
- **No PII / no personal data in code** — host, port, and paths are env-config, never literals. Host `LIFE_AGENT_TRIPS_WEB_HOST` (default `0.0.0.0`), port `LIFE_AGENT_TRIPS_WEB_PORT` (default `8800`), read directly in `server.py` via `os.environ` exactly as `reach/web/server.py` reads its own.
- **No auth** — the network boundary (Tailscale) is the only gate, same posture as `reach/web` and the bridge. Do not add auth; do not expose publicly.
- **No `user_id`** — the trips ledger is single-owner (the `reservation` row has no user column); `store.timeline()/now_next()/search()` take no id. Nothing is resolved from the keyring.
- **Fixtures synthetic by construction** — tests use hand-built reservation dicts / synthetic JSON-LD, never scrubbed real captures.
- **iCalendar output** — CRLF (`\r\n`) line endings, content lines folded to ≤75 octets, TEXT values escaped per RFC 5545 §3.3.11.

---

### Task 1: ICS serializer (`reach/trips/ics.py`)

The pure, heavily-tested core: reservation dicts → one VCALENDAR string. No I/O, no subprocess, no dependency on the server.

**Files:**
- Create: `src/life_agent/reach/trips/__init__.py`
- Create: `src/life_agent/reach/trips/ics.py`
- Test: `tests/test_trips_ics.py`

**Interfaces:**
- Consumes: reservation row dicts as returned by `life_agent.trips.store.timeline()` — each has keys `identity, res_type, title, start_iso, start_tz, end_iso, end_tz, confirmation, provider, dep_iata, arr_iata, lat, lon, cancelled` (plus others this task ignores). `cancelled` is a `bool`; every other field is `str | None`.
- Produces: `to_ics(reservations: list[dict[str, Any]]) -> str` — a full `BEGIN:VCALENDAR … END:VCALENDAR` string, CRLF-terminated and folded. Also module constant `PRODID = "-//life-agent//trips//EN"`.

- [ ] **Step 1: Create the package marker**

Create `src/life_agent/reach/trips/__init__.py`:

```python
"""Trips reach surfaces: a read-only web timeline and a subscribable ICS calendar feed."""
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_trips_ics.py`:

```python
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run (from the worktree root): `python -m pytest tests/test_trips_ics.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'life_agent.reach.trips.ics'`

- [ ] **Step 4: Write the implementation**

Create `src/life_agent/reach/trips/ics.py`:

```python
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

from datetime import datetime, timezone
from typing import Any

PRODID = "-//life-agent//trips//EN"


def _escape(text: str) -> str:
    """Escape a TEXT value per RFC 5545 §3.3.11 (backslash first, then ; , and newline)."""
    return (text.replace("\\", "\\\\").replace(";", "\\;")
                .replace(",", "\\,").replace("\n", "\\n"))


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
        return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return dt.strftime("%Y%m%dT%H%M%S")


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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_trips_ics.py -q`
Expected: PASS (16 passed)

- [ ] **Step 6: Lint and type-check**

Run: `ruff check src/life_agent/reach/trips tests/test_trips_ics.py && mypy src/life_agent/reach/trips/ics.py`
Expected: no ruff errors; `Success: no issues found` from mypy.

- [ ] **Step 7: Commit**

```bash
git add src/life_agent/reach/trips/__init__.py src/life_agent/reach/trips/ics.py tests/test_trips_ics.py
git commit -m "feat(trips): hand-written iCalendar serialiser for the trips projection"
```

---

### Task 2: Timeline page (`reach/trips/index.html`)

One self-contained page reusing GTD's CSS variables, so both surfaces read as one system: a pinned now/next header, a search box, and a reverse-chron timeline grouped by year. Read-only. Its regression guard is the page↔server endpoint contract (a renamed endpoint must break a test).

**Files:**
- Create: `src/life_agent/reach/trips/index.html`
- Test: `tests/test_trips_page.py`

**Interfaces:**
- Consumes (as fetch string literals, not Python): `GET /api/now_next` → `{now: [...], next: {...}|null}`; `GET /api/timeline` → `{reservations: [...]}`; `GET /api/search?q=…` → `{reservations: [...]}`; `GET /calendar.ics` (linked). Each reservation object carries `res_type, title, start_iso, confirmation, provider, dep_iata, arr_iata, cancelled`. These paths and the response shapes are the contract Task 3 must satisfy.
- Produces: a static asset served verbatim by Task 3's `/` route.

- [ ] **Step 1: Write the failing test**

Create `tests/test_trips_page.py`:

```python
"""The trips page is a static asset; this guards the page↔server endpoint contract so a renamed
or dropped endpoint on either side fails a test rather than silently breaking the surface."""
from __future__ import annotations

from pathlib import Path

_PAGE = (Path(__file__).resolve().parents[1]
         / "src/life_agent/reach/trips/index.html").read_text(encoding="utf-8")


def test_page_is_html() -> None:
    assert _PAGE.startswith("<!DOCTYPE html>")
    assert "<title>Trips</title>" in _PAGE


def test_page_calls_every_server_endpoint() -> None:
    for endpoint in ("/api/timeline", "/api/now_next", "/api/search?q=", "/calendar.ics"):
        assert endpoint in _PAGE, f"page no longer references {endpoint}"


def test_page_renders_untrusted_fields_with_textcontent() -> None:
    # All reservation fields are untrusted; they must go through textContent (via el()), and
    # innerHTML may only ever clear a container to empty — never inject a value.
    import re
    assert "textContent" in _PAGE
    for assigned in re.findall(r"\.innerHTML\s*=\s*([^;]+);", _PAGE):
        assert assigned.strip() == '""', f"innerHTML assigned a non-empty value: {assigned!r}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_trips_page.py -q`
Expected: FAIL — `FileNotFoundError: … src/life_agent/reach/trips/index.html`

- [ ] **Step 3: Write the page**

Create `src/life_agent/reach/trips/index.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark light">
<title>Trips</title>
<style>
  :root {
    --bg: #14171c; --panel: #1c2027; --panel2: #22272f; --line: #2c333d;
    --fg: #e6e9ee; --muted: #8b95a3; --accent: #6ea8fe; --today: #ffd166;
    --danger: #e5646e; --ok: #5bcf8a;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--fg);
    font: 15px/1.4 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  }
  header {
    position: sticky; top: 0; z-index: 5; background: var(--bg);
    border-bottom: 1px solid var(--line); padding: 12px 16px;
  }
  h1 { font-size: 17px; margin: 0 0 10px; font-weight: 600; display: flex; gap: 8px; align-items: baseline; }
  h1 .dot { color: var(--muted); font-weight: 400; font-size: 13px; }
  h1 .feed { margin-left: auto; font-size: 12px; }
  a.feed { color: var(--accent); text-decoration: none; border: 1px solid #2f3f5c; border-radius: 999px; padding: 2px 10px; }
  a.feed:hover { background: var(--panel2); }
  .pins { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; }
  .pin { background: var(--panel2); border: 1px solid var(--line); border-radius: 10px; padding: 8px 10px; font-size: 13px; }
  .pin.next { border-color: #2f3f5c; }
  .pin .k { color: var(--muted); text-transform: uppercase; font-size: 11px; letter-spacing: .06em; margin-right: 6px; }
  input[type=search] {
    width: 100%; padding: 9px 11px; border-radius: 8px;
    border: 1px solid var(--line); background: var(--panel2); color: var(--fg); font: inherit;
  }
  main { padding: 16px; max-width: 760px; margin: 0 auto; }
  .year { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .06em; margin: 18px 4px 8px; }
  .res {
    background: var(--panel); border: 1px solid var(--line); border-radius: 12px;
    padding: 10px 12px; margin-bottom: 8px; display: flex; gap: 10px; align-items: baseline;
  }
  .res.cancelled { opacity: .55; }
  .res.cancelled .route { text-decoration: line-through; }
  .icon { font-size: 15px; width: 1.4em; text-align: center; flex: 0 0 auto; }
  .rbody { flex: 1 1 auto; min-width: 0; }
  .route { font-weight: 600; word-break: break-word; }
  .sub { color: var(--muted); font-size: 13px; margin-top: 3px; display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
  .when { color: var(--fg); white-space: nowrap; font-size: 13px; }
  .badge { font-size: 11px; color: var(--muted); border: 1px solid var(--line); border-radius: 999px; padding: 1px 8px; }
  .badge.x { color: var(--danger); border-color: var(--danger); }
  .empty { color: var(--muted); padding: 20px 4px; opacity: .6; }
</style>
</head>
<body>
<header>
  <h1>Trips <span class="dot" id="summary"></span>
    <a class="feed" id="feed" href="/calendar.ics">calendar feed</a></h1>
  <div class="pins" id="pins"></div>
  <input type="search" id="q" placeholder="Search flights, hotels, confirmation…" autocomplete="off">
</header>
<main id="list"></main>

<script>
"use strict";

// Map a schema.org reservation @type substring to a glyph. Unknown types get a neutral dot.
const ICONS = { flight: "✈", lodging: "🛏", train: "🚆",
                bus: "🚌", rental: "🚗", event: "🎫",
                food: "🍽" };

async function api(path) {
  const res = await fetch(path);
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new Error((data && data.error) || (res.status + " " + res.statusText));
  return data;
}

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = text;  // textContent = XSS-safe (every field is untrusted)
  return n;
}

function icon(type) {
  const t = (type || "").toLowerCase();
  for (const k in ICONS) if (t.includes(k)) return ICONS[k];
  return "•";
}

function routeText(r) {
  if (r.dep_iata && r.arr_iata) return r.dep_iata + " → " + r.arr_iata;
  return r.title || r.provider || "Reservation";
}

function whenText(r) {
  // Show the stored calendar date + HH:MM verbatim — no tz math; the string is the record.
  if (!r.start_iso) return "";
  const d = r.start_iso.slice(0, 10), t = r.start_iso.slice(11, 16);
  return t ? d + " " + t : d;
}

function resNode(r) {
  const node = el("div", "res" + (r.cancelled ? " cancelled" : ""));
  node.appendChild(el("div", "icon", icon(r.res_type)));
  const body = el("div", "rbody");
  body.appendChild(el("div", "route", routeText(r)));
  const sub = el("div", "sub");
  if (r.provider) sub.appendChild(el("span", null, r.provider));
  if (r.confirmation) sub.appendChild(el("span", "badge", r.confirmation));
  if (r.cancelled) sub.appendChild(el("span", "badge x", "cancelled"));
  if (sub.childNodes.length) body.appendChild(sub);
  node.appendChild(body);
  node.appendChild(el("div", "when", whenText(r)));
  return node;
}

function render(reservations) {
  const list = document.getElementById("list");
  list.innerHTML = "";
  if (!reservations.length) { list.appendChild(el("div", "empty", "No reservations.")); return; }
  let year = null;
  for (const r of reservations) {
    const y = (r.start_iso || "").slice(0, 4) || "—";
    if (y !== year) { year = y; list.appendChild(el("div", "year", year)); }
    list.appendChild(resNode(r));
  }
}

function pin(kind, r) {
  const p = el("div", "pin" + (kind === "next" ? " next" : ""));
  p.appendChild(el("span", "k", kind));
  const when = whenText(r);
  p.appendChild(el("span", null, routeText(r) + (when ? " · " + when : "")));
  return p;
}

async function loadPins() {
  const pins = document.getElementById("pins");
  pins.innerHTML = "";
  try {
    const nn = await api("/api/now_next");
    for (const r of (nn.now || [])) pins.appendChild(pin("now", r));
    if (nn.next) pins.appendChild(pin("next", nn.next));
  } catch (e) { /* pins are non-critical; the timeline still renders without them */ }
}

async function loadTimeline() {
  const data = await api("/api/timeline");
  const rows = data.reservations || [];
  render(rows);
  document.getElementById("summary").textContent = "· " + rows.length + " reservations";
}

let searchTimer = null;
document.getElementById("q").addEventListener("input", (ev) => {
  const q = ev.target.value.trim();
  clearTimeout(searchTimer);
  searchTimer = setTimeout(async () => {
    if (!q) { loadTimeline(); return; }
    try {
      const data = await api("/api/search?q=" + encodeURIComponent(q));
      const rows = data.reservations || [];
      render(rows);
      document.getElementById("summary").textContent = "· " + rows.length + " match";
    } catch (e) { /* keep the current view on a failed search */ }
  }, 200);
});

loadPins();
loadTimeline();
</script>
</body>
</html>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_trips_page.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/life_agent/reach/trips/index.html tests/test_trips_page.py
git commit -m "feat(trips): read-only timeline page (now/next, search, year-grouped)"
```

---

### Task 3: Web server (`reach/trips/server.py`)

The transport: a single-threaded HTTP/1.0 stdlib server mirroring `reach/web/server.py`, GET-only, no `user_id`, serving the page + JSON API + the ICS feed. `dispatch()` is tested without a socket; one loopback fixture proves the wire.

**Files:**
- Create: `src/life_agent/reach/trips/server.py`
- Test: `tests/test_trips_web.py`

**Interfaces:**
- Consumes: `life_agent.reach.trips.ics.to_ics(reservations)` (Task 1); `src/life_agent/reach/trips/index.html` (Task 2); `life_agent.trips.store.timeline()`, `.now_next(now_iso: str)`, `.search(term: str)`, `.init_db()`, `.get_db()`, and module attr `store.DB_PATH` (monkeypatched in tests).
- Produces: `dispatch(method: str, path: str, body: bytes) -> tuple[int, Payload | str]` (pure, socket-free); `class WebServer(HTTPServer)` with `__init__(self, host=HOST, port=PORT)`; `main() -> None`. `Payload = dict[str, Any]`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_trips_web.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_trips_web.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'life_agent.reach.trips.server'`

- [ ] **Step 3: Write the implementation**

Create `src/life_agent/reach/trips/server.py`:

```python
# src/life_agent/reach/trips/server.py
"""Trips timeline — a read-only reach channel over the trips projection.

Same shape and rationale as life_agent/reach/web/server.py (read its docstring): a tiny single-
threaded, HTTP/1.0 stdlib http.server serving one self-contained page plus a small JSON API,
reachable only over Tailscale (the network boundary is the only gate — no auth). Two differences
from the GTD sibling:

* **Read-only.** Trips mutations (observe/cancel/amend/supersede) come from ingest, never a
  button, so there is no command seam and no POST routes — only GET reads over trips.store.
* **No user_id.** The trips ledger is single-owner (the reservation row has no user column), so
  store.timeline()/now_next()/search() take no id and nothing is resolved from the keyring.

It also publishes GET /calendar.ics — a subscribable feed (ics.to_ics over the current timeline)
so the itinerary lands in the phone's native calendar and works offline / in airplane mode, where
the Tailscale origin is unreachable.
"""
from __future__ import annotations

import os
import traceback
from datetime import datetime
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, HTTPServer
from json import dumps
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from life_agent.reach.trips.ics import to_ics
from life_agent.trips import store

HOST = os.environ.get("LIFE_AGENT_TRIPS_WEB_HOST", "0.0.0.0")
PORT = int(os.environ.get("LIFE_AGENT_TRIPS_WEB_PORT", "8800"))  # after GTD 8797/bridge 8798/daemon 8799

Payload = dict[str, Any]
_INDEX = Path(__file__).parent / "index.html"


class WebError(Exception):
    """A request the server rejects with a 4xx. Carries the status; dispatch maps it to a JSON
    error so a bad request never crashes the accept loop."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


class Ical(str):
    """Marker str subclass so the handler sends text/calendar (not text/html) for the feed."""


@lru_cache(maxsize=1)
def _index_html() -> str:
    """The self-contained page, read once and cached (edit-then-restart, like any static asset)."""
    return _INDEX.read_text(encoding="utf-8")


def dispatch(method: str, path: str, body: bytes) -> tuple[int, Payload | str]:
    """Route one request to (status, payload). A str payload is HTML (the page) or iCal (the feed,
    an Ical instance); a dict is JSON. Holds no state; every 4xx is returned, never raised past
    here, so a bad request never crashes the loop. `body` is unused (read-only surface) but kept
    for parity with the GTD dispatch signature."""
    try:
        if method != "GET":
            raise WebError(405, f"method {method!r} not allowed")
        parts = urlsplit(path)
        route = parts.path
        if route == "/":
            return 200, _index_html()
        if route == "/ready":
            return 200, {"status": "ok"}
        if route == "/api/timeline":
            return 200, {"reservations": store.timeline()}
        if route == "/api/now_next":
            return 200, store.now_next(datetime.now().isoformat())
        if route == "/api/search":
            q = parse_qs(parts.query).get("q", [""])[0]
            return 200, {"reservations": store.search(q) if q else []}
        if route == "/calendar.ics":
            return 200, Ical(to_ics(store.timeline()))
        raise WebError(404, f"no GET endpoint {route!r}")
    except WebError as e:
        return e.status, {"error": e.message}


class _Handler(BaseHTTPRequestHandler):
    # protocol_version left at the HTTP/1.0 default on purpose (see reach/web/server.py docstring).

    def _respond(self, status: int, payload: Payload | str) -> None:
        if isinstance(payload, Ical):
            data, ctype = payload.encode("utf-8"), "text/calendar; charset=utf-8"
        elif isinstance(payload, str):
            data, ctype = payload.encode("utf-8"), "text/html; charset=utf-8"
        else:
            data, ctype = dumps(payload).encode("utf-8"), "application/json"
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        try:
            status, payload = dispatch("GET", self.path, b"")
        except Exception:
            # A seam failure (locked/corrupt DB, disk full) is logged to the journal and returned
            # as a GENERIC 500 — the raw exception (which may embed the KB path or SQL) is never
            # leaked to the client, which is unauthenticated on the tailnet.
            traceback.print_exc()
            status, payload = 500, {"error": "internal error"}
        self._respond(status, payload)

    def do_POST(self) -> None:
        self._respond(405, {"error": "method 'POST' not allowed"})  # read-only surface

    def log_message(self, format: str, *args: Any) -> None:
        return  # quiet: a personal backend, not an access log


class WebServer(HTTPServer):
    """Single-threaded by design (see reach/web/server.py): connection-per-request over HTTP/1.0,
    so a polling browser never stalls the accept loop."""

    def __init__(self, host: str = HOST, port: int = PORT) -> None:
        super().__init__((host, port), _Handler)


def main() -> None:
    store.init_db()  # idempotent; the read-model normally already exists (the trips CLI created it)
    server = WebServer()
    print(f"life-agent trips timeline → http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_trips_web.py -q`
Expected: PASS (12 passed)

- [ ] **Step 5: Lint and type-check the whole package**

Run: `ruff check src/life_agent/reach/trips tests/test_trips_web.py && mypy src/life_agent/reach/trips`
Expected: no ruff errors; `Success: no issues found` from mypy.

- [ ] **Step 6: Run the full trips + reach test slice**

Run: `python -m pytest tests/test_trips_ics.py tests/test_trips_page.py tests/test_trips_web.py tests/trips -q`
Expected: PASS (all green — the new surfaces plus the untouched trips core).

- [ ] **Step 7: Commit**

```bash
git add src/life_agent/reach/trips/server.py tests/test_trips_web.py
git commit -m "feat(trips): read-only web timeline + ICS feed server (port 8800)"
```

---

## Notes for the implementer

- **Run everything from the worktree root** (the checked-out `trips-surfaces` branch) so relative test paths and the `src/` layout resolve.
- **Do not** add a `[project.scripts]` console entry — `reach/web` and `reach/digest` are run via `python -m`, and the trips surface follows suit: `python -m life_agent.reach.trips.server`.
- **Do not** route `/calendar.ics` through the kitinerary `extract()` seam — the whole point (spec §Resolved decisions) is that a subprocess whose contract is "return `[]` on any failure, never raise" would silently serve an empty calendar offline. Keep it the pure `to_ics`.
- The `now_next` comparison over mixed offset/naive `start_iso` strings is approximate near timezone boundaries — a known, documented limitation carried from the trips core, not something to "fix" here.
