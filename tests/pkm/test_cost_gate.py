"""Tests for the ``cost_gate`` policy function."""

from __future__ import annotations

from pathlib import Path

from pkm.policy import Allow, Block, CostEstimate, PolicyContext
from pkm.policy_loader import load_policy

_COST_GATE_SOURCE = '''\
from pkm.policy import Allow, Block


def cost_gate(transform_decl, sources, estimated_cost, context):
    config = context.policy_config.get("cost_gate", {})
    budget_per_inv = config.get("budget_per_invocation_usd", 5.00)
    budget_per_day = config.get("budget_per_day_usd", 50.00)
    budget_per_month = config.get("budget_per_month_usd", 200.00)

    if estimated_cost.total_usd > budget_per_inv:
        return Block(
            reason=(
                f"estimated cost ${estimated_cost.total_usd:.2f} "
                f"exceeds per-invocation budget ${budget_per_inv:.2f}"
            )
        )
    if context.daily_spend_usd + estimated_cost.total_usd > budget_per_day:
        return Block(
            reason=f"would exceed daily budget ${budget_per_day:.2f}"
        )
    if context.monthly_spend_usd + estimated_cost.total_usd > budget_per_month:
        return Block(
            reason=f"would exceed monthly budget ${budget_per_month:.2f}"
        )
    return Allow()
'''


def _setup(root: Path) -> None:
    (root / "policies").mkdir(exist_ok=True)
    (root / "policies" / "cost_gate.py").write_text(
        _COST_GATE_SOURCE, encoding="utf-8",
    )


def _ctx(
    root: Path,
    *,
    budget_per_inv: float = 5.0,
    daily: float = 0.0,
    monthly: float = 0.0,
) -> PolicyContext:
    return PolicyContext(
        root=root,
        daily_spend_usd=daily,
        monthly_spend_usd=monthly,
        policy_config={
            "cost_gate": {
                "budget_per_invocation_usd": budget_per_inv,
                "budget_per_day_usd": 50.0,
                "budget_per_month_usd": 200.0,
            },
        },
    )


def test_cost_gate_allows_under_budget(tmp_path: Path) -> None:
    _setup(tmp_path)
    fn = load_policy(tmp_path, "cost_gate")
    cost = CostEstimate(total_usd=1.0, per_source_usd=0.01, source_count=100)
    result = fn(None, [], cost, _ctx(tmp_path))  # type: ignore[arg-type]
    assert isinstance(result, Allow)


def test_cost_gate_blocks_over_invocation_budget(tmp_path: Path) -> None:
    _setup(tmp_path)
    fn = load_policy(tmp_path, "cost_gate")
    cost = CostEstimate(total_usd=10.0, per_source_usd=0.1, source_count=100)
    result = fn(None, [], cost, _ctx(tmp_path, budget_per_inv=5.0))  # type: ignore[arg-type]
    assert isinstance(result, Block)
    assert "per-invocation" in result.reason


def test_cost_gate_blocks_over_daily_budget(tmp_path: Path) -> None:
    _setup(tmp_path)
    fn = load_policy(tmp_path, "cost_gate")
    cost = CostEstimate(total_usd=2.0, per_source_usd=0.02, source_count=100)
    result = fn(None, [], cost, _ctx(tmp_path, daily=49.0))  # type: ignore[arg-type]
    assert isinstance(result, Block)
    assert "daily" in result.reason


def test_cost_gate_uses_default_thresholds(tmp_path: Path) -> None:
    _setup(tmp_path)
    fn = load_policy(tmp_path, "cost_gate")
    cost = CostEstimate(total_usd=1.0, per_source_usd=0.01, source_count=100)
    ctx = PolicyContext(root=tmp_path, policy_config={})
    result = fn(None, [], cost, ctx)  # type: ignore[arg-type]
    assert isinstance(result, Allow)
