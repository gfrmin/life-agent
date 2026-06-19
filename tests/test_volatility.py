"""Per-construct volatility — the world-knowledge half-lives + the decay property they buy.

    uv run --project . python -m pytest tests/test_volatility.py
"""
from __future__ import annotations

from datetime import date

from life_agent.core import lookup as LK
from life_agent.core import volatility as V


def test_permanent_constructs_get_the_permanent_half_life() -> None:
    assert V.half_life("date of birth") == V.PERMANENT
    assert V.half_life("Israeli ID number") == V.PERMANENT
    assert V.half_life("national identity number") == V.PERMANENT


def test_volatile_constructs_get_short_world_knowledge_half_lives() -> None:
    assert V.half_life("mobile phone number") == 8.0
    assert V.half_life("home address") == 7.0
    assert V.half_life("partner visa") == 3.0
    assert V.half_life("annual salary") == 2.0
    # passport renews (~10y) even though it is an id — the specific keyword wins over the
    # permanent national-id group (ordering matters).
    assert V.half_life("passport number") == 10.0


def test_unknown_or_missing_construct_falls_to_the_default() -> None:
    assert V.half_life("favourite colour") == V.DEFAULT
    assert V.half_life("") == V.DEFAULT
    assert V.half_life(None) == V.DEFAULT


def test_the_half_life_drives_the_recency_decay() -> None:
    # the property the prior buys: over a decade, a permanent fact barely decays while a
    # 2-year-half-life fact (e.g. salary) is almost entirely discounted as possibly-stale.
    today = date(2025, 1, 1)
    permanent = LK.time_factor("2015-01-01", time_indexed=True, today=today,
                               half_life_years=V.PERMANENT)
    volatile = LK.time_factor("2015-01-01", time_indexed=True, today=today, half_life_years=2.0)
    assert permanent > 0.999
    assert volatile < 0.05
    assert permanent > volatile
