"""The one estimator behind every measured action row (gather, escalate).

An episode is a posterior whose leader is right with probability ``p1``, an action taken
from it, and how the question then ended: ``right`` (a correct report), ``wrong`` (a wrong
one) or ``declined``. What the action is worth depends on whether the leader was right, so
each episode is a two-component mixture: with probability ``p1`` the outcome is drawn from
``θ_right``, otherwise from ``θ_wrong``. :func:`fit` estimates both by EM as the posterior
mode under a Dirichlet(alpha) prior on each — one pseudo-observation per outcome at the
default, so no outcome is ever priced as impossible and a handful of episodes cannot declare
certainty.

:func:`as_u_bar` names the four free numbers (``declined`` is each distribution's remainder)
under a caller's prefix, and :func:`row` prices them into the ``(u(y=0), u(y=1))`` pair
:func:`life_agent.core.decide.utility_by_action` ranks, linear in ``p1`` like every other
row. Unmeasured, both distributions are the prior mean (1/3 each), under which the action is
not worth its cost.

**What the mixture can and cannot see.** The weight is ``p1``, so the fit needs episodes
whose outcome varies with the leader's truth. Where an action's outcome barely moves with
``p1`` the two components are weakly identified and the fit leans on the prior; the caller
that records the episodes owns that judgement and states it (see ``scripts/fit_*_row.py``).
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence

OUTCOMES: tuple[str, ...] = ("right", "wrong", "declined")


def keys(prefix: str) -> tuple[str, ...]:
    """The four u_bar keys of ``prefix``'s row."""
    return (f"{prefix}_right_if_right", f"{prefix}_wrong_if_right",
            f"{prefix}_right_if_wrong", f"{prefix}_wrong_if_wrong")


def prior(prefix: str) -> dict[str, float]:
    """The row an unmeasured action reads: the Dirichlet prior mean."""
    return {k: 1.0 / len(OUTCOMES) for k in keys(prefix)}


def fit(episodes: Sequence[tuple[float, str]], *, alpha: float = 2.0,
        iters: int = 500) -> tuple[dict[str, float], dict[str, float]]:
    """``(θ_right, θ_wrong)`` from ``(p1, outcome)`` episodes: the EM posterior mode under a
    Dirichlet(alpha) prior on each component."""
    t_r = {o: 1.0 / len(OUTCOMES) for o in OUTCOMES}
    t_w = dict(t_r)
    for _ in range(iters):
        c_r = {o: alpha - 1.0 for o in OUTCOMES}
        c_w = dict(c_r)
        for p1, o in episodes:
            a, b = p1 * t_r[o], (1.0 - p1) * t_w[o]
            w = a / (a + b) if a + b > 0 else p1
            c_r[o] += w
            c_w[o] += 1.0 - w
        t_r = _normalised(c_r)
        t_w = _normalised(c_w)
    return t_r, t_w


def _normalised(c: Mapping[str, float]) -> dict[str, float]:
    s = sum(c.values())
    return ({o: c[o] / s for o in OUTCOMES} if s > 0
            else {o: 1.0 / len(OUTCOMES) for o in OUTCOMES})


def as_u_bar(prefix: str, t_right: Mapping[str, float],
             t_wrong: Mapping[str, float]) -> dict[str, float]:
    """The fitted row's u_bar keys under ``prefix``."""
    a, b, c, d = keys(prefix)
    return {a: t_right["right"], b: t_right["wrong"],
            c: t_wrong["right"], d: t_wrong["wrong"]}


def row(u_bar: Mapping[str, float], prefix: str, *, u_correct: float, u_wrong: float,
        u_abstain: float, cost: float) -> tuple[float, float]:
    """``(u(y=0), u(y=1))`` for ``prefix``'s action at ``cost`` (in utility units): the
    fitted chances of ending right, wrong or withheld per leader state, priced at the
    owner's utilities. Every measured row is priced HERE, so two of them cannot drift."""
    a, b, c, d = keys(prefix)
    p = {k: float(u_bar.get(k, 1.0 / len(OUTCOMES))) for k in (a, b, c, d)}

    def priced(p_right: float, p_wrong: float) -> float:
        return (p_right * u_correct + p_wrong * u_wrong
                + (1.0 - p_right - p_wrong) * u_abstain - cost)

    return priced(p[c], p[d]), priced(p[a], p[b])
