"""scripts/temper_audit.py — the off-gate competing-values sweep (§14)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import temper_audit as TA

from life_agent.core.decisions import question_id as _qhash

QUESTIONS = [
    {"id": "q-a", "question": "total prize money for I CAN?"},
    {"id": "q-b", "question": "fax number for Candy?"},
    {"id": "q-c", "question": "clean single value?"},
    {"id": "q-d", "question": "never routed?"},
]

PAIRED = {
    "q-a": {"question_id": "q-a", "answerable": True,
            "typed": {"action": "report", "correct": False, "cost_usd": 0.1,
                      "withheld": None},
            "mono": {"action": "report", "correct": True, "cost_usd": 0.5,
                     "withheld": None}},
    "q-b": {"question_id": "q-b", "answerable": True,
            "typed": {"action": "report", "correct": False, "cost_usd": 0.0,
                      "withheld": None},
            "mono": {"action": "report", "correct": True, "cost_usd": 0.5,
                     "withheld": None}},
    "q-c": {"question_id": "q-c", "answerable": True,
            "typed": {"action": "report", "correct": True, "cost_usd": 0.0,
                      "withheld": None},
            "mono": {"action": "report", "correct": True, "cost_usd": 0.5,
                     "withheld": None}},
    "q-d": {"question_id": "q-d", "answerable": True,
            "typed": {"action": "abstain", "correct": None, "cost_usd": 0.0,
                      "withheld": "miss"},
            "mono": {"action": "report", "correct": True, "cost_usd": 0.5,
                     "withheld": None}},
}

DECISIONS = {
    _qhash("total prize money for I CAN?"): {"posterior_summary": {
        "candidates": ["$1,234,567"], "credences": [0.926], "n_obs": 1, "p_none": 0.074}},
    _qhash("fax number for Candy?"): {"posterior_summary": {
        "candidates": ["(852) 5550 0143"], "credences": [0.927], "n_obs": 1,
        "p_none": 0.073}},
    _qhash("clean single value?"): {"posterior_summary": {
        "candidates": ["PL-900001"], "credences": [0.926], "n_obs": 1, "p_none": 0.074}},
}

CHUNKS = {
    "q-a": [("prize $1,234,567 for the season; career $7,654,321 listed",
             "prize $1,234,567 for the season; career $7,654,321")],
    "q-b": [("Tel: (852) 5550 0143  Fax: (852) 5550 0187",
             "Tel: (852) 5550 0143  Fax: (852) 5550 0187")],
    "q-c": [("Passport number PL-900001, expires 23 May 2032",
             "Passport number PL-900001")],
}


def _recover(qid: str, question: str, leader: str) -> tuple[list[TA.Evidence], str]:
    chunks = CHUNKS.get(qid, [])
    return chunks, "extract-cache" if chunks else "unrecovered"


def test_analytic_temper_odds_scaling() -> None:
    assert round(TA.analytic_temper(0.926, 0.5), 3) == 0.862
    assert TA.analytic_temper(0.926, 1.0) == 0.926


def test_exact_temper_matches_the_worked_channel_math() -> None:
    # the run-8 regime: leader 0.926 (effective r ≈ 0.535) tempered at 0.5 lands ≈ 0.823
    # — the exact channel inversion, harder than the analytic 0.862
    assert round(TA.exact_temper_single(0.926, 0.5), 3) == 0.823
    assert TA.exact_temper_single(0.926, 1.0) == pytest.approx(0.926, abs=1e-9)
    # exact flips ⊇ analytic flips: a 0.955 leader the analytic scaling spares, flips
    assert TA.exact_temper_single(0.955, 0.5) < TA.COMMIT_BAR < TA.analytic_temper(0.955, 0.5)


def test_audit_flips_competed_wrongs_and_spares_the_clean_commit() -> None:
    rows = TA.audit_rows(PAIRED, DECISIONS, QUESTIONS, _recover)
    by_qid = {r.qid: r for r in rows}
    assert by_qid["q-a"].counts["D1"] == 1 and by_qid["q-a"].would_flip("D1", 3)
    assert by_qid["q-b"].counts["D1"] >= 1 and by_qid["q-b"].would_flip("D1", 3)
    assert by_qid["q-c"].counts["D1"] == 0 and not by_qid["q-c"].would_flip("D1", 3)
    # the quote-scoped D3 fires when the competitor sits inside the extractor's anchor
    assert by_qid["q-a"].counts["D3"] == 1 and by_qid["q-b"].counts["D3"] >= 1
    assert by_qid["q-c"].counts["D3"] == 0
    # the unrouted question is carried, named, never dropped
    assert by_qid["q-d"].evidence_source == "no-decision"
    m = {(m["detector"], m["cap"]): m for m in TA.summary_matrix(rows, [1, 3])}
    assert m[("D1", 3)]["wrong_flips"] == ["q-a", "q-b"]
    assert m[("D1", 3)]["collateral"] == []


def test_render_names_the_uncovered_set() -> None:
    rows = TA.audit_rows(PAIRED, DECISIONS, QUESTIONS, lambda *a: ([], "unrecovered"))
    text = TA.render(rows, TA.summary_matrix(rows, [3]), [3], "run-x")
    assert "NOT COVERED" in text and "q-a" in text and "q-d" in text


def test_synth_paired_rewrites_only_flips_and_prices_the_stress(tmp_path: Path) -> None:
    rows = TA.audit_rows(PAIRED, DECISIONS, QUESTIONS, _recover)
    floor, stressed = TA.synth_paired(PAIRED, rows, "D1", 3, tmp_path)
    f = {r["question_id"]: r for r in map(json.loads, floor.read_text().splitlines())}
    s = {r["question_id"]: r for r in map(json.loads, stressed.read_text().splitlines())}
    assert f["q-a"]["typed"] == {"action": "abstain", "correct": None,
                                "withheld": "dispersed", "cost_usd": 0.1}
    assert s["q-a"]["typed"]["cost_usd"] == 0.55
    assert f["q-c"] == PAIRED["q-c"]           # the clean commit is untouched
    assert f["q-a"]["mono"] == PAIRED["q-a"]["mono"]  # mono arm never touched
