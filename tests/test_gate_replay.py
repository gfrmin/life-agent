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
