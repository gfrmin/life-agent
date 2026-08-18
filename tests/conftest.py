"""Shared fixtures for life-agent's top-level test suite.

Hermetic by default: no test may read or write the live KB. ``ask.main()`` runs
the demand-led GTD refresh before connecting (interaction contract: act-layer
state), so any test that reaches it without this redirection would project and
re-ingest the owner's LIVE ledger into the live catalogue mid-suite — caught
exactly once, 2026-06-11, before this fixture existed. Tests that need real GTD
paths override these attributes themselves (see tests/test_ask_gtd_refresh.py).
"""

from __future__ import annotations

from pathlib import Path

import pytest

import life_agent.core as C


@pytest.fixture(autouse=True)
def _hermetic_gtd_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(C, "TASKS_LEDGER", tmp_path / "hermetic-events.jsonl")
    monkeypatch.setattr(C, "TASKS_STATE", tmp_path / "hermetic-state.md")


@pytest.fixture(autouse=True)
def _hermetic_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    """No test routes through the lookup family unless it asks to: the router would
    call the live local model and the family would spawn the Julia skin. Tests of the
    family itself bind the real functions by name at import time (tests/test_lookup.py),
    which this attribute patch deliberately does not reach."""
    from life_agent.core import lookup as LK

    monkeypatch.setattr(LK, "lookup_answer", lambda *a, **k: None)


@pytest.fixture(autouse=True)
def _hermetic_narrative(monkeypatch: pytest.MonkeyPatch) -> None:
    """Same reasoning for the narrative family (it spawns the Julia skin for Ū and
    appends to the live decision log): stubbed to None — ask.answer's disabled seam —
    unless the test binds the real functions by name (tests/test_narrative.py)."""
    from life_agent.core import narrative as N

    monkeypatch.setattr(N, "narrative_answer", lambda *a, **k: None)


@pytest.fixture(autouse=True)
def _hermetic_executor(monkeypatch: pytest.MonkeyPatch) -> None:
    """The executor (credence answer-brain daemon) is ask's DEFAULT read-path, but it needs the
    live daemon/bridge; no hermetic test may reach for it. Stub readiness to False so ask
    deterministically takes the in-process fallback (the prior default) without a localhost
    probe. Tests of the executor path override this by name (tests/test_ask.py)."""
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import ask

    monkeypatch.setattr(ask, "_executor_ready", lambda: False)


# --- the synthetic KB for the ledger tests (test_ledger_golden / test_ledger_migrate / …) ------
# PII-OK: synthetic — every value below is invented; the marker string exists only to prove the
# harness output never prints record values.
import json  # noqa: E402
import shutil  # noqa: E402

from life_agent.core import claude_verdicts as CV  # noqa: E402
from life_agent.core import decisions as DEC  # noqa: E402
from life_agent.core import gather_outcomes as GO  # noqa: E402
from life_agent.core import outcomes as O  # noqa: E402
from life_agent.core import reactions as RX  # noqa: E402
from life_agent.ledger import golden as G  # noqa: E402
from life_agent.tasks import events as TEV  # noqa: E402
from life_agent.trips import events as REV  # noqa: E402
from pkm.cache import content_file, lineage_file, meta_file  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
LEDGER_MARKER = "SYNTHETIC-SECRET-VALUE-9f3a"


def _decision(did: str, action: str, creds: list[float], tx: str) -> DEC.DecisionEvent:
    return DEC.DecisionEvent(
        tx_time=tx, run_id="", question_id="0" * 16, family="lookup",
        action_set=DEC.LOOKUP_ACTION_ORDER,
        posterior_summary={"candidates": ["v"] * len(creds), "credences": creds,
                           "p_none": 1 - sum(creds), "n_obs": 1},
        utility_fold_version="f" * 64, chosen_action=action, predicted_eu=0.0,
        decision_id=did, instrument="", cost_usd=None, latency_s=None)


def _reaction(did: str, valence: str, tx: str) -> RX.ReactionEvent:
    return RX.ReactionEvent(tx_time=tx, question_id="0" * 16, decision_id=did,
                            kind="verdict", valence=valence)


def _edge_outcome(grade: str, p: float, lineage: str, tx: str) -> O.OutcomeEvent:
    return O.OutcomeEvent(tx_time=tx, run_id="r", question_id="q-001", claim="c",
                          construct="k", grade=grade, grader="eval_edge",
                          instrument_identity={"edge": "edge:e1"}, lineage_keys=(lineage,),
                          probability=p)


@pytest.fixture
def ledger_kb(tmp_path: Path) -> tuple[Path, G.Paths]:
    root = tmp_path / "kb"
    (root / "utility").mkdir(parents=True)
    (root / "calibration").mkdir()
    (root / "tasks").mkdir()
    (root / "trips").mkdir()
    (root / "eval").mkdir()
    shutil.copyfile(REPO / "config" / "utility-model.example.yaml", root / "utility" / "model.yaml")
    (root / "utility" / "elicitations.jsonl").write_text(
        json.dumps({"tx_time": "2026-01-01T00:00:00+00:00", "latent": "u_wrong",
                    "stated_value": -9.0, "noise_sigma": 0.5}) + "\n", encoding="utf-8")
    p = G.Paths(
        tasks_ledger=root / "tasks" / "events.jsonl", trips_ledger=root / "trips" / "events.jsonl",
        outcomes=root / "calibration" / "outcomes.jsonl",
        decisions=root / "calibration" / "decisions.jsonl",
        reactions=root / "calibration" / "reactions.jsonl",
        claude_verdicts=root / "calibration" / "claude_verdicts.jsonl",
        gather_outcomes=root / "calibration" / "gather_outcomes.jsonl",
        corrections=root / "calibration" / "corrections.jsonl",
        elicitations=root / "utility" / "elicitations.jsonl",
        utility_model=root / "utility" / "model.yaml",
        labels=root / "eval" / "labels.jsonl", pkm_root=root / "pkm")
    # decisions: two abstains (folded), one report (recorded-not-folded)
    d1, d2, d3 = "a" * 64, "b" * 64, "c" * 64
    DEC.append(p.decisions, _decision(d1, "abstain", [0.6, 0.3], "2026-01-01T00:00:01+00:00"))
    DEC.append(p.decisions, _decision(d2, "report", [0.95], "2026-01-01T00:00:02+00:00"))
    DEC.append(p.decisions, _decision(d3, "abstain", [0.7], "2026-01-01T00:00:03+00:00"))
    RX.append(p.reactions, _reaction(d1, "good", "2026-01-01T00:01:00+00:00"))
    RX.append(p.reactions, _reaction(d3, "bad", "2026-01-01T00:02:00+00:00"))
    RX.append(p.reactions, _reaction(d2, "good", "2026-01-01T00:03:00+00:00"))
    RX.append(p.reactions, _reaction(d1, "bad", "2026-01-01T00:04:00+00:00"))
    O.append(p.outcomes, _edge_outcome("CORRECT", 0.8, "l1", "2026-01-01T00:00:00+00:00"))
    O.append(p.outcomes, _edge_outcome("INCORRECT", 0.4, "l2", "2026-01-01T00:00:01+00:00"))
    O.append(p.outcomes, _edge_outcome("CORRECT", 0.9, "l3", "2026-01-01T00:00:02+00:00"))
    CV.append(p.claude_verdicts, CV.ClaudeVerdictEvent(
        tx_time="2026-01-01T00:05:00+00:00", question_id="0" * 16, decision_id=d2,
        dimensions={"correct": 1, "complete": 1, "grounded": 0}))
    probe = str(GO.GROW_ACTUATORS[0]["probe"])
    p.gather_outcomes.write_text(json.dumps(
        {"tx_time": "2026-01-01T00:06:00+00:00", "probe": probe, "ctx": ["yes", "lt20", "0"],
         "recovered": True}) + "\n", encoding="utf-8")
    p.corrections.write_text(json.dumps({"tx_time": "t", "question": "q", "claim": LEDGER_MARKER,
                                         "cell": "x", "claim_as_of": None,
                                         "correction": "c"}) + "\n", encoding="utf-8")
    p.labels.write_text("".join(json.dumps(o) + "\n" for o in [
        {"question_id": "q-001", "value": LEDGER_MARKER, "verdict": "wrong", "note": ""},
        {"question_id": "q-001", "value": LEDGER_MARKER, "verdict": "correct", "note": ""},
    ]), encoding="utf-8")
    # tasks: asserted → amended → second asserted → disposed
    t1, t2 = TEV.new_identity(), TEV.new_identity()
    TEV.append(p.tasks_ledger, [
        TEV.asserted(t1, {"user_id": 1, "text": f"task one {LEDGER_MARKER}", "list": "inbox",
                          "origin": "human"}, tx_time="2026-01-01T00:00:00"),
        TEV.amended(t1, {"list": "next"}, tx_time="2026-01-01T00:00:01"),
        TEV.asserted(t2, {"user_id": 1, "text": "task two", "list": "inbox",
                          "origin": "human"}, tx_time="2026-01-01T00:00:02"),
        TEV.disposed(t2, "done", tx_time="2026-01-01T00:00:03"),
    ])
    # trips: two observations of one identity at different fidelities (manual wins)
    jl = {"@type": "FlightReservation", "reservationNumber": "ZZ999",
          "reservationFor": {"@type": "Flight", "name": "XX 123",
                             "departureAirport": {"iataCode": "AAA"},
                             "arrivalAirport": {"iataCode": "BBB"},
                             "departureTime": "2026-02-01T10:00:00",
                             "arrivalTime": "2026-02-01T12:00:00"}}
    REV.append(p.trips_ledger, [
        REV.observed("res-1", jl, fidelity="kayak-api", source_id="s1",
                     received_at="2026-01-01T00:00:00", tx_time="2026-01-01T00:00:00"),
        REV.observed("res-1", {**jl, "reservationNumber": "ZZ998"}, fidelity="manual",
                     source_id="s2", received_at="2025-12-31T00:00:00",
                     tx_time="2026-01-01T00:00:01"),
    ])
    # a mini pkm root: one artefact under the decision-referenced key d1, plus a demand line
    root2 = p.pkm_root
    assert root2 is not None
    meta_file(root2, d1).parent.mkdir(parents=True)
    content_file(root2, d1).write_bytes(b'{"answer": "synthetic"}')
    lineage_file(root2, d1).write_text(json.dumps({"format_version": 1, "inputs": [
        {"cache_key": "d" * 64, "role": "source_text"}]}), encoding="utf-8")
    meta_file(root2, d1).write_text(json.dumps({
        "format_version": 1, "cache_key": d1, "input_hash": "e" * 64,
        "producer_name": "life_agent.ask.lookup_answer", "producer_version": "1",
        "producer_config_hash": "f" * 64, "status": "success",
        "produced_at": "2026-01-01T00:00:00", "size_bytes": 23, "error_message": None,
        "content_type": "application/x-ask-lookup-answer+json", "content_encoding": "utf-8",
        "producer_metadata": {}, "cache_key_schema_version": 3}), encoding="utf-8")
    (root2 / "logs" / "demand").mkdir(parents=True)
    (root2 / "logs" / "demand" / "2026-01-01.jsonl").write_text(json.dumps(
        {"timestamp": "2026-01-01T00:00:00.000001+00:00", "caller": "test",
         "transform_name": "doc_date", "cache_key": "",
         "input_cache_key": "e" * 64, "hit": False, "cost_usd": 0.0, "latency_ms": 1}) + "\n",
        encoding="utf-8")
    return root, p


