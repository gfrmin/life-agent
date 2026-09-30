"""The enactment of the decider's choice (core/enact.py): the options a request opens, and
the winning option mapped to the view — never a second ranking."""
from __future__ import annotations

from typing import Any

import pytest

from life_agent.core import decide as DEC
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


def test_gather_options_list_each_open_probe_once_at_its_lowest_price() -> None:
    p = _payload(transforms=[*_TRANSFORMS, {"probe": "corroborate_b", "kind": "voi",
                                            "cost": 0.02}])
    assert CO.gather_options(p) == [("corroborate_b", 0.012), ("corroborate_a", 0.004),
                                    ("retrieve_rerank", 0.008)]


def test_guard_transforms_are_never_gather_options() -> None:
    assert "recency" not in dict(CO.gather_options(_payload()))


def test_applied_probes_close_their_option() -> None:
    p = _payload(applied_probes=["corroborate_a", "retrieve_rerank"])
    assert CO.gather_options(p) == [("corroborate_b", 0.012)]


def test_no_option_is_open_when_every_probe_is_applied() -> None:
    done = _payload(applied_probes=["corroborate_a", "corroborate_b", "retrieve_rerank"])
    assert CO.gather_options(done) == [] == CO.gather_options({"candidates": ["x"]})


def test_gather_enacts_the_probe_the_option_names() -> None:
    view = CO.enact(DEC.Option("gather", "corroborate_a", 0.1), _payload(), [0.4, 0.3], 0.3)
    assert (view["effector"], view["probe"]) == ("gather", "corroborate_a")


def test_a_gather_option_without_a_probe_is_a_contract_error() -> None:
    with pytest.raises(ValueError, match="no gather option"):
        CO.enact(DEC.Option("gather", None, 0.1), _payload(), [0.4, 0.3], 0.3)


def test_respond_asserts_the_candidate_the_option_names() -> None:
    view = CO.enact(DEC.Option("respond", 1, 0.5), _payload(), [0.1, 0.85], 0.05)
    assert (view["effector"], view["value"]) == ("report", "y")


def test_respond_without_one_credence_per_candidate_raises() -> None:
    with pytest.raises(ValueError):
        CO.enact(DEC.Option("respond", 0, 0.5), _payload(), [0.9], 0.1)


@pytest.mark.parametrize(("act", "effector"), [("abstain", "abstain"), ("ask", "ask_clarify")])
def test_withholding_acts_carry_no_value(act: str, effector: str) -> None:
    view = CO.enact(DEC.Option(act, None, 0.0), _payload(), [0.4, 0.3], 0.3)
    assert (view["effector"], view["value"], view["probe"]) == (effector, None, None)
    assert view["credences"] == [0.4, 0.3] and view["p_none"] == 0.3


def test_an_undeclared_act_raises() -> None:
    with pytest.raises(ValueError, match="undeclared"):
        CO.enact(DEC.Option("escalate", None, 0.0), _payload(), [0.4, 0.3], 0.3)
