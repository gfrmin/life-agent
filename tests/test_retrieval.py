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


# M0.5 / R2 — finding 3: the scores THEMSELVES are not reproducible. DuckDB sums BM25 term
# contributions in a parallelism-dependent order, so two identical calls on an unchanged corpus
# return the same hits at scores differing by 1-2 ulp (149 of 320 hits, measured). A key whose
# leading term is the raw score therefore cannot be a total order however good its tie-breakers:
# the near-tie is resolved by whichever draw the engine happened to make. Quantising the leading
# term to 9 decimal places discards ~1e-15 of noise at BM25 magnitudes of 10-40 and turns the
# near-tie into a declared tie, resolved by the document key like every other tie.

def _jitter(score: float, ulps: int) -> float:
    import math
    for _ in range(ulps):
        score = math.nextafter(score, math.inf)
    return score


def test_retrieve_set_ranks_ulp_separated_scores_as_a_declared_tie(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # the LOWER-keyed document scores one ulp WORSE, so a raw-score key ranks it second and a
    # quantised key ranks it first. One ulp is ~3.6e-15 here — noise, not evidence.
    hits = [_hit("zulu text", _jitter(31.960842, 1), "c" * 64),
            _hit("alpha text", 31.960842, "a" * 64)]
    _scripted(monkeypatch, hits)
    got = RET.retrieve_set(cast(Any, None), "q", k=2)
    assert [h["artifact_cache_key"] for h in got] == ["a" * 64, "c" * 64]


def test_retrieve_set_is_invariant_to_score_jitter_between_identical_calls(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # the live shape: the same corpus, the same query, two calls, scores that wobble in the
    # last bits and a k that cuts through the wobble. Both the SET and its ORDER must hold.
    def call(ulps: dict[str, int]) -> list[str]:
        _scripted(monkeypatch, [_hit(f"{c} text", _jitter(31.960842, ulps.get(c, 0)), c * 64)
                                for c in ("a", "b", "c", "d")])
        return [h["artifact_cache_key"] for h in RET.retrieve_set(cast(Any, None), "q", k=2)]

    assert call({}) == call({"c": 2, "a": 1}) == call({"d": 3, "b": 1})


def test_retrieve_set_still_separates_scores_that_differ_above_the_quantum(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # the quantum resolves ties, it must not MANUFACTURE them: a real score difference — here
    # 1e-8, four orders of magnitude above the rounding — still decides the rank, against the
    # declared key's preference. (Passes before the quantisation too, and must keep passing.)
    hits = [_hit("alpha text", 31.960842, "a" * 64),
            _hit("zulu text", 31.960842 + 1e-8, "z" * 64)]
    _scripted(monkeypatch, hits)
    got = RET.retrieve_set(cast(Any, None), "q", k=2)
    assert [h["artifact_cache_key"] for h in got] == ["z" * 64, "a" * 64]
