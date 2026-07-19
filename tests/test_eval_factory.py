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


# --- PR-29 review findings, pinned ---------------------------------------------------------

def test_self_quoting_question_is_rejected_before_verification() -> None:
    """PR-29 Critical: a question that quotes its own gold would leak the answer into the
    verifier's retrieval query and prompt — mechanical gate, no verifier call spent."""
    calls = {"verify": 0}

    def verify_complete(s: str, u: str) -> str:
        calls["verify"] += 1
        return "P111222"

    result = F.run_factory(
        _FakeConn(_chunk_rows()),
        lambda s, u: _proposal("is my fake policy number P111222 current?", "P111222"),
        verify_complete,
        target=10, max_proposals=3, k=5, min_chars=10, seed=1)
    assert not result.admitted
    assert result.rejections["gold_in_question"] == 3
    assert calls["verify"] == 0


def test_non_list_answer_variants_rejected_not_char_split() -> None:
    """PR-29 Important: a bare-string answer_variants must never iterate into
    single-character variants (eval-corpus contamination) — strict contract, rejected."""
    reply = json.dumps({"question": "what is my fake policy number?",
                        "answer": "P111222", "answer_variants": "P111222",
                        "subject": "owner", "notes": ""})
    result = _run([reply] * 3)
    assert not result.admitted
    assert result.rejections["parse_error"] == 3


def test_fill_is_single_pass_no_template_injection() -> None:
    """PR-29 Important: LLM/corpus text containing a literal placeholder must not be
    expanded by a later substitution pass."""
    out = F._fill(F.VERIFIER_V1, {"question": "what about {context} literally?",
                                  "context": "SECRET-CONTEXT"})
    assert "what about {context} literally?" in out  # survives verbatim, unexpanded
    assert out.count("SECRET-CONTEXT") == 1


def test_not_found_detection_tolerates_phrasing() -> None:
    assert F._NOT_FOUND_RE.match("NOT_FOUND")
    assert F._NOT_FOUND_RE.match("Not found in the context")
    assert F._NOT_FOUND_RE.match("not-found")
    assert not F._NOT_FOUND_RE.match("P111222 was found")


# --- v1.1 gates (deliberative-audit findings of 2026-07-19, pinned) ------------------------

def _proposal_for(question: str, answer: str, subject: str) -> str:
    return json.dumps({"question": question, "answer": answer, "answer_variants": [],
                       "subject": subject, "notes": "test"})


def test_subject_voice_first_person_with_third_party_subject_rejected() -> None:
    """The q2-084 class: a first-person question about a third party's fact reads the
    owner's voice onto someone else's record — mechanical gate, no verifier call spent."""
    calls = {"verify": 0}

    def verify_complete(s: str, u: str) -> str:
        calls["verify"] += 1
        return "P111222"

    result = F.run_factory(
        _FakeConn(_chunk_rows()),
        lambda s, u: _proposal_for(
            "what fake database do I have a subscription for?", "P111222", "Stephen Fake"),
        verify_complete,
        target=10, max_proposals=3, k=5, min_chars=10, seed=1)
    assert not result.admitted
    assert result.rejections["subject_voice"] == 3
    assert calls["verify"] == 0


def test_subject_voice_third_party_question_in_third_person_admitted() -> None:
    result = _run([_proposal_for(
        "what fake policy number does Stephen Fake hold?", "P111222", "Stephen Fake")] * 3)
    assert len(result.admitted) == 1
    assert result.admitted[0].subject == "Stephen Fake"
    assert result.rejections["subject_voice"] == 0


def test_subject_voice_owner_first_person_admitted_case_insensitive() -> None:
    result = _run([_proposal_for(
        "what is my fake policy number?", "P111222", "Owner")] * 3)
    assert len(result.admitted) == 1


def test_multi_slot_two_interrogatives_rejected() -> None:
    calls = {"verify": 0}

    def verify_complete(s: str, u: str) -> str:
        calls["verify"] += 1
        return "P111222"

    result = F.run_factory(
        _FakeConn(_chunk_rows()),
        lambda s, u: _proposal(
            "what is the fake policy number and when was it issued?", "P111222"),
        verify_complete,
        target=10, max_proposals=3, k=5, min_chars=10, seed=1)
    assert not result.admitted
    assert result.rejections["multi_slot"] == 3
    assert calls["verify"] == 0


def test_multi_slot_single_wh_with_and_inside_a_noun_phrase_admitted() -> None:
    """'and' joining nouns is not a second slot — only a second interrogative clause is."""
    result = _run([_proposal(
        "which fake company provides gas and electricity to my account?", "P111222")] * 3)
    assert len(result.admitted) == 1
    assert result.rejections["multi_slot"] == 0


def test_multi_slot_relative_who_clause_is_not_a_second_slot() -> None:
    result = _run([_proposal(
        "what is the fake number of the person who called about my policy?",
        "P111222")] * 3)
    assert len(result.admitted) == 1


def test_source_cap_limits_admissions_per_source_path() -> None:
    """The CSV-trivia class: one dense file must not fill the corpus — cap admissions
    per source_path; the overflow is rejected BEFORE the verifier spend."""
    rows = [
        (1, "First fake value P111222 sits here.", "docs", "/fake/same.csv"),
        (2, "Second fake value P111222 sits here too.", "docs", "/fake/same.csv"),
        (3, "Third fake value P111222 sits here as well.", "docs", "/fake/same.csv"),
    ]
    replies = iter([
        _proposal("what is the first fake value?", "P111222"),
        _proposal("what is the second fake value?", "P111222"),
        _proposal("what is the third fake value?", "P111222"),
    ])
    calls = {"verify": 0}

    def verify_complete(s: str, u: str) -> str:
        calls["verify"] += 1
        return "P111222"

    result = F.run_factory(
        _FakeConn(rows), lambda s, u: next(replies), verify_complete,
        target=10, max_proposals=3, k=5, min_chars=10, seed=1, per_source_cap=2)
    assert len(result.admitted) == 2
    assert result.rejections["source_cap"] == 1
    assert calls["verify"] == 2


def test_source_cap_zero_disables_the_cap() -> None:
    rows = [
        (i, f"Fake value P111222 row {i}.", "docs", "/fake/same.csv") for i in range(3)
    ]
    replies = iter([
        _proposal(f"what is fake row {i} value?", "P111222") for i in range(3)
    ])
    result = F.run_factory(
        _FakeConn(rows), lambda s, u: next(replies), lambda s, u: "P111222",
        target=10, max_proposals=3, k=5, min_chars=10, seed=1, per_source_cap=0)
    assert len(result.admitted) == 3


def test_first_person_gate_ignores_acronym_us_and_matches_real_first_person() -> None:
    """PR-32 review Important-1: 'US' (visa/bank/dollar) must not read as first person;
    the real pronouns still must."""
    assert not F._is_first_person("What is Stephen Fake's US visa number?")
    assert not F._is_first_person("Which US bank issued the fake statement?")
    assert F._is_first_person("What database do I have a fake subscription for?")
    assert F._is_first_person("What is my fake policy number?")
    assert F._is_first_person("When did we sign the fake lease?")
    assert F._is_first_person("What did the letter tell us to pay?")  # lowercase 'us'


def test_multi_slot_catches_single_wh_two_slot_noun_compound() -> None:
    """PR-32 review Important-2: one wh-word governing two conjoined slot nouns is still
    two value slots ('what is the policy number and effective date?')."""
    calls = {"verify": 0}

    def verify_complete(s: str, u: str) -> str:
        calls["verify"] += 1
        return "P111222"

    result = F.run_factory(
        _FakeConn(_chunk_rows()),
        lambda s, u: _proposal(
            "what is the fake policy number and effective date?", "P111222"),
        verify_complete,
        target=10, max_proposals=3, k=5, min_chars=10, seed=1)
    assert not result.admitted
    assert result.rejections["multi_slot"] == 3
    assert calls["verify"] == 0


def test_multi_slot_same_slot_noun_both_sides_is_not_compound() -> None:
    # "the number on the letter and the number on the permit" asks ONE fact class;
    # only DIFFERENT slot types across the "and" mark a second slot
    assert F._slot_count("which fake number appears on the letter and the permit?") < 2
    assert F._slot_count("what is the fake total cost of gas and electricity?") < 2


def test_multi_slot_synonym_slot_nouns_are_one_class_not_compound() -> None:
    """PR-32 verify round: 'balance and amount due' is standard single-field bill
    phrasing; slot nouns compare by synonym class, not raw word."""
    assert F._slot_count("what is the fake balance and amount due on the account?") < 2
    assert F._slot_count("what is the fake term and duration of the loan?") < 2
    assert F._slot_count("what is the fake account balance and total?") < 2
    # different CLASSES across the 'and' still compound
    assert F._slot_count("what is the fake amount and due date on the invoice?") >= 2


def test_multi_slot_price_and_cost_are_distinct_classes_fail_open_closed() -> None:
    """PR-32 post-merge stress test: a same-class pair is ASSUMED one fact (fails open
    if wrong), so the money class is narrow — price/cost/value are their own classes;
    two-different-money-facts compounds are caught again."""
    assert F._slot_count("what is the fake purchase price and the shipping cost?") >= 2
    assert F._slot_count(
        "what is the fake minimum payment amount and the total cost of the plan?") >= 2
    assert F._slot_count("what is the fake item price and the amount due?") >= 2
    # named residuals, pinned so a change is deliberate: within-class pairs still pass
    # (assumed one fact) — the amount/total/balance merge is the accepted narrow bet
    assert F._slot_count(
        "what is the fake premium amount and the total balance due?") < 2
    assert F._slot_count(
        "what is the fake loan term and the grace period duration?") < 2


def test_proposer_v2_contract_names_the_gates() -> None:
    """The prompt is the other half of each mechanical gate — the contract the model is
    told must match the code that enforces it."""
    assert 'exactly "owner"' in F.PROPOSER_V2
    assert "ONE fact" in F.PROPOSER_V2


# --- v1.1 merge mode (the in-repo replacement for the one-off scratchpad merge) ------------

def _corpus(questions: list[dict[str, Any]]) -> dict[str, Any]:
    return {"format_version": F.FORMAT_VERSION, "questions": questions}


def _cq(question: str, answer: str, source_path: str, *, audit: bool = False
        ) -> dict[str, Any]:
    q: dict[str, Any] = {
        "id": "q2-000", "question": question, "subject": "owner", "answer": answer,
        "answer_variants": [], "notes": "",
        "provenance": {"chunk_id": 1, "source_path": source_path,
                       "source_origin": "docs", "verifier_answer": answer},
    }
    if audit:
        q["audit"] = True
    return q


def test_merge_corpora_dedups_reids_and_redraws_audit() -> None:
    c1 = _corpus([
        _cq("what is my fake policy number?", "P111222", "/fake/a.pdf", audit=True),
        _cq("what fake plate is on the permit?", "P333444", "/fake/b.eml"),
    ])
    c2 = _corpus([
        # duplicate of c1's first question up to normalisation (case/punct)
        _cq("What is my fake POLICY number", "P111222", "/fake/other.pdf"),
        # same (answer, source_path) pair as c1's second — different text, same fact
        _cq("which fake plate appears on the permit?", "P333444", "/fake/b.eml"),
        _cq("what is the third fake value?", "P555666", "/fake/c.pdf"),
    ])
    merged, meta = F.merge_corpora([("runA", c1), ("runB", c2)],
                                   seed=7, audit_fraction=0.34)
    qs = merged["questions"]
    assert [q["id"] for q in qs] == ["q2-001", "q2-002", "q2-003"]
    assert [q["answer"] for q in qs] == ["P111222", "P333444", "P555666"]
    assert [q["provenance"]["factory_run"] for q in qs] == ["runA", "runA", "runB"]
    assert meta["n_merged"] == 3
    assert meta["n_dropped_duplicates"] == 2
    assert meta["kept_per_run"] == {"runA": 2, "runB": 1}
    # audit flags are re-drawn over the merged set, not inherited
    assert len([q for q in qs if q.get("audit")]) == 1  # round(3 * 0.34)
    again, _ = F.merge_corpora([("runA", c1), ("runB", c2)], seed=7, audit_fraction=0.34)
    assert [q["id"] for q in again["questions"] if q.get("audit")] == \
        [q["id"] for q in qs if q.get("audit")]  # seeded — stable


def test_merge_corpora_never_aliases_into_the_input_corpora() -> None:
    """PR-32 review Minor-1: the nightly loop may reuse corpus objects in-process — a
    merged row mutation must never reach back into a source corpus."""
    c1 = _corpus([_cq("what is my fake policy number?", "P111222", "/fake/a.pdf")])
    merged, _ = F.merge_corpora([("runA", c1)], seed=7, audit_fraction=0.5)
    merged["questions"][0]["answer_variants"].append("MUTATED")
    merged["questions"][0]["provenance"]["source_path"] = "MUTATED"
    assert c1["questions"][0]["answer_variants"] == []
    assert c1["questions"][0]["provenance"]["source_path"] == "/fake/a.pdf"


def test_merge_mode_cli_writes_outputs_without_touching_generation(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import life_agent.core.config as LCFG
    monkeypatch.setattr(LCFG, "KB", tmp_path / "kb")
    d1 = tmp_path / "runA"
    d2 = tmp_path / "runB"
    for d, qs in ((d1, [_cq("what is my fake policy number?", "P111222", "/fake/a.pdf")]),
                  (d2, [_cq("what is the other fake value?", "P555666", "/fake/c.pdf")])):
        d.mkdir(parents=True)
        (d / "questions_v2.yaml").write_text(
            yaml.safe_dump(_corpus(qs), sort_keys=False), encoding="utf-8")

    rc = F.main(["--merge", str(d1), str(d2), "--run-id", "merged-test"])

    assert rc == 0
    out = tmp_path / "kb" / "eval" / "factory" / "merged-test"
    merged = yaml.safe_load((out / "questions_v2.yaml").read_text(encoding="utf-8"))
    assert [q["id"] for q in merged["questions"]] == ["q2-001", "q2-002"]
    meta = json.loads((out / "merge_meta.json").read_text(encoding="utf-8"))
    assert meta["n_merged"] == 2
    # no publish without the flag
    assert not (tmp_path / "kb" / "eval" / "questions_v2.yaml").exists()
