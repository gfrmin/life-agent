"""Unit tests for ``run_eval.load_questions``'s explicit-path parameter (the seam the
fairfight/eval ``--questions`` flags thread through).

Hermetic: tmp files only; synthetic fixtures (checksum-failing IDs convention).

Run from the repo root:
    uv run --project . python -m pytest ./tests/test_run_eval_questions.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import run_eval as RE


def _write(path: Path, questions: list[dict]) -> Path:
    path.write_text(yaml.safe_dump({"questions": questions}), encoding="utf-8")
    return path


def test_explicit_path_loads_that_file_and_fills_defaults(tmp_path: Path) -> None:
    p = _write(tmp_path / "alt.yaml",
               [{"id": "q2-001", "question": "what is the value?", "answer": "P123"}])
    qs = RE.load_questions(p)
    assert [q["id"] for q in qs] == ["q2-001"]
    # the same optional-field defaults the default corpus gets — downstream grading
    # relies on these keys existing
    assert qs[0]["subject"] == "n/a"
    assert qs[0]["answer_variants"] == []
    assert qs[0]["distractors"] == []
    assert qs[0]["fuzzy"] is False


def test_explicit_path_accepts_a_string(tmp_path: Path) -> None:
    p = _write(tmp_path / "alt.yaml",
               [{"id": "q2-001", "question": "what is the value?", "answer": "P123"}])
    qs = RE.load_questions(str(p))
    assert [q["id"] for q in qs] == ["q2-001"]


def test_explicit_missing_path_fails_fast_naming_the_path(tmp_path: Path) -> None:
    missing = tmp_path / "nope.yaml"
    with pytest.raises(SystemExit) as ei:
        RE.load_questions(missing)
    assert str(missing) in str(ei.value)


def test_default_still_reads_the_kb_corpus(tmp_path: Path,
                                            monkeypatch: pytest.MonkeyPatch) -> None:
    kb = tmp_path / "kb"
    (kb / "eval").mkdir(parents=True)
    _write(kb / "eval" / "questions.yaml",
           [{"id": "q-001", "question": "what is the value?", "answer": "P123"}])
    monkeypatch.setenv("LIFE_AGENT_KB", str(kb))
    qs = RE.load_questions()
    assert [q["id"] for q in qs] == ["q-001"]


def test_empty_questions_list_fails_fast(tmp_path: Path) -> None:
    p = _write(tmp_path / "alt.yaml", [])
    with pytest.raises(SystemExit):
        RE.load_questions(p)


class _Hit:
    chunk_text = "the value is P123"
    score = 1.0
    source_path = "/fake/a.txt"


def test_grade_retrieval_falls_back_to_question_text_without_search_queries(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """PR-31 review Important-1: a corpus with no authored search_queries (the factory's
    questions_v2.yaml emits none) must not make PASS structurally unreachable — the
    question text itself becomes the query."""
    import pkm.retrieval as PR

    seen: list[str] = []

    def _search(conn: object, query: str, k: int = 20) -> list[_Hit]:
        seen.append(query)
        return [_Hit()]

    monkeypatch.setattr(PR, "search", _search)
    p = _write(tmp_path / "alt.yaml",
               [{"id": "q2-001", "question": "what is the value?", "answer": "P123"}])
    q = RE.load_questions(p)[0]

    row = RE.grade_retrieval(None, q, k=5)

    assert seen == ["what is the value?"]  # the fallback query, nothing else
    assert row["verdict"] == "PASS"


def test_grade_retrieval_authored_search_queries_still_win(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The fallback is empty-only: authored queries are used verbatim and the question
    text is NOT appended (no behavior change for the v1 corpus)."""
    import pkm.retrieval as PR

    seen: list[str] = []

    def _search(conn: object, query: str, k: int = 20) -> list[_Hit]:
        seen.append(query)
        return [_Hit()]

    monkeypatch.setattr(PR, "search", _search)
    p = _write(tmp_path / "alt.yaml",
               [{"id": "q-001", "question": "what is the value?", "answer": "P123",
                 "search_queries": ["P123", "the value"]}])
    q = RE.load_questions(p)[0]

    row = RE.grade_retrieval(None, q, k=5)

    assert seen == ["P123", "the value"]
    assert row["verdict"] == "PASS"
