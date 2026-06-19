#!/usr/bin/env python3
"""Executor eval — over the credence answer-brain LOOP, not a Python brain (Slice 0).

The decision no longer lives in life-agent: this harness is a measurement *body* that drives the
live loop — `/route → /retrieve → /probe/subject → /extract` (the life-agent bridge, :8798) →
`GET /utility` → `POST /decide` (the credence answer-brain daemon, :8799) — and grades the daemon's
effector labels-first. It retires `core/executor.py`: the credence daemon (`gather_decide` /
`terminal_decide`) is the single reasoner; nothing here computes a posterior or picks an action.

Slice 0 is the **no-gather baseline**: `era_split=False` (no recency gather yet — that arrives with
per-construct volatility, Slice 1), the subject covariate down-weights a relative's documents (the
gate-safety the daemon's `owner_scoped` slot will formalize in Slice 2). The honest headline is
unchanged — **CORRECT at ZERO owner-graded confident-wrong** — counted only on owner-graded rows,
with the daemon's effector histogram. No `/log_decision` is posted, so the live calibration log is
untouched (isolation by not-writing).

    bin/answer-brain must be up (daemon :8799 + bridge :8798), or start them separately. Then:
    uv run --project . python scripts/eval_executor.py [--k N] [--limit N] [--only q-002,q-011]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from answer_labels import Label, load_labels, verdict
from eval_grading import answer_matches, chunk_matches_any
from run_eval import _answer_in_corpus, _kb_root, load_questions
from triage_grading import triage

BRIDGE = os.environ.get("LIFE_AGENT_BRIDGE_URL", "http://127.0.0.1:8798")
DAEMON = os.environ.get("ANSWER_BRAIN_URL", "http://127.0.0.1:8799")
# the §2-A net_voi-gated corroborate budget the body offers the daemon: the cloud re-read's
# reliability + its cost (utility units). The daemon rescues a below-bar leader with a corroborate
# only when its VOI clears this cost. GATED OFF (gather_rho=0) by default: the full-eval run showed
# the §2-A RESCUE reports stale values (q-006 → the stale HK address) because the corroborate
# observation carries time_factor=1.0, BYPASSING the construct's volatility decay (Slice 1) that the
# local channel gets — the same "a lever needs its guard" finding as rerank. The net_voi mechanism
# is validated (test_answer_brain §2-A + test_server wire); enabling the rescue safely needs the
# corroborate obs to carry recency. The §2-C owner_scoped corroborate (Slice 2) is unaffected (it
# is a disagreement check, not a rescue) and stays on. Set gather_rho>0 to exercise §2-A.
_GATHER_RHO = 0.0
_GATHER_COST = 0.02


def _post(url: str, payload: dict) -> dict | None:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=300) as r:
        return json.loads(r.read())


def _owner_scoped(question: str) -> bool:
    import re
    return bool(re.search(r"\b(?:my|mine|the owner's)\b", question, re.IGNORECASE))


def _decide_via_loop(question: str, k: int, *, rerank: bool = False) -> dict:
    """Drive one question through the live loop and return a normalized decision view:
    {effector, asserted, candidates, credences, p_none, eu, hits, route}."""
    route = _post(f"{BRIDGE}/route", {"question": question})
    if route is None:  # not a typed lookup → the brain's narrative case (a coverage MISS here)
        return {"effector": "narrative", "asserted": [], "candidates": [], "credences": [],
                "p_none": None, "eu": None, "hits": [], "route": None}
    hits = _post(f"{BRIDGE}/retrieve", {"question": question, "k": k, "rerank": rerank})["hits"]
    hit_keys = list(dict.fromkeys(h["artifact_cache_key"] for h in hits))
    subj = _post(f"{BRIDGE}/probe/subject", {"hit_keys": hit_keys})["subject_state"]
    recency = _post(f"{BRIDGE}/probe/recency", {"hit_keys": hit_keys})["doc_date"]
    ext = _post(f"{BRIDGE}/extract", {  # construct ⇒ bridge decays time_factor at its volatility
        "question": question, "hits": hits, "time_indexed": route["time_indexed"],
        "construct": route["construct"],
        "covariates": {"subject_state": subj, "doc_date": recency}})
    if not ext["candidates"]:  # zero grounded observations → the local edge declined
        return {"effector": "miss", "asserted": [], "candidates": [], "credences": [],
                "p_none": None, "eu": None, "hits": hits, "route": route}
    u_bar = _get(f"{BRIDGE}/utility")["u_bar"]
    candidates = ext["candidates"]
    owner = _owner_scoped(question)
    obs, rho, era = ext["observations"], ext["rho"], ext["era_split"]

    def _decide(observations: list, r: float, era_split: bool, applied: list[str]) -> dict:
        return _post(f"{DAEMON}/decide", {
            "candidates": candidates, "observations": observations, "rho": r, "u_bar": u_bar,
            "era_split": era_split, "owner_scoped": owner, "applied_probes": applied,
            "gather_rho": _GATHER_RHO, "gather_cost": _GATHER_COST})

    applied: list[str] = []
    dec = _decide(obs, rho, era, applied)
    for _ in range(4):  # the gather loop — each probe fires at most once (daemon guarantees)
        if dec["effector"] != "gather":
            break
        if dec.get("probe") == "recency":
            # recency is PRE-APPLIED in /extract (obs already decayed at the construct's
            # volatility) → acknowledge (mark applied, re-decide on the same posterior).
            applied = list(dict.fromkeys([*applied, "recency"]))
            dec = _decide(obs, rho, era, applied)
        elif dec.get("probe") == "corroborate":
            # the owner_scoped attribution guard: a subject-aware whole-doc re-read REPLACES the
            # local channel. The joint's value → one observation (or NONE ⇒ empty ⇒ abstain).
            cr = _post(f"{BRIDGE}/probe/corroborate",
                       {"reextract": True, "question": question, "hits": hits,
                        "candidates": candidates})
            obs, rho, era = cr["observations"], cr["gather_rho"], False
            applied = list(dict.fromkeys([*applied, "corroborate"]))
            dec = _decide(obs, rho, era, applied)
        else:
            break
    asserted = [dec["value"]] if dec["effector"] == "report" and dec["value"] else []
    return {"effector": dec["effector"], "asserted": asserted, "candidates": ext["candidates"],
            "credences": dec["credences"], "p_none": dec["p_none"], "eu": dec["eu"],
            "hits": hits, "route": route}


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
        view = _decide_via_loop(q["question"], args.k, rerank=args.rerank)
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
