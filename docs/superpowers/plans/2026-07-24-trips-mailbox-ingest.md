# Trips Mailbox Ingest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Grow the trips timeline from the mailbox — a notmuch-query-selected, forward-resolved, idempotent batch ingest that upgrades reservations to `email-kitinerary` fidelity through the existing `extract` → `observe` seams.

**Architecture:** Three new modules under `src/life_agent/trips/`: a subprocess adapter over the `notmuch` binary (`notmuch.py`), pure forward→original resolution (`forwards.py`), and the orchestration that wires selection → resolution → `extract()` → `commands.observe()` (`mailbox.py`). A config seam (`core/config.py` + `config/data-sources.example.yaml`) supplies the owner-specific query. A `trips ingest-mail` CLI subcommand drives it. No existing *code* seam is modified; the one shared touch is additive — a new `trips:` top-level key in the existing `config/data-sources.example.yaml` registry (whose loader ignores unknown top-level keys).

**Tech Stack:** Python 3.13, stdlib (`subprocess`, `email`, `hashlib`, `dataclasses`, `re`), `pyyaml` (already a dependency), `notmuch` CLI (external system binary), `uv`-managed project. Tests via `uv run python -m pytest`.

## Global Constraints

Every task's requirements implicitly include this section. Values are copied verbatim from `docs/superpowers/specs/2026-07-24-trips-mailbox-ingest-design.md`.

- **Personal data is never in code.** The notmuch query, ingest address, maildir roots, and binary path are env/YAML **configuration** — code holds the key, never the value. A path or query literal in a module is a bug. `config/data-sources.example.yaml` carries **placeholders only** (`<kayak-ingest-address>`, `<booking-domains>`); the real value lives only under `$LIFE_AGENT_KB`, never in the repo. Do **not** write any absolute machine path (e.g. a user home directory) into any committed file — the `.githooks/pii_check.py` hook blocks it.
- **Fixtures are synthetic by construction** — no live notmuch, no real message content, no real PNRs/addresses. notmuch tests **monkeypatch `subprocess`** (never invoke the real binary) and must run in the **default** suite (NOT gated behind `-m system`).
- **One extraction seam, one write path.** Reuse `trips/extract.py::extract` and `trips/commands.py::observe` **unchanged**. Ingest adds selection + resolution; it never adds a second parser or a second write path.
- **Ledger is truth.** Ingest only appends via `commands.observe`; it never writes projection columns or reservation content into the repo tree.
- **notmuch failures RAISE** (`NotmuchError`) — a missing binary, unreadable index, or malformed query aborts the run loudly. This is categorically different from `extract`'s silent `[]` for a non-booking (a wasted parse, never a wrong record). Within a batch, a single malformed message is **logged, skipped, and counted** — one bad mail never aborts the run; but a failure of the top-level `search` propagates.
- **Idempotency** is via `observe`'s existing `(identity, source_id)` dedup. `source_id = f"mail:{message_id}"` where `message_id` is the **winning** candidate's `Message-ID`. Re-running a broadened query is a no-op.
- **Fidelity** for all mailbox-ingested reservations is `"email-kitinerary"` (tier 2).
- **Run tests with** `uv run python -m pytest` (bare `python` raises `ModuleNotFoundError: life_agent`). The default filter is `-m 'not llm and not system'`.

---

### Task 1: Config seam — `NOTMUCH_BINARY`, `DATA_SOURCES`, `data_sources()`

**Files:**
- Modify: `src/life_agent/core/config.py` (add imports + three additions after the `KITINERARY_EXTRACTOR` line, ~line 48)
- Modify: `config/data-sources.example.yaml` — **it already exists** (the `scripts/data_source_registry.py` schema: `version:1` + `roots`, documented by README/SETUP). Do NOT overwrite it. Restore its original content and **append** a `trips:` section. The registry loader reads only `version`+`roots` and ignores unknown top-level keys, so `trips:` is a safe additive extension.
- Test: `tests/trips/test_config_trips.py` (append)

**Interfaces:**
- Consumes: existing `KB` path constant in `config.py`; the existing registry path convention `KB / "config" / "data-sources.yaml"` (= `scripts/data_source_registry.default_registry_path()`).
- Produces: `config.NOTMUCH_BINARY: str`, `config.DATA_SOURCES: Path` (= `KB / "config" / "data-sources.yaml"`), `config.data_sources() -> dict[str, Any]`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/trips/test_config_trips.py`:

```python
def test_notmuch_binary_defaults_and_env_overridable(monkeypatch) -> None:
    monkeypatch.setenv("NOTMUCH_BINARY", "/opt/notmuch")
    reloaded = importlib.reload(config)
    assert reloaded.NOTMUCH_BINARY == "/opt/notmuch"
    monkeypatch.delenv("NOTMUCH_BINARY", raising=False)
    assert importlib.reload(config).NOTMUCH_BINARY == "notmuch"


def test_data_sources_absent_returns_empty(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(config, "DATA_SOURCES", tmp_path / "nope.yaml")
    assert config.data_sources() == {}


def test_data_sources_default_is_the_existing_registry_path() -> None:
    # Same file scripts/data_source_registry.default_registry_path() resolves, so the query
    # and the source roots share one registry (loader ignores the extra `trips:` key).
    assert config.DATA_SOURCES == config.KB / "config" / "data-sources.yaml"


def test_data_sources_reads_yaml(tmp_path, monkeypatch) -> None:
    f = tmp_path / "data-sources.yaml"
    f.write_text("trips:\n  ingest:\n    query: 'folder:Trips'\n", encoding="utf-8")
    monkeypatch.setattr(config, "DATA_SOURCES", f)
    assert config.data_sources()["trips"]["ingest"]["query"] == "folder:Trips"


def test_data_sources_non_mapping_yaml_returns_empty(tmp_path, monkeypatch) -> None:
    f = tmp_path / "data-sources.yaml"
    f.write_text("- just\n- a\n- list\n", encoding="utf-8")
    monkeypatch.setattr(config, "DATA_SOURCES", f)
    assert config.data_sources() == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/trips/test_config_trips.py -q`
Expected: FAIL — `AttributeError: module 'life_agent.core.config' has no attribute 'NOTMUCH_BINARY'` / `data_sources`.

- [ ] **Step 3: Add the config additions**

In `src/life_agent/core/config.py`, add `Any` to the typing imports at the top (the file currently imports only `os`, `shlex`, `pathlib.Path` — add the line):

```python
from typing import Any
```

Then, immediately after the `KITINERARY_EXTRACTOR = ...` line (~line 48), add:

```python
# The notmuch binary — the mailbox selection seam (trips/notmuch.py), wrapped as a producer
# exactly like the extractor above. Override per-machine via the env var; default assumes it
# is on PATH.
NOTMUCH_BINARY = os.environ.get("NOTMUCH_BINARY", "notmuch")
# The owner's declarative data-source registry — the SAME file scripts/data_source_registry.py
# uses (its default_registry_path() is KB/config/data-sources.yaml). The notmuch query lives
# here as a `trips:` key the registry loader ignores (it reads only version+roots). All
# owner-specific PII (query, ingest address); code holds the KEY (trips.ingest.query), the
# VALUE lives only under $LIFE_AGENT_KB. See config/data-sources.example.yaml for the shape.
DATA_SOURCES = KB / "config" / "data-sources.yaml"


def data_sources() -> dict[str, Any]:
    """Parse the data-source registry. Returns ``{}`` when the file is absent (so a machine
    without it never hard-fails) or when its top level is not a mapping. A generic reader,
    independent of the registry's version/roots validation. No PII in code — the values it
    returns are read from ``$LIFE_AGENT_KB``, never a literal here."""
    if not DATA_SOURCES.exists():
        return {}
    import yaml

    parsed = yaml.safe_load(DATA_SOURCES.read_text(encoding="utf-8"))
    return parsed if isinstance(parsed, dict) else {}
```

- [ ] **Step 4: Extend the EXISTING example config (restore + append `trips:`)**

`config/data-sources.example.yaml` already exists and is documented by README/SETUP and consumed by `scripts/data_source_registry.py`. Task 1's implementer overwrote it — first **restore its original content**, then **append** the `trips:` section (do not remove `version`/`roots`):

```bash
git show 6b6e0d8:config/data-sources.example.yaml > config/data-sources.example.yaml
```

Then append (placeholders only — the registry loader ignores this unknown top-level key):

```yaml

# --- Trips mailbox ingest (life_agent.trips) --------------------------------
# A top-level key the registry loader ignores (it reads only version+roots); read by
# life_agent.core.config.data_sources() and life_agent.trips.mailbox.configured_query().
trips:
  ingest:
    # notmuch query selecting booking mail. The breadth is deliberate: a false positive is a
    # wasted parse (extract returns []), never a wrong record. Compose the filing gesture, the
    # Kayak-forward history, and non-forwarded bookings. Placeholders only — the REAL value
    # lives in $LIFE_AGENT_KB/config/data-sources.yaml, never in this repo:
    query: 'folder:Trips or to:<kayak-ingest-address> or (from:/<booking-domains>/ and subject:/<booking-signal>/)'
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run python -m pytest tests/trips/test_config_trips.py -q`
Expected: PASS (all, including the two pre-existing tests).

- [ ] **Step 6: Commit**

```bash
git add src/life_agent/core/config.py config/data-sources.example.yaml tests/trips/test_config_trips.py
git commit -m "feat(trips): config seam for notmuch binary + data-sources.yaml query"
```

---

### Task 2: notmuch adapter — `trips/notmuch.py`

**Files:**
- Create: `src/life_agent/trips/notmuch.py`
- Test: `tests/trips/test_notmuch.py`

**Interfaces:**
- Consumes: `config.NOTMUCH_BINARY` (Task 1).
- Produces: `notmuch.search(query: str) -> list[str]`, `notmuch.show_raw(msgid: str) -> bytes`, `notmuch.NotmuchError` (subclass of `RuntimeError`), module attribute `notmuch.BINARY: str`.

- [ ] **Step 1: Write the failing tests**

Create `tests/trips/test_notmuch.py`:

```python
"""The mailbox selection seam: a subprocess wrapper over the notmuch binary. Unlike extract,
it RAISES on failure — a broken index must never be a silent empty ingest. Fully hermetic:
subprocess is monkeypatched, the real binary is never invoked."""
from __future__ import annotations

import pytest

from life_agent.trips import notmuch as nm


class _Completed:
    def __init__(self, returncode: int, stdout: bytes, stderr: bytes = b"") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _fake_run(result=None, exc=None):
    def run(args, **kwargs):
        if exc is not None:
            raise exc
        return result
    return run


def test_search_parses_and_strips_id_prefix(monkeypatch) -> None:
    out = b"id:aaa@x\nid:bbb@y\n"
    monkeypatch.setattr(nm.subprocess, "run", _fake_run(_Completed(0, out)))
    assert nm.search("folder:Trips") == ["aaa@x", "bbb@y"]


def test_search_empty_returns_empty_list(monkeypatch) -> None:
    monkeypatch.setattr(nm.subprocess, "run", _fake_run(_Completed(0, b"")))
    assert nm.search("folder:Trips") == []


def test_show_raw_returns_bytes(monkeypatch) -> None:
    monkeypatch.setattr(nm.subprocess, "run", _fake_run(_Completed(0, b"From: a\r\n\r\nhi")))
    assert nm.show_raw("aaa@x") == b"From: a\r\n\r\nhi"


def test_missing_binary_raises(monkeypatch) -> None:
    monkeypatch.setattr(nm.subprocess, "run", _fake_run(exc=FileNotFoundError()))
    with pytest.raises(nm.NotmuchError):
        nm.search("folder:Trips")


def test_nonzero_exit_raises(monkeypatch) -> None:
    monkeypatch.setattr(nm.subprocess, "run", _fake_run(_Completed(1, b"", b"bad query")))
    with pytest.raises(nm.NotmuchError):
        nm.search("(((")


def test_show_raw_empty_body_raises(monkeypatch) -> None:
    monkeypatch.setattr(nm.subprocess, "run", _fake_run(_Completed(0, b"")))
    with pytest.raises(nm.NotmuchError):
        nm.show_raw("missing@x")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/trips/test_notmuch.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'life_agent.trips.notmuch'`.

- [ ] **Step 3: Write the module**

Create `src/life_agent/trips/notmuch.py`:

```python
"""The mailbox selection seam: a subprocess wrapper over the ``notmuch`` binary.

Follows the trips/extract.py precedent — a system binary wrapped as a producer, no new Python
dependency. Unlike extract (which returns ``[]`` for a non-booking and never raises), notmuch
failures RAISE: a missing binary, unreadable index, or malformed query is an operational error
the owner must see, never a silent empty ingest. Selection + fetch only; the bytes it returns
flow into the same extract() seam.
"""
from __future__ import annotations

import subprocess

from life_agent.core.config import NOTMUCH_BINARY

BINARY: str = NOTMUCH_BINARY
_TIMEOUT_SECONDS = 120


class NotmuchError(RuntimeError):
    """A notmuch invocation failed — abort the run loudly (not a silent empty result)."""


def _run(args: list[str]) -> bytes:
    try:
        completed = subprocess.run(
            [BINARY, *args], capture_output=True, timeout=_TIMEOUT_SECONDS, check=False,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as exc:
        raise NotmuchError(f"notmuch invocation failed: {exc}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.decode(errors="replace")[:200]
        raise NotmuchError(f"notmuch exited {completed.returncode}: {detail}")
    return completed.stdout


def search(query: str) -> list[str]:
    """Message-ids matching ``query`` (the ``id:`` prefix stripped). Empty result -> ``[]``."""
    out = _run(["search", "--output=messages", query]).decode(errors="replace")
    ids: list[str] = []
    for raw in out.splitlines():
        line = raw.strip()
        if not line:
            continue
        ids.append(line[3:] if line.startswith("id:") else line)
    return ids


def show_raw(msgid: str) -> bytes:
    """Raw RFC-822 bytes for one message. Raises when notmuch yields nothing for the id."""
    out = _run(["show", "--format=raw", f"id:{msgid}"])
    if not out:
        raise NotmuchError(f"notmuch returned no body for id:{msgid}")
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/trips/test_notmuch.py -q`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add src/life_agent/trips/notmuch.py tests/trips/test_notmuch.py
git commit -m "feat(trips): notmuch subprocess adapter (search/show_raw, raises loudly)"
```

---

### Task 3: Forward resolution — `trips/forwards.py`

**Files:**
- Create: `src/life_agent/trips/forwards.py`
- Test: `tests/trips/test_forwards.py`

**Interfaces:**
- Consumes: nothing (pure; the notmuch lookup is injected).
- Produces: `forwards.resolve_original(headers: Mapping[str, str], lookup: Callable[[str], list[str]]) -> str | None`.

- [ ] **Step 1: Write the failing tests**

Create `tests/trips/test_forwards.py`:

```python
"""Pure forward->original resolution. The notmuch lookup is injected (a dict), so this is
socket-free. Precedence: X-Forwarded-Message-Id -> In-Reply-To -> last References -> subject."""
from __future__ import annotations

from collections.abc import Callable

from life_agent.trips import forwards


def _lookup(mapping: dict[str, list[str]]) -> Callable[[str], list[str]]:
    return lambda query: mapping.get(query, [])


def test_x_forwarded_message_id_wins() -> None:
    headers = {"Message-ID": "<fwd@x>", "X-Forwarded-Message-Id": "<orig@x>",
               "In-Reply-To": "<other@x>"}
    got = forwards.resolve_original(headers, _lookup({"id:orig@x": ["orig@x"]}))
    assert got == "orig@x"


def test_in_reply_to_when_no_xforwarded() -> None:
    headers = {"Message-ID": "<fwd@x>", "In-Reply-To": "<orig@x>"}
    assert forwards.resolve_original(headers, _lookup({"id:orig@x": ["orig@x"]})) == "orig@x"


def test_references_uses_last_id() -> None:
    headers = {"Message-ID": "<fwd@x>", "References": "<a@x> <b@x> <orig@x>"}
    assert forwards.resolve_original(headers, _lookup({"id:orig@x": ["orig@x"]})) == "orig@x"


def test_subject_match_after_stripping_repeated_mixed_case_prefixes() -> None:
    headers = {"Message-ID": "<fwd@x>", "Subject": "Fwd: RE: Fw: Your booking ABC"}
    lookup = _lookup({'subject:"Your booking ABC"': ["orig@x"]})
    assert forwards.resolve_original(headers, lookup) == "orig@x"


def test_returns_none_when_nothing_resolves() -> None:
    headers = {"Message-ID": "<fwd@x>", "X-Forwarded-Message-Id": "<gone@x>"}
    assert forwards.resolve_original(headers, _lookup({})) is None


def test_never_returns_the_forward_itself() -> None:
    # A subject search that only finds the forward itself must not resolve to it.
    headers = {"Message-ID": "<fwd@x>", "Subject": "Fwd: Booking"}
    assert forwards.resolve_original(headers, _lookup({'subject:"Booking"': ["fwd@x"]})) is None


def test_plain_subject_without_prefix_is_not_searched() -> None:
    # No forwarding prefix -> no broad subject lookup (would match unrelated mail).
    called: list[str] = []

    def lookup(q: str) -> list[str]:
        called.append(q)
        return ["someone@x"]

    headers = {"Message-ID": "<msg@x>", "Subject": "Booking confirmation"}
    assert forwards.resolve_original(headers, lookup) is None
    assert called == []  # nothing was looked up


def test_precedence_xforwarded_over_references() -> None:
    headers = {"Message-ID": "<fwd@x>", "X-Forwarded-Message-Id": "<a@x>",
               "References": "<b@x>"}
    lookup = _lookup({"id:a@x": ["a@x"], "id:b@x": ["b@x"]})
    assert forwards.resolve_original(headers, lookup) == "a@x"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/trips/test_forwards.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'life_agent.trips.forwards'`.

- [ ] **Step 3: Write the module**

Create `src/life_agent/trips/forwards.py`:

```python
"""Resolve a forwarded booking mail back to the original it forwarded, before extraction.

Design-mandated (docs/trips-design.md §Ingest): resolution doubles corpus yield (39->80
reservations) and is the sole recovery path for pre-2018 history. Pure logic — the notmuch
``id:``/``subject:`` lookups are injected, so this is socket-free and fully unit-tested.
Precedence, first that resolves to an existing, different message wins:
X-Forwarded-Message-Id -> In-Reply-To -> last References id -> subject match (prefixes stripped).
"""
from __future__ import annotations

import re
from collections.abc import Callable, Mapping

# Forwarding / reply subject prefixes across the clients in a 15-year corpus (en/fr/de/nl...).
_PREFIX_RE = re.compile(
    r"^\s*(?:(?:re|fwd?|tr|wg|rv|sv|vs|aw|antw)\s*:\s*)+", re.IGNORECASE
)


def _clean_id(raw: str) -> str:
    """Strip surrounding <> and whitespace from a Message-ID header value."""
    return raw.strip().strip("<>").strip()


def _strip_prefixes(subject: str) -> str:
    return _PREFIX_RE.sub("", subject).strip()


def _references_last(value: str) -> str | None:
    ids = re.findall(r"<[^>]+>", value)
    return _clean_id(ids[-1]) if ids else None


def resolve_original(
    headers: Mapping[str, str],
    lookup: Callable[[str], list[str]],
) -> str | None:
    """Return the msgid this forward forwarded, or ``None`` if unresolved.

    ``lookup(query)`` runs a notmuch query and returns matching msgids — injected so this stays
    pure. The forward's own Message-ID is never returned as its 'original'.
    """
    own = _clean_id(headers.get("Message-ID", ""))

    queries: list[str] = []
    if xfwd := headers.get("X-Forwarded-Message-Id"):
        queries.append(f"id:{_clean_id(xfwd)}")
    if irt := headers.get("In-Reply-To"):
        queries.append(f"id:{_clean_id(irt)}")
    if (refs := headers.get("References")) and (last := _references_last(refs)):
        queries.append(f"id:{last}")

    for query in queries:
        for mid in lookup(query):
            if mid and mid != own:
                return mid

    subject = headers.get("Subject")
    if subject:
        stripped = _strip_prefixes(subject)
        # Only search when the subject ACTUALLY carried a forwarding prefix — otherwise a plain
        # booking would trigger a broad subject match against unrelated mail.
        if stripped and stripped != subject.strip():
            for mid in lookup(f'subject:"{stripped}"'):
                if mid and mid != own:
                    return mid
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/trips/test_forwards.py -q`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add src/life_agent/trips/forwards.py tests/trips/test_forwards.py
git commit -m "feat(trips): pure forward->original resolution (4-tier precedence)"
```

---

### Task 4: Ingest orchestration — `trips/mailbox.py`

**Files:**
- Create: `src/life_agent/trips/mailbox.py`
- Test: `tests/trips/test_mailbox.py`

**Interfaces:**
- Consumes: `notmuch.search`/`show_raw`/`NotmuchError` (Task 2), `forwards.resolve_original` (Task 3), `extract` (Plan 1), `commands.observe` (Plan 1), `config.data_sources`/`config.DATA_SOURCES` (Task 1).
- Produces: `mailbox.ingest_query(query, *, nm=..., extract_fn=..., observe_fn=..., limit=None, dry_run=False) -> Stats`, `mailbox.configured_query() -> str`, `mailbox.Stats` (dataclass: `selected, forwards_resolved, messages_with_yield, reservations, errors`), `mailbox.IngestConfigError`.

- [ ] **Step 1: Write the failing tests**

Create `tests/trips/test_mailbox.py` (the autouse `temp_trips` fixture from `tests/trips/conftest.py` gives a tmp ledger + db):

```python
"""Mailbox ingest orchestration: select -> resolve forward -> extract higher-yield -> observe.
Hermetic: notmuch + extract are injected fakes; observe is the real write seam over the tmp
ledger, so idempotency and provenance are asserted against real projection state."""
from __future__ import annotations

import pytest

from life_agent.trips import commands, mailbox, store
from life_agent.trips import events as ev
from life_agent.trips import notmuch as nm


def _eml(message_id: str, subject: str = "Booking",
         date: str = "Mon, 12 Aug 2019 09:00:00 +0000", extra: str = "") -> bytes:
    head = f"Message-ID: <{message_id}>\r\nDate: {date}\r\nSubject: {subject}\r\n"
    return (head + extra + "\r\nbody\r\n").encode()


def _flight(fno: str) -> dict:
    return {"@type": "FlightReservation",
            "reservationFor": {"flightNumber": fno,
                "departureAirport": {"iataCode": "LIS"},
                "arrivalAirport": {"iataCode": "AMS"},
                "departureTime": "2019-08-12T09:30:00Z"}}


class FakeNm:
    """Stands in for the notmuch module: search() + show_raw(), plus the real error class."""
    NotmuchError = nm.NotmuchError

    def __init__(self, raws: dict[str, bytes], search_map: dict[str, list[str]]) -> None:
        self.raws = raws
        self.search_map = search_map

    def search(self, query: str) -> list[str]:
        return self.search_map.get(query, [])

    def show_raw(self, msgid: str) -> bytes:
        return self.raws[msgid]


def test_ingests_from_higher_yield_original() -> None:
    fwd = _eml("fwd@x", subject="Fwd: Booking", extra="X-Forwarded-Message-Id: <orig@x>\r\n")
    orig = _eml("orig@x")
    fake = FakeNm(raws={"fwd@x": fwd, "orig@x": orig},
                  search_map={"q": ["fwd@x"], "id:orig@x": ["orig@x"]})
    extract_map = {fwd: [_flight("EX1")], orig: [_flight("EX1"), _flight("EX2")]}
    stats = mailbox.ingest_query("q", nm=fake, extract_fn=lambda raw, ctx: extract_map[raw])
    assert stats.forwards_resolved == 1
    assert stats.reservations == 2            # from the original, the higher-yield candidate
    assert len(store.timeline()) == 2
    # provenance: source_id is the ORIGINAL's message id
    with store.get_db() as conn:
        srcs = {r["source_id"] for r in conn.execute("SELECT source_id FROM source")}
    assert srcs == {"mail:orig@x"}


def test_tie_prefers_original() -> None:
    fwd = _eml("fwd@x", subject="Fwd: Booking", extra="X-Forwarded-Message-Id: <orig@x>\r\n")
    orig = _eml("orig@x")
    fake = FakeNm(raws={"fwd@x": fwd, "orig@x": orig},
                  search_map={"q": ["fwd@x"], "id:orig@x": ["orig@x"]})
    extract_map = {fwd: [_flight("EX1")], orig: [_flight("EX1")]}   # equal yield
    mailbox.ingest_query("q", nm=fake, extract_fn=lambda raw, ctx: extract_map[raw])
    with store.get_db() as conn:
        srcs = {r["source_id"] for r in conn.execute("SELECT source_id FROM source")}
    assert srcs == {"mail:orig@x"}            # tie -> original


def test_non_booking_yields_nothing() -> None:
    msg = _eml("m@x")
    fake = FakeNm(raws={"m@x": msg}, search_map={"q": ["m@x"]})
    stats = mailbox.ingest_query("q", nm=fake, extract_fn=lambda raw, ctx: [])
    assert stats.reservations == 0
    assert stats.messages_with_yield == 0
    assert len(store.timeline()) == 0


def test_bad_message_skipped_and_counted() -> None:
    good = _eml("good@x")
    fake = FakeNm(raws={"good@x": good, "bad@x": b"whatever"},
                  search_map={"q": ["bad@x", "good@x"]})

    def flaky(raw, ctx):
        if raw == b"whatever":
            raise ValueError("boom")
        return [_flight("EX1")]

    stats = mailbox.ingest_query("q", nm=fake, extract_fn=flaky)
    assert stats.errors == 1
    assert stats.reservations == 1            # the good one still ingested
    assert len(store.timeline()) == 1


def test_second_identical_run_is_a_noop() -> None:
    msg = _eml("m@x")
    fake = FakeNm(raws={"m@x": msg}, search_map={"q": ["m@x"]})
    extract_fn = lambda raw, ctx: [_flight("EX1")]
    mailbox.ingest_query("q", nm=fake, extract_fn=extract_fn)
    n_events = len(ev.load(commands.LEDGER_PATH))
    mailbox.ingest_query("q", nm=fake, extract_fn=extract_fn)  # again
    assert len(ev.load(commands.LEDGER_PATH)) == n_events      # idempotent, no new events
    assert len(store.timeline()) == 1


def test_dry_run_writes_nothing_but_counts() -> None:
    msg = _eml("m@x")
    fake = FakeNm(raws={"m@x": msg}, search_map={"q": ["m@x"]})
    stats = mailbox.ingest_query("q", nm=fake, extract_fn=lambda raw, ctx: [_flight("EX1")],
                                 dry_run=True)
    assert stats.reservations == 1
    assert stats.messages_with_yield == 1
    assert len(store.timeline()) == 0         # nothing written
    assert len(ev.load(commands.LEDGER_PATH)) == 0


def test_limit_caps_selection() -> None:
    raws = {f"m{i}@x": _eml(f"m{i}@x") for i in range(5)}
    fake = FakeNm(raws=raws, search_map={"q": list(raws)})
    stats = mailbox.ingest_query("q", nm=fake, extract_fn=lambda raw, ctx: [_flight("EX1")],
                                 limit=2)
    assert stats.selected == 2


def test_notmuch_error_from_search_propagates() -> None:
    class Boom:
        NotmuchError = nm.NotmuchError

        def search(self, query):
            raise nm.NotmuchError("bad index")

        def show_raw(self, msgid):  # pragma: no cover
            raise AssertionError("unreached")

    with pytest.raises(nm.NotmuchError):
        mailbox.ingest_query("q", nm=Boom(), extract_fn=lambda raw, ctx: [])


def test_per_message_resolution_error_degrades_to_forward() -> None:
    # A NotmuchError DURING per-message forward resolution must NOT abort the run and must NOT
    # skip the message — it degrades to extracting the forward itself. Only the top-level
    # selection search aborts (see the test above).
    fwd = _eml("fwd@x", subject="Fwd: Booking", extra="X-Forwarded-Message-Id: <orig@x>\r\n")

    class ResolveBoom(FakeNm):
        def search(self, query: str) -> list[str]:
            if query == "q":
                return ["fwd@x"]            # selection succeeds
            raise nm.NotmuchError("index blip during resolution")  # id:/subject: lookup fails

    fake = ResolveBoom(raws={"fwd@x": fwd}, search_map={})
    stats = mailbox.ingest_query("q", nm=fake, extract_fn=lambda raw, ctx: [_flight("EX1")])
    assert stats.errors == 0                 # degraded, not an error
    assert stats.forwards_resolved == 0
    assert stats.reservations == 1           # the forward itself was still ingested
    assert len(store.timeline()) == 1
    with store.get_db() as conn:
        srcs = {r["source_id"] for r in conn.execute("SELECT source_id FROM source")}
    assert srcs == {"mail:fwd@x"}


def test_configured_query_raises_when_unset(tmp_path, monkeypatch) -> None:
    from life_agent.core import config
    monkeypatch.setattr(config, "DATA_SOURCES", tmp_path / "absent.yaml")
    with pytest.raises(mailbox.IngestConfigError):
        mailbox.configured_query()


def test_configured_query_reads_yaml(tmp_path, monkeypatch) -> None:
    from life_agent.core import config
    f = tmp_path / "data-sources.yaml"
    f.write_text("trips:\n  ingest:\n    query: 'folder:Trips'\n", encoding="utf-8")
    monkeypatch.setattr(config, "DATA_SOURCES", f)
    assert mailbox.configured_query() == "folder:Trips"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/trips/test_mailbox.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'life_agent.trips.mailbox'`.

- [ ] **Step 3: Write the module**

Create `src/life_agent/trips/mailbox.py`:

```python
"""Mailbox-scale ingest: notmuch selection -> forward resolution -> extract -> observe.

The tier-2 (email-kitinerary) upgrade path. Selection is a notmuch query (config, never a
literal). A selected forward is resolved to its original and extraction runs on whichever of
{original, forward} yields more — the original is better evidence, so it wins a tie. Every
reservation is observed idempotently (observe dedups on (identity, source_id)), so re-running
a broadened query costs nothing. A failure of the top-level SELECTION search raises (a bad
query / broken index invalidates the whole run); per-message notmuch or parse failures are
logged, skipped, and counted, and a per-message forward-resolution failure degrades to the
forward — one bad mail never aborts the batch. One extraction seam, one write path.
"""
from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from email import message_from_bytes, policy
from email.message import EmailMessage
from email.utils import parsedate_to_datetime
from typing import Any

from life_agent.core import config
from life_agent.trips import commands, forwards
from life_agent.trips import notmuch as _notmuch
from life_agent.trips.extract import extract as _extract

_log = logging.getLogger(__name__)


class IngestConfigError(RuntimeError):
    """The ingest query is not configured (data-sources.yaml:trips.ingest.query)."""


@dataclass
class Stats:
    selected: int = 0
    forwards_resolved: int = 0
    messages_with_yield: int = 0
    reservations: int = 0
    errors: int = 0


def configured_query() -> str:
    """The owner's booking-signal query from data-sources.yaml. Raises when unset — never a
    silent empty run."""
    ds = config.data_sources()
    trips = ds.get("trips") if isinstance(ds, dict) else None
    ingest = trips.get("ingest") if isinstance(trips, dict) else None
    query = ingest.get("query") if isinstance(ingest, dict) else None
    if not isinstance(query, str) or not query.strip():
        raise IngestConfigError(
            f"no trips.ingest.query in {config.DATA_SOURCES}; set it or pass --query"
        )
    return query


def _parse(raw: bytes) -> EmailMessage:
    msg = message_from_bytes(raw, policy=policy.default)
    assert isinstance(msg, EmailMessage)
    return msg


def _context_date(msg: EmailMessage) -> datetime:
    raw = msg.get("Date")
    if raw:
        try:
            return parsedate_to_datetime(raw)
        except (TypeError, ValueError):
            pass
    return datetime.now()


def _message_id(msg: EmailMessage, fallback: str) -> str:
    mid = (msg.get("Message-ID") or "").strip().strip("<>").strip()
    return mid or fallback


def ingest_query(
    query: str,
    *,
    nm: Any = _notmuch,
    extract_fn: Callable[[bytes, datetime], list[dict[str, Any]]] = _extract,
    observe_fn: Callable[..., str] = commands.observe,
    limit: int | None = None,
    dry_run: bool = False,
) -> Stats:
    """Ingest every reservation selected by ``query``. See module docstring for the contract."""
    stats = Stats()
    ids = nm.search(query)          # NotmuchError propagates: a bad query invalidates the run
    if limit is not None:
        ids = ids[:limit]
    stats.selected = len(ids)

    for msgid in ids:
        try:
            fwd_raw = nm.show_raw(msgid)
            fwd_msg = _parse(fwd_raw)
            candidates: list[tuple[bytes, EmailMessage]] = [(fwd_raw, fwd_msg)]

            # Forward resolution is BEST-EFFORT: a per-message lookup failure (e.g. a
            # malformed subject query, or a broken index mid-scan) must NOT skip an otherwise
            # extractable message, and must never abort the batch.
            try:
                original_id = forwards.resolve_original(dict(fwd_msg.items()), nm.search)
            except _notmuch.NotmuchError:
                original_id = None
            if original_id and original_id != msgid:
                try:
                    orig_raw = nm.show_raw(original_id)
                    candidates.insert(0, (orig_raw, _parse(orig_raw)))  # original first (tie->orig)
                    stats.forwards_resolved += 1
                except _notmuch.NotmuchError:
                    pass                # original unfetchable (e.g. deleted) -> use the forward

            best: tuple[bytes, EmailMessage, list[dict[str, Any]]] = (fwd_raw, fwd_msg, [])
            for raw, msg in candidates:
                found = extract_fn(raw, _context_date(msg))
                if len(found) > len(best[2]):
                    best = (raw, msg, found)
        except Exception as exc:        # one malformed/unfetchable message never aborts the batch
            _log.warning("trips ingest: skipped %s (%s)", msgid, type(exc).__name__)
            stats.errors += 1
            continue

        best_raw, best_msg, best_yield = best
        if not best_yield:
            continue
        stats.messages_with_yield += 1
        if dry_run:
            stats.reservations += len(best_yield)
            continue

        message_id = _message_id(best_msg, msgid)
        sha = hashlib.sha256(best_raw).hexdigest()
        received = _context_date(best_msg).isoformat()
        for jsonld in best_yield:
            observe_fn(
                jsonld, fidelity="email-kitinerary", source_id=f"mail:{message_id}",
                received_at=received,
                source_meta={"message_id": message_id, "sha256": sha, "kind": "email"},
            )
            stats.reservations += 1
    return stats
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/trips/test_mailbox.py -q`
Expected: PASS (10 tests).

- [ ] **Step 5: Commit**

```bash
git add src/life_agent/trips/mailbox.py tests/trips/test_mailbox.py
git commit -m "feat(trips): mailbox ingest orchestration (select->resolve->extract->observe)"
```

---

### Task 5: CLI — `trips ingest-mail`

**Files:**
- Modify: `src/life_agent/trips/cli.py` (add `import sys`, the `_cmd_ingest_mail` handler, and the `ingest-mail` subparser)
- Test: `tests/trips/test_cli.py` (append)

**Interfaces:**
- Consumes: `mailbox.configured_query`, `mailbox.ingest_query`, `mailbox.Stats`, `mailbox.IngestConfigError` (Task 4).
- Produces: the `ingest-mail` CLI subcommand.

- [ ] **Step 1: Write the failing tests**

Append to `tests/trips/test_cli.py`:

```python
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


def test_ingest_mail_missing_config_returns_nonzero(capsys, monkeypatch) -> None:
    from life_agent.trips import mailbox

    def boom() -> str:
        raise mailbox.IngestConfigError("no trips.ingest.query")

    monkeypatch.setattr(mailbox, "configured_query", boom)
    assert cli.main(["ingest-mail"]) == 2
    assert "query" in capsys.readouterr().err.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/trips/test_cli.py -q`
Expected: FAIL — `ingest-mail` is an unknown subcommand (SystemExit → non-zero) / handler missing.

- [ ] **Step 3: Wire the subcommand**

In `src/life_agent/trips/cli.py`:

Add `import sys` to the imports (after `import json`).

Add the handler (near `_cmd_ingest`):

```python
def _cmd_ingest_mail(args: argparse.Namespace) -> int:
    from life_agent.trips import mailbox
    try:
        query = args.query or mailbox.configured_query()
    except mailbox.IngestConfigError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    stats = mailbox.ingest_query(query, limit=args.limit, dry_run=args.dry_run)
    verb = "would ingest" if args.dry_run else "ingested"
    print(f"{verb} {stats.reservations} reservation(s) from "
          f"{stats.messages_with_yield}/{stats.selected} message(s); "
          f"{stats.forwards_resolved} forward(s) resolved, {stats.errors} skipped")
    return 0
```

Register the subparser inside `_build_parser`, after the `list` subparser block (it needs optional flags, so it is added explicitly like `list`, not via `commands_spec`):

```python
    mp = sub.add_parser("ingest-mail")
    mp.add_argument("--query", default=None)
    mp.add_argument("--dry-run", action="store_true")
    mp.add_argument("--limit", type=int, default=None)
    mp.set_defaults(func=_cmd_ingest_mail)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/trips/test_cli.py -q`
Expected: PASS (all, including the pre-existing CLI tests).

- [ ] **Step 5: Full suite + linters**

Run: `uv run python -m pytest -q && uv run ruff check src/life_agent/trips src/life_agent/core/config.py tests/trips && uv run mypy src/life_agent/trips`
Expected: all green (default marker filter skips `-m system`/`llm`).

- [ ] **Step 6: Commit**

```bash
git add src/life_agent/trips/cli.py tests/trips/test_cli.py
git commit -m "feat(trips): trips ingest-mail CLI (query-driven mailbox ingest)"
```

---

## Self-Review

- **Spec coverage:** notmuch seam (Task 2) ✓; query config in data-sources.yaml with no code default (Task 1 + `configured_query` in Task 4) ✓; forward resolution with the 4-tier precedence (Task 3) ✓; extract-on-higher-yield + idempotent observe as `email-kitinerary` (Task 4) ✓; `trips ingest-mail` with `--query`/`--dry-run`/`--limit` (Task 5) ✓; loud-notmuch vs silent-extract postures (Tasks 2 & 4) ✓; PII-safe example config (Task 1) ✓. Deferred items (PDF/pkpass upload, systemd timer) are out of scope by design.
- **Placeholder scan:** none — every step carries the actual code/command. The `<...>` tokens in `data-sources.example.yaml` are deliberate PII placeholders, not plan gaps.
- **Type consistency:** `Stats` fields, `resolve_original` signature, `ingest_query` kwargs, and `search`/`show_raw` return types are used identically across the tasks that produce and consume them. `observe`'s signature (`jsonld, *, fidelity, source_id, received_at, source_meta`) matches Plan 1's `commands.observe`.
