"""Unit tests for the declarative data-source registry (scripts/data_source_registry.py).

Run in the pkm env (has pytest, PyYAML, and the pkm producers):
    uv run --project ../pkm python -m pytest ./tests/test_data_source_registry.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from data_source_registry import (
    Candidate,
    Registry,
    RegistryError,
    Root,
    Row,
    _covered,
    _matches,
    aggregate,
    assert_roots_ingestable,
    bucket_undeclared,
    classify,
    discovery_root,
    forbidden_ingest_zones,
    ingestable_formats,
    load_registry,
)


def _root(id: str, path: str, **kw) -> Root:
    return Root(
        id=id,
        kind=kw.get("kind", "filetree"),
        path=Path(path),
        include=tuple(kw.get("include", ())),
        exclude=tuple(kw.get("exclude", ())),
        tags=tuple(kw.get("tags", ())),
        enabled=kw.get("enabled", True),
        staging_dir=kw.get("staging_dir"),
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
    assert classify(Path("/data/x/a.PDF"), fmt) == (".pdf", "docling", True)
    assert classify(Path("/data/x/a.md"), fmt) == (".md", "pandoc", True)
    assert classify(Path("/data/x/a.xyz"), fmt) == (".xyz", None, False)


def test_ingestable_formats_reflects_real_pkm_producers() -> None:
    fmt = ingestable_formats()
    # Capabilities that exist today (TesseractProducer is landed -> images ingest).
    for ext in (".pdf", ".md", ".docx", ".jpg", ".png", ".eml", ".txt"):
        assert ext in fmt, f"{ext} should be ingestable"
    assert ".sqlite" not in fmt and ".heic" not in fmt  # no producer yet


# --- aggregate ------------------------------------------------------------ #


def test_aggregate_counts_and_bytes() -> None:
    root = Root("docs", "filetree", Path("/data/cloud/documents"), (), (),
                ("documents",), True, None)
    rows = [
        Row("docs", "/data/x/a.pdf", ".pdf", 100, "docling", True),
        Row("docs", "/data/x/b.pdf", ".pdf", 200, "docling", True),
        Row("docs", "/data/x/c.heic", ".heic", 50, None, False),
    ]
    s = aggregate(root, rows)
    assert s.files == 3
    assert s.bytes == 350
    assert s.ingestable_files == 2
    assert s.ingestable_bytes == 300
    assert s.by_ext == {".pdf": 2, ".heic": 1}  # descending by count


# --- discovery (the inverse of the census) -------------------------------- #


def test_discovery_root_is_common_ancestor_of_declared_roots() -> None:
    roots = (
        _root("notes", "/data/notes"),
        _root("docs", "/data/cloud/documents"),
        _root("mail", "/data/mail/acct"),
    )
    assert discovery_root(roots, None) == Path("/data")


def test_discovery_root_single_root_is_that_root() -> None:
    assert discovery_root((_root("a", "/data/projects"),), None) == Path("/data/projects")


def test_discovery_root_override_wins() -> None:
    roots = (_root("a", "/data/notes"),)
    assert discovery_root(roots, "/data/elsewhere") == Path("/data/elsewhere")


def test_discovery_root_empty_registry_needs_a_path() -> None:
    with pytest.raises(RegistryError, match="discovery root"):
        discovery_root((), None)


def test_covered_is_by_location_not_include() -> None:
    reals = ("/data/notes", "/data/cloud/documents")
    # Inside a declared root counts as covered even though notes only ingests *.md.
    assert _covered("/data/notes/sub/scan.png", reals) is True
    assert _covered("/data/cloud/documents/a.pdf", reals) is True
    # A sibling dir that merely shares a name prefix is NOT covered.
    assert _covered("/data/notes-backup/a.md", reals) is False
    assert _covered("/data/projects/proj-a/x.pdf", reals) is False


def test_bucket_undeclared_groups_by_top_dir_and_counts_ingestable() -> None:
    base = Path("/data")
    fmt = {".pdf": "docling", ".jpg": "tesseract"}
    files = [
        "/data/projects/proj-a/a.pdf",
        "/data/projects/proj-a/cert.jpg",
        "/data/projects/proj-a/ledger.journal",  # no producer
        "/data/scratch/note.txt",  # no producer in this fmt map
        "/data/loose.pdf",  # a file directly under base -> "." bucket
    ]
    cands = bucket_undeclared(files, base, fmt)
    by_name = {c.name: c for c in cands}

    assert by_name["projects"].files == 3
    assert by_name["projects"].ingestable_files == 2
    assert by_name["projects"].by_ext == {".pdf": 1, ".jpg": 1}

    assert by_name["scratch"].ingestable_files == 0
    assert by_name["."].files == 1 and by_name["."].ingestable_files == 1

    # Ranked by ingestable files, descending: projects (2) leads.
    assert cands[0].name == "projects"


def test_discover_covers_staging_dirs(monkeypatch) -> None:
    # A maildir root's staging tree (outside its `path`) must count as covered.
    import data_source_registry as dsr

    reg = Registry(
        version=1,
        roots=(
            _root("mail", "/data/mail/acct", kind="maildir",
                  staging_dir=Path("/data/pkm/mail-staging")),
            _root("notes", "/data/notes"),
        ),
    )
    swept = [
        "/data/pkm/mail-staging/INBOX/1.eml",  # covered via staging_dir
        "/data/notes/a.md",  # covered via path
        "/data/library/paper.pdf",  # genuinely undeclared
    ]
    monkeypatch.setattr(dsr, "_plocate_under", lambda base: swept)
    d = dsr.discover(reg, "/data")
    assert [c.name for c in d.candidates] == ["library"]
    assert d.covered == 2


def test_bucket_undeclared_samples_are_ingestable_only() -> None:
    base = Path("/data")
    fmt = {".pdf": "docling"}
    files = ["/data/p/keep.pdf", "/data/p/skip.journal"]
    (cand,) = bucket_undeclared(files, base, fmt)
    assert cand.samples == ("/data/p/keep.pdf",)
    assert isinstance(cand, Candidate)


# --- enumerate_filetree pruning (ingest_sources) -------------------------- #


def test_prune_patterns_derives_subtree_excludes() -> None:
    from ingest_sources import _prune_patterns

    pats = _prune_patterns(("**/.git/**", "git/**", "**/._*", "**/node_modules/**"))
    # subtree excludes (ending /**) become dir-prune patterns; per-file globs do not.
    assert pats == ("**/.git", "git", "**/node_modules")


def test_enumerate_filetree_prunes_vcs_and_cloned_repos(tmp_path: Path) -> None:
    from ingest_sources import enumerate_filetree

    (tmp_path / ".git" / "objects").mkdir(parents=True)
    (tmp_path / ".git" / "objects" / "x.md").write_text("vcs", encoding="utf-8")
    (tmp_path / "git" / "repo").mkdir(parents=True)
    (tmp_path / "git" / "repo" / "README.md").write_text("cloned", encoding="utf-8")
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "a.md").write_text("real", encoding="utf-8")

    archive_excludes = ("git/**", "**/git/**", "**/.git/**")
    root = _root("archive", str(tmp_path), include=("**/*.md",), exclude=archive_excludes)
    got = {p.name for p in enumerate_filetree(root)}
    assert got == {"a.md"}  # VCS + cloned-repo markdown pruned, real note kept

    # Without the excludes, the same files are all enumerated (prune is opt-in).
    root_all = _root("archive", str(tmp_path), include=("**/*.md",))
    assert len(enumerate_filetree(root_all)) == 3


# --- merge_entries (ingest_sources) --------------------------------------- #


def test_merge_entries_dedupes_and_unions_tags() -> None:
    from ingest_sources import merge_entries

    existing = [{"path": "/data/x/a.pdf"}, {"path": "/data/x/b.pdf", "tags": ["documents"]}]
    new = [
        {"path": "/data/x/b.pdf", "tags": ["legal"]},  # dup path -> union tags
        {"path": "/data/x/c.md", "tags": ["notes"]},  # genuinely new
        {"path": "/data/staging/mail", "tags": ["email"], "recursive": True},
    ]
    merged = merge_entries(existing, new)
    paths = [e["path"] for e in merged]
    # existing entries first, then the new staging path
    assert paths == ["/data/x/a.pdf", "/data/x/b.pdf", "/data/x/c.md", "/data/staging/mail"]
    b = next(e for e in merged if e["path"] == "/data/x/b.pdf")
    assert b["tags"] == ["documents", "legal"]  # unioned, sorted
    mail = next(e for e in merged if e["path"] == "/data/staging/mail")
    assert mail["recursive"] is True


# --- ingest guard: never feed the agent's own memory back into the corpus --- #


def _pkm_cfg(tmp_path: Path, root_dir: Path) -> Path:
    cfg = tmp_path / "pkm.yaml"
    cfg.write_text(f"root_dir: {root_dir}\n", encoding="utf-8")
    return cfg


def test_guard_rejects_enabled_root_inside_kb(monkeypatch, tmp_path: Path) -> None:
    kb = tmp_path / "kb"
    (kb / "config").mkdir(parents=True)
    monkeypatch.setenv("LIFE_AGENT_KB", str(kb))
    monkeypatch.delenv("PKM_CONFIG", raising=False)
    roots = (_root("evil", str(kb / "config")),)  # enabled by default
    with pytest.raises(RegistryError, match="protected zone"):
        assert_roots_ingestable(roots)


def test_guard_exempts_census_only_root_inside_kb(monkeypatch, tmp_path: Path) -> None:
    kb = tmp_path / "kb"
    kb.mkdir()
    monkeypatch.setenv("LIFE_AGENT_KB", str(kb))
    monkeypatch.delenv("PKM_CONFIG", raising=False)
    roots = (_root("kb_census", str(kb), enabled=False),)
    assert_roots_ingestable(roots)  # disabled roots are never ingested -> no raise


def test_guard_allows_root_outside_zones(monkeypatch, tmp_path: Path) -> None:
    kb = tmp_path / "kb"
    kb.mkdir()
    monkeypatch.setenv("LIFE_AGENT_KB", str(kb))
    monkeypatch.delenv("PKM_CONFIG", raising=False)
    roots = (_root("real", str(tmp_path / "dropbox")),)
    assert_roots_ingestable(roots)  # a genuine corpus root -> no raise


def test_guard_rejects_root_inside_pkm_store(monkeypatch, tmp_path: Path) -> None:
    store = tmp_path / "pkm" / "live"
    store.mkdir(parents=True)
    (tmp_path / "kb").mkdir()
    monkeypatch.setenv("LIFE_AGENT_KB", str(tmp_path / "kb"))
    roots = (_root("cache", str(store / "runs")),)
    with pytest.raises(RegistryError, match="protected zone"):
        assert_roots_ingestable(roots, pkm_config=_pkm_cfg(tmp_path, store))


def test_guard_allows_mail_root_whose_staging_is_sibling_of_store(
        monkeypatch, tmp_path: Path) -> None:
    # The pkm store is .../pkm/live; mail stages into .../pkm/mail-staging, a SIBLING
    # of the store (not inside it). A maildir root's own path is the real Maildir,
    # well outside any zone — so legitimate mail ingest must not trip the guard.
    store = tmp_path / "pkm" / "live"
    store.mkdir(parents=True)
    (tmp_path / "kb").mkdir()
    monkeypatch.setenv("LIFE_AGENT_KB", str(tmp_path / "kb"))
    roots = (_root("mail", str(tmp_path / "mail" / "fastmail"), kind="maildir",
                   staging_dir=tmp_path / "pkm" / "mail-staging"),)
    assert_roots_ingestable(roots, pkm_config=_pkm_cfg(tmp_path, store))


def test_forbidden_zones_derived_from_env(monkeypatch, tmp_path: Path) -> None:
    kb = tmp_path / "kb"
    kb.mkdir()
    monkeypatch.setenv("LIFE_AGENT_KB", str(kb))
    store = tmp_path / "store"
    store.mkdir()
    zones = forbidden_ingest_zones(pkm_config=_pkm_cfg(tmp_path, store))
    assert set(zones) == {str(kb), str(store)}
