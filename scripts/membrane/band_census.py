"""band_census.py — r50's S2 census: does any frozen candidate family SEPARATE the 70-90 band?

Pre-registered in `docs/unification/reports/r50-band-sharpening-preregistration.md` (S2, KILL).
Three candidates, frozen there: `runner-up` (the second-largest candidate credence), `leader-share`
(the leader's share of the non-null mass) and `n-candidates-fine` ({1, 2, 3, 4plus}). The
bucketing rule is X-only: each tercile-bucketed candidate's cell edges are the terciles of the
feature over the WHOLE keyed replay, rounded to two decimals, computed and printed BEFORE any
realised-correctness figure — so the edges cannot be tuned to y.

Band membership is read THROUGH the harness's own `features_for` (`M-7`): a tick is in the band
iff its `leader-credence=70to80` or `leader-credence=80to90` indicator is set. The separation
test (S2): a cell with n ≥ 10 at or below the deployed break-even AND one with n ≥ 10 above it,
AND a Beta(1,1) Beta-Binomial Bayes factor of the split model over the pooled model ≥ 10.

$0, no engine. Run: `uv run --project . python scripts/membrane/band_census.py`
"""
from __future__ import annotations

import argparse
import json
import math
import statistics as st
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, "scripts")

import membrane.lattice_replay as LR
import membrane.p3_gate as P3
import membrane.report as R
from life_agent.core import config as C
from life_agent.membrane import world as W

CANDIDATES: tuple[str, ...] = ("runner-up", "leader-share", "n-candidates-fine")
BAND_CELLS: tuple[str, ...] = ("leader-credence=70to80", "leader-credence=80to90")
# S2's frozen break-even: the deployed boot Ū's at r49 (`u_wrong` -5.13099). The live boot Ū is
# printed beside it for disclosure; the criterion itself is the frozen number.
FROZEN_BREAK_EVEN = 0.8369
MIN_CELL_N = 10
BF_MIN = 10.0


def feature_value(fid: str, s: W.DecideSummary) -> float | None:
    if fid == "runner-up":
        return float(s.runner_up_credence)
    if fid == "leader-share":
        if s.leader_credence is None:
            return None
        if s.p_none is not None and s.p_none < 1.0:
            return float(s.leader_credence) / (1.0 - float(s.p_none))
        return float(s.leader_credence)
    if fid == "n-candidates-fine":
        return float(min(int(s.n_candidates), 4))
    raise ValueError(f"unknown candidate {fid!r} (frozen: {CANDIDATES})")


def tercile_edges(values: Sequence[float]) -> tuple[float, float]:
    """The frozen X-only rule: the two terciles over ALL supplied values, rounded to 2 dp."""
    q = st.quantiles(list(values), n=3)
    return (round(q[0], 2), round(q[1], 2))


def cell_of(fid: str, value: float, edges: tuple[float, float]) -> str:
    if fid == "n-candidates-fine":
        k = int(value)
        return "4plus" if k >= 4 else str(k)
    if fid == "runner-up" and value == 0.0:
        return "none"                       # structurally zero: fewer than two candidates
    e1, e2 = edges
    if value < e1:
        return f"lt{e1:g}"
    if value < e2:
        return f"{e1:g}to{e2:g}"
    return f"ge{e2:g}"


def in_band(s: W.DecideSummary) -> bool:
    """Through the harness's own feature function, never a re-spelled threshold (`M-7`)."""
    feats = LR.features_for(s, 0.0, ["leader-credence"])
    return any(feats.get(name) == 1.0 for name in BAND_CELLS)


@dataclass(frozen=True)
class CellStat:
    cell: str
    n: int
    correct: int

    @property
    def rate(self) -> float | None:
        return (self.correct / self.n) if self.n else None


def _lbeta(a: float, b: float) -> float:
    return math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)


def log_bayes_factor(cells: Sequence[CellStat]) -> float:
    """ln of the Beta(1,1) Beta-Binomial marginal likelihood of the SPLIT model (one rate per
    cell) over the POOLED model (one rate for the band). Each cell's marginal is
    B(k+1, n-k+1)/B(1,1) and B(1,1) = 1, so the split is a sum of log-Betas."""
    split = sum(_lbeta(c.correct + 1, c.n - c.correct + 1) for c in cells)
    n = sum(c.n for c in cells)
    k = sum(c.correct for c in cells)
    return split - _lbeta(k + 1, n - k + 1)


def separates(cells: Sequence[CellStat], *, break_even: float,
              min_n: int = MIN_CELL_N, bf_min: float = BF_MIN) -> bool:
    big = [c for c in cells if c.n >= min_n and c.rate is not None]
    low = any(c.rate is not None and c.rate <= break_even for c in big)
    high = any(c.rate is not None and c.rate > break_even for c in big)
    if not (low and high) or len(cells) < 2:
        return False
    return log_bayes_factor(cells) >= math.log(bf_min)


def _cell_order(fid: str, edges: tuple[float, float]) -> list[str]:
    if fid == "n-candidates-fine":
        return ["1", "2", "3", "4plus"]
    e1, e2 = edges
    names = [f"lt{e1:g}", f"{e1:g}to{e2:g}", f"ge{e2:g}"]
    return (["none", *names]) if fid == "runner-up" else names


def census(keyed: Sequence[P3.KeyedTick], *, break_even: float) -> dict[str, Any]:
    """Edges from EVERY tick (X only), cells from the BAND only (X and y). The verdict is S2's:
    the separating candidate with the largest Bayes factor is the winner (ties resolve in the
    frozen candidate order); none separating is KILL."""
    band = [t for t in keyed if in_band(t.summary)]
    out: dict[str, Any] = {"n_ticks": len(keyed), "band_n": len(band),
                           "break_even": break_even, "min_cell_n": MIN_CELL_N,
                           "bf_min": BF_MIN, "candidates": {}, "winner": None,
                           "verdict": "KILL"}
    best: tuple[float, str] | None = None
    for fid in CANDIDATES:
        xs = [v for t in keyed if (v := feature_value(fid, t.summary)) is not None]
        edges = tercile_edges(xs) if (fid != "n-candidates-fine" and len(xs) >= 2) else (0.0, 0.0)
        counts: dict[str, list[int]] = {}
        for t in band:
            v = feature_value(fid, t.summary)
            if v is None:
                continue
            c = counts.setdefault(cell_of(fid, v, edges), [0, 0])
            c[0] += 1
            c[1] += int(t.y)
        cells = [CellStat(name, counts[name][0], counts[name][1])
                 for name in _cell_order(fid, edges) if name in counts]
        lbf = log_bayes_factor(cells) if len(cells) >= 2 else None
        sep = separates(cells, break_even=break_even)
        out["candidates"][fid] = {
            "edges": edges, "cells": [{"cell": c.cell, "n": c.n, "correct": c.correct,
                                       "rate": c.rate} for c in cells],
            "log_bf": lbf, "bf": (math.exp(lbf) if lbf is not None else None),
            "separates": sep,
        }
        if sep and lbf is not None and (best is None or lbf > best[0]):
            best = (lbf, fid)
    if best is not None:
        out["winner"] = best[1]
        out["verdict"] = "SEPARATES"
    return out


def render(out: dict[str, Any]) -> str:
    lines = [f"keyed replay: {out['n_ticks']} ticks · band (70-90): {out['band_n']} rows · "
             f"break-even {out['break_even']:.4f} · min cell n {out['min_cell_n']} · "
             f"BF ≥ {out['bf_min']:g}",
             "", "EDGES (X only — computed before any y was read):"]
    for fid, c in out["candidates"].items():
        e1, e2 = c["edges"]
        lines.append(f"  {fid:<20} terciles ({e1:g}, {e2:g})"
                     if fid != "n-candidates-fine" else f"  {fid:<20} cells 1 / 2 / 3 / 4plus")
    lines += ["", "CELLS (band rows only):"]
    for fid, c in out["candidates"].items():
        bf = "n/a" if c["bf"] is None else f"{c['bf']:.3g}"
        lines.append(f"  {fid:<20} BF {bf:>8}  separates={c['separates']}")
        for cell in c["cells"]:
            rate = "n/a" if cell["rate"] is None else f"{cell['rate']:.3f}"
            lines.append(f"    {cell['cell']:<12} n={cell['n']:>3}  correct={cell['correct']:>3}  "
                         f"rate={rate}")
    lines += ["", f"VERDICT (S2): {out['verdict']}"
              + (f" — winner {out['winner']}" if out["winner"] else
                 " — no candidate separates the band; B buys no engine run")]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=C.KB / "eval/r50")
    parser.add_argument("--break-even", type=float, default=FROZEN_BREAK_EVEN)
    args = parser.parse_args(argv)

    import life_agent.core.gate as GATE

    keyed = P3.load_keyed_replay()
    groups = P3.group_by_question(keyed)
    u_bar = R.latest_boot_u_bar(R.load_shadow_records(C.membrane_shadow_log()), "said@1")
    live = GATE.break_even(u_bar) if u_bar else None
    print(f"window: {len(keyed)} ticks / {len(groups)} questions · S2 break-even (frozen) "
          f"{args.break_even:.4f} · live boot break-even "
          f"{live:.4f}" if live is not None else "window: … · live boot Ū unavailable")
    out = census(keyed, break_even=args.break_even)
    out["window"] = {"ticks": len(keyed), "questions": len(groups)}
    out["live_boot_break_even"] = live
    print(render(out))
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "census.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n",
                                          encoding="utf-8")
    print(f"\nWrote → {args.out / 'census.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
