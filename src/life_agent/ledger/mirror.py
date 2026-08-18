"""The live mirror — design §8 C5, §10: one call at each typed writer AFTER its legacy append.

**Append-shaped** (owner Q3 on r03a): the mirror never re-parses the legacy store on the hot
path. The manifest carries, per JSONL source, ``legacy_bytes`` — the byte length the last
sweep/mirror had consumed — so a call reads only the legacy file's *delta* since then, parses
those lines with the SAME parser the sweep uses (:func:`sources.parse_line`), and appends them
at the next dense ordinals under the segment lock (one line, one fsync — the per-line promise
of §10). It is **loud when behind** — a delta longer than the caller's own append means events
were missed (a hook-less writer, a crash between legacy and mirror, a disabled interval) — and
**falls back to the full sweep** (:func:`migrate.sync_source`) whenever the delta cannot be
trusted (no recorded offset, a non-event line in the delta, a legacy file shorter than the
recorded offset, more than :data:`TAIL_CAP` lines behind).

**Fail-open, counted** (owner Q4 on r03a): the legacy append has already returned durably, so
the mirror never raises into a writer — every failure is a WARNING naming source and reason
(never a value) and a ``mirror_failures`` increment on the manifest row, so the C6 two-route
count surfaces it structurally rather than as silent loss.

**Recorded switch** (owner Q5 on r03a): ``LIFE_AGENT_LEDGER_MIRROR=0`` disables the mirror; the
first call in a process logs the switch's state and records it in the manifest
(``mirror_state``), so a disabled mirror reads as *disabled* in the count, never as loss.

The mirror applies to the **configured** legacy store only: a writer appending elsewhere (a
test's tmp path, an ad-hoc file) is skipped, so nothing but the owner's live stores can ever
reach the owner's stream. An uninitialised stream (no ``MANIFEST.json``) makes the mirror inert
with one WARNING per process — run ``python -m life_agent.ledger.migrate migrate all`` first.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from life_agent.ledger import migrate as MIG
from life_agent.ledger import sources as SRC
from life_agent.ledger.paths import Paths
from life_agent.ledger.schema import UnifiedEvent
from life_agent.ledger.store import LedgerStore

log = logging.getLogger(__name__)

MIRROR_ENV = MIG.MIRROR_ENV
TAIL_CAP = 512          # delta lines the mirror will parse itself; beyond → full sweep

# The sources a live writer mirrors (design §8 C5). The three swept sources
# (utility.elicitations, pkm.demand, pkm.artifact) never come through here.
MIRRORED: tuple[str, ...] = (
    "act.tasks", "act.trips", "calibration.decisions", "calibration.reactions",
    "calibration.claude_verdicts", "calibration.outcomes", "calibration.gather_outcomes",
    "calibration.corrections", "eval.labels",
)


@dataclass(frozen=True)
class MirrorResult:
    source_id: str
    action: str          # appended | behind | synced | noop | skipped | disabled | inert | failed
    written: int = 0
    behind: int = 0      # events found beyond the caller's own append (0 when in step)
    detail: str = ""     # locator-safe reason (never a record value)


def enabled() -> bool:
    return os.environ.get(MIRROR_ENV, "1") != "0"


# --- once-per-process state ------------------------------------------------------------------

_announced: dict[str, str] = {}      # root → state announced ("enabled" | "disabled" | "inert")


def _reset_process_state() -> None:
    """Tests only: forget the once-per-process announcements."""
    _announced.clear()


def _announce(store: LedgerStore, on: bool) -> bool:
    """Log the switch state once per process per root and record it in the manifest (owner
    Q5). Returns False if the stream is not initialised (inert)."""
    key = str(store.root)
    if not store.manifest_path.exists():
        if _announced.get(key) != "inert":
            _announced[key] = "inert"
            log.warning("ledger mirror: stream not initialised at %s — mirror inert "
                        "(run `python -m life_agent.ledger.migrate migrate all`)", store.root)
        return False
    state = "enabled" if on else "disabled"
    if _announced.get(key) != state:
        _announced[key] = state
        note = {"enabled": on, "env": os.environ.get(MIRROR_ENV),
                "recorded_at": datetime.now(UTC).isoformat()}
        try:
            store.set_note("mirror_state", note)
        except Exception as exc:  # bookkeeping; the append path must not depend on it
            log.warning("ledger mirror: could not record mirror_state: %s", type(exc).__name__)
        (log.info if on else log.warning)("ledger mirror: %s (%s=%s) at %s", state, MIRROR_ENV,
                                          note["env"], store.root)
    return True


# --- the delta ---------------------------------------------------------------------------------

def _delta(path: Path, offset: int) -> tuple[list[str], int] | None:
    """The legacy file's whole physical lines after ``offset``, and the new consumed length.
    ``None`` when the delta cannot be trusted (file shorter than the offset; unterminated tail —
    a writer's line is not yet whole; a non-UTF-8 byte)."""
    with path.open("rb") as fh:
        fh.seek(0, os.SEEK_END)
        size = fh.tell()
        if size < offset:
            return None
        fh.seek(offset)
        data = fh.read(size - offset)
    if not data:
        return [], offset
    if not data.endswith(b"\n"):
        return None
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return text.split("\n")[:-1], size


# --- the hook ----------------------------------------------------------------------------------

def after_legacy_append(source_id: str, legacy_path: Path, *, n: int = 1,
                        store: LedgerStore | None = None,
                        paths: Paths | None = None) -> MirrorResult:
    """Mirror the ``n`` lines the caller just appended to ``legacy_path`` onto the stream.
    NEVER raises (fail-open, counted); returns what it did. ``store``/``paths`` default to the
    configured stream root and legacy stores (tests pass their own)."""
    try:
        return _mirror(source_id, legacy_path, n=n, store=store, paths=paths)
    except Exception as exc:  # fail-open: the legacy append already returned durably
        why = f"{type(exc).__name__}: {exc}"
        log.warning("ledger mirror: %s failed — %s", source_id, why)
        try:
            if store is None:
                store = LedgerStore(MIG.stream_root())
            if store.manifest_path.exists():
                store.update_source(source_id, add={"mirror_failures": 1},
                                    set={"last_mirror_failure_at": datetime.now(UTC).isoformat()})
        except Exception:
            log.warning("ledger mirror: %s failure could not be counted", source_id)
        return MirrorResult(source_id, "failed", detail=why)


def _mirror(source_id: str, legacy_path: Path, *, n: int, store: LedgerStore | None,
            paths: Paths | None) -> MirrorResult:
    if source_id not in MIRRORED:
        raise ValueError(f"{source_id!r} is not a mirrored source (swept sources never mirror)")
    store = store or LedgerStore(MIG.stream_root())
    paths = paths or Paths.from_config(resolve_pkm=False)
    on = enabled()
    if not _announce(store, on):
        return MirrorResult(source_id, "inert", detail="stream not initialised")
    if not on:
        return MirrorResult(source_id, "disabled")
    configured = paths.legacy_file(source_id)
    if Path(legacy_path).resolve() != configured.resolve():
        log.debug("ledger mirror: %s append at a non-configured path — skipped", source_id)
        return MirrorResult(source_id, "skipped", detail="not the configured legacy store")

    row = store.manifest().get("sources", {}).get(source_id, {})
    offset = row.get("legacy_bytes")
    if offset is None:
        return _full_sync(source_id, paths, store, why="no recorded legacy offset")
    delta = _delta(configured, int(offset))
    if delta is None:
        return _full_sync(source_id, paths, store, why="delta not trustworthy")
    lines, new_offset = delta
    if not lines:
        return MirrorResult(source_id, "noop", detail="already mirrored")
    if len(lines) > TAIL_CAP:
        return _full_sync(source_id, paths, store,
                          why=f"{len(lines)} lines behind (> {TAIL_CAP})", behind=len(lines) - n)

    base = store.parseable_count(source_id)
    parsed: list[SRC.Parsed] = []
    for i, line in enumerate(lines, start=1):
        rec, status = SRC.parse_line(source_id, line, ordinal=base + len(parsed) + 1,
                                     locator=f"{configured.name}:+{i}")
        if rec is None:
            if status == "blank":
                continue
            # a non-event in the delta: the sweep classifies and counts it; not the hot path
            return _full_sync(source_id, paths, store, why=f"{status} line in delta")
        parsed.append(rec)
    events = [UnifiedEvent(source_id=source_id, seq=r.ordinal, tx_time_raw=r.tx_time_raw,
                           kernel_id=r.kernel_id, author=r.author, record=r.record,
                           tx_time=r.tx_time, inputs=r.inputs, output=r.output,
                           recorded_draw=r.recorded_draw) for r in parsed]
    written, _skipped = store.append_many(source_id, events, verify_prefix=False)
    behind = max(0, len(parsed) - max(n, 0))
    add: dict[str, int] = {"writer_tally": written, "mirror_appends": written}
    if behind:
        add["mirror_behind_events"] = behind
        add["mirror_behind_calls"] = 1
        log.warning("ledger mirror: %s was BEHIND by %d event(s) beyond this append — "
                    "caught up (%d written)", source_id, behind, written)
    store.update_source(source_id, add=add,
                        set={"legacy_bytes": new_offset,
                             "last_mirror_at": datetime.now(UTC).isoformat()})
    return MirrorResult(source_id, "behind" if behind else "appended", written=written,
                        behind=behind, detail=f"seq {base + 1}..{base + len(parsed)}")


def _full_sync(source_id: str, paths: Paths, store: LedgerStore, *, why: str,
               behind: int = 0) -> MirrorResult:
    """The safety net: the sweep proper (parse the whole legacy store, append what is missing,
    record counts + the new legacy offset). Loud: WARNING with the reason."""
    log.warning("ledger mirror: %s falling back to a full sync — %s", source_id, why)
    r = MIG.sync_source(source_id, paths, store, verify_prefix=False, mode="sync")
    add = {"mirror_syncs": 1}
    if behind:
        add["mirror_behind_events"] = behind
        add["mirror_behind_calls"] = 1
    store.update_source(source_id, add=add)
    return MirrorResult(source_id, "synced", written=r.written, behind=behind, detail=why)
