#!/usr/bin/env python3
"""``scripts/dominance/run_dominance.py`` — the dominance-analysis CLI.

Reads a finished ``run_fairfight.py`` run directory's ``arms/<arm>/vectors.jsonl``
(validated ``OutcomeVector`` rows — ``life_agent.fairfight.records.from_json``, so a
malformed row fails loudly here rather than silently skewing a welfare sum downstream),
computes the Pareto frontier (``pareto.py``) and the profile-scalarized win map + loss
triage (``profiles.py``/``utility.py``/``winmap.py``/``loss_triage.py``), and writes:

    <run-dir>/dominance/cells.json      — every (arm-pair x profile x scenario) cell
    <run-dir>/dominance/frontier.json   — the Pareto frontier + each arm's Point
    <run-dir>/dominance/LOSS_MAP.md     — per-loss-cell top-5 question triage
    <run-dir>/dominance/summary.md      — the scalarization, frontier, tallies, flags

Usage::

    uv run --project . python scripts/dominance/run_dominance.py --run-dir PATH
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # scripts/: self-import below

from dominance import loss_triage as LT
from dominance import pareto as PA
from dominance import profiles as P
from dominance import winmap as W
from dominance.utility import FORMULA
from life_agent.fairfight import records as REC

# --- loading -------------------------------------------------------------------------------


def _load_arm_vectors(path: Path) -> list[dict[str, Any]]:
    """Read + validate one ``vectors.jsonl`` (``records.from_json`` raises on a
    malformed/unknown-vocabulary row), returning JSON-safe dicts (``records.to_json``)
    — the shape ``utility``/``pareto``/``winmap``/``loss_triage`` all consume.
    """
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            vector = REC.from_json(json.loads(line))
            rows.append(REC.to_json(vector))
    return rows


def load_arms(run_dir: Path) -> dict[str, list[dict[str, Any]]]:
    """``{arm: [row, ...]}`` for every ``arms/<arm>/vectors.jsonl`` under ``run_dir``."""
    arms: dict[str, list[dict[str, Any]]] = {}
    for vectors_path in sorted(run_dir.glob("arms/*/vectors.jsonl")):
        arms[vectors_path.parent.name] = _load_arm_vectors(vectors_path)
    return arms


# --- summary.md ----------------------------------------------------------------------------


def _fmt_point(point: PA.Point, n_missing_cost: int) -> str:
    correct_rate, neg_cost, neg_latency, neg_attention = point
    return (
        f"correct_rate={correct_rate:.3f}, total_cost=${-neg_cost:.4f} "
        f"(missing_cost_rows={n_missing_cost}), mean_latency={-neg_latency:.3f}s, "
        f"attention={-neg_attention:.1f}"
    )


def _fmt_tally(tally: dict[str, Any]) -> str:
    if tally["n"] == 0:
        return "n=0"
    return (
        f"n={tally['n']} win={tally['win']} tie={tally['tie']} loss={tally['loss']} "
        f"weak_dominance={tally['weak_dominance']} strict_win={tally['strict_win']}"
    )


def build_summary_md(
    *,
    run_dir: Path,
    arms: dict[str, list[dict[str, Any]]],
    points: dict[str, PA.Point],
    n_missing_cost: dict[str, int],
    cost_unpriced: dict[str, bool],
    frontier_set: set[str],
    pair_tallies: dict[tuple[str, str], dict[str, Any]],
    region_tallies: dict[tuple[str, str], dict[str, Any]],
    region_names: set[str],
    zero_losses: bool,
    n_excluded_infra: dict[str, int],
    n_total: dict[str, int],
    pair_asymmetry: dict[tuple[str, str], list[str]],
) -> str:
    lines = [f"# dominance summary — {run_dir.name}", ""]

    lines += [
        "## Scalarization (declared, printed verbatim — see utility.py)", "",
        "    " + FORMULA, "",
    ]

    # Final-review CRITICAL-2: every number below (frontier points, win-map cells, loss
    # triage) is computed over the SCORED population only (records.scored — status="ok"
    # rows); name what was excluded so a reader never mistakes a small scored population
    # for a full one.
    lines += ["## Excluded rows (status != \"ok\" — infra failures, never scored)", ""]
    for arm in sorted(n_total):
        lines.append(
            f"- `{arm}`: {n_excluded_infra[arm]} excluded of {n_total[arm]} total "
            f"({n_total[arm] - n_excluded_infra[arm]} scored)")
    lines.append("")

    # PR-21 IMPORTANT-1: name any ordered arm pair whose comparison was restricted to the
    # common scored question set (an asymmetric infra failure) — the analysis proceeded
    # over the intersection instead of hard-aborting, but the asymmetry must stay loud.
    lines += ["## Asymmetric arm pairs (compared over the common scored question set)", ""]
    if pair_asymmetry:
        for (arm_a, arm_b), qids in sorted(pair_asymmetry.items()):
            lines.append(
                f"- `{arm_a}` vs `{arm_b}`: {len(qids)} question(s) excluded from the "
                f"comparison (not scored by both arms): {qids}")
    else:
        lines.append("- none — every arm pair shared one scored question set.")
    lines.append("")

    lines += ["## Pareto frontier (profile-independent)", "",
              "Axes (all oriented \"more is better\"): "
              "(correct_rate, -total_cost, -mean_latency, -attention).", "",
              # final-review IMPORTANT-5 item 2: name what attention counts per arm class,
              # since the axis is not uniformly measured (see run_fairfight.py's
              # `_gather_rounds` for the mapping this note summarises).
              "_Attention = asks_issued (an ask_clarify decision, every arm) + one more "
              "counter per arm class: in-process arms (inprocess/synthesis) add "
              "gather_tiers (one corroboration tier fired = one gather round); the "
              "competitor arm adds its own `search` tool-call count; the baseline "
              "(executor) arm has no observable gather-round count from the daemon's View, "
              "so its attention is asks_issued only — see `run_fairfight._gather_rounds`._",
              ""]
    for arm in sorted(points):
        tag = " **[frontier]**" if arm in frontier_set else ""
        unpriced = " _(cost wholly unpriced — treated as $0: unmeasured, not free)_" if (
            cost_unpriced.get(arm)) else ""
        lines.append(
            f"- `{arm}`{tag}: {_fmt_point(points[arm], n_missing_cost[arm])}{unpriced}")
    # PR-21 IMPORTANT-2: a frontier member whose cost axis is wholly unpriced sits at $0
    # by absence, not by measurement — name it inline so its frontier slot isn't read as
    # "free". (Frontier membership itself is the declared cost-as-0 modelling choice.)
    unpriced_frontier = sorted(a for a in frontier_set if cost_unpriced.get(a))
    if unpriced_frontier:
        lines.append("")
        lines.append(
            "_Cost caveat: frontier member(s) "
            f"{', '.join('`' + a + '`' for a in unpriced_frontier)} have a WHOLLY UNPRICED "
            "cost axis (every row cost_usd=None) — their total_cost is 0 because it was "
            "never measured, not because it is free._")
    lines.append("")

    lines += ["## Profile win map — per ordered arm pair", ""]
    for pair in sorted(pair_tallies):
        arm_a, arm_b = pair
        t = pair_tallies[pair]
        lines.append(f"### {arm_a} vs {arm_b}")
        lines.append("")
        lines.append(f"- overall: {_fmt_tally(t['overall'])}")
        lines.append(f"- measured: {_fmt_tally(t['measured'])}")
        lines.append(f"- modelled: {_fmt_tally(t['modelled'])}")
        region = region_tallies.get(pair)
        if region is not None:
            lines.append(
                f"- REALISTIC_REGION weak-dominance fraction (scenario=all, uniform over "
                f"{len(region_names)} qualifying profiles: {sorted(region_names)}): "
                f"{region['weak_dominance']} ({_fmt_tally(region)})"
            )
        lines.append("")

    if zero_losses:
        lines += ["## Loss triage", "", LT.ZERO_LOSS_FLAG, ""]
    else:
        lines += [
            "## Loss triage", "",
            "See `LOSS_MAP.md` for the per-cell top-5 question triage.", "",
        ]

    return "\n".join(lines) + "\n"


# --- the injectable core --------------------------------------------------------------------


def run(run_dir: Path) -> dict[str, Any]:
    """The analysis's core, thin-``main``-friendly: everything ``main()`` needs is one call."""
    arms_raw = load_arms(run_dir)
    if len(arms_raw) < 2:
        raise SystemExit(
            f"dominance analysis needs >=2 arms with arms/<arm>/vectors.jsonl under "
            f"{run_dir}, found {len(arms_raw)}: {sorted(arms_raw)}"
        )

    # Final-review CRITICAL-2: every downstream computation (Pareto points, win-map
    # cells, loss triage) runs over the SCORED population only — an infra-failed row's
    # bucket must never reach a rate, a welfare sum, a frontier point, or a loss cell.
    # Filtered ONCE here, at the package's one entry point, via records.py's canonical
    # `scored` — never re-implemented per consumer.
    n_total = {arm: len(rows) for arm, rows in arms_raw.items()}
    arms = {arm: REC.scored(rows) for arm, rows in arms_raw.items()}
    n_excluded_infra = {arm: n_total[arm] - len(arms[arm]) for arm in arms_raw}

    points, n_missing_cost, cost_unpriced = PA.build_points(arms)
    frontier_set = PA.frontier(points)

    profiles = W.all_profiles()
    cells = W.build_cells(arms, profiles)
    pair_tallies = W.pair_tally(cells)
    region_names = {name for name, p in profiles.items() if P.in_realistic_region(p)}
    region_tallies = W.region_dominance(cells, region_names)
    # PR-21 IMPORTANT-1: any ordered pair whose two arms' scored question sets differed was
    # intersected (never hard-aborted); name the excluded questions run-wide, not silently.
    pair_asym = W.pair_asymmetry(cells)

    loss_sections, zero_losses = LT.build_loss_report(cells, arms)

    out_dir = run_dir / "dominance"
    out_dir.mkdir(parents=True, exist_ok=True)

    cells_payload = {
        "n_excluded_infra": n_excluded_infra, "n_total": n_total,
        # top-level asymmetry report (keyed "arm_a->arm_b"): empty in the normal symmetric
        # case, populated when build_cells had to intersect a pair to its common set.
        "pair_asymmetry": {f"{a}->{b}": qids for (a, b), qids in sorted(pair_asym.items())},
        "cells": cells,
    }
    (out_dir / "cells.json").write_text(
        json.dumps(cells_payload, indent=2) + "\n", encoding="utf-8")

    # PR-21 IMPORTANT-2: the cost-unpriced caveat is INLINE in frontier.json (not only in
    # summary.md) — a frontier member whose cost axis is wholly unpriced sits at $0 by
    # absence, not by measurement.
    frontier_cost_unpriced = sorted(a for a in frontier_set if cost_unpriced.get(a))
    frontier_payload = {
        "frontier": sorted(frontier_set),
        "point_axes": ["correct_rate", "neg_total_cost", "neg_mean_latency", "neg_attention"],
        "points": {arm: list(pt) for arm, pt in points.items()},
        "n_missing_cost": n_missing_cost,
        "cost_unpriced": cost_unpriced,
        "frontier_cost_unpriced_caveat": frontier_cost_unpriced,
    }
    (out_dir / "frontier.json").write_text(
        json.dumps(frontier_payload, indent=2) + "\n", encoding="utf-8")

    (out_dir / "LOSS_MAP.md").write_text(
        LT.loss_map_md(loss_sections, zero_losses), encoding="utf-8")

    summary_md = build_summary_md(
        run_dir=run_dir, arms=arms, points=points, n_missing_cost=n_missing_cost,
        cost_unpriced=cost_unpriced, frontier_set=frontier_set, pair_tallies=pair_tallies,
        region_tallies=region_tallies, region_names=region_names, zero_losses=zero_losses,
        n_excluded_infra=n_excluded_infra, n_total=n_total, pair_asymmetry=pair_asym,
    )
    (out_dir / "summary.md").write_text(summary_md, encoding="utf-8")

    return {
        "run_dir": run_dir, "out_dir": out_dir, "arms": sorted(arms),
        "frontier": sorted(frontier_set), "n_cells": len(cells),
        "n_loss_cells": len(loss_sections), "zero_losses": zero_losses,
        "n_excluded_infra": n_excluded_infra, "pair_asymmetry": pair_asym,
    }


# --- CLI -------------------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, help="a finished fair-fight run directory")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    result = run(Path(args.run_dir))
    print(
        f"dominance analysis -> {result['out_dir']} "
        f"(arms={result['arms']}, frontier={result['frontier']}, "
        f"cells={result['n_cells']}, loss_cells={result['n_loss_cells']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
