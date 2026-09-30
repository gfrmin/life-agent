"""M4 — the one price table (r14; design §4.2) + the atom derivation (§4.1) + E-5.

Every priced constant that ranks an action lives in ONE declared table
(`core/pricing.py`, which already owned the spend half); the executor and grow menus are
BINDINGS of table rows. The literal values below are the P2 snapshot — dumped from the
pre-M4 declarations before they moved, so a relocation that changes a number fails here,
not in a gate run.

Run: uv run --project . python -m pytest tests/test_pricing_table.py
"""
from __future__ import annotations

from pathlib import Path

from life_agent.core import executor as EX
from life_agent.core import gather_outcomes as GO
from life_agent.core import pricing as P
from life_agent.core import reliability as REL

# --- the P2 snapshot: the pre-M4 declarations, verbatim ---------------------------------

_TIERS = {"corroborate_haiku": ("claude-haiku-4-5", 0.8, 0.004),
          "corroborate_sonnet": ("claude-sonnet-4-6", 0.9, 0.012),
          "corroborate_opus": ("claude-opus-4-8", 0.95, 0.02)}
_TRANSFORMS = [
    {"name": "recency", "probe": "recency", "kind": "guard", "trigger": "era_split"},
    {"name": "corroborate_owner", "probe": "corroborate_opus", "kind": "guard",
     "trigger": "owner_report"},
    {"name": "corroborate_haiku", "probe": "corroborate_haiku", "kind": "voi",
     "trigger": "below_bar", "rho": 0.8, "cost": 0.004},
    {"name": "corroborate_sonnet", "probe": "corroborate_sonnet", "kind": "voi",
     "trigger": "below_bar", "rho": 0.9, "cost": 0.012},
    {"name": "corroborate_opus", "probe": "corroborate_opus", "kind": "voi",
     "trigger": "below_bar", "rho": 0.95, "cost": 0.02},
]
_DELIBERATE = {"name": "deliberate", "probe": "deliberate", "kind": "voi",
               "trigger": "below_bar", "rho": 0.92, "cost": 0.38}
_GROW = [
    {"probe": "retrieve_rerank", "cost": 0.047, "alpha0": 3.0, "beta0": 7.0},
    {"probe": "retrieve_expand", "cost": 0.006, "alpha0": 3.5, "beta0": 6.5},
    {"probe": "re_extract_strong", "cost": 0.02, "alpha0": 4.0, "beta0": 6.0},
]


def test_the_menu_lives_in_the_table() -> None:
    # one declared MENU in the module that already owns the spend half; the version
    # bumps because the table grew (its identity contract is unchanged)
    # v3 (r21): the §18.14 extract_amounts planning-price row joined the table.
    assert P.PRICING_VERSION == 3
    assert P.EXTRACT_AMOUNTS_USD == 0.01
    assert {k: v[0] for k, v in _TIERS.items()} == P.TIER_MODEL
    assert {k: v[1] for k, v in _TIERS.items()} == P.TIER_RHO
    assert P.GATHER_RHO == 0.95
    assert P.DEFAULT_TRANSFORMS == _TRANSFORMS
    assert P.DELIBERATE_TRANSFORM == _DELIBERATE
    assert P.DELIBERATE_FALLBACK_RHO == 0.5
    assert P.RE_EXTRACT_MODEL == "claude-opus-4-8"
    assert P.GROW_ACTUATORS == _GROW


def test_the_executor_and_grow_menus_bind_the_table() -> None:
    # the bindings serve the SAME objects — a second spelling cannot drift
    assert EX.DEFAULT_TRANSFORMS is P.DEFAULT_TRANSFORMS
    assert EX.DELIBERATE_TRANSFORM is P.DELIBERATE_TRANSFORM
    assert EX._TIER_MODEL is P.TIER_MODEL
    assert EX._TIER_RHO is P.TIER_RHO
    assert EX._GATHER_RHO == P.GATHER_RHO
    assert EX._DELIBERATE_FALLBACK_RHO == P.DELIBERATE_FALLBACK_RHO
    assert EX._RE_EXTRACT_MODEL == P.RE_EXTRACT_MODEL
    assert GO.GROW_ACTUATORS is P.GROW_ACTUATORS


def test_the_prior_column_owns_the_reliability_priors() -> None:
    # §3.2: the priors live in the price table's reliability column; the fold module
    # imports them — one spelling (M3 put them in reliability.py as the interim home)
    assert P.RELIABILITY_PRIORS[("extract", "value")] == (4.0, 4.0)
    assert P.RELIABILITY_PRIORS[("eval_claim", "verified")] == (3.0, 2.0)
    assert P.RELIABILITY_PRIORS[("eval_claim", "unsupported")] == (1.0, 3.0)
    assert P.RELIABILITY_PRIORS[("eval_claim", "unverifiable")] == (2.0, 2.0)
    assert REL.PRIORS is P.RELIABILITY_PRIORS


def test_no_priced_constant_is_declared_outside_the_table() -> None:
    # drift gate: the executor and grow modules DECLARE no tier/menu literals any more
    src = Path(__file__).resolve().parent.parent / "src/life_agent/core"
    ex = (src / "executor.py").read_text(encoding="utf-8")
    go = (src / "gather_outcomes.py").read_text(encoding="utf-8")
    rel = (src / "reliability.py").read_text(encoding="utf-8")
    for needle in ('"rho": 0.8', '"cost": 0.38', '"claude-opus-4-8"'):
        assert needle not in ex, needle
    assert '"alpha0": 3.0' not in go
    assert '("extract", "value"): (4.0, 4.0)' not in rel
