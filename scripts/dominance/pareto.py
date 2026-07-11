"""``scripts/dominance/pareto.py`` — the profile-independent Pareto frontier.

Pure (no I/O): a point is one arm's position on four axes, oriented so "more is always
better" on every axis (cost/latency/attention are negated) — that makes the dominance
test a single elementwise comparison, no per-axis sign-flipping at the call site.
"""
from __future__ import annotations

from typing import Any

# (correct_rate, -total_cost, -mean_latency, -attention) — "more is better" on all four.
Point = tuple[float, float, float, float]


def _attention(v: dict[str, Any]) -> float:
    """One row's attention contribution: ``asks_issued`` plus whichever effort counter
    the arm actually reports (``gather_rounds`` when the arm has a gather stage, else
    ``tool_calls`` if any, else 0 — never both, and never imputed beyond that fallback).
    """
    gather = v["gather_rounds"]
    return v["asks_issued"] + (gather if gather is not None else (v["tool_calls"] or 0))


def build_point(vectors: list[dict[str, Any]]) -> tuple[Point, int, bool]:
    """One arm's ``Point`` plus (1) the count of rows with no priced cost (``cost_usd is
    None``) and (2) ``cost_unpriced`` — ``True`` iff the arm has rows but NOT ONE was
    priced (every ``cost_usd is None``), so its ``total_cost`` axis is 0.0 by absence, not
    by measurement. Both are reported alongside, per the brief ("never silently"), not
    folded into the cost sum.

    PR-21 IMPORTANT-2: an all-unpriced arm (the executor baseline: every row
    ``cost_status="partial"``, ``cost_usd=None``) would otherwise land at ``total_cost=0``
    and sit on the frontier via the ``-total_cost`` axis as if it were free. Frontier
    membership itself is left as a printed modelling choice (cost-as-0), but this flag
    makes the "unmeasured, not free" caveat carry through ``frontier.json``/``summary.md``.
    """
    n = len(vectors)
    correct_rate = (sum(1 for v in vectors if v["bucket"] == "CORRECT") / n) if n else 0.0
    costs = [v["cost_usd"] for v in vectors if v["cost_usd"] is not None]
    n_missing_cost = sum(1 for v in vectors if v["cost_usd"] is None)
    cost_unpriced = bool(vectors) and not costs
    total_cost = sum(costs)
    mean_latency = (sum(v["latency_s"] for v in vectors) / n) if n else 0.0
    attention = sum(_attention(v) for v in vectors)
    return (correct_rate, -total_cost, -mean_latency, -attention), n_missing_cost, cost_unpriced


def build_points(
    arms: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, Point], dict[str, int], dict[str, bool]]:
    """``{arm: Point}`` plus ``{arm: n_missing_cost}`` and ``{arm: cost_unpriced}`` over
    every arm in ``arms``."""
    points: dict[str, Point] = {}
    n_missing_cost: dict[str, int] = {}
    cost_unpriced: dict[str, bool] = {}
    for arm, vectors in arms.items():
        points[arm], n_missing_cost[arm], cost_unpriced[arm] = build_point(vectors)
    return points, n_missing_cost, cost_unpriced


def frontier(points: dict[str, Point]) -> set[str]:
    """The weakly non-dominated subset of ``points``.

    An arm ``a`` is dominated (excluded) only if some other arm ``b`` is ``>=`` on every
    axis AND ``>`` on at least one — i.e. ``b`` weakly dominates ``a``. A tie on every
    axis leaves both arms on the frontier (neither dominates the other).
    """
    names = list(points)
    result = set(names)
    for a in names:
        pa = points[a]
        for b in names:
            if b == a:
                continue
            pb = points[b]
            if all(y >= x for x, y in zip(pa, pb, strict=True)) and any(
                y > x for x, y in zip(pa, pb, strict=True)
            ):
                result.discard(a)
                break
    return result
