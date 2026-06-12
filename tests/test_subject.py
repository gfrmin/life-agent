"""life_agent.core.subject — read-side doc_subject projection + owner filter (D2).

The hermetic form of the D2 gate: a hit whose subject classification is
absent or unclear is NAMED as indeterminate (with reason and remedy) and
stays in the synthesis context — never silently excluded; only hits
*determinately* about someone else, or determinately about nobody (generic:
templates, blank forms), are excluded — each named. The planted dropout is
artifact C — retrieved, but with no doc_subject artifact derived.

The owner-match verdict is a cached §18.9 derivation: same (subject,
profile) never calls the model twice; the profile hash is in the key, so a
profile edit invalidates exactly the verdicts.
"""

from __future__ import annotations

import json
import time
from hashlib import sha256
from pathlib import Path
from typing import Any

import duckdb
import pytest

from life_agent.core.subject import (
    SubjectedHit,
    apply_owner_filter,
    owner_verdict,
    project_subjects,
)
from pkm.cache import write_artifact
from pkm.catalogue import open_catalogue, run_migrations
from pkm.producer import ProducerResult
from pkm.transform import ModelResponse


@pytest.fixture
def migrated_root(tmp_path: Path) -> Path:
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


def _subject_content(kind: str, subject: str | None) -> bytes:
    return json.dumps({"format_version": 1, "subject_kind": kind,
                       "subject": subject}).encode("utf-8")


def _seed(root: Path) -> tuple[str, str, str]:
    """Three extractor artifacts: A (tesseract, person — with a superseded
    older projection), B (pandoc, generic), C (docling, NO projection at
    all). Returns (A, B, C) cache keys."""
    a_key, b_key, c_key = "aa" * 32, "bb" * 32, "cc" * 32
    with open_catalogue(root) as conn:
        _write(root, conn, key=a_key, input_hash="11" * 32,
               producer="tesseract", version="1", content=b"id card scan")
        _write(root, conn, key=b_key, input_hash="22" * 32,
               producer="pandoc", version="1", content=b"blank form")
        _write(root, conn, key=c_key, input_hash="33" * 32,
               producer="docling", version="1", content=b"plain doc")

        a_hash = sha256(b"id card scan").hexdigest()
        b_hash = sha256(b"blank form").hexdigest()

        # Superseded projection over A first (older, wrong subject)…
        _write(root, conn, key="d1" * 32, input_hash=a_hash,
               producer="doc_subject", version="0.0.9",
               content=_subject_content("person", "Wrong Earlier Name"),
               lineage=[{"cache_key": a_key, "role": "source_text"}])
        time.sleep(0.01)
        # …then the current one (newer): currency must pick this.
        _write(root, conn, key="d2" * 32, input_hash=a_hash,
               producer="doc_subject", version="0.1.0",
               content=_subject_content("person", "J. Example"),
               lineage=[{"cache_key": a_key, "role": "source_text"}])

        _write(root, conn, key="d3" * 32, input_hash=b_hash,
               producer="doc_subject", version="0.1.0",
               content=_subject_content("generic", None),
               lineage=[{"cache_key": b_key, "role": "source_text"}])
    return a_key, b_key, c_key


# --- project_subjects: tri-state + currency --------------------------------- #


def test_project_subjects_tri_state_and_currency(migrated_root: Path) -> None:
    a, b, c = _seed(migrated_root)
    with open_catalogue(migrated_root) as conn:
        hits = project_subjects(conn, migrated_root, [a, b, c])
    by_key = {h.artifact_cache_key: h for h in hits}
    assert by_key[a].state == "named"
    assert by_key[a].subject == "J. Example"  # currency picked the newer
    assert by_key[a].subject_kind == "person"
    assert by_key[b].state == "generic"
    assert by_key[c].state == "underived"
    assert by_key[c].extractor == "docling"


def test_project_subjects_empty_input(migrated_root: Path) -> None:
    with open_catalogue(migrated_root) as conn:
        assert project_subjects(conn, migrated_root, []) == []


# --- apply_owner_filter: total partition, indeterminates stay in ------------ #


def _hit(key: str, state: str, *, kind: str | None = None,
         subject: str | None = None, extractor: str = "pandoc") -> SubjectedHit:
    return SubjectedHit(artifact_cache_key=key, state=state,  # type: ignore[arg-type]
                        subject_kind=kind, subject=subject, extractor=extractor)


def test_owner_filter_partition_is_total_and_nothing_silent() -> None:
    hits = [
        _hit("a" * 64, "named", kind="person", subject="J. Example"),
        _hit("b" * 64, "named", kind="person", subject="Other Person"),
        _hit("c" * 64, "named", kind="organisation", subject="Example LLC"),
        _hit("d" * 64, "generic"),
        _hit("e" * 64, "named", kind="person", subject="Hard To Say"),
        _hit("f" * 64, "underived", extractor="tesseract"),
    ]
    verdicts = {"J. Example": "owner", "Other Person": "not_owner",
                "Example LLC": "not_owner", "Hard To Say": "unclear"}
    view = apply_owner_filter(hits, verdicts)

    assert "a" * 64 in view.admitted
    # Determinately someone else's: excluded, named with the subject as written.
    assert ("b" * 64, "Other Person") in view.excluded_other
    assert ("c" * 64, "Example LLC") in view.excluded_other
    # Determinately nobody's (template/blank): excluded, named.
    assert view.excluded_generic == ["d" * 64]
    # Indeterminates are ADMITTED and named — never silently excluded (the gate).
    assert "e" * 64 in view.admitted and view.unclear == ["e" * 64]
    assert "f" * 64 in view.admitted and view.underived == ["f" * 64]
    assert view.remedies == ["pkm derive doc_subject_tesseract --input " + "f" * 64]

    # Totality: every hit lands in exactly one named set.
    named_sets = (
        [k for k in view.admitted if k not in view.unclear
         and k not in view.underived]
        + [k for k, _ in view.excluded_other]
        + view.excluded_generic + view.unclear + view.underived
    )
    assert sorted(named_sets) == sorted(h.artifact_cache_key for h in hits)


def test_owner_filter_missing_verdict_is_indeterminate() -> None:
    """A named subject with no verdict (match failed/skipped) is indeterminate
    — admitted and named, never dropped."""
    hits = [_hit("a" * 64, "named", kind="person", subject="J. Example")]
    view = apply_owner_filter(hits, {})
    assert view.admitted == ["a" * 64]
    assert view.unclear == ["a" * 64]


# --- owner_verdict: cached §18.9 derivation --------------------------------- #


class _FakeClient:
    engine_version = "fake-1"

    def __init__(self, verdict: str) -> None:
        self._verdict = verdict
        self.calls = 0

    def complete(self, prompt: str, schema: dict[str, Any]) -> ModelResponse:
        self.calls += 1
        return ModelResponse(raw_text=json.dumps({"verdict": self._verdict}),
                             input_tokens=1, output_tokens=1, latency_ms=1,
                             cost_usd=0.0)


def test_owner_verdict_is_cached(migrated_root: Path) -> None:
    client = _FakeClient("owner")
    profile = "Name: J. Example (also J. Ex)"
    v1 = owner_verdict(migrated_root, "J. Example", profile, client=client)
    v2 = owner_verdict(migrated_root, "J. Example", profile, client=client)
    assert (v1, v2) == ("owner", "owner")
    assert client.calls == 1  # second call replayed from the cache


def test_owner_verdict_profile_edit_invalidates(migrated_root: Path) -> None:
    client = _FakeClient("owner")
    owner_verdict(migrated_root, "J. Example", "profile v1", client=client)
    owner_verdict(migrated_root, "J. Example", "profile v2", client=client)
    assert client.calls == 2  # the profile hash is in the key


def test_owner_verdict_junk_fails_loudly_and_is_not_cached(
    migrated_root: Path,
) -> None:
    client = _FakeClient("maybe")
    with pytest.raises(ValueError, match="maybe"):
        owner_verdict(migrated_root, "J. Example", "p", client=client)
    # Never frozen: a good client afterwards gets a fresh call, not a replay.
    good = _FakeClient("not_owner")
    assert owner_verdict(migrated_root, "J. Example", "p", client=good) == "not_owner"
    assert good.calls == 1
