#!/usr/bin/env python3
"""The off-gate interval sweep (r31a) — predict r31's assert set before money is spent.

Run 9's discipline, applied to r30b's lever: before a priced gate run, the counterfactual is
read off the ARCHIVED record and its prediction published, so the live run either matches a
prediction already on the page or contradicts it in the open. A sweep that is written after
the run is a rationalisation.

**$0 by construction.** Reads the archived decision rows and the questions file only. The one
engine call is the local utility fold (the credence skin, a local process) — the same
`production_posterior()` seam `scripts/gate_splice.py` uses, imported rather than re-derived.
No model call, no retrieval, no gate write.

CRITERIA, FROZEN BEFORE THIS INSTRUMENT READ ANYTHING (r31a):

  S0  **Control.** With the interval rows disabled, the sweep must reproduce the recorded
      action of the archived run on every row it reads. Rows it cannot reproduce are NAMED
      and excluded from every count below — never silently kept, because a sweep that cannot
      reproduce the record it reads is measuring itself.
  S1  **It predicts, it does not describe.** The published assert set is r31's prediction. A
      live row that contradicts it is a defect in this instrument or in the record, disclosed
      as such — not a surprise explained afterwards.
  S2  **Reach is counted only where the archived run WITHHELD.** An interval that displaces a
      crisp *report* is a different and more dangerous event; it is counted separately and
      never netted against reach.
  S3  **The wrong-commit class is counted from birth.** Every predicted interval commit is
      graded by the frozen Winkler rule (`decide.realised_aggregate`) against the question's
      gold; `interval-excludes-gold` is reported beside the reach, per r30b C6 and the owner's
      hard clause — no lever ships while it makes a named wrong-commit class worse.
  S4  **Nothing is tuned to the reading.** Ū is the live model file folded through the same
      seam the deployed path uses; the shape classifier and the interval construction are the
      deployed ones, imported, never re-implemented (the standing lesson: a census must read
      the deployed rule end to end).

Usage:
  uv run python scripts/interval_sweep.py --run-id gate-20260826T083356 [--out FILE]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gate_splice import production_posterior  # S4: the one Ū seam, imported
from run_eval import load_questions

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from life_agent.core import answer_shape as AS
from life_agent.core import config as LCFG
from life_agent.core import decide as DEC_ATOM
from life_agent.core import decisions as DEC
from life_agent.core import lookup as LK


def _eu(values: list[float], weights: list[float]) -> float:
    """The engine's expectation over one tabular row — the dot product `optimise` maximises."""
    return sum(v * w for v, w in zip(values, weights, strict=True))


def _argmax(rows: dict[str, list[float]], weights: list[float]) -> tuple[str, float]:
    best, best_eu = "", float("-inf")
    for name in sorted(rows):                    # deterministic on ties
        eu = _eu(rows[name], weights)
        if eu > best_eu:
            best, best_eu = name, eu
    return best, best_eu


def _label(action: str) -> str:
    """A row key → the recorded action vocabulary (the same mapping both lanes apply)."""
    if action.startswith(DEC_ATOM.INTERVAL_PREFIX):
        return "report"
    if action.startswith("report_scoped_"):
        return "report_scoped"
    if action.startswith("report_"):
        return "report"
    return action


def pinned_questions(run_id: str) -> Path:
    """The population the archived run ACTUALLY read, from its own `run_meta` pin — never a
    default. Guessing the question file is how a sweep silently reads a different population
    than the run it claims to predict (found by this instrument's own control, S0, before any
    verdict: the module default is a 20-question legacy set that shares 0 ids with run 18)."""
    for d in (LCFG.KB / "eval" / "gate-outside-option", LCFG.KB / "eval" / "gate"):
        meta = d / f"run_meta-{run_id}.json"
        if meta.is_file():
            path = (json.loads(meta.read_text()).get("questions") or {}).get("path")
            if path:
                return Path(path)
    raise SystemExit(f"no run_meta pin for {run_id!r} — pass --questions explicitly")


def decisions_for(run_id: str) -> list[dict]:
    rows = []
    for line in (LCFG.KB / "calibration" / "decisions.jsonl").read_text().splitlines():
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("run_id") == run_id:
            rows.append(r)
    return rows


def sweep(run_id: str, questions_path: Path | None) -> dict:
    post = production_posterior()
    raw = post.u_bar()
    qs = load_questions(questions_path or pinned_questions(run_id))
    by_qid = {DEC.question_id(q["question"]): q for q in qs}

    control_ok, control_bad, unreadable = [], [], []
    reach, displaced, excludes = [], [], []
    on_shape = 0
    for r in decisions_for(run_id):
        q = by_qid.get(r.get("question_id"))
        ps = r.get("posterior_summary") or {}
        cands = [str(c) for c in (ps.get("candidates") or [])]
        creds = [float(c) for c in (ps.get("credences") or [])]
        if q is None or not cands or len(cands) != len(creds):
            unreadable.append({"qid": r.get("question_id"), "why": "no question or no posterior"})
            continue
        weights = [*creds, float(ps.get("p_none") or 0.0)]
        shape = AS.answer_space(q["question"])
        u_bar = DEC_ATOM.shaped_u_bar(raw, shape)
        base = LK.action_utilities(weights, u_bar)
        predicted_base, _ = _argmax(base, weights)
        recorded = str(r.get("chosen_action") or "")
        if _label(predicted_base) != recorded:                       # S0
            control_bad.append({"id": q["id"], "recorded": recorded,
                                "predicted": _label(predicted_base)})
            continue
        control_ok.append(q["id"])

        opts = DEC_ATOM.interval_options(cands, u_bar, shape=shape)
        if not opts:
            continue
        on_shape += 1
        rows = LK.action_utilities(weights, u_bar, intervals=opts)
        won, eu = _argmax(rows, weights)
        chosen = DEC_ATOM.interval_by_name(opts, won)
        if chosen is None:
            continue
        gold = str(q.get("answer") or "")
        gv = AS.numeric_value(gold) if gold else None
        x, excl = (DEC_ATOM.realised_aggregate(chosen.lo, chosen.hi, gv)
                   if gv is not None else (None, None))
        row = {"id": q["id"], "was": recorded, "eu": round(eu, 4),
               "n_candidates": len(cands), "n_proposals": len(opts),
               "winkler_x": None if x is None else round(x, 4),
               "excludes_gold": excl}
        (reach if recorded in ("abstain", "ask_clarify") else displaced).append(row)   # S2
        if excl:                                                                        # S3
            excludes.append(q["id"])
    return {"run_id": run_id, "u_bar_has_shape_scales":
            sorted(k for k in raw if k.startswith(("voi_scale_", "regret_scale_"))),
            "control_reproduced": len(control_ok), "control_failed": control_bad,
            "unreadable": unreadable, "rows_where_the_lever_can_fire": on_shape,
            "predicted_reach": reach, "predicted_displacements": displaced,
            "interval_excludes_gold": excludes}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--questions", type=Path, default=None,
                    help="override the run_meta pin (normally unnecessary and unwise)")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)
    out = sweep(args.run_id, args.questions)
    print(json.dumps(out, indent=1, ensure_ascii=False))
    if args.out:
        args.out.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
