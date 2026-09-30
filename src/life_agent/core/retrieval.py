"""The corpus-retrieval seam — FTS over the live pkm catalogue, package-side.

Extracted from ``scripts/ask.py`` so the answer-brain capability bridge
(``life_agent.bridge.server`` — move-3-design) can reuse the EXACT retrieval a live
ask performs without importing from ``scripts/`` (the ``src↛scripts`` boundary
:mod:`life_agent.core.matching` also keeps): there is exactly ONE retrieval
implementation (the move-3 §6 "no second read" obligation).

Query EXPANSION lives in :mod:`life_agent.core.expansion`. Both this seam and the bridge
take the already-built query as input — expansion is the driver's policy, the same cut
``/extract`` makes for covariates.
"""
from __future__ import annotations

from typing import Any

import duckdb

from life_agent.core import config as CFG


def connect() -> duckdb.DuckDBPyConnection:
    """Open the live catalogue read-only (so a running extraction never blocks us)
    and load FTS."""
    root = CFG.pkm_root()
    if root is None:
        raise FileNotFoundError(f"unresolvable pkm root (config: {CFG.PKM_CONFIG})")
    conn = duckdb.connect(str(root / "catalogue.duckdb"), read_only=True)
    conn.execute("INSTALL fts; LOAD fts;")
    return conn


def build_query(question: str, terms: str) -> str:
    """Pure: combine the raw question with expansion terms into one disjunctive BM25
    query. The original words are ALWAYS retained, so expansion can only *add* recall —
    a question that already hit on a rare literal term keeps its hit. Empty terms
    (expansion failed/disabled) leaves the raw-question search unchanged."""
    return f"{question} {terms}".strip() if terms else question


#: The widest FTS window an exclusion may grow the over-fetch to before it settles for fewer
#: than ``k`` hits.
_EXCLUDE_WINDOW_MAX = 16384


def retrieve_set(conn: duckdb.DuckDBPyConnection, question: str, k: int, *,
                 exclude: frozenset[str] = frozenset()) -> list[dict[str, Any]]:
    """FTS the given query over the whole corpus; dedupe by chunk text keeping the best
    score; return the top-k as plain dicts — the cacheable retrieval-set content, carrying
    each hit's artifact cache key for lineage. No snapshot filter.

    Ordered by a DECLARED total order — ``(-round(score, 9), artifact_cache_key, chunk_text)``
    — because pkm's FTS is nondeterministic in TWO layers (M0.5): it returns tied BM25 scores in
    a varying order, and the scores themselves differ by 1-2 ulp between identical calls (DuckDB
    sums term contributions in a parallelism-dependent order). Where either straddled the top-k
    cut, the retrieved *set* changed between two runs of the same code on the same corpus, and
    with it every §18.9 derivation keyed on it.

    ``exclude`` names artifacts whose hits are never returned (the withheld-source eval: the
    documents attesting an answer are taken out of retrieval). They are dropped from the
    ordered window before the dedupe, and the window widens until ``k`` hits survive or the
    index has nothing more; with none excluded there is one search, exactly as without the
    parameter."""
    from pkm.retrieval import SearchResult, search

    # Since r08 (SPEC 0.18.2) pkm's SQL cuts this same declared order, so the over-fetch
    # window is the declared prefix of the corpus rather than an engine sample of a tie
    # block (§6.13); the sort below is defence in depth, idempotent over an ordered window.
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
    window = k * 4
    while True:
        ordered = sorted(search(conn, question, k=window),
                         key=lambda h: (-round(h.score, 9), h.artifact_cache_key, h.chunk_text))
        best: dict[str, SearchResult] = {}
        for h in ordered:
            if h.artifact_cache_key not in exclude:
                best.setdefault(h.chunk_text, h)
        top = list(best.values())[:k]
        if (not exclude or len(top) >= k or len(ordered) < window
                or window >= _EXCLUDE_WINDOW_MAX):
            break
        window *= 2
    return [{"artifact_cache_key": h.artifact_cache_key, "chunk_text": h.chunk_text,
             "score": h.score, "origin": h.source_path} for h in top]
