"""Grading: what an arm did on one question, and whether an assertion landed the gold.

Exact match on the point fact (CLAUDE.md): token-boundary containment of the gold, or one of
its declared variants, in an asserted value. No judge.
"""
from __future__ import annotations

from dataclasses import dataclass

from life_agent.core.matching import answer_matches

#: An assertion can be right or wrong; a withholding is neither. The archives carry every
#: action the arm has ever recorded, so the retired spellings stay in the partition.
ASSERT_ACTIONS: frozenset[str] = frozenset({"report", "report_scoped", "hedge"})
WITHHOLD_ACTIONS: frozenset[str] = frozenset({"abstain", "ask_clarify"})

#: Why a withholding withheld (``decisions.withhold_reason``). ``unavailable`` rows measure
#: the catalogue on the running machine, not the policy, and are censored.
WITHHELD_REASONS: frozenset[str] = frozenset({"miss", "dispersed", "unavailable"})


@dataclass(frozen=True)
class RealisedResponse:
    """One arm's realised answer on one question. ``correct`` is ``None`` for a withholding.
    ``cost_usd`` is the declared price of the probes ``applied`` (``pricing.list_price``:
    the price the decider ranked them at, cache or no cache); ``metered_usd`` is what the
    calls actually metered. The last four are the leader's calibration reading
    (``eval.calibration.read_leader``): its probability, and whether it matched the gold,
    on any action; ``None`` / 0 when there was no candidate."""

    action: str
    correct: bool | None = None
    cost_usd: float = 0.0
    withheld: str | None = None
    applied: tuple[str, ...] = ()
    metered_usd: float | None = None
    p1: float | None = None
    n_candidates: int = 0
    leader_correct: bool | None = None
    truth_in_candidates: bool = False

    def __post_init__(self) -> None:
        if self.action not in ASSERT_ACTIONS | WITHHOLD_ACTIONS:
            raise ValueError(f"unknown action {self.action!r}")
        if self.withheld is not None and self.withheld not in WITHHELD_REASONS:
            raise ValueError(f"unknown withheld reason {self.withheld!r}")
        if self.withheld is not None and self.action in ASSERT_ACTIONS:
            raise ValueError(f"action {self.action!r} asserts; it cannot carry a "
                             f"withheld reason ({self.withheld!r})")


def realised_report(asserted: list[str], gold: str, variants: list[str]) -> bool:
    """Did an assertion land the gold fact? An empty gold (an unanswerable question) is
    never correct."""
    if not gold:
        return False
    return any(answer_matches(gold, variants, a) for a in asserted)
