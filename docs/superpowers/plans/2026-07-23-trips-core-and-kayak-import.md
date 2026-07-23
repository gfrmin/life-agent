# Trips Core + Kayak Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up `life_agent.trips` — an event-sourced itinerary faculty that imports the Kayak export as a full historical timeline (tier `kayak-api`) and lets a single filed confirmation email silently upgrade any record (tier `email-kitinerary`), all queryable from a `trips` CLI.

**Architecture:** Mirrors `life_agent.tasks` exactly — an append-only JSONL event ledger is the truth (`truth = fold(events)`), and a rebuildable SQLite table is the read projection. Reservation identity is content-keyed (excludes provenance), so the same booking seen via Kayak and via its own email dedupes to one row. A pure fidelity-ranked `fold` resolves competing observations and supersession. The one impure edge is `extract()`, a subprocess wrapper over `kitinerary-extractor` following the `pkm/producers/tesseract.py` precedent.

**Tech Stack:** Python 3 stdlib only (`sqlite3`, `subprocess`, `hashlib`, `json`, `argparse`, `dataclasses`) — no new dependency. External system binary `/usr/lib/kf6/kitinerary-extractor`. Repo gates: `uv run mypy`, `uv run ruff`, `uv run pytest`.

## Global Constraints

Copied verbatim from `docs/trips-design.md`. Every task's requirements implicitly include these.

- **Personal data is never part of the code.** No path literal, Maildir root, folder name, account id, confirmation number, route, or traveller name in any `src/` module. Concrete values are configuration (`$LIFE_AGENT_KB/config/…`, env vars) or synthetic fixtures. Code contains the *key*, never the value. A path literal in a module is a bug.
- **Fixtures are synthetic by construction**, never scrubbed captures. Confirmation numbers use checksum-invalid dummy values; routes/names are invented. This repo is public.
- **Extracted content stays in the ledger**, which lives under `$LIFE_AGENT_KB` (out of the repo tree). Nothing in the pipeline writes reservation content into the source tree.
- **Reservation identity excludes provenance** — keyed on the booked thing (segments / stay), never on vendor `eventId` or confirmation number.
- **Fidelity ranking (lower wins):** `manual`=1, `email-kitinerary`=2, `kayak-api`=3, `kayak-ics`=4. Records resolve by `(fidelity, then received_at)`, highest wins.
- **A Kayak re-import is never authoritative about absence.** Kayak drops cancellations (260/260 `isBooked`, 0 `isCancelled`); a reservation missing from a later export must never be inferred as cancelled.
- **`context_date` is mandatory** on every `extract()` call — kitinerary needs it to resolve partial dates. It comes from the email `Date:` header (or, for the Kayak importer, the event's own start date).
- Follow the repo's house style: stdlib `sqlite3`; module-level `*_PATH` constants monkeypatchable in tests; `from __future__ import annotations`; no new pip dependency.

---

## Reconciliations with the spec

Two design decisions this plan locks in where `docs/trips-design.md` left latitude. Both are faithful refinements, flagged here so a reviewer sees they are deliberate:

1. **The ledger is a JSONL file, not a `reservation_event` SQLite table.** The spec lists `reservation_event` among the tables but also says "mirroring `life_agent.tasks`". `tasks` keeps the ledger as `events.jsonl` and rebuilds a SQLite projection from it; this plan does the same (`$LIFE_AGENT_KB/trips/events.jsonl`). The SQLite side holds only projections: `source`, `reservation`, `trip`. This is the more faithful mirror and keeps truth in one append-only place.

2. **Within-identity dedup is fold-derived; cross-identity supersession is an explicit event.** Two mechanisms, kept distinct:
   - *Same identity, many sources* (Kayak + the unchanged flight's own email): the fold picks the winner by `(fidelity, received_at)`. No event — dedup is emergent from content-keyed identity. The losing source is still retained in the `source` table for provenance.
   - *Different identities, one booking evolving* (a schedule change alters `departure_datetime`, which is **in** the content key, so it mints a *new* identity): linked by an explicit `superseded(old, new)` event, exactly as `tasks`' correlator emits one. Plan 1 ships the event and the fold that honours it; the **automatic** PNR-correlator that would emit these from raw ingest is deliberately deferred (it is the risky heuristic — a shared PNR legitimately covers an outbound *and* a return — and earns its own plan). In Plan 1 these events are emitted by the `trips supersede` CLI verb and exercised by the supersession golden test.

3. **The projection is rebuilt on every write, not incrementally applied.** `tasks` applies events incrementally for speed; the trips fold is *global* (a new observation can change an identity's winner, and supersession spans identities), so a per-write `rebuild` from the full ledger is the correct and trivial choice at this scale (hundreds to low-thousands of events rebuild in milliseconds). An incremental `apply` is a later optimization if the ledger ever grows large.

---

## File Structure

All paths are relative to the repository root (the `trips-design` worktree of the `life-agent` repo).

**Created:**
- `src/life_agent/trips/__init__.py` — package docstring, mirroring `tasks/__init__.py`.
- `src/life_agent/trips/identity.py` — `content_key`, `reservation_identity` (pure).
- `src/life_agent/trips/extract.py` — `extract(payload, context_date)` subprocess seam.
- `src/life_agent/trips/events.py` — event types, `Event`, constructors, `append`/`load`, `FIDELITY_RANK`.
- `src/life_agent/trips/fold.py` — `Reservation`, `fold(events)` (pure, fidelity-ranked).
- `src/life_agent/trips/store.py` — SQLite projection: schema, `rebuild`, read queries.
- `src/life_agent/trips/commands.py` — write layer: `observe`/`cancel`/`amend`/`supersede`, ledger-append + rebuild.
- `src/life_agent/trips/seeder.py` — Kayak ICS recogniser → minimal JSON-LD → `extract()` enrich.
- `src/life_agent/trips/kayak.py` — Kayak export JSON → schema.org JSON-LD → `observe`.
- `src/life_agent/trips/cli.py` — `trips` argparse entrypoint.
- `tests/trips/__init__.py`
- `tests/trips/conftest.py` — `temp_trips` autouse fixture (monkeypatch ledger + db to `tmp_path`).
- `tests/trips/fixtures/` — synthetic `.eml`, `.ics`, and Kayak-export `.json`.
- `tests/trips/test_identity.py`, `test_extract.py`, `test_events.py`, `test_fold.py`, `test_store.py`, `test_commands.py`, `test_seeder.py`, `test_kayak.py`, `test_cli.py`.

**Modified:**
- `src/life_agent/core/config.py` — add `TRIPS_LEDGER`, `TRIPS_DB_PATH`, `KITINERARY_EXTRACTOR`.
- `pyproject.toml` — register the `trips` console script (if the repo exposes CLIs there; else document invocation via `python -m life_agent.trips.cli`).

---

## Task 1: Config paths

**Files:**
- Modify: `src/life_agent/core/config.py`
- Test: `tests/trips/test_config_trips.py`

**Interfaces:**
- Produces: `TRIPS_LEDGER: Path`, `TRIPS_DB_PATH: Path`, `KITINERARY_EXTRACTOR: str` — importable from `life_agent.core.config`. The ledger and db mirror `TASKS_LEDGER`/`GTD_DB_PATH`; the extractor path defaults to the installed binary and is env-overridable.

- [ ] **Step 1: Write the failing test**

```python
# tests/trips/test_config_trips.py
"""The trips faculty's resolved paths live under $LIFE_AGENT_KB, never in code."""
from __future__ import annotations

import importlib

import life_agent.core.config as config


def test_trips_paths_are_under_kb() -> None:
    assert config.TRIPS_LEDGER == config.KB / "trips" / "events.jsonl"
    assert config.TRIPS_DB_PATH.name == "trips.db"
    assert config.TRIPS_DB_PATH.parent == config.KB / "trips"


def test_extractor_path_env_overridable(monkeypatch) -> None:
    monkeypatch.setenv("KITINERARY_EXTRACTOR", "/opt/kitinerary")
    reloaded = importlib.reload(config)
    assert reloaded.KITINERARY_EXTRACTOR == "/opt/kitinerary"
    importlib.reload(config)  # restore module state for other tests
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/trips/test_config_trips.py -v`
Expected: FAIL — `AttributeError: module 'life_agent.core.config' has no attribute 'TRIPS_LEDGER'`.

- [ ] **Step 3: Add the constants**

Append to `src/life_agent/core/config.py`, after the GTD block (near `TASKS_STATE`):

```python
# --- Trips (the itinerary faculty) ---
# Append-only event ledger (Observed/Superseded/Cancelled/Amended) — THE source of truth
# for reservations, keyed on a content-derived reservation identity (not vendor eventId).
# The timeline is a fold of it. See life_agent/trips/events.py.
TRIPS_LEDGER = KB / "trips" / "events.jsonl"
# The trips read-model: a materialised SQLite projection of fold(TRIPS_LEDGER) — rebuildable,
# derived (NOT truth; safe to delete and rebuild). No PII: reservation content lives under KB.
TRIPS_DB_PATH = Path(os.environ.get("TRIPS_DB_PATH", str(KB / "trips" / "trips.db"))).expanduser()
# The kitinerary extractor binary — an installed system tool wrapped as a producer (the
# extraction seam). Default is the KF6 install path; override per-machine via the env var.
KITINERARY_EXTRACTOR = os.environ.get("KITINERARY_EXTRACTOR", "/usr/lib/kf6/kitinerary-extractor")
```

If `config/__init__.py` re-exports names (it does — see `core/__init__.py`), add `TRIPS_LEDGER`, `TRIPS_DB_PATH`, `KITINERARY_EXTRACTOR` to its import list and `__all__`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/trips/test_config_trips.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/life_agent/core/config.py src/life_agent/core/__init__.py tests/trips/test_config_trips.py
git commit -m "feat(trips): resolved KB paths + extractor binary config"
```

---

## Task 2: Reservation identity

**Files:**
- Create: `src/life_agent/trips/__init__.py`, `src/life_agent/trips/identity.py`
- Create: `tests/trips/__init__.py`, `tests/trips/test_identity.py`

**Interfaces:**
- Produces:
  - `content_key(jsonld: dict) -> tuple` — the identity-bearing tuple, exposed for debugging/tests.
  - `reservation_identity(jsonld: dict) -> str` — `sha256` hex of the normalized content key.
  - `res_type(jsonld: dict) -> str` — the schema.org `@type` (e.g. `"FlightReservation"`).
- Consumes: schema.org JSON-LD dicts as emitted by kitinerary **and** as normalized by `kayak.py` — both must produce the same key for the same booking. Field access is defensive (missing → empty), because the degenerate cases are real.

The key shapes (from the spec's Reservation identity section):
- flight / train → ordered tuple over segments of `(departure_iata, arrival_iata, departure_datetime, flight_number)`
- lodging → `(property_id_or_name, check_in, check_out)`
- other → `(title, start, end)`

- [ ] **Step 1: Write the failing tests** (covering the degenerate cases the export happened to satisfy)

```python
# tests/trips/test_identity.py
"""Content-keyed identity: same booked thing -> same id, regardless of provenance."""
from __future__ import annotations

from life_agent.trips.identity import content_key, reservation_identity, res_type

_FLIGHT = {
    "@type": "FlightReservation",
    "reservationFor": {
        "@type": "Flight",
        "flightNumber": "TP123",
        "departureAirport": {"@type": "Airport", "iataCode": "LIS"},
        "arrivalAirport": {"@type": "Airport", "iataCode": "AMS"},
        "departureTime": "2019-08-12T09:30:00+01:00",
    },
}

_LODGING = {
    "@type": "LodgingReservation",
    "reservationFor": {"@type": "LodgingBusiness", "name": "Hotel Example"},
    "checkinTime": "2019-08-12",
    "checkoutTime": "2019-08-15",
}


def test_flight_identity_is_stable_and_type_aware() -> None:
    assert res_type(_FLIGHT) == "FlightReservation"
    a = reservation_identity(_FLIGHT)
    assert a == reservation_identity(dict(_FLIGHT))  # same content -> same id
    assert len(a) == 64  # sha256 hex


def test_provenance_does_not_change_identity() -> None:
    """The same flight carrying a different confirmation number is ONE identity."""
    with_conf = {**_FLIGHT, "reservationNumber": "ABC123"}
    without = {**_FLIGHT}
    assert reservation_identity(with_conf) == reservation_identity(without)


def test_lodging_falls_back_to_name_when_no_property_id() -> None:
    key = content_key(_LODGING)
    assert "Hotel Example" in key[0] or key[0][0] == "Hotel Example"


def test_segment_with_no_flight_number_still_keys() -> None:
    """Degenerate case fixtures must cover: a segment lacking flightNumber/airline code."""
    bare = {
        "@type": "FlightReservation",
        "reservationFor": {
            "@type": "Flight",
            "departureAirport": {"iataCode": "LHR"},
            "arrivalAirport": {"iataCode": "JFK"},
            "departureTime": "2015-03-01T10:00:00Z",
        },
    }
    # Must not raise and must produce a stable id (flight_number slot empty, others present).
    first = reservation_identity(bare)
    assert first == reservation_identity(bare)


def test_multisegment_flight_orders_segments() -> None:
    two = {
        "@type": "FlightReservation",
        "reservationFor": [
            {"flightNumber": "TP1", "departureAirport": {"iataCode": "LIS"},
             "arrivalAirport": {"iataCode": "OPO"}, "departureTime": "2019-08-12T09:00:00Z"},
            {"flightNumber": "TP2", "departureAirport": {"iataCode": "OPO"},
             "arrivalAirport": {"iataCode": "AMS"}, "departureTime": "2019-08-12T12:00:00Z"},
        ],
    }
    key = content_key(two)
    assert key[0][0][0] == "LIS" and key[0][-1][1] == "AMS"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/trips/test_identity.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'life_agent.trips'`.

- [ ] **Step 3: Write the package + implementation**

```python
# src/life_agent/trips/__init__.py
"""life_agent.trips — the itinerary faculty: bookings -> a queryable, timezone-correct timeline.

Event-sourced, mirroring life_agent.tasks: an append-only JSONL ledger (events.py) is the
truth, a rebuildable SQLite table (store.py) is the read projection, and truth = fold(events)
(fold.py). Reservation identity (identity.py) is content-keyed and excludes provenance, so the
same booking seen via the Kayak export and via its own confirmation email dedupes to one row.
The single impure edge is extract.py, a subprocess wrapper over kitinerary-extractor.
"""
```

```python
# src/life_agent/trips/identity.py
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


def _iata(place: Any) -> str:
    return _norm(place.get("iataCode")) if isinstance(place, dict) else ""


def _segment_key(seg: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        _iata(seg.get("departureAirport")),
        _iata(seg.get("arrivalAirport")),
        _norm(seg.get("departureTime")),
        _norm(seg.get("flightNumber")),
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
    """Stable sha256 identity over (res_type, content_key). JSON-serialise the key with
    sort_keys so tuple nesting is canonical and reproducible across processes."""
    payload = _SEP.join([res_type(jsonld), json.dumps(content_key(jsonld), sort_keys=True)])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/trips/test_identity.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add src/life_agent/trips/__init__.py src/life_agent/trips/identity.py tests/trips/__init__.py tests/trips/test_identity.py
git commit -m "feat(trips): content-keyed reservation identity"
```

---

## Task 3: Extraction seam

**Files:**
- Create: `src/life_agent/trips/extract.py`
- Create: `tests/trips/test_extract.py`
- Create: `tests/trips/fixtures/flight.eml` (synthetic)

**Interfaces:**
- Produces: `extract(payload: bytes, context_date: datetime) -> list[dict]` — shells to `kitinerary-extractor -o JsonLd --context-date <iso>`, returns the parsed JSON-LD list. **Never raises**; any failure (missing binary, non-zero exit, timeout, unparseable stdout) returns `[]`. This is the only module that touches the binary.
- Consumes: `KITINERARY_EXTRACTOR` from config.

- [ ] **Step 1: Write the synthetic fixture**

Create `tests/trips/fixtures/flight.eml` — a minimal, invented airline confirmation (checksum-invalid PNR, fake names) that kitinerary recognises. Build it from the known-good `test.eml` shape used during design profiling; verify locally it yields a `FlightReservation`. If kitinerary cannot be relied on in CI, mark the live test `@pytest.mark.system` (the repo already gates `system`/`llm` markers — see `pyproject.toml`).

```
From: Example Air <noreply@example.com>
To: traveller@example.org
Subject: Your booking EXMPL0 — LIS to AMS
Date: Mon, 05 Aug 2019 10:00:00 +0100
Content-Type: text/plain; charset=utf-8

Booking reference: EXMPL0
Passenger: PAX EXAMPLE
Flight EX 123
Lisbon (LIS) 12 Aug 09:30  ->  Amsterdam (AMS) 12 Aug 13:45
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/trips/test_extract.py
"""The one impure edge: a deterministic subprocess wrapper over kitinerary-extractor."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from life_agent.trips import extract as ex

_FIX = Path(__file__).parent / "fixtures"


def test_missing_binary_returns_empty_never_raises(monkeypatch) -> None:
    monkeypatch.setattr(ex, "BINARY", "/fake/kitinerary")
    assert ex.extract(b"anything", datetime(2019, 8, 5)) == []


def test_garbage_input_returns_empty(monkeypatch) -> None:
    # A real binary on non-email bytes yields []; if absent, the missing-binary path also gives [].
    assert ex.extract(b"\x00\x01not an email", datetime(2019, 8, 5)) == []


@pytest.mark.system
def test_real_email_yields_flight_reservation() -> None:
    payload = (_FIX / "flight.eml").read_bytes()
    out = ex.extract(payload, datetime(2019, 8, 5))
    assert any(o.get("@type") == "FlightReservation" for o in out)


@pytest.mark.system
def test_raw_jsonld_is_enriched() -> None:
    """kitinerary accepts raw JSON-LD and enriches IATA -> timezone/geo (the seeder trick)."""
    import json
    stub = json.dumps([{
        "@context": "http://schema.org",
        "@type": "FlightReservation",
        "reservationFor": {"@type": "Flight",
            "departureAirport": {"@type": "Airport", "iataCode": "LIS"},
            "arrivalAirport": {"@type": "Airport", "iataCode": "AMS"},
            "departureDay": "2019-08-12"}}]).encode()
    out = ex.extract(stub, datetime(2019, 8, 5))
    assert out, "expected at least one enriched reservation"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/trips/test_extract.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'life_agent.trips.extract'`.

- [ ] **Step 4: Write the implementation** (mirroring `tesseract.py`: never raises, timeout, config-driven binary)

```python
# src/life_agent/trips/extract.py
"""extract(payload, context_date) -> JSON-LD. The only edge that touches the binary.

Follows the pkm/producers/tesseract.py precedent: a system binary wrapped as a producer,
subprocess-called, never raising — any failure returns []. Deterministic: same bytes +
same context_date -> same JSON-LD, with barcode verification underneath. context_date is
mandatory: kitinerary uses it to resolve partial dates ('12 Aug') to a real year, and a
wrong one is the single most common source of garbage output.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime
from typing import Any

from life_agent.core.config import KITINERARY_EXTRACTOR

BINARY: str = KITINERARY_EXTRACTOR
_TIMEOUT_SECONDS = 60


def extract(payload: bytes, context_date: datetime) -> list[dict[str, Any]]:
    """Run the extractor over raw bytes (an email, a PDF, or raw JSON-LD to enrich).

    Returns the parsed JSON-LD reservation list, or [] on any failure. Never raises."""
    try:
        completed = subprocess.run(
            [BINARY, "-o", "JsonLd", "--context-date", context_date.isoformat()],
            input=payload,
            capture_output=True,
            timeout=_TIMEOUT_SECONDS,
            check=False,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return []
    if completed.returncode != 0:
        return []
    try:
        parsed = json.loads(completed.stdout or b"[]")
    except (json.JSONDecodeError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []
    return [o for o in parsed if isinstance(o, dict)]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/trips/test_extract.py -v` (system tests run where the binary exists; `uv run pytest tests/trips/test_extract.py -v -m "not system"` in CI without it)
Expected: PASS — the two non-system tests always; all four where the binary is installed.

- [ ] **Step 6: Commit**

```bash
git add src/life_agent/trips/extract.py tests/trips/test_extract.py tests/trips/fixtures/flight.eml
git commit -m "feat(trips): kitinerary extraction seam (subprocess, never raises)"
```

---

## Task 4: Event ledger

**Files:**
- Create: `src/life_agent/trips/events.py`
- Create: `tests/trips/test_events.py`

**Interfaces:**
- Produces:
  - `EventType = Literal["observed", "superseded", "cancelled", "amended"]`
  - `FIDELITY_RANK: dict[str, int]` — `{"manual":1, "email-kitinerary":2, "kayak-api":3, "kayak-ics":4}`.
  - `@dataclass(frozen=True) Event` with fields `type, identity, tx_time, received_at, fidelity, source_id, superseded_by, reason, payload, event_id`.
  - constructors `observed(identity, jsonld, *, fidelity, source_id, received_at, tx_time=None)`, `superseded(old_identity, new_identity, *, tx_time=None)`, `cancelled(identity, reason, *, source_id=None, received_at=None, tx_time=None)`, `amended(identity, fields, *, tx_time=None)`.
  - `append(ledger: Path, events: list[Event]) -> None`, `load(ledger: Path) -> list[Event]`, `now_iso() -> str`.
- Consumes: nothing from other trips modules (leaf).

- [ ] **Step 1: Write the failing tests**

```python
# tests/trips/test_events.py
"""The append-only ledger: constructors, round-trip serialisation, fidelity ranking."""
from __future__ import annotations

from pathlib import Path

from life_agent.trips import events as ev


def test_fidelity_rank_orders_manual_over_kayak() -> None:
    assert ev.FIDELITY_RANK["manual"] < ev.FIDELITY_RANK["email-kitinerary"]
    assert ev.FIDELITY_RANK["email-kitinerary"] < ev.FIDELITY_RANK["kayak-api"]
    assert ev.FIDELITY_RANK["kayak-api"] < ev.FIDELITY_RANK["kayak-ics"]


def test_observed_carries_fidelity_and_source() -> None:
    e = ev.observed("id1", {"@type": "FlightReservation"},
                    fidelity="kayak-api", source_id="evt-9", received_at="2019-08-05T10:00:00")
    assert e.type == "observed"
    assert e.fidelity == "kayak-api"
    assert e.source_id == "evt-9"
    assert e.payload == {"@type": "FlightReservation"}
    assert e.event_id  # auto-derived, non-empty


def test_round_trip_through_ledger(tmp_path: Path) -> None:
    ledger = tmp_path / "events.jsonl"
    events = [
        ev.observed("id1", {"@type": "FlightReservation"},
                    fidelity="kayak-api", source_id="e1", received_at="2019-08-05T10:00:00"),
        ev.superseded("id1", "id2"),
        ev.cancelled("id2", reason="airline cancelled", source_id="mail-1"),
        ev.amended("id2", {"seatNumber": "12A"}),
    ]
    ev.append(ledger, events)
    loaded = ev.load(ledger)
    assert [e.type for e in loaded] == ["observed", "superseded", "cancelled", "amended"]
    assert loaded[1].superseded_by == "id2"
    assert loaded[3].payload["fields"] == {"seatNumber": "12A"}


def test_load_missing_ledger_is_empty(tmp_path: Path) -> None:
    assert ev.load(tmp_path / "nope.jsonl") == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/trips/test_events.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'life_agent.trips.events'`.

- [ ] **Step 3: Write the implementation** (structural copy of `tasks/events.py`, adapted fields)

```python
# src/life_agent/trips/events.py
"""Append-only event ledger for the trips faculty — the spine the timeline folds out of.

Mirrors tasks/events.py: append-only, corrections are new compensating entries, truth =
fold(events). The event vocabulary differs — a reservation is `observed` (by a source, at a
fidelity), an evolving booking is `superseded` (old identity -> new), a booking is
`cancelled`, and a field is manually `amended`. Within-identity dedup (Kayak + the same
flight's email) is fold-derived from competing `observed` events; cross-identity supersession
(a schedule change mints a new content key) is this explicit `superseded` edge.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

EventType = Literal["observed", "superseded", "cancelled", "amended"]

# Fidelity ranking — LOWER wins. Records resolve by (FIDELITY_RANK[fidelity], received_at).
FIDELITY_RANK: dict[str, int] = {
    "manual": 1,
    "email-kitinerary": 2,
    "kayak-api": 3,
    "kayak-ics": 4,
}

_SEP = "\x1f"


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass(frozen=True)
class Event:
    """One immutable ledger entry concerning a single reservation ``identity``."""

    type: EventType
    identity: str
    tx_time: str
    received_at: str | None = None
    fidelity: str | None = None
    source_id: str | None = None
    superseded_by: str | None = None
    reason: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    event_id: str = ""

    def __post_init__(self) -> None:
        if not self.event_id:
            digest = hashlib.sha256(
                _SEP.join([
                    self.type, self.identity, self.tx_time,
                    self.superseded_by or "", self.source_id or "", self.reason or "",
                ]).encode("utf-8")
            ).hexdigest()[:16]
            object.__setattr__(self, "event_id", digest)


def observed(
    identity: str,
    jsonld: dict[str, Any],
    *,
    fidelity: str,
    source_id: str,
    received_at: str,
    tx_time: str | None = None,
) -> Event:
    """A source asserted this reservation content, at a fidelity, received at a time."""
    return Event(
        type="observed", identity=identity, tx_time=tx_time or now_iso(),
        received_at=received_at, fidelity=fidelity, source_id=source_id, payload=jsonld,
    )


def superseded(old_identity: str, new_identity: str, *, tx_time: str | None = None) -> Event:
    """Link an evolving booking: the reschedule/re-issue minted a new content key."""
    return Event(type="superseded", identity=old_identity,
                 tx_time=tx_time or now_iso(), superseded_by=new_identity)


def cancelled(
    identity: str, reason: str, *,
    source_id: str | None = None, received_at: str | None = None, tx_time: str | None = None,
) -> Event:
    """Mark a reservation (and its supersession chain) cancelled — never a delete."""
    return Event(type="cancelled", identity=identity, tx_time=tx_time or now_iso(),
                 received_at=received_at, source_id=source_id, reason=reason)


def amended(identity: str, fields: dict[str, Any], *, tx_time: str | None = None) -> Event:
    """A manual field override (tier `manual` always wins in the fold)."""
    return Event(type="amended", identity=identity, tx_time=tx_time or now_iso(),
                 payload={"fields": fields})


def _to_json(e: Event) -> str:
    return json.dumps({
        "event_id": e.event_id, "type": e.type, "identity": e.identity,
        "tx_time": e.tx_time, "received_at": e.received_at, "fidelity": e.fidelity,
        "source_id": e.source_id, "superseded_by": e.superseded_by, "reason": e.reason,
        "payload": e.payload,
    }, ensure_ascii=False, sort_keys=True)


def _from_json(line: str) -> Event | None:
    try:
        d = json.loads(line)
        return Event(
            type=d["type"], identity=d["identity"], tx_time=d["tx_time"],
            received_at=d.get("received_at"), fidelity=d.get("fidelity"),
            source_id=d.get("source_id"), superseded_by=d.get("superseded_by"),
            reason=d.get("reason"), payload=d.get("payload", {}), event_id=d.get("event_id", ""),
        )
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def append(ledger: Path, events: list[Event]) -> None:
    if not events:
        return
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as fh:
        for e in events:
            fh.write(_to_json(e) + "\n")


def load(ledger: Path) -> list[Event]:
    if not ledger.exists():
        return []
    out: list[Event] = []
    for line in ledger.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        e = _from_json(line)
        if e is not None:
            out.append(e)
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/trips/test_events.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/life_agent/trips/events.py tests/trips/test_events.py
git commit -m "feat(trips): append-only event ledger (observed/superseded/cancelled/amended)"
```

---

## Task 5: The fold (fidelity-ranked supersession) — highest-risk logic

**Files:**
- Create: `src/life_agent/trips/fold.py`
- Create: `tests/trips/test_fold.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) Reservation` with fields `identity: str, jsonld: dict, fidelity: str, source_id: str, received_at: str | None, cancelled: bool, superseded_by: str | None`.
  - `fold(events: list[Event]) -> dict[str, Reservation]` — one entry per identity ever observed. `superseded_by is None and not cancelled` ⇒ current. Amendments are merged into `jsonld`.
- Consumes: `Event`, `FIDELITY_RANK` from `events.py`.

**Fold algorithm:**
1. Group `observed` events by identity; within each, the winner is `min` by `(FIDELITY_RANK.get(fidelity, 99), invert(received_at))` — highest fidelity, tie-broken by latest `received_at`. Build the base `Reservation` from the winner.
2. Apply `superseded(old, new)` events → set `reservations[old].superseded_by = new` (last writer wins).
3. Apply `cancelled(identity)` → set `.cancelled = True`.
4. Apply `amended(identity, fields)` → deep-merge `fields` into `.jsonld`.

- [ ] **Step 1: Write the failing tests** (the spec's named high-risk scenarios)

```python
# tests/trips/test_fold.py
"""Supersession is the highest-risk logic — tested first, per the design's testing section."""
from __future__ import annotations

from life_agent.trips import events as ev
from life_agent.trips.fold import fold


def _flight(fno: str) -> dict:
    return {"@type": "FlightReservation", "reservationFor": {"flightNumber": fno}}


def test_same_identity_two_sources_email_wins_over_kayak() -> None:
    """Kayak (tier 3) and the flight's own email (tier 2) observe ONE identity -> email wins."""
    events = [
        ev.observed("id1", _flight("EX1"), fidelity="kayak-api",
                    source_id="kayak", received_at="2019-08-01T00:00:00"),
        ev.observed("id1", _flight("EX1"), fidelity="email-kitinerary",
                    source_id="mail", received_at="2019-08-02T00:00:00"),
    ]
    result = fold(events)
    assert set(result) == {"id1"}
    assert result["id1"].fidelity == "email-kitinerary"
    assert result["id1"].source_id == "mail"
    assert result["id1"].superseded_by is None and not result["id1"].cancelled


def test_lower_fidelity_arriving_later_does_not_win() -> None:
    events = [
        ev.observed("id1", _flight("EX1"), fidelity="email-kitinerary",
                    source_id="mail", received_at="2019-08-01T00:00:00"),
        ev.observed("id1", _flight("EX1"), fidelity="kayak-ics",
                    source_id="ics", received_at="2020-01-01T00:00:00"),
    ]
    assert fold(events)["id1"].fidelity == "email-kitinerary"


def test_reschedule_reissue_cancel_folds_to_one_current_cancelled() -> None:
    """confirmation -> schedule change -> re-issue -> cancellation against one PNR must fold
    to exactly ONE current reservation, cancelled, with superseded ancestors retained."""
    events = [
        ev.observed("conf", _flight("EX1"), fidelity="email-kitinerary",
                    source_id="m1", received_at="2019-08-01T00:00:00"),
        ev.observed("sched", _flight("EX1b"), fidelity="email-kitinerary",
                    source_id="m2", received_at="2019-08-02T00:00:00"),
        ev.superseded("conf", "sched"),
        ev.observed("reissue", _flight("EX9"), fidelity="email-kitinerary",
                    source_id="m3", received_at="2019-08-03T00:00:00"),
        ev.superseded("sched", "reissue"),
        ev.cancelled("reissue", reason="cancelled by airline", source_id="m4"),
    ]
    result = fold(events)
    current = [r for r in result.values() if r.superseded_by is None]
    assert len(current) == 1
    assert current[0].identity == "reissue"
    assert current[0].cancelled is True
    superseded = [r for r in result.values() if r.superseded_by is not None]
    assert len(superseded) == 2  # conf, sched retained


def test_amendment_merges_into_jsonld() -> None:
    events = [
        ev.observed("id1", _flight("EX1"), fidelity="kayak-api",
                    source_id="k", received_at="2019-08-01T00:00:00"),
        ev.amended("id1", {"reservationFor": {"flightNumber": "EX1", "seat": "12A"}}),
    ]
    assert fold(events)["id1"].jsonld["reservationFor"]["seat"] == "12A"


def test_kayak_import_never_infers_cancellation_from_absence() -> None:
    """A record present once and simply not re-observed stays booked (Kayak drops
    cancellations; absence is never cancellation)."""
    events = [ev.observed("id1", _flight("EX1"), fidelity="kayak-api",
                          source_id="k", received_at="2019-08-01T00:00:00")]
    assert fold(events)["id1"].cancelled is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/trips/test_fold.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'life_agent.trips.fold'`.

- [ ] **Step 3: Write the implementation**

```python
# src/life_agent/trips/fold.py
"""truth = fold(events): resolve competing observations, supersession and cancellation.

Two dedup mechanisms meet here (see the plan's Reconciliations note):
 * same identity, many `observed` events -> the winner is highest fidelity, tie-broken by
   latest received_at. This is the free dedup content-keyed identity buys us.
 * different identities linked by `superseded` -> the old identity is retained but flagged.

The projection keeps ALL identities (superseded ancestors are retained, never deleted);
`superseded_by is None and not cancelled` is the predicate for a CURRENT reservation.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from life_agent.trips.events import FIDELITY_RANK, Event


@dataclass(frozen=True)
class Reservation:
    identity: str
    jsonld: dict[str, Any]
    fidelity: str
    source_id: str
    received_at: str | None
    cancelled: bool = False
    superseded_by: str | None = None


def _better(a: Event, b: Event) -> Event:
    """The winning observation: lower fidelity rank wins; tie -> later received_at."""
    ra, rb = FIDELITY_RANK.get(a.fidelity or "", 99), FIDELITY_RANK.get(b.fidelity or "", 99)
    if ra != rb:
        return a if ra < rb else b
    return a if (a.received_at or "") >= (b.received_at or "") else b


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in overlay.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def fold(events: list[Event]) -> dict[str, Reservation]:
    winners: dict[str, Event] = {}
    for e in events:
        if e.type == "observed":
            winners[e.identity] = _better(winners[e.identity], e) if e.identity in winners else e

    reservations: dict[str, Reservation] = {
        ident: Reservation(
            identity=ident, jsonld=dict(w.payload), fidelity=w.fidelity or "",
            source_id=w.source_id or "", received_at=w.received_at,
        )
        for ident, w in winners.items()
    }

    for e in events:
        if e.type == "superseded" and e.identity in reservations:
            reservations[e.identity] = replace(reservations[e.identity], superseded_by=e.superseded_by)
        elif e.type == "cancelled" and e.identity in reservations:
            reservations[e.identity] = replace(reservations[e.identity], cancelled=True)
        elif e.type == "amended" and e.identity in reservations:
            merged = _deep_merge(reservations[e.identity].jsonld, e.payload.get("fields", {}))
            reservations[e.identity] = replace(reservations[e.identity], jsonld=merged)

    return reservations
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/trips/test_fold.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add src/life_agent/trips/fold.py tests/trips/test_fold.py
git commit -m "feat(trips): fidelity-ranked fold with supersession + cancellation"
```

---

## Task 6: SQLite projection store

**Files:**
- Create: `src/life_agent/trips/store.py`
- Create: `tests/trips/conftest.py`
- Create: `tests/trips/test_store.py`

**Interfaces:**
- Produces:
  - `DB_PATH: Path` (module-level, monkeypatchable; defaults to `TRIPS_DB_PATH`).
  - `get_db() -> sqlite3.Connection`, `create_schema(conn)`, `init_db()`.
  - `rebuild(conn, events: list[Event]) -> None` — replays the whole ledger through `fold` into the `reservation` table; also upserts `source` rows and `trip` labels carried in payloads.
  - `upsert_source(conn, source_id, *, message_id, path, sha256, received_at, fidelity, kind)`.
  - `upsert_trip(conn, trip_id, *, name, start_date, end_date)`.
  - Read queries: `timeline(limit=None) -> list[dict]`, `now_next() -> dict`, `search(term) -> list[dict]`, `get_reservation(identity) -> dict | None`.
- Consumes: `fold`, `Reservation` (Task 5); `Event` (Task 4); `identity.res_type`.

**Projection columns** (extracted from `jsonld` for querying; `jsonld` stored verbatim): `identity, res_type, title, start_iso, start_tz, end_iso, end_tz, confirmation, provider, dep_iata, arr_iata, lat, lon, cancelled, superseded_by, fidelity, source_id, received_at, trip_id, jsonld`.

- [ ] **Step 1: Write the conftest fixture**

```python
# tests/trips/conftest.py
"""Isolate every trips test to a tmp ledger + tmp db (mirrors tests/test_tasks.py::temp_gtd)."""
from __future__ import annotations

from pathlib import Path

import pytest

from life_agent.trips import commands, store


@pytest.fixture(autouse=True)
def temp_trips(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "trips.db")
    monkeypatch.setattr(commands, "LEDGER_PATH", tmp_path / "events.jsonl")
    store.init_db()
```

Note: `test_store.py` and `test_commands.py` rely on this; `test_identity/extract/events/fold` do not import `store`/`commands`, so the autouse fixture only binds where those modules import (it is defined in `tests/trips/` so it applies to the whole subpackage — harmless for the pure-module tests since it only monkeypatches attributes they never read).

- [ ] **Step 2: Write the failing tests**

```python
# tests/trips/test_store.py
"""The read projection: a rebuildable SQLite view of fold(ledger)."""
from __future__ import annotations

from life_agent.trips import events as ev
from life_agent.trips import store


def _flight(fno: str, dep: str, arr: str, dep_time: str) -> dict:
    return {"@type": "FlightReservation", "reservationNumber": "EXMPL0",
            "reservationFor": {"flightNumber": fno,
                "departureAirport": {"iataCode": dep}, "arrivalAirport": {"iataCode": arr},
                "departureTime": dep_time}}


def test_rebuild_projects_current_reservations() -> None:
    events = [ev.observed("id1", _flight("EX1", "LIS", "AMS", "2019-08-12T09:30:00+01:00"),
                          fidelity="kayak-api", source_id="k1", received_at="2019-08-01T00:00:00")]
    with store.get_db() as conn:
        store.rebuild(conn, events)
    rows = store.timeline()
    assert len(rows) == 1
    assert rows[0]["dep_iata"] == "LIS" and rows[0]["arr_iata"] == "AMS"
    assert rows[0]["confirmation"] == "EXMPL0"


def test_superseded_rows_are_excluded_from_timeline() -> None:
    events = [
        ev.observed("old", _flight("EX1", "LIS", "AMS", "2019-08-12T09:30:00Z"),
                    fidelity="email-kitinerary", source_id="m1", received_at="2019-08-01T00:00:00"),
        ev.observed("new", _flight("EX9", "LIS", "AMS", "2019-08-12T18:00:00Z"),
                    fidelity="email-kitinerary", source_id="m2", received_at="2019-08-02T00:00:00"),
        ev.superseded("old", "new"),
    ]
    with store.get_db() as conn:
        store.rebuild(conn, events)
    idents = {r["identity"] for r in store.timeline()}
    assert idents == {"new"}
    assert store.get_reservation("old")["superseded_by"] == "new"  # retained, queryable


def test_search_matches_iata_and_confirmation() -> None:
    events = [ev.observed("id1", _flight("EX1", "LIS", "AMS", "2019-08-12T09:30:00Z"),
                          fidelity="kayak-api", source_id="k1", received_at="2019-08-01T00:00:00")]
    with store.get_db() as conn:
        store.rebuild(conn, events)
    assert store.search("AMS")
    assert store.search("EXMPL0")
    assert store.search("nowhere") == []
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/trips/test_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'life_agent.trips.store'` (and `commands`, referenced by conftest — create a stub in the next step or accept both are built here; commands lands in Task 7, so temporarily import-guard the conftest OR build Task 7 before running store tests). **Resolution:** create `commands.py` with just `LEDGER_PATH = TRIPS_LEDGER` now (one line) so the conftest imports; the rest of `commands` fills in Task 7.

- [ ] **Step 4: Write the store + the one-line commands stub**

```python
# src/life_agent/trips/commands.py  (stub — completed in Task 7)
from __future__ import annotations

from pathlib import Path

from life_agent.core.config import TRIPS_LEDGER

LEDGER_PATH: Path = TRIPS_LEDGER
```

```python
# src/life_agent/trips/store.py
"""The trips read-model: a materialised SQLite projection of fold(TRIPS_LEDGER).

The view, not the truth — every row derives from the event ledger. `rebuild` replays the
whole ledger through fold(); at this scale (hundreds-low-thousands of events) a full rebuild
per write is milliseconds and sidesteps the global nature of fidelity supersession. JSON-LD
is stored VERBATIM (kitinerary's schema is richer + more volatile than we'd design); the
extracted columns exist only for querying and are a cheap re-derivation, never a lossy one.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from life_agent.core.config import TRIPS_DB_PATH
from life_agent.trips.events import Event
from life_agent.trips.fold import Reservation, fold
from life_agent.trips.identity import res_type

DB_PATH: Path = TRIPS_DB_PATH


def get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def create_schema(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reservation (
            identity TEXT PRIMARY KEY,
            res_type TEXT NOT NULL,
            title TEXT, start_iso TEXT, start_tz TEXT, end_iso TEXT, end_tz TEXT,
            confirmation TEXT, provider TEXT,
            dep_iata TEXT, arr_iata TEXT, lat REAL, lon REAL,
            cancelled INTEGER NOT NULL DEFAULT 0,
            superseded_by TEXT,
            fidelity TEXT NOT NULL, source_id TEXT, received_at TEXT,
            trip_id TEXT,
            jsonld TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS source (
            source_id TEXT PRIMARY KEY, message_id TEXT, path TEXT, sha256 TEXT,
            received_at TEXT, fidelity TEXT, kind TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trip (
            trip_id TEXT PRIMARY KEY, name TEXT, start_date TEXT, end_date TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_res_current "
                 "ON reservation (start_iso) WHERE superseded_by IS NULL")


def init_db() -> None:
    with get_db() as conn:
        create_schema(conn)


# --- column extraction from verbatim JSON-LD ----------------------------------


def _first(rf: Any) -> dict[str, Any]:
    if isinstance(rf, list):
        return rf[0] if rf and isinstance(rf[0], dict) else {}
    return rf if isinstance(rf, dict) else {}


def _iata(place: Any) -> str | None:
    return place.get("iataCode") if isinstance(place, dict) else None


def _project_columns(r: Reservation) -> dict[str, Any]:
    j = r.jsonld
    t = res_type(j)
    rf = j.get("reservationFor")
    seg0 = _first(rf)
    dep, arr = seg0.get("departureAirport"), seg0.get("arrivalAirport")
    start = seg0.get("departureTime") or j.get("checkinTime") or j.get("startTime")
    end = _last_seg(rf).get("arrivalTime") or j.get("checkoutTime") or j.get("endTime")
    geo = arr.get("geo") if isinstance(arr, dict) else None
    provider = seg0.get("name") or (seg0.get("airline") or {}).get("iataCode") \
        or _first(rf).get("name")
    return {
        "res_type": t,
        "title": seg0.get("name") or j.get("name"),
        "start_iso": _iso(start), "start_tz": _tz(start, seg0.get("departureTime")),
        "end_iso": _iso(end), "end_tz": None,
        "confirmation": j.get("reservationNumber") or (
            (j.get("bookingDetail") or {}).get("bookingReferenceNumber")),
        "provider": provider if isinstance(provider, str) else None,
        "dep_iata": _iata(dep), "arr_iata": _iata(arr),
        "lat": geo.get("latitude") if isinstance(geo, dict) else None,
        "lon": geo.get("longitude") if isinstance(geo, dict) else None,
    }


def _iso(v: Any) -> str | None:
    if isinstance(v, dict):  # schema.org DateTime {"@value": ..., "timezone": ...}
        return v.get("@value")
    return v if isinstance(v, str) else None


def _tz(v: Any, raw: Any) -> str | None:
    if isinstance(raw, dict):
        return raw.get("timezone")
    return None


def _last_seg(rf: Any) -> dict[str, Any]:
    if isinstance(rf, list) and rf and isinstance(rf[-1], dict):
        return rf[-1]
    return _first(rf)


# --- rebuild + upserts --------------------------------------------------------


def rebuild(conn: sqlite3.Connection, events: list[Event]) -> None:
    conn.execute("DELETE FROM reservation")
    for ident, r in fold(events).items():
        cols = _project_columns(r)
        conn.execute(
            "INSERT INTO reservation (identity, res_type, title, start_iso, start_tz, "
            "end_iso, end_tz, confirmation, provider, dep_iata, arr_iata, lat, lon, "
            "cancelled, superseded_by, fidelity, source_id, received_at, jsonld) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (ident, cols["res_type"], cols["title"], cols["start_iso"], cols["start_tz"],
             cols["end_iso"], cols["end_tz"], cols["confirmation"], cols["provider"],
             cols["dep_iata"], cols["arr_iata"], cols["lat"], cols["lon"],
             int(r.cancelled), r.superseded_by, r.fidelity, r.source_id, r.received_at,
             json.dumps(r.jsonld, ensure_ascii=False, sort_keys=True)),
        )


def upsert_source(conn: sqlite3.Connection, source_id: str, *, message_id: str | None,
                  path: str | None, sha256: str | None, received_at: str | None,
                  fidelity: str, kind: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO source (source_id, message_id, path, sha256, received_at, "
        "fidelity, kind) VALUES (?,?,?,?,?,?,?)",
        (source_id, message_id, path, sha256, received_at, fidelity, kind))


def upsert_trip(conn: sqlite3.Connection, trip_id: str, *, name: str | None,
                start_date: str | None, end_date: str | None) -> None:
    conn.execute("INSERT OR REPLACE INTO trip (trip_id, name, start_date, end_date) "
                 "VALUES (?,?,?,?)", (trip_id, name, start_date, end_date))


# --- read queries -------------------------------------------------------------


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    d["cancelled"] = bool(d["cancelled"])
    return d


def timeline(limit: int | None = None) -> list[dict[str, Any]]:
    q = ("SELECT * FROM reservation WHERE superseded_by IS NULL "
         "ORDER BY start_iso DESC")
    if limit:
        q += f" LIMIT {int(limit)}"
    with get_db() as conn:
        return [_row_to_dict(r) for r in conn.execute(q).fetchall()]


def get_reservation(identity: str) -> dict[str, Any] | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM reservation WHERE identity = ?", (identity,)).fetchone()
    return _row_to_dict(row) if row else None


def now_next(now_iso: str) -> dict[str, Any]:
    with get_db() as conn:
        current = conn.execute(
            "SELECT * FROM reservation WHERE superseded_by IS NULL AND cancelled = 0 "
            "AND start_iso <= ? AND (end_iso IS NULL OR end_iso >= ?) ORDER BY start_iso DESC",
            (now_iso, now_iso)).fetchall()
        nxt = conn.execute(
            "SELECT * FROM reservation WHERE superseded_by IS NULL AND cancelled = 0 "
            "AND start_iso > ? ORDER BY start_iso ASC LIMIT 1", (now_iso,)).fetchone()
    return {"now": [_row_to_dict(r) for r in current],
            "next": _row_to_dict(nxt) if nxt else None}


def search(term: str) -> list[dict[str, Any]]:
    like = f"%{term}%"
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM reservation WHERE superseded_by IS NULL AND ("
            "dep_iata LIKE ? OR arr_iata LIKE ? OR confirmation LIKE ? OR provider LIKE ? "
            "OR title LIKE ?) ORDER BY start_iso DESC",
            (like, like, like, like, like)).fetchall()
    return [_row_to_dict(r) for r in rows]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/trips/test_store.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add src/life_agent/trips/store.py src/life_agent/trips/commands.py tests/trips/conftest.py tests/trips/test_store.py
git commit -m "feat(trips): SQLite projection store (rebuild + timeline/search/now-next)"
```

---

## Task 7: Command write layer

**Files:**
- Modify: `src/life_agent/trips/commands.py` (replace the stub)
- Create: `tests/trips/test_commands.py`

**Interfaces:**
- Produces:
  - `observe(jsonld, *, fidelity, source_id, received_at, source_meta=None) -> str` — computes identity, appends an `observed` event (idempotent on `(identity, source_id)`), rebuilds the projection, records the `source` row. Returns the identity.
  - `cancel(identity, reason, *, source_id=None, received_at=None) -> str`
  - `amend(identity, fields) -> str`
  - `supersede(old_identity, new_identity) -> str`
- Consumes: `events` (Task 4), `store` (Task 6), `identity` (Task 2).

- [ ] **Step 1: Write the failing tests**

```python
# tests/trips/test_commands.py
"""The write seam: append event -> rebuild projection. Idempotent by (identity, source_id)."""
from __future__ import annotations

from life_agent.trips import commands, store
from life_agent.trips import events as ev


def _flight() -> dict:
    return {"@type": "FlightReservation",
            "reservationFor": {"flightNumber": "EX1",
                "departureAirport": {"iataCode": "LIS"}, "arrivalAirport": {"iataCode": "AMS"},
                "departureTime": "2019-08-12T09:30:00Z"}}


def test_observe_projects_a_reservation() -> None:
    ident = commands.observe(_flight(), fidelity="kayak-api", source_id="k1",
                             received_at="2019-08-01T00:00:00")
    assert store.get_reservation(ident) is not None
    assert len(ev.load(commands.LEDGER_PATH)) == 1


def test_observe_is_idempotent_on_identity_and_source() -> None:
    for _ in range(3):
        commands.observe(_flight(), fidelity="kayak-api", source_id="k1",
                         received_at="2019-08-01T00:00:00")
    assert len(ev.load(commands.LEDGER_PATH)) == 1  # same identity+source -> one event
    assert len(store.timeline()) == 1


def test_same_flight_two_sources_are_two_events_one_row() -> None:
    commands.observe(_flight(), fidelity="kayak-api", source_id="kayak",
                     received_at="2019-08-01T00:00:00")
    ident = commands.observe(_flight(), fidelity="email-kitinerary", source_id="mail",
                             received_at="2019-08-02T00:00:00")
    assert len(ev.load(commands.LEDGER_PATH)) == 2
    assert len(store.timeline()) == 1
    assert store.get_reservation(ident)["fidelity"] == "email-kitinerary"  # email wins


def test_cancel_marks_cancelled() -> None:
    ident = commands.observe(_flight(), fidelity="email-kitinerary", source_id="m1",
                             received_at="2019-08-01T00:00:00")
    commands.cancel(ident, "airline cancelled", source_id="m2")
    assert store.get_reservation(ident)["cancelled"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/trips/test_commands.py -v`
Expected: FAIL — `AttributeError: module 'life_agent.trips.commands' has no attribute 'observe'`.

- [ ] **Step 3: Replace the stub with the full write layer**

```python
# src/life_agent/trips/commands.py
"""Trips commands — the event-sourced write layer.

Each command appends event(s) to the JSONL ledger (truth) then rebuilds the SQLite
projection from the full ledger (the fold is global, so a targeted apply would be wrong).
`observe` is idempotent on (identity, source_id): re-observing the same content from the
same source is a no-op, so re-running an import or re-ingesting a message never double-files.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from life_agent.core.config import TRIPS_LEDGER
from life_agent.trips import events as ev
from life_agent.trips import store
from life_agent.trips.identity import reservation_identity

LEDGER_PATH: Path = TRIPS_LEDGER


def _rebuild() -> None:
    with store.get_db() as conn:
        store.rebuild(conn, ev.load(LEDGER_PATH))


def _already_observed(identity: str, source_id: str) -> bool:
    return any(
        e.type == "observed" and e.identity == identity and e.source_id == source_id
        for e in ev.load(LEDGER_PATH)
    )


def observe(
    jsonld: dict[str, Any], *, fidelity: str, source_id: str, received_at: str,
    source_meta: dict[str, Any] | None = None,
) -> str:
    """Record that `source_id` observed this reservation at `fidelity`. Returns the identity."""
    identity = reservation_identity(jsonld)
    if _already_observed(identity, source_id):
        return identity  # idempotent
    ev.append(LEDGER_PATH, [ev.observed(identity, jsonld, fidelity=fidelity,
                                        source_id=source_id, received_at=received_at)])
    meta = source_meta or {}
    with store.get_db() as conn:
        store.upsert_source(conn, source_id, message_id=meta.get("message_id"),
                            path=meta.get("path"), sha256=meta.get("sha256"),
                            received_at=received_at, fidelity=fidelity,
                            kind=meta.get("kind", ""))
    _rebuild()
    return identity


def cancel(identity: str, reason: str, *, source_id: str | None = None,
           received_at: str | None = None) -> str:
    ev.append(LEDGER_PATH, [ev.cancelled(identity, reason, source_id=source_id,
                                         received_at=received_at)])
    _rebuild()
    return identity


def amend(identity: str, fields: dict[str, Any]) -> str:
    ev.append(LEDGER_PATH, [ev.amended(identity, fields)])
    _rebuild()
    return identity


def supersede(old_identity: str, new_identity: str) -> str:
    ev.append(LEDGER_PATH, [ev.superseded(old_identity, new_identity)])
    _rebuild()
    return new_identity
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/trips/test_commands.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/life_agent/trips/commands.py tests/trips/test_commands.py
git commit -m "feat(trips): command write layer (observe/cancel/amend/supersede, idempotent)"
```

---

## Task 8: Kayak ICS seeder

**Files:**
- Create: `src/life_agent/trips/seeder.py`
- Create: `tests/trips/fixtures/trip.ics` (synthetic)
- Create: `tests/trips/test_seeder.py`

**Interfaces:**
- Produces:
  - `parse_vevents(ics_text: str) -> list[dict]` — VEVENTs as `{uid, summary, description, dtstart, dtend, url}` dicts (stdlib parsing; no `icalendar` dep).
  - `pair_and_recognise(vevents) -> list[tuple[dict, str, datetime]]` — `(minimal_jsonld, trip_id, context_date)`; hotels re-paired by UID suffix, trip container events dropped (they become `trip` labels).
  - `import_ics(path: Path) -> dict` — parse → recognise → `extract()` enrich → `observe(fidelity="kayak-ics")`; returns `{"reservations": n, "trips": m}`.
- Consumes: `extract` (Task 3), `commands.observe` + `store.upsert_trip` (Tasks 6/7).

**Two ICS quirks (from the spec):** hotels are two VEVENTs (`0-<id>`, `1-<id>`) to re-pair; every event embeds `!<tripId>` and the all-day container carries the trip name/dates.

- [ ] **Step 1: Write the synthetic fixture** — `tests/trips/fixtures/trip.ics` with: one flight VEVENT, a split hotel pair (`0-h1`, `1-h1`), and an all-day trip container whose UID references `!TRIPX`. All values invented.

```
BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:evt-flight-1@example.com
SUMMARY:Flight EX 123 LIS to AMS
DESCRIPTION:Lisbon (LIS) to Amsterdam (AMS)\nhttps://www.kayak.com/trips/!TRIPX
DTSTART:20190812T093000Z
DTEND:20190812T134500Z
END:VEVENT
BEGIN:VEVENT
UID:0-hotel-h1@example.com
SUMMARY:Check in to Hotel Example
DESCRIPTION:Hotel Example, Amsterdam\nhttps://www.kayak.com/trips/!TRIPX
DTSTART:20190812T150000Z
END:VEVENT
BEGIN:VEVENT
UID:1-hotel-h1@example.com
SUMMARY:Check out from Hotel Example
DESCRIPTION:Hotel Example, Amsterdam\nhttps://www.kayak.com/trips/!TRIPX
DTSTART:20190815T110000Z
END:VEVENT
BEGIN:VEVENT
UID:!TRIPX@example.com
SUMMARY:Amsterdam trip
DTSTART;VALUE=DATE:20190812
DTEND;VALUE=DATE:20190816
END:VEVENT
END:VCALENDAR
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/trips/test_seeder.py
"""ICS seeder: recognise SUMMARY/DESCRIPTION -> minimal JSON-LD -> extract() enriches."""
from __future__ import annotations

from pathlib import Path

from life_agent.trips import seeder, store

_FIX = Path(__file__).parent / "fixtures"


def test_parse_vevents_reads_all_four() -> None:
    vevents = seeder.parse_vevents((_FIX / "trip.ics").read_text())
    assert len(vevents) == 4


def test_hotels_repair_into_one_stay() -> None:
    vevents = seeder.parse_vevents((_FIX / "trip.ics").read_text())
    recognised = seeder.pair_and_recognise(vevents)
    lodging = [j for j, _tid, _cd in recognised if j.get("@type") == "LodgingReservation"]
    assert len(lodging) == 1
    assert lodging[0]["checkinTime"].startswith("2019-08-12")
    assert lodging[0]["checkoutTime"].startswith("2019-08-15")


def test_trip_container_becomes_a_label_not_a_reservation() -> None:
    vevents = seeder.parse_vevents((_FIX / "trip.ics").read_text())
    recognised = seeder.pair_and_recognise(vevents)
    # 1 flight + 1 lodging = 2 reservations; the !TRIPX container is not one of them.
    assert len(recognised) == 2
    assert all(j.get("@type") != "TripReservation" for j, _t, _c in recognised)


def test_import_ics_lands_at_ics_fidelity(monkeypatch) -> None:
    # Stub extract() to echo its input JSON-LD (avoid depending on the live binary here).
    import json as _json
    monkeypatch.setattr(seeder, "extract",
        lambda payload, ctx: _json.loads(payload.decode()))
    stats = seeder.import_ics(_FIX / "trip.ics")
    assert stats["reservations"] == 2 and stats["trips"] == 1
    rows = store.timeline()
    assert all(r["fidelity"] == "kayak-ics" for r in rows)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/trips/test_seeder.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'life_agent.trips.seeder'`.

- [ ] **Step 4: Write the implementation**

```python
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
            slot.setdefault("name", "").replace("Check in to ", "").replace("Check out from ", "")
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/trips/test_seeder.py -v`
Expected: PASS (4 passed).

- [ ] **Step 6: Commit**

```bash
git add src/life_agent/trips/seeder.py tests/trips/fixtures/trip.ics tests/trips/test_seeder.py
git commit -m "feat(trips): Kayak ICS seeder (recognise -> enrich via extract)"
```

---

## Task 9: Kayak export importer (the coverage floor)

**Files:**
- Create: `src/life_agent/trips/kayak.py`
- Create: `tests/trips/fixtures/kayak-export.json` (synthetic, mirrors the real export shape)
- Create: `tests/trips/test_kayak.py`

**Interfaces:**
- Produces:
  - `event_to_jsonld(event: dict) -> dict | None` — one Kayak trip event → schema.org JSON-LD in the SAME shape kitinerary emits (so `reservation_identity` keys it identically to an email-derived record). `None` for an unrecognised event type.
  - `import_export(path: Path) -> dict` — parse the export JSON, iterate trips → events, `observe(fidelity="kayak-api")` each, upsert trip labels; returns `{"trips": n, "reservations": m, "skipped": k}`.
- Consumes: `commands.observe`, `store.upsert_trip`.

**Kayak event taxonomy → schema.org** (from the verified findings: 160 flight, 90 hotel, 8 train, 1 restaurant, 1 custom): `flight`→`FlightReservation` (segments → `reservationFor` list), `hotel`→`LodgingReservation`, `train`→`TrainReservation`, `restaurant`→`FoodEstablishmentReservation`, else→`Reservation` with title/start/end.

- [ ] **Step 1: Write the synthetic fixture** — `tests/trips/fixtures/kayak-export.json` with two trips, one multi-segment flight (with per-segment IATA + `departureTimeZone`), one hotel, and one event with no confirmation number (the sparse-confirmation case). Field names must match the real export keys observed during Phase 0 profiling. Invented values only. Include the degenerate flight (a segment with no flight number) so identity's defensive path is exercised end-to-end.

- [ ] **Step 2: Write the failing tests**

```python
# tests/trips/test_kayak.py
"""The Kayak export importer: the tier-3 coverage floor, full history on day one."""
from __future__ import annotations

from pathlib import Path

from life_agent.trips import kayak, store

_FIX = Path(__file__).parent / "fixtures"


def test_flight_event_maps_to_schema_org_with_segments() -> None:
    event = {"type": "flight", "eventId": "CKNpOC",
             "legs": [{"segments": [
                 {"departureAirportCode": "LIS", "arrivalAirportCode": "AMS",
                  "departureTimestamp": "2019-08-12T09:30:00", "departureTimeZone": "Europe/Lisbon",
                  "marketingCarrierCode": "TP", "flightNumber": "123"}]}]}
    jsonld = kayak.event_to_jsonld(event)
    assert jsonld["@type"] == "FlightReservation"
    seg = jsonld["reservationFor"]
    seg0 = seg[0] if isinstance(seg, list) else seg
    assert seg0["departureAirport"]["iataCode"] == "LIS"


def test_import_projects_full_history_at_kayak_fidelity() -> None:
    stats = kayak.import_export(_FIX / "kayak-export.json")
    assert stats["reservations"] >= 3
    rows = store.timeline()
    assert rows and all(r["fidelity"] == "kayak-api" for r in rows)


def test_reimport_is_idempotent() -> None:
    kayak.import_export(_FIX / "kayak-export.json")
    first = len(store.timeline())
    kayak.import_export(_FIX / "kayak-export.json")  # again
    assert len(store.timeline()) == first  # observe() dedupes by (identity, source_id)


def test_kayak_and_email_of_same_flight_dedupe_to_one_row() -> None:
    """The whole point: a Kayak flight and its own confirmation email are ONE identity."""
    from life_agent.trips import commands
    kayak.import_export(_FIX / "kayak-export.json")
    before = len(store.timeline())
    # Re-observe the first flight's content as an email at higher fidelity.
    row = next(r for r in store.timeline() if r["res_type"] == "FlightReservation")
    import json
    commands.observe(json.loads(row["jsonld"]), fidelity="email-kitinerary",
                     source_id="mail-x", received_at="2019-09-01T00:00:00")
    after = store.timeline()
    assert len(after) == before  # no new row
    upgraded = store.get_reservation(row["identity"])
    assert upgraded["fidelity"] == "email-kitinerary"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/trips/test_kayak.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'life_agent.trips.kayak'`.

- [ ] **Step 4: Write the implementation**

```python
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
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from life_agent.trips import commands, store

_TYPE_MAP = {
    "flight": "FlightReservation",
    "hotel": "LodgingReservation",
    "train": "TrainReservation",
    "restaurant": "FoodEstablishmentReservation",
}


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
    schema_type = _TYPE_MAP.get(kind)
    if schema_type is None and kind not in ("custom", "activity", "event"):
        schema_type = None
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/trips/test_kayak.py -v`
Expected: PASS (4 passed). If the fixture's event key names differ from the real export, align them to the real profiled keys (the DEEP capture saved during Phase 0 at `/path/to/kayak-trips-export.json` — read its structure, mirror the key names into `event_to_jsonld`, keep the fixture VALUES synthetic).

- [ ] **Step 6: Commit**

```bash
git add src/life_agent/trips/kayak.py tests/trips/fixtures/kayak-export.json tests/trips/test_kayak.py
git commit -m "feat(trips): Kayak export importer (tier-3 coverage floor, dedupes with email)"
```

---

## Task 10: The `trips` CLI

**Files:**
- Create: `src/life_agent/trips/cli.py`
- Create: `tests/trips/test_cli.py`
- Modify: `pyproject.toml` (register console script if the repo uses `[project.scripts]`)

**Interfaces:**
- Produces: `main(argv: list[str] | None = None) -> int` and subcommands:
  - `trips import-kayak <export.json>` → prints trip/reservation counts.
  - `trips import-ics <feed.ics>` → prints counts.
  - `trips ingest <path>` → `extract()` a single email/PDF file and `observe(fidelity="email-kitinerary")` its reservations (proves the upgrade path end-to-end on one file; the mailbox-scale selection is Plan 2).
  - `trips list [--limit N]` → the reverse-chronological timeline.
  - `trips show <identity>` → one reservation's detail (incl. verbatim JSON-LD).
  - `trips search <term>` → matching reservations.
  - `trips supersede <old> <new>` → link an evolving booking.
- Consumes: `kayak`, `seeder`, `extract`, `commands`, `store`.

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/trips/test_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'life_agent.trips.cli'`.

- [ ] **Step 3: Write the implementation**

```python
# src/life_agent/trips/cli.py
"""The `trips` command line — importers + queries over the itinerary ledger.

`import-kayak` lays down the tier-3 history; `ingest <path>` upgrades a single record from a
filed email (the mailbox-scale selection is Plan 2); `list`/`show`/`search` read the
projection. Every write goes through commands.* -> the append-only ledger, exactly like GTD.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from email import policy
from email import message_from_bytes
from email.utils import parsedate_to_datetime
from pathlib import Path

from life_agent.trips import commands, kayak, seeder, store
from life_agent.trips.extract import extract


def _fmt(row: dict) -> str:
    when = (row.get("start_iso") or "?")[:16]
    route = f"{row.get('dep_iata') or ''}->{row.get('arr_iata') or ''}".strip("->")
    label = route or row.get("title") or row.get("res_type")
    flags = " [CANCELLED]" if row.get("cancelled") else ""
    return f"{when}  {row.get('res_type'):24} {label}  <{row.get('fidelity')}>{flags}"


def _cmd_import_kayak(args: argparse.Namespace) -> int:
    stats = kayak.import_export(Path(args.path))
    print(f"imported {stats['reservations']} reservations across {stats['trips']} trips "
          f"({stats['skipped']} skipped)")
    return 0


def _cmd_import_ics(args: argparse.Namespace) -> int:
    stats = seeder.import_ics(Path(args.path))
    print(f"imported {stats['reservations']} reservations across {stats['trips']} trips")
    return 0


def _cmd_ingest(args: argparse.Namespace) -> int:
    path = Path(args.path)
    raw = path.read_bytes()
    try:
        msg = message_from_bytes(raw, policy=policy.default)
        ctx = parsedate_to_datetime(msg["Date"]) if msg["Date"] else datetime.now()
    except Exception:
        ctx = datetime.now()
    n = 0
    for jsonld in extract(raw, ctx):
        commands.observe(jsonld, fidelity="email-kitinerary",
                         source_id=f"file:{path.name}",
                         received_at=ctx.isoformat(),
                         source_meta={"path": str(path), "kind": "email"})
        n += 1
    print(f"ingested {n} reservation(s) from {path.name}")
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    rows = store.timeline(limit=args.limit)
    if not rows:
        print("no reservations")
        return 0
    for r in rows:
        print(_fmt(r))
    return 0


def _cmd_show(args: argparse.Namespace) -> int:
    row = store.get_reservation(args.identity)
    if not row:
        print("not found")
        return 1
    print(_fmt(row))
    print(json.dumps(json.loads(row["jsonld"]), indent=2))
    return 0


def _cmd_search(args: argparse.Namespace) -> int:
    for r in store.search(args.term):
        print(_fmt(r))
    return 0


def _cmd_supersede(args: argparse.Namespace) -> int:
    commands.supersede(args.old, args.new)
    print(f"{args.old} superseded by {args.new}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="trips", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn, pos in [
        ("import-kayak", _cmd_import_kayak, [("path", {})]),
        ("import-ics", _cmd_import_ics, [("path", {})]),
        ("ingest", _cmd_ingest, [("path", {})]),
        ("show", _cmd_show, [("identity", {})]),
        ("search", _cmd_search, [("term", {})]),
        ("supersede", _cmd_supersede, [("old", {}), ("new", {})]),
    ]:
        sp = sub.add_parser(name)
        for arg, kw in pos:
            sp.add_argument(arg, **kw)
        sp.set_defaults(func=fn)
    lp = sub.add_parser("list")
    lp.add_argument("--limit", type=int, default=None)
    lp.set_defaults(func=_cmd_list)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return int(e.code or 2)
    store.init_db()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/trips/test_cli.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Register the console script** (only if `pyproject.toml` has `[project.scripts]`; otherwise document `python -m life_agent.trips.cli`)

```toml
# pyproject.toml, under [project.scripts]
trips = "life_agent.trips.cli:main"
```

- [ ] **Step 6: Run the full trips suite + gates**

Run: `uv run pytest tests/trips/ -v -m "not system"` → all pass.
Run: `uv run ruff check src/life_agent/trips/ tests/trips/` → clean.
Run: `uv run mypy` → clean (no new errors under `src/life_agent/trips/`).

- [ ] **Step 7: Commit**

```bash
git add src/life_agent/trips/cli.py tests/trips/test_cli.py pyproject.toml
git commit -m "feat(trips): trips CLI (import-kayak/import-ics/ingest/list/show/search/supersede)"
```

---

## Task 11: End-to-end acceptance on the real export

**Files:**
- Create: `tests/trips/test_acceptance.py` (marked `@pytest.mark.system` — needs the real export + binary, run manually, not in CI)

**Interfaces:** none new — this exercises the whole stack against the operator's private data outside the repo. The export path comes from an env var (`TRIPS_KAYAK_EXPORT`), never a literal.

- [ ] **Step 1: Write the acceptance test**

```python
# tests/trips/test_acceptance.py
"""Manual acceptance against the real Kayak export (private, out-of-repo). Run:
    TRIPS_KAYAK_EXPORT=/path/to/kayak-trips-export.json uv run pytest \
        tests/trips/test_acceptance.py -m system -v
The export path is an env var — never a literal (public repo, PII)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from life_agent.trips import kayak, store


@pytest.mark.system
def test_full_export_imports_and_dedupes() -> None:
    src = os.environ.get("TRIPS_KAYAK_EXPORT")
    if not src:
        pytest.skip("set TRIPS_KAYAK_EXPORT to the real export to run acceptance")
    stats = kayak.import_export(Path(src).expanduser())
    # The design measured 260 events -> 259 identities (one true duplicate collapses).
    assert stats["reservations"] >= 250
    rows = store.timeline()
    assert len(rows) <= stats["reservations"]  # dedup never inflates
    # Re-import is a no-op.
    again = len(store.timeline())
    kayak.import_export(Path(src).expanduser())
    assert len(store.timeline()) == again
```

- [ ] **Step 2: Run it manually against the real export**

Run: `TRIPS_KAYAK_EXPORT=/path/to/kayak-trips-export.json uv run pytest tests/trips/test_acceptance.py -m system -v`
Expected: PASS — ~259 rows from 260 events, re-import idempotent. If the count is off, the event-key mapping in `kayak.event_to_jsonld` needs aligning to the real export keys (read the real file's structure; keep fixtures synthetic).

- [ ] **Step 3: Verify the ledger + projection live under KB, not the repo**

Run: `git status` → no untracked `*.jsonl`/`*.db` anywhere in the worktree (they are written under `$LIFE_AGENT_KB/trips/`).
Run: `python3 .githooks/pii_check.py $(git diff --cached --name-only)` before committing → clean.

- [ ] **Step 4: Commit**

```bash
git add tests/trips/test_acceptance.py
git commit -m "test(trips): manual acceptance against the real Kayak export"
```

---

## Self-Review

**Spec coverage** — every Phase-1 core requirement maps to a task:

| Spec section | Task |
|---|---|
| Extraction seam (`extract(payload, context_date)`) | 3 |
| Reservation identity (content-keyed, degenerate cases) | 2 |
| Data model: ledger + `source`/`reservation`/`trip` projection | 4, 6 |
| Fidelity tiers + supersession + cancellation | 4, 5 |
| "Kayak import gives full history day one; records upgrade" | 9 (+5, +7) |
| Never infer cancellation from Kayak absence | 5, 9 (tested) |
| The seeder trick (ICS → minimal JSON-LD → enrich) | 8 |
| Hotel re-pairing + trip grouping | 8 |
| Idempotency (ingest twice = no-op) | 7, 9 |
| Config-not-values (paths/keys, synthetic fixtures) | 1, all fixtures |
| Testing: supersession first, cross-tier upgrade, idempotency, no-socket dispatch | 5, 9, 7, (dispatch → Plan 3) |

**Deferred to later plans (out of this plan's scope, by design):**
- **Plan 2 — mailbox ingest:** the notmuch-query selection + forward-to-original resolution (`X-Forwarded-Message-Id` → `In-Reply-To` → `References` → subject) feeding `extract()` via a `trips ingest-mail` verb; the booking-signal query in `$LIFE_AGENT_KB/config/trips.yaml`. Depends only on this plan's `extract`/`commands` seam.
- **Plan 3 — surfaces:** the web timeline (`dispatch(user_id, method, path, body)` + one self-contained `index.html`, mirroring `reach/web`) and the ICS calendar feed (`kitinerary -o iCal`). Depends only on this plan's `store` read queries.
- **Automatic PNR-correlator** (emitting `superseded` events from raw ingest) — the risky heuristic; its own plan.

**Placeholder scan:** no `TODO`/`TBD`/"handle edge cases"/"similar to Task N" — every code step carries runnable code. The one deliberate manual step (Task 11) is a marked `system` test against private data, with the reason stated.

**Type consistency:** `reservation_identity(jsonld)` (single dict arg) is used identically in `identity`, `commands`, and both importers. `observe(jsonld, *, fidelity, source_id, received_at, source_meta=None)` matches across `commands`, `kayak`, `seeder`, `cli`. `Reservation` fields (`identity, jsonld, fidelity, source_id, received_at, cancelled, superseded_by`) match between `fold` and `store._project_columns`. `fold(events) -> dict[str, Reservation]` consumed by `store.rebuild`. `extract(payload: bytes, context_date: datetime) -> list[dict]` consumed by `seeder`, `cli`. Fidelity strings (`kayak-api`, `email-kitinerary`, `kayak-ics`, `manual`) match `FIDELITY_RANK` keys everywhere.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-23-trips-core-and-kayak-import.md`. Two execution options:

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
