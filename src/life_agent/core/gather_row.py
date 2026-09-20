"""The gather row, measured: what entering the gather sequence is worth from a posterior.

An episode starts at a posterior whose leader is right with probability ``p1`` and, after
gathering, ends ``right`` (a correct report), ``wrong`` (a wrong report) or ``declined``.
:mod:`life_agent.core.outcome_mixture` is the estimator — the two-component mixture over the
leader's truth, fit by EM — and this module is its gather half: the keys, the recorded fit,
and the row for the state a decision is in. The attention cost ``kappa_att`` is the price
:func:`life_agent.core.decide.utility_by_action` passes when it prices these numbers.

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

from life_agent.core import outcome_mixture as MIX

#: This row's prefix in ``u_bar``.
PREFIX = "gather"

OUTCOMES: tuple[str, ...] = MIX.OUTCOMES

#: The u_bar keys of the fitted row (``declined`` is the remainder of each distribution).
KEYS: tuple[str, ...] = MIX.keys(PREFIX)

PRIOR: dict[str, float] = MIX.prior(PREFIX)

#: Steps at or beyond this share one row.
MAX_STEP = 3


def fit(episodes: Sequence[tuple[float, str]], *, alpha: float = 2.0,
        iters: int = 500) -> tuple[dict[str, float], dict[str, float]]:
    """``(θ_right, θ_wrong)`` from ``(p1, outcome)`` episodes (:func:`outcome_mixture.fit`)."""
    return MIX.fit(episodes, alpha=alpha, iters=iters)


def as_u_bar(t_right: Mapping[str, float], t_wrong: Mapping[str, float]) -> dict[str, float]:
    """The fitted row's u_bar keys."""
    return MIX.as_u_bar(PREFIX, t_right, t_wrong)


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
