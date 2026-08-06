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


def test_rescue_cold_start_curve_is_more_conservative_than_the_cap() -> None:
    # curves supplied but the edge unseen: Beta(1,3) cold start (0.25) — stricter than the
    # 0.5 cap, never looser (§16 safe-before-calibrated).
    fake = FakeServices(
        route={"construct": "mortgage", "time_indexed": False},
        extracts=[_EMPTY_EXTRACT, _EMPTY_EXTRACT, _EMPTY_EXTRACT],
        corroborate={"observations": [{"reports": 0, "group": 0, "authority": 1.0,
                                       "subject_factor": 1.0, "time_factor": 1.0}],
                     "gather_rho": 0.95, "value": "NEW-7", "new_candidate": "NEW-7",
                     "confidence": 0.9},
        decides=[{"effector": "hedge", "credences": [0.6], "p_none": 0.4, "eu": 0.1}])
    _loop(fake, grow_lane=True, curves={})
    assert fake.posted("/decide")[0]["rho"] == 0.25


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


def test_corroborate_no_confidence_with_curves_folds_at_the_floor() -> None:
    # Calibrated regime: NO signal must never be trusted more than a stated one (a
    # stated 0.95 cold-starts at 0.25) — an absent confidence maps at the curve's most
    # pessimistic bin, never at the declared tier prior.
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
    _loop(fake, grow=False, curves={})
    assert fake.posted("/decide")[1]["rho"] == 0.25


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
    assert fitted["corroborate_haiku"]["rho"] == 0.25     # unseen edge: cold start
