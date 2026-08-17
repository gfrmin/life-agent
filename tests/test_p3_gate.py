"""Hermetic tests for the P3 held-out gate harness (`scripts/membrane/p3_gate.py`).

No engine: the engine probe (`probe_heldout`) is a scripted `system` step. These pin the pure
logic — the question-keyed join (drift-guarded against the frozen `boot_snapshot`), the LOO
grouping, per-tick pricing, question-level act aggregation, and the recomputed-hash join to the
credence baseline.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, "scripts")

import membrane.p3_gate as P3

from life_agent.core import claude_verdicts as CV
from life_agent.core import decisions as DEC
from life_agent.core import gate as GATE
from life_agent.core import reactions as RX
from life_agent.core import utility as UT
from life_agent.membrane import shadow as SH
from life_agent.membrane import world as W

# the gate's utility keys (a minimal Ū — the live-ish values; enough for realised_utility)
U_BAR = {"u_correct": 1.0, "u_wrong": -5.94, "u_abstain": 0.0, "u_hedged": 0.3,
         "u_wrong_scoped": -0.5, "lambda_int": 0.1}


def _decision(decision_id: str, question_id: str, chosen_action: str, *,
              leader: float = 0.9) -> DEC.DecisionEvent:
    return DEC.DecisionEvent(
        tx_time="t", run_id="run-1", question_id=question_id, family="lookup",
        action_set=("report", "hedge", "ask_clarify", "abstain", "report_scoped"),
        posterior_summary={"credences": [leader], "p_none": 0.1, "n_obs": 1},
        utility_fold_version="fv1", chosen_action=chosen_action, predicted_eu=0.5,
        decision_id=decision_id)


def _reaction(decision_id: str, question_id: str, valence: str) -> RX.ReactionEvent:
    return RX.ReactionEvent(tx_time="t", question_id=question_id, decision_id=decision_id,
                            kind="verdict", valence=valence)


def _cv(decision_id: str, correct: int) -> CV.ClaudeVerdictEvent:
    return CV.ClaudeVerdictEvent(tx_time="t", question_id="ignored", decision_id=decision_id,
                                 dimensions={"correct": correct}, evidence=(), note="")


def _tick(qid: str, *, p1: float | None, y: int, respond: bool,
          leader: float | None = 0.9) -> P3.HeldoutTick:
    return P3.HeldoutTick(question_id=qid, leader_credence=leader, p1=p1, y=y, respond=respond)


# --- the drift guard: keyed replay == boot_snapshot projection + question identity ---------


def test_keyed_replay_matches_boot_snapshot_projection_and_carries_question_id(
    tmp_path: Path,
) -> None:
    dpath, rpath, cpath = (tmp_path / "d.jsonl", tmp_path / "r.jsonl", tmp_path / "c.jsonl")
    DEC.append(dpath, _decision("dec-1", "q-A", "report", leader=0.95))
    DEC.append(dpath, _decision("dec-2", "q-B", "abstain", leader=0.4))
    DEC.append(dpath, _decision("dec-3", "q-C", "report", leader=0.7))
    RX.append(rpath, _reaction("dec-1", "q-A", "good"))   # (report, good) -> y=1
    RX.append(rpath, _reaction("dec-2", "q-B", "bad"))    # (abstain, bad) -> y=1
    CV.append(cpath, _cv("dec-3", correct=0))             # Claude-only -> y=0

    snap = SH.boot_snapshot(dpath, rpath, None, claude_verdicts_path=cpath)
    keyed = P3.keyed_verdict_replay(SH._read_decisions(dpath), SH._read_reactions(rpath),
                                    SH._read_claude_verdicts(cpath))
    # byte-identical (summary, y) projection, order included — keyed is boot_snapshot + id
    assert [(t.summary, t.y) for t in keyed] == snap.verdict_replay
    assert [t.question_id for t in keyed] == ["q-A", "q-B", "q-C"]


def test_keyed_replay_owner_reaction_overrules_the_claude_verdict(tmp_path: Path) -> None:
    dpath, rpath, cpath = (tmp_path / "d.jsonl", tmp_path / "r.jsonl", tmp_path / "c.jsonl")
    DEC.append(dpath, _decision("dec-1", "q-A", "report"))
    RX.append(rpath, _reaction("dec-1", "q-A", "bad"))    # (report, bad) -> y=0, routable
    CV.append(cpath, _cv("dec-1", correct=1))             # would say y=1 — must be overruled
    keyed = P3.keyed_verdict_replay(SH._read_decisions(dpath), SH._read_reactions(rpath),
                                    SH._read_claude_verdicts(cpath))
    assert len(keyed) == 1
    assert keyed[0].y == 0  # the owner's routable verdict wins (boot_snapshot's precedence)


# --- LOO grouping -------------------------------------------------------------------------


def test_group_by_question_partitions_completely_and_disjointly() -> None:
    keyed = [P3.KeyedTick("q1", W.summary_from_decision_event(  # minimal summary
        {"posterior_summary": {"credences": [0.9]}, "chosen_action": "report"}), 1)
        for _ in range(3)]
    keyed += [P3.KeyedTick("q2", keyed[0].summary, 0) for _ in range(2)]
    groups = P3.group_by_question(keyed)
    assert set(groups) == {"q1", "q2"}
    assert [len(v) for v in groups.values()] == [3, 2]
    assert sum(len(v) for v in groups.values()) == len(keyed)  # complete + disjoint


# --- per-tick pricing (A1) ----------------------------------------------------------------


def test_price_at_u_bar_matches_gate_realised_utility() -> None:
    rows = [
        _tick("q1", p1=0.9, y=1, respond=True, leader=0.95),   # respond + right → +u_correct
        _tick("q2", p1=0.9, y=0, respond=True, leader=0.85),   # respond + wrong → u_wrong
        _tick("q3", p1=0.5, y=1, respond=False, leader=0.4),   # abstain → u_abstain (0)
    ]
    out = P3.price_at_u_bar(rows, U_BAR, oracle_p=0.9)
    # policy: +1 (right), -5.94 (wrong), 0 (abstain) → (1 - 5.94 + 0)/3
    assert abs(out["policy_eu_per_q"] - (1.0 - 5.94 + 0.0) / 3) < 1e-9
    # respond-all: every row valued as a report → (1 - 5.94 + 1)/3
    assert abs(out["respond_all_eu_per_q"] - (1.0 - 5.94 + 1.0) / 3) < 1e-9
    assert out["n_respond"] == 2
    # buckets bin by leader_credence (0.95→ge90, 0.85→80-90, 0.4→lt50)
    names = {b["bucket"] for b in out["buckets"]}
    assert names == {"ge90", "80-90", "lt50"}


def test_price_abstain_only_is_the_gauge_zero() -> None:
    rows = [_tick("q1", p1=0.5, y=1, respond=False), _tick("q2", p1=0.6, y=0, respond=False)]
    out = P3.price_at_u_bar(rows, U_BAR, oracle_p=0.9)
    assert out["policy_eu_per_q"] == 0.0  # all abstain → gauge 0
    assert out["n_respond"] == 0


# --- question-level acts (A3 typed side) --------------------------------------------------


def test_question_acts_majority_respond_and_anti_flattering_ties() -> None:
    rows = [
        # q1: 2 of 3 respond (majority) → report; responded y = [1,0] → tie → wrong
        _tick("q1", p1=0.9, y=1, respond=True), _tick("q1", p1=0.9, y=0, respond=True),
        _tick("q1", p1=0.5, y=1, respond=False),
        # q2: 1 of 2 respond (tie) → report (assertive tie-break); responded y=[1] → correct
        _tick("q2", p1=0.9, y=1, respond=True), _tick("q2", p1=0.5, y=0, respond=False),
        # q3: 0 of 2 respond → abstain
        _tick("q3", p1=0.5, y=1, respond=False), _tick("q3", p1=0.5, y=0, respond=False),
    ]
    acts = P3.question_acts(rows)
    assert acts["q1"].action == "report" and acts["q1"].correct is False  # tie → wrong
    assert acts["q2"].action == "report" and acts["q2"].correct is True   # tie → respond, y=1
    assert acts["q3"].action == "abstain"


# --- the recomputed-hash join (A3) --------------------------------------------------------


def test_hash_to_qid_recomputes_the_question_id() -> None:
    questions = [{"id": "q2-001", "question": "what is the capital of X?"},
                 {"id": "q2-002", "question": "when did Y happen?"}]
    h2q = P3.hash_to_qid(questions)
    assert h2q[DEC.question_id("what is the capital of X?")] == "q2-001"
    assert h2q[DEC.question_id("when did Y happen?")] == "q2-002"
    assert len(h2q) == 2


def test_build_paired_joins_by_hash_and_names_the_unjoined() -> None:
    q_join = "joined question text?"
    q_membrane_only = "live traffic question not in corpus?"
    h_join, h_only = DEC.question_id(q_join), DEC.question_id(q_membrane_only)
    membrane_acts = {h_join: GATE.RealisedResponse("report", correct=True),
                     h_only: GATE.RealisedResponse("abstain")}
    h2q = {h_join: "q2-005"}  # only the joinable hash maps to a corpus id
    baseline_rows = [
        {"question_id": "q2-005", "answerable": True, "asserted": True,
         "asserted_correct": False, "bucket": "CONFIDENT_WRONG"},
        {"question_id": "q2-099", "answerable": True, "asserted": False,
         "asserted_correct": False, "bucket": "RIGHTLY_WITHHELD"},  # baseline-only
    ]
    paired, only_m, only_b = P3.build_paired(membrane_acts, h2q, baseline_rows)
    assert len(paired) == 1
    assert paired[0].question_id == "q2-005"
    assert paired[0].typed.action == "report" and paired[0].mono.action == "report"
    assert only_m == [h_only]        # the non-corpus membrane question, named
    assert only_b == ["q2-099"]      # the baseline question with no membrane act, named


# --- p3b: the variant-parameterized differential (coarsened-lattice A3) -------------------

def _point(name: str, value: float) -> UT.LatentPosterior:
    return UT.LatentPosterior(name=name, mean=value, variance=0.0, lo=value, hi=value)


def _posterior() -> UT.UtilityPosterior:
    return UT.UtilityPosterior(
        gauge={"u_correct": 1.0, "u_abstain": 0.0},
        latents={"u_wrong": _point("u_wrong", -2.0),
                 "u_hedged": _point("u_hedged", 0.3),
                 "lambda_int": _point("lambda_int", 0.5),
                 "kappa_att": _point("kappa_att", 0.05)},
        n_events=0, fold_version="test")


def _p3b_fixture() -> tuple[list[P3.HeldoutTick], dict[str, str], list[dict]]:
    q = "joined question text?"
    h = DEC.question_id(q)
    rows = [P3.HeldoutTick(question_id=h, leader_credence=0.95, p1=0.97, y=1,
                           respond=True)]
    h2q = {h: "q2-005"}
    baseline_rows = [{"question_id": "q2-005", "answerable": True, "asserted": True,
                      "asserted_correct": True, "bucket": "CONFIDENT_RIGHT"}]
    return rows, h2q, baseline_rows


def test_run_differential_writes_variant_suffixed_artifacts(tmp_path: Path) -> None:
    # two variants over the same rows land as two DISTINCT artifact sets — the FULL P3
    # record and the p3b coarsened arm can never clobber each other (the runs-3/4 lesson)
    rows, h2q, baseline_rows = _p3b_fixture()
    for variant, fams in (("FULL", tuple(P3.LR.ALL_FAMILIES)),
                          ("leader-credence-only", ("leader-credence",))):
        P3.run_differential(rows, variant=variant, families=fams, h2q=h2q,
                            baseline_rows=baseline_rows, posterior=_posterior(),
                            oracle_p=0.9, out=tmp_path, draws=400, seed=7,
                            log=lambda _m: None)
    names = sorted(p.name for p in tmp_path.iterdir())
    assert names == ["a3_gate-FULL.md", "a3_gate-leader-credence-only.md",
                     "a3_meta-FULL.json", "a3_meta-leader-credence-only.json",
                     "a3_paired-FULL.jsonl", "a3_paired-leader-credence-only.jsonl"]


def test_run_differential_matches_the_inline_gate_it_replaced(tmp_path: Path) -> None:
    # refactor guard: the extracted function computes the SAME GateResult the old
    # inline A3 path did — acts → hash join → delta_posterior at the frozen δ/level
    import life_agent.core.gate as GATE

    rows, h2q, baseline_rows = _p3b_fixture()
    gate = P3.run_differential(rows, variant="FULL",
                               families=tuple(P3.LR.ALL_FAMILIES), h2q=h2q,
                               baseline_rows=baseline_rows, posterior=_posterior(),
                               oracle_p=0.9, out=tmp_path, draws=400, seed=7,
                               log=lambda _m: None)
    acts = P3.question_acts(rows)
    paired, _, _ = P3.build_paired(acts, h2q, baseline_rows)
    ref = GATE.delta_posterior(paired, _posterior(), oracle_p=0.9,
                               n_draws=400, seed=7)
    assert gate.p_delta_gt == ref.p_delta_gt
    assert gate.delta_mean == ref.delta_mean
    assert gate.materiality_delta == ref.materiality_delta == 0.05
    assert gate.level == ref.level == 0.90


def test_run_differential_meta_names_the_lattice_under_test(tmp_path: Path) -> None:
    # the coarsened lattice IS the object under test — its families and resolved
    # indicator vocabulary are provenance in the artifact, not a comment
    import json as _json

    rows, h2q, baseline_rows = _p3b_fixture()
    P3.run_differential(rows, variant="leader-credence-only",
                        families=("leader-credence",), h2q=h2q,
                        baseline_rows=baseline_rows, posterior=_posterior(),
                        oracle_p=0.9, out=tmp_path, draws=400, seed=7,
                        log=lambda _m: None)
    meta = _json.loads((tmp_path / "a3_meta-leader-credence-only.json").read_text())
    assert meta["families"] == ["leader-credence"]
    assert meta["indicators"] == P3.LR.FAMILY_NAMES["leader-credence"]
    assert meta["seed"] == 7 and meta["n_joined"] == 1
    assert meta["verdict"] in ("PASS", "FAIL") and "p_delta_gt" in meta


def test_coarsened_shaped_rows_aggregate_to_an_abstain_heavy_typed_arm() -> None:
    # the p3b power caveat, pinned: a lattice that responds only at ge90 yields mostly
    # abstains at the question level — a FAIL there is FAIL-by-abstention, a different
    # failure mode than FULL's over-assertion, and the pre-registration names it
    rows = [
        _tick("q-hi", p1=0.96, y=1, respond=True, leader=0.95),
        _tick("q-mid", p1=0.6, y=1, respond=False, leader=0.75),
        _tick("q-low", p1=0.2, y=0, respond=False, leader=0.4),
    ]
    acts = P3.question_acts(rows)
    assert acts["q-hi"].action == "report" and acts["q-hi"].correct is True
    assert acts["q-mid"].action == "abstain" and acts["q-low"].action == "abstain"
