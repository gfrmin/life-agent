"""Tests for the v0.17.0 pkm MCP surface additions (SPEC §17.2, §17.7, §17.8):

  - ``search`` result dicts gain ``chunk_id`` (§17.2), backed by a new
    ``SearchResult.chunk_id`` field (§15.1).
  - The new read-only ``extract`` tool (§17.7): full chunk text + clamped
    neighbours + provenance, no §15.4 path-currency filter, bare
    ``{"error": ...}`` on unknown chunk / locked catalogue.
  - Optional tool-call audit logging via ``mcp_server.set_tool_log`` /
    ``pkm serve --tool-log`` (§17.8): one JSONL line per call, fail-open.

Stage-A hermetic: seeded ``artifact_chunks`` in ``migrated_root``. No live
corpus is touched.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import patch

import duckdb
import pytest

from pkm.catalogue import open_catalogue
from pkm.retrieval import SearchResult, build_fts_index
from pkm.retrieval import search as pkm_search

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_artifact(
    root: Path,
    *,
    source_id: str,
    cache_key: str,
    path: str,
    texts: list[str],
    seen: str | None = None,
) -> list[int]:
    """Seed one source/artifact with ``texts`` as chunk_index 0..N-1.

    Returns the surrogate ``chunk_id`` values in ``chunk_index`` order (the
    server assigns them via ``nextval('seq_chunk_id')`` at insert time, so
    the caller cannot predict them up front). ``seen`` overrides
    first_seen/last_seen (default: now) — needed to control §15.4 path-
    currency ordering across two versions of the same declared path.
    """
    with open_catalogue(root) as conn:
        if seen is None:
            conn.execute(
                "INSERT INTO sources (source_id, current_path, first_seen, "
                "last_seen, size_bytes) VALUES (?, ?, current_timestamp, "
                "current_timestamp, 0)",
                [source_id, path],
            )
        else:
            conn.execute(
                "INSERT INTO sources (source_id, current_path, first_seen, "
                "last_seen, size_bytes) VALUES (?, ?, CAST(? AS TIMESTAMP), "
                "CAST(? AS TIMESTAMP), 0)",
                [source_id, path, seen, seen],
            )
        conn.execute(
            """
            INSERT INTO artifacts
                (cache_key, input_hash, producer_name, producer_version,
                 producer_config_hash, status, produced_at, content_type,
                 content_path)
            VALUES (?, ?, 'pandoc', '3.6', 'fakehash', 'success',
                    current_timestamp, 'text/plain', '/dev/null')
            """,
            [cache_key, source_id],
        )
        conn.executemany(
            "INSERT INTO artifact_chunks "
            "(artifact_cache_key, chunk_index, chunk_text, source_origin, chunk_id) "
            "VALUES (?, ?, ?, 'pandoc', nextval('seq_chunk_id'))",
            [(cache_key, i, text) for i, text in enumerate(texts)],
        )
        build_fts_index(conn)
        rows = conn.execute(
            "SELECT chunk_index, chunk_id FROM artifact_chunks "
            "WHERE artifact_cache_key = ? ORDER BY chunk_index",
            [cache_key],
        ).fetchall()
    ids_by_index = {int(idx): int(cid) for idx, cid in rows}
    return [ids_by_index[i] for i in range(len(texts))]


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


# ---------------------------------------------------------------------------
# §17.2 — chunk_id surfaced in search
# ---------------------------------------------------------------------------


def test_search_result_has_chunk_id_field(migrated_root: Path) -> None:
    """pkm.retrieval.search's SearchResult carries the surrogate chunk_id."""
    chunk_ids = _seed_artifact(
        migrated_root,
        source_id="a" * 64,
        cache_key="b" * 64,
        path="/fake/path/doc.txt",
        texts=["hello booking world"],
    )
    with open_catalogue(migrated_root) as conn:
        results = pkm_search(conn, "booking")
    assert len(results) == 1
    assert results[0].chunk_id == chunk_ids[0]


def test_search_result_chunk_id_defaults_to_none_backward_compat() -> None:
    """Existing keyword-constructed SearchResult callers keep working —
    the new field must default, not become a required positional."""
    r = SearchResult(
        chunk_text="x",
        score=1.0,
        source_path="/p",
        source_origin=None,
        artifact_cache_key="a" * 64,
    )
    assert r.chunk_id is None


def test_mcp_search_dict_includes_chunk_id(migrated_root: Path) -> None:
    """mcp_server.search's result dicts gain a chunk_id key (SPEC §17.2)."""
    import pkm.mcp_server as ms

    chunk_ids = _seed_artifact(
        migrated_root,
        source_id="a" * 64,
        cache_key="b" * 64,
        path="/fake/path/doc.txt",
        texts=["hello booking world"],
    )
    ms.set_root(migrated_root)
    try:
        results = ms.search("booking")
    finally:
        ms.set_root(None)  # type: ignore[arg-type]

    assert len(results) == 1
    assert results[0]["chunk_id"] == chunk_ids[0]


# ---------------------------------------------------------------------------
# §17.7 — the extract tool
# ---------------------------------------------------------------------------


def test_extract_returns_full_text_and_provenance(migrated_root: Path) -> None:
    import pkm.mcp_server as ms

    texts = [f"chunk number {i} full text" for i in range(6)]
    chunk_ids = _seed_artifact(
        migrated_root,
        source_id="a" * 64,
        cache_key="b" * 64,
        path="/fake/path/doc.txt",
        texts=texts,
    )
    ms.set_root(migrated_root)
    try:
        result = ms.extract(chunk_ids[3])  # default neighbors=1
    finally:
        ms.set_root(None)  # type: ignore[arg-type]

    assert result["chunk_id"] == chunk_ids[3]
    assert result["artifact_cache_key"] == "b" * 64
    assert result["chunk_index"] == 3
    assert result["chunk_text"] == texts[3]
    assert result["source_path"] == "/fake/path/doc.txt"
    assert result["source_origin"] == "pandoc"

    neighbors = result["neighbors"]
    assert isinstance(neighbors, list)
    assert [n["chunk_index"] for n in neighbors] == [2, 4]
    assert [n["chunk_text"] for n in neighbors] == [texts[2], texts[4]]
    # Neighbour entries carry only chunk_index/chunk_text — no chunk_id,
    # no provenance duplication (SPEC §17.7).
    for n in neighbors:
        assert set(n.keys()) == {"chunk_index", "chunk_text"}


def test_extract_neighbors_clamped_to_three(migrated_root: Path) -> None:
    """neighbors is clamped to [0, 3] — an over-large request still only
    returns what exists within 3 either side, never an error."""
    import pkm.mcp_server as ms

    texts = [f"chunk {i}" for i in range(6)]  # indices 0..5
    chunk_ids = _seed_artifact(
        migrated_root,
        source_id="a" * 64,
        cache_key="b" * 64,
        path="/fake/path/doc.txt",
        texts=texts,
    )
    ms.set_root(migrated_root)
    try:
        result = ms.extract(chunk_ids[3], neighbors=100)
    finally:
        ms.set_root(None)  # type: ignore[arg-type]

    neighbors = result["neighbors"]
    assert isinstance(neighbors, list)
    # target index 3, clamp=3 -> range [0,6] minus target -> 0,1,2,4,5
    assert [n["chunk_index"] for n in neighbors] == [0, 1, 2, 4, 5]


def test_extract_neighbors_negative_clamped_to_zero(migrated_root: Path) -> None:
    import pkm.mcp_server as ms

    texts = [f"chunk {i}" for i in range(3)]
    chunk_ids = _seed_artifact(
        migrated_root,
        source_id="a" * 64,
        cache_key="b" * 64,
        path="/fake/path/doc.txt",
        texts=texts,
    )
    ms.set_root(migrated_root)
    try:
        result = ms.extract(chunk_ids[1], neighbors=-5)
    finally:
        ms.set_root(None)  # type: ignore[arg-type]

    assert result["neighbors"] == []


def test_extract_boundary_chunk_has_partial_neighbors(migrated_root: Path) -> None:
    """The first chunk in an artifact has no 'previous' neighbour — this is
    not an error, just a shorter (possibly empty) neighbors list."""
    import pkm.mcp_server as ms

    texts = ["first chunk", "second chunk", "third chunk"]
    chunk_ids = _seed_artifact(
        migrated_root,
        source_id="a" * 64,
        cache_key="b" * 64,
        path="/fake/path/doc.txt",
        texts=texts,
    )
    ms.set_root(migrated_root)
    try:
        result = ms.extract(chunk_ids[0], neighbors=1)
    finally:
        ms.set_root(None)  # type: ignore[arg-type]

    assert "error" not in result
    assert [n["chunk_index"] for n in result["neighbors"]] == [1]


def test_extract_unknown_chunk_id_returns_bare_error_dict(migrated_root: Path) -> None:
    """SPEC §17.7: unknown chunk_id is a defined error, bare {"error": ...}
    dict (not list-wrapped like search's)."""
    import pkm.mcp_server as ms

    ms.set_root(migrated_root)
    try:
        result = ms.extract(999_999_999)
    finally:
        ms.set_root(None)  # type: ignore[arg-type]

    assert result == {"error": result.get("error")}
    assert isinstance(result["error"], str)
    assert "chunk" in result["error"].lower()


def test_extract_locked_catalogue_returns_bare_error_dict(migrated_root: Path) -> None:
    import pkm.mcp_server as ms

    ms.set_root(migrated_root)
    try:
        with patch(
            "duckdb.connect",
            side_effect=duckdb.IOException("Could not set lock"),
        ):
            result = ms.extract(1)
    finally:
        ms.set_root(None)  # type: ignore[arg-type]

    assert set(result.keys()) == {"error"}
    assert "lock" in result["error"].lower()


def test_extract_root_not_set_returns_error() -> None:
    import pkm.mcp_server as ms

    original = ms._ROOT
    ms._ROOT = None
    try:
        result = ms.extract(1)
    finally:
        ms._ROOT = original

    assert set(result.keys()) == {"error"}


def test_extract_midquery_db_error_returns_error_dict_and_logs(
    migrated_root: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A duckdb.Error raised mid-query (after connect succeeds) must map to
    the bare {"error": ...} dict — never propagate through FastMCP — and
    must still emit the §17.8 audit line (results=[], n_results=0, error)."""
    import pkm.mcp_server as ms

    log_path = tmp_path / "tool.jsonl"

    class _FakeConn:
        def execute(self, *a: object, **kw: object) -> object:
            raise duckdb.Error("mid-query boom")

        def close(self) -> None:
            pass

    ms.set_root(migrated_root)
    ms.set_tool_log(log_path)
    try:
        with (
            patch("duckdb.connect", return_value=_FakeConn()),
            caplog.at_level(logging.WARNING, logger="pkm.mcp_server"),
        ):
            result = ms.extract(1)
    finally:
        ms.set_root(None)  # type: ignore[arg-type]
        ms.set_tool_log(None)

    # Bare error dict, naming the failure and carrying the exception text.
    assert set(result.keys()) == {"error"}
    assert "mid-query boom" in result["error"]
    # WARNed into the diagnostic stream (fail loudly), not swallowed.
    assert any(r.levelno == logging.WARNING for r in caplog.records)
    # The audit trail still records that the call happened and failed.
    lines = _read_jsonl(log_path)
    assert len(lines) == 1
    entry = lines[0]
    assert entry["tool"] == "extract"
    assert entry["results"] == []
    assert entry["n_results"] == 0
    assert "mid-query boom" in entry["error"]


def test_extract_ignores_path_currency_filter(migrated_root: Path) -> None:
    """§15.4 explicitly carves extract out: a chunk_id pointer resolves even
    if its source has since been superseded at the same declared path."""
    import pkm.mcp_server as ms

    # Older version at a shared path.
    old_ids = _seed_artifact(
        migrated_root,
        source_id="1" * 64,
        cache_key="2" * 64,
        path="/fake/tasks/state.md",
        texts=["oldstate chunk"],
        seen="2026-01-01 00:00:00",
    )
    # Newer version superseding it (search would only ever see this one).
    with open_catalogue(migrated_root) as conn:
        conn.execute(
            "INSERT INTO sources (source_id, current_path, first_seen, "
            "last_seen, size_bytes) VALUES (?, ?, CAST(? AS TIMESTAMP), "
            "CAST(? AS TIMESTAMP), 0)",
            ["3" * 64, "/fake/tasks/state.md", "2026-02-01 00:00:00", "2026-02-01 00:00:00"],
        )
        conn.execute(
            """
            INSERT INTO artifacts
                (cache_key, input_hash, producer_name, producer_version,
                 producer_config_hash, status, produced_at, content_type,
                 content_path)
            VALUES (?, ?, 'pandoc', '3.6', 'fakehash2', 'success',
                    current_timestamp, 'text/plain', '/dev/null')
            """,
            ["4" * 64, "3" * 64],
        )
        conn.execute(
            "INSERT INTO artifact_chunks "
            "(artifact_cache_key, chunk_index, chunk_text, source_origin, chunk_id) "
            "VALUES (?, ?, ?, 'pandoc', nextval('seq_chunk_id'))",
            ("4" * 64, 0, "newstate chunk"),
        )
        build_fts_index(conn)

    # search() must not find the superseded chunk.
    with open_catalogue(migrated_root) as conn:
        assert pkm_search(conn, "oldstate") == []

    # extract() must still resolve the pointer to the superseded chunk.
    import pkm.mcp_server as ms2  # noqa: F401 (keep isolated import style consistent)

    ms.set_root(migrated_root)
    try:
        result = ms.extract(old_ids[0])
    finally:
        ms.set_root(None)  # type: ignore[arg-type]

    assert "error" not in result
    assert result["chunk_text"] == "oldstate chunk"


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------


def test_extract_tool_registered() -> None:
    import pkm.mcp_server as ms

    tool_names = [t.name for t in ms.mcp._tool_manager.list_tools()]
    assert "extract" in tool_names


# ---------------------------------------------------------------------------
# §17.8 — tool-call logging
# ---------------------------------------------------------------------------


def test_search_writes_tool_log_line(migrated_root: Path, tmp_path: Path) -> None:
    import pkm.mcp_server as ms

    chunk_ids = _seed_artifact(
        migrated_root,
        source_id="a" * 64,
        cache_key="b" * 64,
        path="/fake/path/doc.txt",
        texts=["hello booking world"],
    )
    log_path = tmp_path / "tool.jsonl"
    ms.set_root(migrated_root)
    ms.set_tool_log(log_path)
    try:
        results = ms.search("booking", k=5)
    finally:
        ms.set_root(None)  # type: ignore[arg-type]
        ms.set_tool_log(None)

    lines = _read_jsonl(log_path)
    assert len(lines) == 1
    entry = lines[0]
    assert entry["tool"] == "search"
    assert entry["args"] == {"query": "booking", "k": 5}
    assert entry["n_results"] == 1
    assert isinstance(entry["ts"], str) and entry["ts"]

    logged = entry["results"][0]
    assert logged["chunk_id"] == chunk_ids[0]
    assert logged["artifact_cache_key"] == "b" * 64
    assert logged["source_path"] == "/fake/path/doc.txt"
    assert logged["score"] == results[0]["score"]
    assert logged["snippet_shown"] == results[0]["chunk_text"]
    assert logged["chunk_text_full"] == "hello booking world"


def test_extract_writes_tool_log_target_first_then_neighbors(
    migrated_root: Path, tmp_path: Path
) -> None:
    import pkm.mcp_server as ms

    texts = [f"chunk {i}" for i in range(4)]
    chunk_ids = _seed_artifact(
        migrated_root,
        source_id="a" * 64,
        cache_key="b" * 64,
        path="/fake/path/doc.txt",
        texts=texts,
    )
    log_path = tmp_path / "tool.jsonl"
    ms.set_root(migrated_root)
    ms.set_tool_log(log_path)
    try:
        ms.extract(chunk_ids[1], neighbors=1)  # neighbours at index 0 and 2
    finally:
        ms.set_root(None)  # type: ignore[arg-type]
        ms.set_tool_log(None)

    lines = _read_jsonl(log_path)
    assert len(lines) == 1
    entry = lines[0]
    assert entry["tool"] == "extract"
    # args records what was actually received, pre-clamping.
    assert entry["args"] == {"chunk_id": chunk_ids[1], "neighbors": 1}
    assert entry["n_results"] == 3

    results = entry["results"]
    assert [r["chunk_id"] for r in results] == [chunk_ids[1], chunk_ids[0], chunk_ids[2]]
    assert [r["chunk_text_full"] for r in results] == [texts[1], texts[0], texts[2]]
    for r in results:
        assert r["artifact_cache_key"] == "b" * 64
        assert r["source_path"] == "/fake/path/doc.txt"
        # extract has no ranking score and always shows full text.
        assert r["score"] is None
        assert r["snippet_shown"] is None


def test_extract_tool_log_records_preclamp_neighbors_arg(
    migrated_root: Path, tmp_path: Path
) -> None:
    """args in the log line shows the raw request, not the clamped value."""
    import pkm.mcp_server as ms

    chunk_ids = _seed_artifact(
        migrated_root,
        source_id="a" * 64,
        cache_key="b" * 64,
        path="/fake/path/doc.txt",
        texts=["only chunk"],
    )
    log_path = tmp_path / "tool.jsonl"
    ms.set_root(migrated_root)
    ms.set_tool_log(log_path)
    try:
        ms.extract(chunk_ids[0], neighbors=99)
    finally:
        ms.set_root(None)  # type: ignore[arg-type]
        ms.set_tool_log(None)

    entry = _read_jsonl(log_path)[0]
    assert entry["args"]["neighbors"] == 99


def test_error_call_logs_empty_results_and_error_key(
    migrated_root: Path, tmp_path: Path
) -> None:
    """SPEC §17.8: an errored call logs results=[], n_results=0, plus a
    top-level 'error' key."""
    import pkm.mcp_server as ms

    log_path = tmp_path / "tool.jsonl"
    ms.set_root(migrated_root)
    ms.set_tool_log(log_path)
    try:
        with patch(
            "duckdb.connect",
            side_effect=duckdb.IOException("Could not set lock"),
        ):
            ms.search("anything")
            ms.extract(1)
    finally:
        ms.set_root(None)  # type: ignore[arg-type]
        ms.set_tool_log(None)

    lines = _read_jsonl(log_path)
    assert len(lines) == 2
    for entry in lines:
        assert entry["results"] == []
        assert entry["n_results"] == 0
        assert isinstance(entry.get("error"), str)


def test_tool_log_double_call_appends_two_lines_db_untouched(
    migrated_root: Path, tmp_path: Path
) -> None:
    """Calling search twice with identical args leaves the read-only query
    idempotent, but appends two distinct log lines (SPEC §17.8: 'Not cache
    idempotency')."""
    import pkm.mcp_server as ms

    _seed_artifact(
        migrated_root,
        source_id="a" * 64,
        cache_key="b" * 64,
        path="/fake/path/doc.txt",
        texts=["hello booking world"],
    )
    with open_catalogue(migrated_root) as conn:
        (before,) = conn.execute("SELECT count(*) FROM artifact_chunks").fetchone()

    log_path = tmp_path / "tool.jsonl"
    ms.set_root(migrated_root)
    ms.set_tool_log(log_path)
    try:
        first = ms.search("booking", k=5)
        second = ms.search("booking", k=5)
    finally:
        ms.set_root(None)  # type: ignore[arg-type]
        ms.set_tool_log(None)

    with open_catalogue(migrated_root) as conn:
        (after,) = conn.execute("SELECT count(*) FROM artifact_chunks").fetchone()

    assert before == after
    assert first == second

    lines = _read_jsonl(log_path)
    assert len(lines) == 2
    # Identical modulo the completion timestamp.
    a, b = lines
    a.pop("ts")
    b.pop("ts")
    assert a == b


def test_tool_log_fail_open_on_unwritable_path(
    migrated_root: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A logging failure WARNs and never raises into the tool result."""
    import pkm.mcp_server as ms

    _seed_artifact(
        migrated_root,
        source_id="a" * 64,
        cache_key="b" * 64,
        path="/fake/path/doc.txt",
        texts=["hello booking world"],
    )
    # Parent directory does not exist -> open() raises FileNotFoundError.
    bad_log_path = tmp_path / "no" / "such" / "dir" / "tool.jsonl"
    ms.set_root(migrated_root)
    ms.set_tool_log(bad_log_path)
    try:
        with caplog.at_level(logging.WARNING, logger="pkm.mcp_server"):
            results = ms.search("booking", k=5)
    finally:
        ms.set_root(None)  # type: ignore[arg-type]
        ms.set_tool_log(None)

    assert len(results) == 1
    assert results[0]["chunk_text"]
    assert "error" not in results[0]
    assert any(r.levelno == logging.WARNING for r in caplog.records)
    assert not bad_log_path.parent.exists()


def test_set_tool_log_none_disables_logging(migrated_root: Path, tmp_path: Path) -> None:
    import pkm.mcp_server as ms

    _seed_artifact(
        migrated_root,
        source_id="a" * 64,
        cache_key="b" * 64,
        path="/fake/path/doc.txt",
        texts=["hello booking world"],
    )
    ms.set_root(migrated_root)
    ms.set_tool_log(None)
    try:
        ms.search("booking")
    finally:
        ms.set_root(None)  # type: ignore[arg-type]

    # No log path configured -> no file should have been created anywhere
    # under tmp_path (nothing to assert on a path, but this must not raise).


# ---------------------------------------------------------------------------
# CLI wiring: pkm serve --tool-log PATH -> mcp_server.set_tool_log
# ---------------------------------------------------------------------------


def test_serve_wires_tool_log_flag_through_cli(
    migrated_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pkm import mcp_server
    from pkm.cli import main

    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(f"root_dir: {migrated_root}\n", encoding="utf-8")
    log_path = tmp_path / "tool.jsonl"

    calls: list[str] = []
    monkeypatch.setattr(mcp_server.mcp, "run", lambda **kw: calls.append("run"))

    exit_code = main(
        ["--config", str(cfg_path), "serve", "--tool-log", str(log_path)]
    )

    assert exit_code == 0
    assert calls == ["run"]
    assert log_path == mcp_server._TOOL_LOG_PATH
    assert migrated_root == mcp_server._ROOT

    mcp_server.set_root(None)
    mcp_server.set_tool_log(None)


def test_serve_without_tool_log_flag_leaves_logging_disabled(
    migrated_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pkm import mcp_server
    from pkm.cli import main

    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(f"root_dir: {migrated_root}\n", encoding="utf-8")

    calls: list[str] = []
    monkeypatch.setattr(mcp_server.mcp, "run", lambda **kw: calls.append("run"))

    exit_code = main(["--config", str(cfg_path), "serve"])

    assert exit_code == 0
    assert mcp_server._TOOL_LOG_PATH is None

    mcp_server.set_root(None)
