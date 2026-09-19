"""The scoreboard (`eval/score.py`): the router recombination, the columns, rule 5, and the
pinned owner board. Hermetic except the last test, which needs the owner's KB and skips
without it."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from eval import score as S  # noqa: E402


def _row(qid: str, typed: tuple[str, bool | None, float], mono: tuple[str, bool | None, float],
         censored: bool = False) -> str:
    def arm(a: tuple[str, bool | None, float]) -> dict:
        return {"action": a[0], "correct": a[1], "cost_usd": a[2], "withheld": None}
    return json.dumps({"question_id": qid, "answerable": True, "censored": censored,
                       "typed": arm(typed), "mono": arm(mono)})


LINES = [
    _row("q1", ("report", True, 0.01), ("report", True, 0.30)),    # typed right
    _row("q2", ("report", False, 0.01), ("report", True, 0.30)),   # typed wrong, kept
    _row("q3", ("abstain", None, 0.02), ("report", True, 0.40)),   # escalated right
    _row("q4", ("abstain", None, 0.00), ("report", False, 0.20)),  # escalated wrong
    _row("q5", ("abstain", None, 0.00), ("abstain", None, 0.10)),  # declined by both
    _row("q6", ("abstain", None, 0.00), ("report", True, 0.50), censored=True),
]


def _by_arm() -> dict[str, S.Row]:
    return {r.arm: r for r in S.score_paired("t", LINES)}


def test_typed_and_oracle_are_counted_as_recorded() -> None:
    rows = _by_arm()
    assert (rows["typed"].right, rows["typed"].wrong, rows["typed"].declined) == (1, 1, 3)
    assert (rows["oracle"].right, rows["oracle"].wrong, rows["oracle"].declined) == (3, 1, 1)


def test_router_escalates_exactly_the_typed_withholdings() -> None:
    r = _by_arm()["router"]
    assert (r.rows, r.right, r.wrong, r.declined) == (5, 2, 2, 1)
    assert (r.esc_right, r.esc_wrong) == (1, 1)


def test_router_cost_is_additive_on_escalation() -> None:
    # q1 0.01 + q2 0.01 + q3 (0.02+0.40) + q4 (0+0.20) + q5 (0+0.10) = 0.74 over 5 rows
    assert _by_arm()["router"].usd_per_q == pytest.approx(0.74 / 5)


def test_censored_rows_leave_every_arm() -> None:
    assert {r.rows for r in S.score_paired("t", LINES)} == {5}


def test_s_per_q_is_blank_until_every_row_carries_latency() -> None:
    assert _by_arm()["typed"].s_per_q is None


def test_rule_5_fires_only_beyond_the_tolerance() -> None:
    row = S.summarise("t", "typed", [S.Response(True, False, 0.0)] + [
        S.Response(True, True, 0.0)] * 99)                           # 1.0% wrong
    assert S.gate([row], [{"set": "t", "arm": "typed", "rows": 100, "wrong": 1}]) == []
    assert S.gate([row], [{"set": "t", "arm": "typed", "rows": 1000, "wrong": 9}]) == []
    assert S.gate([row], [{"set": "t", "arm": "typed", "rows": 1000, "wrong": 7}]) != []


def test_a_moved_pin_refuses(tmp_path: Path) -> None:
    (tmp_path / "p.jsonl").write_text("\n".join(LINES), encoding="utf-8")
    sets = {"x": {"kind": "paired", "path": "p.jsonl", "sha256": "0" * 64}}
    with pytest.raises(SystemExit, match="pinned bytes moved"):
        S.score(tmp_path, sets)


def test_an_absent_set_is_named_not_dropped(tmp_path: Path) -> None:
    rows, skipped = S.score(tmp_path, {"x": {"kind": "paired", "path": "nope.jsonl",
                                             "sha256": "0" * 64}})
    assert rows == [] and "absent" in skipped["x"]
    assert "x" in S.render(rows, skipped)


def test_the_owner_board_reproduces_run_18() -> None:
    kb = os.environ.get("LIFE_AGENT_KB")
    spec = S.load_sets()["owner"]
    if not kb or not (Path(kb) / spec["path"]).is_file():
        pytest.skip("needs the owner's KB ($LIFE_AGENT_KB with the run-18 paired archive); "
                    "owner data, not buildable")
    rows, _ = S.score(Path(kb), {"owner": spec})
    got = {r.arm: (r.right, r.wrong, r.declined, round(r.usd_per_q * r.rows, 2))
           for r in rows}
    assert got == {"typed": (61, 2, 41, 0.37), "oracle": (95, 6, 3, 39.01),
                   "router": (97, 5, 2, 15.97)}


def test_the_board_is_never_written_from_less_than_every_pinned_set(tmp_path: Path) -> None:
    sets = {"x": {"kind": "paired", "path": "nope.jsonl", "sha256": "0" * 64},
            "y": {"kind": "pending", "note": "later"}}
    _, skipped = S.score(tmp_path, sets)
    assert S.unscored_pins(sets, skipped) == ["x"]
