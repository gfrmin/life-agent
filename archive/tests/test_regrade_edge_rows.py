"""scripts/regrade_edge_rows.py — append-only re-grading after a gold correction."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import regrade_edge_rows as RG

import life_agent.core.outcomes as O
from life_agent.core.calibration import EdgeOutcome, edge_outcomes_from_log


def _ev(qid: str, claim: str, grade: str, *, edge: str = "deliberate@opus",
        lineage: tuple[str, ...] = ("L",), tx: str = "t0", p: float = 0.9,
        grader: str = "eval_edge") -> O.OutcomeEvent:
    return O.OutcomeEvent(tx_time=tx, run_id="r", question_id=qid, claim=claim,
                          construct="edge-proposal", grade=grade, grader=grader,
                          instrument_identity={"edge": edge}, lineage_keys=lineage,
                          probability=p)


QS = {"q2-105": {"id": "q2-105", "answer": "(852) 5550 0187",  # PII-OK: synthetic phone shape
                 "answer_variants": ["5550 0187"]}}  # PII-OK: synthetic phone shape


def test_plan_supersedes_only_rows_whose_grade_moved() -> None:
    events = [
        _ev("q2-105", "(852) 5550 0143", "CORRECT", tx="t0"),          # stale: the tel  # PII-OK
        _ev("q2-105", "(852) 5550 0187", "CORRECT", lineage=("L2",)),  # already right  # PII-OK
        _ev("q2-105", "nothing", "INCORRECT", lineage=("L3",)),        # already right
        _ev("q2-001", "(852) 5550 0143", "CORRECT", lineage=("L4",)),  # other question  # PII-OK
    ]
    to_append, unfixable = RG.plan_regrades(events, QS, reason="fax/tel", run_id="regrade-x")
    assert unfixable == []
    assert [(e.question_id, e.grade, e.lineage_keys, e.probability) for e in to_append] == [
        ("q2-105", "INCORRECT", ("L",), 0.9)]
    s = to_append[0].signals
    assert s == {"regrade_of": "t0", "superseded_grade": "CORRECT", "reason": "fax/tel"}
    assert to_append[0].run_id == "regrade-x"
    assert to_append[0].instrument_identity == {"edge": "deliberate@opus"}


def test_plan_regrades_the_row_in_force_not_an_already_superseded_one() -> None:
    # a second correction after a first regrade: the in-force row is the LATEST per
    # lineage, so re-planning against the corrected gold is a no-op
    events = [_ev("q2-105", "(852) 5550 0143", "CORRECT", tx="t0"),  # PII-OK: synthetic phone shape
              _ev("q2-105", "(852) 5550 0143", "INCORRECT", tx="t1")]  # PII-OK
    to_append, unfixable = RG.plan_regrades(events, QS, reason="x", run_id="r2")
    assert (to_append, unfixable) == ([], [])


def test_plan_names_lineage_less_rows_it_cannot_supersede() -> None:
    events = [_ev("q2-105", "(852) 5550 0143", "CORRECT", lineage=())]  # PII-OK
    to_append, unfixable = RG.plan_regrades(events, QS, reason="x", run_id="r2")
    assert to_append == [] and [e.claim for e in unfixable] == ["(852) 5550 0143"]  # PII-OK


def test_plan_ignores_non_edge_graders() -> None:
    events = [_ev("q2-105", "(852) 5550 0143", "CORRECT", grader="eval_lookup")]  # PII-OK
    assert RG.plan_regrades(events, QS, reason="x", run_id="r2") == ([], [])


def test_appended_regrade_supersedes_in_the_curve_fold(tmp_path: Path) -> None:
    log = tmp_path / "outcomes.jsonl"
    O.append(log, _ev("q2-105", "(852) 5550 0143", "CORRECT", p=0.97))  # PII-OK
    to_append, _ = RG.plan_regrades(O.read(log), QS, reason="x", run_id="r2")
    for ev in to_append:
        O.append(log, ev)
    assert edge_outcomes_from_log(log) == [EdgeOutcome("deliberate@opus", 0.97, False)]
    # idempotent: a second plan over the appended log is empty
    assert RG.plan_regrades(O.read(log), QS, reason="x", run_id="r3") == ([], [])


def test_cli_dry_run_writes_nothing(tmp_path: Path, capsys) -> None:
    import yaml

    log = tmp_path / "outcomes.jsonl"
    O.append(log, _ev("q2-105", "(852) 5550 0143", "CORRECT"))  # PII-OK: synthetic phone shape
    qfile = tmp_path / "q.yaml"
    qfile.write_text(yaml.safe_dump({"format_version": 2, "questions": list(QS.values())}))
    rc = RG.main(["--question", "q2-105", "--reason", "x", "--questions", str(qfile),
                  "--log", str(log)])
    assert rc == 0
    assert len(O.read(log)) == 1
    assert "dry-run" in capsys.readouterr().out
    rc = RG.main(["--question", "q2-105", "--reason", "x", "--questions", str(qfile),
                  "--log", str(log), "--apply", "--run-id", "regrade-t"])
    assert rc == 0
    rows = O.read(log)
    assert len(rows) == 2 and rows[1].grade == "INCORRECT" and rows[1].run_id == "regrade-t"
