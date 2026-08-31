"""r33 A5 — the carrier census helper (conferral 2 §3.1).

Round 8 mis-stated two of its own nine golds by taking a census from ONE spelling of one
string: one claimed multiplicity where the "carrier" was a substring inside a longer
number; one missed a second genuine carrier under another spelling. The helper sweeps ALL
supplied spellings, excludes substring hits at word boundaries, and reports how the
DEPLOYED candidate rule groups the spellings — imported, never re-implemented (the
standing lesson's fifth instance was minted by exactly that shortcut).

All values synthetic.  # PII-OK: synthetic invoice/meter figures throughout
"""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import carrier_census as CC

from life_agent.core import lookup as LK


def _db(tmp_path: Path, rows: list[tuple[str, str]]) -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(str(tmp_path / "cat.duckdb"))
    conn.execute("CREATE TABLE artifact_chunks ("
                 "artifact_cache_key VARCHAR, chunk_index INT, chunk_text VARCHAR)")
    for i, (key, text) in enumerate(rows):
        conn.execute("INSERT INTO artifact_chunks VALUES (?, ?, ?)", [key, i, text])
    return conn


def test_the_sweep_finds_carriers_a_single_spelling_misses(tmp_path: Path) -> None:
    conn = _db(tmp_path, [("docA", "meter reading 2,378 kWh for the period"),
                          ("docB", "consumption was 2378 kWh in total")])
    one = CC.census(conn, ["2,378"])
    both = CC.census(conn, ["2,378", "2378"])
    assert one["carriers"] == {"docA"}           # the round-8 defect, reproduced
    assert both["carriers"] == {"docA", "docB"}  # the sweep is the fix


def test_substring_hits_are_excluded_not_counted(tmp_path: Path) -> None:
    # the second round-8 self-catch: a "carrier" that was a substring inside a numeric
    # coordinate — a word-boundary test excludes it, and it is REPORTED as excluded
    conn = _db(tmp_path, [("docA", "total 2378 kWh"),
                          ("docC", "coords [12378.5, 22.4] on the site plan")])
    out = CC.census(conn, ["2378"])
    assert out["carriers"] == {"docA"}
    assert out["substring_only"] == {"docC"}     # named, never silently dropped


def test_spelling_groups_come_from_the_deployed_rule() -> None:
    # the engine's own candidate identity groups the spellings: >=5-digit identifiers
    # merge on the digit canon; a 4-digit amount with an affix does NOT merge with its
    # bare form — exactly the norm-class split the census must make visible
    groups = CC.engine_groups(["347229321", "347-229-321", "2,378 kWh", "2378"])
    assert groups[CC.engine_key("347229321")] == ["347229321", "347-229-321"]
    assert CC.engine_key("2,378 kWh") != CC.engine_key("2378")
    assert len(groups) == 3


def test_the_engine_key_is_the_deployed_one_not_a_copy() -> None:
    assert CC.engine_key is LK._candidate_key    # imported, never re-implemented
