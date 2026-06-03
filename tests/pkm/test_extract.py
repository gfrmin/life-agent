"""Integration tests for ``pkm.extract`` — the composition step
(SPEC §7).

These tests exercise the full chain: migrate → ingest → extract,
writing real artifacts to the cache through real producer calls.
Fixtures lean on Pandoc (fast, subprocess) and Unstructured
(~2 s first call, ~0.1 s subsequent) to keep the suite tolerable;
Docling is deliberately not exercised here — its contract is
tested in test_producer_docling.py, and forcing its model load in
every extract run would push the suite over 30 s for questionable
added signal.

Config construction uses the actually-installed producer versions
(discovered at test-collection time via each producer's
``installed_*_version``) so the version check inside the producer
constructors passes; any version drift between the installed
package and a hardcoded test string would be a test-environment
bug, not a pkm bug.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from pkm.catalogue import open_catalogue, run_migrations
from pkm.config import Config, ExtractorConfig
from pkm.extract import ExtractError, ExtractResult, extract
from pkm.ingest import ingest_sources
from pkm.producers.docling import installed_docling_version
from pkm.producers.email_producer import installed_email_version
from pkm.producers.pandoc import installed_pandoc_version
from pkm.producers.unstructured import installed_unstructured_version

# --- Helpers -------------------------------------------------------------


@dataclass(frozen=True)
class _Bench:
    """Shortcut bundle: a migrated root with sources already
    ingested, plus a matching Config object. Each test gets its own
    ``tmp_path``-scoped instance."""

    root: Path
    config: Config
    sources_dir: Path


def _build_config(root: Path) -> Config:
    return Config(
        root_dir=root,
        source=root / "config.yaml",
        extractors={
            "pandoc": ExtractorConfig(
                version=installed_pandoc_version(),
                config={},
            ),
            "docling": ExtractorConfig(
                version=installed_docling_version(),
                config={"ocr": False, "table_structure": True},
            ),
            "unstructured": ExtractorConfig(
                version=installed_unstructured_version(),
                config={"strategy": "auto"},
            ),
            "email": ExtractorConfig(
                version=installed_email_version(),
                config={},
            ),
        },
    )


def _write(path: Path, content: bytes | str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, str):
        path.write_text(content, encoding="utf-8")
    else:
        path.write_bytes(content)
    return path


def _bench(tmp_path: Path, sources: list[tuple[str, bytes | str]]) -> _Bench:
    """Set up a migrated root and ingest the given (relative_path,
    content) pairs. Returns a _Bench ready for ``extract`` calls."""
    root = tmp_path / "knowledge"
    (root / "cache").mkdir(parents=True)
    (root / "logs").mkdir()
    (root / "sources").mkdir()
    run_migrations(root)

    sources_dir = tmp_path / "docs"
    yaml_entries: list[str] = []
    for rel, content in sources:
        p = _write(sources_dir / rel, content)
        yaml_entries.append(f"  - path: {p}\n")
    (root / "sources" / "sources.yaml").write_text(
        "version: 1\nsources:\n" + "".join(yaml_entries),
        encoding="utf-8",
    )

    ingest_sources(root)
    return _Bench(
        root=root, config=_build_config(root), sources_dir=sources_dir
    )


def _artifact_rows(root: Path) -> list[tuple[str, str, str]]:
    with open_catalogue(root) as conn:
        return [
            (input_hash, producer_name, status)
            for input_hash, producer_name, status in conn.execute(
                "SELECT input_hash, producer_name, status FROM artifacts "
                "ORDER BY input_hash, producer_name"
            ).fetchall()
        ]


# --- End-to-end happy path ----------------------------------------------


def test_extract_over_md_and_eml_produces_artifacts(
    tmp_path: Path,
) -> None:
    bench = _bench(
        tmp_path,
        [
            ("note.md", "# Hello\n\nBody text.\n"),
            (
                "mail.eml",
                "From: a@b\nTo: c@d\nSubject: T\n\nBody line.\n",
            ),
        ],
    )

    progress_lines: list[str] = []
    result = extract(
        bench.root,
        bench.config,
        progress=progress_lines.append,
    )

    assert isinstance(result, ExtractResult)
    assert result.total_sources == 2
    assert result.processed == 2
    assert result.succeeded == 2
    assert result.failed == 0
    assert result.cache_hits == 0
    assert not result.interrupted

    rows = _artifact_rows(bench.root)
    producers = {r[1] for r in rows}
    # .eml now routes to the dedicated `email` producer (v0.5.0), not unstructured
    assert producers == {"pandoc", "email"}, rows
    assert all(r[2] == "success" for r in rows)

    assert len(progress_lines) == 2
    assert all(
        "extracted" in line or "cache hit" in line for line in progress_lines
    )


def test_second_extract_is_a_no_op(tmp_path: Path) -> None:
    bench = _bench(
        tmp_path, [("note.md", "# Hello\n\nBody text.\n")]
    )

    extract(bench.root, bench.config)
    rows_before = _artifact_rows(bench.root)

    result = extract(bench.root, bench.config)
    rows_after = _artifact_rows(bench.root)

    assert rows_after == rows_before
    # Routing returned [] so nothing was attempted;
    # cache_hits is zero because we never even asked.
    assert result.succeeded == 0
    assert result.failed == 0
    assert result.cache_hits == 0


# --- retry_failed re-runs failures --------------------------------------


def test_retry_failed_reruns_and_flips_failed_artifact_to_success(
    tmp_path: Path,
) -> None:
    """Force pandoc's artifact into a failed state (simulating a
    prior run that failed), then confirm --retry-failed re-runs
    pandoc and the artifact becomes status=success.

    Without --retry-failed, the routing policy sends the work to
    Docling as a fallback (pandoc failed → Docling runs on .md),
    and pandoc's row stays failed. That behaviour is also
    asserted here as a side-property of the retry-flag check —
    both sides of the flag should be distinguishable."""
    bench = _bench(
        tmp_path, [("note.md", "# Hello\n\nBody.\n")]
    )
    extract(bench.root, bench.config)

    with open_catalogue(bench.root) as conn:
        # Remove chunks first: DuckDB enforces the FK on UPDATE (it treats
        # UPDATE as DELETE+INSERT internally), so artifact_chunks rows must be
        # removed before the artifact status can be overwritten.
        conn.execute(
            "DELETE FROM artifact_chunks WHERE artifact_cache_key IN "
            "(SELECT cache_key FROM artifacts WHERE producer_name = 'pandoc')"
        )
        conn.execute(
            "UPDATE artifacts SET status = 'failed', "
            "error_message = 'simulated', size_bytes = NULL "
            "WHERE producer_name = 'pandoc'"
        )

    # Without retry_failed: routing proposes Docling as fallback
    # (pandoc failed on .md). Pandoc's row stays failed.
    extract(bench.root, bench.config)
    with open_catalogue(bench.root) as conn:
        statuses = {
            r[0]: r[1]
            for r in conn.execute(
                "SELECT producer_name, status FROM artifacts"
            ).fetchall()
        }
    assert statuses["pandoc"] == "failed"

    # With retry_failed: extract deletes the failed row and runs
    # pandoc fresh. The new attempt succeeds; the row flips to
    # status=success.
    result = extract(bench.root, bench.config, retry_failed=True)
    with open_catalogue(bench.root) as conn:
        statuses = {
            r[0]: r[1]
            for r in conn.execute(
                "SELECT producer_name, status FROM artifacts"
            ).fetchall()
        }
    assert statuses["pandoc"] == "success"
    assert result.succeeded >= 1


# --- --source prefix filtering ------------------------------------------


def test_source_prefix_restricts_to_one_source(
    tmp_path: Path,
) -> None:
    bench = _bench(
        tmp_path,
        [
            ("a.md", "# A\n\nFirst document.\n"),
            ("b.md", "# B\n\nSecond document.\n"),
        ],
    )

    # Pick the first source's id and use a 16-char prefix.
    with open_catalogue(bench.root) as conn:
        sids = [
            r[0]
            for r in conn.execute(
                "SELECT source_id FROM sources ORDER BY source_id"
            ).fetchall()
        ]

    target = sids[0]
    result = extract(
        bench.root, bench.config, source_prefix=target[:16]
    )
    assert result.total_sources == 1
    assert result.processed == 1

    # The other source was not processed — no artifact for it.
    rows = _artifact_rows(bench.root)
    assert {r[0] for r in rows} == {target}


def test_source_prefix_shorter_than_16_chars_raises(
    tmp_path: Path,
) -> None:
    bench = _bench(
        tmp_path, [("a.md", "# A\n\n.\n")]
    )
    with pytest.raises(ExtractError, match="at least 16"):
        extract(bench.root, bench.config, source_prefix="abc")


def test_source_prefix_non_hex_raises(tmp_path: Path) -> None:
    bench = _bench(
        tmp_path, [("a.md", "# A\n\n.\n")]
    )
    with pytest.raises(ExtractError, match="hex"):
        extract(
            bench.root,
            bench.config,
            source_prefix="g" * 16,
        )


def test_source_prefix_with_no_match_raises(tmp_path: Path) -> None:
    bench = _bench(
        tmp_path, [("a.md", "# A\n\n.\n")]
    )
    with pytest.raises(ExtractError, match="matched no sources"):
        extract(
            bench.root,
            bench.config,
            source_prefix="f" * 16,
        )


# --- --producer filtering -----------------------------------------------


def test_unknown_producer_name_raises(tmp_path: Path) -> None:
    bench = _bench(
        tmp_path, [("a.md", "# A\n\n.\n")]
    )
    with pytest.raises(ExtractError, match="unknown --producer"):
        extract(
            bench.root,
            bench.config,
            producer_name="pandora",
        )


def test_producer_filter_narrows_to_one_producer(tmp_path: Path) -> None:
    """With --producer email, only the .eml source gets processed; the
    .md doesn't (it routes to Pandoc, which the filter excludes)."""
    bench = _bench(
        tmp_path,
        [
            ("note.md", "# A\n\n.\n"),
            (
                "mail.eml",
                "From: a@b\nTo: c@d\nSubject: T\n\nBody.\n",
            ),
        ],
    )

    result = extract(
        bench.root, bench.config, producer_name="email"
    )
    assert result.succeeded == 1  # only the .eml
    rows = _artifact_rows(bench.root)
    assert len(rows) == 1
    assert rows[0][1] == "email"


# --- Config validation --------------------------------------------------


def test_missing_producer_config_raises_before_any_extraction(
    tmp_path: Path,
) -> None:
    """A corpus with a .md triggers Pandoc; Pandoc's fallback could
    call Docling. Config missing `extractors.docling` should fail
    fast, before any source is processed."""
    bench = _bench(
        tmp_path, [("a.md", "# A\n\n.\n")]
    )
    broken_config = Config(
        root_dir=bench.root,
        source=bench.config.source,
        extractors={
            "pandoc": bench.config.extractors["pandoc"],
            # docling and unstructured missing
        },
    )
    with pytest.raises(ExtractError, match=r"extractors\.docling"):
        extract(bench.root, broken_config)

    # No artifacts produced.
    assert _artifact_rows(bench.root) == []


# --- Empty-corpus edge case ---------------------------------------------


def test_extract_on_empty_source_set_is_a_clean_no_op(
    tmp_path: Path,
) -> None:
    """No sources registered — extract completes without error and
    reports zero work done."""
    root = tmp_path / "knowledge"
    (root / "cache").mkdir(parents=True)
    (root / "logs").mkdir()
    (root / "sources").mkdir()
    run_migrations(root)
    config = _build_config(root)

    result = extract(root, config)
    assert result.total_sources == 0
    assert result.processed == 0
    assert result.succeeded == 0


# --- SIGINT flag semantics (direct, no real signals) --------------------


def test_extract_breaks_out_of_loop_when_stop_is_requested(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The SIGINT handler sets a flag polled between sources. This
    test simulates the flag being set after one source by
    monkeypatching the progress callback to set it.
    """
    bench = _bench(
        tmp_path,
        [
            ("a.md", "# A\n\n.\n"),
            ("b.md", "# B\n\n.\n"),
            ("c.md", "# C\n\n.\n"),
        ],
    )

    # Install a real SIGINT via the running process' own signal
    # machinery: we can't easily send SIGINT from inside pytest, so
    # we instead rely on the progress callback (called after each
    # source) to trigger the same _StopFlag the handler sets.
    import signal

    def progress_and_interrupt(_line: str) -> None:
        # Raise SIGINT ourselves; the handler installed by extract()
        # will flip the stop flag.
        signal.raise_signal(signal.SIGINT)

    result = extract(
        bench.root, bench.config, progress=progress_and_interrupt
    )

    assert result.interrupted
    assert result.processed == 1  # only one source before the signal
    assert result.total_sources == 3


# --- empty_succeeded routing integration (SPEC v0.3.1 §7.3) ------------


@pytest.mark.system
def test_empty_docling_pdf_triggers_tesseract_not_docling(
    tmp_path: Path,
) -> None:
    """A PDF whose cached Docling artifact has texts:[] does not re-run
    Docling; Tesseract runs as fallback via pdftoppm (SPEC v0.3.1 §7.3).

    This is the load-bearing integration claim: source already in
    catalogue as Docling-success-but-empty, re-extracted in a fresh
    pass, triggers only Tesseract. Docling is not invoked again.
    """
    import json
    from unittest.mock import MagicMock, patch

    from pkm.cache import write_artifact
    from pkm.hashing import compute_cache_key
    from pkm.producer import ProducerResult
    from pkm.producers.tesseract import installed_tesseract_version

    # Minimal Docling JSON with zero texts (image-only PDF)
    empty_docling_json = json.dumps({
        "schema_name": "DoclingDocument", "version": "1.0.0",
        "name": "scan", "origin": {}, "furniture": {}, "body": {},
        "groups": [], "texts": [], "pictures": [], "tables": [],
        "key_value_items": [], "form_items": [], "pages": {},
    }).encode()

    # Build bench with a dummy .pdf source
    pdf_content = b"%PDF-1.4 stub"
    bench = _bench(tmp_path, [("scan.pdf", pdf_content)])

    # Get the ingested source_id
    with open_catalogue(bench.root) as conn:
        source_id = conn.execute("SELECT source_id FROM sources").fetchone()[0]

    # Compute Docling's cache key for this source
    from pkm.producers.docling import installed_docling_version
    docling_version = installed_docling_version()
    docling_config = {"ocr": False, "table_structure": True}
    docling_cache_key = compute_cache_key(
        source_id, "docling", docling_version, docling_config
    )

    # Write a fake Docling-success artifact with empty texts
    with open_catalogue(bench.root) as conn:
        write_artifact(
            bench.root, conn,
            cache_key=docling_cache_key,
            input_hash=source_id,
            producer_name="docling",
            producer_version=docling_version,
            producer_config=docling_config,
            result=ProducerResult(
                status="success",
                content=empty_docling_json,
                content_type="application/x-docling-json",
                content_encoding="utf-8",
                error_message=None,
                producer_metadata={},
            ),
        )

    # Build config that includes tesseract
    tesseract_version = installed_tesseract_version()
    config_with_tesseract = Config(
        root_dir=bench.root,
        source=bench.config.source,
        extractors={
            **bench.config.extractors,
            "tesseract": ExtractorConfig(
                version=tesseract_version,
                config={"languages": "heb+eng", "psm": 3, "oem": 3},
            ),
        },
    )

    tesseract_produce_calls: list[str] = []

    def fake_subprocess_run(cmd, **kwargs):
        if cmd[0] == "tesseract" and "--version" in cmd:
            m = MagicMock()
            m.stdout = f"tesseract {tesseract_version}\n"
            m.stderr = ""
            m.returncode = 0
            return m
        if cmd[0] == "pdftoppm":
            # Write one fake page image
            prefix = cmd[-1]
            (tmp_path / "page-01.ppm").write_bytes(b"P6\n1 1\n255\n\x00\x00\x00")
            import shutil
            shutil.copy(tmp_path / "page-01.ppm", Path(prefix).parent / "page-01.ppm")
            m = MagicMock()
            m.stdout = b""
            m.stderr = b""
            m.returncode = 0
            return m
        if cmd[0] == "tesseract":
            # Record that Tesseract was called for OCR (not --version)
            tesseract_produce_calls.append(str(cmd[1]))
            m = MagicMock()
            m.stdout = b"AB1234567 expires 2099-06-30\n"  # PII-OK: synthetic OCR output
            m.stderr = b""
            m.returncode = 0
            return m
        raise ValueError(f"unexpected command: {cmd!r}")

    with patch("subprocess.run", side_effect=fake_subprocess_run):
        extract(bench.root, config_with_tesseract)

    # Tesseract must have been invoked (at least one page OCR call)
    assert tesseract_produce_calls, (
        "Tesseract was never called — empty_succeeded routing failed"
    )

    # Docling must NOT have been invoked again (already succeeded)
    with open_catalogue(bench.root) as conn:
        artifact_rows = conn.execute(
            "SELECT producer_name, status FROM artifacts ORDER BY producer_name"
        ).fetchall()

    producers_run = {name for name, _ in artifact_rows}
    assert "tesseract" in producers_run, "No Tesseract artifact written"
    # Docling appears exactly once (the seeded artifact, not re-run)
    docling_rows = [(n, s) for n, s in artifact_rows if n == "docling"]
    assert len(docling_rows) == 1
    assert docling_rows[0][1] == "success"  # original seeded artifact unchanged
