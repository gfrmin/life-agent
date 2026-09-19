"""The decision: the Bayes act over the candidate posterior (CLAUDE.md rule 2).

One function ranks every action the system can take, :func:`bayes_act`, and nothing else
does. It reads the posterior through one number, ``p1`` = P(asserting now would be correct)
= the credence of the MAP candidate (:func:`p_correct`), and the owner's utility through
the declared rows (:func:`utility_by_action`), and returns the action with the highest
expected utility, ties to the first-listed action in :data:`ACTIONS`.

**The rows** (``u(y=0), u(y=1)`` per action; ``y`` = asserting now would be correct):

- ``abstain``: the gauge zero either way;
- ``respond``: ``u_wrong`` / ``u_correct`` — Chow's rule falls out: respond wins over
  abstain only above ``-u_wrong / (u_correct - u_wrong)`` (0.90 at the declared prior
  ``u_wrong = -9``; the LIVE bar moves with the reaction fold, so never quote 0.90 as
  today's value — read :func:`respond_threshold`);
- ``gather`` and ``ask``: information acts, each priced by a **measured recovery rate**
  ``r`` (a gather or an ask ends in a report with probability r, otherwise in a withhold)
  and its own cost. Absent a measurement, ``r`` is the Beta(1, 1) prior mean 0.5 — never
  the perfect-information row, which is an upper bound and overvalued gathering until it
  was measured (0.093 over 2 182 gathers).

The rows are a declared **evidence model** for the information acts, not the preposterior
over the current posterior; that is a door in ``ROADMAP.md``.

``u_wrong``/``lambda_int``/``kappa_att`` are :class:`life_agent.core.utility.UtilityPosterior`
latents; ``u_correct``/``u_abstain`` its gauge constants. The proplang world
(:mod:`life_agent.membrane.world`, deferred off the path) builds its ``said@1`` sentence
from these same rows, so the two never drift.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from life_agent.core import answer_shape as AS

#: The actions, in tie-break order: the first-listed wins an exact tie, so ``abstain`` is
#: the safe default when nothing is better.
ACTIONS: tuple[str, ...] = ("abstain", "gather", "ask", "respond")

#: u_bar keys carrying the measured recovery rates of the two information acts.
RECOVERY_KEY = "gather_recovery"
ASK_RECOVERY_KEY = "ask_recovery"

#: The Beta(1, 1) prior mean an unmeasured recovery rate reads as.
PRIOR_RECOVERY = 0.5


def utility_by_action(u_bar: Mapping[str, float]) -> dict[str, tuple[float, float]]:
    """``{action: (u(y=0), u(y=1))}`` — the one source of the utility numbers (module
    docstring). Every consumer (the act, thresholds, the report's realised loss, the
    deferred engine's sentence) reads them here."""
    u_correct = float(u_bar.get("u_correct", 1.0))
    u_abstain = float(u_bar.get("u_abstain", 0.0))
    u_wrong = float(u_bar.get("u_wrong", -9.0))
    q = abs(float(u_bar.get("lambda_int", 0.1)))
    g = abs(float(u_bar.get("kappa_att", 0.02)))
    r_gather = float(u_bar.get(RECOVERY_KEY, PRIOR_RECOVERY))
    r_ask = float(u_bar.get(ASK_RECOVERY_KEY, PRIOR_RECOVERY))
    return {
        "abstain": (u_abstain, u_abstain),
        "gather": (u_abstain - g, r_gather * u_correct + (1.0 - r_gather) * u_abstain - g),
        "ask": (u_abstain - q, r_ask * u_correct + (1.0 - r_ask) * u_abstain - q),
        "respond": (u_wrong, u_correct),
    }


def eu_by_action(u_bar: Mapping[str, float], p1: float) -> dict[str, float]:
    """``{action: EU}`` at ``p1`` = P(y=1): ``EU = (1-p1)·u(y=0) + p1·u(y=1)``."""
    return {a: (1.0 - p1) * u0 + p1 * u1 for a, (u0, u1) in utility_by_action(u_bar).items()}


def argmax_action(u_bar: Mapping[str, float], p1: float) -> str:
    """The action the rows fire at ``p1``, every row open and unpriced; ties first-listed."""
    return bayes_act(u_bar, p1)


def bayes_act(u_bar: Mapping[str, float], p1: float, *, gather_open: bool = True,
              gather_cost: float = 0.0) -> str:
    """THE decision: the action maximising expected utility at ``p1``. ``gather`` is ranked
    only while an option is open (``gather_open``) and pays the cost of the option that
    would be enacted, in utility units. Ties resolve to the first-listed of
    :data:`ACTIONS`."""
    eus = eu_by_action(u_bar, p1)
    eus["gather"] -= float(gather_cost)
    ranked = [a for a in ACTIONS if a != "gather" or gather_open]
    return max(ranked, key=lambda a: (eus[a], -ACTIONS.index(a)))


def p_correct(credences: Sequence[float]) -> float:
    """P(asserting now would be correct) = the MAP candidate's credence; 0 with none."""
    return max((float(c) for c in credences), default=0.0)


def respond_threshold(u_bar: Mapping[str, float]) -> float | None:
    """The p1 above which ``respond`` STRICTLY wins the whole menu — the live bar.

    Not merely respond-vs-abstain: respond must also outbid the information acts. Each
    row's EU is linear in p1 and respond's slope (``u_correct - u_wrong``) is the steepest
    (``u_wrong < u_abstain``), so respond overtakes each competitor at one crossing and the
    binding bar is the last of them. ``None`` when some row rises at least as fast (a
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
    changes there."""
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
    ``p > R(q)/(VOI(q)+R(q))``; the owner's DECLARED PRIOR (10:1) puts that bar at
    exactly 0.90 — but the LIVE bar moves with the reaction fold and is not 0.90
    (r32 priced it at 0.852 on 2026-08-30, drifting monotonically as abstain-verdicts
    fold; the weekly readout watches it). Measure the current bar with
    ``scripts/bar_audit.py``; never quote 0.90 as today's value.
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


# --- the quantity shape's loss: interval claims (r30b) -----------------------------------
#
# `docs/unification/reports/r30b-interval-claims.md`. A `quantity` question whose evidence
# disperses over near-agreeing numeric candidates has no action in the action set that is
# both honest and useful: every crisp `report_j` is 0-1 wrong, so the argmax correctly
# withholds (r29 measured this — 18 of 19 quantity questions abstain, 8 of 8 computed ones).
# An INTERVAL claim is that missing action. It is not a second decision rule: it is one more
# tabular row over the SAME K+1 atoms, valued through the SAME assert atom, ranked by the
# SAME `optimise` call — the units lever (`shaped_u_bar`) said what an answer is worth for a
# given question; this says what an answer IS.
#
# A crisp `report_j` is NOT the degenerate case of an interval row: a point interval still
# pays the 2/alpha miss term against a NEARBY candidate, where `report_j` pays flat u_wrong.
# The two losses coexist and the engine picks between them. That difference is the lever.

_WINKLER_ALPHA = 0.2      # r21 (frozen): the rendered central level is 80%
_WINKLER_SCALE = 2.0      # r21 (frozen): x = max(0, 1 - W / (SCALE * |gold|))

# The proposal grid's declared bound. Beyond this many DISTINCT numeric candidate values the
# grid is coarsened to evenly spaced order statistics KEEPING BOTH ENDPOINTS — a deterministic,
# posterior-blind coarsening (nothing here may read a credence: selecting the action space by
# the belief is the host argmax §16 forbids). When it binds, every option built off the
# coarsened grid SAYS so and the recorded claim carries it — a bound cap nothing records reads
# as "these were all the proposals there were".
MAX_INTERVAL_VALUES = 8
INTERVAL_PREFIX = "interval_"


def realised_aggregate(lo: float, hi: float, gold_value: float) -> tuple[float, bool]:
    """The r21 pre-registered interval grade: the Winkler score of an asserted central-80%
    interval against a numeric truth, affinely mapped onto the assert atom's p-argument.
    Returns ``(x, excludes_gold)`` — ``excludes_gold`` is the named wrong-commit class
    (categorical, independent of x). A sharp covering interval reads near 1; an interval
    wider than twice the truth reads 0 even when covering; a miss pays in miss distance
    through the ``2/alpha`` term.

    **One home** (r30b · C4): this is both the DECISION-side loss (the interval row's value at
    each atom, below) and the GRADING-side rule (`core.gate` binds this function). A second
    spelling would let the agent be graded on a loss it did not decide under."""
    w = hi - lo
    if gold_value < lo:
        w += (2.0 / _WINKLER_ALPHA) * (lo - gold_value)
    if gold_value > hi:
        w += (2.0 / _WINKLER_ALPHA) * (gold_value - hi)
    if gold_value == 0.0:
        return (1.0 if lo <= 0.0 <= hi and w == 0.0 else 0.0,
                not (lo <= gold_value <= hi))
    x = max(0.0, 1.0 - w / (_WINKLER_SCALE * abs(gold_value)))
    return x, not (lo <= gold_value <= hi)


@dataclass(frozen=True)
class IntervalOption:
    """One priced interval proposal. ``values`` is the tabular utility row over the K+1 atoms
    (K candidates then NONE) the engine ranks; ``lo_label``/``hi_label`` are the ORIGINAL
    candidate display strings at the endpoints, so a render never reformats a value into
    invented precision or a currency the corpus did not carry."""

    name: str
    lo: float
    hi: float
    lo_label: str
    hi_label: str
    values: tuple[float, ...]
    grid_coarsened: bool = False

    def claim(self) -> dict[str, Any]:
        """The claim itself, in the r21 `aggregate.totals` shape the frozen grader reads.
        ``point`` is the interval's midpoint — a record/display field, never a decision input;
        ``grid_coarsened`` says whether the proposal cap bound (never silent)."""
        return {"lo": self.lo, "hi": self.hi, "point": (self.lo + self.hi) / 2.0,
                "grid_coarsened": self.grid_coarsened}


def _grid(values: list[float]) -> list[float]:
    """The proposal grid over the sorted distinct numeric values — the whole set, or a
    deterministic evenly-spaced coarsening keeping both endpoints when it exceeds the cap."""
    m = len(values)
    if m <= MAX_INTERVAL_VALUES:
        return values
    last = m - 1
    idx = sorted({round(i * last / (MAX_INTERVAL_VALUES - 1))
                  for i in range(MAX_INTERVAL_VALUES)})
    return [values[i] for i in idx]


def interval_options(candidates: Sequence[str], u_bar: Mapping[str, float], *,
                     shape: str) -> tuple[IntervalOption, ...]:
    """The interval rows for one question's candidate set — the ONE construction, bound by
    both decide surfaces (r30b · C3: the in-process family and the daemon wire's
    ``extra_actions``; the daemon supplies no utility arithmetic of its own).

    Empty — so the action set is byte-identical to pre-r30b — unless the question's answer
    shape is ``quantity`` AND at least two DISTINCT candidate values parse numeric (r30b · C2).
    Proposals are the non-degenerate contiguous ranges over the sorted distinct values
    (``[v_a, v_b]`` for ``a < b``); the degenerate range is ``report_j``'s claim and pricing
    one claim under two losses would confound the reading.

    Each row is ``report_j``'s shape generalised: ``u_assert(x_j)`` at candidate j, where
    ``x_j`` is this interval's Winkler grade against candidate j's value; ``u_wrong`` at a
    non-numeric candidate (the claim is about a quantity — a non-numeric truth makes it simply
    wrong) and at NONE. Width is paid for INSIDE ``x`` — there is no external width penalty,
    and adding one would be a second rule (r30b · C1)."""
    if shape != AS.QUANTITY:
        return ()
    parsed = [AS.numeric_value(c) for c in candidates]
    label_of: dict[float, str] = {}
    for value, cand in zip(parsed, candidates, strict=True):
        if value is not None:
            label_of.setdefault(value, str(cand))
    if len(label_of) < 2:
        return ()
    values_sorted = sorted(label_of)
    grid = _grid(values_sorted)
    coarsened = len(grid) < len(values_sorted)
    u_wrong = u_assert(0.0, u_bar)
    out: list[IntervalOption] = []
    for a in range(len(grid)):
        for b in range(a + 1, len(grid)):
            lo, hi = grid[a], grid[b]
            values = (*(u_assert(realised_aggregate(lo, hi, g)[0], u_bar)
                        if g is not None else u_wrong
                        for g in parsed), u_wrong)
            out.append(IntervalOption(name=f"{INTERVAL_PREFIX}{a}_{b}", lo=lo, hi=hi,
                                      lo_label=label_of[lo], hi_label=label_of[hi],
                                      values=values, grid_coarsened=coarsened))
    return tuple(out)


def interval_by_name(options: Sequence[IntervalOption],
                     action: object) -> IntervalOption | None:
    """The chosen action key → its claim, or None when the winner was not an interval. The
    ONE mapping from a wire/engine action name back to the interval it names — both lanes
    use it, so a winning ``interval_a_b`` becomes the same ``report`` + claim either way."""
    if not isinstance(action, str) or not action.startswith(INTERVAL_PREFIX):
        return None
    for o in options:
        if o.name == action:
            return o
    raise ValueError(f"unknown interval action {action!r} "
                     f"(priced: {[o.name for o in options]})")
