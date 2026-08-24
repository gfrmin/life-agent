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


# ── The keystone: the corroborate re-read carries recency (no transform reports stale as
# current) ──
from life_agent.bridge import server as SRV  # noqa: E402
from life_agent.core.joint_extract import JointResult  # noqa: E402


def _jr(value: str | None, as_of: str | None = None) -> JointResult:
    return JointResult(value=value, confidence=0.9, as_of=as_of)


def _hit(key: str, text: str) -> dict:
    return {"artifact_cache_key": key, "chunk_text": text}


def _p(time_indexed: bool, construct: str | None, doc_date: dict, today: str) -> dict:
    return {"time_indexed": time_indexed, "construct": construct, "today": today,
            "covariates": {"doc_date": doc_date}}


def test_corroborate_time_factor_attenuates_a_stale_source() -> None:
    # a re-read value whose only SOURCE doc is old must decay (the q-006 confident-stale bug):
    # address half-life 7y, source dated 14y back ⇒ 0.5^(14/7) = 0.25, NOT 1.0.
    jr = _jr("old st")
    hits = [_hit("d0", "i live at old st now")]
    tf = SRV._corroborate_time_factor(
        jr, hits, _p(True, "address", {"d0": "2010-01-01"}, "2024-01-01"))
    assert tf < 0.3


def test_corroborate_time_factor_keeps_a_fresh_source_current() -> None:
    jr = _jr("new ave")
    hits = [_hit("d0", "moved to new ave")]
    tf = SRV._corroborate_time_factor(
        jr, hits, _p(True, "address", {"d0": "2023-09-01"}, "2024-01-01"))
    assert tf > 0.9


def test_corroborate_time_factor_takes_the_freshest_attestation() -> None:
    # the value is attested in BOTH a stale and a recent doc ⇒ as current as its freshest source.
    jr = _jr("main rd")
    hits = [_hit("old", "main rd"), _hit("new", "main rd")]
    p = _p(True, "address", {"old": "2008-01-01", "new": "2023-09-01"}, "2024-01-01")
    assert SRV._corroborate_time_factor(jr, hits, p) > 0.9


def test_corroborate_time_factor_undated_source_attenuates_to_unknown() -> None:
    # value present but its source is undated under a time-indexed construct ⇒ _A_TIME_UNKNOWN.
    from life_agent.core.lookup import _A_TIME_UNKNOWN
    jr = _jr("somewhere")
    hits = [_hit("d0", "somewhere")]
    tf = SRV._corroborate_time_factor(jr, hits, _p(True, "address", {}, "2024-01-01"))
    assert tf == _A_TIME_UNKNOWN


def test_corroborate_time_factor_passes_through_a_permanent_construct() -> None:
    # a non-time-indexed construct (a DOB/id) never decays — 1.0 regardless of source age.
    jr = _jr("12345")
    hits = [_hit("d0", "id 12345")]
    tf = SRV._corroborate_time_factor(
        jr, hits, _p(False, "date_of_birth", {"d0": "2008-01-01"}, "2024-01-01"))
    assert tf == 1.0


def test_competition_factor_rides_the_abstract_observation() -> None:
    # §4.2's competing-values temper (foundations §14, 2026-08-17): the factor is
    # projected at observe_hits and passes through the parity boundary verbatim —
    # the daemon's r product is the only consumer.
    import dataclasses

    competed = dataclasses.replace(_obs("Alpha", "d0"), n_competing=1,
                                   competition_factor=0.5)
    _candidates, abstract = to_abstract_observations([competed, _obs("Bravo", "d1")])
    assert [a["competition_factor"] for a in abstract] == [0.5, 1.0]


# --- r09 D1: the correlation key on the wire -------------------------------------------------


def test_abstract_observations_carry_the_correlation_key() -> None:
    """r09 D1: every wire observation carries the §5 dedup key — the grounding quote and the
    document key — so a §5-deduped JOIN is computable wherever the wire reaches. The daemon
    never sees these fields (the executor strips them; its own test pins that)."""
    o = _obs("Alpha", "d0")
    o = __import__("dataclasses").replace(o, quote="the alpha value is Alpha per the form")
    _candidates, abstract = to_abstract_observations([o])
    assert abstract[0]["quote"] == "the alpha value is Alpha per the form"
    assert abstract[0]["doc_key"] == "d0"
    assert abstract[0]["value_norm"] == "alpha"  # C2's identity needs the observation's own
    # normal form: deriving it from candidates[reports] breaks on OCR-variant candidates


def test_strip_wire_keys_removes_exactly_the_key_fields() -> None:
    """r09 D1: the parity boundary holds — the brain stays string-blind. One helper, one
    spelling of which fields are wire-only."""
    from life_agent.bridge.observations import strip_wire_keys
    stripped = strip_wire_keys([{"reports": 0, "group": 0, "authority": 0.9,
                                 "subject_factor": 1.0, "time_factor": 1.0,
                                 "competition_factor": 1.0,
                                 "quote": "q", "doc_key": "d0", "value_norm": "v"}])
    assert stripped == [{"reports": 0, "group": 0, "authority": 0.9,
                         "subject_factor": 1.0, "time_factor": 1.0,
                         "competition_factor": 1.0}]


# --- r09 D2: the §5-deduped JOIN, one rule ----------------------------------------------------


def _wire(value: str, doc: str, *, quote: str, authority: float = 0.9,
          reports: int = 0, group: int = 0) -> dict:
    return {"reports": reports, "group": group, "authority": authority,
            "subject_factor": 1.0, "time_factor": 1.0, "competition_factor": 1.0,
            "quote": quote, "doc_key": doc,
            "value_norm": " ".join(value.split()).casefold()}


def test_wire_join_applies_the_deployed_dedup_rule_identically() -> None:
    """C2 — one rule. The wire join and `dedup_correlated` keep IDENTICAL survivors on
    parallel inputs: a contextual quote duplicated across two documents collapses to the
    max-covariate document's copy; the distinct-quote observation survives."""
    import dataclasses

    from life_agent.bridge.observations import join_wire_observations
    from life_agent.core.lookup import dedup_correlated

    dup_quote = "as attested, the alpha value is Alpha for the record"
    objs = [
        dataclasses.replace(_obs("Alpha", "d0", authority=0.9), quote=dup_quote),
        dataclasses.replace(_obs("Alpha", "d1", authority=0.5), quote=dup_quote),
        dataclasses.replace(_obs("Bravo", "d2"), quote="a different grounding entirely"),
    ]
    survivors = dedup_correlated(objs)
    assert [(o.value_raw, o.artifact_cache_key) for o in survivors] == [
        ("Alpha", "d0"), ("Bravo", "d2")]

    wire = [_wire("Alpha", "d0", quote=dup_quote, authority=0.9, reports=0),
            _wire("Alpha", "d1", quote=dup_quote, authority=0.5, reports=0),
            _wire("Bravo", "d2", quote="a different grounding entirely", reports=1)]
    joined = join_wire_observations(wire, [], ["Alpha", "Bravo"])
    assert [(o["value_norm"], o["doc_key"]) for o in joined] == [
        ("alpha", "d0"), ("bravo", "d2")]


def test_wire_join_never_lowers_the_channel() -> None:
    """C3 — the checkpoint's reason to exist: pooling an EMPTY probe reply (a null or a
    value-outside-the-lattice disagree) keeps every channel observation."""
    from life_agent.bridge.observations import join_wire_observations

    channel = [_wire("Alpha", "d0", quote="ctx one alpha"),
               _wire("Alpha", "d1", quote="ctx two alpha")]
    joined = join_wire_observations(channel, [], ["Alpha"])
    assert len(joined) == len(channel)


def test_wire_join_reindexes_groups_by_doc_key() -> None:
    """C4 — the bound's group-0 collision, killed: a probe observation with no document of
    its own gets a FRESH group, never the base channel's first; base groups re-derive from
    doc_key so two chunks of one document stay one group."""
    from life_agent.bridge.observations import join_wire_observations

    channel = [_wire("Alpha", "d0", quote="ctx a"),
               _wire("Beta", "d0", quote="ctx b"),   # a DIFFERENT value: A1 collapses same-value
               _wire("Alpha", "d1", quote="ctx c")]
    probe = [{"reports": 0, "group": 0, "authority": 1.0, "subject_factor": 1.0,
              "time_factor": 1.0, "competition_factor": 1.0,
              "quote": "", "doc_key": "", "value_norm": "alpha"}]
    joined = join_wire_observations(channel, probe, ["Alpha"])
    groups = [o["group"] for o in joined]
    assert groups[0] == groups[1] == 0      # one document, one group
    assert groups[2] == 1                   # the second document
    assert groups[3] == 2                   # the synthesised read: its own fresh group


def test_wire_join_value_only_quotes_never_cluster() -> None:
    """§5's value-only exemption survives the wire: two documents sharing only the bare value
    (no surrounding context) are genuine corroboration, not copies — both kept."""
    from life_agent.bridge.observations import join_wire_observations

    channel = [_wire("Alpha", "d0", quote="Alpha"),
               _wire("Alpha", "d1", quote="Alpha")]
    joined = join_wire_observations(channel, [], ["Alpha"])
    assert len(joined) == 2
