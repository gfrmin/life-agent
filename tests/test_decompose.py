"""The decompose transform (life_agent.core.decompose) — foundations §5, hermetic.

A question may ask for several distinct single-value facts at once ("my mortgage —
lender, amount, and end date" asks three). Decompose splits it into the labeled
single-value sub-questions it asks, so each becomes its OWN candidate set + posterior,
decided per-field by the daemon (no pooling, no slots>1 route-fork). The slots flow
from the QUESTION (the owner's ruling), not a declared vocabulary. A single-value
question is the degenerate one-field case — decompose preserves it exactly, so the
single-value read-path is unchanged.

The local model is faked (the route_question / subject.py client pattern), and §18.9
records land under ``migrated_root``.

Run: uv run --project . python -m pytest tests/test_decompose.py
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from life_agent.core.decompose import Field, decompose_question
from pkm.transform import ModelResponse


@pytest.fixture
def migrated_root(tmp_path: Path) -> Path:
    (tmp_path / "cache").mkdir()
    (tmp_path / "logs").mkdir()
    return tmp_path


class FakeClient:
    """The subject.py fake-client pattern: scripted JSON replies, call counting."""

    engine_version = "fake-1"

    def __init__(self, replies: list[dict] | dict) -> None:
        self._replies = replies if isinstance(replies, list) else [replies]
        self.calls = 0

    def complete(self, prompt: str, schema: dict[str, Any]) -> ModelResponse:
        reply = self._replies[min(self.calls, len(self._replies) - 1)]
        self.calls += 1
        return ModelResponse(raw_text=json.dumps(reply), input_tokens=1,
                             output_tokens=1, latency_ms=1, cost_usd=0.0)


def test_multi_value_splits_into_labeled_fields_and_caches(migrated_root: Path) -> None:
    client = FakeClient({"fields": [
        {"label": "lender", "question": "What is the lender of my mortgage?"},
        {"label": "amount", "question": "What is the amount of my mortgage?"},
        {"label": "end date", "question": "When does my mortgage end?"},
    ]})
    q = "What is my mortgage — lender, amount, and end date?"
    f1 = decompose_question(migrated_root, q, client=client)
    f2 = decompose_question(migrated_root, q, client=client)
    assert f1 == f2 == [
        Field(label="lender", question="What is the lender of my mortgage?"),
        Field(label="amount", question="What is the amount of my mortgage?"),
        Field(label="end date", question="When does my mortgage end?"),
    ]
    assert client.calls == 1  # replayed from cache


def test_single_value_question_yields_one_field(migrated_root: Path) -> None:
    client = FakeClient({"fields": [
        {"label": "passport number", "question": "what is my passport number?"},
    ]})
    fields = decompose_question(migrated_root, "what is my passport number?", client=client)
    assert fields == [Field(label="passport number", question="what is my passport number?")]


def test_empty_decomposition_degrades_to_whole_question(migrated_root: Path) -> None:
    # §9 no-hard-zeros: a model that returns no fields must not DROP the question — decompose
    # degrades to the single whole-question field (the degenerate case), never silence.
    client = FakeClient({"fields": []})
    q = "what is my tax id?"
    assert decompose_question(migrated_root, q, client=client) == [Field(label=q, question=q)]


def test_field_with_blank_subquestion_is_dropped(migrated_root: Path) -> None:
    # a blank sub-question carries no askable content; drop it, keep the real ones (never a
    # blank field reaching retrieve/extract). If ALL are blank, degrade to the whole question.
    client = FakeClient({"fields": [
        {"label": "lender", "question": "What is the lender of my mortgage?"},
        {"label": "junk", "question": "   "},
    ]})
    q = "my mortgage lender?"
    assert decompose_question(migrated_root, q, client=client) == [
        Field(label="lender", question="What is the lender of my mortgage?")]


def test_is_multi_field_only_when_more_than_one(migrated_root: Path) -> None:
    single = FakeClient({"fields": [{"label": "x", "question": "what is x?"}]})
    multi = FakeClient({"fields": [{"label": "a", "question": "what is a?"},
                                   {"label": "b", "question": "what is b?"}]})
    assert len(decompose_question(migrated_root, "what is x?", client=single)) == 1
    assert len(decompose_question(migrated_root, "a and b?", client=multi)) == 2
