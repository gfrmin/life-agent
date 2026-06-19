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
* ``abstain`` → ``u_abstain`` (the gauge zero).

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

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

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


@dataclass(frozen=True)
class RealisedResponse:
    """One policy's realised answer on one question: the action it took and, for an
    assertion, whether it landed the gold fact (``None`` for a withholding)."""

    action: str
    correct: bool | None = None

    def __post_init__(self) -> None:
        if self.action not in _ALL_ACTIONS:
            raise ValueError(f"unknown action {self.action!r} (declared: {sorted(_ALL_ACTIONS)})")

    def asserts(self) -> bool:
        return self.action in ASSERT_ACTIONS


@dataclass(frozen=True)
class PairedOutcome:
    """The two policies' realised answers on one question — the gate's unit of evidence."""

    question_id: str
    answerable: bool
    typed: RealisedResponse
    mono: RealisedResponse


# --- grading + realised utility (pure) ---------------------------------------------------

def realised_report(asserted: list[str], gold: str, variants: list[str]) -> bool:
    """Did an assertion land the gold fact? Token-boundary containment in any asserted
    value/prose (the one shared FTS matcher). Empty gold (an unanswerable question) is
    never correct."""
    if not gold:
        return False
    return any(answer_matches(gold, variants, a) for a in asserted)


def realised_utility(resp: RealisedResponse, u: dict[str, float], *,
                     oracle_p: float) -> float:
    """The realised answer's utility under one sampled (or mean) ``u`` — the stated
    answer-level model (module docstring)."""
    a = resp.action
    if a == "abstain":
        return u["u_abstain"]
    if a == "ask_clarify":
        return oracle_p * u["u_correct"] - u["lambda_int"]
    if a == "report":
        return u["u_correct"] if resp.correct else u["u_wrong"]
    if a == "hedge":
        return u["u_hedged"] if resp.correct else u["u_wrong"]
    if a == "report_scoped":
        # a true scoped claim: lands the gold → u_hedged; a miss is a citable misread, not the
        # catastrophic current-value wrong, so it costs only u_wrong_scoped (scoped-claims §3.1)
        return u["u_hedged"] if resp.correct else u["u_wrong_scoped"]
    raise ValueError(f"unhandled action {a!r}")  # pragma: no cover (guarded at construction)


# --- the Monte-Carlo Δ posterior ---------------------------------------------------------

def _categorical(values: tuple[float, ...], weights: tuple[float, ...],
                 rng: random.Random) -> float:
    """One draw from a discrete grid marginal."""
    r = rng.random()
    cum = 0.0
    for v, w in zip(values, weights, strict=True):
        cum += w
        if r <= cum:
            return v
    return values[-1]


def _sample_u(posterior: UtilityPosterior, rng: random.Random) -> dict[str, float]:
    """Sample one utility vector: the gauge pins fixed, each latent drawn from its grid
    marginal (the v0 posterior is independent across latents — stated; a joint posterior
    would sample the joint)."""
    u = dict(posterior.gauge)
    for name, lp in posterior.latents.items():
        u[name] = _categorical(lp.values, lp.weights, rng)
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
    )


def delta_posterior(paired: list[PairedOutcome], posterior: UtilityPosterior, *,
                    oracle_p: float, n_draws: int = DEFAULT_N_DRAWS,
                    seed: int = DEFAULT_SEED,
                    delta: float = MATERIALITY_DELTA,
                    level: float = GATE_LEVEL) -> GateResult:
    """The Δ-posterior MC over P(U) crossed with the Bayesian bootstrap, and the verdict.

    Deterministic given (paired, posterior, oracle_p, seed) — the gate is a replayable
    fold, like every other edge. An empty corpus yields no evidence: it does not pass.
    """
    u_bar = posterior.u_bar()
    diagnostics = _diagnostics(paired, u_bar, oracle_p=oracle_p)
    if not paired:
        return GateResult(passed=False, p_delta_gt=0.0, delta_mean=0.0,
                          delta_lo=0.0, delta_hi=0.0, materiality_delta=delta,
                          level=level, n_draws=0, u_bar=u_bar, diagnostics=diagnostics)

    rng = random.Random(seed)
    n = len(paired)
    deltas: list[float] = []
    for _ in range(n_draws):
        u = _sample_u(posterior, rng)
        d = [realised_utility(p.typed, u, oracle_p=oracle_p)
             - realised_utility(p.mono, u, oracle_p=oracle_p) for p in paired]
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


def render_report(result: GateResult, *, run_id: str, elapsed: float) -> str:
    """The published gate report (`$LIFE_AGENT_KB/eval/gate/report.md`) — the
    blind-comparison discipline applied to ourselves (SPEC-comparison.md precedent)."""
    d = result.diagnostics
    verdict = "PASS" if result.passed else "FAIL"
    lines = [
        "# Adoption gate — typed families vs the monolithic instrument",
        "",
        f"Decision-weighted gate (bayesian-foundations §8). run_id={run_id}  "
        f"elapsed={elapsed:.1f}s  draws={result.n_draws}",
        "",
        f"## Verdict: **{verdict}**",
        "",
        f"- P(Δ > δ) = **{result.p_delta_gt:.3f}**  (gate: >= {result.level:.2f})",
        "- Δ = EU(typed) - EU(monolithic), per-question mean, gauge units "
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
        f"monolithic {_fmt(d.mono_answer_rate, 2)}  (asserts / answerable)",
        f"- correct-report rate — typed {_fmt(d.typed_correct_rate, 2)} · "
        f"monolithic {_fmt(d.mono_correct_rate, 2)}",
        f"- mean per-question gap at Ū: {_fmt(d.overall_mean_d)}",
        "",
        "## The disagreement region (where the action changes)",
        "",
        f"- {d.disagreement_n} of {d.n} questions; mean gap there "
        f"{_fmt(d.disagreement_mean_d)} (agreement set {_fmt(d.agreement_mean_d)})",
        "",
        "| typed x monolithic | n | mean Δ at Ū |",
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
