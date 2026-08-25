"""M5 — the argmax absorption (r15): the driver holds no choice the ranking could make.

Phase P-I pins: the M3 membrane live lane is DELETED (Q8 — ``map_action`` survives as
the shadow worker's measurement function), ``core/gather.py`` is DELETED (GA-1…GA-3:
gathering is a K row the daemon prices), and B-4's weak-retrieval pre-emption is
DELETED (S-1 split: belief-side — few/weak observations withhold by EU, not by a host
threshold). Deletion pins are drift gates: the absence IS the contract.
"""
from __future__ import annotations

import dataclasses
import inspect
import sys
from pathlib import Path

import pytest

from life_agent.core import config as CFG
from life_agent.core import executor as EX
from life_agent.core import seam as SEAM
from life_agent.membrane import coarse as CRS

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

_SRC = Path(__file__).resolve().parent.parent / "src" / "life_agent"
_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


# --- P-I(a): the M3 live lane is gone ------------------------------------------------ #

def test_the_live_lane_died_from_coarse() -> None:
    """coarse keeps map_action (the shadow worker's measurement, Q8) and nothing live."""
    assert hasattr(CRS, "map_action")
    assert not hasattr(CRS, "live_decide")
    assert not hasattr(CRS, "LIVE_TIMEOUT_S")


def test_config_has_no_membrane_live_flag() -> None:
    assert not hasattr(CFG, "membrane_live")
    assert not hasattr(CFG, "MEMBRANE_LIVE_ENV")


def test_seam_has_no_live_plumbing() -> None:
    """The DaemonDecide request carries no live consult; the LiveFn type is gone."""
    assert not hasattr(SEAM, "LiveFn")
    assert "live" not in {f.name for f in dataclasses.fields(SEAM.DaemonDecide)}


def test_executor_loop_has_no_live_parameter() -> None:
    assert "live" not in inspect.signature(EX.decide_via_loop).parameters
    assert "live" not in inspect.signature(EX.run_pass).parameters


def test_drive_has_no_live_branch() -> None:
    """The driver always shadow-wraps: the flag-gated fork is not in the source."""
    src = (_SRC / "core" / "ask_client.py").read_text()
    assert "membrane_live" not in src
    assert "live_decide" not in src


def test_bridge_has_no_decide_live_endpoint() -> None:
    src = (_SRC / "bridge" / "server.py").read_text()
    assert "_decide_live" not in src
    assert "decide_live" not in src


def test_shadow_keeps_the_feed_not_the_live_half() -> None:
    src = (_SRC / "membrane" / "shadow.py").read_text()
    assert "decide_live" not in src
    assert "_LIVE_WAIT_S" not in src


# --- P-I(b): gather is gone ---------------------------------------------------------- #

def test_gather_module_died() -> None:
    with pytest.raises(ModuleNotFoundError):
        import life_agent.core.gather  # noqa: F401


def test_ask_has_no_gather_fork() -> None:
    src = (_SCRIPTS / "ask.py").read_text()
    assert "gather_answer" not in src
    assert "answer_brain_gate" not in {p.name for p in _SCRIPTS.glob("*.py")}


# --- P-I(c): B-4's pre-emption is gone ----------------------------------------------- #

def test_weak_retrieval_gate_died_from_the_seam() -> None:
    """S-1 split: the belief-side gate dies; the unavailability gates stay (§6.5)."""
    assert not hasattr(SEAM, "GATE_WEAK_RETRIEVAL")
    assert SEAM.GATE_EXECUTOR_DOWN == "executor_down"
    assert SEAM.GATE_ENGINE_DOWN == "engine_down"


def test_ask_has_no_weak_retrieval_predicate() -> None:
    src = (_SCRIPTS / "ask.py").read_text()
    assert "retrieval_is_weak" not in src
    assert "WEAK_SCORE_FLOOR" not in src
    assert "MIN_STRONG_HITS" not in src
