"""Grading composition for the fair-fight harness — turns one arm's raw answer for one
question into the deterministic channel grades a later runner folds into an
``OutcomeVector`` (``src/life_agent/fairfight/records.py``).

This module composes EXISTING referee machinery (never rebuilds it):

- ``scripts/eval_grading.py`` — ``answer_matches``/``chunk_matches_any`` (the shared
  token-boundary matcher) for gold/distractor presence checks.
- ``scripts/triage_grading.py`` — ``triage()`` crosses the retrieval and decision
  channels into one ``(bucket, cause, needs_judgment)``. Only ``bucket``/``cause`` are
  carried into ``ChannelGrades``: ``needs_judgment`` flags rows for the Opus-oracle
  adjudication triage_answers.py runs offline; the harness's blind rubric judge (a later
  task) is a different instrument and does not consume it here.
- ``scripts/run_eval.py`` — ``_answer_in_corpus`` (FTS set-membership, not a LIKE scan;
  imported by name — same cross-script pattern ``eval_executor.py``/``triage_answers.py``
  already use — so a test can monkeypatch ``grading._answer_in_corpus`` directly).
- ``scripts/ask.py`` — ``ABSTENTION`` (the synthesis path's frozen decline string),
  imported lazily inside :func:`detect_decline` to keep this module's own import light.

``run_eval._classify_synthesis`` and ``life_agent.core.citation.audit`` are named in the
task's reuse map but are NOT called here: ``_classify_synthesis`` needs judge scores
(``faithfulness``/``citation_fidelity``) this module never sees, and ``citation.audit``
needs ``SourceLike`` card objects ``grade_channels`` never receives either — both are the
runner/judge stage's job. What this module DOES produce for that stage is
:func:`hermes_citation_check`'s bool: the structural half of ``_classify_synthesis``'s
``structural_unsupported`` flag for the competitor's raw-text ``[bracket]`` citations
(``core.citation.audit`` is the parallel structural check the runner calls directly for
the ``[n]``-citing arms, which already hand it real ``SourceLike`` cards).

**decision_view contract.** ``grade_channels``'s ``decision_view`` parameter is the
normalized dict shape ``scripts/triage_answers.py`` builds via ``_lookup_view`` /
``_narrative_view`` / ``_withheld_view``: at minimum ``action`` (str), ``asserted``
(bool), ``asserted_values`` (list[str]), ``candidates`` (list[str]), and optionally
``scoped`` (bool, lookup-only — a ``report_scoped`` decision, a true time-scoped claim
that is never the cardinal sin). Arms that reuse the production ``ask.answer`` path
(synthesis) build this view the same way ``triage_answers.py`` does. Arms with no
structured decision object at all — the hermes competitor, and any other raw-text arm —
pass ``decision_view=None`` and are graded as **free text**: ``declined`` comes from
:func:`detect_decline` over the whole answer, "asserted" is ``not declined``, and a
value/distractor match is checked over the whole answer text (there is no separate list
of candidate values to check against).

**The competitor / no-candidate-stage mapping.** ``triage()`` needs a
``gold_in_candidates`` bool to distinguish ``extraction_miss`` (surfaced in top-k, never
promoted to a candidate) from ``pooling_loss`` (surfaced as a candidate, lost the
posterior). A free-text arm cannot report that distinction — there is no candidate
stage — so we feed ``gold_in_candidates := gold_in_topk`` into ``triage()`` (the best
available proxy: "was it visible at all") and expose ``gold_in_candidates=None`` on the
returned ``ChannelGrades`` (never imputed — ``records.py``'s documented convention for
"this arm has no candidate stage"). One consequence: ``extraction_miss`` can
structurally never fire for such an arm — every truth that was visible in top-k but
unasserted lands in ``pooling_loss``, which is therefore read as the residual "the arm
saw it and withheld it anyway" bucket for these arms, not literally "lost between chunk
and candidate."
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from eval_grading import answer_matches, chunk_matches_any
from run_eval import _answer_in_corpus
from triage_grading import triage

# Fallback decline-phrasing regexes (case-insensitive, searched anywhere in the answer
# text — unlike the ABSTENTION/NOT_IN_CORPUS checks, these are NOT exact-match). Kept to
# exactly the phrasings named in the plan: broadening this list risks false-positiving a
# real assertion that merely mentions "corpus" or "know" in passing.
_DECLINE_PHRASE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bnot in the corpus\b", re.IGNORECASE),
    re.compile(r"\bno information in\b", re.IGNORECASE),
    re.compile(r"\bi don'?t know\b", re.IGNORECASE),
    re.compile(r"\bcannot find\b", re.IGNORECASE),
    re.compile(r"\bdon'?t have (?:a|any|enough)\b", re.IGNORECASE),
)

# One bracket group, e.g. "[a.txt]" or "[a.txt, b.txt]" — deliberately excludes nested
# brackets so "[[n]]"-style numeric markers don't get mistaken for hermes file citations.
_BRACKET_RE = re.compile(r"\[([^\[\]]+)\]")


@dataclass(frozen=True)
class ChannelGrades:
    """The deterministic decision + retrieval channels for one (arm, question) — every
    field an ``OutcomeVector`` needs from those two axis groups (see the module
    docstring for how each is derived; the rubric/calibration/economics/effort/
    provenance axes are populated elsewhere, by the judge and the runner)."""

    bucket: str
    cause: str | None
    asserted: bool
    asserted_correct: bool
    asserted_distractor: bool
    declined: bool
    correct_abstention: bool
    over_abstention: bool
    gold_in_topk: bool
    gold_in_corpus: bool
    gold_in_candidates: bool | None  # None: this arm has no candidate stage
    distractor_in_topk: bool
    n_retrieved: int


def detect_decline(text: str) -> bool:
    """True iff ``text`` is a decline/withholding, checked in three ways:

    1. Any line starting ``NOT_IN_CORPUS:`` — the hermes competitor prompt's own
       contract (``scripts/fairfight/arm_hermes.py``'s ``PROMPT_V1``).
    2. ``text`` equals ``ask.ABSTENTION`` exactly — the synthesis path's frozen decline
       string (a prefix or paraphrase does NOT count; only the literal render does).
    3. A fallback phrasing regex (case-insensitive, matched anywhere in the text) for
       free-text arms that decline in their own words.
    """
    if any(line.strip().startswith("NOT_IN_CORPUS:") for line in text.splitlines()):
        return True
    from ask import ABSTENTION  # sibling script; sys.path set at module load, above

    if text == ABSTENTION:
        return True
    return any(p.search(text) for p in _DECLINE_PHRASE_PATTERNS)


def _retrieval_channel(
    q: dict, retrieved_texts_full: list[str], *, answerable: bool, conn: Any,
) -> tuple[bool, bool, bool, int]:
    """The channel shared by every arm regardless of decision shape: is the gold/a
    distractor present in what was retrieved, and is the gold anywhere in the corpus at
    all? Mirrors ``triage_answers.py``'s ``triage_one`` retrieval-channel computation."""
    gold = q.get("answer", "")
    variants = q.get("answer_variants", []) or []
    distractors = q.get("distractors", []) or [] if q.get("subject", "n/a") != "n/a" else []

    gold_in_topk = answerable and chunk_matches_any(gold, variants, retrieved_texts_full)
    gold_in_corpus = gold_in_topk or (
        answerable and _answer_in_corpus(conn, gold, variants))
    distractor_in_topk = any(
        answer_matches(d, [], t) for d in distractors for t in retrieved_texts_full)
    return bool(gold_in_topk), bool(gold_in_corpus), bool(distractor_in_topk), len(
        retrieved_texts_full)


def grade_channels(
    q: dict, answer_text: str, retrieved_texts_full: list[str],
    decision_view: dict | None, conn: Any,
) -> ChannelGrades:
    """Grade one arm's answer to one question: the retrieval channel (was the gold
    reachable, and where?) crossed with the decision channel (did the arm assert, and
    was it right?) via ``triage_grading.triage``. See the module docstring for the
    ``decision_view`` contract and the no-candidate-stage mapping."""
    gold = q.get("answer", "")
    variants = q.get("answer_variants", []) or []
    subject = q.get("subject", "n/a")
    distractors = q.get("distractors", []) or [] if subject != "n/a" else []
    answerable = bool(q.get("answerable", bool(gold)))

    gold_in_topk, gold_in_corpus, distractor_in_topk, n_retrieved = _retrieval_channel(
        q, retrieved_texts_full, answerable=answerable, conn=conn)

    gold_in_candidates_out: bool | None
    if decision_view is not None:
        action = decision_view.get("action")
        scoped = bool(decision_view.get("scoped", False))
        asserted = bool(decision_view.get("asserted", False))
        declined = action in ("abstain", "ask_clarify")
        asserted_values = decision_view.get("asserted_values") or []
        candidates = decision_view.get("candidates") or []
        asserted_correct = answerable and any(
            answer_matches(gold, variants, a) for a in asserted_values)
        asserted_distractor = any(
            answer_matches(d, [], a) for d in distractors for a in asserted_values)
        gold_in_candidates_for_triage = answerable and any(
            answer_matches(gold, variants, c) for c in candidates)
        gold_in_candidates_out = bool(gold_in_candidates_for_triage)
    else:
        # free text: no candidate list, no structured action — decline detection stands
        # in for the whole decision, and matching runs over the whole answer text.
        declined = detect_decline(answer_text)
        asserted = not declined
        scoped = False
        asserted_correct = answerable and asserted and answer_matches(
            gold, variants, answer_text)
        asserted_distractor = asserted and any(
            answer_matches(d, [], answer_text) for d in distractors)
        gold_in_candidates_for_triage = gold_in_topk
        gold_in_candidates_out = None  # no candidate stage: never imputed

    t = triage(
        answerable=answerable, asserted=bool(asserted),
        asserted_correct=bool(asserted_correct), asserted_distractor=bool(asserted_distractor),
        gold_in_candidates=bool(gold_in_candidates_for_triage), gold_in_topk=gold_in_topk,
        gold_in_corpus=gold_in_corpus, scoped=scoped,
    )

    correct_abstention = declined and not answerable
    over_abstention = declined and answerable and gold_in_corpus

    return ChannelGrades(
        bucket=t.bucket, cause=t.cause,
        asserted=bool(asserted), asserted_correct=bool(asserted_correct),
        asserted_distractor=bool(asserted_distractor),
        declined=bool(declined), correct_abstention=bool(correct_abstention),
        over_abstention=bool(over_abstention),
        gold_in_topk=gold_in_topk, gold_in_corpus=gold_in_corpus,
        gold_in_candidates=gold_in_candidates_out,
        distractor_in_topk=distractor_in_topk, n_retrieved=n_retrieved,
    )


def hermes_citation_check(answer_text: str, tool_log_rows: list[dict]) -> bool:
    """True iff every ``[bracketed]`` citation token in ``answer_text`` names a
    ``source_path`` the hermes competitor's own tool calls actually returned (the
    competitor prompt's contract: cite source files in ``[brackets]`` exactly as the
    tools returned them). Feeds the structural half of ``run_eval._classify_synthesis``'s
    ``structural_unsupported`` flag for the competitor arm (the caller inverts this bool).

    ``tool_log_rows`` is the parsed ``pkm serve --tool-log`` JSONL (one dict per tool
    call, each with a ``results`` list of dicts carrying ``source_path`` — see
    ``src/pkm/mcp_server.py``). A bracket may hold more than one reference
    (``"[a.pdf, b.pdf]"`` or consecutive ``"[a.pdf][b.pdf]"``) — each is checked
    independently. Citations are accepted against either the full ``source_path`` or its
    basename (a model citing "id_card.txt" for a tool result whose ``source_path`` is
    "/tmp/corpus/id_card.txt" is not a citation fault; hermes was told "exactly as the
    tools returned them" but real models paraphrase the path). No bracket tokens at all
    is vacuously True (nothing to check) — including on an empty tool log.
    """
    known: set[str] = set()
    for row in tool_log_rows:
        for result in row.get("results") or []:
            source_path = result.get("source_path")
            if source_path:
                known.add(source_path)
                known.add(Path(source_path).name)

    tokens = [
        part.strip()
        for group in _BRACKET_RE.findall(answer_text)
        for part in group.split(",")
        if part.strip()
    ]
    if not tokens:
        return True
    return all(token in known for token in tokens)
