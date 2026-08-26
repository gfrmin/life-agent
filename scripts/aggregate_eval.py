#!/usr/bin/env python3
"""The aggregate set's C2 driver + the demand-led warm (r21 phase 2).

Two modes over ``$LIFE_AGENT_KB/eval/aggregate-questions.yaml``:

``--warm``
    The pre-registered demand-led warm: run the DEPLOYED retrieval per question
    (expand + rerank — the bridge lane's exact body), project the amounts, and run the
    named ``pkm derive`` remedies for every underived hit. Metered; aborts at the cap
    (``n_questions x k x p_derive`` — the r21 frozen formula; the computed dollar
    number is published in r21 before the priced run fires). Never a corpus sweep.

``--arm aggregate | --arm narrative``
    Drive each question through the priced lane (the bridge daemon must be up — the
    same surface the gate's typed arm reads) and grade: gradeable rows (a numeric
    gold) through the frozen Winkler rule (``gate.realised_aggregate``); gold-none
    honesty rows against their named expectations. Rows land as JSON for the r21
    report; the Δ_agg comparison is a DISCLOSED reading (gradeable N=11 < 15, the
    CP-A ruling).

  uv run python scripts/aggregate_eval.py --warm [--cap-usd X]
  uv run python scripts/aggregate_eval.py --arm aggregate --out rows.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from life_agent.core import config as LCFG
from life_agent.core import gate as GATE

_K = 20


def _questions(kb: Path) -> list[dict[str, Any]]:
    data = yaml.safe_load((kb / "eval" / "aggregate-questions.yaml").read_text())
    return list(data["questions"])


def _numeric(value: Any) -> float | None:
    import re
    m = re.search(r"-?\d[\d,]*(?:\.\d+)?", str(value or ""))
    return float(m.group(0).replace(",", "")) if m else None


def warm(kb: Path, cap_usd: float) -> int:
    """Retrieve per question with the deployed lane's body, derive the underived."""
    import duckdb

    from life_agent.core import aggregate as AGG
    from life_agent.core import expansion as EXP
    from life_agent.core import rerank as RR
    from life_agent.core import retrieval as RET
    from pkm.config import load_config as pkm_load_config
    from pkm.derive import derive as pkm_derive

    cfg = pkm_load_config(LCFG.PKM_CONFIG)
    root = cfg.root_dir
    conn = duckdb.connect(str(root / "catalogue.duckdb"), read_only=True)
    spent = 0.0
    derived = failed = 0
    try:
        for q in _questions(kb):
            question = str(q["question"])
            terms = EXP.expand_terms(question, root=root)
            pool = RET.retrieve_set(conn, RET.build_query(question, terms),
                                    RR.RERANK_POOL)
            hits = RR.rerank_hits(question, pool, _K)
            keys = list(dict.fromkeys(h["artifact_cache_key"] for h in hits))
            projections = AGG.project_amounts(conn, root, keys,
                                              caller="aggregate_eval.warm")
            remedies = [(p.artifact_cache_key, p.extractor)
                        for p in projections if p.state == "underived"]
            conn.close()  # derive writes; a reader and writer cannot coexist
            for key, extractor in remedies:
                if spent >= cap_usd:
                    print(f"CAP REACHED (${spent:.2f} >= ${cap_usd:.2f}) — aborting "
                          f"with {derived} derived, {failed} failed")
                    return 1
                decl = f"extract_amounts_{extractor}"
                try:
                    result = pkm_derive(root, cfg, decl, input_cache_key=key,
                                        caller="aggregate_eval.warm")
                    cost = float(
                        (result.producer_metadata or {}).get("cost_usd", 0.0) or 0.0
                    ) if hasattr(result, "producer_metadata") else 0.0
                    spent += cost
                    derived += 1
                    print(f"derived {decl} {key[:12]}… (${cost:.4f})")
                except Exception as e:
                    failed += 1
                    print(f"derive failed {decl} {key[:12]}…: {e}")
            conn = duckdb.connect(str(root / "catalogue.duckdb"), read_only=True)
    finally:
        conn.close()
    print(f"warm complete: {derived} derived, {failed} failed, ${spent:.2f} spent "
          f"(cap ${cap_usd:.2f})")
    return 0


def drive_arm(kb: Path, arm: str, out: Path | None) -> int:
    """Drive each question through the priced lane and grade per the frozen rule."""
    import urllib.request

    bridge = os.environ.get("LIFE_AGENT_BRIDGE", "http://127.0.0.1:8377")

    def post(url: str, payload: dict) -> Any:
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(), method="POST",
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=600) as r:
            return json.loads(r.read().decode())

    rows: list[dict[str, Any]] = []
    for q in _questions(kb):
        question, qid = str(q["question"]), str(q["id"])
        view: dict[str, Any]
        if arm == "aggregate":
            route = post(f"{bridge}/route", {"question": question})
            if route:
                view = {"action": "lookup-admitted", "asserted": [],
                        "rendered": "", "aggregate": {}}
            else:
                fam = post(f"{bridge}/route_family", {"question": question})
                if fam.get("family") == "aggregate":
                    view = post(f"{bridge}/aggregate",
                                {"question": question, "k": _K})
                else:
                    view = {"action": "narrative-declined", "asserted": [],
                            "rendered": "", "aggregate": {}}
        else:
            nv = post(f"{bridge}/narrative", {"question": question, "k": _K})
            view = {"action": nv["action"], "asserted": nv["asserted"],
                    "rendered": nv.get("rendered", ""), "aggregate": {}}

        gv = _numeric(q.get("gold")) if q.get("gold") else None
        row: dict[str, Any] = {"id": qid, "arm": arm, "action": view.get("action"),
                               "gold_level": q.get("gold_level"),
                               "gold_numeric": gv}
        totals = (view.get("aggregate") or {}).get("totals") or []
        if gv is not None and totals:
            t = totals[0]
            x, excludes = GATE.realised_aggregate(float(t["lo"]), float(t["hi"]), gv)
            row.update(x=x, excludes_gold=excludes,
                       interval=[t["lo"], t["hi"]], point=t["point"])
        elif gv is not None:
            asserted = [str(a) for a in view.get("asserted") or []]
            row["contains_gold"] = GATE.realised_report(
                asserted, str(q.get("gold")), list(q.get("gold_variants") or []))
        row["rendered_head"] = str(view.get("rendered") or "")[:400]
        rows.append(row)
        print(f"{qid}: {row.get('action')} "
              f"x={row.get('x')} excludes={row.get('excludes_gold')}")

    wrong_class = [r["id"] for r in rows if r.get("excludes_gold")]
    print(f"\nnew-wrong-class commits (interval excludes gold): {len(wrong_class)}"
          + "".join(f"\n  {i}" for i in wrong_class))
    if out:
        out.write_text(json.dumps(rows, indent=1))
        print(f"rows -> {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--warm", action="store_true")
    ap.add_argument("--cap-usd", type=float, default=None)
    ap.add_argument("--arm", choices=["aggregate", "narrative"])
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    kb = Path(os.environ["LIFE_AGENT_KB"])
    if args.warm:
        n = len(_questions(kb))
        from life_agent.core import pricing as PRC
        p_derive = PRC.EXTRACT_AMOUNTS_USD  # the ONE price table (M4) — no fallback
        cap = args.cap_usd if args.cap_usd is not None else n * _K * p_derive
        print(f"warm cap: {n} questions x {_K} x ${p_derive} = ${cap:.2f}")
        return warm(kb, cap)
    if args.arm:
        return drive_arm(kb, args.arm, args.out)
    ap.error("one of --warm / --arm required")


if __name__ == "__main__":
    raise SystemExit(main())
