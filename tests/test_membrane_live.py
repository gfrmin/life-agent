"""``tests/test_membrane_live.py`` — live-integration smokes against the real, frozen
``proplang-govhost`` decider binary (Task 8, first half). Everything in
``tests/test_membrane_{client,world,session}.py`` runs against fakes/scripted transports;
these three tests are first contact with the actual subprocess.

Opt-in only (``system`` marker, skipped by ``pyproject.toml``'s default ``addopts``). Run
explicitly:

    uv run --project . pytest tests/test_membrane_live.py -m system -v -s

Each test skips by name if ``~/.local/bin/proplang-govhost`` is absent, and records (never
asserts equality on) the binary's sha256, so a refreshed binary is visible as a changed number
in the output rather than a silent pass or a hard failure. The binary is a FROZEN artifact of
a sibling repo — nothing here edits, rebuilds, or spawns anything in that repo's checkout;
``MembraneClient.spawn`` runs the installed binary exactly as-is.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from life_agent.membrane import world as W
from life_agent.membrane.client import MembraneClient
from life_agent.membrane.session import MembraneSession
from life_agent.membrane.world import DecideSummary

pytestmark = pytest.mark.system

GOVHOST_BIN = Path.home() / ".local" / "bin" / "proplang-govhost"

# A synthetic u_bar, shape-matched to core/utility.py's UtilityPosterior.u_bar keys (verified
# in world.py's utility_rows/latent_utility_decl docstrings) — used unchanged in tests 1 and 2
# so the handshake declared under table@1 and latent@1 is directly comparable. Its u_wrong is
# the world's FALLBACK -9.0, which is NOT what the live posterior says (see LIVE_U_BAR).
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

# The frozen engine's own attainable credence ceiling (its internal thetaPoints-shaped grid
# tops out here) — a property of the BINARY, not of any utility. This is what a
# utility-derived respond threshold is compared against.
ENGINE_P1_CEILING = 0.9


@pytest.fixture
def govhost_sha256() -> str:
    """Skip (by name) unless the frozen binary exists; otherwise hash it once per test so
    every assertion message below can record which build produced the observed numbers."""
    if not GOVHOST_BIN.exists():
        pytest.skip(f"proplang-govhost not found at {GOVHOST_BIN} — live membrane smoke skipped")
    return hashlib.sha256(GOVHOST_BIN.read_bytes()).hexdigest()


def _summary(**kw: object) -> DecideSummary:
    defaults: dict[str, object] = dict(
        n_candidates=1, leader_credence=0.6, p_none=0.1, n_obs=1,
        era_split=False, owner_scoped=False, grow_pass=False,
    )
    defaults.update(kw)
    return DecideSummary(**defaults)  # type: ignore[arg-type]


# --- test 1: handshake + one decide tick + one evidence tick, real binary -----------------


def test_govhost_handshake_and_decide(govhost_sha256: str) -> None:
    """One real handshake/decide/evidence round-trip through ``MembraneClient.spawn`` +
    ``MembraneSession`` against the frozen ``proplang-govhost``. Asserts the documented
    reply shapes (never a specific value beyond "well-formed" — the corpus-independent
    engine internals aren't this test's contract) and that a verdict evidence tick actually
    conditions the agent: a decide taken right after must report a DIFFERENT ``p1`` than the
    cold-start decide, proving the evidence round-tripped rather than being silently dropped.
    """
    sha = govhost_sha256
    client = MembraneClient.spawn([str(GOVHOST_BIN)], log=lambda _m: None)
    try:
        sess = MembraneSession(client, u_bar=U_BAR, utility_form="table@1", log=lambda _m: None)
        sess.boot()
        engine = sess.engine
        assert engine.get("ok") is True, f"handshake refused (binary sha256={sha}): {engine!r}"
        assert engine.get("proto") == 1, f"proto={engine.get('proto')!r} (binary sha256={sha})"
        models = engine.get("models")
        assert isinstance(models, int) and models > 0, (
            f"models={models!r} not a positive int (binary sha256={sha})"
        )
        namespace_bits = engine.get("namespace_bits")
        assert isinstance(namespace_bits, (int, float)) and namespace_bits > 0, (
            f"namespace_bits={namespace_bits!r} not positive (binary sha256={sha})"
        )

        s = _summary()
        cold = sess.decide(s)
        assert cold.action in set(W.ID_TO_ACTION.values()), (
            f"cold-start action {cold.action!r} not in the declared menu "
            f"{sorted(W.ID_TO_ACTION.values())} (binary sha256={sha})"
        )
        assert "p1" in cold.readouts, f"no p1 readout in {cold.readouts!r} (binary sha256={sha})"
        assert "entropy_bits" in cold.readouts, (
            f"no entropy_bits readout in {cold.readouts!r} (binary sha256={sha})"
        )
        p1_before = cold.readouts["p1"]

        sess.observe_verdict(s, 1)  # round-trips without raising, or the test fails here

        warm = sess.decide(s)
        p1_after = warm.readouts.get("p1")
        assert p1_after != p1_before, (
            f"p1 did NOT move after a y=1 verdict evidence tick: before={p1_before!r} "
            f"after={p1_after!r} (binary sha256={sha}) -- evidence is not conditioning the agent"
        )

        print(
            f"[test_govhost_handshake_and_decide] binary sha256={sha} models={models} "
            f"namespace_bits={namespace_bits} cold_action={cold.action!r} "
            f"p1_before={p1_before!r} p1_after={p1_after!r} warm_action={warm.action!r}"
        )
    finally:
        client.shutdown()


# --- test 2: latent@1 action-degeneracy, the stated-prediction discipline -----------------


def test_latent_degenerate_prediction(govhost_sha256: str) -> None:
    """The credence-governor's stated-prediction discipline, ported: ``latent@1``'s
    ``said: ["var", 1]`` payload is action-degenerate over the wire-expressible subset (the
    frozen ``host-governor/WireU.hs`` parser's ``pSaid`` implements only ``["var", i]``) — every
    terminal value the pointer can express moves together, so the argmaxEU tie among the
    non-charged affordances resolves to the first-listed one (menu order is NORMATIVE,
    membrane-wire.md CL-3), and the fired action is CONSTANT no matter what features are sent.

    This is a FALSIFICATION INSTRUMENT, pinned BEFORE reading the result, not a foregone
    conclusion dressed up as a test: if the action ever varies across materially different
    feature vectors below, the reading of the frozen driver is wrong somewhere -- and that is
    equally a result this test exists to surface. Do not "fix" a variance finding into a pass;
    report it.
    """
    sha = govhost_sha256
    client = MembraneClient.spawn([str(GOVHOST_BIN)], log=lambda _m: None)
    try:
        sess = MembraneSession(client, u_bar=U_BAR, utility_form="latent@1", log=lambda _m: None)
        sess.boot()

        summaries = [
            _summary(n_candidates=0, leader_credence=None, p_none=None, n_obs=0,
                     era_split=False, owner_scoped=False, grow_pass=False),
            _summary(n_candidates=3, leader_credence=0.95, p_none=0.02, n_obs=6,
                     era_split=True, owner_scoped=True, grow_pass=False),
            _summary(n_candidates=1, leader_credence=0.4, p_none=0.6, n_obs=0,
                     era_split=False, owner_scoped=False, grow_pass=True),
        ]
        choices = [sess.decide(s) for s in summaries]
        actions = [c.action for c in choices]
        constant = actions[0]

        assert len(set(actions)) == 1, (
            f"latent@1 action VARIED across materially different feature vectors: {actions} "
            f"(binary sha256={sha}) -- this FALSIFIES the action-degeneracy prediction; "
            "the frozen driver's said=[\"var\",1] reading needs re-derivation, not a code fix"
        )

        sensitivities = [c.readouts.get("sensitivity") for c in choices]
        assert all(v is False for v in sensitivities), (
            f"engine sensitivity readouts={sensitivities} (expected all False, corroborating "
            f"the degeneracy) while the fired action was constant={constant!r} "
            f"(binary sha256={sha})"
        )

        print(
            f"[test_latent_degenerate_prediction] binary sha256={sha} "
            f"constant action={constant!r} across {len(summaries)} feature vectors; "
            f"sensitivity readouts={sensitivities}"
        )
    finally:
        client.shutdown()


# --- test 3: the quantitative Boundary-V/R demand, pinned live ----------------------------


@pytest.mark.parametrize(
    ("label", "u_bar"),
    [("fallback", U_BAR), ("live", LIVE_U_BAR), ("reachable", REACHABLE_U_BAR)],
)
def test_respond_reachability_is_a_function_of_the_utility_posterior(
    label: str, u_bar: dict[str, float], govhost_sha256: str,
) -> None:
    """Whether ``respond`` can fire at all is a FUNCTION of the utility posterior, and this
    pins it as one — against the real binary, at three different utilities. It replaces a test
    that hard-coded ``u_wrong: -9.0`` and asserted the constant "respond needs p1 > 0.9",
    which is how a claim about a fallback constant got published as a claim about the live
    system: the live posterior's u_wrong is about -5.94 (the reaction loop narrowed it), where
    the respond-vs-abstain bar is 0.856 — BELOW the engine's own 0.892 asymptote.

    Two things are asserted, both derived, neither hard-coded:

    1. **The model of the chooser.** Every tick's fired action must equal
       ``world.argmax_action(u_bar, p1)`` — the host-side argmaxEU (first-listed ties) over the
       very table the handshake declared, evaluated at the p1 the engine itself reported. This
       is the check that earns the right to derive anything from that table offline (the
       report's demand ledger does exactly that).
    2. **Reachability.** respond fires iff the engine's attained p1 clears
       ``world.respond_threshold(u_bar)`` — the WHOLE-menu bar (respond must outbid gather/ask,
       not merely abstain, since the engine argmaxes over every row).

    ``REACHABLE_U_BAR`` is the falsification case: under it the threshold drops below what the
    engine can attain, so respond MUST fire. Without it, "respond never fires" would be
    unfalsifiable here. A failure of assertion 1 is a REAL finding (our reading of the frozen
    chooser is wrong) — report it, do not patch it away.
    """
    sha = govhost_sha256
    threshold = W.respond_threshold(u_bar)
    assert threshold is not None, f"respond can never win under {label} u_bar — bad fixture"

    client = MembraneClient.spawn([str(GOVHOST_BIN)], log=lambda _m: None)
    try:
        sess = MembraneSession(client, u_bar=u_bar, utility_form="table@1", log=lambda _m: None)
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
        assert max_p1 <= ENGINE_P1_CEILING + 1e-9, (
            f"p1 EXCEEDED the frozen {ENGINE_P1_CEILING} grid ceiling: max_p1={max_p1} after "
            f"{n_ticks} y=1 verdicts (binary sha256={sha}) -- the thetaPoints grid may have "
            "widened; re-derive every claim that leans on this bound"
        )
        assert not mispredicted, (
            f"the host-side model of the frozen chooser is WRONG under the {label} u_bar: "
            f"(p1, predicted, actual) = {mispredicted[:5]} (binary sha256={sha}). Everything "
            "the offline report derives from the declared table (respond thresholds, the "
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
