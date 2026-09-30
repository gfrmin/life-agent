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
