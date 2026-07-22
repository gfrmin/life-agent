"""core.claude_verdicts — the Claude-issued verdict channel (owner-authorized 2026-07-22).

The owner's ruling: Claude Code (in-session, deliberative — never a one-shot API call) may
issue verdicts on answers on his behalf, overrulable by him; answer quality is
multidimensional and objective; conversion to a single score is DEFERRED. So the record
stores the dimensions raw — no combined scalar — and the engine projection reads only the
``correct`` dimension (the said@1-relevant fact "asserting the leader now would have been
correct"), which is a measured bit, not a scalarization.

The channel is a THIRD reliability class beside OB-12's two (dense/fallible extraction
ticks; sparse/authoritative owner verdicts): denser than the owner, more authoritative than
extraction. It feeds the ENGINE's verdict evidence only — never the utility posterior
(P(U) is the owner's revealed preference; a Claude verdict is a truth measurement, not a
preference, so ``core.reactions.load_reactions`` stays owner-only by construction: it
reads a different file).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from life_agent.core import claude_verdicts as CV


def _event(decision_id: str = "dec-1", *, correct: int = 1,
           dimensions: dict[str, int] | None = None) -> CV.ClaudeVerdictEvent:
    dims = dimensions if dimensions is not None else {"correct": correct}
    return CV.ClaudeVerdictEvent(
        tx_time="2026-07-22T00:00:00Z", question_id="q-001", decision_id=decision_id,
        dimensions=dims, evidence=("source.pdf p.2",), note="")


# --- the record: declared vocabulary, loud construction errors ----------------------------


def test_correct_dimension_is_required() -> None:
    with pytest.raises(ValueError, match="correct"):
        _event(dimensions={"complete": 1})


def test_unknown_dimension_is_a_loud_error() -> None:
    with pytest.raises(ValueError, match="fluency"):
        _event(dimensions={"correct": 1, "fluency": 1})


def test_dimension_values_are_bits() -> None:
    with pytest.raises(ValueError, match="correct"):
        _event(dimensions={"correct": 2})


def test_optional_dimensions_accepted() -> None:
    e = _event(dimensions={"correct": 1, "complete": 0, "grounded": 1})
    assert e.dimensions["complete"] == 0


def test_issuer_defaults_to_claude_code() -> None:
    assert _event().issuer == "claude-code"


# --- the engine projection: y = the correct bit, nothing combined -------------------------


def test_y_is_the_correct_dimension() -> None:
    assert CV.y(_event(correct=1)) == 1
    assert CV.y(_event(correct=0)) == 0


def test_y_ignores_the_other_dimensions() -> None:
    # correct-but-incomplete still prices said@1 as y=1: the engine's utility form
    # asks "would asserting have been correct", not "was the answer complete".
    assert CV.y(_event(dimensions={"correct": 1, "complete": 0})) == 1


# --- append/read round-trip over the append-only log --------------------------------------


def test_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "claude_verdicts.jsonl"
    CV.append(path, _event("dec-1"))
    CV.append(path, _event("dec-2", correct=0))
    got = CV.read(path)
    assert [e.decision_id for e in got] == ["dec-1", "dec-2"]
    assert got[0] == _event("dec-1")


def test_read_drops_retired_keys_not_the_row(tmp_path: Path) -> None:
    # the append-only log must replay across a field retirement (reactions.py precedent)
    path = tmp_path / "claude_verdicts.jsonl"
    row = json.loads(json.dumps({
        "tx_time": "t", "question_id": "q", "decision_id": "d",
        "dimensions": {"correct": 1}, "evidence": [], "note": "",
        "issuer": "claude-code", "format_version": 1, "retired_field": "x"}))
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    got = CV.read(path)
    assert len(got) == 1 and got[0].decision_id == "d"


def test_evidence_round_trips_as_tuple(tmp_path: Path) -> None:
    path = tmp_path / "claude_verdicts.jsonl"
    CV.append(path, _event("dec-1"))
    assert CV.read(path)[0].evidence == ("source.pdf p.2",)


# --- supersession: latest Claude verdict per decision wins --------------------------------


def test_latest_by_decision_supersedes_in_file_order(tmp_path: Path) -> None:
    path = tmp_path / "claude_verdicts.jsonl"
    CV.append(path, _event("dec-1", correct=1))
    CV.append(path, _event("dec-1", correct=0))  # revised
    latest = CV.latest_by_decision(CV.read(path))
    assert set(latest) == {"dec-1"}
    assert CV.y(latest["dec-1"]) == 0
