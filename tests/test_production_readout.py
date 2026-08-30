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


# --- r27 C10: a DECLARED root that is absent is a failure, not a quiet zero -------------
# Row 25's staleness signal can see a stale source but not an ABSENT one: `_rows` returns
# [] for a missing file, so a root that was never there is indistinguishable from a root
# with no traffic. Measured on the authoring box: the readout reported "1 KB root, 4660
# rows, newest 1 day ago" over a stream containing no production traffic at all, with no
# staleness flag, because the only deployment that matters was never declared to it.

def test_a_declared_root_that_is_absent_fails_the_run(tmp_path: Path,
                                                      monkeypatch) -> None:
    """r27 C10. MUST FAIL if a declared root can be missing and the run still succeed.
    Killed by restoring the silent `[]` for an absent root."""
    monkeypatch.setattr(PR, "bar_summary", lambda **k: {"error": "stubbed (hermetic)"})
    good = tmp_path / "kb"
    (good / "calibration").mkdir(parents=True)
    rc = PR.main(["--kb", str(good), "--kb", str(tmp_path / "nope"),
                  "--out", str(tmp_path / "r.md")])
    assert rc != 0, "a declared KB root that does not exist did not fail the run"


def test_a_declared_root_that_is_present_but_empty_succeeds(tmp_path: Path,
                                                            monkeypatch) -> None:
    """r27 C10, the discriminating half (row 23): the check must tell an ABSENT root from
    a root with no traffic yet, or it is a gate that rejects everything. A fresh
    deployment has a root and no stream, and that is a legitimate zero.
    Killed by failing on a missing stream file rather than a missing root.
    (bar_summary is stubbed — A6's watch reaches for the live brain, and a hermetic
    test may not; its own guard is pinned separately below.)"""
    monkeypatch.setattr(PR, "bar_summary", lambda **k: {"error": "stubbed (hermetic)"})
    good = tmp_path / "kb"
    (good / "calibration").mkdir(parents=True)
    rc = PR.main(["--kb", str(good), "--out", str(tmp_path / "r.md")])
    assert rc == 0, "a declared root that exists with no stream yet was treated as absent"


# --- r33 A6 (owner-ruled MONITOR ONLY): the p† line — the bar drift, made visible -------

def _summary_with_bar(bar: dict) -> dict:
    s = PR.readout(DEC, [], [], since="2026-08-25",
                   now=datetime(2026, 8, 27, tzinfo=UTC), sources=({"rows": 3},))
    s["bar"] = bar
    return s


def test_render_carries_the_deployed_bar_beside_the_declared_one() -> None:
    out = PR.render(_summary_with_bar(
        {"p_dagger": 0.8369, "declared": 0.9000, "n_events": 55}))
    assert "p† 0.8369" in out                    # the DEPLOYED bar (r32: not 0.90)
    assert "declared prior 0.9000" in out        # ...never quoted alone
    assert "55 folded events" in out
    assert "drift" in out                        # the direction is named, not implied


def test_render_names_an_unavailable_bar_instead_of_failing() -> None:
    # the readout is a WATCH, never a dependency: a dead daemon renders a named
    # unavailability — the rest of the report still lands
    out = PR.render(_summary_with_bar({"error": "brain unreachable"}))
    assert "p† unavailable (brain unreachable)" in out
    assert "decisions by action" in out          # the report itself survived


def test_render_without_a_bar_key_is_unchanged() -> None:
    # back-compat: a summary predating A6 renders exactly as before
    s = PR.readout(DEC, [], [], since="2026-08-25",
                   now=datetime(2026, 8, 27, tzinfo=UTC), sources=({"rows": 3},))
    out = PR.render(s)
    assert "p†" not in out


def test_bar_summary_never_raises(monkeypatch) -> None:
    # the computation itself is guarded: any failure becomes {"error": ...}
    from life_agent.core import lookup as LK

    def _boom() -> None:
        raise RuntimeError("daemon down")

    monkeypatch.setattr(LK, "shared_brain", _boom)
    out = PR.bar_summary()
    assert set(out) == {"error"} and "daemon down" in out["error"]
