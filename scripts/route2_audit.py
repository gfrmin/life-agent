#!/usr/bin/env python3
"""Second-stage router audit — the family classifier's confusion matrix (r21, C0).

Runs ``aggregate.route_aggregate`` over the three-way-labelled mixed set
(``$LIFE_AGENT_KB/eval/route-audit-family.yaml``: the route-audit set's 21 negatives
labelled ``aggregate`` / ``narrative``, positives byte-untouched). The C0 bar (r21
prereg, frozen): **zero narrative→aggregate false positives**; aggregate recall is
reported, not gated. Verdicts are cached under the live §18.9 key, so re-runs are free
and a gate run inherits them warm.

The first-stage instrument (``route_audit.py`` + ``route-audit.yaml``) is deliberately
untouched — C0's byte-identity claim on lookup admissions reads through it.

  uv run python scripts/route2_audit.py [--audit route-audit-family.yaml]
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from life_agent.core import aggregate as AGG
from life_agent.core import config as LCFG


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    kb = os.environ.get("LIFE_AGENT_KB")
    if not kb:
        print("LIFE_AGENT_KB unset", file=sys.stderr)
        return 2
    ap.add_argument("--audit", type=Path,
                    default=Path(kb) / "eval" / "route-audit-family.yaml")
    args = ap.parse_args(argv)

    items = yaml.safe_load(args.audit.read_text())["items"]
    from pkm.config import load_config as pkm_load_config
    root = pkm_load_config(LCFG.PKM_CONFIG).root_dir

    fp: list[str] = []       # narrative-labelled → aggregate verdict (the C0 bar)
    admitted: list[str] = []  # aggregate-labelled → aggregate verdict (recall)
    missed: list[str] = []    # aggregate-labelled → narrative verdict
    n_narr = n_agg = n_pos = 0
    for item in items:
        q = str(item["question"])
        label = str(item.get("family") or ("lookup" if item.get("lookup") else ""))
        if label not in ("aggregate", "narrative"):
            n_pos += 1
            continue  # stage-1 positives never reach the second stage in production
        r = AGG.route_aggregate(root, q)
        if label == "narrative":
            n_narr += 1
            if r is not None:
                fp.append(q)
        else:
            n_agg += 1
            (admitted if r is not None else missed).append(q)

    print(f"second-stage matrix: {n_narr} narrative / {n_agg} aggregate labelled "
          f"({n_pos} stage-1 positives skipped)")
    print(f"narrative->aggregate false positives: {len(fp)}"
          + ("".join(f"\n  FP: {q}" for q in fp)))
    print(f"aggregate recall: {len(admitted)}/{n_agg}"
          + ("".join(f"\n  missed: {q}" for q in missed)))
    if fp:
        print("\nC0 BAR FAILED — zero narrative->aggregate false positives required.")
        return 1
    print("\nC0 second-stage bar met (recall reported, not gated).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
