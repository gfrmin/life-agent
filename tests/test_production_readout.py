"""The stage-0.3 production readout: a READOUT of the live calibration stream, never a
diagnostic arc — counts and ids only, and (the binding property) no corpus value ever
reaches the rendered report.

Run: uv run --project . python -m pytest tests/test_production_readout.py
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime
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


# --- K3/S5 (C9): the live stream is not a singleton, and a silent watch is visible ------
#
# The readout accrues on whichever box serves. Before K3 the report named one KB root,
# reported nothing about its own window, and a watch that had stopped running looked
# exactly like a watch with nothing to report — an ABSENT file, which nothing reads.

_NOW = datetime(2026, 8, 27, 12, 0, 0, tzinfo=UTC)


def test_the_window_names_the_newest_row_and_its_age() -> None:
    s = PR.readout(DEC, OUT, REA, since="2026-08-25", now=_NOW)
    w = s["window"]
    assert w["newest"] == "2026-08-26T11:00:00+00:00", (
        "the window must name the newest PRODUCTION row — the eval row at 12:00 carries a "
        "gate- run_id, and a run that is excluded from the counts must not set the window "
        "either, or an eval sweep would make a dead stream look fresh")
    assert w["age_days"] == 1
    assert w["as_of"] == _NOW.isoformat(timespec="seconds")


def test_a_stale_stream_says_so_in_the_report() -> None:
    """A watch that stopped running must be visible IN the readout. Before K3 a stopped
    watch produced no file at all, and an absent file is read by nothing."""
    late = datetime(2026, 9, 20, 12, 0, 0, tzinfo=UTC)
    s = PR.readout(DEC, OUT, REA, since="2026-08-25", now=late)
    assert s["window"]["age_days"] == 25
    assert s["window"]["stale"] is True
    assert "STALE" in PR.render(s)
    fresh = PR.readout(DEC, OUT, REA, since="2026-08-25", now=_NOW)
    assert fresh["window"]["stale"] is False and "STALE" not in PR.render(fresh)


def test_an_empty_stream_is_stale_not_silent() -> None:
    s = PR.readout([], [], [], since="2026-08-25", now=_NOW)
    assert s["window"]["newest"] == "" and s["window"]["age_days"] is None
    assert s["window"]["stale"] is True
    assert "STALE" in PR.render(s)


def test_rows_from_several_kb_roots_are_unioned_and_deduped() -> None:
    """Two roots serving the same owner: distinct rows accumulate, and a row present in
    both (a copied or re-synced stream) counts once."""
    other = [{"tx_time": "2026-08-26T13:00:00+00:00", "question_id": "t" * 16,
              "family": "lookup", "chosen_action": "report", "run_id": "ask-3",
              "predicted_eu": 0.5, "posterior_summary": {"candidates": ["X"],
              "credences": [1.0], "p_none": 0.0, "n_obs": 1, "n_indeterminate": 0,
              "n_competing": 0}}]
    unioned = PR.union(DEC, [*DEC, *other])          # root 2 overlaps root 1 entirely
    assert len(unioned) == len(DEC) + 1
    s = PR.readout(unioned, [], [], since="2026-08-25", now=_NOW)
    assert s["decisions"]["report"] == 2             # not 3: the duplicate counts once


def test_sources_are_index_labelled_never_paths() -> None:
    """A KB root is an owner-specific absolute path and the report may be pasted anywhere
    (the readout's own binding property). Roots are reported by INDEX and row count, so a
    dead root is visible as `0 rows` without naming anybody's filesystem."""
    s = PR.readout(DEC, OUT, REA, since="2026-08-25", now=_NOW,
                   sources=({"rows": 5}, {"rows": 0}))
    text = PR.render(s)
    assert "root 1: 5 rows" in text and "root 2: 0 rows (EMPTY)" in text
    assert "/" not in text.split("## Watch")[0].split("- sources:")[1].split("\n")[0]
