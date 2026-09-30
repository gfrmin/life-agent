#!/usr/bin/env python3
"""fit_route_row — measure the route row: what attempting a question is worth.

Two measurements feed :mod:`life_agent.core.route_row`, written to
``$LIFE_AGENT_KB/calibration/route_row.json`` (the bridge prices the route stage from it at
boot). Prints aggregates only, never a question or a value.

* **q per verdict.** The labelled route audit (``$LIFE_AGENT_KB/eval/route-audit.yaml``: each
  item a question, whether it is a lookup, its source) is run through the router
  (:func:`life_agent.core.lookup.route_question`, cached). Counting label x verdict gives
  ``q@accept`` = P(lookup | the router accepts) and ``q@reject`` = P(lookup | the router
  rejects), each a Beta(1, 1) posterior mean.
* **r, w and the first pass's price.** The pinned archives of ``eval/sets.yaml`` (the sets
  that live under the KB; the synthetic repo-resident set is left out) record each attempted
  question's outcome: ``typed.correct`` True / False / None is right / wrong / declined, and
  the rates are Dirichlet(2, 2, 2) posterior means. A row the router declined recorded no
  attempt and is not counted: its signature is a ``miss`` that applied nothing and metered
  $0 (a question that was retrieved for cannot meter nothing on a cold run). The price is the
  mean of ``metered_usd - cost_usd`` over the attempted rows that applied no probe and were
  billed (metered above $0): a cache-served pass metered nothing but is not free, and a row
  that applied a probe also metered that probe's excess over the menu.

    uv run python scripts/fit_route_row.py [--root DIR]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval import score as SCORE
from life_agent.core import config as CFG
from life_agent.core import lookup as LK
from life_agent.core import pricing as PRC
from life_agent.core import route_row as RR


def audit_counts(items: list[dict], root: Path) -> tuple[Counter, Counter, float]:
    """``(label x verdict counts, kind counts of the rejections, USD spent)`` from running
    the router over every audit item."""
    client = LK._client()
    meter: list[float] = []
    cells: Counter = Counter()
    kinds: Counter = Counter()
    for it in items:
        route = LK.route_question(root, str(it["question"]), client=client, meter=meter)
        cells[(bool(it["lookup"]), route.lookup)] += 1
        if not route.lookup:
            kinds[route.kind] += 1
    return cells, kinds, sum(meter)


def attempted(typed: dict) -> bool:
    """Whether a recorded row is an attempt: a row the router declined (a ``miss`` that
    applied nothing and metered $0) is not."""
    return not (typed["withheld"] == "miss" and not typed["applied"]
                and float(typed["metered_usd"]) == 0.0)


def outcome(typed: dict) -> str:
    return {True: "right", False: "wrong", None: "declined"}[typed["correct"]]


def archive_rows(kb: Path) -> tuple[list[dict], dict[str, int], str]:
    """The ``typed`` arm of every non-censored row of the KB-resident pinned archives, the
    rows per set, and a digest of the bytes read."""
    rows: list[dict] = []
    per_set: dict[str, int] = {}
    h = hashlib.sha256()
    for name, spec in SCORE.load_sets().items():
        if spec["kind"] not in ("paired", "typed") or spec.get("root") == "repo":
            continue
        root, why = SCORE.set_root(spec, kb)
        f = root / spec["path"] if root is not None else None
        if f is None or not f.is_file():
            print(f"set {name}: not read ({why or 'file absent'})")
            continue
        data = f.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != spec["sha256"]:
            raise SystemExit(f"{name}: sha256 {digest} != pinned {spec['sha256']}")
        h.update(data)
        got = [json.loads(ln)["typed"] for ln in data.decode("utf-8").splitlines()
               if ln.strip() and not json.loads(ln).get("censored")]
        per_set[name] = len(got)
        rows += got
    return rows, per_set, h.hexdigest()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--audit", default=str(CFG.KB / "eval/route-audit.yaml"))
    ap.add_argument("--root", default=str(CFG.KB / "calibration/route-audit-cache"),
                    help="the derivation cache the router's verdicts are recorded under")
    ap.add_argument("--out", default=str(CFG.ROUTE_ROW))
    a = ap.parse_args(argv)

    root = Path(a.root)
    (root / "cache").mkdir(parents=True, exist_ok=True)
    (root / "logs").mkdir(parents=True, exist_ok=True)
    audit_bytes = Path(a.audit).read_bytes()
    items = yaml.safe_load(audit_bytes)["items"]
    cells, kinds, usd = audit_counts(items, root)
    tp, fn = cells[(True, True)], cells[(True, False)]
    fp, tn = cells[(False, True)], cells[(False, False)]
    print(f"audit {len(items)} items, router spend ${usd:.4f} (cache-miss calls only)")
    print(f"  label lookup:     accepted {tp}  rejected {fn}")
    print(f"  label not lookup: accepted {fp}  rejected {tn}")
    print(f"  kinds of the {fn + tn} rejections: {dict(kinds)}")
    q_accept = RR.beta_mean(tp, tp + fp)
    q_reject = RR.beta_mean(fn, fn + tn)
    print(f"q@accept {q_accept:.4f} (Beta(1,1) mean, {tp}/{tp + fp})   "
          f"q@reject {q_reject:.4f} ({fn}/{fn + tn})")

    rows, per_set, digest = archive_rows(CFG.KB)
    made = [r for r in rows if attempted(r)]
    counts = Counter(outcome(r) for r in made)
    rates = RR.dirichlet_means({o: counts[o] for o in ("right", "wrong", "declined")})
    print(f"archives {per_set}: {len(rows)} rows, {len(rows) - len(made)} not attempted "
          f"(router declined), {len(made)} attempts {dict(counts)}")
    print(f"route_right {rates['right']:.4f}  route_wrong {rates['wrong']:.4f} "
          f"(Dirichlet(2,2,2) means)  route_wrong_other = route_wrong (assumed)")

    base = [float(r["metered_usd"]) - float(r["cost_usd"]) for r in made
            if not r["applied"] and float(r["metered_usd"]) > 0.0]
    if not base:
        raise SystemExit("no billed first pass in the archives: nothing to price")
    price = statistics.fmean(base)
    print(f"first pass: mean ${price:.4f}, median ${statistics.median(base):.4f}, n {len(base)} "
          f"(billed rows that applied no probe); declared in core/pricing.py: "
          f"${PRC.FIRST_PASS_USD:.4f}")

    Path(a.out).write_text(json.dumps({
        "format_version": 1,
        "row": RR.as_u_bar(q_accept, q_reject, rates["right"], rates["wrong"]),
        "n": {"audit": len(items), "accepted": tp + fp, "rejected": fn + tn,
              "lookups_accepted": tp, "lookups_rejected": fn, "attempts": len(made),
              **dict(counts), "first_pass_rows": len(base)},
        "first_pass_usd": price,
        "audit_sha256": hashlib.sha256(audit_bytes).hexdigest(),
        "archives_sha256": digest,
        "prior": "q: Beta(1,1) mean per verdict; r, w: Dirichlet(2,2,2) mean; "
                 "route_wrong_other assumed = route_wrong"},
        indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
