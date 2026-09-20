"""Cost pricing table for :class:`life_agent.core.llm.LLMResult` — pure, no I/O.

Prices are USD per Mtok (million tokens), longest-prefix keyed so a provider's exact served
snapshot (e.g. a dated Anthropic string) still resolves to its family's price. Verified
2026-07-11 against the ``claude-api`` skill (Anthropic models, skill cache dated 2026-06-24)
and a live web search (OpenAI ``gpt-5.1``, raised 2026-07-02) — not hand-recalled. Anthropic's
cache read/write rates aren't in the skill's per-model table; they follow its documented
multipliers (cache read ~0.1x input, cache write at the default 5-minute TTL ~1.25x input).
Local Ollama models (``qwen*`` prefix) cost nothing — the request never leaves the box.

Bump :data:`PRICING_VERSION` whenever a price changes, so a cost total computed against an
older version can be told apart from one computed against the current table.

Since M4 (design §4.2, r14) this module is THE price table: every priced constant that
ranks an action — the corroborate tier ladder, the transform menu, the deliberate row,
the grow actuators, the re-read model, and the reliability prior column (§3.2/D-2) —
is declared here, once, as data. The executor and grow modules BIND these rows; the
reliability fold imports its priors from here. Covariate parameters, sizing/timeouts
and the gate's frozen δ/level are NOT prices and live with their owners.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from life_agent.core.llm import LLMResult

PRICING_VERSION = 3

# r21 (CP-D): the §18.14 extract_amounts derive's planning price — one haiku call on a
# head-capped (20k chars) document; the demand-led warm's cap formula reads this row
# (n_questions x k x this). A per-call REALISED cost still comes from usage x price_of.
EXTRACT_AMOUNTS_USD = 0.01


@dataclass(frozen=True)
class ModelPrice:
    """USD per Mtok (million tokens) for one token kind each."""

    input: float
    output: float
    cache_read: float
    cache_write: float


PRICE_TABLE: dict[str, ModelPrice] = {
    "claude-opus-4-8": ModelPrice(input=5.00, output=25.00, cache_read=0.50, cache_write=6.25),
    "claude-sonnet-4-6": ModelPrice(input=3.00, output=15.00, cache_read=0.30, cache_write=3.75),
    "claude-haiku-4-5": ModelPrice(input=1.00, output=5.00, cache_read=0.10, cache_write=1.25),
    # gpt-5.1: OpenAI doesn't charge a write premium (first-use cache writes bill at the
    # ordinary input rate) — life_agent.core.llm.openai_complete never populates
    # cache_write_tokens for an OpenAI call, so this entry is a documented ceiling, not an
    # observed cost.
    "gpt-5.1": ModelPrice(input=1.25, output=10.00, cache_read=0.125, cache_write=1.25),
    # Local Ollama models never leave the box — free by construction, not a placeholder.
    "qwen": ModelPrice(0.0, 0.0, 0.0, 0.0),
}


def price_of(served_model: str) -> ModelPrice | None:
    """Longest :data:`PRICE_TABLE` prefix matching ``served_model``, else ``None``.

    ``None`` means the model is unpriced — the caller should record ``cost_status="partial"``
    rather than silently reporting a zero or fabricated cost.
    """
    match: str | None = None
    for prefix in PRICE_TABLE:
        if served_model.startswith(prefix) and (match is None or len(prefix) > len(match)):
            match = prefix
    return PRICE_TABLE[match] if match is not None else None


def cost_usd(r: LLMResult) -> float | None:
    """The USD cost of one :class:`LLMResult`, or ``None`` if its model is unpriced."""
    price = price_of(r.served_model)
    if price is None:
        return None
    return (
        r.in_tokens * price.input
        + r.out_tokens * price.output
        + r.cache_read_tokens * price.cache_read
        + r.cache_write_tokens * price.cache_write
    ) / 1_000_000


# --- the menu half of the table (M4, design §4.2) ----------------------------------------

# The corroborate model-tier ladder: the body names the tier (the daemon schedules it by
# name); each tier carries the model it re-reads with and the reliability that re-read is
# conditioned at (the declared value is the curve-conditioned read's COLD fallback — a
# prior, not a fixed reliability).
TIER_MODEL: dict[str, str] = {"corroborate_haiku": "claude-haiku-4-5",
                              "corroborate_sonnet": "claude-sonnet-4-6",
                              "corroborate_opus": "claude-opus-4-8"}
TIER_RHO: dict[str, float] = {"corroborate_haiku": 0.80, "corroborate_sonnet": 0.90,
                              "corroborate_opus": 0.95}
GATHER_RHO = 0.95  # the corroborate re-read's default reliability (the opus tier's)

# The per-question transform MENU the body offers the daemon (the daemon prices +
# schedules; the body enacts the arg-max by probe name). Guards fire on a precondition
# (era_split / an owner-scoped report); voi tiers fire when a leader is below the EU bar,
# each at a stated reliability + cost (frozen-blind world-knowledge priors, monotone in
# model strength; calibrated from verdicts downstream).
DEFAULT_TRANSFORMS: list[dict[str, Any]] = [
    {"name": "recency", "probe": "recency", "kind": "guard", "trigger": "era_split"},
    {"name": "corroborate_owner", "probe": "corroborate_opus", "kind": "guard",
     "trigger": "owner_report"},
    {"name": "corroborate_haiku", "probe": "corroborate_haiku", "kind": "voi",
     "trigger": "below_bar", "rho": 0.80, "cost": 0.004},
    {"name": "corroborate_sonnet", "probe": "corroborate_sonnet", "kind": "voi",
     "trigger": "below_bar", "rho": 0.90, "cost": 0.012},
    {"name": "corroborate_opus", "probe": "corroborate_opus", "kind": "voi",
     "trigger": "below_bar", "rho": 0.95, "cost": 0.020},
]

# The deliberative edge as a menu row (core/deliberate — the promoted A1b arm). The SEED
# template — never offered to the daemon as-is: menu_transforms() re-prices its rho to
# what the enactment fold can actually deliver. rho_seed 0.92 = the arm's measured 92.3%
# correct and cost 0.38 = the run's mean $/question (both ff-v2-delib-20260719, frozen
# blind). Costs are AUTHORED IN USD (as are the tier costs); run_pass converts them to
# gauge utility at u_bar's elicited lambda_usd exchange rate before the daemon reads
# them — the latent is REQUIRED of every model (E-5: a missing latent fails loud).
DELIBERATE_MODEL = "claude-opus-4-8"
DELIBERATE_TRANSFORM: dict[str, Any] = {
    "name": "deliberate", "probe": "deliberate", "kind": "voi",
    "trigger": "below_bar", "rho": 0.92, "cost": 0.38,
}
# An unmeasured deliberate read without curves conditions at min(cap, confidence) — the
# rescue channel's stated-wide-prior rationale verbatim (a lone strong read is an
# unmeasured instrument; fiat trust at its self-report was refuted on q-015).
DELIBERATE_FALLBACK_RHO = 0.5

# The strong re-read's model (the joint extract@<model> edge).
RE_EXTRACT_MODEL = "claude-opus-4-8"

# The escalation rungs (J2, ROADMAP): a rung ANSWERS the question itself, with its own
# origin on the reply, at its own price and its own measured outcome distribution — a row
# core/decide ranks beside respond/gather/ask/abstain, never a fallback. Costs are AUTHORED
# IN USD like everything else here; core/decide converts at u_bar's lambda_usd.
#
# Rung 1 is the deliberative arm (core/deliberate, DELIBERATE_MODEL). Its price is the MEAN
# of the 104 recorded verdicts in ff-v2-delib-20260719 (median $0.337, sd $0.15, max $1.59
# — the mean is the right summary because the act pays the mean over many questions, but the
# spread is why a per-rung budget is a door). A rung with no fitted row reads the mixture
# prior and never fires, so declaring one here cannot spend money by itself.
ESCALATE_RUNGS: list[dict[str, Any]] = [
    {"rung": "1", "model": DELIBERATE_MODEL, "cost": 0.375},
]

# The grow menu as data (autonomous-recall-design; served by the bridge's /grow_menu).
# Costs are in USD, like the corroborate tiers (the executor converts them at lambda_usd);
# the rerank's is measured (10 of the owner's questions, 2026-09-20: mean $0.047, 15k input
# tokens on Sonnet). The Beta(alpha0, beta0) means are frozen-blind world-knowledge priors,
# monotone in mechanism strength, stated before any counts — the counts do the calibrating.
GROW_ACTUATORS: list[dict[str, Any]] = [
    {"probe": "retrieve_rerank", "cost": 0.047, "alpha0": 3.0, "beta0": 7.0},
    {"probe": "retrieve_expand", "cost": 0.006, "alpha0": 3.5, "beta0": 6.5},
    {"probe": "re_extract_strong", "cost": 0.020, "alpha0": 4.0, "beta0": 6.0},
]

# The reliability prior column (§3.2, D-2): where each edge's trust STARTS, wide on
# purpose (the refuted fiat Beta(17,3) taught that trust is earned from evidence).
# ("extract", "value"): the local extractor, one cell. ("eval_claim", *): the claim
# instrument's closed audit partition. The one wire fold lives in core/reliability.py
# and imports this column.
RELIABILITY_PRIORS: dict[tuple[str, str], tuple[float, float]] = {
    ("extract", "value"): (4.0, 4.0),
    ("eval_claim", "verified"): (3.0, 2.0),
    ("eval_claim", "unsupported"): (1.0, 3.0),
    ("eval_claim", "unverifiable"): (2.0, 2.0),
}

# --- the channel half of the table (J1: the constants' one home) --------------------------

# The stated noisy-channel parameters the candidate posterior (core/posterior.py) reads.
# Priors, not measurements: calibration moves them, and a change here moves every credence.
A_ALTERNATIVES = 10.0  # effective number of wrong values a misreport spreads over
BETA_ANCESTRY = 0.3    # within-document temper: m chunks of one document count 1 + β·(m-1)
BETA_MODEL = 0.7       # across-document temper: G documents read by one extractor, 1 + β·(G-1)
# Prior mass on none-of-the-retrieved; the candidates share the rest uniformly. (Uniform
# over K+1 let agreeing junk bury NONE at 0.98 credence on the first eval.)
P_NONE_PRIOR = 0.5
ORACLE_P = 0.9         # owner-as-oracle reliability, pricing ask_clarify
PROB_EPS = 1e-12       # log-domain floor
