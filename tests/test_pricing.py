"""Tests for ``core.pricing`` — pure, no I/O, no network.

Prefix lookup (longest-prefix wins over a dated snapshot suffix), cached-token cost
arithmetic, and the unknown-model → ``None`` (cost_status="partial") contract.
"""
from __future__ import annotations

import pytest

from life_agent.core.llm import LLMResult
from life_agent.core.pricing import PRICE_TABLE, PRICING_VERSION, ModelPrice, cost_usd, price_of


def test_price_of_matches_a_dated_served_model_snapshot() -> None:
    # served_model carries the provider's exact snapshot (e.g. a dated Anthropic string);
    # price_of must resolve it against the bare family prefix in PRICE_TABLE.
    assert price_of("claude-opus-4-8-20260615") == PRICE_TABLE["claude-opus-4-8"]
    assert price_of("claude-sonnet-4-6-20260101") == PRICE_TABLE["claude-sonnet-4-6"]
    assert price_of("claude-haiku-4-5-20251001") == PRICE_TABLE["claude-haiku-4-5"]
    assert price_of("gpt-5.1-2026-01-01") == PRICE_TABLE["gpt-5.1"]


def test_price_of_exact_match() -> None:
    assert price_of("claude-sonnet-4-6") == PRICE_TABLE["claude-sonnet-4-6"]


def test_price_of_local_qwen_models_are_free() -> None:
    assert price_of("qwen2.5:7b-instruct") == ModelPrice(0, 0, 0, 0)
    assert price_of("qwen3.5:9b") == ModelPrice(0, 0, 0, 0)


def test_price_of_unknown_model_is_none() -> None:
    assert price_of("some-unheard-of-model") is None
    assert price_of("") is None


def test_cost_usd_full_arithmetic_over_all_four_token_kinds() -> None:
    price = PRICE_TABLE["claude-sonnet-4-6"]
    r = LLMResult(
        text="x",
        in_tokens=1_000_000,
        out_tokens=1_000_000,
        seconds=1.0,
        served_model="claude-sonnet-4-6",
        cache_read_tokens=1_000_000,
        cache_write_tokens=1_000_000,
        provider="anthropic",
    )
    expected = price.input + price.output + price.cache_read + price.cache_write
    got = cost_usd(r)
    assert got is not None
    assert got == pytest.approx(expected)


def test_cost_usd_scales_linearly_with_tokens() -> None:
    price = PRICE_TABLE["claude-haiku-4-5"]
    r = LLMResult(
        text="x", in_tokens=500_000, out_tokens=0, seconds=0.1, served_model="claude-haiku-4-5"
    )
    got = cost_usd(r)
    assert got is not None
    assert got == pytest.approx(price.input * 0.5)


def test_cost_usd_is_zero_for_local_model() -> None:
    r = LLMResult(
        text="x", in_tokens=500, out_tokens=500, seconds=0.1, served_model="qwen2.5:7b-instruct"
    )
    assert cost_usd(r) == 0.0


def test_cost_usd_is_none_for_unpriced_model() -> None:
    r = LLMResult(text="x", in_tokens=500, out_tokens=500, seconds=0.1, served_model="mystery")
    assert cost_usd(r) is None


def test_cost_usd_none_for_default_empty_served_model() -> None:
    # A default-constructed LLMResult (served_model="") must not silently price as free.
    r = LLMResult(text="x", in_tokens=500, out_tokens=500, seconds=0.1)
    assert cost_usd(r) is None


def test_pricing_version_is_an_int() -> None:
    assert isinstance(PRICING_VERSION, int)


def test_model_price_is_frozen() -> None:
    price = ModelPrice(1.0, 2.0, 0.1, 0.2)
    with pytest.raises(AttributeError):
        price.input = 5.0  # type: ignore[misc]
