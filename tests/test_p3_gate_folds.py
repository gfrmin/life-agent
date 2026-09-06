"""r51b (2c) — `p3_gate.py`: k-fold held-out probing, the declared Ū source, quantile cells.

`probe_heldout` had no test (the engine probe was "a scripted system step"); its seam is the
module attribute `P3.MembraneClient`, replaced here by a scripted transport whose decide reply
encodes exactly how many evidence ticks were folded before it (`p1 = n_seen / 100`) — so a row's
`p1` says which ticks trained the engine that produced it, and K = n must reproduce today's
grouped-LOO rows byte-for-byte (r51b pre-registration X3a).
"""
from __future__ import annotations

import sys
from typing import ClassVar

import pytest

sys.path.insert(0, "scripts")

import membrane.p3_gate as P3

from life_agent.core import gate as GATE
from life_agent.membrane import world as W

U_BAR = {"u_correct": 1.0, "u_wrong": -5.94, "u_abstain": 0.0, "u_hedged": 0.3,
         "u_wrong_scoped": -0.5, "lambda_int": 0.1, "lambda_usd": 0.0}
FAMS = ("leader-credence", "p-none")


def _summary(leader: float | None = 0.9) -> W.DecideSummary:
    return W.DecideSummary(n_candidates=1, leader_credence=leader, p_none=0.05, n_obs=1,
                           era_split=False, owner_scoped=False, grow_pass=False)


def _keyed(qid: str, *, y: int = 1, leader: float | None = 0.9) -> P3.KeyedTick:
    return P3.KeyedTick(qid, _summary(leader), y)


class _Spawn:
    """One scripted engine: handshake ok; every evidence tick counted; a decide tick answers
    `p1 = n_seen / 100`. Records every request in order."""

    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.n_seen = 0
        self.down = False

    def request(self, obj: dict) -> dict:
        self.sent.append(obj)
        if "membrane" in obj:
            return {"ok": True}
        tick = obj["tick"]
        if set(tick) == {"features", "menu"}:       # the probe's decide tick, exactly
            return {"p1": self.n_seen / 100}
        self.n_seen += 1                            # an evidence tick (carries the label)
        return {}

    def shutdown(self) -> None:
        self.down = True


class _FakeEngine:
    spawns: ClassVar[list[_Spawn]] = []

    @classmethod
    def spawn(cls, argv: list[str], *, log: object, read_timeout_s: float) -> _Spawn:
        s = _Spawn()
        cls.spawns.append(s)
        return s


@pytest.fixture
def engine(monkeypatch: pytest.MonkeyPatch) -> type[_FakeEngine]:
    _FakeEngine.spawns = []
    monkeypatch.setattr(P3, "MembraneClient", _FakeEngine)
    return _FakeEngine


def _evidence(spawn: _Spawn) -> list[dict]:
    return [o for o in spawn.sent if "tick" in o and set(o["tick"]) != {"features", "menu"}]


# --- fold assignment --------------------------------------------------------------------------


def test_assign_folds_is_balanced_deterministic_and_order_independent() -> None:
    ids = [f"q{i:02d}" for i in range(23)]
    a = P3.assign_folds(ids, 5)
    b = P3.assign_folds(list(reversed(ids)), 5)
    assert a == b                                    # insertion order is irrelevant
    sizes = sorted(list(a.values()).count(f) for f in range(5))
    assert sizes == [4, 4, 5, 5, 5]                  # differ by at most one
    assert a == {q: i % 5 for i, q in enumerate(sorted(ids))}   # sorted-rank round-robin


def test_fold_order_follows_first_appearance() -> None:
    # inserted C, A, B; sorted-rank folds over k = 3 give A:0, B:1, C:2 — the spawn order is
    # the order the folds FIRST APPEAR in the keyed replay, so K = n is today's loop exactly
    groups = {"q-c": [], "q-a": [], "q-b": []}
    fold_of = P3.assign_folds(list(groups), 3)
    assert fold_of == {"q-a": 0, "q-b": 1, "q-c": 2}
    assert P3.fold_order(groups, fold_of) == [2, 0, 1]


def test_folds_for_defaults_to_loo_and_refuses_out_of_range() -> None:
    assert P3.folds_for(7, None) == 7
    assert P3.folds_for(7, 7) == 7
    assert P3.folds_for(7, 2) == 2
    for bad in (1, 8, 0, -3):
        with pytest.raises(ValueError):
            P3.folds_for(7, bad)


# --- the probe --------------------------------------------------------------------------------


def test_probe_heldout_k_eq_n_is_byte_identical_to_loo(engine: type[_FakeEngine]) -> None:
    # insertion order deliberately != sorted order; q-b carries two ticks
    keyed = [_keyed("q-c"), _keyed("q-a", y=0), _keyed("q-b"), _keyed("q-b", y=0)]
    n_total = len(keyed)
    loo = P3.probe_heldout(keyed, U_BAR, "engine", FAMS)              # folds unset → LOO
    n_loo = len(engine.spawns)
    engine.spawns = []
    kn = P3.probe_heldout(keyed, U_BAR, "engine", FAMS, folds=3)      # K = n
    assert loo == kn
    assert n_loo == len(engine.spawns) == 3                            # one spawn per question
    # p1 encodes the fold: every OTHER question's ticks, in keyed order
    assert [(r.question_id, r.p1) for r in loo] == [
        ("q-c", (n_total - 1) / 100), ("q-a", (n_total - 1) / 100),
        ("q-b", (n_total - 2) / 100), ("q-b", (n_total - 2) / 100)]
    assert [r.y for r in loo] == [1, 0, 1, 0]
    assert all(s.down for s in engine.spawns)


def test_probe_heldout_k_fold_trains_on_other_folds_only_and_spawns_once_per_fold(
        engine: type[_FakeEngine]) -> None:
    import membrane.lattice_replay as LR

    keyed = [_keyed("q-c"), _keyed("q-a"), _keyed("q-d"), _keyed("q-b")]
    rows = P3.probe_heldout(keyed, U_BAR, "engine", FAMS, folds=2)
    # sorted-rank: a:0 b:1 c:0 d:1 — fold 0 appears first (q-c), then fold 1 (q-d)
    assert len(engine.spawns) == 2
    assert [r.question_id for r in rows] == ["q-c", "q-a", "q-d", "q-b"]
    assert [r.p1 for r in rows] == [0.02, 0.02, 0.02, 0.02]
    train0 = [t for t in keyed if t.question_id in ("q-d", "q-b")]
    assert _evidence(engine.spawns[0]) == [
        LR.evidence_tick_for(t.summary, float(i), FAMS, t.y) for i, t in enumerate(train0)]
    train1 = [t for t in keyed if t.question_id in ("q-c", "q-a")]
    assert _evidence(engine.spawns[1]) == [
        LR.evidence_tick_for(t.summary, float(i), FAMS, t.y) for i, t in enumerate(train1)]


def test_probe_heldout_skips_leaderless_questions_and_empty_folds(
        engine: type[_FakeEngine]) -> None:
    keyed = [_keyed("q-a"), _keyed("q-b", leader=None), _keyed("q-c")]
    rows = P3.probe_heldout(keyed, U_BAR, "engine", FAMS, folds=3)
    assert [r.question_id for r in rows] == ["q-a", "q-c"]
    assert len(engine.spawns) == 2                                     # q-b's fold spawns nothing
    assert [r.p1 for r in rows] == [0.02, 0.02]                        # q-b's tick still trains


# --- the declared Ū source --------------------------------------------------------------------


def test_cli_defaults_are_loo_and_boot() -> None:
    args = P3.build_parser().parse_args([])
    assert args.folds is None
    assert args.u_bar_source == "boot"
    assert P3.U_BAR_SOURCES == ("boot", "current")


def _boom() -> None:
    raise AssertionError("must not be called")


def test_resolve_u_bar_boot_refuses_without_a_boot_row() -> None:
    assert P3.resolve_u_bar("boot", override_json=None, boot=lambda: None, current=_boom) is None
    r = P3.resolve_u_bar("boot", override_json=None, boot=lambda: U_BAR, current=_boom)
    assert r is not None
    assert (r.u_bar, r.policy, r.source, r.fold_version) == (
        U_BAR, "all-to-date@boot", "boot", None)


def test_resolve_u_bar_current_reads_the_live_fold_and_names_it() -> None:
    r = P3.resolve_u_bar("current", override_json=None, boot=_boom,
                         current=lambda: (U_BAR, "fv-123", "all-to-date"))
    assert r is not None
    assert (r.u_bar, r.policy, r.source, r.fold_version) == (
        U_BAR, "all-to-date@current", "current", "fv-123")


def test_resolve_u_bar_override_is_reproduction_only() -> None:
    r = P3.resolve_u_bar("current", override_json='{"u_correct": 1, "u_wrong": -9}',
                         boot=_boom, current=_boom)
    assert r is not None
    assert (r.u_bar, r.policy, r.source) == ({"u_correct": 1.0, "u_wrong": -9.0},
                                            "Ū-override", "override")


def test_regime_record_names_the_pricing_source_and_fold_version() -> None:
    reading = P3.UBarReading(U_BAR, "all-to-date@current", "current", "fv-123")
    pairing = GATE.regime_pairing(pricing_u_bar=U_BAR, pricing_policy=reading.policy,
                                  scoring_u_bar=U_BAR, scoring_policy="frozen-elicitations")
    rec = P3.regime_record(pairing, pricing=reading, scoring_u_bar=U_BAR)
    assert rec["pricing"]["policy"] == "all-to-date@current"
    assert rec["pricing"]["source"] == "current"
    assert rec["pricing"]["fold_version"] == "fv-123"
    assert rec["pricing"]["u_bar"] == {k: float(v) for k, v in U_BAR.items()}


def test_rendered_pairing_names_the_u_bar_source() -> None:
    reading = P3.UBarReading(U_BAR, "all-to-date@boot", "boot", None)
    pairing = GATE.regime_pairing(pricing_u_bar=U_BAR, pricing_policy=reading.policy,
                                  scoring_u_bar={**U_BAR, "u_wrong": -9.0},
                                  scoring_policy="frozen-elicitations")
    assert "all-to-date@boot" in GATE.render_regime_pairing(pairing, reach_rate=None)


def test_regimes_that_currently_coincide_are_still_declared_divergent() -> None:
    # a reaction-free KB: the live fold equals the elicitation fold numerically, the labels
    # still differ → DIVERGENT by name, never straddled, never INCONCLUSIVE (r51 Scope)
    pairing = GATE.regime_pairing(pricing_u_bar=U_BAR, pricing_policy="all-to-date@current",
                                  scoring_u_bar=dict(U_BAR), scoring_policy="frozen-elicitations")
    assert pairing.divergent
    assert pairing.pricing_break_even == pairing.scoring_break_even
    for reach in (0.0, pairing.pricing_break_even, 0.5, 1.0):
        assert not pairing.straddles(reach)


# --- quantile cells + calibration summary ---------------------------------------------------


def _rows(rates: list[float] = [0.1, 0.3, 0.5, 0.7, 0.9], *, per: int = 20,  # noqa: B006
          p1: float = 0.86) -> list[P3.HeldoutTick]:
    # leader credence rises with the index; each block of `per` rows realises its own rate
    # exactly; p1 is flat — the pooled shape, built by hand
    out = []
    n = per * len(rates)
    for i in range(n):
        leader = 0.5 + 0.5 * i / (n - 1)
        rate = rates[i // per]
        out.append(P3.HeldoutTick(f"q{i:03d}", leader, p1, int((i % per) < round(rate * per)),
                                  respond=True))
    return out


def test_quantile_cells_are_populated_and_edges_published_for_the_named_key() -> None:
    rows = _rows()
    q5 = P3.quantile_cells(rows, "leader_credence", k=5)
    assert [c.n for c in q5] == [20] * 5
    assert all(c.lo <= c.hi for c in q5) and q5[0].lo == 0.5 and q5[-1].hi == 1.0
    assert [c.name for c in q5] == ["q1", "q2", "q3", "q4", "q5"]
    d10 = P3.quantile_cells(rows, "p1", k=10)
    assert [c.n for c in d10] == [10] * 10
    assert all(c.lo == c.hi == 0.86 for c in d10)     # a flat key still yields ten cells


def test_ece_is_zero_when_p1_equals_realised_and_positive_otherwise() -> None:
    rows = _rows([0.7, 0.7, 0.7, 0.7], per=10, p1=0.7)
    cells = P3.quantile_cells(rows, "p1", k=4)
    assert P3.calibration_summary(cells)["ece"] == pytest.approx(0.0)
    off = _rows([0.7, 0.7, 0.7, 0.7], per=10, p1=0.9)
    assert P3.calibration_summary(P3.quantile_cells(off, "p1", k=4))["ece"] == pytest.approx(0.2)


def test_spearman_is_one_on_a_monotone_gradient_and_near_zero_on_shuffled_noise() -> None:
    up = P3.calibration_summary(P3.quantile_cells(_rows(), "leader_credence", k=5))
    assert up["spearman"] == pytest.approx(1.0)
    # a zigzag of realised rates across the five cells: rank correlation -0.3, under the guard
    zig = _rows([0.5, 0.9, 0.3, 0.8, 0.4])
    rho = P3.calibration_summary(P3.quantile_cells(zig, "leader_credence", k=5))["spearman"]
    assert rho == pytest.approx(-0.3)


def test_fixed_buckets_unchanged_on_owner_default_path() -> None:
    # the owner-KB reader sees the SAME `price_at_u_bar` record it saw in r49/r50: the new
    # tables ride beside it in main, never inside it
    rows = _rows(per=10)
    rec = P3.price_at_u_bar(rows, U_BAR, oracle_p=0.9)
    assert set(rec) == {"n", "policy_eu_per_q", "respond_all_eu_per_q", "p1_spread",
                        "n_respond", "buckets"}
    assert [b["bucket"] for b in rec["buckets"]] == ["50-70", "70-80", "80-90", "ge90"]


def test_rank_tables_cut_the_primary_on_leader_credence_quintiles_and_the_reliability_on_p1_deciles(
        ) -> None:
    # the record main writes: the PRIMARY read is cut on the FEATURE (five cells), the
    # reliability diagram on p1 (ten) — never the other way round (r51 Cells)
    tables = P3.rank_tables(_rows())
    assert set(tables) == {"cells_leader_credence", "summary_leader_credence", "cells_p1",
                           "summary_p1"}
    assert [c["key"] for c in tables["cells_leader_credence"]] == ["leader_credence"] * 5
    assert [c["key"] for c in tables["cells_p1"]] == ["p1"] * 10
    assert tables["summary_leader_credence"]["spearman"] == pytest.approx(1.0)
    assert tables["cells_leader_credence"][0]["lo"] == 0.5


def test_write_heldout_rows_is_variant_suffixed_and_round_trips(tmp_path) -> None:
    # X7 needs the per-tick (p1, y) the run probed; the harness now persists them beside
    # a1_a2.json, one file per variant, and reads them back as the same HeldoutTick rows
    rows = [P3.HeldoutTick("q1", 0.9, 0.87, 1, True), P3.HeldoutTick("q2", None, None, 0, False)]
    path = P3.write_heldout_rows(tmp_path, "FULL", rows)
    assert path == tmp_path / "heldout-FULL.jsonl"
    assert P3.read_heldout_rows(path) == rows
    assert P3.write_heldout_rows(tmp_path, "leader-credence+p-none", rows).name == \
        "heldout-leader-credence+p-none.jsonl"


def test_commit_bar_for_is_the_restricted_argmax_flip_not_the_break_even() -> None:
    # a cheap ask holds the commit bar above the break-even; an expensive one lets them meet
    cheap = {**U_BAR, "lambda_int": 0.1}
    dear = {**U_BAR, "lambda_int": 5.0}
    assert P3.commit_bar_for(dear) == pytest.approx(GATE.break_even(dear), abs=0.001)
    assert P3.commit_bar_for(cheap) > GATE.break_even(cheap) + 0.05
    assert P3.commit_bar_for({**U_BAR, "u_wrong": -1e9}) is None or \
        P3.commit_bar_for({**U_BAR, "u_wrong": -1e9}) >= 0.999
