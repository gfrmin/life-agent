#!/usr/bin/env python3
"""The aggregate set's demand-led warm (r21 phase 2, r30b as amended).

One mode over ``$LIFE_AGENT_KB/eval/aggregate-questions.yaml``:

``--warm``
    The pre-registered demand-led warm: run the DEPLOYED retrieval per question
    (expand + rerank — the bridge lane's exact body), project the amounts, and run the
    named ``pkm derive`` remedies for every underived hit. Metered; aborts at the cap
    (``n_questions x k x p_derive`` — the r21 frozen formula; the computed dollar
    number is published before any priced run fires). Never a corpus sweep.

  uv run python scripts/aggregate_eval.py --warm [--cap-usd X]

**``--arm`` was DELETED at r30b.** It drove the questions through ``/route_family`` and
``/aggregate`` — endpoints K1 removed when the aggregate FAMILY died
(``docs/unification/reports/r22-k1-family-deletion.md``), so it could only 404. Deleting
it is not a loss of reach: r31 drives this same question set through ``run_eval``'s gate
machinery, on the one decide surface, where the interval claim r30b prices is ranked
inside the argmax instead of composed by a family outside it.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from life_agent.core import answer_shape as AS
from life_agent.core import config as LCFG

_K = 20


def _questions(kb: Path) -> list[dict[str, Any]]:
    data = yaml.safe_load((kb / "eval" / "aggregate-questions.yaml").read_text())
    return list(data["questions"])


# r30b (C7): ONE numeric parser, decision-side and grading-side — bound, never re-typed.
_numeric = AS.numeric_value


def warm(kb: Path, cap_usd: float) -> int:
    """Retrieve per question with the deployed lane's body, derive the underived."""
    import duckdb

    import life_agent.core.aggregate as AGG
    import life_agent.core.expansion as EXP
    import life_agent.core.rerank as RR
    import life_agent.core.retrieval as RET
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
                    # DeriveResult carries no realised cost (that lands in the §18.11
                    # demand log) — the meter charges the PLANNING price per cache-miss
                    # node, the cap formula's own denomination, so the cap binds by
                    # construction; realised spend is published from the demand log.
                    from life_agent.core.pricing import EXTRACT_AMOUNTS_USD
                    misses = sum(1 for n in result.nodes if not n.hit)
                    spent += misses * EXTRACT_AMOUNTS_USD
                    derived += 1
                    print(f"derived {decl} {key[:12]}… "
                          f"({misses} miss node(s), meter ${spent:.2f})")
                except Exception as e:
                    failed += 1
                    print(f"derive failed {decl} {key[:12]}…: {e}")
            conn = duckdb.connect(str(root / "catalogue.duckdb"), read_only=True)
    finally:
        conn.close()
    print(f"warm complete: {derived} derived, {failed} failed, metered ${spent:.2f} "
          f"at the planning price (cap ${cap_usd:.2f}); realised spend is in the "
          f"§18.11 demand log under caller=aggregate_eval.warm")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--warm", action="store_true")
    ap.add_argument("--cap-usd", type=float, default=None)
    args = ap.parse_args(argv)
    kb = Path(os.environ["LIFE_AGENT_KB"])
    if args.warm:
        n = len(_questions(kb))
        from life_agent.core import pricing as PRC
        p_derive = PRC.EXTRACT_AMOUNTS_USD  # the ONE price table (M4) — no fallback
        cap = args.cap_usd if args.cap_usd is not None else n * _K * p_derive
        print(f"warm cap: {n} questions x {_K} x ${p_derive} = ${cap:.2f}")
        return warm(kb, cap)
    ap.error("--warm is required")


if __name__ == "__main__":
    raise SystemExit(main())
