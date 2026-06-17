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
    each hit's artifact cache key for lineage. No snapshot filter."""
    from pkm.retrieval import SearchResult, search

    best: dict[str, SearchResult] = {}
    for h in search(conn, question, k=k * 4):  # over-fetch, then dedupe down to k
        prev = best.get(h.chunk_text)
        if prev is None or h.score > prev.score:
            best[h.chunk_text] = h
    top = sorted(best.values(), key=lambda h: h.score, reverse=True)[:k]
    return [{"artifact_cache_key": h.artifact_cache_key, "chunk_text": h.chunk_text,
             "score": h.score, "origin": h.source_path} for h in top]
