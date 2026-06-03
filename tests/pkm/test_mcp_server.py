"""Tests for ``pkm.mcp_server`` — the read-only MCP query surface (SPEC §17).

Stage-A hermetic: seeded ``artifact_chunks`` in ``migrated_root``.
No live corpus is touched.
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import duckdb

from pkm.catalogue import catalogue_path, open_catalogue
from pkm.retrieval import build_fts_index

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HEBREW_CHUNK = "תעודת זהות 123456789"
_ENGLISH_CHUNK = "This is an English sentence about booking confirmations."


def _seed(root: Path) -> None:
    with open_catalogue(root) as conn:
        conn.execute(
            "INSERT INTO sources (source_id, current_path, first_seen, "
            "last_seen, size_bytes) VALUES (?, ?, current_timestamp, "
            "current_timestamp, 0)",
            ["a" * 64, "/fake/path/doc.txt"],
        )
        conn.execute(
            """
            INSERT INTO artifacts
                (cache_key, input_hash, producer_name, producer_version,
                 producer_config_hash, status, produced_at, content_type,
                 content_path)
            VALUES (?, ?, 'email', '1', 'fakehash', 'success',
                    current_timestamp, 'text/plain', '/dev/null')
            """,
            ["b" * 64, "a" * 64],
        )
        conn.executemany(
            "INSERT INTO artifact_chunks "
            "(artifact_cache_key, chunk_index, chunk_text, source_origin, chunk_id) "
            "VALUES (?, ?, ?, 'email', nextval('seq_chunk_id'))",
            [
                ("b" * 64, 0, _HEBREW_CHUNK),
                ("b" * 64, 1, _ENGLISH_CHUNK),
            ],
        )
        build_fts_index(conn)


# ---------------------------------------------------------------------------
# Import guard
# ---------------------------------------------------------------------------


def test_module_importable() -> None:
    import pkm.mcp_server  # noqa: F401


# ---------------------------------------------------------------------------
# Dict shape and k contract
# ---------------------------------------------------------------------------


def test_search_returns_expected_shape(migrated_root: Path) -> None:
    """search() returns dicts with all five documented fields."""
    import pkm.mcp_server as ms

    _seed(migrated_root)
    ms.set_root(migrated_root)
    try:
        results = ms.search("booking")
    finally:
        ms.set_root(None)  # type: ignore[arg-type]

    assert len(results) >= 1
    required = {
        "chunk_text", "score", "source_path", "source_origin", "artifact_cache_key",
    }
    for row in results:
        assert required <= row.keys(), f"missing keys: {required - row.keys()}"


def test_search_honours_k(migrated_root: Path) -> None:
    """k=1 caps results at 1 even when more chunks match."""
    import pkm.mcp_server as ms

    _seed(migrated_root)
    ms.set_root(migrated_root)
    try:
        all_results = ms.search("the", k=100)
        limited = ms.search("the", k=1)
    finally:
        ms.set_root(None)  # type: ignore[arg-type]

    assert len(limited) <= 1
    assert len(all_results) >= len(limited)


def test_search_empty_returns_list(migrated_root: Path) -> None:
    """A query that matches nothing returns [], not an error."""
    import pkm.mcp_server as ms

    _seed(migrated_root)
    ms.set_root(migrated_root)
    try:
        results = ms.search("zzznomatch_xyzzy_9876")
    finally:
        ms.set_root(None)  # type: ignore[arg-type]

    assert results == []


# ---------------------------------------------------------------------------
# Hebrew FTS end-to-end
# ---------------------------------------------------------------------------


def test_search_hebrew_returns_correct_source(migrated_root: Path) -> None:
    """A Hebrew query returns the seeded chunk with the correct source_path.

    Exercises the Unicode-aware tokeniser path through the MCP tool layer.
    """
    import pkm.mcp_server as ms

    _seed(migrated_root)
    ms.set_root(migrated_root)
    try:
        results = ms.search("תעודת זהות", k=5)
    finally:
        ms.set_root(None)  # type: ignore[arg-type]

    assert len(results) >= 1
    assert results[0]["source_path"] == "/fake/path/doc.txt"
    assert "תעודת" in results[0]["chunk_text"]


# ---------------------------------------------------------------------------
# Config flow: set_root bridges --config into the tool closure
# ---------------------------------------------------------------------------


def test_set_root_is_forwarded_to_duckdb(migrated_root: Path) -> None:
    """After set_root(path), the tool opens catalogue_path(path) — not a default."""
    import pkm.mcp_server as ms

    expected_db = str(catalogue_path(migrated_root))
    ms.set_root(migrated_root)
    try:
        with patch("duckdb.connect") as mock_connect:
            fake_conn = MagicMock()
            fake_conn.execute.return_value.fetchall.return_value = []
            fake_conn.execute.return_value.description = []
            mock_connect.return_value = fake_conn

            with contextlib.suppress(Exception):
                ms.search("test")

            assert mock_connect.call_count >= 1
            actual_path = mock_connect.call_args[0][0]
            kwargs = mock_connect.call_args[1]
            assert actual_path == expected_db
            assert kwargs.get("read_only") is True
    finally:
        ms.set_root(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Read-only connection + lock-conflict retryable error
# ---------------------------------------------------------------------------


def test_connect_uses_read_only(migrated_root: Path) -> None:
    """duckdb.connect is always called with read_only=True."""
    import pkm.mcp_server as ms

    ms.set_root(migrated_root)
    try:
        with patch("duckdb.connect") as mock_connect:
            fake_conn = MagicMock()
            fake_conn.execute.return_value.fetchall.return_value = []
            fake_conn.execute.return_value.description = []
            mock_connect.return_value = fake_conn

            with contextlib.suppress(Exception):
                ms.search("test")

            assert mock_connect.call_count >= 1
            kwargs = mock_connect.call_args[1]
            assert kwargs.get("read_only") is True
    finally:
        ms.set_root(None)  # type: ignore[arg-type]


def test_lock_conflict_returns_retryable_error(migrated_root: Path) -> None:
    """When duckdb.connect raises IOException (write lock held), the tool
    returns a structured error dict rather than propagating the exception."""
    import pkm.mcp_server as ms

    ms.set_root(migrated_root)
    try:
        with patch(
            "duckdb.connect",
            side_effect=duckdb.IOException("Could not set lock"),
        ):
            results = ms.search("anything")
    finally:
        ms.set_root(None)  # type: ignore[arg-type]

    assert len(results) == 1
    assert "error" in results[0]
    error_msg = results[0]["error"].lower()
    assert "lock" in error_msg


def test_unset_root_returns_error() -> None:
    """If _ROOT was never set (not initialised), the tool returns an error dict."""
    import pkm.mcp_server as ms

    original = ms._ROOT
    ms._ROOT = None
    try:
        results = ms.search("test")
    finally:
        ms._ROOT = original

    assert len(results) == 1
    assert "error" in results[0]


# ---------------------------------------------------------------------------
# KWIC snippet correctness
# ---------------------------------------------------------------------------


def test_kwic_match_past_char_300(migrated_root: Path) -> None:
    """The matched term is present in the snippet even when it sits past char 300.

    This is the load-bearing test: it fails under head-truncation and passes
    under KWIC.
    """
    import pkm.mcp_server as ms

    term = "NEEDLE"
    # Space-separated words so FTS tokenizes cleanly; concatenating directly
    # with "x"*400 would make one long token "xxx...needle" that never matches.
    preamble = "word " * 80  # ~400 chars, term starts at char ~400
    with open_catalogue(migrated_root) as conn:
        conn.execute(
            "INSERT INTO sources (source_id, current_path, first_seen, "
            "last_seen, size_bytes) VALUES (?, ?, current_timestamp, "
            "current_timestamp, 0)",
            ["c" * 64, "/fake/path/needle.txt"],
        )
        conn.execute(
            """
            INSERT INTO artifacts
                (cache_key, input_hash, producer_name, producer_version,
                 producer_config_hash, status, produced_at, content_type,
                 content_path)
            VALUES (?, ?, 'email', '1', 'fakehash2', 'success',
                    current_timestamp, 'text/plain', '/dev/null')
            """,
            ["d" * 64, "c" * 64],
        )
        conn.execute(
            "INSERT INTO artifact_chunks "
            "(artifact_cache_key, chunk_index, chunk_text, source_origin, chunk_id) "
            "VALUES (?, ?, ?, 'test', nextval('seq_chunk_id'))",
            ("d" * 64, 0, preamble + term + " found here"),
        )
        build_fts_index(conn)

    ms.set_root(migrated_root)
    try:
        results = ms.search(term.lower(), k=5)
    finally:
        ms.set_root(None)  # type: ignore[arg-type]

    hits = [r for r in results if r["source_path"] == "/fake/path/needle.txt"]
    assert len(hits) >= 1, "expected a hit for the needle chunk"
    snippet = hits[0]["chunk_text"]
    assert term.upper() in snippet or term.lower() in snippet


def test_kwic_email_body_not_swallowed_by_headers(migrated_root: Path) -> None:
    """A body term is present in the snippet even when email headers precede it.

    Email chunks have From/To/Date/Subject headers (~250 chars) before the body.
    Head-truncation returns the envelope; KWIC centres on the body term.
    """
    import pkm.mcp_server as ms

    headers = (
        "From: sender@example.com\n"
        "To: recipient@example.com\n"
        "Date: Thu, 01 Jan 2026 12:00:00 +0000\n"
        "Subject: Some Long Subject Line That Fills Up Space\n"
        "Message-ID: <abc123@example.com>\n\n"
    )  # ~200 chars of headers
    body_term = "BODYCONTENT"
    # Space before body_term ensures FTS tokenizes it as its own token.
    chunk = headers + "other words here " * 4 + body_term + " rest of body"

    with open_catalogue(migrated_root) as conn:
        conn.execute(
            "INSERT INTO sources (source_id, current_path, first_seen, "
            "last_seen, size_bytes) VALUES (?, ?, current_timestamp, "
            "current_timestamp, 0)",
            ["e" * 64, "/fake/path/email.eml"],
        )
        conn.execute(
            """
            INSERT INTO artifacts
                (cache_key, input_hash, producer_name, producer_version,
                 producer_config_hash, status, produced_at, content_type,
                 content_path)
            VALUES (?, ?, 'email', '1', 'fakehash3', 'success',
                    current_timestamp, 'text/plain', '/dev/null')
            """,
            ["f" * 64, "e" * 64],
        )
        conn.execute(
            "INSERT INTO artifact_chunks "
            "(artifact_cache_key, chunk_index, chunk_text, source_origin, chunk_id) "
            "VALUES (?, ?, ?, 'email', nextval('seq_chunk_id'))",
            ("f" * 64, 0, chunk),
        )
        build_fts_index(conn)

    ms.set_root(migrated_root)
    try:
        results = ms.search(body_term.lower(), k=5)
    finally:
        ms.set_root(None)  # type: ignore[arg-type]

    hits = [r for r in results if r["source_path"] == "/fake/path/email.eml"]
    assert len(hits) >= 1, "expected a hit for the email chunk"
    assert body_term in hits[0]["chunk_text"]


def test_kwic_snippet_length_bound(migrated_root: Path) -> None:
    """All returned chunk_text values are within the SNIPPET_CHARS bound."""
    import pkm.mcp_server as ms

    _seed(migrated_root)
    ms.set_root(migrated_root)
    try:
        results = ms.search("booking", k=10)
    finally:
        ms.set_root(None)  # type: ignore[arg-type]

    max_len = ms.SNIPPET_CHARS + 4  # 300 + up to 2x "..." (ellipsis chars)
    for row in results:
        assert len(row["chunk_text"]) <= max_len, (
            f"snippet too long: {len(row['chunk_text'])} > {max_len}"
        )


def test_kwic_short_chunk_unmodified(migrated_root: Path) -> None:
    """A chunk shorter than SNIPPET_CHARS is returned verbatim — no ellipsis."""
    import pkm.mcp_server as ms

    short_text = "Short chunk with booking info."
    with open_catalogue(migrated_root) as conn:
        conn.execute(
            "INSERT INTO sources (source_id, current_path, first_seen, "
            "last_seen, size_bytes) VALUES (?, ?, current_timestamp, "
            "current_timestamp, 0)",
            ["g" * 64, "/fake/path/short.txt"],
        )
        conn.execute(
            """
            INSERT INTO artifacts
                (cache_key, input_hash, producer_name, producer_version,
                 producer_config_hash, status, produced_at, content_type,
                 content_path)
            VALUES (?, ?, 'email', '1', 'fakehash4', 'success',
                    current_timestamp, 'text/plain', '/dev/null')
            """,
            ["h" * 64, "g" * 64],
        )
        conn.execute(
            "INSERT INTO artifact_chunks "
            "(artifact_cache_key, chunk_index, chunk_text, source_origin, chunk_id) "
            "VALUES (?, ?, ?, 'test', nextval('seq_chunk_id'))",
            ("h" * 64, 0, short_text),
        )
        build_fts_index(conn)

    ms.set_root(migrated_root)
    try:
        results = ms.search("booking", k=10)
    finally:
        ms.set_root(None)  # type: ignore[arg-type]

    hits = [r for r in results if r["source_path"] == "/fake/path/short.txt"]
    assert len(hits) >= 1
    assert hits[0]["chunk_text"] == short_text
    assert not hits[0]["chunk_text"].startswith("…")
    assert not hits[0]["chunk_text"].endswith("…")


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------


def test_search_tool_registered() -> None:
    """The FastMCP server has 'search' registered as a tool."""
    import pkm.mcp_server as ms

    tool_names = [t.name for t in ms.mcp._tool_manager.list_tools()]
    assert "search" in tool_names
