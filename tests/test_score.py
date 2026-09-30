"""The scoreboard (`eval/score.py`): the router recombination, the columns, the falls, and the
pinned owner board. Hermetic except the last test, which needs the owner's KB and skips
without it."""
from __future__ import annotations

import json
import math
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


def test_a_paired_set_may_name_the_arms_it_emits() -> None:
    rows = S.score_paired("t", LINES, ("outside", "router"))
    assert [r.arm for r in rows] == ["outside", "router"]
    full = {r.arm: r for r in S.score_paired("t", LINES)}
    assert rows == [full["outside"], full["router"]]   # router still recombines the typed arm


def test_the_default_emits_every_arm() -> None:
    assert [r.arm for r in S.score_paired("t", LINES)] == ["typed", "outside", "router"]
    assert [r.arm for r in S.score_paired("t", LINES, S.ARMS)] == ["typed", "outside", "router"]


def test_an_unknown_arm_refuses() -> None:
    with pytest.raises(SystemExit, match="unknown arm"):
        S.score_paired("t", LINES, ("mono",))


def test_a_set_with_arms_reaches_score_and_has_no_typed_calibration(tmp_path: Path) -> None:
    import hashlib
    f = tmp_path / "p.jsonl"
    f.write_text("\n".join(LINES), encoding="utf-8")
    sets = {"x": {"kind": "paired", "path": "p.jsonl", "arms": ["outside"],
                  "sha256": hashlib.sha256(f.read_bytes()).hexdigest()}}
    rows, _ = S.score(tmp_path, sets)
    assert [r.arm for r in rows] == ["outside"]
    _, cals = S.with_calibration(tmp_path, sets, rows)
    assert cals == {}


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
    assert S.falls([new], [_board(old)], G) == []


def test_rule_5_blocks_one_wrong_that_nine_rights_do_not_pay_for() -> None:
    # at u_wrong -9 a wrong costs exactly nine rights: eight new rights and one new wrong
    # lower U; nine and one leave it level (merges); ten and one raise it
    old = S.summarise("t", "typed", [S.Response(False, None, 0.0)] * 20)

    def new(k_right: int) -> S.Row:
        return S.summarise("t", "typed", [S.Response(True, True, 0.0)] * k_right
                           + [S.Response(True, False, 0.0)]
                           + [S.Response(False, None, 0.0)] * (19 - k_right))
    assert S.falls([new(8)], [_board(old)], G) != []
    assert S.falls([new(9)], [_board(old)], G) == []
    assert S.falls([new(10)], [_board(old)], G) == []


def test_rule_5_charges_spend_at_lambda_usd() -> None:
    old = S.summarise("t", "typed", [S.Response(True, True, 0.0)] * 4)
    dearer = S.summarise("t", "typed", [S.Response(True, True, 0.25)] * 4)
    assert S.falls([dearer], [_board(old)], G) != []       # same answers, $1 more
    assert S.falls([old], [_board(dearer)], G) == []


def test_rule_5_names_an_unpaired_row() -> None:
    old = S.summarise("t", "typed", [S.Response(True, True, 0.0)] * 4)
    new = S.summarise("t", "typed", [S.Response(True, True, 0.0)] * 5)
    assert S.falls([new], [_board(old)], G) == ["t/typed: 4 -> 5 rows, not paired"]


def test_the_board_shows_u_per_question_only_with_a_gauge() -> None:
    rows = S.score_paired("t", LINES)
    # the typed row: U/q, s/q (blank until latency), then log score and ECE (— on an old archive)
    assert S.render(rows, {}).splitlines()[6].endswith("| — | — | — | — |")
    priced = S.render(rows, {}, G)
    typed = rows[0]
    assert "u_wrong -9.0000" in priced
    assert priced.splitlines()[6].endswith(
        f"| {G.total(_board(typed)) / typed.rows:+.3f} | — | — | — |")


def test_a_scored_row_carries_its_note_onto_the_board() -> None:
    """A U/q is a claim about a population, and the clause naming that population is the
    first thing a reader drops — `atm`'s five wrongs each name the gold fact in another
    surface form, so a bare U/q on the board says something its note denies. Killed by
    rendering notes for skipped sets only, which is what the board did until the `atm`
    row was pinned."""
    rows = S.score_paired("t", LINES)
    board = S.render(rows, {}, G, {"t": "what   t\n  is", "other": "never scored"})
    assert "- **`t`** — what t is" in board
    assert "other" not in board


def test_a_note_is_rendered_once_for_a_set_with_several_arms() -> None:
    """`owner` is three rows from one set; its note belongs under the board once."""
    rows = S.score_paired("t", LINES)
    assert len({r.arm for r in rows}) > 1
    assert S.render(rows, {}, G, {"t": "one note"}).count("- **`t`** —") == 1


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
    applied at the menu's prices, cache or no cache (the per-call arm it
    replaced: 61/2/41 at $20.95, forty calls to the deliberative rung its warm replays had
    metered at $0)."""
    kb = os.environ.get("LIFE_AGENT_KB")
    spec = S.load_sets()["owner-0920"]
    if not kb or not (Path(kb) / spec["path"]).is_file():
        pytest.skip("needs the owner's KB ($LIFE_AGENT_KB with the run-18 paired archive); "
                    "owner data, not buildable")
    rows, _ = S.score(Path(kb), {"owner-0920": spec})
    got = {r.arm: (r.right, r.wrong, r.declined, round(r.usd_per_q * r.rows, 2))
           for r in rows}
    # frozen 2026-09-20 recordings; the router recombines them with the 48/0/56 typed arm,
    # which is no longer a board row (`owner/typed` is the 2026-09-30 re-run)
    assert got == {"outside": (87, 13, 4, 43.00), "router": (90, 11, 3, 24.51)}


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



# --- Calibration columns and section ---------------------------------------------------

def _cal_row(action: str, correct: bool | None, p1: float | None, n: int, leader: bool | None,
             truth: bool) -> dict:
    return {"question_id": "s", "censored": False,
            "typed": {"action": action, "correct": correct, "cost_usd": 0.0, "p1": p1,
                      "n_candidates": n, "leader_correct": leader, "truth_in_candidates": truth}}


def _typed_set(tmp_path: Path, rows: list[dict]) -> tuple[dict, str]:
    import hashlib
    f = tmp_path / "t.jsonl"
    f.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    return ({"g": {"kind": "typed", "path": "t.jsonl",
                   "sha256": hashlib.sha256(f.read_bytes()).hexdigest()}}, f.read_text())


def test_an_old_archive_renders_dashes_and_no_calibration_section(tmp_path: Path) -> None:
    sets, _ = _typed_set(tmp_path, [{"question_id": "a", "typed": {
        "action": "report", "correct": True, "cost_usd": 0.0}}])
    rows, _ = S.score(tmp_path, sets)
    rows, cals = S.with_calibration(tmp_path, sets, rows)
    assert cals == {} and (rows[0].log_score, rows[0].ece, rows[0].n_scored) == (None,) * 3
    board = S.render(rows, {}, None, None, cals)
    assert "## Calibration" not in board and "| — | — | — | — |" in board


def test_a_new_archive_renders_numbers_and_a_reliability_table(tmp_path: Path) -> None:
    sets, _ = _typed_set(tmp_path, [
        _cal_row("report", True, 0.9, 1, True, True),
        _cal_row("abstain", None, 0.5, 2, False, False),      # scored: an abstain has a leader
        _cal_row("abstain", None, None, 0, None, False)])     # no candidate
    rows, _ = S.score(tmp_path, sets)
    rows, cals = S.with_calibration(tmp_path, sets, rows)
    (r,) = rows
    assert r.n_scored == 2
    assert r.log_score == pytest.approx((math.log(0.9) + math.log(0.5)) / 2)
    board = S.render(rows, {}, None, None, cals)
    assert f"| {r.log_score:.3f} | {r.ece:.3f} |" in board
    assert "## Calibration" in board and "| 0.9-1.0 | 1 | 0.900 | 1.000 |" in board
    assert "2 scored · 1 with no candidate · 1 truth absent" in board


def test_the_calibration_fields_are_optional_on_a_board_row() -> None:
    """A committed board written before the columns has none of the three keys."""
    row = S.summarise("t", "typed", [S.Response(True, True, 0.0)])
    assert (row.log_score, row.ece, row.n_scored) == (None, None, None)


def test_a_set_names_a_decision_run_for_an_archive_that_predates_the_fields(
        tmp_path: Path) -> None:
    import hashlib
    from datetime import UTC, datetime

    import yaml

    from life_agent.core import decisions as DEC
    q = "what is the synthetic code?"   # PII-OK: synthetic question
    (tmp_path / "q.yaml").write_text(yaml.safe_dump({"questions": [
        {"id": "q1", "question": q, "answer": "K7"}]}), encoding="utf-8")
    (tmp_path / "calibration").mkdir()
    ev = DEC.DecisionEvent(
        tx_time=datetime.now(UTC).isoformat(), run_id="run-x", question_id=DEC.question_id(q),
        family="lookup", action_set=("abstain",),
        posterior_summary={"candidates": ["K7"], "credences": [0.8]},
        utility_fold_version="v", chosen_action="abstain", predicted_eu=0.0)
    DEC.append(tmp_path / "calibration" / "decisions.jsonl", ev)
    f = tmp_path / "t.jsonl"
    f.write_text(json.dumps({"question_id": "q1", "typed": {
        "action": "abstain", "correct": None, "cost_usd": 0.0}}), encoding="utf-8")
    sets = {"g": {"kind": "typed", "path": "t.jsonl", "questions": "q.yaml",
                  "decisions_run": "run-x", "sha256": hashlib.sha256(f.read_bytes()).hexdigest()}}
    rows, _ = S.score(tmp_path, sets)
    rows, cals = S.with_calibration(tmp_path, sets, rows)
    assert cals["g"].n_scored == 1 and rows[0].log_score == pytest.approx(math.log(0.8))


# --- cite: partial answers are their own columns, priced at their own gauge rows ----------

def _cite_lines() -> list[str]:
    def row(qid: str, action: str, correct: bool | None) -> str:
        arm = {"action": action, "correct": correct, "cost_usd": 0.0, "withheld": None}
        return json.dumps({"question_id": qid, "answerable": True, "censored": False,
                           "typed": arm, "mono": {**arm, "action": "abstain",
                                                  "correct": None}})
    return [row("a", "report", True), row("b", "report", False), row("c", "cite", True),
            row("d", "cite", True), row("e", "cite", False), row("f", "abstain", None)]


def test_cites_count_apart_from_value_answers_and_declines() -> None:
    typed = {r.arm: r for r in S.score_paired("t", _cite_lines())}["typed"]
    assert (typed.right, typed.wrong) == (1, 1)
    assert (typed.cite_right, typed.cite_wrong, typed.declined) == (2, 1, 1)
    # the router escalates a cite as it does any non-assertion, and does not count it
    router = {r.arm: r for r in S.score_paired("t", _cite_lines())}["router"]
    assert (router.cite_right, router.cite_wrong) == (0, 0)


def test_the_gauge_prices_cites_at_the_cite_rows_and_defaults_them() -> None:
    row = S.summarise("t", "typed", [S.Response(False, True, 0.0, cite=True)] * 2
                      + [S.Response(False, False, 0.0, cite=True)])
    g = S.Gauge(1.0, -9.0, 0.0, 2.0, u_cite_right=0.6, u_cite_wrong=-2.0)
    assert g.total(_board(row)) == pytest.approx(2 * 0.6 - 2.0)
    assert (G.u_cite_right, G.u_cite_wrong) == (0.5, -1.0)
    assert G.total(_board(row)) == pytest.approx(2 * 0.5 - 1.0)
    # a committed board row from before the columns has no cite counts: they read as zero
    old = {k: v for k, v in _board(row).items() if not k.startswith("cite")}
    assert G.total(old) == pytest.approx(0.0)


def test_the_board_renders_the_cite_columns_and_the_gauge_rows() -> None:
    rows = S.score_paired("t", _cite_lines(), ("typed",))
    text = S.render(rows, {}, G)
    assert "| cite-right | cite-wrong |" in text
    assert "u_cite_right 0.5, u_cite_wrong -1" in text
    # 1 right - 9 wrong + 2 cite-right - 1 cite-wrong, over 6 rows
    assert f"{(1 - 9 + 2 * 0.5 - 1.0) / 6:+.3f}" in text
