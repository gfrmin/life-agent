"""``scripts/fairfight`` — the Phase-0 fair-fight harness (runner-side scripts).

Composition only: this package wires existing referee machinery (``eval_grading``,
``triage_grading``, ``run_eval``, ``ask``) into the harness's per-arm grading and
run orchestration. See ``scripts/fairfight/grading.py`` for the grading composition
module.
"""
from __future__ import annotations
