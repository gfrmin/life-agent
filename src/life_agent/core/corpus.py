"""Corpus-state digest — the identity of "what retrieval can see".

``corpus_digest`` is the corpus half of the north-star equation
``answer = f(corpus_state, question)`` (PRINCIPLES §1): a single SHA-256 over the set of
chunked artifacts plus the chunk count, i.e. exactly the universe FTS retrieval ranks over.
It keys the cached ``life_agent.ask.retrieve`` stage (pkm SPEC §18.9): any change to what
retrieval can see produces a new digest and forces a fresh retrieval, while the synthesis
stage is keyed on the *retrieved set's content* — so a corpus change that does not alter
what a question retrieves still replays the cached answer (early cutoff).

Ask-stage artifacts themselves are never chunked (their content types are not in
``CHUNKABLE_CONTENT_TYPES``), so recording an answer cannot churn this digest.
"""
from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from pkm.hashing import canonical_json

if TYPE_CHECKING:
    import duckdb


def corpus_digest(conn: duckdb.DuckDBPyConnection) -> str:
    """SHA-256 hex of the canonical retrieval universe: the sorted distinct artifact cache
    keys present in ``artifact_chunks``, plus the total chunk count (so a re-chunk of the
    same artifacts still changes the digest). Read-only; milliseconds on a personal corpus."""
    keys = [
        r[0]
        for r in conn.execute(
            "SELECT DISTINCT artifact_cache_key FROM artifact_chunks ORDER BY artifact_cache_key"
        ).fetchall()
    ]
    (count,) = conn.execute("SELECT count(*) FROM artifact_chunks").fetchone()  # type: ignore[misc]
    payload = canonical_json({"artifacts": keys, "chunks": count})
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
