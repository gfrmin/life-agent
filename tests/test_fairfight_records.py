"""``life_agent.fairfight.records`` — the OutcomeVector record.

Pure, no I/O: every axis is a separate field (no pre-combined score/utility/welfare —
only a downstream profile may weight them), JSONL round-trips exactly, and the four
vocabularies the record names (``arm``, ``cost_status``, ``status``, ``bucket``) fail
loudly at construction, mirroring ``core/outcomes.py``'s ``OutcomeEvent`` discipline.
"""
from __future__ import annotations

import json

import pytest

from life_agent.fairfight import records as R

# Every field the brief names, verbatim (also the drift gate — see
# test_every_axis_present_no_more_no_less).
_ALL_FIELDS = frozenset({
    "format_version", "run_id", "arm", "question_id", "answerable",
    "faithfulness", "completeness", "citation_fidelity",
    "bucket", "cause", "asserted", "asserted_correct", "asserted_distractor",
    "hallucinated", "declined", "correct_abstention", "over_abstention",
    "gold_in_topk", "gold_in_corpus", "gold_in_candidates", "distractor_in_topk",
    "n_retrieved",
    "probability", "p_none", "p_none_correct", "brier",
    "cost_usd", "cost_status", "in_tokens", "out_tokens", "cache_read_tokens",
    "cache_write_tokens", "latency_s", "model_tier_mix",
    "gather_rounds", "asks_issued", "tool_calls", "think_ticks",
    "answer_sha256", "answer_chars", "lineage_keys", "status", "notes",
})


def _vector(**overrides: object) -> R.OutcomeVector:
    base: dict = dict(
        format_version=R.FORMAT_VERSION,
        run_id="run-2026-07-11",
        arm="baseline",
        question_id="q-001",
        answerable=True,
        faithfulness=4,
        completeness=3,
        citation_fidelity=5,
        bucket="CORRECT",
        cause=None,
        asserted=True,
        asserted_correct=True,
        asserted_distractor=False,
        hallucinated=False,
        declined=False,
        correct_abstention=False,
        over_abstention=False,
        gold_in_topk=True,
        gold_in_corpus=True,
        gold_in_candidates=True,
        distractor_in_topk=False,
        n_retrieved=20,
        probability=0.87,
        p_none=0.05,
        p_none_correct=False,
        brier=0.02,
        cost_usd=0.0034,
        cost_status="measured",
        in_tokens=1200,
        out_tokens=340,
        cache_read_tokens=800,
        cache_write_tokens=0,
        latency_s=2.4,
        model_tier_mix={"sonnet": 2, "haiku": 1},
        gather_rounds=1,
        asks_issued=0,
        tool_calls=None,
        think_ticks=None,
        answer_sha256="a" * 64,
        answer_chars=128,
        lineage_keys=("key1", "key2"),
        status="ok",
        notes="",
    )
    base.update(overrides)
    return R.OutcomeVector(**base)  # type: ignore[arg-type]


# --- schema drift gate -------------------------------------------------------------

def test_every_axis_present_no_more_no_less() -> None:
    field_names = {f.name for f in __import__("dataclasses").fields(R.OutcomeVector)}
    assert field_names == _ALL_FIELDS


def test_no_pre_combined_scalar_field() -> None:
    forbidden_substrings = ("score", "utility", "welfare")
    field_names = {f.name for f in __import__("dataclasses").fields(R.OutcomeVector)}
    for name in field_names:
        for bad in forbidden_substrings:
            assert bad not in name.lower(), f"field {name!r} looks like a combined score"


# --- JSONL round-trip ----------------------------------------------------------------

def test_round_trip_via_json_dumps_loads() -> None:
    vec = _vector()
    payload = R.to_json(vec)
    line = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    obj = json.loads(line)
    got = R.from_json(obj)
    assert got == vec


def test_round_trip_preserves_none_axes() -> None:
    vec = _vector(
        faithfulness=None, completeness=None, citation_fidelity=None,
        cause=None, hallucinated=None, gold_in_candidates=None,
        probability=None, p_none=None, p_none_correct=None, brier=None,
        cost_usd=None, gather_rounds=None, tool_calls=None, think_ticks=None,
    )
    payload = R.to_json(vec)
    obj = json.loads(json.dumps(payload))
    got = R.from_json(obj)
    assert got == vec
    assert got.think_ticks is None


def test_lineage_keys_tuple_to_list_and_back() -> None:
    vec = _vector(lineage_keys=("a", "b", "c"))
    payload = R.to_json(vec)
    assert payload["lineage_keys"] == ["a", "b", "c"]
    assert isinstance(payload["lineage_keys"], list)
    got = R.from_json(payload)
    assert got.lineage_keys == ("a", "b", "c")
    assert isinstance(got.lineage_keys, tuple)


def test_model_tier_mix_dict_round_trips_and_is_not_aliased() -> None:
    mix = {"sonnet": 3, "haiku": 1}
    vec = _vector(model_tier_mix=mix)
    payload = R.to_json(vec)
    assert payload["model_tier_mix"] == {"sonnet": 3, "haiku": 1}
    payload["model_tier_mix"]["sonnet"] = 999
    assert vec.model_tier_mix == {"sonnet": 3, "haiku": 1}  # to_json didn't alias the field
    got = R.from_json(R.to_json(vec))
    got_mix = got.model_tier_mix
    got_mix["haiku"] = 999
    assert vec.model_tier_mix == {"sonnet": 3, "haiku": 1}  # from_json didn't alias the input


def test_empty_lineage_keys_round_trips() -> None:
    vec = _vector(lineage_keys=())
    got = R.from_json(R.to_json(vec))
    assert got.lineage_keys == ()


# --- closed vocabularies (construction-time validation) -------------------------------

def test_unknown_arm_rejected() -> None:
    with pytest.raises(ValueError, match="arm"):
        _vector(arm="freelancer")


def test_unknown_cost_status_rejected() -> None:
    with pytest.raises(ValueError, match="cost_status"):
        _vector(cost_status="approximate")


def test_unknown_status_rejected() -> None:
    with pytest.raises(ValueError, match="status"):
        _vector(status="crashed")


def test_unknown_bucket_rejected() -> None:
    with pytest.raises(ValueError, match="bucket"):
        _vector(bucket="MAYBE")


def test_all_declared_arms_construct() -> None:
    for arm in R.ARMS:
        _vector(arm=arm)


def test_all_declared_cost_statuses_construct() -> None:
    for status in R.COST_STATUSES:
        _vector(cost_status=status)


def test_all_declared_statuses_construct() -> None:
    for status in R.STATUSES:
        _vector(status=status)


def test_all_declared_buckets_construct() -> None:
    for bucket in R.BUCKETS:
        _vector(bucket=bucket)


def test_bucket_vocabulary_matches_triage_grading() -> None:
    # scripts/triage_grading.py is the canonical source (src/ must not import it, so this
    # is a manually-kept-in-sync drift check, not an import).
    assert frozenset(
        {"CORRECT", "CONFIDENT_WRONG", "RIGHTLY_WITHHELD", "WRONGLY_WITHHELD", "SCOPED"}
    ) == R.BUCKETS


# --- frozen / immutable ---------------------------------------------------------------

def test_outcome_vector_is_frozen() -> None:
    vec = _vector()
    with pytest.raises(AttributeError):
        vec.arm = "competitor"  # type: ignore[misc]


# --- scored: the ONE canonical status="ok" filter (final-review CRITICAL-2) -----------

def test_scored_filters_out_non_ok_status_dataclass_instances() -> None:
    ok1 = _vector(question_id="q-1", status="ok")
    err = _vector(question_id="q-2", status="error")
    timeout = _vector(question_id="q-3", status="timeout")
    ok2 = _vector(question_id="q-4", status="ok")
    out = R.scored([ok1, err, timeout, ok2])
    assert out == [ok1, ok2]


def test_scored_filters_out_non_ok_status_dicts() -> None:
    ok = R.to_json(_vector(question_id="q-1", status="ok"))
    err = R.to_json(_vector(question_id="q-2", status="error"))
    out = R.scored([ok, err])
    assert out == [ok]
    assert isinstance(out[0], dict)


def test_scored_empty_list_returns_empty_list() -> None:
    assert R.scored([]) == []


def test_scored_all_ok_returns_everything_in_order() -> None:
    vecs = [_vector(question_id=f"q-{i}", status="ok") for i in range(3)]
    assert R.scored(vecs) == vecs


def test_scored_all_excluded_returns_empty() -> None:
    vecs = [_vector(question_id="q-1", status="error"),
            _vector(question_id="q-2", status="timeout")]
    assert R.scored(vecs) == []


def test_external_arms_is_a_subset_of_arms_and_names_all_three() -> None:
    """Drift gate: every externally-driven arm must also be a declared arm (a vector with
    that arm name must construct); the hermes-driven set is a strict subset (the
    deliberative arm is claude-driven) — growing either means touching the constants
    deliberately."""
    assert R.EXTERNAL_ARMS <= R.ARMS
    assert frozenset({"competitor", "oracle", "deliberative"}) == R.EXTERNAL_ARMS
    assert frozenset({"competitor", "oracle"}) == R.HERMES_ARMS
    assert R.HERMES_ARMS < R.EXTERNAL_ARMS
    assert "baseline" not in R.EXTERNAL_ARMS
