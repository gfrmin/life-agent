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

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from life_agent.bridge.observations import to_abstract_observations
from life_agent.bridge.server import BridgeDeps, BridgeServer, dispatch
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
                     half_life_years: float = 5.0) -> tuple[list[Observation], int]:
        seen["cov"], seen["time_indexed"], seen["today"] = covariates, time_indexed, today
        seen["half_life_years"] = half_life_years
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
    assert payload == {"subject_state": {"d0": "owner"}}
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
    assert payload == {"status": "ok"}


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
