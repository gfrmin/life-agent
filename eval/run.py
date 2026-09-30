"""Run the act over a question set and write the archive `eval/score.py` scores.

Drives every question through the executor surface (``ask.answer_via_executor``: the bridge's
host decider), grades the reply by exact match on the gold, and writes one JSONL row per
question under ``$LIFE_AGENT_KB/eval/typed/``. A question whose gold chunk is absent from
this machine's catalogue is censored.

Point the run at a bridge with ``LIFE_AGENT_BRIDGE_URL``. Decisions carry a ``gate-`` run id,
so the production readout excludes them. Prints counts only.

    uv run python -m eval.run --questions $LIFE_AGENT_KB/eval/questions_generated.yaml
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from eval.grading import RealisedResponse, realised_report
from life_agent.core import config as CFG
from life_agent.core import decisions as DEC
from life_agent.core import pricing as PRC

_DEFAULTS: dict[str, Any] = {"subject": "n/a", "answer": "", "answer_variants": [],
                             "distractors": [], "fuzzy": False, "search_queries": [],
                             "mode_hint": None, "notes": ""}


def load_questions(path: Path | str) -> list[dict[str, Any]]:
    """A question set (schema: ``eval/questions.example.yaml``), optional fields defaulted.
    Owner sets hold personal data and live under ``$LIFE_AGENT_KB``, never in the repo."""
    fixture = Path(path).expanduser()
    if not fixture.exists():
        raise SystemExit(f"question set not found: {fixture}")
    data = yaml.safe_load(fixture.read_text(encoding="utf-8"))
    questions = data.get("questions") if isinstance(data, dict) else None
    if not questions:
        raise SystemExit(f"no 'questions:' list found in {fixture}")
    return [{**{k: (list(v) if isinstance(v, list) else v) for k, v in _DEFAULTS.items()},
             **q} for q in questions]


def gold_available(conn: Any, questions: list[dict[str, Any]]) -> dict[str, bool]:
    """Which questions this machine's catalogue can answer at all: a question is unavailable
    iff the chunk its gold was taken from is absent here. The content-addressed pair
    ``(artifact_cache_key, chunk_index)`` is preferred; ``chunk_id`` is a surrogate that a
    catalogue rebuild re-issues. A question that cannot be checked counts as AVAILABLE:
    censoring removes evidence, so a failed probe must never shrink the set."""
    out: dict[str, bool] = {}
    for q in questions:
        qid = str(q["id"])
        prov = q.get("provenance") or {}
        cache_key, chunk_index = prov.get("artifact_cache_key"), prov.get("chunk_index")
        chunk_id = prov.get("chunk_id")
        if cache_key is not None and chunk_index is not None:
            sql = ("SELECT count(*) FROM artifact_chunks "
                   "WHERE artifact_cache_key = ? AND chunk_index = ?")
            params: list[Any] = [cache_key, chunk_index]
        elif chunk_id is not None:
            sql = "SELECT count(*) FROM artifact_chunks WHERE chunk_id = ?"
            params = [chunk_id]
        else:
            out[qid] = True
            continue
        try:
            row = conn.execute(sql, params).fetchone()
            out[qid] = bool(row and row[0])
        except Exception as e:
            print(f"  ! availability probe failed for {qid} ({e}) — counted AVAILABLE")
            out[qid] = True
    return out


def typed_response(view: dict[str, Any], q: dict[str, Any], *,
                   available: bool = True) -> RealisedResponse:
    """The arm's realised answer from the executor's view. It is priced at the menu's
    declared prices for the probes it applied, on every action: an abstain that gathered
    still paid for it."""
    gold, variants = q.get("answer", ""), q.get("answer_variants", [])
    applied = tuple(str(p) for p in view["applied"])
    cost, metered = PRC.list_price(applied), float(view["spend_usd"] or 0.0)
    eff = str(view["effector"])
    if eff == "report":
        return RealisedResponse("report", realised_report(
            [str(a) for a in view["asserted"]], gold, variants),
            cost_usd=cost, applied=applied, metered_usd=metered)
    reason = DEC.withhold_reason(effector=view.get("effector"),
                                 candidates=view.get("candidates"), available=available)
    return RealisedResponse("ask_clarify" if eff == "ask_clarify" else "abstain", None,
                            cost_usd=cost, withheld=reason, applied=applied,
                            metered_usd=metered)


def main(argv: list[str] | None = None) -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import ask

    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--questions", required=True)
    ap.add_argument("--k", type=int, default=20)
    ap.add_argument("--out", default=None, help="default: $LIFE_AGENT_KB/eval/typed/<run>.jsonl")
    a = ap.parse_args(argv)
    if not ask._executor_ready():
        print(f"REFUSED: the bridge at {ask.EXECUTOR_BRIDGE} is not ready", file=sys.stderr)
        return 2
    questions = load_questions(a.questions)
    run_id = f"gate-typed-{datetime.now().strftime('%Y%m%dT%H%M%S')}"
    out = Path(a.out) if a.out else CFG.KB / "eval" / "typed" / f"{run_id}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    conn = ask.connect()
    try:
        available = gold_available(conn, questions)
    finally:
        conn.close()
    tally: Counter[str] = Counter()
    ask.EXECUTOR_RUN_ID = run_id
    try:
        with out.open("w", encoding="utf-8") as fh:
            for q in questions:
                qid = str(q["id"])
                ask.answer_via_executor(q["question"], a.k)
                view = ask.EXECUTOR_VIEW_LAST
                if view is None:
                    raise SystemExit(f"executor view missing for {qid} — the bridge went "
                                     "down mid-run; the reading is void")
                ok = available.get(qid, True)
                r = typed_response(view, q, available=ok)
                fh.write(json.dumps({
                    "question_id": qid, "answerable": bool(q.get("answerable", True)),
                    "run_id": run_id, "censored": not ok,
                    "typed": {"action": r.action, "correct": r.correct,
                              "cost_usd": r.cost_usd, "withheld": r.withheld,
                              "applied": list(r.applied),
                              "metered_usd": r.metered_usd}}) + "\n")
                fh.flush()
                tally["censored" if not ok else ("declined" if r.correct is None
                                                 else "right" if r.correct else "wrong")] += 1
    finally:
        ask.EXECUTOR_RUN_ID = None
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    try:
        shown = f"$LIFE_AGENT_KB/{out.relative_to(CFG.KB)}"
    except ValueError:
        shown = str(out)
    print(" · ".join(f"{k} {v}" for k, v in sorted(tally.items()))
          + f" → {shown} (sha256 {digest})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
