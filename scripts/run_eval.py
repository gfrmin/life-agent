#!/usr/bin/env python3
"""Answer-grounded retrieval eval (supersedes run_phase1_eval.py's source-id grading).

Ground truth is the ANSWER (the fact), not a source_id. For each question we check
whether the answer surfaces in a top-k retrieved chunk (token-boundary match, §3 of the
plan), and classify the outcome by MODE:

    PASS            — answer in a top-k chunk
    RETRIEVAL_MISS  — answer is somewhere in the corpus but not in top-k
    ABSENT_COVERAGE — answer nowhere in corpus, source not ingested
    ABSENT_EXTRACTION — answer nowhere in corpus, extraction destroyed it (OCR)
    (ABSENT_UNSPECIFIED if no mode_hint)

SUBJECT_CONFUSION is reported as an ORTHOGONAL flag (set when a distractor — a confusable
wrong-subject value, e.g. the partner's ID — is retrieved in top-k); it is not a verdict.

The question fixture is PII-bearing and lives OUTSIDE this public repo, at
$LIFE_AGENT_KB/eval/questions.yaml (fail-fast if absent). The grading logic is in
scripts/eval_grading.py (unit-tested).

A --synthesis flag runs the end-to-end grader: it synthesises via the production answer
path, audits citations deterministically (citation_guard), and judges faithfulness +
citation_fidelity with the cross-provider LLM judge (modal-of-N) → hallucination /
grounded-answer / abstention-honesty rates in eval/synthesis_log.md.

The synthesis path inherits the ask derivation cache (pkm SPEC §18.9): a re-run against an
unchanged corpus replays every answer from cache (only judge calls spend). Per-stage hit/miss
counters land in the report; --fresh forces recomputation (recording stays write-once).

Every graded question additionally appends one outcome event to the calibration log
($LIFE_AGENT_KB/calibration/outcomes.jsonl — bayesian-foundations §8, the third evidence
stream; append-only, never backfilled; --no-outcomes for dry runs). Retrieval verdicts
grade the selection channel; synthesis verdicts grade the monolithic answer instrument,
with the answer's §18.9 stage cache keys as lineage. No probability is asserted by the
current pipeline, so events are logged for attribution and excluded from proper scoring
until Ask v0 (slice 2) asserts credences.

Usage (run in this monorepo's env for pkm.retrieval + DuckDB):
    uv run --project . python scripts/run_eval.py [--config PATH] [--k N] \
        [--rebuild-index] [--synthesis] [--fresh]
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_grading import answer_matches, chunk_matches_any, classify

# Effectively-unbounded k for the in-corpus set-membership check: we want "does the
# answer appear ANYWHERE", not a ranked top-k, so we take all FTS matches and confirm
# with the token-boundary matcher (specific answers match few chunks; this only runs
# for answers NOT already in top-k, i.e. rare/absent ones).
_MEMBERSHIP_K = 100_000

_JUDGE_N = 3  # modal-of-N judge calls for the synthesis grader (matches the comparison harness)


def _kb_root() -> Path:
    env = os.environ.get("LIFE_AGENT_KB")
    return Path(env).expanduser() if env else Path.home() / ".life-agent/kb"


def load_questions() -> list[dict]:
    """Load the answer-grounded question set from the KB fixture; fail fast if absent
    (it holds PII and is not in this repo). Fills optional-field defaults."""
    import yaml

    fixture = _kb_root() / "eval/questions.yaml"
    if not fixture.exists():
        raise SystemExit(
            f"eval fixture not found: {fixture}\n"
            "It holds PII and lives in $LIFE_AGENT_KB, outside this public repo.\n"
            "Set LIFE_AGENT_KB or create it (schema: life-agent/eval/questions.example.yaml)."
        )
    data = yaml.safe_load(fixture.read_text(encoding="utf-8"))
    questions = data.get("questions") if isinstance(data, dict) else None
    if not questions:
        raise SystemExit(f"no 'questions:' list found in {fixture}")
    for q in questions:
        q.setdefault("subject", "n/a")
        q.setdefault("answer", "")
        q.setdefault("answer_variants", [])
        q.setdefault("distractors", [])
        q.setdefault("fuzzy", False)
        q.setdefault("search_queries", [])
        q.setdefault("mode_hint", None)
        q.setdefault("notes", "")
    return questions


def _answer_in_corpus(conn, answer: str, variants: list[str]) -> bool:
    """Set-membership via the FTS index (not a LIKE scan): search the answer's tokens
    unbounded, then confirm with the token-boundary matcher."""
    from pkm.retrieval import search

    for query in [answer, *variants]:
        if not query:
            continue
        hits = search(conn, query, k=_MEMBERSHIP_K)
        if chunk_matches_any(answer, variants, [h.chunk_text for h in hits]):
            return True
    return False


def grade_retrieval(conn, q: dict, k: int) -> dict:
    """Retrieval-level grade for one question (the active grader today)."""
    from pkm.retrieval import search

    answer = q["answer"]
    variants = q["answer_variants"]
    distractors = q["distractors"] if q["subject"] != "n/a" else []

    # Top-k chunks across all search_queries (union).
    topk_texts: list[str] = []
    top_snippet = ""
    for query in q["search_queries"]:
        for hit in search(conn, query, k=k):
            topk_texts.append(hit.chunk_text)
            if not top_snippet:
                top_snippet = (
                    f"[{hit.score:.2f}] {Path(hit.source_path).name}: "
                    + hit.chunk_text[:70].replace("\n", " ")
                )

    if answer:
        answer_in_topk = chunk_matches_any(answer, variants, topk_texts)
        answer_in_corpus = answer_in_topk or _answer_in_corpus(conn, answer, variants)
    else:
        # known-unanswerable (no ground-truth value) -> ABSENT by construction
        answer_in_topk = answer_in_corpus = False

    distractor_in_topk = any(
        answer_matches(d, [], t) for d in distractors for t in topk_texts
    )

    v = classify(
        answer_in_topk=answer_in_topk,
        answer_in_corpus=answer_in_corpus,
        distractor_in_topk=distractor_in_topk,
        mode_hint=q["mode_hint"],
    )
    return {
        "id": q["id"],
        "question": q["question"],
        "subject": q["subject"],
        "verdict": v.verdict,
        "subject_confusion": v.subject_confusion,
        "top_snippet": top_snippet,
        "notes": q["notes"],
    }


# --- outcome events (bayesian-foundations §8: the calibration log) ----------------------
# Pure builders mapping graded rows to OutcomeEvents (unit-tested without IO). The grade
# vocabularies are validated at construction against life_agent.core.outcomes.GRADERS —
# an unknown verdict is a loud error here, never a silent new category in the log.

def synthesis_grade_label(row: dict) -> str:
    """Pure: one closed grade from the synthesis row's verdict booleans
    (classifier v2 — slice 3 added DECLINED).

    Precedence: ABSTAINED_OK / DECLINED (the production decision was an EU
    abstention — it asserts nothing, so it can neither pass nor hallucinate;
    the first seeding run's judge gave abstentions 3/3 against answerable
    questions, silently counting declines as grounded) > HALLUCINATED >
    PASS > WEAK (answerable, neither grounded nor fabricated)."""
    if row.get("declined"):
        return "DECLINED" if row["answerable"] else "ABSTAINED_OK"
    if row["hallucinated"]:
        return "HALLUCINATED"
    if not row["answerable"] and row["abstained_correctly"]:
        return "ABSTAINED_OK"
    if row["synthesis_pass"]:
        return "PASS"
    return "WEAK"


def retrieval_outcome(r: dict, q: dict, *, k: int, run_id: str):
    """One outcome event from a retrieval-grader row: the selection channel (M2)
    graded — was the true value in the admitted evidence? ABSENT_* grades record
    coverage facts, not instrument errors; the fold differentiates by grade."""
    from life_agent.core import outcomes as O

    return O.OutcomeEvent(
        tx_time=O.now_iso(), run_id=run_id, question_id=str(r["id"]),
        claim=q.get("answer") or "(none — known-unanswerable)",
        construct="selection", grade=r["verdict"], grader="eval_retrieval",
        instrument_identity={"producer_name": "pkm.retrieval.search",
                             "producer_config": {"k": k,
                                                 "queries": "union(search_queries)"}},
    )


def synthesis_outcome(row: dict, *, run_id: str):
    """One outcome event from a synthesis-grader row: the monolithic answer instrument
    graded end-to-end. Lineage is the answer's §18.9 stage cache keys (captured from
    ask.STAGES_LAST by synthesis_grade); the synthesize key pins the exact instrument
    identity — the dict here is the grouping identity, not a duplicate of every key
    component."""
    from life_agent.core import derivations as D
    from life_agent.core import outcomes as O
    from life_agent.core.llm import DEFAULT_ANSWER_MODEL

    return O.OutcomeEvent(
        tx_time=O.now_iso(), run_id=run_id, question_id=str(row["id"]),
        claim=row["answer"],
        construct="grounded-answer", grade=synthesis_grade_label(row),
        grader="eval_synthesis",
        instrument_identity={"producer_name": "life_agent.ask.synthesize",
                             "producer_version": D.SYNTHESIZE_VERSION,
                             "engine_version": D.ENGINE_VERSION,
                             "model": DEFAULT_ANSWER_MODEL},
        lineage_keys=tuple(row.get("lineage_keys", ())),
        # classifier v2 disclosure: pre-v2 events graded answerable abstentions
        # PASS (the 2026-06-13 seeding run) — fold readers can condition on this
        signals={"classifier_version": 2, "declined": bool(row.get("declined"))},
    )


def _append_outcomes(events: list, log_path: Path | None = None) -> Path:
    """Append events to the calibration log (durable, append-only) and report scoring
    when any event asserted a probability (none do until Ask v0 slice 2)."""
    from life_agent.core import OUTCOMES_LOG
    from life_agent.core import outcomes as O

    log = log_path or OUTCOMES_LOG
    for e in events:
        O.append(log, e)
    print(f"Outcomes: {len(events)} appended → {log}")
    pairs = O.scored_pairs(events)
    if pairs:
        s = O.summarize_scores(pairs)
        print(f"  proper scores: n={s.n} mean_log={s.mean_log:.4f} "
              f"mean_brier={s.mean_brier:.4f}")
    return log


def lookup_claim_rows(q: dict, lk) -> list[dict]:
    """Pure: per-claim grading rows for one routed lookup result (foundations §3 —
    every answer is a claim set). Each candidate is the binary claim "V = candidate"
    with its asserted credence; the none-of-the-retrieved atom is the claim "V is not
    among the candidates". Correctness via the shared token-boundary matcher; an
    unanswerable question (no ground-truth value) makes every candidate claim false
    and the none claim true."""
    rows: list[dict] = []
    any_match = False
    for cand, cred in zip(lk.candidates, lk.credences, strict=True):
        correct = bool(q.get("answer")) and answer_matches(
            q["answer"], q.get("answer_variants", []), cand)
        any_match = any_match or correct
        rows.append({"claim": cand, "probability": cred, "correct": correct})
    rows.append({"claim": "(none of the retrieved)", "probability": lk.p_none,
                 "correct": not any_match})
    return rows


def lookup_outcome(q: dict, lk, row: dict, *, run_id: str):
    """One credence-bearing outcome event for one lookup claim — the first events
    proper scoring can consume (probability is set)."""
    from life_agent.core import lookup as LK
    from life_agent.core import outcomes as O

    return O.OutcomeEvent(
        tx_time=O.now_iso(), run_id=run_id, question_id=str(q["id"]),
        claim=str(row["claim"]), construct=str(lk.construct),
        grade="CORRECT" if row["correct"] else "INCORRECT", grader="eval_lookup",
        # the extract hash pins the EXACT instrument these claims grade (§2): a
        # prompt change starts a new reliability posterior, never pooling the old
        instrument_identity={"producer_name": "life_agent.ask.lookup_answer",
                             "extract_prompt_hash": LK.extract_instrument_hash()},
        lineage_keys=(lk.answer_cache_key,),
        probability=float(row["probability"]),
    )


def narrative_claim_rows(q: dict, nv) -> list[dict]:
    """Pure: the gradeable claim rows for one narrative-family result (§7 move 2's
    evidence). Deterministically gradeable claims only: one containing the gold
    answer (token-boundary, variants) grades CORRECT; one containing a wrong-subject
    distractor (and not the gold) grades INCORRECT. Everything else is ungradeable at
    claim level and emits nothing — DISCLOSED selection on the grading channel: the
    stream reaches value-bearing claims, so cells it cannot reach stay at their wide
    priors (narrative.py docstring, move 2)."""
    rows: list[dict] = []
    for c in nv.claims:
        has_gold = bool(q.get("answer")) and answer_matches(
            q["answer"], q.get("answer_variants", []), c.text)
        has_distractor = any(answer_matches(d, [], c.text)
                             for d in (q.get("distractors") or []))
        if not has_gold and not has_distractor:
            continue
        rows.append({"claim": c.text[:200], "probability": c.credence,
                     "correct": has_gold,
                     "signals": {"audit_cell": c.cell, "included": c.included}})
    return rows


def narrative_claim_outcome(q: dict, nv, row: dict, *, run_id: str):
    """One credence-bearing outcome event for one narrative claim — the population
    stream the per-cell Beta fold conditions on (grader ``eval_claim``)."""
    from life_agent.core import narrative as N
    from life_agent.core import outcomes as O

    return O.OutcomeEvent(
        tx_time=O.now_iso(), run_id=run_id, question_id=str(q["id"]),
        claim=str(row["claim"]), construct="claim",
        grade="CORRECT" if row["correct"] else "INCORRECT", grader="eval_claim",
        instrument_identity=N.instrument_identity(),
        lineage_keys=(nv.answer_cache_key,),
        probability=float(row["probability"]),
        signals=dict(row["signals"]),
    )


def coverage_outcome(q: dict, nv, *, run_id: str):
    """One proposal-coverage event (§7 move 3): did the proposal set contain the gold
    claim at all? A MISSED event is an observed proposer miss — the open-world tail's
    evidence. Answerable questions only (None otherwise: nothing to propose)."""
    from life_agent.core import narrative as N
    from life_agent.core import outcomes as O

    if not q.get("answer"):
        return None
    proposed = any(answer_matches(q["answer"], q.get("answer_variants", []), c.text)
                   for c in nv.claims)
    return O.OutcomeEvent(
        tx_time=O.now_iso(), run_id=run_id, question_id=str(q["id"]),
        claim=str(q["answer"]), construct="proposal-coverage",
        grade="PROPOSED" if proposed else "MISSED", grader="eval_coverage",
        instrument_identity=N.instrument_identity(),
        lineage_keys=(nv.answer_cache_key,),
        signals={"n_claims": len(nv.claims)},
    )


# --- the adoption gate (bayesian-foundations §8): typed families vs the monolithic ------
# The grading model lives here (a driver concern); the math + the stated realised-utility
# model live in life_agent.core.gate. Each policy is graded on ONE common answer-grounded
# scale (gold token-containment), so the comparison values them identically.

def _typed_response(lk, nv, typed_text: str, q: dict, abstention: str):
    """The typed policy's realised answer on one question, from the family decisions the
    production path just took (LOOKUP_LAST / NARRATIVE_LAST)."""
    from life_agent.core import gate as GATE

    gold, variants = q.get("answer", ""), q.get("answer_variants", [])
    if lk is not None:
        if lk.action == "report":
            asserted = [lk.candidates[0]] if lk.candidates else []
        elif lk.action == "hedge":
            asserted = list(lk.candidates)
        else:  # abstain | ask_clarify — a withholding
            return GATE.RealisedResponse(action=lk.action, correct=None)
        return GATE.RealisedResponse(
            action=lk.action, correct=GATE.realised_report(asserted, gold, variants))
    if nv is not None:
        if nv.action == "report":
            asserted = [c.text for c in nv.claims if c.included]
            return GATE.RealisedResponse(
                action="report", correct=GATE.realised_report(asserted, gold, variants))
        return GATE.RealisedResponse(action="abstain", correct=None)
    # no family decided: the weak-retrieval abstention (shared with the monolithic) or
    # the family seam disabled — either way the typed path asserted nothing
    return GATE.RealisedResponse(action="abstain", correct=None)


def _monolithic_response(mono_text: str, q: dict, abstention: str):
    """The monolithic instrument's realised answer: the raw synthesize prose, graded by
    the same gold-containment. It abstains only where retrieval is too weak to synthesize
    (the guard it shares with the typed path)."""
    from life_agent.core import gate as GATE

    if mono_text == abstention:
        return GATE.RealisedResponse(action="abstain", correct=None)
    correct = GATE.realised_report([mono_text], q.get("answer", ""),
                                   q.get("answer_variants", []))
    return GATE.RealisedResponse(action="report", correct=correct)


def gate_paired_outcomes(conn, questions: list[dict], k: int, ask) -> list:
    """Run both policies over the corpus and pair their realised answers per question.
    The typed pass IS the production path (ask.answer); the monolithic pass is the same
    path with the typed families switched off (families=False → raw synthesize prose)."""
    from life_agent.core import gate as GATE

    paired = []
    for q in questions:
        typed_text, _, _ = ask.answer(conn, q["question"], k)
        lk, nv = ask.LOOKUP_LAST, ask.NARRATIVE_LAST  # capture before the next call resets
        typed = _typed_response(lk, nv, typed_text, q, ask.ABSTENTION)
        mono_text, _, _ = ask.answer(conn, q["question"], k, families=False)
        mono = _monolithic_response(mono_text, q, ask.ABSTENTION)
        answerable = bool(q.get("answerable", bool(q.get("answer"))))
        paired.append(GATE.PairedOutcome(
            question_id=str(q["id"]), answerable=answerable, typed=typed, mono=mono))
        tmark = "·" if not typed.asserts() else ("✓" if typed.correct else "✗")
        mmark = "·" if not mono.asserts() else ("✓" if mono.correct else "✗")
        print(f"  {q['id']}: typed {tmark}{typed.action[:6]:<6} "
              f"mono {mmark}{mono.action[:6]}")
    return paired


def _paired_to_dict(p) -> dict:
    return {"question_id": p.question_id, "answerable": p.answerable,
            "typed": {"action": p.typed.action, "correct": p.typed.correct},
            "mono": {"action": p.mono.action, "correct": p.mono.correct}}


def format_lookup_report(rows: list[dict], k: int, elapsed: float) -> str:
    n_routed = sum(1 for r in rows if r["routed"])
    actions = Counter(r["action"] for r in rows if r["routed"])
    reports = [r for r in rows if r["action"] == "report"]
    n_report_correct = sum(1 for r in reports if r["top_correct"])
    lines = [
        "# Lookup-family eval log (Ask v0 — credence-bearing claims)",
        "",
        f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}   k={k}   elapsed={elapsed:.1f}s",
        "",
        f"Routed to lookup: {n_routed}/{len(rows)}   actions: "
        + " · ".join(f"{a}={c}" for a, c in sorted(actions.items())),
        f"Report accuracy: {n_report_correct}/{len(reports)} top candidates correct.",
        "",
        "| ID | action | top candidate | p | correct | Q |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        if not r["routed"]:
            lines.append(f"| {r['id']} | narrative | — | — | — | {r['question'][:44]} |")
            continue
        ok = {True: "✓", False: "✗", None: "—"}[r["top_correct"]]
        lines.append(f"| {r['id']} | {r['action']} | {r['top'][:28]} | {r['top_p']:.2f} "
                     f"| {ok} | {r['question'][:44]} |")
    return "\n".join(lines) + "\n"


# --- synthesis grader (end-to-end: the advertisable hallucination-rate number) ----------
# Grades the PRODUCTION answer path (ask.answer) with two instruments: a deterministic
# citation audit (citation_guard, no LLM) + a single-answer cross-provider LLM judge
# (faithfulness + citation_fidelity, modal-of-N) reusing the blind-judge infra. The pure
# classification + rate math are split out so they are unit-tested without any API call.

def _classify_synthesis(*, faithfulness: int, citation_fidelity: int,
                        structural_unsupported: bool, answerable: bool,
                        declined: bool = False) -> dict:
    """Pure: map modal judge scores + the deterministic audit to verdict booleans
    (classifier v2).

    - declined: the production path's EU decision was an abstention (lookup or
      narrative). A decline asserts NOTHING: it cannot pass and it cannot
      hallucinate — the judge's scores against an abstention render are noise
      (the seeding run produced both 3/3 "PASS" and a cite=0 "HALLUCINATED" for
      abstentions), so the deterministic decision verdict overrides the judge.
    - synthesis_pass: faithfulness>=2 AND citation_fidelity>=2 AND not declined.
    - hallucinated: a fabricated / wrong-subject / mis-cited assertion — faithfulness<=1, OR
      citation_fidelity==0, OR the deterministic guard found an unsupported verbatim citation.
    - abstained_correctly (unanswerable only): declining IS the correct response;
      otherwise the judge's honesty read (faithfulness>=2) stands."""
    return {
        "declined": declined,
        "synthesis_pass": faithfulness >= 2 and citation_fidelity >= 2 and not declined,
        "hallucinated": (not declined) and (
            faithfulness <= 1 or citation_fidelity == 0 or structural_unsupported),
        "abstained_correctly": (not answerable) and (declined or faithfulness >= 2),
    }


def synthesis_rates(rows: list[dict]) -> dict:
    """Pure: the headline reliability numbers from a list of graded rows. A declined
    answerable question is its own bucket (classifier v2): never grounded, never a
    hallucination — the EU layer choosing silence is a measured behaviour, not a
    pass."""
    answerable = [r for r in rows if r["answerable"]]
    unanswerable = [r for r in rows if not r["answerable"]]
    declined = [r for r in answerable if r.get("declined")]
    grounded = [r for r in answerable if r["synthesis_pass"]]
    hallucinated = [r for r in rows if r["hallucinated"]]
    honest = [r for r in unanswerable if r["abstained_correctly"]]

    def _rate(a: list, b: list) -> float | None:
        return (len(a) / len(b)) if b else None

    return {
        "n": len(rows),
        "n_answerable": len(answerable), "n_unanswerable": len(unanswerable),
        "n_grounded": len(grounded), "n_hallucinated": len(hallucinated),
        "n_honest": len(honest), "n_declined": len(declined),
        "grounded_rate": _rate(grounded, answerable),
        "hallucination_rate": _rate(hallucinated, rows),
        "abstention_honesty": _rate(honest, unanswerable),
        "declined_rate": _rate(declined, answerable),
    }


def _synthesis_judge_once(q: dict, answer_text: str, sources: list[dict], rubric_text: str):
    """One single-answer judge call -> {faithfulness, citation_fidelity, _served} or None.
    Reuses the cross-provider judge (_common.judge_complete) and the frozen rubric."""
    import json

    sys.path.insert(0, str(Path(__file__).resolve().parent / "comparison"))
    import _common as JC

    src_block = "\n\n".join(f"[{s['n']}] {s['text']}" for s in sources) or "(no sources cited)"
    system = (
        "You are an impartial grader of ONE answer to a question about a person's own records. "
        "You are given the answer and the SOURCE TEXTS it cited (as [n]). Judge ONLY from what is "
        "shown. For citation_fidelity you MUST check the cited source text actually contains the "
        "asserted fact. Asserting a listed wrong-subject distractor caps faithfulness at 1. A "
        "correct 'not in the corpus' for a truly-absent fact is full marks. Return STRICT JSON "
        'only: {"faithfulness":int,"citation_fidelity":int}.\n\n' + rubric_text
    )
    user = (
        f"QUESTION: {q['question']}\n"
        f"CANONICAL ANSWER: {q.get('answer') or '(no single value)'}   "
        f"ACCEPTABLE VARIANTS: {q.get('answer_variants') or '[]'}\n"
        f"MUST-NOT-ASSERT (wrong-subject distractors): {q.get('distractors') or '[]'}\n"
        f"ANSWERABLE FROM CORPUS: {q.get('answerable', bool(q.get('answer')))}\n\n"
        f"ANSWER:\n{answer_text}\n\nCITED SOURCES:\n{src_block}\n"
    )
    r = JC.judge_complete(system, user, max_tokens=200)
    txt = r.text.strip()
    if txt.startswith("```"):
        txt = txt.strip("`").split("\n", 1)[-1].rsplit("```", 1)[0]
    try:
        obj = json.loads(txt[txt.index("{"): txt.rindex("}") + 1])
        return {"faithfulness": int(obj["faithfulness"]),
                "citation_fidelity": int(obj["citation_fidelity"]),
                "_served": r.served_model}
    except (ValueError, KeyError, TypeError):
        return None


def synthesis_grade(conn, q: dict, k: int, *, fresh: bool = False) -> dict:
    """End-to-end grade for one question: synthesise via the production path, audit citations
    deterministically, then judge (modal-of-N). Returns a row consumed by ``synthesis_rates``.
    ``fresh`` bypasses the ask derivation cache (recomputes; never overwrites)."""
    here = str(Path(__file__).resolve().parent)
    sys.path.insert(0, here)
    sys.path.insert(0, str(Path(__file__).resolve().parent / "comparison"))
    import ask
    import citation_guard
    from blind_judge import _rubric_text, modal

    text, cards, _ = ask.answer(conn, q["question"], k, no_cache=fresh)
    # §18.9 stage cache keys of THIS answer (outcome lineage; empty on the pre-key paths)
    lineage_keys = tuple(ask.STAGES_LAST[s] for s in ("retrieve", "synthesize")
                         if s in ask.STAGES_LAST)
    nv = ask.NARRATIVE_LAST  # the §7 claim set behind this answer (None off-path)
    lk = ask.LOOKUP_LAST
    # the production path's own decision: an EU abstention asserts nothing — the
    # deterministic decline verdict, not the judge, classifies it (classifier v2)
    declined = ((nv is not None and nv.action == "abstain")
                or (lk is not None and lk.action in ("abstain", "ask_clarify")))
    sources = [{"n": c.n, "text": c.text} for c in cards]
    audit = citation_guard.audit(text, cards)
    rubric = _rubric_text()

    faith: list[int] = []
    cite: list[int] = []
    served: set[str] = set()
    for _ in range(_JUDGE_N):
        j = _synthesis_judge_once(q, text, sources, rubric)
        if not j:
            continue
        faith.append(j["faithfulness"])
        cite.append(j["citation_fidelity"])
        served.add(j["_served"])

    f_modal, c_modal = modal(faith), modal(cite)
    answerable = bool(q.get("answerable", bool(q.get("answer"))))
    verdict = _classify_synthesis(
        faithfulness=f_modal, citation_fidelity=c_modal,
        structural_unsupported=bool(audit.unsupported), answerable=answerable,
        declined=declined,
    )
    return {
        "id": q["id"], "question": q["question"], "answerable": answerable,
        "faithfulness": f_modal, "citation_fidelity": c_modal, "structural_ok": audit.ok,
        "answer": text[:140].replace("\n", " "), "served": sorted(served),
        "lineage_keys": lineage_keys, "_nv": nv, **verdict,
    }


def _cache_line(cache: dict[str, int]) -> str:
    """One line of per-stage derivation-cache hit rates for the report ('' when empty)."""
    if not cache:
        return ""
    parts = []
    for stage in ("expand", "retrieve", "synthesize"):
        hits = cache.get(f"{stage}.hit", 0)
        total = hits + cache.get(f"{stage}.miss", 0)
        if total:
            parts.append(f"{stage} {hits}/{total}")
    return f"Derivation cache hits: {' · '.join(parts)}" if parts else ""


def format_synthesis_report(rows: list[dict], rates: dict, k: int, elapsed: float,
                            cache: dict[str, int] | None = None) -> str:
    def _pct(x: float | None) -> str:
        return "n/a" if x is None else f"{100 * x:.0f}%"

    lines = [
        "# Synthesis eval log (end-to-end: grounded + hallucination rate)",
        "",
        f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}   k={k}   elapsed={elapsed:.1f}s   "
        f"judge=modal-of-{_JUDGE_N}",
        *([cl, ""] if (cl := _cache_line(cache or {})) else [""]),
        f"**Hallucination rate: {_pct(rates['hallucination_rate'])}** "
        f"({rates['n_hallucinated']}/{rates['n']} answers fabricated / wrong-subject / mis-cited).",
        f"**Grounded-answer rate: {_pct(rates['grounded_rate'])}** "
        f"({rates['n_grounded']}/{rates['n_answerable']} answerable questions).",
        f"**Declined (EU abstention on answerable): {_pct(rates.get('declined_rate'))}** "
        f"({rates.get('n_declined', 0)}/{rates['n_answerable']}).",
        f"**Abstention-honesty: {_pct(rates['abstention_honesty'])}** "
        f"({rates['n_honest']}/{rates['n_unanswerable']} known-unanswerable questions).",
        "",
        "Every emitted *verbatim* fact is additionally verified at answer time to appear in its "
        "cited source (deterministic citation guard); the rates above are the LLM-judge measure of "
        "semantic faithfulness.",
        "",
        "| ID | faith | cite | struct | verdict | Q |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        v = synthesis_grade_label(r)
        struct = "ok" if r["structural_ok"] else "⚠"
        lines.append(f"| {r['id']} | {r['faithfulness']} | {r['citation_fidelity']} | {struct} "
                     f"| {v} | {r['question'][:48]} |")
    return "\n".join(lines) + "\n"


def format_report(results: list[dict], k: int, elapsed: float) -> str:
    counts = Counter(r["verdict"] for r in results)
    in_corpus = [r for r in results if r["verdict"] in ("PASS", "RETRIEVAL_MISS")]
    n_pass = counts["PASS"]
    n_confused = sum(1 for r in results if r["subject_confusion"])

    lines = [
        "# Eval log (answer-grounded)",
        "",
        f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}   k={k}   elapsed={elapsed:.1f}s",
        "",
        f"**Retrieval: {n_pass}/{len(in_corpus)} of in-corpus answers surfaced in top-k.**",
        "",
        "Failure modes (by count):",
        f"- PASS: {counts['PASS']}",
        f"- RETRIEVAL_MISS (in corpus, not top-k): {counts['RETRIEVAL_MISS']}",
        f"- ABSENT_COVERAGE (not ingested): {counts['ABSENT_COVERAGE']}",
        f"- ABSENT_EXTRACTION (OCR destroyed): {counts['ABSENT_EXTRACTION']}",
        f"- ABSENT_UNSPECIFIED: {counts['ABSENT_UNSPECIFIED']}",
        f"- SUBJECT_CONFUSION flagged (orthogonal): {n_confused}",
        "",
        "| ID | Verdict | Subj | Conf | Question |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        conf = "⚠" if r["subject_confusion"] else ""
        lines.append(
            f"| {r['id']} | {r['verdict']} | {r['subject']} | {conf} | {r['question'][:54]} |"
        )
    lines += ["", "## Details", ""]
    for r in results:
        lines.append(f"### {r['id']} — {r['verdict']}"
                     + ("  (SUBJECT_CONFUSION)" if r["subject_confusion"] else ""))
        lines.append(f"**Q:** {r['question']}")
        lines.append(f"**Notes:** {r['notes']}")
        if r["top_snippet"]:
            lines.append(f"**Top hit:** {r['top_snippet']}")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default=os.environ.get(
            "PKM_CONFIG", str(Path("~/.config/life-agent/pkm.yaml").expanduser())),
        help="pkm config.yaml (default: $PKM_CONFIG or ~/.config/life-agent/pkm.yaml)",
    )
    parser.add_argument("--k", type=int, default=20, help="top-k per query")
    parser.add_argument("--rebuild-index", action="store_true", help="rebuild FTS first")
    parser.add_argument(
        "--synthesis", action="store_true",
        help=(
            "run the end-to-end synthesis grader (LLM judge) → "
            "hallucination/grounded/abstention rates"
        ),
    )
    parser.add_argument(
        "--fresh", action="store_true",
        help="bypass the ask derivation cache: recompute every answer "
             "(recording stays write-once — existing derivations stand)",
    )
    parser.add_argument(
        "--lookup", action="store_true",
        help="run the lookup-family eval: route every question through the production "
             "answer path, grade the typed family's credence-bearing claims, and "
             "report proper scores (log/Brier) — the first calibrated numbers",
    )
    parser.add_argument(
        "--gate", action="store_true",
        help="run the decision-weighted adoption gate (bayesian-foundations §8): the "
             "typed families vs the monolithic instrument over the corpus, P(Δ>δ) "
             "integrated over the utility posterior → eval/gate/{report.md,paired.jsonl}",
    )
    parser.add_argument(
        "--no-outcomes", action="store_true",
        help="skip appending graded outcomes to the calibration log "
             "($LIFE_AGENT_KB/calibration/outcomes.jsonl) — dry runs only; the log "
             "is append-only evidence and cannot be backfilled",
    )
    args = parser.parse_args()

    import duckdb
    import yaml

    questions = load_questions()
    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    db_path = Path(cfg["root_dir"]).expanduser() / "catalogue.duckdb"
    conn = duckdb.connect(str(db_path))
    conn.execute("INSTALL fts; LOAD fts;")

    if args.rebuild_index:
        from pkm.retrieval import build_fts_index
        print("Building FTS index …")
        build_fts_index(conn)

    if args.gate:
        import json

        from life_agent.core import config as LCFG
        from life_agent.core import gate as GATE
        from life_agent.core import lookup as LK
        from life_agent.core import utility as UT

        print(f"Running the adoption gate (k={args.k}) over {len(questions)} questions "
              f"(both policies; the typed pass is the production path, the monolithic "
              f"pass switches the families off) …")
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import ask

        t0 = time.monotonic()
        run_id = f"gate-{datetime.now().strftime('%Y%m%dT%H%M%S')}"
        paired = gate_paired_outcomes(conn, questions, args.k, ask)

        # the FULL utility posterior (marginals, not just Ū — the gate samples P(U)),
        # folded from the FROZEN model + elicitations (blind discipline: untouched here)
        brain = LK.shared_brain()
        model = UT.load_model(LCFG.UTILITY_MODEL)
        evidence = list(UT.load_elicitations(LCFG.UTILITY_ELICITATIONS, model))
        post = UT.posterior(brain, model, evidence)
        for warning in post.endpoint_warnings(model.endpoint_mass_warn):
            print(f"  ⚠ {warning}")

        result = GATE.delta_posterior(paired, post, oracle_p=LK._ORACLE_P)
        elapsed = time.monotonic() - t0

        gate_dir = _kb_root() / "eval" / "gate"
        gate_dir.mkdir(parents=True, exist_ok=True)
        (gate_dir / "report.md").write_text(
            GATE.render_report(result, run_id=run_id, elapsed=elapsed), encoding="utf-8")
        (gate_dir / "paired.jsonl").write_text(
            "".join(json.dumps(_paired_to_dict(p), sort_keys=True) + "\n"
                    for p in paired), encoding="utf-8")
        print(f"\nGate report → {gate_dir / 'report.md'}")
        verdict = "PASS" if result.passed else "FAIL"
        print(f"  verdict {verdict} · P(Δ>{result.materiality_delta})="
              f"{result.p_delta_gt:.3f} (gate ≥ {result.level:.2f}) · "
              f"Δ̄={result.delta_mean:+.3f} "
              f"[{result.delta_lo:+.3f}, {result.delta_hi:+.3f}]")
        d = result.diagnostics
        ar = lambda x: "n/a" if x is None else f"{x:.2f}"  # noqa: E731
        print(f"  answer rate: typed {ar(d.typed_answer_rate)} · "
              f"mono {ar(d.mono_answer_rate)} · disagreement {d.disagreement_n}/{d.n}")
        # the gate reads evidence; it makes no graded claims and logs no decisions
        return 0 if result.passed else 1

    if args.lookup:
        print(f"Running lookup-family eval (k={args.k}) over {len(questions)} questions "
              f"(production answer path; route + extraction cached, so re-runs are "
              f"near-free) …")
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import ask

        t0 = time.monotonic()
        run_id = f"eval-lookup-{datetime.now().strftime('%Y%m%dT%H%M%S')}"
        rows: list[dict] = []
        events: list = []
        for q in questions:
            ask.answer(conn, q["question"], args.k)
            lk = ask.LOOKUP_LAST
            if lk is None:
                rows.append({"id": q["id"], "question": q["question"],
                             "routed": False, "action": None, "top": "",
                             "top_p": 0.0, "top_correct": None})
                print(f"  · {q['id']}: narrative")
                continue
            claim_rows = lookup_claim_rows(q, lk)
            events.extend(lookup_outcome(q, lk, row, run_id=run_id)
                          for row in claim_rows)
            top = lk.candidates[0] if lk.candidates else "(none)"
            top_correct = claim_rows[0]["correct"] if lk.candidates else None
            rows.append({"id": q["id"], "question": q["question"], "routed": True,
                         "action": lk.action, "top": top,
                         "top_p": lk.credences[0] if lk.credences else 0.0,
                         "top_correct": top_correct})
            mark = "✓" if top_correct else "✗"
            print(f"  {mark} {q['id']}: {lk.action} — {top[:36]!r} "
                  f"p={rows[-1]['top_p']:.2f}")
        elapsed = time.monotonic() - t0

        out = _kb_root() / "eval/lookup_log.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(format_lookup_report(rows, args.k, elapsed), encoding="utf-8")
        print(f"\nLookup report → {out}")
        if not args.no_outcomes and events:
            _append_outcomes(events)
        n_routed = sum(1 for r in rows if r["routed"])
        reports = [r for r in rows if r["action"] == "report"]
        print(f"  routed {n_routed}/{len(rows)} · report accuracy "
              f"{sum(1 for r in reports if r['top_correct'])}/{len(reports)}")
        return 0

    if args.synthesis:
        import json

        print(f"Running synthesis grader (k={args.k}) over {len(questions)} questions "
              f"(production answer path + deterministic citation audit + modal-of-{_JUDGE_N} "
              f"LLM judge) …")
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import ask

        ask.reset_cache_stats()
        t0 = time.monotonic()
        rows = [synthesis_grade(conn, q, args.k, fresh=args.fresh) for q in questions]
        elapsed = time.monotonic() - t0
        rates = synthesis_rates(rows)
        cache = ask.cache_stats()

        out = _kb_root() / "eval/synthesis_log.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(format_synthesis_report(rows, rates, args.k, elapsed, cache),
                       encoding="utf-8")

        sys.path.insert(0, str(Path(__file__).resolve().parent / "comparison"))
        import _common as JC
        served = sorted({s for r in rows for s in r["served"]})
        (_kb_root() / "eval/judge_meta.json").write_text(
            json.dumps({"judge_model": JC.JUDGE_MODEL, "served": served, "n_modal": _JUDGE_N,
                        "rubric": "rubric_v1.yaml"}, indent=2), encoding="utf-8")

        print(f"\nSynthesis report → {out}")
        print(f"  hallucination-rate={rates['hallucination_rate']}  "
              f"grounded-rate={rates['grounded_rate']}  "
              f"abstention-honesty={rates['abstention_honesty']}")
        if (cl := _cache_line(cache)):
            print(f"  {cl}")

        if not args.no_outcomes:
            run_id = f"eval-synthesis-{datetime.now().strftime('%Y%m%dT%H%M%S')}"
            events = [synthesis_outcome(row, run_id=run_id) for row in rows]
            # §7 slice 3: the claim-level + proposal-coverage streams (the narrative
            # family's population and open-world-tail evidence — §8 grader 1)
            n_claim = n_cov = 0
            for q, row in zip(questions, rows, strict=True):
                nv = row.get("_nv")
                if nv is None:
                    continue
                for crow in narrative_claim_rows(q, nv):
                    events.append(narrative_claim_outcome(q, nv, crow, run_id=run_id))
                    n_claim += 1
                cov = coverage_outcome(q, nv, run_id=run_id)
                if cov is not None:
                    events.append(cov)
                    n_cov += 1
            print(f"  narrative streams: {n_claim} claim events · {n_cov} coverage events")
            _append_outcomes(events)
        return 0 if (rates["hallucination_rate"] or 0.0) == 0.0 else 1

    print(f"Running answer-grounded eval (k={args.k}) over {len(questions)} questions …")
    t0 = time.monotonic()
    results = [grade_retrieval(conn, q, args.k) for q in questions]
    elapsed = time.monotonic() - t0

    report = format_report(results, args.k, elapsed)
    out = _kb_root() / "eval/eval_log.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")
    print(f"\nReport written to {out}\n")

    if not args.no_outcomes:
        run_id = f"eval-retrieval-{datetime.now().strftime('%Y%m%dT%H%M%S')}"
        _append_outcomes([retrieval_outcome(r, q, k=args.k, run_id=run_id)
                          for r, q in zip(results, questions, strict=True)])

    # stdout summary
    counts = Counter(r["verdict"] for r in results)
    in_corpus = counts["PASS"] + counts["RETRIEVAL_MISS"]
    print(f"Retrieval: {counts['PASS']}/{in_corpus} in-corpus answers in top-k")
    for r in results:
        mark = {"PASS": "✓"}.get(r["verdict"], "·")
        conf = " ⚠CONFUSION" if r["subject_confusion"] else ""
        print(f"  {mark} {r['id']} [{r['verdict']}]{conf}: {r['question'][:52]}")
    return 0 if counts["PASS"] >= 1 else 1


if __name__ == "__main__":
    sys.exit(main())
