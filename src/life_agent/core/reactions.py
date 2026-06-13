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
successor. Narrative abstains (no single credence), notes, and unrouted verdicts are
likewise recorded but not folded.

**Supersession, not accumulation:** the owner may revise a verdict; the fold takes the
latest verdict per ``(decision_id, kind)`` (file order is replay order), so one decision
contributes one threshold observation.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

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


def load_reactions(reactions_path: Path, decisions_path: Path) -> list[UT.Reaction]:
    """Join verdicts ⋈ decisions by ``decision_id`` and emit ``utility.Reaction`` events
    for the **clean abstain rows only** (good/bad-on-abstain in the lookup family). Report
    verdicts, narrative abstains, notes, and unrouted verdicts are skipped — recorded in
    the log, never folded (§4.4)."""
    decisions = {d.decision_id: d for d in DEC.read(decisions_path) if d.decision_id}
    # supersession: latest verdict per (decision_id, kind); file order is replay order
    latest: dict[tuple[str, str], ReactionEvent] = {}
    for r in read(reactions_path):
        latest[(r.decision_id, r.kind)] = r

    out: list[UT.Reaction] = []
    for r in latest.values():
        if r.kind != "verdict" or r.valence not in _FOLDED_VALENCES:
            continue
        d = decisions.get(r.decision_id)
        if d is None or d.chosen_action != "abstain" or d.family != "lookup":
            continue  # unrouted, a report row, or a non-lookup (narrative) abstain
        creds = d.posterior_summary.get("credences") or []
        if not creds:
            continue  # an abstention with no candidate carries no u(wrong) threshold
        p = float(creds[0])
        if not 0.0 <= p < 1.0:
            continue
        out.append(UT.Reaction(
            tx_time=r.tx_time, latent="u_wrong",
            reacted=(r.valence == "good"), sign=-1.0,
            threshold=_abstain_threshold(p)))
    return out
