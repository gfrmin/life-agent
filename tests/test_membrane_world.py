"""Hermetic tests for the answer-domain membrane world (life_agent.membrane.world).

No wire, no subprocess: these pin the pure data/functions Task 2 produces — the
canonical per-tick feature encoding (:func:`shadow_features`), the world's declared
namespace/menu/utility, and the reduction of the executor's live shapes (payload/dec
dicts from ``core/executor.py``) and the decision log's replay shape
(``DecisionEvent.posterior_summary``) to one canonical :class:`DecideSummary`. Fixture
values below are synthetic (public repo, PRINCIPLES §12) — no owner data.
"""
from __future__ import annotations

import pytest

from life_agent.membrane import world as W

# The REAL utility posterior, as GET :8798/utility served it on 2026-07-11 — kept here as a
# named fixture (7 scalar utility means; no owner data, PRINCIPLES §12) because several of
# the properties below are only interesting where the live numbers differ MATERIALLY from
# world.utility_rows' fallback defaults: the reaction loop has already narrowed u_wrong from
# the -9.0 default to about -5.94, which moves every utility-derived threshold. A test that
# only ever exercised the defaults is how a threshold that is really a FUNCTION of utility
# got published as the constant 0.9.
LIVE_U_BAR: dict[str, float] = {
    "u_correct": 1.0, "u_abstain": 0.0, "u_wrong": -5.9395, "u_wrong_scoped": -2.0827,
    "u_hedged": 0.3964, "lambda_int": 1.0009, "kappa_att": 0.0344,
}

# --- AFFORDANCES / MENU_IDS / ID_TO_ACTION (drift-gate pins) -----------------------------


def test_affordances_menu_ids_and_id_to_action_are_consistent() -> None:
    assert W.AFFORDANCES == (
        ("gather", 4), ("ask", 3), ("abstain", 2), ("respond", 1),
    )
    assert W.MENU_IDS == [4, 3, 2, 1]
    assert W.ID_TO_ACTION == {4: "gather", 3: "ask", 2: "abstain", 1: "respond"}


def test_utility_forms_and_think_posture() -> None:
    assert W.UTILITY_FORMS == ("table@1", "latent@1")
    assert W.THINK_POSTURE == "abstain"


# --- indicator_names(): the single source of the shadow-feature vocabulary ---------------


def test_indicator_names_is_stable_and_exhaustive() -> None:
    # Pinned literal order — a drift here means shadow_features/handshake_decl silently
    # disagree with the declared vocabulary (CLAUDE.md: drift-gate single-source constants).
    assert W.indicator_names() == [
        "n-candidates=0", "n-candidates=1", "n-candidates=2plus",
        "leader-credence=lt50", "leader-credence=50to70", "leader-credence=70to80",
        "leader-credence=80to90", "leader-credence=ge90",
        "p-none=lt20", "p-none=20to50", "p-none=ge50",
        "n-obs=0", "n-obs=1to2", "n-obs=3plus",
        "era-split=1", "owner-scoped=1", "grow-pass=1",
    ]


def test_indicator_names_has_no_duplicates() -> None:
    names = W.indicator_names()
    assert len(names) == len(set(names))


# --- summary_from_payload(): the live path ------------------------------------------------


def _summary(**kw: object) -> W.DecideSummary:
    defaults: dict[str, object] = dict(
        n_candidates=0, leader_credence=None, p_none=None, n_obs=0,
        era_split=False, owner_scoped=False, grow_pass=False,
    )
    defaults.update(kw)
    return W.DecideSummary(**defaults)  # type: ignore[arg-type]


def test_summary_from_payload_reads_candidates_observations_and_flags() -> None:
    payload = {
        "candidates": ["A", "B", "C"],
        "observations": [{"o": 1}, {"o": 2}],
        "era_split": True,
        "owner_scoped": True,
    }
    dec = {"credences": [0.2, 0.5, 0.3], "p_none": 0.1}

    s = W.summary_from_payload(payload, dec)

    assert s == _summary(n_candidates=3, leader_credence=0.5, p_none=0.1, n_obs=2,
                          era_split=True, owner_scoped=True, grow_pass=False)


def test_summary_from_payload_empty_credences_and_none_p_none() -> None:
    payload = {"candidates": [], "observations": [], "era_split": False, "owner_scoped": False}
    dec = {"credences": [], "p_none": None}

    s = W.summary_from_payload(payload, dec)

    assert s.n_candidates == 0
    assert s.leader_credence is None
    assert s.p_none is None
    assert s.n_obs == 0


def test_summary_from_payload_grow_pass_true_only_when_grow_block_present() -> None:
    base = {"candidates": ["A"], "observations": [], "era_split": False, "owner_scoped": False}
    dec = {"credences": [0.9], "p_none": 0.0}

    without_grow = W.summary_from_payload(base, dec)
    with_grow = W.summary_from_payload({**base, "sensors": {"extracted": "some"},
                                        "grow": {"actuators": []}}, dec)

    assert without_grow.grow_pass is False
    assert with_grow.grow_pass is True


# --- summary_from_decision_event(): the warm/replay path ----------------------------------


def test_summary_from_decision_event_reads_lookup_shaped_posterior_summary() -> None:
    event = {
        "family": "lookup",
        "posterior_summary": {
            "candidates": ["X", "Y"], "credences": [0.3, 0.6],
            "p_none": 0.05, "n_obs": 4, "n_indeterminate": 0,
        },
    }

    s = W.summary_from_decision_event(event)

    assert s.n_candidates == 2
    assert s.leader_credence == 0.6
    assert s.p_none == 0.05
    assert s.n_obs == 4


def test_summary_from_decision_event_flags_are_always_false() -> None:
    event = {
        "family": "lookup",
        "posterior_summary": {"candidates": ["X"], "credences": [0.9],
                              "p_none": 0.0, "n_obs": 1},
    }

    s = W.summary_from_decision_event(event)

    assert s.era_split is False
    assert s.owner_scoped is False
    assert s.grow_pass is False


def test_summary_from_decision_event_degrades_on_narrative_shaped_posterior_summary() -> None:
    # narrative's posterior_summary carries no candidates/credences/n_obs keys — the reduction
    # must degrade to "no candidates known" rather than raise.
    event = {
        "family": "narrative",
        "posterior_summary": {
            "n_proposed": 3, "n_included": 1, "marginal_credence": 0.7,
            "abstain_reason": None, "cells": {}, "coverage": [], "coverage_n": 0,
        },
    }

    s = W.summary_from_decision_event(event)

    assert s.n_candidates == 0
    assert s.leader_credence is None
    assert s.p_none is None
    assert s.n_obs == 0


# --- shadow_features(): bucket boundaries --------------------------------------------------


@pytest.mark.parametrize("n,bucket", [(0, "0"), (1, "1"), (2, "2plus"), (5, "2plus")])
def test_shadow_features_n_candidates_buckets(n: int, bucket: str) -> None:
    feats = W.shadow_features(_summary(n_candidates=n), t=0.0)
    assert feats[f"n-candidates={bucket}"] == 1.0


@pytest.mark.parametrize("credence,bucket", [
    (0.0, "lt50"), (0.49, "lt50"),
    (0.5, "50to70"), (0.69, "50to70"),
    (0.7, "70to80"), (0.79, "70to80"),
    (0.8, "80to90"), (0.89, "80to90"),
    (0.9, "ge90"), (1.0, "ge90"),
])
def test_shadow_features_leader_credence_boundaries(credence: float, bucket: str) -> None:
    feats = W.shadow_features(_summary(leader_credence=credence), t=0.0)
    assert feats[f"leader-credence={bucket}"] == 1.0
    # exactly one leader-credence indicator fires
    fired = [k for k in feats if k.startswith("leader-credence=")]
    assert fired == [f"leader-credence={bucket}"]


def test_shadow_features_leader_credence_none_emits_no_indicator() -> None:
    feats = W.shadow_features(_summary(leader_credence=None), t=0.0)
    assert not any(k.startswith("leader-credence=") for k in feats)


@pytest.mark.parametrize("p_none,bucket", [
    (0.0, "lt20"), (0.19, "lt20"),
    (0.2, "20to50"), (0.49, "20to50"),
    (0.5, "ge50"), (1.0, "ge50"),
])
def test_shadow_features_p_none_boundaries(p_none: float, bucket: str) -> None:
    feats = W.shadow_features(_summary(p_none=p_none), t=0.0)
    assert feats[f"p-none={bucket}"] == 1.0
    fired = [k for k in feats if k.startswith("p-none=")]
    assert fired == [f"p-none={bucket}"]


def test_shadow_features_p_none_none_emits_no_indicator() -> None:
    feats = W.shadow_features(_summary(p_none=None), t=0.0)
    assert not any(k.startswith("p-none=") for k in feats)


@pytest.mark.parametrize("n,bucket", [(0, "0"), (1, "1to2"), (2, "1to2"), (3, "3plus"),
                                      (10, "3plus")])
def test_shadow_features_n_obs_buckets(n: int, bucket: str) -> None:
    feats = W.shadow_features(_summary(n_obs=n), t=0.0)
    assert feats[f"n-obs={bucket}"] == 1.0


def test_shadow_features_flags_present_only_when_true() -> None:
    on = W.shadow_features(_summary(era_split=True, owner_scoped=True, grow_pass=True), t=0.0)
    off = W.shadow_features(_summary(era_split=False, owner_scoped=False, grow_pass=False), t=0.0)

    assert on["era-split=1"] == 1.0
    assert on["owner-scoped=1"] == 1.0
    assert on["grow-pass=1"] == 1.0
    assert "era-split=1" not in off
    assert "owner-scoped=1" not in off
    assert "grow-pass=1" not in off


def test_shadow_features_t_passthrough() -> None:
    feats = W.shadow_features(_summary(), t=417.0)
    assert feats["t"] == 417.0


def test_shadow_features_all_emitted_keys_are_declared_indicators() -> None:
    declared = set(W.indicator_names())
    s = _summary(n_candidates=2, leader_credence=0.75, p_none=0.3, n_obs=5,
                 era_split=True, owner_scoped=True, grow_pass=True)
    feats = W.shadow_features(s, t=1.0)
    emitted = {k for k in feats if k != "t"}
    assert emitted <= declared


# --- utility_rows(): table@1 arithmetic + fallbacks ----------------------------------------


def test_utility_rows_uses_declared_fallbacks_on_empty_u_bar() -> None:
    rows = W.utility_rows({})
    by_fire = {r["fire"]: r for r in rows if "fire" in r}

    assert by_fire[1]["u"] == [-9.0, 1.0]         # respond, u_wrong fallback -9.0
    assert by_fire[2]["u"] == [0.0, 0.0]          # abstain, status-quo
    # gather/ask are priced as MYOPIC PERFECT INFORMATION (utility_rows' declared bake-in):
    # [u_abstain - cost, u_correct - cost] — having gathered, you take the correct act. NOT
    # [-cost, -cost]: a row constant in y is a pure cost, and a pure cost can never beat
    # abstain at any p1, which would make the whole information menu unfirable.
    assert by_fire[3]["u"] == [-0.1, 0.9]         # ask, lambda_int fallback 0.1
    assert by_fire[4]["u"] == [-0.02, 0.98]       # gather, kappa_att fallback 0.02


def test_utility_rows_honours_custom_u_bar() -> None:
    rows = W.utility_rows({"u_wrong": -4.0, "lambda_int": -0.3, "kappa_att": 0.5})
    by_fire = {r["fire"]: r for r in rows if "fire" in r}

    assert by_fire[1]["u"] == [-4.0, 1.0]
    assert by_fire[3]["u"] == [-0.3, 0.7]         # abs(-0.3) == 0.3, charged on both outcomes
    assert by_fire[4]["u"] == [-0.5, 0.5]


def test_utility_rows_information_actions_are_not_constant_in_y() -> None:
    """The regression this world shipped with: `gather -> [-g, -g]` and `ask -> [-q, -q]`
    are CONSTANT in y, i.e. pure costs against `abstain -> [0, 0]` — so EU(gather) = -g < 0
    = EU(abstain) at EVERY p1 and every u_bar, abstain strictly dominates the entire
    information menu, and a menu whose whole point is effort allocation can never fire one.
    Pinned as a property (u(y=1) > u(y=0) for both), not as two magic numbers."""
    for u_bar in ({}, {"u_wrong": -5.9395, "lambda_int": 1.0009, "kappa_att": 0.0344}):
        pairs = W.utility_by_action(u_bar)
        for action in ("gather", "ask"):
            u0, u1 = pairs[action]
            assert u1 > u0, f"{action} is constant in y under {u_bar} — it can never fire"


def test_utility_rows_covers_every_menu_id() -> None:
    rows = W.utility_rows({})
    fired_ids = {r["fire"] for r in rows if "fire" in r}
    assert fired_ids == set(W.MENU_IDS)


@pytest.mark.parametrize("u_bar", [
    {},                                                            # the declared fallbacks
    {"u_wrong": -9.0, "lambda_int": 0.1, "kappa_att": 0.02},       # the fallbacks, explicit
    LIVE_U_BAR,                                                    # the real posterior
    {"u_wrong": -0.5, "lambda_int": 3.0, "kappa_att": 2.0},        # costs above the answer
])
def test_utility_rows_think_sentinel_is_strictly_dominated(u_bar: dict[str, float]) -> None:
    """Re-derived from the rows themselves (min entry - 1.0), so it stays strictly worse
    than every real row at EVERY p1 under the NEW row shapes too — including a u_bar whose
    effort costs exceed the value of a correct answer."""
    rows = W.utility_rows(u_bar)
    internal = [r for r in rows if r.get("internal") == "think"]
    assert len(internal) == 1
    u0, u1 = internal[0]["u"]
    assert u0 == u1
    other_values = [v for r in rows if "fire" in r for v in r["u"]]
    assert u0 < min(other_values)
    for p1 in (0.0, 0.25, 0.5, 0.75, 1.0):  # dominated in EU, not just entrywise
        assert u0 < min(W.eu_by_action(u_bar, p1).values())


# --- EU arithmetic, argmax, and the respond-reachability threshold ---------------------------


def test_eu_by_action_is_the_declared_table_read_at_p1() -> None:
    eus = W.eu_by_action(LIVE_U_BAR, 0.5)
    assert eus["abstain"] == pytest.approx(0.0)
    assert eus["respond"] == pytest.approx(0.5 * 1.0 + 0.5 * -5.9395)
    assert eus["gather"] == pytest.approx(0.5 * 1.0 - 0.0344)


def test_argmax_action_resolves_ties_first_listed() -> None:
    """At p1 exactly on gather's own break-even against abstain, the two tie — and
    AFFORDANCES order (gather first) decides, the wire's own rule."""
    g = abs(LIVE_U_BAR["kappa_att"])
    eus = W.eu_by_action(LIVE_U_BAR, g)  # EU(gather) == EU(abstain) == 0 here
    assert eus["gather"] == pytest.approx(eus["abstain"])
    assert W.argmax_action(LIVE_U_BAR, g) == "gather"


def test_respond_threshold_is_a_function_of_utility_not_a_constant() -> None:
    """The false claim this pins against: "respond needs p1 > 0.9" was TRUE only at the
    world's FALLBACK u_wrong=-9.0 — and only against abstain. Both parts move with the
    posterior, so both are derived, never hard-coded."""
    default_vs_abstain = (0.0 - (-9.0)) / (1.0 - (-9.0))
    live_vs_abstain = (0.0 - LIVE_U_BAR["u_wrong"]) / (1.0 - LIVE_U_BAR["u_wrong"])
    assert default_vs_abstain == pytest.approx(0.9)
    assert live_vs_abstain == pytest.approx(0.8559, abs=1e-4)  # the live bar is LOWER

    # ...but the engine argmaxes over the WHOLE menu, so the binding bar is respond vs the
    # best information action, not vs abstain. Under the perfect-information bake-in gather
    # is worth far more than abstain, so the real bar is far higher than either number above.
    whole_menu = W.respond_threshold(LIVE_U_BAR)
    assert whole_menu is not None
    assert whole_menu == pytest.approx(0.9942, abs=1e-4)
    assert whole_menu > live_vs_abstain


def test_respond_threshold_agrees_with_argmax_on_both_sides() -> None:
    for u_bar in ({}, LIVE_U_BAR):
        threshold = W.respond_threshold(u_bar)
        assert threshold is not None
        assert W.argmax_action(u_bar, threshold - 1e-6) != "respond"
        assert W.argmax_action(u_bar, min(1.0, threshold + 1e-6)) == "respond"


def test_ask_is_pointwise_dominated_by_gather_whenever_interrupting_costs_more() -> None:
    """gather and ask carry the same payoff shape and differ only by cost, so q >= g makes
    ask unfirable at ANY credence. At the live posterior q ~ 1.0 vs g ~ 0.03: ask is dead by
    ~30x — a consequence of WHERE the exchange rates are sourced (register item 6), surfaced
    by the demand ledger rather than buried."""
    pairs = W.utility_by_action(LIVE_U_BAR)
    (g0, g1), (a0, a1) = pairs["gather"], pairs["ask"]
    assert g0 > a0 and g1 > a1
    assert all(W.argmax_action(LIVE_U_BAR, p1) != "ask" for p1 in (0.0, 0.3, 0.5, 0.9, 1.0))


# --- latent_utility_decl(): the latent@1 form -----------------------------------------------


def test_latent_utility_decl_first_residual_is_theta_ask() -> None:
    decl = W.latent_utility_decl({})
    assert decl["form"] == "latent@1"
    residuals = decl["residuals"]
    assert residuals[0]["name"] == "theta_ask"


def test_latent_utility_decl_grid_is_strictly_positive_and_ascending_on_defaults() -> None:
    decl = W.latent_utility_decl({})
    grid = decl["residuals"][0]["grid"]
    assert all(v > 0 for v in grid)
    assert grid == sorted(grid)
    assert len(grid) == len(set(grid))  # strictly ascending, no ties


def test_latent_utility_decl_grid_stays_ascending_for_a_realistic_large_lambda_int() -> None:
    # the example utility model's lambda_int prior is centered at 1.0 — far above the wire
    # spec's golden-example floor (0.05); the grid must not collide with the fixed 0.1/0.2/0.4
    # points from the golden example.
    decl = W.latent_utility_decl({"lambda_int": 1.0})
    grid = decl["residuals"][0]["grid"]
    assert all(v > 0 for v in grid)
    assert grid == sorted(grid)
    assert len(grid) == len(set(grid))


def test_latent_utility_decl_floor_equals_q() -> None:
    decl = W.latent_utility_decl({"lambda_int": -0.3})
    grid = decl["residuals"][0]["grid"]
    assert grid[0] == pytest.approx(0.3)


def test_latent_utility_decl_clamps_zero_lambda_int_to_a_positive_floor() -> None:
    decl = W.latent_utility_decl({"lambda_int": 0.0})
    grid = decl["residuals"][0]["grid"]
    assert grid[0] == pytest.approx(1e-6)
    assert grid == sorted(grid)
    assert len(grid) == len(set(grid))  # strictly ascending, no ties
    assert all(g > 0 for g in grid)


def test_latent_utility_decl_declared_tau_price_gauge() -> None:
    decl = W.latent_utility_decl({})
    assert decl["said"] == ["var", 1]
    assert decl["tau"] == {"points": [0.5, 1, 2], "weights": [0.5, 0.3, 0.2]}
    assert decl["price"] == "tick-price"
    assert decl["gauge"] == {"zero": "status-quo", "scale": "answer-utility"}


# --- handshake_decl(): the full first-line world declaration --------------------------------


def test_handshake_decl_namespace_covers_every_guard_name() -> None:
    decl = W.handshake_decl({})
    namespace = set(decl["world"]["namespace"])
    guard_names = {g["name"] for g in decl["world"]["guards"]}
    assert guard_names <= namespace
    assert namespace  # nonempty


def test_handshake_decl_guards_are_singleton_half_grids() -> None:
    decl = W.handshake_decl({})
    for guard in decl["world"]["guards"]:
        assert guard["grid"] == [0.5]


def test_handshake_decl_menu_order_is_exactly_4_3_2_1() -> None:
    decl = W.handshake_decl({})
    assert [m["id"] for m in decl["world"]["menu"]] == [4, 3, 2, 1]
    assert [m["name"] for m in decl["world"]["menu"]] == ["gather", "ask", "abstain", "respond"]
    for m in decl["world"]["menu"]:
        assert m["slots"] == []


def test_handshake_decl_echo_is_all_false() -> None:
    decl = W.handshake_decl({})
    assert decl["world"]["echo"] == {
        "last_action": False, "tick": False, "ticks_spent_thinking": False,
    }


def test_handshake_decl_membrane_version_is_1() -> None:
    decl = W.handshake_decl({})
    assert decl["membrane"] == 1


def test_handshake_decl_table_form_carries_utility_rows() -> None:
    decl = W.handshake_decl({}, utility_form="table@1")
    utility = decl["world"]["utility"]
    assert utility["form"] == "table@1"
    assert utility["rows"] == W.utility_rows({})


def test_handshake_decl_latent_form_carries_latent_block() -> None:
    decl = W.handshake_decl({}, utility_form="latent@1")
    utility = decl["world"]["utility"]
    assert utility == W.latent_utility_decl({})


def test_handshake_decl_unknown_utility_form_raises_value_error() -> None:
    with pytest.raises(ValueError):
        W.handshake_decl({}, utility_form="bogus@1")
