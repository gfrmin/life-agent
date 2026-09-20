#!/usr/bin/env python3
"""fit_gather_row — measure the gather row from recorded decision sequences.

Each m5-base A-loop fixture records one question's full exchange with the bridge. Every
``/decide`` that chose ``gather`` is an episode: its posterior (``p1`` from
:mod:`life_agent.core.posterior` over the observations it carried) and the question's final
output, graded by exact match against the gold in the question set (``right`` / ``wrong`` /
``declined``). A late gather, taken after earlier ones failed to lift the leader, is its own
episode at its own ``p1`` and step (the gathers already applied); one row is fit per step, so
the fit sees what gathering is worth from each state. The episodes fit
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


def episodes(fixture: dict, gold: dict) -> list[tuple[int, float, str]]:
    """``(step, p1, graded outcome)`` for every recorded ``/decide`` that chose ``gather`` with
    a candidate on the table; ``step`` is the number of gathers already applied."""
    out = fixture["outputs"]
    if out["effector"] == "report":
        ok = GATE.realised_report([str(a) for a in out["asserted"]], gold.get("answer", ""),
                                  gold.get("answer_variants", []))
        outcome = "right" if ok else "wrong"
    else:
        outcome = "declined"
    eps: list[tuple[int, float, str]] = []
    for w in fixture["wire"]:
        if w["seam"] != "http" or not str(w["request"].get("url", "")).endswith("/decide"):
            continue
        resp = w["response"]
        resp = json.loads(resp) if isinstance(resp, str) else resp
        req = w["request"]["payload"]
        n = len(req.get("candidates") or [])
        if resp.get("effector") != "gather" or n == 0:
            continue
        credences, _ = POST.candidate_posterior(n, list(req.get("observations") or []),
                                                float(req["rho"]))
        step = min(len(req.get("applied_probes") or []), GR.MAX_STEP)
        eps.append((step, DEC.p_correct(credences), outcome))
    return eps


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
    found: list[tuple[int, float, str]] = []
    h = hashlib.sha256()
    for f in files:
        qid = f.stem.rsplit("aloop-", 1)[1]
        if qid not in gold:
            continue
        data = f.read_bytes()
        h.update(data)
        found += episodes(json.loads(data), gold[qid])
    steps = {}
    for st in range(GR.MAX_STEP + 1):
        eps = [(p1, o) for s_, p1, o in found if s_ == st]
        t_right, t_wrong = GR.fit(eps)
        steps[str(st)] = {**GR.as_u_bar(t_right, t_wrong), "n": len(eps)}
        print(f"step {st}: {len(eps)} gathers {dict(Counter(o for _, o in eps))} → "
              + ", ".join(f"{k} {steps[str(st)][k]:.3f}" for k in GR.KEYS))
    Path(a.out).write_text(json.dumps({
        "steps": steps, "fixtures_sha256": h.hexdigest(),
        "prior": "Dirichlet(2,2,2) posterior mode, EM, per step"},
        indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
