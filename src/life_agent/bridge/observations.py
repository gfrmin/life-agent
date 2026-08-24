"""The parity boundary, Python side (move-2-design §1/§2).

The answer-brain daemon reasons over ABSTRACT observations — integers and floats: which candidate
index an observation reports, which ancestry group it belongs to, and its already-projected §4.1
covariates. Candidate identity (string canon) and group keying are *normalisation, not
inference*, so they stay here, on the body side. The brain never sees a candidate string.

This is the single source of that mapping: the bridge's ``extract`` (Move 3) calls it, so the
abstract form the brain consumes is provably the one the Stage-1 parity fixtures pin.
"""
from __future__ import annotations

from typing import Any

from life_agent.core.lookup import Observation, _candidate_key, candidates_from

# One observation reduced to numbers: the candidate index it reports, its ancestry-group index, and
# the already-projected reliability covariates. Matches credence `AnswerBrain.Obs` field-for-field
# — plus the two WIRE-ONLY correlation-key fields (r09 D1): `quote` (§5's cluster key) and
# `doc_key` (the artifact), which make a §5-deduped JOIN computable wherever the wire reaches.
# The daemon never sees them: `strip_wire_keys` removes them before any decide post.
AbstractObservation = dict[str, Any]

#: The wire-only fields — one spelling (r09 D1). Everything else in an abstract observation is
#: brain-facing.
WIRE_KEY_FIELDS: tuple[str, ...] = ("quote", "doc_key", "value_norm")


def strip_wire_keys(observations: list[AbstractObservation]) -> list[AbstractObservation]:
    """The parity boundary, enforced: drop the correlation-key fields so the brain stays
    string-blind. Pure; returns new dicts."""
    return [{k: v for k, v in o.items() if k not in WIRE_KEY_FIELDS} for o in observations]


def to_abstract_observations(
    observations: list[Observation],
) -> tuple[list[str], list[AbstractObservation]]:
    """Map grounded observations to ``(candidate display strings, abstract observations)``.

    ``candidates`` are the distinct values in first-seen order (display form = the first raw form;
    identity is the §4.2 canonical key, so date/number format and OCR variants of one value collapse
    to a single candidate while values with different significant digits never merge). Each abstract
    observation is pure numbers — ``{reports, group, authority, subject_factor, time_factor,
    competition_factor}`` — where ``reports`` is the 0-based index of the candidate it asserts and
    ``group`` is the 0-based first-seen index of its source document (chunks of one document share
    a group, driving the §4.2 ancestry temper). The covariates pass through verbatim; they are
    projected upstream (the probes; the competition factor at ``observe_hits``), not here.
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
                "competition_factor": o.competition_factor,
                # r09 D1 — the correlation key, wire-only (stripped before the brain).
                # value_norm rides too: C2's identity needs the observation's OWN normal
                # form (candidates[reports] breaks on OCR-variant candidates).
                "quote": o.quote,
                "doc_key": o.artifact_cache_key,
                "value_norm": o.value_norm,
            }
        )
    return candidates, abstract


def join_wire_observations(
    channel: list[AbstractObservation],
    probe: list[AbstractObservation],
    candidates: list[str],
) -> list[AbstractObservation]:
    """r09 D2 — the §5-deduped JOIN: pool the standing channel with a probe's observations
    and apply THE deployed rule (``lookup.dedup_drop_rows`` — called, never re-implemented).

    Groups re-derive from ``doc_key`` (C4): each distinct document is one group; an
    observation with no document of its own (a synthesised probe read) keeps its own fresh
    group, so it never collides with the base channel's first document — the defect the r07
    bound tolerated. An observation missing ``value_norm`` falls back to its candidate's
    normal form. Pure; returns new dicts in pooled order."""
    from life_agent.core.lookup import _norm_value, dedup_drop_rows

    pooled = [*channel, *probe]

    def _vn(o: AbstractObservation) -> str:
        if o.get("value_norm") is not None:
            return str(o["value_norm"])
        j = int(o.get("reports", -1))
        return _norm_value(candidates[j]) if 0 <= j < len(candidates) else ""

    def _cov(o: AbstractObservation) -> float:
        return (float(o.get("authority", 1.0)) * float(o.get("subject_factor", 1.0))
                * float(o.get("time_factor", 1.0)))

    rows = [(str(o.get("quote") or ""), str(o.get("doc_key") or ""), _vn(o), _cov(o))
            for o in pooled]
    drop = dedup_drop_rows(rows)
    group_order: dict[str, int] = {}
    out: list[AbstractObservation] = []
    for i, o in enumerate(pooled):
        if i in drop:
            continue
        gkey = str(o.get("doc_key") or "") or f"#anon:{i}"
        group_order.setdefault(gkey, len(group_order))
        out.append({**o, "group": group_order[gkey]})
    return out

