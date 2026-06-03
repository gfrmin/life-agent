"""Tests for ``pkm.ingest`` — sources.yaml → sources / source_paths
(SPEC §8.1, §8.2, §13.2, §13.4).
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import pytest
import yaml

from pkm.catalogue import open_catalogue
from pkm.ingest import IngestError, IngestResult, ingest_sources

# --- Helpers --------------------------------------------------------------


def _write_sources_yaml(root: Path, entries: list[dict[str, Any]]) -> Path:
    path = root / "sources" / "sources.yaml"
    path.write_text(
        yaml.safe_dump({"version": 1, "sources": entries}),
        encoding="utf-8",
    )
    return path


def _write_file(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _count_sources(root: Path) -> int:
    with open_catalogue(root) as conn:
        (n,) = conn.execute("SELECT COUNT(*) FROM sources").fetchone()
    return int(n)


def _count_source_paths(root: Path) -> int:
    with open_catalogue(root) as conn:
        (n,) = conn.execute("SELECT COUNT(*) FROM source_paths").fetchone()
    return int(n)


def _tags_for(root: Path, source_id: str) -> list[str]:
    with open_catalogue(root) as conn:
        rows = conn.execute(
            "SELECT tag FROM source_tags WHERE source_id = ? ORDER BY tag",
            [source_id],
        ).fetchall()
    return [r[0] for r in rows]


# --- Positive cases -------------------------------------------------------


def test_ingest_single_file_creates_source_and_path(
    migrated_root: Path, tmp_path: Path,
) -> None:
    src = tmp_path / "doc.txt"
    _write_file(src, b"hello")
    _write_sources_yaml(migrated_root, [{"path": str(src), "tags": ["note"]}])

    result = ingest_sources(migrated_root)
    assert isinstance(result, IngestResult)
    assert result.scanned == 1
    assert result.ingested == 1
    assert result.new_sources == 1
    assert result.new_paths == 1
    assert result.skipped == []

    # sha256("hello") is a stable value — pin it to catch any drift in
    # how the hasher is fed. Matches hashlib.sha256(b"hello").hexdigest().
    expected_sid = (
        "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    )
    with open_catalogue(migrated_root) as conn:
        row = conn.execute(
            "SELECT source_id, current_path, size_bytes, mime_type "
            "FROM sources"
        ).fetchone()
    assert row is not None
    assert row[0] == expected_sid
    # v0.4.0: the stored path is the declared one (abspath, symlinks not
    # dereferenced — §8.2). For a plain file this equals its abspath.
    assert row[1] == os.path.abspath(src)
    assert row[2] == 5
    # mime_type from stdlib mimetypes.guess_type("doc.txt") → "text/plain"
    assert row[3] == "text/plain"
    assert _tags_for(migrated_root, expected_sid) == ["note"]


def test_ingest_is_idempotent_on_row_counts(
    migrated_root: Path, tmp_path: Path,
) -> None:
    src = tmp_path / "doc.txt"
    _write_file(src, b"hello")
    _write_sources_yaml(migrated_root, [{"path": str(src)}])

    r1 = ingest_sources(migrated_root)
    assert r1.new_sources == 1
    assert r1.new_paths == 1

    r2 = ingest_sources(migrated_root)
    assert r2.new_sources == 0
    assert r2.new_paths == 0
    # The source is re-observed (last_seen is bumped) — "ingested"
    # counts observations, not new rows.
    assert r2.ingested == 1
    assert _count_sources(migrated_root) == 1
    assert _count_source_paths(migrated_root) == 1


def test_ingest_updates_last_seen_and_preserves_first_seen(
    migrated_root: Path, tmp_path: Path,
) -> None:
    src = tmp_path / "doc.txt"
    _write_file(src, b"hello")
    _write_sources_yaml(migrated_root, [{"path": str(src)}])

    ingest_sources(migrated_root)
    with open_catalogue(migrated_root) as conn:
        first_seen_1, last_seen_1 = conn.execute(
            "SELECT first_seen, last_seen FROM sources"
        ).fetchone()

    time.sleep(0.01)  # let the wall clock move

    ingest_sources(migrated_root)
    with open_catalogue(migrated_root) as conn:
        first_seen_2, last_seen_2 = conn.execute(
            "SELECT first_seen, last_seen FROM sources"
        ).fetchone()

    assert first_seen_2 == first_seen_1
    assert last_seen_2 >= last_seen_1


def test_ingest_moved_file_keeps_source_id_and_adds_path(
    migrated_root: Path, tmp_path: Path,
) -> None:
    src_a = tmp_path / "a.txt"
    _write_file(src_a, b"hello")
    _write_sources_yaml(migrated_root, [{"path": str(src_a)}])
    ingest_sources(migrated_root)

    src_b = tmp_path / "b.txt"
    _write_file(src_b, b"hello")
    src_a.unlink()
    _write_sources_yaml(migrated_root, [{"path": str(src_b)}])

    r = ingest_sources(migrated_root)
    assert r.new_sources == 0
    assert r.new_paths == 1

    with open_catalogue(migrated_root) as conn:
        (current_path,) = conn.execute(
            "SELECT current_path FROM sources"
        ).fetchone()
        paths = [
            row[0]
            for row in conn.execute(
                "SELECT path FROM source_paths ORDER BY path"
            ).fetchall()
        ]
    assert current_path == os.path.abspath(src_b)
    assert paths == sorted([os.path.abspath(src_a), os.path.abspath(src_b)])


def test_ingest_recursive_directory_walks_files_and_inherits_tags(
    migrated_root: Path, tmp_path: Path,
) -> None:
    dir_ = tmp_path / "mydocs"
    _write_file(dir_ / "a.txt", b"aaa")
    _write_file(dir_ / "sub" / "b.txt", b"bbb")
    _write_sources_yaml(
        migrated_root,
        [{"path": str(dir_), "tags": ["docs"], "recursive": True}],
    )

    r = ingest_sources(migrated_root)
    assert r.scanned == 2
    assert r.ingested == 2
    assert r.new_sources == 2

    with open_catalogue(migrated_root) as conn:
        sids = [
            row[0]
            for row in conn.execute("SELECT source_id FROM sources").fetchall()
        ]
        # Every source has exactly the inherited tag.
        per_source = conn.execute(
            "SELECT source_id, tag FROM source_tags ORDER BY source_id, tag"
        ).fetchall()
    assert len(sids) == 2
    assert sorted((s, "docs") for s in sids) == sorted(per_source)


def test_ingest_dedupes_identical_content_at_different_paths(
    migrated_root: Path, tmp_path: Path,
) -> None:
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    _write_file(a, b"hello")
    _write_file(b, b"hello")
    _write_sources_yaml(
        migrated_root, [{"path": str(a)}, {"path": str(b)}]
    )

    r = ingest_sources(migrated_root)
    assert r.scanned == 2
    assert r.ingested == 2
    assert r.new_sources == 1
    assert r.new_paths == 2
    assert _count_sources(migrated_root) == 1
    assert _count_source_paths(migrated_root) == 2


# --- §13.4 skip-and-continue tests ---------------------------------------


def test_ingest_missing_file_is_skipped_and_logged(
    migrated_root: Path,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    missing = tmp_path / "no_such.txt"
    _write_sources_yaml(migrated_root, [{"path": str(missing)}])

    with caplog.at_level("WARNING", logger="pkm.ingest"):
        r = ingest_sources(migrated_root)

    assert r.scanned == 1
    assert r.ingested == 0
    assert r.new_sources == 0
    assert r.skipped == [str(missing)]
    assert _count_sources(migrated_root) == 0
    # The event identifier is in extras (for structured queries),
    # not in the human-readable message.
    assert any(
        rec.levelname == "WARNING"
        and getattr(rec, "event", None) == "ingest_skipped"
        for rec in caplog.records
    )


def test_ingest_directory_without_recursive_flag_is_skipped(
    migrated_root: Path, tmp_path: Path,
) -> None:
    dir_ = tmp_path / "docs"
    _write_file(dir_ / "a.txt", b"x")
    _write_sources_yaml(migrated_root, [{"path": str(dir_)}])

    r = ingest_sources(migrated_root)
    assert r.scanned == 1
    assert r.ingested == 0
    assert r.skipped == [str(dir_)]
    assert _count_sources(migrated_root) == 0


def test_ingest_broken_symlink_is_skipped(
    migrated_root: Path, tmp_path: Path,
) -> None:
    link = tmp_path / "link"
    link.symlink_to(tmp_path / "nonexistent")
    _write_sources_yaml(migrated_root, [{"path": str(link)}])

    r = ingest_sources(migrated_root)
    assert r.scanned == 1
    assert r.ingested == 0
    assert r.skipped == [str(link)]


def test_ingest_continues_past_bad_entries(
    migrated_root: Path, tmp_path: Path,
) -> None:
    good = tmp_path / "good.txt"
    _write_file(good, b"ok")
    _write_sources_yaml(
        migrated_root,
        [
            {"path": str(tmp_path / "missing1.txt")},
            {"path": str(good)},
            {"path": str(tmp_path / "missing2.txt")},
        ],
    )

    r = ingest_sources(migrated_root)
    assert r.scanned == 3
    assert r.ingested == 1
    assert r.new_sources == 1
    assert len(r.skipped) == 2
    assert _count_sources(migrated_root) == 1


# --- v0.4.0: declared paths stored, symlinks not dereferenced ------------
# (SPEC §8.2, §13.6)


def test_ingest_symlink_preserves_declared_eml_extension(
    migrated_root: Path, tmp_path: Path,
) -> None:
    """A ``.eml`` symlink to an extension-less file is stored under its
    declared ``.eml`` name, not the canonical extension-less target. This
    is the routing-critical behaviour: the suffix must survive so §7.3
    routes the source to the Unstructured email producer. Under the old
    canonicalizing behaviour ``current_path`` would have been the
    extension-less target and this source would have routed to nothing.
    """
    from pkm.routing import route

    target = tmp_path / "maildir-msg"  # extension-less, Maildir-style
    _write_file(target, b"From: a@b\n\nbody")
    link = tmp_path / "msg.eml"
    link.symlink_to(target)
    _write_sources_yaml(migrated_root, [{"path": str(link)}])

    r = ingest_sources(migrated_root)
    assert r.new_sources == 1
    assert r.skipped == []

    with open_catalogue(migrated_root) as conn:
        (current_path,) = conn.execute(
            "SELECT current_path FROM sources"
        ).fetchone()
    assert current_path == os.path.abspath(link)
    assert Path(current_path).suffix == ".eml"
    # ...and that preserved suffix is exactly what selects the email producer
    # (v0.5.0; .eml moved off unstructured to the dedicated `email` producer).
    assert "email" in route(extension=Path(current_path).suffix.lower())


def test_ingest_symlink_preserves_declared_pdf_extension(
    migrated_root: Path, tmp_path: Path,
) -> None:
    """Generic proof the silent-no-op footgun is closed for any
    extension, not just email: a ``.pdf`` symlink to an extension-less
    file is stored as ``.pdf``."""
    target = tmp_path / "scan-no-ext"
    _write_file(target, b"%PDF-1.4 fake")
    link = tmp_path / "scan.pdf"
    link.symlink_to(target)
    _write_sources_yaml(migrated_root, [{"path": str(link)}])

    ingest_sources(migrated_root)
    with open_catalogue(migrated_root) as conn:
        (current_path,) = conn.execute(
            "SELECT current_path FROM sources"
        ).fetchone()
    assert Path(current_path).suffix == ".pdf"
    assert current_path == os.path.abspath(link)


def test_ingest_recursive_dir_of_symlinks_preserves_extensions(
    migrated_root: Path, tmp_path: Path,
) -> None:
    """The mail-bridge shape: a staging directory of ``.eml`` symlinks
    pointing at extension-less Maildir files. Recursive ingest stores
    each declared ``.eml`` path (leaf symlink files are enumerated by
    their own name)."""
    maildir = tmp_path / "maildir"
    _write_file(maildir / "111", b"From: a\n\none")
    _write_file(maildir / "222", b"From: b\n\ntwo")
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "111.eml").symlink_to(maildir / "111")
    (staging / "222.eml").symlink_to(maildir / "222")
    _write_sources_yaml(
        migrated_root,
        [{"path": str(staging), "tags": ["email"], "recursive": True}],
    )

    r = ingest_sources(migrated_root)
    assert r.new_sources == 2
    assert r.skipped == []
    with open_catalogue(migrated_root) as conn:
        suffixes = sorted(
            Path(row[0]).suffix
            for row in conn.execute(
                "SELECT current_path FROM sources"
            ).fetchall()
        )
    assert suffixes == [".eml", ".eml"]


def test_ingest_symlink_hashes_target_bytes_and_is_idempotent(
    migrated_root: Path, tmp_path: Path,
) -> None:
    """``source_id`` is the SHA-256 of the symlink *target's* bytes
    (reading follows the link), so naming is independent of identity; a
    second run adds no new rows."""
    target = tmp_path / "maildir-msg"
    _write_file(target, b"hello")
    link = tmp_path / "msg.eml"
    link.symlink_to(target)
    _write_sources_yaml(migrated_root, [{"path": str(link)}])

    ingest_sources(migrated_root)
    expected_sid = (  # sha256("hello")
        "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    )
    with open_catalogue(migrated_root) as conn:
        (sid,) = conn.execute("SELECT source_id FROM sources").fetchone()
    assert sid == expected_sid

    r2 = ingest_sources(migrated_root)
    assert r2.new_sources == 0
    assert r2.new_paths == 0
    assert _count_sources(migrated_root) == 1
    assert _count_source_paths(migrated_root) == 1


# --- Manifest validation -------------------------------------------------


def test_ingest_raises_when_manifest_is_missing(
    migrated_root: Path,
) -> None:
    with pytest.raises(IngestError, match="not found"):
        ingest_sources(migrated_root)


def test_ingest_raises_on_malformed_yaml(
    migrated_root: Path,
) -> None:
    path = migrated_root / "sources" / "sources.yaml"
    path.write_text("{{not: valid", encoding="utf-8")
    with pytest.raises(IngestError, match="valid YAML"):
        ingest_sources(migrated_root)


def test_ingest_rejects_unknown_manifest_version(
    migrated_root: Path,
) -> None:
    path = migrated_root / "sources" / "sources.yaml"
    path.write_text(
        yaml.safe_dump({"version": 99, "sources": []}),
        encoding="utf-8",
    )
    with pytest.raises(IngestError, match="version"):
        ingest_sources(migrated_root)


def test_ingest_rejects_non_mapping_top_level(
    migrated_root: Path,
) -> None:
    path = migrated_root / "sources" / "sources.yaml"
    path.write_text("- just a list\n", encoding="utf-8")
    with pytest.raises(IngestError, match="mapping"):
        ingest_sources(migrated_root)


def test_ingest_accepts_empty_sources_list(
    migrated_root: Path,
) -> None:
    _write_sources_yaml(migrated_root, [])
    r = ingest_sources(migrated_root)
    assert r.scanned == 0
    assert r.ingested == 0
    assert r.new_sources == 0
    assert r.skipped == []


# --- Tag behaviour --------------------------------------------------------


def test_ingest_same_tags_re_ingested_is_row_stable(
    migrated_root: Path, tmp_path: Path,
) -> None:
    """Re-ingesting with the same tags leaves the source_tags row set
    unchanged. SPEC §13.5 specifies DELETE-then-INSERT as the
    implementation of declarative tag overwrite; this test pins the
    net-state invariant — two runs with identical yaml produce the
    same rows, not duplicates (the ``(source_id, tag)`` primary key
    would reject duplicates, but the DELETE clears the slate first)
    and not losses.
    """
    src = tmp_path / "doc.txt"
    _write_file(src, b"hi")
    _write_sources_yaml(
        migrated_root, [{"path": str(src), "tags": ["a", "b"]}]
    )
    ingest_sources(migrated_root)
    ingest_sources(migrated_root)

    with open_catalogue(migrated_root) as conn:
        (sid,) = conn.execute("SELECT source_id FROM sources").fetchone()
        (n,) = conn.execute("SELECT COUNT(*) FROM source_tags").fetchone()
    assert int(n) == 2
    assert _tags_for(migrated_root, sid) == ["a", "b"]


def test_ingest_overwrites_tags_on_re_ingest(
    migrated_root: Path, tmp_path: Path,
) -> None:
    """Tags in sources.yaml are declarative (see decision 1 and
    SPEC §13.5). A second run with different tags overwrites the
    stored tags in ``source_tags`` rather than merging. Removing a
    tag in yaml removes the corresponding ``source_tags`` row."""
    src = tmp_path / "doc.txt"
    _write_file(src, b"hi")

    _write_sources_yaml(
        migrated_root, [{"path": str(src), "tags": ["a", "b"]}]
    )
    ingest_sources(migrated_root)

    with open_catalogue(migrated_root) as conn:
        (sid,) = conn.execute("SELECT source_id FROM sources").fetchone()
    assert _tags_for(migrated_root, sid) == ["a", "b"]

    _write_sources_yaml(
        migrated_root, [{"path": str(src), "tags": ["c"]}]
    )
    ingest_sources(migrated_root)
    assert _tags_for(migrated_root, sid) == ["c"]
