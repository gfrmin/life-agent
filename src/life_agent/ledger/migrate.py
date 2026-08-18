"""The migration writer and the sweeps — design §8 C0 (census), C2 (migrate), C5 (sync), C6
(two-route counts).

    uv run python -m life_agent.ledger.migrate census                     # C0: read-only
    uv run python -m life_agent.ledger.migrate migrate [all|<source_id>]  # C2: legacy → segments
    uv run python -m life_agent.ledger.migrate sync    [all|<source_id>]  # C5: the tail sweep
    uv run python -m life_agent.ledger.migrate counts                     # C6: two routes

One rule everywhere: **the legacy store is the recovery source during dual-write.** ``migrate``
and ``sync`` are the same operation — *append every legacy record not yet on the segment, in
the source's canonical order, dedup by event identity* — differing only in what they verify
(``migrate`` verifies the whole occupied prefix by ``event_id``; ``sync`` verifies the last
occupied ordinal, the cheap alignment spot-check the live mirror also uses). Both are
idempotent (a re-run appends nothing) and loud (a legacy record that disagrees with the event
at its ordinal raises — nothing is rewritten; the disagreement is the owner's to disposition
by compensating entry). ``pkm.artifact`` is set-shaped (one occurrence per identity, R5): its
sweep dedups by ``output`` (the cache key), never by ordinal. Writes go only to the segments
and ``MANIFEST.json`` under ``$LIFE_AGENT_KB/ledger/`` (S1); pkm is read-only here.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from life_agent.core import config
from life_agent.ledger import sources as SRC
from life_agent.ledger.paths import Paths
from life_agent.ledger.schema import UnifiedEvent
from life_agent.ledger.store import LedgerConflictError, LedgerStore

MIRROR_ENV = "LIFE_AGENT_LEDGER_MIRROR"     # "0" disables the live mirror + sweeps (rollback)


def stream_root(kb: Path | None = None) -> Path:
    return (kb or config.KB) / "ledger"


def _bind(scan: SRC.Scan) -> list[UnifiedEvent]:
    """The scan's records as events at their canonical ordinals."""
    out: list[UnifiedEvent] = []
    for rec in scan.parsed:
        out.append(UnifiedEvent(source_id=scan.source_id, seq=rec.ordinal,
                                tx_time_raw=rec.tx_time_raw, kernel_id=rec.kernel_id,
                                author=rec.author, record=rec.record, tx_time=rec.tx_time,
                                inputs=rec.inputs, output=rec.output,
                                recorded_draw=rec.recorded_draw))
    return out


# --- C0: the census (read-only) ------------------------------------------------------------------

def census(paths: Paths, *, order: tuple[str, ...] = SRC.MIGRATION_ORDER,
           out: Any = None) -> dict[str, Any]:
    """Per-source parsed / unparseable / duplicate-key / blank counts + diagnostics; writes
    nothing. The result is the dry-run manifest (C0) and the C6 baseline."""
    out = out or sys.stdout
    rows: dict[str, Any] = {}
    for sid in order:
        sc = SRC.scan(sid, paths)
        rows[sid] = {**sc.counts(), "unparseable_locators": list(sc.unparseable_locators[:20])}
        print(f"census   {sid:28s} parsed={len(sc.parsed):7d} unparseable={sc.unparseable:3d} "
              f"duplicate_key={sc.duplicate_key:3d} blank={sc.blank:3d} "
              + " ".join(f"{k}={json.dumps(v, sort_keys=True)}" for k, v in sc.extras.items()
                         if k not in ("clock",)), file=out)
    return {"format_version": 1, "kind": "census", "at": datetime.now(UTC).isoformat(),
            "sources": rows}


# --- C2 / C5: migrate == sync ---------------------------------------------------------------

@dataclass(frozen=True)
class SyncResult:
    source_id: str
    parsed: int          # legacy records in canonical order
    before: int          # events on the segment before
    written: int
    skipped: int         # already present (idempotent)
    after: int
    unparseable: int
    duplicate_key: int


def sync_source(source_id: str, paths: Paths, store: LedgerStore, *,
                verify_prefix: bool, mode: str, scan: SRC.Scan | None = None) -> SyncResult:
    """Append every legacy record of one source not yet on its segment (canonical order)."""
    sc = scan if scan is not None else SRC.scan(source_id, paths)
    before = store.parseable_count(source_id)
    if source_id == "pkm.artifact":
        # set-shaped (R5): one occurrence per identity — dedup by the pointed-at cache key
        have = store.outputs(source_id) if before else set()
        fresh = [r for r in sc.parsed if r.output not in have]
        events = [UnifiedEvent(source_id=source_id, seq=before + i + 1, tx_time_raw=r.tx_time_raw,
                               kernel_id=r.kernel_id, author=r.author, record=r.record,
                               tx_time=r.tx_time, inputs=r.inputs, output=r.output,
                               recorded_draw=r.recorded_draw) for i, r in enumerate(fresh)]
        written, skipped = store.append_many(source_id, events, verify_prefix=False)
        skipped += len(sc.parsed) - len(fresh)
    else:
        events = _bind(sc)
        written, skipped = store.append_many(source_id, events, verify_prefix=verify_prefix)
    after = store.parseable_count(source_id)
    store.bump_tally(source_id, written)
    extra: dict[str, Any] = {}
    if "legacy_bytes" in sc.extras:      # JSONL sources: the live mirror resumes from here
        extra["legacy_bytes"] = sc.extras["legacy_bytes"]
    store.record_source_counts(
        source_id, parsed=len(sc.parsed), unparseable=sc.unparseable,
        duplicate_key=sc.duplicate_key, blank=sc.blank,
        **{f"last_{mode}_at": datetime.now(UTC).isoformat()}, **extra,
    )
    return SyncResult(source_id, len(sc.parsed), before, written, skipped, after,
                      sc.unparseable, sc.duplicate_key)


def migrate(paths: Paths, store: LedgerStore, *, sources: tuple[str, ...] = SRC.MIGRATION_ORDER,
            out: Any = None, epoch: str | None = None) -> list[SyncResult]:
    """C2: the migration proper — full-prefix verification, the manifest epoch set once."""
    out = out or sys.stdout
    store.set_epoch(epoch or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"))
    results = []
    for sid in sources:
        r = sync_source(sid, paths, store, verify_prefix=True, mode="migrate")
        results.append(r)
        print(_fmt(r, "migrate"), file=out)
    return results


def sync(paths: Paths, store: LedgerStore, *, sources: tuple[str, ...] = SRC.MIGRATION_ORDER,
         out: Any = None) -> list[SyncResult]:
    """C5: the sweep — the same operation with the cheap alignment check."""
    out = out or sys.stdout
    results = []
    for sid in sources:
        r = sync_source(sid, paths, store, verify_prefix=False, mode="sync")
        results.append(r)
        print(_fmt(r, "sync"), file=out)
    return results


def _fmt(r: SyncResult, verb: str) -> str:
    return (f"{verb:8s} {r.source_id:28s} parsed={r.parsed:7d} segment {r.before:7d}→{r.after:7d} "
            f"written={r.written:7d} skipped={r.skipped:7d} unparseable={r.unparseable} "
            f"duplicate_key={r.duplicate_key}")


# --- C6: the two-route counts ---------------------------------------------------------------

def counts(paths: Paths, store: LedgerStore, *, order: tuple[str, ...] = SRC.MIGRATION_ORDER,
           baseline: dict[str, Any] | None = None, out: Any = None) -> dict[str, Any]:
    """Per source: (i) the writer's tally from the manifest, (ii) the segment's parseable line
    count (`wc -l` minus quarantined), (iii) the legacy parsed count now, and (iv) the C0
    baseline parsed count if given — with the reconciliation `tally == segment == legacy`."""
    out = out or sys.stdout
    m = store.manifest()
    rows: dict[str, Any] = {}
    all_ok = True
    for sid in order:
        sc = SRC.scan(sid, paths)
        seg_lines = _wc_l(store.segment_path(sid))
        quarantined = len(store.quarantine(sid))
        segment = store.parseable_count(sid)
        tally = int(m["sources"].get(sid, {}).get("writer_tally", 0))
        base = None if baseline is None else baseline.get("sources", {}).get(sid, {}).get("parsed")
        ok = tally == segment == len(sc.parsed)
        all_ok &= ok
        # A set-shaped source (R5) can only fall BEHIND its segment by deletion on the legacy
        # side: identities the stream recorded whose files are gone. Name that class exactly —
        # it is a legacy loss the append-only stream survived, never a mirror fault.
        legacy_lost = None
        lost_keys: list[str] | None = None
        if not ok and sid == "pkm.artifact":
            have = {r.output for r in sc.parsed}
            # by identity, not by cardinality (reviewer ruling on r03): the keys are the claim
            lost_keys = sorted(o for o in store.outputs(sid) if o not in have)
            legacy_lost = len(lost_keys)
        rows[sid] = {"writer_tally": tally, "segment_wc_l": seg_lines, "quarantined": quarantined,
                     "segment_parseable": segment, "legacy_parsed": len(sc.parsed),
                     "c0_parsed": base,
                     "growth_since_c0": None if base is None else len(sc.parsed) - base,
                     "legacy_lost_identities": legacy_lost, "legacy_lost_keys": lost_keys,
                     "ok": ok}
        verdict = "OK" if ok else "MISMATCH"
        if legacy_lost:
            verdict += (f" — legacy lost {legacy_lost} identit{'y' if legacy_lost == 1 else 'ies'} "
                        f"the segment retains (deletion on the legacy side)")
        print(f"counts   {sid:28s} tally={tally:7d} segment={segment:7d} (wc -l {seg_lines}, "
              f"quarantined {quarantined}) legacy={len(sc.parsed):7d}"
              + (f" c0={base} growth={len(sc.parsed) - base}" if base is not None else "")
              + f" → {verdict}", file=out)
    print(f"counts   {'all sources reconcile' if all_ok else 'MISMATCH present'}", file=out)
    return {"ok": all_ok, "sources": rows}


def _wc_l(path: Path) -> int:
    if not path.exists():
        return 0
    return path.read_bytes().count(b"\n")


# --- CLI ------------------------------------------------------------------------------------------

def _progress(label: str) -> Callable[[str], None]:
    return lambda s: print(f"{label} {s}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m life_agent.ledger.migrate")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("census")
    c.add_argument("--write", default=None,
                   help="write the dry-run manifest JSON here (under $LIFE_AGENT_KB/ledger/)")
    for cmd in ("migrate", "sync"):
        s = sub.add_parser(cmd)
        s.add_argument("source", nargs="?", default="all")
    k = sub.add_parser("counts")
    k.add_argument("--baseline", default=None, help="a census JSON to reconcile against")
    args = ap.parse_args(argv)
    paths = Paths.from_config()
    store = LedgerStore(stream_root())
    if args.cmd == "census":
        result = census(paths)
        if args.write:
            dst = Path(args.write)
            if not dst.resolve().is_relative_to(stream_root().resolve()):
                ap.error("census --write must point under $LIFE_AGENT_KB/ledger/ (S1)")
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            print(f"census   written {dst.name}")
        return 0
    if os.environ.get(MIRROR_ENV, "1") == "0" and args.cmd in ("migrate", "sync"):
        print(f"{MIRROR_ENV}=0: the writer is disabled (rollback switch)", file=sys.stderr)
        return 2
    srcs = (SRC.MIGRATION_ORDER if getattr(args, "source", "all") == "all"
            else (args.source,))
    try:
        if args.cmd == "migrate":
            migrate(paths, store, sources=srcs)
        elif args.cmd == "sync":
            sync(paths, store, sources=srcs)
        elif args.cmd == "counts":
            base = json.loads(Path(args.baseline).read_text()) if args.baseline else None
            return 0 if counts(paths, store, baseline=base)["ok"] else 1
    except LedgerConflictError as exc:
        print(f"CONFLICT {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
