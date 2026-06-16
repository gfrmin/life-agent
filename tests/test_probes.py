"""life_agent.core.probes — the probe library the answer-brain selects by VOI.

Each probe pairs an impure projection edge with a pure mapping core; the pure cores
carry the logic and are tested hermetically here, the edges get one wiring test each
(mirroring test_temporal / test_subject). The load-bearing contract: every
``subject_state`` / ``doc_date`` a probe emits must be a value the observation kernel
accepts (``lookup.subject_factor`` / ``lookup.time_factor``) — asserted directly, so a
probe that drifts out of the kernel's partition fails here, not in production.
"""
from __future__ import annotations

import json
import time
from datetime import date
from hashlib import sha256
from pathlib import Path
from typing import Any

import duckdb
import pytest

from life_agent.core.lookup import subject_factor, time_factor
from life_agent.core.probes import (
    _date_from_email_text,
    _fresh_hits,
    _recency_covariate,
    _subject_covariate,
    probe_authority,
    probe_recency,
    probe_subject,
)
from life_agent.core.subject import SubjectedHit
from life_agent.core.temporal import DatedHit
from pkm.cache import write_artifact
from pkm.catalogue import open_catalogue, run_migrations
from pkm.producer import ProducerResult
from pkm.transform import ModelResponse

# --- fixtures + helpers (module-local, as the sibling test trees define them) ---------


@pytest.fixture
def migrated_root(tmp_path: Path) -> Path:
    (tmp_path / "cache").mkdir()
    (tmp_path / "logs").mkdir()
    run_migrations(tmp_path)
    return tmp_path


def _success(content: bytes) -> ProducerResult:
    return ProducerResult(
        status="success", content=content, content_type="text/plain",
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


# --- recency probe: doc_date covariate (pure core + wiring) ---------------------------


def test_recency_covariate_maps_state_to_kernel_input() -> None:
    """dated → its ISO date; undated/underived → None (the probe projected, so an absent
    date is "projected but unknown", the kernel's stated attenuation — not "untouched")."""
    dated = [
        DatedHit("a", "dated", date(2026, 6, 1), "email"),
        DatedHit("b", "undated", None, "docling"),
        DatedHit("c", "underived", None, "pandoc"),
    ]
    cov = _recency_covariate(dated)
    assert cov == {"a": "2026-06-01", "b": None, "c": None}
    # contract: every emitted doc_date is a value time_factor accepts (no raise)
    for iso in cov.values():
        time_factor(iso, time_indexed=True)


def test_date_from_email_text_parses_the_header_block() -> None:
    """Pure: the ISO date from the rendered ``Date:`` header (first block); None when the
    header is absent or unparseable, and the body is never mistaken for the header."""
    assert _date_from_email_text(
        "Date: Mon, 01 Jun 2026 10:00:00 +0000\nFrom: a@b\n\nbody") == "2026-06-01"
    assert _date_from_email_text("From: a@b\nSubject: hi\n\nno date here") is None
    assert _date_from_email_text("Date: not-a-real-date\n\nbody") is None
    # a "Date:" in the BODY (after the blank line) is not the header — ignored
    assert _date_from_email_text("From: a@b\n\nDate: Tue, 02 Jul 2024 00:00:00") is None


def test_probe_recency_fills_email_gap_from_header(migrated_root: Path) -> None:
    """The fallback: an email hit the projection left dateless is filled from its Date
    header; a projected date still wins over the header; and a NON-email doc that merely
    starts 'Date:' is left alone (None) — the fallback is email-only, read-only."""
    e, p, a = "ee" * 32, "ff" * 32, "aa" * 32
    e_body = b"Date: Tue, 02 Jul 2024 09:00:00 +0000\nFrom: x@y\n\nhello"
    p_body = b"Date: 2099-12-31 is a heading in this PDF\n\nnot an email"
    a_body = b"Date: Wed, 01 Jan 2020 00:00:00 +0000\n\nstale header, fresh projection"
    with open_catalogue(migrated_root) as conn:
        _write(migrated_root, conn, key=e, input_hash="11" * 32, producer="email",
               version="1", content=e_body)
        _write(migrated_root, conn, key=p, input_hash="22" * 32, producer="pandoc",
               version="1", content=p_body)
        _write(migrated_root, conn, key=a, input_hash="33" * 32, producer="email",
               version="1", content=a_body)
        a_hash = sha256(a_body).hexdigest()
        _write(migrated_root, conn, key="d1" * 32, input_hash=a_hash,
               producer="doc_date_email", version="0.1.0",
               content=json.dumps({"format_version": 1, "date": "2026-06-01"}).encode(),
               lineage=[{"cache_key": a, "role": "source_text"}])
        cov = probe_recency(conn, migrated_root, [e, p, a])
    assert cov == {e: "2024-07-02", p: None, a: "2026-06-01"}


def test_probe_recency_projects_current_date(migrated_root: Path) -> None:
    """Wiring: project the CURRENT doc_date (currency picks the newer of two) onto each
    hit, read-only."""
    a, b, c = "aa" * 32, "bb" * 32, "cc" * 32
    with open_catalogue(migrated_root) as conn:
        _write(migrated_root, conn, key=a, input_hash="11" * 32, producer="email",
               version="1", content=b"Date: Mon, 01 Jun 2026 10:00:00 +0000\n\nhi")
        _write(migrated_root, conn, key=b, input_hash="22" * 32, producer="docling",
               version="1", content=b"undated scan")
        _write(migrated_root, conn, key=c, input_hash="33" * 32, producer="pandoc",
               version="1", content=b"plain doc")
        a_hash = sha256(b"Date: Mon, 01 Jun 2026 10:00:00 +0000\n\nhi").hexdigest()
        b_hash = sha256(b"undated scan").hexdigest()
        _write(migrated_root, conn, key="d1" * 32, input_hash=a_hash,
               producer="doc_date_email", version="0.0.9",
               content=json.dumps({"format_version": 1, "date": "2020-01-01"}).encode(),
               lineage=[{"cache_key": a, "role": "source_text"}])
        time.sleep(0.01)
        _write(migrated_root, conn, key="d2" * 32, input_hash=a_hash,
               producer="doc_date_email", version="0.1.0",
               content=json.dumps({"format_version": 1, "date": "2026-06-01"}).encode(),
               lineage=[{"cache_key": a, "role": "source_text"}])
        _write(migrated_root, conn, key="d3" * 32, input_hash=b_hash,
               producer="doc_date", version="0.1.0",
               content=json.dumps({"format_version": 1, "date": None}).encode(),
               lineage=[{"cache_key": b, "role": "source_text"}])
        cov = probe_recency(conn, migrated_root, [a, b, c])
    assert cov == {a: "2026-06-01", b: None, c: None}  # currency picked the newer


# --- authority probe: declared source-authority class per origin (pure) ---------------


def test_authority_is_the_declared_class_per_origin() -> None:
    hits = [
        {"artifact_cache_key": "k_pdf", "origin": "/tmp/docs/bill.pdf"},
        {"artifact_cache_key": "k_eml", "origin": "/tmp/x/signature.eml"},
        {"artifact_cache_key": "k_mail", "origin": "/tmp/mail/cur/9.txt"},
        {"artifact_cache_key": "k_md", "origin": "/tmp/notes/jot.md"},
        {"artifact_cache_key": "k_other", "origin": "/tmp/scans/photo.png"},
    ]
    auth = probe_authority(hits)
    assert auth["k_pdf"] == ("document", 0.95)
    assert auth["k_eml"] == ("email", 0.90)
    assert auth["k_mail"] == ("email", 0.90)   # a maildir path is email even as .txt
    assert auth["k_md"] == ("note", 0.80)
    assert auth["k_other"] == ("other", 0.85)  # the stated default


# --- subject probe: whose-document covariate (pure core + wiring) ---------------------


def _sub(key: str, state: str, *, subject: str | None = None,
         kind: str | None = None, extractor: str = "pandoc") -> SubjectedHit:
    return SubjectedHit(artifact_cache_key=key, state=state,  # type: ignore[arg-type]
                        subject_kind=kind, subject=subject, extractor=extractor)


def test_subject_covariate_partition_and_kernel_contract() -> None:
    """The probe WEIGHTS, never filters: a not_owner hit becomes the 'other' covariate
    (down-weighted), it is NOT dropped. Indeterminates (unclear / missing verdict / named
    with no subject) → 'unclear'. Every emitted state is one subject_factor accepts."""
    subs = [
        _sub("owner", "named", subject="J. Example", kind="person"),
        _sub("other", "named", subject="Someone Else", kind="person"),
        _sub("unclear", "named", subject="Ambiguous", kind="person"),
        _sub("novote", "named", subject="No Verdict", kind="person"),
        _sub("noname", "named", subject=None, kind="person"),
        _sub("generic", "generic"),
        _sub("underiv", "underived", extractor="tesseract"),
    ]
    verdict_of = {"J. Example": "owner", "Someone Else": "not_owner",
                  "Ambiguous": "unclear"}  # "No Verdict" deliberately absent
    cov = _subject_covariate(subs, verdict_of)
    assert cov == {
        "owner": "owner", "other": "other", "unclear": "unclear",
        "novote": "unclear", "noname": "unclear",
        "generic": "generic", "underiv": "underived",
    }
    # the not_owner truth is re-weighted, not deleted (the finding's whole point)
    assert "other" in cov
    # contract: every emitted state is a value subject_factor accepts (no raise)
    for state in cov.values():
        subject_factor(state)


class _FakeVerdictClient:
    engine_version = "fake-1"

    def __init__(self, verdict: str) -> None:
        self._verdict = verdict
        self.calls = 0

    def complete(self, prompt: str, schema: dict[str, Any]) -> ModelResponse:
        self.calls += 1
        return ModelResponse(raw_text=json.dumps({"verdict": self._verdict}),
                             input_tokens=1, output_tokens=1, latency_ms=1,
                             cost_usd=0.0)


def test_probe_subject_projects_classifies_and_caches(migrated_root: Path) -> None:
    """Wiring: project doc_subject + classify the named subject once (cached), map to the
    covariate. C (no projection) stays as 'underived' — named, never dropped."""
    a, b, c = "aa" * 32, "bb" * 32, "cc" * 32
    with open_catalogue(migrated_root) as conn:
        _write(migrated_root, conn, key=a, input_hash="11" * 32, producer="tesseract",
               version="1", content=b"id card scan")
        _write(migrated_root, conn, key=b, input_hash="22" * 32, producer="pandoc",
               version="1", content=b"blank form")
        _write(migrated_root, conn, key=c, input_hash="33" * 32, producer="docling",
               version="1", content=b"plain doc")
        a_hash = sha256(b"id card scan").hexdigest()
        b_hash = sha256(b"blank form").hexdigest()
        _write(migrated_root, conn, key="d2" * 32, input_hash=a_hash,
               producer="doc_subject", version="0.1.0",
               content=json.dumps({"format_version": 1, "subject_kind": "person",
                                   "subject": "J. Example"}).encode(),
               lineage=[{"cache_key": a, "role": "source_text"}])
        _write(migrated_root, conn, key="d3" * 32, input_hash=b_hash,
               producer="doc_subject", version="0.1.0",
               content=json.dumps({"format_version": 1, "subject_kind": "generic",
                                   "subject": None}).encode(),
               lineage=[{"cache_key": b, "role": "source_text"}])
        client = _FakeVerdictClient("owner")
        cov = probe_subject(conn, migrated_root, [a, b, c],
                            profile="Name: J. Example", client=client)
    assert cov == {a: "owner", b: "generic", c: "underived"}


# --- corroborate probe: independent-document filter (pure core) -----------------------


def test_fresh_hits_drops_documents_already_held() -> None:
    """Corroboration counts only INDEPENDENT new documents — a chunk of a doc we already
    have adds no independent evidence, so it is dropped."""
    hits = [
        {"artifact_cache_key": "held", "chunk_text": "x", "score": 9.0, "origin": "a"},
        {"artifact_cache_key": "new", "chunk_text": "y", "score": 8.0, "origin": "b"},
    ]
    fresh = _fresh_hits(hits, exclude_keys={"held"})
    assert [h["artifact_cache_key"] for h in fresh] == ["new"]
