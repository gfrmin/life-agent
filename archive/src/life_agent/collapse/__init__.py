"""The module collapse's behaviour-preservation instrument (docs/module-collapse-design.md §7).

Recorded once from the pre-collapse tree at M0, replayed at every later checkpoint: the
fixture set is the collapse's bisection oracle. Nothing here is on the decision path — the
recorder taps injected seams and the replayer drives the same entry points with the recorded
engine, so a fixture is a pure function of what the site ranked over.
"""
from __future__ import annotations

from life_agent.collapse.compare import FieldDiff, compare_body, compare_outputs, render_diffs
from life_agent.collapse.fixture import Exchange, Fixture, coverage, manifest

__all__ = ["Exchange", "FieldDiff", "Fixture", "compare_body", "compare_outputs",
           "coverage", "manifest", "render_diffs"]
