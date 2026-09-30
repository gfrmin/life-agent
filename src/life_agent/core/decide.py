"""The decision: the Bayes act over the candidate posterior (CLAUDE.md rule 2).

One function ranks every choice the system can make, :func:`bayes_act`, and nothing else
does. Every choice is a row: one ``abstain``, one ``gather`` per open probe, one ``ask``,
one ``cite`` per document, one ``respond`` per candidate (:func:`options`). It reads the
posterior through the candidate credences and the owner's utility through the declared rows
(:func:`utility_by_action`), and returns the :class:`Option` with the highest expected
utility, ties to the first-listed option (the order is :func:`options`'s contract).

**The rows** (``u(y=0), u(y=1)`` per action; ``y`` = asserting now would be correct):

- ``abstain``: the gauge zero either way;
- ``respond``: ``u_wrong`` / ``u_correct`` — Chow's rule falls out: respond wins over
  abstain only above ``-u_wrong / (u_correct - u_wrong)`` (0.90 at the declared prior
  ``u_wrong = -9``; the LIVE bar moves with the reaction fold, so never quote 0.90 as
  today's value — read :func:`respond_threshold`);
- ``gather``: the measured value of gathering on (:mod:`life_agent.core.gather_row`): per
  leader state ``y``, the fitted chances that the question ends in a correct report, a
  wrong one, or a withhold, priced at the owner's utilities, less the attention cost
  ``kappa_att``. The decider sets the row for the number of gathers already applied.
  Unmeasured, both states read the Dirichlet prior mean (1/3 each), under which gathering
  is not worth its cost. The measured row is shared by every probe, evaluated at ``p1`` =
  P(asserting now would be correct) = the MAP credence (:func:`p_correct`); each probe's
  option differs from the others only by its price;
- ``ask``: priced by a **measured recovery rate** ``r`` (an ask ends in a report with
  probability r, otherwise in a withhold) less ``lambda_int``; unmeasured, ``r`` is the
  Beta(1, 1) mean 0.5. Never the perfect-information row, which is an upper bound;
- ``cite``: name the DOCUMENT believed to hold the answer without asserting the value.
  ``u_cite_wrong`` / ``u_cite_right`` (declared latents, defaulting to
  :data:`CITE_WRONG_DEFAULT` / :data:`CITE_RIGHT_DEFAULT`) price it, and each document's
  row is evaluated at its OWN chance of holding the answer, P(g) = the summed credence of
  the candidates that document's observations report (:func:`options`). The consumers
  that read the rows at a single ``p1`` (:func:`respond_threshold`,
  :func:`argmax_crossings`) evaluate cite at P(g) = ``p1`` — the leader's credence, a
  lower bound on the best document's P(g) — so a bar they derive is a LOWER bound on the
  bar the decider applies.

The information rows are **measured evidence models**, not the preposterior over the current
posterior; that is a door in ``ROADMAP.md``.

**The route state** (:func:`route_options`) is the choice made before any retrieval: whether
to attempt the question at all. Its rows are ``abstain`` and ``attempt``. The router's
verdict is an OBSERVATION of the answer type: a question it rejects (a list, an aggregate, a
summary, several values at once) has, if the router is right, no single-span answer, so it
lies outside the hypothesis space (candidate spans, or NONE) and attempting it cannot end
right. The only uncertainty is whether the router is right: ``q`` = P(single-span answer |
verdict), one measured number per verdict. ``attempt`` is worth ``q·V_lookup + (1 - q)·V_other
- price`` (:mod:`life_agent.core.route_row`).

``u_wrong``/``lambda_int``/``kappa_att`` are :class:`life_agent.core.utility.UtilityPosterior`
latents; ``u_correct``/``u_abstain`` its gauge constants.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from life_agent.core import gather_row as GR
from life_agent.core import pricing as PRC
from life_agent.core import route_row as RR

#: The actions, in tie-break order: the first-listed wins an exact tie, so ``abstain`` is
#: the safe default when nothing is better, and ``cite`` precedes ``respond`` (a tie goes to
#: the cheaper claim).
ACTIONS: tuple[str, ...] = ("abstain", "gather", "ask", "cite", "respond")

#: The route state's actions, in tie-break order: declining wins an exact tie.
ROUTE_ACTIONS: tuple[str, ...] = ("abstain", "attempt")

#: The u_bar key carrying the ask's measured recovery rate.
ASK_RECOVERY_KEY = "ask_recovery"

#: The Beta(1, 1) prior mean an unmeasured recovery rate reads as (core/pricing.py).
PRIOR_RECOVERY = PRC.PRIOR_RECOVERY

#: The prior means an undeclared ``u_cite_right`` / ``u_cite_wrong`` read as: a right pointer
#: is half a right answer, a wrong one costs one read.
CITE_RIGHT_DEFAULT = 0.5
CITE_WRONG_DEFAULT = -1.0


def utility_by_action(u_bar: Mapping[str, float]) -> dict[str, tuple[float, float]]:
    """``{action: (u(y=0), u(y=1))}`` — the one source of the utility numbers (module
    docstring). Every consumer (the act, thresholds, the report's realised loss, the
    deferred engine's sentence) reads them here."""
    u_correct = float(u_bar.get("u_correct", 1.0))
    u_abstain = float(u_bar.get("u_abstain", 0.0))
    u_wrong = float(u_bar.get("u_wrong", -9.0))
    q = abs(float(u_bar.get("lambda_int", 0.1)))
    g = abs(float(u_bar.get("kappa_att", 0.02)))
    r_ask = float(u_bar.get(ASK_RECOVERY_KEY, PRIOR_RECOVERY))
    gr = {k: float(u_bar.get(k, GR.PRIOR[k])) for k in GR.KEYS}
    cite_right = float(u_bar.get("u_cite_right", CITE_RIGHT_DEFAULT))
    cite_wrong = float(u_bar.get("u_cite_wrong", CITE_WRONG_DEFAULT))

    def gathered(p_right: float, p_wrong: float) -> float:
        return (p_right * u_correct + p_wrong * u_wrong
                + (1.0 - p_right - p_wrong) * u_abstain - g)

    return {
        "abstain": (u_abstain, u_abstain),
        "gather": (gathered(gr["gather_right_if_wrong"], gr["gather_wrong_if_wrong"]),
                   gathered(gr["gather_right_if_right"], gr["gather_wrong_if_right"])),
        "ask": (u_abstain - q, r_ask * u_correct + (1.0 - r_ask) * u_abstain - q),
        "cite": (cite_wrong, cite_right),
        "respond": (u_wrong, u_correct),
    }


def eu_by_action(u_bar: Mapping[str, float], p1: float) -> dict[str, float]:
    """``{action: EU}`` at ``p1`` = P(y=1): ``EU = (1-p1)·u(y=0) + p1·u(y=1)``."""
    return {a: (1.0 - p1) * u0 + p1 * u1 for a, (u0, u1) in utility_by_action(u_bar).items()}


@dataclass(frozen=True)
class Option:
    """One row of the argmax: the ``action``, what it is aimed at (``target``: the candidate
    index for ``respond``, the document group for ``cite``, the probe name for ``gather``,
    ``None`` otherwise) and its expected utility."""
    action: str
    target: int | str | None
    eu: float


def p_document(credences: Sequence[float], candidates: Sequence[int]) -> float:
    """P(a document holds the answer) = the summed credence of the candidate indices its
    observations report (the candidates are distinct, so the credences add)."""
    return sum(float(credences[j]) for j in candidates if 0 <= j < len(credences))


def options(u_bar: Mapping[str, float], credences: Sequence[float],
            gathers: Sequence[tuple[str, float]] = (),
            groups: Sequence[tuple[int, Sequence[int]]] = ()) -> list[Option]:
    """Every choice as a row, in tie-break order: ``abstain``, the gather options in the
    order given (``gathers`` = ``(probe, cost)`` pairs; each is the gather row at ``p1``
    less its cost), ``ask``, one ``cite`` per document in the order given (``groups`` =
    ``(group, candidate indices)`` pairs, each at its own :func:`p_document`), then one
    ``respond`` per candidate by index at that candidate's own credence. ``gather`` and
    ``ask`` are evaluated at ``p1`` = :func:`p_correct`."""
    eus = eu_by_action(u_bar, p_correct(credences))
    pairs = utility_by_action(u_bar)
    c0, c1 = pairs["cite"]
    u0, u1 = pairs["respond"]
    return [Option("abstain", None, eus["abstain"]),
            *(Option("gather", probe, eus["gather"] - float(cost)) for probe, cost in gathers),
            Option("ask", None, eus["ask"]),
            *(Option("cite", g, (1.0 - p) * c0 + p * c1)
              for g, reported in groups for p in [p_document(credences, reported)]),
            *(Option("respond", j, (1.0 - float(c)) * u0 + float(c) * u1)
              for j, c in enumerate(credences))]


def choose(rows: Sequence[Option]) -> Option:
    """THE argmax: the :class:`Option` of highest expected utility among ``rows``, an exact
    tie going to the first-listed. Every stage's rows are ranked here and nowhere else."""
    return max(rows, key=lambda o: o.eu)


def bayes_act(u_bar: Mapping[str, float], credences: Sequence[float],
              gathers: Sequence[tuple[str, float]] = (),
              groups: Sequence[tuple[int, Sequence[int]]] = ()) -> Option:
    """THE decision over the candidate posterior: :func:`choose` over :func:`options`."""
    return choose(options(u_bar, credences, gathers, groups))


def route_options(u_bar: Mapping[str, float], lookup: bool) -> list[Option]:
    """The pre-retrieval state as rows, in tie-break order: ``abstain`` (``u_abstain``), then
    ``attempt`` at ``q·V_lookup + (1 - q)·V_other - price``, where, all read from ``u_bar``
    (:mod:`life_agent.core.route_row`):

    - ``q`` is P(the question has a single-span answer | the router's verdict ``lookup``);
    - ``V_lookup = r·u_correct + w·u_wrong + (1 - r - w)·u_abstain``, the value of attempting
      a real lookup at the measured right / wrong rates ``r``, ``w``;
    - ``V_other = w_o·u_wrong + (1 - w_o)·u_abstain``: a question whose answer is not a span
      is never answered right;
    - ``price`` is the first pass's price in utility (unpriced, 0).
    """
    u_correct = float(u_bar.get("u_correct", 1.0))
    u_abstain = float(u_bar.get("u_abstain", 0.0))
    u_wrong = float(u_bar.get("u_wrong", -9.0))
    row = {k: float(u_bar.get(k, RR.PRIOR[k])) for k in RR.PRIOR}
    right, wrong = row[RR.RIGHT_KEY], row[RR.WRONG_KEY]
    q = row[RR.q_key(lookup)]
    v_lookup = right * u_correct + wrong * u_wrong + (1.0 - right - wrong) * u_abstain
    v_other = row[RR.WRONG_OTHER_KEY] * u_wrong + (1.0 - row[RR.WRONG_OTHER_KEY]) * u_abstain
    price = float(u_bar.get(RR.PRICE_KEY, 0.0))
    return [Option("abstain", None, u_abstain),
            Option("attempt", None, q * v_lookup + (1.0 - q) * v_other - price)]


def argmax_action(u_bar: Mapping[str, float], p1: float) -> str:
    """The action the rows fire at ``p1``, every row open and unpriced, one document holding
    the lone candidate; ties first-listed."""
    return bayes_act(u_bar, [p1], [("", 0.0)], [(0, [0])]).action


def p_correct(credences: Sequence[float]) -> float:
    """P(asserting now would be correct) = the MAP candidate's credence; 0 with none."""
    return max((float(c) for c in credences), default=0.0)


def respond_threshold(u_bar: Mapping[str, float]) -> float | None:
    """The p1 above which ``respond`` STRICTLY wins the whole menu — the live bar.

    Not merely respond-vs-abstain: respond must also outbid the information acts. Each
    row's EU is linear in p1 and respond's slope (``u_correct - u_wrong``) is the steepest
    (``u_wrong < u_abstain``), so respond overtakes each competitor at one crossing and the
    binding bar is the last of them. The ``cite`` row is read at P(g) = ``p1`` (its slope,
    ``u_cite_right - u_cite_wrong``, is below respond's), and a document's real P(g) is at
    least ``p1`` when it holds the leader, so this bar is a LOWER bound on the bar the
    decider applies. ``None`` when some row rises at least as fast (a
    degenerate u_bar): a reachability statement, not an error."""
    pairs = utility_by_action(u_bar)
    r0, r1 = pairs["respond"]
    thresholds: list[float] = []
    for action, (a0, a1) in pairs.items():
        if action == "respond":
            continue
        denom = (r1 - r0) - (a1 - a0)
        if denom <= 0:
            return None
        thresholds.append((a0 - r0) / denom)
    return max(thresholds) if thresholds else None


def argmax_crossings(u_bar: Mapping[str, float]) -> list[float]:
    """The p1 values in (0, 1) at which :func:`argmax_action` changes its mind — the
    consumer thresholds, derived from the rows rather than assumed. Every row is linear in
    p1, so a pair crosses at most once; a crossing counts only where the WHOLE argmax
    changes there. The ``cite`` row is read at P(g) = ``p1``, so the crossings are the
    single-``p1`` ones (a lower bound where a document pools several candidates)."""
    rows = list(utility_by_action(u_bar).values())
    out: list[float] = []
    for i, (a0, a1) in enumerate(rows):
        for b0, b1 in rows[i + 1:]:
            denom = (a1 - a0) - (b1 - b0)
            if denom == 0.0:
                continue
            p = (b0 - a0) / denom
            eps = 1e-6
            if not 0.0 + eps < p < 1.0 - eps:
                continue
            if argmax_action(u_bar, p - eps) != argmax_action(u_bar, p + eps):
                out.append(p)
    return sorted(set(out))


def u_assert(p_correct: float, u_bar: Mapping[str, float]) -> float:
    """The atomic correctness utility ``p·u_correct + (1 - p)·u_wrong`` (module docstring):
    the single written source of the assert-vs-wrong trade-off both families derive from.
    ``u_assert(1, Ū) = u_correct`` and ``u_assert(0, Ū) = u_wrong`` by construction."""
    return p_correct * u_bar["u_correct"] + (1.0 - p_correct) * u_bar["u_wrong"]


def break_even(u_bar: Mapping[str, float]) -> float:
    """The respond-vs-abstain break-even credence under ``u_bar`` (Chow's rule, with
    ``u_abstain = 0``): the ``p`` at which :func:`u_assert` crosses zero."""
    at_zero, at_one = u_assert(0.0, u_bar), u_assert(1.0, u_bar)
    span = at_one - at_zero
    if span <= 0.0:
        raise ValueError(
            "degenerate Ū: u_assert does not increase in p "
            f"(u_assert(0)={at_zero!r}, u_assert(1)={at_one!r}), so no break-even exists")
    return -at_zero / span


