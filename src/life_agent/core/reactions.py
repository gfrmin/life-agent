"""The reaction log + the verdict→Reaction producer — bayesian-foundations §4.4 loop.

The owner's reactions to the agent's logged EU decisions are revealed-preference evidence
about utility. This module is the calibration leg's third append-only log
(:data:`life_agent.core.config.REACTIONS_LOG`) plus the pure producer that turns verdicts
into the :class:`life_agent.core.utility.Reaction` events the posterior already folds.

**The join is on a per-decision ``decision_id``** (§4.4): a verdict binds to the exact
decision whose credence ``p`` and action set its threshold; ``question_id`` is not unique
across runs and ``run_id`` is per-*run* on the eval path, so neither can be the key.

**Only the clean abstain rows fold (v0).** A verdict on an *abstention* is a clean u(wrong)
observation — nothing was reported, so there is no wrong value or wrong subject to mistake
for a preference. At credence ``p`` the report/abstain boundary is the credence-implied
indifference point ``u(wrong)*(p) = -p/(1-p)``, so a verdict there is a soft threshold
observation on u(wrong): ``good`` ("glad you didn't guess") favours u(wrong) below it,
``bad`` ("I wanted an answer") above it. Verdicts on *reports* are cross-latent
contaminated (wrong-subject / didn't-want-report) and signed gate-favourable, so they are
recorded but NOT folded until the §8 grader-3 attribution lands — that is the named
successor. Notes, report-verdicts, and unrouted verdicts are recorded but not folded.

**Narrative abstains fold jointly (§7.1).** A narrative ``ALL_WITHHELD`` abstention reacted
to at the marginal claim's credence ``p_max`` is a soft observation on the inclusion margin
``g(U) = p(1-p)·u(wrong) - κ_att + p²`` — a :class:`~life_agent.core.utility.MarginReaction`
coupling u(wrong) and κ_att. The cleanliness *inverts* from lookup: the clean ``good`` rows
are one-directional, so **both** valences fold (the contaminated ``bad`` rows are the only
counter-pressure — without them the posterior runs to the grid edge and the gate passes
spuriously). The ``bad`` rows are coverage-gated (a low-coverage "I wanted an answer" is more
likely a proposal-recall failure than a utility complaint); the ``good`` rows are ungated. The
which-claim residual is left in the retained free-text ``reason`` (foundations §14 successor).
``NO_CLAIMS`` abstains (no ``p_max``) and narrative reports are recorded but not folded.

**Supersession, not accumulation:** the owner may revise a verdict; the fold takes the
latest verdict per ``(decision_id, kind)`` (file order is replay order), so one decision
contributes one threshold observation.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from life_agent.core import decisions as DEC
from life_agent.core import jsonl_log
from life_agent.core import utility as UT

FORMAT_VERSION = 1

# Closed vocabularies (grow by edit as the later streams land: correction, reask,
# clarify_reaction, disposal). An event outside them is a loud construction error.
KINDS: frozenset[str] = frozenset({"verdict"})
VALENCES: dict[str, frozenset[str]] = {"verdict": frozenset({"good", "bad", "note"})}

# Valences that carry a binary utility signal; ``note`` is text-only (logged, not folded).
_FOLDED_VALENCES: frozenset[str] = frozenset({"good", "bad"})

# §7.1: a narrative `bad`-on-ALL_WITHHELD folds as counter-pressure only when the proposal
# coverage posterior mean clears this bar; below it the "I wanted an answer" is more likely a
# recall failure than a utility complaint. The wide coverage prior (Beta(2,2), mean 0.5) keeps
# the gate permissive until eval_coverage evidence sharpens it; the joint endpoint-mass monitor
# is the backstop. Frozen-blind (never tuned to a gate result).
_COVERAGE_BAR: float = 0.5


@dataclass(frozen=True)
class ReactionEvent:
    """One owner reaction to one decision (§4.4 schema, format_version 1). ``reason`` is
    the nullable free-text note ``capture`` prompts for on ``bad``/``note`` — the one
    disambiguator that cannot be reconstructed later, kept even when mostly empty."""

    tx_time: str
    question_id: str
    decision_id: str
    kind: str
    valence: str
    reason: str | None = None
    format_version: int = FORMAT_VERSION

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"unknown reaction kind {self.kind!r} (declared: {sorted(KINDS)})")
        if self.valence not in VALENCES[self.kind]:
            raise ValueError(
                f"valence {self.valence!r} is not in kind {self.kind!r}'s vocabulary "
                f"{sorted(VALENCES[self.kind])}")


def _to_line(event: ReactionEvent) -> str:
    return json.dumps(asdict(event), sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _from_line(line: str) -> ReactionEvent:
    return ReactionEvent(**json.loads(line))


def append(path: Path, event: ReactionEvent) -> None:
    """Append one reaction line, durably (the shared append-only mechanics)."""
    jsonl_log.append_line(path, _to_line(event))


def read(path: Path) -> list[ReactionEvent]:
    """Every reaction in file order — the canonical replay order. Malformed lines raise."""
    return [_from_line(line) for line in jsonl_log.read_lines(path)]


def _abstain_threshold(p: float) -> float:
    """The credence-implied indifference point on u(wrong): -p/(1-p), here the positive
    ``threshold`` the ``sign=-1`` kernel crosses at u(wrong) = -p/(1-p)."""
    return p / (1.0 - p)


def _coverage_mean(summary: dict[str, Any]) -> float | None:
    """The proposal-coverage posterior mean from a narrative decision's summary, or None."""
    cov = summary.get("coverage")
    if not isinstance(cov, list) or len(cov) != 2:
        return None
    a, b = float(cov[0]), float(cov[1])
    return a / (a + b) if (a + b) > 0 else None


def _lookup_reaction(r: ReactionEvent, d: DEC.DecisionEvent) -> UT.Reaction | None:
    """A clean lookup abstain-verdict → a u(wrong) threshold observation at -p/(1-p) (§4.4)."""
    creds = d.posterior_summary.get("credences") or []
    if not creds:
        return None  # an abstention with no candidate carries no u(wrong) threshold
    p = float(creds[0])
    if not 0.0 <= p < 1.0:
        return None
    return UT.Reaction(tx_time=r.tx_time, latent="u_wrong",
                       reacted=(r.valence == "good"), sign=-1.0,
                       threshold=_abstain_threshold(p))


def _narrative_reaction(r: ReactionEvent, d: DEC.DecisionEvent) -> UT.MarginReaction | None:
    """A clean narrative ``ALL_WITHHELD`` abstain-verdict → a joint (u(wrong), κ_att) margin
    observation at the marginal claim's ``p_max`` (§7.1). Both valences fold (the ``bad`` rows
    are the only counter-pressure); the ``bad`` rows are coverage-gated; ``NO_CLAIMS`` (no
    ``p_max``) does not fold. The free-text ``reason`` is retained on the row (which-claim
    residual evidence — §14)."""
    from life_agent.core import narrative as N  # lazy: keep the import graph acyclic
    if d.posterior_summary.get("abstain_reason") != N.REASON_ALL_WITHHELD:
        return None
    raw = d.posterior_summary.get("marginal_credence")
    if raw is None:
        return None
    p = float(raw)
    if not 0.0 <= p < 1.0:
        return None
    if r.valence == "bad":
        cov = _coverage_mean(d.posterior_summary)
        if cov is None or cov < _COVERAGE_BAR:
            return None  # recorded-not-folded: low coverage ⇒ likely a recall failure
    return UT.MarginReaction(
        tx_time=r.tx_time,
        coeffs=(("kappa_att", -1.0), ("u_wrong", p * (1.0 - p))),
        offset=-(p ** 2), reacted=(r.valence == "good"), sign=-1.0,
        tau_group="narrative")


def load_reactions(reactions_path: Path,
                   decisions_path: Path) -> list[UT.Reaction | UT.MarginReaction]:
    """Join verdicts ⋈ decisions by ``decision_id`` and emit utility evidence for the clean
    rows: lookup abstain-verdicts → ``Reaction`` (u(wrong) threshold, §4.4); narrative
    ``ALL_WITHHELD`` abstain-verdicts → ``MarginReaction`` (joint u(wrong), κ_att; §7.1). Report
    verdicts, ``NO_CLAIMS`` abstains, notes, coverage-gated narrative ``bad`` rows, and unrouted
    verdicts are recorded in the log, never folded."""
    decisions = {d.decision_id: d for d in DEC.read(decisions_path) if d.decision_id}
    # supersession: latest verdict per (decision_id, kind); file order is replay order
    latest: dict[tuple[str, str], ReactionEvent] = {}
    for r in read(reactions_path):
        latest[(r.decision_id, r.kind)] = r

    out: list[UT.Reaction | UT.MarginReaction] = []
    for r in latest.values():
        if r.kind != "verdict" or r.valence not in _FOLDED_VALENCES:
            continue
        d = decisions.get(r.decision_id)
        if d is None or d.chosen_action != "abstain":
            continue  # unrouted, or a report row (recorded-not-folded)
        ev: UT.Reaction | UT.MarginReaction | None
        if d.family == "lookup":
            ev = _lookup_reaction(r, d)
        elif d.family == "narrative":
            ev = _narrative_reaction(r, d)
        else:
            ev = None
        if ev is not None:
            out.append(ev)
    return out
