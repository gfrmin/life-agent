"""Unit tests for the synthesis grader's pure logic (scripts/run_eval.py).

No live API: the LLM judge is monkeypatched; the classification + rate math are pure.
Run: uv run --project . python -m pytest tests/test_synthesis_grade.py
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "comparison"))

import run_eval as re_


def test_classify_grounded_pass() -> None:
    v = re_._classify_synthesis(faithfulness=3, citation_fidelity=3,
                                structural_unsupported=False, answerable=True)
    assert v["synthesis_pass"] and not v["hallucinated"]


def test_classify_hallucination_on_low_faithfulness() -> None:
    v = re_._classify_synthesis(faithfulness=1, citation_fidelity=2,
                                structural_unsupported=False, answerable=True)
    assert v["hallucinated"] and not v["synthesis_pass"]


def test_classify_hallucination_on_structural_unsupported() -> None:
    # the deterministic guard alone can flag a hallucination even if the judge was lenient
    v = re_._classify_synthesis(faithfulness=2, citation_fidelity=2,
                                structural_unsupported=True, answerable=True)
    assert v["hallucinated"]


def test_classify_honest_abstention() -> None:
    v = re_._classify_synthesis(faithfulness=3, citation_fidelity=3,
                                structural_unsupported=False, answerable=False)
    assert v["abstained_correctly"] and not v["hallucinated"]


def test_synthesis_rates_arithmetic() -> None:
    rows = [
        {"answerable": True, "synthesis_pass": True,
         "hallucinated": False, "abstained_correctly": False},
        {"answerable": True, "synthesis_pass": False,
         "hallucinated": True, "abstained_correctly": False},
        {"answerable": False, "synthesis_pass": False,
         "hallucinated": False, "abstained_correctly": True},
    ]
    r = re_.synthesis_rates(rows)
    assert (r["n"], r["n_answerable"], r["n_unanswerable"]) == (3, 2, 1)
    assert r["grounded_rate"] == 0.5                      # 1 of 2 answerable grounded
    assert abs(r["hallucination_rate"] - 1 / 3) < 1e-9
    assert r["abstention_honesty"] == 1.0


def test_judge_once_parses_strict_json(monkeypatch) -> None:
    import _common as JC

    monkeypatch.setattr(
        JC, "judge_complete",
        lambda s, u, **k: SimpleNamespace(
            text='{"faithfulness": 3, "citation_fidelity": 2}', served_model="gpt-x"),
    )
    out = re_._synthesis_judge_once(
        {"question": "q", "answer": "x"}, "ans", [{"n": 1, "text": "x"}], "RUBRIC")
    assert out["faithfulness"] == 3 and out["citation_fidelity"] == 2 and out["_served"] == "gpt-x"


def test_cache_line_formats_per_stage_hit_rates() -> None:
    cache = {"expand.hit": 9, "expand.miss": 1, "retrieve.miss": 10,
             "synthesize.hit": 10}
    assert re_._cache_line(cache) == (
        "Derivation cache hits: expand 9/10 · retrieve 0/10 · synthesize 10/10")
    assert re_._cache_line({}) == ""  # caching off → no line


def test_synthesis_report_carries_the_cache_line() -> None:
    rates = {"hallucination_rate": 0.0, "n_hallucinated": 0, "n": 1,
             "grounded_rate": 1.0, "n_grounded": 1, "n_answerable": 1,
             "abstention_honesty": None, "n_honest": 0, "n_unanswerable": 0,
             "declined_rate": 0.0, "n_declined": 0}
    row = {"id": "q-001", "faithfulness": 3, "citation_fidelity": 3, "structural_ok": True,
           "hallucinated": False, "synthesis_pass": True, "question": "q?",
           "answerable": True}
    with_cache = re_.format_synthesis_report([row], rates, 8, 1.0, {"synthesize.hit": 1})
    assert "Derivation cache hits: synthesize 1/1" in with_cache
    without = re_.format_synthesis_report([row], rates, 8, 1.0)
    assert "Derivation cache" not in without
