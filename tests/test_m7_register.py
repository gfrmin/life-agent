"""M7 (r17) — the §6 named-exceptions register, PINNED: the re-listing guard.

The register's purpose is that the next census reads it and re-lists nothing. These
two tests make that mechanical: the census below must equal the design's §6 headings
(a new entry without a censused pin fails loudly), and every censused pin artefact
must exist on the tree (an entry whose pin rots fails loudly). Both were verified RED
by mutation before landing (a fake 6.99 entry; a mangled needle)."""
from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_DESIGN = _ROOT / "docs" / "module-collapse-design.md"

#: §6 entry → (pin artefact, needle that must appear in it; "" = existence only).
_REGISTER_PINS: dict[str, tuple[str, str]] = {
    "6.1": ("tests/test_brain.py",
            "def test_live_skin_serves_draw_but_not_for_the_utility_posterior_s_measures"),
    "6.2": ("tests/test_membrane_world.py", "def test_"),
    "6.3": ("src/life_agent/core/reliability.py", "PRIORS"),
    "6.4": ("tests/test_brain.py",
            "def test_live_skin_serves_draw_but_not_for_the_utility_posterior_s_measures"),
    "6.5": ("tests/test_collapse_record.py",
            "def test_seam_driver_reads_the_event_through_the_seal"),
    "6.6": ("tests/test_collapse_record.py",
            "def test_the_seal_routes_every_recorded_derivation_off_the_passed_root"),
    "6.7": ("scripts/collapse_replay.py", ""),
    "6.8": ("tests/test_collapse_compare.py", "def test_"),
    "6.9": ("tests/test_probes.py", "corroborate"),
    "6.10": ("tests/test_gate_tree_pin.py", "def test_"),
    "6.11": ("scripts/carrier_audit.py", "frozen"),
    "6.12": ("scripts/replace_audit.py", "frozen"),
    "6.13": ("src/pkm/retrieval.py", "round(scored.score, 9)"),
}


def test_the_register_headings_equal_the_census() -> None:
    text = _DESIGN.read_text(encoding="utf-8")
    entries = set(re.findall(r"^\*\*(6\.\d+)\b", text, flags=re.M))
    assert entries == set(_REGISTER_PINS), (
        f"§6 and the census disagree: design-only {sorted(entries - set(_REGISTER_PINS))}, "
        f"census-only {sorted(set(_REGISTER_PINS) - entries)} — a new register entry needs "
        "its pin censused here (the re-listing guard)")


def test_every_register_pin_artefact_exists() -> None:
    for entry, (path, needle) in _REGISTER_PINS.items():
        p = _ROOT / path
        assert p.exists(), f"§{entry}: pin artefact {path} is missing"
        if needle:
            assert needle in p.read_text(encoding="utf-8"), (
                f"§{entry}: {path} no longer carries its pin {needle!r}")


# --- P-II (D-6): the remaining partitions derive from, or gate on, the one vocabulary -


def test_d6_executor_withhold_derives_from_the_one_vocabulary() -> None:
    """The grow-offer latch's terminal set is a DERIVED view: the non-full-report
    terminals plus the miss reason — spelled from `DEC.ACTIONS`, not re-listed."""
    import inspect

    from life_agent.core import decisions as DEC
    from life_agent.core import executor as EX

    assert frozenset({"miss"}) | (DEC.ACTIONS
                                                  - {"report", "report_scoped"}) == EX._WITHHOLD
    src = inspect.getsource(EX)
    assert "_WITHHOLD = frozenset({\"miss\"}) | (DEC.ACTIONS" in src, (
        "EX._WITHHOLD must DERIVE from the one vocabulary (D-6), not re-list it")


def test_d6_membrane_mapping_domain_is_gated_on_the_real_vocabulary() -> None:
    """§6.2's second world keeps its own affordances; what is gateable is the
    MAPPING: its real-side domain is the one vocabulary (+ gather the kernel and
    miss the reason), and the enact map's values are real actions."""
    from life_agent.core import decisions as DEC
    from life_agent.membrane import coarse as CO
    from life_agent.membrane import world as W

    assert set(W.REAL_TO_MEMBRANE) == DEC.ACTIONS | {"gather", "miss"}
    assert set(CO._ENACT_EFFECTOR.values()) <= DEC.ACTIONS


# --- P-III (D-4): the leader order is ONE label-view --------------------------------


def test_d4_the_leader_order_is_one_view() -> None:
    """One stable weight-desc index view (labels only — the argmax is the engine's);
    the three render/poster sites bind it."""
    import inspect

    from life_agent.bridge import server as BR
    from life_agent.core import decisions as DEC
    from life_agent.core import executor as EX
    from life_agent.core import lookup as LK

    assert DEC.leader_order([0.2, 0.5, 0.3]) == [1, 2, 0]
    assert DEC.leader_order([0.5, 0.5]) == [0, 1]   # stable on ties — original order
    assert DEC.leader_order([]) == []
    assert "leader_order(" in inspect.getsource(LK)
    assert "leader_order(" in inspect.getsource(EX.render_view)
    assert "leader_order(" in inspect.getsource(BR)
