#!/usr/bin/env python3
"""regrade_outside_option — the board's outside option, graded like the act itself.

A gate archive's outside-option arm (``mono``) is a replay of the V1 deliberative run, whose
answers are PROSE: it is graded right whenever the gold appears anywhere in a paragraph,
while the typed arm must assert one span. On the 87 questions where both graders can be run
over the SAME live answers, that is 0.897 against 0.805 — so the two arms on today's board
are not held to one standard, and every router number built from them is optimistic.

This rewrites the arm from the live deliberative rung (``core/deliberate``), graded on the
ANSWER line it commits, by ``gate.realised_report`` — the grader the typed arm faces. The
rung's recorded answers are content-addressed, so a question already answered at this corpus
pin costs nothing; ``--live`` pays for the rest, under ``--budget-usd``. Each row's cost is
what the call actually cost, so the board prices the action at its price, never at zero for
a replay. Prints counts only; writes ``<name>-strict.jsonl``.

    uv run python scripts/regrade_outside_option.py PAIRED.jsonl --live --budget-usd 8
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
from life_agent.core import corpus as CORPUS
from life_agent.core import deliberate as DL
from life_agent.core import derivations as D
from life_agent.core import gate as GATE
from life_agent.core import terminals as TERM
from life_agent.tasks import read

#: The rung's identity, matching what core/deliberate runs and what the bridge caches.
MODEL = DL.DeliberateConfig.model
MAX_TURNS = DL.DeliberateConfig.max_turns


def rung_answer(root: Path, question: str, digest: str, *, live: bool) -> dict | None:
    """The rung's recorded answer for one question, or ``None`` when it has none and
    ``live`` is off. A live call records itself, so the next run replays it."""
    key = D.deliberate_key(question, digest, model=MODEL,
                           prompt_template=DL.PROMPT_DELIB_V2, max_turns=MAX_TURNS)
    raw = D.lookup(root, key.cache_key)
    if raw is not None:
        return dict(json.loads(raw.decode("utf-8")), cache="hit")
    if not live:
        return None
    r = DL.answer(question, DL.config_from_env())
    if r.status != "ok":
        return {"value": None, "declined": True, "cost_usd": r.cost_usd or 0.0,
                "status": r.status, "cache": "error"}
    DL.record_answer(root, key, r)
    return {"value": r.value, "text": r.text, "declined": r.declined,
            "cost_usd": r.cost_usd or 0.0, "cache": "miss"}


def graded(answer: dict | None, q: dict) -> dict:
    """The arm's row: what the rung committed, graded on its answer line."""
    if answer is None:
        return {"action": "abstain", "correct": None, "cost_usd": 0.0,
                "withheld": "not_recorded"}
    value = str(answer.get("value") or "")
    cost = float(answer.get("cost_usd") or 0.0)
    if answer.get("declined") or not value:
        return {"action": "abstain", "correct": None, "cost_usd": cost,
                "withheld": "rung_declined"}
    ok = GATE.realised_report([value], q.get("answer", ""), q.get("answer_variants", []))
    return {"action": "report", "correct": bool(ok), "cost_usd": cost, "withheld": None}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paired")
    ap.add_argument("--questions", default=str(CFG.KB / "eval/questions_v2.yaml"))
    ap.add_argument("--live", action="store_true", help="pay for questions with no answer")
    ap.add_argument("--budget-usd", type=float, default=8.0)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    gold = {q["id"]: q for q in
            yaml.safe_load(Path(a.questions).read_text(encoding="utf-8"))["questions"]}
    conn = TERM.connect()
    try:
        digest = CORPUS.corpus_digest(conn)
    finally:
        conn.close()
    root = read.pkm_root()
    rows = [json.loads(line) for line in
            Path(a.paired).read_text(encoding="utf-8").splitlines() if line]
    counts: Counter[str] = Counter()
    spend = 0.0
    out_rows = []
    for row in rows:
        q = gold.get(row["question_id"])
        if q is None:
            print(f"{row['question_id']} is not in the question set", file=sys.stderr)
            return 2
        live = a.live and spend < a.budget_usd
        answer = rung_answer(root, q["question"], digest, live=live)
        if answer is not None and answer.get("cache") != "hit":
            spend += float(answer.get("cost_usd") or 0.0)
        counts[str((answer or {}).get("cache", "absent"))] += 1
        arm = graded(answer, q)
        counts[arm["withheld"] or ("right" if arm["correct"] else "wrong")] += 1
        out_rows.append({**row, "mono": arm, "outside_option": "deliberate-answer-line"})
    out = Path(a.out) if a.out else Path(a.paired).with_name(
        Path(a.paired).stem.replace("-exact", "") + "-strict.jsonl")
    out.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in out_rows),
                   encoding="utf-8")
    digest_out = hashlib.sha256(out.read_bytes()).hexdigest()
    where = (f"$LIFE_AGENT_KB/{out.relative_to(CFG.KB)}"
             if out.is_relative_to(CFG.KB) else out.name)
    print(" · ".join(f"{k} {v}" for k, v in sorted(counts.items()))
          + f" · paid ${spend:.2f}")
    print(f"wrote {len(out_rows)} rows → {where} (sha256 {digest_out})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
