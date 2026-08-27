"""K1 (r22) — the aggregate family is gone, and the offer set is unchanged.

C1 is a re-listing guard: every symbol the milestone deleted must resolve nowhere in
`src/`, `scripts/` or `tests/`. C4 pins the daemon's offer set, which is the evidence
that K1 bought no priced gate run. Both were verified RED by mutation before landing
(C1 against a reintroduced symbol, C4 against a menu row).
"""
from __future__ import annotations

import re
from pathlib import Path

from life_agent.core import decisions as DEC
from life_agent.core import pricing as PRC
from life_agent.core.executor import menu_transforms

_ROOT = Path(__file__).resolve().parents[1]
_TREES = ("src", "scripts", "tests")

# The frozen C1 list. A name here must not resolve anywhere in the tree — not as a
# definition, not as a call, not as a dict key. This file is the sole exception.
DELETED: tuple[str, ...] = (
    "_route_family", "route_aggregate", "AggregateRoute", "AggregateResult",
    "aggregate_answer", "render_aggregate", "AGGREGATE_ACTION_ORDER",
    "aggregate_route_key", "aggregate_answer_key", "ROUTE2_PROMPT", "ROUTE2_SCHEMA",
    "AGGREGATE_LAST", "AGGREGATE_ROUTE_VERSION", "AGGREGATE_ANSWER_VERSION",
)


def _sources() -> list[Path]:
    me = Path(__file__).resolve()
    return [p for t in _TREES for p in (_ROOT / t).rglob("*.py")
            if p.resolve() != me and "__pycache__" not in p.parts]


def test_deleted_family_symbols_resolve_nowhere() -> None:
    """C1: the deletion is complete. A survivor means the family is half-removed —
    worse than either end state, because the dead half still shapes decisions."""
    survivors: dict[str, list[str]] = {}
    for py in _sources():
        text = py.read_text(encoding="utf-8")
        for name in DELETED:
            if re.search(rf"\b{re.escape(name)}\b", text):
                survivors.setdefault(name, []).append(py.relative_to(_ROOT).as_posix())
    assert not survivors, (
        f"K1 deleted these but they still resolve: {survivors} — the aggregate family "
        f"is half-removed"
    )


def test_families_are_exactly_lookup_and_narrative() -> None:
    """C1: the declared family set. `aggregate` is gone; what remains of the split dies
    with `/route` at migration stage M5 (membrane-shadow §11 i-6)."""
    assert frozenset({"lookup", "narrative"}) == DEC.FAMILIES, (
        f"declared families drifted: {sorted(DEC.FAMILIES)}"
    )


def test_bridge_serves_no_family_router_or_aggregate_endpoint() -> None:
    """C1: the wire. A retired endpoint that still answers is a live decision path."""
    from life_agent.bridge import server

    assert "/route_family" not in server._POST, "the second-stage router still serves"
    assert "/aggregate" not in server._POST, "the aggregate handler still serves"


# --- C4: the offer set is unchanged, so no priced gate run is bought -------------------
# Frozen from master 4ddc469 (the tree K1 branched from). menu_transforms re-prices the
# tier and deliberate rows through the per-edge curves, so with NO curves it returns the
# declared rows plus the deliberate row at its conservative cap.

FROZEN_PROBES: tuple[str, ...] = ("recency", "corroborate_opus", "corroborate_haiku",
                                  "corroborate_sonnet", "corroborate_opus", "deliberate")


def test_menu_offer_set_is_unchanged_by_k1() -> None:
    """C4: K1 adds no menu row, so the daemon ranks the same acts over the same prices.
    That is the evidence K1 needs no priced gate run — a new row would move the argmax
    on every question and demand one. The `extract_amounts` row is deliberately deferred
    to migration stage E3, where the hand-set prices it would need are grounded."""
    rows = menu_transforms(None)
    assert tuple(r["probe"] for r in rows) == FROZEN_PROBES, (
        "the transform menu changed — K1 moved the argmax and owes a priced gate run"
    )
    assert [r["name"] for r in rows[:-1]] == [t["name"] for t in PRC.DEFAULT_TRANSFORMS]
    assert rows[-1]["name"] == PRC.DELIBERATE_TRANSFORM["name"]


def test_grow_actuators_are_unchanged_by_k1() -> None:
    """C4, the recall half: the grow menu is data (`pricing.GROW_ACTUATORS`) and K1 adds
    no actuator to it either."""
    assert tuple(a["probe"] for a in PRC.GROW_ACTUATORS) == (
        "retrieve_rerank", "retrieve_expand", "re_extract_strong")
