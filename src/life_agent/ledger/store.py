"""The segment store — ``docs/unified-ledger-design.md`` §10 (the durability contract).

Layout: one segment file per ``source_id`` under ``<root>/<source_id>.jsonl`` plus
``<root>/MANIFEST.json``. The logical stream is the union of the segments in
``(source_id, seq)`` order (design §3; reviewer Q6). Guarantees, each tested:

* **single writer per segment** — a per-segment ``flock`` around every append;
* **append** = one whole canonical line + ``flush`` + ``fsync`` (``jsonl_log`` generalised);
* **torn tail** — *a torn line was never an event*: on open-for-append the writer inspects
  the last physical line; if it is unterminated or unparseable it is **quarantined** — its
  ``(segment, byte_offset, length, bytes hex, detected_at)`` recorded in the manifest, the
  physical line newline-terminated so nothing concatenates onto it, **the segment never
  truncated** and the quarantine entry never removed (owner S6). ``seq`` is the ordinal among
  *parseable* lines, so the re-appended canonical line reuses the torn ordinal and density
  holds; ``event_id`` dedup stays well-defined;
* **reads are loud** outside quarantined ranges and silent inside them: an unlisted
  unparseable line raises :class:`LedgerReadError` naming segment and ordinal;
* **idempotent re-append** — appending an event whose ``(source_id, seq)`` is already present
  with the same ``event_id`` is a no-op; a different ``event_id`` at an occupied ordinal, or a
  gap, raises :class:`LedgerConflictError`;
* **manifest writes** are temp-file + ``os.replace``.
"""
from __future__ import annotations

import fcntl
import json
import os
import tempfile
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NamedTuple

from life_agent.ledger import schema as S

MANIFEST_FORMAT_VERSION = 1


class LedgerError(Exception):
    """Base for the store's loud failures."""


class LedgerReadError(LedgerError):
    """An unparseable, non-quarantined line: ``segment`` + physical ``ordinal`` + ``offset``."""

    def __init__(self, segment: str, ordinal: int, offset: int, why: str) -> None:
        super().__init__(f"{segment}: physical line {ordinal} at byte {offset}: {why}")
        self.segment, self.ordinal, self.offset = segment, ordinal, offset


class LedgerConflictError(LedgerError):
    """A `seq` gap, or a different event at an occupied ordinal."""


@dataclass(frozen=True)
class Quarantine:
    segment: str
    byte_offset: int
    length: int
    bytes_hex: str
    detected_at: str
    reason: str


class _Line(NamedTuple):
    """One physical segment line (a NamedTuple: constructed thousands of times per scan)."""
    ordinal: int      # physical line ordinal, 1-based
    offset: int       # byte offset of the line start
    length: int       # bytes excluding the terminating newline
    raw: bytes        # the line bytes without the newline
    terminated: bool  # ends with '\n'


def _now() -> str:
    return datetime.now(UTC).isoformat()


class LedgerStore:
    """The per-source segment store rooted at ``root``."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        # `_lines` cache: (size, mtime_ns) → parsed physical lines. Never stale — every append
        # grows the file — and only ever over-fresh under a concurrent writer (a later stat
        # misses and re-reads). Saves the repeated whole-segment scans one append performs.
        self._scan_cache: dict[str, tuple[tuple[int, int], list[_Line]]] = {}

    # --- paths ---------------------------------------------------------------------------
    @property
    def manifest_path(self) -> Path:
        return self.root / "MANIFEST.json"

    def segment_path(self, source_id: str) -> Path:
        if source_id not in S.SOURCE_IDS | S.RESERVED_SOURCE_IDS:
            raise ValueError(f"unknown source_id {source_id!r}")
        return self.root / f"{source_id}.jsonl"

    def _lock_path(self, source_id: str) -> Path:
        return self.root / f".{source_id}.lock"

    @contextmanager
    def _manifest_lock(self) -> Iterator[None]:
        """MANIFEST.json is shared by every segment; its read-modify-writes take this lock so
        two live writers on different sources cannot lose each other's update (the segment
        lock alone does not cover it)."""
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / ".MANIFEST.lock").open("a+") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    # --- manifest --------------------------------------------------------------------------
    def manifest(self) -> dict[str, Any]:
        if not self.manifest_path.exists():
            return {"format_version": MANIFEST_FORMAT_VERSION, "epoch": None,
                    "sources": {}, "quarantine": []}
        m: dict[str, Any] = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        return m

    def _write_manifest(self, m: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.root, prefix=".MANIFEST.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(json.dumps(m, sort_keys=True, ensure_ascii=False, indent=2) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self.manifest_path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def set_epoch(self, epoch: str) -> None:
        with self._manifest_lock():
            m = self.manifest()
            if m.get("epoch") is None:
                m["epoch"] = epoch
                self._write_manifest(m)

    def record_source_counts(self, source_id: str, **counts: Any) -> None:
        """Record per-source migration counts (unparseable, duplicate-key, …) — additive."""
        with self._manifest_lock():
            m = self.manifest()
            m["sources"].setdefault(source_id, {}).update(counts)
            self._write_manifest(m)

    def bump_tally(self, source_id: str, written: int) -> int:
        """Add to the writer's running tally for a source (the two-route count's first route)
        under the manifest lock; returns the new tally."""
        row = self.update_source(source_id, add={"writer_tally": int(written)})
        return int(row["writer_tally"])

    def update_source(self, source_id: str, *, set: dict[str, Any] | None = None,
                      add: dict[str, int] | None = None) -> dict[str, Any]:
        """One manifest read-modify-write for a source's row: ``set`` overwrites fields,
        ``add`` increments integer counters (absent → 0). Returns the row after the write."""
        with self._manifest_lock():
            m = self.manifest()
            row = m["sources"].setdefault(source_id, {})
            for k, v in (add or {}).items():
                row[k] = int(row.get(k, 0)) + int(v)
            row.update(set or {})
            self._write_manifest(m)
            return dict(row)

    def set_note(self, key: str, value: Any) -> None:
        """Set one top-level manifest field (e.g. the live mirror's recorded state) under the
        manifest lock. Never touches ``sources``/``quarantine``."""
        if key in ("sources", "quarantine", "format_version", "epoch"):
            raise ValueError(f"{key!r} is not a note")
        with self._manifest_lock():
            m = self.manifest()
            m[key] = value
            self._write_manifest(m)

    def quarantine(self, source_id: str | None = None) -> list[Quarantine]:
        rows = [Quarantine(**q) for q in self.manifest().get("quarantine", [])]
        seg = None if source_id is None else self.segment_path(source_id).name
        return [q for q in rows if seg is None or q.segment == seg]

    def _quarantined_offsets(self, source_id: str) -> set[int]:
        return {q.byte_offset for q in self.quarantine(source_id)}

    def _add_quarantine(self, q: Quarantine) -> None:
        with self._manifest_lock():
            m = self.manifest()
            if any(x["segment"] == q.segment and x["byte_offset"] == q.byte_offset
                   for x in m["quarantine"]):
                return
            m["quarantine"].append(q.__dict__)   # never removed (S6)
            self._write_manifest(m)

    # --- physical scan ---------------------------------------------------------------------
    def _lines(self, source_id: str) -> list[_Line]:
        p = self.segment_path(source_id)
        try:
            st = p.stat()
        except FileNotFoundError:
            return []
        key = (st.st_size, st.st_mtime_ns)
        hit = self._scan_cache.get(source_id)
        if hit is not None and hit[0] == key:
            return hit[1]
        data = p.read_bytes()
        out: list[_Line] = []
        pos, ordinal = 0, 0
        while pos < len(data):
            nl = data.find(b"\n", pos)
            if nl < 0:
                out.append(_Line(ordinal + 1, pos, len(data) - pos, data[pos:], False))
                break
            out.append(_Line(ordinal + 1, pos, nl - pos, data[pos:nl], True))
            ordinal += 1
            pos = nl + 1
        self._scan_cache[source_id] = (key, out)
        return out

    @staticmethod
    def _parses(raw: bytes) -> bool:
        try:
            S.from_line(raw.decode("utf-8"))
            return True
        except Exception:
            return False

    def _prepare_tail(self, source_id: str) -> None:
        """The torn-tail protocol (§10): quarantine an unterminated/unparseable last line,
        terminate it, never truncate. Idempotent."""
        lines = self._lines(source_id)
        if not lines:
            return
        last = lines[-1]
        if last.offset in self._quarantined_offsets(source_id):
            if not last.terminated:
                self._terminate(source_id)
            return
        if last.terminated and self._parses(last.raw):
            return
        reason = "unterminated" if not last.terminated else "unparseable"
        self._add_quarantine(Quarantine(
            segment=self.segment_path(source_id).name, byte_offset=last.offset,
            length=last.length, bytes_hex=last.raw.hex(), detected_at=_now(), reason=reason))
        if not last.terminated:
            self._terminate(source_id)

    def _terminate(self, source_id: str) -> None:
        with self.segment_path(source_id).open("ab") as fh:
            fh.write(b"\n")
            fh.flush()
            os.fsync(fh.fileno())

    # --- reads -----------------------------------------------------------------------------
    def read(self, source_id: str) -> list[S.UnifiedEvent]:
        """Every event of a source in ``seq`` order — loud outside quarantine, silent inside;
        density (``seq == ordinal among parseable lines``) is verified."""
        return list(self.iter(source_id))

    def iter(self, source_id: str) -> Iterator[S.UnifiedEvent]:
        quarantined = self._quarantined_offsets(source_id)
        seg = self.segment_path(source_id).name
        expected = 0
        for ln in self._lines(source_id):
            if ln.offset in quarantined:
                continue
            if not ln.terminated:
                raise LedgerReadError(seg, ln.ordinal, ln.offset,
                                      "unterminated tail (open the writer to quarantine it)")
            try:
                e = S.from_line(ln.raw.decode("utf-8"))
            except Exception as exc:  # loud, named, never skipped
                raise LedgerReadError(seg, ln.ordinal, ln.offset,
                                      f"unparseable: {exc}") from exc
            expected += 1
            if e.seq != expected:
                raise LedgerReadError(seg, ln.ordinal, ln.offset,
                                      f"seq {e.seq} != dense ordinal {expected}")
            if e.source_id != source_id:
                raise LedgerReadError(seg, ln.ordinal, ln.offset,
                                      f"source_id {e.source_id!r} in segment {seg}")
            yield e

    def parseable_count(self, source_id: str) -> int:
        quarantined = self._quarantined_offsets(source_id)
        return sum(1 for ln in self._lines(source_id)
                   if ln.offset not in quarantined and ln.terminated)

    def next_seq(self, source_id: str) -> int:
        return self.parseable_count(source_id) + 1

    def event_ids(self, source_id: str) -> list[str]:
        """Every event_id of a source in ``seq`` order (loud outside quarantine)."""
        return [e.event_id for e in self.iter(source_id)]

    def outputs(self, source_id: str) -> set[str]:
        """The set of ``output`` addresses a source's events point at (the pkm.artifact sweep's
        dedup key — one occurrence per identity, R5)."""
        return {e.output for e in self.iter(source_id) if e.output}

    # --- append ------------------------------------------------------------------------------
    def append(self, event: S.UnifiedEvent) -> bool:
        """Append one event under the segment lock (line + flush + fsync). Returns True if
        written, False if the identical event was already present at that ordinal (idempotent
        re-append)."""
        written, _skipped = self.append_many(event.source_id, [event])
        return written == 1

    def append_many(self, source_id: str, events: Iterable[S.UnifiedEvent], *,
                    verify_prefix: bool = True) -> tuple[int, int]:
        """Append events **in seq order** under ONE lock with ONE physical scan and one fsync
        at the end (the durability promise holds for every event whose append returned; a
        crash mid-batch loses only an unfsynced tail, which the torn-tail protocol and the
        idempotent re-run cover). Events at an already-occupied ordinal must be the same event
        (by ``event_id``): with ``verify_prefix`` every such ordinal is checked against the
        parsed segment; without it only the LAST occupied ordinal is checked (the cheap
        alignment spot-check the live mirror uses). A different event at an occupied
        ordinal, or a gap, raises :class:`LedgerConflictError`. Returns (written, skipped)."""
        self.root.mkdir(parents=True, exist_ok=True)
        seg = self.segment_path(source_id)
        with self._lock_path(source_id).open("a+") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            fh = None
            written = skipped = 0
            try:
                self._prepare_tail(source_id)
                quarantined = self._quarantined_offsets(source_id)
                existing = [ln for ln in self._lines(source_id)
                            if ln.offset not in quarantined and ln.terminated]
                n = len(existing)
                for e in events:
                    if e.source_id != source_id:
                        raise LedgerConflictError(
                            f"event for {e.source_id!r} offered to segment {source_id!r}")
                    if e.seq <= n:
                        if verify_prefix or e.seq == n:
                            have = S.from_line(existing[e.seq - 1].raw.decode("utf-8"))
                            if have.event_id != e.event_id:
                                raise LedgerConflictError(
                                    f"{source_id} seq {e.seq} is occupied by a different event")
                        skipped += 1
                        continue
                    if e.seq != n + written + 1:
                        raise LedgerConflictError(
                            f"{source_id}: seq {e.seq} would leave a gap "
                            f"(next is {n + written + 1})")
                    if fh is None:
                        fh = seg.open("ab")
                    fh.write(S.to_line(e).encode("utf-8") + b"\n")
                    written += 1
                if fh is not None:
                    fh.flush()
                    os.fsync(fh.fileno())
                return written, skipped
            finally:
                if fh is not None:
                    fh.close()
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
