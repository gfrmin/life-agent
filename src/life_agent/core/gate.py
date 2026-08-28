"""The decision-weighted adoption gate — bayesian-foundations §8.

Adoption is an *action*, not a hypothesis test, and the comparison is itself Bayesian:
two corpus-mean EUs are noisy estimates and the corpus is sparsest exactly when the gate
first runs. We hold a posterior over the EU gap ``Δ = EU(typed) - EU(monolithic)`` and
pass iff ``P(Δ > δ) >= level``, integrated over the §4.4 utility posterior ``P(U)``.

Two uncertainties compose, per Monte-Carlo draw:

* **utility uncertainty** — ``U ~ P(U)``, the §4.4 posterior, sampled from its grid
  marginals (the gauge pins ``u_correct=+1``, ``u_abstain=0`` are fixed, having no
  state to sample);
* **finite-corpus uncertainty** — the corpus mean is a noisy estimate of the deployment
  mean, modelled by the proper **Bayesian bootstrap** (Rubin 1981): ``Dirichlet(1,…,1)``
  weights over the N paired questions. Stated assumption (a named limitation, like the
  eval's selection-bias disclosures): the eval questions are treated as exchangeable
  draws from the deployment distribution — they are a curated set, so this is a proxy,
  not a claim.

::

    Δ_draw = Σ_q w_q · [ u(typed_q ; U) - u(monolithic_q ; U) ],   w ~ Dir(1).

The gate is *decision-weighted* because the utility model sits INSIDE it: a timid policy
(abstention priced high) cannot pass by abstaining everywhere — its abstentions are
valued at the gauge zero against the monolithic's realised reports — and the
**disagreement region** (questions where the two policies choose different *kinds* of
action) is examined explicitly, since a system can lose mean log score yet win exactly
where the action changes.

**Realised-utility model (stated).** The families decide per claim under κ_att (that
choice is already baked into the action each policy took); the gate *values the realised
answer* on one common answer-level scale, so typed and monolithic are valued identically
(a rigged comparison values them differently):

* ``report`` → ``u_correct`` if the gold answer is token-contained in the asserted
  value/prose, else ``u_wrong``;
* ``hedge`` → ``u_hedged`` if the gold is among the hedged candidates, else ``u_wrong``;
* ``ask_clarify`` → ``oracle_p · u_correct - λ_int`` (the owner-oracle price the family
  itself used — not graded against gold);
* ``abstain`` → ``u_abstain`` (the gauge zero);
* every action additionally pays its arm's REALISED spend, ``-lambda_usd * cost_usd``
  (run-6 semantics, §14-registered: both arms — the typed view's total metered spend
  and the replay row's recorded usage cost; money burned is burned whatever the act).
  A utility sample without the ``lambda_usd`` latent prices spend at exactly zero, so
  pre-run-6 artifacts replay to the old Δ unchanged.

An unanswerable question (empty gold) makes every report ``u_wrong`` and abstention the
gauge zero — the honest-abstention reward falls out, no special case.

**Frozen-blind discipline (§8).** The materiality margin δ and the level are frozen in
this module BEFORE any gate result is seen; the utility prior and the preference-evidence
cutoff are likewise frozen (``model.yaml`` + ``elicitations.jsonl``, committed) and never
tuned to a gate outcome. The answer rate is published as a named diagnostic; a hard
answer-rate floor is declined on the document's own grounds — a structural constraint
where a priced quantity belongs.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from life_agent.core.decide import u_assert
from life_agent.core.matching import answer_matches

if TYPE_CHECKING:  # avoid a hard import cycle; the posterior is a plain dataclass
    from life_agent.core.utility import UtilityPosterior

# --- the frozen gate constants (blind-comparison discipline, §8) -------------------------
# δ in gauge units (u_correct = 1): typed must beat monolithic by >= 1/20 of a correct
# answer's worth, averaged per question, to count as material.
MATERIALITY_DELTA = 0.05
# The posterior-mass bar on P(Δ > δ). Calibrated to adoption's reversibility (we can
# revert a policy), not a significance ritual — high enough to be a real bar.
GATE_LEVEL = 0.90
DEFAULT_N_DRAWS = 20000
DEFAULT_SEED = 8675309

# The action partition that flips the utility sign: an assertion can be right or wrong;
# a withholding sits at the gauge (abstain) or a priced meta-cost (ask_clarify). report_scoped
# is an assertion (it states a value), but a TRUE one about the record — it lands u_hedged or
# costs only u_wrong_scoped (a citable misread), never the catastrophic current-value u_wrong.
ASSERT_ACTIONS: frozenset[str] = frozenset({"report", "report_scoped", "hedge"})
WITHHOLD_ACTIONS: frozenset[str] = frozenset({"abstain", "ask_clarify"})
_ALL_ACTIONS = ASSERT_ACTIONS | WITHHOLD_ACTIONS

# Why a withholding withheld (foundations §14, the availability registration). The action
# space is unchanged — these annotate an existing `abstain`, they are not new actions, so a
# reading that ignores them is byte-identical to the pre-run-6 Δ. The three are causally
# distinct and want opposite fixes: MISS is reach (nothing was grounded), DISPERSED is
# threshold/evidence-strength (a posterior existed and lost the argmax), UNAVAILABLE is
# neither — the corpus on the running machine cannot answer the question, so the row
# measures the corpus, not the policy, and is censored from Δ (see `delta_posterior`).
WITHHELD_MISS = "miss"
WITHHELD_DISPERSED = "dispersed"
WITHHELD_UNAVAILABLE = "unavailable"
WITHHELD_REASONS: frozenset[str] = frozenset(
    {WITHHELD_MISS, WITHHELD_DISPERSED, WITHHELD_UNAVAILABLE})


@dataclass(frozen=True)
class RealisedResponse:
    """One policy's realised answer on one question: the action it took and, for an
    assertion, whether it landed the gold fact (``None`` for a withholding).
    ``cost_usd`` is the arm's REALISED per-question spend (the typed view's
    decisions-v2 field; the replay row's recorded usage cost) — priced into Δ by
    ``realised_utility`` iff the utility sample carries the ``lambda_usd`` latent
    (run-6 semantics, pre-registered; absent latent ⇒ the old Δ byte-for-byte).
    ``withheld`` names WHY a withholding withheld (``WITHHELD_REASONS``); ``None`` on
    assertions and on any arm that does not report a reason. It is appended last and
    defaults to ``None`` deliberately — ``RealisedResponse`` is constructed positionally
    in the fairfight and membrane harnesses, and a default of ``None`` reproduces every
    pre-run-6 reading unchanged."""

    action: str
    correct: bool | None = None
    cost_usd: float = 0.0
    withheld: str | None = None
    # r21: the aggregate family's pre-registered Winkler grade in [0, 1] — None on
    # every other row (byte-identical valuation to before).
    x: float | None = None

    def __post_init__(self) -> None:
        if self.action not in _ALL_ACTIONS:
            raise ValueError(f"unknown action {self.action!r} (declared: {sorted(_ALL_ACTIONS)})")
        if self.withheld is not None and self.withheld not in WITHHELD_REASONS:
            raise ValueError(f"unknown withheld reason {self.withheld!r} "
                             f"(declared: {sorted(WITHHELD_REASONS)})")
        if self.withheld is not None and self.asserts():
            raise ValueError(f"action {self.action!r} asserts; it cannot carry a "
                             f"withheld reason ({self.withheld!r})")

    def asserts(self) -> bool:
        return self.action in ASSERT_ACTIONS


@dataclass(frozen=True)
class PairedOutcome:
    """The two policies' realised answers on one question — the gate's unit of evidence."""

    question_id: str
    answerable: bool
    typed: RealisedResponse
    mono: RealisedResponse

    def censored(self) -> bool:
        """Is this row excluded from Δ? True iff the TYPED arm withheld because this
        machine's catalogue cannot answer the question. Deliberately one-sided: the
        replay arm is a frozen full-corpus recording, so it never suffers availability,
        and a rule keyed on it would censor nothing while looking symmetric."""
        return self.typed.withheld == WITHHELD_UNAVAILABLE


# --- grading + realised utility (pure) ---------------------------------------------------

def realised_report(asserted: list[str], gold: str, variants: list[str]) -> bool:
    """Did an assertion land the gold fact? Token-boundary containment in any asserted
    value/prose (the one shared FTS matcher). Empty gold (an unanswerable question) is
    never correct."""
    if not gold:
        return False
    return any(answer_matches(gold, variants, a) for a in asserted)


_WINKLER_ALPHA = 0.2      # r21 (frozen): the rendered central level is 80%
_WINKLER_SCALE = 2.0      # r21 (frozen): x = max(0, 1 - W / (SCALE * |gold|))


def realised_aggregate(lo: float, hi: float, gold_value: float
                       ) -> tuple[float, bool]:
    """The r21 pre-registered interval grade: the Winkler score of the asserted
    central-80% interval against the numeric gold, affinely mapped onto the assert
    atom's p-argument. Returns ``(x, excludes_gold)`` — ``excludes_gold`` is the
    family's named wrong-commit class (categorical, independent of x). A sharp
    covering interval reads near 1; an interval wider than twice the gold reads 0
    even when covering; a miss pays in miss distance through the 2/alpha term."""
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


def realised_utility(resp: RealisedResponse, u: dict[str, float], *,
                     oracle_p: float) -> float:
    """The realised answer's utility under one sampled (or mean) ``u`` — the stated
    answer-level model (module docstring), minus the arm's realised spend priced at
    the sampled ``lambda_usd`` exchange rate. Spend is spent whatever the act was
    (an abstain that burned a deliberate call still paid for it). ``lambda_usd`` is a
    REQUIRED latent of every model (E-5, M4): a ``u`` lacking it is a modelling error
    and fails loud — the old 0.0 comparability pin died with the two module-local
    defaults (every live fold passes REQUIRED_LATENTS; nothing replays archived
    pre-elicitation vectors through this function)."""
    spend = u["lambda_usd"] * resp.cost_usd  # REQUIRED latent — missing fails loud (E-5)
    a = resp.action
    if a == "abstain":
        return u["u_abstain"] - spend
    if a == "ask_clarify":
        return oracle_p * u["u_correct"] - u["lambda_int"] - spend
    if a == "report":
        # D-1 (M4): the report outcome IS the atom at p ∈ {1, 0} — one written source.
        # r21: an aggregate report carries the pre-registered Winkler x instead (the
        # frozen interval grade); rows without one are byte-identical to before.
        if resp.x is not None:
            return u_assert(resp.x, u) - spend
        return u_assert(1.0 if resp.correct else 0.0, u) - spend
    if a == "hedge":
        return (u["u_hedged"] if resp.correct else u["u_wrong"]) - spend
    if a == "report_scoped":
        # a true scoped claim: lands the gold → u_hedged; a miss is a citable misread, not the
        # catastrophic current-value wrong, so it costs only u_wrong_scoped (scoped-claims §3.1)
        return (u["u_hedged"] if resp.correct else u["u_wrong_scoped"]) - spend
    raise ValueError(f"unhandled action {a!r}")  # pragma: no cover (guarded at construction)


# --- the Monte-Carlo Δ posterior ---------------------------------------------------------

def _sample_u(posterior: UtilityPosterior, rng: random.Random) -> dict[str, float]:
    """Sample one utility vector for the offline gate's MC: the gauge pins fixed, each latent
    drawn from a Gaussian(mean, variance) summary clamped to its support [lo,hi]. This is an
    OFFLINE-EVAL approximation of the continuous posterior (the agent never sees it); the latent
    posteriors are near-Gaussian (truncated-Gaussian), so the moment summary is a faithful
    sampler."""
    u = dict(posterior.gauge)
    for name, lp in posterior.latents.items():
        x = rng.gauss(lp.mean, math.sqrt(max(lp.variance, 0.0)))
        u[name] = min(max(x, lp.lo), lp.hi)
    return u


def _dirichlet_ones(n: int, rng: random.Random) -> list[float]:
    """Dirichlet(1,…,1) weights — the proper Bayesian bootstrap over n observations."""
    g = [rng.expovariate(1.0) for _ in range(n)]  # Gamma(1,1) = Exp(1)
    z = sum(g)
    return [x / z for x in g]


@dataclass(frozen=True)
class ActionPairCell:
    n: int
    mean_d: float


@dataclass(frozen=True)
class Diagnostics:
    n: int
    n_answerable: int
    typed_answer_rate: float | None
    mono_answer_rate: float | None
    typed_correct_rate: float | None
    mono_correct_rate: float | None
    disagreement_n: int
    overall_mean_d: float | None
    disagreement_mean_d: float | None
    agreement_mean_d: float | None
    action_pairs: dict[tuple[str, str], ActionPairCell]
    # Availability censoring (foundations §14). Diagnostics fold ALL rows — a censored
    # question stays visible here precisely because it is invisible to Δ. ``n_censored``
    # defaults to 0 and ``withheld_reasons`` to empty, so every pre-run-6 construction of
    # this dataclass is unchanged.
    n_censored: int = 0
    censored_mean_d: float | None = None
    withheld_reasons: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class GateResult:
    passed: bool
    p_delta_gt: float
    delta_mean: float
    delta_lo: float
    delta_hi: float
    materiality_delta: float
    level: float
    n_draws: int
    u_bar: dict[str, float]
    diagnostics: Diagnostics


def _rate(num: int, den: int) -> float | None:
    return (num / den) if den else None


def _mean(xs: list[float]) -> float | None:
    return (sum(xs) / len(xs)) if xs else None


def _diagnostics(paired: list[PairedOutcome], u_bar: dict[str, float],
                 *, oracle_p: float) -> Diagnostics:
    """The at-Ū breakdown (the collapse point): per-question gaps, the disagreement
    region, answer + correct-report rates, the action contingency."""
    answerable = [p for p in paired if p.answerable]
    d_at_bar = {p.question_id: (realised_utility(p.typed, u_bar, oracle_p=oracle_p)
                                - realised_utility(p.mono, u_bar, oracle_p=oracle_p))
                for p in paired}
    disagree = [p for p in paired if p.typed.asserts() != p.mono.asserts()]
    agree = [p for p in paired if p.typed.asserts() == p.mono.asserts()]

    pairs: dict[tuple[str, str], list[float]] = {}
    for p in paired:
        pairs.setdefault((p.typed.action, p.mono.action), []).append(d_at_bar[p.question_id])

    censored = [p for p in paired if p.censored()]
    reasons: dict[str, int] = {}
    for p in paired:
        if p.typed.withheld is not None:
            reasons[p.typed.withheld] = reasons.get(p.typed.withheld, 0) + 1

    return Diagnostics(
        n=len(paired),
        n_answerable=len(answerable),
        typed_answer_rate=_rate(sum(1 for p in answerable if p.typed.asserts()),
                                len(answerable)),
        mono_answer_rate=_rate(sum(1 for p in answerable if p.mono.asserts()),
                               len(answerable)),
        typed_correct_rate=_rate(
            sum(1 for p in answerable if p.typed.asserts() and p.typed.correct),
            len(answerable)),
        mono_correct_rate=_rate(
            sum(1 for p in answerable if p.mono.asserts() and p.mono.correct),
            len(answerable)),
        disagreement_n=len(disagree),
        overall_mean_d=_mean(list(d_at_bar.values())),
        disagreement_mean_d=_mean([d_at_bar[p.question_id] for p in disagree]),
        agreement_mean_d=_mean([d_at_bar[p.question_id] for p in agree]),
        action_pairs={k: ActionPairCell(n=len(v), mean_d=sum(v) / len(v))
                      for k, v in sorted(pairs.items())},
        n_censored=len(censored),
        # what Δ would have paid for the censored rows had they not been censored — the
        # size of the bias being removed, published so the removal is auditable
        censored_mean_d=_mean([d_at_bar[p.question_id] for p in censored]),
        withheld_reasons=reasons,
    )


def delta_posterior(paired: list[PairedOutcome], posterior: UtilityPosterior, *,
                    oracle_p: float, n_draws: int = DEFAULT_N_DRAWS,
                    seed: int = DEFAULT_SEED,
                    delta: float = MATERIALITY_DELTA,
                    level: float = GATE_LEVEL) -> GateResult:
    """The Δ-posterior MC over P(U) crossed with the Bayesian bootstrap, and the verdict.

    Deterministic given (paired, posterior, oracle_p, seed) — the gate is a replayable
    fold, like every other edge. An empty corpus yields no evidence: it does not pass.

    Availability censoring (foundations §14, registered blind before run 6): rows whose
    typed arm withheld because THIS machine's catalogue cannot answer the question are
    excluded from both the gap vector and the bootstrap's weights. Such a row measures the
    corpus, not the policy — and because the replay arm is a frozen full-corpus recording,
    leaving it in would bias Δ pro-baseline by a per-machine amount. Censored rows stay in
    ``diagnostics`` (which folds every row), so the exclusion is published, never silent.
    With no censored rows the arithmetic below is byte-identical to the pre-run-6 Δ.
    """
    u_bar = posterior.u_bar()
    diagnostics = _diagnostics(paired, u_bar, oracle_p=oracle_p)
    included = [p for p in paired if not p.censored()]
    # the guard tests INCLUDED, not paired: a corpus that censors every row has no
    # evidence either, and must fail loudly rather than return a normal-looking result
    if not included:
        return GateResult(passed=False, p_delta_gt=0.0, delta_mean=0.0,
                          delta_lo=0.0, delta_hi=0.0, materiality_delta=delta,
                          level=level, n_draws=0, u_bar=u_bar, diagnostics=diagnostics)

    rng = random.Random(seed)
    n = len(included)
    deltas: list[float] = []
    for _ in range(n_draws):
        u = _sample_u(posterior, rng)
        d = [realised_utility(p.typed, u, oracle_p=oracle_p)
             - realised_utility(p.mono, u, oracle_p=oracle_p) for p in included]
        w = _dirichlet_ones(n, rng)
        deltas.append(sum(wi * di for wi, di in zip(w, d, strict=True)))

    deltas.sort()
    p_gt = sum(1 for x in deltas if x > delta) / n_draws
    return GateResult(
        passed=p_gt >= level,
        p_delta_gt=p_gt,
        delta_mean=sum(deltas) / n_draws,
        delta_lo=deltas[int(0.05 * n_draws)],
        delta_hi=deltas[min(int(0.95 * n_draws), n_draws - 1)],
        materiality_delta=delta,
        level=level,
        n_draws=n_draws,
        u_bar=u_bar,
        diagnostics=diagnostics,
    )


# --- the published report ----------------------------------------------------------------

def _fmt(x: float | None, places: int = 3) -> str:
    return "n/a" if x is None else f"{x:.{places}f}"


def _censoring_lines(d: Diagnostics) -> list[str]:
    """The availability block (foundations §14). ALWAYS emitted when the typed arm
    reported withholding reasons — including the zero-censored case, because "0 censored"
    is the disclosure the registration demands, and a block that appears only when
    censoring bit would make its absence ambiguous."""
    if not d.withheld_reasons:
        return []
    order = [WITHHELD_MISS, WITHHELD_DISPERSED, WITHHELD_UNAVAILABLE]
    breakdown = " · ".join(f"{r} {d.withheld_reasons.get(r, 0)}" for r in order)
    lines = [
        "## Withholdings, and what Δ was computed over",
        "",
        f"- typed withholding reasons: {breakdown}",
        f"- **censored from Δ: {d.n_censored}** of {d.n} "
        f"(unavailable — this machine's catalogue cannot answer them)",
        f"- Δ was computed over {d.n - d.n_censored} question(s); "
        f"diagnostics above fold all {d.n}",
    ]
    if d.n_censored:
        lines.append(
            f"- the censored rows' mean gap at Ū was {_fmt(d.censored_mean_d)} — "
            "the per-question bias removed, published so the removal is auditable")
    lines.append("")
    return lines


def render_report(result: GateResult, *, run_id: str, elapsed: float,
                  baseline: str = "monolithic") -> str:
    """The published gate report (`$LIFE_AGENT_KB/eval/gate/report.md`) — the
    blind-comparison discipline applied to ourselves (SPEC-comparison.md precedent).

    r27: ``baseline`` NAMES THE ARM THIS RUN ACTUALLY RAN AGAINST. It used to be
    hard-coded "monolithic" in the title and in both rate labels, while the caller chose
    the arm — so every report in the §14 series from run 6 on was titled as a comparison
    against the monolithic single-call instrument when the baseline was in fact the
    raw-deliberative replay (Claude Code with corpus access, the owner's outside option).
    The paired rows carried the right tag throughout; only the prose was wrong, and the
    prose is what gets quoted into the ledger. Default kept as "monolithic" so a caller
    that does not pass it renders exactly as before.
    """
    d = result.diagnostics
    verdict = "PASS" if result.passed else "FAIL"
    lines = [
        f"# Adoption gate — typed families vs the {baseline} baseline",
        "",
        f"Decision-weighted gate (bayesian-foundations §8). run_id={run_id}  "
        f"elapsed={elapsed:.1f}s  draws={result.n_draws}",
        "",
        f"## Verdict: **{verdict}**",
        "",
        f"- P(Δ > δ) = **{result.p_delta_gt:.3f}**  (gate: >= {result.level:.2f})",
        f"- Δ = EU(typed) - EU({baseline}), per-question mean, gauge units "
        "(u_correct = 1)",
        f"- Δ posterior: mean **{_fmt(result.delta_mean)}**, "
        f"90% interval [{_fmt(result.delta_lo)}, {_fmt(result.delta_hi)}]",
        f"- materiality margin δ = {result.materiality_delta} "
        f"(**frozen** before any gate result was seen — §8 blind discipline)",
        "",
        "## The two policies, at Ū",
        "",
        f"- questions: {d.n} ({d.n_answerable} answerable)",
        f"- **answer rate** — typed {_fmt(d.typed_answer_rate, 2)} · "
        f"{baseline} {_fmt(d.mono_answer_rate, 2)}  (asserts / answerable)",
        f"- correct-report rate — typed {_fmt(d.typed_correct_rate, 2)} · "
        f"{baseline} {_fmt(d.mono_correct_rate, 2)}",
        f"- mean per-question gap at Ū: {_fmt(d.overall_mean_d)}",
        "",
        *_censoring_lines(d),
        "## The disagreement region (where the action changes)",
        "",
        f"- {d.disagreement_n} of {d.n} questions; mean gap there "
        f"{_fmt(d.disagreement_mean_d)} (agreement set {_fmt(d.agreement_mean_d)})",
        "",
        f"| typed x {baseline} | n | mean Δ at Ū |",
        "| --- | ---: | ---: |",
    ]
    for (ta, ma), cell in d.action_pairs.items():
        lines.append(f"| {ta} x {ma} | {cell.n} | {cell.mean_d:+.3f} |")
    lines += [
        "",
        "## Utility posterior mean (Ū)",
        "",
        "```",
        *(f"{k} = {v:+.4f}" for k, v in sorted(result.u_bar.items())),
        "```",
        "",
        "_The utility prior and the preference-evidence cutoff were **frozen** "
        "(model.yaml + elicitations) before this result; neither is tuned to it. "
        "A hard answer-rate floor is declined — the answer rate is a published "
        "diagnostic, not a constraint (§8)._",
    ]
    return "\n".join(lines) + "\n"
