#!/usr/bin/env python3
"""fit_gather_row — measure the gather row from recorded decision sequences.

Each m5-base A-loop fixture records one question's full exchange with the bridge. Its first
``/decide`` request fixes the starting posterior (``p1`` from :mod:`life_agent.core.posterior`
over the recorded observations); its final output, graded by exact match against the gold
in the question set, is the outcome (``right`` / ``wrong`` / ``declined``). The episodes fit
:mod:`life_agent.core.gather_row`, written to ``$LIFE_AGENT_KB/calibration/gather_row.json``
(the bridge prices the gather row from it at boot). Prints counts only.

    uv run python scripts/fit_gather_row.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import yaml

from life_agent.core import config as CFG
from life_agent.core import decide as DEC
from life_agent.core import gate as GATE
from life_agent.core import gather_row as GR
from life_agent.core import posterior as POST


def episode(fixture: dict, gold: dict) -> tuple[float, str] | None:
    """``(p1 at the first decide, graded outcome)`` for one recorded A-loop question, or None
    when it never reached ``/decide`` with a candidate."""
    decides = [w for w in fixture["wire"] if w["seam"] == "http"
               and str(w["request"].get("url", "")).endswith("/decide")]
    if not decides:
        return None
    req = decides[0]["request"]["payload"]
    n = len(req.get("candidates") or [])
    if n == 0:
        return None
    credences, _ = POST.candidate_posterior(n, list(req.get("observations") or []),
                                            float(req["rho"]))
    out = fixture["outputs"]
    if out["effector"] != "report":
        return DEC.p_correct(credences), "declined"
    ok = GATE.realised_report([str(a) for a in out["asserted"]], gold.get("answer", ""),
                              gold.get("answer_variants", []))
    return DEC.p_correct(credences), ("right" if ok else "wrong")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fixtures", default=str(CFG.KB / "eval/collapse-fixtures/m5-base"))
    ap.add_argument("--questions", default=str(CFG.KB / "eval/questions_v2.yaml"))
    ap.add_argument("--out", default=str(CFG.KB / "calibration/gather_row.json"))
    a = ap.parse_args(argv)
    gold = {q["id"]: q for q in yaml.safe_load(Path(a.questions).read_text())["questions"]}
    files = sorted(Path(a.fixtures).glob("*-aloop-*.json"))
    if not files:
        print(f"no A-loop fixtures under {a.fixtures}", file=sys.stderr)
        return 2
    episodes: list[tuple[float, str]] = []
    h = hashlib.sha256()
    for f in files:
        qid = f.stem.rsplit("aloop-", 1)[1]
        if qid not in gold:
            continue
        data = f.read_bytes()
        h.update(data)
        ep = episode(json.loads(data), gold[qid])
        if ep is not None:
            episodes.append(ep)
    t_right, t_wrong = GR.fit(episodes)
    row = GR.as_u_bar(t_right, t_wrong)
    Path(a.out).write_text(json.dumps({
        "u_bar": row, "n_episodes": len(episodes),
        "outcomes": dict(Counter(o for _, o in episodes)),
        "fixtures_sha256": h.hexdigest(), "prior": "Dirichlet(2,2,2) posterior mode, EM"},
        indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{len(episodes)} episodes {dict(Counter(o for _, o in episodes))} → "
          + ", ".join(f"{k} {v:.3f}" for k, v in row.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
