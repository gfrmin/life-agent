#!/usr/bin/env python3
"""r46 leg B — price the theta grid's precision, and read whether it is free.

    uv run python scripts/membrane/grid_precision.py --leg sweep|w6|equality

Criteria T1-T6 and four consequence branches are frozen in
`docs/unification/reports/r46b-grid-precision-preregistration.md`.

`GD-15` registered the fork (`r44` discretised, so `r04-stocktake` §3(ii)'s "if the swap
discretises, the sixteenths rule applies" came due) and `GD-17` handed it forward after
measuring its first ground false. The deployed grid is entirely NON-DYADIC: read as exact
rationals, every value carries a factor of 5, and the engine's fold cost tracks dyadic
representability rather than wire size.

Everything load-bearing is IMPORTED, never re-implemented (`M-7`):

* the grid rule is `world.theta_grid`, varied ONLY by patching that one module attribute, so
  the wire is always built by the deployed `world.handshake_decl`;
* the session, client and boot are `MembraneSession` / `MembraneClient.spawn` /
  `shadow.boot_snapshot`;
* the summary reducer is `world.summary_from_payload`, the same one `submit_decide` uses;
* the collision constant and the endpoint/quantile/rate constants are read from `world`, never
  restated here.

Engine **CPU** (`utime + stime` from `/proc`), never wall clock: this box runs loaded, which
is `GD-17`'s own rule for the same measurement.
"""
from __future__ import annotations

import argparse
import contextlib
import dataclasses
import itertools
import json
import os
import statistics
import subprocess
import sys
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from life_agent.core import config as CFG
from life_agent.membrane import world as W
from life_agent.membrane.client import MembraneClient
from life_agent.membrane.session import MembraneSession
from life_agent.membrane.shadow import boot_snapshot

DEFAULT_ENGINE = str(Path.home() / ".local/bin/proplang-host")

#: The one collision constant, read from the deployed rule (T3 checks against THIS).
COLLISION = W._GRID_COLLISION


def dyadic(grid: Sequence[float], k: int) -> list[float]:
    """`grid` snapped to the 2**-k lattice. Precision only: the caller checks identity (T3)."""
    return [round(x * (2 ** k)) / (2 ** k) for x in grid]


def grid_identity(base: Sequence[float], snapped: Sequence[float]) -> dict[str, Any]:
    """T3 — did the snap preserve the grid's IDENTITY, as opposed to shrinking it?

    `n`, sort order, and no two rungs merged under the deployed collision constant. A speedup
    bought by collapsing the hypothesis space is a different lever and must not pass as this
    one."""
    gaps = [b - a for a, b in itertools.pairwise(snapped)]
    return {
        "n_before": len(base), "n_after": len(set(snapped)),
        "sorted": list(snapped) == sorted(snapped),
        "min_gap": min(gaps) if gaps else None,
        "no_merge": all(g > COLLISION for g in gaps),
        "max_displacement": max(abs(a - b) for a, b in zip(base, snapped, strict=True)),
    }


def _patch_grid(grid: Sequence[float]) -> Callable[[Mapping[str, float]], list[float]]:
    """A `theta_grid` stand-in returning `grid`, matching the deployed signature exactly."""
    def _grid(u_bar: Mapping[str, float]) -> list[float]:
        return list(grid)
    return _grid


def deployed_snapshot() -> Any:
    """The boot snapshot **the deployed bridge builds** — `server.py:1239-1241`, all four
    arguments, not a subset.

    Caught before the reading (`M-7`, `M-20`): a first pass copied
    `p0_engine_replay.py`'s two-argument call, which omits `warm_vectors_dir` and the Claude
    verdict channel. That snapshot holds **70** verdicts where the deployed one reaches
    **250**, so every "depth 250" row would silently have been a depth-70 row wearing the
    label — and `T2` is precisely a claim about depth 250."""
    return boot_snapshot(CFG.DECISIONS_LOG, CFG.REACTIONS_LOG,
                         CFG.membrane_warm_vectors_dir(),
                         claude_verdicts_path=CFG.CLAUDE_VERDICTS_LOG)


def _child_pid(parent: int) -> int | None:
    out = subprocess.run(["pgrep", "-P", str(parent), "-f", "proplang-host"],
                         capture_output=True, text=True).stdout.split()
    return int(out[0]) if out else None


def _cpu(pid: int) -> float:
    with open(f"/proc/{pid}/stat", encoding="utf-8") as fh:
        parts = fh.read().rsplit(")", 1)[1].split()
    return (int(parts[11]) + int(parts[12])) / os.sysconf("SC_CLK_TCK")


@contextlib.contextmanager
def booted(grid: Sequence[float], u_bar: dict[str, float], depth: int,
           engine: str) -> Iterator[dict[str, Any]]:
    """A session booted to `depth` under `grid`, yielding the session and its boot cost.

    The grid is injected by patching `world.theta_grid` — the wire is still assembled by the
    deployed `handshake_decl`, so this varies precision and nothing else."""
    original = W.theta_grid
    # mypy cannot type a rebound module-level function; the stand-in matches the
    # deployed signature exactly (see `_patch_grid`) and is restored in `finally`.
    W.theta_grid = _patch_grid(grid)  # type: ignore[assignment]
    client = None
    try:
        snap = deployed_snapshot()
        client = MembraneClient.spawn([engine], log=lambda _m: None)
        pid = _child_pid(os.getpid())
        assert pid is not None, "engine child not found — cannot measure CPU"
        sess = MembraneSession(client, u_bar=u_bar, log=lambda _m: None)
        c0, w0 = _cpu(pid), time.time()
        sess.boot(verdict_replay=snap.verdict_replay[:depth], outcome_replay=[])
        yield {"session": sess, "pid": pid, "cpu_s": _cpu(pid) - c0,
               "wall_s": time.time() - w0, "t": sess.t,
               "models": (sess.engine or {}).get("models"),
               "available": len(snap.verdict_replay)}
    finally:
        if client is not None:
            client.shutdown()
        W.theta_grid = original


def live_u_bar() -> dict[str, float]:
    """The `u_bar` the deployed shadow last booted under — read from its own ledger."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import membrane.report as R
    u = R.latest_boot_u_bar(R.load_shadow_records(CFG.membrane_shadow_log()), "said@1")
    if u is None:
        raise SystemExit("no boot u_bar on the shadow ledger")
    return {k: float(v) for k, v in u.items()}


def leg_sweep(u_bar: dict[str, float], engine: str, depths: Sequence[int],
              ks: Sequence[int], reps: int) -> None:
    """T1 + T2 + T3 — the ratio at each depth, including the 250 `GD-17` never reached."""
    base = W.theta_grid(u_bar)
    print(f"base grid n={len(base)}  collision={COLLISION}")
    for k in ks:
        ident = grid_identity(base, dyadic(base, k))
        print(f"  2^-{k:<3} identity {json.dumps(ident)}")
    print()
    for depth in depths:
        for label, grid in [("deployed", base)] + [(f"2^-{k}", dyadic(base, k)) for k in ks]:
            for rep in range(1, reps + 1):
                with booted(grid, u_bar, depth, engine) as b:
                    print(json.dumps({"leg": "sweep", "depth": depth, "grid": label,
                                      "rep": rep, "cpu_s": round(b["cpu_s"], 3),
                                      "wall_s": round(b["wall_s"], 2), "t": b["t"],
                                      "models": b["models"]}), flush=True)


def leg_w6(u_bar: dict[str, float], engine: str, k: int, ticks: Sequence[int]) -> None:
    """T4 — `W6`'s own method, through the DEPLOYED session API.

    `W6` fed blocks of `1 1 1 1 1 1 0` (6/7 = the measured operating rate) and read the `p1`
    gap grow monotonically — 0.001423 / 0.002707 / 0.003189 at 14 / 42 / 98 ticks — moving
    ONE rung by 7e-3. Here every rung moves, by far less, and the gap is measured rather than
    extrapolated from the displacement.

    Evidence is folded with `MembraneSession.observe_verdict` and `p1` is read from
    `decide(...).readouts` — the same two calls the deployed shadow makes. An earlier draft
    hand-rolled a `{"query": {"readouts": [...]}}` request; that is re-spelling the wire, and
    `M-7` is exactly about not doing it."""
    base = W.theta_grid(u_bar)
    probe = W.DecideSummary(n_candidates=2, leader_credence=0.857, p_none=0.05, n_obs=2,
                            era_split=False, owner_scoped=False, grow_pass=False)
    block = [1, 1, 1, 1, 1, 1, 0]
    out: dict[str, dict[int, float | None]] = {}
    for label, grid in (("deployed", base), (f"2^-{k}", dyadic(base, k))):
        original = W.theta_grid
        W.theta_grid = _patch_grid(grid)  # type: ignore[assignment]
        client = None
        try:
            client = MembraneClient.spawn([engine], log=lambda _m: None)
            sess = MembraneSession(client, u_bar=u_bar, log=lambda _m: None)
            sess.boot()
            out[label] = {}
            fed = 0
            for target in ticks:
                while fed < target:
                    sess.observe_verdict(probe, block[fed % len(block)])
                    fed += 1
                value = (sess.decide(probe).readouts or {}).get("p1")
                out[label][target] = float(value) if isinstance(
                    value, (int, float)) else None
        finally:
            if client is not None:
                client.shutdown()
            W.theta_grid = original
    gaps = {t: abs((out["deployed"][t] or 0.0) - (out[f"2^-{k}"][t] or 0.0)) for t in ticks}
    print(json.dumps({"leg": "w6", "k": k, "p1": out,
                      "gap_by_tick": {str(t): gaps[t] for t in ticks},
                      "monotone": all(gaps[a] <= gaps[b]
                                      for a, b in itertools.pairwise(ticks)),
                      "w6_reference_gap_at_98": 0.003189,
                      "w6_reference_displacement": 0.007}, default=str))


def corpus_summaries(checkpoint: str = "m5-base") -> list[tuple[str, Any]]:
    """The decision population: every recorded `/decide` exchange in the pinned corpus,
    reduced by the DEPLOYED reducer (`world.summary_from_payload` — the same call
    `submit_decide` makes), deduplicated on the summary itself.

    A decide is a function of the summary at a given engine state, so identical summaries
    cannot disagree; the raw and distinct counts are both reported so the population is never
    quoted as larger than it decides."""
    root = CFG.KB / "eval" / "collapse-fixtures" / checkpoint
    seen: dict[tuple[Any, ...], tuple[str, Any]] = {}
    raw = 0
    for path in sorted(root.glob("*.json")):
        if path.name == "manifest.json":
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        for ex in doc.get("wire") or []:
            req = ex.get("request")
            if not isinstance(req, dict) or req.get("url") != "/decide":
                continue
            payload, dec = req.get("payload"), ex.get("response")
            if not (isinstance(payload, dict) and isinstance(dec, dict)):
                continue
            raw += 1
            summary = W.summary_from_payload(payload, dec)
            seen.setdefault(dataclasses.astuple(summary),
                            (str(doc.get("fixture_id")), summary))
    print(f"population: {raw} recorded /decide exchanges -> {len(seen)} distinct summaries")
    return list(seen.values())


def leg_equality(u_bar: dict[str, float], engine: str, k: int, depth: int) -> None:
    """T5 — the leg that decides. Actions under the deployed grid vs the snapped one, at one
    fixed fold depth, over the pinned corpus's own decide population. Every differing row is
    named; `p1` is reported alongside so a near-tie is visible as a near-tie."""
    population = corpus_summaries()
    base = W.theta_grid(u_bar)
    results: dict[str, list[Any]] = {}
    for label, grid in (("deployed", base), (f"2^-{k}", dyadic(base, k))):
        with booted(grid, u_bar, depth, engine) as b:
            sess = b["session"]
            rows = []
            for fixture_id, summary in population:
                choice = sess.decide(summary)
                rows.append((fixture_id, choice.action,
                             (choice.readouts or {}).get("p1")))
            results[label] = rows
            print(json.dumps({"leg": "equality", "grid": label, "depth": depth,
                              "boot_cpu_s": round(b["cpu_s"], 3), "t": b["t"],
                              "models": b["models"], "n": len(rows)}), flush=True)
    a, c = results["deployed"], results[f"2^-{k}"]
    differing = [(fa, aa, ca, pa, pc)
                 for (fa, aa, pa), (_fc, ca, pc) in zip(a, c, strict=True) if aa != ca]
    gaps = [abs((pa or 0.0) - (pc or 0.0)) for (_f, _a, pa), (_g, _b, pc)
            in zip(a, c, strict=True)]
    print(json.dumps({"leg": "equality", "n": len(a), "n_differing_actions": len(differing),
                      "differing": differing[:20],
                      "p1_gap_max": max(gaps) if gaps else None,
                      "p1_gap_median": statistics.median(gaps) if gaps else None,
                      "w6_reference_scale": 0.003189}, default=str))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--leg", required=True, choices=["sweep", "w6", "equality"])
    ap.add_argument("--engine", default=DEFAULT_ENGINE)
    ap.add_argument("--depths", default="0,25,60,100,250")
    ap.add_argument("--ks", default="8,11,14")
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--k", type=int, default=14)
    ap.add_argument("--equality-depth", type=int, default=60)
    args = ap.parse_args(argv)
    u_bar = live_u_bar()
    if args.leg == "sweep":
        leg_sweep(u_bar, args.engine,
                  [int(d) for d in args.depths.split(",")],
                  [int(k) for k in args.ks.split(",")], args.reps)
    elif args.leg == "w6":
        leg_w6(u_bar, args.engine, args.k, [14, 42, 98])
    else:
        leg_equality(u_bar, args.engine, args.k, args.equality_depth)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
