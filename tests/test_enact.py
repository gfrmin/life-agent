"""The enactment of the decider's act (core/enact.py): determined by the act and the request
alone, never a second ranking."""
from __future__ import annotations

from typing import Any

import pytest

from life_agent.core import enact as CO

_TRANSFORMS = [
    {"name": "recency", "probe": "recency", "kind": "guard", "trigger": "era_split"},
    {"name": "b", "probe": "corroborate_b", "kind": "voi", "cost": 0.012},
    {"name": "a", "probe": "corroborate_a", "kind": "voi", "cost": 0.004},
]
_GROW = {"actuators": [{"probe": "retrieve_rerank", "cost": 0.008}]}


def _payload(**kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {"candidates": ["x", "y"], "applied_probes": [],
                            "transforms": _TRANSFORMS, "grow": _GROW}
    base.update(kw)
    return base


def test_gather_options_are_cheapest_first_across_transforms_and_grow() -> None:
    assert CO.gather_options(_payload()) == ["corroborate_a", "retrieve_rerank",
                                             "corroborate_b"]


def test_guard_transforms_are_never_gather_options() -> None:
    assert "recency" not in CO.gather_options(_payload())


def test_applied_probes_close_their_option() -> None:
    p = _payload(applied_probes=["corroborate_a", "retrieve_rerank"])
    assert CO.gather_options(p) == ["corroborate_b"]


def test_gather_is_open_until_every_option_is_applied() -> None:
    assert CO.gather_open(_payload())
    done = _payload(applied_probes=["corroborate_a", "corroborate_b", "retrieve_rerank"])
    assert not CO.gather_open(done)
    assert not CO.gather_open({"candidates": ["x"]})


def test_gather_enacts_the_cheapest_open_option() -> None:
    view = CO.enact("gather", _payload(), [0.4, 0.3], 0.3)
    assert (view["effector"], view["probe"]) == ("gather", "corroborate_a")


def test_gather_with_nothing_open_is_a_contract_error_not_a_fallback() -> None:
    done = _payload(applied_probes=["corroborate_a", "corroborate_b", "retrieve_rerank"])
    with pytest.raises(ValueError, match="no gather option"):
        CO.enact("gather", done, [0.4, 0.3], 0.3)


def test_respond_asserts_the_map_candidate_not_index_zero() -> None:
    view = CO.enact("respond", _payload(), [0.1, 0.85], 0.05)
    assert (view["effector"], view["value"]) == ("report", "y")


def test_respond_ties_break_in_candidate_order() -> None:
    assert CO.enact("respond", _payload(), [0.45, 0.45], 0.1)["value"] == "x"


def test_respond_without_one_credence_per_candidate_raises() -> None:
    with pytest.raises(ValueError):
        CO.enact("respond", _payload(), [0.9], 0.1)


@pytest.mark.parametrize(("act", "effector"), [("abstain", "abstain"), ("ask", "ask_clarify")])
def test_withholding_acts_carry_no_value(act: str, effector: str) -> None:
    view = CO.enact(act, _payload(), [0.4, 0.3], 0.3)
    assert (view["effector"], view["value"], view["probe"]) == (effector, None, None)
    assert view["credences"] == [0.4, 0.3] and view["p_none"] == 0.3


def test_an_undeclared_act_raises() -> None:
    with pytest.raises(ValueError, match="undeclared"):
        CO.enact("escalate", _payload(), [0.4, 0.3], 0.3)


def test_gather_cost_is_the_price_of_the_option_that_would_be_enacted() -> None:
    assert CO.gather_cost(_payload()) == 0.004
    assert CO.gather_cost(_payload(applied_probes=["corroborate_a"])) == 0.008
    done = _payload(applied_probes=["corroborate_a", "corroborate_b", "retrieve_rerank"])
    assert CO.gather_cost(done) == 0.0
