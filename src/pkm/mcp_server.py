"""Read-only MCP server for pkm — the query surface (SPEC §17).

Exposes a single ``search`` tool over stdio that wraps the FTS retrieval
layer.  Stdout carries the MCP JSON-RPC protocol; all logging goes to
stderr / the JSONL log file.  Do NOT add print() calls here.

Usage (started by Claude Code via settings.json mcpServers entry):

    pkm --config /path/to/config.yaml serve
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import duckdb
from mcp.server.fastmcp import FastMCP

from pkm.catalogue import catalogue_path
from pkm.retrieval import search as _search

log = logging.getLogger(__name__)
mcp = FastMCP("pkm-memory")

# Set once at `pkm serve` startup (in cli.py) after --config is parsed.
# The tool closure reads this stash so the flag actually reaches queries.
_ROOT: Path | None = None

SNIPPET_CHARS = 300
_HALF = SNIPPET_CHARS // 2
# Approximate FTS tokenization — adequate for locating a centre token;
# not guaranteed identical to DuckDB's \p{L}\p{N} Unicode class.
_TOKEN_RE = re.compile(r"\W+", re.UNICODE)


def set_root(root: Path | None) -> None:
    global _ROOT
    _ROOT = root


def _kwic_snippet(text: str, query: str) -> str:
    """Return a ~300-char window centred on the first query token in text.

    Falls back to head-truncation if no token is found (defensive).
    Centres on first matched token; the answer value may fall outside the
    window if it sits far from the label in the same chunk.
    """
    tokens = [t for t in _TOKEN_RE.split(query) if t]
    lo = len(text)
    for tok in tokens:
        m = re.search(re.escape(tok), text, re.IGNORECASE)
        if m:
            lo = min(lo, m.start())  # offset into original text — safe to slice
    if lo == len(text):
        # Defensive fallback: no token found
        return text[:SNIPPET_CHARS] + ("…" if len(text) > SNIPPET_CHARS else "")
    start = max(0, lo - _HALF)
    end = min(len(text), lo + _HALF)
    snippet = text[start:end]
    if start > 0:
        snippet = "…" + snippet
    if end < len(text):
        snippet = snippet + "…"
    return snippet


@mcp.tool()
def search(query: str, k: int = 10) -> list[dict[str, object]]:
    """Search the personal knowledge corpus by keyword (FTS, Unicode/Hebrew-aware).

    Returns up to k matching chunks, each with a keyword-in-context snippet
    (≤~300 chars centred on the first matched token) and provenance, ranked by
    BM25 relevance.  Does not synthesise an answer — the caller composes a
    cited response from the returned chunks.

    On a retryable failure (catalogue locked by an active extraction) returns a
    single-element list with an ``"error"`` key; the caller should retry after
    the extraction completes.
    """
    if _ROOT is None:
        return [{"error": "server not initialised — _ROOT not set; restart pkm serve"}]

    db_path = catalogue_path(_ROOT)
    try:
        conn = duckdb.connect(str(db_path), read_only=True)
    except duckdb.IOException as exc:
        log.warning("catalogue locked: %s", exc)
        return [{"error": "corpus locked by active extraction; retry shortly"}]

    try:
        results = _search(conn, query, k=k)
    finally:
        conn.close()

    return [
        {
            "chunk_text": _kwic_snippet(r.chunk_text, query),
            "score": r.score,
            "source_path": r.source_path,
            "source_origin": r.source_origin,
            "artifact_cache_key": r.artifact_cache_key,
        }
        for r in results
    ]
