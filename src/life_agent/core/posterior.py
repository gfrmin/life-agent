"""The candidate posterior: K retrieved candidates + NONE, conditioned on the extractions.

The belief every answer is decided on. The truth is one of the K candidates the extractor
reported, or NONE ("not among the retrieved"). The prior puts ``P_NONE_PRIOR`` on NONE and
spreads the rest uniformly. Each observation is a noisy report of one candidate: with
reliability ``r = rho · authority · subject · time · competition`` it names the truth, and
otherwise it names one of ``A_ALTERNATIVES`` wrong values at random. Correlated reports are
tempered: ``m`` chunks of one document count as ``1 + β_anc·(m-1)`` observations, and ``G``
documents read by the one extractor count as ``1 + β_mod·(G-1)``.

Pure functions over the ``/decide`` wire observations (``reports``, ``group``, ``authority``,
``subject_factor``, ``time_factor``, optional ``competition_factor``). The arithmetic follows
credence's ``answer_brain.jl`` step for step (log weights renormalised after every
condition), which the replay pin in ``tests/test_posterior.py`` holds it to. This module
ranks nothing: the act is proplang's.
"""
from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from life_agent.core.pricing import (
    A_ALTERNATIVES,
    BETA_ANCESTRY,
    BETA_MODEL,
    P_NONE_PRIOR,
    PROB_EPS,
)


def temper_scales(groups: Sequence[int]) -> list[float]:
    """Per observation, the exponent its log-likelihood is scaled by; 1.0 for a lone one."""
    counts = Counter(groups)
    n_groups = len(counts)
    s_mod = 1.0 if n_groups == 0 else (1.0 + BETA_MODEL * (n_groups - 1)) / n_groups
    return [(1.0 + BETA_ANCESTRY * (counts[g] - 1)) / counts[g] * s_mod for g in groups]


def reliability(rho: float, obs: Mapping[str, Any]) -> float:
    """The chance this observation names the truth."""
    return float(rho * obs["authority"] * obs["subject_factor"] * obs["time_factor"]
                 * obs.get("competition_factor", 1.0))


def log_match_miss(r: float, scale: float) -> tuple[float, float]:
    """The tempered log-likelihood of a report under the hypothesis it names, and under any
    other hypothesis (NONE included)."""
    return (scale * math.log(max(r + (1.0 - r) / A_ALTERNATIVES, PROB_EPS)),
            scale * math.log(max((1.0 - r) / A_ALTERNATIVES, PROB_EPS)))


def _normalised(log_w: Sequence[float]) -> list[float]:
    top = max(log_w)
    log_total = top + math.log(sum(math.exp(x - top) for x in log_w))
    return [x - log_total for x in log_w]


def log_posterior(k: int, observations: Sequence[Mapping[str, Any]],
                  rho: float) -> list[float]:
    """Normalised log weights over candidates ``0..k-1`` then NONE, in observation order."""
    if k < 1:
        raise ValueError("the posterior needs at least one candidate")
    log_w = _normalised([math.log((1.0 - P_NONE_PRIOR) / k)] * k + [math.log(P_NONE_PRIOR)])
    for obs, scale in zip(observations, temper_scales([o["group"] for o in observations]),
                          strict=True):
        match, miss = log_match_miss(reliability(rho, obs), scale)
        hit = obs["reports"]
        log_w = _normalised([w + (match if h == hit else miss) for h, w in enumerate(log_w)])
    return log_w


def candidate_posterior(k: int, observations: Sequence[Mapping[str, Any]],
                        rho: float) -> tuple[list[float], float]:
    """``(credences, p_none)``: the candidates' posterior mass in candidate order, and NONE's."""
    log_w = log_posterior(k, observations, rho)
    top = max(log_w)
    w = [math.exp(x - top) for x in log_w]
    total = sum(w)
    weights = [x / total for x in w]
    return weights[:k], weights[k]
