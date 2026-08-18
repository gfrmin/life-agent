"""Live readout (scripts/live_readout.py) — hermetic. Pins the live/eval discriminator,
the §4.4 decision_id verdict join, and the staleness headline the MVP exit test reads."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import live_readout as LR


def _dec(did: str, day: str, *, family: str = "lookup", action: str = "report",
         n_obs: int | None = 2, run_id: str = "", cost: float = 0.01,
         latency: float | None = 3.0) -> dict:
    row = {"decision_id": did, "tx_time": f"{day}T09:00:00+00:00", "family": family,
           "chosen_action": action, "cost_usd": cost, "latency_s": latency,
           "posterior_summary": {"n_obs": n_obs}}
    if run_id:
        row["run_id"] = run_id
    return row


def test_gate_rows_are_never_live() -> None:
    assert LR.is_live({"run_id": ""}) is True
    assert LR.is_live({}) is True
    assert LR.is_live({"run_id": "gate-20260817T195737"}) is False


def test_summarize_counts_only_live_rows_and_joins_verdicts() -> None:
    decisions = [
        _dec("d1", "2026-08-01"),
        _dec("d2", "2026-08-01", action="abstain"),
        _dec("d3", "2026-08-02", family="narrative", n_obs=None),
        _dec("g1", "2026-08-03", run_id="gate-20260817T195737"),   # eval — excluded
    ]
    reactions = [
        {"decision_id": "d1", "valence": "good", "kind": "verdict"},
        {"decision_id": "d2", "valence": "bad", "kind": "verdict"},
        {"decision_id": "g1", "valence": "good", "kind": "verdict"},   # binds an eval row
        {"decision_id": "unknown", "valence": "good", "kind": "verdict"},
    ]
    r = LR.summarize(decisions, reactions, date(2026, 8, 5))
    assert r.n_live == 3 and r.n_posterior == 2
    assert r.answer_rate == 0.5                       # one report of two posterior rows
    assert r.by_family == {"lookup": 2, "narrative": 1}
    assert r.first_day == "2026-08-01" and r.last_day == "2026-08-02"
    assert r.days_since_last == 3 and r.active_days == 2
    # only verdicts binding a LIVE decision join; the eval-bound and orphan ones do not
    assert (r.n_verdicts, r.n_verdicts_joined) == (4, 2)
    assert r.verdict_split == {"good": 1, "bad": 1}
    assert r.spend_usd == 0.03


def test_staleness_is_the_headline() -> None:
    fresh = LR.summarize([_dec("d1", "2026-08-18")], [], date(2026, 8, 18))
    assert fresh.days_since_last == 0
    assert "**LIVE**" in LR.render(fresh)
    stale = LR.summarize([_dec("d1", "2026-08-06")], [], date(2026, 8, 18))
    assert "IDLE — 12 days since the last live decision" in LR.render(stale)


def test_empty_stream_says_so_plainly() -> None:
    r = LR.summarize([], [], date(2026, 8, 18))
    assert r.n_live == 0 and r.days_since_last is None
    assert "never run" in LR.render(r)
