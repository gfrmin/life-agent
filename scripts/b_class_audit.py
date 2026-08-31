#!/usr/bin/env python3
"""r39 — the B class: which constant kills narrative inclusion?

    uv run python scripts/b_class_audit.py

Binds the DEPLOYED functional (`narrative.include_eu`, `narrative._include_fn`) and the
production `u_bar`; it never re-derives the algebra (`M-7`, six instances). Criteria B1-B5 are
frozen in `docs/unification/reports/r39-b-class-preregistration.md`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from life_agent.core import config as CFG
from life_agent.core import narrative as NARR

#: The point-estimate EU. `narrative.include_eu`'s own docstring says it is **NOT on the
#: decision path** — it is the reference formula. Kept for the contrast the report draws.
include_eu = NARR.include_eu

#: The DEPLOYED functional. The engine evaluates THIS over the cell Beta; the audit binds it
#: and evaluates its declared terms rather than re-deriving the integral (`M-7`).
include_fn = NARR._include_fn

REASON = NARR.REASON_ALL_WITHHELD


def narrative_rows(path: Path | None = None) -> list[dict[str, Any]]:
    """Every narrative-family decision row. B1's population."""
    p = path or CFG.DECISIONS_LOG
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("family") == "narrative":
            out.append(r)
    return out


def observed_cells(rows: list[dict[str, Any]]) -> list[tuple[str, float, float]]:
    """Every (cell, a, b) the decisions actually recorded — REAL Betas, one per row-cell.

    The first version of this function returned ``(max(a), max(b))`` per cell, which composes
    a Beta that may never have occurred: taking the largest ``a`` from one row and the largest
    ``b`` from another describes no decision. Defect found and fixed before the verdict; the
    report publishes it (r05's lesson)."""
    out: list[tuple[str, float, float]] = []
    for r in rows:
        for cell, ab in ((r.get("posterior_summary") or {}).get("cells") or {}).items():
            a, b = float(ab[0]), float(ab[1])
            if a + b > 0:
                out.append((cell, a, b))
    return out


def integrated_eu(a: float, b: float, u_bar: dict[str, float], tf: float = 1.0) -> float:
    """The DEPLOYED claim-EU on a cell Beta(a, b): `_include_fn`'s declared terms evaluated at
    the Beta's own moments, E[θ] and E[θ²]. This is what the engine optimises — the point
    estimate at E[θ] is NOT (see `narrative.include_eu`'s docstring), and the two differ by
    the variance term, which is positive and therefore *favours* inclusion."""
    fn = include_fn(u_bar, tf)
    e1 = a / (a + b)
    e2 = a * (a + 1) / ((a + b) * (a + b + 1))
    total = float(fn["offset"])
    for coef, term in fn["terms"]:
        total += float(coef) * (e2 if term["type"] == "centered_power" else e1)
    return total


def breakeven_reliance(u_bar: dict[str, float], kappa: float | None = None,
                       lo: float = 0.0, hi: float = 1.0, iters: int = 200) -> float | None:
    """The reliance p at which the DEPLOYED point EU crosses zero, by bisection on the
    imported `include_eu`. None when no p in [0,1] clears it."""
    ub = dict(u_bar)
    if kappa is not None:
        ub["kappa_att"] = kappa
    if include_eu(hi, ub) < 0:
        return None
    for _ in range(iters):
        mid = (lo + hi) / 2
        if include_eu(mid, ub) < 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def kappa_for(p: float, u_bar: dict[str, float]) -> float:
    """The kappa at which reliance p exactly breaks even: kappa = p*u_assert(p)."""
    return include_eu(p, {**u_bar, "kappa_att": 0.0})


def u_wrong_for(p: float, u_bar: dict[str, float], lo: float = -100.0,
                hi: float = 0.0, iters: int = 200) -> float | None:
    """The u_wrong at which reliance p exactly breaks even, by bisection on the imported EU."""
    if include_eu(p, {**u_bar, "u_wrong": hi}) < 0:
        return None
    for _ in range(iters):
        mid = (lo + hi) / 2
        if include_eu(p, {**u_bar, "u_wrong": mid}) < 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2
