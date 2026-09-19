#!/usr/bin/env python3
"""Score the ROUTER arm on archived gate artifacts — arithmetic only, no inference.

The router answers with the typed arm where the typed arm asserted, and hands every
withheld question to the oracle. Both halves already exist in any archived paired file
(`typed` and `mono` on the same row), so the router's contingency is a pure
recombination: no model call, no API spend, no re-grading. If the routing thesis is
right, this prints a row that delivers more correct answers than EITHER arm at a
fraction of the oracle's spend, and it prints it from data recorded weeks ago.

This tool deliberately reports COUNTS and DOLLARS, not Δ. A Δ would price the router
under the same gauge that (see `life_agent.core.router`) makes escalation lose to
silence by construction; the counts are what a reader can check without first accepting
u_wrong. The gauge diagnostic is printed alongside so the two are never confused.

Usage:
  uv run python scripts/route_arm.py --paired <paired.jsonl> [--oracle-cost 0.3751]
      [--json OUT]

`--paired` takes the archived paired-rows file a gate run writes (the same format
`scripts/gate_splice.py --typed-from` reads).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import life_agent.core.gate as GATE
import life_agent.core.router as ROUTER

# Deliberately NOT importing scripts.gate_splice: its archive reader is three lines, but
# reaching it drags in run_eval and the whole instrument stack, so a read-only tool would
# need the full eval environment to print a table. Duplicating the three lines is the
# smaller sin; if a third caller appears, lift the reader into life_agent.core.gate
# instead of widening this import (DR-ROUTE-3).


def _resp(arm: dict) -> GATE.RealisedResponse:
    return GATE.RealisedResponse(
        action=str(arm["action"]), correct=arm.get("correct"),
        cost_usd=float(arm.get("cost_usd") or 0.0), withheld=arm.get("withheld"))


def paired_rows(path: Path) -> list[GATE.PairedOutcome]:
    """Archived paired-rows JSONL -> PairedOutcome, keeping each row's recorded cost."""
    out = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        r = json.loads(ln)
        out.append(GATE.PairedOutcome(
            question_id=str(r["question_id"]), answerable=bool(r["answerable"]),
            typed=_resp(r["typed"]), mono=_resp(r["mono"])))
    return sorted(out, key=lambda p: p.question_id)


def _line(tag: str, s: ROUTER.RouterSummary) -> str:
    return (f"  {tag:<9} correct {s.correct:>3}  wrong {s.wrong:>3}  withheld "
            f"{s.withheld:>3}  delivered {s.delivered:>3}  precision {s.precision:.3f}"
            f"  ${s.total_cost:>7.2f}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--paired", required=True, type=Path)
    ap.add_argument("--oracle-cost", type=float, default=None,
                    help="oracle $/q for the gauge diagnostic; default = the mono arm's "
                         "own measured mean from this archive")
    ap.add_argument("--json", type=Path, default=None)
    ap.add_argument("--u-wrong", type=float, default=-8.9993,
                    help="gauge diagnostic only; default = the r28 production mean")
    ap.add_argument("--lambda-usd", type=float, default=1.3311,
                    help="gauge diagnostic only; default = the r28 production mean")
    a = ap.parse_args(argv)

    rows = paired_rows(a.paired)
    live = [r for r in rows if not r.censored()]
    censored = len(rows) - len(live)

    typed = ROUTER.summarise([r.typed for r in live])
    oracle = ROUTER.summarise([r.mono for r in live])
    router = ROUTER.summarise([ROUTER.route(r) for r in live])

    print(f"\n{a.paired}  ({len(live)} rows folded, {censored} censored)\n")
    print(_line("typed", typed))
    print(_line("oracle", oracle))
    print(_line("router", router))

    if oracle.total_cost > 0:
        print(f"\n  router spend = {100 * router.total_cost / oracle.total_cost:.0f}% "
              f"of oracle;  answers delivered {router.delivered} vs {oracle.delivered}")

    # --- the gauge diagnostic: is escalation even rational under the live posterior?
    oracle_cost = a.oracle_cost if a.oracle_cost is not None else oracle.mean_cost
    oracle_p = oracle.precision
    u_bar = {"u_correct": 1.0, "u_abstain": 0.0, "u_wrong": a.u_wrong,
             "lambda_usd": a.lambda_usd}

    payload = {
        "paired": str(a.paired), "n_folded": len(live), "n_censored": censored,
        "arms": {t: vars(s) for t, s in
                 (("typed", typed), ("oracle", oracle), ("router", router))},
        "oracle_p": oracle_p, "oracle_cost": oracle_cost,
    }

    if u_bar is not None:
        eu = ROUTER.escalate_eu(u_bar, oracle_p=oracle_p, oracle_cost=oracle_cost)
        be_u = ROUTER.breakeven_u_wrong(oracle_p=oracle_p,
                                        lambda_usd=u_bar["lambda_usd"],
                                        oracle_cost=oracle_cost)
        be_l = ROUTER.breakeven_lambda_usd(oracle_p=oracle_p,
                                           u_wrong=u_bar["u_wrong"],
                                           oracle_cost=oracle_cost)
        print(f"\n  gauge: u_wrong {u_bar['u_wrong']:+.4f}  lambda_usd "
              f"{u_bar['lambda_usd']:.4f}  oracle p {oracle_p:.4f} @ ${oracle_cost:.4f}")
        print(f"  EU(escalate) = {eu:+.4f}   EU(abstain) = 0")
        print(f"  break-even u_wrong    {be_u:+.4f}  (in use {u_bar['u_wrong']:+.4f})")
        print(f"  break-even lambda_usd {be_l:.4f}  (in use {u_bar['lambda_usd']:.4f})")
        verdict = ("ESCALATION IS IRRATIONAL under this gauge — the router above is a "
                   "counterfactual the deployed engine would never choose"
                   if eu < u_bar["u_abstain"] else
                   "escalation clears abstain; the engine would route")
        print(f"\n  -> {verdict}\n")
        payload["gauge"] = {"u_wrong": u_bar["u_wrong"],
                            "lambda_usd": u_bar["lambda_usd"], "eu_escalate": eu,
                            "breakeven_u_wrong": be_u, "breakeven_lambda_usd": be_l,
                            "escalation_rational": eu >= u_bar["u_abstain"]}

    if a.json:
        a.json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                          encoding="utf-8")
        print(f"  wrote {a.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
