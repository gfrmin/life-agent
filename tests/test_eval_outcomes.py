"""run_eval's outcome builders (bayesian-foundations §8): pure, no IO, no DB.

The builders map graded eval rows to OutcomeEvents; construction validates grades against
the closed grader vocabularies in life_agent.core.outcomes, so these tests double as the
drift gate between the eval's verdict vocabulary and the calibration log's.

Run: uv run --project . python -m pytest tests/test_eval_outcomes.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "comparison"))

import run_eval as re_

from life_agent.core import outcomes as O


def _synth_row(**overrides: object) -> dict:
    base: dict = dict(
        id="q-001", question="what is X?", answerable=True,
        faithfulness=3, citation_fidelity=3, structural_ok=True,
        answer="X is 42 [1]", served=["m"], lineage_keys=("rk", "sk"),
        synthesis_pass=True, hallucinated=False, abstained_correctly=False,
    )
    base.update(overrides)
    return base


# --- synthesis_grade_label precedence ---------------------------------------------------

def test_label_pass() -> None:
    assert re_.synthesis_grade_label(_synth_row()) == "PASS"


def test_label_hallucinated_wins_over_everything() -> None:
    row = _synth_row(hallucinated=True, synthesis_pass=True)
    assert re_.synthesis_grade_label(row) == "HALLUCINATED"


def test_label_abstained_ok_for_honest_unanswerable() -> None:
    row = _synth_row(answerable=False, abstained_correctly=True, synthesis_pass=True)
    assert re_.synthesis_grade_label(row) == "ABSTAINED_OK"


def test_label_weak_when_neither_grounded_nor_fabricated() -> None:
    row = _synth_row(synthesis_pass=False)
    assert re_.synthesis_grade_label(row) == "WEAK"


def test_every_label_is_in_the_grader_vocabulary() -> None:
    # drift gate: the builder can only emit grades the log accepts
    rows = [
        _synth_row(),
        _synth_row(hallucinated=True),
        _synth_row(answerable=False, abstained_correctly=True),
        _synth_row(synthesis_pass=False),
    ]
    for row in rows:
        assert re_.synthesis_grade_label(row) in O.GRADERS["eval_synthesis"]


# --- builders produce valid, attributed events ------------------------------------------

def test_retrieval_outcome_event() -> None:
    r = {"id": "q-007", "verdict": "RETRIEVAL_MISS"}
    q = {"answer": "123456789"}
    e = re_.retrieval_outcome(r, q, k=20, run_id="eval-retrieval-test")
    assert e.grader == "eval_retrieval" and e.grade == "RETRIEVAL_MISS"
    assert e.construct == "selection"
    assert e.claim == "123456789"
    assert e.instrument_identity["producer_config"]["k"] == 20
    assert e.probability is None and e.lineage_keys == ()


def test_retrieval_outcome_unanswerable_claim_is_named() -> None:
    e = re_.retrieval_outcome({"id": "q-009", "verdict": "ABSENT_COVERAGE"},
                              {"answer": ""}, k=20, run_id="r")
    assert e.claim == "(none — known-unanswerable)"


def test_synthesis_outcome_event_carries_lineage() -> None:
    e = re_.synthesis_outcome(_synth_row(), run_id="eval-synthesis-test")
    assert e.grader == "eval_synthesis" and e.grade == "PASS"
    assert e.construct == "grounded-answer"
    assert e.lineage_keys == ("rk", "sk")
    assert e.instrument_identity["producer_name"] == "life_agent.ask.synthesize"
    assert e.probability is None


def test_unknown_verdict_fails_loudly() -> None:
    # a new eval verdict must be declared in the grader vocabulary, never silently logged
    with pytest.raises(ValueError, match="grade"):
        re_.retrieval_outcome({"id": "q", "verdict": "SHRUG"}, {"answer": "x"},
                              k=20, run_id="r")


# --- the narrative family's claim + coverage streams (§7, slice 3) -----------------------

def _nv(*claims):
    from types import SimpleNamespace

    return SimpleNamespace(claims=list(claims), answer_cache_key="nak")


def _claim(text: str, cell: str = "verified", credence: float = 0.7,
           included: bool = True):
    from types import SimpleNamespace

    return SimpleNamespace(text=text, cell=cell, credence=credence, included=included)


_Q = {"id": "q-042", "answer": "999999991", "answer_variants": [],
      "distractors": ["888888884"]}


def test_narrative_claim_rows_grade_gold_and_distractor_only() -> None:
    nv = _nv(_claim("Your number is 999999991."),
             _claim("Another card shows 888888884.", cell="unsupported",
                    credence=0.25, included=False),
             _claim("It is renewed annually.", cell="unverifiable", credence=0.5))
    rows = re_.narrative_claim_rows(_Q, nv)
    assert [(r["correct"], r["signals"]["audit_cell"]) for r in rows] == [
        (True, "verified"), (False, "unsupported")]
    assert rows[0]["probability"] == 0.7
    assert rows[1]["signals"]["included"] is False


def test_narrative_claim_rows_gold_wins_over_distractor() -> None:
    nv = _nv(_claim("Mine is 999999991, the other card 888888884."))
    rows = re_.narrative_claim_rows(_Q, nv)
    assert len(rows) == 1 and rows[0]["correct"] is True


def test_narrative_claim_outcome_event() -> None:
    from life_agent.core import narrative as N

    nv = _nv(_claim("Your number is 999999991."))
    row = re_.narrative_claim_rows(_Q, nv)[0]
    e = re_.narrative_claim_outcome(_Q, nv, row, run_id="r")
    assert e.grader == "eval_claim" and e.grade == "CORRECT"
    assert e.construct == "claim"
    assert e.probability == 0.7
    assert e.signals == {"audit_cell": "verified", "included": True}
    assert e.instrument_identity == N.instrument_identity()
    assert e.lineage_keys == ("nak",)


def test_coverage_outcome_proposed_missed_and_unanswerable() -> None:
    proposed = re_.coverage_outcome(_Q, _nv(_claim("It is 999999991.")), run_id="r")
    assert proposed.grade == "PROPOSED" and proposed.grader == "eval_coverage"
    assert proposed.signals == {"n_claims": 1}
    missed = re_.coverage_outcome(_Q, _nv(_claim("No number found.")), run_id="r")
    assert missed.grade == "MISSED"
    # an unproposable question (no gold answer) emits nothing
    assert re_.coverage_outcome({"id": "q", "answer": ""}, _nv(), run_id="r") is None


def test_coverage_counts_withheld_proposals_too() -> None:
    # coverage measures the PROPOSER, pre-decision: a withheld gold claim is PROPOSED
    nv = _nv(_claim("It is 999999991.", included=False, credence=0.3))
    assert re_.coverage_outcome(_Q, nv, run_id="r").grade == "PROPOSED"
