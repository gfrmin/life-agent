#!/usr/bin/env python3
"""Shadow correctness judge for the Δ2 gate — measured beside the matcher, never instead.

The token-boundary matcher (eval_grading.answer_matches) has two live failure modes:
it UNDER-credits format/paraphrase answers (the deliberative π* run's 8/104
adjudication-shaped misses) and OVER-credits correction-shaped sentences that mention
the gold while superseding it. An LLM judge fixes both directions — but a grader change
moves Δ and the reliability curves directly, so it enters under the eval-rigor rules:

- SHADOW-ONLY here: the gate verdict and every outcome row stay matcher-graded
  (run 5 remains comparable to runs 3/4); this module only publishes the
  matcher-vs-judge disagreement table for hand audit. Adoption is pre-registered
  for run 6 iff that audit clears — never a silent mid-series grader swap.
- CROSS-PROVIDER by construction: the judge rides ``_common.judge_complete``
  (OpenAI-family pin), so it does not share the Anthropic answering models'
  blind spots — a same-family judge is correlated error, not measurement.
- BLIND: the judge sees (question, gold, variants, candidate) and NOTHING about
  which arm produced the candidate (the citation-shape-leak lesson).
- MODAL-OF-N over VALID votes: garbled/erroring votes are None; fewer than two
  valid votes, or a tie, is UNJUDGED (None) — one model's word, or a coin flip,
  is not a verdict. Unjudged items are counted and disclosed, never guessed.
- CACHED append-only (``$LIFE_AGENT_KB/eval/judge-verdicts.jsonl``): re-runs are
  free and deterministic by replay; None verdicts are NEVER cached (a transient
  failure must not poison future replays).
"""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from eval_grading import answer_matches

JUDGE_PROMPT_VERSION = "1"  # bump on ANY change to JUDGE_SYSTEM or the user template
JUDGE_SYSTEM = (
    "You grade whether a CANDIDATE answer asserts the same fact as a GOLD answer to a "
    "question. Reply with STRICT JSON only: {\"correct\": true} or {\"correct\": false}. "
    "correct=true iff the candidate asserts the gold value — in any format, wording, "
    "unit spelling, or language, including inside a longer sentence. correct=false if "
    "the candidate asserts a different value, asserts no value, only refuses or asks a "
    "question, or MENTIONS the gold while correcting, superseding, or denying it "
    "(mentioning is not asserting). Judge the fact, not the style."
)
_N = 3  # modal-of-N (matches the synthesis grader's convention)


def judge_key(question: str, gold: str, variants: list[str], candidate: str, *,
              judge: str) -> str:
    """Content-addressed verdict identity: prompt version + the JUDGE MODEL PIN + the
    exact judged inputs. The judge is part of the identity (PR #65 review): without it,
    bumping the JUDGE_MODEL pin silently replays the old model's cached verdicts — the
    exact silent-grader-swap this module forbids."""
    payload = json.dumps(
        {"v": JUDGE_PROMPT_VERSION, "judge": judge, "question": question, "gold": gold,
         "variants": list(variants), "candidate": candidate},
        sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _user_prompt(question: str, gold: str, variants: list[str], candidate: str) -> str:
    # blind: question/gold/variants/candidate ONLY — arm identity never enters
    v = f"\nGOLD VARIANTS: {' | '.join(variants)}" if variants else ""
    return (f"QUESTION: {question}\nGOLD: {gold}{v}\nCANDIDATE: {candidate}")


def _parse_vote(text: str) -> bool | None:
    """Fail-safe parse (the joint_extract._parse precedent): a garbled reply is a None
    vote, never a guessed one."""
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    v = obj.get("correct")
    return v if isinstance(v, bool) else None


def judge_correct(question: str, gold: str, variants: list[str], candidate: str, *,
                  complete: Callable[[str, str], Any], n: int = _N) -> bool | None:
    """Modal-of-n verdict over VALID votes; None (unjudged) on thin or tied votes.
    Each vote is fail-open — including SystemExit, which core/llm raises for a missing
    key or provider error and which would sail through ``except Exception`` and void a
    PAID gate run (PR #65 review; the run_fairfight precedent). Early-exits the moment
    the remaining votes cannot change the majority-of-valid outcome (byte-identical
    verdicts at ~2/3 the calls on agreeing judges)."""
    user = _user_prompt(question, gold, variants, candidate)
    votes: list[bool | None] = []
    for i in range(n):
        try:
            votes.append(_parse_vote(complete(JUDGE_SYSTEM, user).text))
        except (Exception, SystemExit):
            votes.append(None)
        t = sum(v is True for v in votes)
        f = sum(v is False for v in votes)
        remaining = n - i - 1
        if t > f + remaining or f > t + remaining:
            break
    valid = [v for v in votes if v is not None]
    if len(valid) < 2 or sum(valid) * 2 == len(valid):
        return None
    return sum(valid) * 2 > len(valid)


def load_verdicts(path: Path) -> dict[str, bool]:
    """The append-only verdict cache, loaded as {key: correct}."""
    out: dict[str, bool] = {}
    if path.exists():
        for ln in path.read_text(encoding="utf-8").splitlines():
            if ln.strip():
                rec = json.loads(ln)
                out[str(rec["key"])] = bool(rec["correct"])
    return out


def judge_with_cache(cache: dict[str, bool], path: Path | None, question: str,
                     gold: str, variants: list[str], candidate: str, *,
                     complete: Callable[[str, str], Any], judge: str,
                     n: int = _N) -> bool | None:
    """Cache-first verdict; a live verdict is appended (None never cached — a transient
    failure must not freeze into future replays). ``judge`` is the model pin, part of
    the verdict identity and recorded beside it."""
    key = judge_key(question, gold, variants, candidate, judge=judge)
    if key in cache:
        return cache[key]
    verdict = judge_correct(question, gold, variants, candidate, complete=complete, n=n)
    if verdict is None:
        return None
    cache[key] = verdict
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"key": key, "correct": verdict, "judge": judge,
                                "prompt_version": JUDGE_PROMPT_VERSION},
                               sort_keys=True) + "\n")
    return verdict


def shadow_disagreements(items: list[dict], *,
                         judge: Callable[[dict], bool | None]) -> tuple[list[dict], dict]:
    """Grade every item both ways; return (disagreement rows, stats). The matcher verdict
    is recomputed here from the same (gold, variants, candidate) the run graded with, so
    the comparison is exact, never a re-derivation drift."""
    rows: list[dict] = []
    stats = {"n_items": 0, "n_judged": 0, "n_unjudged": 0, "n_agree": 0}
    for it in items:
        stats["n_items"] += 1
        m = answer_matches(it["gold"], it["variants"], it["candidate"])
        jv = judge(it)
        if jv is None:
            stats["n_unjudged"] += 1
            continue
        stats["n_judged"] += 1
        if jv == bool(m):
            stats["n_agree"] += 1
        else:
            rows.append({**it, "matcher": "CORRECT" if m else "INCORRECT",
                         "judge": "CORRECT" if jv else "INCORRECT"})
    return rows, stats


def _cell(s: object) -> str:
    """Markdown-table-safe cell: the disagreement table IS the pre-registered audit
    artifact — a newline or pipe in a candidate must not shift verdicts onto wrong
    questions (PR #65 review)."""
    return str(s).replace("\n", " ")[:80].replace("|", "\\|")


def format_judge_shadow(rows: list[dict], stats: dict,
                        mono_covered: bool = True) -> str:
    """The report section — SHADOW framing first, disagreements as the audit table,
    coverage gaps disclosed (no silent caps)."""
    lines = [
        "",
        "## Judge shadow (SHADOW only — grading unchanged)",
        "",
        f"Cross-provider modal-of-{_N} correctness judge beside the token matcher; the "
        "gate verdict and every outcome row above are MATCHER-graded. Adoption is "
        "pre-registered for the run after next iff this disagreement audit clears "
        "(bayesian-foundations §14).",
        "",
        f"- items judged: {stats['n_judged']}/{stats['n_items']} "
        f"(unjudged {stats['n_unjudged']} — thin/tied votes, disclosed never guessed)",
    ]
    if not mono_covered:
        lines.append("- mono arm NOT shadowed — the live monolithic baseline's text is "
                     "not captured; only a replay baseline is covered")
    if stats["n_judged"]:
        lines.append(f"- agreement: {stats['n_agree']}/{stats['n_judged']}")
    if not rows:
        lines.append("- no disagreements — the matcher and the judge grade this run "
                     "identically")
    else:
        lines += ["", "| question | arm | matcher | judge | candidate |",
                  "| --- | --- | --- | --- | --- |"]
        lines += [f"| {_cell(r['question_id'])} | {_cell(r['arm'])} "
                  f"| {r['matcher']} | {r['judge']} | {_cell(r['candidate'])} |"
                  for r in rows]
    return "\n".join(lines) + "\n"
