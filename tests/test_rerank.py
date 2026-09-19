"""core/rerank.py — the listwise rerank is a recorded, metered derivation (hermetic: the
model is a scripted callable; every value is synthetic)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from life_agent.core import rerank as RR
from life_agent.core.llm import LLMResult


def _pool(n: int) -> list[dict[str, Any]]:
    return [{"artifact_cache_key": f"{i:064x}", "chunk_text": f"snippet {i}", "score": 1.0}
            for i in range(n)]


@pytest.fixture
def root(tmp_path: Path) -> Path:
    (tmp_path / "cache").mkdir()
    (tmp_path / "logs").mkdir()
    return tmp_path


def _scripted(calls: list[dict[str, Any]], text: str = "[3, 1]"):
    def complete(system: str, user: str, **kw: Any) -> LLMResult:
        calls.append(kw)
        return LLMResult(text=text, in_tokens=12_000, out_tokens=20, seconds=1.0,
                         served_model="claude-sonnet-4-6")
    return complete


def test_a_rerank_is_recorded_and_replays_free_and_identical(
        root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(RR, "anthropic_complete", _scripted(calls))
    pool = _pool(5)
    hits, cost = RR.rerank("which?", pool, 3, root=root)
    assert [h["chunk_text"] for h in hits] == ["snippet 2", "snippet 0", "snippet 1"]
    assert cost == pytest.approx(12_000 * 3.0 / 1e6 + 20 * 15.0 / 1e6)
    assert calls[0]["temperature"] == 0.0            # deterministic, so replay is faithful
    again, cost2 = RR.rerank("which?", pool, 3, root=root)
    assert again == hits and cost2 == 0.0 and len(calls) == 1


def test_a_failed_rerank_is_the_lexical_head_and_is_not_recorded(
        root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*a: Any, **k: Any) -> LLMResult:
        raise RuntimeError("api down")
    monkeypatch.setattr(RR, "anthropic_complete", boom)
    hits, cost = RR.rerank("which?", _pool(5), 3, root=root)
    assert hits == _pool(5)[:3] and cost == 0.0
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(RR, "anthropic_complete", _scripted(calls))
    RR.rerank("which?", _pool(5), 3, root=root)
    assert len(calls) == 1                           # the failure left nothing to replay


def test_a_small_pool_is_not_reranked() -> None:
    assert RR.rerank("which?", _pool(2), 3) == (_pool(2), 0.0)
