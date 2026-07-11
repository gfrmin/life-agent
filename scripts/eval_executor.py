#!/usr/bin/env python3
"""Executor eval — over the credence answer-brain LOOP, not a Python brain.

The decision lives in the credence daemon (`gather_decide` / `terminal_decide`), the single
reasoner; the loop that ENACTS its VOI schedule over the life-agent bridge — `/route →
/retrieve → /probe → /extract → /decide`, then each scheduled transform — is
:mod:`life_agent.core.executor` (shared with the production read-path so both drive ONE
executor, PRINCIPLES §16/§4). This harness is a measurement BODY: it injects the urllib
transport, runs each eval question through that loop, and grades the daemon's effector
labels-first.

The honest headline — **CORRECT at ZERO owner-graded confident-wrong** — is counted only on
owner-graded rows, with the daemon's effector histogram. No `/log_decision` is posted, so the
live calibration log is untouched (isolation by not-writing).

    bin/answer-brain must be up (daemon :8799 + bridge :8798), or start them separately. Then:
    uv run --project . python scripts/eval_executor.py [--k N] [--limit N] [--only q-002,q-011]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.request
from collections import Counter
from datetime import datetime
from pathlib import Path

from life_agent.core import executor as EX
from life_agent.core import shadow_mirror as SM

sys.path.insert(0, str(Path(__file__).resolve().parent))
from answer_labels import Label, load_labels, verdict
from eval_grading import answer_matches, chunk_matches_any
from run_eval import _answer_in_corpus, _kb_root, load_questions
from triage_grading import triage

BRIDGE = os.environ.get("LIFE_AGENT_BRIDGE_URL", "http://127.0.0.1:8798")
DAEMON = os.environ.get("ANSWER_BRAIN_URL", "http://127.0.0.1:8799")

# Grow (escalating recall on a withholding terminal) is ON by default; the loop's grow logic and
# the transform menu now live in core/executor.py. `ANSWER_BRAIN_GROW=0` is the no-grow baseline.
_GROW = os.environ.get("ANSWER_BRAIN_GROW", "1") != "0"
# The grow-lane flag (slice 6): recall decided by the daemon over the priced grow menu; the
# same env var scripts/ask.py reads, so the eval measures the production path verbatim.
_GROW_LANE = os.environ.get("LIFE_AGENT_GROW_LANE", "") == "1"


def _post(url: str, payload: dict) -> dict | None:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=300) as r:
        return json.loads(r.read())


def _post_for(question: str) -> EX.Post:
    """The shadow-wrapped post for one eval question — same question_id derivation
    (sha256 of the raw question text, [:16]) and the same shared mirror
    (life_agent.core.shadow_mirror) as every production caller, so a live-service eval run
    feeds the membrane shadow exactly like the ask read-path does."""
    question_id = hashlib.sha256(question.encode("utf-8")).hexdigest()[:16]
    return SM.shadow_wrapped_post(_post, BRIDGE, question_id)


def _grade(conn, q: dict, view: dict, labels: list[Label]) -> dict:
    gold = q.get("answer", "")
    variants = q.get("answer_variants", [])
    distractors = q.get("distractors", []) if q.get("subject", "n/a") != "n/a" else []
    answerable = bool(gold)
    cards = [h["chunk_text"] for h in view["hits"]]
    asserted = view["asserted"]

    gold_in_topk = answerable and chunk_matches_any(gold, variants, cards)
    gold_in_corpus = gold_in_topk or (answerable and _answer_in_corpus(conn, gold, variants))
    gold_in_candidates = answerable and any(
        answer_matches(gold, variants, c) for c in view["candidates"])
    asserted_correct = answerable and any(answer_matches(gold, variants, a) for a in asserted)
    asserted_distractor = any(answer_matches(d, [], a) for d in distractors for a in asserted)
    asserted_verdict = next(
        (v for a in asserted if (v := verdict(labels, q["id"], a)) is not None), None)

    t = triage(answerable=answerable, asserted=bool(asserted),
               asserted_correct=asserted_correct, asserted_distractor=asserted_distractor,
               gold_in_candidates=gold_in_candidates, gold_in_topk=gold_in_topk,
               gold_in_corpus=gold_in_corpus, scoped=False, asserted_verdict=asserted_verdict)
    return {
        "id": q["id"], "question": q["question"], "subject": q.get("subject", "n/a"),
        "answerable": answerable, "gold": gold, "effector": view["effector"],
        "asserted": asserted, "candidates": view["candidates"][:5],
        "credences": [round(c, 3) for c in view["credences"][:5]], "p_none": view["p_none"],
        "bucket": t.bucket, "cause": t.cause, "needs_judgment": t.needs_judgment,
        "owner_graded": asserted_verdict is not None, "asserted_verdict": asserted_verdict,
        "channel": {"gold_in_topk": bool(gold_in_topk), "gold_in_corpus": bool(gold_in_corpus),
                    "gold_in_candidates": bool(gold_in_candidates),
                    "asserted_correct": bool(asserted_correct)},
    }


def render_report(packets: list[dict], *, k: int, elapsed: float) -> str:
    answerable = [p for p in packets if p["answerable"]]
    correct = [p for p in packets if p["bucket"] == "CORRECT"]
    real_cw = [p for p in packets if p["bucket"] == "CONFIDENT_WRONG" and p["owner_graded"]]
    token_cw = [p for p in packets if p["bucket"] == "CONFIDENT_WRONG" and not p["owner_graded"]]
    effectors = Counter(p["effector"] for p in packets)
    lines = [
        "# Answer-brain loop eval — credence decides — correct @ zero owner-graded confident-wrong",
        "",
        f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}   k={k}   elapsed={elapsed:.1f}s   "
        f"n={len(packets)}   (decision: credence daemon /decide, not a Python brain)",
        "",
        f"**CORRECT {len(correct)}/{len(answerable)} answerable** · "
        f"**real-CONFIDENT_WRONG {len(real_cw)} (gate: 0)** · "
        f"token-CW {len(token_cw)} (unlabeled, NOT the gate)",
        "",
        "Effectors: " + " · ".join(f"{e}={n}" for e, n in sorted(effectors.items())),
        "",
        "| ID | effector | bucket | cause | top cand | p | gold@topk | Q |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for p in packets:
        cand = (p["candidates"][0][:22] if p["candidates"] else "—")
        pc = f"{p['credences'][0]:.2f}" if p["credences"] else "—"
        lines.append(
            f"| {p['id']} | {p['effector']} | {p['bucket']} | {p['cause'] or ''} | {cand} | {pc} "
            f"| {'✓' if p['channel']['gold_in_topk'] else '·'} | {p['question'][:34]} |")
    if real_cw:
        lines += ["", "## ⛔ owner-graded CONFIDENT_WRONG (the gate breach — must be empty)", ""]
        lines += [f"- {p['id']} ({p['effector']}): {p['asserted']} — {p['asserted_verdict']}"
                  for p in real_cw]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default=os.environ.get(
        "PKM_CONFIG", str(Path("~/.config/life-agent/pkm.yaml").expanduser())))
    parser.add_argument("--k", type=int, default=20)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--only", default="")
    parser.add_argument("--rerank", action="store_true",
                        help="recall lever (Slice 4): over-fetch + listwise rerank in /retrieve")
    args = parser.parse_args()

    import duckdb
    import yaml

    questions = load_questions()
    if args.only:
        want = {x.strip() for x in args.only.split(",") if x.strip()}
        questions = [q for q in questions if q["id"] in want]
    if args.limit:
        questions = questions[: args.limit]

    # a separate read-only handle, only for the retrieval-channel grading (gold_in_corpus)
    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    conn = duckdb.connect(str(Path(cfg["root_dir"]).expanduser() / "catalogue.duckdb"),
                          read_only=True)
    conn.execute("INSTALL fts; LOAD fts;")
    labels = load_labels(_kb_root() / "eval" / "labels.jsonl")

    # liveness check — fail loud if the loop isn't up
    for url, name in ((f"{BRIDGE}/ready", "bridge"), (f"{DAEMON}/ready", "daemon")):
        try:
            urllib.request.urlopen(url, timeout=3)
        except Exception as e:
            print(f"answer-brain {name} not reachable at {url}: {e}\n"
                  f"  start it: bin/answer-brain  (or the daemon + bridge separately)")
            return 2

    print(f"Answer-brain loop eval: {len(questions)} questions · k={args.k} · "
          f"decision = credence daemon · {len(labels)} owner label(s)")
    t0 = time.monotonic()
    packets: list[dict] = []
    for q in questions:
        view = EX.decide_via_loop(q["question"], args.k, bridge=BRIDGE, daemon=DAEMON,
                                  post=_post_for(q["question"]), get=_get, grow=_GROW,
                                  rerank=args.rerank, grow_lane=_GROW_LANE)
        p = _grade(conn, q, view, labels)
        packets.append(p)
        print(f"  {p['id']}: {p['effector']} → {p['bucket']}"
              + (f"/{p['cause']}" if p["cause"] else ""))
    elapsed = time.monotonic() - t0

    out_dir = _kb_root() / "eval" / "exec"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "loop_packets.jsonl").write_text(
        "".join(json.dumps(p, ensure_ascii=False, sort_keys=True) + "\n" for p in packets),
        encoding="utf-8")
    (out_dir / "loop_report.md").write_text(
        render_report(packets, k=args.k, elapsed=elapsed), encoding="utf-8")

    answerable = sum(1 for p in packets if p["answerable"])
    correct = sum(1 for p in packets if p["bucket"] == "CORRECT")
    real_cw = sum(1 for p in packets
                  if p["bucket"] == "CONFIDENT_WRONG" and p["owner_graded"])
    print(f"\nLoop eval → {out_dir}/loop_report.md")
    print(f"  CORRECT {correct}/{answerable} · real-CONFIDENT_WRONG {real_cw} (gate: 0) · "
          f"effectors {dict(Counter(p['effector'] for p in packets))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
