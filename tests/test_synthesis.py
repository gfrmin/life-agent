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
