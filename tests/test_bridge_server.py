"""Hermetic contract tests for the capability bridge (move-3-design §2/§7).

The bridge is a stateless JSON-over-HTTP service wrapping life-agent's body-side reads. These
pin its contract WITHOUT a model or a live corpus: the seams (`route_question`, `observe_hits`,
the probes, `retrieve_set`, the utility u_bar) are monkeypatched, so each test exercises only
the bridge's parse / dispatch / serialise — never a second implementation of a read.

Three obligations beyond shape (§1 proof obligation):
- the single-source assertion: `/extract` returns *precisely* ``to_abstract_observations``'s
  output (the brain stays string-blind) — the endpoint and the function meet one assertion;
- 400-on-malformed + 404 + `/ready`, proven over real loopback HTTP;
- statelessness: an interleaved request cannot perturb a repeat.
"""
from __future__ import annotations

import dataclasses
import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from life_agent.bridge import server as bridge_server
from life_agent.bridge.observations import to_abstract_observations
from life_agent.bridge.server import BridgeDeps, BridgeServer, dispatch
from life_agent.core import config
from life_agent.core import decisions as DEC
from life_agent.core import lookup as LK
from life_agent.core import probes as P
from life_agent.core import reactions as RX
from life_agent.core import retrieval as RET
from life_agent.core.lookup import Observation

# --- fixtures: fake deps + a dispatch helper ------------------------------------------

@pytest.fixture
def deps(tmp_path: Path) -> BridgeDeps:
    """The warm handles, all sentinels — the seams that would use them are monkeypatched,
    so the bridge only passes them through. ``profile``/``u_bar`` are the server-side PII the
    body never sends (move-3 §3); ``decisions_path`` is a tmp calibration log so /log_decision
    never touches the real KB; ``fold_version`` is a fixed sentinel."""
    return BridgeDeps(
        root=Path("/fake/root"),
        conn=object(),               # sentinel; retrieval/probes patched
        client=object(),             # sentinel; route/observe/subject patched
        profile="I am the owner; my name is Synthetic Owner.",
        u_bar=lambda: {"u_correct": 1.0, "u_wrong": -5.0, "u_hedged": 0.2,
                       "u_abstain": 0.0, "oracle_p": 0.9, "lambda_int": 0.1,
                       "kappa_att": 0.0},
        decisions_path=tmp_path / "decisions.jsonl",
        reactions_path=tmp_path / "reactions.jsonl",
        fold_version=lambda: "fold-test-v1",
        gather_outcomes_path=tmp_path / "gather_outcomes.jsonl",
    )


def _call(deps: BridgeDeps, method: str, path: str,
          body: dict[str, Any] | None = None) -> tuple[int, Any]:
    raw = json.dumps(body).encode("utf-8") if body is not None else b""
    return dispatch(deps, method, path, raw)


def _obs(value: str, key: str, *, authority: float = 0.9,
         subject_factor: float = 1.0, time_factor: float = 1.0) -> Observation:
    return Observation(
        card_n=1, artifact_cache_key=key, obs_cache_key=f"obs_{value}_{key}",
        value_raw=value, value_norm=" ".join(value.split()).casefold(), quote="",
        authority_class="synthetic", authority=authority,
        subject_factor=subject_factor, time_factor=time_factor,
    )


# --- /route ----------------------------------------------------------------------------

def test_route_returns_construct_and_time_indexed(deps: BridgeDeps,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(LK, "route_question",
                        lambda root, q, **k: LK.Route(construct="phone number",
                                                      time_indexed=True))
    status, payload = _call(deps, "POST", "/route", {"question": "my mobile?"})
    assert status == 200
    assert payload == {"construct": "phone number", "time_indexed": True}


def test_route_none_is_json_null_the_narrative_path(deps: BridgeDeps,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    # route_question returns None for a non-typed-lookup question → the brain's narrative case.
    monkeypatch.setattr(LK, "route_question", lambda root, q, **k: None)
    status, payload = _call(deps, "POST", "/route", {"question": "tell me about my week"})
    assert status == 200
    assert payload is None


# --- /retrieve -------------------------------------------------------------------------

def test_retrieve_builds_query_from_terms_and_returns_hits(
        deps: BridgeDeps, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def fake_retrieve_set(conn: Any, query: str, k: int) -> list[dict[str, Any]]:
        seen["query"], seen["k"] = query, k
        return [{"artifact_cache_key": "a0", "chunk_text": "…", "score": 1.0, "origin": "o"}]

    monkeypatch.setattr(RET, "retrieve_set", fake_retrieve_set)
    status, payload = _call(deps, "POST", "/retrieve",
                            {"question": "mobile number", "terms": "phone cell", "k": 5})
    assert status == 200
    assert payload["hits"][0]["artifact_cache_key"] == "a0"
    # expansion is an INPUT: the body supplies terms, the bridge only composes the query.
    assert seen["query"] == "mobile number phone cell"
    assert seen["k"] == 5


def test_retrieve_without_terms_uses_raw_question(
        deps: BridgeDeps, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}
    monkeypatch.setattr(RET, "retrieve_set",
                        lambda conn, query, k: seen.update(query=query) or [])
    _call(deps, "POST", "/retrieve", {"question": "am i a contractor?"})
    assert seen["query"] == "am i a contractor?"


# --- /extract: the single-source (brain-blindness) assertion ---------------------------

def test_extract_is_exactly_to_abstract_observations(
        deps: BridgeDeps, monkeypatch: pytest.MonkeyPatch) -> None:
    # observe_hits is the model edge; with it fixed, /extract must return PRECISELY the abstract
    # form to_abstract_observations produces — the daemon (Move 2) consumes this verbatim.
    observations = [_obs("Alpha", "d0", authority=0.95, time_factor=0.3),
                    _obs("Bravo", "d1", subject_factor=0.05),
                    _obs("Alpha", "d0")]
    monkeypatch.setattr(LK, "observe_hits", lambda *a, **k: (observations, 2))
    monkeypatch.setattr(LK, "extractor_reliability_mean", lambda *a, **k: 0.7)

    status, payload = _call(deps, "POST", "/extract",
                            {"question": "q", "hits": [{"chunk_text": "x"}]})
    exp_candidates, exp_abstract = to_abstract_observations(observations)
    assert status == 200
    assert payload["candidates"] == exp_candidates
    assert payload["observations"] == exp_abstract          # the brain stays string-blind
    assert payload["rho"] == 0.7
    assert payload["indeterminate"] == 2                    # ⊥/ungrounded count, never dropped


def test_extract_threads_covariates_and_time_indexed_into_observe(
        deps: BridgeDeps, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def fake_observe(root: Any, q: str, hits: list[dict[str, Any]], *, client: Any,
                     covariates: LK.HitCovariates, time_indexed: bool, today: Any,
                     half_life_years: float = 5.0,
                     meter: list[float] | None = None) -> tuple[list[Observation], int]:
        seen["cov"], seen["time_indexed"], seen["today"] = covariates, time_indexed, today
        seen["half_life_years"] = half_life_years
        if meter is not None:
            meter.append(0.002)  # a cache-miss call's realised spend
        return [], 0

    monkeypatch.setattr(LK, "observe_hits", fake_observe)
    monkeypatch.setattr(LK, "extractor_reliability_mean", lambda *a, **k: 0.5)
    _call(deps, "POST", "/extract", {
        "question": "q", "hits": [],
        "covariates": {"doc_date": {"d0": "2015-06-02"}, "subject_state": {"d0": "owner"}},
        "time_indexed": True, "today": "2026-06-17",
    })
    assert seen["time_indexed"] is True
    assert seen["cov"].doc_date == {"d0": "2015-06-02"}
    assert seen["cov"].subject_state == {"d0": "owner"}
    assert seen["today"].isoformat() == "2026-06-17"


def test_extract_reply_carries_the_metered_base_spend(
        deps: BridgeDeps, monkeypatch: pytest.MonkeyPatch) -> None:
    # base extract calls are cloud-priced since the Ollama deprecation — the reply must
    # carry the cache-miss spend so the executor's spend_usd (the gate's run-6 spend
    # term) sees it; warm replays appended nothing and ride at $0
    def fake_observe(*a: Any, meter: list[float] | None = None,
                     **k: Any) -> tuple[list, int]:
        if meter is not None:
            meter.extend([0.002, 0.003])
        return [], 0

    monkeypatch.setattr(LK, "observe_hits", fake_observe)
    monkeypatch.setattr(LK, "extractor_reliability_mean", lambda *a, **k: 0.5)
    _, payload = _call(deps, "POST", "/extract", {"question": "q", "hits": []})
    assert payload["cost_usd"] == pytest.approx(0.005)


def test_extract_projects_era_split_from_doc_date(
        deps: BridgeDeps, monkeypatch: pytest.MonkeyPatch) -> None:
    # The string-blind body cannot compute era_split (abstract obs carry no value/date); the
    # bridge projects it from the RAW obs + doc_date. Two values >5y apart ⇒ True.
    observations = [_obs("Vcur", "d_new"), _obs("Vstale", "d_old")]
    monkeypatch.setattr(LK, "observe_hits", lambda *a, **k: (observations, 0))
    monkeypatch.setattr(LK, "extractor_reliability_mean", lambda *a, **k: 0.7)
    status, payload = _call(deps, "POST", "/extract", {
        "question": "q", "hits": [{"chunk_text": "x"}],
        "covariates": {"doc_date": {"d_new": "2026-01-01", "d_old": "2015-01-01"}},
    })
    assert status == 200
    assert payload["era_split"] is True


def test_extract_era_split_false_without_doc_date(
        deps: BridgeDeps, monkeypatch: pytest.MonkeyPatch) -> None:
    # No doc_date covariate ⇒ recency cannot discriminate ⇒ False (a permanent fact is not decayed).
    observations = [_obs("Vcur", "d_new"), _obs("Vstale", "d_old")]
    monkeypatch.setattr(LK, "observe_hits", lambda *a, **k: (observations, 0))
    monkeypatch.setattr(LK, "extractor_reliability_mean", lambda *a, **k: 0.7)
    status, payload = _call(deps, "POST", "/extract",
                            {"question": "q", "hits": [{"chunk_text": "x"}]})
    assert status == 200
    assert payload["era_split"] is False


# --- the probes ------------------------------------------------------------------------

def test_probe_recency(deps: BridgeDeps, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(P, "probe_recency",
                        lambda conn, root, keys, **k: {"d0": "2015-06-02", "d1": None})
    status, payload = _call(deps, "POST", "/probe/recency", {"hit_keys": ["d0", "d1"]})
    assert status == 200
    assert payload == {"doc_date": {"d0": "2015-06-02", "d1": None}}


def test_probe_subject_loads_profile_server_side(
        deps: BridgeDeps, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def fake_subject(conn: Any, root: Any, keys: list[str], *, profile: str,
                     client: Any, **k: Any) -> dict[str, str]:
        seen["profile"] = profile
        return {"d0": "owner"}

    monkeypatch.setattr(P, "probe_subject", fake_subject)
    status, payload = _call(deps, "POST", "/probe/subject", {"hit_keys": ["d0"]})
    assert status == 200
    assert payload == {"subject_state": {"d0": "owner"}, "cost_usd": 0.0}
    # the profile is the bridge's server-side datum; it is NEVER carried in the request (§3).
    assert seen["profile"] == deps.profile


def test_probe_authority_serialises_tuple_as_list(
        deps: BridgeDeps, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(P, "probe_authority",
                        lambda hits: {"d0": ("document", 0.95), "d1": ("email", 0.90)})
    status, payload = _call(deps, "POST", "/probe/authority",
                            {"hits": [{"artifact_cache_key": "d0", "origin": "x.pdf"}]})
    assert status == 200
    assert payload == {"authority": {"d0": ["document", 0.95], "d1": ["email", 0.90]}}


def test_probe_corroborate_passes_leader_and_excludes(
        deps: BridgeDeps, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def fake_corr(conn: Any, q: str, leader: str, *, k: int,
                  exclude_keys: Any) -> list[dict[str, Any]]:
        seen.update(question=q, leader=leader, k=k, exclude=list(exclude_keys))
        return [{"artifact_cache_key": "a_new", "chunk_text": "…", "score": 2.0, "origin": "o"}]

    monkeypatch.setattr(P, "probe_corroborate", fake_corr)
    status, payload = _call(deps, "POST", "/probe/corroborate", {
        "question": "mobile?", "leader_value": "<current>", "k": 6,
        "exclude_keys": ["a0", "a1"]})
    assert status == 200
    assert payload["hits"][0]["artifact_cache_key"] == "a_new"
    assert seen == {"question": "mobile?", "leader": "<current>", "k": 6,
                    "exclude": ["a0", "a1"]}


# --- the grow lane (slice 6): /grow_menu + /log_gather + the K-enlarging re-extract ------
# The bridge owns the gather-outcome store (it owns the other writes): /grow_menu serves the
# declared sensor vocabulary + menu actuators with body-persisted warm counts (the /decide grow
# block, verbatim); /log_gather appends one structure-observe row per enacted grow.

def test_grow_menu_serves_the_decide_grow_block(deps: BridgeDeps) -> None:
    status, payload = _call(deps, "GET", "/grow_menu")
    assert status == 200
    block = payload["grow"]
    assert block["features"]["names"] == ["extracted", "p_none", "indeterminate"]
    probes = [a["probe"] for a in block["actuators"]]
    assert probes == ["retrieve_rerank", "retrieve_expand", "re_extract_strong"]
    assert all(a["warm_counts"] is None for a in block["actuators"])  # cold store


def test_log_gather_appends_and_warms_the_menu(deps: BridgeDeps) -> None:
    sensors = {"extracted": "some", "p_none": "hi", "indeterminate": "none"}
    status, payload = _call(deps, "POST", "/log_gather", {
        "probe": "re_extract_strong", "sensors": sensors, "recovered": True})
    assert status == 200 and payload["logged"] is True
    _call(deps, "POST", "/log_gather", {
        "probe": "re_extract_strong", "sensors": sensors, "recovered": False})
    _status, menu = _call(deps, "GET", "/grow_menu")
    by_probe = {a["probe"]: a for a in menu["grow"]["actuators"]}
    wc = by_probe["re_extract_strong"]["warm_counts"]
    assert wc == {"contexts": [{"ctx": ["some", "hi", "none"], "n1": 1, "n0": 1}]}
    assert by_probe["retrieve_rerank"]["warm_counts"] is None


def test_log_gather_rejects_unknown_probe(deps: BridgeDeps) -> None:
    status, payload = _call(deps, "POST", "/log_gather", {
        "probe": "not_a_menu_row", "recovered": True,
        "sensors": {"extracted": "some", "p_none": "hi", "indeterminate": "none"}})
    assert status == 400
    assert "probe" in payload["error"]


def test_reextract_allow_new_enlarges_the_candidate_set(
        deps: BridgeDeps, monkeypatch: pytest.MonkeyPatch) -> None:
    # The re-extract grow actuator: the strong whole-doc re-read names a value OUTSIDE the
    # current candidate set ⇒ with allow_new it comes back as a NEW candidate + one observation
    # indexed at len(candidates) (K enlarges — the whole point of grow); without allow_new the
    # corroborate contract is unchanged (outside-set ⇒ no observation).
    import life_agent.core.joint_extract as JE

    monkeypatch.setattr(JE, "extract_joint",
                        lambda root, q, hits, *, model, k: JE.JointResult(
                            value="NEW-7", confidence=0.9, as_of=None))
    body = {"reextract": True, "question": "id?", "hits": [
        {"artifact_cache_key": "d0", "chunk_text": "…"}],
        "candidates": ["A", "B"], "model": "claude-opus-4-8", "rho": 0.95}
    status, payload = _call(deps, "POST", "/probe/corroborate", {**body, "allow_new": True})
    assert status == 200
    assert payload["new_candidate"] == "NEW-7"
    assert payload["observations"][0]["reports"] == 2  # the appended candidate's index
    status2, payload2 = _call(deps, "POST", "/probe/corroborate", body)
    assert status2 == 200
    assert payload2["observations"] == [] and "new_candidate" not in payload2


def test_reextract_confirming_sentence_maps_to_the_candidate(
        deps: BridgeDeps, monkeypatch: pytest.MonkeyPatch) -> None:
    # The q-011 pooling loss: the strong re-read CONFIRMS the leader but phrases it inside a
    # full sentence with the expiry date beside it; exact-normalized equality
    # saw a disagreement, returned no observation, and the replace-contract erased the grounded
    # channel — a formatting mismatch masquerading as evidence conflict. The join now matches
    # by unique token-boundary containment (the graders' own answer_matches), exact first.
    import life_agent.core.joint_extract as JE

    monkeypatch.setattr(JE, "extract_joint",
                        lambda root, q, hits, *, model, k: JE.JointResult(
                            value="Passport number PL-900001, expires 23 May 2032",
                            confidence=0.9, as_of=None))
    status, payload = _call(deps, "POST", "/probe/corroborate", {
        "reextract": True, "question": "passport?", "hits": [
            {"artifact_cache_key": "d0", "chunk_text": "…"}],
        "candidates": ["PL-800002", "PL-900001"], "model": "claude-opus-4-8", "rho": 0.95})
    assert status == 200
    assert payload["observations"] == [{"reports": 1, "group": 0, "authority": 1.0,
                                        "subject_factor": 1.0, "time_factor": 1.0}]
    # containment resolves BEFORE allow_new: a confirming sentence must never mint a
    # duplicate candidate and split the posterior mass with the value it confirms.
    status2, payload2 = _call(deps, "POST", "/probe/corroborate", {
        "reextract": True, "allow_new": True, "question": "passport?", "hits": [
            {"artifact_cache_key": "d0", "chunk_text": "…"}],
        "candidates": ["PL-900001"], "model": "claude-opus-4-8", "rho": 0.95})
    assert status2 == 200
    assert "new_candidate" not in payload2
    assert payload2["observations"][0]["reports"] == 0


def test_reextract_correction_sentence_never_confirms_the_stale_candidate(
        deps: BridgeDeps, monkeypatch: pytest.MonkeyPatch) -> None:
    # The review's manufactured-CW case: a re-read that MENTIONS the known candidate while
    # CORRECTING it to a same-shaped successor. Containment alone would confirm the
    # superseded value at the tier's trusted rho (0.95 on the daemon-scheduled paths);
    # the same-shape competing token must keep the conservative no-observation contract —
    # and allow_new must NOT mint the whole correction sentence as a candidate either.
    import life_agent.core.joint_extract as JE

    monkeypatch.setattr(JE, "extract_joint",
                        lambda root, q, hits, *, model, k: JE.JointResult(
                            value="PL-900001 was renewed; the new number is PL-800002",
                            confidence=0.9, as_of=None))
    status, payload = _call(deps, "POST", "/probe/corroborate", {
        "reextract": True, "allow_new": True, "question": "id?", "hits": [
            {"artifact_cache_key": "d0", "chunk_text": "…"}],
        "candidates": ["PL-900001"], "model": "claude-opus-4-8", "rho": 0.95})
    assert status == 200
    assert payload["observations"] == []
    assert "new_candidate" not in payload


def test_reextract_ambiguous_containment_stays_no_observation(

        deps: BridgeDeps, monkeypatch: pytest.MonkeyPatch) -> None:
    # A sentence containing TWO candidates settles nothing — the conservative contract
    # (outside-set => no observation) holds; disagreement semantics are preserved.
    import life_agent.core.joint_extract as JE

    monkeypatch.setattr(JE, "extract_joint",
                        lambda root, q, hits, *, model, k: JE.JointResult(
                            value="either PL-900001 or PL-800002 depending on the scan",
                            confidence=0.6, as_of=None))
    status, payload = _call(deps, "POST", "/probe/corroborate", {
        "reextract": True, "question": "passport?", "hits": [
            {"artifact_cache_key": "d0", "chunk_text": "…"}],
        "candidates": ["PL-800002", "PL-900001"], "model": "claude-opus-4-8", "rho": 0.95})
    assert status == 200
    assert payload["observations"] == []


def test_reextract_returns_the_reads_own_confidence(
        deps: BridgeDeps, monkeypatch: pytest.MonkeyPatch) -> None:
    # The wire must not discard the instrument's stated uncertainty: the k=0 strong rescue
    # conditions at min(tier rho, this confidence), so a hesitant read hedges instead of
    # asserting at the tier's flat prior (the q-005 near-miss at credence 0.995).
    import life_agent.core.joint_extract as JE

    monkeypatch.setattr(JE, "extract_joint",
                        lambda root, q, hits, *, model, k: JE.JointResult(
                            value="NEW-7", confidence=0.55, as_of=None))
    status, payload = _call(deps, "POST", "/probe/corroborate", {
        "reextract": True, "allow_new": True, "question": "id?",
        "hits": [{"artifact_cache_key": "d0", "chunk_text": "…"}],
        "candidates": [], "model": "claude-opus-4-8", "rho": 0.95})
    assert status == 200
    assert payload["confidence"] == 0.55
    assert payload["new_candidate"] == "NEW-7"


def test_reextract_returns_the_joint_cache_key(
        deps: BridgeDeps, monkeypatch: pytest.MonkeyPatch) -> None:
    # The §18.9 lineage must ride the wire: without it, an extract-tier outcome row is
    # lineage-less and a warm replay double-counts one observation into the curve fold
    # (dedup_edge_events keeps lineage-less rows by design). extract_joint computes the
    # key unconditionally, so the reply field is always present — mirroring the
    # deliberate reply's cache_key.
    import life_agent.core.joint_extract as JE

    monkeypatch.setattr(JE, "extract_joint",
                        lambda root, q, hits, *, model, k: JE.JointResult(
                            value="NEW-7", confidence=0.9, as_of=None, cache_key="jk-1"))
    status, payload = _call(deps, "POST", "/probe/corroborate", {
        "reextract": True, "allow_new": True, "question": "id?",
        "hits": [{"artifact_cache_key": "d0", "chunk_text": "…"}],
        "candidates": [], "model": "claude-opus-4-8", "rho": 0.95})
    assert status == 200
    assert payload["cache_key"] == "jk-1"


def test_reextract_prices_its_tokens(
        deps: BridgeDeps, monkeypatch: pytest.MonkeyPatch) -> None:
    # PR #67 review: the typed arm's spend feed counted ONLY deliberate — tier re-reads
    # are real billed calls and must be metered on the wire, or the run-6 spend term
    # prices the typed arm's tier spend at $0 while the replay arm is fully priced
    # (a Δ biased pro-typed on exactly the semantics the term introduces).
    import life_agent.core.joint_extract as JE

    monkeypatch.setattr(JE, "extract_joint",
                        lambda root, q, hits, *, model, k: JE.JointResult(
                            value="NEW-7", confidence=0.9, as_of=None, cache_key="jk-1",
                            in_tokens=1_000_000, out_tokens=0,
                            served_model="claude-haiku-4-5"))
    status, payload = _call(deps, "POST", "/probe/corroborate", {
        "reextract": True, "allow_new": True, "question": "id?",
        "hits": [{"artifact_cache_key": "d0", "chunk_text": "…"}],
        "candidates": [], "model": "claude-haiku-4-5", "rho": 0.80})
    assert status == 200
    assert payload["cost_usd"] == 1.00  # 1 Mtok input at haiku's $1/Mtok


def test_reextract_warm_replay_prices_at_zero(
        deps: BridgeDeps, monkeypatch: pytest.MonkeyPatch) -> None:
    # a §18.9 warm replay restores value/confidence with zero tokens and no served
    # model — its realised spend is exactly $0, priced via the REQUESTED model pin
    import life_agent.core.joint_extract as JE

    monkeypatch.setattr(JE, "extract_joint",
                        lambda root, q, hits, *, model, k: JE.JointResult(
                            value="NEW-7", confidence=0.9, as_of=None, cache_key="jk-1"))
    status, payload = _call(deps, "POST", "/probe/corroborate", {
        "reextract": True, "allow_new": True, "question": "id?",
        "hits": [{"artifact_cache_key": "d0", "chunk_text": "…"}],
        "candidates": [], "model": "claude-opus-4-8", "rho": 0.95})
    assert status == 200
    assert payload["cost_usd"] == 0.0


def test_source_time_factor_tolerates_partial_self_reported_as_of() -> None:
    # run 3's q2-009: the joint read SELF-REPORTED as_of='2012' (a bare year, cached
    # content-addressed ⇒ deterministic) and the volatility projector crashed the
    # corroborate probe (HTTP 500) on fromisoformat. A partial date normalizes to the
    # EARLIEST point of its stated period (maximal age ⇒ maximal decay — the keystone:
    # never fresher than stated); an unparseable one falls to None (the stated
    # unknown-date attenuation). hits=[] ⇒ the self-report is the operative branch.
    p = {"time_indexed": True, "construct": "passport_number",
         "covariates": {}, "today": "2026-08-07"}
    full_year = bridge_server._source_time_factor("v", "2012-01-01", [], p)
    assert bridge_server._source_time_factor("v", "2012", [], p) == full_year
    full_month = bridge_server._source_time_factor("v", "2012-07-01", [], p)
    assert bridge_server._source_time_factor("v", "2012-07", [], p) == full_month
    unknown = bridge_server._source_time_factor("v", None, [], p)
    assert bridge_server._source_time_factor("v", "mid-2012", [], p) == unknown
    # a datetime-shaped self-report carries a FULL date — degrading it to the flat
    # unknown attenuation (0.6) would let an old value enter FRESHER than stated
    # (review Major: for a 2012 date under a 10y half-life the true decay is ≈0.36);
    # the compact ISO form restores what date.fromisoformat accepted pre-normalizer.
    full_day = bridge_server._source_time_factor("v", "2012-05-01", [], p)
    assert bridge_server._source_time_factor(
        "v", "2012-05-01T00:00:00Z", [], p) == full_day
    assert bridge_server._source_time_factor("v", "20120501", [], p) == full_day


# --- /utility (GET): the utility posterior's u_bar, computed server-side ----------------

def test_utility_returns_u_bar(deps: BridgeDeps) -> None:
    status, payload = _call(deps, "GET", "/utility")
    assert status == 200
    assert payload["u_bar"]["u_wrong"] == -5.0
    assert set(payload["u_bar"]) == {"u_correct", "u_wrong", "u_hedged", "u_abstain",
                                     "oracle_p", "lambda_int", "kappa_att"}


# --- /log_decision: emit answer-brain decisions into the calibration log ----------------
# The verdict-emission seam (move-4 successor): the body posts the terminal decision the
# governor enacted; the bridge writes it shaped exactly as the lookup family's own decisions,
# so the owner's one-bit verdict folds into u(wrong) through the EXISTING reaction loop.

def _decision(effector: str = "abstain", credences: tuple[float, ...] = (0.3, 0.5, 0.1),
              candidates: tuple[str, ...] = ("A", "B", "C"),
              p_none: float = 0.1, eu: float = 0.0) -> dict[str, Any]:
    return {"effector": effector, "credences": list(credences),
            "candidates": list(candidates), "p_none": p_none, "eu": eu, "n_obs": 3}


def test_log_decision_appends_lookup_shaped_event_and_returns_id(deps: BridgeDeps) -> None:
    status, payload = _call(deps, "POST", "/log_decision",
                            {"question": "my mobile?", "retrieval_keys": ["d1", "d0"],
                             "decision": _decision()})
    assert status == 200
    did = payload["decision_id"]
    assert did and did.startswith("ab-")          # namespaced off the lookup §18.9 keys
    logged = DEC.read(deps.decisions_path)
    assert len(logged) == 1
    d = logged[0]
    assert d.family == "lookup"
    assert d.chosen_action == "abstain"
    assert d.action_set == DEC.LOOKUP_ACTION_ORDER
    assert d.decision_id == did
    assert d.run_id == "answer-brain"
    assert d.utility_fold_version == "fold-test-v1"


def test_log_decision_records_indeterminate_and_competition(deps: BridgeDeps) -> None:
    # the record's replayability fix (§14, 2026-08-17): run 8's single-candidate commits
    # were blind to in-chunk competition — the bridge writer now discloses both counts,
    # with honest zero defaults for callers predating the fields.
    _call(deps, "POST", "/log_decision",
          {"question": "q", "retrieval_keys": ["d0"],
           "decision": {**_decision(effector="report"),
                        "n_indeterminate": 2, "n_competing": 1}})
    _call(deps, "POST", "/log_decision",
          {"question": "q2", "retrieval_keys": ["d0"], "decision": _decision()})
    with_fields, without = DEC.read(deps.decisions_path)
    assert with_fields.posterior_summary["n_indeterminate"] == 2
    assert with_fields.posterior_summary["n_competing"] == 1
    assert without.posterior_summary["n_indeterminate"] == 0
    assert without.posterior_summary["n_competing"] == 0


def test_extract_discloses_the_competed_observation_count(
        deps: BridgeDeps, monkeypatch: pytest.MonkeyPatch) -> None:
    import dataclasses as _dc
    observations = [_dc.replace(_obs("Alpha", "d0"), n_competing=1,
                                competition_factor=0.5),
                    _obs("Bravo", "d1")]
    monkeypatch.setattr(LK, "observe_hits", lambda *a, **k: (observations, 0))
    monkeypatch.setattr(LK, "extractor_reliability_mean", lambda *a, **k: 0.7)
    status, payload = _call(deps, "POST", "/extract",
                            {"question": "q", "hits": [{"chunk_text": "x"}]})
    assert status == 200
    assert payload["n_competing"] == 1
    # the wire carries the factor per observation — the daemon's r product consumes it
    assert [o["competition_factor"] for o in payload["observations"]] == [0.5, 1.0]


def test_log_decision_carries_instrument_and_price(deps: BridgeDeps) -> None:
    # §10 accounting on the ledger (decisions v2): the edge that answered, at what price,
    # passes through when the body posts it — and defaults stay honest when it doesn't.
    _call(deps, "POST", "/log_decision",
          {"question": "q", "retrieval_keys": ["d0"],
           "decision": {**_decision(effector="report"),
                        "instrument": "deliberate@claude-opus-4-8",
                        "cost_usd": 0.42, "latency_s": 23.0}})
    _call(deps, "POST", "/log_decision",
          {"question": "q2", "retrieval_keys": ["d0"], "decision": _decision()})
    priced, unpriced = DEC.read(deps.decisions_path)
    assert priced.instrument == "deliberate@claude-opus-4-8"
    assert priced.cost_usd == 0.42
    assert priced.latency_s == 23.0
    assert unpriced.instrument == ""
    assert unpriced.cost_usd is None


def test_log_decision_run_id_passthrough(deps: BridgeDeps) -> None:
    # in-gate executor decisions must not masquerade as live traffic: the body may tag
    # the run; absent → the live default stands
    _call(deps, "POST", "/log_decision",
          {"question": "q", "retrieval_keys": ["d0"],
           "decision": {**_decision(), "run_id": "gate-20260806T999999"}})
    _call(deps, "POST", "/log_decision",
          {"question": "q2", "retrieval_keys": ["d0"], "decision": _decision()})
    tagged, untagged = DEC.read(deps.decisions_path)
    assert tagged.run_id == "gate-20260806T999999"
    assert untagged.run_id == "answer-brain"


def test_log_decision_sorts_credences_leader_first(deps: BridgeDeps) -> None:
    # The load-bearing parity: the daemon returns credences in CANDIDATE order (server.jl
    # `w[1:k]`), but the fold reads credences[0] as the LEADER. The bridge must sort desc, or an
    # abstain folds at the wrong p. Input (0.3, 0.5, 0.1)/(A,B,C) → leader B at 0.5.
    _call(deps, "POST", "/log_decision",
          {"question": "q", "retrieval_keys": ["d0"], "decision": _decision()})
    d = DEC.read(deps.decisions_path)[0]
    assert d.posterior_summary["credences"] == [0.5, 0.3, 0.1]
    assert d.posterior_summary["candidates"] == ["B", "A", "C"]


def test_log_decision_rejects_gather_steer(deps: BridgeDeps) -> None:
    # `gather` is enacted by the body internally (re-extract + re-decide); it is never a
    # terminal decision, so it must not be logged.
    status, payload = _call(deps, "POST", "/log_decision",
                            {"question": "q", "retrieval_keys": [],
                             "decision": _decision(effector="gather")})
    assert status == 400
    assert "error" in payload
    assert DEC.read(deps.decisions_path) == []


def test_log_decision_id_is_stable_across_identical_calls(deps: BridgeDeps) -> None:
    body = {"question": "q", "retrieval_keys": ["d0", "d1"], "decision": _decision()}
    _, p1 = _call(deps, "POST", "/log_decision", body)
    _, p2 = _call(deps, "POST", "/log_decision", body)
    assert p1["decision_id"] == p2["decision_id"]   # content-addressed: re-runs coalesce


def test_log_decision_id_changes_with_evidence(deps: BridgeDeps) -> None:
    _, p1 = _call(deps, "POST", "/log_decision",
                  {"question": "q", "retrieval_keys": ["d0"], "decision": _decision()})
    _, p2 = _call(deps, "POST", "/log_decision",
                  {"question": "q", "retrieval_keys": ["d0", "d9"], "decision": _decision()})
    assert p1["decision_id"] != p2["decision_id"]   # a different retrieval set ⇒ a new decision


def test_log_decision_abstain_verdict_folds_into_u_wrong(
        deps: BridgeDeps, tmp_path: Path) -> None:
    # THE seam proof: a logged answer-brain abstain + a one-bit verdict folds through the
    # EXISTING reaction loop (reactions.load_reactions) into a u(wrong) threshold at -p/(1-p).
    _, payload = _call(deps, "POST", "/log_decision",
                       {"question": "my mobile?", "retrieval_keys": ["d0"],
                        "decision": _decision(effector="abstain", credences=(0.5, 0.3),
                                              candidates=("cur", "stale"))})
    did = payload["decision_id"]
    reactions_path = tmp_path / "reactions.jsonl"
    RX.append(reactions_path, RX.ReactionEvent(
        tx_time="2026-06-18T00:00:00Z", question_id="x", decision_id=did,
        kind="verdict", valence="bad"))
    folded = RX.load_reactions(reactions_path, deps.decisions_path)
    assert len(folded) == 1
    r = folded[0]
    assert r.latent == "u_wrong"
    assert r.reacted is False                       # "bad" → "I wanted an answer"
    assert r.sign == -1.0
    assert r.threshold == pytest.approx(0.5 / (1.0 - 0.5))   # leader p=0.5 → 1.0


def test_log_decision_report_is_recorded_not_folded(
        deps: BridgeDeps, tmp_path: Path) -> None:
    # A verdict on a REPORT is cross-latent contaminated → recorded, never folded (the existing
    # contract must hold for the new source too).
    _, payload = _call(deps, "POST", "/log_decision",
                       {"question": "q", "retrieval_keys": ["d0"],
                        "decision": _decision(effector="report", credences=(0.9, 0.1))})
    reactions_path = tmp_path / "reactions.jsonl"
    RX.append(reactions_path, RX.ReactionEvent(
        tx_time="2026-06-18T00:00:00Z", question_id="x",
        decision_id=payload["decision_id"], kind="verdict", valence="good"))
    assert RX.load_reactions(reactions_path, deps.decisions_path) == []


def test_log_decision_requires_decision_object(deps: BridgeDeps) -> None:
    status, _ = _call(deps, "POST", "/log_decision",
                      {"question": "q", "retrieval_keys": []})
    assert status == 400


def test_log_decision_empty_credences_is_400(deps: BridgeDeps) -> None:
    status, _ = _call(deps, "POST", "/log_decision",
                      {"question": "q", "retrieval_keys": [],
                       "decision": {"effector": "abstain", "credences": []}})
    assert status == 400


# --- /log_reaction: the owner's one-bit verdict, appended for the fold --------------------
# Symmetric to /log_decision: the app captures good/bad in-session and posts it; the bridge
# appends a ReactionEvent (the decision's own question_id for linkage) that the EXISTING fold
# joins by decision_id. Mirrors ask-live's `react()` (one bit, fold-fate echoed).

def _log_a_decision(deps: BridgeDeps, effector: str = "abstain",
                    credences: tuple[float, ...] = (0.5, 0.3)) -> str:
    _, payload = _call(deps, "POST", "/log_decision",
                       {"question": "my mobile?", "retrieval_keys": ["d0"],
                        "decision": _decision(effector=effector, credences=credences,
                                              candidates=("cur", "stale"))})
    return str(payload["decision_id"])


def test_log_reaction_appends_verdict_and_reports_fold_fate(deps: BridgeDeps) -> None:
    did = _log_a_decision(deps, effector="abstain")
    status, payload = _call(deps, "POST", "/log_reaction",
                            {"decision_id": did, "valence": "bad"})
    assert status == 200
    assert payload["valence"] == "bad"
    assert payload["chosen_action"] == "abstain"
    assert payload["folds"] is True               # an abstain verdict moves u_wrong
    events = RX.read(deps.reactions_path)
    assert len(events) == 1
    assert events[0].decision_id == did
    assert events[0].kind == "verdict"
    assert events[0].valence == "bad"
    # the ReactionEvent carries the DECISION's question_id (the linkage react() copies)
    assert events[0].question_id == DEC.read(deps.decisions_path)[0].question_id


def test_log_reaction_round_trip_folds_into_u_wrong(deps: BridgeDeps) -> None:
    # The full in-app path THROUGH THE BRIDGE: /log_decision (abstain) then /log_reaction (bad)
    # → load_reactions folds one u_wrong threshold. No ask-live, no new fold code.
    did = _log_a_decision(deps, effector="abstain", credences=(0.5, 0.3))
    _call(deps, "POST", "/log_reaction", {"decision_id": did, "valence": "bad"})
    folded = RX.load_reactions(deps.reactions_path, deps.decisions_path)
    assert len(folded) == 1
    assert folded[0].latent == "u_wrong"
    assert folded[0].threshold == pytest.approx(1.0)   # p=0.5 → -p/(1-p) = 1.0


def test_log_reaction_report_is_recorded_not_folded(deps: BridgeDeps) -> None:
    did = _log_a_decision(deps, effector="report", credences=(0.9, 0.1))
    status, payload = _call(deps, "POST", "/log_reaction",
                            {"decision_id": did, "valence": "good"})
    assert status == 200
    assert payload["folds"] is False
    assert RX.load_reactions(deps.reactions_path, deps.decisions_path) == []


def test_log_reaction_unknown_decision_is_404(deps: BridgeDeps) -> None:
    status, _ = _call(deps, "POST", "/log_reaction",
                      {"decision_id": "ab-does-not-exist", "valence": "good"})
    assert status == 404


def test_log_reaction_bad_valence_is_400(deps: BridgeDeps) -> None:
    did = _log_a_decision(deps)
    status, _ = _call(deps, "POST", "/log_reaction", {"decision_id": did, "valence": "meh"})
    assert status == 400


# --- the membrane shadow: /decide-support, the log_decision/log_reaction folds, /ready ---
# The bridge is the shadow's ONLY production touchpoint (Task 5): a fake stands in for
# MembraneShadow (never a real spawned binary in a test — the shadow's own hermetic tests
# already cover its internals). The cardinal rule under test here is the fail-open one: the
# shadow must never change an existing endpoint's reply, whether disabled (deps.membrane is
# None, the default the `deps` fixture already gives every other test in this file) or
# enabled-but-raising.


@dataclasses.dataclass
class _FakeMembrane:
    """Duck-types the bridge's use of MembraneShadow: submit_decide/submit_decision/
    submit_reaction (call-recording, optionally raising) + stats()."""

    submit_decide_calls: list[tuple[str, dict[str, Any], dict[str, Any]]] = dataclasses.field(
        default_factory=list)
    submit_decision_calls: list[tuple[str, str, dict[str, Any]]] = dataclasses.field(
        default_factory=list)
    submit_reaction_calls: list[tuple[str, str]] = dataclasses.field(default_factory=list)
    submit_gate_calls: list[tuple[str, str]] = dataclasses.field(default_factory=list)
    stats_value: dict[str, Any] = dataclasses.field(
        default_factory=lambda: {"forms": {}, "drops": 0})
    raise_on_submit_decide: bool = False
    raise_on_submit_decision: bool = False
    raise_on_submit_reaction: bool = False
    raise_on_submit_gate: bool = False
    raise_on_stats: bool = False
    decide_live_calls: list[tuple[str, dict[str, Any], dict[str, Any]]] = dataclasses.field(
        default_factory=list)
    decide_live_value: dict[str, Any] | None = None
    raise_on_decide_live: bool = False

    def submit_decide(self, question_id: str, payload: dict[str, Any],
                      dec: dict[str, Any]) -> None:
        self.submit_decide_calls.append((question_id, payload, dec))
        if self.raise_on_submit_decide:
            raise RuntimeError("boom: submit_decide")

    def submit_decision(self, decision_id: str, question_id: str, event: dict[str, Any]) -> None:
        self.submit_decision_calls.append((decision_id, question_id, event))
        if self.raise_on_submit_decision:
            raise RuntimeError("boom: submit_decision")

    def submit_reaction(self, decision_id: str, valence: str) -> None:
        self.submit_reaction_calls.append((decision_id, valence))
        if self.raise_on_submit_reaction:
            raise RuntimeError("boom: submit_reaction")

    def submit_gate(self, question_id: str, gate: str) -> None:
        self.submit_gate_calls.append((question_id, gate))
        if self.raise_on_submit_gate:
            raise RuntimeError("boom: submit_gate")

    def decide_live(self, question_id: str, payload: dict[str, Any],
                    dec: dict[str, Any]) -> dict[str, Any] | None:
        self.decide_live_calls.append((question_id, payload, dec))
        if self.raise_on_decide_live:
            raise RuntimeError("boom: decide_live")
        return self.decide_live_value

    def stats(self) -> dict[str, Any]:
        if self.raise_on_stats:
            raise RuntimeError("boom: stats")
        return self.stats_value


def _with_membrane(deps: BridgeDeps, membrane: _FakeMembrane) -> BridgeDeps:
    return dataclasses.replace(deps, membrane=membrane)


# --- /decide-support: disabled fast-path, enabled submit, never raises -------------------

def test_decide_support_disabled_is_the_deps_fixture_default(deps: BridgeDeps) -> None:
    # deps.membrane is None by default (every OTHER test in this file relies on exactly
    # this — absence must be zero behaviour change on every other endpoint).
    assert deps.membrane is None


def test_decide_support_disabled_fast_path_no_validation(deps: BridgeDeps) -> None:
    # disabled must return immediately — no field validation at all, even on a body
    # missing every required field, since this sits on the executor's hot path once per
    # decide tick and must never pay parse cost when there is no shadow to feed.
    status, payload = _call(deps, "POST", "/decide-support", {})
    assert status == 200
    assert payload == {"ok": False, "disabled": True}


def test_decide_support_enabled_calls_submit_decide(deps: BridgeDeps) -> None:
    fake = _FakeMembrane()
    deps2 = _with_membrane(deps, fake)
    body = {"question_id": "q-1", "payload": {"candidates": ["a"]},
            "dec": {"credences": [0.9], "effector": "report"}}
    status, payload = _call(deps2, "POST", "/decide-support", body)
    assert status == 200
    assert payload == {"ok": True}
    assert fake.submit_decide_calls == [("q-1", body["payload"], body["dec"])]


def test_decide_support_enabled_malformed_body_is_400(deps: BridgeDeps) -> None:
    fake = _FakeMembrane()
    deps2 = _with_membrane(deps, fake)
    status, payload = _call(deps2, "POST", "/decide-support",
                            {"question_id": "q-1", "payload": "not-a-dict", "dec": {}})
    assert status == 400
    assert "error" in payload
    assert fake.submit_decide_calls == []


def test_decide_support_enabled_missing_question_id_is_400(deps: BridgeDeps) -> None:
    fake = _FakeMembrane()
    deps2 = _with_membrane(deps, fake)
    status, _payload = _call(deps2, "POST", "/decide-support", {"payload": {}, "dec": {}})
    assert status == 400
    assert fake.submit_decide_calls == []


def test_decide_support_never_raises_when_submit_decide_raises(deps: BridgeDeps) -> None:
    fake = _FakeMembrane(raise_on_submit_decide=True)
    deps2 = _with_membrane(deps, fake)
    status, payload = _call(deps2, "POST", "/decide-support",
                            {"question_id": "q-1", "payload": {}, "dec": {}})
    assert status == 200
    assert payload == {"ok": True}          # the reply is unchanged by the raise
    assert len(fake.submit_decide_calls) == 1


# --- /log_decision + /log_reaction: fold into the shadow, fail-open ----------------------

def test_log_decision_folds_into_membrane_submit_decision(deps: BridgeDeps) -> None:
    fake = _FakeMembrane()
    deps2 = _with_membrane(deps, fake)
    status, payload = _call(deps2, "POST", "/log_decision",
                            {"question": "my mobile?", "retrieval_keys": ["d1", "d0"],
                             "decision": _decision()})
    assert status == 200
    assert len(fake.submit_decision_calls) == 1
    decision_id, question_id, event = fake.submit_decision_calls[0]
    assert decision_id == payload["decision_id"]
    assert question_id == DEC.read(deps2.decisions_path)[0].question_id
    assert event["chosen_action"] == "abstain"
    assert event["decision_id"] == decision_id


def test_log_decision_reply_unchanged_when_submit_decision_raises(deps: BridgeDeps) -> None:
    fake = _FakeMembrane(raise_on_submit_decision=True)
    deps2 = _with_membrane(deps, fake)
    status, payload = _call(deps2, "POST", "/log_decision",
                            {"question": "q", "retrieval_keys": ["d0"], "decision": _decision()})
    assert status == 200
    assert "decision_id" in payload
    assert len(DEC.read(deps2.decisions_path)) == 1     # the real append is unaffected
    assert len(fake.submit_decision_calls) == 1          # the shadow still saw the attempt


def test_log_reaction_folds_into_membrane_submit_reaction(deps: BridgeDeps) -> None:
    fake = _FakeMembrane()
    deps2 = _with_membrane(deps, fake)
    did = _log_a_decision(deps2, effector="abstain")
    status, payload = _call(deps2, "POST", "/log_reaction",
                            {"decision_id": did, "valence": "bad"})
    assert status == 200
    assert fake.submit_reaction_calls == [(did, "bad")]
    assert payload["folds"] is True   # the existing reply is untouched by the fold


def test_log_reaction_reply_unchanged_when_submit_reaction_raises(deps: BridgeDeps) -> None:
    fake = _FakeMembrane(raise_on_submit_reaction=True)
    deps2 = _with_membrane(deps, fake)
    did = _log_a_decision(deps2, effector="abstain")
    status, payload = _call(deps2, "POST", "/log_reaction",
                            {"decision_id": did, "valence": "bad"})
    assert status == 200
    assert payload["folds"] is True
    events = RX.read(deps2.reactions_path)
    assert len(events) == 1                          # the real append is unaffected
    assert fake.submit_reaction_calls == [(did, "bad")]


# --- GET /ready: the membrane block, both states ------------------------------------------

def test_ready_membrane_disabled(deps: BridgeDeps) -> None:
    status, payload = _call(deps, "GET", "/ready")
    assert status == 200
    assert payload == {"status": "ok", "membrane": {"enabled": False}}


def test_ready_membrane_enabled_reports_stats(deps: BridgeDeps) -> None:
    fake = _FakeMembrane(stats_value={"forms": {"said@1": {"alive": True}}, "drops": 2})
    deps2 = _with_membrane(deps, fake)
    status, payload = _call(deps2, "GET", "/ready")
    assert status == 200
    assert payload["status"] == "ok"
    assert payload["membrane"] == {"forms": {"said@1": {"alive": True}}, "drops": 2}


def test_ready_membrane_stats_raising_does_not_crash_ready(deps: BridgeDeps) -> None:
    # `_membrane_ready_block`'s try/except is load-bearing, not cosmetic: `dispatch` only
    # catches `BridgeError`, so an uncaught exception out of `stats()` would propagate past
    # dispatch and (over real HTTP) become a 500 on `GET /ready`; `core/ask_client.py`'s
    # `_ready()` treats any non-2xx as the bridge being down, so a misbehaving shadow would
    # present as an apparent outage of the production answer path — exactly what this
    # feature must never cause. Pin that the guard holds: a raising stats() still yields a
    # 200 with the rest of the ready block intact, the membrane sub-block carrying an error
    # marker instead of propagating.
    fake = _FakeMembrane(raise_on_stats=True)
    deps2 = _with_membrane(deps, fake)
    status, payload = _call(deps2, "GET", "/ready")
    assert status == 200
    assert payload is not None
    assert payload["status"] == "ok"
    assert payload["membrane"] == {"enabled": True, "stats_error": True}


# --- build_deps' _build_membrane: iff LIFE_AGENT_MEMBRANE_COMMAND is set, never lets a ----
# --- construction/start failure prevent the bridge from serving --------------------------

class _FakeShadowInstance:
    def __init__(self, cfg: Any, *, u_bar: Any, snapshot: Any) -> None:
        self.cfg = cfg
        self.u_bar = u_bar
        self.snapshot = snapshot
        self.start_called = False

    def start(self) -> None:
        self.start_called = True


class _RaisingOnInitShadow:
    def __init__(self, *_a: Any, **_k: Any) -> None:
        raise RuntimeError("boom: construction")


class _RaisingOnStartShadow:
    def __init__(self, *_a: Any, **_k: Any) -> None:
        pass

    def start(self) -> None:
        raise RuntimeError("boom: start (e.g. double-start, or Thread.start() failure)")


def test_build_membrane_disabled_when_no_command(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(config.MEMBRANE_COMMAND_ENV, raising=False)
    assert bridge_server._build_membrane(lambda: {}) is None


def test_build_membrane_constructs_and_starts_when_command_set(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(config.MEMBRANE_COMMAND_ENV, "fake-govhost --flag")
    monkeypatch.setattr(config, "KB", tmp_path)
    # DECISIONS_LOG/REACTIONS_LOG/CLAUDE_VERDICTS_LOG are precomputed at import time off the
    # REAL KB, so patching config.KB alone would not move them — pin all three under tmp_path,
    # or the snapshot closure below would touch whatever real calibration logs exist on disk.
    # (The Claude verdict log joined boot_snapshot in the verdict-channel PR; before it had any
    # rows this test passed by accident — n_source_records read 0 only because the file was
    # empty. It must be pinned like the other two.)
    monkeypatch.setattr(config, "DECISIONS_LOG", tmp_path / "calibration" / "decisions.jsonl")
    monkeypatch.setattr(config, "REACTIONS_LOG", tmp_path / "calibration" / "reactions.jsonl")
    monkeypatch.setattr(
        config, "CLAUDE_VERDICTS_LOG", tmp_path / "calibration" / "claude_verdicts.jsonl")
    monkeypatch.setattr(bridge_server.MEM, "MembraneShadow", _FakeShadowInstance)
    result = bridge_server._build_membrane(lambda: {"u_wrong": -5.0})
    assert isinstance(result, _FakeShadowInstance)
    assert result.start_called is True
    assert result.cfg.command == ["fake-govhost", "--flag"]
    assert result.cfg.forms == ("said@1",)                   # the declared default
    assert result.cfg.log_path == tmp_path / "membrane" / "shadow.jsonl"
    assert result.cfg.queue_size == bridge_server._MEMBRANE_QUEUE_SIZE
    assert result.cfg.max_respawns == bridge_server._MEMBRANE_MAX_RESPAWNS
    assert result.cfg.respawn_backoff_s == bridge_server._MEMBRANE_RESPAWN_BACKOFF_S
    assert result.u_bar()["u_wrong"] == -5.0
    # `snapshot` reads config.DECISIONS_LOG/REACTIONS_LOG (empty under the tmp KB pinned
    # above) — calling it must not raise, proving the closure captured usable paths.
    snap = result.snapshot()
    assert snap.n_source_records == 0


def test_build_membrane_falls_back_to_none_when_construction_raises(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(config.MEMBRANE_COMMAND_ENV, "fake-govhost")
    monkeypatch.setattr(config, "KB", tmp_path)
    monkeypatch.setattr(bridge_server.MEM, "MembraneShadow", _RaisingOnInitShadow)
    assert bridge_server._build_membrane(lambda: {}) is None


def test_build_membrane_falls_back_to_none_when_start_raises(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(config.MEMBRANE_COMMAND_ENV, "fake-govhost")
    monkeypatch.setattr(config, "KB", tmp_path)
    monkeypatch.setattr(bridge_server.MEM, "MembraneShadow", _RaisingOnStartShadow)
    assert bridge_server._build_membrane(lambda: {}) is None


# --- malformed / unknown / method ------------------------------------------------------

def test_empty_body_is_400(deps: BridgeDeps) -> None:
    status, payload = _call(deps, "POST", "/extract")
    assert status == 400
    assert "error" in payload


def test_malformed_json_is_400(deps: BridgeDeps) -> None:
    status, _ = dispatch(deps, "POST", "/extract", b"{not json")
    assert status == 400


def test_missing_required_field_is_400(deps: BridgeDeps) -> None:
    status, _ = _call(deps, "POST", "/route", {"not_question": "x"})
    assert status == 400


def test_unknown_path_is_404(deps: BridgeDeps) -> None:
    status, _ = _call(deps, "POST", "/nope", {})
    assert status == 404


def test_bad_method_is_405(deps: BridgeDeps) -> None:
    # every 4xx is RETURNED, not raised past dispatch — a bad request never crashes the loop.
    status, payload = dispatch(deps, "DELETE", "/route", b"")
    assert status == 405
    assert "error" in payload


# --- transport: real loopback HTTP (dispatch + 400 + /ready + statelessness) -----------

@pytest.fixture
def live_bridge(deps: BridgeDeps,
                monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[str, dict[str, Any]]]:
    """A real BridgeServer on an ephemeral loopback port. ``observe_hits`` is patched to be a
    pure function of the question, so an interleaved request cannot perturb a repeat."""
    monkeypatch.setattr(LK, "extractor_reliability_mean", lambda *a, **k: 0.5)

    def observe_for(root: Any, q: str, hits: list[dict[str, Any]], **k: Any
                    ) -> tuple[list[Observation], int]:
        return [_obs(f"V_{q}", "d0")], 0          # candidate is a pure function of q

    monkeypatch.setattr(LK, "observe_hits", observe_for)

    server = BridgeServer(deps, host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    base = f"http://{host}:{port}"
    try:
        yield base, {}
    finally:
        server.shutdown()
        server.server_close()


def _http(base: str, method: str, path: str,
          body: dict[str, Any] | None = None) -> tuple[int, Any]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


def test_http_ready(live_bridge: tuple[str, dict[str, Any]]) -> None:
    base, _ = live_bridge
    status, payload = _http(base, "GET", "/ready")
    assert status == 200
    # deps.membrane is None (the fixture's default) over this live server too.
    assert payload == {"status": "ok", "membrane": {"enabled": False}}


def test_http_malformed_body_is_400(live_bridge: tuple[str, dict[str, Any]]) -> None:
    base, _ = live_bridge
    req = urllib.request.Request(base + "/extract", data=b"{bad", method="POST")
    try:
        urllib.request.urlopen(req, timeout=5)
        raise AssertionError("expected HTTP 400")
    except urllib.error.HTTPError as e:
        assert e.code == 400


def test_http_statelessness_interleaved_request_does_not_perturb_repeat(
        live_bridge: tuple[str, dict[str, Any]]) -> None:
    base, _ = live_bridge
    first = _http(base, "POST", "/extract", {"question": "qA", "hits": []})
    _http(base, "POST", "/extract", {"question": "qB", "hits": []})   # interleave
    again = _http(base, "POST", "/extract", {"question": "qA", "hits": []})
    assert first == again
    assert first[1]["candidates"] == ["V_qA"]


# --- _shutdown: the SIGTERM/SIGINT cleanup (Task 9) -------------------------------------
#
# `_shutdown` is called directly (never via `signal.signal`/`os.kill`) — a real OS signal
# delivered to the test process would be indistinguishable from a real interpreter-killing
# SIGTERM. `_install_shutdown_handlers` itself (the two `signal.signal` registrations) is
# intentionally not exercised here: it is one line of stdlib wiring around `_shutdown`.

class _FakeCloseableMembrane:
    def __init__(self, *, raises: bool = False) -> None:
        self.closed = False
        self._raises = raises

    def close(self) -> None:
        self.closed = True
        if self._raises:
            raise RuntimeError("boom")


class _FakeShutdownDeps:
    def __init__(self, membrane: _FakeCloseableMembrane | None) -> None:
        self.membrane = membrane


class _FakeShutdownServer:
    def __init__(self, membrane: _FakeCloseableMembrane | None) -> None:
        self.deps = _FakeShutdownDeps(membrane)


def test_shutdown_closes_membrane_then_exits() -> None:
    membrane = _FakeCloseableMembrane()
    with pytest.raises(SystemExit) as exc:
        bridge_server._shutdown(_FakeShutdownServer(membrane))  # type: ignore[arg-type]
    assert exc.value.code == 0
    assert membrane.closed is True


def test_shutdown_is_fail_open_when_close_raises() -> None:
    """A raising close() must not prevent shutdown — the process still exits cleanly."""
    membrane = _FakeCloseableMembrane(raises=True)
    with pytest.raises(SystemExit) as exc:
        bridge_server._shutdown(_FakeShutdownServer(membrane))  # type: ignore[arg-type]
    assert exc.value.code == 0
    assert membrane.closed is True  # close() ran (and raised) before the suppress


def test_shutdown_with_no_membrane_still_exits() -> None:
    with pytest.raises(SystemExit) as exc:
        bridge_server._shutdown(_FakeShutdownServer(None))  # type: ignore[arg-type]
    assert exc.value.code == 0


# --- /gate-support: the seam's gate pre-emptions reach the shadow (M2) -------------------

def test_gate_support_disabled_fast_path_no_validation(deps: BridgeDeps) -> None:
    status, payload = _call(deps, "POST", "/gate-support", {})
    assert status == 200
    assert payload == {"ok": False, "disabled": True}


def test_gate_support_enabled_calls_submit_gate(deps: BridgeDeps) -> None:
    fake = _FakeMembrane()
    deps2 = _with_membrane(deps, fake)
    status, payload = _call(deps2, "POST", "/gate-support",
                            {"question_id": "q-1", "gate": "weak_retrieval"})
    assert status == 200
    assert payload == {"ok": True}
    assert fake.submit_gate_calls == [("q-1", "weak_retrieval")]


def test_gate_support_enabled_missing_gate_is_400(deps: BridgeDeps) -> None:
    fake = _FakeMembrane()
    deps2 = _with_membrane(deps, fake)
    status, _payload = _call(deps2, "POST", "/gate-support", {"question_id": "q-1"})
    assert status == 400
    assert fake.submit_gate_calls == []


def test_gate_support_enabled_missing_question_id_is_400(deps: BridgeDeps) -> None:
    fake = _FakeMembrane()
    deps2 = _with_membrane(deps, fake)
    status, _payload = _call(deps2, "POST", "/gate-support", {"gate": "weak_retrieval"})
    assert status == 400
    assert fake.submit_gate_calls == []


def test_gate_support_never_raises_when_submit_gate_raises(deps: BridgeDeps) -> None:
    fake = _FakeMembrane(raise_on_submit_gate=True)
    deps2 = _with_membrane(deps, fake)
    status, payload = _call(deps2, "POST", "/gate-support",
                            {"question_id": "q-1", "gate": "weak_retrieval"})
    assert status == 200
    assert payload == {"ok": True}


# --- /decide-live: the M3 synchronous coarse-menu consult --------------------------------

def test_decide_live_disabled_fast_path(deps: BridgeDeps) -> None:
    status, payload = _call(deps, "POST", "/decide-live", {})
    assert status == 200
    assert payload == {"ok": False, "disabled": True}


def test_decide_live_returns_the_shadow_result(deps: BridgeDeps) -> None:
    result = {"dec": {"effector": "report", "value": "beta"},
              "action": "respond", "degraded": None}
    fake = _FakeMembrane(decide_live_value=result)
    deps2 = _with_membrane(deps, fake)
    body = {"question_id": "q-1", "payload": {"candidates": ["beta"]},
            "dec": {"effector": "abstain"}}
    status, payload = _call(deps2, "POST", "/decide-live", body)
    assert status == 200
    assert payload == {"ok": True, **result}
    assert fake.decide_live_calls == [
        ("q-1", {"candidates": ["beta"]}, {"effector": "abstain"})]


def test_decide_live_down_shadow_is_named(deps: BridgeDeps) -> None:
    fake = _FakeMembrane(decide_live_value=None)
    deps2 = _with_membrane(deps, fake)
    status, payload = _call(deps2, "POST", "/decide-live",
                            {"question_id": "q-1", "payload": {}, "dec": {}})
    assert status == 200
    assert payload == {"ok": False, "down": True}


def test_decide_live_never_raises_when_the_shadow_raises(deps: BridgeDeps) -> None:
    fake = _FakeMembrane(raise_on_decide_live=True)
    deps2 = _with_membrane(deps, fake)
    status, payload = _call(deps2, "POST", "/decide-live",
                            {"question_id": "q-1", "payload": {}, "dec": {}})
    assert status == 200
    assert payload == {"ok": False, "down": True}


def test_decide_live_malformed_body_is_400(deps: BridgeDeps) -> None:
    fake = _FakeMembrane()
    deps2 = _with_membrane(deps, fake)
    for body in ({"payload": {}, "dec": {}},
                 {"question_id": "q-1", "payload": "x", "dec": {}},
                 {"question_id": "q-1", "payload": {}, "dec": "x"}):
        status, _payload = _call(deps2, "POST", "/decide-live", body)
        assert status == 400, body
    assert fake.decide_live_calls == []


# --- /probe/deliberate (the promoted A1b edge on the transform menu) ---------------------

def _deliberate_result(**overrides: Any) -> Any:
    from life_agent.core import deliberate as DL

    base: dict[str, Any] = dict(
        question="what is my rent?", model="claude-opus-4-8",
        text="NIS 4,200 [lease.pdf]", value="NIS 4,200", credence=0.85,
        declined=False, status="ok", notes="", cost_usd=0.42, latency_s=23.0,
        input_tokens=1000, output_tokens=50, session_id="sess-1",
        tool_calls=5, gather_rounds=3)
    base.update(overrides)
    return DL.DeliberateResult(**base)


@pytest.fixture
def deliberate_seams(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, Any]:
    """Patch the three seams the handler composes: the CLI edge, the §18.9 recorder, and
    the corpus digest. Returns the seen-calls dict for assertions. Also pins a
    resolvable PKM_CONFIG (the cfg refuses an absent one) so the suite is hermetic."""
    pkm_cfg = tmp_path / "pkm.yaml"
    pkm_cfg.write_text("root_dir: /x\n")
    monkeypatch.setattr(bridge_server.config, "PKM_CONFIG", pkm_cfg)
    seen: dict[str, Any] = {"answers": [], "records": [], "result": _deliberate_result()}
    monkeypatch.setattr(bridge_server.DL, "answer",
                        lambda q, cfg, **k: (seen["answers"].append(q),
                                             seen["result"])[1])
    monkeypatch.setattr(bridge_server.DL, "record_answer",
                        lambda root, key, r: (seen["records"].append(key.cache_key),
                                              True)[1])
    monkeypatch.setattr(bridge_server.CORPUS, "corpus_digest", lambda conn: "digest-t")
    return seen


def test_deliberate_confirms_an_existing_candidate(
        deps: BridgeDeps, deliberate_seams: dict[str, Any]) -> None:
    status, payload = _call(deps, "POST", "/probe/deliberate",
                            {"question": "what is my rent?",
                             "candidates": ["NIS 4,200", "NIS 9,999"]})
    assert status == 200
    assert payload["observations"] == [{"reports": 0, "group": 0, "authority": 1.0,
                                        "subject_factor": 1.0, "time_factor": 1.0}]
    assert payload["confidence"] == 0.85
    assert payload["cost_usd"] == 0.42
    assert payload["model"] == "claude-opus-4-8"
    assert payload["declined"] is False
    assert "new_candidate" not in payload
    assert deliberate_seams["records"]          # the §18.9 artifact was recorded


def test_deliberate_mints_a_new_candidate_with_allow_new(
        deps: BridgeDeps, deliberate_seams: dict[str, Any]) -> None:
    deliberate_seams["result"] = _deliberate_result(value="NIS 5,100",
                                                    text="NIS 5,100 [contract.pdf]")
    status, payload = _call(deps, "POST", "/probe/deliberate",
                            {"question": "what is my rent?",
                             "candidates": ["NIS 9,999"], "allow_new": True})
    assert status == 200
    assert payload["new_candidate"] == "NIS 5,100"
    assert payload["observations"] == [{"reports": 1, "group": 0, "authority": 1.0,
                                        "subject_factor": 1.0, "time_factor": 1.0}]


def test_deliberate_outside_set_without_allow_new_yields_no_observation(
        deps: BridgeDeps, deliberate_seams: dict[str, Any]) -> None:
    deliberate_seams["result"] = _deliberate_result(value="NIS 5,100")
    status, payload = _call(deps, "POST", "/probe/deliberate",
                            {"question": "what is my rent?", "candidates": ["NIS 9,999"]})
    assert status == 200
    assert payload["observations"] == []
    assert "new_candidate" not in payload


def test_deliberate_decline_yields_no_observation_and_still_records(
        deps: BridgeDeps, deliberate_seams: dict[str, Any]) -> None:
    deliberate_seams["result"] = _deliberate_result(
        text="NOT_IN_CORPUS: no rent document", value=None, credence=None,
        declined=True)
    status, payload = _call(deps, "POST", "/probe/deliberate",
                            {"question": "what is my rent?", "candidates": ["NIS 9,999"],
                             "allow_new": True})
    assert status == 200
    assert payload["observations"] == []
    assert payload["declined"] is True
    # a decline IS a successful call — a warm NOT_IN_CORPUS replay is valid evidence
    assert deliberate_seams["records"]


def test_deliberate_error_yields_no_observation_and_no_record(
        deps: BridgeDeps, deliberate_seams: dict[str, Any]) -> None:
    deliberate_seams["result"] = _deliberate_result(status="error", text="", value=None,
                                                    credence=None, cost_usd=None)
    status, payload = _call(deps, "POST", "/probe/deliberate",
                            {"question": "what is my rent?", "candidates": ["NIS 9,999"]})
    assert status == 200
    assert payload["status"] == "error"
    assert payload["observations"] == []
    assert deliberate_seams["records"] == []


def test_deliberate_warm_hit_replays_without_a_model_call(
        deps: BridgeDeps, deliberate_seams: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch) -> None:
    recorded = json.dumps({
        "format_version": 1, "question": "what is my rent?",
        "model": "claude-opus-4-8", "text": "NIS 4,200 [lease.pdf]",
        "value": "NIS 4,200", "credence": 0.85, "declined": False,
        "cost_usd": 0.42, "session_id": "sess-0", "tool_calls": 5,
        "gather_rounds": 3}).encode("utf-8")
    monkeypatch.setattr(bridge_server.D, "lookup", lambda root, key: recorded)
    status, payload = _call(deps, "POST", "/probe/deliberate",
                            {"question": "what is my rent?", "candidates": ["NIS 4,200"]})
    assert status == 200
    assert payload["cache"] == "hit"
    assert payload["cost_usd"] == 0.0                 # a warm chain costs zero model calls
    assert payload["observations"] == [{"reports": 0, "group": 0, "authority": 1.0,
                                        "subject_factor": 1.0, "time_factor": 1.0}]
    assert deliberate_seams["answers"] == []          # the CLI was never invoked


def test_deliberate_miss_reply_carries_the_cache_key(
        deps: BridgeDeps, deliberate_seams: dict[str, Any]) -> None:
    # The reply names the §18.9 identity of the (question x corpus) cell so the caller
    # can dedup warm replays in the outcomes stream — one artifact, one observation.
    status, payload = _call(deps, "POST", "/probe/deliberate",
                            {"question": "what is my rent?",
                             "candidates": ["NIS 4,200"]})
    assert status == 200
    assert payload["cache"] == "miss"
    assert payload["cache_key"] == deliberate_seams["records"][0]


def test_deliberate_warm_hit_carries_the_same_cache_key(
        deps: BridgeDeps, deliberate_seams: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch) -> None:
    # A warm replay is the SAME artifact — its reply must carry the same identity the
    # ledger was consulted with, so downstream dedup sees one observation, not two.
    recorded = json.dumps({
        "format_version": 1, "question": "what is my rent?",
        "model": "claude-opus-4-8", "text": "NIS 4,200 [lease.pdf]",
        "value": "NIS 4,200", "credence": 0.85, "declined": False,
        "cost_usd": 0.42, "session_id": "sess-0", "tool_calls": 5,
        "gather_rounds": 3}).encode("utf-8")
    seen_keys: list[str] = []
    monkeypatch.setattr(bridge_server.D, "lookup",
                        lambda root, key: (seen_keys.append(key), recorded)[1])
    status, payload = _call(deps, "POST", "/probe/deliberate",
                            {"question": "what is my rent?", "candidates": ["NIS 4,200"]})
    assert status == 200
    assert payload["cache"] == "hit"
    assert payload["cache_key"] == seen_keys[0]


def test_deliberate_cache_off_reply_has_no_cache_key(
        deps: BridgeDeps, deliberate_seams: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch) -> None:
    # Digest failure ⇒ no key was ever computed ⇒ nothing to dedup on — the field is
    # absent, never fabricated.
    def boom(conn: Any) -> str:
        raise RuntimeError("catalogue locked")

    monkeypatch.setattr(bridge_server.CORPUS, "corpus_digest", boom)
    status, payload = _call(deps, "POST", "/probe/deliberate",
                            {"question": "what is my rent?", "candidates": ["NIS 4,200"]})
    assert status == 200
    assert payload["cache"] == "off"
    assert "cache_key" not in payload


def test_deliberate_time_indexed_observation_decays_not_hand_set(
        deps: BridgeDeps, deliberate_seams: dict[str, Any]) -> None:
    # The keystone (q-006): no transform may hand-set time_factor=1.0 on a time-indexed
    # construct. The deliberate observation is as current as the freshest retrieved
    # source attestation, through the same volatility decay /extract applies.
    status, payload = _call(deps, "POST", "/probe/deliberate",
                            {"question": "what is my rent?",
                             "candidates": ["NIS 4,200"],
                             "time_indexed": True, "construct": "rent",
                             "hits": [{"artifact_cache_key": "d0",
                                       "chunk_text": "rent NIS 4,200"}],
                             "covariates": {"doc_date": {"d0": "2019-01-01"}}})
    assert status == 200
    (obs,) = payload["observations"]
    assert obs["time_factor"] < 1.0


def test_deliberate_untimed_construct_keeps_unit_time_factor(
        deps: BridgeDeps, deliberate_seams: dict[str, Any]) -> None:
    status, payload = _call(deps, "POST", "/probe/deliberate",
                            {"question": "what is my rent?",
                             "candidates": ["NIS 4,200"]})
    assert status == 200
    (obs,) = payload["observations"]
    assert obs["time_factor"] == 1.0


def test_deliberate_digest_failure_answers_with_cache_off(
        deps: BridgeDeps, deliberate_seams: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(conn: Any) -> str:
        raise RuntimeError("catalogue locked")

    monkeypatch.setattr(bridge_server.CORPUS, "corpus_digest", boom)
    status, payload = _call(deps, "POST", "/probe/deliberate",
                            {"question": "what is my rent?", "candidates": ["NIS 4,200"]})
    assert status == 200
    assert payload["cache"] == "off"                  # named, never silent
    assert payload["observations"] != []
    assert deliberate_seams["records"] == []          # unkeyed ⇒ never recorded


def test_respond_survives_a_client_that_hung_up(deps: BridgeDeps) -> None:
    # a caller that timed out mid-read leaves a dead socket; writing to it must not
    # raise out of the handler (which wedged the single-threaded server — run-6 void)
    import io

    from life_agent.bridge import server as S

    class _DeadFile(io.BytesIO):
        def write(self, *_a):
            raise BrokenPipeError(32, "Broken pipe")

    h = S._Handler.__new__(S._Handler)
    h.wfile = _DeadFile()
    h.close_connection = False
    h.send_response = lambda *a, **k: None
    h.send_header = lambda *a, **k: None
    h.end_headers = lambda: None
    h._respond(200, {"ok": True})          # must NOT raise
    assert h.close_connection is True


def test_deliberate_cfg_refuses_an_unresolvable_pkm_config(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # run 6 (2026-08-17): the raw env read gave "" with PKM_CONFIG unset and the claude
    # CLI was told to start `pkm --config "" serve` — the MCP server crashed and nine
    # cold deliberates declined blind. The cfg resolves like the rest of the bridge
    # (core.config.PKM_CONFIG) and refuses loudly when that is not a file.
    monkeypatch.setattr(bridge_server.config, "PKM_CONFIG", tmp_path / "absent.yaml")
    with pytest.raises(RuntimeError, match="PKM_CONFIG does not resolve"):
        bridge_server._deliberate_cfg()
    present = tmp_path / "pkm.yaml"
    present.write_text("root_dir: /x\n")
    monkeypatch.setattr(bridge_server.config, "PKM_CONFIG", present)
    assert bridge_server._deliberate_cfg().pkm_config == str(present)
