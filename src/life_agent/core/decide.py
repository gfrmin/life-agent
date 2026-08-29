"""The decision-theoretic skeleton shared by every Ask response family - the unifier.

bayesian-foundations §3/§4.4: a response is an expected-utility decision,
``argmax_a E_belief[U(a, outcome)]`` under the one learned utility posterior Ū
(:mod:`life_agent.core.utility`). The two families (:mod:`~life_agent.core.lookup`,
:mod:`~life_agent.core.narrative`) realise *the same rule* over *legitimately different
beliefs*. This module is the one place the shared piece - the atomic correctness utility -
is written, so neither family hand-asserts it (derive, don't assert).

**The atom.** Under the gauge (``u_correct = +1``, ``u_abstain = 0`` -
:data:`life_agent.core.utility.GAUGE`), asserting a claim correct with probability ``p`` is
worth

    u_assert(p, Ū) = p·u_correct + (1 - p)·u_wrong.

**Every family EU derives from it:**

- **lookup** (belief: a categorical posterior over K candidate values + a NONE atom) -
  :func:`life_agent.core.lookup.action_utilities`::

      U(report, atom j) = u_assert(1 if j is MAP else 0)  # crisp report
      U(hedge, NONE)    = u_assert(0)                     # hedge misleads iff NONE
      U(hedge, j!=NONE) = u_hedged                        # named-set value (a latent)
      U(ask_clarify)    = rho·u_correct - lambda_int      # oracle price (NOT u_assert:
                                                          #   infallible when it knows)
      U(abstain)        = u_abstain                       # the gauge zero

- **narrative** (belief: independent per-claim correctness credences) -
  :func:`life_agent.core.narrative.include_eu`::

      EU(include | p) = p·u_assert(p) - kappa_att  # reliance p scales the assert EU,
                                                   #   minus the per-claim attention
      EU(withhold)    = u_abstain = 0              # the gauge zero

**Separability - why narrative's per-claim threshold *is* the argmax, not an ad-hoc rule.**
Narrative chooses a *subset* A of n claims to include. The claims' correctness credences are
independent (independent population/coverage folds - nothing couples them) and the answer
utility is additive over claims, so

    EU(A) = Σ_{i in A} EU(include | p_i) + Σ_{i not in A} u_abstain
          = Σ_{i in A} EU(include | p_i)                 (u_abstain = 0, gauge).

Maximising over all 2**n subsets therefore factorises: include claim i **iff**
``EU(include | p_i) > u_abstain``. The per-claim threshold in
:func:`life_agent.core.narrative.decide_claims` is the *exact* powerset argmax - no
enumeration. (Lookup cannot factorise this way: its atoms are mutually exclusive hypotheses
about one value, with a genuine NONE-mass alternative, so it optimises the whole categorical
through the credence skin.)

**The two beliefs are legitimately different - do not collapse them.** lookup's NONE atom is
a *hypothesis* ("the truth is not among the retrieved candidates"), priced ``u_assert(0)`` =
``u_wrong`` when reported; narrative's withhold sits at the gauge ``u_abstain = 0``. The two
zeros mean different things; one shared utility *atom* does not make one shared belief.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from life_agent.core import answer_shape as AS


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
    ``p > R(q)/(VOI(q)+R(q))``; today's uniform 0.90 bar is that formula with
    VOI≡1/R≡const held constant across every question.
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
