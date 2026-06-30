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


class FakeServices:
    """A scripted bridge + daemon. ``decides`` is consumed in order (the daemon's effector
    stream); every other endpoint returns its fixed fixture. Records calls for assertions."""

    def __init__(self, *, route: dict[str, Any] | None,
                 hits: list[dict[str, Any]] | None = None,
                 extract: dict[str, Any] | None = None,
                 decides: list[dict[str, Any]] | None = None,
                 narrative: dict[str, Any] | None = None,
                 corroborate: dict[str, Any] | None = None,
                 utility: dict[str, float] | None = None) -> None:
        self.route = route
        self.hits = hits if hits is not None else _HIT
        self.extract = extract if extract is not None else _EXTRACT
        self._decides = list(decides or [])
        self.narrative = narrative
        self.corroborate = corroborate
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
            return self.extract
        if url.endswith("/probe/corroborate"):
            return self.corroborate
        if url.endswith("/decide"):
            return self._decides.pop(0)
        raise AssertionError(f"unexpected POST {url}")

    def get(self, url: str) -> dict[str, Any]:
        self.calls.append((url, None))
        if url.endswith("/utility"):
            return {"u_bar": self.utility}
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
