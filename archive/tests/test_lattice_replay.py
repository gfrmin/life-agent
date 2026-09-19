"""Hermetic tests for the P3-seed replay experiment (no engine).

The load-bearing guarantee is a DRIFT GUARD: the "full" lattice variant's handshake and
features must be byte-identical to the frozen `world.handshake_decl`/`world.shadow_features`.
That identity is the whole basis of register §17.4's claim that the FULL run reproduces the
live folded engine — if the experiment's baseline ever diverged from the real world, the
smoke-reproduction result would be meaningless.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import membrane.lattice_replay as L

from life_agent.membrane import session as SS
from life_agent.membrane import world as W

U_BAR = {
    "u_correct": 1.0, "u_abstain": 0.0, "u_wrong": -5.9395, "u_hedged": 0.3964,
    "lambda_int": 1.0009, "kappa_att": 0.0344,
}


def _summary(**kw: object) -> W.DecideSummary:
    base: dict[str, object] = {
        "n_candidates": 2, "leader_credence": 0.83, "p_none": 0.1, "n_obs": 3,
        "era_split": False, "owner_scoped": False, "grow_pass": False,
    }
    base.update(kw)
    return W.DecideSummary(**base)  # type: ignore[arg-type]


def test_full_indicator_names_match_the_frozen_world() -> None:
    assert L.indicator_names_for(L.ALL_FAMILIES) == W.indicator_names()


def test_full_handshake_is_byte_identical_to_the_frozen_world() -> None:
    assert L.handshake_for(U_BAR, L.ALL_FAMILIES) == W.handshake_decl(U_BAR)


def test_full_features_match_the_frozen_world_across_shapes() -> None:
    for s in (
        _summary(),
        _summary(leader_credence=None),          # unknown leader → declared at 0.0 (r44)
        _summary(p_none=None),
        _summary(era_split=True, owner_scoped=True, grow_pass=True),
        _summary(n_candidates=0, n_obs=0, leader_credence=0.2, p_none=0.9),
    ):
        for t in (0.0, 7.0):
            assert L.features_for(s, t, L.ALL_FAMILIES) == W.shadow_features(s, t)


def test_narrowing_drops_the_other_families() -> None:
    s = _summary(leader_credence=0.95, p_none=0.3, n_candidates=2, n_obs=3)
    feats = L.features_for(s, 0.0, ["leader-credence"])
    # no p-none/n-candidates/n-obs/flags in the NAMESPACE; the kept family is fully covered
    assert set(feats) == {"t", *L.indicator_names_for(["leader-credence"])}
    assert [k for k, v in feats.items() if v == 1.0] == ["leader-credence=ge90"]
    names = L.indicator_names_for(["leader-credence"])
    assert names == [f"leader-credence={b}" for b in W._CREDENCE_BUCKETS]


def test_commits_respond_matches_the_break_even() -> None:
    # respond iff p1 > (u_abstain - u_wrong)/(u_correct - u_wrong) = 0.8559 under U_BAR
    be = (0.0 - U_BAR["u_wrong"]) / (U_BAR["u_correct"] - U_BAR["u_wrong"])
    assert not L.commits_respond(U_BAR, be - 0.01)
    assert L.commits_respond(U_BAR, be + 0.01)


def test_evidence_tick_is_the_session_declaration_not_a_second_spelling() -> None:
    """One relation, ONE declaration (`M6`).

    r45 found `session.observe_verdict` sending a menu-less evidence tick that HEAD
    refuses outright, and then found the SAME body re-spelled in this script and in
    `p3_gate.py` — one relation with three declarations, which is exactly how the
    value-join defect survived M6 (r34-r38). Repairing only the session would have left
    r46's own replay tooling silently broken on HEAD. This pins every sender to the one
    declaration, so the next change cannot fix one and miss two.
    """
    s = _summary()
    for families in (L.ALL_FAMILIES, ["leader-credence"]):
        for t, y in ((0.0, 1), (7.0, 0)):
            assert L.evidence_tick_for(s, t, families, y) == {
                "tick": SS.evidence_tick_body(L.features_for(s, t, families), y)}


def test_the_evidence_tick_declaration_carries_the_menu() -> None:
    """The reason the declaration exists: HEAD requires the declared namespace covered
    exactly, `act` is in it, and `shadow_features` never emits `act` -- so the menu is the
    only supplier and a menu-less evidence tick is refused."""
    body = SS.evidence_tick_body({"t": 0.0}, 1)
    assert body["menu"] == [W.ACT_NAME]
    assert body["evidence"] == 1
