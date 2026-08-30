"""The one recorder (module-collapse M2, design §5.1) — one body, one place where a
decision becomes two records (the §18.9 node and the ledger row), and the §6.5
unavailability event.

Every value here is SYNTHETIC (CLAUDE.md: the repo is public and PII-free).

Run: uv run --project . python -m pytest tests/test_recorder.py
"""
from __future__ import annotations

import json
from pathlib import Path

from life_agent.core import decisions as DEC
from life_agent.core import derivations as D
from life_agent.core import recorder as REC

# --- the one body (no accounting field is optional on the poster's side) ------------------

def test_the_one_body_has_no_optional_key() -> None:
    body = REC.body(
        question="what is the synthetic serial?",  # PII-OK: synthetic question
        retrieval_keys=["k2", "k1"],
        effector="report", credences=[0.9, 0.1], candidates=["A", "B"],
        p_none=None, eu=None, n_obs=2, n_indeterminate=0, n_competing=0,
        instrument=None, cost_usd=None, latency_s=None, run_id=None,
        regime="full", policy="all-to-date")
    dec = body["decision"]
    assert body["question"] and body["retrieval_keys"] == ["k2", "k1"]
    assert dec["p_none"] == 0.0 and dec["eu"] == 0.0
    assert dec["instrument"] == "" and dec["run_id"] == "answer-brain"
    assert dec["cost_usd"] == 0.0 and dec["latency_s"] == 0.0
    assert dec["regime"] == "full" and dec["policy"] == "all-to-date"
    # never an absent key: the union the bridge accepts, every key present
    assert sorted(dec) == ["candidates", "cost_usd", "credences", "effector", "eu",
                           "instrument", "latency_s", "n_competing", "n_indeterminate",
                           "n_obs", "p_none", "policy", "regime", "run_id"]


def test_the_body_passes_realised_values_through() -> None:
    body = REC.body(
        question="q", retrieval_keys=[], effector="hedge", credences=[0.6, 0.4],
        candidates=["A", "B"], p_none=0.1, eu=0.42, n_obs=3, n_indeterminate=1,
        n_competing=2, instrument="deliberate@synthetic-model",  # PII-OK: synthetic
        cost_usd=0.004, latency_s=1.25, run_id="gate-run",
        regime="full", policy="all-to-date")
    dec = body["decision"]
    assert dec["instrument"] == "deliberate@synthetic-model"
    assert dec["cost_usd"] == 0.004 and dec["latency_s"] == 1.25
    assert dec["run_id"] == "gate-run" and dec["eu"] == 0.42


def test_record_via_bridge_posts_exactly_once_and_returns_the_id() -> None:
    posted: list[tuple[str, dict]] = []

    def post(url: str, payload: dict) -> dict:
        posted.append((url, payload))
        return {"decision_id": "abc123"}

    body = REC.body(question="q", retrieval_keys=[], effector="report",
                    credences=[1.0], candidates=["A"], p_none=0.0, eu=0.5,
                    n_obs=1, n_indeterminate=0, n_competing=0, instrument="",
                    cost_usd=0.0, latency_s=0.0, run_id="r",
                    regime="full", policy="all-to-date")
    decision_id = REC.record_via_bridge(post, "http://b", body)
    assert decision_id == "abc123"
    assert len(posted) == 1 and posted[0][0] == "http://b/log_decision"
    assert posted[0][1] is body


# --- the leaves' tail: two writes, one place -----------------------------------------------

def _leaf_event(decision_id: str) -> DEC.DecisionEvent:
    return DEC.DecisionEvent(
        tx_time="2026-08-25T00:00:00Z", run_id="ask", question_id="a" * 16,
        family="lookup", action_set=DEC.LOOKUP_ACTION_ORDER,
        posterior_summary={"candidates": ["A"], "credences": [1.0], "p_none": 0.0,
                           "n_obs": 1, "n_indeterminate": 0, "n_competing": 0},
        utility_fold_version="ufv", chosen_action="report", predicted_eu=0.5,
        decision_id=decision_id)


def test_record_local_is_one_call_two_writes(tmp_path: Path) -> None:
    """D.record (the §18.9 node) then DEC.append (the ledger row) — the decision_id =
    akey.cache_key rule preserved verbatim (the event carries the key the node landed at)."""
    root, decisions = tmp_path / "root", tmp_path / "decisions.jsonl"
    akey = D.lookup_answer_key("q", "obshash", "ufv", {"p": 1})
    content = json.dumps({"format_version": 1}).encode()
    REC.record_local(root, akey, content,
                     lineage=[{"cache_key": "obs1", "role": "observation"}],
                     decisions_path=decisions, event=_leaf_event(akey.cache_key))
    events = DEC.read(decisions)
    assert [e.decision_id for e in events] == [akey.cache_key]
    assert D.meta_file(root, akey.cache_key).exists()


# --- the §6.5 unavailability record --------------------------------------------------------

def test_record_unavailable_appends_the_one_event_and_binds_nothing(tmp_path: Path) -> None:
    decisions = tmp_path / "decisions.jsonl"
    out = REC.record_unavailable("is the stack up?",  # PII-OK: synthetic question
                                 decisions_path=decisions)
    assert out is None  # nothing to bind a verdict to
    events = DEC.read(decisions)
    assert len(events) == 1
    e = events[0]
    assert e.regime == "unavailable" and e.decision_id == ""
    assert e.chosen_action == "abstain" and e.family == "lookup"
    assert e.policy == DEC.POLICY_DEFAULT and e.defaulted == ("policy",)
    assert e.instrument == "" and e.cost_usd == 0.0 and e.latency_s == 0.0
    assert e.utility_fold_version == "" and e.predicted_eu == 0.0
    assert e.run_id == "answer-brain"
    assert e.question_id == DEC.question_id("is the stack up?")  # PII-OK: synthetic
    assert e.posterior_summary == {"candidates": [], "credences": [], "p_none": 0.0,
                                   "n_obs": 0, "n_indeterminate": 0, "n_competing": 0}


def test_record_unavailable_takes_the_surface_run_id(tmp_path: Path) -> None:
    decisions = tmp_path / "decisions.jsonl"
    REC.record_unavailable("q", run_id="gate-arm", decisions_path=decisions)
    assert DEC.read(decisions)[0].run_id == "gate-arm"


# --- the one-writer drift gate (7.4's seeded defect: a second writer of decisions.jsonl) --

def test_the_family_leaves_do_not_append_the_decision_ledger_themselves() -> None:
    """M2 (design §5.1): the leaves' own ``DEC.append`` calls moved into the one recorder.
    A leaf module that grows its own append back is the seeded defect 7.4 names — killed
    here at the source level (the pattern ``tests/test_seam.py`` pins ``.optimise`` with),
    and at the store level by the fixture replay's one-event-per-decision bodies."""
    root = Path(__file__).resolve().parents[1] / "src" / "life_agent" / "core"
    for leaf in ("lookup.py", "narrative.py"):
        src = (root / leaf).read_text(encoding="utf-8")
        assert "DEC.append(" not in src, (
            f"{leaf} appends the decision ledger itself — the one recorder "
            "(core/recorder.py) is the only writer since M2 (r12)")


# --- r33 RC-1: the miss row — a coverage failure the reaction stream can finally see ----

def test_record_miss_appends_a_reactable_lookup_row(tmp_path: Path) -> None:
    """A lookup that grounds nothing writes ONE local row: regime "miss", chosen_action
    "abstain" (the §6.5 precedent — the action vocabulary stays closed), a REAL
    content-addressed id (the ONE rule) so the owner's verdict can bind, and an empty
    fold version — no /decide ran."""
    dpath = tmp_path / "decisions.jsonl"
    did = REC.record_miss("what is my X?", retrieval_keys=["d1", "d0"],
                          n_indeterminate=3, decisions_path=dpath)
    assert did == DEC.decision_id_for("what is my X?", ["d1", "d0"], [], 0.0)
    assert did.startswith("ab-")
    rows = [json.loads(line) for line in dpath.read_text().splitlines()]
    assert len(rows) == 1
    row = rows[0]
    assert row["family"] == "lookup" and row["chosen_action"] == "abstain"
    assert row["regime"] == "miss"
    assert row["decision_id"] == did
    assert row["utility_fold_version"] == ""            # no fold ran
    assert row["posterior_summary"]["n_obs"] == 0
    assert row["posterior_summary"]["n_indeterminate"] == 3
    assert row["posterior_summary"]["credences"] == []
    assert row["cost_usd"] == 0.0 and row["instrument"] == ""
    assert tuple(row["defaulted"]) == ("policy",)       # the writer states the regime


def test_the_bridge_binds_the_one_id_rule() -> None:
    """DEC.decision_id_for is THE declaration (r33 promoted it from the bridge); the
    bridge's `_decision_id` must BE it — a second spelling cannot exist."""
    from life_agent.bridge import server as BS
    assert BS._decision_id is DEC.decision_id_for
