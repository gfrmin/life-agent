"""The credence seam (src/life_agent/core/brain.py) — bayesian-foundations §11.

Four strata, hermetic by default:

0. The production spawn argv built by `_docker_argv` — pure, no subprocess, no docker.
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
    t = FakeTransport(results={"initialize": {"protocol": "1.7", "version": "0", "methods": []}})
    with B.Brain(t) as b:
        b.initialize()
    # initialize sends the protocol-major handshake.
    assert t.sent[0]["method"] == "initialize" and t.sent[0]["params"]["protocol"] == "1"
    assert t.sent[-1]["method"] == "shutdown"
    assert t.closed


def test_initialize_rejects_major_mismatch() -> None:
    t = FakeTransport(results={"initialize": {"protocol": "2.0"}})
    with pytest.raises(B.BrainError) as exc:
        B.Brain(t).initialize()
    assert exc.value.code == -32010


def test_destroy_state() -> None:
    t = FakeTransport()
    B.Brain(t).destroy_state("s_1")
    assert t.sent[0] == {"jsonrpc": "2.0", "id": 1, "method": "destroy_state",
                         "params": {"state_id": "s_1"}}


# --- the production spawn argv (no subprocess, no docker) --------------------------------
# `_docker_argv` reads $CREDENCE_SKIN_RUN_ARGS at CALL time, so a plain `monkeypatch.setenv`
# is observable here — unlike B.CREDENCE_SKIN_IMAGE / B._DEV_REPO, which freeze at import and
# would need an importlib.reload. Same shape as tests/test_config_membrane.py's
# membrane_command trio (unset / shell-split / empty string). Until now the `docker run`
# branch was exercised by no test at all.

def test_docker_argv_is_bare_when_run_args_unset(monkeypatch) -> None:
    monkeypatch.delenv(B.CREDENCE_SKIN_RUN_ARGS_ENV, raising=False)
    assert B._docker_argv("img:1") == ["docker", "run", "--rm", "-i", "img:1"]


def test_docker_argv_shell_splits_run_args_before_the_image(monkeypatch) -> None:
    monkeypatch.setenv(B.CREDENCE_SKIN_RUN_ARGS_ENV,
                       "--memory=4g --label managed-by=example")
    assert B._docker_argv("img:1") == [
        "docker", "run", "--rm", "-i",
        "--memory=4g", "--label", "managed-by=example", "img:1"]


def test_docker_argv_empty_run_args_is_bare(monkeypatch) -> None:
    monkeypatch.setenv(B.CREDENCE_SKIN_RUN_ARGS_ENV, "")
    assert B._docker_argv("img:1") == ["docker", "run", "--rm", "-i", "img:1"]


def test_docker_argv_never_names_the_container(monkeypatch) -> None:
    """No ``--name``: engines are spawned concurrently from several processes and ``--rm``
    cleanup is not guaranteed on SIGKILL, so a fixed name would collide with nothing
    anywhere to reconcile it. Attribution is ``--label``, which the deployment passes in."""
    monkeypatch.delenv(B.CREDENCE_SKIN_RUN_ARGS_ENV, raising=False)
    assert "--name" not in B._docker_argv("img:1")


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
    if not (B._DEV_REPO or B._DEV_SERVER):
        pytest.skip("set $CREDENCE_REPO or $CREDENCE_SKIN_SERVER to spawn a dev engine")
    with B.Brain.spawn() as b:
        b.initialize()
        s = b.create_state({"type": "beta", "alpha": 1.0, "beta": 1.0})
        b.condition(s, kernel={"type": "bernoulli"}, observation=1.0)
        # Beta(1,1) + one success -> Beta(2,1), mean 2/3
        assert b.mean(s) == pytest.approx(2 / 3, abs=1e-9)


# --- the VOI wire shapes the module collapse pins (M0; design §2.5, §6.3b) ----------------
# Two claims made falsifiable rather than promised: `value` is the wire that would price a
# kernel in the terminals-only regime (ruling Q-R4 — unclaimed, it dies), and `draw` decides
# where the adoption gate's host P(U) sampler lives (pre-committed procedure, Q4).

def test_value_is_pinned_like_optimise_as_the_voi_wire_shape() -> None:
    """`value(state_id, action_utilities) -> float`: the maximum expected utility WITHOUT
    the action — VOI = value(informed) - value(uninformed), composed at the call site
    (design §2.5). Deleting `Brain.value` fails here, which is what earns it "dormant-keep"
    instead of a promise.

    The preference shape is the one the decision path actually builds: the
    `functional_per_action` map `lookup.action_utilities` produces, one tabular functional
    per action over the K candidates + NONE."""
    t = FakeTransport(results={"value": {"value": 0.42}})
    b = B.Brain(t)
    action_utilities = {"report_0": [1.0, -5.0, -5.0], "hedge": [0.2, 0.2, -5.0],
                        "abstain": [0.0, 0.0, 0.0]}
    preference = {"type": "functional_per_action",
                  "actions": {name: {"type": "tabular", "values": vec}
                              for name, vec in action_utilities.items()}}
    out = b.value("s_1", actions={"type": "finite", "values": [0.0]},
                  preference=preference)
    assert isinstance(out, float) and out == pytest.approx(0.42)
    (req,) = t.sent
    assert req["method"] == "value"
    assert req["params"]["state_id"] == "s_1"
    assert req["params"]["preference"] == preference
    assert set(req["params"]) == {"state_id", "actions", "preference"}


def test_draw_is_not_on_this_body_s_wire_surface() -> None:
    """§6.3b's check, host side: `Brain` exposes no `draw`, so the adoption gate's
    `_sample_u` cannot sample the utility posterior over the wire today — it approximates
    P(U) host-side from moment summaries. Whether the ENGINE exposes one is the live
    half of the check (`test_live_skin_advertises_its_method_surface`, opt-in)."""
    assert not hasattr(B.Brain, "draw")


@pytest.mark.system
def test_live_skin_serves_draw_but_not_for_the_utility_posterior_s_measures() -> None:
    """The Q4/§6.3b wire-shape check, executed against the engine — and left in as a
    TRIPWIRE.

    Measured at M0 on the pinned protocol-1.12 image: ``draw`` is served as a verb and works
    on conjugate measures (Beta), but has no method for either measure the utility posterior
    folds into — ``truncated_gaussian`` (an independent latent, ``utility._fold_1d``) or
    ``truncated_mv_gaussian`` (a coupled component, ``utility._fold_joint``). So P(U) cannot
    be sampled over the wire today, and ``gate._sample_u``'s host moment-Gaussian sampler
    stays inside §6.1's exception rather than becoming debt §6.3b.

    **If this test fails because a draw SUCCEEDED, the engine has gained the capability and
    the ruling flips**: register §6.3b with the retirement path (a ``Brain.draw`` wrapper,
    then sample on the wire) and delete the exception's coverage of G-3.
    """
    if not (B._DEV_REPO or B._DEV_SERVER):
        pytest.skip("set $CREDENCE_REPO or $CREDENCE_SKIN_SERVER to spawn a dev engine")
    with B.Brain.spawn() as b:
        info = b.initialize()
        assert "draw" in set(info.get("methods") or ()), "the verb itself is gone"
        conjugate = b.create_state({"type": "beta", "alpha": 2.0, "beta": 3.0})
        try:
            assert isinstance(b._call("draw", {"state_id": conjugate})["value"], float)
        finally:
            b.destroy_state(conjugate)
        for spec in ({"type": "truncated_gaussian", "mu": 0.0, "sigma": 1.0,
                      "lo": -5.0, "hi": 5.0},
                     {"type": "truncated_mv_gaussian", "mu": [0.0, 0.0],
                      "sigma": [1.0, 1.0], "lo": [-5.0, -5.0], "hi": [5.0, 5.0]}):
            sid = b.create_state(spec)
            try:
                with pytest.raises(B.BrainError, match="no method matching draw"):
                    b._call("draw", {"state_id": sid})
            finally:
                b.destroy_state(sid)
