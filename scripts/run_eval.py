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
from datetime import UTC, datetime
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


def load_questions(path: Path | str | None = None) -> list[dict]:
    """Load an answer-grounded question set; fail fast if absent (every corpus holds
    PII and lives in $LIFE_AGENT_KB, never in this repo). Fills optional-field defaults.

    ``path`` selects an alternate corpus (e.g. the factory's ``questions_v2.yaml``);
    the default remains the owner-authored ``$LIFE_AGENT_KB/eval/questions.yaml``."""
    import yaml

    fixture = Path(path).expanduser() if path is not None else _kb_root() / "eval/questions.yaml"
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

    # Top-k chunks across all search_queries (union). Corpora without authored
    # search_queries (the factory's questions_v2.yaml emits none) fall back to the
    # question text itself — otherwise topk stays empty and PASS is structurally
    # unreachable, misreporting the corpus as total retrieval failure. No-op for the
    # v1 corpus (every question authors its queries).
    topk_texts: list[str] = []
    top_snippet = ""
    for query in q["search_queries"] or [q["question"]]:
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
    import life_agent.core.outcomes as O

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
    import life_agent.core.derivations as D
    import life_agent.core.outcomes as O
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
    import life_agent.core.outcomes as O
    from life_agent.core import OUTCOMES_LOG

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
    import life_agent.core.lookup as LK
    import life_agent.core.outcomes as O

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
    import life_agent.core.narrative as N
    import life_agent.core.outcomes as O

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
    import life_agent.core.narrative as N
    import life_agent.core.outcomes as O

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


def edge_outcome(q: dict, event: dict, *, run_id: str):
    """One attributed outcome for ONE answer-proposing firing's RAW proposal — the
    per-edge reliability curve's evidence (Δ1). Grades the event's ``value`` against
    gold on the shared token-boundary scale, independent of the committed act: an
    in-gate abstain still yields the firing's observation (the curve is P(edge's
    answer correct | self-report), not P(the gate asserted)). None when there is
    nothing to grade — a decline/error left no value, no self-report (rows without
    probability are never scored), or no gold scale (unanswerable: skipped, the
    coverage_outcome precedent — a disclosed selection, never a fabricated INCORRECT).
    Lineage is the §18.9 artifact key, the warm-replay dedup axis. The row shape is
    byte-identical to the pre-tier writer's deliberate rows — logged rows keep folding
    identically."""
    import life_agent.core.outcomes as O

    edge = event.get("edge")
    value, conf = event.get("value"), event.get("confidence")
    if not edge or value is None or conf is None or not q.get("answer"):
        return None
    correct = answer_matches(q["answer"], q.get("answer_variants", []), str(value))
    lineage = event.get("lineage")
    return O.OutcomeEvent(
        tx_time=O.now_iso(), run_id=run_id, question_id=str(q["id"]),
        claim=str(value)[:200], construct="edge-proposal",
        grade="CORRECT" if correct else "INCORRECT", grader="eval_edge",
        instrument_identity={"edge": str(edge)},
        lineage_keys=(str(lineage),) if lineage else (),
        probability=float(conf),
    )


def judge_shadow_items(questions: list[dict], typed_views: list, replay: dict | None) -> list[dict]:
    """Every (arm, candidate) pair the matcher graded this run, WITH the matcher's own
    granularity (PR #65 review): the typed arm one item PER asserted value (the gate's
    realised_report is any-per-value — a joined string drifts in both directions), a
    hedge one item per candidate (the gate grades hedge over ``view["candidates"]``),
    each gradeable edge firing, and the replay arm's report text. The ``arm`` label
    exists for the REPORT table only; the judge prompt never sees it (eval_judge builds
    the prompt from question/gold/variants/candidate alone). Skips mirror the matcher's
    own: abstains, declined/blank replay rows, rows whose status is not exactly "ok"
    (a MISSING status is an abstain in _replay_response — never graded), gold-less
    questions, valueless/self-report-less/edge-less events. A LIVE monolithic baseline
    is not covered (its text is not captured) — the report section discloses that."""
    items: list[dict] = []
    for q, view in typed_views:
        gold = str(q.get("answer") or "")
        if not gold:
            continue
        base = {"question_id": str(q["id"]), "question": str(q["question"]),
                "gold": gold, "variants": list(q.get("answer_variants", []))}
        items += [{**base, "arm": "typed", "candidate": str(a)}
                  for a in view["asserted"]]
        if view["effector"] == "hedge":
            items += [{**base, "arm": "typed-hedge", "candidate": str(c)}
                      for c in view["candidates"]]
        items += [{**base, "arm": f"edge:{ev['edge']}", "candidate": str(ev["value"])}
                  for ev in view["edge_events"]
                  if ev.get("edge") and ev.get("value") is not None
                  and ev.get("confidence") is not None]
    if replay:
        by_id = {str(q["id"]): q for q in questions}
        for qid, row in replay.items():
            q = by_id.get(str(qid))
            if q is None:
                continue
            gold = str(q.get("answer") or "")
            if not gold:
                continue
            text = row.get("text")
            if row.get("declined") or row.get("status") != "ok" \
                    or not str(text or "").strip():
                continue
            items.append({"question_id": str(qid), "question": str(q["question"]),
                          "gold": gold, "variants": list(q.get("answer_variants", [])),
                          "arm": "mono", "candidate": str(text)})
    return items


def judge_grade_items(questions: list[dict], typed_views: list,
                      replay: dict | None) -> list[dict]:
    """The gate arms' gradeable candidates under judge ADOPTION (§14 run-6
    registration (2): the shadow audit cleared 2026-08-14). Exactly the shadow's items
    minus the edge firings — the eval_edge curve rows adopt LAST, separately (they move
    live behaviour), so they stay matcher-graded and never appear here."""
    return [it for it in judge_shadow_items(questions, typed_views, replay)
            if not str(it["arm"]).startswith("edge:")]


def apply_judge_verdicts(paired: list, items: list[dict]) -> tuple[list, list[dict],
                                                                   list[dict]]:
    """Pure: re-grade the paired rows' assertions with judge verdicts (adoption),
    mirroring the matcher's own granularity — any-per-value on typed asserts, over the
    hedge candidates on a hedge, the replay prose on mono. Withholdings carry no
    correctness and pass through untouched; an asserting row with NO items (the
    gold-less question the item builder skips) keeps the matcher's verdict — the judge
    cannot dispute a verdict it was never asked for, and silence must not read as
    unjudged. Returns ``(regraded, flips, unjudged)``: ``flips`` names every row the
    judge moved on either arm (the registration's must-name-before-Δ-is-trusted list);
    a nonzero ``unjudged`` (a None verdict — provider failure, tied votes) means the
    caller must REFUSE the priced reading — a matcher fallback would mix graders
    inside one Δ, exactly what the registration forbids."""
    import dataclasses

    by_row: dict[tuple[str, str], list[dict]] = {}
    for it in items:
        by_row.setdefault((str(it["question_id"]), str(it["arm"])), []).append(it)

    regraded: list = []
    flips: list[dict] = []
    unjudged: list[dict] = []

    def _regrade(qid: str, side: str, resp):
        if not resp.asserts():
            return resp
        arm = ("mono" if side == "mono"
               else "typed-hedge" if resp.action == "hedge" else "typed")
        row_items = by_row.get((qid, arm), [])
        if not row_items:
            return resp
        missing = [it for it in row_items if it.get("verdict") is None]
        if missing:
            unjudged.extend({"question_id": qid, "arm": side,
                             "candidate": it["candidate"]} for it in missing)
            return resp
        correct = any(bool(it["verdict"]) for it in row_items)
        if correct != bool(resp.correct):
            # the ITEM arm (typed-hedge vs typed vs mono) — the §14 table must name
            # WHAT the judge moved, and a hedge-candidate flip is not a report flip
            flips.append({"question_id": qid, "arm": arm,
                          "matcher": bool(resp.correct), "judge": correct,
                          "candidates": [it["candidate"] for it in row_items]})
        return dataclasses.replace(resp, correct=correct)

    for p in paired:
        regraded.append(dataclasses.replace(
            p, typed=_regrade(p.question_id, "typed", p.typed),
            mono=_regrade(p.question_id, "mono", p.mono)))
    return regraded, flips, unjudged


def format_judge_grading_note(flips: list[dict], *, n_items: int) -> str:
    """The report preamble's grading block: adoption is named, and every judge-flipped
    row on either arm is LISTED — the §14 registration makes naming them a precondition
    of trusting Δ (typed asserts are corroboration-shaped, the judge's measured
    false-negative shape at ~0.5%)."""
    lines = [f"> **Grading:** JUDGE-ADOPTED (cross-provider modal-of-3; §14 run-6 "
             f"registration (2), audit cleared) — {n_items} candidate(s) judged, "
             f"{len(flips)} matcher-vs-judge flip(s). The eval_edge curve rows stay "
             f"matcher-graded (adopt last, as registered).", ""]
    if flips:
        lines += ["| ID | arm | matcher | judge | candidate(s) |",
                  "|---|---|---|---|---|"]
        for f in flips:
            cand = " · ".join(str(c) for c in f["candidates"])[:80].replace("|", "\\|")
            lines.append(
                f"| {f['question_id']} | {f['arm']} "
                f"| {'CORRECT' if f['matcher'] else 'INCORRECT'} "
                f"| {'CORRECT' if f['judge'] else 'INCORRECT'} | {cand} |")
        lines.append("")
    return "\n".join(lines) + "\n"


def _fresh_edge_rows(typed_views: list, *, run_id: str, log=None) -> tuple:
    """Grade every collected firing and dedup against the log's already-written §18.9
    lineage — the ONE writer body, shared by the normal post-run path and the
    crash-salvage path (a mid-run failure must not discard the completed questions'
    paid curve food). Returns ``(fresh, n_dup, prior)``."""
    import life_agent.core.outcomes as O
    from life_agent.core import OUTCOMES_LOG

    rows = [e for q, v in typed_views for e in edge_outcomes(q, v, run_id=run_id)]
    prior = [ev for ev in O.read(OUTCOMES_LOG if log is None else log)
             if ev.grader == "eval_edge"]
    seen = {key for ev in prior for key in ev.lineage_keys}
    fresh = dedup_edge_events(rows, seen)
    return fresh, len(rows) - len(fresh), prior


def edge_outcomes(q: dict, view: dict, *, run_id: str) -> list:
    """Every gradeable firing on the view's attribution stream, in firing order —
    the extract tiers (corroborate haiku/sonnet/opus, the k=0 rescue,
    re_extract_strong) alongside deliberate. Reads ONLY ``edge_events``: the
    deliberate firing appears there too, so also reading the legacy single slot
    would double-count (a lineage-less duplicate always survives dedup). The
    question id stamped is the EVAL-CORPUS id — the --gate-loo hold-out's exclusion
    key (calibration.edge_outcomes_from_log's stated hazard for any other spelling)."""
    return [e for ev in view["edge_events"]
            if (e := edge_outcome(q, ev, run_id=run_id)) is not None]


def dedup_edge_events(events: list, seen: set) -> list:
    """Pure: drop edge events whose §18.9 lineage was already graded — a warm replay
    returns the SAME artifact, and grading it once per run would double-count one
    observation into the curve fold. ``seen`` (mutated) carries the log's
    already-written keys in and the batch's keys out; lineage-less rows (caching was
    off) cannot be identified and are always kept."""
    out = []
    for e in events:
        if e.lineage_keys and any(k in seen for k in e.lineage_keys):
            continue
        out.append(e)
        seen.update(e.lineage_keys)
    return out


# --- the adoption gate (bayesian-foundations §8): typed families vs the monolithic ------
# The grading model lives here (a driver concern); the math + the stated realised-utility
# model live in life_agent.core.gate. Each policy is graded on ONE common answer-grounded
# scale (gold token-containment), so the comparison values them identically.

def _typed_response(lk, nv, typed_text: str, q: dict, abstention: str):
    """The typed policy's realised answer on one question, from the family decisions the
    production path just took (LOOKUP_LAST / NARRATIVE_LAST)."""
    import life_agent.core.gate as GATE

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


def withheld_reason(view: dict, *, available: bool):
    """WHY the typed arm withheld (gate.WITHHELD_REASONS) — foundations §14.

    The executor already separates the causes structurally and the gate used to discard
    it: ``miss`` means no posterior ever existed (``/extract`` grounded nothing, so the
    daemon was never consulted), while ``abstain`` means a posterior existed and lost the
    EU argmax. They want opposite fixes — reach vs threshold — so collapsing them is what
    left run 5's 70 abstains undirected.

    ``available=False`` dominates: if this machine's catalogue cannot answer the question,
    the withholding says nothing about the policy and the row is censored from Δ.
    """
    import life_agent.core.gate as GATE

    if not available:
        return GATE.WITHHELD_UNAVAILABLE
    if str(view.get("effector")) == "miss" or not view.get("candidates"):
        return GATE.WITHHELD_MISS
    return GATE.WITHHELD_DISPERSED


def _typed_response_executor(view: dict, q: dict, *, available: bool = True):
    """The typed policy's realised answer when the typed arm runs through the EXECUTOR
    surface (ask.answer_via_executor → the daemon/bridge loop — the surface the priced
    transform menu, incl. the deliberate edge, lives on). Same answer-level scale as
    every arm. The executor's miss (the local edge declined, nothing asserted) maps to
    abstain — but now carries its reason rather than being flattened into one; the gate's
    action space is unchanged, so a reading that ignores the reason is byte-identical.
    ``report_scoped`` never reaches here today (the executor view populates ``asserted``
    for plain report only and renders scoped as a withholding)."""
    import life_agent.core.gate as GATE

    gold, variants = q.get("answer", ""), q.get("answer_variants", [])
    # the arm's TOTAL realised spend (spend_usd: deliberate AND metered tiers — the
    # deliberate-only decisions-v2 slot would price typed tier spend at $0 while the
    # replay arm is fully priced, #67 review) rides every action: an abstain that
    # burned calls still paid for them
    cost = float(view["spend_usd"] or 0.0)
    eff = str(view["effector"])
    if eff == "report":
        return GATE.RealisedResponse(action="report", correct=GATE.realised_report(
            [str(a) for a in view["asserted"]], gold, variants), cost_usd=cost)
    if eff == "hedge":
        return GATE.RealisedResponse(action="hedge", correct=GATE.realised_report(
            [str(c) for c in view["candidates"]], gold, variants), cost_usd=cost)
    reason = withheld_reason(view, available=available)
    if eff == "ask_clarify":
        return GATE.RealisedResponse(action="ask_clarify", correct=None, cost_usd=cost,
                                     withheld=reason)
    return GATE.RealisedResponse(action="abstain", correct=None, cost_usd=cost,
                                 withheld=reason)


def executor_run_stats(typed_views: list) -> dict:
    """Pure: the §10 spend + fired-count summary for one executor-arm gate run — the
    report publishes what the run actually cost, never leaves it implicit."""
    fired = [v for _, v in typed_views if v.get("instrument")]
    return {"n": len(typed_views),
            "deliberate_fired": len(fired),
            "warm_hits": sum(1 for v in fired if v.get("cost_usd") == 0.0),
            # TOTAL metered spend (tiers included since #67) — not the deliberate
            # slot's sum; a question can pay without the deliberate edge ever firing
            "spend_usd": sum(float(v.get("spend_usd") or 0.0)
                             for _, v in typed_views)}


def _monolithic_response(mono_text: str, q: dict, abstention: str):
    """The monolithic instrument's realised answer: the raw synthesize prose, graded by
    the same gold-containment. It abstains only where retrieval is too weak to synthesize
    (the guard it shares with the typed path)."""
    import life_agent.core.gate as GATE

    if mono_text == abstention:
        return GATE.RealisedResponse(action="abstain", correct=None)
    correct = GATE.realised_report([mono_text], q.get("answer", ""),
                                   q.get("answer_variants", []))
    return GATE.RealisedResponse(action="report", correct=correct)


def load_replay_answers(path: Path) -> dict[str, dict]:
    """A fair-fight arm's stored ``answers.jsonl`` (or its run dir), keyed by question id
    — the Δ2 outside-option baseline replayed offline (owner decision 2026-08-06: the
    comparator is what he would do anyway — ask Claude with corpus access)."""
    import json as _json

    if path.is_dir():
        path = path / "arms" / "deliberative" / "answers.jsonl"
    rows = [_json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]
    return {str(r["question_id"]): r for r in rows}


def _replay_response(row: dict, q: dict):
    """One replayed raw-deliberative answer on the SAME answer-level scale as every arm
    (gold token-containment on the prose). A decline or a failed run grades as an
    abstention — the arm asserted nothing there."""
    import life_agent.core.gate as GATE

    text = str(row.get("text") or "").strip()
    # the outside option's realised spend is recorded per row (usage.estimated_cost_usd
    # in the ff run) — priced into Δ from run 6 exactly like the typed arm's spend;
    # spent whether the row asserted or declined
    cost = float((row.get("usage") or {}).get("estimated_cost_usd") or 0.0)
    if row.get("status") != "ok" or row.get("declined") or not text:
        # a blank-but-ok row is a degenerate run, not an assertion — grading it as a
        # report would mint a spurious confident-wrong (the A3 sign rested on 3 CWs)
        return GATE.RealisedResponse(action="abstain", correct=None, cost_usd=cost)
    correct = GATE.realised_report([text], q.get("answer", ""),
                                   q.get("answer_variants", []))
    return GATE.RealisedResponse(action="report", correct=correct, cost_usd=cost)


def gold_available(conn, questions: list[dict]) -> dict[str, bool]:
    """Which questions THIS machine's catalogue can answer at all — foundations §14.

    Gold-side and exact: a question is unavailable iff the chunk its gold answer was
    factored from is absent here. That is the honest reading of "the corpus differs across
    machines": retrieval is pure SQL over the catalogue (pkm SPEC §15.2 — it never opens a
    source file), so what decides reach is which chunks are present, not which files are.

    Fail-CLOSED on the wrong side: any question we cannot check (no provenance chunk_id, an
    unreadable catalogue) is reported AVAILABLE, so it stays in Δ. Censoring is the
    intervention that removes evidence, and a probe failure must never silently shrink the
    corpus the gate is judged on.

    **Dual predicate, preferring the content-addressed handle.** ``chunk_id`` is a surrogate
    sequence (pkm migration 0005) that ``pkm rebuild-catalogue`` re-issues, so on its own it
    is only meaningful across catalogues sharing a chunking lineage — the limit disclosed in
    the §14 registration. Corpora at factory ``format_version >= 2`` also carry
    ``(artifact_cache_key, chunk_index)``, the ``artifact_chunks`` PRIMARY KEY and exactly
    what ``corpus_digest`` hashes; that pair is used when present and decides availability
    on an independently re-chunked catalogue. The fallback is per-question, not per-corpus,
    so a partly-backfilled corpus degrades one question at a time.
    """
    out: dict[str, bool] = {}
    for q in questions:
        qid = str(q["id"])
        prov = q.get("provenance") or {}
        cache_key, chunk_index = prov.get("artifact_cache_key"), prov.get("chunk_index")
        chunk_id = prov.get("chunk_id")
        if cache_key is not None and chunk_index is not None:
            sql = ("SELECT count(*) FROM artifact_chunks "
                   "WHERE artifact_cache_key = ? AND chunk_index = ?")
            params: list = [cache_key, chunk_index]
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


def corpus_note(conn, questions: list[dict], *, corpus: dict | None = None) -> str:
    """The `> **Corpus:** …` provenance line — foundations §14.

    A reading whose corpus is unrecorded is not replayable, and until now no gate report
    has ever carried one: "the corpus digest held across all firings" was an out-of-band
    operator check, not a property of the artifact. This makes it one. Fail-open — a
    missing digest degrades the header, it never voids a paid reading.

    ``corpus`` is ``corpus_identity()``'s dict when the caller already resolved it (the
    gate path), so the header, the sidecar and every paired row publish ONE computation
    rather than three that could disagree."""
    if corpus is None:
        corpus = corpus_identity(conn, pin=None)
    if not corpus.get("digest"):
        return f"> **Corpus:** digest unavailable ({corpus.get('note')})\n\n"

    size = ""
    if corpus.get("n_artifacts") is not None:
        size = f" — {corpus['n_artifacts']} artifacts / {corpus['n_chunks']} chunks"
    status = {
        "matched": f" · PINNED `{corpus['snapshot']}` (matches)",
        "unpinned": " · unpinned",
        "error": f" · pin unresolved ({corpus.get('note')})",
    }.get(str(corpus.get("pin_status")), "")
    if corpus.get("pin_status") == "mismatched":
        d = corpus.get("diff_vs_pin") or {}
        status = (f" · **CORPUS MISMATCH vs `{corpus['snapshot']}`"
                  f" (+{d.get('n_added', '?')}/-{d.get('n_removed', '?')} artifacts)"
                  f" — NOT comparable to the pinned series**")
    try:
        avail = gold_available(conn, questions)
        n_un = sum(1 for v in avail.values() if not v)
        unavail = (f"{n_un} of {len(questions)} question(s) unavailable here"
                   if n_un else "all questions available on this catalogue")
    except Exception as e:
        unavail = f"availability unchecked ({e})"
    return f"> **Corpus:** digest `{corpus['digest']}`{size}{status} — {unavail}\n\n"


def corpus_identity(conn, *, pin: str | None) -> dict:
    """The corpus half of a run's identity, and the pin check — foundations §8/§14.

    Returns ``{digest, snapshot, pin_status, n_artifacts, n_chunks, diff_vs_pin, note}``.
    ``pin_status`` is one of ``matched`` / ``mismatched`` / ``unpinned`` / ``error``.

    Fail-open on the *recording* (a digest we cannot compute degrades the header, never
    voids a paid reading — ``corpus_note``'s rule), but the caller treats ``mismatched`` as
    fail-CLOSED: refusing before the run spends money costs nothing, whereas discovering
    afterwards that Δ was computed on a different universe than the series it is compared
    to costs the whole reading."""
    out: dict = {"digest": None, "snapshot": pin, "pin_status": "unpinned",
                 "n_artifacts": None, "n_chunks": None, "diff_vs_pin": None, "note": None}
    try:
        from life_agent.core.corpus import corpus_digest
        out["digest"] = corpus_digest(conn)
        row = conn.execute(
            "SELECT count(DISTINCT artifact_cache_key), count(*) FROM artifact_chunks"
        ).fetchone()
        out["n_artifacts"], out["n_chunks"] = (int(row[0]), int(row[1])) if row else (None, None)
    except Exception as e:
        out["pin_status"] = "error"
        out["note"] = f"{type(e).__name__}: {e}"
        return out

    if not pin:
        return out
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent / "corpus"))
        import pin_corpus as PIN
        manifest = PIN.load_manifest(pin)
    except SystemExit as e:
        out["pin_status"] = "error"
        out["note"] = str(e)
        return out
    if manifest["corpus_digest"] == out["digest"]:
        out["pin_status"] = "matched"
        return out
    out["pin_status"] = "mismatched"
    live = {"artifacts": [], "n_chunks": out["n_chunks"]}
    try:
        live["artifacts"] = [
            r[0] for r in conn.execute(
                "SELECT DISTINCT artifact_cache_key FROM artifact_chunks "
                "ORDER BY artifact_cache_key").fetchall()
        ]
        added, removed = PIN.key_diff(manifest, live)
        out["diff_vs_pin"] = {"n_added": len(added), "n_removed": len(removed),
                              "added_sample": added[:5], "removed_sample": removed[:5]}
    except Exception as e:
        out["note"] = f"diff unavailable: {type(e).__name__}: {e}"
    return out


def _sha256_file(path: Path) -> str | None:
    import hashlib
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


# §6.10 — the decision path, declared once. A gate reading is a comparison, and a
# comparison whose background is free to move attributes nothing: run 10 pinned its recipe
# (the flags, the corpus, the golds, the utility fold) and ran against a tree that had
# quietly gained three further decision-path changes, two of them invisible to the 7.2
# oracle because the fixture set tapes the bridge at the `http` seam. It read FAIL on one
# wrong commit and no argument could say which of four changes bought it.
#
# What belongs here is exactly what can change a decision on the typed arm: the body
# (`core`), the bridge it decides through (`bridge`), and the harness that drives the arm.
# What does NOT belong: transport (`reach`), the act layer (`tasks`, `trips`), the
# equivalence instrument itself (`collapse`) and prose — none can move a terminal, and
# pinning them would make the diff noisy enough to be ignored, which is the failure mode
# this is built against.
_DECISION_LOGIC: tuple[str, ...] = (
    "src/life_agent/core/**/*.py",
    "src/life_agent/bridge/**/*.py",
)
# The harness shapes a run and so belongs in the digest — but it changes for reasons that
# are not decision changes (this very pin is one), and a diff that fires on every run is a
# diff that gets ignored. Reported as its own tier so a harness-only move never reads as a
# decision move.
_RUN_HARNESS: tuple[str, ...] = (
    "scripts/eval_executor.py",
    "scripts/run_eval.py",
)
_DECISION_PATH: tuple[str, ...] = _DECISION_LOGIC + _RUN_HARNESS


def _tier(rel: str) -> str:
    from pathlib import PurePosixPath
    return ("logic" if any(PurePosixPath(rel).full_match(pat) for pat in _DECISION_LOGIC)
            else "harness")


def decision_path_tree(root: Path | str | None = None) -> dict:
    """Hash every file on the declared decision path; return the manifest and its digest.

    Recorded in `run_meta.json` before the first question, so a killed run still carries
    the tree it would have measured. The digest is over the manifest lines, so a rename is
    a difference like any other."""
    import hashlib
    root = Path(root) if root is not None else Path(__file__).resolve().parent.parent
    files: dict[str, str] = {}
    for pattern in _DECISION_PATH:
        for path in sorted(root.glob(pattern)):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            files[path.relative_to(root).as_posix()] = \
                hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = "\n".join(f"{rel} {sha}" for rel, sha in sorted(files.items()))
    return {
        "format_version": 1,
        "declared": list(_DECISION_PATH),
        "n": len(files),
        "digest": hashlib.sha256(manifest.encode("utf-8")).hexdigest(),
        "files": files,
    }


def tree_diff(old: dict, new: dict) -> dict:
    """Name every difference between two decision-path trees. A digest mismatch is a
    refusal; this is what makes it actionable — 'something else changed' is what run 10's
    report was reduced to saying."""
    o, n = dict(old.get("files") or {}), dict(new.get("files") or {})
    added = sorted(set(n) - set(o))
    removed = sorted(set(o) - set(n))
    changed = sorted(k for k in set(o) & set(n) if o[k] != n[k])
    return {"added": added, "removed": removed, "changed": changed,
            "identical": not (added or removed or changed)}


def decision_path_tree_at(root: Path | str, ref: str) -> dict:
    """The same manifest, computed at a git ref instead of the working tree.

    Every run before §6.10 recorded a git sha and a dirty flag but no tree; a CLEAN sha is
    the tree, so the whole back-series stays comparable. Without this the pin could only
    ever compare runs fired after itself, which is the slowest possible way to become
    useful."""
    import hashlib
    import subprocess
    from pathlib import PurePosixPath
    root = Path(root)
    listing = subprocess.run(["git", "-C", str(root), "ls-tree", "-r", "--name-only", ref],
                             capture_output=True, text=True, check=True).stdout.splitlines()
    # PurePath.full_match, not fnmatch: `**` must mean what it means to Path.glob above, or
    # the two halves of this pin disagree about which files are on the decision path — and
    # a pin whose halves disagree is worse than none. (fnmatch's `**` is a plain `*`, so
    # `core/**/*.py` silently skipped every file directly under `core/`.)
    wanted = sorted(rel for rel in listing
                    if any(PurePosixPath(rel).full_match(pat) for pat in _DECISION_PATH))
    files: dict[str, str] = {}
    for rel in wanted:
        blob = subprocess.run(["git", "-C", str(root), "show", f"{ref}:{rel}"],
                              capture_output=True, check=True).stdout
        files[rel] = hashlib.sha256(blob).hexdigest()
    manifest = "\n".join(f"{rel} {sha}" for rel, sha in sorted(files.items()))
    return {
        "format_version": 1,
        "declared": list(_DECISION_PATH),
        "n": len(files),
        "digest": hashlib.sha256(manifest.encode("utf-8")).hexdigest(),
        "files": files,
    }


def comparison_tree(meta: dict, *, root: Path | str | None = None) -> dict | None:
    """The comparison run's decision-path tree: recorded if it has one, else reconstructed
    from a clean recorded commit, else None — and None means the report says 'not diffed'.

    A run fired from a DIRTY tree is not its commit, and reconstructing one anyway would
    manufacture the very 'nothing else changed' this entry exists to prevent."""
    recorded = meta.get("decision_path_tree")
    if recorded:
        return recorded
    git = meta.get("life_agent_git") or {}
    if not git.get("sha") or git.get("dirty"):
        return None
    root = Path(root) if root is not None else Path(__file__).resolve().parent.parent
    try:
        return decision_path_tree_at(root, str(git["sha"]))
    except Exception:
        return None


def tree_pin_note(tree: dict, *, compare: dict | None, compare_run_id: str | None) -> str:
    """The report's tree block — §6.10's pin. Goes ABOVE the verdict, because a reader who
    reaches the number without knowing what moved underneath it has already been misled.

    Differences are grouped by tier and the claim is kept to what a hash can support: a
    tree diff can say WHAT moved, never whether the mover was intended. Overclaiming here
    ("cannot be attributed") on a harness-only difference would teach readers to skip the
    block, which is how a pin dies."""
    head = (f"> **Decision-path tree:** {tree['n']} file(s), digest "
            f"`{tree['digest'][:16]}…`")
    if compare is None:
        return (head + " — **not diffed** (no comparison run given). This run's Δ is not "
                "attributable to any single change unless the tree is compared to the run "
                "it is read against (§6.10).\n\n")
    d = tree_diff(compare, tree)
    if d["identical"]:
        return head + (f" — **identical** to `{compare_run_id}`'s. Any difference in Δ is "
                       "this run's own (§6.10).\n\n")
    moved = sorted({f for k in ("changed", "added", "removed") for f in d[k]})
    logic = [f for f in moved if _tier(f) == "logic"]
    harness = [f for f in moved if _tier(f) == "harness"]
    parts = []
    for label, group in (("decision logic", logic), ("harness", harness)):
        if group:
            parts.append(f"**{label}** ({len(group)}): "
                         + ", ".join(f"`{f}`" for f in sorted(group)))
    detail = " · ".join(f"{k} {len(d[k])}" for k in ("changed", "added", "removed") if d[k])
    tail = ("Δ is attributable only insofar as this list IS the intended change (§6.10)."
            if logic else
            "No decision logic moved; the difference is harness only (§6.10).")
    return head + (f" — **differs** from `{compare_run_id}`'s ({detail}). "
                   + " · ".join(parts) + ". " + tail + "\n\n")


def build_gate_run_meta(*, run_id: str, args, questions: list[dict], questions_path,
                        corpus: dict, availability: dict[str, bool],
                        baseline: str) -> dict:
    """The gate's identity sidecar — the fairfight `run_meta.json` pattern (§14).

    §8's blind discipline claims the question set, the utility model and the elicitations
    were frozen before the result. Nothing recorded that, so the claim had exactly the
    evidentiary status the corpus claim had — an operator memory. These sha256 pins are as
    load-bearing as the digest.

    Written BEFORE the first question runs, so a voided or killed run still has its
    provenance on disk (runs 3 and 4 lost theirs to the next run's clobber)."""
    import life_agent.core.config as LCFG
    import life_agent.core.gate as GATE
    unavailable = sorted(qid for qid, ok in availability.items() if not ok)
    return {
        "format_version": 1,
        "run_id": run_id,
        "created_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "life_agent_git": _git_info(Path(__file__).resolve().parent.parent),
        "decision_path_tree": decision_path_tree(),
        "corpus": corpus,
        "questions": {
            "path": str(questions_path) if questions_path else None,
            "sha256": _sha256_file(questions_path) if questions_path else None,
            "n": len(questions),
        },
        "availability": {
            # which predicate actually decided: the content-addressed pair when the corpus
            # carries it, else the surrogate. A reader must not have to guess.
            "predicate": ("artifact_cache_key" if all(
                (q.get("provenance") or {}).get("artifact_cache_key") for q in questions
            ) else "chunk_id"),
            "n_unavailable": len(unavailable),
            "unavailable_ids": unavailable,
        },
        "gate": {
            "baseline": baseline,
            # mirrors the call site's own choice (gate_paired_outcomes typed_arm=…)
            "typed_arm": "executor" if getattr(args, "gate_executor", False) else "family",
            "k": getattr(args, "k", None),
            "loo": bool(getattr(args, "gate_loo", False)),
            "judge_shadow": bool(getattr(args, "judge_shadow", False)),
            # which grader produced the paired rows' correctness (§14 run-6 reg. (2))
            "grading": ("judge" if getattr(args, "judge_grade", False) else "matcher"),
            "materiality_delta": GATE.MATERIALITY_DELTA,
            "level": GATE.GATE_LEVEL,
        },
        "utility": {
            "model_path": str(LCFG.UTILITY_MODEL),
            "model_sha256": _sha256_file(LCFG.UTILITY_MODEL),
            "elicitations_path": str(LCFG.UTILITY_ELICITATIONS),
            "elicitations_sha256": _sha256_file(LCFG.UTILITY_ELICITATIONS),
        },
        "env_flags": {
            "LIFE_AGENT_BRIDGE_URL": os.environ.get("LIFE_AGENT_BRIDGE_URL"),
            "ANSWER_BRAIN_URL": os.environ.get("ANSWER_BRAIN_URL"),
        },
    }


def _git_info(repo_dir: Path) -> dict:
    """Best-effort (sha, dirty). Never raises — a broken git is a note, not a dead run.
    Same contract as scripts/fairfight/run_fairfight.py:155."""
    import subprocess
    try:
        sha = subprocess.run(["git", "-C", str(repo_dir), "rev-parse", "HEAD"],
                             capture_output=True, text=True, timeout=10,
                             check=True).stdout.strip()
        status = subprocess.run(["git", "-C", str(repo_dir), "status", "--porcelain"],
                                capture_output=True, text=True, timeout=10,
                                check=True).stdout
        return {"sha": sha, "dirty": bool(status.strip()), "note": None}
    except Exception as e:
        return {"sha": None, "dirty": None, "note": f"{type(e).__name__}: {e}"}


def gate_paired_outcomes(conn, questions: list[dict], k: int, ask,
                         replay: dict[str, dict] | None = None,
                         typed_arm: str = "family",
                         typed_views: list | None = None,
                         loo: bool = False) -> list:
    """Run the typed policy over the corpus and pair it against the baseline arm per
    question. The typed pass is the production answer path with the **gather-augmented**
    lookup loop (gather=True → re-retrieve corroboration on the top candidates, then
    re-weight by recency + whose-document before deciding) — or, with
    ``typed_arm="executor"``, the executor surface (ask.answer_via_executor: the
    daemon/bridge loop the priced transform menu lives on — the ONLY arm that can carry
    the deliberate edge; a mid-run down stack VOIDS the reading loudly, and
    ``typed_views`` collects each (question, view) pair for the attributed-outcome
    writer). The baseline is the monolithic pass (families=False → raw synthesize
    prose) — or, with ``replay``, the raw-deliberative outside option replayed from a
    stored run (Δ2): the join is STRICT, a question the replay lacks is named and
    refused, never silently dropped.

    ``loo=True`` (executor arm only) is the held-out reading's discipline: before each
    question the module hold-out (ask.EXECUTOR_HOLD_OUT_QUESTION_ID) is set to that
    question's id, so the executor's per-question curve fold excludes the question's
    own graded outcome rows — grouped leave-one-question-out (the p3_gate precedent;
    in-sample curves = §17.4's leakage re-enacted). Cleared after the run, voided or
    not, so nothing leaks into a later live ask's fold."""
    import life_agent.core.gate as GATE

    if loo and typed_arm != "executor":
        raise ValueError(
            "loo holds curves out of the EXECUTOR arm's per-question fold — the "
            "family arm folds no curves, so a LOO reading over it would be a silent "
            "no-op wearing the held-out label (pass typed_arm='executor')")
    if replay is not None:
        missing = sorted(str(q["id"]) for q in questions if str(q["id"]) not in replay)
        if missing:
            raise ValueError(
                f"replay baseline lacks {len(missing)} question(s): {missing} — "
                "the corpora must match (no silent drop; pass the run that answered "
                "these questions)")
    available = gold_available(conn, questions)
    n_unavailable = sum(1 for v in available.values() if not v)
    if n_unavailable:
        print(f"  ! {n_unavailable}/{len(questions)} question(s) unavailable on this "
              "catalogue — they will be CENSORED from Δ and named in the report")
    paired = []
    try:
        for q in questions:
            if typed_arm == "executor":
                if loo:
                    ask.EXECUTOR_HOLD_OUT_QUESTION_ID = str(q["id"])
                ask.answer_via_executor(q["question"], k)
                view = ask.EXECUTOR_VIEW_LAST
                if view is None:
                    raise RuntimeError(
                        f"executor view missing for {q['id']} — the daemon/bridge went "
                        "down mid-run; the reading is void (fix the stack and rerun)")
                typed = _typed_response_executor(
                    view, q, available=available.get(str(q["id"]), True))
                if typed_views is not None:
                    typed_views.append((q, view))
            else:
                typed_text, _, _ = ask.answer(conn, q["question"], k, gather=True)
                lk, nv = ask.LOOKUP_LAST, ask.NARRATIVE_LAST  # capture before next call
                typed = _typed_response(lk, nv, typed_text, q, ask.ABSTENTION)
            if replay is not None:
                mono = _replay_response(replay[str(q["id"])], q)
            else:
                mono_text, _, _ = ask.answer(conn, q["question"], k, families=False)
                mono = _monolithic_response(mono_text, q, ask.ABSTENTION)
            answerable = bool(q.get("answerable", bool(q.get("answer"))))
            paired.append(GATE.PairedOutcome(
                question_id=str(q["id"]), answerable=answerable, typed=typed, mono=mono))
            tmark = "·" if not typed.asserts() else ("✓" if typed.correct else "✗")
            mmark = "·" if not mono.asserts() else ("✓" if mono.correct else "✗")
            blabel = "delib" if replay is not None else "mono"
            print(f"  {q['id']}: typed {tmark}{typed.action[:6]:<6} "
                  f"{blabel} {mmark}{mono.action[:6]}")
    finally:
        if loo:
            ask.EXECUTOR_HOLD_OUT_QUESTION_ID = None
    return paired


def _paired_to_dict(p, baseline: str = "monolithic", *, run_id: str = "",
                    corpus_digest: str = "", corpus_snapshot: str = "") -> dict:
    # every row names its baseline arm — a Δ2 paired.jsonl must never read as the §8 one.
    # cost_usd rides both arms (#67 review): the artifact must DETERMINE the Δ the report
    # computed, or every offline reanalysis silently zeroes the run-6 spend term. `withheld`
    # rides for the same reason (§14 availability registration): it decides which rows Δ
    # was computed over, so an artifact without it cannot reproduce the published number.
    # run_id + corpus identity ride by the same argument one level up: §14 routes cross-run
    # comparability THROUGH these artifacts, and a Δ series that claims one universe must be
    # able to SHOW it. Until now run_id was recoverable only from the filename, and the
    # corpus not at all — `jq -s 'group_by(.corpus_digest)'` over the archive is the check
    # that "the digest held across all firings" never had.
    return {"question_id": p.question_id, "answerable": p.answerable, "baseline": baseline,
            "run_id": run_id, "corpus_digest": corpus_digest,
            "corpus_snapshot": corpus_snapshot,
            "censored": p.censored(),
            "typed": {"action": p.typed.action, "correct": p.typed.correct,
                      "cost_usd": p.typed.cost_usd, "withheld": p.typed.withheld},
            "mono": {"action": p.mono.action, "correct": p.mono.correct,
                     "cost_usd": p.mono.cost_usd, "withheld": p.mono.withheld}}


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


def archive_gate_artifacts(gate_dir: Path, *, run_id: str) -> list[Path]:
    """Copy the fixed-path gate artifacts to run-id-suffixed names, mechanically.

    The run-6 pre-registration (bayesian-foundations §14) routes cross-merge
    comparability THROUGH the published artifacts — and the manual archive ritual was
    missed on runs 3 and 4 (their paired.jsonl/report.md were clobbered by the next
    run; PR #68 review). Names match the pre-existing manual archives
    (report-<run_id>.md / paired-<run_id>.jsonl) so one glob spans both eras. A
    missing source is skipped, never raised — a voided run archives what it wrote."""
    archived: list[Path] = []
    for name, suffix in (("report.md", ".md"), ("paired.jsonl", ".jsonl"),
                         ("run_meta.json", ".json")):
        src = gate_dir / name
        if src.exists():
            dst = gate_dir / f"{name.split('.')[0]}-{run_id}{suffix}"
            dst.write_bytes(src.read_bytes())
            archived.append(dst)
    return archived


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
    # the issue-#56 refusal signal is its own part, NOT a cache stage: refusals over
    # expand ATTEMPTS (a rate the owner can read directly), cached count named.
    n_ref = cache.get("expand_refusal.hit", 0) + cache.get("expand_refusal.miss", 0)
    if n_ref:
        n_att = cache.get("expand.hit", 0) + cache.get("expand.miss", 0)
        parts.append(f"expand refusals {n_ref}/{n_att} "
                     f"({cache.get('expand_refusal.hit', 0)} cached)")
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
    parser.add_argument(
        "--questions", default=None,
        help="alternate question corpus (e.g. $LIFE_AGENT_KB/eval/questions_v2.yaml — "
             "the factory output); default: $LIFE_AGENT_KB/eval/questions.yaml",
    )
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
        "--gate-replay", default=None,
        help="Δ2 (the outside-option gate): replace the gate's monolithic baseline with "
             "a REPLAYED raw-deliberative arm — path to a fair-fight run dir (or its "
             "answers.jsonl). The comparator becomes what the owner would do without "
             "the agent; the join is strict (a missing question refuses, named).",
    )
    parser.add_argument(
        "--gate-executor", action="store_true",
        help="run the gate's TYPED arm through the executor surface "
             "(ask.answer_via_executor — the daemon/bridge loop where the priced "
             "transform menu, incl. the deliberate edge, lives) instead of the "
             "in-process family decide. Requires the bridge + daemon up (refuses "
             "loudly). Buffers eval_edge attributed outcomes during the run and "
             "appends them AFTER it, lineage-deduped — the in-run curve fold never "
             "sees its own run's rows.",
    )
    parser.add_argument(
        "--gate-loo", action="store_true",
        help="the held-out reading (run 4): fold the executor arm's per-edge curves "
             "leave-one-QUESTION-out — each question's decide conditions on curves "
             "folded WITHOUT its own outcome rows (the p3_gate precedent; in-sample "
             "curves = §17.4 leakage re-enacted). Requires --gate-executor (the only "
             "arm that folds curves).",
    )
    parser.add_argument(
        "--corpus-pin", default=None, metavar="NAME",
        help="require the live corpus to equal a pinned version "
             "($LIFE_AGENT_KB/eval/corpus/NAME.json — see scripts/corpus/pin_corpus.py). "
             "A mismatch REFUSES before the run spends anything, printing what was added "
             "or removed: a Δ compared against a series it does not share a universe with "
             "is not a reading (foundations §8/§14). Without this the digest is still "
             "recorded, just unchecked.",
    )
    parser.add_argument(
        "--compare-run-meta", default=None, metavar="RUN_META",
        help="path to the run_meta.json of the run this one will be READ AGAINST. Its "
             "decision-path tree is diffed against this run's and every difference is "
             "named in the report (§6.10). Run 10 pinned its recipe and not its tree, and "
             "read FAIL against a tree carrying three further decision-path changes: no "
             "argument could say which bought it. Without this the tree is still recorded, "
             "just undiffed — and the report says so.",
    )
    parser.add_argument(
        "--corpus-pin-mismatch", choices=("refuse", "allow"), default="refuse",
        help="what a pin mismatch does (default: refuse). 'allow' proceeds but stamps "
             "pin_status=mismatched into run_meta.json, the report header, and EVERY "
             "paired row — a knowingly off-corpus reading must be self-identifying.",
    )
    parser.add_argument(
        "--no-outcomes", action="store_true",
        help="skip appending graded outcomes to the calibration log "
             "($LIFE_AGENT_KB/calibration/outcomes.jsonl) — dry runs only; the log "
             "is append-only evidence and cannot be backfilled",
    )
    parser.add_argument(
        "--judge-shadow", action="store_true",
        help="SHADOW-grade every matcher-graded candidate (typed assert, replay text, "
             "edge firings) with the cross-provider modal-of-3 correctness judge and "
             "publish the disagreement table in the gate report. Grading is UNCHANGED "
             "(the verdict and all outcome rows stay matcher-graded — run 5 remains "
             "comparable to runs 3/4); adoption is pre-registered for run 6 iff the "
             "disagreement audit clears. Live cross-provider calls (cached append-only "
             "in $LIFE_AGENT_KB/eval/judge-verdicts.jsonl; ~$1/run cold).",
    )
    parser.add_argument(
        "--judge-grade", action="store_true",
        help="ADOPT judge grading for the gate arms (§14 run-6 registration (2): the "
             "run-5 shadow audit cleared): the paired rows' correctness comes from the "
             "cross-provider modal-of-3 judge (cache-first), the matcher becomes the "
             "shadow, and every flipped row is named in the report. The eval_edge "
             "curve rows stay matcher-graded (adopt last, separately). An unjudged "
             "candidate REFUSES the priced reading — mixed grading inside one Δ is "
             "not a reading. Requires --gate-executor and --gate-replay.",
    )
    args = parser.parse_args()

    if args.judge_grade and args.judge_shadow:
        # under adoption the matcher IS the shadow (the flip table is the disagreement
        # table) — a second, differently-rolled judge section would be two readings
        print("REFUSED: --judge-grade adopts the judge, so the flip table IS the "
              "disagreement table — drop --judge-shadow.")
        return 2
    if args.judge_grade and not (args.gate_executor and args.gate_replay):
        # the family arm captures no per-value asserts and a LIVE mono baseline's prose
        # is never captured — grading would silently read any([]) == False on every
        # asserting row (the shadow's own coverage note)
        print("REFUSED: --judge-grade grades the arms' captured text — pass "
              "--gate-executor (per-value asserts) and --gate-replay (the mono "
              "prose; a live baseline's text is not captured).")
        return 2

    if args.gate_loo and not args.gate_executor:
        # refused before any state is touched: the family arm folds no curves, so a
        # LOO run without the executor arm would read as held-out while holding
        # nothing out
        print("REFUSED: --gate-loo holds curves out of the EXECUTOR arm's per-question "
              "fold — pass --gate-executor (the only arm that folds curves).")
        return 2
    if args.gate_loo:
        # PR #58 review Major: flag-off, answer_via_executor folds no curves at ALL
        # (ask.py: transforms, curves = None, None) — the run would complete and
        # publish the held-out label over a total no-op (§17.4's shape: the label
        # outrunning the mechanics)
        import life_agent.core.config as _LCFG
        if not _LCFG.deliberate_enabled():
            print("REFUSED: --gate-loo needs the deliberate edge on (it is on by "
                  "default; LIFE_AGENT_DELIBERATE=0 is set in this process) — without "
                  "it the executor arm folds no curves and the held-out label would "
                  "be vacuous.")
            return 2
    if args.gate_executor:
        # run 6 (2026-08-17): PKM_CONFIG unset in the launcher → the bridge's MCP config
        # said `pkm --config "" serve` → nine cold deliberates declined blind at ~$1.2
        # each. The bridge now refuses per call; refuse HERE before any spend (the
        # bridge normally shares this process's env — a remote bridge is its own
        # preflight, and the per-call refusal still names it).
        import life_agent.core.config as _LCFG
        if _LCFG.deliberate_enabled() and not _LCFG.PKM_CONFIG.is_file():
            print(f"REFUSED: the deliberate edge is on but PKM_CONFIG does not resolve "
                  f"to a file ({_LCFG.PKM_CONFIG}) — the deliberate edge's pkm MCP "
                  f"server cannot start; set PKM_CONFIG (see .env).")
            return 2

    import duckdb
    import yaml

    questions = load_questions(args.questions)
    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    db_path = Path(cfg["root_dir"]).expanduser() / "catalogue.duckdb"
    try:
        conn = duckdb.connect(str(db_path))
    except duckdb.IOException as e:
        # a live service (the bridge) may hold the write lock; every eval path only
        # READS the catalogue except --rebuild-index, which genuinely needs the writer
        if args.rebuild_index:
            raise
        print(f"catalogue write-locked ({e}); connecting read-only")
        conn = duckdb.connect(str(db_path), read_only=True)
    conn.execute("INSTALL fts; LOAD fts;")

    if args.rebuild_index:
        from pkm.retrieval import build_fts_index
        print("Building FTS index …")
        build_fts_index(conn)

    if args.gate:
        import json

        import life_agent.core.config as LCFG
        import life_agent.core.gate as GATE
        import life_agent.core.lookup as LK
        import life_agent.core.utility as UT

        replay = (load_replay_answers(Path(args.gate_replay).expanduser())
                  if args.gate_replay else None)
        baseline_name = (f"raw-deliberative replay ({args.gate_replay})"
                         if replay is not None else "monolithic (families=False)")
        typed_name = ("executor surface (answer_via_executor)" if args.gate_executor
                      else "the production family path")
        print(f"Running the adoption gate (k={args.k}) over {len(questions)} questions "
              f"(typed = {typed_name}; baseline = {baseline_name}) …")
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import ask

        if args.gate_executor and not ask._executor_ready():
            # a partial-stack run would read as policy behaviour — refuse, never degrade
            print(f"REFUSED: --gate-executor needs the bridge + daemon up "
                  f"({ask.EXECUTOR_BRIDGE}, {ask.EXECUTOR_DAEMON}) — start them "
                  f"(bin/answer-brain) and rerun.")
            return 2

        t0 = time.monotonic()
        run_id = f"gate-{datetime.now().strftime('%Y%m%dT%H%M%S')}"

        # Corpus identity is resolved and CHECKED before anything is spent. A mismatch is
        # cheap to refuse now and impossible to repair later: a Δ computed on a different
        # universe than the series it is compared against is not a reading (§8/§14).
        corpus = corpus_identity(conn, pin=args.corpus_pin)
        if corpus["pin_status"] == "mismatched":
            d = corpus.get("diff_vs_pin") or {}
            print(f"CORPUS MISMATCH vs pin '{args.corpus_pin}':\n"
                  f"  live {corpus['digest']}\n"
                  f"  +{d.get('n_added', '?')} artifacts added, "
                  f"-{d.get('n_removed', '?')} removed since the pin")
            if args.corpus_pin_mismatch == "refuse":
                print("REFUSED before spending. Re-pin under a new name if the corpus "
                      "moved deliberately, or pass --corpus-pin-mismatch=allow to "
                      "publish a self-identified off-corpus reading.")
                return 2
            print("  proceeding — every artifact will be stamped pin_status=mismatched")
        elif corpus["pin_status"] == "matched":
            print(f"corpus pin '{args.corpus_pin}' MATCHED ({corpus['digest'][:16]}…)")

        # a Δ2 run writes to its OWN directory — it must never overwrite the frozen §8
        # monolithic gate artifacts, and every paired row names its baseline arm
        gate_dir = _kb_root() / "eval" / ("gate-outside-option" if replay is not None
                                          else "gate")
        baseline_tag = ("raw-deliberative-replay" if replay is not None
                        else "monolithic")
        gate_dir.mkdir(parents=True, exist_ok=True)

        # Provenance lands BEFORE the first question, so a killed or voided run still has
        # its identity on disk — runs 3 and 4 lost theirs to the next run's clobber.
        run_meta = build_gate_run_meta(
            run_id=run_id, args=args, questions=questions,
            questions_path=args.questions, corpus=corpus,
            availability=gold_available(conn, questions), baseline=baseline_tag)
        (gate_dir / "run_meta.json").write_text(
            json.dumps(run_meta, indent=2, sort_keys=True), encoding="utf-8")

        typed_views: list = []
        if args.gate_executor:
            # in-gate executor decisions carry the run_id — never masquerading as live
            ask.EXECUTOR_RUN_ID = run_id
        try:
            paired = gate_paired_outcomes(
                conn, questions, args.k, ask, replay=replay,
                typed_arm="executor" if args.gate_executor else "family",
                typed_views=typed_views if args.gate_executor else None,
                loo=args.gate_loo)
        except BaseException:
            # crash salvage: a mid-run failure voids the READING, never the completed
            # questions' paid curve food (the run-3 external-kill precedent) — grade
            # and append whatever accrued, say so, and re-raise.
            if args.gate_executor and typed_views and not args.no_outcomes:
                s_fresh, s_dup, _ = _fresh_edge_rows(typed_views, run_id=run_id)
                if s_fresh:
                    _append_outcomes(s_fresh)
                print(f"  (mid-run failure — salvaged {len(s_fresh)} edge outcome "
                      f"row(s) from {len(typed_views)} completed question(s), deduped "
                      f"{s_dup}; the gate reading is VOID)")
            raise
        finally:
            ask.EXECUTOR_RUN_ID = None

        exec_note = ""
        if args.gate_executor:
            # the writer: grade every firing the run produced (extract tiers AND
            # deliberate — the view's edge_events stream), dedup against the log's
            # already-graded §18.9 lineage, and append AFTER the run — the in-run
            # curve fold (ask._edge_curves per question) never saw its own run's rows
            stats = executor_run_stats(typed_views)
            fresh, n_dup, prior = _fresh_edge_rows(typed_views, run_id=run_id)
            # the pre-run evidence base IN FORCE (latest row per edge+lineage — a
            # regrade's superseding row replaces, never adds; calibration's fold), read
            # BEFORE this run's rows are appended (run 7's note counted post-append)
            from life_agent.core import OUTCOMES_LOG as _OL
            from life_agent.core.calibration import edge_outcomes_from_log as _eofl
            n_in_force = len(_eofl(_OL))
            if args.no_outcomes:
                print(f"  (edge outcomes NOT written — --no-outcomes; would have "
                      f"written {len(fresh)}, deduped {n_dup})")
            elif fresh:
                _append_outcomes(fresh)
            n_written = 0 if args.no_outcomes else len(fresh)
            print(f"  deliberate: fired {stats['deliberate_fired']}/{stats['n']} "
                  f"(warm {stats['warm_hits']}) · spend ${stats['spend_usd']:.2f} · "
                  f"edge outcomes written {n_written} (deduped {n_dup})")
            exec_note = (f"> **Typed arm:** executor surface (answer_via_executor) — "
                         f"deliberate fired {stats['deliberate_fired']}/{stats['n']} "
                         f"(warm {stats['warm_hits']}), spend "
                         f"${stats['spend_usd']:.2f}, edge outcomes written "
                         f"{n_written} (deduped {n_dup})\n\n")
            if args.gate_loo:
                # the held-out reading names its evidence base — and a vacuous LOO
                # (no attributed rows yet) is disclosed IN THE REPORT, never read as
                # a held-out result (stdout alone is not disclosure)
                if not prior:
                    print("  ⚠ --gate-loo is VACUOUS: the log has no eval_edge rows "
                          "yet — every fold is empty either way; run the cold "
                          "harvest (run 3) first")
                vac = (" **(VACUOUS — no attributed rows existed; every fold was "
                       "empty either way)**" if not prior else "")
                exec_note += (
                    f"> **Curves:** held-out (grouped leave-one-question-out) over "
                    f"{n_in_force} pre-run attributed edge outcome row(s) in force "
                    f"({len(prior)} logged) — each question's decide conditioned on "
                    f"curves folded without its own rows{vac}\n\n")

        # judge ADOPTION (§14 run-6 registration (2)): the arms' correctness is
        # re-graded by the cross-provider modal judge BEFORE Δ — after the edge append,
        # so a judge failure can refuse the reading without voiding the paid curve
        # food. Cache-first: a rerun resumes from the verdict cache.
        grading_note = ""
        if args.judge_grade:
            sys.path.insert(0, str(Path(__file__).resolve().parent / "comparison"))
            import _common as JC
            import eval_judge as EJ
            jcache_path = _kb_root() / "eval" / "judge-verdicts.jsonl"
            jcache = EJ.load_verdicts(jcache_path)
            gitems = judge_grade_items(questions, typed_views, replay)
            n_cached = sum(1 for it in gitems if EJ.judge_key(
                it["question"], it["gold"], it["variants"], it["candidate"],
                judge=JC.JUDGE_MODEL) in jcache)
            print(f"  judge grading {len(gitems)} candidate(s) "
                  f"({n_cached} cached) …")
            for it in gitems:
                it["verdict"] = EJ.judge_with_cache(
                    jcache, jcache_path, it["question"], it["gold"], it["variants"],
                    it["candidate"], complete=JC.judge_complete, judge=JC.JUDGE_MODEL)
            paired, jflips, junjudged = apply_judge_verdicts(paired, gitems)
            if junjudged:
                names = ", ".join(f"{u['question_id']}/{u['arm']}" for u in junjudged)
                print(f"REFUSED: {len(junjudged)} candidate(s) unjudged after "
                      f"modal-of-3 ({names}) — a matcher fallback would mix graders "
                      f"inside one Δ (§14). Edge outcomes above are already appended "
                      f"(paid food kept); rerun to resume from the verdict cache.")
                return 2
            grading_note = format_judge_grading_note(jflips, n_items=len(gitems))
            if jflips:
                print(f"  judge flipped {len(jflips)} row(s): "
                      + ", ".join(f"{f['question_id']}/{f['arm']}" for f in jflips))

        # the FULL utility posterior (marginals, not just Ū — the gate samples P(U)),
        # folded from the FROZEN model + elicitations (blind discipline: untouched here)
        brain = LK.shared_brain()
        model = UT.load_model(LCFG.UTILITY_MODEL)
        # widen to the Evidence union so the invariant list[...] matches posterior's
        # parameter (only Elicitations exist on this path; reactions fold elsewhere)
        evidence: list[UT.Evidence] = list(UT.load_elicitations(LCFG.UTILITY_ELICITATIONS,
                                                                 model))
        post = UT.posterior(brain, model, evidence)
        for warning in post.endpoint_warnings(model.endpoint_mass_warn):
            print(f"  ⚠ {warning}")

        result = GATE.delta_posterior(paired, post, oracle_p=LK._ORACLE_P)
        elapsed = time.monotonic() - t0

        compare_meta = None
        if args.compare_run_meta:
            compare_meta = json.loads(
                Path(args.compare_run_meta).read_text(encoding="utf-8"))
        preamble = ((f"> **Baseline arm:** {baseline_name}\n\n"
                     if replay is not None else "")
                    + exec_note + grading_note
                    + tree_pin_note(run_meta["decision_path_tree"],
                                    compare=(comparison_tree(compare_meta)
                                             if compare_meta else None),
                                    compare_run_id=(compare_meta or {}).get("run_id"))
                    + corpus_note(conn, questions, corpus=corpus))
        (gate_dir / "report.md").write_text(
            preamble + GATE.render_report(result, run_id=run_id, elapsed=elapsed),
            encoding="utf-8")
        (gate_dir / "paired.jsonl").write_text(
            "".join(json.dumps(_paired_to_dict(
                        p, baseline=baseline_tag, run_id=run_id,
                        corpus_digest=corpus["digest"] or "",
                        corpus_snapshot=(f"{corpus['snapshot']}!MISMATCH"
                                         if corpus["pin_status"] == "mismatched"
                                         else corpus["snapshot"] or "")),
                    sort_keys=True) + "\n"
                    for p in paired), encoding="utf-8")

        # the judge SHADOW (opt-in) runs AFTER the gate artifacts are on disk and
        # APPENDS its section — a kill or judge failure mid-shadow can no longer void
        # the paid reading (PR #65 review; the run-3 external-kill precedent). Grading
        # is unchanged: the verdict above and every outcome row stay matcher-graded
        # (comparability; adoption pre-registered for the run after next). Fail-open
        # incl. SystemExit — core/llm's missing-key/provider-error convention.
        if args.judge_shadow:
            try:
                sys.path.insert(0, str(Path(__file__).resolve().parent / "comparison"))
                import _common as JC
                import eval_judge as EJ
                cache_path = _kb_root() / "eval" / "judge-verdicts.jsonl"
                jcache = EJ.load_verdicts(cache_path)
                items = judge_shadow_items(questions, typed_views, replay)

                def _judge(it: dict) -> bool | None:
                    return EJ.judge_with_cache(
                        jcache, cache_path, it["question"], it["gold"], it["variants"],
                        it["candidate"], complete=JC.judge_complete,
                        judge=JC.JUDGE_MODEL)
                sh_rows, sh_stats = EJ.shadow_disagreements(items, judge=_judge)
                judge_note = EJ.format_judge_shadow(sh_rows, sh_stats,
                                                    mono_covered=replay is not None)
                with (gate_dir / "report.md").open("a", encoding="utf-8") as f:
                    f.write(judge_note)
                print(f"  judge shadow: {sh_stats['n_judged']}/{sh_stats['n_items']} "
                      f"judged · agree {sh_stats['n_agree']} · "
                      f"disagree {len(sh_rows)} · unjudged {sh_stats['n_unjudged']} "
                      f"(grading unchanged)")
            except (Exception, SystemExit) as e:
                print(f"  (judge shadow failed, grading unchanged and the gate "
                      f"artifacts already written: {e})")
        # mechanical, after the judge append so the archive carries the full report —
        # the fixed paths are the NEXT run's clobber victims (runs 3/4 were lost to
        # the manual ritual; the §14 replayability invariant runs through these files)
        archive_gate_artifacts(gate_dir, run_id=run_id)
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
