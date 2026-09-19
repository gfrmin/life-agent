"""scripts/route_audit.py — the router confusion matrix (hermetic part)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import route_audit as RA


def test_matrix_counts_and_rates() -> None:
    items = [("a", True), ("b", True), ("c", False), ("d", False), ("e", True)]
    verdicts = {"a": {"lookup": True}, "b": {"lookup": False}, "c": {"lookup": True},
                "d": {"lookup": False}, "e": {"lookup": True}}
    m = RA.matrix(items, verdicts)
    assert (m["tp"], m["fn"], m["fp"], m["tn"]) == (2, 1, 1, 1)
    assert m["fn_rate"] == 1 / 3 and m["fp_rate"] == 0.5


def test_matrix_empty_sets_do_not_divide_by_zero() -> None:
    assert RA.matrix([], {}) == {"tp": 0, "fn": 0, "fp": 0, "tn": 0,
                                 "fn_rate": 0.0, "fp_rate": 0.0}


def test_route_prompt_names_document_kinds_beyond_personal_records() -> None:
    # run 6's 17 route refusals were document-content point facts (papers, theses,
    # statistics, code); the v2 prompt (2026-08-17, audit archived in the KB) names
    # them — drift-gated so "personal document" cannot quietly narrow the router again.
    from life_agent.core import lookup as LK

    for word in ("papers", "theses", "spreadsheets", "code", "stand for", "formula",
                 "one unit"):
        assert word in LK.ROUTE_PROMPT
