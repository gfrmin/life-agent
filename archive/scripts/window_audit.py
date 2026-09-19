"""Window-determinism audit — r08's instrument (register §6.13).

THE FROZEN CRITERIA (committed before any measurement; the report of record is
docs/unification/reports/r08-window-determinism.md — C1..C8 there govern):

  C1  the pre-fix baseline must REPRODUCE the defect (>= 1 draw-unstable question at a
      deployed surface across 5 identical calls) or the checkpoint STOPS with a refutation.
  C2  post-fix the same read is ZERO draw-unstable questions on every surface — any nonzero
      reverts the fix and STOPS for a ruling.
  C3  calls span >= 2 fresh processes (M0.5: the instability is seed/parallelism-dependent;
      in-process stability alone proves nothing) — `live` runs once per process, `stability`
      compares across the files.
  C4  the saturation census is PUBLISHED, never gated: per question/surface the largest
      quantised tie block intersecting the window and whether the boundary block extends
      beyond it (probed at 2x the window).
  C5  three post-fix replay draws compared at commit granularity (r07's measures): the
      retrieval-attributable component of wobble = 0 (hard; attribution = wobble ∩ Read A's
      unstable set); the residue is named, counted, and NOT diagnosed (ruling 4's cap).
  C8  outputs carry qids, fingerprints and counts only — never chunk text, queries, or
      leader values; files land under $LIFE_AGENT_KB/eval/window/.

Three subcommands, each $0 and read-only over the catalogue:

  live       Read A + Read B in one pass: per question x surface, N identical calls
             fingerprinted at BOTH layers (the raw over-fetch window and the deduped top-k),
             plus the census probe at 2x the window.
  stability  merge >= 2 `live` files (C3): per question/surface verdict over ALL calls in
             all files; names the unstable set.
  draws      compare >= 2 replay rows-dumps (scripts/replay_audit.py --out-yaml) at commit
             granularity and split any wobble by the `stability` file's unstable set.

Surfaces (the deployed callers' shapes, docs/unification/reports/r08 STATE):
  base      retrieve_set(conn, question, k=20)            — the arm's first pass
  expanded  retrieve_set(conn, question+cached terms, 20) — CACHED expansion only; a cold
            expansion skips the surface and names it ($0 — no model call exists here)
  pool      retrieve_set(conn, question, k=150)           — the rerank pool cut
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

SURFACE_K = {"base": 20, "expanded": 20, "pool": 150}
OVER_FETCH = 4          # mirrors retrieve_set / probe_corroborate: window = k * 4
DEFAULT_CALLS = 5


# --- pure measures (tested hermetically) -----------------------------------------------------

def quantise(score: float) -> float:
    """R2's quantum: the ninth decimal place, where 1-2 ulp of engine noise dies."""
    return round(score, 9)


def fingerprint(hit: dict[str, Any]) -> str:
    """One row's semantic identity — the full tuple the declared order ranks. Hashed so the
    output files carry no corpus text (C8)."""
    blob = f"{hit['artifact_cache_key']}\x1f{hit['chunk_text']}\x1f{quantise(hit['score'])!r}"
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def draw_verdict(draws: list[list[str]]) -> str:
    """Compare N fingerprint lists: 'stable' (identical, order included), 'order' (same
    rows, permuted), 'set' (different rows). Order matters — the declared key's ORDER is
    what every downstream consumer folds in."""
    first = draws[0]
    if all(d == first for d in draws[1:]):
        return "stable"
    if all(sorted(d) == sorted(first) for d in draws[1:]):
        return "order"
    return "set"


def census(qscores: list[float], window: int) -> dict[str, Any]:
    """Read B: given (already descending) scores probed at ~2x the window, the largest
    quantised tie block intersecting the window, and whether the block at the cut boundary
    extends beyond it — i.e. whether the window SAMPLED a population it did not contain."""
    q = [quantise(s) for s in qscores]
    blocks = Counter(q)
    in_window = q[:window]
    largest = max((blocks[s] for s in set(in_window)), default=0)
    straddles = len(q) > window and q[window - 1] == q[window]
    boundary = blocks[q[window - 1]] if len(q) >= window and window > 0 else 0
    return {"rows_probed": len(q), "largest_block_in_window": largest,
            "boundary_block": boundary, "straddles": straddles}


def wobble_census(draws: list[dict[str, dict[str, Any] | None]]) -> dict[str, list[str]]:
    """Read C's comparator, r07's measures at N draws: per question — 'stable' (readable
    everywhere, identical (action, n_obs)), 'wobble' (readable everywhere, differing),
    'flap' (readable in some draws, cold in others), 'never' (cold everywhere)."""
    qids = sorted({q for d in draws for q in d})
    out: dict[str, list[str]] = {"stable": [], "wobble": [], "flap": [], "never": []}
    for qid in qids:
        views = [d.get(qid) for d in draws]
        if all(v is None for v in views):
            out["never"].append(qid)
        elif any(v is None for v in views):
            out["flap"].append(qid)
        else:
            keys = {(v["action"], v["n_obs"]) for v in views if v is not None}
            out["wobble" if len(keys) > 1 else "stable"].append(qid)
    return out


def attribute(*, wobble: list[str], unstable: list[str]) -> dict[str, list[str]]:
    """C5's split: a wobbling question is §6.13's ONLY if its live retrieval is unstable;
    the rest is residue — named and left (ruling 4's cap forbids diagnosing it here)."""
    u = set(unstable)
    return {"retrieval_attributable": sorted(set(wobble) & u),
            "residue": sorted(set(wobble) - u)}


def rows_from_dump(path: Path) -> dict[str, dict[str, Any] | None]:
    """One replay rows-dump -> {qid: {'action','n_obs'}} for readable rows, None for cold or
    excluded ones (excluded entries are 'qid (reason)' / 'qid/mode (reason)' strings)."""
    blob = json.loads(path.read_text())
    out: dict[str, dict[str, Any] | None] = {}
    for entry in blob.get("excluded", []):
        out[str(entry).split(" ")[0].split("/")[0]] = None
    for row in blob.get("rows", []):
        dep = row.get("deployed")
        out[row["qid"]] = ({"action": dep["action"], "n_obs": dep["n_obs"]}
                           if dep else None)
    return out


# --- the live read (Read A + Read B; read-only, $0) ------------------------------------------

def _connect() -> Any:
    import duckdb

    from life_agent.tasks import read
    root = read.pkm_root()
    conn = duckdb.connect(str(root / "catalogue.duckdb"), read_only=True)
    conn.execute("INSTALL fts; LOAD fts;")
    return root, conn


def _cached_terms(root: Path, question: str) -> str | None:
    """The expansion the deployed arm would use, CACHE ONLY — a cold key returns None and
    the surface is skipped by name. No model client exists in this process."""
    import life_agent.core as C
    from life_agent.core import derivations as D
    from life_agent.core.expansion import EXPAND_MODEL, EXPAND_SYSTEM, usable_terms
    key = D.expand_key(question, model=EXPAND_MODEL, prompt_template=EXPAND_SYSTEM,
                       temperature=C.TEMPERATURE, max_tokens=120)
    cached = D.lookup(root, key.cache_key)
    return usable_terms(cached.decode("utf-8")) if cached is not None else None


def live_read(questions: list[dict], calls: int) -> dict[str, Any]:
    from life_agent.core.retrieval import build_query, retrieve_set
    from pkm.retrieval import search
    root, conn = _connect()
    out: dict[str, Any] = {"calls": calls, "questions": {}}
    for q in questions:
        qid, text = q["id"], q["question"]
        surfaces: dict[str, Any] = {}
        for name, k in SURFACE_K.items():
            if name == "expanded":
                terms = _cached_terms(root, text)
                if terms is None:
                    surfaces[name] = {"skipped": "expansion cold"}
                    continue
                query = build_query(text, terms)
            else:
                query = text
            window = k * OVER_FETCH
            window_draws, top_draws = [], []
            for _ in range(calls):
                raw = search(conn, query, k=window)
                window_draws.append([fingerprint(h.__dict__ | {"score": h.score})
                                     for h in raw])
                top_draws.append([fingerprint(h) for h in retrieve_set(conn, query, k)])
            probe = search(conn, query, k=window * 2)
            surfaces[name] = {
                "window": {"verdict": draw_verdict(window_draws), "draws": window_draws},
                "top": {"verdict": draw_verdict(top_draws), "draws": top_draws},
                "census": census([h.score for h in probe], window),
            }
        out["questions"][qid] = surfaces
    return out


# --- merges ----------------------------------------------------------------------------------

def merge_stability(files: list[Path]) -> dict[str, Any]:
    blobs = [json.loads(p.read_text()) for p in files]
    qids = sorted({q for b in blobs for q in b["questions"]})
    per_q: dict[str, Any] = {}
    unstable: list[str] = []
    for qid in qids:
        verdicts: dict[str, str] = {}
        for surf in SURFACE_K:
            # Window and top-k rows are different-length lists: pool ALL calls from ALL
            # processes within each layer (C3 — cross-process disagreement must convict even
            # when every process is internally stable), then let the worse layer speak (the
            # deduped top-k can mask a sampled window).
            wdraws = [d for b in blobs
                      for d in (b["questions"].get(qid, {}).get(surf) or {})
                      .get("window", {}).get("draws", [])]
            tdraws = [d for b in blobs
                      for d in (b["questions"].get(qid, {}).get(surf) or {})
                      .get("top", {}).get("draws", [])]
            if not wdraws and not tdraws:
                verdicts[surf] = "skipped"
                continue
            vw = draw_verdict(wdraws) if wdraws else "stable"
            vt = draw_verdict(tdraws) if tdraws else "stable"
            order = {"stable": 0, "order": 1, "set": 2}
            verdicts[surf] = vw if order[vw] >= order[vt] else vt
        per_q[qid] = verdicts
        if any(v in ("order", "set") for v in verdicts.values()):
            unstable.append(qid)
    return {"files": [str(p) for p in files], "per_question": per_q,
            "unstable": unstable, "n_unstable": len(unstable)}


def compare_draws(rows_files: list[Path], stability_file: Path | None) -> dict[str, Any]:
    draws = [rows_from_dump(p) for p in rows_files]
    wc = wobble_census(draws)
    unstable = (json.loads(stability_file.read_text())["unstable"]
                if stability_file else [])
    att = attribute(wobble=wc["wobble"], unstable=unstable)
    return {"files": [str(p) for p in rows_files],
            "census": {k: len(v) for k, v in wc.items()}, **wc, **att}


# --- cli -------------------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("live")
    p.add_argument("--questions", required=True)
    p.add_argument("--calls", type=int, default=DEFAULT_CALLS)
    p.add_argument("--out", required=True)
    p = sub.add_parser("stability")
    p.add_argument("files", nargs="+")
    p.add_argument("--out", required=True)
    p = sub.add_parser("draws")
    p.add_argument("files", nargs="+")
    p.add_argument("--stability")
    p.add_argument("--out", required=True)
    args = ap.parse_args()

    if args.cmd == "live":
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from run_eval import load_questions
        result = live_read(load_questions(args.questions), args.calls)
    elif args.cmd == "stability":
        result = merge_stability([Path(f) for f in args.files])
        print(f"unstable: {result['n_unstable']} -> {result['unstable']}")
    else:
        result = compare_draws([Path(f) for f in args.files],
                               Path(args.stability) if args.stability else None)
        print(f"census: {result['census']}  retrieval_attributable: "
              f"{result['retrieval_attributable']}  residue: {result['residue']}")
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
