"""The parity boundary, Python side (move-2-design §1/§2).

The answer-brain daemon reasons over ABSTRACT observations — integers and floats: which candidate
index an observation reports, which ancestry group it belongs to, and its already-projected §4.1
covariates. Candidate identity (string canon) and group keying are *normalisation, not
inference*, so they stay here, on the body side. The brain never sees a candidate string.

This is the single source of that mapping: the bridge's ``extract`` (Move 3) and the parity-fixture
oracle (``scripts/dump_parity_fixtures.py``) both call it, so the abstract form the brain
consumes is provably the one the Stage-1 parity fixtures pin.
"""
from __future__ import annotations

from typing import Any

from life_agent.core.lookup import Observation, _candidate_key, candidates_from

# One observation reduced to numbers: the candidate index it reports, its ancestry-group index, and
# the already-projected reliability covariates. Matches credence `AnswerBrain.Obs` field-for-field.
AbstractObservation = dict[str, Any]


def to_abstract_observations(
    observations: list[Observation],
) -> tuple[list[str], list[AbstractObservation]]:
    """Map grounded observations to ``(candidate display strings, abstract observations)``.

    ``candidates`` are the distinct values in first-seen order (display form = the first raw form;
    identity is the §4.2 canonical key, so date/number format and OCR variants of one value collapse
    to a single candidate while values with different significant digits never merge). Each abstract
    observation is pure numbers — ``{reports, group, authority, subject_factor, time_factor}`` —
    where ``reports`` is the 0-based index of the candidate it asserts and ``group`` is the 0-based
    first-seen index of its source document (chunks of one document share a group, driving the §4.2
    ancestry temper). The covariates pass through verbatim; they are projected upstream (the
    probes), not here.
    """
    candidates = candidates_from(observations)
    cand_index = {_candidate_key(c): j for j, c in enumerate(candidates)}
    group_order: dict[str, int] = {}
    abstract: list[AbstractObservation] = []
    for o in observations:
        group_order.setdefault(o.artifact_cache_key, len(group_order))
        abstract.append(
            {
                "reports": cand_index[_candidate_key(o.value_raw)],
                "group": group_order[o.artifact_cache_key],
                "authority": o.authority,
                "subject_factor": o.subject_factor,
                "time_factor": o.time_factor,
            }
        )
    return candidates, abstract
