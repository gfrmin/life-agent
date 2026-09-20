"""Unit tests for the fair-fight baseline arm (scripts/fairfight/arm_baseline.py) and
ask.py's EFFORT_LAST counter.

Hermetic: monkeypatches ``ask`` internals (``answer_via_executor``/``_executor_ready``)
rather than driving real retrieval or LLM calls. Fake meter entries are appended directly to
``life_agent.core.llm``'s active meter list (the same chokepoint ``reset_meter``/
``meter_read`` manage) between a real ``reset_meter()``/``meter_read()`` bracket, per the
task brief's "real reset_meter/meter_read with injected LLMResults" guidance.

Run from the repo root:
    uv run --project . python -m pytest ./tests/test_fairfight_arms.py
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import ask
from fairfight import arm_baseline as AB
from fairfight import grading as G

from life_agent.core import executor as EX
from life_agent.core import llm as LLM


def _q(id_: str = "q-001", question: str = "what is my ID?") -> dict:
    return {"id": id_, "question": question}


def _bill(n: int = 1) -> None:
    """Append ``n`` fake LLMResults to the currently-active meter (must run between
    reset_meter()/meter_read(), which the arm functions already bracket their call in)."""
    assert LLM._METER is not None, "meter not active — called outside reset_meter/meter_read"
    for _ in range(n):
        LLM._METER.append(LLM.LLMResult(
            text="x", in_tokens=10, out_tokens=5, seconds=0.01,
            served_model="stub", provider="anthropic"))


def _fake_card(n: int, text: str, origin: str = "/data/a.txt") -> SimpleNamespace:
    """A ``core.sources.SourceCard``-shaped stand-in (task 10: ``RawAnswer.cards``
    capture) — only ``n``/``text``/``origin`` are read by the arm modules."""
    return SimpleNamespace(n=n, text=text, origin=origin)


# --- RawAnswer / _view_declined: the ONE declined convention, tested against grading.py ----


@pytest.mark.parametrize(
    ("asserted", "scoped", "expected"),
    [(True, False, False), (False, True, False), (False, False, True), (True, True, False)],
)
def test_view_declined_matches_grading_convention(
    asserted: bool, scoped: bool, expected: bool,
) -> None:
    assert AB._view_declined({"asserted": asserted, "scoped": scoped}) == expected


def test_view_declined_agrees_with_grade_channels_own_formula(monkeypatch) -> None:
    """The SAME formula, not a re-derivation that could drift: cross-check against
    scripts/fairfight/grading.py's grade_channels (task-8 brief: "do NOT invent a third
    convention")."""
    monkeypatch.setattr(G, "_answer_in_corpus", lambda conn, answer, variants: False)
    q = {"id": "q1", "question": "x?", "answer": "", "answer_variants": [],
         "distractors": [], "subject": "n/a", "answerable": False}
    view = {"asserted": False, "scoped": False, "asserted_values": [], "candidates": []}
    grades = G.grade_channels(q, "some rendered text", [], view, conn=None)
    assert AB._view_declined(view) == grades.declined


# --- baseline (executor) ------------------------------------------------------------------


def _executor_view(**overrides: object) -> dict:
    """A ``core.executor.View``-shaped dict — the typed-lookup branch (``route`` is not
    ``None``). Every fake below sets ``ask.EXECUTOR_VIEW_LAST`` to one of these itself
    (the way the real ``ask.answer_via_executor`` does), never leaning on a leftover
    value from a prior test (the established ``EXECUTOR_LAST`` convention, extended)."""
    base: dict = dict(
        effector="report", asserted=["P123"], candidates=["P123"], credences=[0.9],
        p_none=0.05, eu=0.8, n_obs=1, hits=[], route={"construct": "id"},
    )
    base.update(overrides)
    return base


def test_answer_baseline_executor_happy_path(monkeypatch) -> None:
    monkeypatch.setattr(ask, "_executor_ready", lambda: True)

    def fake_answer_via_executor(question: str, k: int):
        _bill(2)
        ask.EXECUTOR_LAST = "ab-deadbeef"
        ask.EXECUTOR_VIEW_LAST = _executor_view()
        return ("credence 0.900 — P123 [1]", [], {})

    monkeypatch.setattr(ask, "answer_via_executor", fake_answer_via_executor)
    out = AB.answer_baseline(_q(), 8)
    assert out.status == "ok" and out.notes == ""
    assert out.text == "credence 0.900 — P123 [1]"
    # final-review CRITICAL-1: a typed-lookup report now carries a REAL structured view
    # (built from ask.EXECUTOR_VIEW_LAST), not None — grading no longer pattern-matches
    # the rendered text for this case.
    assert out.decision_view == {
        "family": "lookup", "action": "report", "effector": "report",
        "asserted": True, "scoped": False, "asserted_values": ["P123"],
        "candidates": ["P123"], "credences": [0.9], "p_none": 0.05,
    }
    assert out.declined is False
    assert out.lineage_keys == ("ab-deadbeef",)
    assert len(out.llm_calls) == 2
    assert out.effort == {}                      # not reachable from the executor path
    assert out.question_id == "q-001"
    assert out.latency_s >= 0.0


def test_answer_baseline_executor_grammar_rendered_withholding_grades_not_confident_wrong(
    monkeypatch,
) -> None:
    """The CONFIRMED final-review bug (CRITICAL-1): before this fix, the executor arm's
    withholding never carried a structured decision_view, so grading fell back to
    free-text ``detect_decline`` over the RENDERED credence-grammar string — which does
    not recognise ``core.lookup.GRAMMAR``'s own withholding renderings — reading
    declined=False -> asserted=True -> CONFIDENT_WRONG for a decision that never
    asserted anything. This is the harness manufacturing the exact failure the program's
    hard gate forbids. Red without the fix (decision_view stayed None, detect_decline
    over the grammar text failed to match, bucket came out CONFIDENT_WRONG)."""
    monkeypatch.setattr(ask, "_executor_ready", lambda: True)
    ask.EXECUTOR_LAST = None

    def fake_answer_via_executor(question: str, k: int):
        view = _executor_view(effector="abstain", asserted=[], candidates=["999999999"],
                              credences=[0.4], p_none=0.6)
        ask.EXECUTOR_VIEW_LAST = view
        return (EX.render_view(view), [], {})

    monkeypatch.setattr(ask, "answer_via_executor", fake_answer_via_executor)
    out = AB.answer_baseline(_q(question="what is my ID number?"), 8)
    assert out.declined is True
    assert out.decision_view is not None and out.decision_view["asserted"] is False

    monkeypatch.setattr(G, "_answer_in_corpus", lambda conn, answer, variants: False)
    q = {"id": "q-001", "question": "what is my ID number?", "answer": "123456789",
         "answer_variants": [], "distractors": [], "subject": "n/a", "answerable": True}
    grades = G.grade_channels(q, out.text, [], out.decision_view, conn=None)
    assert grades.declined is True
    assert grades.asserted is False
    assert grades.bucket != "CONFIDENT_WRONG"
    assert grades.bucket == "RIGHTLY_WITHHELD"  # gold never reached the corpus in this fixture


def test_answer_baseline_executor_hedge_is_asserting_not_declined(monkeypatch) -> None:
    # mirrors triage_answers._lookup_view's convention exactly: hedge IS an
    # assertion-class act, not a withholding.
    monkeypatch.setattr(ask, "_executor_ready", lambda: True)
    ask.EXECUTOR_LAST = None

    def fake_answer_via_executor(question: str, k: int):
        view = _executor_view(effector="hedge", asserted=[], candidates=["A", "B"],
                              credences=[0.4, 0.3], p_none=0.3)
        ask.EXECUTOR_VIEW_LAST = view
        return (EX.render_view(view), [], {})

    monkeypatch.setattr(ask, "answer_via_executor", fake_answer_via_executor)
    out = AB.answer_baseline(_q(), 8)
    assert out.decision_view["asserted"] is True
    assert out.decision_view["asserted_values"] == ["A", "B"]
    assert out.declined is False


def test_answer_baseline_executor_unrouted_view_falls_back_to_free_text(
    monkeypatch,
) -> None:
    # a view with no route (view["route"] is None) carries no structured candidates, so
    # _executor_decision returns None and grading falls back to detect_decline over the
    # rendered text (never fabricate a candidate list the executor never gave us).
    monkeypatch.setattr(ask, "_executor_ready", lambda: True)
    ask.EXECUTOR_LAST = None

    def fake_answer_via_executor(question: str, k: int):
        ask.EXECUTOR_VIEW_LAST = {
            "effector": "report", "asserted": True, "candidates": [], "credences": [],
            "p_none": None, "eu": None, "n_obs": 0, "hits": [], "route": None,
            "rendered": "you travelled in May [1]\n\nnarrative footer",
        }
        return ("you travelled in May [1]\n\nnarrative footer", [], {})

    monkeypatch.setattr(ask, "answer_via_executor", fake_answer_via_executor)
    out = AB.answer_baseline(_q(), 8)
    assert out.decision_view is None
    assert out.declined is False       # free text, no decline phrase present


def test_answer_baseline_executor_captures_cards(monkeypatch) -> None:
    # task 10: the runner needs the retrieved set for grade_channels/judge sources — the
    # prior task's single return statement discarded it as `_cards`.
    monkeypatch.setattr(ask, "_executor_ready", lambda: True)

    def fake_answer_via_executor(question: str, k: int):
        ask.EXECUTOR_VIEW_LAST = None  # this fake doesn't exercise the decision-view seam
        return ("P123 [1]", [_fake_card(1, "the passport text")], {})

    monkeypatch.setattr(ask, "answer_via_executor", fake_answer_via_executor)
    out = AB.answer_baseline(_q(), 8)
    assert out.cards == ({"n": 1, "text": "the passport text", "origin": "/data/a.txt"},)


def test_answer_baseline_executor_down_never_falls_back_silently(monkeypatch) -> None:
    monkeypatch.setattr(ask, "_executor_ready", lambda: False)

    def must_not_be_called(*a: object, **k: object) -> object:
        raise AssertionError("a down stack must not be driven at all")

    monkeypatch.setattr(ask, "answer_via_executor", must_not_be_called)
    out = AB.answer_baseline(_q(), 8)
    assert out.status == "error"
    assert "executor" in out.notes.lower() and "unreachable" in out.notes.lower()
    assert out.text == ""
    assert out.llm_calls == []                   # nothing billed — the call never ran
    assert out.cards == ()


# --- EFFORT_LAST: no leakage across calls -------------------------------------------------


def test_effort_last_does_not_leak_across_questions(monkeypatch) -> None:
    monkeypatch.setattr(ask, "_executor_ready", lambda: True)

    def fake_answer_with_effort(question, k):
        ask.EXECUTOR_VIEW_LAST = None
        ask.TERM.EFFORT_LAST = {"retrieve_passes": 1}
        return ("text1", [], {})

    monkeypatch.setattr(ask, "answer_via_executor", fake_answer_with_effort)
    out1 = AB.answer_baseline(_q("q-1"), 8)
    assert out1.effort == {"retrieve_passes": 1}

    # q-2 goes down the executor-down branch, which never calls answer_via_executor — without
    # an explicit reset, EFFORT_LAST would still read q-1's counts.
    monkeypatch.setattr(ask, "_executor_ready", lambda: False)
    out2 = AB.answer_baseline(_q("q-2"), 8)
    assert out2.effort == {}


def test_answer_via_executor_itself_resets_effort_last_to_empty(monkeypatch) -> None:
    ask.TERM.EFFORT_LAST = {"retrieve_passes": 3, "gather_tiers": 2}  # stale from a prior call
    monkeypatch.setattr(ask, "_executor_ready", lambda: False)
    ask.answer_via_executor("q", 8)
    assert ask.TERM.EFFORT_LAST == {}


