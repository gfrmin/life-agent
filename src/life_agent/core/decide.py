"""The decision-theoretic skeleton shared by every Ask response family - the unifier.

bayesian-foundations §3/§4.4: a response is an expected-utility decision,
``argmax_a E_belief[U(a, outcome)]`` under the one learned utility posterior Ū
(:mod:`life_agent.core.utility`). The two families (:mod:`~life_agent.core.lookup`,
:mod:`~life_agent.core.narrative`) realise *the same rule* over *legitimately different
beliefs*. This module is the one place the shared piece - the atomic correctness utility -
is written, so neither family hand-asserts it (derive, don't assert).

**The atom.** Under the gauge (``u_correct = +1``, ``u_abstain = 0`` -
:data:`life_agent.core.utility.GAUGE`), asserting a claim correct with probability ``p`` is
worth

    u_assert(p, Ū) = p·u_correct + (1 - p)·u_wrong.

**Every family EU derives from it:**

- **lookup** (belief: a categorical posterior over K candidate values + a NONE atom) -
  :func:`life_agent.core.lookup.action_utilities`::

      U(report, atom j) = u_assert(1 if j is MAP else 0)  # crisp report
      U(hedge, NONE)    = u_assert(0)                     # hedge misleads iff NONE
      U(hedge, j!=NONE) = u_hedged                        # named-set value (a latent)
      U(ask_clarify)    = rho·u_correct - lambda_int      # oracle price (NOT u_assert:
                                                          #   infallible when it knows)
      U(abstain)        = u_abstain                       # the gauge zero

- **narrative** (belief: independent per-claim correctness credences) -
  :func:`life_agent.core.narrative.include_eu`::

      EU(include | p) = p·u_assert(p) - kappa_att  # reliance p scales the assert EU,
                                                   #   minus the per-claim attention
      EU(withhold)    = u_abstain = 0              # the gauge zero

**Separability - why narrative's per-claim threshold *is* the argmax, not an ad-hoc rule.**
Narrative chooses a *subset* A of n claims to include. The claims' correctness credences are
independent (independent population/coverage folds - nothing couples them) and the answer
utility is additive over claims, so

    EU(A) = Σ_{i in A} EU(include | p_i) + Σ_{i not in A} u_abstain
          = Σ_{i in A} EU(include | p_i)                 (u_abstain = 0, gauge).

Maximising over all 2**n subsets therefore factorises: include claim i **iff**
``EU(include | p_i) > u_abstain``. The per-claim threshold in
:func:`life_agent.core.narrative.decide_claims` is the *exact* powerset argmax - no
enumeration. (Lookup cannot factorise this way: its atoms are mutually exclusive hypotheses
about one value, with a genuine NONE-mass alternative, so it optimises the whole categorical
through the credence skin.)

**The two beliefs are legitimately different - do not collapse them.** lookup's NONE atom is
a *hypothesis* ("the truth is not among the retrieved candidates"), priced ``u_assert(0)`` =
``u_wrong`` when reported; narrative's withhold sits at the gauge ``u_abstain = 0``. The two
zeros mean different things; one shared utility *atom* does not make one shared belief.
"""
from __future__ import annotations

from collections.abc import Mapping

from life_agent.core import answer_shape as AS


def u_assert(p_correct: float, u_bar: Mapping[str, float]) -> float:
    """The atomic correctness utility ``p·u_correct + (1 - p)·u_wrong`` (module docstring):
    the single written source of the assert-vs-wrong trade-off both families derive from.
    ``u_assert(1, Ū) = u_correct`` and ``u_assert(0, Ū) = u_wrong`` by construction."""
    return p_correct * u_bar["u_correct"] + (1.0 - p_correct) * u_bar["u_wrong"]


def shaped_u_bar(u_bar: Mapping[str, float], shape: str) -> dict[str, float]:
    """Ū scaled for one question's answer shape (r30,
    `docs/unification/reports/r30-units-lever.md` — the direct answer to "how to define
    utilities of answers for given questions": the question determines the loss shape, the
    loss shape determines what an answer is worth).

    ``answer_shape.ANCHOR_SHAPE`` (``exact``) is the ANCHOR: ``u_correct``/``u_wrong`` pass
    through unscaled — today's §4.4 gauge convention, unchanged. Each other declared shape
    (``answer_shape.SCALED_SHAPES``) carries a ``voi_scale_<shape>`` (multiplies
    ``u_correct``) and a ``regret_scale_<shape>`` (multiplies ``u_wrong``), read from Ū when
    the owner's model.yaml has opted the shape in and **defaulting to 1.0 — the anchor's own
    value — when it has not** (so a u_bar carrying none of the six optional latents is
    unchanged for every shape; C4). This is the ONLY place a scale applies — every
    `current_u_bar` caller routes Ū through this function before pricing an answer (C5); a
    second construction path is a drift-gate failure, not a refinement.

    Chow's rule falls out of this at the `exact` special case: report iff
    ``p > R(q)/(VOI(q)+R(q))``; today's uniform 0.90 bar is that formula with
    VOI≡1/R≡const held constant across every question.
    """
    if shape not in AS.SHAPES:
        raise ValueError(f"unknown answer shape {shape!r} (declared: {sorted(AS.SHAPES)})")
    out = dict(u_bar)
    if shape == AS.ANCHOR_SHAPE:
        return out
    voi = float(u_bar.get(f"voi_scale_{shape}", 1.0))
    regret = float(u_bar.get(f"regret_scale_{shape}", 1.0))
    out["u_correct"] = u_bar["u_correct"] * voi
    out["u_wrong"] = u_bar["u_wrong"] * regret
    return out
