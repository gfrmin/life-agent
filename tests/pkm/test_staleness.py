"""Staleness (SPEC §18.10) — read-only, deterministic, catalogue-only.

    superseded = a newer success for the same (input_hash, producer_name)
    stale      = superseded, plus everything derived downstream of a stale artifact

The catalogue is built with direct INSERTs so each artifact's ``produced_at`` is
controlled exactly — that recency is the whole point. ``pkm.staleness`` never
writes, never touches the filesystem, never deletes (SPEC §18.10 flag-never-delete).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import duckdb

from pkm import staleness
from pkm.catalogue import open_catalogue


# A 64-hex cache key from a short readable stem, so test intent stays legible.
def _key(stem: str) -> str:
    return (stem + "0" * 64)[:64]


def _artifact(
    conn: duckdb.DuckDBPyConnection,
    *,
    key: str,
    input_hash: str,
    producer: str,
    version: str,
    when: str,
    status: str = "success",
) -> None:
    conn.execute(
        "INSERT INTO artifacts "
        "(cache_key, input_hash, producer_name, producer_version, "
        " producer_config_hash, status, produced_at, content_type, content_path) "
        "VALUES (?, ?, ?, ?, 'cfg', ?, ?, 'text/plain', '/dev/null')",
        [key, input_hash, producer, version, status, datetime.fromisoformat(when)],
    )


def _edge(conn: duckdb.DuckDBPyConnection, *, derived: str, frm: str,
          role: str = "source") -> None:
    conn.execute(
        "INSERT INTO artifact_lineage (artifact_cache_key, input_cache_key, role) "
        "VALUES (?, ?, ?)",
        [derived, frm, role],
    )


# --- superseded: the base case ---------------------------------------------- #

def test_a_lone_artifact_is_never_superseded(migrated_root: Path) -> None:
    with open_catalogue(migrated_root) as conn:
        _artifact(conn, key=_key("a"), input_hash="s" * 64, producer="docling",
                  version="1", when="2026-01-01T00:00:00")
        assert staleness.superseded(conn) == {}
        assert staleness.stale(conn) == []


def test_a_newer_rederivation_supersedes_the_older(migrated_root: Path) -> None:
    with open_catalogue(migrated_root) as conn:
        old, new = _key("old"), _key("new")
        _artifact(conn, key=old, input_hash="s" * 64, producer="docling",
                  version="1", when="2026-01-01T00:00:00")
        _artifact(conn, key=new, input_hash="s" * 64, producer="docling",
                  version="2", when="2026-02-01T00:00:00")
        # the older one is superseded BY the newer (current) one
        assert staleness.superseded(conn) == {old: new}
        st = staleness.stale(conn)
        assert [(s.cache_key, s.reason, s.via) for s in st] == [(old, "superseded", new)]


def test_failed_artifacts_neither_supersede_nor_are_superseded(migrated_root: Path) -> None:
    with open_catalogue(migrated_root) as conn:
        ok, fail = _key("ok"), _key("fail")
        _artifact(conn, key=ok, input_hash="s" * 64, producer="docling",
                  version="1", when="2026-01-01T00:00:00")
        # a newer FAILED attempt on the same input must not supersede the success
        _artifact(conn, key=fail, input_hash="s" * 64, producer="docling",
                  version="2", when="2026-03-01T00:00:00", status="failed")
        assert staleness.superseded(conn) == {}
        assert staleness.stale(conn) == []


def test_same_input_different_producers_are_independent(migrated_root: Path) -> None:
    with open_catalogue(migrated_root) as conn:
        # docling and tesseract both ran the same source — neither supersedes the other
        _artifact(conn, key=_key("doc"), input_hash="s" * 64, producer="docling",
                  version="1", when="2026-01-01T00:00:00")
        _artifact(conn, key=_key("tes"), input_hash="s" * 64, producer="tesseract",
                  version="1", when="2026-02-01T00:00:00")
        assert staleness.superseded(conn) == {}


def test_timestamp_tie_is_broken_deterministically_by_cache_key(migrated_root: Path) -> None:
    with open_catalogue(migrated_root) as conn:
        lo, hi = _key("aaa"), _key("zzz")  # same produced_at; cache_key breaks the tie
        _artifact(conn, key=lo, input_hash="s" * 64, producer="docling",
                  version="1", when="2026-01-01T00:00:00")
        _artifact(conn, key=hi, input_hash="s" * 64, producer="docling",
                  version="2", when="2026-01-01T00:00:00")
        # highest cache_key wins the tie → it is current, the other superseded
        assert staleness.superseded(conn) == {lo: hi}


# --- stale: transitive downstream closure ----------------------------------- #

def test_stale_propagates_downstream_two_hops(migrated_root: Path) -> None:
    with open_catalogue(migrated_root) as conn:
        old, new = _key("ocrold"), _key("ocrnew")
        chunk, entities = _key("chunk"), _key("entities")
        # source extracted twice (v1 superseded by v2)
        _artifact(conn, key=old, input_hash="s" * 64, producer="docling",
                  version="1", when="2026-01-01T00:00:00")
        _artifact(conn, key=new, input_hash="s" * 64, producer="docling",
                  version="2", when="2026-02-01T00:00:00")
        # a chunking artifact derived from the OLD extraction, and entities from that chunk
        _artifact(conn, key=chunk, input_hash="c" * 64, producer="chunk",
                  version="1", when="2026-01-02T00:00:00")
        _artifact(conn, key=entities, input_hash="e" * 64, producer="entity_extraction",
                  version="1", when="2026-01-03T00:00:00")
        _edge(conn, derived=chunk, frm=old)
        _edge(conn, derived=entities, frm=chunk)

        st = {s.cache_key: s for s in staleness.stale(conn)}
        assert set(st) == {old, chunk, entities}
        assert (st[old].reason, st[old].via) == ("superseded", new)
        assert (st[chunk].reason, st[chunk].via) == ("stale-input", old)
        assert (st[entities].reason, st[entities].via) == ("stale-input", chunk)


def test_derivative_of_the_current_artifact_is_not_stale(migrated_root: Path) -> None:
    with open_catalogue(migrated_root) as conn:
        old, new = _key("old"), _key("new")
        chunk_old, chunk_new = _key("cold"), _key("cnew")
        _artifact(conn, key=old, input_hash="s" * 64, producer="docling",
                  version="1", when="2026-01-01T00:00:00")
        _artifact(conn, key=new, input_hash="s" * 64, producer="docling",
                  version="2", when="2026-02-01T00:00:00")
        _artifact(conn, key=chunk_old, input_hash="c" * 64, producer="chunk",
                  version="1", when="2026-01-02T00:00:00")
        _artifact(conn, key=chunk_new, input_hash="d" * 64, producer="chunk",
                  version="1", when="2026-02-02T00:00:00")
        _edge(conn, derived=chunk_old, frm=old)   # derived from the superseded extraction
        _edge(conn, derived=chunk_new, frm=new)   # derived from the current extraction

        stale_keys = {s.cache_key for s in staleness.stale(conn)}
        assert old in stale_keys and chunk_old in stale_keys
        assert chunk_new not in stale_keys  # built on the current artifact → fresh


def test_superseded_reason_takes_precedence_over_stale_input(migrated_root: Path) -> None:
    # An artifact that is BOTH superseded and downstream of a stale input is reported
    # as "superseded" (the stronger, direct reason).
    with open_catalogue(migrated_root) as conn:
        root_old, root_new = _key("rold"), _key("rnew")
        deriv_old, deriv_new = _key("dold"), _key("dnew")
        _artifact(conn, key=root_old, input_hash="s" * 64, producer="docling",
                  version="1", when="2026-01-01T00:00:00")
        _artifact(conn, key=root_new, input_hash="s" * 64, producer="docling",
                  version="2", when="2026-02-01T00:00:00")
        # deriv has its own (input_hash, producer) group with a newer sibling, AND
        # is derived from the superseded root_old
        _artifact(conn, key=deriv_old, input_hash="t" * 64, producer="action_items",
                  version="1", when="2026-01-05T00:00:00")
        _artifact(conn, key=deriv_new, input_hash="t" * 64, producer="action_items",
                  version="2", when="2026-03-05T00:00:00")
        _edge(conn, derived=deriv_old, frm=root_old)

        st = {s.cache_key: s for s in staleness.stale(conn)}
        assert st[deriv_old].reason == "superseded"
        assert st[deriv_old].via == deriv_new


# --- shape, order, purity --------------------------------------------------- #

def test_output_is_sorted_by_cache_key(migrated_root: Path) -> None:
    with open_catalogue(migrated_root) as conn:
        for stem, inp in [("aaa", "1"), ("mmm", "2"), ("zzz", "3")]:
            old, new = _key(stem + "old"), _key(stem + "new")
            _artifact(conn, key=old, input_hash=inp * 64, producer="docling",
                      version="1", when="2026-01-01T00:00:00")
            _artifact(conn, key=new, input_hash=inp * 64, producer="docling",
                      version="2", when="2026-02-01T00:00:00")
        keys = [s.cache_key for s in staleness.stale(conn)]
        assert keys == sorted(keys)


def test_stale_artifact_carries_its_producer_name(migrated_root: Path) -> None:
    with open_catalogue(migrated_root) as conn:
        old, new = _key("old"), _key("new")
        _artifact(conn, key=old, input_hash="s" * 64, producer="docling",
                  version="1", when="2026-01-01T00:00:00")
        _artifact(conn, key=new, input_hash="s" * 64, producer="docling",
                  version="2", when="2026-02-01T00:00:00")
        (s,) = staleness.stale(conn)
        assert s.producer_name == "docling"


def test_empty_catalogue_has_no_stale(migrated_root: Path) -> None:
    with open_catalogue(migrated_root) as conn:
        assert staleness.superseded(conn) == {}
        assert staleness.stale(conn) == []


def test_staleness_writes_nothing(migrated_root: Path) -> None:
    # purity: computing staleness must not change the catalogue (no rows, no schema).
    with open_catalogue(migrated_root) as conn:
        old, new = _key("old"), _key("new")
        _artifact(conn, key=old, input_hash="s" * 64, producer="docling",
                  version="1", when="2026-01-01T00:00:00")
        _artifact(conn, key=new, input_hash="s" * 64, producer="docling",
                  version="2", when="2026-02-01T00:00:00")
        before = conn.execute("SELECT count(*) FROM artifacts").fetchone()[0]
        staleness.stale(conn)
        staleness.superseded(conn)
        after = conn.execute("SELECT count(*) FROM artifacts").fetchone()[0]
        assert before == after == 2
