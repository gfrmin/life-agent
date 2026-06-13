"""The decision log — no EU decision is ever made unlogged (bayesian-foundations §8).

Append-only JSONL at :data:`life_agent.core.config.DECISIONS_LOG`
(``$LIFE_AGENT_KB/calibration/decisions.jsonl``). Owner reactions are readable as
*choices* — the §4.4 utility posterior's evidence — only against the decision context:
what the agent chose, among which actions, under which posterior, valuing them with
which utility fold. That context is recorded here and nowhere else, so the stream is
unbackfillable by the same option-value derivation as the outcomes log; it also feeds
§10's metareasoning accounting. Reactions join by ``question_id``.

Same discipline as :mod:`life_agent.core.outcomes`: append-only, file order is the
canonical replay order, closed vocabularies fail loudly at construction, appends are
durable. (Deliberate near-duplication of that module's mechanics — two event logs is
duplication, the third extracts a helper.)
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from life_agent.core import jsonl_log

FORMAT_VERSION = 1

# Question families with an EU response layer. Grows by edit as families land
# (aggregate and thread join at bayesian-foundations §12 stages 2-3).
FAMILIES: frozenset[str] = frozenset({"lookup", "narrative"})

# The M4 response actions (bayesian-foundations §3). ask-about-U is deliberately absent
# — utility learning is passive until the governor (§4.4, a stated action-set
# coarsening).
ACTIONS: frozenset[str] = frozenset({"report", "hedge", "ask_clarify", "abstain"})


@dataclass(frozen=True)
class DecisionEvent:
    """One EU decision (bayesian-foundations §8 schema, format_version 1).

    ``posterior_summary`` is the answer-posterior digest the decision was taken under
    (claim credences, dispersion — enough to reconstruct *why* without the full
    artifacts, which the §18.9 lineage already holds). ``utility_fold_version`` pins
    exactly which utility posterior valued the actions
    (:func:`life_agent.core.utility.fold_version`). ``predicted_eu`` is the chosen
    action's expected utility at decision time — the quantity later reactions grade.
    ``decision_id`` is the **per-decision** join key the reaction loop binds verdicts to
    (§4.4): the answer's §18.9 cache key, content-addressed so two truly identical
    decisions coalesce. It is *not* ``run_id`` (per-*run* on the eval path — overloading it
    would give one field two cardinalities). Empty only on pre-reaction-loop lines, which
    no verdict joins.
    """

    tx_time: str
    run_id: str
    question_id: str
    family: str
    action_set: tuple[str, ...]
    posterior_summary: dict[str, Any]
    utility_fold_version: str
    chosen_action: str
    predicted_eu: float
    decision_id: str = ""
    format_version: int = field(default=FORMAT_VERSION)

    def __post_init__(self) -> None:
        if self.family not in FAMILIES:
            raise ValueError(f"unknown family {self.family!r} (declared: {sorted(FAMILIES)})")
        if not self.action_set:
            raise ValueError("action_set is empty — a decision needs alternatives")
        unknown = set(self.action_set) - ACTIONS
        if unknown:
            raise ValueError(
                f"action(s) {sorted(unknown)} not in the declared vocabulary {sorted(ACTIONS)}"
            )
        if self.chosen_action not in self.action_set:
            raise ValueError(
                f"chosen action {self.chosen_action!r} not in the action set "
                f"{list(self.action_set)}"
            )


def _to_line(event: DecisionEvent) -> str:
    payload = asdict(event)
    payload["action_set"] = list(event.action_set)
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _from_line(line: str) -> DecisionEvent:
    obj = json.loads(line)
    obj["action_set"] = tuple(obj.get("action_set", ()))
    return DecisionEvent(**obj)


def append(path: Path, event: DecisionEvent) -> None:
    """Append one decision line, durably (the shared append-only mechanics)."""
    jsonl_log.append_line(path, _to_line(event))


def read(path: Path) -> list[DecisionEvent]:
    """Every decision in file order — the canonical replay order. Malformed lines
    raise; a missing file means no decisions yet."""
    return [_from_line(line) for line in jsonl_log.read_lines(path)]
