"""Unit tests for ``scripts/fairfight/oracle_audit.py`` (roadmap A1 validation audit).

Hermetic: synthetic vectors/answers/questions built in-memory or under ``tmp_path``;
no KB, no run dir, no network. Synthetic values only (P-prefixed fake IDs, same
convention as the other fairfight test files).

Run from the repo root:
    uv run --project . python -m pytest ./tests/test_fairfight_oracle_audit.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from fairfight import oracle_audit as OA


def _vec(qid: str, bucket: str, *, status: str = "ok", answerable: bool = True,
         cause: str | None = None, cost: float | None = 0.5) -> dict[str, Any]:
    return {"question_id": qid, "bucket": bucket, "cause": cause, "status": status,
            "answerable": answerable, "cost_usd": cost, "latency_s": 2.0, "tool_calls": 3}


def _ans(qid: str, text: str) -> dict[str, Any]:
    return {"question_id": qid, "text": text}


def _qs() -> list[dict[str, Any]]:
    return [
        {"id": "q-001", "question": "what is the first value?", "answer": "P111"},
        {"id": "q-002", "question": "what is the second value?", "answer": "P222"},
        {"id": "q-003", "question": "what is the third value?", "answer": "P333"},
        {"id": "q-004", "question": "is there a fourth value?", "answer": ""},
    ]


def _build(vectors: list[dict[str, Any]], answers: list[dict[str, Any]]) -> dict[str, Any]:
    return OA.build_audit(vectors, answers, _qs(), arm="oracle", run_id="ff-test",
                          arm_config={"model": "fake-frontier"})


def test_bucket_to_audit_class_mapping_is_total() -> None:
    assert OA.audit_class("CORRECT") == "agree"
    assert OA.audit_class("RIGHTLY_WITHHELD") == "agree"
    assert OA.audit_class("CONFIDENT_WRONG") == "disagree_value"
    assert OA.audit_class("WRONGLY_WITHHELD") == "oracle_miss"
    assert OA.audit_class("SCOPED") == "scoped"
    assert OA.audit_class("SOME_FUTURE_BUCKET") == "other"  # listed, never dropped


def test_agreement_rates_and_class_counts() -> None:
    audit = _build(
        [_vec("q-001", "CORRECT"), _vec("q-002", "CONFIDENT_WRONG"),
         _vec("q-003", "WRONGLY_WITHHELD"),
         _vec("q-004", "RIGHTLY_WITHHELD", answerable=False)],
        [_ans("q-001", "P111 [a.txt]"), _ans("q-002", "P999 [b.txt]"),
         _ans("q-003", "NOT_IN_CORPUS: not found"), _ans("q-004", "NOT_IN_CORPUS: absent")],
    )
    assert audit["n_scored"] == 4
    assert audit["agreement_rate"] == 0.5  # q-001 + q-004
    assert audit["answerable_agreement_rate"] == 1 / 3  # q-001 of q-001..q-003
    assert audit["by_class"] == {"agree": 2, "disagree_value": 1, "oracle_miss": 1}
    assert audit["total_cost_usd"] == 2.0


def test_disagreements_carry_gold_and_oracle_text_for_adjudication() -> None:
    audit = _build(
        [_vec("q-002", "CONFIDENT_WRONG", cause="wrong_value")],
        [_ans("q-002", "P999 [b.txt]")],
    )
    (d,) = audit["disagreements"]
    assert d["question_id"] == "q-002"
    assert d["gold"] == "P222"
    assert d["oracle_text"] == "P999 [b.txt]"
    assert d["audit_class"] == "disagree_value"
    assert d["cause"] == "wrong_value"


def test_infra_failures_excluded_from_rates_but_named() -> None:
    audit = _build(
        [_vec("q-001", "CORRECT"), _vec("q-002", "CORRECT", status="timeout")],
        [_ans("q-001", "P111"), _ans("q-002", "")],
    )
    assert audit["n_scored"] == 1
    assert audit["agreement_rate"] == 1.0
    assert audit["n_excluded_infra"] == 1
    assert audit["excluded_question_ids"] == ["q-002"]


def test_render_md_has_adjudication_checklist_per_disagreement() -> None:
    audit = _build(
        [_vec("q-001", "CORRECT"), _vec("q-002", "CONFIDENT_WRONG")],
        [_ans("q-001", "P111"), _ans("q-002", "P999")],
    )
    md = OA.render_md(audit)
    assert md.count("[ ] oracle_right   [ ] gold_right   [ ] both_wrong") == 1
    assert "### q-002 — disagree_value (CONFIDENT_WRONG)" in md
    assert "**gold:** P222" in md
    assert "**oracle said:** P999" in md
    assert "| q-001 | agree | CORRECT |" in md


def test_render_md_clean_run_says_no_disagreements() -> None:
    audit = _build([_vec("q-001", "CORRECT")], [_ans("q-001", "P111")])
    md = OA.render_md(audit)
    assert "None — the oracle agrees with the gold everywhere" in md
    assert "[ ] oracle_right" not in md


def test_main_writes_json_and_md_under_the_run_dir(tmp_path: Path,
                                                    monkeypatch: Any) -> None:
    run_dir = tmp_path / "ff-test"
    arm_dir = run_dir / "arms" / "oracle"
    arm_dir.mkdir(parents=True)
    (arm_dir / "vectors.jsonl").write_text(
        json.dumps(_vec("q-001", "CORRECT")) + "\n", encoding="utf-8")
    (arm_dir / "answers.jsonl").write_text(
        json.dumps(_ans("q-001", "P111 [a.txt]")) + "\n", encoding="utf-8")
    (run_dir / "run_meta.json").write_text(json.dumps(
        {"run_id": "ff-test", "arm_configs": {"oracle": {"model": "fake-frontier"}}}),
        encoding="utf-8")
    monkeypatch.setattr(OA, "load_questions", _qs)

    rc = OA.main(["--run-dir", str(run_dir)])

    assert rc == 0
    audit = json.loads((run_dir / "audit" / "oracle_vs_gold.json").read_text())
    assert audit["agreement_rate"] == 1.0
    assert audit["arm_config"] == {"model": "fake-frontier"}
    md = (run_dir / "audit" / "oracle_vs_gold.md").read_text()
    assert "Oracle-vs-gold audit — oracle @ ff-test" in md


def test_main_survives_malformed_and_missing_run_meta(tmp_path: Path,
                                                       monkeypatch: Any) -> None:
    """PR-27 review Important-1: a truncated run_meta.json (non-atomic _write_json +
    interrupted run) must cost the header fields, never the audit."""
    for name, meta_bytes in (("corrupt", b'{"run_id": "ff-tr'), ("missing", None)):
        run_dir = tmp_path / name
        arm_dir = run_dir / "arms" / "oracle"
        arm_dir.mkdir(parents=True)
        (arm_dir / "vectors.jsonl").write_text(
            json.dumps(_vec("q-001", "CORRECT")) + "\n", encoding="utf-8")
        (arm_dir / "answers.jsonl").write_text(
            json.dumps(_ans("q-001", "P111")) + "\n", encoding="utf-8")
        if meta_bytes is not None:
            (run_dir / "run_meta.json").write_bytes(meta_bytes)
        monkeypatch.setattr(OA, "load_questions", _qs)

        assert OA.main(["--run-dir", str(run_dir)]) == 0
        audit = json.loads((run_dir / "audit" / "oracle_vs_gold.json").read_text())
        assert audit["agreement_rate"] == 1.0
        assert audit["run_id"] == name  # fallback: the run dir's own name
        assert audit["arm_config"] is None


def test_scoped_rows_are_listed_without_the_three_way_checklist() -> None:
    audit = _build([_vec("q-001", "SCOPED")], [_ans("q-001", "P111 (as of earlier)")])
    md = OA.render_md(audit)
    assert "### q-001 — scoped (SCOPED)" in md
    assert "[ ] oracle_right" not in md  # not a factual dispute — no owner bit pulled
    assert "no adjudication required" in md


def test_not_in_gold_placeholder_is_distinct_from_unanswerable(tmp_path: Path) -> None:
    audit = OA.build_audit(
        [_vec("q-999", "CONFIDENT_WRONG"), _vec("q-004", "CONFIDENT_WRONG",
                                                 answerable=False)],
        [_ans("q-999", "P000"), _ans("q-004", "P000")],
        _qs(), arm="oracle", run_id="ff-test", arm_config=None)
    md = OA.render_md(audit)
    assert "**gold:** (not in the gold file)" in md          # q-999: lookup gap
    assert "**gold:** (none — marked unanswerable)" in md    # q-004: real semantics


def test_zero_scored_is_named_not_a_clean_bill(tmp_path: Path) -> None:
    audit = _build([_vec("q-001", "CORRECT", status="error")], [_ans("q-001", "")])
    md = OA.render_md(audit)
    assert "Nothing was scored (n=0)" in md
    assert "agrees with the gold everywhere" not in md
