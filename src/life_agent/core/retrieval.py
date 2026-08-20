"""The corpus-retrieval seam — FTS over the live pkm catalogue, package-side.

Extracted from ``scripts/ask.py`` so the answer-brain capability bridge
(``life_agent.bridge.server`` — move-3-design) can reuse the EXACT retrieval a live
ask performs without importing from ``scripts/`` (the ``src↛scripts`` boundary
:mod:`life_agent.core.matching` also keeps). ``ask`` re-exports these names, so its
callers and tests are unchanged and there is exactly ONE retrieval implementation
(the move-3 §6 "no second read" obligation).

Query EXPANSION stays in ``scripts/ask.py`` (it is a cloud-model reformulation, entangled
with that script's caching). Both this seam and the bridge take the already-built query as
input — expansion is the driver's policy, the same cut ``/extract`` makes for covariates.
"""
from __future__ import annotations

from typing import Any

import duckdb


def build_query(question: str, terms: str) -> str:
    """Pure: combine the raw question with expansion terms into one disjunctive BM25
    query. The original words are ALWAYS retained, so expansion can only *add* recall —
    a question that already hit on a rare literal term keeps its hit. Empty terms
    (expansion failed/disabled) leaves the raw-question search unchanged."""
    return f"{question} {terms}".strip() if terms else question


def retrieve_set(conn: duckdb.DuckDBPyConnection, question: str, k: int) -> list[dict[str, Any]]:
    """FTS the given query over the whole corpus; dedupe by chunk text keeping the best
    score; return the top-k as plain dicts — the cacheable retrieval-set content, carrying
    each hit's artifact cache key for lineage. No snapshot filter.

    Ordered by a DECLARED total order — ``(-round(score, 9), artifact_cache_key, chunk_text)``
    — because pkm's FTS is nondeterministic in TWO layers (M0.5): it returns tied BM25 scores in
    a varying order, and the scores themselves differ by 1-2 ulp between identical calls (DuckDB
    sums term contributions in a parallelism-dependent order). Where either straddled the top-k
    cut, the retrieved *set* changed between two runs of the same code on the same corpus, and
    with it every §18.9 derivation keyed on it."""
    from pkm.retrieval import SearchResult, search

    # Over-fetch, ORDER, then dedupe: sorting first keeps the dedupe rule unchanged (the
    # best-scoring copy of a duplicated chunk survives, since the order is score-major) while
    # making its tie — identical text at an identical score in two documents, this corpus's
    # commonest shape — resolve by the declared key rather than by arrival order.
    #
    # The leading term is QUANTISED (R2): a key led by a quantity that is not reproducible to
    # the last bit cannot be a total order however good its tie-breakers. At BM25 magnitudes of
    # 10-40 the ninth decimal place discards ~1e-15 of engine noise — six orders of magnitude
    # below any score difference the corpus produces — so a near-tie becomes a declared tie,
    # resolved by the document key like every other. It resolves ties; it does not make them:
    # the tie census over the battery is unchanged at 88 questions and 742 tied hits.
    ordered = sorted(search(conn, question, k=k * 4),
                     key=lambda h: (-round(h.score, 9), h.artifact_cache_key, h.chunk_text))
    best: dict[str, SearchResult] = {}
    for h in ordered:
        best.setdefault(h.chunk_text, h)
    top = list(best.values())[:k]
    return [{"artifact_cache_key": h.artifact_cache_key, "chunk_text": h.chunk_text,
             "score": h.score, "origin": h.source_path} for h in top]
