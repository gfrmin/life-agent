"""boot.py — what a freshly booted decider replays: the decision ⋈ verdict join.

``decisions.jsonl`` ⋈ ``reactions.jsonl`` on ``decision_id``, each verdict decoded to
``y`` = "asserting now would have been correct" by the one declared table
(:data:`life_agent.core.reactions.VERDICT_Y`, via :func:`~.session.verdict_y`). The
latest reaction per decision wins; file order is replay order. The Claude verdict channel
(:mod:`life_agent.core.claude_verdicts`) joins the same decisions and replays after the
owner's, and yields to an owner verdict on the same decision.

A missing log reads as empty. A line that does not parse is skipped and COUNTED
(:attr:`BootSnapshot.n_skipped_lines`), so a corrupt log is visible rather than a quietly
smaller replay.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from life_agent.core import claude_verdicts as CV
from life_agent.core import decisions as DEC
from life_agent.core import jsonl_log as JL
from life_agent.core import reactions as RX

from . import world as W
from .session import verdict_y

_REACTION_FIELDS: frozenset[str] = frozenset(f.name for f in fields(RX.ReactionEvent))


@dataclass(frozen=True)
class BootSnapshot:
    """``verdict_replay`` is :meth:`~.session.MembraneSession.boot`'s parameter verbatim;
    ``verdict_actions`` is the recorded act of each row, index-aligned. ``n_source_records``
    counts the rows read before the join, so the gap to ``len(verdict_replay)`` is what the
    join excluded."""

    verdict_replay: list[tuple[W.DecideSummary, int]]
    n_source_records: int
    n_skipped_lines: int = 0
    verdict_actions: list[str] = field(default_factory=list)
    # boot() also takes outcome evidence; this snapshot supplies none.
    outcome_replay: list[tuple[str, W.DecideSummary, int]] = field(default_factory=list)


def _lines(path: Path) -> list[str]:
    return JL.read_lines(path) if path.exists() else []


def _decision(line: str) -> DEC.DecisionEvent:
    obj = json.loads(line)
    obj["action_set"] = tuple(obj.get("action_set", ()))
    return DEC.DecisionEvent(**obj)


def _reaction(line: str) -> RX.ReactionEvent:
    obj = json.loads(line)
    return RX.ReactionEvent(**{k: v for k, v in obj.items() if k in _REACTION_FIELDS})


def _parse[T](lines: list[str], parse: Callable[[str], T]) -> tuple[list[T], int]:
    out: list[T] = []
    skipped = 0
    for line in lines:
        try:
            out.append(parse(line))
        except Exception:
            skipped += 1
    return out, skipped


def boot_snapshot(decisions_path: Path, reactions_path: Path, *,
                  claude_verdicts_path: Path | None = None) -> BootSnapshot:
    decisions, s1 = _parse(_lines(decisions_path), _decision)
    reactions, s2 = _parse(_lines(reactions_path), _reaction)
    claude, s3 = (_parse(_lines(claude_verdicts_path), CV.from_line)
                  if claude_verdicts_path is not None else ([], 0))

    by_id: dict[str, DEC.DecisionEvent] = {d.decision_id: d for d in decisions if d.decision_id}
    latest: dict[str, RX.ReactionEvent] = {}
    for r in reactions:
        latest[r.decision_id] = r

    replay: list[tuple[W.DecideSummary, int]] = []
    actions: list[str] = []
    for decision_id, r in latest.items():
        d = by_id.get(decision_id)
        y = verdict_y(d.chosen_action, r.valence) if d is not None else None
        if d is None or y is None:
            continue
        replay.append((W.summary_from_decision_event(asdict(d)), y))
        actions.append(d.chosen_action)

    for decision_id, cv in CV.latest_by_decision(claude).items():
        d = by_id.get(decision_id)
        if d is None:
            continue
        owner = latest.get(decision_id)
        if owner is not None and verdict_y(d.chosen_action, owner.valence) is not None:
            continue  # an owner verdict on the same decision takes precedence
        replay.append((W.summary_from_decision_event(asdict(d)), CV.y(cv)))
        actions.append(d.chosen_action)

    return BootSnapshot(verdict_replay=replay,
                        n_source_records=len(decisions) + len(reactions) + len(claude),
                        n_skipped_lines=s1 + s2 + s3, verdict_actions=actions)
