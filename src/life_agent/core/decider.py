"""decider.py — the one place life-agent's actions are chosen (CLAUDE.md rule 2).

The bridge answers ``POST /decide`` through :func:`decide`:

    request → candidate posterior (core/posterior) → p1 = the MAP credence
            → the Bayes act over every option (core/decide.bayes_act)
            → enactment (core/enact) → the view

Nothing here learns: the posterior is calibrated where the evidence is shaped (reliability
folded from outcomes), the utility where the owner's reactions are folded, and the act is
their expected-utility maximum.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from life_agent.core import decide as DEC
from life_agent.core import enact as EN
from life_agent.core import gather_row as GR
from life_agent.core import posterior as POST


def decide(payload: Mapping[str, Any], u_bar: Mapping[str, float]) -> dict[str, Any]:
    """Rank one ``/decide`` request under ``u_bar`` and return the executor's view:
    ``effector``, ``value``, ``probe``, ``credences``, ``p_none``, plus the chosen ``act``,
    ``p1`` (P(asserting now would be correct) = the MAP credence) and ``eu`` (the winning
    option's expected utility, net of the gather's price when gather was chosen)."""
    candidates = list(payload.get("candidates") or [])
    credences, p_none = POST.candidate_posterior(
        len(candidates), list(payload.get("observations") or []), float(payload["rho"]))
    p1 = DEC.p_correct(credences)
    u_bar = GR.at_step(u_bar, len(payload.get("applied_probes") or []))
    option = DEC.bayes_act(u_bar, credences, EN.gather_options(dict(payload)))
    view = EN.enact(option, dict(payload), credences, p_none)
    return {**view, "act": option.action, "p1": p1, "eu": option.eu}


class Decider:
    """The bridge's handle: the current Ū (read per request, so a reaction fold moves the
    next decision) and the status ``/ready`` reports."""

    def __init__(self, u_bar: Callable[[], Mapping[str, float]]) -> None:
        self._u_bar = u_bar

    def decide(self, question_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        del question_id  # recorded by the executor's /log_decision, not needed to rank
        return decide(payload, self._u_bar())

    def status(self) -> dict[str, object]:
        return {"kind": "host"}
