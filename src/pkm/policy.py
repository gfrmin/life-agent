"""Policy evaluation for transform runs (SPEC v0.2.0 §22.1).

A policy is a callable that inspects a transform declaration, its
target sources, and an estimated cost, and returns one of three
decisions: Allow, Block, or RequireApproval.

Policies are evaluated sequentially in declaration order.  The first
Block short-circuits.  Any RequireApproval promotes the overall
decision even if other policies Allow.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from pkm.transform_declaration import TransformDeclaration


@dataclass(frozen=True)
class Allow:
    """Proceed without restriction."""


@dataclass(frozen=True)
class Block:
    """Refuse the transform run."""

    reason: str


@dataclass(frozen=True)
class RequireApproval:
    """Pause for human-in-the-loop approval."""

    reason: str


PolicyDecision = Allow | Block | RequireApproval


@dataclass(frozen=True)
class CostEstimate:
    """Estimated cost for a transform run."""

    total_usd: float
    per_source_usd: float
    source_count: int


@dataclass(frozen=True)
class SourceRef:
    """Lightweight reference to a source for policy evaluation."""

    source_id: str
    tags: frozenset[str]
    path: str


@dataclass(frozen=True)
class PolicyContext:
    """Ambient context available to policies."""

    root: Any
    daily_spend_usd: float = 0.0
    monthly_spend_usd: float = 0.0
    policy_config: dict[str, dict[str, Any]] = field(default_factory=dict)


class PolicyCallable(Protocol):
    """Signature every policy function must satisfy (§22.1)."""

    def __call__(
        self,
        transform_decl: TransformDeclaration,
        sources: list[SourceRef],
        estimated_cost: CostEstimate,
        context: PolicyContext,
    ) -> PolicyDecision: ...


def evaluate_policies(
    policies: list[PolicyCallable],
    transform_decl: TransformDeclaration,
    sources: list[SourceRef],
    estimated_cost: CostEstimate,
    context: PolicyContext,
) -> PolicyDecision:
    """Evaluate policies sequentially (§22.1).

    First Block short-circuits.  Any RequireApproval promotes the
    overall result.  All-Allow returns Allow.
    """
    approval_reasons: list[str] = []

    for policy in policies:
        decision = policy(transform_decl, sources, estimated_cost, context)
        if isinstance(decision, Block):
            return decision
        if isinstance(decision, RequireApproval):
            approval_reasons.append(decision.reason)

    if approval_reasons:
        return RequireApproval(reason="; ".join(approval_reasons))

    return Allow()
