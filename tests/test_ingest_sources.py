"""The porcelain stage matrix of scripts/ingest_sources.py.

Pins the interaction contract's porcelain rule: the composition owns sequencing
knowledge so the human doesn't have to — `--chunk` chains `rebuild-index` after
`chunk --backfill`, because a chunk pass whose FTS index is stale silently
misses the new content in search (invariant 3: nothing silent).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import ingest_sources


def test_ingest_alone_only_registers() -> None:
    assert ingest_sources.stages(extract=False, chunk=False) == [["ingest"]]


def test_extract_appends_one_stage() -> None:
    assert ingest_sources.stages(extract=True, chunk=False) == [["ingest"], ["extract"]]


def test_chunk_chains_rebuild_index() -> None:
    assert ingest_sources.stages(extract=False, chunk=True) == [
        ["ingest"], ["chunk", "--backfill"], ["rebuild-index"]]


def test_full_promote_runs_all_stages_in_order() -> None:
    assert ingest_sources.stages(extract=True, chunk=True) == [
        ["ingest"], ["extract"], ["chunk", "--backfill"], ["rebuild-index"]]
