"""M5 — the argmax absorption (r15): the driver holds no choice the ranking could make.

Phase P-I pins: the M3 membrane live lane is DELETED (Q8 — ``map_action`` survives as
the shadow worker's measurement function), ``core/gather.py`` is DELETED (GA-1…GA-3:
gathering is a K row the daemon prices), and B-4's weak-retrieval pre-emption is
DELETED (S-1 split: belief-side — few/weak observations withhold by EU, not by a host
threshold). Deletion pins are drift gates: the absence IS the contract.
"""
from __future__ import annotations

import dataclasses
import inspect
import sys
from pathlib import Path

import pytest

from life_agent.core import config as CFG
from life_agent.core import executor as EX
from life_agent.core import seam as SEAM
from life_agent.membrane import coarse as CRS

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

_SRC = Path(__file__).resolve().parent.parent / "src" / "life_agent"
_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


# --- P-I(a): the M3 live lane is gone ------------------------------------------------ #

def test_the_live_lane_died_from_coarse() -> None:
    """coarse keeps map_action (the shadow worker's measurement, Q8) and nothing live."""
    assert hasattr(CRS, "map_action")
    assert not hasattr(CRS, "live_decide")
    assert not hasattr(CRS, "LIVE_TIMEOUT_S")


def test_config_has_no_membrane_live_flag() -> None:
    assert not hasattr(CFG, "membrane_live")
    assert not hasattr(CFG, "MEMBRANE_LIVE_ENV")


def test_seam_has_no_live_plumbing() -> None:
    """The DaemonDecide request carries no live consult; the LiveFn type is gone."""
    assert not hasattr(SEAM, "LiveFn")
    assert "live" not in {f.name for f in dataclasses.fields(SEAM.DaemonDecide)}


def test_executor_loop_has_no_live_parameter() -> None:
    assert "live" not in inspect.signature(EX.decide_via_loop).parameters
    assert "live" not in inspect.signature(EX.run_pass).parameters


def test_drive_has_no_live_branch() -> None:
    """The driver always shadow-wraps: the flag-gated fork is not in the source."""
    src = (_SRC / "core" / "ask_client.py").read_text()
    assert "membrane_live" not in src
    assert "live_decide" not in src


def test_bridge_has_no_decide_live_endpoint() -> None:
    src = (_SRC / "bridge" / "server.py").read_text()
    assert "_decide_live" not in src
    assert "decide_live" not in src


def test_shadow_keeps_the_feed_not_the_live_half() -> None:
    src = (_SRC / "membrane" / "shadow.py").read_text()
    assert "decide_live" not in src
    assert "_LIVE_WAIT_S" not in src


# --- P-I(b): gather is gone ---------------------------------------------------------- #

def test_gather_module_died() -> None:
    with pytest.raises(ModuleNotFoundError):
        import life_agent.core.gather  # noqa: F401


def test_ask_has_no_gather_fork() -> None:
    src = (_SCRIPTS / "ask.py").read_text()
    assert "gather_answer" not in src
    assert "answer_brain_gate" not in {p.name for p in _SCRIPTS.glob("*.py")}


# --- P-I(c): B-4's pre-emption is gone ----------------------------------------------- #

def test_weak_retrieval_gate_died_from_the_seam() -> None:
    """S-1 split: the belief-side gate dies; the unavailability gates stay (§6.5)."""
    assert not hasattr(SEAM, "GATE_WEAK_RETRIEVAL")
    assert SEAM.GATE_EXECUTOR_DOWN == "executor_down"
    assert SEAM.GATE_ENGINE_DOWN == "engine_down"


def test_ask_has_no_weak_retrieval_predicate() -> None:
    src = (_SCRIPTS / "ask.py").read_text()
    assert "retrieval_is_weak" not in src
    assert "WEAK_SCORE_FLOOR" not in src
    assert "MIN_STRONG_HITS" not in src


# --- P-II as amended by A5 (run-17 ruling): the report-economy latch is RESTORED ------ #

def _fake_services_module():  # the executor test rig, reused without duplication
    import tests.test_executor as TE
    return TE


def test_report_terminal_gets_no_grow_offer() -> None:
    """A5 (the run-17 ruling): the report-economy latch is MEASURED protection — run 17
    priced the every-terminal offer at answer rate 0.62 -> 0.49 (dispersal; run 13's
    lesson again). A confident report ends the loop with NO grow re-ask; the engine's
    real preference for the re-read (A2's 62/63) is priced by the §14 hand-priced-VOI
    arc, not enacted here."""
    te = _fake_services_module()
    fake = te.FakeServices(
        route={"construct": "passport number", "time_indexed": False},
        decides=[
            {"effector": "report", "value": "P123", "credences": [0.9, 0.05],
             "p_none": 0.05, "eu": 0.8},
        ])
    view = te._loop(fake)
    assert view["effector"] == "report"
    decides = fake.posted("/decide")
    assert len(decides) == 1                  # one plain consult; the latch holds
    assert "grow" not in decides[0]
    assert fake.posted("/log_gather") == []   # nothing enacted, nothing logged


def test_withholding_terminal_still_gets_the_grow_offer() -> None:
    """The latch is withhold-ONLY: an abstaining terminal with unapplied grow
    actuators is re-asked WITH the grow block (unchanged since the grow lane landed —
    the daemon prices recall where the arm would otherwise stay silent)."""
    te = _fake_services_module()
    fake = te.FakeServices(
        route={"construct": "passport number", "time_indexed": False},
        decides=[
            {"effector": "abstain", "credences": [0.2, 0.1], "p_none": 0.7, "eu": 0.0},
            {"effector": "abstain", "credences": [0.2, 0.1], "p_none": 0.7, "eu": 0.0},
        ])
    view = te._loop(fake)
    assert view["effector"] == "abstain"
    decides = fake.posted("/decide")
    assert len(decides) == 2
    assert "grow" not in decides[0] and "sensors" not in decides[0]  # first pass plain
    assert "grow" in decides[1] and "sensors" in decides[1]          # the offer fired


# --- P-II (A1 + D-5): withhold-reason is ONE derivation ------------------------------- #

def test_withhold_reason_is_one_derivation() -> None:
    from life_agent.core import decisions as DEC2
    assert DEC2.withhold_reason(effector="report", candidates=["x"],
                                available=False) == "unavailable"
    assert DEC2.withhold_reason(effector="miss", candidates=[], available=True) == "miss"
    assert DEC2.withhold_reason(effector="abstain", candidates=[],
                                available=True) == "miss"
    assert DEC2.withhold_reason(effector="abstain", candidates=["x"],
                                available=True) == "dispersed"


def test_reason_consumers_derive_not_respell() -> None:
    """D-5 drift gate: the named consumers call the one derivation."""
    root = Path(__file__).resolve().parent.parent
    assert "withhold_reason" in (root / "scripts" / "run_eval.py").read_text()
    assert "withhold_reason" in (_SRC / "core" / "executor.py").read_text()


# --- P-III: the terminals-only regime is DECLARED and reachable ----------------------- #

def test_leaf_decision_declares_the_terminals_regime(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """§2.3: the in-process leaves rank over T by the skin — their decision rows say so
    (regime declared, not defaulted; the silent 'full' default was a wrong claim)."""
    import life_agent.core.decisions as DEC2
    import life_agent.core.lookup as LK
    from life_agent.core import config as CFG2
    from life_agent.core import recorder as REC
    from life_agent.core.brain import Brain
    from tests.test_lookup import MODEL_YAML, ScriptedTransport

    model_path = tmp_path / "model.yaml"
    model_path.write_text(MODEL_YAML, encoding="utf-8")
    monkeypatch.setattr(CFG2, "UTILITY_MODEL", model_path)
    monkeypatch.setattr(CFG2, "UTILITY_ELICITATIONS", tmp_path / "elicit.jsonl")
    monkeypatch.setattr(LK, "_U_BAR", None)

    events: list[DEC2.DecisionEvent] = []

    def fake_record_local(root, akey, content, *, lineage, decisions_path, event):
        events.append(event)

    monkeypatch.setattr(REC, "record_local", fake_record_local)
    obs = LK.Observation(card_n=1, artifact_cache_key="a" * 64, obs_cache_key="o" * 64,
                         value_raw="V1", value_norm="v1", quote="V1 is it",
                         authority_class="body", authority=1.0)
    LK.decide_and_record(tmp_path, "what is V?", "thing", [obs], 0,
                         n_hits=1, time_indexed=False,
                         brain=Brain(ScriptedTransport(optimise_action="abstain")))
    assert len(events) == 1
    assert events[0].regime == "terminals-only"
    assert events[0].policy == "all-to-date"
    assert events[0].defaulted == ()


def test_drive_down_branch_runs_the_terminals_regime(monkeypatch) -> None:
    """Q1 (signed): an unavailable daemon answers over T — the driver runs the absorbed
    body and returns its rendered text; no §6.5 record lands (an optimiser DID run)."""
    from life_agent.core import ask_client as AC2
    from life_agent.core import recorder as REC
    from life_agent.core import terminals as TERM2

    unavailable: list[str] = []
    monkeypatch.setattr(REC, "record_unavailable",
                        lambda q, **k: unavailable.append(q))

    class _Conn:
        def close(self) -> None: ...
    monkeypatch.setattr(TERM2, "connect", lambda: _Conn())
    monkeypatch.setattr(TERM2, "answer",
                        lambda conn, q, k, **kw: ("cited answer [1]", [], {}))
    monkeypatch.setattr(TERM2, "LOOKUP_LAST", None)
    monkeypatch.setattr(TERM2, "NARRATIVE_LAST", None)

    r = AC2.drive("what is V?", 20, ready=lambda: False)
    assert r.down is False
    assert r.text == "cited answer [1]"
    assert r.view is None
    assert unavailable == []


def test_drive_down_branch_falls_to_unavailable_when_terminals_cannot_run(
        monkeypatch) -> None:
    """No catalogue / no skin ⇒ the §6.5 unavailability record, exactly as before."""
    from life_agent.core import ask_client as AC2
    from life_agent.core import recorder as REC
    from life_agent.core import terminals as TERM2

    unavailable: list[str] = []
    monkeypatch.setattr(REC, "record_unavailable",
                        lambda q, **k: unavailable.append(q))
    monkeypatch.setattr(TERM2, "connect",
                        lambda: (_ for _ in ()).throw(RuntimeError("no catalogue")))
    monkeypatch.setattr(AC2.SM, "mirror_gate", lambda *a, **k: None)

    r = AC2.drive("what is V?", 20, ready=lambda: False)
    assert r.down is True and r.view is None and r.decision_id is None
    assert unavailable == ["what is V?"]


def test_ask_once_has_no_dispatch_choice() -> None:
    """B-1/B-5: the executor= choice and --legacy died — availability decides."""
    import ask
    assert "executor" not in inspect.signature(ask.ask_once).parameters
    src = (_SCRIPTS / "ask.py").read_text()
    assert "--legacy" not in src


# --- P-IV (A3): the single-writer invariant, drift-gated ------------------------------ #

def test_record_local_callers_are_exactly_the_family_leaves() -> None:
    """A3: one recorder, the declared family leaf call sites, no other writer and no
    second spelling. r21 (CP-D) added an aggregate leaf; K1 (r22) deleted the family it
    belonged to, so the census returns to the two leaves. This guard has now fired on a
    real change in BOTH directions — an added writer and a removed one."""
    hits = []
    for py in (_SRC).rglob("*.py"):
        text = py.read_text()
        if "REC.record_local(" in text or "recorder.record_local(" in text:
            hits.append(py.relative_to(_SRC).as_posix())
    assert sorted(hits) == ["core/lookup.py", "core/narrative.py"]


# --- P-V (L-3): report_scoped_j — the engine picks the scoped value ------------------- #

def test_scoped_rows_are_per_dated_candidate_and_engine_picked() -> None:
    """L-3: one report_scoped_j row per dated candidate, engine-priced; the host pick
    of V_s (freshest dated) DIED — a scripted engine choosing report_scoped_1 must
    surface candidate 1's value and ITS as-of date, even when candidate 0's record is
    fresher."""
    import life_agent.core.lookup as LK

    captured: dict = {}

    class _Brain:
        def create_state(self, spec):
            return "s1"
        def condition(self, sid, *, kernel, observation):
            return None
        def marginal(self, sid, **k):
            return None
        def expect(self, sid, *, function):
            # the attested-record EU: candidate 1's row prices higher than 0's
            vals = function["values"]
            return 0.9 if vals[1] > vals[0] else 0.2
        def optimise(self, sid, *, actions, preference):
            captured["rows"] = sorted(preference["actions"])
            return "report_scoped_1", 0.9
        def destroy_state(self, sid):
            return None

    obs = [
        LK.Observation(card_n=1, artifact_cache_key="a" * 64, obs_cache_key="o" * 64,
                       value_raw="OLD-VAL", value_norm="old-val", quote="q1",
                       authority_class="body", authority=1.0, doc_date="2026-05-01"),
        LK.Observation(card_n=2, artifact_cache_key="b" * 64, obs_cache_key="p" * 64,
                       value_raw="NEW-VAL", value_norm="new-val", quote="q2",
                       authority_class="body", authority=1.0, doc_date="2026-01-01"),
    ]
    # candidate order: OLD-VAL is j=0 (fresher record), NEW-VAL is j=1 (staler record)
    scoped = LK._scoped_options(_Brain(), obs, ["OLD-VAL", "NEW-VAL"], (4.0, 4.0),
                                u_bar={"u_hedged": 0.5, "u_wrong_scoped": -2.0},
                                state_current="s1", weights_current=[0.5, 0.4, 0.1],
                                time_indexed=False)
    assert set(scoped) == {0, 1}
    action, _eu, j = LK.decide(_Brain(), "s1", [0.5, 0.4, 0.1],
                              {"u_correct": 1.0, "u_wrong": -9.0, "u_hedged": 0.5,
                               "u_abstain": 0.0, "lambda_int": 0.1},
                              scoped={jj: t[0] for jj, t in scoped.items()})
    assert "report_scoped_0" in captured["rows"] and "report_scoped_1" in captured["rows"]
    assert "report_scoped" not in captured["rows"]  # the flat host-picked row died
    assert (action, j) == ("report_scoped", 1)


def test_undated_candidates_have_no_scoped_rows() -> None:
    """'No dated ⇒ disabled' is an EMPTY option set (no EU mass), not a 0.0 row."""
    import life_agent.core.lookup as LK
    rows = LK.action_utilities([0.6, 0.3, 0.1], {"u_correct": 1.0, "u_wrong": -9.0,
                                                 "u_hedged": 0.5, "u_abstain": 0.0,
                                                 "lambda_int": 0.1}, scoped={})
    assert not any(a.startswith("report_scoped") for a in rows)
