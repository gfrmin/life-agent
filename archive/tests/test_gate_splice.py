"""scripts/gate_splice.py — the arm-splice counterfactual harness (foundations §14).

Hermetic: the pure splice/cost helpers only. The production posterior needs the credence
skin (julia) and is exercised by the archived counterfactual report, not here."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import gate_splice as GS

from life_agent.core import gate as GATE
from life_agent.core.decisions import question_id as qhash


def _paired(path: Path, rows: list[dict]) -> Path:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


def _row(qid: str, typed: dict, mono: dict) -> dict:
    return {"question_id": qid, "answerable": True, "typed": typed, "mono": mono}


def test_splice_takes_typed_from_one_archive_and_mono_from_another(tmp_path: Path) -> None:
    a = GS.load_paired(_paired(tmp_path / "a.jsonl", [
        _row("q1", {"action": "abstain", "correct": None},
             {"action": "report", "correct": True}),
        _row("q2", {"action": "report", "correct": True, "cost_usd": 0.5},
             {"action": "report", "correct": True})]))
    b = GS.load_paired(_paired(tmp_path / "b.jsonl", [
        _row("q1", {"action": "report", "correct": True, "cost_usd": 1.0},
             {"action": "report", "correct": False, "cost_usd": 0.4, "withheld": None}),
        _row("q2", {"action": "report", "correct": False},
             {"action": "abstain", "correct": None, "cost_usd": 0.3})]))
    out = GS.splice(a, b, typed_cost=None, mono_cost=None, zero_cost=False)
    assert [p.question_id for p in out] == ["q1", "q2"]
    # typed from a (its own archived cost, 0 when the field predates spend)
    assert out[0].typed == GATE.RealisedResponse("abstain", None, 0.0)
    assert out[1].typed == GATE.RealisedResponse("report", True, 0.5)
    # mono from b, with b's archived costs
    assert out[0].mono == GATE.RealisedResponse("report", False, 0.4)
    assert out[1].mono == GATE.RealisedResponse("abstain", None, 0.3)


def test_splice_cost_modes(tmp_path: Path) -> None:
    rows = GS.load_paired(_paired(tmp_path / "a.jsonl", [
        _row("q1", {"action": "report", "correct": True, "cost_usd": 0.5},
             {"action": "report", "correct": True, "cost_usd": 0.7})]))
    zero = GS.splice(rows, rows, typed_cost=None, mono_cost=None, zero_cost=True)[0]
    assert (zero.typed.cost_usd, zero.mono.cost_usd) == (0.0, 0.0)
    priced = GS.splice(rows, rows, typed_cost={"q1": 0.02}, mono_cost={"q1": 0.9},
                       zero_cost=False)[0]
    assert (priced.typed.cost_usd, priced.mono.cost_usd) == (0.02, 0.9)
    # a question the cost map lacks spent nothing there — never the archived value
    priced2 = GS.splice(rows, rows, typed_cost={}, mono_cost={}, zero_cost=False)[0]
    assert (priced2.typed.cost_usd, priced2.mono.cost_usd) == (0.0, 0.0)


def test_splice_refuses_differing_question_sets(tmp_path: Path) -> None:
    a = GS.load_paired(_paired(tmp_path / "a.jsonl", [
        _row("q1", {"action": "abstain"}, {"action": "abstain"})]))
    b = GS.load_paired(_paired(tmp_path / "b.jsonl", [
        _row("q2", {"action": "abstain"}, {"action": "abstain"})]))
    with pytest.raises(SystemExit, match="question sets differ"):
        GS.splice(a, b, typed_cost=None, mono_cost=None, zero_cost=False)


def test_decisions_cost_sums_per_question_for_one_run_only(tmp_path: Path, monkeypatch) -> None:
    questions = [{"id": "q2-001", "question": "How many?"},
                 {"id": "q2-002", "question": "Which email?"}]
    log = tmp_path / "decisions.jsonl"
    log.write_text("".join(json.dumps(r) + "\n" for r in [
        {"run_id": "run-A", "question_id": qhash("How many?"), "cost_usd": 0.5},
        {"run_id": "run-A", "question_id": qhash("How many?"), "cost_usd": 0.25},
        {"run_id": "run-A", "question_id": qhash("Which email?"), "cost_usd": None},
        {"run_id": "run-B", "question_id": qhash("Which email?"), "cost_usd": 9.0},
        {"run_id": "run-A", "question_id": "unknownhash000000", "cost_usd": 3.0},
    ]), encoding="utf-8")
    monkeypatch.setattr(GS.LCFG, "DECISIONS_LOG", log)
    assert GS.decisions_cost("run-A", questions) == {"q2-001": 0.75, "q2-002": 0.0}


def test_replay_cost_reads_usage_estimated_cost(tmp_path: Path) -> None:
    ans = tmp_path / "arms" / "deliberative"
    ans.mkdir(parents=True)
    (ans / "answers.jsonl").write_text(
        json.dumps({"question_id": "q1", "usage": {"estimated_cost_usd": 0.31}}) + "\n"
        + json.dumps({"question_id": "q2", "usage": {}}) + "\n", encoding="utf-8")
    assert GS.replay_cost(tmp_path) == {"q1": 0.31, "q2": 0.0}
