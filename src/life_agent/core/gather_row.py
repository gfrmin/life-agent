"""The gather row, measured: what entering the gather sequence is worth from a posterior.

An episode starts at a posterior whose leader is right with probability ``p1`` and, after
gathering, ends ``right`` (a correct report), ``wrong`` (a wrong report) or ``declined``. The
outcome depends on whether the leader was right, so each episode is a two-component mixture:
with probability ``p1`` it is drawn from ``θ_right`` (the outcome distribution when the
leader is right), otherwise from ``θ_wrong``. :func:`fit` estimates both by EM as the
posterior mode under a Dirichlet(2, 2, 2) prior on each (one pseudo-observation per outcome,
so no outcome is ever priced as impossible). :func:`as_u_bar` carries the four free numbers
into ``u_bar`` so :func:`life_agent.core.decide.utility_by_action` prices the gather row as

    u(y) = θ_y(right)·u_correct + θ_y(wrong)·u_wrong + θ_y(declined)·u_abstain - κ

linear in ``p1`` like every other row. Unmeasured, both distributions are the prior mean
(1/3 each), under which gathering is not worth its cost.

The episodes are recorded decision sequences (``scripts/fit_gather_row.py`` builds them
from the m5-base A-loop fixtures, graded by exact match against the gold). The fit is the
value of the whole sequence under the policy that recorded it, applied at every step: a
measured evidence model, not the preposterior over the current posterior (a door in
``ROADMAP.md``).
"""
from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path

OUTCOMES: tuple[str, ...] = ("right", "wrong", "declined")

#: The u_bar keys of the fitted row (``declined`` is the remainder of each distribution).
KEYS: tuple[str, ...] = ("gather_right_if_right", "gather_wrong_if_right",
                         "gather_right_if_wrong", "gather_wrong_if_wrong")

PRIOR: dict[str, float] = {k: 1.0 / 3.0 for k in KEYS}


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


def as_u_bar(t_right: Mapping[str, float], t_wrong: Mapping[str, float]) -> dict[str, float]:
    """The fitted row's u_bar keys."""
    return {"gather_right_if_right": t_right["right"], "gather_wrong_if_right": t_right["wrong"],
            "gather_right_if_wrong": t_wrong["right"], "gather_wrong_if_wrong": t_wrong["wrong"]}


def load(path: Path) -> dict[str, float]:
    """The fitted row recorded at ``path``, or the prior when there is none."""
    if not path.is_file():
        return dict(PRIOR)
    row = json.loads(path.read_text(encoding="utf-8"))["u_bar"]
    return {k: float(row[k]) for k in KEYS}
