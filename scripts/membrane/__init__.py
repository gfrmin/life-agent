"""``scripts/membrane`` — the membrane shadow's differential + demand report (Task 7).

Reads a finished (or still-accruing) shadow log
(``life_agent.membrane.shadow.MembraneShadow``'s append-only JSONL — boot/respawn/
decide/evidence rows) and, optionally, a fair-fight run directory's ``baseline`` arm
outcomes, and produces the report the proplang session reads to decide what to build
next: per-form activity, the differential against the incumbent production system,
grounded contingency/loss numbers, and the demand ledger (named limitations actually
hit this run, each with its count and the boundary it demands).

``report.py`` is the whole package: pure functions over record lists (I/O only at the
edges — ``load_shadow_records``/``load_baseline_vectors`` read, ``main`` writes), same
shape as ``scripts/dominance/``.
"""
from __future__ import annotations
