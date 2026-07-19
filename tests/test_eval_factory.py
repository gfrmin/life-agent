"""Unit tests for the verified question factory (scripts/eval_factory/factory.py).

Hermetic: fake DuckDB conn (canned chunk rows), fake `complete` callables, monkeypatched
pkm retrieval — no network, no corpus, no KB. Synthetic values only (P-prefixed fakes).

Run from the repo root:
    uv run --project . python -m pytest ./tests/test_eval_factory.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from eval_factory import factory as F

import pkm.retrieval as R


class _FakeConn:
    """Returns the canned chunk rows for the sampling query."""

    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self.rows = rows

    def execute(self, sql: str, params: list[Any] | None = None) -> _FakeConn:
        return self

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self.rows


def _chunk_rows() -> list[tuple[Any, ...]]:
    # (chunk_id, chunk_text, source_origin, current_path)
    return [
        (1, "The policy number is P111222 for the fake account.", "docs", "/fake/a.pdf"),
        (2, "Registered plate P333444 appears on the fake permit.", "mail", "/fake/b.eml"),
        (3, "Some other fake text mentioning value P555666 today.", "docs", "/fake/c.pdf"),
    ]


def _proposal(question: str, answer: str, variants: list[str] | None = None) -> str:
    return json.dumps({"question": question, "answer": answer,
                       "answer_variants": variants or [], "subject": "owner",
                       "notes": "test"})


def _hit(text: str, path: str = "/fake/hit.pdf") -> R.SearchResult:
    return R.SearchResult(chunk_text=text, score=1.0, source_path=path,
                          source_origin="docs", artifact_cache_key="k", chunk_id=9)


@pytest.fixture(autouse=True)
def _fake_search(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(F.R, "search", lambda conn, q, k=20: [_hit("context with P111222")])


# --- sampling ------------------------------------------------------------------------------

def test_sample_chunks_round_robins_across_origin_strata() -> None:
    out = F.sample_chunks(_FakeConn(_chunk_rows()), min_chars=10, limit=3, seed=1)
    assert len(out) == 3
    # round-robin: the single "mail" chunk cannot be crowded out by the two "docs" ones
    assert {c["source_origin"] for c in out[:2]} == {"docs", "mail"}


def test_sample_chunks_respects_limit() -> None:
    out = F.sample_chunks(_FakeConn(_chunk_rows()), min_chars=10, limit=2, seed=1)
    assert len(out) == 2


# --- the admission pipeline ----------------------------------------------------------------

def _run(propose_replies: list[str], verify_reply: str = "P111222", *,
         target: int = 10) -> F.FactoryResult:
    replies = iter(propose_replies)
    return F.run_factory(
        _FakeConn(_chunk_rows()),
        lambda s, u: next(replies),
        lambda s, u: verify_reply,
        target=target, max_proposals=len(propose_replies), k=5, min_chars=10, seed=1)


def test_grounded_verified_proposal_is_admitted() -> None:
    # chunk 2 ("mail" stratum) is sampled first in round-robin order? Order-independent:
    # propose the value that IS in whichever chunk arrives, by echoing P111222 for all —
    # only the chunk that contains P111222 grounds; others reject as ungrounded.
    result = _run([_proposal("what is my fake policy number?", "P111222")] * 3)
    assert len(result.admitted) == 1
    a = result.admitted[0]
    assert a.answer == "P111222"
    assert a.verifier_answer == "P111222"
    # P111222 grounds only in its own chunk; the other two sampled chunks reject as
    # ungrounded (dedup runs AFTER grounding, so they never mark the question seen)
    assert result.rejections["ungrounded"] == 2


def test_duplicate_question_text_is_rejected_once_grounded() -> None:
    rows = [(1, "The fake value P111222 appears here.", "docs", "/fake/a.pdf"),
            (2, "Elsewhere the fake value P111222 recurs.", "mail", "/fake/b.eml")]
    replies = iter([_proposal("what is my fake value?", "P111222")] * 2)
    result = F.run_factory(
        _FakeConn(rows), lambda s, u: next(replies), lambda s, u: "P111222",
        target=10, max_proposals=2, k=5, min_chars=10, seed=1)
    assert len(result.admitted) == 1
    assert result.rejections["duplicate"] == 1


def test_hallucinated_gold_is_rejected_before_verification() -> None:
    calls = {"verify": 0}

    def verify_complete(s: str, u: str) -> str:
        calls["verify"] += 1
        return "P999999"

    result = F.run_factory(
        _FakeConn(_chunk_rows()),
        lambda s, u: _proposal("what is the fake value?", "P999999"),
        verify_complete,
        target=10, max_proposals=3, k=5, min_chars=10, seed=1)
    assert len(result.admitted) == 0
    assert result.rejections["ungrounded"] == 3
    assert calls["verify"] == 0  # a hallucinated gold never spends a verifier call


def test_verifier_mismatch_and_not_found_reject() -> None:
    mismatch = _run([_proposal("q one about the fake policy?", "P111222")],
                    verify_reply="P333444")
    assert mismatch.rejections["not_verified"] == 1 and not mismatch.admitted

    not_found = _run([_proposal("q two about the fake policy?", "P111222")],
                     verify_reply="NOT_FOUND")
    assert not_found.rejections["not_verified"] == 1 and not not_found.admitted


def test_skip_and_malformed_replies_are_counted() -> None:
    result = _run(['{"skip": true}', "not json at all", '["a", "list"]'])
    assert result.rejections["skip"] == 1
    assert result.rejections["parse_error"] == 2
    assert not result.admitted


def test_target_stops_the_run_early() -> None:
    proposals = [
        _proposal("q one about the fake policy?", "P111222"),
        _proposal("q two about the fake plate?", "P333444"),
        _proposal("q three about the fake value?", "P555666"),
    ]
    replies = iter(proposals)
    calls = {"n": 0}

    def propose_complete(s: str, u: str) -> str:
        calls["n"] += 1
        return next(replies)

    result = F.run_factory(
        _FakeConn(_chunk_rows()), propose_complete,
        lambda s, u: "P111222",  # only q-one's gold ever verifies
        target=1, max_proposals=3, k=5, min_chars=10, seed=1)
    # admission order depends on stratum round-robin; the run must stop at target=1
    assert len(result.admitted) <= 1
    assert calls["n"] <= 3


def test_verifier_sees_only_the_question_never_the_chunk(
        monkeypatch: pytest.MonkeyPatch) -> None:
    seen_queries: list[str] = []

    def fake_search(conn: Any, q: str, k: int = 20) -> list[R.SearchResult]:
        seen_queries.append(q)
        return [_hit("independent context with P111222")]

    monkeypatch.setattr(F.R, "search", fake_search)
    verifier_prompts: list[str] = []

    def verify_complete(s: str, u: str) -> str:
        verifier_prompts.append(u)
        return "P111222"

    F.run_factory(
        _FakeConn(_chunk_rows()),
        lambda s, u: _proposal("what is my fake policy number?", "P111222"),
        verify_complete,
        target=10, max_proposals=3, k=5, min_chars=10, seed=1)
    assert seen_queries == ["what is my fake policy number?"]  # the question text ONLY
    (vp,) = verifier_prompts
    # anti-circularity: the generator's source chunk text never reaches the verifier
    assert "The policy number is P111222 for the fake account." not in vp
    assert "independent context with P111222" in vp


# --- outputs -------------------------------------------------------------------------------

def _admitted_result(n: int = 5) -> F.FactoryResult:
    result = F.FactoryResult()
    for i in range(n):
        result.admitted.append(F.Admitted(
            question=f"fake question {i}?", answer=f"P{i}{i}{i}", answer_variants=(),
            subject="owner", notes="", chunk_id=i, source_path=f"/fake/{i}.pdf",
            source_origin="docs", verifier_answer=f"P{i}{i}{i}"))
    return result


def test_questions_yaml_ids_are_sequential_and_audit_sample_seeded() -> None:
    corpus = F.questions_yaml_dict(_admitted_result(10), audit_fraction=0.2, seed=3)
    qs = corpus["questions"]
    assert [q["id"] for q in qs] == [f"q2-{i:03d}" for i in range(1, 11)]
    audits = [q for q in qs if q.get("audit")]
    assert len(audits) == 2  # round(10 * 0.2), seeded — stable across runs
    again = F.questions_yaml_dict(_admitted_result(10), audit_fraction=0.2, seed=3)
    assert [q["id"] for q in again["questions"] if q.get("audit")] == \
        [q["id"] for q in audits]


def test_write_outputs_lands_corpus_meta_and_report(tmp_path: Path) -> None:
    result = _admitted_result(3)
    corpus = F.questions_yaml_dict(result, audit_fraction=0.34, seed=3)
    ypath = F.write_outputs(tmp_path / "run", result, corpus,
                            {"run_id": "factory-test"}, cost_usd=1.25)
    loaded = yaml.safe_load(ypath.read_text(encoding="utf-8"))
    assert loaded["questions"][0]["provenance"]["source_path"] == "/fake/0.pdf"
    assert json.loads((tmp_path / "run" / "factory_meta.json").read_text())["run_id"] == \
        "factory-test"
    report = (tmp_path / "run" / "report.md").read_text()
    assert "admitted: **3**" in report
    assert "$1.25" in report
    assert "one bit each" in report


def test_factory_never_touches_questions_yaml(tmp_path: Path,
                                              monkeypatch: pytest.MonkeyPatch) -> None:
    kb = tmp_path / "kb"
    gold = kb / "eval" / "questions.yaml"
    gold.parent.mkdir(parents=True)
    gold.write_text("questions: []\n", encoding="utf-8")
    monkeypatch.setenv("LIFE_AGENT_KB", str(kb))
    result = _admitted_result(2)
    corpus = F.questions_yaml_dict(result, audit_fraction=0.5, seed=3)
    F.write_outputs(kb / "eval" / "factory" / "t", result, corpus, {}, cost_usd=None)
    assert gold.read_text(encoding="utf-8") == "questions: []\n"  # owner file untouched
    assert not (kb / "eval" / "questions_v2.yaml").exists()  # canonical only via --publish
