"""The candidate posterior (core/posterior.py): its closed forms, and the replay pin that
holds the port to the Julia answer-brain it replaces."""
from __future__ import annotations

import hashlib
import math
import os
import sys
from pathlib import Path

import pytest

from life_agent.core import posterior as P
from life_agent.core.pricing import A_ALTERNATIVES, P_NONE_PRIOR

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from eval import replay  # noqa: E402


def _obs(reports: int, group: int, authority: float = 1.0, **kw: float) -> dict[str, float]:
    return {"reports": reports, "group": group, "authority": authority,
            "subject_factor": kw.get("subject", 1.0), "time_factor": kw.get("time", 1.0),
            "competition_factor": kw.get("competition", 1.0)}


def test_no_observation_leaves_the_prior() -> None:
    cred, p_none = P.candidate_posterior(4, [], rho=0.8)
    assert p_none == pytest.approx(P_NONE_PRIOR)
    assert cred == pytest.approx([(1 - P_NONE_PRIOR) / 4] * 4)


def test_one_observation_matches_the_closed_form() -> None:
    k, r = 3, 0.6
    cred, p_none = P.candidate_posterior(k, [_obs(1, 0)], rho=r)
    hit, miss = r + (1 - r) / A_ALTERNATIVES, (1 - r) / A_ALTERNATIVES
    z = (1 - P_NONE_PRIOR) / k * (hit + 2 * miss) + P_NONE_PRIOR * miss
    assert cred[1] == pytest.approx((1 - P_NONE_PRIOR) / k * hit / z)
    assert cred[0] == cred[2] == pytest.approx((1 - P_NONE_PRIOR) / k * miss / z)
    assert p_none == pytest.approx(P_NONE_PRIOR * miss / z)


def test_the_temper_counts_chunks_and_documents_below_their_number() -> None:
    assert P.temper_scales([7]) == [1.0]
    assert P.temper_scales([0, 0]) == pytest.approx([0.65, 0.65])      # (1 + 0.3) / 2
    assert P.temper_scales([0, 1]) == pytest.approx([0.85, 0.85])      # (1 + 0.7) / 2
    assert P.temper_scales([]) == []


def test_every_covariate_scales_reliability() -> None:
    o = _obs(0, 0, authority=0.5, subject=0.5, time=0.5, competition=0.5)
    assert P.reliability(0.8, o) == pytest.approx(0.8 / 16)
    del o["competition_factor"]  # an older bridge omits it: uncontested
    assert P.reliability(0.8, o) == pytest.approx(0.8 / 8)


def test_agreeing_reports_raise_the_leader_and_lower_none() -> None:
    one, none_one = P.candidate_posterior(2, [_obs(0, 0)], rho=0.7)
    two, none_two = P.candidate_posterior(2, [_obs(0, 0), _obs(0, 1)], rho=0.7)
    assert two[0] > one[0] and none_two < none_one
    assert math.fsum(two) + none_two == pytest.approx(1.0)


def test_no_candidates_is_refused() -> None:
    with pytest.raises(ValueError):
        P.candidate_posterior(0, [], rho=0.5)


# --- the replay pin ------------------------------------------------------------------------

# m5-base: 104 questions recorded through the executor loop on 2026-08-26, 605 /decide calls
# answered by the Julia daemon (credence 0.105.2). Pinned by its manifest's sha256.
_M5_BASE = "eval/collapse-fixtures/m5-base"
_M5_MANIFEST_SHA = "8b5a64653804bd4d747cd9b5b7aacf814c57155f18c3e135924bfea5cd152fad"
_M5_DECIDES = 605
# Julia's own log/exp round differently from the C library's in the last ulp: 447 of the 605
# replay bit-for-bit, the rest within 5.6e-16. The tolerance is that measured residue.
_TOL = 1e-15


def test_the_port_replays_the_julia_daemon_on_m5_base() -> None:
    kb = os.environ.get("LIFE_AGENT_KB")
    directory = Path(kb or "/nonexistent") / _M5_BASE
    if not (directory / "manifest.json").is_file():
        pytest.skip("needs the owner's KB ($LIFE_AGENT_KB with the m5-base collapse fixtures); "
                    "owner data, not buildable")
    sha = hashlib.sha256((directory / "manifest.json").read_bytes()).hexdigest()
    assert sha == _M5_MANIFEST_SHA, "the m5-base fixture set changed; re-pin deliberately"
    fixtures = [fx for fx in replay.read_all(directory) if fx.trace == "A-loop"]
    n = 0
    for fid, payload, resp in replay.http_exchanges(fixtures, "/decide"):
        k = len(payload["candidates"])
        cred, p_none = P.candidate_posterior(k, payload["observations"], payload["rho"])
        want = [*resp["credences"], resp["p_none"]]
        got = [*cred, p_none]
        assert max(abs(a - b) for a, b in zip(got, want, strict=True)) <= _TOL, fid
        assert got.index(max(got)) == want.index(max(want)), fid
        n += 1
    assert n == _M5_DECIDES
