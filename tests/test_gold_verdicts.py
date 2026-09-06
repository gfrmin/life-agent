"""r51b (2b) — `scripts/gold_verdicts.py`: the gold-verdict writer for an EXTERNAL KB.

On a labelled public corpus the benchmark's human-annotated answer IS the truth measurement,
so a verdict may be derived from it mechanically — but only into a KB that declares itself
external (`external-corpus.json`), and never with the deliberative issuer. Issuer-blind
supersession (`latest_by_decision`) means a `gold:*` row on the OWNER's ledger would supersede
a deliberated one, so the manifest refusal is the ONE guard, and it fails closed (`GD-30` (4)).

The verdict is the benchmark's own matcher (`atm_bench.vendored.atm_number_match`); the
harness's `answer_matches` is recorded beside it as a cross-tab bit and decides nothing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, "scripts")

import claude_verdict as CLI
import gold_verdicts as GV
import membrane.p3_gate as P3

from life_agent.core import claude_verdicts as CV
from life_agent.core import decisions as DEC
from life_agent.membrane import shadow as SH

# PII-OK: every value below is synthetic ATM-Bench-shaped QA (invented dates, amounts, ids)
QUESTIONS = [
    {"id": "atm-q1", "question": "When was the parcel collected?", "answer": "14 December 2023",
     "fuzzy": False, "notes": "evidence: email000000000001"},
    {"id": "atm-q2", "question": "How many chairs were ordered?", "answer": "12",
     "fuzzy": False, "notes": "evidence: email000000000002"},
    {"id": "atm-q3", "question": "Where is the lakeside cabin?", "answer": "the lakeside cabin",
     "fuzzy": True, "notes": "evidence: email000000000003"},
    {"id": "atm-q4", "question": "Today is 2024-03-10. When did the invoice arrive?",
     "answer": "2024-03-09", "fuzzy": False, "notes": "evidence: email000000000004"},
]


def _decision(decision_id: str, question: str, candidates: list[str], credences: list[float],
              *, chosen: str = "report") -> DEC.DecisionEvent:
    return DEC.DecisionEvent(
        tx_time="2026-09-06T00:00:00Z", run_id="ff-atm", question_id=DEC.question_id(question),
        family="lookup", action_set=("report", "hedge", "ask_clarify", "abstain", "report_scoped"),
        posterior_summary={"candidates": candidates, "credences": credences, "p_none": 0.1,
                           "n_obs": 2},
        utility_fold_version="fv1", chosen_action=chosen, predicted_eu=0.5,
        decision_id=decision_id)


@pytest.fixture
def kb(tmp_path: Path) -> Path:
    root = tmp_path / "kb"
    (root / "eval").mkdir(parents=True)
    (root / "calibration").mkdir()
    (root / "eval" / "questions.yaml").write_text(
        yaml.safe_dump({"questions": QUESTIONS}, allow_unicode=True), encoding="utf-8")
    (root / GV.MANIFEST).write_text(json.dumps(
        {"corpus": "atm-bench", "license": "CC-BY-NC-4.0", "built_at": "2026-09-06",
         "counts": {}, "evaluator_sha": "ef4e5dff"}), encoding="utf-8")
    return root


def _seed(kb: Path, *decisions: DEC.DecisionEvent) -> None:
    for d in decisions:
        DEC.append(kb / "calibration" / "decisions.jsonl", d)


def _events(kb: Path) -> list[CV.ClaudeVerdictEvent]:
    return CV.read(kb / "calibration" / "claude_verdicts.jsonl")


# --- the predicate and the verdict ----------------------------------------------------------


def test_gradeable_is_answer_typed_number_only() -> None:
    assert GV.gradeable("14 December 2023")
    assert GV.gradeable("$1,250")
    assert not GV.gradeable("the lakeside cabin")
    assert not GV.gradeable("email000000000001, email000000000002")


def test_grades_the_leader_by_max_credence_not_index_zero(kb: Path) -> None:
    _seed(kb, _decision("d1", QUESTIONS[1]["question"], ["7", "12"], [0.2, 0.8]))
    assert GV.main(["grade", "--kb", str(kb)]) == 0
    (ev,) = _events(kb)
    assert ev.dimensions["correct"] == 1                    # the leader "12" is right


def test_date_format_mismatch_is_correct_and_the_harness_bit_is_recorded_beside_it(
        kb: Path) -> None:
    # the harness's `answer_matches` is date-aware on a bare date (both rules say right);
    # the bit is recorded either way — the cross-tab is an OUTPUT, never the verdict
    _seed(kb, _decision("d1", QUESTIONS[0]["question"], ["2023-12-14"], [0.9]))
    assert GV.main(["grade", "--kb", str(kb)]) == 0
    (ev,) = _events(kb)
    assert ev.dimensions["correct"] == 1
    assert ev.note == "harness-match:1"


def test_relative_date_resolves_against_the_question_anchor_where_the_harness_cannot(
        kb: Path) -> None:
    # "yesterday" against "Today is 2024-03-10": the benchmark's matcher resolves it, the
    # harness rule has no anchor — the disagreement the cross-tab exists to count
    _seed(kb, _decision("d1", QUESTIONS[3]["question"], ["yesterday"], [0.9]))
    assert GV.main(["grade", "--kb", str(kb)]) == 0
    (ev,) = _events(kb)
    assert ev.dimensions["correct"] == 1
    assert ev.note == "harness-match:0"


def test_token_boundary_not_substring(kb: Path) -> None:
    _seed(kb, _decision("d1", QUESTIONS[1]["question"], ["123"], [0.9]))
    assert GV.main(["grade", "--kb", str(kb)]) == 0
    (ev,) = _events(kb)
    assert ev.dimensions["correct"] == 0
    assert ev.note == "harness-match:0"


def test_writes_gold_issuer_and_corpus_evidence(kb: Path) -> None:
    _seed(kb, _decision("d1", QUESTIONS[1]["question"], ["12"], [0.9]))
    assert GV.main(["grade", "--kb", str(kb)]) == 0
    (ev,) = _events(kb)
    assert ev.issuer == "gold:atm-bench"
    assert ev.evidence == ("atm-bench:atm-q2",)
    assert ev.question_id == DEC.question_id(QUESTIONS[1]["question"])
    assert ev.decision_id == "d1"
    assert ev.issuer != CV.ISSUER


# --- counts, skips, idempotence ---------------------------------------------------------------


def test_skips_fuzzy_and_non_gradeable_and_counts(kb: Path, capsys: pytest.CaptureFixture[str]
                                                  ) -> None:
    _seed(kb, _decision("d1", QUESTIONS[2]["question"], ["a cabin"], [0.9]),   # fuzzy
          _decision("d2", QUESTIONS[1]["question"], ["12"], [0.9]))
    assert GV.main(["grade", "--kb", str(kb)]) == 0
    assert [e.decision_id for e in _events(kb)] == ["d2"]
    out = capsys.readouterr().out
    assert "not_gradeable=1" in out and "correct=1" in out and "eligible=2" in out
    assert "cabin" not in out                                 # counts only, never a value


def test_skips_decisions_without_a_question_and_counts(kb: Path,
                                                       capsys: pytest.CaptureFixture[str]) -> None:
    _seed(kb, _decision("d1", "A question the file does not carry?", ["1"], [0.9]),
          _decision("d2", "Narrative row", [], [], chosen="abstain"))           # not eligible
    assert GV.main(["grade", "--kb", str(kb)]) == 0
    assert _events(kb) == []
    out = capsys.readouterr().out
    assert "no_question=1" in out and "eligible=1" in out


def test_rerun_appends_nothing(kb: Path) -> None:
    _seed(kb, _decision("d1", QUESTIONS[1]["question"], ["12"], [0.9]),
          _decision("d2", QUESTIONS[0]["question"], ["14 December 2023"], [0.9]))
    assert GV.main(["grade", "--kb", str(kb)]) == 0
    first = (kb / "calibration" / "claude_verdicts.jsonl").read_bytes()
    assert GV.main(["grade", "--kb", str(kb)]) == 0
    assert (kb / "calibration" / "claude_verdicts.jsonl").read_bytes() == first
    assert len(_events(kb)) == 2


def test_rows_replay_through_shadow_reader_and_keyed_replay(kb: Path) -> None:
    # the row shape the harness actually folds (`M-7`): shadow's reader → keyed replay → y
    decisions = [_decision("d1", QUESTIONS[1]["question"], ["12"], [0.9]),
                 _decision("d2", QUESTIONS[0]["question"], ["2023-12-15"], [0.9])]
    _seed(kb, *decisions)
    assert GV.main(["grade", "--kb", str(kb)]) == 0
    events = SH._read_claude_verdicts(kb / "calibration" / "claude_verdicts.jsonl")
    ticks = P3.keyed_verdict_replay(decisions, [], events)
    assert [(t.question_id, t.y) for t in ticks] == [
        (DEC.question_id(QUESTIONS[1]["question"]), 1),
        (DEC.question_id(QUESTIONS[0]["question"]), 0)]


# --- the one guard --------------------------------------------------------------------------


def test_refuses_a_kb_without_the_external_manifest(tmp_path: Path,
                                                    capsys: pytest.CaptureFixture[str]) -> None:
    owner_like = tmp_path / "owner-kb"
    (owner_like / "calibration").mkdir(parents=True)
    (owner_like / "eval").mkdir()
    (owner_like / "eval" / "questions.yaml").write_text(
        yaml.safe_dump({"questions": QUESTIONS}), encoding="utf-8")
    DEC.append(owner_like / "calibration" / "decisions.jsonl",
               _decision("d1", QUESTIONS[1]["question"], ["12"], [0.9]))
    assert GV.main(["grade", "--kb", str(owner_like)]) == 2
    assert not (owner_like / "calibration" / "claude_verdicts.jsonl").exists()
    assert GV.MANIFEST in capsys.readouterr().out


def test_eligible_from_is_the_cli_rule(kb: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # one eligibility rule: the CLI's `_eligible` binds the extracted `eligible_from`
    from life_agent.core import config

    decisions = [_decision("d1", QUESTIONS[1]["question"], ["12"], [0.9]),
                 _decision("d2", "Narrative row", [], [], chosen="abstain")]
    _seed(kb, *decisions)
    monkeypatch.setattr(config, "DECISIONS_LOG", kb / "calibration" / "decisions.jsonl")
    assert set(CLI._eligible()) == set(CLI.eligible_from(decisions)) == {"d1"}
    assert GV.eligible_from is CLI.eligible_from


# --- the audit sample (X3d) -----------------------------------------------------------------


def test_audit_sample_is_seeded_and_writes_nothing_to_the_kb(kb: Path, tmp_path: Path) -> None:
    _seed(kb, *[_decision(f"d{i}", QUESTIONS[i % 2]["question"], ["12"], [0.9])
                for i in range(6)])
    assert GV.main(["grade", "--kb", str(kb)]) == 0
    before = sorted(p.relative_to(kb) for p in kb.rglob("*") if p.is_file())
    snapshot = {p: p.read_bytes() for p in kb.rglob("*") if p.is_file()}
    out = tmp_path / "audit.jsonl"
    assert GV.main(["audit-sample", "--kb", str(kb), "--n", "3", "--seed", "11",
                    "--out", str(out)]) == 0
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 3
    assert set(rows[0]) == {"decision_id", "question", "gold", "leader"}      # blind
    key = Path(str(out) + ".key.jsonl")
    keys = [json.loads(line) for line in key.read_text(encoding="utf-8").splitlines()]
    assert [k["decision_id"] for k in keys] == [r["decision_id"] for r in rows]
    assert set(keys[0]) == {"decision_id", "verdict"} and keys[0]["verdict"] in (0, 1)
    again = tmp_path / "audit2.jsonl"
    GV.main(["audit-sample", "--kb", str(kb), "--n", "3", "--seed", "11", "--out", str(again)])
    assert again.read_bytes() == out.read_bytes()             # seeded
    assert sorted(p.relative_to(kb) for p in kb.rglob("*") if p.is_file()) == before
    assert {p: p.read_bytes() for p in kb.rglob("*") if p.is_file()} == snapshot


def test_audit_sample_can_carry_the_evidence_emails_beside_each_blind_row(
        kb: Path, tmp_path: Path) -> None:
    # X3d deliberates each row AGAINST THE CORPUS: with --evidence-dir the blind rows carry
    # the bodies of the emails the question's notes name (ids → files), still no verdict
    _seed(kb, _decision("d1", QUESTIONS[1]["question"], ["12"], [0.9]))
    assert GV.main(["grade", "--kb", str(kb)]) == 0
    emails = tmp_path / "emails"
    emails.mkdir()
    (emails / "email000000000002.eml").write_bytes(
        b"Subject: Chairs\r\nMessage-ID: <email000000000002@atm-bench>\r\n\r\n"
        b"Twelve chairs were ordered for the hall.\r\n")   # PII-OK: synthetic
    out = tmp_path / "audit.jsonl"
    assert GV.main(["audit-sample", "--kb", str(kb), "--n", "5", "--seed", "1",
                    "--out", str(out), "--evidence-dir", str(emails)]) == 0
    (row,) = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert set(row) == {"decision_id", "question", "gold", "leader", "evidence"}
    assert row["evidence"] == {"email000000000002": "Subject: Chairs\n\n"
                                                    "Twelve chairs were ordered for the hall."}
