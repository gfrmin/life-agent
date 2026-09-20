"""The live stream as a board row (`scripts/live_archive.py`).

The binding properties: a verdict binds a decision by `decision_id` and never by
`question_id`; eval traffic never enters; an assert the owner did not grade is recorded
but not scored; a withhold is scoreable on its own. The last test closes the loop by
scoring the archive with the real scoreboard, so the shape cannot drift apart from its
only reader.

Run: uv run --project . python -m pytest tests/test_live_archive.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import live_archive as LA  # noqa: E402

from eval import score as S  # noqa: E402


def _dec(did: str, action: str, *, qid: str = "q" * 16, run: str = "answer-brain",
         cost: float = 0.01, tx: str = "2026-09-20T10:00:00+00:00") -> dict:
    return {"decision_id": did, "chosen_action": action, "question_id": qid,
            "run_id": run, "cost_usd": cost, "tx_time": tx, "latency_s": 1.5,
            "posterior_summary": {"withheld": "dispersed"}}


def _rx(did: str, valence: str, *, tx: str = "2026-09-20T10:05:00+00:00") -> dict:
    return {"decision_id": did, "valence": valence, "kind": "verdict", "tx_time": tx,
            "question_id": "q" * 16}


def test_a_verdict_binds_by_decision_not_by_question() -> None:
    """Two decisions on the SAME question, one graded good. Killed by joining on
    question_id, which would grade both — the defect live_readout names in its docstring
    and the reason decision_id is the join key."""
    rows = LA.archive([_dec("d1", "report"), _dec("d2", "report")], [_rx("d1", "good")])
    by_id = {r["decision_id"]: r for r in rows}
    assert by_id["d1"]["typed"]["correct"] is True and not by_id["d1"]["censored"]
    assert by_id["d2"]["typed"]["correct"] is None and by_id["d2"]["censored"]


def test_eval_traffic_never_enters_the_live_row() -> None:
    """Killed by dropping the is_live filter: a gate run would supply the live row's
    evidence, which is the arm scoring itself on its own benchmark."""
    rows = LA.archive([_dec("d1", "report", run="gate-20260920T000000"),
                       _dec("d2", "abstain")], [])
    assert [r["decision_id"] for r in rows] == ["d2"]


def test_an_ungraded_assert_is_recorded_but_not_scored() -> None:
    """The row exists (the archive describes the whole population) and is censored (the
    board may not count an answer nobody graded). Killed by omitting the row, which hides
    the ungraded population, or by scoring it, which invents a grade."""
    rows = LA.archive([_dec("d1", "report")], [])
    assert len(rows) == 1 and rows[0]["censored"]
    assert LA.summarise(rows) == {"rows": 1, "scoreable": 0, "ungraded_asserts": 1,
                                  "right": 0, "wrong": 0, "declined": 0,
                                  "graded_withholds": {}, "spend_usd": 0.01,
                                  "first": "2026-09-20", "last": "2026-09-20"}


def test_a_verdict_on_a_withhold_is_counted_but_never_scored_as_wrong() -> None:
    """The loudest signal in the live stream: the owner marking a DECLINE bad — "you
    should have answered". It cannot make the row wrong (only a committed answer can be
    wrong, rule 1) and the gauge prices every withhold the same, so the board's counts
    must not move; the summary must still say it, or the archive drops the one thing the
    owner actually complained about. Killed either by scoring it wrong or by dropping it
    from the summary."""
    decisions = [_dec("d1", "abstain"), _dec("d2", "abstain")]
    reactions = [_rx("d1", "bad"), _rx("d2", "good")]
    rows = LA.archive(decisions, reactions)
    assert all(r["typed"]["correct"] is None and not r["censored"] for r in rows)
    s = LA.summarise(rows, LA.verdicts_by_decision(reactions))
    assert s["declined"] == 2 and s["wrong"] == 0
    assert s["graded_withholds"] == {"wanted_an_answer": 1, "endorsed": 1}


def test_a_withhold_is_scoreable_without_a_verdict() -> None:
    """Declining is an answer (rule 1) priced at u_declined, so it needs no grade.
    Killed by censoring every ungraded row, which would empty the row of its declines —
    the majority of what the act does."""
    rows = LA.archive([_dec("d1", "abstain")], [])
    assert not rows[0]["censored"] and rows[0]["typed"]["correct"] is None


def test_a_bad_verdict_is_a_wrong_answer() -> None:
    rows = LA.archive([_dec("d1", "report")], [_rx("d1", "bad")])
    assert rows[0]["typed"]["correct"] is False and not rows[0]["censored"]


def test_the_latest_verdict_wins() -> None:
    """The owner may re-grade; the record is append-only, so the archive must read the
    last word rather than the first."""
    rows = LA.archive([_dec("d1", "report")],
                      [_rx("d1", "bad"), _rx("d1", "good", tx="2026-09-20T11:00:00+00:00")])
    assert rows[0]["typed"]["correct"] is True


def test_a_verdict_that_binds_nothing_is_dropped_not_guessed() -> None:
    rows = LA.archive([_dec("d1", "report")], [{"valence": "good", "kind": "verdict"}])
    assert rows[0]["censored"]


def test_since_bounds_the_window() -> None:
    rows = LA.archive([_dec("old", "abstain", tx="2026-08-01T00:00:00+00:00"),
                       _dec("new", "abstain")], [], since="2026-09-01")
    assert [r["decision_id"] for r in rows] == ["new"]


def test_the_archive_is_in_the_shape_the_scoreboard_scores() -> None:
    """The loop closed: the real scorer reads the real writer's output. Killed by any
    drift in the row shape — a renamed key, a censored flag the board does not honour,
    a correctness the board reads differently."""
    rows = LA.archive([_dec("d1", "report"), _dec("d2", "report"), _dec("d3", "abstain"),
                       _dec("d4", "report")],
                      [_rx("d1", "good"), _rx("d2", "bad")])
    lines = [json.dumps(r) for r in rows]
    (row,) = S.score_typed("live", lines)
    # d4 is the ungraded assert: censored, so it leaves the arm entirely.
    assert (row.arm, row.rows, row.right, row.wrong, row.declined) == ("typed", 3, 1, 1, 1)
    assert row.usd_per_q == 0.01
