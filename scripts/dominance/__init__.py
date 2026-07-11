"""``scripts/dominance`` — the fair-fight run's dominance analysis.

Reads a finished ``run_fairfight.py`` run directory's ``arms/<arm>/vectors.jsonl``
(``life_agent.fairfight.records.OutcomeVector`` rows) and computes two levels of claim:

1. **The profile-independent Pareto frontier** (``pareto.py``) — which arms are
   weakly non-dominated on (correct_rate, cost, latency, attention), no scalarization.
2. **The profile-scalarized win map** (``profiles.py`` + ``utility.py`` + ``winmap.py``)
   — per (ordered arm-pair x profile x scenario) win/tie/loss verdicts under a declared
   utility scalarization, plus per-loss-cell triage (``loss_triage.py``) naming the
   questions responsible.

``run_dominance.py`` is the CLI entrypoint: it writes
``<run-dir>/dominance/{cells.json,frontier.json,LOSS_MAP.md,summary.md}``.
"""
from __future__ import annotations
