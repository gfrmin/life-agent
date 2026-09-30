"""The candidate posterior: K retrieved candidates + NONE, conditioned on the extractions.

The belief every answer is decided on. The truth is one of the K candidates the extractor
reported, or NONE ("not among the retrieved"); with K = 0 it is NONE with certainty. The
prior puts ``P_NONE_PRIOR`` on NONE and
spreads the rest uniformly. Each observation is a noisy report of one candidate: with
reliability ``r = rho · authority · subject · time · competition`` it names the truth, and
otherwise it names one of ``A_ALTERNATIVES`` wrong values at random. Correlated reports are
tempered: ``m`` chunks of one document count as ``1 + β_anc·(m-1)`` observations, and ``G``
documents read by the one extractor count as ``1 + β_mod·(G-1)``.

Pure functions over the ``/decide`` wire observations (``reports``, ``group``, ``authority``,
``subject_factor``, ``time_factor``, optional ``competition_factor``). The arithmetic
renormalises log weights after every condition, which the replay pin in
``tests/test_posterior.py`` holds it to. This module ranks nothing: the act is
:func:`life_agent.core.decide.bayes_act`.
"""
from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from life_agent.core.pricing import (
    A_ALTERNATIVES,
    BETA_ANCESTRY,
    BETA_MODEL,
    P_NONE_PRIOR,
    PROB_EPS,
)


@dataclass(frozen=True)
class Channel:
    """The channel's constants: what the posterior is a function of besides the evidence.
    The defaults are the stated values in :mod:`life_agent.core.pricing`
    (:func:`default_channel`); another setting is evaluated by passing it. ``eta`` is a global
    exponent on every observation's tempered log-likelihood: 1.0 is the model as stated, above
    it the evidence counts for more overall, below it for less."""

    p_none_prior: float
    beta_ancestry: float
    beta_model: float
    a_alternatives: float
    eta: float = 1.0


def default_channel() -> Channel:
    """The stated constants, read from :mod:`life_agent.core.pricing` at the call."""
    return Channel(P_NONE_PRIOR, BETA_ANCESTRY, BETA_MODEL, A_ALTERNATIVES)


def temper_scales(groups: Sequence[int], channel: Channel | None = None) -> list[float]:
    """Per observation, the exponent its log-likelihood is scaled by; 1.0 for a lone one."""
    ch = channel or default_channel()
    counts = Counter(groups)
    n_groups = len(counts)
    s_mod = 1.0 if n_groups == 0 else (1.0 + ch.beta_model * (n_groups - 1)) / n_groups
    return [(1.0 + ch.beta_ancestry * (counts[g] - 1)) / counts[g] * s_mod for g in groups]


def reliability(rho: float, obs: Mapping[str, Any]) -> float:
    """The chance this observation names the truth."""
    return float(rho * obs["authority"] * obs["subject_factor"] * obs["time_factor"]
                 * obs.get("competition_factor", 1.0))


def log_match_miss(r: float, scale: float,
                   channel: Channel | None = None) -> tuple[float, float]:
    """The tempered log-likelihood of a report under the hypothesis it names, and under any
    other hypothesis (NONE included)."""
    a = (channel or default_channel()).a_alternatives
    return (scale * math.log(max(r + (1.0 - r) / a, PROB_EPS)),
            scale * math.log(max((1.0 - r) / a, PROB_EPS)))


def normalised(log_w: Sequence[float]) -> list[float]:
    """The log weights shifted so they sum to one in probability (log-sum-exp)."""
    top = max(log_w)
    log_total = top + math.log(sum(math.exp(x - top) for x in log_w))
    return [x - log_total for x in log_w]


def log_posterior(k: int, observations: Sequence[Mapping[str, Any]],
                  rho: float, channel: Channel | None = None) -> list[float]:
    """Normalised log weights over candidates ``0..k-1`` then NONE, in observation order."""
    if k < 0:
        raise ValueError("the posterior cannot have a negative number of candidates")
    ch = channel or default_channel()
    # with no candidate the truth is NONE: the prior mass on the candidates has nowhere to go
    prior = [math.log((1.0 - ch.p_none_prior) / k)] * k if k else []
    log_w = normalised([*prior, math.log(ch.p_none_prior)])
    for obs, scale in zip(observations,
                          temper_scales([o["group"] for o in observations], ch),
                          strict=True):
        match, miss = log_match_miss(reliability(rho, obs), scale * ch.eta, ch)
        hit = obs["reports"]
        log_w = normalised([w + (match if h == hit else miss) for h, w in enumerate(log_w)])
    return log_w


def candidate_posterior(k: int, observations: Sequence[Mapping[str, Any]],
                        rho: float, channel: Channel | None = None
                        ) -> tuple[list[float], float]:
    """``(credences, p_none)``: the candidates' posterior mass in candidate order, and NONE's."""
    log_w = log_posterior(k, observations, rho, channel)
    top = max(log_w)
    w = [math.exp(x - top) for x in log_w]
    total = sum(w)
    weights = [x / total for x in w]
    return weights[:k], weights[k]
