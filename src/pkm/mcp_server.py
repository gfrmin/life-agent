"""Read-only MCP server for pkm — the query surface (SPEC §17).

Dormant by design: the live server was torn down (an operational call — a
leaked process — not an architecture verdict). MCP remains the endorsed
seam (PRINCIPLES.md §5); this module is the ready-to-revive surface and
returns to service when the spine decision forces it.

Exposes two tools over stdio: ``search`` (§17.2, ranked KWIC snippets) and
``extract`` (§17.7, one chunk's full text plus neighbours), both wrapping
the FTS retrieval layer. Optional tool-call audit logging (§17.8) is
enabled via ``set_tool_log`` / ``pkm serve --tool-log``. Stdout carries the
MCP JSON-RPC protocol; all logging goes to stderr / the JSONL log file.
Do NOT add print() calls here.

Usage (started by Claude Code via settings.json mcpServers entry):

    pkm --config /path/to/config.yaml serve
"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path

import duckdb
from mcp.server.fastmcp import FastMCP

from pkm.catalogue import catalogue_path
from pkm.retrieval import search as _search

log = logging.getLogger(__name__)
mcp = FastMCP("pkm-memory")

# Set once at `pkm serve` startup (in cli.py) after --config is parsed.
# The tool closures read this stash so the flag actually reaches queries.
_ROOT: Path | None = None

# SPEC §17.8: optional tool-call audit log path, set once at `pkm serve`
# startup via `--tool-log`. None (the default) means "don't log".
_TOOL_LOG_PATH: Path | None = None

SNIPPET_CHARS = 300
_HALF = SNIPPET_CHARS // 2
# Approximate FTS tokenization — adequate for locating a centre token;
# not guaranteed identical to DuckDB's \p{L}\p{N} Unicode class.
_TOKEN_RE = re.compile(r"\W+", re.UNICODE)

# SPEC §17.7: neighbours are clamped to this closed interval, never rejected.
_MIN_NEIGHBORS = 0
_MAX_NEIGHBORS = 3


def set_root(root: Path | None) -> None:
    global _ROOT
    _ROOT = root


def set_tool_log(path: Path | None) -> None:
    """Enable (or disable, with ``None``) §17.8 tool-call audit logging.

    Stashed at module scope, mirroring ``set_root``: `_cmd_serve` calls this
    once at startup after parsing ``--tool-log``, and the tool closures read
    the stash at call time.
    """
    global _TOOL_LOG_PATH
    _TOOL_LOG_PATH = path


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _log_tool_call(
    ts: str,
    tool: str,
    args: dict[str, object],
    results: list[dict[str, object]],
    *,
    error: str | None = None,
) -> None:
    """Append one §17.8 audit line, fail-open.

    A write failure (missing directory, disk full, permissions) is caught,
    logged once at WARNING, and otherwise ignored — this must never be the
    reason a ``search`` or ``extract`` call raises into the MCP transport.
    """
    if _TOOL_LOG_PATH is None:
        return
    entry: dict[str, object] = {
        "ts": ts,
        "tool": tool,
        "args": args,
        "n_results": len(results),
        "results": results,
    }
    if error is not None:
        entry["error"] = error
    try:
        with _TOOL_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as exc:
        log.warning(
            "tool-log write failed: %s",
            exc,
            extra={
                "event": "tool_log_write_failed",
                "path": str(_TOOL_LOG_PATH),
                "error": str(exc),
            },
        )


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
    ts = _now_iso()
    args: dict[str, object] = {"query": query, "k": k}

    if _ROOT is None:
        error = "server not initialised — _ROOT not set; restart pkm serve"
        _log_tool_call(ts, "search", args, [], error=error)
        return [{"error": error}]

    db_path = catalogue_path(_ROOT)
    try:
        conn = duckdb.connect(str(db_path), read_only=True)
    except duckdb.IOException as exc:
        log.warning("catalogue locked: %s", exc)
        error = "corpus locked by active extraction; retry shortly"
        _log_tool_call(ts, "search", args, [], error=error)
        return [{"error": error}]

    try:
        results = _search(conn, query, k=k)
    finally:
        conn.close()

    payload: list[dict[str, object]] = [
        {
            "chunk_id": r.chunk_id,
            "chunk_text": _kwic_snippet(r.chunk_text, query),
            "score": r.score,
            "source_path": r.source_path,
            "source_origin": r.source_origin,
            "artifact_cache_key": r.artifact_cache_key,
        }
        for r in results
    ]
    log_results: list[dict[str, object]] = [
        {
            "chunk_id": r.chunk_id,
            "artifact_cache_key": r.artifact_cache_key,
            "source_path": r.source_path,
            "score": r.score,
            "snippet_shown": row["chunk_text"],
            "chunk_text_full": r.chunk_text,
        }
        for r, row in zip(results, payload, strict=True)
    ]
    _log_tool_call(ts, "search", args, log_results)
    return payload


@mcp.tool()
def extract(chunk_id: int, neighbors: int = 1) -> dict[str, object]:
    """Recover one identified chunk's full text plus its immediate context.

    Complements ``search``: pass a ``chunk_id`` from a prior search result
    (or a stored citation) to get the chunk's full, untruncated text plus up
    to ``neighbors`` chunks on each side within the same artifact (clamped
    to [0, 3]). Unlike ``search``, this does NOT apply the SPEC §15.4
    path-currency filter — a chunk_id is a concrete pointer the caller
    already holds, a stronger signal than currency.

    Returns a single ``{"error": ...}`` dict (never a raised exception) for
    an unknown chunk_id or a retryable locked-catalogue condition.
    """
    ts = _now_iso()
    args: dict[str, object] = {"chunk_id": chunk_id, "neighbors": neighbors}
    clamped = max(_MIN_NEIGHBORS, min(_MAX_NEIGHBORS, neighbors))

    if _ROOT is None:
        error = "server not initialised — _ROOT not set; restart pkm serve"
        _log_tool_call(ts, "extract", args, [], error=error)
        return {"error": error}

    db_path = catalogue_path(_ROOT)
    try:
        conn = duckdb.connect(str(db_path), read_only=True)
    except duckdb.IOException as exc:
        log.warning("catalogue locked: %s", exc)
        error = "corpus locked by active extraction; retry shortly"
        _log_tool_call(ts, "extract", args, [], error=error)
        return {"error": error}

    try:
        # No §15.4 path-currency join here, by design (SPEC §17.7): a
        # chunk_id is a concrete pointer, resolved regardless of whether its
        # source has since been superseded at the same declared path.
        row = conn.execute(
            """
            SELECT ac.artifact_cache_key, ac.chunk_index, ac.chunk_text,
                   ac.source_origin, s.current_path
            FROM artifact_chunks ac
            JOIN artifacts a ON ac.artifact_cache_key = a.cache_key
            JOIN sources s ON a.input_hash = s.source_id
            WHERE ac.chunk_id = ?
            """,
            [chunk_id],
        ).fetchone()

        if row is None:
            error = f"unknown chunk_id: {chunk_id}"
            _log_tool_call(ts, "extract", args, [], error=error)
            return {"error": error}

        artifact_cache_key = str(row[0])
        chunk_index = int(row[1])
        chunk_text = str(row[2])
        source_origin = row[3]
        source_path = str(row[4])

        neighbor_rows = conn.execute(
            """
            SELECT chunk_index, chunk_text, chunk_id
            FROM artifact_chunks
            WHERE artifact_cache_key = ?
              AND chunk_index BETWEEN ? AND ?
              AND chunk_index != ?
            ORDER BY chunk_index ASC
            """,
            [
                artifact_cache_key,
                chunk_index - clamped,
                chunk_index + clamped,
                chunk_index,
            ],
        ).fetchall()
    except duckdb.Error as exc:
        # Mid-query failure (the connect-time lock case is handled above):
        # map to the same bare {"error": ...} convention rather than letting
        # the exception propagate through FastMCP, and still emit the §17.8
        # audit line — the trail records that the call happened and failed.
        log.warning(
            "extract query failed: %s",
            exc,
            extra={
                "event": "extract_query_failed",
                "chunk_id": chunk_id,
                "error": str(exc),
            },
        )
        error = f"extract query failed ({type(exc).__name__}): {exc}"
        _log_tool_call(ts, "extract", args, [], error=error)
        return {"error": error}
    finally:
        conn.close()

    neighbors_payload = [
        {"chunk_index": int(idx), "chunk_text": str(text)} for idx, text, _cid in neighbor_rows
    ]

    log_results: list[dict[str, object]] = [
        {
            "chunk_id": chunk_id,
            "artifact_cache_key": artifact_cache_key,
            "source_path": source_path,
            "score": None,
            "snippet_shown": None,
            "chunk_text_full": chunk_text,
        }
    ]
    log_results.extend(
        {
            "chunk_id": int(cid),
            "artifact_cache_key": artifact_cache_key,
            "source_path": source_path,
            "score": None,
            "snippet_shown": None,
            "chunk_text_full": str(text),
        }
        for _idx, text, cid in neighbor_rows
    )
    _log_tool_call(ts, "extract", args, log_results)

    return {
        "chunk_id": chunk_id,
        "artifact_cache_key": artifact_cache_key,
        "chunk_index": chunk_index,
        "chunk_text": chunk_text,
        "neighbors": neighbors_payload,
        "source_path": source_path,
        "source_origin": source_origin,
    }
