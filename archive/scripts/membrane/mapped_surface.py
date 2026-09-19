#!/usr/bin/env python3
"""r46 leg A — read the MAPPED surface: what an enactment would have been.

    uv run python scripts/membrane/mapped_surface.py

The engine's raw affordance is a constant on this stream — every one of the 6 628 rows
carrying an `action` records `gather`, across both engine arms and all four row kinds — so
a §18 bar reading it compares two constants. The one surface that can vary is
`coarse.map_action`'s, and between M5's deletion of the live lane (`4e5debd`) and r46 it had
no writer at all.

This instrument reads it over the pinned corpus: the **605 `/decide` request/reply exchanges
across the 314 m5-base fixtures** — exactly the `(payload, dec)` pair the live seam forwards
to `submit_decide` through `/decide-support`. Criteria and consequence branches are frozen in
`docs/unification/reports/r46-readable-surface-preregistration.md` (amendment 1 corrects the
population; the criteria are untouched).

Everything load-bearing is IMPORTED, never re-implemented (`M-7`):

* the mapping is `coarse.map_action` itself, called with the real payload and daemon view;
* the agreement predicate is the rule's OWN behaviour — it returns `dec` itself on agreement
  and a fresh dict on every other branch, so `mapped is dec` IS the predicate. Re-deriving it
  from `REAL_TO_MEMBRANE` would be the re-implemented constant `M-7` names;
* the affordance vocabulary is `world.AFFORDANCES`.

What the corpus does not record is declared, never smuggled (amendment 1): the engine's own
`action` is supplied as the measured constant `gather` — and the surface is ALSO reported at
all four affordances so the dependence is visible — while `readouts["p1"]` is load-bearing on
exactly one branch (`_gather`'s exhausted fallback), whose size is published and whose p1 is
swept over the range the shadow ledger actually recorded.
"""
from __future__ import annotations

import argparse
import collections
import json
import statistics
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from life_agent.core import config as CFG
from life_agent.membrane import coarse as CO
from life_agent.membrane import world as W

#: The deployed rule and the deployed vocabulary, bound not copied.
map_action = CO.map_action
AFFORDANCES = [name for name, _ in W.AFFORDANCES]

#: The engine's measured affordance. A SUBSTITUTION, named as one: licensed by the census
#: (6 628 / 6 628 rows), not by assumption, and reported alongside all four alternatives.
MEASURED_ACTION = "gather"


def decide_exchanges(fixtures: Path) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    """Every recorded `/decide` request/reply pair, in fixture order."""
    out: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    for path in sorted(fixtures.glob("*.json")):
        if path.name == "manifest.json":
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        for ex in doc.get("wire") or []:
            req = ex.get("request")
            if not isinstance(req, dict) or req.get("url") != "/decide":
                continue
            payload, dec = req.get("payload"), ex.get("response")
            if isinstance(payload, dict) and isinstance(dec, dict):
                out.append((str(doc.get("fixture_id")), payload, dec))
    return out


def recorded_p1_range(ledger: Path) -> list[tuple[str, float]]:
    """min / median / max of the p1 the shadow ledger actually recorded. The exhausted
    branch is the only place `map_action` reads p1, so this is swept rather than invented."""
    p1s = []
    if ledger.exists():
        for line in ledger.read_text(encoding="utf-8").splitlines():
            if not line:
                continue
            row = json.loads(line)
            value = (row.get("readouts") or {}).get("p1")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                p1s.append(float(value))
    if not p1s:
        return []
    return [("min", min(p1s)), ("median", statistics.median(p1s)), ("max", max(p1s))]


def read(exchanges: list[tuple[str, dict[str, Any], dict[str, Any]]],
         action: str, p1: float) -> dict[str, Any]:
    """One pass of the deployed rule over the whole population."""
    effectors: collections.Counter[Any] = collections.Counter()
    degraded: collections.Counter[Any] = collections.Counter()
    probes: collections.Counter[Any] = collections.Counter()
    echoes = overrides = 0
    differs_and_echoes = differs_and_contributes = 0
    errors = 0
    for _fid, payload, dec in exchanges:
        try:
            mapped, degradation = map_action(payload, dec, action, {"p1": p1})
        except Exception:
            errors += 1
            continue
        echo = mapped is dec
        effectors[mapped.get("effector")] += 1
        degraded[degradation] += 1
        probes[mapped.get("probe")] += 1
        echoes += echo
        overrides += not echo
        if mapped.get("effector") != dec.get("effector"):
            differs_and_echoes += echo
            differs_and_contributes += not echo
    total = len(exchanges)
    return {
        "action": action, "p1": p1, "n": total, "errors": errors,
        "effectors": dict(effectors), "degraded": dict(degraded),
        "distinct_effectors": len([k for k in effectors if effectors[k]]),
        "echoes": echoes, "overrides": overrides,
        "echo_fraction": (echoes / total) if total else 0.0,
        "n_probes_selected": sum(v for k, v in probes.items() if k),
        "differs_from_daemon": differs_and_echoes + differs_and_contributes,
        "differs_and_contributes": differs_and_contributes,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--checkpoint", default="m5-base")
    ap.add_argument("--fixtures", default=None)
    ap.add_argument("--ledger", default=None)
    args = ap.parse_args()

    fixtures = Path(args.fixtures) if args.fixtures else (
        CFG.KB / "eval" / "collapse-fixtures" / args.checkpoint)
    ledger = Path(args.ledger) if args.ledger else (CFG.KB / "membrane" / "shadow.jsonl")

    exchanges = decide_exchanges(fixtures)
    if not exchanges:  # S4: the universe clause — an empty read is a FAIL, not a zero
        print(f"FAIL (S4): no /decide exchanges under {fixtures}")
        return 1
    daemon = collections.Counter(dec.get("effector") for _f, _p, dec in exchanges)
    print(f"population: {len(exchanges)} /decide exchanges over "
          f"{len({f for f, _p, _d in exchanges})} fixtures under {fixtures.name}")
    print(f"recorded daemon effector: {dict(daemon)}\n")

    p1_range = recorded_p1_range(ledger)
    if not p1_range:
        print(f"FAIL (S4): no recorded p1 in {ledger}")
        return 1
    print(f"recorded p1 range (shadow ledger): "
          f"{ {k: round(v, 4) for k, v in p1_range} }\n")

    print("=== the measured affordance, swept over the recorded p1 range ===")
    for label, p1 in p1_range:
        r = read(exchanges, MEASURED_ACTION, p1)
        print(f"  action={r['action']:<8} p1={p1:.4f} ({label:<6}) "
              f"effectors={r['effectors']} degraded={r['degraded']}")
        print(f"    distinct={r['distinct_effectors']} echo={r['echoes']}/{r['n']} "
              f"({r['echo_fraction']:.3f}) probes_selected={r['n_probes_selected']} "
              f"differs_from_daemon={r['differs_from_daemon']} "
              f"of which engine-contributed={r['differs_and_contributes']} "
              f"errors={r['errors']}")

    print("\n=== all four affordances (the substitution's dependence, made visible) ===")
    median_p1 = dict(p1_range)["median"]
    for action in AFFORDANCES:
        r = read(exchanges, action, median_p1)
        print(f"  action={action:<8} distinct={r['distinct_effectors']} "
              f"echo={r['echo_fraction']:.3f} effectors={r['effectors']} "
              f"degraded={r['degraded']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
