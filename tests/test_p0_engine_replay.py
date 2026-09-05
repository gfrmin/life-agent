"""r41 / P0-2's replay instrument — its own guards. Every one is a mutation target.

The instrument BINDS the warm-up (`shadow.boot_snapshot`, `MembraneSession.boot`) and the
decide; it re-implements neither (`M-7`, seven instances).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import p0_engine_replay as PR

from life_agent.membrane import shadow as SH
from life_agent.membrane import world as W


def _decide(t: int, action: str = "gather", **summary: object) -> dict:
    s = {"n_candidates": 2, "leader_credence": 0.9, "p_none": 0.05, "n_obs": 4,
         "era_split": False, "owner_scoped": True, "grow_pass": False}
    s.update(summary)
    return {"kind": "decide", "t": t, "action": action, "form": "said@1",
            "readouts": {"p1": 0.33, "entropy_bits": 3.9}, "summary": s, "ts": 1.0}


def _boot(n: int, ts: float = 0.0) -> dict:
    return {"kind": "boot", "n_source_records": n, "ts": ts,
            "u_bar": {"u_correct": 1.0, "u_wrong": -9.0, "u_abstain": 0.0}}


def test_the_replay_binds_the_deployed_warm_up() -> None:
    """M-7: the boot it reproduces is the shadow's own, not a copy."""
    assert PR.boot_snapshot is SH.boot_snapshot


def test_epochs_pair_each_decide_with_the_boot_it_ran_under() -> None:
    """A decide is only reproducible against ITS boot's u_bar and warm size, so the pairing
    is the unit of replay. A decide attributed to the wrong boot replays a different world."""
    recs = [_boot(10, ts=1.0), _decide(1), _decide(2), _boot(20, ts=2.0), _decide(3)]
    eps = PR.epochs(recs)
    assert [e["boot"]["n_source_records"] for e in eps] == [10, 20]
    assert [len(e["decides"]) for e in eps] == [2, 1]
    assert eps[1]["decides"][0]["t"] == 3


def test_a_decide_before_any_boot_is_dropped_not_misattributed() -> None:
    """The ledger can begin mid-stream. Attaching such a decide to a later boot would
    reproduce it under a world it never ran in."""
    assert PR.epochs([_decide(1), _boot(10)]) == [{"boot": _boot(10), "decides": []}]


def test_summary_of_rebuilds_the_engines_own_input_type() -> None:
    """Amendment 1's basis: the recorded summary IS world.DecideSummary."""
    s = PR.summary_of(_decide(13))
    assert isinstance(s, W.DecideSummary)
    assert s.n_candidates == 2 and s.leader_credence == 0.9


def test_a_pre_r50_summary_without_the_record_only_field_still_rebuilds() -> None:
    """r50 added `runner_up_credence` to DecideSummary with a default. It is RECORD-ONLY: it
    never enters the tick, so a summary recorded before it existed rebuilds without inventing
    an engine input — the reproduction guarantee is about inputs, and the tick is byte-identical
    with the field absent or present."""
    d = _decide(13)
    assert "runner_up_credence" not in d["summary"]          # a pre-r50 record
    s = PR.summary_of(d)
    assert s.runner_up_credence == 0.0
    with_field = PR.summary_of({**d, "summary": {**d["summary"], "runner_up_credence": 0.3}})
    assert W.shadow_features(s, 1.0) == W.shadow_features(with_field, 1.0)


def test_a_summary_missing_a_field_is_refused_not_defaulted() -> None:
    """Defaulting an absent field would invent an input and call the result a reproduction."""
    d = _decide(13)
    del d["summary"]["p_none"]
    with pytest.raises(ValueError, match="p_none"):
        PR.summary_of(d)


def test_readouts_match_requires_every_recorded_key() -> None:
    """A replay that reproduced only the keys it happened to emit would pass by omission."""
    assert PR._readouts_match({"p1": 0.5}, {"p1": 0.5, "extra": 1})
    assert not PR._readouts_match({"p1": 0.5, "entropy_bits": 3.0}, {"p1": 0.5})
    assert not PR._readouts_match({"p1": 0.5}, {"p1": 0.5000001})


def test_supersession_bound_counts_reactions_after_the_boot(tmp_path: Path) -> None:
    """The addendum's disclosure: reactions supersede, so verdicts replayed today may not be
    the verdicts of that boot. Counted BEFORE the comparison, as an upper bound."""
    p = tmp_path / "reactions.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in [
        {"tx_time": "2020-01-01T00:00:00"}, {"tx_time": "2099-01-01T00:00:00"},
        {"tx_time": "2099-06-01T00:00:00"},
    ]), encoding="utf-8")
    assert PR.supersession_bound(0.0, p) == 3      # epoch 0 -> everything is after
    import datetime as d
    late = d.datetime(2099, 3, 1).timestamp()
    assert PR.supersession_bound(late, p) == 1     # only the 2099-06 row


def test_supersession_bound_is_zero_when_the_log_is_missing(tmp_path: Path) -> None:
    """A missing log is 'nothing known', not a crash — but it must not read as 'nothing to
    disclose' either, which is why the caller prints the bound rather than branching on it."""
    assert PR.supersession_bound(0.0, tmp_path / "absent.jsonl") == 0


def test_an_unreachable_t_is_reported_unreadable_not_failed(capsys) -> None:
    """`t` is an INPUT feature, so a session that cannot reach the recorded `t` compared a
    different engine state. Calling that a mismatch blames the engine for the ledger's own
    shrinkage — `G-3`: a check whose universe is absent reports absence, never a verdict.

    Driven through `main` because the distinction lives in the verdict, not in `replay_one`.
    """
    import p0_engine_replay as PR2

    calls = {}

    def fake_replay(binary, epoch, decide):
        calls["n"] = calls.get("n", 0) + 1
        return {"t_recorded": 193, "t_reached": 70, "verdicts_available": 70,
                "action_recorded": "gather", "action_replayed": "gather",
                "readouts_recorded": {"p1": 0.8}, "readouts_replayed": {"p1": 0.5},
                "action_match": True, "readouts_match": False}

    PR2.replay_one = fake_replay
    try:
        rc = PR2.main(["--binary", "/nonexistent", "--limit", "1",
                       "--shadow", str(_shadow_fixture())])
    finally:
        PR2.replay_one = PR.replay_one
    out = capsys.readouterr().out
    assert "UNREADABLE" in out, out
    assert rc == 2, "no readable row means the run reports UNREADABLE, not a pass or a fail"


def _shadow_fixture() -> Path:
    import tempfile
    p = Path(tempfile.mkdtemp()) / "shadow.jsonl"
    p.write_text(json.dumps(_boot(1644, ts=0.0)) + "\n" + json.dumps(_decide(193)) + "\n",
                 encoding="utf-8")
    return p
