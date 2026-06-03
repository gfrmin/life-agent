"""Shared pytest fixtures for the pkm test suite.

- ``tmp_root`` — a per-test directory shaped like the knowledge
  root specified in SPEC §3.
- ``migrated_root`` — ``tmp_root`` with all pending migrations
  applied (schema v1). Use this fixture for cache-level tests that
  need the catalogue to exist.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pkm.catalogue import run_migrations


@pytest.fixture
def tmp_root(tmp_path: Path) -> Path:
    """A fresh, SPEC §3-shaped knowledge root for a single test.

    Guarantees on the returned directory:

      - ``<root>/cache/`` exists and is empty.
      - ``<root>/logs/`` exists and is empty.
      - ``<root>/sources/`` exists and is empty.
      - ``<root>/catalogue.duckdb`` does NOT exist (migrations create
        it; tests exercising migrations rely on its absence).
      - ``<root>/config.yaml`` does NOT exist; tests that need one
        write it themselves so each test's config is explicit.

    Teardown is pytest's built-in ``tmp_path`` cleanup.
    """
    (tmp_path / "cache").mkdir()
    (tmp_path / "logs").mkdir()
    (tmp_path / "sources").mkdir()
    return tmp_path


@pytest.fixture
def migrated_root(tmp_root: Path) -> Path:
    """``tmp_root`` after all pending migrations have been applied.

    Produces a knowledge root with the catalogue file present and
    at the current schema version. Cache-level tests use this
    fixture so they can ``open_catalogue`` and expect all tables
    (schema_meta, sources, source_paths, source_tags, artifacts,
    artifact_lineage, pending_approvals, etc.) to exist.
    """
    run_migrations(tmp_root)
    return tmp_root
