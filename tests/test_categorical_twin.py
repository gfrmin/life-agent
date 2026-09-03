"""r46 leg D categorical-twin instrument — the load-bearing predicates, hermetic (no engine).

Every declaration the instrument sends is a DELTA on the deployed `handshake_decl_cat`
(`M-7`): a drift in `categorical.handshake_decl_cat` / `world.theta_grid` breaks these tests
rather than silently reshaping a probe. K7's mutation verification runs against this file.
"""
from __future__ import annotations

import inspect
import json
import sys

sys.path.insert(0, "scripts")

from membrane import categorical_twin as CT

from life_agent.membrane import categorical as CAT
from life_agent.membrane import world as W

U_BAR = {"u_correct": 1.0, "u_abstain": 0.0, "u_wrong": -5.130990,
         "lambda_int": 0.1, "kappa_att": 0.02, "u_hedged": 0.4, "lambda_usd": 1.33}


def test_base_cat_decl_is_the_deployed_one_verbatim() -> None:
    for k in (2, 3, 5):
        assert json.dumps(CT.base_cat_decl(U_BAR, k), sort_keys=True) == json.dumps(
            CAT.handshake_decl_cat(U_BAR, k), sort_keys=True), k


def test_base_now_carries_the_items_r47_landed() -> None:
    """**The drift pin worked.** Leg D read a base declaration carrying NEITHER codebooks
    NOR a clock, and this test pinned that. `r47` then landed both into the deployed
    `handshake_decl_cat`, so the pin fired — exactly what a drift pin is for.

    `base_cat_decl` is defined as the deployed declaration verbatim, so it must track it.
    What this means for the record: leg D's K1/K2 arms measured a world without those
    items, and re-running them needs leg D's own tree (`M-28` — a measurement pins its
    tree for the whole run), not this one. The instrument stays in tree, tested and
    dormant, like `carrier_audit.py` and `replace_audit.py` before it."""
    world = CT.base_cat_decl(U_BAR, 3)["world"]
    assert "obs_arity" in world
    assert world["codebooks"] == {"theta": W.theta_grid(U_BAR)}
    assert world["clock"] == [
        {"name": W.CLOCK_NAME, "price": W.clock_price(U_BAR), "batch": W.CLOCK_BATCH}
    ]


def test_the_leg_d_deltas_are_now_no_ops_on_the_deployed_base() -> None:
    """Post-`r47` the instrument's `codebooks=`/`clock=` deltas add what the base already
    declares, so they are idempotent rather than additive. Asserted explicitly so the
    instrument cannot quietly appear to be varying something it no longer varies."""
    base = json.dumps(CT.base_cat_decl(U_BAR, 3), sort_keys=True)
    both = json.dumps(CT.cat_decl(U_BAR, 3, codebooks=True, clock=True), sort_keys=True)
    assert base == both


def test_codebooks_delta_adds_exactly_the_one_theta_rule() -> None:
    world = CT.cat_decl(U_BAR, 3, codebooks=True)["world"]
    assert world["codebooks"] == {"theta": W.theta_grid(U_BAR)}
    # nothing else moved from the base except the added key
    base = CT.base_cat_decl(U_BAR, 3)["world"]
    for key in ("namespace", "guards", "menu", "obs_arity", "utility"):
        assert world[key] == base[key], key


def test_clock_delta_adds_the_derived_clock_row() -> None:
    world = CT.cat_decl(U_BAR, 3, clock=True)["world"]
    assert world["clock"] == [
        {"name": W.CLOCK_NAME, "price": W.clock_price(U_BAR), "batch": W.CLOCK_BATCH}
    ]


def test_theta_rule_is_the_deployed_binary_grid() -> None:
    # GD-13's answer: ONE rule. The categorical world binds r44's `theta_grid` unchanged.
    assert CT.theta_rule(U_BAR) == W.theta_grid(U_BAR)


def test_theta_rule_is_k_independent() -> None:
    # The theta codebook parametrises the channel rate, not the candidate count: the rule
    # takes u_bar alone and no k. This is the structural half of GD-13's decision.
    params = list(inspect.signature(CT.theta_rule).parameters)
    assert params == ["u_bar"]


def test_respond_arm_is_code_conditional() -> None:
    # The categorical respond arm compares y against (act - RESPOND_BASE) — code-conditional,
    # not scalar-p1-linear, so the binary crossings half has no categorical definition.
    assert CT.respond_arm_is_code_conditional() is True


def test_menu_head_is_abstain() -> None:
    # K5's inertness signature reads the menu head; the categorical grid leads with abstain.
    assert CAT.act_grid_cat(3)[0] == 1.0


def test_full_cat_features_covers_every_declared_name() -> None:
    # arm B demands every declared name on a tick; `cat_features` omits dormant ones, so the
    # coverage repair must carry them all (dormant 0.0, active overriding).
    s = CT._cat_summary(3, ())
    full = CT.full_cat_features(s, 0.0)
    for name in CAT.cat_indicator_names():
        assert name in full, name
    assert full["t"] == 0.0
    for name, val in CAT.cat_features(s, 0.0).items():
        assert full[name] == val, name


def test_cat_summary_helper_carries_only_numbers() -> None:
    s = CT._cat_summary(3, (1, 2))
    assert s.k == 3
    assert s.obs_codes == (1, 2)
    assert s.n_obs == 2
    assert s.n_obs_unmapped == 0
