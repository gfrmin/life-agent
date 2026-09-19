"""The one decider (membrane/decider.py): the posterior is local, the act is the engine's,
and nothing substitutes for a down engine."""
from __future__ import annotations

from typing import Any

import pytest

from life_agent.core import config
from life_agent.core import posterior as POST
from life_agent.membrane import boot as BOOT
from life_agent.membrane import decider as DCD
from life_agent.membrane import world as W
from life_agent.membrane.client import MembraneClient, MembraneError

_HELLO = {"ok": True, "proto": 1, "models": 960}


class _Engine:
    """A scripted engine: answers the handshake, then every decision tick with ``act`` and
    every evidence tick with an observation. Records what it was sent."""

    def __init__(self, act: str = "respond", p1: float = 0.97, *, die_after: int = -1) -> None:
        self.act, self.p1, self.die_after = act, p1, die_after
        self.sent: list[dict[str, Any]] = []
        self.shut = False

    def request(self, obj: dict[str, Any]) -> dict[str, Any]:
        self.sent.append(obj)
        if self.die_after == 0:
            raise MembraneError("membrane driver closed the wire (EOF)")
        self.die_after -= 1
        if "membrane" in obj:
            return dict(_HELLO)
        tick = obj["tick"]
        if "evidence" in tick:
            return {"observed": tick["evidence"]}
        return {"act": {"act": dict(W.AFFORDANCES)[self.act]}, "p1": self.p1}

    def shutdown(self) -> None:
        self.shut = True

    def ticks(self) -> list[dict[str, Any]]:
        return [o["tick"] for o in self.sent if "tick" in o]


def _decider(engines: list[_Engine], snap: BOOT.BootSnapshot | None = None) -> DCD.Decider:
    pool = list(engines)
    return DCD.Decider(spawn=lambda: pool.pop(0),  # type: ignore[arg-type, return-value]
                       u_bar=lambda: {"u_wrong": -9.0},
                       snapshot=lambda: snap or BOOT.BootSnapshot([], 0),
                       log=lambda _m: None)


_OBS = [{"reports": 1, "group": 0, "authority": 1.0, "subject_factor": 1.0,
         "time_factor": 1.0, "competition_factor": 1.0},
        {"reports": 1, "group": 1, "authority": 1.0, "subject_factor": 1.0,
         "time_factor": 1.0, "competition_factor": 1.0}]


def _payload(**kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "question_id": "q1", "candidates": ["x", "y"], "observations": _OBS, "rho": 0.8,
        "applied_probes": [], "era_split": False, "owner_scoped": False,
        "transforms": [{"probe": "corroborate_a", "kind": "voi", "cost": 0.004}]}
    base.update(kw)
    return base


def test_the_posterior_is_local_and_the_act_is_the_engines() -> None:
    eng = _Engine("respond", 0.97)
    view = _decider([eng]).decide("q1", _payload())
    credences, p_none = POST.candidate_posterior(2, _OBS, 0.8)
    assert view["credences"] == credences and view["p_none"] == p_none
    assert (view["act"], view["effector"], view["value"]) == ("respond", "report", "y")
    assert view["p1"] == 0.97
    assert view["eu"] == pytest.approx(W.eu_by_action({"u_wrong": -9.0}, 0.97)["respond"])


def test_the_engine_act_stands_where_a_host_argmax_would_differ() -> None:
    """The poison: the leader is near-certain, so any host EU argmax would respond. The
    engine abstains, and the decider enacts abstain."""
    obs = _OBS * 4
    assert max(POST.candidate_posterior(2, obs, 0.95)[0]) > 0.99
    view = _decider([_Engine("abstain", 0.2)]).decide("q1", _payload(observations=obs,
                                                                      rho=0.95))
    assert (view["effector"], view["value"]) == ("abstain", None)


def test_the_tick_says_whether_gather_is_open() -> None:
    eng = _Engine("abstain")
    d = _decider([eng])
    d.decide("q1", _payload())
    d.decide("q1", _payload(applied_probes=["corroborate_a"]))
    opens = [t["features"][W.FEASIBILITY["gather"]] for t in eng.ticks()]
    assert opens == [1.0, 0.0]


def test_a_dead_engine_is_named_and_rebooted_on_the_next_request() -> None:
    dying, fresh = _Engine(die_after=1), _Engine("ask")
    d = _decider([dying, fresh])
    with pytest.raises(DCD.DeciderUnavailableError, match="EOF"):
        d.decide("q1", _payload())
    assert dying.shut and d.status()["booted"] is False
    assert d.decide("q1", _payload())["effector"] == "ask_clarify"


def test_a_failed_boot_is_named_and_the_client_is_shut() -> None:
    eng = _Engine(die_after=0)
    with pytest.raises(DCD.DeciderUnavailableError):
        _decider([eng]).boot()
    assert eng.shut


def test_boot_replays_the_snapshot_as_evidence_ticks() -> None:
    s = W.DecideSummary(1, 0.9, 0.05, 2, False, False, False)
    eng = _Engine()
    _decider([eng], BOOT.BootSnapshot([(s, 1), (s, 0)], 4)).boot()
    assert [t["evidence"] for t in eng.ticks()] == [1, 0]


def test_a_verdict_folds_once_under_the_decide_time_summary() -> None:
    eng = _Engine("abstain")
    d = _decider([eng])
    d.decide("q1", _payload(era_split=True))
    d.bind("d1", "q1", {"chosen_action": "abstain", "posterior_summary": {}})
    assert d.observe_reaction("d1", "bad") is True
    assert d.observe_reaction("d1", "good") is False  # the next boot takes the latest
    evidence = [t for t in eng.ticks() if "evidence" in t]
    assert len(evidence) == 1 and evidence[0]["features"]["era-split=1"] == 1.0


def test_an_unbound_or_undeclared_verdict_does_not_fold() -> None:
    d = _decider([_Engine()])
    d.boot()
    assert d.observe_reaction("nope", "good") is False
    d.bind("d2", "q2", {"chosen_action": "gather", "posterior_summary": {}})
    assert d.observe_reaction("d2", "good") is False


def test_a_verdict_before_boot_is_left_to_the_boot_replay() -> None:
    eng = _Engine()
    d = _decider([eng])
    d.bind("d1", "q9", {"chosen_action": "abstain", "posterior_summary": {}})
    assert d.observe_reaction("d1", "bad") is False
    assert eng.sent == []


# --- against the pinned engine ------------------------------------------------------------


@pytest.mark.system
def test_the_pinned_engine_boots_and_decides() -> None:
    command = config.membrane_command()
    if command is None:
        pytest.skip("needs the decider engine: run `make engine`")
    d = DCD.Decider(spawn=lambda: MembraneClient.spawn(command, log=lambda _m: None),
                    u_bar=lambda: {}, snapshot=lambda: BOOT.BootSnapshot([], 0),
                    log=lambda _m: None)
    try:
        opened = d.decide("q1", _payload())
        closed = d.decide("q1", _payload(applied_probes=["corroborate_a"]))
    finally:
        d.close()
    assert opened["act"] in dict(W.AFFORDANCES)
    assert closed["act"] != "gather"
