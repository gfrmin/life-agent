"""Unit tests for the dogfood ask REPL's pure helpers (scripts/ask.py).

Run in the pkm env (has duckdb/yaml/pytest, which ask.py imports at module load):
    uv run --project ~/git/pkm python -m pytest ~/git/life-agent/tests/test_ask.py

Only the dependency-free logic is covered here — log-entry formatting and the
retrieve() dedupe/rank. The live retrieval + LLM synthesis paths are exercised by the
manual end-to-end verification in the plan, not in CI.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import ask  # noqa: E402
from _common import SourceCard  # noqa: E402


# --- log_entry formatting -------------------------------------------------- #

def _cards():
    return [SourceCard(n=1, text="x", origin="/a/b/id_scan.pdf"),
            SourceCard(n=2, text="y", origin="/c/2024-01-15.eml")]


def test_log_entry_good_omits_note_line() -> None:
    entry = ask.log_entry("q?", "the answer [1]", _cards(), {1: 0.89, 2: 0.76},
                          "GOOD", "", when="14:32")
    assert entry.startswith("## 14:32  GOOD\n")
    assert "Q: q?" in entry
    assert "A: the answer [1]" in entry
    assert "sources: id_scan.pdf(0.89), 2024-01-15.eml(0.76)" in entry
    assert "note:" not in entry


def test_log_entry_bad_includes_note() -> None:
    entry = ask.log_entry("q?", "wrong", _cards(), {1: 0.5, 2: 0.4},
                          "BAD", "OCR garbled the digits", when="09:01")
    assert "## 09:01  BAD" in entry
    assert "note: OCR garbled the digits" in entry


def test_log_entry_no_sources_omits_sources_line() -> None:
    entry = ask.log_entry("q?", "nothing retrieved", [], {}, "BAD", "missing source",
                          when="00:00")
    assert "sources:" not in entry
    assert "note: missing source" in entry


# --- retrieve() dedupe + rank (no DuckDB; pkm.retrieval.search monkeypatched) #

def _hit(text: str, score: float, path: str = "/p/doc"):
    return SimpleNamespace(chunk_text=text, score=score, source_path=path)


def test_retrieve_dedupes_keeping_best_score_and_ranks(monkeypatch) -> None:
    import pkm.retrieval as R

    hits = [_hit("A", 0.3), _hit("B", 0.9), _hit("A", 0.7), _hit("C", 0.5)]
    monkeypatch.setattr(R, "search", lambda conn, q, k: hits)

    out = ask.retrieve(conn=None, question="q", k=10)

    # one card per distinct chunk, ranked by best score desc, numbered 1..n
    assert [c.text for c, _ in out] == ["B", "A", "C"]
    assert [s for _, s in out] == [0.9, 0.7, 0.5]   # "A" kept its better 0.7, not 0.3
    assert [c.n for c, _ in out] == [1, 2, 3]


def test_retrieve_truncates_to_k(monkeypatch) -> None:
    import pkm.retrieval as R

    hits = [_hit(t, sc) for t, sc in [("A", 0.9), ("B", 0.8), ("C", 0.7), ("D", 0.6)]]
    monkeypatch.setattr(R, "search", lambda conn, q, k: hits)

    out = ask.retrieve(conn=None, question="q", k=2)
    assert [c.text for c, _ in out] == ["A", "B"]
