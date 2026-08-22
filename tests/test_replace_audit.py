"""Replace-branch audit (scripts/replace_audit.py) — hermetic.

The instrument answers one question: at the five sites where a probe's reply REPLACES the
grounded channel instead of joining it (design §6.12), does the discard reach the answer?
Its criteria are frozen in the module docstring; what these tests pin is that the instrument
measures what those criteria say — and, after r05 shipped three defects in its own measures,
that every mirror of the decision path is READ FROM the decision path rather than hand-copied.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import replace_audit as RA

import life_agent.core.deliberate as DL
import life_agent.core.executor as EX

_RUN = "gate-20260821T094545"
_OTHER = "gate-20260821T194120"


def _arm(action="report", leader="v", n_obs=1, p_none=0.1, eu=0.5, credences=None):
    return RA.Arm(action=action, leader=leader, n_obs=n_obs, n_docs=1,
                  p_none=p_none, eu=eu, credences=credences or [0.9])


# --- criterion 1: the sites, mirrored from the executor and never hand-copied ---------

def test_the_site_table_is_derived_from_the_executor_module():
    """A hand-copied tier list rots the moment a tier is added. Every model spelling the
    audit maps must come from `core.executor`'s own constants."""
    for probe, model in EX._TIER_MODEL.items():
        assert EX.extract_edge(model) in RA.EDGE_SITES, probe
    assert EX.extract_edge(EX._RE_EXTRACT_MODEL) in RA.EDGE_SITES
    assert DL.instrument(EX._DELIBERATE_MODEL) in RA.EDGE_SITES
    # every registered site id is one of the five §6.12 enumerates
    assert set(RA.SITES) == {"S1", "S2", "S3", "S4", "S5"}


def test_the_deliberate_edge_maps_to_s3_alone():
    assert RA.site_of_edge(DL.instrument(EX._DELIBERATE_MODEL)) == ("S3",)


def test_an_opus_extract_edge_is_an_ambiguity_class_not_a_guess():
    """`corroborate_opus`, in-loop `re_extract_strong` and the k=0 rescue walk all spell
    themselves `extract@<opus>`; the records cannot separate them, so the audit returns all
    three rather than picking one."""
    sites = RA.site_of_edge(EX.extract_edge(EX._RE_EXTRACT_MODEL))
    assert set(sites) == {"S1", "S4", "S5"}


def test_the_cheaper_tiers_are_unambiguous():
    assert RA.site_of_edge(EX.extract_edge(EX._TIER_MODEL["corroborate_haiku"])) == ("S1",)
    assert RA.site_of_edge(EX.extract_edge(EX._TIER_MODEL["corroborate_sonnet"])) == ("S1",)


def test_an_unknown_edge_is_named_never_silently_dropped():
    assert RA.site_of_edge("extract@some-future-model") == ("?",)


# --- criterion 8(a): the deployed arm is READ, never re-derived -----------------------

def test_the_deployed_arm_is_read_off_the_recorded_decision_row():
    row = {"chosen_action": "report", "predicted_eu": 0.44,
           "posterior_summary": {"candidates": ["a", "b"], "credences": [0.03, 0.90],
                                 "p_none": 0.07, "n_obs": 1}}
    arm = RA.deployed_arm(row)
    assert arm.action == "report"
    assert arm.leader == "b"          # argmax over the RECORDED credences
    assert arm.n_obs == 1
    assert arm.p_none == 0.07
    assert arm.eu == 0.44


def test_a_decision_row_with_no_candidates_has_no_leader():
    row = {"chosen_action": "abstain", "predicted_eu": 0.0,
           "posterior_summary": {"candidates": [], "credences": [], "p_none": 1.0,
                                 "n_obs": 0}}
    assert RA.deployed_arm(row).leader == ""


# --- criterion 2: channel loss ---------------------------------------------------------

def test_channel_loss_counts_only_a_positive_discard():
    assert RA.channel_loss(_arm(n_obs=5), _arm(n_obs=1)) == 4
    assert RA.channel_loss(_arm(n_obs=1), _arm(n_obs=5)) == 0
    assert RA.channel_loss(None, _arm(n_obs=1)) == 0


# --- criterion 4: the split ------------------------------------------------------------

_G, _V = "gold", []


def test_a_wrong_commit_becoming_right_is_a_repair():
    assert RA.classify(_arm(leader="wrong"), _arm(leader=_G), _G, _V) == "repair"


def test_a_wrong_commit_becoming_a_withholding_is_a_repair():
    assert RA.classify(_arm(leader="wrong"), _arm(action="abstain"), _G, _V) == "repair"


def test_a_right_commit_becoming_wrong_is_a_regression():
    assert RA.classify(_arm(leader=_G), _arm(leader="wrong"), _G, _V) == "regression"


def test_a_right_commit_becoming_a_withholding_is_a_regression():
    assert RA.classify(_arm(leader=_G), _arm(action="abstain"), _G, _V) == "regression"


def test_a_withholding_that_becomes_a_correct_commit_is_a_repair():
    """The frozen C4 text left this direction unnamed; the docstring fixes it BEFORE the
    read, and the fix has to be the one the docstring states."""
    assert RA.classify(_arm(action="abstain"), _arm(leader=_G), _G, _V) == "repair"


def test_a_withholding_that_becomes_a_wrong_commit_is_a_regression():
    assert RA.classify(_arm(action="abstain"), _arm(leader="wrong"), _G, _V) == "regression"


def test_two_withholdings_are_unchanged():
    assert RA.classify(_arm(action="abstain"), _arm(action="miss"), _G, _V) == "unchanged"


def test_an_ungradeable_row_is_named_not_bucketed():
    assert RA.classify(_arm(leader=_G), None, _G, _V) == "ungradeable"


# --- criterion 5: conservatism, both directions ----------------------------------------

def test_conservatism_is_named_in_both_directions():
    assert RA.conservative_side(_arm(action="abstain"), _arm()) == "conservative"
    assert RA.conservative_side(_arm(), _arm(action="abstain")) == "aggressive"
    assert RA.conservative_side(_arm(), _arm()) == "none"


# --- criterion 6: the S3 collapse signature is a CONJUNCTION ---------------------------

def test_the_s3_collapse_signature_needs_every_conjunct():
    ok = dict(instrument=DL.instrument(EX._DELIBERATE_MODEL), graded_edge=False,
              dep_n_obs=0, base_n_obs=5)
    assert RA.s3_collapse(**ok)
    assert not RA.s3_collapse(**{**ok, "instrument": ""})          # deliberate never fired
    assert not RA.s3_collapse(**{**ok, "graded_edge": True})       # it named a value
    assert not RA.s3_collapse(**{**ok, "dep_n_obs": 3})            # channel survived
    assert not RA.s3_collapse(**{**ok, "base_n_obs": 0})           # nothing to collapse


def test_an_extract_edge_never_reads_as_an_s3_collapse():
    assert not RA.s3_collapse(instrument=EX.extract_edge(EX._RE_EXTRACT_MODEL),
                              graded_edge=False, dep_n_obs=0, base_n_obs=5)


# --- criterion 7: the verdict, applied mechanically ------------------------------------

def test_verdict_buys_a_run_only_when_repairs_exceed_regressions():
    v, _ = RA.verdict(exposure=9, reach=3, repairs=3, regressions=0)
    assert v == "BUILD+PRICE"


def test_verdict_refuses_when_regressions_do_not_lose():
    v, _ = RA.verdict(exposure=9, reach=3, repairs=1, regressions=2)
    assert v == "REFUSE"
    v, _ = RA.verdict(exposure=9, reach=2, repairs=1, regressions=1)
    assert v == "REFUSE"


def test_verdict_at_reach_zero_with_exposure_is_known_and_uncovered():
    v, _ = RA.verdict(exposure=9, reach=0, repairs=0, regressions=0)
    assert v == "KNOWN-UNCOVERED"


def test_verdict_below_the_inherited_bar_of_five_is_no_go():
    v, _ = RA.verdict(exposure=4, reach=0, repairs=0, regressions=0)
    assert v == "NO-GO"


def test_exposure_zero_reads_as_untaken_not_as_clean():
    v, why = RA.verdict(exposure=0, reach=0, repairs=0, regressions=0)
    assert v == "NO-GO"
    assert "untaken" in why


# --- the record loaders ----------------------------------------------------------------

def _write(tmp_path: Path, name: str, rows: list[dict]) -> Path:
    p = tmp_path / name
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return p


def test_decisions_are_filtered_to_the_run_and_the_last_row_per_question_wins(tmp_path):
    p = _write(tmp_path, "decisions.jsonl", [
        {"run_id": _OTHER, "question_id": "q1", "chosen_action": "abstain"},
        {"run_id": _RUN, "question_id": "q1", "chosen_action": "abstain"},
        {"run_id": _RUN, "question_id": "q1", "chosen_action": "report"},
        {"run_id": _RUN, "question_id": "q2", "chosen_action": "hedge"},
    ])
    got = RA.load_decisions(p, _RUN)
    assert set(got) == {"q1", "q2"}
    assert got["q1"]["chosen_action"] == "report"   # the terminal row, not the first


def test_edge_rows_group_by_eval_id_and_keep_firing_order(tmp_path):
    p = _write(tmp_path, "outcomes.jsonl", [
        {"run_id": _RUN, "question_id": "q2-011", "grader": "eval_edge",
         "instrument_identity": {"edge": "extract@claude-haiku-4-5"}, "grade": "INCORRECT"},
        {"run_id": _RUN, "question_id": "q2-011", "grader": "eval_edge",
         "instrument_identity": {"edge": "deliberate@claude-opus-4-8"}, "grade": "INCORRECT"},
        {"run_id": _OTHER, "question_id": "q2-011", "grader": "eval_edge",
         "instrument_identity": {"edge": "deliberate@claude-opus-4-8"}, "grade": "CORRECT"},
        {"run_id": _RUN, "question_id": "q2-011", "grader": "judge",
         "instrument_identity": {"edge": "extract@claude-opus-4-8"}, "grade": "CORRECT"},
    ])
    got = RA.load_edges(p, _RUN)
    assert [e["edge"] for e in got["q2-011"]] == ["extract@claude-haiku-4-5",
                                                  "deliberate@claude-opus-4-8"]
    assert got["q2-011"][0]["grade"] == "INCORRECT"


def test_a_row_without_an_edge_identity_is_ignored(tmp_path):
    p = _write(tmp_path, "outcomes.jsonl", [
        {"run_id": _RUN, "question_id": "q2-011", "grader": "eval_edge",
         "instrument_identity": {"producer_name": "pandoc"}, "grade": "CORRECT"},
    ])
    assert RA.load_edges(p, _RUN) == {}
