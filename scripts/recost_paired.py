#!/usr/bin/env python3
"""recost_paired — put an archived typed arm on the menu's price list.

A paired archive priced its typed arm at what its calls metered, and a warm run meters $0
for every derivation a cache served — so two runs of one policy price differently, and a
replayed escalation reads as free. The board prices the act, not the cache
(``pricing.list_price``): each row's typed ``cost_usd`` becomes the declared price of the
probes that run applied, the metered figure moves to ``metered_usd``, and the sequence
rides as ``applied`` — the fields ``run_eval`` writes on every new archive.

An archived run's applied sequence is read from its A-loop fixtures (one
``*-aloop-<question_id>.json`` per question: the wire the run recorded), as the ordered
union of ``applied_probes`` over its ``/decide`` payloads. Every row must have a fixture or
nothing is written. The outside arm is untouched. Prints counts only.

    uv run python scripts/recost_paired.py $LIFE_AGENT_KB/eval/gate-outside-option/<paired>.jsonl \\
        --fixtures $LIFE_AGENT_KB/eval/collapse-fixtures/m5-base
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from life_agent.core import config as CFG
from life_agent.core import pricing as PRC


def applied_from_fixture(fixture: Mapping[str, Any]) -> list[str]:
    """The probes a recorded run applied, in first-applied order: the union of the
    ``applied_probes`` its ``/decide`` payloads carried."""
    out: list[str] = []
    for w in fixture.get("wire") or []:
        req = w.get("request") or {}
        if w.get("seam") != "http" or not str(req.get("url", "")).endswith("/decide"):
            continue
        for p in (req.get("payload") or {}).get("applied_probes") or []:
            if str(p) not in out:
                out.append(str(p))
    return out


def recost(rows: Sequence[Mapping[str, Any]],
           applied_by_id: Mapping[str, Sequence[str]]) -> list[dict[str, Any]]:
    """The rows with the typed arm priced at the menu list. A row without a recorded
    sequence refuses the whole file (every row or none)."""
    missing = [str(r["question_id"]) for r in rows
               if str(r["question_id"]) not in applied_by_id]
    if missing:
        raise KeyError(f"{len(missing)} row(s) have no recorded sequence")
    out: list[dict[str, Any]] = []
    for r in rows:
        applied = [str(p) for p in applied_by_id[str(r["question_id"])]]
        typed = dict(r["typed"])
        typed.update({"metered_usd": float(typed.get("cost_usd") or 0.0),
                      "cost_usd": PRC.list_price(applied), "applied": applied})
        out.append({**r, "typed": typed})
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paired", help="the paired archive to re-cost")
    ap.add_argument("--fixtures", required=True,
                    help="directory holding the run's *-aloop-<question_id>.json fixtures")
    ap.add_argument("--out", default=None, help="default: <paired stem>-priced.jsonl")
    a = ap.parse_args(argv)
    src = Path(a.paired)
    out = Path(a.out) if a.out else src.with_name(f"{src.stem}-priced.jsonl")
    if out.exists():
        print(f"refusing to overwrite {out.name}: an archive's bytes must not move",
              file=sys.stderr)
        return 2
    rows = [json.loads(ln) for ln in src.read_text(encoding="utf-8").splitlines()
            if ln.strip()]
    applied_by_id = {
        f.stem.rsplit("-aloop-", 1)[1]:
            applied_from_fixture(json.loads(f.read_text(encoding="utf-8")))
        for f in Path(a.fixtures).glob("*-aloop-*.json")}
    try:
        priced = recost(rows, applied_by_id)
    except KeyError as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 2
    out.write_text("".join(json.dumps(r) + "\n" for r in priced), encoding="utf-8")
    n_delib = sum("deliberate" in r["typed"]["applied"] for r in priced)
    listed = sum(float(r["typed"]["cost_usd"]) for r in priced)
    metered = sum(float(r["typed"]["metered_usd"]) for r in priced)
    where = (f"$LIFE_AGENT_KB/{out.relative_to(CFG.KB)}" if out.is_relative_to(CFG.KB)
             else str(out))
    print(f"{len(priced)} rows · deliberate applied on {n_delib} · at the menu's prices "
          f"${listed:.2f} (metered ${metered:.2f}) → {where} "
          f"(sha256 {hashlib.sha256(out.read_bytes()).hexdigest()})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
