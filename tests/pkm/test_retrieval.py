"""Tests for ``pkm.retrieval`` — FTS keyword search substrate
(SPEC v0.1.11 Step 3).

Stage-A hermetic: hand-seeded ``artifact_chunks`` in ``migrated_root``.
No live corpus is touched. The Hebrew tokenisation test is the critical
one: if DuckDB FTS reverts to the default ``ignore='(\\.|[^a-z])+'``
pattern, all Hebrew characters are treated as separators, the index
contains zero tokens, and the Hebrew query returns nothing — failing
this test immediately rather than mysteriously at eval time.
"""

from __future__ import annotations

from pathlib import Path

from pkm.catalogue import open_catalogue
from pkm.retrieval import SearchResult, build_fts_index, search

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HEBREW_CHUNK = "תעודת זהות 123456789"
_ENGLISH_CHUNK = "This is an English sentence about invoices."


def _seed(migrated_root: Path) -> None:
    """Populate the tables that retrieval queries join across."""
    with open_catalogue(migrated_root) as conn:
        # sources row (provides source_id → path lookup)
        conn.execute(
            "INSERT INTO sources (source_id, current_path, first_seen, "
            "last_seen, size_bytes) VALUES (?, ?, current_timestamp, "
            "current_timestamp, 0)",
            ["a" * 64, "/fake/path/id_card.jpg"],
        )
        # artifacts row
        conn.execute(
            """
            INSERT INTO artifacts
                (cache_key, input_hash, producer_name, producer_version,
                 producer_config_hash, status, produced_at, content_type,
                 content_path)
            VALUES (?, ?, 'tesseract', '5.5.2', 'fakehash', 'success',
                    current_timestamp, 'text/plain', '/dev/null')
            """,
            ["b" * 64, "a" * 64],
        )
        # artifact_chunks rows
        conn.executemany(
            "INSERT INTO artifact_chunks "
            "(artifact_cache_key, chunk_index, chunk_text, source_origin, chunk_id) "
            "VALUES (?, ?, ?, 'test', nextval('seq_chunk_id'))",
            [
                ("b" * 64, 0, _HEBREW_CHUNK),
                ("b" * 64, 1, _ENGLISH_CHUNK),
            ],
        )
        build_fts_index(conn)


# ---------------------------------------------------------------------------
# FTS basic contract
# ---------------------------------------------------------------------------


def test_fts_hebrew_hit(migrated_root: Path) -> None:
    """A Hebrew-token query returns the chunk that contains it.

    This directly exercises the Unicode-aware tokeniser configuration.
    If ``ignore`` reverts to the ``[^a-z]+`` default, Hebrew characters
    are all treated as separators, the FTS index contains zero Hebrew
    tokens, and this query returns empty — failing here rather than
    silently at eval time.
    """
    _seed(migrated_root)
    with open_catalogue(migrated_root) as conn:
        results = search(conn, "תעודת")
    assert len(results) >= 1
    texts = [r.chunk_text for r in results]
    assert any("תעודת" in t for t in texts)


def test_fts_english_hit(migrated_root: Path) -> None:
    """An English-token query returns the chunk that contains it."""
    _seed(migrated_root)
    with open_catalogue(migrated_root) as conn:
        results = search(conn, "invoices")
    assert len(results) >= 1
    assert any("invoices" in r.chunk_text for r in results)


def test_fts_no_hit(migrated_root: Path) -> None:
    """A query that matches nothing returns an empty list."""
    _seed(migrated_root)
    with open_catalogue(migrated_root) as conn:
        results = search(conn, "xyzzy_no_match_12345")
    assert results == []


def test_fts_ranking(migrated_root: Path) -> None:
    """A more-relevant chunk ranks above a less-relevant one."""
    with open_catalogue(migrated_root) as conn:
        # Seed a second source with two chunks: one with 3 hits on "apple",
        # one with 1 hit — the higher-frequency one should rank first.
        conn.execute(
            "INSERT INTO sources (source_id, current_path, first_seen, "
            "last_seen, size_bytes) VALUES (?, ?, current_timestamp, "
            "current_timestamp, 0)",
            ["c" * 64, "/fake/apples.txt"],
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
            ["d" * 64, "c" * 64],
        )
        conn.executemany(
            "INSERT INTO artifact_chunks "
            "(artifact_cache_key, chunk_index, chunk_text, source_origin, chunk_id) "
            "VALUES (?, ?, ?, 'test', nextval('seq_chunk_id'))",
            [
                ("d" * 64, 0, "apple apple apple"),
                ("d" * 64, 1, "apple banana cherry"),
            ],
        )
        build_fts_index(conn)
        results = search(conn, "apple")

    assert len(results) >= 2
    # The chunk with 3 occurrences of "apple" must rank above the one with 1
    top_two = results[:2]
    top_two_texts = [r.chunk_text for r in top_two]
    assert "apple apple apple" in top_two_texts
    higher = next(r for r in top_two if r.chunk_text == "apple apple apple")
    lower = next(r for r in top_two if r.chunk_text == "apple banana cherry")
    assert higher.score >= lower.score


def test_search_result_has_provenance(migrated_root: Path) -> None:
    """SearchResult carries source_path, source_origin, and artifact_cache_key."""
    _seed(migrated_root)
    with open_catalogue(migrated_root) as conn:
        results = search(conn, "123456789")
    assert len(results) >= 1
    r = results[0]
    assert isinstance(r, SearchResult)
    assert r.source_path == "/fake/path/id_card.jpg"
    assert r.source_origin == "test"
    assert r.artifact_cache_key == "b" * 64


# ---------------------------------------------------------------------------
# Source-path currency (SPEC §15.4)
# ---------------------------------------------------------------------------


def _seed_path_version(
    migrated_root: Path,
    *,
    source_id: str,
    path: str,
    seen: str,
    cache_key: str | None,
    chunks: list[str],
) -> None:
    """Seed one ingested version of a declared path (source → artifact → chunks).

    ``cache_key=None`` seeds the source row only — a version whose extraction
    has not produced chunks yet (§15.4 content-currency).
    """
    with open_catalogue(migrated_root) as conn:
        conn.execute(
            "INSERT INTO sources (source_id, current_path, first_seen, "
            "last_seen, size_bytes) VALUES (?, ?, CAST(? AS TIMESTAMP), "
            "CAST(? AS TIMESTAMP), 0)",
            [source_id, path, seen, seen],
        )
        if cache_key is None:
            return
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
            "VALUES (?, ?, ?, 'test', nextval('seq_chunk_id'))",
            [(cache_key, i, text) for i, text in enumerate(chunks)],
        )


def test_path_superseded_version_excluded(migrated_root: Path) -> None:
    """Two ingested versions of one declared path: only the newest is retrievable.

    SPEC §15.4 — the superseded version's chunks stay catalogued but never
    surface in search results.
    """
    _seed_path_version(
        migrated_root,
        source_id="1" * 64,
        path="/fake/tasks/state.md",
        seen="2026-01-01 00:00:00",
        cache_key="2" * 64,
        chunks=["oldstate common"],
    )
    _seed_path_version(
        migrated_root,
        source_id="3" * 64,
        path="/fake/tasks/state.md",
        seen="2026-02-01 00:00:00",
        cache_key="4" * 64,
        chunks=["newstate common"],
    )
    with open_catalogue(migrated_root) as conn:
        build_fts_index(conn)
        common = search(conn, "common")
        old_only = search(conn, "oldstate")
        # Flag-never-delete: the superseded chunks are still catalogued.
        (kept,) = conn.execute(
            "SELECT count(*) FROM artifact_chunks WHERE artifact_cache_key = ?",
            ["2" * 64],
        ).fetchone()
    assert [r.chunk_text for r in common] == ["newstate common"]
    assert old_only == []
    assert kept == 1


def test_path_currency_single_version_unaffected(migrated_root: Path) -> None:
    """A path ingested once (the overwhelming case) is admitted as before."""
    _seed(migrated_root)
    with open_catalogue(migrated_root) as conn:
        results = search(conn, "invoices")
    assert any("invoices" in r.chunk_text for r in results)


def test_path_currency_tiebreak_deterministic(migrated_root: Path) -> None:
    """Equal timestamps: the (last_seen, first_seen, source_id) DESC order picks
    exactly one current version, deterministically (SPEC §15.4 tiebreak)."""
    _seed_path_version(
        migrated_root,
        source_id="7" * 64,
        path="/fake/tasks/tie.md",
        seen="2026-03-01 00:00:00",
        cache_key="a1" + "0" * 62,
        chunks=["tieloser"],
    )
    _seed_path_version(
        migrated_root,
        source_id="8" * 64,
        path="/fake/tasks/tie.md",
        seen="2026-03-01 00:00:00",
        cache_key="a2" + "0" * 62,
        chunks=["tiewinner"],
    )
    with open_catalogue(migrated_root) as conn:
        build_fts_index(conn)
        winner = search(conn, "tiewinner")
        loser = search(conn, "tieloser")
    assert len(winner) == 1
    assert loser == []


def test_current_version_without_chunks_yields_nothing(migrated_root: Path) -> None:
    """Content-currency, not chunk-availability (SPEC §15.4): a newer version
    with no chunks yet must NOT resurrect the superseded version's chunks."""
    _seed_path_version(
        migrated_root,
        source_id="5" * 64,
        path="/fake/tasks/pending.md",
        seen="2026-01-01 00:00:00",
        cache_key="6" * 64,
        chunks=["ghosttoken"],
    )
    _seed_path_version(
        migrated_root,
        source_id="9" * 64,
        path="/fake/tasks/pending.md",
        seen="2026-02-01 00:00:00",
        cache_key=None,  # ingested, not yet extracted/chunked
        chunks=[],
    )
    with open_catalogue(migrated_root) as conn:
        build_fts_index(conn)
        results = search(conn, "ghosttoken")
    assert results == []


def test_path_superseded_chunk_count(migrated_root: Path) -> None:
    """The excluded set is countable (SPEC §15.4 / §14.6 no hidden state)."""
    from pkm.retrieval import count_path_superseded_chunks

    _seed(migrated_root)  # single-version corpus: nothing excluded
    with open_catalogue(migrated_root) as conn:
        assert count_path_superseded_chunks(conn) == 0
    _seed_path_version(
        migrated_root,
        source_id="1" * 64,
        path="/fake/tasks/state.md",
        seen="2026-01-01 00:00:00",
        cache_key="2" * 64,
        chunks=["oldstate one", "oldstate two"],
    )
    _seed_path_version(
        migrated_root,
        source_id="3" * 64,
        path="/fake/tasks/state.md",
        seen="2026-02-01 00:00:00",
        cache_key="4" * 64,
        chunks=["newstate"],
    )
    with open_catalogue(migrated_root) as conn:
        assert count_path_superseded_chunks(conn) == 2


def test_search_returns_at_most_k_results(migrated_root: Path) -> None:
    """search() respects the ``k`` limit."""
    with open_catalogue(migrated_root) as conn:
        # Seed many chunks that all match "word"
        conn.execute(
            "INSERT INTO sources (source_id, current_path, first_seen, "
            "last_seen, size_bytes) VALUES (?, ?, current_timestamp, "
            "current_timestamp, 0)",
            ["e" * 64, "/fake/many.txt"],
        )
        conn.execute(
            """
            INSERT INTO artifacts
                (cache_key, input_hash, producer_name, producer_version,
                 producer_config_hash, status, produced_at, content_type,
                 content_path)
            VALUES (?, ?, 'pandoc', '3.6', 'fakehash3', 'success',
                    current_timestamp, 'text/plain', '/dev/null')
            """,
            ["f" * 64, "e" * 64],
        )
        rows = [("f" * 64, i, f"word sentence {i}") for i in range(30)]
        conn.executemany(
            "INSERT INTO artifact_chunks "
            "(artifact_cache_key, chunk_index, chunk_text, source_origin, chunk_id) "
            "VALUES (?, ?, ?, 'test', nextval('seq_chunk_id'))",
            rows,
        )
        build_fts_index(conn)
        results = search(conn, "word", k=5)

    assert len(results) <= 5
