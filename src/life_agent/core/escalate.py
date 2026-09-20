"""The escalation rungs as rows: hand the question to a named outside answerer.

A rung answers the question itself and the reply says so (origin, rung, what was disclosed).
It is a row like any other, so the act reaches it on value: what a rung is worth is the
:mod:`life_agent.core.outcome_mixture` row fitted from that rung's own recorded verdicts —
per leader state, the chances the rung ends right, wrong or declined — less its price
(:data:`life_agent.core.pricing.ESCALATE_RUNGS`, USD, converted at ``lambda_usd``).

The fit is recorded at ``$LIFE_AGENT_KB/calibration/escalate_row.json`` by
``scripts/fit_escalate_row.py``. A rung with no fit reads the mixture prior (1/3 each),
under which escalating never pays, so a declared rung cannot spend before it is measured.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from life_agent.core import outcome_mixture as MIX
from life_agent.core import pricing as PRC

#: The declared rungs, in the order the act lists them.
RUNGS: tuple[str, ...] = tuple(str(r["rung"]) for r in PRC.ESCALATE_RUNGS)

#: The price of each rung in USD, as declared.
PRICE_USD: dict[str, float] = {str(r["rung"]): float(r["cost"]) for r in PRC.ESCALATE_RUNGS}


def action(rung: str) -> str:
    """The action name (and u_bar prefix) of a rung: ``escalate@<rung>``."""
    return f"escalate@{rung}"


#: The rung actions, in declaration order.
ACTIONS: tuple[str, ...] = tuple(action(r) for r in RUNGS)


def rung_of(act: str) -> str | None:
    """The rung an action names, or ``None`` when it is not an escalation."""
    return act.split("@", 1)[1] if act in ACTIONS else None


def price(rung: str, u_bar: Mapping[str, float]) -> float:
    """A rung's price in utility units: its declared USD at the owner's ``lambda_usd``."""
    return PRICE_USD[rung] * abs(float(u_bar.get("lambda_usd", 1.0)))


def load(path: Path) -> dict[str, float]:
    """The fitted rung rows recorded at ``path`` as u_bar keys, or none when there is no
    fit (the act then reads the prior and never escalates)."""
    if not path.is_file():
        return {}
    recorded = json.loads(path.read_text(encoding="utf-8"))["rungs"]
    return {k: float(v) for rung, row in recorded.items()
            for k, v in row.items() if k in MIX.keys(action(rung))}
