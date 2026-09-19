"""The routing objective: the oracle is an ACTION, not an opponent.

Every arm-vs-arm reading to date (r6..r50) asks *should typed replace the baseline*.
That is an adoption question about two whole systems. The deployed question is
per-question and different: *for THIS question, do I answer, or do I pay the oracle?*
Under that objective pi* stops being a competitor and becomes a priced affordance,
and the 41 withholdings of run 18 stop being losses — each is a routing decision the
system got as far as making and then had nowhere to send.

Two consequences, both mechanical:

1. **The escalate row is `ask_clarify` with a different oracle.** `action_utilities`
   already prices a consultation: ``_ORACLE_P * u_correct - lambda_int`` (owner-as-
   oracle). An LLM oracle is the same row with the owner's reliability replaced by the
   baseline's MEASURED accuracy and the interruption price replaced by
   ``lambda_usd * cost``. No new decision rule, no daemon change — one more row over
   the same K+1 simplex, exactly as r30b added intervals.

2. **Under the current gauge the system is right to never escalate.** With the
   published u_wrong = -8.9993, lambda_usd = 1.3311 and the baseline's 95/101 realised
   accuracy at $0.3751/q, EU(escalate) = -0.093 against EU(abstain) = 0. Silence
   dominates consulting a 94%-accurate oracle. :func:`breakeven_u_wrong` and
   :func:`breakeven_lambda_usd` locate the two thresholds that flip it (-7.43 and
   1.082 respectively) — both within ~20% of the values in use, and both
   ASSERTED rather than elicited. That is the finding this module exists to make
   checkable, not a claim it assumes.

Nothing here reads a credence or re-grades an answer. :func:`route` is a pure
recombination of a `PairedOutcome` that already exists in every archived run, so the
router arm can be scored from run-18 artifacts with no new inference and no API spend.

See `docs/GLOSSARY.md` for the vocabulary; DR-ROUTE-1 for why escalation pays both arms.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from life_agent.core import gate as GATE
from life_agent.core.decide import u_assert

__all__ = [
    "ESCALATE", "escalate_eu", "escalate_row", "breakeven_u_wrong",
    "breakeven_lambda_usd", "route", "route_all", "RouterSummary", "summarise",
]

# The action name. Deliberately NOT added to gate.WITHHOLD_ACTIONS here: an escalation
# is not a withholding (it delivers an answer), and quietly widening the gate's action
# partition would silently change every archived reading. Wiring it into the gate is a
# separate, pre-registered step (DR-ROUTE-2).
ESCALATE = "escalate"


# --- the priced action -------------------------------------------------------------

def escalate_eu(u_bar: Mapping[str, float], *, oracle_p: float,
                oracle_cost: float) -> float:
    """EU of handing this question to the oracle: ``u_assert(oracle_p) - lambda_usd*cost``.

    Derived from :func:`life_agent.core.decide.u_assert` — the one written assert-vs-wrong
    atom — so the escalate row cannot drift from the report rows it competes with (C3:
    one declaration, two lanes). ``oracle_p`` is the oracle's MEASURED accuracy on
    delivered answers (pi*: 95/101 = 0.941 at run 18), never a prior guess; passing an
    unmeasured value is how this row becomes a wish.
    """
    if not 0.0 <= oracle_p <= 1.0:
        raise ValueError(f"oracle_p must be a probability, got {oracle_p!r}")
    if oracle_cost < 0.0:
        raise ValueError(f"oracle_cost must be non-negative, got {oracle_cost!r}")
    return u_assert(oracle_p, u_bar) - u_bar["lambda_usd"] * oracle_cost


def escalate_row(u_bar: Mapping[str, float], k: int, *, oracle_p: float,
                 oracle_cost: float) -> list[float]:
    """The escalate row over the K candidates + NONE, flat like ``ask_clarify``.

    Flat because the oracle's accuracy does not depend on which of OUR candidates is
    true — it is not reading our candidate list. That is precisely why escalation can
    rescue a `dispersed` row: it is the only action whose value is independent of the
    posterior that failed to concentrate.
    """
    if k < 0:
        raise ValueError(f"k must be non-negative, got {k!r}")
    return [escalate_eu(u_bar, oracle_p=oracle_p, oracle_cost=oracle_cost)] * (k + 1)


# --- where the gauge flips ---------------------------------------------------------

def breakeven_u_wrong(*, oracle_p: float, lambda_usd: float, oracle_cost: float,
                      u_correct: float = 1.0) -> float:
    """The u_wrong at which EU(escalate) == EU(abstain) == 0.

    Solves ``p*u_correct + (1-p)*u_w - lambda_usd*cost = 0`` for u_w. A u_wrong DEEPER
    (more negative) than this makes silence dominate consulting the oracle on every
    question, whatever the posterior says. At run-18 values this returns -7.43; the
    gauge in use is -8.9993.
    """
    if oracle_p >= 1.0:
        raise ValueError("a perfect oracle has no break-even; u_wrong never binds")
    return (lambda_usd * oracle_cost - oracle_p * u_correct) / (1.0 - oracle_p)


def breakeven_lambda_usd(*, oracle_p: float, u_wrong: float, oracle_cost: float,
                         u_correct: float = 1.0) -> float:
    """The lambda_usd at which EU(escalate) == 0, holding u_wrong fixed.

    The second lever on the same indifference: a HIGHER exchange rate than this makes
    escalation irrational. At run-18 values this returns 1.082; the rate in use is
    1.3311, imputed from token counts under a flat-rate plan (r28 V3).
    """
    if oracle_cost <= 0.0:
        raise ValueError("a free oracle has no break-even exchange rate")
    return u_assert(oracle_p, {"u_correct": u_correct, "u_wrong": u_wrong}) / oracle_cost


# --- the router arm, by recombination ----------------------------------------------

def route(paired: GATE.PairedOutcome) -> GATE.RealisedResponse:
    """The router's realised response on one question: typed when it asserted, else the
    oracle's.

    The policy under test is exactly the one the deployed system already computes — it
    asserts above the bar and withholds below it — with the withholding branch sent to
    the oracle instead of to silence. So this is a recombination, not a simulation: every
    field comes from a response some arm actually produced.

    **Cost is additive (DR-ROUTE-1).** An escalated question paid the typed attempt AND
    the oracle call. Charging only the oracle would flatter the router by the price of
    the retrieval it discarded. Censored rows (the corpus cannot answer) pass through
    untouched so :meth:`PairedOutcome.censored` keeps its meaning.
    """
    if paired.censored():
        return paired.typed
    if paired.typed.action in GATE.ASSERT_ACTIONS:
        return paired.typed
    m = paired.mono
    return GATE.RealisedResponse(
        action=m.action, correct=m.correct,
        cost_usd=paired.typed.cost_usd + m.cost_usd, withheld=m.withheld)


def route_all(rows: Iterable[GATE.PairedOutcome]) -> list[GATE.PairedOutcome]:
    """Every row with the router spliced into the ``typed`` slot, oracle left as ``mono``.

    The result feeds `gate.delta_posterior` unchanged, so the router can be gated against
    the oracle by the same frozen delta and level as any other arm.
    """
    return [GATE.PairedOutcome(question_id=r.question_id, answerable=r.answerable,
                               typed=route(r), mono=r.mono) for r in rows]


@dataclass(frozen=True)
class RouterSummary:
    """One policy's realised contingency over a question set, with spend."""

    n: int
    correct: int
    wrong: int
    withheld: int
    total_cost: float

    @property
    def delivered(self) -> int:
        return self.correct + self.wrong

    @property
    def precision(self) -> float:
        """Correct as a share of DELIVERED answers. Undefined (0.0) on a silent arm."""
        return self.correct / self.delivered if self.delivered else 0.0

    @property
    def mean_cost(self) -> float:
        return self.total_cost / self.n if self.n else 0.0


def summarise(responses: Sequence[GATE.RealisedResponse]) -> RouterSummary:
    """Contingency + spend for one arm. Counts only; no utility, no gauge, no posterior —
    so a reader can check the router's answer count without first accepting u_wrong."""
    correct = sum(1 for r in responses if r.asserts() and r.correct)
    wrong = sum(1 for r in responses if r.asserts() and not r.correct)
    withheld = sum(1 for r in responses if not r.asserts())
    return RouterSummary(n=len(responses), correct=correct, wrong=wrong,
                         withheld=withheld,
                         total_cost=sum(r.cost_usd for r in responses))
