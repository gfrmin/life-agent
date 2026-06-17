"""Hermetic tests for the parity boundary (move-2-design §2/§7).

``to_abstract_observations`` is the Python side of the answer-brain's parity cut: grounded
observations → the abstract integer/float form the credence brain reasons over. These pin its
contract (candidate indexing, ancestry grouping, identity collapse, covariate pass-through)
without a model or a corpus — the same mapping the Stage-1 parity fixtures were generated through.
"""
from __future__ import annotations

from life_agent.bridge.observations import to_abstract_observations
from life_agent.core.lookup import Observation


def _obs(
    value_raw: str,
    artifact_key: str,
    *,
    authority: float = 0.9,
    subject_factor: float = 1.0,
    time_factor: float = 1.0,
) -> Observation:
    return Observation(
        card_n=1,
        artifact_cache_key=artifact_key,
        obs_cache_key=f"obs_{value_raw}_{artifact_key}",
        value_raw=value_raw,
        value_norm=" ".join(value_raw.split()).casefold(),
        quote="",
        authority_class="synthetic",
        authority=authority,
        subject_factor=subject_factor,
        time_factor=time_factor,
    )


def test_distinct_values_become_indexed_candidates() -> None:
    candidates, abstract = to_abstract_observations([_obs("Alpha", "d0"), _obs("Bravo", "d1")])
    assert candidates == ["Alpha", "Bravo"]
    assert [a["reports"] for a in abstract] == [0, 1]
    assert [a["group"] for a in abstract] == [0, 1]


def test_same_document_shares_one_ancestry_group() -> None:
    candidates, abstract = to_abstract_observations([_obs("Alpha", "d0"), _obs("Alpha", "d0")])
    assert candidates == ["Alpha"]
    assert [a["reports"] for a in abstract] == [0, 0]
    assert [a["group"] for a in abstract] == [0, 0]  # one group → the §4.2 ancestry temper


def test_group_index_is_first_seen_order() -> None:
    # Groups are keyed by first appearance, not lexical order of the artifact key.
    _candidates, abstract = to_abstract_observations(
        [_obs("X", "d9"), _obs("Y", "d1"), _obs("Z", "d9")]
    )
    assert [a["group"] for a in abstract] == [0, 1, 0]


def test_date_format_variants_collapse_to_one_candidate() -> None:
    # _candidate_key keys an unambiguous date on its ISO form, so two spellings are one candidate;
    # display is the first raw form, and both observations report index 0.
    candidates, abstract = to_abstract_observations(
        [_obs("2024-03-05", "d0"), _obs("March 5, 2024", "d1")]
    )
    assert candidates == ["2024-03-05"]
    assert [a["reports"] for a in abstract] == [0, 0]
    assert [a["group"] for a in abstract] == [0, 1]


def test_distinct_dates_stay_separate_candidates() -> None:
    candidates, abstract = to_abstract_observations(
        [_obs("2024-03-05", "d0"), _obs("2024-03-06", "d1")]
    )
    assert candidates == ["2024-03-05", "2024-03-06"]
    assert [a["reports"] for a in abstract] == [0, 1]


def test_covariates_pass_through_verbatim() -> None:
    _candidates, abstract = to_abstract_observations(
        [_obs("Alpha", "d0", authority=0.95, subject_factor=0.05, time_factor=0.30)]
    )
    assert abstract[0]["authority"] == 0.95
    assert abstract[0]["subject_factor"] == 0.05
    assert abstract[0]["time_factor"] == 0.30


def test_empty_observations_yield_empty_mapping() -> None:
    candidates, abstract = to_abstract_observations([])
    assert candidates == []
    assert abstract == []
