"""Run the act over a question set and write the archive `eval/score.py` scores.

Drives every question through the executor surface (``ask_client.drive``: the bridge's
host decider), grades the reply by exact match on the gold, and writes one JSONL row per
question under ``$LIFE_AGENT_KB/eval/typed/``. A question whose gold chunk is absent from
this machine's catalogue is censored.

Point the run at a bridge with ``LIFE_AGENT_BRIDGE_URL``. Decisions carry a ``gate-`` run id,
so the production readout excludes them. Prints counts only.

``--withhold-source`` re-asks each question with every document that attests its answer
withheld from retrieval (``eval/withheld.py``): the answer is then absent, so declining is
right, an assertion is wrong, and an assertion of the gold is a leak, counted loudly. Such a
run is ``gate-withheld-…`` and its rows say ``"answerable": false``.

    uv run python -m eval.run --questions $LIFE_AGENT_KB/eval/questions_generated.yaml
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any, TypedDict

import yaml

from eval import withheld as WH
from eval.calibration import read_leader
from eval.grading import RealisedResponse, realised_report
from life_agent.core import ask_client as AC
from life_agent.core import config as CFG
from life_agent.core import decisions as DEC
from life_agent.core import pricing as PRC
from life_agent.core import retrieval as RET

_DEFAULTS: dict[str, Any] = {"subject": "n/a", "answer": "", "answer_variants": [],
                             "distractors": [], "fuzzy": False, "search_queries": [],
                             "mode_hint": None, "notes": ""}


class _Seen(TypedDict):
    """The leader's calibration reading, as `RealisedResponse` keywords."""

    p1: float | None
    n_candidates: int
    leader_correct: bool | None
    truth_in_candidates: bool


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
                   available: bool = True, conn: Any = None) -> RealisedResponse:
    """The arm's realised answer from the executor's view. It is priced at the menu's
    declared prices for the probes it applied, on every action: an abstain that gathered
    still paid for it. A cite is right iff the cited document attests the gold
    (``withheld.attesting_artifacts`` over ``conn``, the catalogue connection)."""
    gold, variants = q.get("answer", ""), q.get("answer_variants", [])
    applied = tuple(str(p) for p in view["applied"])
    cost, metered = PRC.list_price(applied), float(view["spend_usd"] or 0.0)
    eff = str(view["effector"])
    lead = read_leader(view.get("candidates") or [], view.get("credences") or [], gold, variants)
    seen = _Seen(p1=lead.p1, n_candidates=lead.n_candidates,
                 leader_correct=lead.leader_correct,
                 truth_in_candidates=lead.truth_in_candidates)
    if eff == "report":
        return RealisedResponse("report", realised_report(
            [str(a) for a in view["asserted"]], gold, variants),
            cost_usd=cost, applied=applied, metered_usd=metered, **seen)
    if eff == "cite":
        if conn is None:
            raise ValueError("grading a cite needs the catalogue connection")
        key = str(view["cited"]["cache_key"])
        return RealisedResponse("cite", key in WH.attesting_artifacts(conn, gold, variants),
                                cost_usd=cost, applied=applied, metered_usd=metered,
                                cited=key, **seen)
    reason = DEC.withhold_reason(effector=view.get("effector"),
                                 candidates=view.get("candidates"), available=available)
    return RealisedResponse("ask_clarify" if eff == "ask_clarify" else "abstain", None,
                            cost_usd=cost, withheld=reason, applied=applied,
                            metered_usd=metered, **seen)


def is_leak(view: dict[str, Any], q: dict[str, Any],
            withheld: frozenset[str] = frozenset()) -> bool:
    """A withheld question whose gold reached the act anyway: an asserted value or any
    candidate matches it, so some document attesting it was not withheld; or the act cited
    one of the ``withheld`` documents."""
    if str((view.get("cited") or {}).get("cache_key") or "") in withheld:
        return True
    gold, variants = q.get("answer", ""), q.get("answer_variants", [])
    seen = [str(c) for c in (view.get("candidates") or [])] + [
        str(a) for a in (view.get("asserted") or [])]
    return realised_report(seen, gold, variants)


def archive_row(qid: str, run_id: str, r: RealisedResponse, *, censored: bool,
                answerable: bool = True, withheld: int | None = None,
                leak: bool = False) -> dict[str, Any]:
    """One archive line. The default mode's line is unchanged; a withheld-source line
    carries the count of artifacts withheld and whether the gold leaked."""
    row: dict[str, Any] = {
        "question_id": qid, "answerable": answerable, "run_id": run_id, "censored": censored,
        "typed": {"action": r.action, "correct": r.correct, "cost_usd": r.cost_usd,
                  "withheld": r.withheld, "applied": list(r.applied),
                  "metered_usd": r.metered_usd, "p1": r.p1, "n_candidates": r.n_candidates,
                  "leader_correct": r.leader_correct,
                  "truth_in_candidates": r.truth_in_candidates, "cited": r.cited}}
    if withheld is not None:
        row["withheld"] = {"n_artifacts": withheld}
        if leak:
            row["leak"] = True
    return row


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--questions", required=True)
    ap.add_argument("--k", type=int, default=20)
    ap.add_argument("--limit", type=int, default=None, help="only the first N questions")
    ap.add_argument("--only-ids", default=None, metavar="FILE",
                    help="a JSON list of question ids; only those questions are run")
    ap.add_argument("--withhold-source", action="store_true",
                    help="re-ask each question with every document attesting its answer "
                         "withheld from retrieval (eval/withheld.py)")
    ap.add_argument("--out", default=None, help="default: $LIFE_AGENT_KB/eval/typed/<run>.jsonl")
    a = ap.parse_args(argv)
    if a.withhold_source:
        WH.force_deliberate_off()
    if not AC._ready():
        print(f"REFUSED: the bridge at {AC.BRIDGE} is not ready", file=sys.stderr)
        return 2
    questions = load_questions(a.questions)
    if a.only_ids:
        wanted = set(json.loads(Path(a.only_ids).read_text(encoding="utf-8")))
        questions = [q for q in questions if str(q["id"]) in wanted]
    questions = questions[:a.limit]
    kind = "withheld" if a.withhold_source else "typed"
    run_id = f"gate-{kind}-{datetime.now().strftime('%Y%m%dT%H%M%S')}"
    out = Path(a.out) if a.out else CFG.KB / "eval" / "typed" / f"{run_id}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    conn = RET.connect()
    try:
        available = gold_available(conn, questions)
        plans = ({str(q["id"]): WH.plan(conn, q) for q in questions}
                 if a.withhold_source else {})
        tally = run_questions(questions, a, conn=conn, out=out, run_id=run_id,
                              available=available, plans=plans)
    finally:
        conn.close()
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    try:
        shown = f"$LIFE_AGENT_KB/{out.relative_to(CFG.KB)}"
    except ValueError:
        shown = str(out)
    print(" · ".join(f"{k} {v}" for k, v in sorted(tally.items()))
          + f" → {shown} (sha256 {digest})")
    return 0


def run_questions(questions: list[dict[str, Any]], a: argparse.Namespace, *, conn: Any,
                  out: Path, run_id: str, available: dict[str, bool],
                  plans: dict[str, WH.Withholding]) -> Counter[str]:
    """Drive every question through the executor, grade it and write its archive row to
    ``out``; the tally counts right, wrong, cite-right, cite-wrong, declined, censored and
    leaks."""
    tally: Counter[str] = Counter()
    with out.open("w", encoding="utf-8") as fh:
        for q in questions:
            qid = str(q["id"])
            post: Callable[..., Any] = AC.post_json
            if a.withhold_source:
                if plans[qid].skipped:
                    tally[f"skipped {plans[qid].skipped}"] += 1
                    continue
                post = WH.with_exclusion(post, plans[qid].keys)
            view = AC.drive(q["question"], a.k, bridge=AC.BRIDGE, post=post, run_id=run_id,
                            ready=AC._ready).view
            if view is None:
                raise SystemExit(f"executor view missing for {qid} — the bridge went "
                                 "down mid-run; the reading is void")
            ok = available.get(qid, True)
            r = typed_response(view, q, available=ok, conn=conn)
            leak = a.withhold_source and is_leak(view, q, plans[qid].keys)
            fh.write(json.dumps(archive_row(
                qid, run_id, r, censored=not ok,
                answerable=not a.withhold_source and bool(q.get("answerable", True)),
                withheld=len(plans[qid].keys) if a.withhold_source else None,
                leak=leak)) + "\n")
            fh.flush()
            tally[_tally_key(r, censored=not ok)] += 1
            if leak:
                tally["LEAK"] += 1
    return tally


def _tally_key(r: RealisedResponse, *, censored: bool) -> str:
    if censored:
        return "censored"
    prefix = "cite-" if r.action == "cite" else ""
    if r.correct is None:
        return "declined"
    return prefix + ("right" if r.correct else "wrong")


if __name__ == "__main__":
    raise SystemExit(main())
