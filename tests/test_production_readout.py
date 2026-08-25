"""The stage-0.3 production readout: a READOUT of the live calibration stream, never a
diagnostic arc — counts and ids only, and (the binding property) no corpus value ever
reaches the rendered report.

Run: uv run --project . python -m pytest tests/test_production_readout.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import production_readout as PR

DEC = [
    {"tx_time": "2026-08-26T10:00:00+00:00", "question_id": "q" * 16, "family": "lookup",
     "chosen_action": "report", "run_id": "ask-1", "predicted_eu": 0.5,
     "posterior_summary": {"candidates": ["SECRET-VALUE-1"], "credences": [1.0],
                           "p_none": 0.0, "n_obs": 2, "n_indeterminate": 0,
                           "n_competing": 0, "instrument": "deliberate@some-model"}},
    {"tx_time": "2026-08-26T11:00:00+00:00", "question_id": "r" * 16, "family": "lookup",
     "chosen_action": "abstain", "run_id": "ask-2", "predicted_eu": 0.0,
     "posterior_summary": {"candidates": [], "credences": [], "p_none": 0.9,
                           "n_obs": 0, "n_indeterminate": 0, "n_competing": 0}},
    {"tx_time": "2026-08-26T12:00:00+00:00", "question_id": "s" * 16, "family": "lookup",
     "chosen_action": "report", "run_id": "gate-20260826T000000", "predicted_eu": 0.7,
     "posterior_summary": {"candidates": ["EVAL-ONLY"], "credences": [1.0], "p_none": 0.0,
                           "n_obs": 1, "n_indeterminate": 0, "n_competing": 0}},
]
OUT = [
    {"tx_time": "2026-08-26T10:05:00+00:00", "question_id": "q" * 16, "grade": "INCORRECT",
     "grader": "matcher", "probability": 0.9, "run_id": "ask-1",
     "instrument_identity": {"edge": "deliberate@some-model"},
     "claim": "SECRET-VALUE-1"},
]
REA = [
    {"tx_time": "2026-08-26T10:06:00+00:00", "question_id": "q" * 16, "decision_id": "d1",
     "kind": "answer", "valence": "bad"},
]


def test_readout_counts_actions_watches_wrongs_and_excludes_eval_runs() -> None:
    s = PR.readout(DEC, OUT, REA, since="2026-08-25")
    assert s["decisions"]["report"] == 1          # the gate- run is excluded
    assert s["decisions"]["abstain"] == 1
    assert s["deliberate_commits"] == 1
    assert s["wrong"][0]["question_id"] == "q" * 16
    assert s["reactions"]["bad"] == 1


def test_the_rendered_report_carries_no_corpus_value() -> None:
    s = PR.readout(DEC, OUT, REA, since="2026-08-25")
    text = PR.render(s)
    assert "SECRET-VALUE-1" not in text           # the binding property: ids, never values
    assert "q" * 16 in text
    assert "deliberate@some-model" in text        # instrument names are not corpus values


def test_since_filters_by_tx_time() -> None:
    s = PR.readout(DEC, OUT, REA, since="2026-08-27")
    assert s["decisions"] == {} and s["wrong"] == [] and s["reactions"] == {}
