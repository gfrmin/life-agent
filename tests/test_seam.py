"""The M0 act-committing seam (life_agent.core.seam) — hermetic.

One function commits acts (roadmap M0): the P1 skin `optimise` calls (lookup,
per-claim narrative), the P2 daemon `/decide` POST, and the pre-empting gates
(weak retrieval, executor down) all pass through :func:`seam.commit`. These tests
pin the dispatch contract and the drift gate that keeps the seam single-source.

Run: uv run --project . python -m pytest tests/test_seam.py
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from life_agent.core import seam as S

SRC = Path(__file__).resolve().parents[1] / "src" / "life_agent"


class _RefusingBrain:
    """A brain double that fails the test if the seam consults it — the gate branch
    must decide from the declared observation alone."""

    def optimise(self, state_id: str, *, actions: dict[str, Any],
                 preference: dict[str, Any]) -> tuple[Any, float]:
        raise AssertionError("gate branch must not consult the engine")


class _CannedBrain:
    """Returns a canned (action, eu) and records the call for passthrough checks."""

    def __init__(self, action: Any, eu: float) -> None:
        self.action, self.eu = action, eu
        self.calls: list[tuple[str, dict[str, Any], dict[str, Any]]] = []

    def optimise(self, state_id: str, *, actions: dict[str, Any],
                 preference: dict[str, Any]) -> tuple[Any, float]:
        self.calls.append((state_id, actions, preference))
        return self.action, self.eu


# --- gates: declared observations decide, the engine is not consulted --------------------

def test_gate_short_circuits_to_abstain() -> None:
    d = S.commit(None, gates=(S.GATE_WEAK_RETRIEVAL,))
    assert d.action == "abstain"
    assert d.gate == S.GATE_WEAK_RETRIEVAL
    assert d.eu is None and d.view is None


def test_gate_preempts_an_engine_request() -> None:
    # a declared gate decides even when a full request rides along — the observation
    # pre-empts, exactly as the host forks did before M0, but now visibly at the seam.
    req = S.SkinOptimise(brain=_RefusingBrain(), state_id="s_1",
                         actions={"type": "finite", "values": [0.0]},
                         preference={"type": "functional_per_action", "actions": {}})
    d = S.commit(req, gates=(S.GATE_EXECUTOR_DOWN,))
    assert d.action == "abstain" and d.gate == S.GATE_EXECUTOR_DOWN


def test_no_request_and_no_gate_is_a_contract_error() -> None:
    with pytest.raises(AssertionError):
        S.commit(None)


# --- P1: the skin optimise dispatch ------------------------------------------------------

def test_skin_optimise_passthrough() -> None:
    brain = _CannedBrain("hedge", 1.23)
    actions = {"type": "finite", "values": [0.0]}
    pref = {"type": "functional_per_action", "actions": {"hedge": {}}}
    d = S.commit(S.SkinOptimise(brain=brain, state_id="s_7", actions=actions,
                                preference=pref))
    assert (d.action, d.eu, d.gate, d.view) == ("hedge", 1.23, None, None)
    assert brain.calls == [("s_7", actions, pref)]


def test_skin_optimise_action_is_verbatim() -> None:
    # the seam never renames an act — report_j → report mapping is the caller's render
    # concern, not the commit's.
    d = S.commit(S.SkinOptimise(brain=_CannedBrain("report_2", -0.5), state_id="s",
                                actions={}, preference={}))
    assert d.action == "report_2" and d.eu == -0.5


# --- P2: the daemon /decide dispatch -----------------------------------------------------

def test_daemon_decide_posts_and_returns_view() -> None:
    seen: list[tuple[str, dict[str, Any]]] = []
    reply = {"effector": "report", "value": "42", "credences": [0.9], "p_none": 0.05,
             "eu": 0.8}

    def post(url: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        seen.append((url, payload))
        return reply

    payload = {"candidates": ["42"], "observations": [1], "rho": 0.8}
    d = S.commit(S.DaemonDecide(post=post, daemon="http://d:1", payload=payload))
    assert seen == [("http://d:1/decide", payload)]
    assert d.view is reply
    assert d.action == "report" and d.eu == 0.8 and d.gate is None


def test_daemon_null_reply_asserts() -> None:
    d = S.DaemonDecide(post=lambda url, payload: None, daemon="http://d:1", payload={})
    with pytest.raises(AssertionError):
        S.commit(d)


def test_daemon_missing_eu_is_none() -> None:
    d = S.commit(S.DaemonDecide(post=lambda u, p: {"effector": "miss"},
                                daemon="http://d:1", payload={}))
    assert d.action == "miss" and d.eu is None


# --- the drift gate: exactly ONE module commits acts -------------------------------------

def test_only_the_seam_calls_optimise() -> None:
    """`.optimise(` may appear only in brain.py (the client method) and seam.py (the one
    commit site). A new call anywhere else in src/life_agent is a doctrine bug — a fork
    committing acts outside the seam (roadmap M0; a fork found later is a bug, not a
    preference)."""
    offenders = [
        p.relative_to(SRC)
        for p in SRC.rglob("*.py")
        if p.name not in {"brain.py", "seam.py"}
        and re.search(r"\.optimise\(", p.read_text())
    ]
    assert offenders == []


def test_only_the_seam_posts_decide() -> None:
    """The daemon `/decide` POST may be built only in seam.py. `/decide-support` (the
    membrane shadow's mirror feed) and the bridge's server-side route table are not act
    commits and are excluded by pattern, not by file list."""
    pat = re.compile(r"""/decide["']""")
    offenders = [
        p.relative_to(SRC)
        for p in SRC.rglob("*.py")
        if p.name != "seam.py" and pat.search(p.read_text())
    ]
    assert offenders == []


# --- M3: the live consult re-point (DaemonDecide.live) -----------------------------------

def test_daemon_decide_with_live_commits_the_consult_view() -> None:
    payload = {"candidates": ["a"], "u_bar": {}}
    reply = {"effector": "report", "value": "a", "eu": 1.5}
    seen: list[tuple[dict, dict]] = []

    def live(p: dict, r: dict) -> tuple[dict, str | None]:
        seen.append((p, r))
        return ({"effector": "abstain", "value": None, "eu": None}, None)

    d = S.commit(S.DaemonDecide(post=lambda u, p: reply, daemon="http://d:1",
                                payload=payload, live=live))
    assert seen == [(payload, reply)]  # consulted with the payload + the daemon's reply
    assert d.action == "abstain"
    assert d.eu is None
    assert d.gate is None
    assert d.view == {"effector": "abstain", "value": None, "eu": None}


def test_daemon_decide_live_gate_names_engine_down() -> None:
    def live(p: dict, r: dict) -> tuple[dict, str | None]:
        return ({"effector": "abstain", "value": None}, S.GATE_ENGINE_DOWN)

    d = S.commit(S.DaemonDecide(post=lambda u, p: {"effector": "report"},
                                daemon="http://d:1", payload={}, live=live))
    assert d.action == "abstain"
    assert d.gate == S.GATE_ENGINE_DOWN


def test_daemon_decide_without_live_is_unchanged() -> None:
    d = S.commit(S.DaemonDecide(post=lambda u, p: {"effector": "hedge", "eu": 0.25},
                                daemon="http://d:1", payload={}))
    assert d.action == "hedge"
    assert d.eu == 0.25
    assert d.gate is None
