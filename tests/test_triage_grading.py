"""Unit tests for the triage classifier (scripts/triage_grading.py).

The classifier crosses the RETRIEVAL channel (was the truth retrievable?) with the
DECISION channel (did the agent assert, and was it right?) to bucket every question
by the lever that would fix it. Pure logic, no IO. Run from the repo root:

    uv run --project . python -m pytest ./tests/test_triage_grading.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from triage_grading import gate_assertions, triage


def _sub(gold: str, variants: list[str], text: str) -> bool:
    """A tiny substring matcher standing in for answer_matches (keeps these tests pure)."""
    return any(g in text for g in [gold, *variants])


def _t(**kw):
    """A fully-specified call with answerable/reachable defaults the case overrides."""
    base = dict(
        answerable=True,
        asserted=False,
        asserted_correct=False,
        asserted_distractor=False,
        gold_in_candidates=False,
        gold_in_topk=False,
        gold_in_corpus=False,
    )
    base.update(kw)
    return triage(**base)


# --- gate_assertions: per-field attribution of the gold for a compound answer ----------


def test_gate_assertions_single_value_returns_the_union() -> None:
    # No per-field detail (a single-value answer) → grade the asserted values as-is.
    assert gate_assertions(None, ["P123"], "P123", [], matches=_sub) == ["P123"]


def test_gate_assertions_attributes_to_the_gold_field() -> None:
    # The gold field reported the gold → it is the gate-relevant assertion (→ CORRECT downstream).
    fields = [{"asserted": ["BankCo"], "candidates": ["BankCo"]},
              {"asserted": ["250000"], "candidates": ["250000"]}]
    assert gate_assertions(fields, ["BankCo", "250000"], "250000", [],
                           matches=_sub) == ["250000"]


def test_gate_assertions_excludes_sibling_when_gold_field_withheld() -> None:
    # The gold field (its candidates hold the gold) ABSTAINED; a sibling reported. The sibling
    # answers a different sub-question we hold no gold for → it is NOT gate-relevant, so the gate
    # sees no assertion (→ WRONGLY_WITHHELD, never a false confident-wrong).
    fields = [{"asserted": ["BankCo"], "candidates": ["BankCo"]},           # sibling, reported
              {"asserted": [], "candidates": ["250000", "260000"]}]          # gold field, withheld
    assert gate_assertions(fields, ["BankCo"], "250000", [], matches=_sub) == []


def test_gate_assertions_keeps_gold_field_wrong_value() -> None:
    # The gold field had the gold in candidates but reported a DIFFERENT value → a genuine
    # confident-wrong; the wrong assertion stays gate-relevant.
    fields = [{"asserted": ["BankCo"], "candidates": ["BankCo"]},
              {"asserted": ["260000"], "candidates": ["250000", "260000"]}]  # had gold, said other
    assert gate_assertions(fields, ["BankCo", "260000"], "250000", [],
                           matches=_sub) == ["260000"]


def test_gate_assertions_falls_back_to_union_when_gold_unextracted() -> None:
    # No field extracted the gold (it is in nobody's candidates) → we cannot attribute, so grade
    # the union conservatively (never hide a possible wrong by attribution failure).
    fields = [{"asserted": ["BankCo"], "candidates": ["BankCo"]},
              {"asserted": ["999"], "candidates": ["999"]}]
    assert gate_assertions(fields, ["BankCo", "999"], "250000", [],
                           matches=_sub) == ["BankCo", "999"]


# --- asserted answers: CORRECT vs the cardinal sin --------------------------


def test_asserted_and_correct_is_correct() -> None:
    t = _t(asserted=True, asserted_correct=True, gold_in_candidates=True,
           gold_in_topk=True, gold_in_corpus=True)
    assert t.bucket == "CORRECT"
    assert t.cause is None
    assert t.needs_judgment  # Opus confirms genuine + current, not a coincidental match


def test_asserted_wrong_value_is_confident_wrong() -> None:
    t = _t(asserted=True, asserted_correct=False, gold_in_candidates=True,
           gold_in_topk=True, gold_in_corpus=True)
    assert t.bucket == "CONFIDENT_WRONG"
    assert t.cause == "wrong_value"
    assert t.needs_judgment  # Opus confirms truly wrong, not an unlisted variant


def test_asserted_distractor_is_confident_wrong() -> None:
    t = _t(asserted=True, asserted_correct=False, asserted_distractor=True,
           gold_in_corpus=True)
    assert t.bucket == "CONFIDENT_WRONG"
    assert t.cause == "distractor"


def test_correct_assertion_outranks_a_coincidental_distractor_match() -> None:
    # a value can token-match both the gold and a distractor; correctness wins
    t = _t(asserted=True, asserted_correct=True, asserted_distractor=True,
           gold_in_candidates=True, gold_in_topk=True, gold_in_corpus=True)
    assert t.bucket == "CORRECT"


# --- scoped: a true time-scoped claim, never the cardinal sin ---------------


def test_scoped_is_its_own_bucket_never_confident_wrong() -> None:
    # report_scoped asserts "as of <date>, X" — true about the record even when the gold
    # (current value) differs and is not in candidates; it must never grade confident-wrong.
    t = _t(scoped=True, asserted=True, asserted_correct=False, gold_in_corpus=True)
    assert t.bucket == "SCOPED"
    assert t.cause == "as_of_record"
    assert t.needs_judgment  # the oracle confirms the record genuinely attests it


# --- the owner's temporal verdict overrides token-match ---------------------


def test_owner_stale_plain_assertion_is_a_confident_wrong() -> None:
    # owner: "a stale answer is still wrong" for a current-value question. A plainly-asserted
    # stale value is a confident-wrong, tagged stale_value (the recency/scoping-fixable kind);
    # only a SCOPED rendering (scoped=True) escapes the sin.
    t = _t(asserted=True, asserted_correct=False, gold_in_corpus=True,
           asserted_verdict="stale")
    assert t.bucket == "CONFIDENT_WRONG"
    assert t.cause == "stale_value"
    assert not t.needs_judgment  # the owner already judged it stale


def test_scoped_stale_value_is_an_honest_non_answer_not_a_sin() -> None:
    # the same stale value, but SCOPED ("as of <date>, X"): the SCOPED bucket, never the sin.
    t = _t(scoped=True, asserted=True, asserted_correct=False, asserted_verdict="stale")
    assert t.bucket == "SCOPED"


def test_owner_correct_verdict_overrides_token_mismatch() -> None:
    # token-match says wrong (a co-valid answer like "Ben Craft"), but the owner labelled it
    # correct — his verdict wins, no oracle needed.
    t = _t(asserted=True, asserted_correct=False, asserted_verdict="correct")
    assert t.bucket == "CORRECT"
    assert not t.needs_judgment


def test_owner_wrong_verdict_is_a_confirmed_sin() -> None:
    t = _t(asserted=True, asserted_correct=True, asserted_verdict="wrong")
    assert t.bucket == "CONFIDENT_WRONG"
    assert not t.needs_judgment  # owner-confirmed, not a token-match guess


# --- rightly withheld: nothing clean to say ---------------------------------


def test_withheld_unanswerable_is_rightly_withheld() -> None:
    t = _t(answerable=False)
    assert t.bucket == "RIGHTLY_WITHHELD"
    assert t.cause == "unanswerable"
    assert not t.needs_judgment


def test_withheld_answerable_but_absent_is_coverage_gap() -> None:
    # the truth exists in the world but is not in the corpus: an ingestion gap
    t = _t(answerable=True, gold_in_corpus=False)
    assert t.bucket == "RIGHTLY_WITHHELD"
    assert t.cause == "coverage_gap"
    assert not t.needs_judgment


# --- wrongly withheld: the answer-rate loss, bucketed by where truth was lost --


def test_withheld_truth_in_corpus_not_topk_is_retrieval_miss() -> None:
    t = _t(gold_in_corpus=True, gold_in_topk=False)
    assert t.bucket == "WRONGLY_WITHHELD"
    assert t.cause == "retrieval_miss"
    assert not t.needs_judgment


def test_withheld_truth_in_chunk_not_extracted_is_extraction_miss() -> None:
    t = _t(gold_in_corpus=True, gold_in_topk=True, gold_in_candidates=False)
    assert t.bucket == "WRONGLY_WITHHELD"
    assert t.cause == "extraction_miss"
    assert not t.needs_judgment


def test_withheld_truth_extracted_but_lost_is_pooling_loss() -> None:
    # the mobile-number class: the true value was a candidate but lost the posterior
    t = _t(gold_in_corpus=True, gold_in_topk=True, gold_in_candidates=True)
    assert t.bucket == "WRONGLY_WITHHELD"
    assert t.cause == "pooling_loss"
    assert t.needs_judgment  # Opus: genuine ambiguity vs a recoverable answer


# --- precedence: an assertion is graded on the decision channel regardless of
# where retrieval landed (a confident-wrong with a retrieval miss is still the sin) --


def test_confident_wrong_even_when_retrieval_also_missed() -> None:
    t = _t(asserted=True, asserted_correct=False, gold_in_corpus=True,
           gold_in_topk=False, gold_in_candidates=False)
    assert t.bucket == "CONFIDENT_WRONG"
    assert t.cause == "wrong_value"
