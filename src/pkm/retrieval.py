"""FTS keyword search substrate (SPEC v0.1.11 Step 3).

Unicode-aware configuration is mandatory for Hebrew (and any non-ASCII
language). DuckDB FTS's default ``ignore`` regex is ``'(\\.|[^a-z])+'``,
which treats every non-ASCII character as a separator. Hebrew (U+05D0-U+05EA)
contains no [a-z] characters, so a chunk like "תעודת זהות 123456789" would
tokenise to *zero tokens*: the index builds silently, queries return empty, and
no diagnostic is produced.

The override ``ignore='[^\\p{L}\\p{N}]+'`` uses RE2 Unicode property classes
(DuckDB's regex engine is RE2), splitting on anything that is not a Unicode
letter or digit. This means Hebrew, Arabic, CJK, and any other script are
indexed correctly alongside English.

Stemmer is disabled (``stemmer='none'``): no stemmer handles Hebrew morphology.
Stopwords are disabled (``stopwords='none'``): English stopwords would not
apply to Hebrew text.
``strip_accents=0``: niqud-safe; avoids stripping Hebrew vowel diacritics.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import duckdb

logger = logging.getLogger(__name__)

_FTS_INPUT_ID = "chunk_id"
_FTS_CONTENT_FIELD = "chunk_text"
_FTS_TABLE = "artifact_chunks"

# Unicode-aware ignore pattern. Must be a RE2 pattern.
# '[^\\p{L}\\p{N}]+' means: split on any run of characters that are
# neither a Unicode letter (\\p{L}) nor a Unicode digit (\\p{N}).
_FTS_IGNORE = "[^\\p{L}\\p{N}]+"

# SPEC §15.4 source-path currency: among sources sharing a declared
# current_path, exactly one is path-current — the most recent by
# (last_seen, first_seen, source_id) descending (deterministic tiebreaks,
# mirroring §18.10's most-recent-first ordering). Retrieval admits chunks
# only from path-current sources; superseded path-versions stay catalogued.
_PATH_CURRENT_CTE = """
    path_current AS (
        SELECT source_id FROM (
            SELECT
                source_id,
                row_number() OVER (
                    PARTITION BY current_path
                    ORDER BY last_seen DESC, first_seen DESC, source_id DESC
                ) AS rn
            FROM sources
        )
        WHERE rn = 1
    )
"""


@dataclass(frozen=True)
class SearchResult:
    chunk_text: str
    score: float
    source_path: str
    source_origin: str | None
    artifact_cache_key: str
    # SPEC v0.17.0 §17.2: the artifact_chunks surrogate key (§15.1), surfaced
    # so a caller can address this result via the `extract` MCP tool (§17.7).
    # Defaulted (not a new positional-required field) to keep existing
    # keyword-arg construction sites valid.
    chunk_id: int | None = None


def build_fts_index(conn: duckdb.DuckDBPyConnection) -> None:
    """Create or recreate the FTS index over ``artifact_chunks``.

    Idempotent: drops the existing index if present before rebuilding.
    Call after bulk writes (backfill, large extract runs) — incremental
    updates require a full rebuild because DuckDB FTS has no partial
    update support.
    """
    conn.execute("INSTALL fts; LOAD fts;")
    conn.execute(
        f"""
        PRAGMA create_fts_index(
            '{_FTS_TABLE}',
            '{_FTS_INPUT_ID}',
            '{_FTS_CONTENT_FIELD}',
            stemmer='none',
            ignore='{_FTS_IGNORE}',
            strip_accents=0,
            overwrite=1
        )
        """
    )
    logger.debug(
        "FTS index rebuilt on %s",
        _FTS_TABLE,
        extra={"event": "fts_index_rebuilt", "table": _FTS_TABLE},
    )


def count_path_superseded_chunks(conn: duckdb.DuckDBPyConnection) -> int:
    """How many chunks the §15.4 currency filter excludes from retrieval.

    Read-only; SPEC §14.6 (no hidden state): callers can surface the
    narrowing instead of having the retrievable corpus shrink silently.
    """
    row = conn.execute(
        f"""
        WITH {_PATH_CURRENT_CTE}
        SELECT count(*)
        FROM {_FTS_TABLE} ac
        JOIN artifacts a ON ac.artifact_cache_key = a.cache_key
        JOIN sources s ON a.input_hash = s.source_id
        WHERE s.source_id NOT IN (SELECT source_id FROM path_current)
        """
    ).fetchone()
    return int(row[0]) if row is not None else 0


def search(
    conn: duckdb.DuckDBPyConnection,
    query: str,
    k: int = 20,
) -> list[SearchResult]:
    """Run a FTS query and return ranked hits with provenance.

    The FTS index must already exist (call ``build_fts_index`` once
    after populating ``artifact_chunks``). If the index does not exist,
    returns an empty list after logging a warning.

    Join path: ``artifact_chunks`` → ``artifacts`` (on
    ``artifact_cache_key = cache_key``) → ``sources`` (on
    ``input_hash = source_id``) to resolve the original file path.

    Source-path currency (SPEC §15.4): only chunks from the path-current
    version of each declared path are returned; superseded path-versions
    remain catalogued but never surface here.

    Args:
        conn: Open DuckDB connection.
        query: The search query string.
        k: Maximum number of results to return.

    Returns:
        List of ``SearchResult`` ordered by descending relevance score.
        Empty if no matches or index absent.
    """
    conn.execute("INSTALL fts; LOAD fts;")
    try:
        # Compute BM25 scores on artifact_chunks alone (no JOINs in the
        # match_bm25 call — DuckDB FTS uses scalar subqueries internally
        # that fail when the outer query has JOIN-expanded rows).
        rows = conn.execute(
            f"""
            WITH {_PATH_CURRENT_CTE}
            SELECT
                scored.chunk_text,
                scored.score,
                s.current_path,
                scored.source_origin,
                scored.artifact_cache_key,
                scored.{_FTS_INPUT_ID}
            FROM (
                SELECT
                    {_FTS_INPUT_ID},
                    artifact_cache_key,
                    {_FTS_CONTENT_FIELD} AS chunk_text,
                    source_origin,
                    fts_main_{_FTS_TABLE}.match_bm25(
                        {_FTS_INPUT_ID},
                        ?,
                        fields := '{_FTS_CONTENT_FIELD}'
                    ) AS score
                FROM {_FTS_TABLE}
            ) scored
            JOIN artifacts a ON scored.artifact_cache_key = a.cache_key
            JOIN sources s ON a.input_hash = s.source_id
            JOIN path_current pc ON s.source_id = pc.source_id
            WHERE scored.score IS NOT NULL
            ORDER BY scored.score DESC
            LIMIT ?
            """,
            [query, k],
        ).fetchall()
    except Exception as exc:
        logger.warning(
            "FTS search failed (index may not exist): %s",
            exc,
            extra={"event": "fts_search_failed", "query": query, "error": str(exc)},
        )
        return []

    return [
        SearchResult(
            chunk_text=row[0],
            score=float(row[1]),
            source_path=row[2],
            source_origin=row[3],
            artifact_cache_key=row[4],
            chunk_id=int(row[5]),
        )
        for row in rows
    ]
