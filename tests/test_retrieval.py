"""The corpus-retrieval seam (life_agent.core.retrieval) — hermetic, no DuckDB.

``retrieve_set`` is the one retrieval implementation the live ask and the bridge share, so
its output must be a function of the search results themselves, not of the order the FTS
engine happened to return them in. ``pkm.retrieval.search`` is imported INSIDE the function,
so patching the module attribute reaches it.

Run: uv run --project . python -m pytest tests/test_retrieval.py
"""
from __future__ import annotations

from typing import Any, cast

import pytest

from life_agent.core import retrieval as RET


def _hit(chunk: str, score: float, key: str) -> Any:
    from pkm.retrieval import SearchResult
    return SearchResult(chunk_text=chunk, score=score, source_path=f"/corpus/{key[:8]}.eml",
                        source_origin=None, artifact_cache_key=key)


def _scripted(monkeypatch: pytest.MonkeyPatch, hits: list[Any]) -> None:
    import pkm.retrieval
    monkeypatch.setattr(pkm.retrieval, "search", lambda conn, q, k: list(hits))


# M0.5 — finding 2: pkm's FTS returns tied BM25 scores in a nondeterministic order (13 ties
# among 80 hits on a measured query), and `retrieve_set`'s stable sort preserved that order.
# Where a tie straddles the top-k cut the retrieved SET changed between two runs of the same
# code on the same corpus — the fixtures' recorded inputs, and every §18.9 derivation keyed
# on them. The fix is a declared total order: (-score, artifact_cache_key, chunk_text).

def test_retrieve_set_is_invariant_to_the_order_search_returns(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # four chunks, all tied, k=2: whichever two survive must not depend on arrival order.
    hits = [_hit("alpha text", 31.960842, "a" * 64), _hit("bravo text", 31.960842, "b" * 64),
            _hit("charlie text", 31.960842, "c" * 64), _hit("delta text", 31.960842, "d" * 64)]
    _scripted(monkeypatch, hits)
    forward = RET.retrieve_set(cast(Any, None), "q", k=2)
    _scripted(monkeypatch, list(reversed(hits)))
    reverse = RET.retrieve_set(cast(Any, None), "q", k=2)
    assert forward == reverse


def test_retrieve_set_orders_ties_by_the_declared_key(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # the declared order is (-score, artifact_cache_key, chunk_text): score dominates, then
    # the document, then the text — so the ranking is reproducible and cheap to reason about.
    hits = [_hit("zulu text", 31.960842, "c" * 64), _hit("alpha text", 31.960842, "a" * 64),
            _hit("mike text", 40.0, "z" * 64)]
    _scripted(monkeypatch, hits)
    got = RET.retrieve_set(cast(Any, None), "q", k=3)
    assert [h["artifact_cache_key"] for h in got] == ["z" * 64, "a" * 64, "c" * 64]


def test_retrieve_set_dedupes_duplicate_chunk_text_deterministically(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # identical chunk text across DIFFERENT documents at an identical score is the corpus's
    # commonest shape (a forwarded/quoted copy). Keeping the first-arrived one made the
    # surviving document — the identity the whole §5 dedup then reasons over — depend on the
    # engine's order.
    dup = [_hit("a shared paragraph", 31.960842, "b" * 64),
           _hit("a shared paragraph", 31.960842, "a" * 64)]
    _scripted(monkeypatch, dup)
    forward = RET.retrieve_set(cast(Any, None), "q", k=5)
    _scripted(monkeypatch, list(reversed(dup)))
    reverse = RET.retrieve_set(cast(Any, None), "q", k=5)
    assert len(forward) == 1
    assert forward == reverse


def test_retrieve_set_still_keeps_the_best_scoring_copy_of_a_chunk(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # the tie-break must not disturb the dedupe RULE: best score wins, whatever the order.
    dup = [_hit("a shared paragraph", 12.0, "a" * 64),
           _hit("a shared paragraph", 31.960842, "b" * 64)]
    _scripted(monkeypatch, dup)
    assert RET.retrieve_set(cast(Any, None), "q", k=5)[0]["artifact_cache_key"] == "b" * 64
    _scripted(monkeypatch, list(reversed(dup)))
    assert RET.retrieve_set(cast(Any, None), "q", k=5)[0]["artifact_cache_key"] == "b" * 64
