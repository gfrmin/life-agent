"""r46c act-conditioning instrument — the load-bearing predicates, hermetic (no engine).

Every declaration the instrument sends is pinned here as a DELTA on the deployed one
(`M-7`): a drift in `world.handshake_decl` / `session.evidence_tick_body` breaks these
tests, never silently reshapes a probe. K7's mutation verification runs against this file.
"""
from __future__ import annotations

import json
import sys
from typing import Any

import pytest

sys.path.insert(0, "scripts")

from membrane import act_conditioning as AC

from life_agent.membrane import coarse as CO
from life_agent.membrane import world as W
from life_agent.membrane.session import evidence_tick_body

U_BAR = {"u_correct": 1.0, "u_abstain": 0.0, "u_wrong": -8.710166,
         "lambda_int": 0.1, "kappa_att": 0.02}


def test_base_decl_is_the_deployed_one_verbatim() -> None:
    assert json.dumps(AC.base_decl(U_BAR), sort_keys=True) == json.dumps(
        W.handshake_decl(U_BAR), sort_keys=True)


def test_mirrored_decl_adds_exactly_one_name_and_one_guard() -> None:
    base, mirrored = W.handshake_decl(U_BAR), AC.mirrored_decl(U_BAR)
    bw, mw = base["world"], mirrored["world"]
    assert mw["namespace"] == [*bw["namespace"], AC.MIRROR_NAME]
    assert mw["guards"] == [*bw["guards"],
                            {"name": AC.MIRROR_NAME, "grid": [1.5, 2.5, 3.5]}]
    for key in ("menu", "codebooks", "clock", "utility"):
        assert mw[key] == bw[key], key


def test_observer_decl_moves_act_from_menu_to_guard() -> None:
    base, obs = W.handshake_decl(U_BAR), AC.observer_decl(U_BAR)
    bw, ow = base["world"], obs["world"]
    assert ow["menu"] == []
    assert ow["guards"] == [*bw["guards"],
                            {"name": W.ACT_NAME, "grid": [1.5, 2.5, 3.5]}]
    assert ow["namespace"] == bw["namespace"]
    for key in ("codebooks", "clock", "utility"):
        assert ow[key] == bw[key], key


def test_pinned_decl_is_a_one_point_menu() -> None:
    pinned = AC.pinned_decl(U_BAR, "gather")
    assert pinned["world"]["menu"] == [{"name": W.ACT_NAME, "grid": [2.0]}]
    base = W.handshake_decl(U_BAR)
    for key in ("namespace", "guards", "codebooks", "clock", "utility"):
        assert pinned["world"][key] == base["world"][key], key


def test_act_value_binds_the_declared_projection() -> None:
    # _VALUE_FOR[REAL_TO_MEMBRANE[x]] — the pre-registration's one projection.
    assert AC.act_value("report") == 4.0
    assert AC.act_value("abstain") == 1.0
    assert AC.act_value("gather") == 2.0
    assert AC.act_value("ask_clarify") == 3.0
    assert AC.act_value("not-an-action") is None  # named exclusion, never a raise


def test_observer_tick_is_the_declared_body_minus_the_menu() -> None:
    feats = {"t": 3.0, "n-obs=0": 1.0, W.ACT_NAME: 2.0}
    body = evidence_tick_body(feats, 1)
    expected = {k: v for k, v in body.items() if k != "menu"}
    assert AC.observer_tick(feats, 1) == expected


def test_mirrored_tick_carries_the_mirror_feature_and_the_menu() -> None:
    feats = {"t": 3.0, "n-obs=0": 1.0}
    tick = AC.mirrored_tick(feats, 0, 4.0)
    assert tick == evidence_tick_body({**feats, AC.MIRROR_NAME: 4.0}, 0)


class _StubClient:
    """Captures request order; replies like the wire (act on decide, observed on fold)."""

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    def request(self, obj: dict[str, Any]) -> dict[str, Any]:
        self.sent.append(json.loads(json.dumps(obj)))  # deep copy at send time
        tick = obj.get("tick")
        if tick is None:
            return {"ok": True, "models": 1}
        if "evidence" in tick:
            return {"observed": True, "loss_bits": 1.0}
        return {"act": {W.ACT_NAME: 1.0}, "p1": 0.5, "entropy_bits": 1.0}


def _rows() -> list[tuple[W.DecideSummary, int, str]]:
    mk = lambda n: W.DecideSummary(  # noqa: E731
        n_candidates=n, leader_credence=0.9, p_none=0.05, n_obs=n,
        era_split=False, owner_scoped=False, grow_pass=False)
    return [(mk(1), 1, "report"), (mk(2), 0, "abstain")]


def test_ceiling_pass_is_prequential_probe_before_fold() -> None:
    client = _StubClient()
    out = AC.ceiling_pass(client, _rows(), conditional_values=[1.0, 2.0, 3.0, 4.0])
    ticks = [m["tick"] for m in client.sent if "tick" in m]
    evidence_idx = [i for i, t in enumerate(ticks) if "evidence" in t]
    assert len(evidence_idx) == 2
    # every decide for row i precedes row i's evidence tick; the mirror feature appears
    # on each conditional probe (there is no menu-less "plain" decide — arm B's door
    # refuses one) and on the fold tick (the recorded act).
    first_fold = evidence_idx[0]
    decides_before = [t for t in ticks[:first_fold] if "evidence" not in t]
    assert len(decides_before) == 4  # four conditional probes, one per grid value
    assert [t["features"][AC.MIRROR_NAME] for t in decides_before] == [1.0, 2.0, 3.0, 4.0]
    fold = ticks[first_fold]
    assert fold["features"][AC.MIRROR_NAME] == AC.act_value("report")
    assert len(out) == 2 and all("p1_by_value" in r for r in out)


def test_ceiling_pass_skips_and_names_an_unmapped_action() -> None:
    client = _StubClient()
    rows = [*_rows(), (_rows()[0][0], 1, "not-an-action")]
    out = AC.ceiling_pass(client, rows, conditional_values=[1.0])
    assert len(out) == 3
    assert out[2]["skipped"] == "unmapped-action"
    ticks = [m["tick"] for m in client.sent if "tick" in m]
    assert sum(1 for t in ticks if "evidence" in t) == 2  # the unmapped row never folds


def test_flip_locator_finds_a_true_flip_of_the_deployed_rule() -> None:
    payload = {"applied_probes": [], "transforms": [], "u_bar": U_BAR,
               "candidates": ["a", "b"]}
    dec = {"effector": "abstain", "credences": [0.9, 0.1], "p_none": 0.0}
    flip = AC.locate_commit_bar(payload, dec)
    assert flip is not None
    lo, _ = CO.map_action(payload, dec, "gather", {"p1": flip - 1e-6})
    hi, _ = CO.map_action(payload, dec, "gather", {"p1": flip + 1e-6})
    assert lo["effector"] != "report"
    assert hi["effector"] == "report"


def test_run_stamp_names_the_tree_and_the_instrument_mtimes() -> None:
    stamp = AC.run_stamp()
    for key in ("git_head", "dirty", "mtimes", "started"):
        assert key in stamp, key
    assert any(p.endswith("act_conditioning.py") for p in stamp["mtimes"])


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
