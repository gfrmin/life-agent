# copied from credence-governor@cea4c04 benchmarks/approach_dominance/dominance.py
# (ONLY the tie-band verdict constants/logic — EPS_ABS=1e-9, EPS_REL=0.005, the
# ``_verdict(regret, scale)`` idea — and the ``_tally`` win/tie/loss aggregator
# skeleton, copied as DATA/LOGIC, never imported from credence-governor, a different
# repo. NOT copied: the grid/skin/foil machinery, ``arms.py``, ``routing_belief.py``,
# ``scenarios.py``, ``synthetic_competitors.py`` — this module scores life-agent
# ``OutcomeVector`` rows crossed with declared profiles, not the governor's routing grid.
"""``scripts/dominance/winmap.py`` — the profile-scalarized win map.

One cell per (ordered arm-pair x profile x scenario), ``scenario in {"all", "answerable",
"unanswerable"}`` (filtered by each row's ``answerable`` flag). ``arm_a``/``arm_b`` welfare
is ``utility.welfare`` under that profile over that scenario's rows; the verdict is
``arm_a``'s regret against ``arm_b`` under the copied tie band. A cell is tagged
``cell_source="modelled"`` if ANY contributing row (either arm) has
``cost_status != "measured"``, else ``"measured"`` — matching ``utility.py``'s own
measured/modelled discipline so a modelled cost never quietly inflates a "measured" win.
"""
from __future__ import annotations

import itertools
from typing import Any

from .profiles import PERSONAS, PRESETS, Profile
from .utility import welfare

# Declared tie band (unchanged from the copied source): a verdict is a tie iff
# |welfare regret| ≤ max(EPS_ABS, EPS_REL · scale).
EPS_ABS = 1e-9
EPS_REL = 0.005  # 0.5% of the larger welfare magnitude

SCENARIOS: tuple[str, ...] = ("all", "answerable", "unanswerable")


def _verdict(regret: float, scale: float) -> str:
    band = max(EPS_ABS, EPS_REL * scale)
    if regret > band:
        return "win"
    if regret < -band:
        return "loss"
    return "tie"


def _tally(cells: list[dict[str, Any]]) -> dict[str, Any]:
    w = sum(1 for c in cells if c["verdict"] == "win")
    t = sum(1 for c in cells if c["verdict"] == "tie")
    losses = sum(1 for c in cells if c["verdict"] == "loss")
    n = len(cells)
    return {
        "n": n, "win": w, "tie": t, "loss": losses,
        "weak_dominance": round((w + t) / n, 4) if n else None,
        "strict_win": round(w / n, 4) if n else None,
    }


def all_profiles() -> dict[str, Profile]:
    """``PRESETS`` + ``PERSONAS`` — the win map's default profile set (task-11 brief)."""
    return {**PRESETS, **PERSONAS}


def _scenario_rows(vectors: list[dict[str, Any]], scenario: str) -> list[dict[str, Any]]:
    if scenario == "all":
        return vectors
    if scenario == "answerable":
        return [v for v in vectors if v["answerable"]]
    if scenario == "unanswerable":
        return [v for v in vectors if not v["answerable"]]
    raise ValueError(f"unknown scenario {scenario!r} — declared: {SCENARIOS}")


def _cell_source(rows_a: list[dict[str, Any]], rows_b: list[dict[str, Any]]) -> str:
    measured = all(v["cost_status"] == "measured" for v in rows_a) and all(
        v["cost_status"] == "measured" for v in rows_b
    )
    return "measured" if measured else "modelled"


def build_cells(
    arms: dict[str, list[dict[str, Any]]], profiles: dict[str, Profile] | None = None,
) -> list[dict[str, Any]]:
    """One cell per (ordered arm-pair x profile x scenario).

    ``profiles`` defaults to :func:`all_profiles` (``PRESETS`` + ``PERSONAS``). Ordered
    pairs (both ``(a, b)`` and ``(b, a)``) so every cell's verdict is unambiguously
    "from ``arm_a``'s perspective" without a second lookup. ``n_questions`` is
    ``arm_a``'s row count for that scenario — the two arms are expected to share one
    question corpus (the fair-fight harness's own invariant), so this equals ``arm_b``'s
    count in practice; :mod:`loss_triage` re-derives the actual common ``question_id``
    set per cell rather than trusting this count, so a real mismatch surfaces there
    (fewer than ``n_questions`` triaged rows), not as a silently wrong number here.
    """
    profiles = profiles if profiles is not None else all_profiles()
    names = sorted(arms)
    cells: list[dict[str, Any]] = []
    for arm_a, arm_b in itertools.permutations(names, 2):
        for profile_name, profile in profiles.items():
            for scenario in SCENARIOS:
                rows_a = _scenario_rows(arms[arm_a], scenario)
                rows_b = _scenario_rows(arms[arm_b], scenario)
                welfare_a = welfare(profile, rows_a)
                welfare_b = welfare(profile, rows_b)
                regret = welfare_a - welfare_b
                scale = max(abs(welfare_a), abs(welfare_b), 1.0)
                cells.append({
                    "arm_a": arm_a, "arm_b": arm_b, "profile": profile_name,
                    "scenario": scenario,
                    "welfare_a": round(welfare_a, 6), "welfare_b": round(welfare_b, 6),
                    "regret": round(regret, 6), "verdict": _verdict(regret, scale),
                    "cell_source": _cell_source(rows_a, rows_b),
                    "n_questions": len(rows_a),
                })
    return cells


def pair_tally(cells: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    """Per ordered arm-pair headline: overall + measured-only + modelled-only tallies
    (across every profile x scenario cell for that pair) — the "measured vs modelled
    separated" per-pair tally the brief asks ``summary.md`` to print.
    """
    by_pair: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for c in cells:
        by_pair.setdefault((c["arm_a"], c["arm_b"]), []).append(c)
    return {
        pair: {
            "overall": _tally(rows),
            "measured": _tally([r for r in rows if r["cell_source"] == "measured"]),
            "modelled": _tally([r for r in rows if r["cell_source"] == "modelled"]),
        }
        for pair, rows in by_pair.items()
    }


def region_dominance(
    cells: list[dict[str, Any]], region_profiles: set[str], *, scenario: str = "all",
) -> dict[tuple[str, str], dict[str, Any]]:
    """Per ordered arm-pair: :func:`_tally` restricted to ``scenario`` cells whose
    profile is in ``region_profiles`` (``profiles.in_realistic_region``'s output).

    Interpretation (declared, per the task-11 brief: "uniform weighting ... state the
    interpretation in the docstring"): every qualifying profile counts once — a simple
    unweighted average over ``REALISTIC_REGION``'s profiles, not a weighted integral
    over the continuous ``(harm, lam)`` region (the discrete PRESETS/PERSONAS set is
    the only sample of that region this package has). Restricted to ``scenario="all"``
    by default — the win map's headline scenario; ``answerable``/``unanswerable``
    dominance is available per-cell in ``cells.json`` for a reader who wants the split.
    """
    by_pair: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for c in cells:
        if c["scenario"] != scenario or c["profile"] not in region_profiles:
            continue
        by_pair.setdefault((c["arm_a"], c["arm_b"]), []).append(c)
    return {pair: _tally(rows) for pair, rows in by_pair.items()}
