"""Extraction audit (scripts/extraction_audit.py) — hermetic: the class vocabulary and
the delivered-reach rule are frozen in the module docstring; these pin the per-chunk
classifier and the criterion-1 rule that a lever's ceiling is counted in QUESTIONS whose
commit would change, never in chunks or artifacts."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import extraction_audit as EA


def test_classify_chunk_covers_the_frozen_vocabulary() -> None:
    chunk = "the fee is 1,234,567 due at signing (prior 7,654,321)"
    gold, variants = "1,234,567", []
    assert EA.classify_chunk(None, gold, variants, chunk)[0] == "no-cache-record"
    assert EA.classify_chunk({"found": False}, gold, variants, chunk)[0] == "declined"
    # the one-value schema spent its slot on the rival figure
    k, v = EA.classify_chunk(
        {"found": True, "value": "7,654,321", "quote": "prior 7,654,321"},
        gold, variants, chunk)
    assert (k, v) == ("picked-other", "7,654,321")
    # found the gold, but neither quote nor value is verbatim in the chunk
    k2, _ = EA.classify_chunk(
        {"found": True, "value": "1 234 567", "quote": "fee: 1 234 567"},
        gold, variants, chunk)
    assert k2 == "ungrounded"
    # the anomaly class is named, never dropped
    k3, _ = EA.classify_chunk(
        {"found": True, "value": "1,234,567", "quote": "the fee is 1,234,567"},
        gold, variants, chunk)
    assert k3 == "grounded"


def test_classify_accepts_a_variant_spelling_of_the_gold() -> None:
    chunk = "renewal on 24/02/2020 confirmed"
    k, _ = EA.classify_chunk({"found": True, "value": "24/02/2020",
                              "quote": "renewal on 24/02/2020"},
                             "2020-02-24", ["24/02/2020"], chunk)
    assert k == "grounded"


def _row(qid: str, arts: dict[str, list[str]]) -> EA.Row:
    return EA.Row(qid=qid, action="miss", gold="g", artifacts_by_class=arts,
                  counts={c: len(a) for c, a in arts.items()})


def test_delivered_reach_counts_questions_not_chunks() -> None:
    rows = [
        _row("q1", {"declined": ["d1", "d2"]}),          # 2 independent artifacts
        _row("q2", {"declined": ["d1"]}),                # only one document
        _row("q3", {"declined": ["d1"], "ungrounded": ["d2"]}),  # 1+1 across classes
    ]
    # the sub-bar single-observation regime: two independent artifacts required
    assert EA.delivered_reach(rows, EA._FIXABLE, 2) == ["q1", "q3"]
    # a single class alone carries only q1
    assert EA.delivered_reach(rows, ("declined",), 2) == ["q1"]
    # if one clean observation cleared the bar, every fixable question would count
    assert EA.delivered_reach(rows, EA._FIXABLE, 1) == ["q1", "q2", "q3"]
    # an artifact repeated across classes is ONE artifact, never two
    assert EA.delivered_reach([_row("q4", {"declined": ["d1"], "ungrounded": ["d1"]})],
                              EA._FIXABLE, 2) == []


def test_single_obs_credence_reads_the_runs_own_rows() -> None:
    decisions = {
        "a": {"posterior_summary": {"n_obs": 1, "candidates": ["x"],
                                    "credences": [0.80]}},
        "b": {"posterior_summary": {"n_obs": 1, "candidates": ["y"],
                                    "credences": [0.82]}},
        "c": {"posterior_summary": {"n_obs": 1, "candidates": ["z"],
                                    "credences": [0.84]}},
        # excluded: more than one observation, and a multi-candidate row
        "d": {"posterior_summary": {"n_obs": 3, "candidates": ["w"],
                                    "credences": [0.99]}},
        "e": {"posterior_summary": {"n_obs": 1, "candidates": ["p", "q"],
                                    "credences": [0.99, 0.01]}},
    }
    median, n = EA.single_obs_credence(decisions)
    assert (median, n) == (0.82, 3)
    assert EA.single_obs_credence({}) == (None, 0)
