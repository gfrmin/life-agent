"""The §7 fold adapters — A1-A14 as the **existing** folds applied to the stream's records.

Design §7 states each adapter as ``A(stream) := legacy_fold([e.record for e in stream if
e.source_id ∈ S] in declared order)``. This module realises that literally: for each source
it **materialises** the segment's records — ``record`` verbatim, one canonical line per event,
in ``seq`` order — into a legacy-shaped file under a work directory, and hands the harness a
:class:`Paths` over those files, so every artefact function in :mod:`golden` runs
**unchanged** over the stream. No fold logic is added or re-implemented anywhere. The three
stated exceptions are the design's own:

* **A2** — the stamp's sha is over the dual-written legacy ledger's bytes (R1):
  ``state_sha_source`` stays the legacy file; the events come from the stream.
* **A10** — the stream carries identities, never bytes (R5): the decision-referenced keys come
  from the stream's ``calibration.decisions``; content/meta are read-replayed from the real pkm
  root under each identity. The stream check beside it: every referenced key present on disk
  is also a ``pkm.artifact`` output on the stream (printed by the harness).
* **A11 / A12** — ``pkm.artifact`` records are materialised as a **cache-shaped tree**
  (``cache/aa/bb…/meta.json`` + ``lineage.json`` via pkm's own path functions) so
  ``_iter_meta_files`` / ``_check_meta_consistency`` / ``_meta_to_row`` / ``_read_lineage``
  run unchanged over the stream (reviewer V8 — the same functions, the same skips, the same
  ``produced_at`` rendering); ``pkm.demand`` records are materialised into
  ``logs/demand/<timestamp[:10]>.jsonl`` — the UTC-day file *is* ``timestamp[:10]`` for every
  line (C0 census: 103,875 / 103,875, ``file_day_mismatch=0``).

Materialisation writes only under ``$LIFE_AGENT_KB/ledger/golden/<T>/work/`` (S1); the S8
lifecycle applies (scratch, removed on a green run, retained on red).
"""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from life_agent.ledger.paths import Paths
from life_agent.ledger.schema import SOURCE_IDS, canonical
from life_agent.ledger.store import LedgerStore
from pkm.cache import lineage_file, meta_file

# Paths field ↔ source_id (the JSONL sources); pkm's two are directory-shaped.
FIELD_OF: dict[str, str] = {
    "act.tasks": "tasks_ledger", "act.trips": "trips_ledger",
    "calibration.outcomes": "outcomes", "calibration.decisions": "decisions",
    "calibration.reactions": "reactions", "calibration.claude_verdicts": "claude_verdicts",
    "calibration.gather_outcomes": "gather_outcomes", "calibration.corrections": "corrections",
    "utility.elicitations": "elicitations", "eval.labels": "labels",
}
SOURCE_OF: dict[str, str] = {v: k for k, v in FIELD_OF.items()}


def materialise_source(store: LedgerStore, source_id: str, workdir: Path, *,
                       limit: int | None = None) -> Path | None:
    """Write one source's records (verbatim, canonical, seq order; the first ``limit`` if
    given) into its legacy shape under ``workdir``. Returns the file/dir path, or None for a
    directory-shaped source (pkm) whose root is ``workdir / "pkm"``."""
    if source_id not in SOURCE_IDS:
        raise ValueError(f"unknown source_id {source_id!r}")
    events = store.read(source_id)
    if limit is not None:
        events = events[:limit]
    if source_id == "pkm.artifact":
        root = workdir / "pkm"
        for e in events:
            key = str(e.record["meta"].get("cache_key") or e.output)
            mf = meta_file(root, key)
            mf.parent.mkdir(parents=True, exist_ok=True)
            mf.write_text(json.dumps(e.record["meta"], sort_keys=True, ensure_ascii=False),
                          encoding="utf-8")
            if e.record.get("lineage") is not None:
                lineage_file(root, key).write_text(
                    json.dumps(e.record["lineage"], sort_keys=True, ensure_ascii=False),
                    encoding="utf-8")
        return None
    if source_id == "pkm.demand":
        root = workdir / "pkm" / "logs" / "demand"
        root.mkdir(parents=True, exist_ok=True)
        by_day: dict[str, list[str]] = {}
        for e in events:
            by_day.setdefault(str(e.record.get("timestamp", ""))[:10], []).append(
                canonical(e.record))
        for day, lines in by_day.items():
            (root / f"{day}.jsonl").write_text("".join(ln + "\n" for ln in lines),
                                               encoding="utf-8")
        return None
    f = workdir / f"{source_id}.jsonl"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("".join(canonical(e.record) + "\n" for e in events), encoding="utf-8")
    return f


def materialise(store: LedgerStore, workdir: Path, legacy: Paths, *,
                sources: tuple[str, ...] | None = None,
                limits: dict[str, int] | None = None) -> Paths:
    """The stream as a :class:`Paths`: every requested source materialised under ``workdir``;
    the rest of the fields keep pointing at ``legacy`` (A2's sha source, the utility model —
    a config input, not an event flavour — and A10's read-replay root)."""
    wanted = tuple(sources) if sources is not None else tuple(sorted(SOURCE_IDS))
    lim = limits or {}
    fields: dict[str, Any] = {}
    for sid in wanted:
        f = materialise_source(store, sid, workdir, limit=lim.get(sid))
        if f is not None:
            fields[FIELD_OF[sid]] = f
    if "pkm.artifact" in wanted or "pkm.demand" in wanted:
        fields["pkm_root"] = workdir / "pkm"
        (workdir / "pkm").mkdir(parents=True, exist_ok=True)
    return replace(
        legacy, **fields,
        answers_root=legacy.answers_root or legacy.pkm_root,     # R5: bytes under the identity
        state_sha_source=legacy.state_sha_source or legacy.tasks_ledger,   # R1
    )


def changed_sources(before: Paths, after: Paths) -> tuple[str, ...]:
    """Which JSONL sources a seed redirected (by comparing the two Paths field-wise)."""
    out = []
    for sid, field_name in FIELD_OF.items():
        if getattr(before, field_name) != getattr(after, field_name):
            out.append(sid)
    return tuple(out)


def stream_counts(store: LedgerStore) -> dict[str, int]:
    return {sid: store.parseable_count(sid) for sid in sorted(SOURCE_IDS)}
