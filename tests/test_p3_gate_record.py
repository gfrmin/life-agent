"""Hermetic tests for the p3 harness's RECORD (`scripts/membrane/p3_gate.py`): the `M-32`
phase marks (a long measurement timestamps its own phase boundaries and publishes its
wall/CPU split) and the `M-33` regime record in `a3_meta` (the regimes a differential
reading spans, with both Ū at full precision, plus the marginal-commit table that decides
whether the pairing bit).

No engine, no clock: every clock is injected.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, "scripts")

import membrane.p3_gate as P3

from life_agent.core import decisions as DEC
from life_agent.core import gate as GATE
from life_agent.core import utility as UT


def _point(name: str, value: float) -> UT.LatentPosterior:
    return UT.LatentPosterior(name=name, mean=value, variance=0.0, lo=value, hi=value)


def _posterior() -> UT.UtilityPosterior:
    # the same test posterior `test_p3_gate.py` uses (u_wrong -2.0 => break-even 0.6667)
    return UT.UtilityPosterior(
        gauge={"u_correct": 1.0, "u_abstain": 0.0},
        latents={"u_wrong": _point("u_wrong", -2.0),
                 "u_hedged": _point("u_hedged", 0.3),
                 "lambda_int": _point("lambda_int", 0.5),
                 "lambda_usd": _point("lambda_usd", 0.0),
                 "kappa_att": _point("kappa_att", 0.05)},
        n_events=0, fold_version="test", policy="frozen-elicitations")


def _p3b_fixture() -> tuple[list[P3.HeldoutTick], dict[str, str], list[dict]]:
    h = DEC.question_id("joined question text?")
    rows = [P3.HeldoutTick(question_id=h, leader_credence=0.95, p1=0.97, y=1, respond=True)]
    baseline_rows = [{"question_id": "q2-005", "answerable": True, "asserted": True,
                      "asserted_correct": True, "bucket": "CONFIDENT_RIGHT"}]
    return rows, {h: "q2-005"}, baseline_rows

# PII-OK: synthetic utility means — a deployed-shaped Ū (break-even 0.8559) against the
# test posterior's u_wrong = -2.0 (break-even 0.6667), so the pair is divergent by design.
PRICING = {"u_correct": 1.0, "u_wrong": -5.9395, "u_abstain": 0.0}


class _Times:
    """A stand-in for `os.times()`: user, system, children_user, children_system, elapsed."""

    def __init__(self, user: float, system: float, cu: float, cs: float) -> None:
        self.user, self.system = user, system
        self.children_user, self.children_system = cu, cs
        self.elapsed = 0.0


def _mark(phase: str, *, at: float, mono: float, cpu: tuple[float, float, float, float]
          ) -> P3.PhaseMark:
    return P3.phase_mark(phase, now=lambda: at, mono=lambda: mono,
                         times=lambda: _Times(*cpu))


# --- M-32: phase marks ------------------------------------------------------------------


def test_phase_mark_reads_injected_clocks_and_sums_self_and_children_cpu() -> None:
    m = _mark("probe:FULL", at=1_757_000_000.0, mono=12.5, cpu=(1.0, 0.5, 100.0, 2.0))
    assert m.phase == "probe:FULL"
    assert m.at == "2025-09-04T15:33:20Z"          # ISO-8601 UTC, seconds — liveness
    assert m.wall == 12.5
    assert m.cpu == 103.5                          # the engines are CHILDREN: counted


def test_phase_spans_pair_consecutive_marks_and_the_last_mark_terminates() -> None:
    marks = [_mark("load", at=0.0, mono=0.0, cpu=(0, 0, 0, 0)),
             _mark("probe:FULL", at=5.0, mono=5.0, cpu=(1, 0, 0, 0)),
             _mark("end", at=65.0, mono=65.0, cpu=(2, 0, 50, 3))]
    spans = P3.phase_spans(marks)
    assert [(s.phase, s.wall_s, s.cpu_s) for s in spans] == [
        ("load", 5.0, 1.0), ("probe:FULL", 60.0, 54.0)]


def test_render_phase_boundary_names_the_phase_and_the_previous_span() -> None:
    first = _mark("load", at=0.0, mono=0.0, cpu=(0, 0, 0, 0))
    second = _mark("probe:FULL", at=3725.0, mono=3725.0, cpu=(100.0, 0, 3000.0, 0))
    assert P3.render_phase_boundary(None, first) == "[1970-01-01T00:00:00Z] ▶ load"
    line = P3.render_phase_boundary(first, second)
    assert line.startswith("[1970-01-01T01:02:05Z] ▶ probe:FULL")
    assert "load" in line and "wall 1:02:05" in line and "cpu 0:51:40" in line


def test_render_phase_summary_publishes_every_span_and_the_wall_cpu_split() -> None:
    marks = [_mark("load", at=0.0, mono=0.0, cpu=(0, 0, 0, 0)),
             _mark("probe:FULL", at=10.0, mono=10.0, cpu=(2, 0, 0, 0)),
             _mark("a3:FULL", at=110.0, mono=110.0, cpu=(3, 0, 80, 0)),
             _mark("end", at=120.0, mono=120.0, cpu=(4, 0, 80, 0))]
    text = P3.render_phase_summary(marks)
    for phase in ("load", "probe:FULL", "a3:FULL"):
        assert phase in text
    assert "end" not in text.replace("cpu/wall", "")  # the terminator has no span
    assert "total wall 0:02:00" in text and "cpu 0:01:24" in text
    assert "cpu/wall 0.70" in text


def test_fmt_hms_is_hours_minutes_seconds() -> None:
    assert P3.fmt_hms(0) == "0:00:00"
    assert P3.fmt_hms(59.6) == "0:01:00"
    assert P3.fmt_hms(50_522) == "14:02:02"       # r49's fourteen hours, to the second


def test_write_phases_roundtrips_marks_spans_and_totals(tmp_path: Path) -> None:
    marks = [_mark("load", at=0.0, mono=0.0, cpu=(0, 0, 0, 0)),
             _mark("end", at=7.5, mono=7.5, cpu=(1.0, 0.5, 4.0, 0.0))]
    path = P3.write_phases(tmp_path, marks)
    assert path == tmp_path / "phases.json"
    d = json.loads(path.read_text())
    assert [m["phase"] for m in d["marks"]] == ["load", "end"]
    assert d["spans"] == [{"phase": "load", "wall_s": 7.5, "cpu_s": 5.5}]
    assert d["total"] == {"wall_s": 7.5, "cpu_s": 5.5}


# --- M-33: the regime record + the marginal-commit table ----------------------------------


def _pairing() -> GATE.RegimePairing:
    return GATE.regime_pairing(pricing_u_bar=PRICING, pricing_policy="all-to-date",
                               scoring_u_bar=_posterior().u_bar(),
                               scoring_policy="frozen-elicitations")


def test_regime_record_carries_both_policies_break_evens_and_u_bars_at_full_precision() -> None:
    rec = P3.regime_record(_pairing(), pricing_u_bar=PRICING,
                           scoring_u_bar=_posterior().u_bar())
    assert rec["pricing"]["policy"] == "all-to-date"
    assert rec["scoring"]["policy"] == "frozen-elicitations"
    assert rec["pricing"]["break_even"] == GATE.break_even(PRICING)
    assert rec["scoring"]["break_even"] == GATE.break_even(_posterior().u_bar())
    assert rec["pricing"]["u_bar"]["u_wrong"] == -5.9395          # the dict, not a digest
    assert rec["scoring"]["u_bar"]["u_wrong"] == -2.0
    assert rec["divergent"] is True


def _paired(rows: list[tuple[str, bool, bool, bool]]) -> list[GATE.PairedOutcome]:
    """rows: (qid, typed_asserts, typed_correct, mono_asserts) — mono correct when it asserts."""
    acts, h2q, baseline = {}, {}, []
    for qid, t_assert, t_correct, m_assert in rows:
        h = DEC.question_id(f"question {qid}?")
        acts[h] = (GATE.RealisedResponse("report", correct=t_correct) if t_assert
                   else GATE.RealisedResponse("abstain"))
        h2q[h] = qid
        baseline.append({"question_id": qid, "answerable": True, "asserted": m_assert,
                         "asserted_correct": m_assert, "bucket": "x"})
    paired, _, _ = P3.build_paired(acts, h2q, baseline)
    return paired


def test_marginal_commits_counts_typed_asserts_over_mono_withheld_and_the_reverse() -> None:
    paired = _paired([("q1", True, True, False),    # marginal commit, correct
                      ("q2", True, False, False),   # marginal commit, wrong
                      ("q3", True, True, True),     # both assert — not marginal
                      ("q4", False, False, True),   # abstain-x-report — the reverse
                      ("q5", False, False, False)])
    table = P3.marginal_commits(paired)
    assert table == {"n": 2, "correct": 1, "rate": 0.5, "abstain_x_report": 1}


def test_the_harness_marginal_table_binds_the_gates_one_declaration() -> None:
    """`M-7`: the harness records the table the gate's verdict was computed from — the same
    function, not a re-spelling."""
    paired = _paired([("a", True, True, False), ("b", True, False, False),
                      ("c", False, None, True)])
    assert P3.marginal_commits(paired) == GATE.marginal_commits(paired).as_record()


def test_marginal_commits_rate_is_none_when_nothing_is_marginal() -> None:
    assert P3.marginal_commits(_paired([("q1", True, True, True)]))["rate"] is None


def test_run_differential_meta_carries_regimes_and_the_marginal_table(tmp_path: Path) -> None:
    rows, h2q, baseline_rows = _p3b_fixture()
    P3.run_differential(rows, variant="FULL", families=tuple(P3.LR.ALL_FAMILIES), h2q=h2q,
                        baseline_rows=baseline_rows, baseline_arm="deliberative",
                        posterior=_posterior(), pairing=_pairing(), pricing_u_bar=PRICING,
                        oracle_p=0.9, out=tmp_path, draws=400, seed=7, log=lambda _m: None)
    meta = json.loads((tmp_path / "a3_meta-FULL.json").read_text())
    assert meta["regimes"] == P3.regime_record(_pairing(), pricing_u_bar=PRICING,
                                               scoring_u_bar=_posterior().u_bar())
    assert meta["marginal_commits"] == {"n": 0, "correct": 0, "rate": None,
                                        "abstain_x_report": 0}
    assert meta["verdict"] in ("PASS", "FAIL"), "no marginal commit: the pairing cannot bite"


def _heldout(rows: list[tuple[str, bool, bool, bool]]
             ) -> tuple[list[P3.HeldoutTick], dict[str, str], list[dict]]:
    ticks, h2q, baseline = [], {}, []
    for qid, t_assert, t_correct, m_assert in rows:
        h = DEC.question_id(f"question {qid}?")
        ticks.append(P3.HeldoutTick(question_id=h, leader_credence=0.95, p1=0.97,
                                    y=1 if t_correct else 0, respond=t_assert))
        h2q[h] = qid
        baseline.append({"question_id": qid, "answerable": True, "asserted": m_assert,
                         "asserted_correct": m_assert, "bucket": "x"})
    return ticks, h2q, baseline


def test_run_differential_logs_the_pairing_at_the_measured_marginal_rate(tmp_path: Path
                                                                          ) -> None:
    # three marginal commits right, one wrong → 0.75, inside [0.6667, 0.8559]: the r49 shape
    rows, h2q, baseline = _heldout([("q1", True, True, False), ("q2", True, True, False),
                                    ("q3", True, True, False), ("q4", True, False, False)])
    lines: list[str] = []
    P3.run_differential(rows, variant="FULL", families=tuple(P3.LR.ALL_FAMILIES), h2q=h2q,
                        baseline_rows=baseline, baseline_arm="deliberative",
                        posterior=_posterior(), pairing=_pairing(), pricing_u_bar=PRICING,
                        oracle_p=0.9, out=tmp_path, draws=400, seed=7, log=lines.append)
    text = "\n".join(lines)
    assert "pairing-sensitive" in text and "0.750" in text
    meta = json.loads((tmp_path / "a3_meta-FULL.json").read_text())
    assert meta["marginal_commits"]["rate"] == 0.75
    # the honest verdict (`M-34`): a straddling reach is INCONCLUSIVE in the record, the log
    # and the published report — never a PASS/FAIL that the pairing decided
    assert meta["verdict"] == "INCONCLUSIVE"
    assert "verdict INCONCLUSIVE" in text
    assert "## Verdict: **INCONCLUSIVE**" in (tmp_path / "a3_gate-FULL.md").read_text()


def test_run_differential_says_so_when_no_commit_is_marginal(tmp_path: Path) -> None:
    rows, h2q, baseline_rows = _p3b_fixture()       # both arms assert on the one row
    lines: list[str] = []
    P3.run_differential(rows, variant="FULL", families=tuple(P3.LR.ALL_FAMILIES), h2q=h2q,
                        baseline_rows=baseline_rows, baseline_arm="deliberative",
                        posterior=_posterior(), pairing=_pairing(), pricing_u_bar=PRICING,
                        oracle_p=0.9, out=tmp_path, draws=400, seed=7, log=lines.append)
    text = "\n".join(lines)
    assert "no marginal commits" in text and "pairing-sensitive" not in text
