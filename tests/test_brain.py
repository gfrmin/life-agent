"""The credence seam (src/life_agent/core/brain.py) — bayesian-foundations §11.

Three strata, hermetic by default:

1. Protocol tests against a scripted in-memory transport (no subprocess): request
   envelopes, result extraction, error mapping.
2. Transport tests against a *Python* fake skin speaking the real wire protocol over
   real pipes (ready sentinel, line framing, bounded close) — no Julia.
3. One live smoke against the real Julia skin, ``@pytest.mark.system`` (opt-in:
   ``pytest -m system tests/test_brain.py``; cold-compile can take ~2 min).

Run: uv run --project . python -m pytest tests/test_brain.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from life_agent.core import brain as B

# --- stratum 1: protocol over a scripted transport --------------------------------------


class FakeTransport:
    """Scripted responses keyed by method; records every request line."""

    def __init__(self, results: dict[str, object] | None = None,
                 errors: dict[str, dict] | None = None) -> None:
        self.sent: list[dict] = []
        self.results = results or {}
        self.errors = errors or {}
        self.closed = False

    def send(self, line: str) -> None:
        self.sent.append(json.loads(line))

    def recv(self) -> str:
        req = self.sent[-1]
        if req["method"] in self.errors:
            return json.dumps({"jsonrpc": "2.0", "id": req["id"],
                               "error": self.errors[req["method"]]})
        return json.dumps({"jsonrpc": "2.0", "id": req["id"],
                           "result": self.results.get(req["method"], "ok")})

    def close(self) -> None:
        self.closed = True


def test_request_envelope_is_jsonrpc2_with_incrementing_ids() -> None:
    t = FakeTransport(results={"mean": {"mean": 0.5}, "weights": {"weights": [1.0]}})
    b = B.Brain(t)
    b.mean("s_1")
    b.weights("s_1")
    assert [r["id"] for r in t.sent] == [1, 2]
    for r in t.sent:
        assert r["jsonrpc"] == "2.0" and "method" in r and "params" in r
    assert t.sent[0]["params"] == {"state_id": "s_1"}


def test_create_state_returns_state_id() -> None:
    t = FakeTransport(results={"create_state": {"state_id": "s_7"}})
    b = B.Brain(t)
    assert b.create_state({"type": "beta", "alpha": 1.0, "beta": 1.0}) == "s_7"
    assert t.sent[0]["params"] == {"type": "beta", "alpha": 1.0, "beta": 1.0}


def test_condition_returns_log_marginal() -> None:
    t = FakeTransport(results={"condition": {"state_id": "s_1", "log_marginal": -0.693}})
    b = B.Brain(t)
    lm = b.condition("s_1", kernel={"type": "bernoulli"}, observation=1.0)
    assert lm == pytest.approx(-0.693)
    assert t.sent[0]["params"]["kernel"] == {"type": "bernoulli"}


def test_expect_mean_weights_value_extract_scalars() -> None:
    t = FakeTransport(results={
        "expect": {"value": 0.25}, "mean": {"mean": 0.5},
        "weights": {"weights": [0.2, 0.8]},
        "value": {"value": 0.85},
    })
    b = B.Brain(t)
    assert b.expect("s", function={"type": "identity"}) == pytest.approx(0.25)
    assert b.mean("s") == pytest.approx(0.5)
    assert b.weights("s") == [0.2, 0.8]
    assert b.value("s", actions={"type": "finite", "values": [0, 1]},
                   preference={"type": "tabular_2d", "matrix": [[1, 0], [0, 1]]}
                   ) == pytest.approx(0.85)


def test_optimise_returns_action_and_eu() -> None:
    t = FakeTransport(results={"optimise": {"action": "report", "eu": 0.9}})
    b = B.Brain(t)
    action, eu = b.optimise("s", actions={"type": "finite",
                                          "values": ["report", "abstain"]},
                            preference={"type": "tabular_2d", "matrix": [[1, 0]]})
    assert action == "report" and eu == pytest.approx(0.9)


def test_skin_error_maps_to_brain_error_with_code() -> None:
    t = FakeTransport(errors={"mean": {"code": -32000, "message": "state not found: s_9"}})
    b = B.Brain(t)
    with pytest.raises(B.BrainError, match="state not found") as exc:
        b.mean("s_9")
    assert exc.value.code == -32000


def test_context_manager_shuts_down_and_closes() -> None:
    t = FakeTransport()
    with B.Brain(t) as b:
        b.initialize()
    assert t.sent[-1]["method"] == "shutdown"
    assert t.closed


def test_destroy_state() -> None:
    t = FakeTransport()
    B.Brain(t).destroy_state("s_1")
    assert t.sent[0] == {"jsonrpc": "2.0", "id": 1, "method": "destroy_state",
                         "params": {"state_id": "s_1"}}


# --- stratum 2: the subprocess transport over real pipes (Python fake skin) -------------

_FAKE_SKIN = r"""
import json, sys
print(json.dumps({"status": "ready"}), flush=True)
for line in sys.stdin:
    req = json.loads(line)
    if req["method"] == "shutdown":
        print(json.dumps({"jsonrpc": "2.0", "id": req["id"], "result": "ok"}), flush=True)
        break
    print(json.dumps({"jsonrpc": "2.0", "id": req["id"],
                      "result": {"echo": req["method"]}}), flush=True)
"""


def test_subprocess_transport_waits_for_ready_and_round_trips() -> None:
    t = B.SubprocessTransport([sys.executable, "-c", _FAKE_SKIN], startup_timeout=30.0)
    b = B.Brain(t)
    assert b._call("anything", {"x": 1}) == {"echo": "anything"}
    b.shutdown()


def test_subprocess_transport_early_crash_is_a_loud_error() -> None:
    with pytest.raises(B.BrainError, match="before ready"):
        B.SubprocessTransport(
            [sys.executable, "-c", "import sys; sys.exit(3)"], startup_timeout=30.0)


def test_subprocess_transport_death_mid_session_is_loud() -> None:
    t = B.SubprocessTransport(
        [sys.executable, "-c",
         'import json; print(json.dumps({"status": "ready"}), flush=True)'],
        startup_timeout=30.0)
    b = B.Brain(t)
    with pytest.raises(B.BrainError, match="died"):
        b.mean("s_1")
    t.close()


# --- stratum 3: live Julia smoke (opt-in) ------------------------------------------------


@pytest.mark.system
def test_live_skin_beta_bernoulli_conjugate_update() -> None:
    repo = Path(B.CREDENCE_REPO)
    if not (repo / "apps/skin/server.jl").exists():
        pytest.skip(f"credence repo not found at {repo}")
    with B.Brain.spawn() as b:
        b.initialize()
        s = b.create_state({"type": "beta", "alpha": 1.0, "beta": 1.0})
        b.condition(s, kernel={"type": "bernoulli"}, observation=1.0)
        # Beta(1,1) + one success -> Beta(2,1), mean 2/3
        assert b.mean(s) == pytest.approx(2 / 3, abs=1e-9)
