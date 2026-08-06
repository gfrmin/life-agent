"""Per-edge confidence calibration — the gate's defense (answer-executor plan, finding 2).

A self-reported confidence ``c`` from an edge (the local extractor, a joint-read model) must
never be folded as the observation reliability directly: elicited success probabilities are
systematically overconfident, and worst exactly where the answer is WRONG — the one region the
zero-confident-wrong gate cares about. The executor folds ``calib_edge(c)`` instead: a monotone
map from self-reported confidence to *empirical* reliability, learned per edge from the owner's
graded outcomes, **pessimistic where evidence is thin** (cold-start errs toward scope/abstain;
evidence earns confidence).

The estimator is a Beta-shrunk binned isotonic curve, pure Python (no new dependency):

  * bin the outcomes by confidence; each bin's reliability is the posterior mean of a
    ``Beta(prior_alpha + #correct, prior_beta + #wrong)`` — the pessimistic prior shrinks thin
    bins toward ``prior_alpha / (prior_alpha + prior_beta)``;
  * pool-adjacent-violators (PAV) makes the per-bin means monotone non-decreasing — a higher
    self-reported confidence can never map to a *lower* calibrated reliability.

Frozen-blind: the curve folds from verdicts, never fitted to a gate; the prior is conservative
by design (prior conservatism is allowed; fitting to a gate is not).
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Outcome:
    """One graded edge output: the edge's self-reported confidence and whether it was correct
    (the owner's trichotomy verdict folded to a bit — ``correct`` true only for a current-value
    hit; stale and wrong both fold to false, since a stale answer is still wrong)."""

    confidence: float
    correct: bool


@dataclass(frozen=True)
class EdgeOutcome:
    """An :class:`Outcome` tagged with the edge that produced it — the row the executor's demand
    log emits (which edge committed, at what confidence, graded by the owner's verdict)."""

    edge: str
    confidence: float
    correct: bool


def _bin_index(c: float, n_bins: int) -> int:
    return min(max(int(c * n_bins), 0), n_bins - 1)


def _pav(values: list[float], weights: list[float]) -> list[float]:
    """Pool-adjacent-violators: the weighted isotonic (non-decreasing) fit of ``values``.
    Returns one fitted value per input bin."""
    # each block: [mean, total weight, number of original bins it spans]
    blocks: list[list[float]] = []
    for v, w in zip(values, weights, strict=True):
        blocks.append([v, w, 1.0])
        while len(blocks) >= 2 and blocks[-2][0] >= blocks[-1][0]:
            v2, w2, c2 = blocks.pop()
            v1, w1, c1 = blocks.pop()
            blocks.append([(v1 * w1 + v2 * w2) / (w1 + w2), w1 + w2, c1 + c2])
    out: list[float] = []
    for mean, _w, count in blocks:
        out.extend([mean] * int(count))
    return out


@dataclass(frozen=True)
class ReliabilityCurve:
    """A fitted, monotone map ``confidence → calibrated reliability`` over ``n_bins`` bins."""

    bin_reliability: tuple[float, ...]  # the monotone per-bin reliability, length n_bins

    def calibrate(self, c: float) -> float:
        """The calibrated reliability for a self-reported confidence ``c`` (clamped to [0, 1])."""
        c = min(max(c, 0.0), 1.0)
        return self.bin_reliability[_bin_index(c, len(self.bin_reliability))]


def fit_reliability_curve(outcomes: list[Outcome], *, prior_alpha: float = 1.0,
                          prior_beta: float = 3.0, n_bins: int = 10) -> ReliabilityCurve:
    """Fit the per-edge calibration curve from graded outcomes (empty ⇒ the pessimistic prior
    everywhere). ``Beta(prior_alpha, prior_beta)`` is the cold-start reliability — keep its mean
    well below 0.5 so an unproven edge cannot clear the assertion floor on self-report alone."""
    if n_bins < 1:
        raise ValueError(f"n_bins must be ≥ 1, got {n_bins}")
    n_correct = [0] * n_bins
    n_wrong = [0] * n_bins
    for o in outcomes:
        b = _bin_index(min(max(o.confidence, 0.0), 1.0), n_bins)
        if o.correct:
            n_correct[b] += 1
        else:
            n_wrong[b] += 1
    # per-bin Beta posterior mean + its total weight (prior mass + evidence)
    means = [(prior_alpha + nc) / (prior_alpha + prior_beta + nc + nw)
             for nc, nw in zip(n_correct, n_wrong, strict=True)]
    weights = [prior_alpha + prior_beta + nc + nw
               for nc, nw in zip(n_correct, n_wrong, strict=True)]
    return ReliabilityCurve(bin_reliability=tuple(_pav(means, weights)))


def fit_edge_curves(records: list[EdgeOutcome], *, prior_alpha: float = 1.0,
                    prior_beta: float = 3.0, n_bins: int = 10) -> dict[str, ReliabilityCurve]:
    """Group graded outcomes by edge and fit one curve per edge — the executor's calibration
    fold over the demand log. An edge with no records simply does not appear (the executor
    falls back to the pessimistic prior via :func:`curve_for`)."""
    by_edge: dict[str, list[Outcome]] = defaultdict(list)
    for r in records:
        by_edge[r.edge].append(Outcome(r.confidence, r.correct))
    return {edge: fit_reliability_curve(outs, prior_alpha=prior_alpha,
                                        prior_beta=prior_beta, n_bins=n_bins)
            for edge, outs in by_edge.items()}


def curve_for(curves: dict[str, ReliabilityCurve], edge: str, *, prior_alpha: float = 1.0,
              prior_beta: float = 3.0, n_bins: int = 10) -> ReliabilityCurve:
    """The fitted curve for an edge, or the pessimistic cold-start prior for one not yet seen —
    so a brand-new (or starved) edge errs toward scope/abstain until evidence earns its trust."""
    return curves.get(edge) or fit_reliability_curve([], prior_alpha=prior_alpha,
                                                      prior_beta=prior_beta, n_bins=n_bins)


def edge_outcomes_from_log(path: Path) -> list[EdgeOutcome]:
    """The per-edge grading rows out of the §8 outcomes log: every event whose
    ``instrument_identity`` names its ``edge`` explicitly AND that carries the asserted
    probability. Legacy rows without an edge are skipped, never guessed into a namespace
    (the question_id lesson: a derived spelling silently splits the attribution and every
    curve reads as cold). The correct bit is the grader's own CORRECT_GRADES fold."""
    from life_agent.core import outcomes as O

    rows: list[EdgeOutcome] = []
    for ev in O.read(path):
        edge = ev.instrument_identity.get("edge")
        if not edge or ev.probability is None:
            continue
        rows.append(EdgeOutcome(str(edge), float(ev.probability),
                                ev.grade in O.CORRECT_GRADES[ev.grader]))
    return rows
