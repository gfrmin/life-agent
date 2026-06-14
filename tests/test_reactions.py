"""The reaction log + the verdict→Reaction producer (bayesian-foundations §4.4 loop).

No skin, no DB: the log is a jsonl file, the producer is a pure join over it and the
decision log. These tests pin the schema (closed vocab), the supersession rule (latest
verdict per (decision_id, kind), against double-counting), the decision_id join
(matched / unrouted), and — the load-bearing one — that **only clean abstain rows fold**
into u_wrong, at the credence-implied threshold -p/(1-p). The conditioning-moves-Ū test
lives in tests/test_utility.py (it needs the brain).

Run: uv run --project . python -m pytest tests/test_reactions.py
"""
from __future__ import annotations

from pathlib import Path

import pytest

from life_agent.core import decisions as DEC
from life_agent.core import narrative as N
from life_agent.core import reactions as R
from life_agent.core import utility as UT

# --- the schema (closed vocabulary) -----------------------------------------------------

def test_reaction_event_validates_kind_and_valence() -> None:
    R.ReactionEvent(tx_time="t", question_id="q", decision_id="d",
                    kind="verdict", valence="good")  # ok
    with pytest.raises(ValueError, match="kind"):
        R.ReactionEvent(tx_time="t", question_id="q", decision_id="d",
                        kind="shrug", valence="good")
    with pytest.raises(ValueError, match="valence"):
        R.ReactionEvent(tx_time="t", question_id="q", decision_id="d",
                        kind="verdict", valence="meh")


def test_append_read_roundtrip_and_order(tmp_path: Path) -> None:
    p = tmp_path / "reactions.jsonl"
    assert R.read(p) == []  # missing file = no evidence
    a = R.ReactionEvent(tx_time="1", question_id="q1", decision_id="d1",
                        kind="verdict", valence="good")
    b = R.ReactionEvent(tx_time="2", question_id="q2", decision_id="d2",
                        kind="verdict", valence="bad")
    R.append(p, a)
    R.append(p, b)
    back = R.read(p)
    assert back == [a, b]  # file order is replay order


def test_read_tolerates_retired_reason_field(tmp_path: Path) -> None:
    # the log is append-only and predates the retirement of the free-text ``reason``; a legacy
    # row carrying it still reads (the unknown key is dropped), never crashes the replay.
    p = tmp_path / "reactions.jsonl"
    p.write_text('{"tx_time":"1","question_id":"q","decision_id":"d","kind":"verdict",'
                 '"valence":"bad","reason":null,"format_version":1}\n', encoding="utf-8")
    back = R.read(p)
    assert len(back) == 1 and back[0].valence == "bad" and not hasattr(back[0], "reason")


# --- the producer: a clean abstain verdict → one u_wrong threshold observation ----------

def _abstain_decision(decision_id: str, p: float, *, family: str = "lookup") -> DEC.DecisionEvent:
    summary = ({"credences": [p, 1 - p]} if family == "lookup"
               else {"n_proposed": 2, "n_included": 0})
    return DEC.DecisionEvent(
        tx_time="t", run_id="ask", question_id="q", family=family,
        action_set=("report", "hedge", "ask_clarify", "abstain"),
        posterior_summary=summary, utility_fold_version="fv",
        chosen_action="abstain", predicted_eu=0.0, decision_id=decision_id)


def _report_decision(decision_id: str, p: float) -> DEC.DecisionEvent:
    return DEC.DecisionEvent(
        tx_time="t", run_id="ask", question_id="q", family="lookup",
        action_set=("report", "hedge", "ask_clarify", "abstain"),
        posterior_summary={"credences": [p, 1 - p]}, utility_fold_version="fv",
        chosen_action="report", predicted_eu=0.5, decision_id=decision_id)


def _write(tmp: Path, decisions: list, reactions: list) -> tuple[Path, Path]:
    dpath, rpath = tmp / "decisions.jsonl", tmp / "reactions.jsonl"
    for d in decisions:
        DEC.append(dpath, d)
    for r in reactions:
        R.append(rpath, r)
    return rpath, dpath


def test_good_on_abstain_folds_to_a_threshold_below_minus_p(tmp_path: Path) -> None:
    # good on an abstention at p=0.4 ⇒ "glad you didn't guess" ⇒ u_wrong < -p/(1-p)
    rpath, dpath = _write(
        tmp_path, [_abstain_decision("d1", 0.4)],
        [R.ReactionEvent(tx_time="t", question_id="q", decision_id="d1",
                         kind="verdict", valence="good")])
    out = R.load_reactions(rpath, dpath)
    assert len(out) == 1
    rx = out[0]
    assert rx.latent == "u_wrong" and rx.reacted is True and rx.sign == -1.0
    assert rx.threshold == pytest.approx(0.4 / 0.6)  # p/(1-p)


def test_bad_on_abstain_folds_with_reacted_false(tmp_path: Path) -> None:
    rpath, dpath = _write(
        tmp_path, [_abstain_decision("d1", 0.4)],
        [R.ReactionEvent(tx_time="t", question_id="q", decision_id="d1",
                         kind="verdict", valence="bad")])
    out = R.load_reactions(rpath, dpath)
    assert len(out) == 1 and out[0].reacted is False and out[0].sign == -1.0
    assert out[0].threshold == pytest.approx(0.4 / 0.6)


# --- the contamination guard: report verdicts NEVER fold into u_wrong -------------------

def test_report_verdict_is_recorded_but_not_folded(tmp_path: Path) -> None:
    rpath, dpath = _write(
        tmp_path, [_report_decision("d1", 0.9)],
        [R.ReactionEvent(tx_time="t", question_id="q", decision_id="d1",
                         kind="verdict", valence="bad")])
    assert R.load_reactions(rpath, dpath) == []  # cross-latent contamination — deferred


def test_note_valence_is_rejected(tmp_path: Path) -> None:
    # the verdict is one bit — good/bad. The retired ``note`` valence (a no-op the fold never
    # read) is no longer in the vocabulary: constructing it is a loud error, not a silent skip.
    with pytest.raises(ValueError, match="valence"):
        R.ReactionEvent(tx_time="t", question_id="q", decision_id="d1",
                        kind="verdict", valence="note")


def test_narrative_summary_without_schema_fields_is_held_not_folded(tmp_path: Path) -> None:
    # a narrative decision logged before the §7.1 schema (no abstain_reason / marginal_credence)
    # carries no invertible margin — held, never folded or crashed (pre-schema degradation).
    # The meaningful in-schema non-fold (NO_CLAIMS) is covered separately, below.
    rpath, dpath = _write(
        tmp_path, [_abstain_decision("d1", 0.0, family="narrative")],
        [R.ReactionEvent(tx_time="t", question_id="q", decision_id="d1",
                         kind="verdict", valence="good")])
    assert R.load_reactions(rpath, dpath) == []


# --- the join: unrouted, and supersession -----------------------------------------------

def test_verdict_with_no_matching_decision_is_unrouted(tmp_path: Path) -> None:
    rpath, dpath = _write(
        tmp_path, [_abstain_decision("d1", 0.4)],
        [R.ReactionEvent(tx_time="t", question_id="q", decision_id="OTHER",
                         kind="verdict", valence="good")])
    assert R.load_reactions(rpath, dpath) == []  # never mis-assigned


def test_supersession_latest_verdict_per_decision_wins(tmp_path: Path) -> None:
    # the owner revises good → bad on the same decision: folds ONCE, as bad
    rpath, dpath = _write(
        tmp_path, [_abstain_decision("d1", 0.4)],
        [R.ReactionEvent(tx_time="1", question_id="q", decision_id="d1",
                         kind="verdict", valence="good"),
         R.ReactionEvent(tx_time="2", question_id="q", decision_id="d1",
                         kind="verdict", valence="bad")])
    out = R.load_reactions(rpath, dpath)
    assert len(out) == 1 and out[0].reacted is False  # last write (bad) wins, once


# --- the narrative family: the joint (u_wrong, κ_att) margin fold (§7.1) -----------------

def _narrative_abstain(decision_id: str, p_max: float | None, *, reason: str,
                       coverage: tuple[float, float] = (3.0, 1.0)) -> DEC.DecisionEvent:
    return DEC.DecisionEvent(
        tx_time="t", run_id="ask", question_id="q", family="narrative",
        action_set=("report", "abstain"),
        posterior_summary={"n_proposed": 2, "n_included": 0,
                           "marginal_credence": p_max, "abstain_reason": reason,
                           "coverage": list(coverage), "coverage_n": 5},
        utility_fold_version="fv", chosen_action="abstain", predicted_eu=0.0,
        decision_id=decision_id)


def test_narrative_all_withheld_good_folds_to_a_joint_margin(tmp_path: Path) -> None:
    # good on ALL_WITHHELD at p_max ⇒ a MarginReaction coupling u_wrong and κ_att (§7.1)
    p = 0.6
    rpath, dpath = _write(
        tmp_path, [_narrative_abstain("d1", p, reason=N.REASON_ALL_WITHHELD)],
        [R.ReactionEvent(tx_time="t", question_id="q", decision_id="d1",
                         kind="verdict", valence="good")])
    out = R.load_reactions(rpath, dpath)
    assert len(out) == 1
    mr = out[0]
    assert isinstance(mr, UT.MarginReaction)
    assert mr.reacted is True and mr.sign == -1.0 and mr.tau_group == "narrative"
    assert dict(mr.coeffs) == pytest.approx({"kappa_att": -1.0, "u_wrong": p * (1 - p)})
    assert mr.offset == pytest.approx(-(p ** 2))  # margin g = p(1-p)u_wrong - κ + p²


def test_narrative_bad_folds_as_counterpressure_when_coverage_clears_bar(
        tmp_path: Path) -> None:
    # coverage mean 3/4 = 0.75 ≥ 0.5 ⇒ the bad row is genuine counter-pressure (reacted False)
    rpath, dpath = _write(
        tmp_path, [_narrative_abstain("d1", 0.6, reason=N.REASON_ALL_WITHHELD,
                                      coverage=(3.0, 1.0))],
        [R.ReactionEvent(tx_time="t", question_id="q", decision_id="d1",
                         kind="verdict", valence="bad")])
    out = R.load_reactions(rpath, dpath)
    assert len(out) == 1 and isinstance(out[0], UT.MarginReaction) and out[0].reacted is False


def test_narrative_bad_is_quarantined_below_the_coverage_bar(tmp_path: Path) -> None:
    # coverage mean 1/5 = 0.2 < 0.5 ⇒ likely a recall failure, recorded-not-folded
    rpath, dpath = _write(
        tmp_path, [_narrative_abstain("d1", 0.6, reason=N.REASON_ALL_WITHHELD,
                                      coverage=(1.0, 4.0))],
        [R.ReactionEvent(tx_time="t", question_id="q", decision_id="d1",
                         kind="verdict", valence="bad")])
    assert R.load_reactions(rpath, dpath) == []


def test_narrative_good_is_coverage_ungated(tmp_path: Path) -> None:
    # even at low coverage, a good (endorsing the *shown* withheld set) folds — §7.1
    rpath, dpath = _write(
        tmp_path, [_narrative_abstain("d1", 0.6, reason=N.REASON_ALL_WITHHELD,
                                      coverage=(1.0, 4.0))],
        [R.ReactionEvent(tx_time="t", question_id="q", decision_id="d1",
                         kind="verdict", valence="good")])
    out = R.load_reactions(rpath, dpath)
    assert len(out) == 1 and out[0].reacted is True


def test_narrative_no_claims_does_not_fold(tmp_path: Path) -> None:
    # NO_CLAIMS (no p_max) is a proposal/coverage failure, not a foldable utility call
    rpath, dpath = _write(
        tmp_path, [_narrative_abstain("d1", None, reason=N.REASON_NO_CLAIMS)],
        [R.ReactionEvent(tx_time="t", question_id="q", decision_id="d1",
                         kind="verdict", valence="good")])
    assert R.load_reactions(rpath, dpath) == []
