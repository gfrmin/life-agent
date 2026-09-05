"""r49b / `M-33` — the regime-pairing declaration on a differential reading.

`r49` priced its policy under the deployed `all-to-date` Ū (break-even 0.8369) and scored
it under the gate's blind `frozen-elicitations` Ū (break-even 0.9000). Its whole
differential was 24 marginal commits at 0.875 — *between* the two — so the verdict's sign
was decided by the pairing rather than by the policy, and nothing in the reading said so.

These tests pin the declaration, NOT the resolution: which regime a gate ought to score at
is an open owner question (r49b §5), so the check must stay correct under every answer.
"""
from __future__ import annotations

import pytest

from life_agent.core import gate as G

# The two regimes r49 actually spanned. These are utility POSTERIOR MEANS, which the
# shadow's own record already declares publishable (`shadow._write_boot_record`: "seven
# scalar utility means: no PII, no corpus content") — real numbers, not synthetic, and
# the test is worth less if they are invented.
DEPLOYED = {"u_correct": 1.0, "u_wrong": -5.130990272278651}
BLIND = {"u_correct": 1.0, "u_wrong": -8.9993}


def test_break_even_matches_the_closed_form_for_both_regimes() -> None:
    assert G.break_even(DEPLOYED) == pytest.approx(0.836894, abs=5e-7)
    assert G.break_even(BLIND) == pytest.approx(0.899993, abs=5e-7)


def test_break_even_is_derived_through_decide_u_assert_not_respelled() -> None:
    """`M-7`: the break-even must ride the ONE atomic correctness utility, so a change to
    `decide.u_assert` moves it rather than leaving a second spelling behind."""
    from life_agent.core import decide as D

    for u_bar in (DEPLOYED, BLIND):
        p = G.break_even(u_bar)
        assert D.u_assert(p, u_bar) == pytest.approx(0.0, abs=1e-12)


def test_pairing_is_not_divergent_when_both_regimes_agree() -> None:
    p = G.regime_pairing(pricing_u_bar=DEPLOYED, pricing_policy="all-to-date",
                         scoring_u_bar=DEPLOYED, scoring_policy="all-to-date")
    assert not p.divergent
    assert p.straddles(0.875) is False


def test_pairing_is_divergent_when_the_regimes_differ() -> None:
    p = G.regime_pairing(pricing_u_bar=DEPLOYED, pricing_policy="all-to-date",
                         scoring_u_bar=BLIND, scoring_policy="frozen-elicitations")
    assert p.divergent
    assert p.pricing_break_even == pytest.approx(0.836894, abs=5e-7)
    assert p.scoring_break_even == pytest.approx(0.899993, abs=5e-7)


def test_the_r49_configuration_straddles() -> None:
    p = G.regime_pairing(pricing_u_bar=DEPLOYED, pricing_policy="all-to-date",
                         scoring_u_bar=BLIND, scoring_policy="frozen-elicitations")
    assert p.straddles(0.875) is True


@pytest.mark.parametrize("reach", [0.70, 0.95, None])
def test_reach_outside_the_interval_does_not_straddle(reach: float | None) -> None:
    p = G.regime_pairing(pricing_u_bar=DEPLOYED, pricing_policy="all-to-date",
                         scoring_u_bar=BLIND, scoring_policy="frozen-elicitations")
    assert p.straddles(reach) is False


@pytest.mark.parametrize("endpoint", ["pricing", "scoring"])
def test_reach_exactly_on_an_endpoint_does_not_straddle(endpoint: str) -> None:
    """The EXACT break-even, not a rounded stand-in: at an endpoint the marginal rows are
    worth exactly zero under one regime, so the sign is carried by the rest of the reading."""
    p = G.regime_pairing(pricing_u_bar=DEPLOYED, pricing_policy="all-to-date",
                         scoring_u_bar=BLIND, scoring_policy="frozen-elicitations")
    exact = getattr(p, f"{endpoint}_break_even")
    assert p.straddles(exact) is False


def test_regimes_that_currently_coincide_are_still_declared_divergent() -> None:
    """Two conditioning sets can fold to the same mean and later part again — the deployed
    `all-to-date` bar sat within 0.002 of the blind one in August 2026 and diverged after
    (r49b §4b). Divergence is a property of the DECLARATION, not of today's arithmetic."""
    p = G.regime_pairing(pricing_u_bar=DEPLOYED, pricing_policy="all-to-date",
                         scoring_u_bar=DEPLOYED, scoring_policy="frozen-elicitations")
    assert p.divergent
    assert p.pricing_break_even == p.scoring_break_even


def test_render_declares_both_regimes_and_warns_on_a_straddle() -> None:
    p = G.regime_pairing(pricing_u_bar=DEPLOYED, pricing_policy="all-to-date",
                         scoring_u_bar=BLIND, scoring_policy="frozen-elicitations")
    out = G.render_regime_pairing(p, reach_rate=0.875)
    assert "all-to-date" in out and "frozen-elicitations" in out
    assert "0.8369" in out and "0.9000" in out
    assert "0.875" in out
    assert "pairing-sensitive" in out.lower()


def test_render_is_quiet_when_one_regime_governs() -> None:
    p = G.regime_pairing(pricing_u_bar=DEPLOYED, pricing_policy="all-to-date",
                         scoring_u_bar=DEPLOYED, scoring_policy="all-to-date")
    out = G.render_regime_pairing(p, reach_rate=0.875)
    assert "all-to-date" in out
    assert "pairing-sensitive" not in out.lower()


def test_render_declares_the_divergence_even_without_a_straddle() -> None:
    """A divergent pairing is disclosed whether or not this run's reach straddles —
    the corrected `M-31` requires the two numbers to be published, not merely warned."""
    p = G.regime_pairing(pricing_u_bar=DEPLOYED, pricing_policy="all-to-date",
                         scoring_u_bar=BLIND, scoring_policy="frozen-elicitations")
    out = G.render_regime_pairing(p, reach_rate=0.50)
    assert "0.8369" in out and "0.9000" in out
    assert "pairing-sensitive" not in out.lower()


def test_preflight_render_names_the_interval_that_would_bite() -> None:
    """The pre-run form: reach is unknown, so the block must name the interval to watch —
    this is the disclosure that would have fired BEFORE r49 spent fourteen hours."""
    p = G.regime_pairing(pricing_u_bar=DEPLOYED, pricing_policy="all-to-date",
                         scoring_u_bar=BLIND, scoring_policy="frozen-elicitations")
    out = G.render_regime_pairing(p, reach_rate=None)
    assert "0.8369" in out and "0.9000" in out
    assert "preflight" in out.lower()
    assert "pairing-sensitive" in out.lower()


def test_straddle_is_order_independent() -> None:
    """The pricing bar is not always the lower one: in August 2026 the deployed
    `all-to-date` bar sat at 0.8983, ABOVE some blind readings. The interval is the pair,
    whichever way round it arrives."""
    forward = G.regime_pairing(pricing_u_bar=DEPLOYED, pricing_policy="all-to-date",
                               scoring_u_bar=BLIND, scoring_policy="frozen-elicitations")
    reversed_ = G.regime_pairing(pricing_u_bar=BLIND, pricing_policy="frozen-elicitations",
                                 scoring_u_bar=DEPLOYED, scoring_policy="all-to-date")
    assert forward.straddles(0.875) is True
    assert reversed_.straddles(0.875) is True
