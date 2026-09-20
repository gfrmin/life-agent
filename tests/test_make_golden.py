"""scripts/make_golden.py — the generated golden set keeps only answers known by construction
(hermetic: the model is a scripted callable; every value is synthetic)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import make_golden as MG

from life_agent.core.llm import LLMResult

CHUNK = "Policy schedule. Policy number: ZX-4417-09. Renewal date 2031-03-01."  # PII-OK: synthetic


def _reply(facts: list[dict[str, str]]) -> LLMResult:
    return LLMResult(text=json.dumps({"facts": facts}), in_tokens=1000, out_tokens=100,
                     seconds=0.1, served_model="claude-haiku-4-5-20251001")


def test_parse_facts_reads_the_json_and_tolerates_prose_around_it() -> None:
    text = 'Here: {"facts": [{"question": "q?", "answer": "a"}]} done'
    assert MG.parse_facts(text) == [{"question": "q?", "answer": "a"}]
    assert MG.parse_facts("no json") == []
    assert MG.parse_facts('{"facts": [{"question": "q?"}]}') == []


def test_only_a_verbatim_answer_is_kept() -> None:
    ok = {"question": "What is the insurance policy number?", "answer": "ZX-4417-09"}
    assert MG.reject_reason(ok, CHUNK) is None
    assert MG.reject_reason({**ok, "answer": "ZX 4417 09"}, CHUNK) == "not_verbatim"
    assert MG.reject_reason({**ok, "question": "Is ZX-4417-09 the number?"},
                            CHUNK) == "answer_in_question"
    assert MG.reject_reason({**ok, "answer": "x" * 61}, CHUNK) == "long_answer"


def test_generate_counts_keeps_and_stops_at_the_budget() -> None:
    facts = [{"question": "What is the insurance policy number?", "answer": "ZX-4417-09"},
             {"question": "When does the insurance policy renew?", "answer": "2031-03-01"},
             {"question": "Who is the insurer?", "answer": "Invented Mutual"}]
    chunks = [("a" * 64, 0, CHUNK), ("b" * 64, 3, CHUNK)]
    rows, counts, spend = MG.generate(chunks, lambda s, u: _reply(facts), budget_usd=100.0)
    # the second chunk repeats both questions with the same answers: one row each
    assert [r["answer"] for r in rows] == ["ZX-4417-09", "2031-03-01"]
    assert rows[0]["provenance"] == {"artifact_cache_key": "a" * 64, "chunk_index": 0}
    assert counts["kept"] == 2 and counts["rejected_not_verbatim"] == 2
    assert counts["rejected_duplicate"] == 2
    assert spend > 0
    _, stopped, _ = MG.generate(chunks, lambda s, u: _reply(facts), budget_usd=1e-9)
    assert stopped["chunks"] == 1 and stopped["budget_stop"] == 1


def test_a_question_with_two_answers_is_dropped_everywhere() -> None:
    other = "Policy schedule. Policy number: QW-1000-01."  # PII-OK: synthetic
    q = "What is the insurance policy number?"
    replies = iter([_reply([{"question": q, "answer": "ZX-4417-09"}]),
                    _reply([{"question": q, "answer": "QW-1000-01"}])])
    rows, counts, _ = MG.generate([("a" * 64, 0, CHUNK), ("b" * 64, 0, other)],
                                  lambda s, u: next(replies), budget_usd=100.0)
    assert rows == [] and counts["rejected_ambiguous"] == 2
