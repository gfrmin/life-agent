"""life_agent.core.temporal — read-side doc_date projection + predicate (D1).

The hermetic form of the D1 gate: documents whose date cannot be determined
are NAMED (with reason and remedy), never silently dropped. The planted
dropout is artifact C — retrieved, but with no doc_date artifact derived.
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import date
from pathlib import Path

import duckdb
import pytest

from life_agent.core.temporal import (
    DatedHit,
    TemporalView,
    apply_temporal,
    project_dates,
)
from pkm.cache import write_artifact
from pkm.catalogue import open_catalogue, run_migrations
from pkm.producer import ProducerResult


@pytest.fixture
def migrated_root(tmp_path: Path) -> Path:
    """A migrated pkm root (the tests/pkm/conftest.py fixture is package-local,
    so the life_agent test tree defines its own)."""
    (tmp_path / "cache").mkdir()
    (tmp_path / "logs").mkdir()
    run_migrations(tmp_path)
    return tmp_path


def _success(content: bytes, content_type: str = "text/plain") -> ProducerResult:
    return ProducerResult(
        status="success", content=content, content_type=content_type,
        content_encoding="utf-8", error_message=None, producer_metadata={},
    )


def _write(root: Path, conn: duckdb.DuckDBPyConnection, *, key: str,
           input_hash: str, producer: str, version: str, content: bytes,
           lineage: list[dict[str, str]] | None = None) -> None:
    write_artifact(
        root, conn, cache_key=key, input_hash=input_hash,
        producer_name=producer, producer_version=version, producer_config={},
        result=_success(content), lineage=lineage,
        cache_key_schema_version=1 if lineage is None else 3,
    )


def _doc_date_content(d: str | None) -> bytes:
    return json.dumps({"format_version": 1, "date": d}).encode("utf-8")


def _seed(root: Path) -> tuple[str, str, str]:
    """Three extractor artifacts: A (email, dated — with a superseded older
    projection), B (docling, null date), C (pandoc, NO projection at all).
    Returns (A, B, C) cache keys."""
    a_key, b_key, c_key = "aa" * 32, "bb" * 32, "cc" * 32
    with open_catalogue(root) as conn:
        _write(root, conn, key=a_key, input_hash="11" * 32, producer="email",
               version="1", content=b"Date: Mon, 01 Jun 2026 10:00:00 +0000\n\nhi")
        _write(root, conn, key=b_key, input_hash="22" * 32, producer="docling",
               version="1", content=b"undated scan")
        _write(root, conn, key=c_key, input_hash="33" * 32, producer="pandoc",
               version="1", content=b"plain doc")

        a_content_hash = hashlib.sha256(
            b"Date: Mon, 01 Jun 2026 10:00:00 +0000\n\nhi").hexdigest()
        b_content_hash = hashlib.sha256(b"undated scan").hexdigest()

        # Superseded projection over A first (older produced_at, wrong date)…
        _write(root, conn, key="d1" * 32, input_hash=a_content_hash,
               producer="doc_date_email", version="0.0.9",
               content=_doc_date_content("2020-01-01"),
               lineage=[{"cache_key": a_key, "role": "source_text"}])
        time.sleep(0.01)
        # …then the current one (newer): currency must pick this.
        _write(root, conn, key="d2" * 32, input_hash=a_content_hash,
               producer="doc_date_email", version="0.1.0",
               content=_doc_date_content("2026-06-01"),
               lineage=[{"cache_key": a_key, "role": "source_text"}])

        _write(root, conn, key="d3" * 32, input_hash=b_content_hash,
               producer="doc_date", version="0.1.0",
               content=_doc_date_content(None),
               lineage=[{"cache_key": b_key, "role": "source_text"}])
    return a_key, b_key, c_key


def test_project_dates_tri_state_and_currency(migrated_root: Path) -> None:
    a, b, c = _seed(migrated_root)
    with open_catalogue(migrated_root) as conn:
        hits = project_dates(conn, migrated_root, [a, b, c])

    by_key = {h.artifact_cache_key: h for h in hits}
    assert by_key[a] == DatedHit(a, "dated", date(2026, 6, 1), "email")
    assert by_key[b] == DatedHit(b, "undated", None, "docling")
    assert by_key[c] == DatedHit(c, "underived", None, "pandoc")


def test_project_dates_logs_demand(migrated_root: Path) -> None:
    a, b, c = _seed(migrated_root)
    with open_catalogue(migrated_root) as conn:
        project_dates(conn, migrated_root, [a, b, c])

    log_dir = migrated_root / "logs" / "demand"
    entries = [json.loads(line)
               for f in sorted(log_dir.iterdir())
               for line in f.read_text("utf-8").splitlines()]
    by_input = {e["input_cache_key"]: e for e in entries}
    assert by_input[a]["hit"] is True
    assert by_input[b]["hit"] is True
    assert by_input[c]["hit"] is False          # unmet demand — the VOI signal
    assert by_input[c]["cache_key"] == ""        # unresolvable read-side
    assert {e["caller"] for e in entries} == {"ask.temporal"}


def test_apply_temporal_names_indeterminates(migrated_root: Path) -> None:
    """The planted dropout (C) is present and named, never silently dropped."""
    a, b, c = _seed(migrated_root)
    with open_catalogue(migrated_root) as conn:
        hits = project_dates(conn, migrated_root, [a, b, c])

    view = apply_temporal(hits, since=date(2026, 1, 1), until=None,
                          recent=False)
    assert view.admitted == [a]
    assert view.excluded == []
    assert view.undated == [b]
    assert view.underived == [c]
    assert any("pkm derive doc_date_pandoc" in r and c in r
               for r in view.remedies)


def test_apply_temporal_excluded_is_named_with_its_date(
    migrated_root: Path,
) -> None:
    a, b, c = _seed(migrated_root)
    with open_catalogue(migrated_root) as conn:
        hits = project_dates(conn, migrated_root, [a, b, c])

    view = apply_temporal(hits, since=date(2026, 6, 2), until=None,
                          recent=False)
    assert view.admitted == []
    assert view.excluded == [(a, date(2026, 6, 1))]
    assert view.undated == [b]
    assert view.underived == [c]


def test_apply_temporal_recent_ranks_and_drops_nothing(
    migrated_root: Path,
) -> None:
    a, b, c = _seed(migrated_root)
    with open_catalogue(migrated_root) as conn:
        hits = project_dates(conn, migrated_root, [a, b, c])

    view = apply_temporal(hits, since=None, until=None, recent=True)
    assert view.admitted == [a]                  # newest-first (single dated)
    assert view.excluded == []
    assert view.undated == [b]
    assert view.underived == [c]


def test_temporal_view_is_total(migrated_root: Path) -> None:
    """Every input hit appears in exactly one partition — nothing vanishes."""
    a, b, c = _seed(migrated_root)
    with open_catalogue(migrated_root) as conn:
        hits = project_dates(conn, migrated_root, [a, b, c])
    view: TemporalView = apply_temporal(hits, since=date(2026, 1, 1),
                                        until=None, recent=False)
    accounted = (set(view.admitted) | {k for k, _ in view.excluded}
                 | set(view.undated) | set(view.underived))
    assert accounted == {a, b, c}
