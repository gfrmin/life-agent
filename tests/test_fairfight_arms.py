"""Unit tests for the fair-fight in-process arms (scripts/fairfight/arm_baseline.py,
scripts/fairfight/arm_synthesis.py) and ask.py's EFFORT_LAST counter.

Hermetic: monkeypatches ``ask`` internals (``answer``/``answer_via_executor``/``connect``/
``_executor_ready``/``GA.gather_answer``/``SYN.synthesize``) rather than driving real
retrieval or LLM calls. Fake meter entries are appended directly to
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
from fairfight import arm_synthesis as AS
from fairfight import grading as G

from life_agent.core import llm as LLM


def _q(id_: str = "q-001", question: str = "what is my ID?") -> dict:
    return {"id": id_, "question": question}


class _FakeConn:
    """A conn sentinel that records whether the arm closed it (open/close hygiene)."""

    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def _bill(n: int = 1) -> None:
    """Append ``n`` fake LLMResults to the currently-active meter (must run between
    reset_meter()/meter_read(), which the arm functions already bracket their call in)."""
    assert LLM._METER is not None, "meter not active — called outside reset_meter/meter_read"
    for _ in range(n):
        LLM._METER.append(LLM.LLMResult(
            text="x", in_tokens=10, out_tokens=5, seconds=0.01,
            served_model="stub", provider="anthropic"))


def _fake_lookup(**overrides: object) -> SimpleNamespace:
    base = dict(
        action="report", construct="passport number", candidates=["P123"],
        credences=[0.9], p_none=0.05, n_hits=3, n_indeterminate=0, observations=[],
        scoped_value=None, as_of=None, answer_cache_key="lk-1",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _fake_narrative(**overrides: object) -> SimpleNamespace:
    claim = SimpleNamespace(text="the claim", included=True, credence=0.9)
    base = dict(action="report", claims=[claim], answer_cache_key="nv-1")
    base.update(overrides)
    return SimpleNamespace(**base)


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


def test_answer_baseline_executor_happy_path(monkeypatch) -> None:
    monkeypatch.setattr(ask, "_executor_ready", lambda: True)

    def fake_answer_via_executor(question: str, k: int):
        _bill(2)
        ask.EXECUTOR_LAST = "ab-deadbeef"
        return ("credence 0.900 — P123 [1]", [], {})

    monkeypatch.setattr(ask, "answer_via_executor", fake_answer_via_executor)
    out = AB.answer_baseline(_q(), 8, path="executor")
    assert out.status == "ok" and out.notes == ""
    assert out.text == "credence 0.900 — P123 [1]"
    assert out.decision_view is None            # free text: no structured view from here
    assert out.declined is False
    assert out.lineage_keys == ("ab-deadbeef",)
    assert len(out.llm_calls) == 2
    assert out.effort == {}                      # not reachable from the executor path
    assert out.question_id == "q-001"
    assert out.latency_s >= 0.0


def test_answer_baseline_executor_declined_is_free_text_detected(monkeypatch) -> None:
    monkeypatch.setattr(ask, "_executor_ready", lambda: True)
    ask.EXECUTOR_LAST = None  # the real answer_via_executor resets this; our fake stands in

    def fake_answer_via_executor(question: str, k: int):
        return (ask.ABSTENTION, [], {})

    monkeypatch.setattr(ask, "answer_via_executor", fake_answer_via_executor)
    out = AB.answer_baseline(_q(), 8, path="executor")
    assert out.declined is True
    assert out.decision_view is None
    assert out.lineage_keys == ()                # EXECUTOR_LAST never set on this branch


def test_answer_baseline_executor_down_never_falls_back_silently(monkeypatch) -> None:
    monkeypatch.setattr(ask, "_executor_ready", lambda: False)

    def must_not_be_called(*a: object, **k: object) -> object:
        raise AssertionError("must not silently fall back to the in-process path")

    monkeypatch.setattr(ask, "answer", must_not_be_called)
    monkeypatch.setattr(ask, "answer_via_executor", must_not_be_called)
    out = AB.answer_baseline(_q(), 8, path="executor")
    assert out.status == "error"
    assert "executor" in out.notes.lower() and "unreachable" in out.notes.lower()
    assert out.text == ""
    assert out.llm_calls == []                   # nothing billed — the call never ran


# --- baseline (inprocess) ------------------------------------------------------------------


def test_answer_baseline_inprocess_happy_path_turns_gather_on(monkeypatch) -> None:
    conn = _FakeConn()
    captured: dict = {}
    monkeypatch.setattr(ask, "connect", lambda: conn)

    def fake_answer(c, question: str, k: int, **kwargs: object):
        captured["conn"] = c
        captured["kwargs"] = kwargs
        _bill(1)
        ask.LOOKUP_LAST = _fake_lookup()
        ask.NARRATIVE_LAST = None
        ask.STAGES_LAST = {"retrieve": "rk1", "lookup_answer": "lk1"}
        ask.EFFORT_LAST = {"retrieve_passes": 1, "gather_tiers": 1}
        return ("P123 [1]", [], {})

    monkeypatch.setattr(ask, "answer", fake_answer)
    out = AB.answer_baseline(_q(), 8, path="inprocess")
    assert captured["conn"] is conn
    assert captured["kwargs"].get("gather") is True   # the one flag this arm turns on
    assert out.status == "ok"
    assert out.decision_view is not None and out.decision_view["family"] == "lookup"
    assert out.decision_view["asserted"] is True
    assert out.declined is False
    assert out.lineage_keys == ("rk1", "lk1")
    assert out.effort == {"retrieve_passes": 1, "gather_tiers": 1}
    assert len(out.llm_calls) == 1
    assert conn.closed is True                        # the arm closes its own connection


def test_answer_baseline_inprocess_withheld_view_when_no_family_answered(monkeypatch) -> None:
    monkeypatch.setattr(ask, "connect", lambda: _FakeConn())

    def fake_answer(c, question, k, **kwargs):
        ask.LOOKUP_LAST = None
        ask.NARRATIVE_LAST = None
        ask.STAGES_LAST = {}
        ask.EFFORT_LAST = {"retrieve_passes": 1, "gather_tiers": 1}
        return (ask.ABSTENTION, [], {})

    monkeypatch.setattr(ask, "answer", fake_answer)
    out = AB.answer_baseline(_q(), 8, path="inprocess")
    assert out.decision_view == {
        "family": None, "construct": None, "action": "abstain", "asserted": False,
        "asserted_values": [], "candidates": [], "credences": [],
        "p_none": None, "n_hits": None, "n_indeterminate": None, "observations": [],
    }
    assert out.declined is True


def test_answer_baseline_inprocess_error_path_meters_and_closes_conn(monkeypatch) -> None:
    conn = _FakeConn()
    monkeypatch.setattr(ask, "connect", lambda: conn)

    def fake_answer(c, question, k, **kwargs):
        _bill(1)
        raise RuntimeError("boom")

    monkeypatch.setattr(ask, "answer", fake_answer)
    out = AB.answer_baseline(_q(), 8, path="inprocess")
    assert out.status == "error"
    assert "boom" in out.notes
    assert out.text == "" and out.decision_view is None and out.lineage_keys == ()
    assert len(out.llm_calls) == 1                    # the meter is still read on failure
    assert conn.closed is True                         # the connection is still closed


def test_answer_baseline_inprocess_systemexit_is_caught_not_propagated(monkeypatch) -> None:
    # core/llm.py's anthropic_complete/openai_complete/secret raise SystemExit on API/secret
    # failure (core/expansion.py + core/rerank.py already catch it explicitly for the same
    # reason) — a bare `except Exception` would let this kill the whole fair-fight run.
    monkeypatch.setattr(ask, "connect", lambda: _FakeConn())
    monkeypatch.setattr(ask, "answer",
                         lambda c, q, k, **kw: (_ for _ in ()).throw(
                             SystemExit("Anthropic API 529: overloaded")))
    out = AB.answer_baseline(_q(), 8, path="inprocess")
    assert out.status == "error"
    assert "SystemExit" in out.notes
    assert "Anthropic API 529" in out.notes


def test_answer_baseline_inprocess_omits_effort_key_families_leave_absent(monkeypatch) -> None:
    # Faithful, not guessed: when the fake answer() never touches EFFORT_LAST at all (as if
    # this call never reached the retrieve seam), the arm reports exactly what ask.py leaves
    # behind, not an invented default.
    monkeypatch.setattr(ask, "connect", lambda: _FakeConn())
    ask.EFFORT_LAST = {}

    def fake_answer(c, question, k, **kwargs):
        ask.LOOKUP_LAST = None
        ask.NARRATIVE_LAST = None
        ask.STAGES_LAST = {}
        return ("x", [], {})

    monkeypatch.setattr(ask, "answer", fake_answer)
    out = AB.answer_baseline(_q(), 8, path="inprocess")
    assert out.effort == {}


# --- EFFORT_LAST: no leakage across calls -------------------------------------------------


def test_effort_last_does_not_leak_across_questions(monkeypatch) -> None:
    monkeypatch.setattr(ask, "connect", lambda: _FakeConn())

    def fake_answer_with_effort(c, question, k, **kwargs):
        ask.LOOKUP_LAST = None
        ask.NARRATIVE_LAST = None
        ask.STAGES_LAST = {}
        ask.EFFORT_LAST = {"retrieve_passes": 1, "gather_tiers": 1}
        return ("text1", [], {})

    monkeypatch.setattr(ask, "answer", fake_answer_with_effort)
    out1 = AB.answer_baseline(_q("q-1"), 8, path="inprocess")
    assert out1.effort == {"retrieve_passes": 1, "gather_tiers": 1}

    # q-2 goes down the executor-down branch, which never calls ask.answer at all — without
    # an explicit reset, EFFORT_LAST would still read q-1's counts.
    monkeypatch.setattr(ask, "_executor_ready", lambda: False)
    out2 = AB.answer_baseline(_q("q-2"), 8, path="executor")
    assert out2.effort == {}


def test_answer_via_executor_itself_resets_effort_last_to_empty(monkeypatch) -> None:
    ask.EFFORT_LAST = {"retrieve_passes": 3, "gather_tiers": 2}  # stale from a prior call
    monkeypatch.setattr(ask, "_executor_ready", lambda: False)
    ask.answer_via_executor("q", 8)
    assert ask.EFFORT_LAST == {}


# --- ask.answer(): the EFFORT_LAST counting seams themselves -----------------------------


def _weak_floor_hit(score: float = 9.0) -> dict:
    return {"artifact_cache_key": "a" * 64, "chunk_text": "ID is P123", "score": score,
            "origin": "/data/id.pdf"}


def test_ask_answer_counts_one_retrieve_pass_and_zero_gather_tiers_by_default(
    monkeypatch,
) -> None:
    # _hermetic_lookup (conftest autouse) stubs LK.lookup_answer -> None; _hermetic_narrative
    # stubs N.narrative_answer -> None, so the raw synthesize prose (mocked below) returns
    # unscored — no live LLM/DuckDB touched.
    monkeypatch.setattr(ask, "_pkm_root", lambda: Path("/fake/root"))
    monkeypatch.setattr(ask, "_retrieve_set", lambda conn, q, k: [_weak_floor_hit()])
    monkeypatch.setattr(ask.SYN, "synthesize",
                        lambda *a, **k: ("raw prose [1]", "sk", False))
    text, _cards, _scores = ask.answer(conn=None, question="what is the ID?", k=8,
                                       expand=False)
    assert text == "raw prose [1]"
    assert ask.EFFORT_LAST == {"retrieve_passes": 1, "gather_tiers": 0}


def test_ask_answer_counts_gather_tier_fired_when_gather_true(monkeypatch) -> None:
    monkeypatch.setattr(ask, "_pkm_root", lambda: Path("/fake/root"))
    monkeypatch.setattr(ask, "_retrieve_set", lambda conn, q, k: [_weak_floor_hit()])
    monkeypatch.setattr(ask.GA, "gather_answer", lambda *a, **k: None)
    monkeypatch.setattr(ask.SYN, "synthesize",
                        lambda *a, **k: ("raw prose [1]", "sk", False))
    ask.answer(conn=None, question="what is the ID?", k=8, expand=False, gather=True)
    assert ask.EFFORT_LAST == {"retrieve_passes": 1, "gather_tiers": 1}


def test_ask_answer_gather_tier_stays_zero_when_families_off(monkeypatch) -> None:
    # families=False (the monolithic instrument) never reaches the `if gather:` line at
    # all, even when gather=True is passed — 0 is a true fact here, not a placeholder.
    monkeypatch.setattr(ask, "_pkm_root", lambda: Path("/fake/root"))
    monkeypatch.setattr(ask, "_retrieve_set", lambda conn, q, k: [_weak_floor_hit()])
    monkeypatch.setattr(ask.GA, "gather_answer",
                        lambda *a, **k: (_ for _ in ()).throw(
                            AssertionError("gather must not run when families=False")))
    monkeypatch.setattr(ask.SYN, "synthesize",
                        lambda *a, **k: ("raw prose [1]", "sk", False))
    ask.answer(conn=None, question="what is the ID?", k=8, expand=False,
              gather=True, families=False)
    assert ask.EFFORT_LAST == {"retrieve_passes": 1, "gather_tiers": 0}


def test_ask_answer_effort_last_resets_between_calls(monkeypatch) -> None:
    monkeypatch.setattr(ask, "_pkm_root", lambda: Path("/fake/root"))
    monkeypatch.setattr(ask, "_retrieve_set", lambda conn, q, k: [_weak_floor_hit()])
    monkeypatch.setattr(ask.GA, "gather_answer", lambda *a, **k: None)
    monkeypatch.setattr(ask.SYN, "synthesize",
                        lambda *a, **k: ("raw prose [1]", "sk", False))
    ask.answer(conn=None, question="q1", k=8, expand=False, gather=True)
    assert ask.EFFORT_LAST["gather_tiers"] == 1
    ask.answer(conn=None, question="q2", k=8, expand=False)  # gather=False this time
    assert ask.EFFORT_LAST == {"retrieve_passes": 1, "gather_tiers": 0}


# --- synthesis arm --------------------------------------------------------------------------


def test_answer_synthesis_calls_ask_answer_with_no_extra_flags(monkeypatch) -> None:
    conn = _FakeConn()
    captured: dict = {}
    monkeypatch.setattr(ask, "connect", lambda: conn)

    def fake_answer(c, question, k, **kwargs):
        captured["kwargs"] = kwargs
        _bill(1)
        ask.LOOKUP_LAST = None
        ask.NARRATIVE_LAST = _fake_narrative()
        ask.STAGES_LAST = {"retrieve": "rk", "synthesize": "sk", "narrative_answer": "nk"}
        ask.EFFORT_LAST = {"retrieve_passes": 1, "gather_tiers": 0}
        return ("the claim [1]", [], {})

    monkeypatch.setattr(ask, "answer", fake_answer)
    out = AS.answer_synthesis(_q(), 8)
    assert captured["kwargs"] == {}                    # NOT gather=True — this is the delta
    assert out.status == "ok"
    assert out.decision_view is not None and out.decision_view["family"] == "narrative"
    assert out.declined is False
    assert out.lineage_keys == ("rk", "sk", "nk")
    assert out.effort == {"retrieve_passes": 1, "gather_tiers": 0}
    assert conn.closed is True


def test_answer_synthesis_error_path_never_propagates(monkeypatch) -> None:
    monkeypatch.setattr(ask, "connect", lambda: _FakeConn())
    monkeypatch.setattr(ask, "answer",
                         lambda c, q, k, **kw: (_ for _ in ()).throw(RuntimeError("kaboom")))
    out = AS.answer_synthesis(_q(), 8)
    assert out.status == "error"
    assert "kaboom" in out.notes
    assert out.text == ""


def test_answer_synthesis_declined_derivation_matches_baseline_inprocess(monkeypatch) -> None:
    # Same view -> same declined verdict via the SAME formula, whichever arm module called it
    # (the harness's one declined convention — task-8 brief).
    view = {"asserted": False, "scoped": False}
    monkeypatch.setattr(ask, "connect", lambda: _FakeConn())

    def fake_answer(c, question, k, **kwargs):
        ask.LOOKUP_LAST = _fake_lookup(action="abstain", candidates=[], credences=[])
        ask.NARRATIVE_LAST = None
        ask.STAGES_LAST = {}
        ask.EFFORT_LAST = {}
        return (ask.ABSTENTION, [], {})

    monkeypatch.setattr(ask, "answer", fake_answer)
    out_synth = AS.answer_synthesis(_q(), 8)
    out_base = AB.answer_baseline(_q(), 8, path="inprocess")
    assert out_synth.declined == out_base.declined == AB._view_declined(view)
