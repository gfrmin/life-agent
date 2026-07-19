"""Unit tests for the explicit loss ledger (scripts/fairfight/loss_ledger.py).

Hermetic: no LLM, no corpus, no real utility model. The utility posterior is a fake
``UtilityPosterior`` built with **zero-variance** latents, so ``gate._sample_u`` returns the
posterior means exactly and every regret expectation is exact (q05 == q95 == mean). The
synthetic vectors carry only invented ids/values (``q-90x``) — no personal data.

Run from the repo root:
    uv run --project . python -m pytest ./tests/test_loss_ledger.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from fairfight import loss_ledger as LL

from life_agent.core.utility import LatentPosterior, UtilityPosterior

# The pricing the fake posterior pins (the real posterior's names: u_correct/u_abstain are
# the gauge, the rest are latents — see UtilityPosterior.u_bar).
_ORACLE_P = 0.9


def _fake_posterior() -> UtilityPosterior:
    def lp(name: str, mean: float, lo: float, hi: float) -> LatentPosterior:
        return LatentPosterior(name=name, mean=mean, variance=0.0, lo=lo, hi=hi)

    return UtilityPosterior(
        gauge={"u_correct": 1.0, "u_abstain": 0.0},
        latents={
            "u_wrong": lp("u_wrong", -6.0, -10.0, 0.0),
            "u_wrong_scoped": lp("u_wrong_scoped", -2.0, -6.0, 0.0),
            "u_hedged": lp("u_hedged", 0.4, 0.0, 1.0),
            "lambda_int": lp("lambda_int", 1.0, 0.0, 3.0),
            "kappa_att": lp("kappa_att", 0.03, 0.0, 1.0),
        },
        n_events=0,
        fold_version="test-posterior",
    )


def _row(qid: str, bucket: str, *, answerable: bool, gold_in_corpus: bool, asserted: bool,
         asserted_correct: bool, declined: bool, cause: str | None = None,
         status: str = "ok") -> dict:
    return {
        "question_id": qid, "answerable": answerable, "bucket": bucket, "cause": cause,
        "asserted": asserted, "asserted_correct": asserted_correct, "declined": declined,
        "gold_in_corpus": gold_in_corpus, "gold_in_topk": gold_in_corpus,
        "gold_in_candidates": None, "status": status,
    }


def _synthetic_rows() -> list[dict]:
    return [
        # CORRECT → class none, regret exactly 0
        _row("q-901", "CORRECT", answerable=True, gold_in_corpus=True,
             asserted=True, asserted_correct=True, declined=False),
        # CONFIDENT_WRONG → class confident_wrong, regret u_correct - u_wrong = 7.0
        _row("q-902", "CONFIDENT_WRONG", answerable=True, gold_in_corpus=True,
             asserted=True, asserted_correct=False, declined=False, cause="wrong_value"),
        # WRONGLY_WITHHELD/retrieval_miss → regret u_correct - u_abstain = 1.0
        _row("q-903", "WRONGLY_WITHHELD", answerable=True, gold_in_corpus=True,
             asserted=False, asserted_correct=False, declined=True, cause="retrieval_miss"),
        # RIGHTLY_WITHHELD (unanswerable) → class none, regret 0
        _row("q-904", "RIGHTLY_WITHHELD", answerable=False, gold_in_corpus=False,
             asserted=False, asserted_correct=False, declined=True, cause="unanswerable"),
        # infra failure → excluded, never graded
        _row("q-905", "CORRECT", answerable=True, gold_in_corpus=True,
             asserted=True, asserted_correct=True, declined=False, status="error"),
    ]


def _write_run(tmp_path: Path, rows: list[dict]) -> Path:
    arm_dir = tmp_path / "arms" / "baseline"
    arm_dir.mkdir(parents=True)
    (arm_dir / "vectors.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return tmp_path


def _build(tmp_path: Path, *, samples: int = 200, seed: int = 7) -> LL.Ledger:
    run_dir = _write_run(tmp_path, _synthetic_rows())
    return LL.load_and_build(run_dir, "baseline", _fake_posterior(),
                             oracle_p=_ORACLE_P, n_samples=samples, seed=seed)


# --- the two acts + the stage label ------------------------------------------------------

def test_actual_asserted_is_report_graded_by_asserted_correct() -> None:
    r = LL.actual_response(_row("q", "CORRECT", answerable=True, gold_in_corpus=True,
                                asserted=True, asserted_correct=True, declined=False))
    assert r.action == "report" and r.correct is True


def test_actual_declined_is_abstain() -> None:
    r = LL.actual_response(_row("q", "WRONGLY_WITHHELD", answerable=True, gold_in_corpus=True,
                                asserted=False, asserted_correct=False, declined=True))
    assert r.action == "abstain"


def test_oracle_reports_when_gold_knowable_else_abstains() -> None:
    knowable = _row("q", "CORRECT", answerable=True, gold_in_corpus=True,
                    asserted=True, asserted_correct=True, declined=False)
    unanswerable = _row("q", "RIGHTLY_WITHHELD", answerable=False, gold_in_corpus=False,
                        asserted=False, asserted_correct=False, declined=True)
    absent = _row("q", "WRONGLY_WITHHELD", answerable=True, gold_in_corpus=False,
                  asserted=False, asserted_correct=False, declined=True)
    assert LL.oracle_response(knowable).action == "report"
    assert LL.oracle_response(knowable).correct is True
    assert LL.oracle_response(unanswerable).action == "abstain"
    assert LL.oracle_response(absent).action == "abstain"


def test_stage_class_mapping() -> None:
    def cls(bucket: str, cause: str | None = None) -> str:
        return LL.stage_class(_row("q", bucket, answerable=True, gold_in_corpus=True,
                                   asserted=False, asserted_correct=False, declined=True,
                                   cause=cause))

    assert cls("CORRECT") == "none"
    assert cls("RIGHTLY_WITHHELD") == "none"
    assert cls("CONFIDENT_WRONG") == "confident_wrong"
    assert cls("WRONGLY_WITHHELD", "extraction_miss") == "extraction_miss"
    assert cls("WRONGLY_WITHHELD", None) == "unattributed"
    assert cls("SCOPED") == "scoped"  # an honest scoped claim: its own lever, own class
    assert cls("SOME_FUTURE_BUCKET") == "unattributed"  # unknown buckets counted, never crash


# --- the assembled ledger ----------------------------------------------------------------

def test_excluded_rows_counts_infra_failures(tmp_path: Path) -> None:
    assert _build(tmp_path).excluded_rows == 1


def test_per_class_totals_and_ranking(tmp_path: Path) -> None:
    ledger = _build(tmp_path)
    by_class = {cr.cls: cr for cr in ledger.per_class}
    assert by_class["confident_wrong"].mean == pytest.approx(7.0)
    assert by_class["confident_wrong"].n_questions == 1
    assert by_class["confident_wrong"].question_ids == ("q-902",)
    assert by_class["retrieval_miss"].mean == pytest.approx(1.0)
    assert by_class["retrieval_miss"].n_questions == 1
    assert by_class["none"].mean == pytest.approx(0.0)
    assert by_class["none"].n_questions == 2  # CORRECT + RIGHTLY_WITHHELD
    # ranked by mean EU mass, descending
    assert [cr.cls for cr in ledger.per_class] == ["confident_wrong", "retrieval_miss", "none"]


def test_total_is_the_sum_of_class_mass(tmp_path: Path) -> None:
    assert _build(tmp_path).total_mean == pytest.approx(8.0)  # 7 + 1 + 0 + 0


def test_zero_variance_collapses_quantiles_to_the_mean(tmp_path: Path) -> None:
    ledger = _build(tmp_path)
    for cr in ledger.per_class:
        assert cr.q05 == pytest.approx(cr.mean) and cr.q95 == pytest.approx(cr.mean)
    for qr in ledger.per_question:
        assert qr.q05 == pytest.approx(qr.mean) and qr.q95 == pytest.approx(qr.mean)
    assert ledger.total_q05 == pytest.approx(ledger.total_mean)
    assert ledger.total_q95 == pytest.approx(ledger.total_mean)


def test_json_round_trips(tmp_path: Path) -> None:
    d = LL.to_json_dict(_build(tmp_path))
    assert json.loads(json.dumps(d, sort_keys=True)) == d
    assert d["u_bar"]["u_wrong"] == pytest.approx(-6.0)
    assert d["excluded_rows"] == 1


def test_md_contains_ranked_class_lines_in_order(tmp_path: Path) -> None:
    md = LL.render_md(_build(tmp_path))
    i_cw = md.index("| confident_wrong |")
    i_rm = md.index("| retrieval_miss |")
    i_none = md.index("| none |")
    assert i_cw < i_rm < i_none
    assert "The ranking above is the explicit basis for 'what do we attack next'." in md


def test_write_outputs_lands_both_files_under_run_dir(tmp_path: Path) -> None:
    run_dir = _write_run(tmp_path, _synthetic_rows())
    ledger = LL.load_and_build(run_dir, "baseline", _fake_posterior(),
                               oracle_p=_ORACLE_P, n_samples=50, seed=7)
    jpath, mpath = LL.write_outputs(run_dir, ledger)
    assert jpath == run_dir / "loss_ledger" / "baseline.json"
    assert mpath == run_dir / "loss_ledger" / "baseline.md"
    assert json.loads(jpath.read_text())["arm"] == "baseline"
    assert mpath.read_text().startswith("# Loss ledger — baseline")


# --- the review's two correctness findings, pinned ---------------------------------------

def test_scoped_rows_price_as_report_scoped_with_their_own_class() -> None:
    # A SCOPED row has asserted=False (triage_answers: asserted = report|hedge only) but its
    # asserted_correct IS the scoped value's gold match (grading.py computes it over
    # asserted_values, which for a scoped view is [scoped_value]). Pricing it as abstain
    # charged an honest non-answer full withhold-regret and dumped it in "unattributed".
    post = _fake_posterior()

    def one(row: dict) -> float:
        return LL.regret_samples([row], post, oracle_p=_ORACLE_P,
                                 n_samples=1, seed=7)[row["question_id"]][0]

    ok = _row("q-906", "SCOPED", answerable=True, gold_in_corpus=True,
              asserted=False, asserted_correct=True, declined=False, cause="as_of_record")
    bad = _row("q-907", "SCOPED", answerable=True, gold_in_corpus=True,
               asserted=False, asserted_correct=False, declined=False, cause="as_of_record")
    assert LL.actual_response(ok).action == "report_scoped"
    assert LL.stage_class(ok) == "scoped"
    # scoped-correct: oracle u_correct(1.0) - u_hedged(0.4) = 0.6
    assert one(ok) == pytest.approx(0.6)
    # scoped-incorrect: oracle u_correct(1.0) - u_wrong_scoped(-2.0) = 3.0
    assert one(bad) == pytest.approx(3.0)


def test_correct_outside_corpus_proxy_has_zero_regret_not_negative() -> None:
    # The reviewer's reproduced case: CORRECT (asserted_correct=True) while the FTS
    # retrieval-channel proxy says gold_in_corpus=False. A corpus-only oracle abstains
    # (utility 0) against the arm's u_correct (1.0) — regret -1, dragging the "none"
    # class negative. The dominating oracle reports-correct whenever the arm itself
    # proved the gold attainable, so regret is exactly 0.
    post = _fake_posterior()

    def one(row: dict) -> float:
        return LL.regret_samples([row], post, oracle_p=_ORACLE_P,
                                 n_samples=1, seed=7)[row["question_id"]][0]

    row = _row("q-908", "CORRECT", answerable=True, gold_in_corpus=False,
               asserted=True, asserted_correct=True, declined=False)
    assert LL.stage_class(row) == "none"
    assert one(row) == pytest.approx(0.0)


def test_regret_is_never_negative_across_the_act_grid() -> None:
    # Domination, exhaustively: every (bucket-shape, answerable, gold_in_corpus,
    # asserted_correct) combination the vector schema can express prices >= 0.
    post = _fake_posterior()

    def one(row: dict) -> float:
        return LL.regret_samples([row], post, oracle_p=_ORACLE_P,
                                 n_samples=1, seed=7)[row["question_id"]][0]

    shapes = [("CORRECT", True, True), ("CONFIDENT_WRONG", True, False),
              ("WRONGLY_WITHHELD", False, False), ("RIGHTLY_WITHHELD", False, False),
              ("SCOPED", False, True), ("SCOPED", False, False)]
    for bucket, asserted, asserted_correct in shapes:
        for answerable in (True, False):
            for gic in (True, False):
                row = _row("q-909", bucket, answerable=answerable, gold_in_corpus=gic,
                           asserted=asserted, asserted_correct=asserted_correct,
                           declined=not asserted and bucket != "SCOPED")
                assert one(row) >= 0.0, (bucket, answerable, gic)
