"""Reach audit (scripts/reach_audit.py) — hermetic: the class vocabulary is frozen in
the module docstring; these pin the classifier that lands each withheld question in
exactly one class, and the SQL prefilter's only-over-select property."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import reach_audit as RA


def test_like_pattern_is_token_ordered_and_escaped() -> None:
    assert RA._like_pattern("$1,234,567") == "%1%234%567%"
    assert RA._like_pattern("74.2%") == "%74%2%"      # the literal % never survives
    assert RA._like_pattern("a_b") == "%a%b%"          # _ splits at the token boundary
    assert RA._like_pattern("!!!") is None             # no tokens → no pattern


def test_classify_covers_the_frozen_vocabulary() -> None:
    home = "home-doc"
    assert RA.classify(set(), home, set()) == "gold-absent"
    assert RA.classify({home}, home, {home}) == "single-doc"
    assert RA.classify({home, "d2"}, home, set()) == "rescuable-unretrieved"
    assert RA.classify({home, "d2"}, home, {"d2"}) == "rescuable-retrieved"
    # a retrieved hit on the HOME doc alone is not a rescue — independence decides
    assert RA.classify({home, "d2"}, home, {home}) == "rescuable-unretrieved"
    # no provenance recorded → every gold-bearing doc counts as independent
    assert RA.classify({"d2"}, None, {"d2"}) == "rescuable-retrieved"


def test_classify_miss_split() -> None:
    assert RA.classify_miss(set(), set()) == "absent"
    assert RA.classify_miss({"d1"}, set()) == "not-retrieved"
    assert RA.classify_miss({"d1"}, {"d1"}) == "retrieved-not-extracted"


class _FakeConn:
    """SQL prefilter stub: returns every row, so the exact matcher does the deciding —
    the over-select contract the real ILIKE scan is allowed at most to share."""
    def __init__(self, rows: list[tuple[str, str]]) -> None:
        self._rows = rows

    def execute(self, sql: str, params: list) -> _FakeConn:
        return self

    def fetchall(self) -> list[tuple[str, str]]:
        return self._rows


def test_gold_bearing_artifacts_verifies_with_the_gate_matcher() -> None:
    rows = [("d1", "the fee is $1,234,567 due at signing"),
            ("d2", "totals: 1,234,567 (and 7,654,321)"),
            ("d3", "unrelated numbers 3 290 mentioning 250,999 apart")]  # prefilter noise
    keys = RA.gold_bearing_artifacts(_FakeConn(rows), "$1,234,567", ["1,234,567"])
    assert keys == {"d1", "d2"}


def test_audit_rows_joins_paired_decisions_and_retrieval(monkeypatch) -> None:
    paired = {
        "q-a": {"typed": {"action": "abstain"}},
        "q-b": {"typed": {"action": "abstain"}},
        "q-c": {"typed": {"action": "report"}},       # asserted — not audited
    }
    # the decisions log keys by the content-addressed question HASH, not the qid
    decisions = {
        RA._qhash("what is the fee?"): {
            "posterior_summary": {"n_obs": 2, "n_competing": 1}},
        # q-b has NO decision row — the unlogged-miss shape; still audited, miss-split
    }
    questions = [
        {"id": "q-a", "question": "what is the fee?", "answer": "1,234,567",
         "answer_variants": [], "provenance": {"artifact_cache_key": "home-a"}},
        {"id": "q-b", "question": "what is the tel?", "answer": "5550 0143",  # PII-OK
         "answer_variants": [], "provenance": {"artifact_cache_key": "home-b"}},
        {"id": "q-c", "question": "asserted", "answer": "x", "answer_variants": []},
    ]
    conn = _FakeConn([("home-a", "fee: 1,234,567"), ("indep-a", "fee 1,234,567 again"),
                      ("home-b", "tel 5550 0143")])  # PII-OK: synthetic phone shape
    monkeypatch.setattr(RA.RET, "retrieve_set", lambda c, q, k: [
        {"artifact_cache_key": "indep-a", "chunk_text": "fee 1,234,567 again"}])
    rows = RA.audit_rows(paired, decisions, questions, conn, k=5)
    assert [r.qid for r in rows] == ["q-a", "q-b"]
    a, b = rows
    assert (a.klass, a.miss_klass, a.n_obs, a.n_competing) == (
        "rescuable-retrieved", None, 2, 1)
    # q-b: gold only in its home doc; its (bogus) retrieval hit doesn't carry ITS gold
    assert (b.klass, b.miss_klass, b.n_obs) == ("single-doc", "not-retrieved", None)
