"""Tests for ``pkm.policy`` — policy evaluation."""

from __future__ import annotations

from typing import Any

from pkm.policy import (
    Allow,
    Block,
    CostEstimate,
    PolicyContext,
    PolicyDecision,
    RequireApproval,
    SourceRef,
    evaluate_policies,
)
from pkm.transform_declaration import TransformDeclaration


def _decl() -> TransformDeclaration:
    return TransformDeclaration(
        name="test_transform",
        version="0.1.0",
        producer_class="test.TestProducer",
        model_identity={"provider": "stub", "model": "stub"},
        prompt_name="test_v1",
        prompt_text="test prompt",
        prompt_hash="a" * 64,
        output_schema_name="test_v1",
        output_schema={},
        policies=[],
        input_producer=None,
        input_required_status="success",
        declaration_hash="b" * 64,
    )


def _cost() -> CostEstimate:
    return CostEstimate(total_usd=1.0, per_source_usd=0.01, source_count=100)


def _ctx() -> PolicyContext:
    return PolicyContext(root="/tmp")


def _sources() -> list[SourceRef]:
    return [SourceRef(source_id="s1", tags=frozenset(), path="/doc.txt")]


def _always_allow(
    _td: Any, _s: Any, _c: Any, _ctx: Any,
) -> PolicyDecision:
    return Allow()


def _always_block(
    _td: Any, _s: Any, _c: Any, _ctx: Any,
) -> PolicyDecision:
    return Block(reason="blocked by policy")


def _always_require(
    _td: Any, _s: Any, _c: Any, _ctx: Any,
) -> PolicyDecision:
    return RequireApproval(reason="needs approval")


def _require_sensitive(
    _td: Any, _s: Any, _c: Any, _ctx: Any,
) -> PolicyDecision:
    return RequireApproval(reason="sensitive data")


def test_all_allow_returns_allow() -> None:
    result = evaluate_policies(
        [_always_allow, _always_allow],
        _decl(), _sources(), _cost(), _ctx(),
    )
    assert isinstance(result, Allow)


def test_empty_policies_returns_allow() -> None:
    result = evaluate_policies(
        [], _decl(), _sources(), _cost(), _ctx(),
    )
    assert isinstance(result, Allow)


def test_block_short_circuits() -> None:
    calls: list[str] = []

    def tracking_allow(
        _td: Any, _s: Any, _c: Any, _ctx: Any,
    ) -> PolicyDecision:
        calls.append("allow")
        return Allow()

    result = evaluate_policies(
        [_always_block, tracking_allow],
        _decl(), _sources(), _cost(), _ctx(),
    )
    assert isinstance(result, Block)
    assert result.reason == "blocked by policy"
    assert calls == []


def test_require_approval_promotes() -> None:
    result = evaluate_policies(
        [_always_allow, _always_require, _always_allow],
        _decl(), _sources(), _cost(), _ctx(),
    )
    assert isinstance(result, RequireApproval)
    assert "needs approval" in result.reason


def test_multiple_require_approval_combines_reasons() -> None:
    result = evaluate_policies(
        [_always_require, _require_sensitive],
        _decl(), _sources(), _cost(), _ctx(),
    )
    assert isinstance(result, RequireApproval)
    assert "needs approval" in result.reason
    assert "sensitive data" in result.reason


def test_block_beats_require_approval() -> None:
    result = evaluate_policies(
        [_always_require, _always_block],
        _decl(), _sources(), _cost(), _ctx(),
    )
    assert isinstance(result, Block)
