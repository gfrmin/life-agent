# copied from credence-governor@cea4c04 benchmarks/approach_dominance/profiles.py
# (``Profile`` dataclass + ``PRESETS``/``PERSONAS``/``REALISTIC_REGION`` values, copied
# verbatim as DATA — never imported from credence-governor, a different repo. Dropped:
# the TS drift-guard machinery (``PROFILE_TS`` + the ``profile.ts`` mirror discipline —
# this package has no TypeScript sibling to drift against) and ``routing_rewards()``
# (a routing-sweep helper this package has no routing sweep to feed).
"""``scripts/dominance/profiles.py`` — profiles, personas, and the realistic region.

A Profile is the 5-tuple the product ships: the value of a correct answer (``reward``),
false-block aversion (``lam`` = λ), interruption cost (``q``), harm cost (``harm``), and
the dollar value of a second of wall-clock (``w_time``). These are the SAME values the
credence-governor benchmark ships (see the provenance header above) — copied as frozen
data, not re-derived, so the dominance analysis scores against the same declared
preferences the routing benchmark does.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import cast


@dataclass(frozen=True)
class Profile:
    reward: float  # $ value of a correct answer (the routing coordinate)
    lam: float  # λ — false-block aversion (unitless)
    q: float  # interruption cost ($)
    harm: float  # harm cost ($)
    w_time: float  # time coordinate ($/sec of wall-clock)


# ── PRESETS — byte-for-byte the values in credence-governor's profiles.py ─────────────
PRESETS: dict[str, Profile] = {
    "cost-saver": Profile(reward=0.02, lam=0.25, q=0.05, harm=1.0, w_time=0.002),
    "balanced": Profile(reward=1.0, lam=1.0, q=0.02, harm=1.0, w_time=0.014),
    "quality-first": Profile(reward=5.0, lam=2.0, q=0.1, harm=2.0, w_time=0.014),
    "speed-first": Profile(reward=1.0, lam=1.0, q=0.5, harm=1.0, w_time=0.05),
}

# ── PERSONAS — the §App-B table. q is unspecified in App-B; carries the balanced
#    default (it touches neither routing nor the harm-recall axes the eval scores). ──
PERSONAS: dict[str, Profile] = {
    "indie-hacker": Profile(reward=0.02, lam=0.25, q=0.02, harm=0.25, w_time=0.002),
    "startup-balanced": Profile(reward=1.0, lam=1.0, q=0.02, harm=1.0, w_time=0.014),
    "regulated-enterprise": Profile(reward=2.0, lam=2.0, q=0.02, harm=2.5, w_time=0.014),
    "fintech-safety": Profile(reward=5.0, lam=2.0, q=0.02, harm=3.0, w_time=0.014),
    "quality-research": Profile(reward=5.0, lam=2.0, q=0.02, harm=2.0, w_time=0.014),
}

# ── Realistic region (§App-B) — the prior the dominance fraction integrates over.
#    Declared, swappable, printed. Excludes the harm-indifferent corner (harm < 0.25). ──
REALISTIC_REGION = {
    "harm": (0.5, 3.0),  # harm in [0.5, 3.0]
    "lam": (0.25, 4.0),  # lam (lambda) in [0.25, 4.0]
    "weighting": "uniform",  # §App-B ruling: uniform over the region…
    "sensitivity": "persona",  # …with the persona-weighted integral printed alongside
    "excludes": "harm < 0.25",
}


def in_realistic_region(p: Profile) -> bool:
    """True iff ``p``'s ``(harm, lam)`` falls inside ``REALISTIC_REGION``'s bounds
    (inclusive at both ends — the region's own comments read as closed intervals).

    Not part of the copied source: a small local helper ``run_dominance.py`` uses to
    pick the uniformly-weighted subset of ``PRESETS`` or ``PERSONAS`` the summary's
    "dominance fraction over REALISTIC_REGION" integrates over (task-11 brief: "uniform
    weighting over the presets+personas whose (harm, lam) fall inside the region
    bounds"). Every ``PRESETS`` entry currently qualifies; ``indie-hacker`` is the one
    ``PERSONAS`` entry excluded (``harm=0.25 < 0.5``).
    """
    harm_lo, harm_hi = cast("tuple[float, float]", REALISTIC_REGION["harm"])
    lam_lo, lam_hi = cast("tuple[float, float]", REALISTIC_REGION["lam"])
    return harm_lo <= p.harm <= harm_hi and lam_lo <= p.lam <= lam_hi
