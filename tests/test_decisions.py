"""The decision log (bayesian-foundations §8) — no EU decision is ever made unlogged.

Mirrors the outcomes-log discipline: append-only JSONL, file order = canonical replay
order, closed vocabularies validated at construction, durable appends, loud corruption.

Run: uv run --project . python -m pytest tests/test_decisions.py
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from life_agent.core import decisions as D


def _event(**overrides: object) -> D.DecisionEvent:
    base: dict = dict(
        tx_time="2026-06-12T12:00:00+00:00",
        run_id="ask-test",
        question_id="q-001",
        family="lookup",
        action_set=("report", "hedge", "ask_clarify", "abstain"),
        posterior_summary={"top_claim_credence": 0.92, "n_claims": 1},
        utility_fold_version="a" * 64,
        chosen_action="report",
        predicted_eu=0.87,
    )
    base.update(overrides)
    return D.DecisionEvent(**base)  # type: ignore[arg-type]


# --- closed vocabularies -----------------------------------------------------------------

def test_unknown_family_rejected() -> None:
    with pytest.raises(ValueError, match="family"):
        _event(family="vibes")


def test_action_outside_vocabulary_rejected() -> None:
    with pytest.raises(ValueError, match="action"):
        _event(action_set=("report", "shrug"))


def test_chosen_action_must_be_in_action_set() -> None:
    with pytest.raises(ValueError, match="chosen"):
        _event(chosen_action="abstain", action_set=("report", "hedge"))


def test_empty_action_set_rejected() -> None:
    with pytest.raises(ValueError, match="action_set"):
        _event(action_set=())


# --- append-only round trip --------------------------------------------------------------

def test_round_trip_and_order(tmp_path: Path) -> None:
    log = tmp_path / "calibration" / "decisions.jsonl"
    first = _event(question_id="q-001")
    second = _event(question_id="q-002", chosen_action="abstain", predicted_eu=0.0)
    D.append(log, first)
    D.append(log, second)
    assert D.read(log) == [first, second]
    assert len(log.read_text(encoding="utf-8").splitlines()) == 2


def test_read_missing_is_empty(tmp_path: Path) -> None:
    assert D.read(tmp_path / "absent.jsonl") == []


def test_lines_are_canonical_json(tmp_path: Path) -> None:
    log = tmp_path / "decisions.jsonl"
    D.append(log, _event())
    line = log.read_text(encoding="utf-8").splitlines()[0]
    obj = json.loads(line)
    assert obj["format_version"] == D.FORMAT_VERSION
    assert line == json.dumps(obj, sort_keys=True, ensure_ascii=False,
                              separators=(",", ":"))


def test_corrupt_line_is_loud(tmp_path: Path) -> None:
    log = tmp_path / "decisions.jsonl"
    log.write_text('{"oops": true}\n', encoding="utf-8")
    with pytest.raises((KeyError, TypeError, ValueError)):
        D.read(log)
