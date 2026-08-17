"""Hermetic tests for the body's executor loop (core/executor.py).

The loop drives the credence answer-brain daemon's VOI schedule over the life-agent bridge:
route → retrieve → probe → extract → /decide, enacting each net_voi-scheduled transform the
daemon returns and re-deciding until a terminal effector. The decision lives in the daemon;
this is the BODY that enacts it. I/O is injected (post/get), so the whole control flow — grow
escalation, recency acknowledgement, corroborate-tier enaction, terminal mapping — is pinned
WITHOUT a live daemon or bridge.
"""
from __future__ import annotations

from typing import Any

from life_agent.core import executor as EX

B = "http://bridge"
D = "http://daemon"
_U = {"u_correct": 1.0, "u_wrong": -5.0, "u_hedged": 0.2, "u_abstain": 0.0,
      "oracle_p": 0.9, "lambda_int": 0.1, "kappa_att": 0.0}
_HIT = [{"artifact_cache_key": "d0", "chunk_text": "Passport No: P123"}]
_EXTRACT = {"candidates": ["P123"],
            "observations": [{"reports": 0, "group": 0, "authority": 0.9,
                              "subject_factor": 1.0, "time_factor": 1.0}],
            "rho": 0.7, "era_split": False, "indeterminate": 0, "half_life_years": 5.0}


_GROW_MENU = {
    "features": {"names": ["extracted", "p_none", "indeterminate"],
                 "values": [["none", "some"], ["hi", "mid", "lo"], ["none", "some"]]},
    "actuators": [
        {"probe": "retrieve_rerank", "cost": 0.004, "alpha0": 3.0, "beta0": 7.0,
         "warm_counts": None},
        {"probe": "retrieve_expand", "cost": 0.006, "alpha0": 3.5, "beta0": 6.5,
         "warm_counts": None},
        {"probe": "re_extract_strong", "cost": 0.020, "alpha0": 4.0, "beta0": 6.0,
         "warm_counts": None},
    ],
}


class FakeServices:
    """A scripted bridge + daemon. ``decides`` is consumed in order (the daemon's effector
    stream); ``extracts``, when given, is consumed per /extract call (a grow pass re-extracts);
    every other endpoint returns its fixed fixture. Records calls for assertions."""

    def __init__(self, *, route: dict[str, Any] | None,
                 hits: list[dict[str, Any]] | None = None,
                 extract: dict[str, Any] | None = None,
                 extracts: list[dict[str, Any]] | None = None,
                 decides: list[dict[str, Any]] | None = None,
                 narrative: dict[str, Any] | None = None,
                 corroborate: dict[str, Any] | None = None,
                 deliberate: dict[str, Any] | None = None,
                 utility: dict[str, float] | None = None) -> None:
        self.route = route
        self.hits = hits if hits is not None else _HIT
        self.extract = extract if extract is not None else _EXTRACT
        self._extracts = list(extracts) if extracts is not None else None
        self._decides = list(decides or [])
        self.narrative = narrative
        self.corroborate = corroborate
        self.deliberate = deliberate
        self.utility = utility if utility is not None else _U
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    def post(self, url: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        self.calls.append((url, payload))
        if url.endswith("/route"):
            return self.route
        if url.endswith("/narrative"):
            return self.narrative
        if url.endswith("/retrieve"):
            return {"hits": self.hits}
        if url.endswith("/probe/subject"):
            return {"subject_state": {}}
        if url.endswith("/probe/recency"):
            return {"doc_date": {}}
        if url.endswith("/extract"):
            if self._extracts is not None:
                return self._extracts.pop(0)
            return self.extract
        if url.endswith("/probe/corroborate"):
            return self.corroborate
        if url.endswith("/probe/deliberate"):
            return self.deliberate
        if url.endswith("/log_gather"):
            return {"logged": True}
        if url.endswith("/decide"):
            return self._decides.pop(0)
        raise AssertionError(f"unexpected POST {url}")

    def get(self, url: str) -> dict[str, Any]:
        self.calls.append((url, None))
        if url.endswith("/utility"):
            return {"u_bar": self.utility}
        if url.endswith("/grow_menu"):
            return {"grow": _GROW_MENU}
        raise AssertionError(f"unexpected GET {url}")

    def posted(self, suffix: str) -> list[dict[str, Any]]:
        return [p for (u, p) in self.calls if u.endswith(suffix) and p is not None]


def _loop(fake: FakeServices, question: str = "what is my passport number?",
          **kw: Any) -> dict[str, Any]:
    return EX.decide_via_loop(question, 20, bridge=B, daemon=D,
                              post=fake.post, get=fake.get, **kw)


def test_route_none_takes_narrative_path() -> None:
    # A non-typed question: the router declines, the loop runs the narrative family and never
    # touches retrieve/extract/decide.
    fake = FakeServices(route=None, narrative={
        "action": "report", "asserted": ["you travelled in May"],
        "rendered": "you travelled in May [1]\n\nnarrative footer",
        "hits": [{"artifact_cache_key": "d0", "chunk_text": "x"}]})
    view = _loop(fake, "tell me about my week")
    assert view["effector"] == "report"
    assert view["asserted"] == ["you travelled in May"]
    assert view["route"] is None
    assert view["rendered"] == "you travelled in May [1]\n\nnarrative footer"  # preserved
    assert fake.posted("/extract") == []  # the narrative path skips the typed pipeline


def test_typed_report_is_terminal() -> None:
    fake = FakeServices(route={"construct": "passport number", "time_indexed": False},
                        decides=[{"effector": "report", "value": "P123",
                                  "credences": [0.95, 0.05], "p_none": 0.05, "eu": 0.9}])
    view = _loop(fake, grow=False)
    assert view["effector"] == "report"
    assert view["asserted"] == ["P123"]
    assert view["candidates"] == ["P123"]
    assert view["n_obs"] == 1  # the footer's grounded-observation count is faithful


def test_extract_miss_short_circuits() -> None:
    # Zero grounded observations → the local edge declined; the loop returns a miss without
    # ever consulting the daemon.
    fake = FakeServices(route={"construct": "passport number", "time_indexed": False},
                        extract={"candidates": [], "observations": [], "rho": 0.7,
                                 "era_split": False, "indeterminate": 3, "half_life_years": 5.0})
    view = _loop(fake, grow=False)
    assert view["effector"] == "miss"
    assert view["candidates"] == []
    assert fake.posted("/decide") == []


def test_recency_gather_is_acknowledged_then_report() -> None:
    # The daemon schedules a recency gather; recency is PRE-APPLIED in /extract, so the body
    # acknowledges it (marks applied, re-decides on the same posterior) and the next decide reports.
    fake = FakeServices(
        route={"construct": "home address", "time_indexed": True},
        extract={**_EXTRACT, "era_split": True},
        decides=[{"effector": "gather", "probe": "recency", "credences": [0.6, 0.4],
                  "p_none": 0.1, "eu": 0.3},
                 {"effector": "report", "value": "P123", "credences": [0.9, 0.1],
                  "p_none": 0.05, "eu": 0.8}])
    view = _loop(fake, grow=False)
    assert view["effector"] == "report"
    decides = fake.posted("/decide")
    assert len(decides) == 2
    assert "recency" in decides[1]["applied_probes"]  # acknowledged on the re-decide


def test_corroborate_tier_is_enacted_then_report() -> None:
    # The daemon schedules a corroborate at the haiku tier; the body re-reads (whole-doc,
    # subject-aware) at that tier's model and re-decides on the replacement channel.
    fake = FakeServices(
        route={"construct": "tax id", "time_indexed": False},
        extract={**_EXTRACT, "candidates": ["P123", "Q999"]},
        corroborate={"observations": [{"reports": 0, "group": 0, "authority": 1.0,
                                       "subject_factor": 1.0, "time_factor": 1.0}],
                     "gather_rho": 0.80, "value": "P123"},
        decides=[{"effector": "gather", "probe": "corroborate_haiku",
                  "credences": [0.5, 0.5], "p_none": 0.1, "eu": 0.2},
                 {"effector": "report", "value": "P123", "credences": [0.9, 0.1],
                  "p_none": 0.05, "eu": 0.8}])
    view = _loop(fake, grow=False)
    assert view["effector"] == "report"
    corr = fake.posted("/probe/corroborate")
    assert len(corr) == 1
    assert corr[0]["reextract"] is True
    assert corr[0]["model"] == "claude-haiku-4-5"  # the scheduled tier's model


def test_grow_fires_when_none_is_the_map_hypothesis() -> None:
    # The cheap pass abstains AND the agent's belief says the answer is OUTSIDE the set — NONE
    # ("not among the retrieved candidates") outweighs the best present candidate (p_none ≥ leader).
    # That is the discovery case grow exists for: enlarge recall, re-decide, take the grown report.
    fake = FakeServices(
        route={"construct": "passport number", "time_indexed": False},
        decides=[{"effector": "abstain", "credences": [0.2, 0.1], "p_none": 0.7, "eu": -0.1},
                 {"effector": "report", "value": "P123", "credences": [0.9, 0.1],
                  "p_none": 0.05, "eu": 0.8}])
    view = _loop(fake, grow=True)
    assert view["effector"] == "report"
    assert view["asserted"] == ["P123"]
    retrieves = fake.posted("/retrieve")
    assert any(r["rerank"] for r in retrieves)  # grow ran a rerank recall pass


def test_grow_skipped_when_present_leader_beats_none() -> None:
    # A withhold whose present leader OUTWEIGHS NONE (p_none < leader) is the CORROBORATE case, not
    # grow: the agent believes the answer IS among the retrieved candidates (just under the EU bar),
    # so widening recall would only add distractors. The body consults the agent's P(NONE), not the
    # bare withholding effector (the de-patch — belief-driven recall, answer_brain.jl's NONE seam).
    fake = FakeServices(
        route={"construct": "passport number", "time_indexed": False},
        decides=[{"effector": "abstain", "credences": [0.55, 0.1], "p_none": 0.35, "eu": -0.05},
                 {"effector": "report", "value": "WRONG", "credences": [0.9, 0.1],
                  "p_none": 0.05, "eu": 0.8}])  # a grown report the gate must NOT reach
    view = _loop(fake, grow=True)
    assert view["effector"] == "abstain"        # stayed withheld — no grow rescue attempted
    assert view["asserted"] == []               # did NOT adopt the unreached grown report
    assert len(fake.posted("/retrieve")) == 1   # exactly one (cheap) recall pass; grow skipped


def test_truth_likely_missing_true_when_no_candidates() -> None:
    # Nothing extracted ⇒ the truth is definitionally not in the set ⇒ grow (discover).
    assert EX._truth_likely_missing(
        {"candidates": [], "credences": [], "p_none": None}) is True


def test_truth_likely_missing_true_when_none_is_map() -> None:
    # P(NONE) ≥ the best present candidate ⇒ the answer is likely outside the set ⇒ grow.
    assert EX._truth_likely_missing(
        {"candidates": ["a", "b"], "credences": [0.3, 0.2], "p_none": 0.5}) is True


def test_truth_likely_missing_false_when_present_leader_wins() -> None:
    # A present candidate outweighs NONE ⇒ the answer is likely in the set ⇒ corroborate, not grow.
    assert EX._truth_likely_missing(
        {"candidates": ["a", "b"], "credences": [0.6, 0.1], "p_none": 0.3}) is False


# --- the grow lane (slice 6): the DAEMON schedules recall; the body enacts + logs --------
# grow_lane=True replaces the hardcoded cascade: after a withholding terminal, the body
# re-decides WITH the grow block (sensors + menu actuators + warm counts); the daemon prices
# the grow argmax (engine grow_value over the structure-BMA g) and names the probe; the body
# enacts it, re-decides on the new evidence, and logs one gather outcome per enactment.

def test_grow_lane_daemon_schedules_retrieve_expand() -> None:
    fake = FakeServices(
        route={"construct": "passport number", "time_indexed": False},
        decides=[
            {"effector": "abstain", "credences": [0.2, 0.1], "p_none": 0.7, "eu": 0.0},
            {"effector": "gather", "probe": "retrieve_expand", "credences": [0.2, 0.1],
             "p_none": 0.7, "eu": 0.0},
            {"effector": "report", "value": "P123", "credences": [0.9, 0.1],
             "p_none": 0.05, "eu": 0.8},
        ])
    view = _loop(fake, grow_lane=True)
    assert view["effector"] == "report"
    decides = fake.posted("/decide")
    assert len(decides) == 3
    assert "grow" not in decides[0] and "sensors" not in decides[0]   # first pass is plain
    assert decides[1]["grow"]["actuators"][0]["probe"] == "retrieve_rerank"  # menu forwarded
    assert decides[1]["sensors"]["extracted"] == "some"
    assert decides[1]["sensors"]["p_none"] == "hi"                    # NONE is MAP ⇒ hi bucket
    retrieves = fake.posted("/retrieve")
    assert (retrieves[-1]["rerank"], retrieves[-1]["expand"]) == (True, True)  # enacted
    logged = fake.posted("/log_gather")
    assert len(logged) == 1
    assert logged[0]["probe"] == "retrieve_expand" and logged[0]["recovered"] is True


def test_grow_lane_respects_a_daemon_decline() -> None:
    # The daemon prices the grow lane and still withholds terminally ⇒ the body enacts NOTHING —
    # no cascade, no retry. The agent decides; the body carries it out (the de-patch).
    fake = FakeServices(
        route={"construct": "passport number", "time_indexed": False},
        decides=[
            {"effector": "abstain", "credences": [0.5, 0.2], "p_none": 0.3, "eu": 0.0},
            {"effector": "abstain", "credences": [0.5, 0.2], "p_none": 0.3, "eu": 0.0},
        ])
    view = _loop(fake, grow_lane=True)
    assert view["effector"] == "abstain"
    assert len(fake.posted("/retrieve")) == 1     # no recall enacted
    assert fake.posted("/log_gather") == []       # nothing enacted ⇒ nothing logged


def test_grow_lane_re_extract_strong_enlarges_k() -> None:
    # The daemon schedules the strong re-extract; the whole-doc re-read names a value OUTSIDE
    # the local candidate set ⇒ allow_new enlarges K and the re-decide reports the new value.
    fake = FakeServices(
        route={"construct": "tax id", "time_indexed": False},
        corroborate={"observations": [{"reports": 1, "group": 0, "authority": 1.0,
                                       "subject_factor": 1.0, "time_factor": 1.0}],
                     "gather_rho": 0.95, "value": "NEW-7", "new_candidate": "NEW-7"},
        decides=[
            {"effector": "abstain", "credences": [0.2], "p_none": 0.7, "eu": 0.0},
            {"effector": "gather", "probe": "re_extract_strong", "credences": [0.2],
             "p_none": 0.7, "eu": 0.0},
            {"effector": "report", "value": "NEW-7", "credences": [0.1, 0.9],
             "p_none": 0.0, "eu": 0.8},
        ])
    view = _loop(fake, grow_lane=True)
    assert view["effector"] == "report"
    assert view["asserted"] == ["NEW-7"]
    corr = fake.posted("/probe/corroborate")
    assert len(corr) == 1 and corr[0]["allow_new"] is True
    assert fake.posted("/decide")[2]["candidates"] == ["P123", "NEW-7"]  # K enlarged
    logged = fake.posted("/log_gather")
    assert logged[0]["probe"] == "re_extract_strong" and logged[0]["recovered"] is True


def test_grow_lane_zero_candidates_walks_the_menu_cheapest_first() -> None:
    # Nothing extracted ⇒ no posterior to price against (the k=0 degenerate case): the body
    # walks the menu cheapest-first until candidates appear, then the daemon decides. An
    # enactment that produced nothing logs recovered=False; the one that surfaced the
    # candidates logs the final report.
    empty = {"candidates": [], "observations": [], "rho": 0.7, "era_split": False,
             "indeterminate": 0, "half_life_years": 5.0}
    fake = FakeServices(
        route={"construct": "passport number", "time_indexed": False},
        extracts=[empty, empty, _EXTRACT],   # cheap, rerank (still empty), expand (grounds)
        decides=[{"effector": "report", "value": "P123", "credences": [0.95],
                  "p_none": 0.05, "eu": 0.9}])
    view = _loop(fake, grow_lane=True)
    assert view["effector"] == "report"
    logged = {p["probe"]: p["recovered"] for p in fake.posted("/log_gather")}
    assert logged == {"retrieve_rerank": False, "retrieve_expand": True}


def test_grow_lane_log_gather_failure_never_breaks_the_answer() -> None:
    # The gather-outcome write is fail-open by contract (as /log_decision is): a bridge blip
    # on /log_gather must never destroy an already-decided answer (review finding #1 on PR 20).
    empty = {"candidates": [], "observations": [], "rho": 0.7, "era_split": False,
             "indeterminate": 0, "half_life_years": 5.0}
    fake = FakeServices(
        route={"construct": "passport number", "time_indexed": False},
        extracts=[empty, _EXTRACT],
        decides=[{"effector": "report", "value": "P123", "credences": [0.95],
                  "p_none": 0.05, "eu": 0.9}])
    real_post = fake.post

    def flaky_post(url: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        if url.endswith("/log_gather"):
            raise OSError("bridge blip")
        return real_post(url, payload)

    fake.post = flaky_post  # type: ignore[method-assign]
    view = _loop(fake, grow_lane=True)
    assert view["effector"] == "report"
    assert view["asserted"] == ["P123"]


def test_re_extract_strong_empty_reread_collapses_the_channel() -> None:
    # The strong re-read REPLACES the channel exactly as corroborate does — including when it
    # comes back EMPTY (the strong model failed to confirm any local candidate): the weaker
    # local evidence must not survive it (review finding #2). The re-decide then runs on the
    # empty channel (disagree ⇒ NONE-dominant ⇒ abstain), never on the stale weak obs.
    fake = FakeServices(
        route={"construct": "tax id", "time_indexed": False},
        corroborate={"observations": [], "gather_rho": 0.95, "value": None},
        decides=[
            {"effector": "abstain", "credences": [0.2], "p_none": 0.7, "eu": 0.0},
            {"effector": "gather", "probe": "re_extract_strong", "credences": [0.2],
             "p_none": 0.7, "eu": 0.0},
            {"effector": "abstain", "credences": [0.1], "p_none": 0.9, "eu": 0.0},
            {"effector": "abstain", "credences": [0.1], "p_none": 0.9, "eu": 0.0},
        ])
    view = _loop(fake, grow_lane=True)
    assert view["effector"] == "abstain"
    decides = fake.posted("/decide")
    assert decides[2]["observations"] == []      # the channel was replaced, not kept
    assert decides[2]["rho"] == 0.95             # at the strong re-read's reliability


def test_zero_candidate_walk_retires_its_probes() -> None:
    # A retrieval actuator enacted in the k=0 walk is APPLIED: the daemon must not be offered
    # it again later in the same pass (review finding #3 — a re-offer would re-enact and
    # double-count one event into the warm-count fold).
    empty = {"candidates": [], "observations": [], "rho": 0.7, "era_split": False,
             "indeterminate": 0, "half_life_years": 5.0}
    fake = FakeServices(
        route={"construct": "passport number", "time_indexed": False},
        extracts=[empty, _EXTRACT],   # cheap empty; the rerank walk grounds
        decides=[
            {"effector": "abstain", "credences": [0.2], "p_none": 0.7, "eu": 0.0},
            {"effector": "abstain", "credences": [0.2], "p_none": 0.7, "eu": 0.0},
        ])
    view = _loop(fake, grow_lane=True)
    assert view["effector"] == "abstain"
    decides = fake.posted("/decide")
    # the grow-priced re-ask (2nd decide) already carries the walked probe as applied
    assert "retrieve_rerank" in decides[1]["applied_probes"]
    # and only ONE outcome row was logged for it (no double count)
    logged = [p for p in fake.posted("/log_gather") if p["probe"] == "retrieve_rerank"]
    assert len(logged) == 1


def test_grow_lane_off_keeps_the_legacy_cascade() -> None:
    # The flag gate (parity-safe cutover): grow_lane absent ⇒ the old cascade behaviour,
    # untouched — /grow_menu and /log_gather are never consulted.
    fake = FakeServices(
        route={"construct": "passport number", "time_indexed": False},
        decides=[{"effector": "abstain", "credences": [0.2, 0.1], "p_none": 0.7, "eu": -0.1},
                 {"effector": "report", "value": "P123", "credences": [0.9, 0.1],
                  "p_none": 0.05, "eu": 0.8}])
    view = _loop(fake, grow=True)
    assert view["effector"] == "report"
    assert fake.posted("/log_gather") == []
    assert all(not u.endswith("/grow_menu") for (u, _) in fake.calls)


# --- render_view: the executor's decision in the shared credence grammar ----------------

def test_render_view_report_uses_grammar_with_citations() -> None:
    view = {"effector": "report", "asserted": ["P123"], "candidates": ["P123", "Q9"],
            "credences": [0.92, 0.08], "p_none": 0.05, "eu": 0.8, "n_obs": 3,
            "hits": [{"artifact_cache_key": "d0", "chunk_text": "Passport No: P123"},
                     {"artifact_cache_key": "d1", "chunk_text": "unrelated chunk"}],
            "route": {"construct": "passport number"}}
    out = EX.render_view(view)
    assert "P123" in out
    assert "credence 0.920" in out
    assert "[1]" in out and "[2]" not in out  # only the hit carrying the value is cited
    assert "decision report" in out            # the footer names the posterior


def test_render_view_abstain_with_no_candidates() -> None:
    view = {"effector": "abstain", "asserted": [], "candidates": [], "credences": [],
            "p_none": 0.9, "eu": 0.0, "n_obs": 0, "hits": [], "route": {}}
    out = EX.render_view(view)
    assert "No answer asserted" in out


def test_render_view_report_shows_the_leaders_credence_not_index0() -> None:
    # The daemon returns credences in CANDIDATE order (server.jl w[1:k]), not weight-sorted; the
    # reported value is the MAP/leader, generally NOT index 0. render_view must show the LEADER's
    # credence — else a report states the first-extracted candidate's probability (the bridge's
    # /log_decision already sorts leader-first; render_view must match).
    view = {"effector": "report", "asserted": ["P123"], "candidates": ["Q9", "P123"],
            "credences": [0.08, 0.92], "p_none": 0.0, "eu": 0.8, "n_obs": 2,
            "hits": [{"artifact_cache_key": "d0", "chunk_text": "Passport No: P123"}],
            "route": {"construct": "passport number"}}
    out = EX.render_view(view)
    assert "credence 0.920" in out      # the leader P123's credence
    assert "credence 0.080" not in out  # not the first-extracted candidate's


def test_render_view_narrative_passes_through_verbatim() -> None:
    # A narrative view is rendered bridge-side; render_view returns it unchanged.
    view = {"effector": "report", "asserted": ["x"], "candidates": [], "credences": [],
            "p_none": None, "eu": None, "n_obs": 0, "hits": [], "route": None,
            "rendered": "you travelled in May [1]\n\nnarrative footer"}
    assert EX.render_view(view) == "you travelled in May [1]\n\nnarrative footer"


# --- the k=0 strong rescue (extraction-loss conversion; the q-005 class) -----------------
# Nothing grounds locally AND every retrieval rung of the k=0 walk comes back empty: the walk
# now reaches its last, priciest rung — the strong whole-doc re-read with allow_new — instead
# of conceding miss with the one capable reader unconsulted. The minted candidate hands the
# decision straight back to the daemon (k >= 1 again); the rescue conditions at the READ'S OWN
# stated confidence (capped by the tier prior), so a hesitant strong read hedges rather than
# asserting at the tier's flat rho — the wire must not discard the instrument's uncertainty.

_EMPTY_EXTRACT = {"candidates": [], "observations": [], "rho": 0.7, "era_split": False,
                  "indeterminate": 2, "half_life_years": 5.0}


def test_zero_candidate_walk_reaches_the_strong_re_extract() -> None:
    fake = FakeServices(
        route={"construct": "mortgage", "time_indexed": False},
        extracts=[_EMPTY_EXTRACT, _EMPTY_EXTRACT, _EMPTY_EXTRACT],
        corroborate={"observations": [{"reports": 0, "group": 0, "authority": 1.0,
                                       "subject_factor": 1.0, "time_factor": 1.0}],
                     "gather_rho": 0.95, "value": "NEW-7", "new_candidate": "NEW-7",
                     "confidence": 0.9},
        decides=[{"effector": "report", "value": "NEW-7", "credences": [0.93],
                  "p_none": 0.07, "eu": 0.8}])
    view = _loop(fake, grow_lane=True)
    assert view["effector"] == "report"
    assert view["asserted"] == ["NEW-7"]
    corr = fake.posted("/probe/corroborate")
    assert len(corr) == 1
    assert corr[0]["allow_new"] is True and corr[0]["candidates"] == []
    decides = fake.posted("/decide")
    assert decides[0]["candidates"] == ["NEW-7"]
    assert decides[0]["rho"] == 0.5              # min(_RESCUE_RHO 0.5, confidence 0.9)
    logged = {p["probe"]: p["recovered"] for p in fake.posted("/log_gather")}
    assert logged == {"retrieve_rerank": False, "retrieve_expand": False,
                      "re_extract_strong": True}


def test_zero_candidate_rescue_carries_low_confidence_into_rho() -> None:
    # The q-005 shape: the strong read answers but says 0.55 — the decide must condition
    # below the wide-prior cap, never at the tier's 0.95 (the flat rho asserted a
    # near-miss at credence 0.995; the self-confidence rho asserted a vague read, q-015).
    fake = FakeServices(
        route={"construct": "mortgage", "time_indexed": False},
        extracts=[_EMPTY_EXTRACT, _EMPTY_EXTRACT, _EMPTY_EXTRACT],
        corroborate={"observations": [{"reports": 0, "group": 0, "authority": 1.0,
                                       "subject_factor": 1.0, "time_factor": 1.0}],
                     "gather_rho": 0.95, "value": "NEW-7", "new_candidate": "NEW-7",
                     "confidence": 0.35},
        decides=[{"effector": "hedge", "credences": [0.62], "p_none": 0.38, "eu": 0.3}])
    view = _loop(fake, grow_lane=True)
    assert view["effector"] == "hedge"
    assert view["candidates"] == ["NEW-7"]       # named, not silently dropped
    assert fake.posted("/decide")[0]["rho"] == 0.35


def test_zero_candidate_rescue_without_confidence_uses_the_prior_cap() -> None:
    # A legacy bridge reply without "confidence" degrades to the wide prior, never crashes.
    fake = FakeServices(
        route={"construct": "mortgage", "time_indexed": False},
        extracts=[_EMPTY_EXTRACT, _EMPTY_EXTRACT, _EMPTY_EXTRACT],
        corroborate={"observations": [{"reports": 0, "group": 0, "authority": 1.0,
                                       "subject_factor": 1.0, "time_factor": 1.0}],
                     "gather_rho": 0.95, "value": "NEW-7", "new_candidate": "NEW-7"},
        decides=[{"effector": "report", "value": "NEW-7", "credences": [0.93],
                  "p_none": 0.07, "eu": 0.8}])
    _loop(fake, grow_lane=True)
    assert fake.posted("/decide")[0]["rho"] == 0.5


def test_zero_candidate_rescue_empty_read_stays_miss() -> None:
    # The q-017 shape (known-unanswerable, junk pool): the strong read names nothing ⇒ no
    # candidate is minted, no decide fires, the miss stands — the rescue must not turn an
    # honest miss into anything else.
    fake = FakeServices(
        route={"construct": "visa expiry", "time_indexed": False},
        extracts=[_EMPTY_EXTRACT, _EMPTY_EXTRACT, _EMPTY_EXTRACT],
        corroborate={"observations": [], "gather_rho": 0.95, "value": None,
                     "confidence": None})
    view = _loop(fake, grow_lane=True)
    assert view["effector"] == "miss"
    assert fake.posted("/decide") == []
    logged = {p["probe"]: p["recovered"] for p in fake.posted("/log_gather")}
    assert logged["re_extract_strong"] is False


def test_zero_candidate_rescue_needs_hits() -> None:
    # Nothing retrieved at any breadth ⇒ there is nothing to re-read: no corroborate call.
    fake = FakeServices(
        route={"construct": "mortgage", "time_indexed": False},
        hits=[],
        extracts=[_EMPTY_EXTRACT, _EMPTY_EXTRACT, _EMPTY_EXTRACT])
    view = _loop(fake, grow_lane=True)
    assert view["effector"] == "miss"
    assert fake.posted("/probe/corroborate") == []


def test_zero_candidates_without_grow_lane_stays_miss() -> None:
    # Flag parity: grow_lane off keeps the legacy k=0 behaviour byte-for-byte — the breadth
    # cascade still walks its three passes, but no rescue, no corroborate, no decide.
    fake = FakeServices(
        route={"construct": "mortgage", "time_indexed": False},
        extracts=[_EMPTY_EXTRACT, _EMPTY_EXTRACT, _EMPTY_EXTRACT])
    view = _loop(fake)
    assert view["effector"] == "miss"
    assert fake.posted("/probe/corroborate") == []
    assert fake.posted("/decide") == []


# --- M3: the live coarse-menu consult threads through to the seam ------------------------

def test_live_consult_rewrites_the_terminal_view() -> None:
    # the daemon says report; the injected live consult (the seam's DaemonDecide.live)
    # overrides to abstain — the loop terminates on the REWRITTEN view.
    fake = FakeServices(
        route={"construct": "passport number", "time_indexed": False},
        decides=[{"effector": "report", "value": "P123", "credences": [0.9],
                  "p_none": 0.05, "eu": 0.8}])
    consults: list[tuple[dict[str, Any], dict[str, Any]]] = []

    def live(payload: dict[str, Any], dec: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
        consults.append((payload, dec))
        return ({**dec, "effector": "abstain", "value": None}, None)

    view = _loop(fake, grow=False, live=live)
    assert view["effector"] == "abstain"
    assert view["asserted"] == []
    assert len(consults) == 1
    assert consults[0][1]["effector"] == "report"  # consulted with the daemon's own reply


def test_live_consult_gather_override_enacts_the_probe() -> None:
    # daemon terminal-abstains twice; the live consult overrides the FIRST to a gather at
    # the haiku tier (the transitional fine selection) and passes the second through — the
    # loop enacts the corroborate re-read exactly as a daemon-scheduled gather.
    fake = FakeServices(
        route={"construct": "tax id", "time_indexed": False},
        corroborate={"observations": [{"reports": 0, "group": 0, "authority": 1.0,
                                       "subject_factor": 1.0, "time_factor": 1.0}],
                     "gather_rho": 0.80, "value": "P123"},
        decides=[{"effector": "abstain", "value": None, "credences": [0.5],
                  "p_none": 0.4, "eu": 0.0},
                 {"effector": "abstain", "value": None, "credences": [0.6],
                  "p_none": 0.3, "eu": 0.0}])
    calls = iter([("gather", "corroborate_haiku"), (None, None)])

    def live(payload: dict[str, Any], dec: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
        eff, probe = next(calls)
        if eff is None:
            return (dec, None)
        return ({**dec, "effector": eff, "probe": probe}, None)

    view = _loop(fake, grow=False, live=live)
    assert view["effector"] == "abstain"
    corr = fake.posted("/probe/corroborate")
    assert len(corr) == 1
    assert corr[0]["model"] == "claude-haiku-4-5"
    assert len(fake.posted("/decide")) == 2


# --- per-edge calibration threading (plan item 3: constants become the curve) ------------
#
# With `curves` supplied, a read's self-stated confidence folds through the per-edge
# reliability curve (calibration.curve_for — pessimistic cold start) instead of the flat
# constants. Without `curves` (every existing call site) behaviour is bit-identical to the
# constants — pinned by all the tests above.


def _fitted_curves(edge: str, confidence: float, n: int = 40) -> dict[str, Any]:
    from life_agent.core import calibration as CAL

    return {edge: CAL.fit_reliability_curve([CAL.Outcome(confidence, True)] * n)}


def test_rescue_folds_confidence_through_the_edge_curve() -> None:
    # Same fixture as the walk-reaches-strong-re-extract test, but with a fitted curve for
    # the opus extract edge: the decide conditions at curve(0.9), not min(0.5, 0.9).
    curves = _fitted_curves("extract@claude-opus-4-8", 0.9)
    expected = curves["extract@claude-opus-4-8"].calibrate(0.9)
    assert expected > 0.5  # the fitted edge has EARNED more than the flat cap
    fake = FakeServices(
        route={"construct": "mortgage", "time_indexed": False},
        extracts=[_EMPTY_EXTRACT, _EMPTY_EXTRACT, _EMPTY_EXTRACT],
        corroborate={"observations": [{"reports": 0, "group": 0, "authority": 1.0,
                                       "subject_factor": 1.0, "time_factor": 1.0}],
                     "gather_rho": 0.95, "value": "NEW-7", "new_candidate": "NEW-7",
                     "confidence": 0.9},
        decides=[{"effector": "report", "value": "NEW-7", "credences": [0.93],
                  "p_none": 0.07, "eu": 0.8}])
    _loop(fake, grow_lane=True, curves=curves)
    assert fake.posted("/decide")[0]["rho"] == expected


def test_rescue_unmeasured_edge_keeps_the_declared_cap() -> None:
    # curves supplied but the edge has no attributed rows: the PER-EDGE regime keeps
    # the declared fallback (min(cap, confidence) = 0.5 here) — another edge's
    # evidence must never regime-switch this one to the cold start (§2, never
    # pooled). [Supersedes the global-switch pin: "curves={} ⇒ 0.25" was an artifact
    # of treating the fold's non-emptiness as one regime for ALL edges.]
    fake = FakeServices(
        route={"construct": "mortgage", "time_indexed": False},
        extracts=[_EMPTY_EXTRACT, _EMPTY_EXTRACT, _EMPTY_EXTRACT],
        corroborate={"observations": [{"reports": 0, "group": 0, "authority": 1.0,
                                       "subject_factor": 1.0, "time_factor": 1.0}],
                     "gather_rho": 0.95, "value": "NEW-7", "new_candidate": "NEW-7",
                     "confidence": 0.9},
        decides=[{"effector": "hedge", "credences": [0.6], "p_none": 0.4, "eu": 0.1}])
    _loop(fake, grow_lane=True, curves={})
    assert fake.posted("/decide")[0]["rho"] == 0.5


def test_rescue_measured_edge_folds_through_its_curve_cold_bins() -> None:
    # the §16 pessimism survives per-edge: once the rescue edge IS measured, its curve
    # rules — a confidence landing in an unobserved bin folds at the Beta(1,3) cold
    # start (0.25), stricter than the 0.5 cap, never looser.
    curves = _fitted_curves("extract@claude-opus-4-8", 0.95)
    fake = FakeServices(
        route={"construct": "mortgage", "time_indexed": False},
        extracts=[_EMPTY_EXTRACT, _EMPTY_EXTRACT, _EMPTY_EXTRACT],
        corroborate={"observations": [{"reports": 0, "group": 0, "authority": 1.0,
                                       "subject_factor": 1.0, "time_factor": 1.0}],
                     "gather_rho": 0.95, "value": "NEW-7", "new_candidate": "NEW-7",
                     "confidence": 0.9},
        decides=[{"effector": "hedge", "credences": [0.6], "p_none": 0.4, "eu": 0.1}])
    _loop(fake, grow_lane=True, curves=curves)
    assert (fake.posted("/decide")[0]["rho"]
            == curves["extract@claude-opus-4-8"].calibrate(0.9))


def test_corroborate_tier_folds_confidence_through_the_edge_curve() -> None:
    # The scheduled haiku tier's re-read states its own confidence; with curves the
    # conditioning rho is curve(confidence) for extract@claude-haiku-4-5, not the echoed
    # gather_rho — the instrument's uncertainty is no longer discarded on regular tiers.
    curves = _fitted_curves("extract@claude-haiku-4-5", 0.7)
    expected = curves["extract@claude-haiku-4-5"].calibrate(0.7)
    fake = FakeServices(
        route={"construct": "tax id", "time_indexed": False},
        extract={**_EXTRACT, "candidates": ["P123", "Q999"]},
        corroborate={"observations": [{"reports": 0, "group": 0, "authority": 1.0,
                                       "subject_factor": 1.0, "time_factor": 1.0}],
                     "gather_rho": 0.80, "value": "P123", "confidence": 0.7},
        decides=[{"effector": "gather", "probe": "corroborate_haiku",
                  "credences": [0.5, 0.5], "p_none": 0.1, "eu": 0.2},
                 {"effector": "report", "value": "P123", "credences": [0.9, 0.1],
                  "p_none": 0.05, "eu": 0.8}])
    _loop(fake, grow=False, curves=curves)
    assert fake.posted("/decide")[1]["rho"] == expected


def test_deliberate_gather_is_enacted_and_folds_through_its_curve() -> None:
    # The daemon schedules the deliberate transform (the promoted A1b edge); the body
    # enacts it via /probe/deliberate and re-decides at curve(confidence) for the
    # deliberate@<model> edge — the raw self-report is a signal, never the rho.
    curves = _fitted_curves("deliberate@claude-opus-4-8", 0.85)
    expected = curves["deliberate@claude-opus-4-8"].calibrate(0.85)
    fake = FakeServices(
        route={"construct": "rent", "time_indexed": False},
        extract={**_EXTRACT, "candidates": ["NIS 4,200", "NIS 9,999"]},
        deliberate={"observations": [{"reports": 0, "group": 0, "authority": 1.0,
                                      "subject_factor": 1.0, "time_factor": 1.0}],
                    "confidence": 0.85, "model": "claude-opus-4-8",
                    "value": "NIS 4,200", "status": "ok", "declined": False,
                    "cost_usd": 0.42, "latency_s": 23.0, "cache": "miss"},
        decides=[{"effector": "gather", "probe": "deliberate",
                  "credences": [0.5, 0.5], "p_none": 0.3, "eu": 0.1},
                 {"effector": "report", "value": "NIS 4,200", "credences": [0.9, 0.1],
                  "p_none": 0.05, "eu": 0.8}])
    view = _loop(fake, grow=False, curves=curves,
                 transforms=[*EX.DEFAULT_TRANSFORMS, EX.DELIBERATE_TRANSFORM])
    assert view["effector"] == "report"
    delib = fake.posted("/probe/deliberate")
    assert len(delib) == 1
    assert delib[0]["question"] == "what is my passport number?"
    assert delib[0]["allow_new"] is True
    assert fake.posted("/decide")[1]["rho"] == expected


def test_deliberate_tick_prices_the_view() -> None:
    # The view names the edge that answered and its realised price, so the terminal
    # decision logs with the §10 accounting attached (decisions v2 fields).
    fake = FakeServices(
        route={"construct": "rent", "time_indexed": False},
        extract={**_EXTRACT, "candidates": ["NIS 4,200"]},
        deliberate={"observations": [{"reports": 0, "group": 0, "authority": 1.0,
                                      "subject_factor": 1.0, "time_factor": 1.0}],
                    "confidence": 0.85, "model": "claude-opus-4-8",
                    "value": "NIS 4,200", "status": "ok", "declined": False,
                    "cost_usd": 0.42, "latency_s": 23.0, "cache": "miss"},
        decides=[{"effector": "gather", "probe": "deliberate",
                  "credences": [0.5], "p_none": 0.3, "eu": 0.1},
                 {"effector": "report", "value": "NIS 4,200", "credences": [0.9],
                  "p_none": 0.05, "eu": 0.8}])
    view = _loop(fake, grow=False, curves={})
    assert view["instrument"] == "deliberate@claude-opus-4-8"
    assert view["cost_usd"] == 0.42
    assert view["latency_s"] == 23.0


def test_view_without_a_deliberate_tick_is_unpriced() -> None:
    fake = FakeServices(
        route={"construct": "tax id", "time_indexed": False},
        decides=[{"effector": "report", "value": "P123", "credences": [0.95],
                  "p_none": 0.02, "eu": 0.9}])
    view = _loop(fake, grow=False)
    assert view["instrument"] == ""
    assert view["cost_usd"] is None


def test_deliberate_tick_carries_the_raw_proposal_on_the_view() -> None:
    # The attributed-outcome writer grades the edge's RAW proposal against gold,
    # independent of the committed act — the view must surface what the edge SAID
    # (value), its self-report (the curve's signal axis), and the §18.9 lineage
    # (the warm-replay dedup key). The committed act here is abstain: the proposal
    # must survive on the view regardless.
    fake = FakeServices(
        route={"construct": "rent", "time_indexed": False},
        extract={**_EXTRACT, "candidates": ["NIS 4,200"]},
        deliberate={"observations": [{"reports": 0, "group": 0, "authority": 1.0,
                                      "subject_factor": 1.0, "time_factor": 1.0}],
                    "confidence": 0.85, "model": "claude-opus-4-8",
                    "value": "NIS 4,200", "status": "ok", "declined": False,
                    "cost_usd": 0.42, "latency_s": 23.0, "cache": "miss",
                    "cache_key": "dk-42"},
        decides=[{"effector": "gather", "probe": "deliberate",
                  "credences": [0.5], "p_none": 0.3, "eu": 0.1},
                 {"effector": "abstain", "credences": [0.4], "p_none": 0.6,
                  "eu": 0.0}])
    view = _loop(fake, grow=False, curves={})
    assert view["effector"] == "abstain"
    assert view["instrument_value"] == "NIS 4,200"
    assert view["instrument_confidence"] == 0.85
    assert view["instrument_lineage"] == "dk-42"


def test_view_without_a_deliberate_tick_has_no_raw_proposal() -> None:
    # All consumers INDEX these keys (never .get) — the defaults must exist on the
    # plain typed path.
    fake = FakeServices(
        route={"construct": "tax id", "time_indexed": False},
        decides=[{"effector": "report", "value": "P123", "credences": [0.95],
                  "p_none": 0.02, "eu": 0.9}])
    view = _loop(fake, grow=False)
    assert view["instrument_value"] is None
    assert view["instrument_confidence"] is None
    assert view["instrument_lineage"] is None


def test_miss_and_narrative_views_default_the_raw_proposal_fields() -> None:
    # The other two View return sites (extract-miss short circuit, narrative family)
    # carry the same keys with the same defaults.
    miss = _loop(FakeServices(
        route={"construct": "passport number", "time_indexed": False},
        extract={"candidates": [], "observations": [], "rho": 0.7,
                 "era_split": False, "indeterminate": 3, "half_life_years": 5.0}),
        grow=False)
    assert miss["effector"] == "miss"
    assert miss["instrument_value"] is None
    assert miss["instrument_lineage"] is None
    narr = _loop(FakeServices(route=None, narrative={
        "action": "report", "asserted": ["you travelled in May"],
        "rendered": "you travelled in May [1]\n\nnarrative footer",
        "hits": [{"artifact_cache_key": "d0", "chunk_text": "x"}]}),
        "tell me about my week")
    assert narr["instrument_value"] is None
    assert narr["instrument_lineage"] is None


def test_deliberate_decline_leaves_no_gradeable_proposal() -> None:
    # NOT_IN_CORPUS: no value proposed — nothing for the writer to grade (declines
    # are not graded rows, a stated v0 coarsening) — but the lineage still names the
    # §18.9 artifact (a decline IS recorded).
    fake = FakeServices(
        route={"construct": "rent", "time_indexed": False},
        extract={**_EXTRACT, "candidates": ["NIS 9,999"]},
        deliberate={"observations": [], "confidence": None, "model": "claude-opus-4-8",
                    "value": None, "status": "ok", "declined": True, "cache": "miss",
                    "cache_key": "dk-declined"},
        decides=[{"effector": "gather", "probe": "deliberate",
                  "credences": [0.4], "p_none": 0.5, "eu": 0.0},
                 {"effector": "abstain", "credences": [0.1], "p_none": 0.9,
                  "eu": 0.0}])
    view = _loop(fake, grow=False, curves={})
    assert view["instrument_value"] is None
    assert view["instrument_confidence"] is None
    assert view["instrument_lineage"] == "dk-declined"


def test_run_pass_prices_the_menu_in_owner_utility_via_lambda_usd() -> None:
    # plan item C: transform rows are AUTHORED in USD; the decide payload prices them in
    # gauge utility at u_bar's elicited exchange rate — the rate is a learned latent,
    # never a constant invented in a menu row.
    fake = FakeServices(
        route={"construct": "tax id", "time_indexed": False},
        utility={**_U, "lambda_usd": 2.0},
        decides=[{"effector": "report", "value": "P123", "credences": [0.95],
                  "p_none": 0.02, "eu": 0.9}])
    _loop(fake, grow=False)
    sent = fake.posted("/decide")[0]["transforms"]
    authored = {t["probe"]: t["cost"] for t in EX.DEFAULT_TRANSFORMS if "cost" in t}
    priced = {t["probe"]: t["cost"] for t in sent if "cost" in t}
    assert priced["corroborate_haiku"] == 2.0 * authored["corroborate_haiku"]
    assert priced["corroborate_opus"] == 2.0 * authored["corroborate_opus"]


def test_run_pass_without_the_rate_latent_keeps_legacy_costs() -> None:
    # legacy parity: a u_bar lacking lambda_usd (pre-elicitation prod) prices at the
    # old $1 ≈ 1-gauge convention — costs ride through unchanged.
    fake = FakeServices(
        route={"construct": "tax id", "time_indexed": False},
        decides=[{"effector": "report", "value": "P123", "credences": [0.95],
                  "p_none": 0.02, "eu": 0.9}])
    _loop(fake, grow=False)
    sent = {t["probe"]: t["cost"]
            for t in fake.posted("/decide")[0]["transforms"] if "cost" in t}
    assert sent["corroborate_haiku"] == next(
        t["cost"] for t in EX.DEFAULT_TRANSFORMS if t["probe"] == "corroborate_haiku")


def test_run_pass_prices_the_grow_block_at_the_same_rate() -> None:
    # the grow actuators' costs are the same authored-USD convention — one rate, one
    # place (the decide payload), bridge untouched.
    fake = FakeServices(
        route={"construct": "passport number", "time_indexed": False},
        utility={**_U, "lambda_usd": 2.0},
        decides=[{"effector": "abstain", "credences": [0.2], "p_none": 0.7, "eu": -0.1},
                 {"effector": "abstain", "credences": [0.2], "p_none": 0.7, "eu": -0.1}])
    _loop(fake, grow_lane=True)
    with_grow = [p for p in fake.posted("/decide") if "grow" in p]
    assert with_grow, "the withhold re-ask must carry the grow block"
    costs = {a["probe"]: a["cost"] for a in with_grow[0]["grow"]["actuators"]}
    assert costs["re_extract_strong"] == 2.0 * 0.020


# --- edge_events: the attribution stream for the extract-tier writers --------------------
# Every answer-proposing firing (corroborate tiers, the k=0 rescue, re_extract_strong,
# deliberate) appends ONE event {edge, value, confidence, lineage} in firing order — the
# gate's writer grades each event's OWN raw proposal against gold, so the cheap tiers'
# curves finally accrue evidence. Edges key on the REQUESTED model: decide-time
# conditioning looks up extract_edge(requested), and served_model is "" on §18.9 warm
# replays — stamping it would split the curve namespace.

def test_corroborate_tier_appends_an_edge_event() -> None:
    fake = FakeServices(
        route={"construct": "tax id", "time_indexed": False},
        extract={**_EXTRACT, "candidates": ["P123", "Q999"]},
        corroborate={"observations": [{"reports": 0, "group": 0, "authority": 1.0,
                                       "subject_factor": 1.0, "time_factor": 1.0}],
                     "gather_rho": 0.80, "value": "P123", "confidence": 0.7,
                     "cache_key": "jk-1"},
        decides=[{"effector": "gather", "probe": "corroborate_haiku",
                  "credences": [0.5, 0.5], "p_none": 0.1, "eu": 0.2},
                 {"effector": "report", "value": "P123", "credences": [0.9, 0.1],
                  "p_none": 0.05, "eu": 0.8}])
    view = _loop(fake, grow=False)
    assert view["edge_events"] == [{"edge": "extract@claude-haiku-4-5", "value": "P123",
                                    "confidence": 0.7, "lineage": "jk-1"}]


def test_escalating_tiers_append_one_event_each() -> None:
    # haiku then opus both fire (each tier at most once); two events, firing order.
    fake = FakeServices(
        route={"construct": "tax id", "time_indexed": False},
        extract={**_EXTRACT, "candidates": ["P123", "Q999"]},
        corroborate={"observations": [{"reports": 0, "group": 0, "authority": 1.0,
                                       "subject_factor": 1.0, "time_factor": 1.0}],
                     "gather_rho": 0.80, "value": "P123", "confidence": 0.7,
                     "cache_key": "jk-1"},
        decides=[{"effector": "gather", "probe": "corroborate_haiku",
                  "credences": [0.5, 0.5], "p_none": 0.1, "eu": 0.2},
                 {"effector": "gather", "probe": "corroborate_opus",
                  "credences": [0.6, 0.4], "p_none": 0.1, "eu": 0.3},
                 {"effector": "report", "value": "P123", "credences": [0.9, 0.1],
                  "p_none": 0.05, "eu": 0.8}])
    view = _loop(fake, grow=False)
    assert [e["edge"] for e in view["edge_events"]] == [
        "extract@claude-haiku-4-5", "extract@claude-opus-4-8"]


def test_rescue_walk_appends_an_edge_event() -> None:
    # the k=0 strong rescue fires the opus re-read; its proposal is a gradeable firing
    # whether or not the committed act later reports.
    fake = FakeServices(
        route={"construct": "mortgage", "time_indexed": False},
        extracts=[_EMPTY_EXTRACT, _EMPTY_EXTRACT, _EMPTY_EXTRACT],
        corroborate={"observations": [{"reports": 0, "group": 0, "authority": 1.0,
                                       "subject_factor": 1.0, "time_factor": 1.0}],
                     "gather_rho": 0.95, "value": "NEW-7", "new_candidate": "NEW-7",
                     "confidence": 0.9, "cache_key": "jk-r"},
        decides=[{"effector": "report", "value": "NEW-7", "credences": [0.93],
                  "p_none": 0.07, "eu": 0.8}])
    view = _loop(fake, grow_lane=True)
    assert view["edge_events"] == [{"edge": "extract@claude-opus-4-8", "value": "NEW-7",
                                    "confidence": 0.9, "lineage": "jk-r"}]


def test_non_minting_rescue_event_survives_on_the_miss_view() -> None:
    # a declining strong read (value None) still fired and still names its §18.9
    # artifact — the event rides the MISS view with its lineage (nothing to grade,
    # but the dedup axis is preserved for any future decline-aware fold).
    fake = FakeServices(
        route={"construct": "visa expiry", "time_indexed": False},
        extracts=[_EMPTY_EXTRACT, _EMPTY_EXTRACT, _EMPTY_EXTRACT],
        corroborate={"observations": [], "gather_rho": 0.95, "value": None,
                     "confidence": None, "cache_key": "jk-d"})
    view = _loop(fake, grow_lane=True)
    assert view["effector"] == "miss"
    assert view["edge_events"] == [{"edge": "extract@claude-opus-4-8", "value": None,
                                    "confidence": None, "lineage": "jk-d"}]


def test_re_extract_strong_appends_an_edge_event() -> None:
    fake = FakeServices(
        route={"construct": "tax id", "time_indexed": False},
        extract={**_EXTRACT, "candidates": ["P123"]},
        corroborate={"observations": [{"reports": 0, "group": 0, "authority": 1.0,
                                       "subject_factor": 1.0, "time_factor": 1.0}],
                     "gather_rho": 0.95, "value": "P123", "confidence": 0.8,
                     "cache_key": "jk-s"},
        decides=[{"effector": "gather", "probe": "re_extract_strong",
                  "credences": [0.5], "p_none": 0.2, "eu": 0.2},
                 {"effector": "report", "value": "P123", "credences": [0.9],
                  "p_none": 0.05, "eu": 0.8}])
    view = _loop(fake, grow=False)
    assert view["edge_events"] == [{"edge": "extract@claude-opus-4-8", "value": "P123",
                                    "confidence": 0.8, "lineage": "jk-s"}]


def test_deliberate_appends_an_edge_event_and_keeps_the_legacy_slot() -> None:
    # deliberate appears in the event stream like every other firing, AND the six
    # decisions-v2 single-slot fields stay byte-identical (their consumers: the
    # /log_decision accounting and executor_run_stats — requirement-2 pin).
    fake = FakeServices(
        route={"construct": "rent", "time_indexed": False},
        extract={**_EXTRACT, "candidates": ["NIS 4,200"]},
        deliberate={"observations": [{"reports": 0, "group": 0, "authority": 1.0,
                                      "subject_factor": 1.0, "time_factor": 1.0}],
                    "confidence": 0.85, "model": "claude-opus-4-8",
                    "value": "NIS 4,200", "status": "ok", "declined": False,
                    "cost_usd": 0.42, "latency_s": 23.0, "cache": "miss",
                    "cache_key": "dk-42"},
        decides=[{"effector": "gather", "probe": "deliberate",
                  "credences": [0.5], "p_none": 0.3, "eu": 0.1},
                 {"effector": "abstain", "credences": [0.4], "p_none": 0.6,
                  "eu": 0.0}])
    view = _loop(fake, grow=False, curves={})
    assert view["edge_events"] == [{"edge": "deliberate@claude-opus-4-8",
                                    "value": "NIS 4,200", "confidence": 0.85,
                                    "lineage": "dk-42"}]
    assert view["instrument"] == "deliberate@claude-opus-4-8"
    assert view["cost_usd"] == 0.42
    assert view["latency_s"] == 23.0
    assert view["instrument_value"] == "NIS 4,200"
    assert view["instrument_confidence"] == 0.85
    assert view["instrument_lineage"] == "dk-42"


def test_view_spend_accumulates_every_metered_firing() -> None:
    # PR #67 review: view["cost_usd"] is the deliberate slot (decisions-v2) — the gate's
    # spend feed needs the TOTAL realised spend, tiers included, or the run-6 term
    # prices typed tier spend at $0 while the replay arm is fully priced.
    fake = FakeServices(
        route={"construct": "rent", "time_indexed": False},
        extract={**_EXTRACT, "candidates": ["NIS 4,200", "NIS 9,999"]},
        corroborate={"observations": [{"reports": 0, "group": 0, "authority": 1.0,
                                       "subject_factor": 1.0, "time_factor": 1.0}],
                     "gather_rho": 0.80, "value": "NIS 4,200", "confidence": 0.7,
                     "cache_key": "jk-1", "cost_usd": 0.012},
        deliberate={"observations": [{"reports": 0, "group": 0, "authority": 1.0,
                                      "subject_factor": 1.0, "time_factor": 1.0}],
                    "confidence": 0.85, "model": "claude-opus-4-8",
                    "value": "NIS 4,200", "status": "ok", "declined": False,
                    "cost_usd": 0.42, "latency_s": 23.0, "cache": "miss",
                    "cache_key": "dk-42"},
        decides=[{"effector": "gather", "probe": "corroborate_haiku",
                  "credences": [0.5, 0.5], "p_none": 0.1, "eu": 0.2},
                 {"effector": "gather", "probe": "deliberate",
                  "credences": [0.6, 0.4], "p_none": 0.1, "eu": 0.3},
                 {"effector": "report", "value": "NIS 4,200", "credences": [0.9, 0.1],
                  "p_none": 0.05, "eu": 0.8}])
    view = _loop(fake, grow=False, curves={},
                 transforms=[*EX.DEFAULT_TRANSFORMS, EX.DELIBERATE_TRANSFORM])
    assert view["spend_usd"] == 0.012 + 0.42
    assert view["cost_usd"] == 0.42  # the decisions-v2 deliberate slot, untouched


def test_all_view_shapes_carry_spend() -> None:
    plain = _loop(FakeServices(
        route={"construct": "tax id", "time_indexed": False},
        decides=[{"effector": "report", "value": "P123", "credences": [0.95],
                  "p_none": 0.02, "eu": 0.9}]), grow=False)
    assert plain["spend_usd"] == 0.0
    narr = _loop(FakeServices(route=None, narrative={
        "action": "report", "asserted": ["you travelled in May"],
        "rendered": "you travelled in May [1]\n\nnarrative footer",
        "hits": [{"artifact_cache_key": "d0", "chunk_text": "x"}]}),
        "tell me about my week")
    assert narr["spend_usd"] == 0.0


def test_grow_menu_actuator_without_cost_rides_through() -> None:
    # PR #67 review: a version-skewed bridge serving a cost-less actuator row must not
    # KeyError the whole question inside the re-pricing map — guard like the transforms.
    class _CostlessGrow(FakeServices):
        def get(self, url: str) -> dict[str, Any]:
            if url.endswith("/grow_menu"):
                self.calls.append((url, None))
                return {"grow": {**_GROW_MENU,
                                 "actuators": [*_GROW_MENU["actuators"],
                                               {"probe": "guard_row"}]}}
            return super().get(url)
    fake = _CostlessGrow(
        route={"construct": "passport number", "time_indexed": False},
        utility={**_U, "lambda_usd": 2.0},
        decides=[{"effector": "abstain", "credences": [0.2], "p_none": 0.7, "eu": -0.1},
                 {"effector": "abstain", "credences": [0.2], "p_none": 0.7, "eu": -0.1}])
    view = _loop(fake, grow_lane=True)
    assert view["effector"] == "abstain"  # survived; no KeyError on the guard row


def test_grow_escalation_keeps_the_abandoned_passes_events() -> None:
    # PR #63 review (survivorship bias): the legacy grow path replaced the whole view,
    # discarding the withheld pass's firings — exactly the wrong-leaning proposals the
    # curve fold most needs. Every pass's firings must ride the RETURNED view,
    # whichever pass wins. Adopted direction: pass 1 fires haiku then abstains
    # (NONE is MAP → escalate); the grown pass fires opus and reports.
    fake = FakeServices(
        route={"construct": "passport number", "time_indexed": False},
        corroborate={"observations": [{"reports": 0, "group": 0, "authority": 1.0,
                                       "subject_factor": 1.0, "time_factor": 1.0}],
                     "gather_rho": 0.80, "value": "P123", "confidence": 0.7,
                     "cache_key": "jk-1", "cost_usd": 0.012},
        decides=[{"effector": "gather", "probe": "corroborate_haiku",
                  "credences": [0.2], "p_none": 0.6, "eu": 0.0},
                 {"effector": "abstain", "credences": [0.2], "p_none": 0.7, "eu": -0.1},
                 {"effector": "gather", "probe": "corroborate_opus",
                  "credences": [0.5], "p_none": 0.2, "eu": 0.3},
                 {"effector": "report", "value": "P123", "credences": [0.9],
                  "p_none": 0.05, "eu": 0.8}])
    view = _loop(fake, grow=True)
    assert view["effector"] == "report"
    assert [e["edge"] for e in view["edge_events"]] == [
        "extract@claude-haiku-4-5", "extract@claude-opus-4-8"]
    # PR #67 review: the abandoned pass's SPEND survives the swap like its events do —
    # money burned on a discarded pass was still burned
    assert view["spend_usd"] == 0.012 + 0.012


def test_grow_escalation_keeps_the_grown_passes_events_when_not_adopted() -> None:
    # Kept direction: the grown passes also fire (opus on tier 1) but stay withheld —
    # their firings must survive on the ORIGINAL view the loop returns.
    fake = FakeServices(
        route={"construct": "passport number", "time_indexed": False},
        corroborate={"observations": [{"reports": 0, "group": 0, "authority": 1.0,
                                       "subject_factor": 1.0, "time_factor": 1.0}],
                     "gather_rho": 0.80, "value": "P123", "confidence": 0.7,
                     "cache_key": "jk-1", "cost_usd": 0.012},
        decides=[{"effector": "gather", "probe": "corroborate_haiku",
                  "credences": [0.2], "p_none": 0.6, "eu": 0.0},
                 {"effector": "abstain", "credences": [0.2], "p_none": 0.7, "eu": -0.1},
                 {"effector": "gather", "probe": "corroborate_opus",
                  "credences": [0.3], "p_none": 0.5, "eu": 0.0},
                 {"effector": "abstain", "credences": [0.3], "p_none": 0.6, "eu": -0.1},
                 {"effector": "abstain", "credences": [0.3], "p_none": 0.6, "eu": -0.1}])
    view = _loop(fake, grow=True)
    assert view["effector"] == "abstain"
    assert [e["edge"] for e in view["edge_events"]] == [
        "extract@claude-haiku-4-5", "extract@claude-opus-4-8"]
    assert view["spend_usd"] == 0.012 + 0.012  # the grown pass's spend kept too


def test_tier_reply_without_cache_key_warns_of_bridge_skew(capsys) -> None:
    # PR #63 review: a version-skewed bridge (predating the cache_key wire field)
    # yields lineage-less rows that dedup keeps by design — warm replays would then
    # double-count into the curves on every gate run, silently. The skew must be LOUD.
    fake = FakeServices(
        route={"construct": "tax id", "time_indexed": False},
        extract={**_EXTRACT, "candidates": ["P123", "Q999"]},
        corroborate={"observations": [{"reports": 0, "group": 0, "authority": 1.0,
                                       "subject_factor": 1.0, "time_factor": 1.0}],
                     "gather_rho": 0.80, "value": "P123", "confidence": 0.7},
        decides=[{"effector": "gather", "probe": "corroborate_haiku",
                  "credences": [0.5, 0.5], "p_none": 0.1, "eu": 0.2},
                 {"effector": "report", "value": "P123", "credences": [0.9, 0.1],
                  "p_none": 0.05, "eu": 0.8}])
    view = _loop(fake, grow=False)
    assert view["edge_events"][0]["lineage"] is None
    assert "cache_key" in capsys.readouterr().out  # the skew is named, never silent


def test_all_view_shapes_carry_edge_events() -> None:
    # consumers INDEX the key (never .get) — the default must exist on every return
    # site: plain typed, extract-miss short circuit, and the narrative family.
    plain = _loop(FakeServices(
        route={"construct": "tax id", "time_indexed": False},
        decides=[{"effector": "report", "value": "P123", "credences": [0.95],
                  "p_none": 0.02, "eu": 0.9}]), grow=False)
    assert plain["edge_events"] == []
    miss = _loop(FakeServices(
        route={"construct": "passport number", "time_indexed": False},
        extract={"candidates": [], "observations": [], "rho": 0.7,
                 "era_split": False, "indeterminate": 3, "half_life_years": 5.0}),
        grow=False)
    assert miss["edge_events"] == []
    narr = _loop(FakeServices(route=None, narrative={
        "action": "report", "asserted": ["you travelled in May"],
        "rendered": "you travelled in May [1]\n\nnarrative footer",
        "hits": [{"artifact_cache_key": "d0", "chunk_text": "x"}]}),
        "tell me about my week")
    assert narr["edge_events"] == []


def test_deliberate_new_candidate_enlarges_k() -> None:
    fake = FakeServices(
        route={"construct": "rent", "time_indexed": False},
        extract={**_EXTRACT, "candidates": ["NIS 9,999"]},
        deliberate={"observations": [{"reports": 1, "group": 0, "authority": 1.0,
                                      "subject_factor": 1.0, "time_factor": 1.0}],
                    "confidence": 0.85, "model": "claude-opus-4-8",
                    "value": "NIS 4,200", "new_candidate": "NIS 4,200",
                    "status": "ok", "declined": False, "cache": "miss"},
        decides=[{"effector": "gather", "probe": "deliberate",
                  "credences": [0.4], "p_none": 0.6, "eu": 0.0},
                 {"effector": "report", "value": "NIS 4,200",
                  "credences": [0.2, 0.75], "p_none": 0.05, "eu": 0.7}])
    view = _loop(fake, grow=False, curves={})
    assert view["candidates"] == ["NIS 9,999", "NIS 4,200"]
    assert view["effector"] == "report"
    assert fake.posted("/decide")[1]["candidates"] == ["NIS 9,999", "NIS 4,200"]


def test_deliberate_without_curves_takes_the_conservative_cap() -> None:
    # No curves supplied: an unmeasured instrument conditions at min(0.5, confidence) —
    # the rescue-channel rationale verbatim, never the raw self-report.
    fake = FakeServices(
        route={"construct": "rent", "time_indexed": False},
        extract={**_EXTRACT, "candidates": ["NIS 4,200"]},
        deliberate={"observations": [{"reports": 0, "group": 0, "authority": 1.0,
                                      "subject_factor": 1.0, "time_factor": 1.0}],
                    "confidence": 0.85, "model": "claude-opus-4-8",
                    "value": "NIS 4,200", "status": "ok", "declined": False,
                    "cache": "miss"},
        decides=[{"effector": "gather", "probe": "deliberate",
                  "credences": [0.5], "p_none": 0.3, "eu": 0.1},
                 {"effector": "report", "value": "NIS 4,200", "credences": [0.9],
                  "p_none": 0.05, "eu": 0.8}])
    _loop(fake, grow=False)
    assert fake.posted("/decide")[1]["rho"] == 0.5


def test_deliberate_decline_collapses_the_channel() -> None:
    # NOT_IN_CORPUS from the deliberative reference replaces the weak local evidence
    # (the corroborate empty-read contract verbatim): the re-decide sees zero
    # observations and the withhold stands honestly.
    fake = FakeServices(
        route={"construct": "rent", "time_indexed": False},
        extract={**_EXTRACT, "candidates": ["NIS 9,999"]},
        deliberate={"observations": [], "confidence": None, "model": "claude-opus-4-8",
                    "value": None, "status": "ok", "declined": True, "cache": "miss"},
        decides=[{"effector": "gather", "probe": "deliberate",
                  "credences": [0.4], "p_none": 0.5, "eu": 0.0},
                 {"effector": "abstain", "credences": [0.1], "p_none": 0.9, "eu": 0.0}])
    view = _loop(fake, grow=False, curves={})
    assert view["effector"] == "abstain"
    assert fake.posted("/decide")[1]["observations"] == []


def test_corroborate_no_confidence_without_curves_keeps_the_tier_rho() -> None:
    # Legacy regime (curves=None): a reply with no stated confidence conditions at the
    # tier's declared rho — bit-identical to master.
    fake = FakeServices(
        route={"construct": "tax id", "time_indexed": False},
        extract={**_EXTRACT, "candidates": ["P123", "Q999"]},
        corroborate={"observations": [{"reports": 0, "group": 0, "authority": 1.0,
                                       "subject_factor": 1.0, "time_factor": 1.0}],
                     "gather_rho": 0.80, "value": "P123"},
        decides=[{"effector": "gather", "probe": "corroborate_haiku",
                  "credences": [0.5, 0.5], "p_none": 0.1, "eu": 0.2},
                 {"effector": "report", "value": "P123", "credences": [0.9, 0.1],
                  "p_none": 0.05, "eu": 0.8}])
    _loop(fake, grow=False)
    assert fake.posted("/decide")[1]["rho"] == 0.80


def test_corroborate_no_confidence_on_a_measured_edge_folds_at_the_floor() -> None:
    # Within a MEASURED edge, NO signal must never be trusted more than a stated one —
    # an absent confidence maps at the curve's most pessimistic bin, never back at the
    # declared tier prior. (An UNMEASURED edge keeps its declared prior instead — the
    # per-edge regime; see test_one_measured_edge_never_regime_switches….)
    curves = _fitted_curves("extract@claude-haiku-4-5", 0.7)
    fake = FakeServices(
        route={"construct": "tax id", "time_indexed": False},
        extract={**_EXTRACT, "candidates": ["P123", "Q999"]},
        corroborate={"observations": [{"reports": 0, "group": 0, "authority": 1.0,
                                       "subject_factor": 1.0, "time_factor": 1.0}],
                     "gather_rho": 0.80, "value": "P123"},
        decides=[{"effector": "gather", "probe": "corroborate_haiku",
                  "credences": [0.5, 0.5], "p_none": 0.1, "eu": 0.2},
                 {"effector": "report", "value": "P123", "credences": [0.9, 0.1],
                  "p_none": 0.05, "eu": 0.8}])
    _loop(fake, grow=False, curves=curves)
    assert (fake.posted("/decide")[1]["rho"]
            == curves["extract@claude-haiku-4-5"].calibrate(0.0))


def test_deliberate_error_reply_keeps_the_grounded_channel() -> None:
    # A CLI failure is an INFRASTRUCTURE event, not evidence for NONE: the grounded
    # local observations must survive it (the fail-open invariant — an instrumentation
    # failure never breaks an already-grounded answer).
    fake = FakeServices(
        route={"construct": "tax id", "time_indexed": False},
        extract={**_EXTRACT, "candidates": ["P123"]},
        deliberate={"observations": [], "confidence": None, "model": "claude-opus-4-8",
                    "value": None, "status": "error", "declined": False,
                    "cache": "miss"},
        decides=[{"effector": "gather", "probe": "deliberate",
                  "credences": [0.6], "p_none": 0.3, "eu": 0.1},
                 {"effector": "report", "value": "P123", "credences": [0.85],
                  "p_none": 0.1, "eu": 0.6}])
    view = _loop(fake, grow=False, curves={})
    assert view["effector"] == "report"
    second = fake.posted("/decide")[1]
    assert len(second["observations"]) == 1      # the local channel survived
    assert second["rho"] == 0.7                  # at its own rho, untouched


def test_deliberate_transport_failure_is_fail_open() -> None:
    # The probe post raising (client timeout, bridge hiccup) must degrade exactly like a
    # status=error reply — channel kept, probe retired, the loop re-decides.
    class _Fake(FakeServices):
        def post(self, url: str, payload: dict[str, Any]) -> dict[str, Any] | None:
            if url.endswith("/probe/deliberate"):
                self.calls.append((url, payload))
                raise OSError("timed out")
            return super().post(url, payload)

    fake = _Fake(
        route={"construct": "tax id", "time_indexed": False},
        extract={**_EXTRACT, "candidates": ["P123"]},
        decides=[{"effector": "gather", "probe": "deliberate",
                  "credences": [0.6], "p_none": 0.3, "eu": 0.1},
                 {"effector": "report", "value": "P123", "credences": [0.85],
                  "p_none": 0.1, "eu": 0.6}])
    view = _loop(fake, grow=False, curves={})
    assert view["effector"] == "report"
    assert len(fake.posted("/decide")[1]["observations"]) == 1


def test_failed_deliberate_call_still_accounts_its_spend() -> None:
    # An is_error CLI result still bills — the §10 accounting must reach the view even
    # when the observation is discarded (the channel-keeping error path).
    fake = FakeServices(
        route={"construct": "tax id", "time_indexed": False},
        extract={**_EXTRACT, "candidates": ["P123"]},
        deliberate={"observations": [], "confidence": None, "model": "claude-opus-4-8",
                    "value": None, "status": "error", "declined": False,
                    "cost_usd": 0.11, "latency_s": 240.0, "cache": "miss"},
        decides=[{"effector": "gather", "probe": "deliberate",
                  "credences": [0.6], "p_none": 0.3, "eu": 0.1},
                 {"effector": "report", "value": "P123", "credences": [0.85],
                  "p_none": 0.1, "eu": 0.6}])
    view = _loop(fake, grow=False, curves={})
    assert view["cost_usd"] == 0.11
    assert view["latency_s"] == 240.0


def test_tier_rho_and_menu_rho_never_drift() -> None:
    # Drift gate (single-source constants): menu_transforms' curves=None parity — the
    # C2 guarantee — RESTS on the declared _TIER_RHO equalling the DEFAULT_TRANSFORMS
    # rho for every tier row. Nothing else fails if a future edit touches one of them.
    for t in EX.DEFAULT_TRANSFORMS:
        if t["kind"] == "voi" and t["probe"] in EX._TIER_RHO:
            assert t["rho"] == EX._TIER_RHO[t["probe"]], t["name"]


def test_menu_transforms_prices_what_enactment_can_deliver() -> None:
    # C2: the daemon must never buy a probe at a rho the body cannot cash. Without
    # curves the tiers keep their declared priors (parity) and the deliberate row
    # prices at the conservative cap; with fitted curves every voi row re-prices at
    # the SAME fold the enactment will use.
    rows = {t["name"]: t for t in EX.menu_transforms(None)}
    assert rows["corroborate_opus"]["rho"] == 0.95        # parity without curves
    assert rows["deliberate"]["rho"] == 0.5               # the cap, never 0.92 fiat
    curves = _fitted_curves("extract@claude-opus-4-8", 0.95)
    fitted = {t["name"]: t for t in EX.menu_transforms(curves)}
    expected = curves["extract@claude-opus-4-8"].calibrate(0.95)
    assert fitted["corroborate_opus"]["rho"] == expected
    # an UNMEASURED sibling keeps its declared prior (per-edge regime — see below)
    assert fitted["corroborate_haiku"]["rho"] == 0.8


def test_one_measured_edge_never_regime_switches_the_unmeasured_tiers() -> None:
    # §2: each edge is its own error model, never pooled — evidence about
    # deliberate@opus is NOT evidence about extract@haiku. The first writer covers
    # only the deliberate edge, so a GLOBAL calibrated-regime switch would collapse
    # the whole corroborate ladder to the 0.25 cold start (prod-wide, permanently —
    # nothing writes extract@ outcomes to earn them out) the moment the first
    # deliberate outcome row lands. The regime is per-edge: measured edges fold
    # through their curve, unmeasured edges keep their declared fallback.
    curves = _fitted_curves("deliberate@claude-opus-4-8", 0.85)
    fitted = {t["name"]: t for t in EX.menu_transforms(curves)}
    assert fitted["corroborate_haiku"]["rho"] == 0.8
    assert fitted["corroborate_sonnet"]["rho"] == 0.9
    assert fitted["corroborate_opus"]["rho"] == 0.95
    assert (fitted["deliberate"]["rho"]
            == curves["deliberate@claude-opus-4-8"].calibrate(0.92))
    # conditioning takes the same per-edge fork as pricing
    assert EX._conditioned_rho(curves, "extract@claude-haiku-4-5", 0.7, 0.80) == 0.80
    assert (EX._conditioned_rho(curves, "deliberate@claude-opus-4-8", 0.85, 0.5)
            == curves["deliberate@claude-opus-4-8"].calibrate(0.85))


def test_measured_edge_absent_confidence_still_folds_at_the_floor() -> None:
    # within a MEASURED edge the pessimism stands: an absent confidence folds at the
    # curve's most pessimistic bin, never back at the declared prior
    curves = _fitted_curves("extract@claude-haiku-4-5", 0.7)
    edge = "extract@claude-haiku-4-5"
    assert (EX._conditioned_rho(curves, edge, None, 0.80)
            == curves[edge].calibrate(0.0))


# --- the MVP dual-lane fallback (interaction contract: know — the uncalibrated lane) ----

def _withhold_view(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "effector": "abstain", "asserted": [], "candidates": [], "credences": [],
        "p_none": 0.9, "eu": 0.0, "n_obs": 0,
        "hits": [{"artifact_cache_key": "d0", "chunk_text": "lease ends 2027-03-01",
                  "score": 4.2, "origin": "file:///lease.pdf"}],
        "route": {"construct": "lease end date"}, "question": "when does my lease end?"}
    base.update(overrides)
    return base


def test_render_view_fallback_lane_off_is_byte_identical(monkeypatch) -> None:
    # absence of the flag is byte-for-byte today's render — rollback is unsetting it
    import life_agent.core.config as CFG
    monkeypatch.delenv(CFG.FALLBACK_LANE_ENV, raising=False)
    out = EX.render_view(_withhold_view())
    assert "No answer asserted" in out and "uncalibrated" not in out


def test_render_view_fallback_lane_appends_labeled_prose_on_typed_withhold(
        monkeypatch) -> None:
    # flag on + typed route + withholding + hits ⇒ the abstention STILL renders first
    # (named reason, held-back candidates), then the monolithic prose under an explicit
    # uncalibrated label — typed-first, labeled fallback, nothing silent
    import life_agent.core.config as CFG
    import life_agent.core.synthesis as SYN
    monkeypatch.setenv(CFG.FALLBACK_LANE_ENV, "1")
    calls: list[tuple] = []

    def fake_synthesize(root, question, hits, profile, **kw):
        calls.append((root, question, hits, profile))
        return "your lease ends 2027-03-01 [1]", "ck-1", True

    monkeypatch.setattr(SYN, "synthesize", fake_synthesize)
    view = _withhold_view()
    out = EX.render_view(view)
    assert "No answer asserted" in out                       # the typed decision leads
    assert "uncalibrated" in out                             # the lane is labeled
    assert "your lease ends 2027-03-01 [1]" in out
    ((_, q, hits, _),) = calls
    assert q == "when does my lease end?" and hits is view["hits"]


def test_render_view_fallback_lane_skips_asserting_and_narrative_views(
        monkeypatch) -> None:
    import life_agent.core.config as CFG
    import life_agent.core.synthesis as SYN
    monkeypatch.setenv(CFG.FALLBACK_LANE_ENV, "1")
    monkeypatch.setattr(SYN, "synthesize",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("called")))
    # a report asserts — no lane
    report = _withhold_view(effector="report", asserted=["2027-03-01"],
                            candidates=["2027-03-01"], credences=[0.95])
    assert "uncalibrated" not in EX.render_view(report)
    # a hedge already surfaces candidates — no lane
    hedge = _withhold_view(effector="hedge", candidates=["a", "b"],
                           credences=[0.5, 0.4])
    assert "uncalibrated" not in EX.render_view(hedge)
    # a narrative view IS the prose lane already — passes through verbatim, untouched
    nv = {"effector": "report", "asserted": ["x"], "candidates": [], "credences": [],
          "p_none": None, "eu": None, "n_obs": 0, "hits": [], "route": None,
          "rendered": "prose [1]\n\nnarrative footer", "question": "q?"}
    assert EX.render_view(nv) == "prose [1]\n\nnarrative footer"


def test_render_view_fallback_lane_needs_hits_and_question(monkeypatch) -> None:
    # nothing retrieved ⇒ nothing to synthesize over; a pre-lane View (no question key,
    # the membrane/report harnesses) degrades to today's render — never a crash
    import life_agent.core.config as CFG
    import life_agent.core.synthesis as SYN
    monkeypatch.setenv(CFG.FALLBACK_LANE_ENV, "1")
    monkeypatch.setattr(SYN, "synthesize",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("called")))
    assert "uncalibrated" not in EX.render_view(_withhold_view(hits=[]))
    no_q = _withhold_view()
    del no_q["question"]
    assert "uncalibrated" not in EX.render_view(no_q)


def test_render_view_fallback_lane_failure_is_named_not_silent(monkeypatch) -> None:
    # a failed lane (missing key raises SystemExit via core/llm) must not kill the typed
    # render NOR vanish silently — the notice names the unavailability (invariant 3)
    import life_agent.core.config as CFG
    import life_agent.core.synthesis as SYN
    monkeypatch.setenv(CFG.FALLBACK_LANE_ENV, "1")

    def boom(*a, **k):
        raise SystemExit("ANTHROPIC_API_KEY not found in env or gnome-keyring")

    monkeypatch.setattr(SYN, "synthesize", boom)
    out = EX.render_view(_withhold_view())
    assert "No answer asserted" in out
    assert "uncalibrated lane unavailable" in out


def test_loop_views_carry_the_question(monkeypatch) -> None:
    # both View producers thread the question — the render seam's lane needs it and a
    # View without it silently disables the lane (the back-compat degrade above)
    fake = FakeServices(
        route={"construct": "passport number", "time_indexed": False},
        decides=[{"effector": "report", "value": "P123", "credences": [0.9],
                  "p_none": 0.05, "eu": 0.8}])
    view = _loop(fake)
    assert view["question"] == "what is my passport number?"
    nfake = FakeServices(route=None, narrative={
        "action": "report", "asserted": ["x"], "rendered": "prose", "hits": []})
    nview = _loop(nfake)
    assert nview["question"] == "what is my passport number?"
