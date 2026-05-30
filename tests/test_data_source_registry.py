"""Unit tests for the declarative data-source registry (scripts/data_source_registry.py).

Run in the pkm env (has pytest, PyYAML, and the pkm producers):
    uv run --project ~/git/pkm python -m pytest ~/git/life-agent/tests/test_data_source_registry.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from data_source_registry import (  # noqa: E402
    Registry,
    RegistryError,
    Root,
    Row,
    _matches,
    aggregate,
    classify,
    ingestable_formats,
    load_registry,
)

VALID = """\
version: 1
roots:
  - id: notes
    kind: filetree
    path: /data/notes
    include: ["**/*.md"]
    tags: [notes]
  - id: photos
    kind: filetree
    path: /data/photoprism
    enabled: false
  - id: mail
    kind: maildir
    path: /data/mail
    include: [INBOX]
    staging_dir: /tmp/staging/mail
    tags: [email]
"""


def _write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "data-sources.yaml"
    p.write_text(text, encoding="utf-8")
    return p


# --- load_registry -------------------------------------------------------- #


def test_load_valid_registry(tmp_path: Path) -> None:
    reg = load_registry(_write(tmp_path, VALID))
    assert isinstance(reg, Registry)
    assert [r.id for r in reg.roots] == ["notes", "photos", "mail"]

    notes = reg.roots[0]
    assert notes.kind == "filetree"
    assert notes.path == Path("/data/notes")
    assert notes.include == ("**/*.md",)
    assert notes.tags == ("notes",)
    assert notes.enabled is True  # default

    assert reg.roots[1].enabled is False  # explicit
    assert reg.roots[2].staging_dir == Path("/tmp/staging/mail")


def test_missing_file_fails(tmp_path: Path) -> None:
    with pytest.raises(RegistryError, match="not found"):
        load_registry(tmp_path / "nope.yaml")


@pytest.mark.parametrize(
    "text, match",
    [
        ("version: 2\nroots: [{id: a, kind: filetree, path: /x}]\n", "version: 1"),
        ("version: 1\nroots: []\n", "non-empty `roots`"),
        ("version: 1\nroots:\n  - {id: a, kind: bogus, path: /x}\n", "unknown kind"),
        ("version: 1\nroots:\n  - {id: a, kind: filetree}\n", "required string field 'path'"),
        (
            "version: 1\nroots:\n"
            "  - {id: dup, kind: filetree, path: /x}\n"
            "  - {id: dup, kind: filetree, path: /y}\n",
            "duplicate root id",
        ),
    ],
)
def test_malformed_registry_fails(tmp_path: Path, text: str, match: str) -> None:
    with pytest.raises(RegistryError, match=match):
        load_registry(_write(tmp_path, text))


# --- _matches (include/exclude globs) ------------------------------------- #


def test_matches_empty_include_is_all() -> None:
    assert _matches("a/b/c.pdf", (), ()) is True


def test_matches_include_filters() -> None:
    assert _matches("a/b/note.md", ("*.md",), ()) is True
    assert _matches("a/b/scan.png", ("*.md",), ()) is False


def test_matches_double_star_includes_top_level() -> None:
    # `**/*.md` must match a flat (top-level) file, not only nested ones.
    assert _matches("note.md", ("**/*.md",), ()) is True
    assert _matches("sub/note.md", ("**/*.md",), ()) is True
    assert _matches("note.txt", ("**/*.md",), ()) is False


def test_matches_exclude_overrides() -> None:
    assert _matches("Archive/x/git/log.md", ("*.md",), ("*/git/*",)) is False
    assert _matches("Archive/x/notes/log.md", ("*.md",), ("*/git/*",)) is True


# --- classify ------------------------------------------------------------- #


def test_classify_uses_fmt_map() -> None:
    fmt = {".pdf": "docling", ".md": "pandoc"}
    assert classify(Path("/x/a.PDF"), fmt) == (".pdf", "docling", True)
    assert classify(Path("/x/a.md"), fmt) == (".md", "pandoc", True)
    assert classify(Path("/x/a.xyz"), fmt) == (".xyz", None, False)


def test_ingestable_formats_reflects_real_pkm_producers() -> None:
    fmt = ingestable_formats()
    # Capabilities that exist today (TesseractProducer is landed -> images ingest).
    for ext in (".pdf", ".md", ".docx", ".jpg", ".png", ".eml", ".txt"):
        assert ext in fmt, f"{ext} should be ingestable"
    assert ".sqlite" not in fmt and ".heic" not in fmt  # no producer yet


# --- aggregate ------------------------------------------------------------ #


def test_aggregate_counts_and_bytes() -> None:
    root = Root("docs", "filetree", Path("/data/dropbox/documents"), (), (), ("documents",), True, None)
    rows = [
        Row("docs", "/x/a.pdf", ".pdf", 100, "docling", True),
        Row("docs", "/x/b.pdf", ".pdf", 200, "docling", True),
        Row("docs", "/x/c.heic", ".heic", 50, None, False),
    ]
    s = aggregate(root, rows)
    assert s.files == 3
    assert s.bytes == 350
    assert s.ingestable_files == 2
    assert s.ingestable_bytes == 300
    assert s.by_ext == {".pdf": 2, ".heic": 1}  # descending by count


# --- merge_entries (ingest_sources) --------------------------------------- #


def test_merge_entries_dedupes_and_unions_tags() -> None:
    from ingest_sources import merge_entries  # noqa: E402

    existing = [{"path": "/x/a.pdf"}, {"path": "/x/b.pdf", "tags": ["documents"]}]
    new = [
        {"path": "/x/b.pdf", "tags": ["legal"]},  # dup path -> union tags
        {"path": "/x/c.md", "tags": ["notes"]},  # genuinely new
        {"path": "/staging/mail", "tags": ["email"], "recursive": True},
    ]
    merged = merge_entries(existing, new)
    paths = [e["path"] for e in merged]
    assert paths == ["/x/a.pdf", "/x/b.pdf", "/x/c.md", "/staging/mail"]  # existing first
    b = next(e for e in merged if e["path"] == "/x/b.pdf")
    assert b["tags"] == ["documents", "legal"]  # unioned, sorted
    mail = next(e for e in merged if e["path"] == "/staging/mail")
    assert mail["recursive"] is True
