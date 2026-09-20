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


def test_typed_and_outside_are_counted_as_recorded() -> None:
    rows = _by_arm()
    assert (rows["typed"].right, rows["typed"].wrong, rows["typed"].declined) == (1, 1, 3)
    assert (rows["outside"].right, rows["outside"].wrong, rows["outside"].declined) == (3, 1, 1)


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


G = S.Gauge(u_right=1.0, u_wrong=-9.0, u_declined=0.0, lambda_usd=2.0)


def _board(row: S.Row) -> dict:
    from dataclasses import asdict
    return asdict(row)


def test_the_gauge_prices_a_row_from_its_counts() -> None:
    row = S.summarise("t", "typed", [S.Response(True, True, 0.5), S.Response(True, False, 0.0),
                                     S.Response(False, None, 0.5)])
    # 1 right - 9 wrong + 0 declined - 2/$ x $1.00 spent
    assert G.total(_board(row)) == pytest.approx(1.0 - 9.0 - 2.0)


def test_rule_5_passes_a_change_that_trades_declines_for_right_answers() -> None:
    old = S.summarise("t", "typed", [S.Response(False, None, 0.0)] * 10)
    new = S.summarise("t", "typed", [S.Response(True, True, 0.0)] * 10)
    assert S.gate([new], [_board(old)], G) == []


def test_rule_5_blocks_one_wrong_that_nine_rights_do_not_pay_for() -> None:
    # at u_wrong -9 a wrong costs exactly nine rights: eight new rights and one new wrong
    # lower U; nine and one leave it level (merges); ten and one raise it
    old = S.summarise("t", "typed", [S.Response(False, None, 0.0)] * 20)

    def new(k_right: int) -> S.Row:
        return S.summarise("t", "typed", [S.Response(True, True, 0.0)] * k_right
                           + [S.Response(True, False, 0.0)]
                           + [S.Response(False, None, 0.0)] * (19 - k_right))
    assert S.gate([new(8)], [_board(old)], G) != []
    assert S.gate([new(9)], [_board(old)], G) == []
    assert S.gate([new(10)], [_board(old)], G) == []


def test_rule_5_charges_spend_at_lambda_usd() -> None:
    old = S.summarise("t", "typed", [S.Response(True, True, 0.0)] * 4)
    dearer = S.summarise("t", "typed", [S.Response(True, True, 0.25)] * 4)
    assert S.gate([dearer], [_board(old)], G) != []       # same answers, $1 more
    assert S.gate([old], [_board(dearer)], G) == []


def test_rule_5_names_an_unpaired_row() -> None:
    old = S.summarise("t", "typed", [S.Response(True, True, 0.0)] * 4)
    new = S.summarise("t", "typed", [S.Response(True, True, 0.0)] * 5)
    assert S.gate([new], [_board(old)], G) == ["t/typed: 4 -> 5 rows, not paired"]


def test_the_board_shows_u_per_question_only_with_a_gauge() -> None:
    rows = S.score_paired("t", LINES)
    # the typed row: U/q then s/q (blank until latency) close the line
    assert S.render(rows, {}).splitlines()[6].endswith("| — | — |")
    priced = S.render(rows, {}, G)
    typed = rows[0]
    assert "u_wrong -9.0000" in priced
    assert priced.splitlines()[6].endswith(f"| {G.total(_board(typed)) / typed.rows:+.3f} | — |")


def test_a_typed_set_scores_the_typed_row_alone(tmp_path: Path) -> None:
    import hashlib

    lines = [json.dumps({"question_id": f"g{i}", "censored": c,
                         "typed": {"action": a, "correct": ok, "cost_usd": 0.01}})
             for i, (a, ok, c) in enumerate([("report", True, False), ("report", False, False),
                                             ("abstain", None, False), ("report", True, True)])]
    (tmp_path / "t.jsonl").write_text("\n".join(lines), encoding="utf-8")
    sha = hashlib.sha256((tmp_path / "t.jsonl").read_bytes()).hexdigest()
    rows, _ = S.score(tmp_path, {"g": {"kind": "typed", "path": "t.jsonl", "sha256": sha}})
    ((r),) = rows
    assert (r.arm, r.rows, r.right, r.wrong, r.declined) == ("typed", 3, 1, 1, 1)


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


def test_the_owner_board_reproduces_the_host_act_on_one_grader_and_one_price_list() -> None:
    """The pinned incumbent — J1's host Bayes act — both arms graded on the answer they
    commit and priced at their declared prices. The outside arm's 13 wrongs are the honest
    count: the prose grading it replaced scored the same answers 5 wrong by accepting a
    gold that appeared anywhere in a paragraph. The typed arm's $1.44 is every probe it
    applied at the menu's prices, cache or no cache (the daemon it replaced: 61/2/41 at
    $20.95, forty calls to the deliberative rung its warm replays had metered at $0)."""
    kb = os.environ.get("LIFE_AGENT_KB")
    spec = S.load_sets()["owner"]
    if not kb or not (Path(kb) / spec["path"]).is_file():
        pytest.skip("needs the owner's KB ($LIFE_AGENT_KB with the run-18 paired archive); "
                    "owner data, not buildable")
    rows, _ = S.score(Path(kb), {"owner": spec})
    got = {r.arm: (r.right, r.wrong, r.declined, round(r.usd_per_q * r.rows, 2))
           for r in rows}
    assert got == {"typed": (48, 0, 56, 1.44), "outside": (87, 13, 4, 43.00),
                   "router": (90, 11, 3, 24.51)}


def test_the_board_is_never_written_from_less_than_every_pinned_set(tmp_path: Path) -> None:
    sets = {"x": {"kind": "paired", "path": "nope.jsonl", "sha256": "0" * 64},
            "y": {"kind": "pending", "note": "later"}}
    _, skipped = S.score(tmp_path, sets)
    assert S.unscored_pins(sets, skipped) == ["x"]


# --- A set may name its own root (J3) --------------------------------------------------
# Every set used to resolve against one $LIFE_AGENT_KB, which two of them are not: the
# synthetic `sample` lives in the repo so a stranger can score it from a clone with no KB
# at all, and the external `atm` corpus is deliberately its own KB root, named by an env
# var so no machine-specific path enters this public file.

def test_a_repo_rooted_set_scores_without_a_kb() -> None:
    root, why = S.set_root({"root": "repo"}, None)
    assert (root, why) == (S.REPO, "")


def test_the_synthetic_sample_row_is_scored_from_the_repo_alone() -> None:
    """The stranger's board row, end to end: no $LIFE_AGENT_KB, real pinned bytes.
    Killed by resolving `sample` against the KB again, or by the archive leaving the tree."""
    spec = S.load_sets()["sample"]
    rows, skipped = S.score(None, {"sample": spec})
    assert "sample" not in skipped, skipped
    ((r),) = rows
    assert (r.arm, r.rows, r.wrong) == ("typed", 14, 0)
    assert r.right > 0, "the sample row asserts nothing — a decider that only declines"


def test_an_env_rooted_set_says_which_variable_is_unset(monkeypatch) -> None:
    monkeypatch.delenv("LIFE_AGENT_ATM_KB", raising=False)
    root, why = S.set_root({"root_env": "LIFE_AGENT_ATM_KB"}, Path("/kb"))
    assert root is None and "LIFE_AGENT_ATM_KB" in why


def test_an_env_rooted_set_reads_from_its_own_root(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LIFE_AGENT_ATM_KB", str(tmp_path))
    root, why = S.set_root({"root_env": "LIFE_AGENT_ATM_KB"}, Path("/kb"))
    assert (root, why) == (tmp_path, "")


def test_a_set_with_no_root_declared_still_reads_the_kb(tmp_path: Path) -> None:
    """The discriminating control: the default must not move."""
    assert S.set_root({"path": "x.jsonl"}, tmp_path) == (tmp_path, "")

