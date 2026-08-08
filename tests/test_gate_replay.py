"""The Δ2 gate baseline: the owner's outside option as a replayed raw-deliberative arm.

The comparator the §8 gate values arm B against becomes what the owner would actually do
without the agent — ask Claude with corpus access and act on what it says (owner decision
2026-08-06). Measured offline: the fair-fight run's stored answers replay as the arm; the
join is STRICT (a missing question is named, never silently dropped — no silent caps).

Run: uv run --project . python -m pytest tests/test_gate_replay.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import run_eval as RE


def _row(qid: str, text: str, *, declined: bool = False,
         status: str = "ok") -> dict[str, Any]:
    return {"question_id": qid, "text": text, "declined": declined, "status": status}


def _write_answers(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


# --- load_replay_answers -----------------------------------------------------------------

def test_load_replay_answers_from_jsonl(tmp_path: Path) -> None:
    p = _write_answers(tmp_path / "answers.jsonl",
                       [_row("q2-001", "P123 [doc.pdf]"), _row("q2-002", "x")])
    rows = RE.load_replay_answers(p)
    assert set(rows) == {"q2-001", "q2-002"}
    assert rows["q2-001"]["text"] == "P123 [doc.pdf]"


def test_load_replay_answers_from_run_dir(tmp_path: Path) -> None:
    _write_answers(tmp_path / "arms" / "deliberative" / "answers.jsonl",
                   [_row("q2-001", "P123")])
    rows = RE.load_replay_answers(tmp_path)
    assert set(rows) == {"q2-001"}


# --- _replay_response: the arm graded on the ONE common answer-level scale ---------------

def test_replay_report_graded_by_gold_containment() -> None:
    q = {"id": "q2-001", "answer": "P123", "answer_variants": [], "fuzzy": False}
    r = RE._replay_response(_row("q2-001", "the number is P123 [doc.pdf]"), q)
    assert r.action == "report"
    assert r.correct is True
    wrong = RE._replay_response(_row("q2-001", "the number is Q999 [doc.pdf]"), q)
    assert wrong.action == "report"
    assert wrong.correct is False


def test_replay_decline_is_an_abstention() -> None:
    q = {"id": "q2-001", "answer": "P123", "answer_variants": [], "fuzzy": False}
    r = RE._replay_response(
        _row("q2-001", "NOT_IN_CORPUS: nothing", declined=True), q)
    assert r.action == "abstain"
    assert r.correct is None


def test_replay_error_row_is_an_abstention() -> None:
    q = {"id": "q2-001", "answer": "P123", "answer_variants": [], "fuzzy": False}
    r = RE._replay_response(_row("q2-001", "", status="error"), q)
    assert r.action == "abstain"


def test_replay_blank_ok_row_is_an_abstention_not_a_confident_wrong() -> None:
    # rc=0 with an empty result is a degenerate run, not an assertion — grading it as a
    # report would mint a spurious confident-wrong (the A3 sign rested on 3 of those).
    q = {"id": "q2-001", "answer": "P123", "answer_variants": [], "fuzzy": False}
    assert RE._replay_response(_row("q2-001", ""), q).action == "abstain"
    assert RE._replay_response(_row("q2-001", "   "), q).action == "abstain"
    none_text = dict(_row("q2-001", ""), text=None)
    assert RE._replay_response(none_text, q).action == "abstain"


def test_paired_dict_names_its_baseline_arm() -> None:
    import life_agent.core.gate as GATE

    p = GATE.PairedOutcome(
        question_id="q2-001", answerable=True,
        typed=GATE.RealisedResponse(action="abstain", correct=None),
        mono=GATE.RealisedResponse(action="report", correct=True))
    d = RE._paired_to_dict(p, baseline="raw-deliberative-replay")
    assert d["baseline"] == "raw-deliberative-replay"
    assert RE._paired_to_dict(p)["baseline"] == "monolithic"


# --- gate_paired_outcomes with the replay baseline ----------------------------------------

class _FakeAsk:
    """The production path stub: typed pass answers; a families=False call would be the
    monolithic arm — with a replay baseline it must never fire."""

    ABSTENTION = "ABSTAIN-SENTINEL"

    def __init__(self) -> None:
        self.LOOKUP_LAST: Any = None
        self.NARRATIVE_LAST: Any = None
        self.calls: list[dict[str, Any]] = []

    def answer(self, conn: Any, question: str, k: int, **kw: Any) -> tuple[str, list, dict]:
        self.calls.append(kw)
        return self.ABSTENTION, [], {}


def _questions() -> list[dict[str, Any]]:
    return [{"id": "q2-001", "question": "value?", "answer": "P123",
             "answer_variants": [], "fuzzy": False, "answerable": True}]


def test_gate_pairs_typed_against_the_replay_arm(tmp_path: Path) -> None:
    replay = {"q2-001": _row("q2-001", "P123 [doc.pdf]")}
    paired = RE.gate_paired_outcomes(None, _questions(), 20, _FakeAsk(), replay=replay)
    (p,) = paired
    assert p.mono.action == "report"
    assert p.mono.correct is True
    assert p.typed.action == "abstain"


def test_gate_replay_never_runs_the_monolithic_pass(tmp_path: Path) -> None:
    fake = _FakeAsk()
    RE.gate_paired_outcomes(None, _questions(), 20, fake, replay={
        "q2-001": _row("q2-001", "P123")})
    assert all(c.get("families") is not False for c in fake.calls)
    assert not any("families" in c for c in fake.calls)


def test_gate_replay_missing_question_is_named_never_dropped() -> None:
    with pytest.raises(ValueError, match="q2-001"):
        RE.gate_paired_outcomes(None, _questions(), 20, _FakeAsk(), replay={})


# --- the executor typed arm (--gate-executor): the gate finally SEES the edge -------------

def _exec_view(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "effector": "abstain", "asserted": [], "candidates": ["P123"],
        "credences": [0.6], "p_none": 0.4, "eu": 0.0, "n_obs": 1,
        "hits": [], "route": {"construct": "passport number"},
        "instrument": "", "cost_usd": None, "latency_s": None,
        "instrument_value": None, "instrument_confidence": None,
        "instrument_lineage": None, "edge_events": []}
    base.update(overrides)
    return base


def test_typed_response_executor_grades_each_effector() -> None:
    q = {"id": "q1", "answer": "P123", "answer_variants": []}
    r = RE._typed_response_executor(_exec_view(effector="report", asserted=["P123"]), q)
    assert r.action == "report" and r.correct is True
    r = RE._typed_response_executor(_exec_view(effector="report", asserted=["WRONG"]), q)
    assert r.action == "report" and r.correct is False
    r = RE._typed_response_executor(
        _exec_view(effector="hedge", candidates=["X", "P123"]), q)
    assert r.action == "hedge" and r.correct is True
    r = RE._typed_response_executor(_exec_view(effector="ask_clarify"), q)
    assert r.action == "ask_clarify" and r.correct is None
    # the executor's miss (the local edge declined) asserted nothing — an abstention
    # on the gate's answer-level scale
    r = RE._typed_response_executor(_exec_view(effector="miss"), q)
    assert r.action == "abstain" and r.correct is None
    r = RE._typed_response_executor(_exec_view(effector="abstain"), q)
    assert r.action == "abstain" and r.correct is None


class _FakeExecutorAsk:
    """ask with the executor surface stubbed: answer_via_executor pops the scripted view
    into EXECUTOR_VIEW_LAST; the family path must never run under the executor arm."""

    ABSTENTION = "ABSTAIN-SENTINEL"

    def __init__(self, views: list[dict[str, Any] | None]) -> None:
        self._views = list(views)
        self.EXECUTOR_VIEW_LAST: dict[str, Any] | None = None
        self.EXECUTOR_HOLD_OUT_QUESTION_ID: str | None = None
        self.executor_calls: list[str] = []
        self.holdouts_seen: list[str | None] = []

    def answer_via_executor(self, question: str, k: int) -> tuple[str, list, dict]:
        self.executor_calls.append(question)
        self.holdouts_seen.append(self.EXECUTOR_HOLD_OUT_QUESTION_ID)
        self.EXECUTOR_VIEW_LAST = self._views.pop(0)
        return ("rendered", [], {})

    def answer(self, conn: Any, question: str, k: int, **kw: Any) -> tuple[str, list, dict]:
        raise AssertionError("the family path must not run under the executor arm")


def test_gate_executor_arm_pairs_the_view_against_replay() -> None:
    fake = _FakeExecutorAsk([_exec_view(effector="report", asserted=["P123"],
                                        instrument="deliberate@claude-opus-4-8",
                                        cost_usd=0.31)])
    replay = {"q2-001": _row("q2-001", "P123 [doc.pdf]")}
    paired = RE.gate_paired_outcomes(None, _questions(), 20, fake, replay=replay,
                                     typed_arm="executor")
    (p,) = paired
    assert p.typed.action == "report" and p.typed.correct is True
    assert p.mono.action == "report" and p.mono.correct is True
    assert fake.executor_calls == ["value?"]


def test_gate_executor_arm_collects_views_for_the_writer() -> None:
    view = _exec_view(effector="abstain", instrument="deliberate@claude-opus-4-8",
                      instrument_value="P123", instrument_confidence=0.85,
                      instrument_lineage="dk-1", cost_usd=0.31, latency_s=21.7,
                      edge_events=[{"edge": "deliberate@claude-opus-4-8",
                                    "value": "P123", "confidence": 0.85,
                                    "lineage": "dk-1"}])
    fake = _FakeExecutorAsk([view])
    out: list = []
    RE.gate_paired_outcomes(None, _questions(), 20, fake,
                            replay={"q2-001": _row("q2-001", "P123")},
                            typed_arm="executor", typed_views=out)
    ((q, v),) = out
    assert q["id"] == "q2-001" and v is view
    # the writer's rows build straight off the collected pair — the abstained act
    # still grades the edge's raw proposal
    (e,) = RE.edge_outcomes(q, v, run_id="r")
    assert e.grade == "CORRECT" and e.probability == 0.85


def test_judge_shadow_items_cover_every_graded_candidate_and_skip_ungradeable() -> None:
    # the shadow judge grades exactly what the matcher grades: the typed arm's assert,
    # the replay arm's report text, and every gradeable edge firing — and skips what
    # the matcher never grades (abstains, declined/blank replay rows, gold-less
    # questions, valueless events). Arm labels are for the REPORT table only; the
    # judge prompt never sees them (pinned in test_eval_judge).
    questions = [*_two_questions(),
                 {"id": "q2-003", "question": "no gold?", "answer": "",
                  "answer_variants": [], "fuzzy": False, "answerable": False}]
    typed_views = [
        (questions[0], _exec_view(
            effector="report", asserted=["P123"],
            edge_events=[{"edge": "extract@claude-haiku-4-5", "value": "P123",
                          "confidence": 0.7, "lineage": "jk-1"},
                         {"edge": "deliberate@claude-opus-4-8", "value": None,
                          "confidence": None, "lineage": "dk-d"}])),
        (questions[1], _exec_view(effector="abstain")),  # no assert → no typed item
        (questions[2], _exec_view(effector="report", asserted=["whatever"])),  # no gold
    ]
    replay = {"q2-001": _row("q2-001", "the number is P123 [doc.pdf]"),
              "q2-002": _row("q2-002", "NOT_IN_CORPUS", declined=True),
              "q2-003": _row("q2-003", "x")}
    items = RE.judge_shadow_items(questions, typed_views, replay)
    assert [(i["question_id"], i["arm"], i["candidate"]) for i in items] == [
        ("q2-001", "typed", "P123"),
        ("q2-001", "edge:extract@claude-haiku-4-5", "P123"),
        ("q2-001", "mono", "the number is P123 [doc.pdf]")]
    assert items[0]["gold"] == "P123" and items[0]["question"] == "value?"


def test_gate_writer_flatmaps_tier_rows() -> None:
    # two questions, 1 + 2 firings → 3 rows: the writer walks every view's whole
    # attribution stream, so a run harvests the extract tiers alongside deliberate
    views = [
        _exec_view(edge_events=[{"edge": "extract@claude-haiku-4-5", "value": "P123",
                                 "confidence": 0.7, "lineage": "jk-1"}]),
        _exec_view(edge_events=[{"edge": "extract@claude-opus-4-8", "value": "X9",
                                 "confidence": 0.8, "lineage": "jk-2"},
                                {"edge": "deliberate@claude-opus-4-8", "value": "X9",
                                 "confidence": 0.9, "lineage": "dk-2"}]),
    ]
    fake = _FakeExecutorAsk(list(views))
    out: list = []
    RE.gate_paired_outcomes(None, _two_questions(), 20, fake,
                            replay={"q2-001": _row("q2-001", "P123"),
                                    "q2-002": _row("q2-002", "X9")},
                            typed_arm="executor", typed_views=out)
    rows = [e for q, v in out for e in RE.edge_outcomes(q, v, run_id="r")]
    assert [(r.question_id, r.instrument_identity["edge"], r.grade) for r in rows] == [
        ("q2-001", "extract@claude-haiku-4-5", "CORRECT"),
        ("q2-002", "extract@claude-opus-4-8", "CORRECT"),
        ("q2-002", "deliberate@claude-opus-4-8", "CORRECT")]


def test_gate_executor_arm_mid_run_down_is_loud() -> None:
    # a mid-run down stack must VOID the reading (raise, naming the question), never
    # silently convert the remaining questions into abstentions
    fake = _FakeExecutorAsk([None])
    with pytest.raises(RuntimeError, match="q2-001"):
        RE.gate_paired_outcomes(None, _questions(), 20, fake,
                                replay={"q2-001": _row("q2-001", "P123")},
                                typed_arm="executor")


def test_typed_views_accumulate_before_a_mid_run_failure() -> None:
    # the crash-salvage writer's load-bearing property (PR #63 review; the run-3 kill
    # precedent): completed questions' views are already on the out-param when a later
    # question voids the reading — their paid firings can still be graded and written.
    view = _exec_view(edge_events=[{"edge": "extract@claude-haiku-4-5", "value": "P123",
                                    "confidence": 0.7, "lineage": "jk-1"}])
    fake = _FakeExecutorAsk([view, None])
    out: list = []
    with pytest.raises(RuntimeError, match="q2-002"):
        RE.gate_paired_outcomes(None, _two_questions(), 20, fake,
                                replay={"q2-001": _row("q2-001", "P123"),
                                        "q2-002": _row("q2-002", "X9")},
                                typed_arm="executor", typed_views=out)
    ((q, v),) = out
    assert q["id"] == "q2-001" and v is view


def test_fresh_edge_rows_grades_collected_views_and_dedups_against_the_log(
        tmp_path: Path) -> None:
    # the one writer body shared by the normal post-run path and the crash-salvage
    # path: grade every collected firing, dedup against the log's already-written
    # §18.9 lineage, return (fresh, n_dup, prior).
    import life_agent.core.outcomes as O

    log = tmp_path / "outcomes.jsonl"
    q = _questions()[0]
    view = _exec_view(edge_events=[{"edge": "extract@claude-haiku-4-5", "value": "P123",
                                    "confidence": 0.7, "lineage": "jk-1"}])
    (row,) = RE.edge_outcomes(q, view, run_id="r0")
    O.append(log, row)  # a prior run already graded this artifact
    fresh, n_dup, prior = RE._fresh_edge_rows(
        [(q, view),
         (q, _exec_view(edge_events=[{"edge": "extract@claude-opus-4-8", "value": "P123",
                                      "confidence": 0.8, "lineage": "jk-2"}]))],
        run_id="r1", log=log)
    assert [r.instrument_identity["edge"] for r in fresh] == ["extract@claude-opus-4-8"]
    assert n_dup == 1
    assert len(prior) == 1


# --- --gate-loo: the run-4 held-out discipline (grouped leave-one-question-out) ----------

def _two_questions() -> list[dict[str, Any]]:
    return [*_questions(), {"id": "q2-002", "question": "other?", "answer": "X9",
                            "answer_variants": [], "fuzzy": False, "answerable": True}]


def test_gate_loo_holds_out_each_question_in_turn() -> None:
    # under loo=True the executor arm's curve fold must exclude the question being
    # asked — the hold-out is set BEFORE each call and cleared after the run, so a
    # question's decide never conditions on its own graded outcome (p3_gate precedent)
    fake = _FakeExecutorAsk([_exec_view(), _exec_view()])
    replay = {"q2-001": _row("q2-001", "P123"), "q2-002": _row("q2-002", "X9")}
    RE.gate_paired_outcomes(None, _two_questions(), 20, fake, replay=replay,
                            typed_arm="executor", loo=True)
    assert fake.holdouts_seen == ["q2-001", "q2-002"]
    assert fake.EXECUTOR_HOLD_OUT_QUESTION_ID is None


def test_gate_loo_off_never_touches_the_hold_out() -> None:
    # loo=False (the default, run 3's shape) must leave the live hold-out untouched —
    # the in-sample fold is run 3's DISCLOSED shape, not an accident of the new flag
    fake = _FakeExecutorAsk([_exec_view()])
    RE.gate_paired_outcomes(None, _questions(), 20, fake,
                            replay={"q2-001": _row("q2-001", "P123")},
                            typed_arm="executor", loo=False)
    assert fake.holdouts_seen == [None]


def test_gate_loo_resets_the_hold_out_when_the_run_voids() -> None:
    # a voided reading (mid-run down) must not leak the last question's hold-out into
    # the module state a later LIVE ask would fold under
    fake = _FakeExecutorAsk([None])
    with pytest.raises(RuntimeError, match="q2-001"):
        RE.gate_paired_outcomes(None, _questions(), 20, fake,
                                replay={"q2-001": _row("q2-001", "P123")},
                                typed_arm="executor", loo=True)
    assert fake.EXECUTOR_HOLD_OUT_QUESTION_ID is None


def test_gate_loo_on_the_family_arm_refuses() -> None:
    # the family arm folds no curves — a LOO reading over it would be a silent no-op
    # wearing the held-out label; refuse loudly
    with pytest.raises(ValueError, match="executor"):
        RE.gate_paired_outcomes(None, _questions(), 20, _FakeAsk(),
                                replay={"q2-001": _row("q2-001", "P123")}, loo=True)


def test_gate_loo_without_executor_flag_refuses(monkeypatch, capsys) -> None:
    # CLI precondition: --gate-loo without --gate-executor is refused BEFORE any state
    # is touched — there is no curve fold on the family arm to hold anything out of
    monkeypatch.setattr(sys, "argv", ["run_eval.py", "--gate", "--gate-loo"])
    assert RE.main() == 2
    assert "--gate-executor" in capsys.readouterr().out


def test_gate_loo_without_deliberate_flag_refuses(monkeypatch, capsys) -> None:
    # PR #58 review Major: with LIFE_AGENT_DELIBERATE unset, answer_via_executor never
    # folds curves at all (ask.py: transforms, curves = None, None) — a --gate-loo run
    # would complete and publish the held-out label over a TOTAL no-op, the §17.4
    # label-outruns-mechanics shape. Refused before any state is touched.
    monkeypatch.delenv("LIFE_AGENT_DELIBERATE", raising=False)
    monkeypatch.setattr(sys, "argv",
                        ["run_eval.py", "--gate", "--gate-executor", "--gate-loo"])
    monkeypatch.setattr(RE, "load_questions",
                        lambda p: (_ for _ in ()).throw(AssertionError("state touched")))
    assert RE.main() == 2
    assert "LIFE_AGENT_DELIBERATE" in capsys.readouterr().out


def test_executor_run_stats_summarise_spend_and_fired() -> None:
    views = [
        ({"id": "a"}, _exec_view(instrument="deliberate@claude-opus-4-8",
                                 cost_usd=0.31)),
        ({"id": "b"}, _exec_view(instrument="deliberate@claude-opus-4-8",
                                 cost_usd=0.0)),          # warm §18.9 replay
        ({"id": "c"}, _exec_view()),                      # edge never fired
    ]
    s = RE.executor_run_stats(views)
    assert s["n"] == 3
    assert s["deliberate_fired"] == 2
    assert s["warm_hits"] == 1
    assert s["spend_usd"] == pytest.approx(0.31)
