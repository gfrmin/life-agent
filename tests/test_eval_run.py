"""``eval.run``: the question loader, the availability probe and the typed response."""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval import run as ER


def _write(path: Path, questions: list[dict]) -> Path:
    path.write_text(yaml.safe_dump({"questions": questions}), encoding="utf-8")
    return path


def test_load_questions_fills_defaults_without_sharing_them(tmp_path: Path) -> None:
    p = _write(tmp_path / "alt.yaml",
               [{"id": "q-1", "question": "what is the value?", "answer": "P123"},
                {"id": "q-2", "question": "and the other?", "answer": "P456"}])
    qs = ER.load_questions(str(p))
    assert [q["id"] for q in qs] == ["q-1", "q-2"]
    assert qs[0]["subject"] == "n/a" and qs[0]["fuzzy"] is False
    assert qs[0]["answer_variants"] == [] and qs[0]["distractors"] == []
    qs[0]["answer_variants"].append("x")
    assert qs[1]["answer_variants"] == []


def test_load_questions_fails_fast(tmp_path: Path) -> None:
    missing = tmp_path / "nope.yaml"
    with pytest.raises(SystemExit) as ei:
        ER.load_questions(missing)
    assert str(missing) in str(ei.value)
    with pytest.raises(SystemExit):
        ER.load_questions(_write(tmp_path / "empty.yaml", []))


def test_gold_available_prefers_the_content_address_and_fails_open() -> None:
    conn = duckdb.connect(":memory:")
    conn.execute("CREATE TABLE artifact_chunks "
                 "(chunk_id INTEGER, artifact_cache_key VARCHAR, chunk_index INTEGER)")
    conn.execute("INSERT INTO artifact_chunks VALUES (7, 'k1', 0)")
    qs = [{"id": "by-key", "provenance": {"artifact_cache_key": "k1", "chunk_index": 0,
                                          "chunk_id": 999}},
          {"id": "key-absent", "provenance": {"artifact_cache_key": "k2", "chunk_index": 0}},
          {"id": "by-id", "provenance": {"chunk_id": 7}},
          {"id": "id-absent", "provenance": {"chunk_id": 8}},
          {"id": "no-provenance"}]
    assert ER.gold_available(conn, qs) == {"by-key": True, "key-absent": False, "by-id": True,
                                           "id-absent": False, "no-provenance": True}
    conn.execute("DROP TABLE artifact_chunks")
    assert ER.gold_available(conn, qs[:1]) == {"by-key": True}   # a failed probe never censors


def _view(effector: str, **kw: object) -> dict:
    return {"effector": effector, "applied": ["corroborate_haiku"], "spend_usd": 0.002,
            "asserted": [], "candidates": ["P123"], **kw}


def test_typed_response_grades_a_report_and_prices_what_was_applied() -> None:
    q = {"answer": "P123", "answer_variants": []}
    right = ER.typed_response(_view("report", asserted=["P123"]), q)
    wrong = ER.typed_response(_view("report", asserted=["P999"]), q)
    assert (right.action, right.correct, right.withheld) == ("report", True, None)
    assert wrong.correct is False
    assert right.applied == ("corroborate_haiku",) and right.metered_usd == 0.002
    assert right.cost_usd == ER.PRC.list_price(("corroborate_haiku",)) > 0


def test_typed_response_names_why_it_withheld() -> None:
    q = {"answer": "P123", "answer_variants": []}
    assert ER.typed_response(_view("abstain"), q).withheld == "dispersed"
    assert ER.typed_response(_view("abstain", candidates=[]), q).withheld == "miss"
    assert ER.typed_response(_view("miss"), q).action == "abstain"
    assert ER.typed_response(_view("abstain"), q, available=False).withheld == "unavailable"
    asked = ER.typed_response(_view("ask_clarify"), q)
    assert (asked.action, asked.correct) == ("ask_clarify", None)


def test_typed_response_records_the_leaders_calibration_reading() -> None:
    """`p1` and whether the leader landed the gold ride on every action: an abstain still
    has a leader. The reading is the highest credence, not the first candidate."""
    q = {"answer": "P123", "answer_variants": []}
    view = _view("abstain", candidates=["P999", "P123"], credences=[0.25, 0.6])
    r = ER.typed_response(view, q)
    assert (r.p1, r.n_candidates, r.leader_correct, r.truth_in_candidates) == (
        0.6, 2, True, True)
    wrong = ER.typed_response(_view("report", asserted=["P999"], candidates=["P999", "P123"],
                                    credences=[0.7, 0.2]), q)
    assert (wrong.p1, wrong.leader_correct, wrong.truth_in_candidates) == (0.7, False, True)


def test_typed_response_without_a_candidate_reads_no_leader() -> None:
    r = ER.typed_response(_view("abstain", candidates=[], credences=[]),
                          {"answer": "P123", "answer_variants": []})
    assert (r.p1, r.n_candidates, r.leader_correct, r.truth_in_candidates) == (
        None, 0, None, False)
    # a hand-built view without `credences` still grades: no leader, but the truth is seen
    bare = ER.typed_response(_view("abstain"), {"answer": "P123", "answer_variants": []})
    assert (bare.p1, bare.leader_correct, bare.truth_in_candidates) == (None, None, True)


# --- cite: graded by attestation of the cited document ------------------------------------

def _catalogue() -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(":memory:")
    conn.execute("CREATE TABLE artifact_chunks (artifact_cache_key VARCHAR, chunk_text VARCHAR)")
    conn.executemany("INSERT INTO artifact_chunks VALUES (?, ?)", [
        ("d-attests", "Passport No: P123"), ("d-also", "copy of P123 on file"),
        ("d-other", "Passport No: P999")])
    return conn


def _cite_view(key: str, **kw: object) -> dict:
    return _view("cite", cited={"cache_key": key, "hit_n": 1}, **kw)


def test_a_cite_is_right_iff_the_cited_document_attests_the_gold() -> None:
    q = {"answer": "P123", "answer_variants": []}
    conn = _catalogue()
    right = ER.typed_response(_cite_view("d-also"), q, conn=conn)
    wrong = ER.typed_response(_cite_view("d-other"), q, conn=conn)
    assert (right.action, right.correct, right.cited, right.withheld) == (
        "cite", True, "d-also", None)
    assert (wrong.action, wrong.correct, wrong.cited) == ("cite", False, "d-other")
    assert right.applied == ("corroborate_haiku",) and right.cost_usd > 0
    with pytest.raises(ValueError, match="catalogue"):
        ER.typed_response(_cite_view("d-also"), q)


def test_the_archive_row_carries_the_cited_key_and_the_tally_counts_cites() -> None:
    q = {"answer": "P123", "answer_variants": []}
    r = ER.typed_response(_cite_view("d-also"), q, conn=_catalogue())
    assert ER.archive_row("q-1", "run", r, censored=False)["typed"]["cited"] == "d-also"
    plain = ER.typed_response(_view("abstain"), q)
    assert ER.archive_row("q-2", "run", plain, censored=False)["typed"]["cited"] is None
    wrong = ER.typed_response(_cite_view("d-other"), q, conn=_catalogue())
    assert [ER._tally_key(x, censored=False) for x in (r, wrong, plain)] == [
        "cite-right", "cite-wrong", "declined"]
    assert ER._tally_key(r, censored=True) == "censored"


def test_a_cite_of_a_withheld_document_is_a_leak() -> None:
    q = {"answer": "P123", "answer_variants": []}
    assert ER.is_leak(_cite_view("d-attests", candidates=[]), q, frozenset({"d-attests"}))
    assert not ER.is_leak(_cite_view("d-other", candidates=[]), q, frozenset({"d-attests"}))
    assert not ER.is_leak(_view("abstain", candidates=[]), q, frozenset({"d-attests"}))
