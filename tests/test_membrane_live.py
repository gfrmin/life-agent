"""``tests/test_membrane_live.py`` — live-integration smokes against the real, frozen
``proplang-host`` decider binary (Task 8, first half). Everything in
``tests/test_membrane_{client,world,session}.py`` runs against fakes/scripted transports;
these tests are first contact with the actual subprocess.

Opt-in only (``system`` marker, skipped by ``pyproject.toml``'s default ``addopts``). Run
explicitly:

    LIFE_AGENT_MEMBRANE_COMMAND=/path/to/proplang-host \\
        uv run --project . pytest tests/test_membrane_live.py -m system -v -s

Each test skips by name unless ``LIFE_AGENT_MEMBRANE_COMMAND`` names a launch argv (the
same env the daemon reads via ``MembraneClient.from_env``), and records (never asserts
equality on) the binary's sha256 when the launcher is a plain file, so a refreshed binary
is visible as a changed number in the output rather than a silent pass or a hard failure.
The binary is a FROZEN artifact of a sibling repo — nothing here edits, rebuilds, or
spawns anything in that repo's checkout; ``MembraneClient.spawn`` runs it exactly as-is.

The re-derived wire (proplang-host, steps 3-10): handshake reply ``{"ok": true, "proto":
1, ...}``; the decide reply is the full assignment ``{"act": {"act": <grid value>}}``; the
single ``said@1`` utility form (``table@1``/``latent@1`` are retired).
"""
from __future__ import annotations

import hashlib
import os
import shlex
from pathlib import Path

import pytest

from life_agent.membrane import world as W
from life_agent.membrane.client import MEMBRANE_ENV, MembraneClient
from life_agent.membrane.session import MembraneSession
from life_agent.membrane.world import DecideSummary

pytestmark = pytest.mark.system

# A synthetic u_bar, shape-matched to core/utility.py's UtilityPosterior.u_bar keys (verified
# in world.py's utility_by_action docstring) — used unchanged so the handshake declared under
# said@1 is directly comparable across tests. Its u_wrong is the world's FALLBACK -9.0, which
# is NOT what the live posterior says (see LIVE_U_BAR).
U_BAR: dict[str, float] = {
    "u_correct": 1.0, "u_abstain": 0.0, "u_wrong": -9.0, "u_wrong_scoped": -4.0,
    "u_hedged": 0.2, "lambda_int": 1.0, "kappa_att": 0.02,
}

# The REAL utility posterior (GET :8798/utility, 2026-07-11): the reaction loop has already
# narrowed u_wrong to about -5.94. Seven scalar means — no owner data. It is here because a
# suite that only ever declared the -9.0 fallback is exactly how a threshold that is a
# FUNCTION of utility got shipped as the constant 0.9.
LIVE_U_BAR: dict[str, float] = {
    "u_correct": 1.0, "u_abstain": 0.0, "u_wrong": -5.9395, "u_wrong_scoped": -2.0827,
    "u_hedged": 0.3964, "lambda_int": 1.0009, "kappa_att": 0.0344,
}

# A utility under which respond IS reachable at the engine's own credence ceiling (a wrong
# assert costs barely more than silence). Not a realistic posterior — a FALSIFICATION case:
# the reachability test must be able to come out the other way, or it pins nothing.
REACHABLE_U_BAR: dict[str, float] = {**LIVE_U_BAR, "u_wrong": -0.1, "kappa_att": 0.02}

# The frozen engine's own attainable credence ceiling (its internal grid tops out here) — a
# property of the BINARY, not of any utility. This is what a utility-derived respond
# threshold is compared against.
ENGINE_P1_CEILING = 0.9


def _membrane_argv() -> list[str]:
    """The launch argv from the daemon's own env var, or skip (by name) — these smokes need
    the real, installed proplang-host, and nothing here hard-codes its path."""
    cmd = os.environ.get(MEMBRANE_ENV)
    if not cmd:
        pytest.skip(f"{MEMBRANE_ENV} unset — live membrane smoke skipped (set it to the "
                    "proplang-host launch argv)")
    return shlex.split(cmd)


@pytest.fixture
def membrane_argv() -> list[str]:
    return _membrane_argv()


@pytest.fixture
def binary_sha256(membrane_argv: list[str]) -> str:
    """Hash the launcher's executable once per test (best-effort — an argv whose command[0]
    is not a plain file records ``"unknown"``) so every assertion message can record which
    build produced the observed numbers."""
    p = Path(membrane_argv[0])
    if p.is_file():
        return hashlib.sha256(p.read_bytes()).hexdigest()
    return "unknown"


def _summary(**kw: object) -> DecideSummary:
    defaults: dict[str, object] = dict(
        n_candidates=1, leader_credence=0.6, p_none=0.1, n_obs=1,
        era_split=False, owner_scoped=False, grow_pass=False,
    )
    defaults.update(kw)
    return DecideSummary(**defaults)  # type: ignore[arg-type]


# --- test 1: handshake + one decide tick + one evidence tick, real binary -----------------


def test_host_handshake_and_decide(membrane_argv: list[str], binary_sha256: str) -> None:
    """One real handshake/decide/evidence round-trip through ``MembraneClient.spawn`` +
    ``MembraneSession`` against the frozen ``proplang-host``. Asserts the documented reply
    shapes (never a specific value beyond "well-formed" — the corpus-independent engine
    internals aren't this test's contract) and that a verdict evidence tick actually
    conditions the agent: a decide taken right after must report a DIFFERENT ``p1`` than the
    cold-start decide, proving the evidence round-tripped rather than being silently dropped.
    """
    sha = binary_sha256
    client = MembraneClient.spawn(membrane_argv, log=lambda _m: None)
    try:
        sess = MembraneSession(client, u_bar=U_BAR, utility_form="said@1", log=lambda _m: None)
        sess.boot()
        engine = sess.engine
        assert engine.get("ok") is True, f"handshake refused (binary sha256={sha}): {engine!r}"
        assert engine.get("proto") == 1, f"proto={engine.get('proto')!r} (binary sha256={sha})"

        s = _summary()
        cold = sess.decide(s)
        assert cold.action in set(W.VALUE_TO_ACTION.values()), (
            f"cold-start action {cold.action!r} not in the declared menu "
            f"{sorted(W.VALUE_TO_ACTION.values())} (binary sha256={sha})"
        )
        assert "p1" in cold.readouts, f"no p1 readout in {cold.readouts!r} (binary sha256={sha})"
        p1_before = cold.readouts["p1"]

        sess.observe_verdict(s, 1)  # round-trips without raising, or the test fails here

        warm = sess.decide(s)
        p1_after = warm.readouts.get("p1")
        assert p1_after != p1_before, (
            f"p1 did NOT move after a y=1 verdict evidence tick: before={p1_before!r} "
            f"after={p1_after!r} (binary sha256={sha}) -- evidence is not conditioning the agent"
        )

        print(
            f"[test_host_handshake_and_decide] binary sha256={sha} "
            f"cold_action={cold.action!r} p1_before={p1_before!r} p1_after={p1_after!r} "
            f"warm_action={warm.action!r}"
        )
    finally:
        client.shutdown()


# --- test 2: the quantitative respond-reachability demand, pinned live ---------------------


@pytest.mark.parametrize(
    ("label", "u_bar"),
    [("fallback", U_BAR), ("live", LIVE_U_BAR), ("reachable", REACHABLE_U_BAR)],
)
def test_respond_reachability_is_a_function_of_the_utility_posterior(
    label: str, u_bar: dict[str, float], membrane_argv: list[str], binary_sha256: str,
) -> None:
    """Whether ``respond`` can fire at all is a FUNCTION of the utility posterior, and this
    pins it as one — against the real binary, at three different utilities. It replaces a test
    that hard-coded ``u_wrong: -9.0`` and asserted the constant "respond needs p1 > 0.9",
    which is how a claim about a fallback constant got published as a claim about the live
    system.

    Two things are asserted, both derived, neither hard-coded:

    1. **The model of the chooser.** Every tick's fired action must equal
       ``world.argmax_action(u_bar, p1)`` — the host-side argmaxEU (first-listed ties) over the
       very sentence the handshake declared, evaluated at the p1 the engine itself reported.
    2. **Reachability.** respond fires iff the engine's attained p1 clears
       ``world.respond_threshold(u_bar)`` — the WHOLE-menu bar (respond must outbid gather/ask,
       not merely abstain, since the engine argmaxes over every affordance).

    ``REACHABLE_U_BAR`` is the falsification case: under it the threshold drops below what the
    engine can attain, so respond MUST fire. A failure of assertion 1 is a REAL finding (our
    reading of the frozen chooser is wrong) — report it, do not patch it away.
    """
    sha = binary_sha256
    threshold = W.respond_threshold(u_bar)
    assert threshold is not None, f"respond can never win under {label} u_bar — bad fixture"

    client = MembraneClient.spawn(membrane_argv, log=lambda _m: None)
    try:
        sess = MembraneSession(client, u_bar=u_bar, utility_form="said@1", log=lambda _m: None)
        sess.boot()

        s = _summary(n_candidates=1, leader_credence=0.95, p_none=0.02, n_obs=10)
        n_ticks = 40
        max_p1: float | None = None
        respond_fired = False
        actions: list[str] = []
        mispredicted: list[tuple[float, str, str]] = []

        for _ in range(n_ticks):
            sess.observe_verdict(s, 1)
            choice = sess.decide(s)
            actions.append(choice.action)
            p1 = choice.readouts.get("p1")
            if isinstance(p1, int | float):
                max_p1 = float(p1) if max_p1 is None else max(max_p1, float(p1))
                predicted = W.argmax_action(u_bar, float(p1))
                if predicted != choice.action:
                    mispredicted.append((float(p1), predicted, choice.action))
            if choice.action == "respond":
                respond_fired = True

        assert max_p1 is not None, (
            f"no p1 readout observed across {n_ticks} y=1 verdict ticks (binary sha256={sha})"
        )
        assert not mispredicted, (
            f"the host-side model of the frozen chooser is WRONG under the {label} u_bar: "
            f"(p1, predicted, actual) = {mispredicted[:5]} (binary sha256={sha}). Everything "
            "the offline report derives from the declared sentence (respond thresholds, the "
            "policy-by-credence regions) rests on this agreeing -- re-derive it, do not "
            "loosen this assertion"
        )
        expect_respond = max_p1 > threshold
        assert respond_fired == expect_respond, (
            f"respond_fired={respond_fired} but the {label} u_bar's whole-menu threshold "
            f"({threshold:.4f}) against the attained max_p1 ({max_p1:.4f}) says "
            f"{expect_respond} (binary sha256={sha}, actions tail={actions[-5:]})"
        )

        vs_abstain = ((u_bar["u_abstain"] - u_bar["u_wrong"])
                      / (u_bar["u_correct"] - u_bar["u_wrong"]))
        print(
            f"[respond_reachability:{label}] binary sha256={sha} max_p1={max_p1} "
            f"threshold_whole_menu={threshold:.4f} threshold_vs_abstain={vs_abstain:.4f} "
            f"respond_fired={respond_fired} distinct_actions={sorted(set(actions))} "
            f"actions_tail={actions[-5:]}"
        )
    finally:
        client.shutdown()


# --- test 3 (E1 stage 1): the categorical world on the real binary ------------------------


def test_categorical_world_handshakes_and_decides(
    membrane_argv: list[str], binary_sha256: str,
) -> None:
    """First contact for the E1 categorical declaration (obs_arity = K+1, the
    value-indexed act grid, the §4.3 utility sentence) against the REAL engine: one
    session-per-question episode — handshake, three code-valued evidence ticks, one
    decide — through ``categorical.run_categorical`` exactly as the shadow runs it.
    Asserts well-formed replies and a decodable act, never a specific choice (the
    engine's internals aren't this test's contract)."""
    from life_agent.membrane import categorical as C

    s = C.CatSummary(
        k=3, obs_codes=(1, 1, 2), n_obs=3, n_obs_unmapped=0, daemon_map_index=0,
        era_split=False, owner_scoped=True, grow_pass=False,
    )
    choice = C.run_categorical(membrane_argv, U_BAR, s, read_timeout_s=60.0)
    assert choice.engine.get("ok") is True
    assert choice.engine.get("proto") == 1
    assert isinstance(choice.engine.get("models"), int)
    valid = {"abstain", "gather", "ask", "respond_1", "respond_2", "respond_3"}
    assert choice.action in valid, (
        f"undecodable act {choice.action!r} (binary {binary_sha256[:12]})"
    )
    assert "p1" in choice.readouts
    print(f"\n  categorical K=3: models={choice.engine['models']} "
          f"action={choice.action} p1={choice.readouts.get('p1')} "
          f"(binary {binary_sha256[:12]})")


def test_categorical_k2_declaration_is_accepted_alongside_binary(
    membrane_argv: list[str],
) -> None:
    """A K=1 world (obs_arity 2 — the wire's floor, extensionally the binary channel)
    must also handshake: the smallest lawful categorical episode."""
    from life_agent.membrane import categorical as C

    s = C.CatSummary(
        k=1, obs_codes=(1,), n_obs=1, n_obs_unmapped=0, daemon_map_index=0,
        era_split=False, owner_scoped=False, grow_pass=False,
    )
    choice = C.run_categorical(membrane_argv, U_BAR, s, read_timeout_s=60.0)
    assert choice.engine.get("ok") is True
    assert choice.action in {"abstain", "gather", "ask", "respond_1"}
