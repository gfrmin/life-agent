"""``scripts/dominance/utility.py`` — the declared scalarization.

Not copied from anywhere: this is a NEW modelling choice for the life-agent fair-fight
harness (credence-governor's ``dominance.py`` scores its own routing welfare —
``reward * correct - cost`` over a synthetic accuracy grid; this package scores real
``OutcomeVector`` rows over the triage bucket vocabulary instead).

``question_utility`` is a *declared* scalarization, not a measurement: which axes matter
and how they trade off is a modelling choice, printed verbatim (see ``FORMULA`` below)
into ``summary.md`` by ``run_dominance.py`` so a reader can audit or swap it without
re-deriving it from this module. The formula, term by term:

    question_utility(p, v) = reward * 1{bucket == CORRECT}
                            - harm * 1{bucket == CONFIDENT_WRONG}
                            - lam * reward * 1{bucket == WRONGLY_WITHHELD}
                            - q * 1{asks_issued > 0}
                            - w_time * latency_s
                            - (cost_usd or 0)

``bucket in {RIGHTLY_WITHHELD, SCOPED}`` contributes no bucket-conditioned term (a
correct withholding is neither rewarded nor penalised beyond the row's own
cost/time/interruption terms; ``SCOPED`` is a real, non-confident-wrong answer that this
scalarization does not separately reward — a future revision could).
"""
from __future__ import annotations

from typing import Any

from .profiles import Profile

FORMULA = (
    "question_utility(p, v) = reward*1{bucket==CORRECT} - harm*1{bucket==CONFIDENT_WRONG} "
    "- lam*reward*1{bucket==WRONGLY_WITHHELD} - q*1{asks_issued>0} "
    "- w_time*latency_s - (cost_usd or 0)"
)


def question_utility(p: Profile, v: dict[str, Any]) -> float:
    """One question's utility under profile ``p`` — see the module docstring / ``FORMULA``.

    ``v`` is one ``OutcomeVector`` row as a JSON-safe dict (``life_agent.fairfight.
    records.to_json`` shape) — a dict, not the dataclass, so this function works
    identically over rows freshly read from ``vectors.jsonl`` and rows round-tripped
    through ``cells.json``/``LOSS_MAP.md`` triage.
    """
    u = 0.0
    bucket = v["bucket"]
    if bucket == "CORRECT":
        u += p.reward
    if bucket == "CONFIDENT_WRONG":
        u -= p.harm
    if bucket == "WRONGLY_WITHHELD":
        u -= p.lam * p.reward
    if v["asks_issued"] > 0:
        u -= p.q
    u -= p.w_time * v["latency_s"]
    u -= v["cost_usd"] or 0.0
    return u


def welfare(p: Profile, vectors: list[dict[str, Any]]) -> float:
    """Σ ``question_utility`` over ``vectors`` — one arm's rows for one (profile, scenario)."""
    return sum(question_utility(p, v) for v in vectors)
