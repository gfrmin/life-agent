"""The golden-replay harness — ``docs/unified-ledger-design.md`` §9.

Phase 2 (this tranche): every §9 artefact is **snapshotted from the legacy stores with the
existing folds** at a recorded T0, **replayed** through the same folds, and **compared** by
the pre-stated criterion. Phase 3 re-points ``replay`` at the §7 adapters over the unified
stream; the snapshots and comparators do not change.

    uv run python -m life_agent.ledger.golden snapshot [all|<artefact>] --t0 <T0>
    uv run python -m life_agent.ledger.golden replay   [all|<artefact>]
    uv run python -m life_agent.ledger.golden compare  [all|<artefact>] --t0 <T0> \
                                                       [--seed-defect <name>]
    uv run python -m life_agent.ledger.golden julia-run --t0 <T0>   # A4b, one skin session (S3)
    uv run python -m life_agent.ledger.golden counts                # the two-route counts row

Every ``compare`` prints its comparator's inputs — as **PII-safe locators**: sizes, digests,
and the first differing keys where a key is a hash/id (anything else is redacted to a
digest) — and exits non-zero on mismatch. Transcripts of this tool land in the public repo's
reports, so no record *value* is ever printed.

Criteria (design §9): byte artefacts store the exact canonical bytes/text of the fold's
output; semantic artefacts (A1, A3, A11) store the row multiset. Both compare by canonical
equality; the difference is *what* is stored, which is where R1/R2 live.

Seeded defects run against a **working copy** of the legacy files under
``<snapshot dir>/work/<seed>/`` (owner S1: the only KB subtree this tranche writes), never
against the legacy stores themselves; the pkm cache is copied only for the referenced keys.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import shutil
import sqlite3
import subprocess
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from life_agent.core import calibration as CAL
from life_agent.core import claude_verdicts as CV
from life_agent.core import config
from life_agent.core import decisions as DEC
from life_agent.core import derivations as D
from life_agent.core import gather_outcomes as GO
from life_agent.core import outcomes as O
from life_agent.core import reactions as RX
from life_agent.core import utility as UT
from life_agent.core.narrative import _cell_observations, instrument_identity
from life_agent.ledger import adapters as AD
from life_agent.ledger.paths import Paths
from life_agent.ledger.schema import canonical
from life_agent.ledger.store import LedgerStore
from life_agent.tasks import events as TEV
from life_agent.tasks import knowledge as KN
from life_agent.tasks import store as TST
from life_agent.trips import events as REV
from life_agent.trips import store as RST
from pkm.cache import content_file, meta_file
from pkm.rebuild import (
    LineageCorruptionError,
    _check_meta_consistency,
    _iter_meta_files,
    _meta_to_row,
    _read_lineage,
)

_HEX = re.compile(r"^(ab-)?[0-9a-f]{8,}$")


# --- small helpers -----------------------------------------------------------------------------

def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _canon_lines(path: Path) -> list[str]:
    """Each JSON line re-serialised canonically (the multiset comparator's unit)."""
    return [canonical(json.loads(ln)) for ln in _lines(path)]


def _sorted_multiset(items: list[str]) -> list[str]:
    return sorted(items)


def _norm(value: str) -> str:
    return " ".join(str(value).split()).casefold()


# --- the artefacts (design §7 A1..A14) -- each a pure function Paths -> JSON-able object -------

def a1_gtd(p: Paths) -> Any:
    """A1 — semantic (R2): the `tasks` row multiset projected to the fold-determined columns,
    ignoring the AUTOINCREMENT `id`. `created_at`/`completed_at` stay (S4)."""
    conn = sqlite3.connect(":memory:")
    try:
        TST.create_schema(conn)
        TST.rebuild(conn, TEV.load(p.tasks_ledger))
        rows = conn.execute(
            "SELECT identity, user_id, text, list, due_date, is_today, origin, created_at, "
            "completed_at FROM tasks").fetchall()
    finally:
        conn.close()
    return {"kind": "semantic", "comparator": "multiset of rows ignoring id",
            "rows": _sorted_multiset([canonical(list(r)) for r in rows])}


def a2_state_md(p: Paths) -> Any:
    """A2 — byte (R1): the rendered document, stamp included; the sha is over the legacy
    ledger's BYTES (the dual-written file keeps supplying them in Phase 3)."""
    src = p.state_sha_source or p.tasks_ledger
    data = src.read_bytes() if src.exists() else b""
    text = KN.render(TEV.load(p.tasks_ledger), ledger_sha=_sha(data))
    return {"kind": "byte", "comparator": "byte-identical text", "text": text}


def a3_trips(p: Paths) -> Any:
    """A3 — semantic: the `reservation` row multiset (all columns; identity is the PK)."""
    conn = sqlite3.connect(":memory:")
    try:
        RST.create_schema(conn)
        RST.rebuild(conn, REV.load(p.trips_ledger))
        cols = [r[1] for r in conn.execute("PRAGMA table_info(reservation)").fetchall()]
        rows = conn.execute(f"SELECT {', '.join(cols)} FROM reservation").fetchall()
    finally:
        conn.close()
    return {"kind": "semantic", "comparator": "multiset of full rows", "columns": cols,
            "rows": _sorted_multiset([canonical(list(r)) for r in rows])}


def _utility_evidence(p: Paths) -> tuple[UT.UtilityModel, list[UT.Evidence]]:
    model = UT.load_model(p.utility_model)
    events: list[UT.Evidence] = list(UT.load_elicitations(p.elicitations, model))
    events += RX.load_reactions(p.reactions, p.decisions)   # the declared segment order (§3)
    return model, events


def a4a_fold_version(p: Paths) -> Any:
    """A4a — byte (R3, always-on): the sha over (model, evidence-in-order)."""
    model, events = _utility_evidence(p)
    return {"kind": "byte", "comparator": "fold_version hex equality",
            "fold_version": UT.fold_version(model, events), "n_events": len(events)}


def a4b_posterior(p: Paths, brain: Any) -> Any:
    """A4b — Julia-in-the-loop (R3/S3): the posterior through the pinned credence skin."""
    from life_agent.core import brain as B
    model, events = _utility_evidence(p)
    post = UT.posterior(brain, model, events)
    return {"kind": "julia", "comparator": "exact equality of u_bar and per-latent params",
            "image": B.CREDENCE_SKIN_IMAGE, "protocol_major": B.PROTOCOL_MAJOR,
            "fold_version": post.fold_version, "n_events": post.n_events,
            "u_bar": post.u_bar(),
            "latents": {n: asdict(lp) for n, lp in sorted(post.latents.items())}}


def a5_curves(p: Paths) -> Any:
    """A5 — byte: canonical JSON of fit_edge_curves over the outcomes log."""
    curves = CAL.fit_edge_curves(CAL.edge_outcomes_from_log(p.outcomes))
    return {"kind": "byte", "comparator": "canonical JSON of {edge: bin_reliability}",
            "curves": {e: list(c.bin_reliability) for e, c in sorted(curves.items())}}


def a6_reactions(p: Paths) -> Any:
    """A6 — byte: the folded evidence list, in order."""
    evs = RX.load_reactions(p.reactions, p.decisions)
    return {"kind": "byte", "comparator": "canonical JSON of the evidence list in order",
            "evidence": [{"kind": type(e).__name__, **asdict(e)} for e in evs]}


def a7_claude(p: Paths) -> Any:
    """A7 — byte: latest Claude verdict per decision."""
    latest = CV.latest_by_decision(CV.read(p.claude_verdicts))
    return {"kind": "byte", "comparator": "canonical JSON of latest_by_decision",
            "latest": {k: {"tx_time": v.tx_time, "dimensions": dict(v.dimensions),
                           "issuer": v.issuer, "evidence": list(v.evidence), "note": v.note}
                       for k, v in sorted(latest.items())}}


def a8_gather(p: Paths) -> Any:
    """A8 — byte: the /decide grow block."""
    return {"kind": "byte", "comparator": "canonical JSON of grow_block",
            "grow": GO.grow_block(p.gather_outcomes)}


def a9_cells(p: Paths) -> Any:
    """A9 — byte: the per-cell observation lists and the coverage grade list (current
    instrument)."""
    current = instrument_identity()
    coverage = [1.0 if e.grade in O.CORRECT_GRADES["eval_coverage"] else 0.0
                for e in O.read(p.outcomes)
                if e.grader == "eval_coverage" and e.instrument_identity == current]
    return {"kind": "byte", "comparator": "canonical JSON of cell observations + coverage list",
            "cells": _cell_observations(p.outcomes), "coverage": coverage}


def _answer_keys(p: Paths) -> list[str]:
    return sorted({d.decision_id for d in DEC.read(p.decisions)
                   if re.fullmatch(r"[0-9a-f]{64}", d.decision_id or "")})


def a10_answers(p: Paths) -> Any:
    """A10 — identity + bytes (R5): every decision-referenced §18.9 key → sha of content and
    of meta.json on disk (read replay, never re-execution)."""
    out: dict[str, Any] = {}
    root = p.answers_root or p.pkm_root
    for key in _answer_keys(p):
        if root is None:
            out[key] = {"present": False}
            continue
        content = D.lookup(root, key)
        mf = meta_file(root, key)
        out[key] = {"present": content is not None,
                    "content_sha256": _sha(content) if content is not None else None,
                    "meta_sha256": _sha(mf.read_bytes()) if mf.exists() else None}
    return {"kind": "identity", "comparator": "key set + content/meta digests",
            "keys": out}


def a11_pkm_index(p: Paths) -> Any:
    """A11 — semantic: the `artifacts` + `artifact_lineage` rowsets rebuild_artifacts would
    produce from meta.json/lineage.json (pure, read-only — the catalogue is never touched)."""
    rows: list[str] = []
    lineage: list[str] = []
    root = p.pkm_root
    if root is not None:
        for key, mp in _iter_meta_files(root):
            try:   # rebuild_artifacts' own try/except: the same functions, the same skips (V8)
                meta = json.loads(mp.read_text(encoding="utf-8"))
                _check_meta_consistency(key, meta)
                r = _meta_to_row(key, meta)
                lin = _read_lineage(key, mp.parent)
            except (OSError, json.JSONDecodeError, KeyError, ValueError, TypeError,
                    LineageCorruptionError):
                continue
            rows.append(canonical([x if isinstance(x, (int, float, str, type(None))) else str(x)
                                   for x in r]))
            lineage.extend(canonical(list(t)) for t in lin)
    return {"kind": "semantic", "comparator": "rowset equality of artifacts + artifact_lineage",
            "artifacts": _sorted_multiset(rows), "lineage": _sorted_multiset(lineage)}


def a12_demand(p: Paths) -> Any:
    """A12 — byte (R6): per UTC-day file, the multiset of canonical lines."""
    root = p.pkm_root
    files: dict[str, list[str]] = {}
    if root is not None and (root / "logs" / "demand").exists():
        for f in sorted((root / "logs" / "demand").glob("*.jsonl")):
            files[f.name] = _sorted_multiset(_canon_lines(f))
    return {"kind": "byte", "comparator": "multiset of canonical lines per file", "files": files}


def a13_labels(p: Paths) -> Any:
    """A13 — byte: the label list in order plus the last-wins verdict per (question_id,
    norm(value)) — see r02 DEVIATIONS for the exact-norm restatement."""
    lines = _canon_lines(p.labels)
    last: dict[str, str] = {}
    for ln in lines:
        o = json.loads(ln)
        v = o.get("verdict") or ("correct" if o.get("correct") else "wrong")
        last[f"{o.get('question_id')}\x1f{_norm(o.get('value', ''))}"] = v
    return {"kind": "byte", "comparator": "ordered label lines + last-wins table",
            "labels": lines, "last_wins": last}


def a14_corrections(p: Paths) -> Any:
    """A14 — byte: multiset of canonical lines."""
    return {"kind": "byte", "comparator": "multiset of canonical lines",
            "lines": _sorted_multiset(_canon_lines(p.corrections))}


ARTEFACTS: dict[str, Callable[[Paths], Any]] = {
    "gtd": a1_gtd, "state-md": a2_state_md, "trips": a3_trips,
    "utility-fold-version": a4a_fold_version, "curves": a5_curves, "reactions": a6_reactions,
    "claude-verdicts": a7_claude, "gather": a8_gather, "cells": a9_cells,
    "answers": a10_answers, "pkm-index": a11_pkm_index, "demand": a12_demand,
    "labels": a13_labels, "corrections": a14_corrections,
}
JULIA_ARTEFACT = "utility-posterior"


# --- the two-route counts row -------------------------------------------------------------------

def counts(p: Paths) -> dict[str, Any]:
    """Per legacy source: raw newline count, non-empty lines, and the reader's parsed count."""
    readers: dict[str, Callable[[Path], int]] = {
        "act.tasks": lambda f: len(TEV.load(f)),
        "act.trips": lambda f: len(REV.load(f)),
        "calibration.outcomes": lambda f: len(O.read(f)),
        "calibration.decisions": lambda f: len(DEC.read(f)),
        "calibration.reactions": lambda f: len(RX.read(f)),
        "calibration.claude_verdicts": lambda f: len(CV.read(f)),
        "calibration.gather_outcomes": lambda f: len(_canon_lines(f)),
        "calibration.corrections": lambda f: len(_canon_lines(f)),
        "utility.elicitations": lambda f: len(
            UT.load_elicitations(f, UT.load_model(p.utility_model))),
        "eval.labels": lambda f: len(_canon_lines(f)),
    }
    out: dict[str, Any] = {}
    for sid, f in p.legacy_files().items():
        if not f.exists():
            out[sid] = {"exists": False}
            continue
        data = f.read_bytes()
        out[sid] = {"exists": True, "raw_newlines": data.count(b"\n"),
                    "nonempty_lines": len(_lines(f)), "parsed": readers[sid](f),
                    "sha256": _sha(data)}
    root = p.pkm_root
    if root is not None:
        n_meta = sum(1 for _ in _iter_meta_files(root))
        dd = root / "logs" / "demand"
        n_demand = sum(len(_lines(f)) for f in dd.glob("*.jsonl")) if dd.exists() else 0
        out["pkm.artifact"] = {"meta_json_files": n_meta}
        out["pkm.demand"] = {"lines": n_demand}
    return out


# --- seeded defects (design §9 kill categories + the invariance fixture) --------------------------

@dataclass(frozen=True)
class Seed:
    name: str
    category: str                    # kill-1..4 (reorder/drop/substitute/retarget) | invariance
    must_kill: tuple[str, ...]       # §9's claim
    apply: Callable[[Paths, Path], Paths]   # (paths, workdir) -> paths over a copy
    exact: bool = False              # §9 claims "exactly these" (V5) — a SUPERSET is a MISS


def _copy(src: Path, workdir: Path, name: str) -> Path:
    dst = workdir / name
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.exists():
        shutil.copyfile(src, dst)
    else:
        dst.write_text("", encoding="utf-8")
    return dst


def _rewrite(path: Path, lines: list[str]) -> None:
    path.write_text("".join(ln + "\n" for ln in lines), encoding="utf-8")


def _folded_reaction_ordinals(p: Paths) -> list[int]:
    """Ordinals (0-based line index) of reaction rows that the fold keeps (joined to an abstain
    decision, latest per key)."""
    decisions = {d.decision_id: d for d in DEC.read(p.decisions) if d.decision_id}
    rows = RX.read(p.reactions)
    latest: dict[tuple[str, str], int] = {}
    for i, r in enumerate(rows):
        latest[(r.decision_id, r.kind)] = i
    keep = []
    for (did, _kind), i in latest.items():
        d = decisions.get(did)
        if d is not None and d.chosen_action == "abstain":
            keep.append(i)
    return sorted(keep)


def seed_reorder_reactions(p: Paths, w: Path) -> Paths:
    """Swap two reaction rows on the SAME folded decision with different valence (flips the
    latest-per-key value); else swap the first-appearance rows of two folded keys (flips the
    fold's evidence order — `latest.values()` insertion order)."""
    f = _copy(p.reactions, w, "reactions.jsonl")
    lines = _lines(f)
    rows = RX.read(p.reactions)
    folded_keys = {rows[i].decision_id for i in _folded_reaction_ordinals(p)}
    pair: tuple[int, int] | None = None
    for did in sorted(folded_keys):
        ords = [i for i, r in enumerate(rows) if r.decision_id == did and r.kind == "verdict"]
        for a in ords:
            for b in ords:
                if a < b and rows[a].valence != rows[b].valence:
                    pair = (a, b)
                    break
            if pair:
                break
        if pair:
            break
    if pair is None:
        first = sorted({rows[i].decision_id: i for i in range(len(rows) - 1, -1, -1)
                        if rows[i].decision_id in folded_keys}.values())
        if len(first) < 2:
            raise SystemExit("seed reorder-reactions: fewer than two folded keys — cannot seed")
        pair = (first[0], first[1])
    i, j = pair
    lines[i], lines[j] = lines[j], lines[i]
    _rewrite(f, lines)
    return replace(p, reactions=f)


def seed_reorder_tasks(p: Paths, w: Path) -> Paths:
    f = _copy(p.tasks_ledger, w, "tasks-events.jsonl")
    lines = _lines(f)
    by_identity: dict[str, list[int]] = {}
    for i, ln in enumerate(lines):
        try:
            by_identity.setdefault(json.loads(ln)["identity"], []).append(i)
        except (json.JSONDecodeError, KeyError):
            continue
    # prefer an identity whose second event is an `amended`; else any identity with ≥2 events
    pick = None
    for ords in by_identity.values():
        if len(ords) >= 2 and json.loads(lines[ords[1]]).get("type") == "amended":
            pick = ords[:2]
            break
    if pick is None:
        for ords in by_identity.values():
            if len(ords) >= 2:
                pick = ords[:2]
                break
    if pick is None:
        raise SystemExit("seed reorder-tasks: no identity with two events — cannot seed")
    i, j = pick
    lines[i], lines[j] = lines[j], lines[i]
    _rewrite(f, lines)
    return replace(p, tasks_ledger=f)


def seed_drop_task_disposed(p: Paths, w: Path) -> Paths:
    f = _copy(p.tasks_ledger, w, "tasks-events.jsonl")
    lines = _lines(f)
    idx = [i for i, ln in enumerate(lines) if '"type": "disposed"' in ln
           or '"type":"disposed"' in ln]
    if not idx:
        raise SystemExit("seed drop-task-disposed: no disposed event — cannot seed")
    del lines[idx[-1]]
    _rewrite(f, lines)
    return replace(p, tasks_ledger=f)


def seed_drop_edge_outcome(p: Paths, w: Path) -> Paths:
    f = _copy(p.outcomes, w, "outcomes.jsonl")
    lines = _lines(f)
    idx = [i for i, ln in enumerate(lines) if json.loads(ln).get("grader") == "eval_edge"]
    if not idx:
        raise SystemExit("seed drop-edge-outcome: no eval_edge row — cannot seed")
    del lines[idx[-1]]      # the last row is in force by construction (latest for its lineage)
    _rewrite(f, lines)
    return replace(p, outcomes=f)


def seed_substitute_artifact(p: Paths, w: Path) -> Paths:
    """Copy every decision-referenced §18.9 artefact dir into a work pkm root and flip one byte
    of the first content found."""
    src_root = p.answers_root or p.pkm_root      # the read-replay root (R5)
    if src_root is None:
        raise SystemExit("seed substitute-artifact: no pkm root")
    keys = _answer_keys(p)
    root2 = w / "pkm"
    flipped = False
    for key in keys:
        src_dir = meta_file(src_root, key).parent
        if not src_dir.exists():
            continue
        dst_dir = meta_file(root2, key).parent
        dst_dir.mkdir(parents=True, exist_ok=True)
        for child in src_dir.iterdir():
            if child.is_file():
                shutil.copyfile(child, dst_dir / child.name)
        cf = content_file(root2, key)
        if not flipped and cf.exists() and cf.stat().st_size > 0:
            data = bytearray(cf.read_bytes())
            data[0] ^= 0x01
            cf.write_bytes(bytes(data))
            flipped = True
    if not flipped:
        raise SystemExit("seed substitute-artifact: no referenced artefact content on disk")
    return replace(p, answers_root=root2)


def seed_substitute_decision(p: Paths, w: Path) -> Paths:
    """Alter one credence in the posterior_summary of a decision that a folded reaction joins:
    `credences[0]` for a lookup decision, `marginal_credence` for a narrative one."""
    f = _copy(p.decisions, w, "decisions.jsonl")
    lines = _lines(f)
    reactions = RX.read(p.reactions)
    targets = [reactions[i].decision_id for i in _folded_reaction_ordinals(p)]
    if not targets:
        raise SystemExit("seed substitute-decision: no folded reaction — cannot seed")
    for i, ln in enumerate(lines):
        o = json.loads(ln)
        if o.get("decision_id") not in targets:
            continue
        ps = o.get("posterior_summary", {})
        if ps.get("credences"):
            ps["credences"][0] = 0.5 * float(ps["credences"][0]) or 0.25
        elif ps.get("marginal_credence") is not None:
            ps["marginal_credence"] = 0.5 * float(ps["marginal_credence"]) or 0.25
        else:
            continue
        lines[i] = canonical(o)
        _rewrite(f, lines)
        return replace(p, decisions=f)
    raise SystemExit("seed substitute-decision: no joined decision carries a credence")


def seed_retarget_reaction(p: Paths, w: Path) -> Paths:
    """Repoint one folded reaction's decision_id at a different EXISTING decision."""
    f = _copy(p.reactions, w, "reactions.jsonl")
    lines = _lines(f)
    folded = _folded_reaction_ordinals(p)
    if not folded:
        raise SystemExit("seed retarget-reaction: no folded reaction — cannot seed")
    i = folded[0]
    o = json.loads(lines[i])
    others = [d.decision_id for d in DEC.read(p.decisions)
              if d.decision_id and d.decision_id != o["decision_id"]]
    if not others:
        raise SystemExit("seed retarget-reaction: no other decision to retarget to")
    o["decision_id"] = others[0]
    lines[i] = canonical(o)
    _rewrite(f, lines)
    return replace(p, reactions=f)


def seed_unrouted_reaction(p: Paths, w: Path) -> Paths:
    """The pinned-invariance fixture: a reaction whose decision_id matches no decision."""
    f = _copy(p.reactions, w, "reactions.jsonl")
    lines = _lines(f)
    lines.append(canonical({"tx_time": "2026-01-01T00:00:00+00:00",
                            "question_id": "0" * 16, "decision_id": "ab-" + "0" * 32,
                            "kind": "verdict", "valence": "good", "format_version": 1}))
    _rewrite(f, lines)
    return replace(p, reactions=f)


def seed_unrouted_claude_verdict(p: Paths, w: Path) -> Paths:
    """Kill 5 (V5): a Claude verdict whose decision_id matches no decision. `latest_by_decision`
    is a routing-blind map keyed on decision_id, so the row lands in A7 — and only A7."""
    f = _copy(p.claude_verdicts, w, "claude_verdicts.jsonl")
    lines = _lines(f)
    lines.append(canonical({"tx_time": "2026-01-01T00:00:00+00:00", "question_id": "0" * 16,
                            "decision_id": "ab-" + "0" * 32, "dimensions": {"correct": 1},
                            "evidence": [], "note": "", "issuer": CV.ISSUER,
                            "format_version": 1}))
    _rewrite(f, lines)
    return replace(p, claude_verdicts=f)


SEEDS: dict[str, Seed] = {s.name: s for s in [
    Seed("reorder-reactions", "kill-1 reorder", ("reactions", "utility-fold-version"),
         seed_reorder_reactions),
    Seed("reorder-tasks", "kill-1 reorder", ("gtd", "state-md"), seed_reorder_tasks),
    Seed("drop-task-disposed", "kill-2 drop", ("gtd", "state-md"), seed_drop_task_disposed),
    Seed("drop-edge-outcome", "kill-2 drop", ("curves",), seed_drop_edge_outcome),
    Seed("substitute-artifact", "kill-3 substitute", ("answers",), seed_substitute_artifact),
    Seed("substitute-decision", "kill-3 substitute", ("utility-fold-version", "reactions"),
         seed_substitute_decision),
    Seed("retarget-reaction", "kill-4 retarget", ("reactions", "utility-fold-version"),
         seed_retarget_reaction),
    Seed("unrouted-claude-verdict", "kill-5 unrouted-verdict", ("claude-verdicts",),
         seed_unrouted_claude_verdict, exact=True),
    Seed("unrouted-reaction", "invariance", (), seed_unrouted_reaction),
]}


# --- snapshot / replay / compare -----------------------------------------------------------------

def golden_root(kb: Path | None = None) -> Path:
    return (kb or config.KB) / "ledger" / "golden"


def _digest(obj: Any) -> str:
    return _sha(canonical(obj).encode("utf-8"))


def _locator(key: Any) -> str:
    """A PII-safe rendering of a differing key: hex ids pass through; anything else is a digest."""
    s = str(key)
    return s if _HEX.match(s) else "sha256:" + _sha(s.encode("utf-8"))[:12]


def _diff_locators(a: Any, b: Any, limit: int = 5) -> list[str]:
    """Where two comparator objects differ, as locators only — never values."""
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b), key=str):
            if k not in a:
                out.append(f"+{_locator(k)}")
            elif k not in b:
                out.append(f"-{_locator(k)}")
            elif canonical(a[k]) != canonical(b[k]):
                sub = _diff_locators(a[k], b[k], limit)
                out.append(f"~{_locator(k)}" + (f"[{','.join(sub[:3])}]" if sub else ""))
            if len(out) >= limit:
                break
        return out
    if isinstance(a, list) and isinstance(b, list):
        out = [f"len {len(a)}→{len(b)}"] if len(a) != len(b) else []
        for i, (x, y) in enumerate(zip(a, b, strict=False)):
            if canonical(x) != canonical(y):
                out.append(f"[{i}] {_sha(canonical(x).encode())[:10]}"
                           f"→{_sha(canonical(y).encode())[:10]}")
                if len(out) >= limit:
                    break
        return out
    return [f"{_sha(canonical(a).encode())[:10]}→{_sha(canonical(b).encode())[:10]}"]


def _size(obj: Any) -> str:
    if isinstance(obj, dict):
        for k in ("rows", "keys", "artifacts", "lines", "labels", "evidence"):
            if k in obj and isinstance(obj[k], (list, dict)):
                return f"{k}={len(obj[k])}"
        if "text" in obj:
            return f"bytes={len(obj['text'].encode('utf-8'))}"
    return "-"


def snapshot(names: list[str], t0: str, p: Paths, *, kb: Path | None = None,
             out: Any = None) -> Path:
    out = out or sys.stdout
    d = golden_root(kb) / t0
    d.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {"t0": t0, "head": _git_head(),
                                "written_at": datetime.now(UTC).isoformat(),
                                "counts": counts(p), "artefacts": {}}
    for n in names:
        obj = ARTEFACTS[n](p)
        (d / f"{n}.json").write_text(canonical(obj) + "\n", encoding="utf-8")
        manifest["artefacts"][n] = {"kind": obj["kind"], "digest": _digest(obj),
                                    "size": _size(obj)}
        print(f"snapshot {n:22s} kind={obj['kind']:9s} {_size(obj):14s} "
              f"digest={_digest(obj)[:16]}", file=out)
    (d / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                                     encoding="utf-8")
    return d


def replay(names: list[str], p: Paths, out: Any = None) -> dict[str, Any]:
    out = out or sys.stdout
    res = {}
    for n in names:
        obj = ARTEFACTS[n](p)
        res[n] = obj
        print(f"replay   {n:22s} kind={obj['kind']:9s} {_size(obj):14s} "
              f"digest={_digest(obj)[:16]}", file=out)
    return res


def stream_store(kb: Path | None = None) -> LedgerStore:
    return LedgerStore((kb or config.KB) / "ledger")


def _stream_paths(store: LedgerStore, w: Path, p: Paths, *, out: Any,
                  limits: dict[str, int] | None = None,
                  sources: tuple[str, ...] | None = None) -> Paths:
    """The stream as a Paths (adapters.materialise) + the transcript header line."""
    m = store.manifest()
    counts_ = AD.stream_counts(store)
    print(f"stream   root=$LIFE_AGENT_KB/ledger epoch={m.get('epoch')} "
          f"events={{{', '.join(f'{k}:{v}' for k, v in counts_.items())}}}"
          + (f" truncated_to={json.dumps(limits, sort_keys=True)}" if limits else ""), file=out)
    return AD.materialise(store, w / "materialised", p, limits=limits, sources=sources)


def _seed_on_stream(seeded: Paths, base: Paths, w: Path, *, out: Any) -> Paths:
    """A seed applied to the stream copy: the seed mutated the materialised files; re-migrate
    the affected sources into a WORK store (the writer + segments round trip under the defect)
    and materialise that store back — the fold then reads a genuinely defective stream."""
    from life_agent.ledger import migrate as MG
    changed = AD.changed_sources(base, seeded)
    if not changed:
        print("stream   seed touched no stream source (artefact bytes only) — no re-migration",
              file=out)
        return seeded
    work_store = LedgerStore(w / "stream-copy")
    res = MG.migrate(seeded, work_store, sources=changed, out=io.StringIO(), epoch="seeded")
    print("stream   re-migrated into work store: "
          + ", ".join(f"{r.source_id}={r.after}" for r in res), file=out)
    return AD.materialise(work_store, w / "materialised-seeded", seeded, sources=changed)


def compare(names: list[str], t0: str, p: Paths, *, kb: Path | None = None,
            seed: str | None = None, out: Any = None, source: str = "legacy",
            store: LedgerStore | None = None,
            limits: dict[str, int] | None = None) -> tuple[bool, dict[str, bool]]:
    """Replay each artefact (through a seeded working copy if `seed`; from the unified stream
    if `source == "stream"`), compare against the T0 snapshot by canonical equality, print
    PII-safe locators; returns (all_ok, per-artefact)."""
    out = out or sys.stdout
    d = golden_root(kb) / t0
    w: Path | None = None
    if source not in ("legacy", "stream"):
        raise ValueError(f"source must be legacy|stream, got {source!r}")
    if seed or source == "stream":
        w = work_dir(d, seed or "stream")
        _remove_work(w)
        w.mkdir(parents=True)
    if source == "stream":
        assert w is not None
        p = _stream_paths(store or stream_store(kb), w, p, out=out, limits=limits)
    if seed:
        s = SEEDS[seed]
        assert w is not None
        base = p
        p = s.apply(p, w)
        if source == "stream":
            p = _seed_on_stream(p, base, w, out=out)
        claim = ", ".join(s.must_kill) or "(invariance: must stay green)"
        print(f"seed     {seed} ({s.category}); §9 must kill: "
              f"{'exactly ' if s.exact else ''}{claim}", file=out)
    results: dict[str, bool] = {}
    for n in names:
        snap_path = d / f"{n}.json"
        if not snap_path.exists():
            print(f"compare  {n:22s} NO SNAPSHOT at {t0}", file=out)
            results[n] = False
            continue
        snap = json.loads(snap_path.read_text(encoding="utf-8"))
        now = ARTEFACTS[n](p)
        ok = canonical(snap) == canonical(now)
        results[n] = ok
        line = (f"compare  {n:22s} kind={snap['kind']:9s} comparator=<{snap['comparator']}> "
                f"snapshot[{_size(snap)} {_digest(snap)[:12]}] "
                f"replay[{_size(now)} {_digest(now)[:12]}] → {'GREEN' if ok else 'RED'}")
        if not ok:
            line += "  diff@ " + "; ".join(_diff_locators(snap, now))
        print(line, file=out)
    all_ok = all(results.values())
    if source == "stream" and "answers" in names:
        st = store or stream_store(kb)
        outputs = st.outputs("pkm.artifact")
        keys = _answer_keys(p)
        root = p.answers_root or p.pkm_root
        on_disk = [k for k in keys if root is not None and meta_file(root, k).exists()]
        missing = [k for k in on_disk if k not in outputs]
        print(f"stream   answers: {len(keys)} decision-referenced keys, {len(on_disk)} on disk, "
              f"{len(on_disk) - len(missing)} of those are pkm.artifact outputs on the stream"
              + (f" — MISSING {len(missing)}: {missing[:3]}" if missing else ""), file=out)
    verdict_ok = all_ok
    if seed:
        s = SEEDS[seed]
        killed = tuple(n for n, ok in results.items() if not ok)
        claimed = tuple(n for n in s.must_kill if n in names)
        if s.category == "invariance":
            state = "GREEN as required" if all_ok else "RED — invariance BROKEN"
            verdict_ok = all_ok
            print(f"verdict  invariance fixture: {state}", file=out)
        else:
            missed = [n for n in claimed if n not in killed]
            collateral = [n for n in killed if n not in claimed]
            # V4: CLAIM MET is a floor; the EXACT/SUPERSET flag is reported beside it, and a
            # seed that claims "exactly" (V5) turns any collateral into a MISS.
            flag = "EXACT" if not collateral else f"SUPERSET collateral={collateral}"
            met = not missed and not (s.exact and collateral)
            verdict_ok = met
            print(f"verdict  killed={list(killed)} claimed={list(claimed)} "
                  f"{'CLAIM MET' if met else 'CLAIM MISSED: ' + str(missed or collateral)} "
                  f"[{flag}]", file=out)
    # S8: the working copy is scratch — removed when the (seeded) run completed as claimed
    # (green, for the unseeded stream materialisation), retained for diagnosis otherwise.
    # Nothing but work/<seed>/ (or work/stream/) is ever in its path.
    if w is not None and verdict_ok:
        _remove_work(w)
    return all_ok, results


def work_dir(snapshot_dir: Path, seed: str) -> Path:
    return snapshot_dir / "work" / seed


def _remove_work(w: Path) -> None:
    """S8: scratch deletion only — refuses anything that is not a ``…/work/<seed>`` directory."""
    if w.parent.name != "work" or w.parent.parent.parent.name != "golden":
        raise ValueError(f"refusing to remove {w}: not a golden work directory")
    if w.exists():
        shutil.rmtree(w)


UTILITY_SOURCES = ("utility.elicitations", "calibration.reactions", "calibration.decisions")


def julia_run(t0: str, p: Paths, *, kb: Path | None = None, out: Any = None,
              source: str = "legacy", store: LedgerStore | None = None) -> bool:
    """A4b. ``legacy`` (S3, Phase 2): ONE skin session; snapshot and replay computed inside it
    and compared, the snapshot stored. ``stream`` (S7, Phase 3): ONE skin session; the
    stream's utility evidence — truncated to T0's recorded per-source counts so the evidence
    set matches the stored datum — folded through the pinned skin and compared against the
    STORED T0 `utility-posterior.json` (the R3 comparison proper)."""
    out = out or sys.stdout
    from life_agent.core import brain as B
    d = golden_root(kb) / t0
    d.mkdir(parents=True, exist_ok=True)
    print(f"julia    image={B.CREDENCE_SKIN_IMAGE} protocol_major={B.PROTOCOL_MAJOR}", file=out)
    w: Path | None = None
    if source == "stream":
        snap_path = d / f"{JULIA_ARTEFACT}.json"
        if not snap_path.exists():
            print(f"julia    NO STORED DATUM at {t0} — run the legacy julia-run first", file=out)
            return False
        snap = json.loads(snap_path.read_text(encoding="utf-8"))
        man = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
        limits = {sid: int(man["counts"][sid]["parsed"]) for sid in UTILITY_SOURCES
                  if man["counts"].get(sid, {}).get("exists")}
        w = work_dir(d, "julia-stream")
        _remove_work(w)
        w.mkdir(parents=True)
        p = _stream_paths(store or stream_store(kb), w, p, out=out, limits=limits,
                          sources=UTILITY_SOURCES)
        print(f"julia    evidence truncated to T0 counts {json.dumps(limits, sort_keys=True)} "
              f"(r02 DONE 1) so the evidence set matches the stored datum", file=out)
        with B.Brain.spawn() as brain:
            info = brain.initialize()
            print(f"julia    server={json.dumps(info, sort_keys=True)}", file=out)
            now = a4b_posterior(p, brain)
        note = "the R3 comparison proper: stream fold vs the stored T0 datum (parity leg 2)"
    else:
        with B.Brain.spawn() as brain:
            info = brain.initialize()
            print(f"julia    server={json.dumps(info, sort_keys=True)}", file=out)
            snap = a4b_posterior(p, brain)
            (d / f"{JULIA_ARTEFACT}.json").write_text(canonical(snap) + "\n", encoding="utf-8")
            now = a4b_posterior(p, brain)
        note = "this snapshot is the first credence→proplang parity datum (R3)"
    ok = canonical(snap) == canonical(now)
    print(f"compare  {JULIA_ARTEFACT:22s} kind=julia     comparator=<{snap['comparator']}> "
          f"stored[fold_version={snap['fold_version'][:16]} n_events={snap['n_events']} "
          f"u_bar={json.dumps(snap['u_bar'], sort_keys=True)}] "
          f"replay[fold_version={now['fold_version'][:16]} n_events={now['n_events']} "
          f"u_bar={json.dumps(now['u_bar'], sort_keys=True)}] → {'GREEN' if ok else 'RED'}"
          + ("" if ok else "  diff@ " + "; ".join(_diff_locators(snap, now))), file=out)
    print(f"note     {note}", file=out)
    if w is not None and ok:
        _remove_work(w)
    return ok


def _git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:
        return "unknown"


# --- CLI ------------------------------------------------------------------------------------------

def _names(arg: str) -> list[str]:
    return list(ARTEFACTS) if arg == "all" else [arg]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m life_agent.ledger.golden")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for cmd in ("snapshot", "replay", "compare"):
        s = sub.add_parser(cmd)
        s.add_argument("artefact", nargs="?", default="all")
        s.add_argument("--t0", default=None)
        if cmd == "compare":
            s.add_argument("--seed-defect", default=None, choices=sorted(SEEDS))
            s.add_argument("--from", dest="source", default="legacy",
                           choices=("legacy", "stream"))
    j = sub.add_parser("julia-run")
    j.add_argument("--t0", required=True)
    j.add_argument("--from", dest="source", default="legacy", choices=("legacy", "stream"))
    sub.add_parser("counts")
    args = ap.parse_args(argv)
    p = Paths.from_config()
    if args.cmd == "counts":
        print(json.dumps(counts(p), indent=2, sort_keys=True))
        return 0
    if args.cmd == "snapshot":
        t0 = args.t0 or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        snapshot(_names(args.artefact), t0, p)
        print(f"snapshot dir $LIFE_AGENT_KB/ledger/golden/{t0}")
        return 0
    if args.cmd == "replay":
        replay(_names(args.artefact), p)
        return 0
    if args.cmd == "compare":
        if not args.t0:
            ap.error("--t0 is required for compare")
        ok, _ = compare(_names(args.artefact), args.t0, p, seed=args.seed_defect,
                        source=args.source)
        return 0 if ok else 1
    if args.cmd == "julia-run":
        return 0 if julia_run(args.t0, p, source=args.source) else 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
