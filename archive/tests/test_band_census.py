"""Hermetic tests for r50's S2 census (`scripts/membrane/band_census.py`): the three frozen
candidate features, the X-only tercile bucketing rule, band membership read THROUGH the
harness's own `features_for` (`M-7`), the Beta(1,1) Beta-Binomial split-vs-pooled Bayes
factor, and S2's separation test. No engine, no ledger: every tick is synthetic.
"""
from __future__ import annotations

import math
import sys

import pytest

sys.path.insert(0, "scripts")

import membrane.band_census as BC
import membrane.p3_gate as P3

from life_agent.membrane import world as W


def _s(leader: float | None, *, runner: float = 0.0, p_none: float | None = 0.1,
       n_candidates: int = 2) -> W.DecideSummary:
    return W.DecideSummary(n_candidates=n_candidates, leader_credence=leader, p_none=p_none,
                           n_obs=1, era_split=False, owner_scoped=False, grow_pass=False,
                           runner_up_credence=runner)


def _tick(qid: str, leader: float | None, y: int, **kw: object) -> P3.KeyedTick:
    return P3.KeyedTick(question_id=qid, summary=_s(leader, **kw), y=y)  # type: ignore[arg-type]


# --- the three frozen candidates -----------------------------------------------------------


def test_candidate_list_is_the_frozen_one() -> None:
    assert BC.CANDIDATES == ("runner-up", "leader-share", "n-candidates-fine")


def test_runner_up_feature_is_the_summary_field() -> None:
    assert BC.feature_value("runner-up", _s(0.8, runner=0.15)) == 0.15


def test_leader_share_is_the_leaders_share_of_the_non_null_mass() -> None:
    assert BC.feature_value("leader-share", _s(0.6, p_none=0.25)) == pytest.approx(0.8)
    assert BC.feature_value("leader-share", _s(0.6, p_none=None)) == 0.6      # no p_none: leader
    assert BC.feature_value("leader-share", _s(None)) is None                 # no leader: none


def test_n_candidates_fine_caps_at_four() -> None:
    got = [BC.feature_value("n-candidates-fine", _s(0.8, n_candidates=k)) for k in (1, 2, 3, 4, 9)]
    assert got == [1, 2, 3, 4, 4]


# --- the X-only tercile rule ---------------------------------------------------------------


def test_tercile_edges_are_the_two_terciles_rounded_to_two_decimals() -> None:
    values = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
    e1, e2 = BC.tercile_edges(values)
    assert (e1, e2) == (0.23, 0.57)          # statistics.quantiles(n=3, exclusive), round(…, 2)


def test_cell_of_is_lt_mid_ge_with_a_structural_zero_cell_for_runner_up() -> None:
    edges = (0.1, 0.3)
    assert BC.cell_of("runner-up", 0.0, edges) == "none"          # fewer than two candidates
    assert BC.cell_of("runner-up", 0.05, edges) == "lt0.1"
    assert BC.cell_of("runner-up", 0.1, edges) == "0.1to0.3"      # lower edge inclusive
    assert BC.cell_of("runner-up", 0.3, edges) == "ge0.3"         # upper edge inclusive
    assert BC.cell_of("leader-share", 0.0, edges) == "lt0.1"     # zero is not structural here


def test_n_candidates_fine_cells_are_named_not_terciled() -> None:
    assert [BC.cell_of("n-candidates-fine", v, (0, 0)) for v in (1, 2, 3, 4)] \
        == ["1", "2", "3", "4plus"]


# --- band membership THROUGH the harness's own features_for (M-7) ---------------------------


def test_in_band_is_the_70_90_leader_credence_cells_of_features_for() -> None:
    assert BC.in_band(_s(0.7)) and BC.in_band(_s(0.85)) and BC.in_band(_s(0.8999))
    assert not BC.in_band(_s(0.69)) and not BC.in_band(_s(0.9)) and not BC.in_band(_s(None))


# --- the Beta(1,1) split-vs-pooled Bayes factor ---------------------------------------------


def test_log_bayes_factor_matches_the_closed_form_on_a_small_case() -> None:
    # cells (2 of 2) and (0 of 2) vs pooled (2 of 4):
    #   split  = lbeta(3,1) + lbeta(1,3) = 2·ln(1/3);  pooled = lbeta(3,3) = ln(1/30)
    cells = [BC.CellStat("a", n=2, correct=2), BC.CellStat("b", n=2, correct=0)]
    assert BC.log_bayes_factor(cells) == pytest.approx(2 * math.log(1 / 3) - math.log(1 / 30))


def test_an_uninformative_split_is_penalised_and_a_sharp_one_rewarded() -> None:
    same = [BC.CellStat("a", n=20, correct=16), BC.CellStat("b", n=20, correct=16)]
    sharp = [BC.CellStat("a", n=20, correct=20), BC.CellStat("b", n=20, correct=10)]
    assert BC.log_bayes_factor(same) < 0
    assert math.exp(BC.log_bayes_factor(sharp)) > 10


# --- S2's separation test -----------------------------------------------------------------


def test_separates_needs_ten_row_cells_on_both_sides_of_the_break_even_and_bf_ten() -> None:
    be = 0.8369
    both_sides = [BC.CellStat("lo", n=20, correct=12), BC.CellStat("hi", n=20, correct=20)]
    assert BC.separates(both_sides, break_even=be)
    thin = [BC.CellStat("lo", n=9, correct=4), BC.CellStat("hi", n=40, correct=39)]
    assert not BC.separates(thin, break_even=be)                 # the low cell is under 10
    one_side = [BC.CellStat("a", n=20, correct=19), BC.CellStat("b", n=20, correct=20)]
    assert not BC.separates(one_side, break_even=be)             # nothing at or below 0.8369


# --- the census over keyed ticks: edges from ALL ticks, cells from the BAND only ------------


def _corpus() -> list[P3.KeyedTick]:
    ticks: list[P3.KeyedTick] = []
    # 20 band rows with a competitor (runner 0.25) that are wrong half the time …
    for i in range(20):
        ticks.append(_tick(f"q{i}", 0.8, 1 if i % 2 else 0, runner=0.25))
    # … 20 band rows at the SAME leader without one that are always right (so only the
    # runner-up, not the leader or its share, can tell the two groups apart) …
    for i in range(20, 40):
        ticks.append(_tick(f"q{i}", 0.8, 1, runner=0.0))
    # … and 20 out-of-band rows that must not enter the cells but do enter the edges
    for i in range(40, 60):
        ticks.append(_tick(f"q{i}", 0.95, 1, runner=0.5))
    return ticks


def test_census_edges_use_every_tick_and_cells_only_the_band() -> None:
    out = BC.census(_corpus(), break_even=0.8369)
    assert out["band_n"] == 40
    ru = out["candidates"]["runner-up"]
    assert ru["edges"] == BC.tercile_edges([0.25] * 20 + [0.0] * 20 + [0.5] * 20)
    assert sum(c["n"] for c in ru["cells"]) == 40                # out-of-band rows excluded


def test_census_names_the_separating_candidate_and_kills_when_none_does() -> None:
    out = BC.census(_corpus(), break_even=0.8369)
    assert out["candidates"]["runner-up"]["separates"] is True
    assert out["winner"] == "runner-up"
    flat = [_tick(f"q{i}", 0.8, 1 if i % 5 else 0, runner=0.0) for i in range(40)]
    dead = BC.census(flat, break_even=0.8369)
    assert dead["winner"] is None and dead["verdict"] == "KILL"


def test_census_winner_is_the_separating_candidate_with_the_largest_bayes_factor() -> None:
    # three band groups: A wrong with a competitor; B right without one; C right without one
    # but at a higher leader-share (p_none 0.4). `runner-up` splits {A} vs {B, C}: perfectly.
    # `leader-share` splits {A, B} vs {C}: it separates too (0.5 vs 1.0), but with a smaller
    # Bayes factor because B dilutes its low cell. The winner must be the LARGER factor.
    ticks: list[P3.KeyedTick] = []
    ticks += [_tick(f"a{i}", 0.8, 0, runner=0.25, p_none=0.1) for i in range(20)]
    ticks += [_tick(f"b{i}", 0.8, 1, runner=0.0, p_none=0.1) for i in range(20)]
    ticks += [_tick(f"c{i}", 0.8, 1, runner=0.0, p_none=0.4) for i in range(20)]
    out = BC.census(ticks, break_even=0.8369)
    ru, ls = out["candidates"]["runner-up"], out["candidates"]["leader-share"]
    assert ru["separates"] and ls["separates"]
    assert ru["log_bf"] > ls["log_bf"]
    assert out["winner"] == "runner-up"
