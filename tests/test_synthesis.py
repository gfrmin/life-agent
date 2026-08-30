"""The cited-answer synthesizer's pure seams (the live model call is exercised elsewhere).

Here: `cards_from_hits` attaching each card's `as_of` from a doc_date projection — the
temporal-scope keystone's date threading at the narrative family's proposal stage.
"""
from __future__ import annotations

from life_agent.core import synthesis as SYN


def _hit(key: str, text: str) -> dict[str, str]:
    return {"artifact_cache_key": key, "chunk_text": text, "origin": f"/c/{key}", "score": 1.0}


def test_cards_from_hits_attaches_dates_when_given() -> None:
    hits = [_hit("a", "bank zephyr current bank"), _hit("b", "bank aurum older")]
    dates = {"a": "2025-11-03", "b": None}     # b projected-but-undated
    cards = SYN.cards_from_hits(hits, dates)
    assert [(c.n, c.as_of) for c in cards] == [(1, "2025-11-03"), (2, None)]


def test_cards_from_hits_is_date_blind_by_default() -> None:
    # back-compat: omitting `dates` leaves every card undated (the hermetic path)
    cards = SYN.cards_from_hits([_hit("a", "x"), _hit("b", "y")])
    assert all(c.as_of is None for c in cards)
    # a key absent from the map is undated, not an error (the dates map is partial)
    cards2 = SYN.cards_from_hits([_hit("a", "x"), _hit("b", "y")], {"a": "2024-01-01"})
    assert [c.as_of for c in cards2] == ["2024-01-01", None]


# --- r33 RC-2: the proposal stage returns its realised price (the ONE price rule) -------

def _fake_llm(text: str = "answer [1]"):
    from life_agent.core.llm import LLMResult
    return LLMResult(text=text, in_tokens=1000, out_tokens=200, seconds=1.5,
                     served_model="claude-haiku-4-5-20251001")


def test_synthesize_returns_its_realised_price(monkeypatch) -> None:
    import pytest

    import life_agent.core as C
    from life_agent.core import pricing as PR
    fake = _fake_llm()
    monkeypatch.setattr(C, "anthropic_complete", lambda *a, **k: fake)
    text, _key, cached, cost = SYN.synthesize(None, "q?", [_hit("a", "x")], "")
    assert cached is False and text == "answer [1]"
    expected = PR.cost_usd(fake)
    assert expected is not None and cost == pytest.approx(expected) and cost > 0


def test_synthesize_cached_serve_prices_zero(monkeypatch, tmp_path) -> None:
    import life_agent.core as C
    monkeypatch.setattr(C, "anthropic_complete", lambda *a, **k: _fake_llm())
    (tmp_path / "cache").mkdir()
    (tmp_path / "logs").mkdir()
    _t1, key1, cached1, cost1 = SYN.synthesize(tmp_path, "q?", [_hit("a", "x")], "")
    _t2, key2, cached2, cost2 = SYN.synthesize(tmp_path, "q?", [_hit("a", "x")], "")
    assert key1 == key2 and cached1 is False and cached2 is True
    assert cost1 > 0 and cost2 == 0.0            # a cached serve costs nothing
