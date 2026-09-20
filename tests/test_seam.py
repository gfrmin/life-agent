"""The M0 act-committing seam (life_agent.core.seam) — hermetic.

One function commits acts (roadmap M0): the bridge `/decide` POST and the pre-empting
gate (executor down) both pass through :func:`seam.commit`. These tests
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


# --- gates: declared observations decide, the engine is not consulted --------------------

# r23 (F8): the exemption is an EXACT repo-relative path, never a basename. `p.name` let
# a file called `seam.py` ANYWHERE under src/life_agent exempt itself from the guard that
# says one function commits acts — a fork committing acts outside the seam, invisible.
_SEAM_EXEMPT = frozenset({"core/seam.py"})


def test_gate_short_circuits_to_abstain() -> None:
    d = S.commit(None, gates=(S.GATE_EXECUTOR_DOWN,))
    assert d.action == "abstain"
    assert d.gate == S.GATE_EXECUTOR_DOWN
    assert d.eu is None and d.view is None


def test_gate_preempts_an_engine_request() -> None:
    # a declared gate decides even when a full request rides along — the observation
    # pre-empts, exactly as the host forks did before M0, but now visibly at the seam.
    def post(url: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        raise AssertionError("gate branch must not consult the decider")

    req = S.Decide(post=post, bridge="http://d:1", payload={})
    d = S.commit(req, gates=(S.GATE_EXECUTOR_DOWN,))
    assert d.action == "abstain" and d.gate == S.GATE_EXECUTOR_DOWN


def test_no_request_and_no_gate_is_a_contract_error() -> None:
    with pytest.raises(AssertionError):
        S.commit(None)


# --- the decider: the bridge /decide dispatch -----------------------------------------------------

def test_decide_posts_and_returns_view() -> None:
    seen: list[tuple[str, dict[str, Any]]] = []
    reply = {"effector": "report", "value": "42", "credences": [0.9], "p_none": 0.05,
             "eu": 0.8}

    def post(url: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        seen.append((url, payload))
        return reply

    payload = {"candidates": ["42"], "observations": [1], "rho": 0.8}
    d = S.commit(S.Decide(post=post, bridge="http://d:1", payload=payload))
    assert seen == [("http://d:1/decide", payload)]
    assert d.view is reply
    assert d.action == "report" and d.eu == 0.8 and d.gate is None


def test_decide_null_reply_asserts() -> None:
    d = S.Decide(post=lambda url, payload: None, bridge="http://d:1", payload={})
    with pytest.raises(AssertionError):
        S.commit(d)


def test_decide_missing_eu_is_none() -> None:
    d = S.commit(S.Decide(post=lambda u, p: {"effector": "miss"},
                                bridge="http://d:1", payload={}))
    assert d.action == "miss" and d.eu is None


# --- the drift gate: exactly ONE module commits acts -------------------------------------

def test_only_the_seam_calls_optimise() -> None:
    """No engine `.optimise(` call survives in src/life_agent: the act is
    ``core/decide.bayes_act`` (its callers are gated in tests/test_decider.py). A new call
    is a doctrine bug — a fork committing acts outside the seam."""
    offenders = [
        p.relative_to(SRC)
        for p in SRC.rglob("*.py")
        if p.relative_to(SRC).as_posix() not in _SEAM_EXEMPT
        and re.search(r"\.optimise\(", p.read_text())
    ]
    assert offenders == []


def test_only_the_seam_posts_decide() -> None:
    """The `/decide` POST may be built only in seam.py. The bridge's server-side route
    table serves it and is not an act commit."""
    pat = re.compile(r"""/decide["']""")
    offenders = [
        p.relative_to(SRC)
        for p in SRC.rglob("*.py")
        if p.relative_to(SRC).as_posix() not in ("core/seam.py", "bridge/server.py")
        and pat.search(p.read_text())
    ]
    assert offenders == []
