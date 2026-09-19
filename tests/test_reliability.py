"""D-2 — one reliability posterior per edge: reliability.py.

A Beta prior declared per (edge, cell) in ONE table, conditioned on a 0/1 stream by the
exact conjugate fold, read back as (alpha, beta) or as a mean.

Run: uv run --project . python -m pytest tests/test_reliability.py
"""
from __future__ import annotations

from pathlib import Path

import pytest

from life_agent.core import reliability as REL


def test_the_prior_table_declares_both_edges_in_one_home() -> None:
    # the extractor's wide Beta(4,4) and the claim instrument's three audit cells —
    # the exact priors the two instances declared before the unification
    assert REL.PRIORS[("extract", "value")] == (4.0, 4.0)
    assert REL.PRIORS[("eval_claim", "verified")] == (3.0, 2.0)
    assert REL.PRIORS[("eval_claim", "unsupported")] == (1.0, 3.0)
    assert REL.PRIORS[("eval_claim", "unverifiable")] == (2.0, 2.0)
    assert len(REL.PRIORS) == 4


def test_reliability_is_the_conjugate_fold() -> None:
    assert REL.reliability("eval_claim", "verified", []) == (3.0, 2.0)
    assert REL.reliability("eval_claim", "verified", [1.0, 0.0, 1.0]) == (5.0, 3.0)
    assert REL.reliability("extract", "value", [1.0, 0.0, 0.0]) == (5.0, 6.0)


def test_mean_is_alpha_over_the_total() -> None:
    assert REL.mean("extract", "value", [1.0]) == 5.0 / 9.0


def test_an_undeclared_edge_cell_is_loud() -> None:
    with pytest.raises(ValueError, match="nonsense"):
        REL.reliability("extract", "nonsense", [])


def test_the_fold_lives_once() -> None:
    # drift gate: the instruments BIND the one fold — no second Beta fold in lookup.
    src = Path(__file__).resolve().parent.parent / "src/life_agent/core"
    lookup_src = (src / "lookup.py").read_text(encoding="utf-8")
    assert '"type": "beta"' not in lookup_src


def test_the_extractor_mean_replays_the_recorded_rho() -> None:
    """m5-base's 102 A-loop questions each opened with the rho the skin read off the recorded
    outcomes log; the conjugate fold over that snapshot reproduces it bit-for-bit."""
    import json
    import os

    from life_agent.core import lookup as LK

    root = Path(os.environ.get("LIFE_AGENT_KB") or "/nonexistent")
    directory = root / "eval/collapse-fixtures/m5-base"
    if not (directory / "snapshots/outcomes.snapshot").is_file():
        pytest.skip("needs the owner's KB ($LIFE_AGENT_KB with the m5-base collapse fixtures); "
                    "owner data, not buildable")
    opened: list[float] = []
    for path in sorted(directory.glob("m5-base-aloop-*.json")):
        wire = json.loads(path.read_text(encoding="utf-8"))["wire"]
        decides = [x for x in wire if x["seam"] == "http"
                   and str(x["request"].get("url", "")).endswith("/decide")]
        if decides:  # two questions never reached a decide
            opened.append(decides[0]["request"]["payload"]["rho"])
    assert len(opened) == 102 and len(set(opened)) == 1
    assert LK.extractor_reliability_mean(directory / "snapshots/outcomes.snapshot") == opened[0]
