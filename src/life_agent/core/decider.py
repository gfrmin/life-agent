"""decider.py — the one place life-agent's actions are chosen (CLAUDE.md rule 2).

The bridge answers ``POST /decide`` through :func:`decide`:

    request → candidate posterior (core/posterior) → p1 = the MAP credence
            → the best gather option (core/decide.best_gather, over the request's menu)
            → the Bayes act (core/decide.bayes_act) → enactment (core/enact) → the view

Nothing here learns: the posterior is calibrated where the evidence is shaped (reliability
folded from outcomes), the utility where the owner's reactions are folded, and the act is
their expected-utility maximum. proplang, as an engine for the act, is a door after the MVP
(``ROADMAP.md``; :mod:`life_agent.membrane` is kept green for it).
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
    ``p1`` (P(asserting now would be correct) = the MAP credence) and ``eu`` (the chosen
    row's expected utility at that p1 — for a gather, the chosen option's, net of its
    price)."""
    candidates = list(payload.get("candidates") or [])
    credences, p_none = POST.candidate_posterior(
        len(candidates), list(payload.get("observations") or []), float(payload["rho"]))
    p1 = DEC.p_correct(credences)
    step = len(payload.get("applied_probes") or [])
    choice = DEC.best_gather(u_bar, p1, step, EN.gather_options(dict(payload)))
    stepped = GR.at_step(u_bar, step)
    act = DEC.bayes_act(stepped, p1, gather_open=choice is not None,
                        gather_eu=choice[1] if choice else None)
    view = EN.enact(act, dict(payload), credences, p_none,
                    probe=choice[0] if choice else None)
    eu = choice[1] if act == "gather" and choice else DEC.eu_by_action(stepped, p1)[act]
    return {**view, "act": act, "p1": p1, "eu": eu}


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
