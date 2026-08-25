"""The decision-equivalence comparator (module-collapse-design.md §7.2) — the field-class
rule, the float tolerance, and the seeded defects it must kill.

Every value here is SYNTHETIC: the real fixtures carry question text and corpus values and
live out of tree under ``$LIFE_AGENT_KB/eval/collapse-fixtures/`` (CLAUDE.md: the repo is
public and PII-free).

Run: uv run --project . python -m pytest tests/test_collapse_compare.py
"""
from __future__ import annotations

import pytest

from life_agent.collapse import compare as CMP
from life_agent.collapse import fixture as FX


def _body(**over: object) -> dict:
    """A minimal, fully-classified /log_decision body — the shape bridge/_log_decision
    accepts (server.py:776), plus the two fields M0 adds."""
    body = {
        "question": "what is the synthetic serial?",  # PII-OK: synthetic question
        "retrieval_keys": ["k1", "k2"],
        "decision": {
            "effector": "report", "credences": [0.8, 0.2], "candidates": ["A", "B"],
            "p_none": 0.05, "eu": 0.61, "n_obs": 3, "n_indeterminate": 1,
            "n_competing": 0, "instrument": "", "run_id": "collapse-m0",
            "cost_usd": 0.004, "latency_s": 1.25,
            "regime": "full", "policy": "all-to-date",
        },
    }
    for path, value in over.items():
        dotted = path.replace("__", ".")
        head, _, tail = dotted.partition(".")
        if tail:
            body[head][tail] = value  # type: ignore[index]
        else:
            body[head] = value
    return body


def _drop(body: dict, dotted: str) -> dict:
    head, _, tail = dotted.partition(".")
    out = {k: (dict(v) if isinstance(v, dict) else v) for k, v in body.items()}
    if tail:
        out[head].pop(tail, None)
    else:
        out.pop(head, None)
    return out


# --- the field-class rule ---------------------------------------------------------------

def test_identical_bodies_have_no_diffs() -> None:
    assert CMP.compare_body(_body(), _body()) == []


def test_a_changed_value_compared_field_is_killed() -> None:
    diffs = CMP.compare_body(_body(), _body(decision__effector="abstain"))
    assert [d.path for d in diffs] == ["decision.effector"]
    assert diffs[0].reason == "value"


def test_runtime_measured_fields_are_not_compared_by_value() -> None:
    """`latency_s` and warm-hit `cost_usd` are measured, not tabled (§7.2's signed
    field-class list) — a replay that takes longer is not a behaviour change."""
    assert CMP.compare_body(_body(), _body(decision__latency_s=99.0,
                                           decision__cost_usd=0.5)) == []


def test_a_runtime_measured_field_must_still_be_present() -> None:
    diffs = CMP.compare_body(_body(), _drop(_body(), "decision.latency_s"))
    assert [(d.path, d.reason) for d in diffs] == [("decision.latency_s", "absent")]


def test_a_runtime_measured_field_must_keep_its_type() -> None:
    diffs = CMP.compare_body(_body(), _body(decision__latency_s="1.25"))
    assert [(d.path, d.reason) for d in diffs] == [("decision.latency_s", "type")]


def test_a_none_valued_runtime_field_is_a_type_of_its_own_and_matches_none() -> None:
    assert CMP.compare_body(_body(decision__cost_usd=None),
                            _body(decision__cost_usd=None)) == []
    diffs = CMP.compare_body(_body(decision__cost_usd=None), _body(decision__cost_usd=0.1))
    assert [(d.path, d.reason) for d in diffs] == [("decision.cost_usd", "type")]


def test_an_unclassified_field_is_a_mismatch_never_a_silent_pass() -> None:
    """never-silently-weaken: a field the collapse adds must be CLASSIFIED at the
    checkpoint that adds it, not absorbed by a permissive comparator."""
    diffs = CMP.compare_body(_body(), _body(decision__novel_field=1))
    assert [(d.path, d.reason) for d in diffs] == [("decision.novel_field", "unclassified")]


def test_floats_compare_at_1e_9() -> None:
    assert CMP.compare_body(_body(), _body(decision__eu=0.61 + 1e-12)) == []
    assert [d.path for d in CMP.compare_body(_body(), _body(decision__eu=0.61 + 1e-6))] \
        == ["decision.eu"]


def test_every_body_field_is_declared_in_exactly_one_class() -> None:
    """The class list is the contract — a field in both classes, or in neither while the
    recorder emits it, is a design bug, not a runtime surprise."""
    assert not (FX.VALUE_COMPARED & FX.RUNTIME_MEASURED)
    emitted = {"question", "retrieval_keys"} | {
        f"decision.{k}" for k in _body()["decision"]}
    assert emitted <= (FX.VALUE_COMPARED | FX.RUNTIME_MEASURED)


# --- the seeded defects §7.5 names for this instrument ------------------------------------

def test_seeded_defect_swapped_tie_break_is_killed() -> None:
    """M-10: two equal-credence candidates, the leader-first label view flipped
    first-listed ↔ last-listed. Pre-registered kill 1."""
    tie = _body(decision__credences=[0.5, 0.5], decision__candidates=["A", "B"])
    swapped = _body(decision__credences=[0.5, 0.5], decision__candidates=["B", "A"])
    assert [d.path for d in CMP.compare_body(tie, swapped)] == ["decision.candidates"]


def test_seeded_defect_optional_accounting_field_is_killed() -> None:
    """Q-O6 regressed: the poster drops an accounting field instead of recording 0.0/""."""
    diffs = CMP.compare_body(_body(), _drop(_body(), "decision.instrument"))
    assert [(d.path, d.reason) for d in diffs] == [("decision.instrument", "absent")]


def test_seeded_defect_policy_swap_is_killed() -> None:
    """`frozen-elicitations` served to the decider (or `all-to-date` to the gate)."""
    diffs = CMP.compare_body(_body(), _body(decision__policy="frozen-elicitations"))
    assert [(d.path, d.reason) for d in diffs] == [("decision.policy", "value")]


def test_seeded_defect_regime_swap_is_killed() -> None:
    diffs = CMP.compare_body(_body(), _body(decision__regime="terminals-only"))
    assert [(d.path, d.reason) for d in diffs] == [("decision.regime", "value")]


# --- outputs (fixtures whose decision never reaches the poster) ---------------------------

def test_outputs_without_a_body_compare_on_the_chosen_act() -> None:
    """A miss / a down stack posts nothing — the comparator still pins the act (§6.5)."""
    rec = {"effector": "abstain", "asserted": [], "candidates": [], "credences": [],
           "p_none": None, "eu": None, "gate": "executor_down", "log_decision": None}
    assert CMP.compare_outputs(rec, dict(rec)) == []
    diffs = CMP.compare_outputs(rec, {**rec, "gate": None})
    assert [(d.path, d.reason) for d in diffs] == [("gate", "value")]


def test_outputs_audit_fields_are_recorded_not_compared() -> None:
    """The render is a LABEL view (D-4): recorded for audit, never a decision — comparing
    it would make a cosmetic string a behaviour change."""
    rec = {"effector": "report", "asserted": ["A"], "candidates": ["A"],
           "credences": [1.0], "p_none": 0.0, "eu": 0.5, "gate": None,
           "log_decision": None, "audit": {"rendered_sha": "aaa"}}
    assert CMP.compare_outputs(rec, {**rec, "audit": {"rendered_sha": "bbb"}}) == []


def test_a_missing_body_on_one_side_only_is_killed() -> None:
    with_body = {"effector": "report", "asserted": ["A"], "candidates": ["A"],
                 "credences": [1.0], "p_none": 0.0, "eu": 0.5, "gate": None,
                 "log_decision": _body()}
    without = {**with_body, "log_decision": None}
    diffs = CMP.compare_outputs(with_body, without)
    assert [(d.path, d.reason) for d in diffs] == [("log_decision", "absent")]


def test_diffs_render_one_line_per_field() -> None:
    diffs = CMP.compare_body(_body(), _body(decision__effector="abstain"))
    text = CMP.render_diffs("m0-synthetic-1", diffs)
    assert "m0-synthetic-1" in text and "decision.effector" in text
    assert "report" in text and "abstain" in text


@pytest.mark.parametrize("path", sorted(FX.RUNTIME_MEASURED))
def test_every_runtime_measured_field_is_named_in_the_body_shape(path: str) -> None:
    """The measured list may not name a field the poster never emits — a stale entry is a
    silent loosening (it would excuse a field that later appears)."""
    _, _, tail = path.partition(".")
    assert tail and tail in _body()["decision"]


# --- the M2 direction assertions (§7.2's expected-change mechanism, r12 DIR-1/DIR-2) ------
# A fixture whose `expected_change.checkpoint` names M2 is compared under its pre-registered
# direction instead of raw equality — TIGHT: every field the direction does not name stays
# under the standing classes, the named fields must match exactly, and the change must have
# HAPPENED (a fixture replaying unchanged fails the direction: the checkpoint claims a move
# it did not make).

def _poster_outputs(body: dict) -> dict:
    return {"effector": "report", "asserted": ["A"], "candidates": ["A", "B"],
            "credences": [0.8, 0.2], "p_none": 0.05, "eu": 0.61, "gate": None,
            "log_decision": body, "audit": {"poster": "x"}}


def _recorded_poster() -> dict:
    """The m2-base A-poster recorded shape: accounting keys present (the CLI poster posts
    them, cost/latency at null on an unpriced firing), regime/policy ABSENT."""
    body = _body(decision__cost_usd=None, decision__latency_s=None)
    del body["decision"]["regime"], body["decision"]["policy"]
    return _poster_outputs(body)


def _replayed_poster() -> dict:
    """The one poster's body (r12 D2): regime/policy stated, unpriced cost/latency at 0.0."""
    return _poster_outputs(_body(decision__cost_usd=0.0, decision__latency_s=0.0,
                                 decision__run_id="collapse-m0"))


def test_m2_poster_direction_passes_the_registered_delta() -> None:
    assert CMP.compare_directed(_recorded_poster(), _replayed_poster(),
                                checkpoint="M2", question="q") == []


def test_m2_poster_direction_requires_the_change_to_have_happened() -> None:
    """An unchanged replay FAILS the direction — the checkpoint claims a move."""
    diffs = CMP.compare_directed(_recorded_poster(), _recorded_poster(),
                                 checkpoint="M2", question="q")
    assert {d.path for d in diffs} == {"log_decision.decision.regime",
                                       "log_decision.decision.policy"}


def test_m2_poster_direction_kills_a_wrong_regime_value() -> None:
    actual = _replayed_poster()
    actual["log_decision"]["decision"]["regime"] = "terminals-only"
    diffs = CMP.compare_directed(_recorded_poster(), actual, checkpoint="M2", question="q")
    assert [d.path for d in diffs] == ["log_decision.decision.regime"]


def test_m2_poster_direction_kills_any_other_field_change() -> None:
    actual = _replayed_poster()
    actual["log_decision"]["decision"]["credences"] = [0.7, 0.3]
    diffs = CMP.compare_directed(_recorded_poster(), actual, checkpoint="M2", question="q")
    assert [d.path for d in diffs] == ["log_decision.decision.credences"]


def test_m2_poster_direction_kills_an_unnamed_new_field() -> None:
    actual = _replayed_poster()
    actual["log_decision"]["decision"]["defaulted"] = []
    diffs = CMP.compare_directed(_recorded_poster(), actual, checkpoint="M2", question="q")
    assert [(d.path, d.reason) for d in diffs] == [
        ("log_decision.decision.defaulted", "unclassified")]


def test_m2_poster_direction_allows_priced_cost_to_stay_a_number() -> None:
    """A fixture recorded with a realised price keeps kind number → number."""
    rec = _recorded_poster()
    rec["log_decision"]["decision"]["cost_usd"] = 0.004
    act = _replayed_poster()
    act["log_decision"]["decision"]["cost_usd"] = 0.0041  # runtime-measured: value free
    assert CMP.compare_directed(rec, act, checkpoint="M2", question="q") == []


def _recorded_seam() -> dict:
    return {"effector": "abstain", "asserted": [], "candidates": [], "credences": [],
            "p_none": None, "eu": None, "gate": "executor_down", "log_decision": None,
            "audit": {"question_id": "abc"}}


def _replayed_seam(question: str = "the stack is down") -> dict:  # PII-OK: synthetic
    body = {
        "question": question, "retrieval_keys": [],
        "decision": {"effector": "abstain", "credences": [], "candidates": [],
                     "p_none": 0.0, "eu": 0.0, "n_obs": 0, "n_indeterminate": 0,
                     "n_competing": 0, "instrument": "", "run_id": "answer-brain",
                     "cost_usd": 0.0, "latency_s": 0.0,
                     "regime": "unavailable", "policy": "all-to-date"},
    }
    return {"effector": "abstain", "asserted": [], "candidates": [], "credences": [],
            "p_none": None, "eu": None, "gate": "executor_down",
            "regime": "unavailable", "policy": "all-to-date",
            "log_decision": body, "audit": {"defaulted": ["policy"]}}


def test_m2_seam_direction_passes_the_unavailability_record() -> None:
    assert CMP.compare_directed(_recorded_seam(), _replayed_seam(),
                                checkpoint="M2/M5",
                                question="the stack is down") == []  # PII-OK: synthetic


def test_m2_seam_direction_requires_the_record() -> None:
    diffs = CMP.compare_directed(_recorded_seam(), _recorded_seam(),
                                 checkpoint="M2/M5", question="the stack is down")
    assert diffs  # unchanged replay = the record never appeared = FAIL


def test_m2_seam_direction_kills_a_changed_act() -> None:
    actual = _replayed_seam()
    actual["effector"] = "report"
    actual["log_decision"]["decision"]["effector"] = "report"
    diffs = CMP.compare_directed(_recorded_seam(), actual,
                                 checkpoint="M2/M5", question="the stack is down")
    assert "effector" in {d.path for d in diffs}


def test_m2_seam_direction_kills_a_foldable_regime() -> None:
    """The record must say `unavailable` — a `full` abstain would fold as a verdict."""
    actual = _replayed_seam()
    actual["regime"] = "full"
    actual["log_decision"]["decision"]["regime"] = "full"
    diffs = CMP.compare_directed(_recorded_seam(), actual,
                                 checkpoint="M2/M5", question="the stack is down")
    assert {d.path for d in diffs} >= {"regime", "log_decision.decision.regime"}


def test_an_unknown_direction_checkpoint_fails_loud() -> None:
    diffs = CMP.compare_directed(_recorded_seam(), _replayed_seam(),
                                 checkpoint="M9", question="q")
    assert [(d.path, d.reason) for d in diffs] == [
        ("expected_change.checkpoint", "unclassified")]


# --- AMENDMENT 1: DIR-1's true scope — every pre-collapse poster body (A-loop included) ----

def _recorded_aloop() -> dict:
    """The A-loop recorded shape: the reach poster's REDUCED body (no accounting keys at
    all, no regime/policy), with the loop's realised instrument in the recorded audit."""
    body = _body()
    for key in ("instrument", "cost_usd", "latency_s", "run_id", "regime", "policy"):
        del body["decision"][key]
    out = _poster_outputs(body)
    out["audit"] = {"instrument": None, "run_id": "collapse-m0"}
    return out


def _replayed_aloop(instrument: str = "", run_id: str = "answer-brain") -> dict:
    return _poster_outputs(_body(decision__instrument=instrument,
                                 decision__cost_usd=0.0, decision__latency_s=0.0,
                                 decision__run_id=run_id))


def test_m2_poster_direction_accepts_the_aloop_appearances() -> None:
    assert CMP.compare_directed(_recorded_aloop(), _replayed_aloop(),
                                checkpoint="M2", question="q") == []


def test_m2_poster_direction_pins_the_appearing_instrument_to_the_recorded_audit() -> None:
    rec = _recorded_aloop()
    rec["audit"]["instrument"] = "deliberate@synthetic-model"  # PII-OK: synthetic
    ok = _replayed_aloop(instrument="deliberate@synthetic-model")  # PII-OK: synthetic
    assert CMP.compare_directed(rec, ok, checkpoint="M2", question="q") == []
    diffs = CMP.compare_directed(rec, _replayed_aloop(instrument=""),
                                 checkpoint="M2", question="q")
    assert [d.path for d in diffs] == ["log_decision.decision.instrument"]


def test_m2_poster_direction_kills_a_wrong_appearing_run_id() -> None:
    diffs = CMP.compare_directed(_recorded_aloop(), _replayed_aloop(run_id="ask"),
                                 checkpoint="M2", question="q")
    assert [d.path for d in diffs] == ["log_decision.decision.run_id"]


def test_compare_fixture_applies_dir1_to_unannotated_pre_collapse_poster_bodies() -> None:
    """The A-loop fixtures carry no expected_change annotation, but their recorded bodies
    came from the pre-collapse reach poster (signature: no `regime` key) — DIR-1 reaches
    them (amendment 1); a B-trace body (regime present) stays under raw equality."""
    fx = FX.Fixture(fixture_id="f1", checkpoint="m2-base", trace="A-loop",
                    classes=(), question="q", question_id="x" * 16,
                    inputs={}, outputs=_recorded_aloop())
    assert CMP.compare_fixture(fx, _replayed_aloop()) == []
    fx_b = FX.Fixture(fixture_id="f2", checkpoint="m2-base", trace="B-lookup",
                      classes=(), question="q", question_id="x" * 16,
                      inputs={}, outputs=_poster_outputs(_body()))
    changed = _poster_outputs(_body(decision__regime="terminals-only"))
    assert [d.path for d in CMP.compare_fixture(fx_b, changed)] == [
        "log_decision.decision.regime"]


def test_compare_fixture_null_body_stays_null_under_dir1() -> None:
    """A miss / route-null A-poster fixture (body null) must replay null — a poster that
    suddenly posts for a non-decision is a violation, not the M2 direction."""
    fx = FX.Fixture(fixture_id="f3", checkpoint="m2-base", trace="A-poster",
                    classes=(), question="q", question_id="x" * 16, inputs={},
                    outputs={"effector": "miss", "asserted": [], "candidates": [],
                             "credences": [], "p_none": None, "eu": None, "gate": None,
                             "log_decision": None},
                    expected_change={"checkpoint": "M2", "direction": "d"})
    same = {"effector": "miss", "asserted": [], "candidates": [], "credences": [],
            "p_none": None, "eu": None, "gate": None, "log_decision": None}
    assert CMP.compare_fixture(fx, same) == []
    posts_now = dict(same, log_decision=_body())
    assert CMP.compare_fixture(fx, posts_now)  # a new post where none was = FAIL
