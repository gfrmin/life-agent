"""Hermetic tests for the answer-domain membrane world (life_agent.membrane.world).

No wire, no subprocess: these pin the pure data/functions Task 2 produces — the
canonical per-tick feature encoding (:func:`shadow_features`), the world's declared
namespace/menu/utility (the re-derived ``proplang-host`` wire: one writable ``act`` name,
a ``said@1`` utility sentence), and the reduction of the executor's live shapes
(payload/dec dicts from ``core/executor.py``) and the decision log's replay shape
(``DecisionEvent.posterior_summary``) to one canonical :class:`DecideSummary`. Fixture
values below are synthetic (public repo, PRINCIPLES §12) — no owner data.
"""
from __future__ import annotations

import pytest

from life_agent.membrane import world as W

# The REAL utility posterior, as GET :8798/utility served it on 2026-07-11 — kept here as a
# named fixture (7 scalar utility means; no owner data, PRINCIPLES §12) because several of
# the properties below are only interesting where the live numbers differ MATERIALLY from
# world.utility_by_action's fallback defaults: the reaction loop has already narrowed u_wrong
# from the -9.0 default to about -5.94, which moves every utility-derived threshold. A test
# that only ever exercised the defaults is how a threshold that is really a FUNCTION of
# utility got published as the constant 0.9.
LIVE_U_BAR: dict[str, float] = {
    "u_correct": 1.0, "u_abstain": 0.0, "u_wrong": -5.9395, "u_wrong_scoped": -2.0827,
    "u_hedged": 0.3964, "lambda_int": 1.0009, "kappa_att": 0.0344,
}

# --- AFFORDANCES / VALUE_TO_ACTION / UTILITY_FORMS (grid-order + drift-gate pins) ---------


def test_affordances_are_grid_ordered_with_abstain_first() -> None:
    # GRID ORDER is normative on the wire: the first point is the safe wait (abstain), and
    # argmaxEU ties resolve first-listed (membrane-wire.md §2, CL-3). The v1 gather-wins-ties
    # posture died with the id/slots menu.
    assert W.ACT_NAME == "act"
    names = [name for name, _ in W.AFFORDANCES]
    values = [v for _, v in W.AFFORDANCES]
    assert names == ["abstain", "gather", "ask", "respond"]
    assert names[0] == "abstain"
    assert len(set(names)) == 4       # four distinct names
    assert len(set(values)) == 4      # four distinct grid values
    assert values == W.ACT_GRID       # the menu grid IS the affordance values, in order


def test_value_to_action_round_trips_every_affordance() -> None:
    assert set(W.VALUE_TO_ACTION.values()) == {name for name, _ in W.AFFORDANCES}
    for name, v in W.AFFORDANCES:
        assert W.VALUE_TO_ACTION[v] == name


def test_utility_forms_is_said_at_1_only() -> None:
    # ``assign@1``/``table@1``/``latent@1`` are the OLD roadmap's record; the re-derived wire
    # accepts exactly one form, the priced sentence.
    assert W.UTILITY_FORMS == ("said@1",)


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
                          era_split=True, owner_scoped=True, grow_pass=False,
                          runner_up_credence=0.3)


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


# --- runner_up_credence (r50): the raw second credence, on BOTH reducers --------------------


def test_summary_from_payload_carries_the_runner_up_credence() -> None:
    # the second-largest credence, not index 1 (the daemon returns candidate order)
    dec = {"credences": [0.5, 0.15, 0.3], "p_none": 0.05}
    s = W.summary_from_payload({"candidates": ["A", "B", "C"], "observations": []}, dec)
    assert s.leader_credence == 0.5 and s.runner_up_credence == 0.3


def test_runner_up_credence_is_zero_with_fewer_than_two_candidates() -> None:
    one = W.summary_from_payload({"candidates": ["A"], "observations": []},
                                 {"credences": [0.9], "p_none": 0.1})
    none = W.summary_from_payload({"candidates": [], "observations": []},
                                  {"credences": [], "p_none": None})
    assert one.runner_up_credence == 0.0 and none.runner_up_credence == 0.0


def test_summary_from_decision_event_carries_the_runner_up_credence() -> None:
    event = {"posterior_summary": {"candidates": ["A", "B"], "credences": [0.2, 0.7],
                                   "p_none": 0.1, "n_obs": 2}}
    s = W.summary_from_decision_event(event)
    assert s.leader_credence == 0.7 and s.runner_up_credence == 0.2


def test_runner_up_credence_does_not_enter_the_declared_vocabulary() -> None:
    # r50 step (a) is neutral: a raw field on the summary, NOT a new indicator family — the
    # handshake namespace, the tick body and the world digest are byte-untouched until the
    # census (S2) names a family
    s = _summary(n_candidates=2, leader_credence=0.8, p_none=0.1, n_obs=1,
                 runner_up_credence=0.15)
    assert not any("runner" in n for n in W.indicator_names())
    assert not any("runner" in n for n in W.shadow_features(s, 0.0))


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
    # exactly one leader-credence indicator fires; r44 item 2: the rest are emitted at 0.0
    # rather than omitted, because HEAD's door requires exact namespace coverage.
    fired = [k for k, v in feats.items() if k.startswith("leader-credence=") and v == 1.0]
    assert fired == [f"leader-credence={bucket}"]


def test_shadow_features_leader_credence_none_fires_no_indicator() -> None:
    """r44 item 2: the family is still DECLARED (coverage), but nothing in it fires."""
    feats = W.shadow_features(_summary(leader_credence=None), t=0.0)
    family = {k: v for k, v in feats.items() if k.startswith("leader-credence=")}
    assert family and not any(v == 1.0 for v in family.values())


@pytest.mark.parametrize("p_none,bucket", [
    (0.0, "lt20"), (0.19, "lt20"),
    (0.2, "20to50"), (0.49, "20to50"),
    (0.5, "ge50"), (1.0, "ge50"),
])
def test_shadow_features_p_none_boundaries(p_none: float, bucket: str) -> None:
    feats = W.shadow_features(_summary(p_none=p_none), t=0.0)
    assert feats[f"p-none={bucket}"] == 1.0
    fired = [k for k, v in feats.items() if k.startswith("p-none=") and v == 1.0]
    assert fired == [f"p-none={bucket}"]


def test_shadow_features_p_none_none_fires_no_indicator() -> None:
    feats = W.shadow_features(_summary(p_none=None), t=0.0)
    family = {k: v for k, v in feats.items() if k.startswith("p-none=")}
    assert family and not any(v == 1.0 for v in family.values())


@pytest.mark.parametrize("n,bucket", [(0, "0"), (1, "1to2"), (2, "1to2"), (3, "3plus"),
                                      (10, "3plus")])
def test_shadow_features_n_obs_buckets(n: int, bucket: str) -> None:
    feats = W.shadow_features(_summary(n_obs=n), t=0.0)
    assert feats[f"n-obs={bucket}"] == 1.0


def test_shadow_features_flags_fire_only_when_true() -> None:
    on = W.shadow_features(_summary(era_split=True, owner_scoped=True, grow_pass=True), t=0.0)
    off = W.shadow_features(_summary(era_split=False, owner_scoped=False, grow_pass=False), t=0.0)

    assert on["era-split=1"] == 1.0
    assert on["owner-scoped=1"] == 1.0
    assert on["grow-pass=1"] == 1.0
    # r44 item 2: declared for coverage, at 0.0 — never absent.
    assert off["era-split=1"] == 0.0
    assert off["owner-scoped=1"] == 0.0
    assert off["grow-pass=1"] == 0.0


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


# --- utility_by_action(): the (y=0, y=1) pairs + fallbacks ---------------------------------


def test_utility_by_action_uses_declared_fallbacks_on_empty_u_bar() -> None:
    pairs = W.utility_by_action({})

    assert pairs["respond"] == (-9.0, 1.0)        # (u_wrong fallback -9.0, u_correct 1.0)
    assert pairs["abstain"] == (0.0, 0.0)         # status-quo, constant in y
    # gather/ask are priced as MYOPIC PERFECT INFORMATION: [u_abstain - cost, u_correct - cost]
    # — having gathered, you take the correct act. NOT [-cost, -cost]: a row constant in y is a
    # pure cost, and a pure cost can never beat abstain at any p1, unfiring the whole menu.
    assert pairs["ask"] == (-0.1, 0.9)            # lambda_int fallback 0.1
    assert pairs["gather"] == (-0.02, 0.98)       # kappa_att fallback 0.02


def test_utility_by_action_honours_custom_u_bar() -> None:
    pairs = W.utility_by_action({"u_wrong": -4.0, "lambda_int": -0.3, "kappa_att": 0.5})

    assert pairs["respond"] == (-4.0, 1.0)
    assert pairs["ask"] == (-0.3, 0.7)            # abs(-0.3) == 0.3, charged on both outcomes
    assert pairs["gather"] == (-0.5, 0.5)


def test_utility_by_action_information_actions_are_not_constant_in_y() -> None:
    """The regression an earlier world shipped with: `gather -> [-g, -g]` and `ask -> [-q, -q]`
    are CONSTANT in y, i.e. pure costs against `abstain -> [0, 0]` — so EU(gather) = -g < 0 =
    EU(abstain) at EVERY p1 and every u_bar, abstain strictly dominates the entire information
    menu, and a menu whose whole point is effort allocation can never fire one. Pinned as a
    property (u(y=1) > u(y=0) for both), not as two magic numbers."""
    for u_bar in ({}, {"u_wrong": -5.9395, "lambda_int": 1.0009, "kappa_att": 0.0344}):
        pairs = W.utility_by_action(u_bar)
        for action in ("gather", "ask"):
            u0, u1 = pairs[action]
            assert u1 > u0, f"{action} is constant in y under {u_bar} — it can never fire"


def test_utility_by_action_covers_every_affordance() -> None:
    pairs = W.utility_by_action({})
    assert set(pairs) == {name for name, _ in W.AFFORDANCES}


# --- utility_said(): the drift gate (the sentence MUST equal the pairs) --------------------


def _eval_said(expr: object, *, act: float, y: int) -> object:
    """A small pure evaluator for the ``said@1`` accepted subset (``parseSaid``:
    var, c, +, -, *, get, if, >, =). The whole point is a SECOND, independent reading of the
    sentence: if this and :func:`world.utility_by_action` disagree, the wire declaration has
    silently drifted from the host-side arithmetic. ``var 1`` is the outcome residue y;
    ``get "act"`` is the chosen affordance's grid value under evaluation."""
    if not isinstance(expr, list):
        raise ValueError(f"not a sentence node: {expr!r}")
    op = expr[0]
    if op == "c":
        return expr[1]
    if op == "var":
        return {1: y}[expr[1]]  # only the outcome residue is declared
    if op == "get":
        return {"act": act}[expr[1]]
    if op == "+":
        return _eval_said(expr[1], act=act, y=y) + _eval_said(expr[2], act=act, y=y)  # type: ignore[operator]
    if op == "-":
        return _eval_said(expr[1], act=act, y=y) - _eval_said(expr[2], act=act, y=y)  # type: ignore[operator]
    if op == "*":
        return _eval_said(expr[1], act=act, y=y) * _eval_said(expr[2], act=act, y=y)  # type: ignore[operator]
    if op == "=":
        return _eval_said(expr[1], act=act, y=y) == _eval_said(expr[2], act=act, y=y)
    if op == ">":
        return _eval_said(expr[1], act=act, y=y) > _eval_said(expr[2], act=act, y=y)  # type: ignore[operator]
    if op == "if":
        cond = _eval_said(expr[1], act=act, y=y)
        return _eval_said(expr[2], act=act, y=y) if cond else _eval_said(expr[3], act=act, y=y)
    raise ValueError(f"unsupported op {op!r}")


@pytest.mark.parametrize("u_bar", [{}, LIVE_U_BAR])
def test_utility_said_sentence_equals_the_pairs_at_every_grid_point(
    u_bar: dict[str, float],
) -> None:
    """The single-source drift gate: for every affordance value v and y in {0,1}, evaluating
    the declared ``said@1`` sentence at ``act=v`` must equal ``utility_by_action[name][y]`` —
    for at least two materially different u_bar fixtures (the fallbacks and the live
    posterior). If this fails, the wire says one thing and the host arithmetic another."""
    said = W.utility_said(u_bar)
    pairs = W.utility_by_action(u_bar)
    for name, v in W.AFFORDANCES:
        for y in (0, 1):
            got = _eval_said(said, act=v, y=y)
            assert got == pytest.approx(pairs[name][y]), f"{name} y={y} under {u_bar}"


def test_utility_said_uses_only_the_accepted_subset() -> None:
    # the sentence must not reach for any op outside parseSaid's set — the evaluator above
    # raises on an unknown op, so a successful full evaluation IS the proof.
    said = W.utility_said(LIVE_U_BAR)
    for name, v in W.AFFORDANCES:  # noqa: B007 - v is the payload, name only for readability
        _eval_said(said, act=v, y=1)


# --- EU arithmetic, argmax, and the respond-reachability threshold ---------------------------


def test_eu_by_action_is_the_declared_table_read_at_p1() -> None:
    eus = W.eu_by_action(LIVE_U_BAR, 0.5)
    assert eus["abstain"] == pytest.approx(0.0)
    assert eus["respond"] == pytest.approx(0.5 * 1.0 + 0.5 * -5.9395)
    assert eus["gather"] == pytest.approx(0.5 * 1.0 - 0.0344)


def test_argmax_action_resolves_ties_first_listed() -> None:
    """At an all-zero-cost u_bar (lambda_int == kappa_att == 0) and p1 == 0, abstain, gather
    and ask all score exactly 0 — and AFFORDANCES order (abstain first, the safe wait) decides,
    the wire's own rule."""
    u_bar = {"lambda_int": 0.0, "kappa_att": 0.0}  # g == q == 0
    eus = W.eu_by_action(u_bar, 0.0)
    assert eus["abstain"] == pytest.approx(eus["gather"]) == pytest.approx(eus["ask"])
    assert W.argmax_action(u_bar, 0.0) == "abstain"


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
    # is worth more than abstain at any p1 above its own cost, so the real bar is far higher.
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


# --- handshake_decl(): the full first-line world declaration --------------------------------


def test_handshake_decl_namespace_is_t_then_indicators_then_act() -> None:
    decl = W.handshake_decl({})
    namespace = decl["world"]["namespace"]
    assert namespace[0] == "t"                       # RIDER 2: t first
    assert namespace[-1] == W.ACT_NAME               # the one writable name, last
    assert set(namespace) == {"t", W.ACT_NAME, *W.indicator_names()}
    assert len(namespace) == len(W.indicator_names()) + 2  # every indicator + t + act, no more


def test_handshake_decl_guards_are_singleton_half_grids_over_the_indicators() -> None:
    decl = W.handshake_decl({})
    guards = decl["world"]["guards"]
    assert [g["name"] for g in guards] == W.indicator_names()
    for guard in guards:
        assert guard["grid"] == [0.5]


def test_handshake_decl_menu_is_exactly_the_one_act_row_with_its_grid() -> None:
    decl = W.handshake_decl({})
    assert decl["world"]["menu"] == [{"name": W.ACT_NAME, "grid": W.ACT_GRID}]


def test_handshake_decl_utility_is_the_said_at_1_sentence() -> None:
    decl = W.handshake_decl(LIVE_U_BAR)
    utility = decl["world"]["utility"]
    assert utility["form"] == "said@1"
    assert utility["said"] == W.utility_said(LIVE_U_BAR)


def test_handshake_decl_has_no_echo_block() -> None:
    # the echo block died with the step-5 wire.
    decl = W.handshake_decl({})
    assert "echo" not in decl["world"]


def test_handshake_decl_membrane_version_is_1() -> None:
    decl = W.handshake_decl({})
    assert decl["membrane"] == 1


def test_handshake_decl_unknown_utility_form_raises_value_error() -> None:
    with pytest.raises(ValueError):
        W.handshake_decl({}, utility_form="table@1")
    with pytest.raises(ValueError):
        W.handshake_decl({}, utility_form="bogus@1")


# --- r44: the world-declaration repair (items 1, 2, 4) ---------------------------------


#: Half a lattice step — the most `_snap_to_lattice` can move any rung. DERIVED from the
#: declared constant, never a magic tolerance: if the lattice is ever re-declared this
#: follows it, and a snap that displaced further would fail these tests rather than pass a
#: loosened one.
_LATTICE_TOLERANCE = 2.0 ** -(W._GRID_LATTICE_BITS + 1)


def test_theta_grid_puts_a_rung_at_the_measured_operating_rate() -> None:
    """Item 1's first rung. #19's false clear is a PLACEMENT failure — a rung near but not
    at the operating rate lets the posterior settle on the KL-nearest rung.

    **r46 leg B weakened "at" from exact equality to within half a lattice step, and did it
    on a measurement rather than for convenience.** `r44`'s own W6 moved this rung by
    7e-3 and read a `p1` gap of 3.2e-3 at 98 ticks, growing with data — concluding that even
    then *"no false clear is reachable on this world at this data volume"*. The snap moves it
    by at most 4.8e-7, four orders of magnitude less, and leg B measured the resulting `p1`
    gap directly: ~1e-6 at 2**-14 and ~1e-10 at 2**-30, non-growing, against zero differing
    decisions over 428 distinct summaries. The clause is honoured to a measured tolerance,
    not abandoned."""
    grid = W.theta_grid({})
    assert min(abs(W.OPERATING_RATE - g) for g in grid) <= _LATTICE_TOLERANCE


def test_theta_grid_puts_a_rung_at_every_finite_argmax_crossing() -> None:
    """The same argument applied to this world's actual consumer: the p1 values at which the
    declared utility changes its mind are where a threshold sits. Same lattice tolerance,
    same justification."""
    u_bar = {"u_correct": 1.0, "u_abstain": 0.0, "u_wrong": -9.0,
             "lambda_int": 0.1, "kappa_att": 0.02}
    crossings = W.argmax_crossings(u_bar)
    assert crossings, "a utility with four distinct rows must cross somewhere in (0, 1)"
    grid = W.theta_grid(u_bar)
    for c in crossings:
        assert min(abs(c - g) for g in grid) <= _LATTICE_TOLERANCE, (
            f"no rung within half a lattice step of crossing {c}"
        )


def test_theta_grid_rungs_all_sit_on_the_declared_lattice() -> None:
    """The lever itself: cost scales with the dyadic denominator's BIT LENGTH, so every rung
    must actually be short. An IEEE double is already dyadic — the pre-snap grid's values are
    54-57 bit — so this asserts SHORTNESS, which is the thing that is paid for."""
    from fractions import Fraction
    for u_bar in ({}, {"u_wrong": -9.0}, {"u_correct": 2.0, "u_abstain": -0.5}):
        for value in W.theta_grid(u_bar):
            bits = Fraction(value).denominator.bit_length() - 1
            assert bits <= W._GRID_LATTICE_BITS, f"{value!r} needs {bits} bits"


def test_the_snap_is_refused_rather_than_allowed_to_merge_two_rungs() -> None:
    """`_GRID_COLLISION` bounds a fixed value against a crossing; it says nothing about two
    CROSSINGS, which can be arbitrarily close. A merge would shrink `models = n(17n-16)` —
    a representation change silently becoming a different lever. The ladder must step to a
    finer lattice instead, and must never return a shorter grid."""
    close = [0.5, 0.5 + 2.0 ** -30]
    snapped = W._snap_to_lattice(close)
    assert len(snapped) == len(close) == len(set(snapped))
    assert snapped == sorted(snapped)


def test_argmax_crossings_are_where_the_argmax_actually_changes() -> None:
    u_bar = {"u_correct": 1.0, "u_abstain": 0.0, "u_wrong": -9.0,
             "lambda_int": 0.1, "kappa_att": 0.02}
    for c in W.argmax_crossings(u_bar):
        assert 0.0 < c < 1.0
        assert W.argmax_action(u_bar, c - 1e-6) != W.argmax_action(u_bar, c + 1e-6)


def test_theta_grid_is_sorted_unique_and_strictly_inside_the_unit_interval() -> None:
    for u_bar in ({}, {"u_wrong": 0.0}, {"u_correct": 100.0, "u_abstain": 90.0}):
        grid = W.theta_grid(u_bar)
        assert grid, "an empty grid is refused by the wire (pairGridNamed)"
        assert grid == sorted(grid) and len(grid) == len(set(grid))
        assert all(0.0 < x < 1.0 for x in grid)


def test_handshake_declares_codebooks_theta_equal_to_the_grid_rule() -> None:
    u_bar = {"u_correct": 1.0, "u_abstain": 0.0, "u_wrong": -9.0}
    world = W.handshake_decl(u_bar)["world"]
    assert world["codebooks"]["theta"] == W.theta_grid(u_bar)


def test_handshake_declares_the_clock_row() -> None:
    world = W.handshake_decl({})["world"]
    assert world["clock"] == [{"name": W.CLOCK_NAME, "price": W.clock_price({}),
                              "batch": W.CLOCK_BATCH}]
    assert W.CLOCK_BATCH >= 1


def test_the_clock_name_is_not_a_namespace_name() -> None:
    """The wire refuses a clock whose internal name collides with the namespace."""
    assert W.CLOCK_NAME not in W.handshake_decl({})["world"]["namespace"]


def test_the_clock_price_strictly_dominates_the_utility_span() -> None:
    """`think` is not an affordance this world models. Its price is DERIVED so that
    `thinkValue - price` is strictly below the worst achievable row EU — never raised
    until it stops firing."""
    for u_bar in ({}, {"u_correct": 100.0, "u_abstain": 90.0, "u_wrong": 0.0}):
        pairs = W.utility_by_action(u_bar)
        vals = [v for pair in pairs.values() for v in pair]
        assert W.clock_price(u_bar) > max(vals) - min(vals)


def test_shadow_features_covers_the_declared_namespace_minus_the_writable_name() -> None:
    """Item 2: HEAD's door requires EXACT coverage, and r43 measured that padding the
    writable name in is refused (feature/assignment collision), not conservative."""
    s = W.DecideSummary(2, None, None, 3, False, False, False)
    feats = W.shadow_features(s, 7.0)
    ns = W.handshake_decl({})["world"]["namespace"]
    assert set(feats) == set(ns) - {W.ACT_NAME}


def test_shadow_features_never_emits_the_writable_name() -> None:
    for credence in (None, 0.9):
        s = W.DecideSummary(2, credence, None, 3, True, False, True)
        assert W.ACT_NAME not in W.shadow_features(s, 0.0)


def test_shadow_features_emits_inapplicable_buckets_at_zero() -> None:
    """The old contract ('dormancy is free — absent names read 0.0') is dead at HEAD."""
    s = W.DecideSummary(2, None, None, 3, False, False, False)
    feats = W.shadow_features(s, 0.0)
    absent = [n for n in W.indicator_names() if n.startswith("leader-credence=")]
    assert absent and all(feats[n] == 0.0 for n in absent)
