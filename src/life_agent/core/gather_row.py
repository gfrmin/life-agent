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

The row is conditioned on the state beyond ``p1`` that decides what another gather can still
find: the number of gathers already applied (``step``, capped at :data:`MAX_STEP`). The fit is
one row per step; :func:`at_step` selects the row for a decision. The episodes are the
recorded decides that chose ``gather`` (``scripts/fit_gather_row.py`` builds them from the
m5-base A-loop fixtures, graded by exact match against the gold): the value of gathering on
from a state under the policy that recorded it. A measured evidence model, not the
preposterior over the current posterior (a door in ``ROADMAP.md``); steps of one question are
not independent draws.
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

#: Steps at or beyond this share one row.
MAX_STEP = 3


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


def step_key(key: str, step: int) -> str:
    return f"{key}@{step}"


def load(path: Path) -> dict[str, float]:
    """The per-step fitted rows recorded at ``path`` as u_bar keys (``<key>@<step>``), or none
    when there is no fit (the decider then reads the prior)."""
    if not path.is_file():
        return {}
    steps = json.loads(path.read_text(encoding="utf-8"))["steps"]
    return {step_key(k, int(st)): float(row[k]) for st, row in steps.items() for k in KEYS}


def at_step(u_bar: Mapping[str, float], applied: int) -> dict[str, float]:
    """``u_bar`` with the gather row of the fitted step for ``applied`` gathers (the largest
    fitted step not above ``min(applied, MAX_STEP)``); unchanged when nothing is fitted."""
    out = dict(u_bar)
    for st in range(min(applied, MAX_STEP), -1, -1):
        if all(step_key(k, st) in u_bar for k in KEYS):
            out.update({k: float(u_bar[step_key(k, st)]) for k in KEYS})
            break
    return out
