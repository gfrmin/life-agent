"""u_wrong_curve.py — the `u_wrong` sensitivity curve on one held-out run (r51b X7).

`u_wrong` is an identified latent, not part of the affine gauge (`GD-27`); the ruled regime
quotes the gate at the elicitation value and publishes both break-evens (`M-34`). This script
re-scores ONE run's held-out ticks at each point of a frozen grid — the commit policy
recomputed at that point's bar (`lattice_replay.commits_respond`, the engine's own exhaustion
rule), the A3 pairing rebuilt through the harness's own `question_acts`/`build_paired`, Δ by
the Bayesian bootstrap at that FIXED utility (the gate's `realised_utility` and Dirichlet
weights, `M-7`) — and reports per point the implied commit bar (`gate.break_even`), coverage
(the share of ticks the policy commits) and selective risk (the wrong rate among them): the
bounded-improvement reading `OPEN-QUESTIONS-utility.md` OQ-0' (c') asks for. **A sensitivity
deliverable, never a verdict** (`M-4`): nothing here re-reads a bar, and the ruled regime's
point is marked, not preferred.

  uv run --project . python scripts/membrane/u_wrong_curve.py --out $LIFE_AGENT_KB/eval/r51 \\
      --variant FULL --questions-v2 QUESTIONS.yaml --baseline-run RUN_DIR [--grid ...]
"""
from __future__ import annotations

import argparse
import json
import random
import statistics as st
import sys
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

sys.path.insert(0, "scripts")

import life_agent.core.gate as GATE
import membrane.lattice_replay as LR
import membrane.p3_gate as P3

GRID: tuple[float, ...] = (-1.0, -4.0, -5.131, -7.4285, -9.0, -12.0)
RULED_POINT = -9.0   # the elicitation-only value the gate scores at (`M-34`); marked, not preferred


def u_bar_at(base: Mapping[str, float], u_wrong: float) -> dict[str, float]:
    """The run's own pricing Ū with ONLY ``u_wrong`` replaced — every other latent as used."""
    return {**{k: float(v) for k, v in base.items()}, "u_wrong": float(u_wrong)}


def implied_bar(u_bar: Mapping[str, float]) -> float:
    """The commit bar the point implies — the gate's break-even, derived through
    `decide.u_assert` (`M-7`), which under the pinned gauge reads |u|/(1+|u|)."""
    return GATE.break_even(u_bar)


def effective_bar(u_bar: Mapping[str, float]) -> float | None:
    """Where the engine's restricted argmax actually flips to respond (the harness's one
    spelling, `p3_gate.commit_bar_for`): above the break-even whenever a cheap ``ask``
    outbids ``respond`` — the two are published side by side, never conflated."""
    return P3.commit_bar_for(u_bar)


def policy_at(rows: Sequence[P3.HeldoutTick], u_bar: Mapping[str, float]) -> list[P3.HeldoutTick]:
    """Recompute each tick's commit at this Ū — the engine's exhaustion rule, never a
    re-spelled threshold."""
    return [replace(r, respond=(r.p1 is not None and LR.commits_respond(u_bar, r.p1)))
            for r in rows]


def coverage_and_risk(rows: Sequence[P3.HeldoutTick]) -> dict[str, Any]:
    covered = [r for r in rows if r.respond]
    risk = (1.0 - st.mean(float(r.y) for r in covered)) if covered else None
    return {"n_ticks": len(rows), "n_covered": len(covered),
            "coverage": (len(covered) / len(rows)) if rows else None, "selective_risk": risk}


def delta_at_u(paired: Sequence[GATE.PairedOutcome], u_bar: Mapping[str, float], *,
               oracle_p: float, draws: int, seed: int,
               delta: float = GATE.MATERIALITY_DELTA) -> dict[str, Any]:
    """Δ at ONE fixed utility: the gate's per-row realised utilities and its Dirichlet
    bootstrap over rows, with P(U) collapsed to this point (the gate integrates over P(U);
    a curve holds U fixed by construction)."""
    included = GATE._included(list(paired))
    if not included:
        return {"p_delta_gt": 0.0, "delta_mean": 0.0, "delta_lo": 0.0, "delta_hi": 0.0,
                "n_included": 0, "materiality_delta": delta}
    u = dict(u_bar)
    d = [GATE.realised_utility(p.typed, u, oracle_p=oracle_p)
         - GATE.realised_utility(p.mono, u, oracle_p=oracle_p) for p in included]
    rng = random.Random(seed)
    deltas = sorted(sum(wi * di for wi, di in zip(GATE._dirichlet_ones(len(d), rng), d,
                                                  strict=True)) for _ in range(draws))
    return {"p_delta_gt": sum(1 for x in deltas if x > delta) / draws,
            "delta_mean": sum(deltas) / draws,
            "delta_lo": deltas[int(0.05 * draws)],
            "delta_hi": deltas[min(int(0.95 * draws), draws - 1)],
            "n_included": len(included), "materiality_delta": delta}


def curve_point(rows: Sequence[P3.HeldoutTick], u_bar: Mapping[str, float],
                h2q: Mapping[str, str], baseline_rows: Sequence[dict[str, Any]], *,
                oracle_p: float, draws: int, seed: int) -> dict[str, Any]:
    at = policy_at(rows, u_bar)
    acts = P3.question_acts(at)
    paired, only_m, only_b = P3.build_paired(acts, h2q, baseline_rows,
                                             verdicts=P3.verdicts_by_question(rows))
    point: dict[str, Any] = {
        "u_wrong": float(u_bar["u_wrong"]), "implied_bar": implied_bar(u_bar),
        "effective_bar": effective_bar(u_bar),
        **coverage_and_risk(at),
        "n_joined": len(paired), "n_membrane_only": len(only_m), "n_baseline_only": len(only_b),
        "marginal_commits": GATE.marginal_commits(paired).as_record(),
        "typed_acts": {h2q[h]: (a.action, a.correct) for h, a in acts.items() if h in h2q},
        **delta_at_u(paired, u_bar, oracle_p=oracle_p, draws=draws, seed=seed),
    }
    return point


def render(points: Sequence[Mapping[str, Any]], *, variant: str, base_u_wrong: float) -> str:
    f = lambda x, n=3: "n/a" if x is None else f"{x:.{n}f}"  # noqa: E731
    lines = [f"# `u_wrong` sensitivity curve — variant `{variant}`", "",
             "A sensitivity deliverable, **never a verdict** (`M-4`): the same held-out ticks "
             "re-scored at each grid point of the identified latent; the ruled regime's point "
             f"(`{RULED_POINT}`) and the run's own pricing point (`{base_u_wrong}`) are marked, "
             "not preferred.", "",
             "| u_wrong | implied bar | effective bar | coverage | selective risk | joined | "
             "marginal n / rate | P(Δ>δ) | Δ̄ [5%, 95%] |",
             "|---:|---:|---:|---:|---:|---:|---|---:|---|"]
    for p in points:
        mark = ((" ◆" if p["u_wrong"] == base_u_wrong else "")
                + (" ★" if p["u_wrong"] == RULED_POINT else ""))
        m = p["marginal_commits"]
        lines.append(f"| {p['u_wrong']}{mark} | {f(p['implied_bar'], 4)} | "
                     f"{f(p['effective_bar'], 3)} | {f(p['coverage'])} | "
                     f"{f(p['selective_risk'])} | {p['n_joined']} | {m['n']} / {f(m['rate'])} | "
                     f"{f(p['p_delta_gt'])} | {p['delta_mean']:+.3f} [{p['delta_lo']:+.3f}, "
                     f"{p['delta_hi']:+.3f}] |")
    lines += ["", "◆ the run's pricing point · ★ the ruled regime's point (`M-34`). Implied bar = "
              "the break-even; effective bar = where the engine's restricted argmax actually "
              "flips to respond (a cheap `ask` can hold it above the break-even). Coverage = the "
              "share of held-out ticks the policy commits at the effective bar; selective risk = "
              "the wrong rate among them; δ = the gate's frozen materiality."]
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, required=True, help="the p3_gate --out dir")
    parser.add_argument("--variant", default="FULL")
    parser.add_argument("--questions-v2", type=Path, required=True)
    parser.add_argument("--baseline-run", type=Path, required=True)
    parser.add_argument("--baseline-arm", default="baseline")
    parser.add_argument("--grid", default=",".join(str(g) for g in GRID))
    parser.add_argument("--draws", type=int, default=GATE.DEFAULT_N_DRAWS)
    parser.add_argument("--seed", type=int, default=GATE.DEFAULT_SEED)
    parser.add_argument("--oracle-p", type=float, default=None,
                        help="default: lookup._ORACLE_P, the harness's own")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    out: Path = args.out
    rows = P3.read_heldout_rows(out / f"heldout-{args.variant}.jsonl")
    meta = json.loads((out / f"a3_meta-{args.variant}.json").read_text(encoding="utf-8"))
    base = {str(k): float(v) for k, v in meta["regimes"]["pricing"]["u_bar"].items()}
    h2q = P3.hash_to_qid(P3._load_v2_questions(args.questions_v2))
    baseline_rows = P3._load_baseline_rows(args.baseline_run, args.baseline_arm)
    if args.oracle_p is None:
        import life_agent.core.lookup as LK

        oracle_p = float(LK._ORACLE_P)
    else:
        oracle_p = float(args.oracle_p)
    grid = [float(g) for g in str(args.grid).split(",") if g.strip()]
    points = [curve_point(rows, u_bar_at(base, g), h2q, baseline_rows, oracle_p=oracle_p,
                          draws=args.draws, seed=args.seed) for g in grid]
    record = {"variant": args.variant, "grid": grid, "base_u_bar": base, "ruled_point": RULED_POINT,
              "draws": args.draws, "seed": args.seed, "oracle_p": oracle_p, "n_ticks": len(rows),
              "points": points}
    (out / f"u_wrong_curve-{args.variant}.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    text = render(points, variant=args.variant, base_u_wrong=base["u_wrong"])
    (out / f"u_wrong_curve-{args.variant}.md").write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
