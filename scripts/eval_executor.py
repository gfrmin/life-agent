#!/usr/bin/env python3
"""The ``--executor`` measurement harness (answer-executor plan, Step 2).

Composes :func:`life_agent.core.executor.answer_question` over the PII eval corpus: the cheap
local edge (``lookup_answer``) escalates to the subject-aware joint edge (``extract_joint`` at a
cloud model) under a CALIBRATED floor — the joint edge replaces a withheld / sub-floor local, or
runs a disagreement check on an owner-scoped commit (the mother's-passport guard). It grades
labels-first (the owner's trichotomy verdict is authoritative), and the honest headline is
**CORRECT at ZERO owner-graded confident-wrong + cloud tokens spent**, with unlabeled joint
commits parked as **PENDING** (queued for the owner, never counted into CORRECT or the gate).

Four rigor guards make the run valid (see docs/.../this-repo-is-supposed-mutable-taco.md):

  (a) **Config-consistent bootstrap** — the local edge IS the production single-pass path
      (expand → retrieve → owner-filter → §4.1 covariates), and one ``u_bar``/fold is pinned for
      the whole run (so the assertion floor ``p*`` does not move mid-run).
  (b) **Leave-one-QUESTION-out calibration** — ``calib_local`` is fit on the OTHER questions'
      graded outcomes (one outcome per question, the LOQO unit), ``calib_joint`` cold-starts
      (no joint history yet). At N≈10 the curve is prior-dominated and decision-moot — it is kept
      as the DIAGNOSTIC (the per-question calibrated-lead vs ``p*``), load-bearing only once the
      demand log accrues. The pessimistic prior is never tuned to the gate (frozen-blind).
  (c) **Isolated decision log** — the executor writes an EVAL ``decisions.jsonl`` under
      ``$LIFE_AGENT_KB/eval/exec/``; the live ``calibration/decisions.jsonl`` (which feeds the
      §4.4 reaction fold) is never touched.
  (d) **Honest grading** — confident-wrong is counted only on owner-graded rows; a joint-edge
      commit on an UNLABELED value is PENDING (token-match → confident-wrong is suppressed for the
      joint edge, since token-match manufactures false sins on co-valid unlisted answers).

Output lands under ``$LIFE_AGENT_KB/eval/exec/`` — PII, stays in the KB, never the repo.

    ANTHROPIC_API_KEY=$(secret-tool lookup service env key ANTHROPIC_API_KEY) \\
        uv run --project . python scripts/eval_executor.py [--joint-model M] [--k N] [--limit N]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from answer_labels import Label, load_labels, verdict
from eval_grading import answer_matches, chunk_matches_any
from run_eval import _answer_in_corpus, _kb_root, load_questions
from triage_answers import _lookup_view, _withheld_view
from triage_grading import triage

from life_agent.core import calibration as CAL
from life_agent.core import executor as EX
from life_agent.core import joint_extract as JE
from life_agent.core import lookup as LK

# the executor's strongest tier by default — the q-002 attribution showcase wants the best
# subject reasoning; --joint-model trades it down (haiku/sonnet) for a cheaper sweep.
DEFAULT_JOINT_MODEL = "claude-opus-4-8"


# --- (a) the production single-pass local path, mirrored for config consistency ----------


def _context(conn, root, ask, question: str, k: int, *, profile: str):
    """Mirror ``ask.answer``'s single-pass lookup path so the local edge calibrates on the same
    distribution it decides on: expand → retrieve → owner-filter → §4.1 covariates (no temporal,
    no gather, no rerank — those are separate edges). Returns ``(hits, cards, scores, cov)``."""
    terms = ask._expand_terms(question, root=root)
    query = ask.build_query(question, terms)
    hits = ask._retrieve_set(conn, query, k)
    subject_state: dict[str, str] = {}
    if ask.owner_question(question):
        hits, _report, subject_state = ask._apply_subject_to_hits(
            conn, root, hits, profile=profile)
    pairs = ask._cards_from_set(hits)
    cards = [c for c, _ in pairs]
    scores = {c.n: s for c, s in pairs}
    hit_keys = list(dict.fromkeys(h["artifact_cache_key"] for h in hits))
    date_of = {d.artifact_cache_key: (d.date.isoformat() if d.date is not None else None)
               for d in ask.T.project_dates(conn, root, hit_keys, caller="eval.executor")}
    return hits, cards, scores, LK.HitCovariates(subject_state=subject_state, doc_date=date_of)


def _local_pass(conn, root, ask, questions: list[dict], k: int, *, profile: str,
                eval_log: Path) -> dict[str, tuple]:
    """Run the production local edge once per question (isolated log). The result feeds BOTH the
    calibration bootstrap and the executor pass (so local is not re-run / re-logged)."""
    ctx: dict[str, tuple] = {}
    for q in questions:
        hits, cards, scores, cov = _context(conn, root, ask, q["question"], k, profile=profile)
        lk = LK.lookup_answer(root, q["question"], hits, covariates=cov,
                              decisions_path=eval_log, run_id="eval-exec-local")
        ctx[q["id"]] = (lk, hits, cards, scores, cov)
    return ctx


# --- (b) the leave-one-question-out calibration bootstrap --------------------------------


def _bootstrap(ctx: dict[str, tuple], labels: list[Label]) -> dict[str, CAL.EdgeOutcome]:
    """One local ``EdgeOutcome`` per question (the LOQO unit): the local commit's top value
    joined to the owner verdict. ``correct`` iff the verdict is "correct" — a stale OR a wrong
    answer both fold False (a stale answer is still wrong for a current-value question).
    Questions where local did not commit, or whose commit is unlabeled, contribute nothing."""
    out: dict[str, CAL.EdgeOutcome] = {}
    for qid, (lk, *_rest) in ctx.items():
        if lk is None or not EX.committed(lk.action) or not lk.credences:
            continue
        value = lk.candidates[0] if lk.candidates else ""
        v = verdict(labels, qid, value)
        if v is None:
            continue
        out[qid] = CAL.EdgeOutcome(edge="local", confidence=lk.credences[0],
                                   correct=(v == "correct"))
    return out


def _calib_local_loqo(bootstrap: dict[str, CAL.EdgeOutcome], held_out: str) -> CAL.ReliabilityCurve:
    """``calib_local`` fit on every question EXCEPT ``held_out`` — leave-one-question-out, so a
    question is never graded by a curve that saw its own outcome."""
    others = [CAL.Outcome(o.confidence, o.correct)
              for qid, o in bootstrap.items() if qid != held_out]
    return CAL.fit_reliability_curve(others)


# --- the executor pass + (d) honest grading ----------------------------------------------


def _grade(conn, ask, q: dict, res: EX.ExecutorResult, lk_local, cards, p_star: float,
           cal_lead: float, labels: list[Label]) -> dict:
    """Build one graded packet from the executor's committed answer. Confident-wrong counts only
    on owner-graded rows; a joint-edge commit on an unlabeled value is PENDING (suppressing the
    token-match → confident-wrong fallback that would falsely sin a co-valid unlisted answer)."""
    gold = q.get("answer", "")
    variants = q.get("answer_variants", [])
    distractors = q.get("distractors", []) if q.get("subject", "n/a") != "n/a" else []
    answerable = bool(gold)
    lk = res.result
    view = _lookup_view(lk) if lk is not None else _withheld_view()

    retrieved_texts = [c.text for c in cards]
    gold_in_topk = answerable and chunk_matches_any(gold, variants, retrieved_texts)
    gold_in_corpus = gold_in_topk or (answerable and _answer_in_corpus(conn, gold, variants))
    gold_in_candidates = answerable and any(
        answer_matches(gold, variants, c) for c in view["candidates"])
    asserted_correct = answerable and any(
        answer_matches(gold, variants, a) for a in view["asserted_values"])
    asserted_distractor = any(
        answer_matches(d, [], a) for d in distractors for a in view["asserted_values"])
    asserted_verdict = next(
        (v for a in view["asserted_values"] if (v := verdict(labels, q["id"], a)) is not None),
        None)

    pending = res.edge == "joint" and view["asserted"] and asserted_verdict is None
    if pending:
        bucket, cause, needs = "PENDING_JUDGMENT", "joint_unlabeled", True
    else:
        t = triage(answerable=answerable, asserted=view["asserted"],
                   asserted_correct=asserted_correct, asserted_distractor=asserted_distractor,
                   gold_in_candidates=gold_in_candidates, gold_in_topk=gold_in_topk,
                   gold_in_corpus=gold_in_corpus, scoped=view.get("scoped", False),
                   asserted_verdict=asserted_verdict)
        bucket, cause, needs = t.bucket, t.cause, t.needs_judgment

    return {
        "id": q["id"], "question": q["question"], "subject": q.get("subject", "n/a"),
        "answerable": answerable, "gold": gold,
        "edge": res.edge, "cloud_tokens": res.cloud_tokens,
        "bucket": bucket, "cause": cause, "needs_judgment": needs, "pending": bool(pending),
        "owner_graded": asserted_verdict is not None, "asserted_verdict": asserted_verdict,
        "owner_scoped": ask.owner_question(q["question"]),
        "p_star": round(p_star, 4), "calibrated_lead": round(cal_lead, 4),
        "local_action": lk_local.action if lk_local is not None else None,
        "local_cred": (round(lk_local.credences[0], 4)
                       if lk_local is not None and lk_local.credences else None),
        "asserted_values": view["asserted_values"], "action": view["action"],
        "rendered": (lk.rendered[:240].replace("\n", " ") if lk is not None else ""),
        "channel": {
            "gold_in_topk": bool(gold_in_topk), "gold_in_corpus": bool(gold_in_corpus),
            "gold_in_candidates": bool(gold_in_candidates),
            "asserted_correct": bool(asserted_correct),
            "asserted_distractor": bool(asserted_distractor)},
        "origin": (Path(cards[0].origin).name if cards else ""),
    }


def _executor_pass(conn, root, ask, questions: list[dict], ctx: dict[str, tuple],
                   bootstrap: dict[str, CAL.EdgeOutcome], labels: list[Label], *,
                   joint_model: str, k: int, u_bar: dict[str, float],
                   eval_log: Path) -> list[dict]:
    p_star = EX.p_star(u_bar)
    calib_joint = CAL.curve_for({}, "joint")  # cold-start: no joint history yet (pessimistic)
    packets: list[dict] = []
    for q in questions:
        qid = q["id"]
        lk0, hits, cards, _scores, _cov = ctx[qid]
        calib_local = _calib_local_loqo(bootstrap, qid)
        cal_lead = EX.calibrated_lead(lk0, calib_local) if (
            lk0 is not None and lk0.credences) else 0.0
        try:
            res = EX.answer_question(
                owner_scoped=ask.owner_question(q["question"]), u_bar=u_bar,
                calib_local=calib_local, calib_joint=calib_joint,
                local_fn=lambda lk0=lk0: lk0,
                joint_extract_fn=lambda q=q, hits=hits: JE.extract_joint(
                    root, q["question"], hits, model=joint_model, k=k),
                joint_decide_fn=lambda jr, construct, q=q, hits=hits: EX.decide_joint(
                    root, q["question"], construct, jr, calib_joint, n_hits=len(hits),
                    decisions_path=eval_log, run_id="eval-exec-joint"))
        except Exception as e:  # one bad cloud call must not kill the run — name it, move on
            print(f"  {qid}: ERROR {e}")
            packets.append({"id": qid, "question": q["question"], "edge": "error",
                            "error": str(e), "bucket": "ERROR", "cause": None,
                            "answerable": bool(q.get("answer", "")), "cloud_tokens": 0,
                            "pending": False, "owner_graded": False})
            continue
        p = _grade(conn, ask, q, res, lk0, cards, p_star, cal_lead, labels)
        packets.append(p)
        tag = " ⏳" if p["pending"] else (" ☁" if p["cloud_tokens"] else "")
        print(f"  {qid}: {p['edge']} → {p['bucket']}"
              + (f"/{p['cause']}" if p["cause"] else "") + tag)
    return packets


# --- reporting ---------------------------------------------------------------------------


def render_report(packets: list[dict], *, joint_model: str, k: int, p_star: float,
                  elapsed: float) -> str:
    answerable = [p for p in packets if p.get("answerable")]
    correct = [p for p in packets if p["bucket"] == "CORRECT"]
    real_cw = [p for p in packets if p["bucket"] == "CONFIDENT_WRONG" and p.get("owner_graded")]
    token_cw = [p for p in packets
                if p["bucket"] == "CONFIDENT_WRONG" and not p.get("owner_graded")]
    pending = [p for p in packets if p.get("pending")]
    errors = [p for p in packets if p["bucket"] == "ERROR"]
    edges = Counter(p["edge"] for p in packets)
    total_cloud = sum(p.get("cloud_tokens", 0) for p in packets)
    mean_cloud = total_cloud / len(packets) if packets else 0.0
    zero_cloud = [p for p in packets if not p.get("cloud_tokens")]

    lines = [
        "# Answer-executor measurement — correct at zero owner-graded confident-wrong",
        "",
        f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}   joint-model={joint_model}   "
        f"k={k}   p*={p_star:.3f}   elapsed={elapsed:.1f}s   n={len(packets)}",
        "",
        f"**CORRECT {len(correct)}/{len(answerable)} answerable** · "
        f"**real-CONFIDENT_WRONG {len(real_cw)} (gate: 0)** · "
        f"PENDING {len(pending)} (joint commits queued for the owner) · "
        f"token-CW {len(token_cw)} (unlabeled, needs owner — NOT the gate)"
        + (f" · ERROR {len(errors)}" if errors else ""),
        "",
        f"**Cloud: {total_cloud} tokens** ({mean_cloud:.0f}/question; "
        f"{len(zero_cloud)}/{len(packets)} answered at zero cloud).",
        "",
        "Edges: " + " · ".join(f"{e}={n}" for e, n in sorted(edges.items())),
        "",
        "## Calibrated-lead diagnostic (does the local edge clear the floor on its own?)",
        "",
        "At N≈10 the LOQO curve is prior-dominated — most calibrated leads fall below p*, so the "
        "executor escalates. This table is the evidence, not a knob: the curve earns commit "
        "authority only as the demand log accrues.",
        "",
        "| ID | owner? | local act | local c | calib lead | ≥p*? | edge | cloud | bucket |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for p in packets:
        if p["bucket"] == "ERROR":
            continue
        cl = p.get("calibrated_lead")
        clears = "✓" if (cl is not None and cl >= p_star) else "·"
        lines.append(
            f"| {p['id']} | {'✓' if p.get('owner_scoped') else '·'} "
            f"| {p.get('local_action') or '—'} | {p.get('local_cred')} | {cl} | {clears} "
            f"| {p['edge']} | {p.get('cloud_tokens', 0)} | {p['bucket']} |")

    if pending:
        lines += ["", "## PENDING — joint commits awaiting an owner verdict", "",
                  "Token-match cannot tell a co-valid unlisted answer from a wrong one; the owner "
                  "labels these (then re-run to fold them into calib_joint + the gate).", "",
                  "| ID | value | as_of/render |", "|---|---|---|"]
        for p in pending:
            val = (p["asserted_values"][0] if p["asserted_values"] else "—")[:40]
            lines.append(f"| {p['id']} | {val} | {p['rendered'][:60]} |")

    if real_cw:
        lines += ["", "## ⛔ owner-graded CONFIDENT_WRONG (the gate breach — must be empty)", ""]
        for p in real_cw:
            lines.append(f"- {p['id']} ({p['edge']}): asserted "
                         f"{p['asserted_values']} — owner verdict {p['asserted_verdict']}")
    return "\n".join(lines) + "\n"


def _pending_rows(packets: list[dict], joint_model: str) -> list[dict]:
    """Joint commits awaiting a verdict, in the existing pending_labels.jsonl shape
    (question_id, question, value, source, origin, evidence) so the owner can label them."""
    rows = []
    for p in packets:
        if not p.get("pending"):
            continue
        rows.append({"question_id": p["id"], "question": p["question"],
                     "value": p["asserted_values"][0] if p["asserted_values"] else "",
                     "source": joint_model, "origin": p.get("origin", ""),
                     "evidence": p["rendered"]})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--config",
        default=os.environ.get(
            "PKM_CONFIG", str(Path("~/.config/life-agent/pkm.yaml").expanduser())),
        help="pkm config.yaml (default: $PKM_CONFIG or ~/.config/life-agent/pkm.yaml)")
    parser.add_argument("--joint-model", default=DEFAULT_JOINT_MODEL,
                        help=f"the joint edge's cloud model (default: {DEFAULT_JOINT_MODEL})")
    parser.add_argument("--k", type=int, default=20, help="top-k hits per question")
    parser.add_argument("--limit", type=int, default=0,
                        help="run only the first N questions (0 = all; for a smoke run)")
    parser.add_argument("--only", default="",
                        help="comma-separated question ids to run (e.g. q-002,q-011) — a smoke")
    args = parser.parse_args()

    import duckdb
    import yaml

    questions = load_questions()
    if args.only:
        want = {x.strip() for x in args.only.split(",") if x.strip()}
        questions = [q for q in questions if q["id"] in want]
    if args.limit:
        questions = questions[: args.limit]

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    db_path = Path(cfg["root_dir"]).expanduser() / "catalogue.duckdb"
    conn = duckdb.connect(str(db_path))
    conn.execute("INSTALL fts; LOAD fts;")

    import ask
    root = ask._pkm_root()
    profile = ask.owner.load_profile()

    out_dir = _kb_root() / "eval" / "exec"
    out_dir.mkdir(parents=True, exist_ok=True)
    eval_log = out_dir / "decisions.jsonl"  # (c) isolated — never the live decisions log

    # (a) pin one u_bar / fold for the whole run (p* must not move mid-run)
    u_bar, fold_ver = LK.current_u_bar(LK.shared_brain())
    p_star = EX.p_star(u_bar)
    labels = load_labels(_kb_root() / "eval" / "labels.jsonl")

    print(f"Executor eval: {len(questions)} questions · joint={args.joint_model} · k={args.k} · "
          f"p*={p_star:.3f} · fold={fold_ver[:12]} · {len(labels)} owner label(s)")
    print(f"  isolated decision log → {eval_log}")
    t0 = time.monotonic()

    print("Local pass (config-consistent bootstrap) …")
    ctx = _local_pass(conn, root, ask, questions, args.k, profile=profile, eval_log=eval_log)
    bootstrap = _bootstrap(ctx, labels)
    print(f"  bootstrap: {len(bootstrap)} owner-graded local outcome(s) "
          f"({sum(o.correct for o in bootstrap.values())} correct)")

    print("Executor pass (LOQO calib · joint escalation) …")
    packets = _executor_pass(conn, root, ask, questions, ctx, bootstrap, labels,
                             joint_model=args.joint_model, k=args.k, u_bar=u_bar,
                             eval_log=eval_log)
    elapsed = time.monotonic() - t0

    (out_dir / "packets.jsonl").write_text(
        "".join(json.dumps(p, ensure_ascii=False, sort_keys=True) + "\n" for p in packets),
        encoding="utf-8")
    (out_dir / "report.md").write_text(
        render_report(packets, joint_model=args.joint_model, k=args.k, p_star=p_star,
                      elapsed=elapsed), encoding="utf-8")
    pend = _pending_rows(packets, args.joint_model)
    (out_dir / "pending_joints.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in pend),
        encoding="utf-8")

    correct = sum(1 for p in packets if p["bucket"] == "CORRECT")
    answerable = sum(1 for p in packets if p.get("answerable"))
    real_cw = sum(1 for p in packets
                  if p["bucket"] == "CONFIDENT_WRONG" and p.get("owner_graded"))
    total_cloud = sum(p.get("cloud_tokens", 0) for p in packets)
    print(f"\nExecutor eval → {out_dir}/report.md  (+ packets.jsonl, {len(pend)} pending)")
    print(f"  CORRECT {correct}/{answerable} · real-CONFIDENT_WRONG {real_cw} (gate: 0) · "
          f"PENDING {len(pend)} · cloud {total_cloud} tok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
