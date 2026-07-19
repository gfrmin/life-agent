"""life_agent.fairfight -- the fair-fight harness's shared record.

Phase 0 of the fair-fight harness: the per-question runner and the Pareto/profile
dominance analysis are later tasks; this package currently holds only the
``OutcomeVector`` record they share.
"""
from __future__ import annotations

from life_agent.fairfight.records import (
    ARMS,
    BUCKETS,
    COST_STATUSES,
    EXTERNAL_ARMS,
    FORMAT_VERSION,
    STATUSES,
    OutcomeVector,
    from_json,
    scored,
    to_json,
)

__all__ = [
    "ARMS",
    "BUCKETS",
    "COST_STATUSES",
    "EXTERNAL_ARMS",
    "FORMAT_VERSION",
    "STATUSES",
    "OutcomeVector",
    "from_json",
    "scored",
    "to_json",
]
