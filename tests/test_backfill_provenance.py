"""Unit tests for the gold-provenance backfill (scripts/eval_factory/backfill_provenance.py).

Hermetic: in-memory DuckDB with a minimal ``artifact_chunks``, synthetic questions, no KB.

The point of this script is that it may ONLY add ``artifact_cache_key``/``chunk_index``.
The gate's blind discipline rests on being able to assert that the question set did not
move across the rewrite, so the refusal paths below are the load-bearing tests, not the
happy path.

Run from the repo root:
    uv run --project . python -m pytest ./tests/test_backfill_provenance.py
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from eval_factory import backfill_provenance as B


def _conn() -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(":memory:")
    conn.execute(
        "CREATE TABLE artifact_chunks "
        "(chunk_id BIGINT, artifact_cache_key VARCHAR, chunk_index INTEGER)"
    )
    conn.execute(
        "INSERT INTO artifact_chunks VALUES (100,'aaa',0), (101,'aaa',1), (102,'bbb',7)"
    )
    return conn


def _corpus(*provenances: dict[str, Any]) -> dict[str, Any]:
    return {
        "format_version": 1,
        "questions": [
            {"id": f"q2-{i:03d}", "question": f"q{i}?", "subject": "owner",
             "answer": f"A{i}", "answer_variants": [], "notes": "", "provenance": p}
            for i, p in enumerate(provenances, start=1)
        ],
    }


def test_resolve_handles_returns_the_primary_key_pair() -> None:
    assert B.resolve_handles(_conn(), [100, 102]) == {100: ("aaa", 0), 102: ("bbb", 7)}


def test_resolve_handles_empty_input_does_not_build_a_degenerate_query() -> None:
    assert B.resolve_handles(_conn(), []) == {}


def test_backfill_adds_the_pair_and_keeps_the_surrogate() -> None:
    corpus = _corpus({"chunk_id": 101, "source_path": "/fake/a.pdf"})
    out, filled, unresolved = B.backfill(corpus, B.resolve_handles(_conn(), [101]))
    assert (filled, unresolved) == (1, [])
    prov = out["questions"][0]["provenance"]
    assert (prov["artifact_cache_key"], prov["chunk_index"]) == ("aaa", 1)
    assert prov["chunk_id"] == 101          # surrogate kept, not replaced
    assert prov["source_path"] == "/fake/a.pdf"
    # the input must not be mutated — callers diff before against after
    assert "artifact_cache_key" not in corpus["questions"][0]["provenance"]


def test_backfill_is_idempotent_on_an_already_backfilled_question() -> None:
    corpus = _corpus({"chunk_id": 101, "artifact_cache_key": "zzz", "chunk_index": 5})
    out, filled, _ = B.backfill(corpus, B.resolve_handles(_conn(), [101]))
    assert filled == 0
    # and crucially it does NOT overwrite an existing handle with a freshly-resolved one:
    # on a re-chunked catalogue that would silently repoint the gold.
    assert out["questions"][0]["provenance"]["artifact_cache_key"] == "zzz"


def test_backfill_names_unresolved_questions_instead_of_dropping_them() -> None:
    corpus = _corpus({"chunk_id": 999, "source_path": "/gone.pdf"})
    out, filled, unresolved = B.backfill(corpus, B.resolve_handles(_conn(), [999]))
    assert (filled, unresolved) == (0, ["q2-001"])
    assert "artifact_cache_key" not in out["questions"][0]["provenance"]
    assert len(out["questions"]) == 1       # never dropped


def test_assert_provenance_only_passes_for_an_additive_rewrite() -> None:
    corpus = _corpus({"chunk_id": 100})
    out, _, _ = B.backfill(corpus, B.resolve_handles(_conn(), [100]))
    B.assert_provenance_only(corpus, out)   # must not raise


def test_assert_provenance_only_refuses_a_changed_answer() -> None:
    """The blind-discipline guard: a corpus rewrite must never move an answer."""
    corpus = _corpus({"chunk_id": 100})
    out, _, _ = B.backfill(corpus, B.resolve_handles(_conn(), [100]))
    out["questions"][0]["answer"] = "TAMPERED"
    with pytest.raises(SystemExit, match="non-provenance change"):
        B.assert_provenance_only(corpus, out)


def test_assert_provenance_only_refuses_a_rewritten_existing_provenance_key() -> None:
    corpus = _corpus({"chunk_id": 100, "source_path": "/fake/a.pdf"})
    out, _, _ = B.backfill(corpus, B.resolve_handles(_conn(), [100]))
    out["questions"][0]["provenance"]["source_path"] = "/somewhere/else.pdf"
    with pytest.raises(SystemExit, match="may only ADD keys"):
        B.assert_provenance_only(corpus, out)


def test_assert_provenance_only_refuses_a_dropped_question() -> None:
    corpus = _corpus({"chunk_id": 100}, {"chunk_id": 102})
    out, _, _ = B.backfill(corpus, B.resolve_handles(_conn(), [100, 102]))
    out["questions"].pop()
    with pytest.raises(SystemExit, match="question count changed"):
        B.assert_provenance_only(corpus, out)
