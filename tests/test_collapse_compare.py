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
