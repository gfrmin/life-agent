"""Component 1 of the aggregate family (life_agent.core.aggregate) — design §5/§9, hermetic.

The r19 pre-registration's t1-t10. No model, no engine: the wire choreography is verified
by the local :class:`ConjugateBrain` oracle (the ``test_narrative.py`` convention, extended
with the ``mu``-centred variance functional the recall read uses).

Run: uv run --project . python -m pytest tests/test_aggregate.py
"""
from __future__ import annotations

import hashlib
import json
import math
import statistics
from datetime import date
from pathlib import Path
from typing import Any

import duckdb
import pytest

from life_agent.core import gate as GATE
from life_agent.core.aggregate import (
    _RECALL_PRIOR,
    AMOUNTS_PRODUCERS,
    UNREADABLE,
    Addend,
    Generator,
    PairCovariates,
    RecallPosterior,
    RegistryError,
    Scope,
    compose_total,
    expected_slots,
    load_registry,
    pair_covariates,
    project_amounts,
    recall_posterior,
    same_entity_posterior,
)
from pkm.cache import write_artifact
from pkm.catalogue import open_catalogue, run_migrations
from pkm.producer import ProducerResult
from pkm.transforms.extract_amounts import ExtractAmountsProducer

FIXTURE = Path(__file__).parent / "fixtures" / "generators-synthetic.yaml"


class ConjugateBrain:
    """Test-oracle brain double: independent Beta-Bernoulli conjugacy + moment reads.
    Verifies the fold CHOREOGRAPHY (create → one bernoulli per expected slot → mean +
    centered_power variance → destroy) hermetically; the real engine is covered by its
    own skin tests."""

    def __init__(self) -> None:
        self._states: dict[str, tuple[float, float]] = {}
        self._n = 0
        self.conditions = 0
        self.destroyed: list[str] = []

    def create_state(self, spec: dict) -> str:
        assert spec["type"] == "beta", spec
        self._n += 1
        sid = f"s_{self._n}"
        self._states[sid] = (float(spec["alpha"]), float(spec["beta"]))
        return sid

    def destroy_state(self, sid: str) -> None:
        self._states.pop(sid, None)
        self.destroyed.append(sid)

    def condition(self, sid: str, *, kernel: dict, observation: float) -> float:
        assert kernel == {"type": "bernoulli"}, kernel
        self.conditions += 1
        a, b = self._states[sid]
        self._states[sid] = (a + observation, b + (1.0 - observation))
        return 0.0

    def mean(self, sid: str) -> float:
        a, b = self._states[sid]
        return a / (a + b)

    def expect(self, sid: str, *, function: dict) -> float:
        assert function["type"] == "centered_power" and function["n"] == 2, function
        a, b = self._states[sid]
        e1 = a / (a + b)
        e2 = a * (a + 1.0) / ((a + b) * (a + b + 1.0))
        mu = float(function.get("mu", 0.0))
        return e2 - 2.0 * mu * e1 + mu * mu


class RaisingBrain(ConjugateBrain):
    """The oracle with a poisoned mean read — proves the state dies in the finally."""

    def mean(self, sid: str) -> float:
        raise RuntimeError("wire read refused")


def _gen(gid: str = "g-pay", *, cadence: str = "monthly", kind: str = "income",
         active_from: date = date(2025, 1, 1), active_to: date | None = None,
         scope_keys: frozenset[str] = frozenset({"income"}),
         evidence: tuple[str, ...] = ("cite.txt",)) -> Generator:
    return Generator(generator_id=gid, kind=kind, cadence=cadence,
                     active_from=active_from, active_to=active_to,
                     scope_keys=scope_keys, evidence=evidence)


YEAR = Scope(key="income", start=date(2025, 1, 1), end=date(2025, 12, 31))


def _beta_moments(a: float, b: float) -> tuple[float, float]:
    m = a / (a + b)
    return m, a * b / ((a + b) ** 2 * (a + b + 1.0))


# --- t1: misses are observations -----------------------------------------------------

def test_misses_are_observations() -> None:
    brain = ConjugateBrain()
    hits = frozenset(f"2025-{m:02d}" for m in range(1, 10))  # 9 of 12 months
    post = recall_posterior(brain, [_gen()], YEAR, {"g-pay": hits})
    a0, b0 = _RECALL_PRIOR
    assert brain.conditions == 12  # every expected slot folds, misses included
    assert post.n_slots == 12 and post.n_hits == 9 and post.estimated
    mean, var = _beta_moments(a0 + 9.0, b0 + 3.0)
    assert post.mean == pytest.approx(mean)
    assert post.variance == pytest.approx(var)
    hits_only_mean = (a0 + 9.0) / (a0 + 9.0 + b0)  # the fold-hits-only fallacy
    assert post.mean < hits_only_mean
    assert set(post.missed) == {f"g-pay:2025-{m:02d}" for m in (10, 11, 12)}


# --- t2: the prior is overturned by one monthly scope --------------------------------

def test_prior_overturned_by_one_monthly_scope() -> None:
    a0, b0 = _RECALL_PRIOR
    assert a0 / (a0 + b0) > 0.5  # weakly optimistic, not uniform
    assert a0 + b0 < 12.0  # weak enough that one monthly scope dominates
    brain = ConjugateBrain()
    hits = frozenset(f"2025-{m:02d}" for m in range(1, 4))  # 3 of 12
    post = recall_posterior(brain, [_gen()], YEAR, {"g-pay": hits})
    assert post.mean < 0.5  # the data overturned the optimistic prior


# --- t3: no covering generator ⇒ prior-dominated, declared ---------------------------

def test_no_covering_generator_prior_dominated() -> None:
    brain = ConjugateBrain()
    post = recall_posterior(brain, [_gen()], Scope(key="travel", start=date(2025, 1, 1),
                                                   end=date(2025, 12, 31)), {})
    assert not post.estimated
    assert brain.conditions == 0
    mean, var = _beta_moments(*_RECALL_PRIOR)
    assert post.mean == pytest.approx(mean)
    assert post.variance == pytest.approx(var)
    assert post.expected == () and post.missed == () and post.n_slots == 0
    assert post.prior == _RECALL_PRIOR


# --- t4: extra hits are named, never folded ------------------------------------------

def test_extra_hit_named_not_folded() -> None:
    brain = ConjugateBrain()
    hits = frozenset({"2025-01", "2024-12"})  # 2024-12 precedes the scope
    post = recall_posterior(brain, [_gen()], YEAR, {"g-pay": hits})
    assert brain.conditions == 12  # census size unchanged by the stray hit
    assert post.n_hits == 1
    assert post.extra_hits == ("g-pay:2024-12",)


# --- t5: calendar enumeration + active-window clipping -------------------------------

def test_expected_slots_calendars() -> None:
    scope = Scope(key="income", start=date(2025, 2, 15), end=date(2025, 8, 10))
    assert expected_slots(_gen(), scope) == tuple(
        f"2025-{m:02d}" for m in range(2, 9))
    assert expected_slots(_gen(cadence="quarterly"), scope) == (
        "2025-Q1", "2025-Q2", "2025-Q3")
    assert expected_slots(_gen(cadence="annual"), scope) == ("2025",)
    clipped = _gen(active_from=date(2025, 5, 1), active_to=date(2025, 6, 30))
    assert expected_slots(clipped, scope) == ("2025-05", "2025-06")
    dead = _gen(active_from=date(2026, 1, 1))
    assert expected_slots(dead, scope) == ()


# --- t6: the synthetic fixture loads; content hash pins the bytes --------------------

def test_registry_loads_fixture_and_hashes(tmp_path: Path) -> None:
    root = tmp_path / "kb"
    root.mkdir()
    (root / "notes-series").mkdir()
    (root / "statements-series").mkdir()
    loaded = load_registry(FIXTURE, evidence_root=root)
    assert [g.generator_id for g in loaded.entries] == ["gen-notes", "gen-statements"]
    assert loaded.content_hash == hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    edited = tmp_path / "edited.yaml"
    edited.write_bytes(FIXTURE.read_bytes() + b"\n")
    assert load_registry(edited, evidence_root=root).content_hash != loaded.content_hash


# --- t7: unknown cadence is loud -----------------------------------------------------

def test_registry_unknown_cadence_loud(tmp_path: Path) -> None:
    p = tmp_path / "r.yaml"
    p.write_text("generators:\n"
                 "  - generator_id: g-bad\n    kind: income\n    cadence: weekly\n"
                 "    active_from: 2025-01-01\n    active_to: null\n"
                 "    scope_keys: [income]\n    evidence: [cite.txt]\n")
    (tmp_path / "cite.txt").touch()
    with pytest.raises(RegistryError, match="g-bad"):
        load_registry(p, evidence_root=tmp_path)


# --- t8: an unresolvable evidence citation is loud -----------------------------------

def test_registry_unresolvable_evidence_loud(tmp_path: Path) -> None:
    p = tmp_path / "r.yaml"
    p.write_text("generators:\n"
                 "  - generator_id: g-uncited\n    kind: income\n    cadence: monthly\n"
                 "    active_from: 2025-01-01\n    active_to: null\n"
                 "    scope_keys: [income]\n    evidence: [absent.txt]\n")
    with pytest.raises(RegistryError, match="g-uncited"):
        load_registry(p, evidence_root=tmp_path)
    empty = tmp_path / "e.yaml"
    empty.write_text("generators:\n"
                     "  - generator_id: g-empty\n    kind: income\n    cadence: monthly\n"
                     "    active_from: 2025-01-01\n    active_to: null\n"
                     "    scope_keys: [income]\n    evidence: []\n")
    with pytest.raises(RegistryError, match="g-empty"):  # uncited schedules never enter
        load_registry(empty, evidence_root=tmp_path)


# --- t9: scope-generic — a non-financial generator behaves identically ---------------

def test_non_financial_generator() -> None:
    brain = ConjugateBrain()
    notes = _gen("g-notes", kind="meeting-note", scope_keys=frozenset({"meetings"}))
    scope = Scope(key="meetings", start=date(2025, 1, 1), end=date(2025, 6, 30))
    post = recall_posterior(brain, [notes], scope,
                            {"g-notes": frozenset({"2025-01", "2025-02"})})
    assert post.estimated and post.n_slots == 6 and post.n_hits == 2
    a0, b0 = _RECALL_PRIOR
    assert post.mean == pytest.approx((a0 + 2.0) / (a0 + b0 + 6.0))


# --- t10: the wire state dies in the finally -----------------------------------------

def test_state_destroyed_on_success_and_on_read_error() -> None:
    brain = ConjugateBrain()
    recall_posterior(brain, [_gen()], YEAR, {"g-pay": frozenset({"2025-01"})})
    assert brain.destroyed and not brain._states
    raising = RaisingBrain()
    with pytest.raises(RuntimeError, match="wire read refused"):
        recall_posterior(raising, [_gen()], YEAR, {"g-pay": frozenset({"2025-01"})})
    assert raising.destroyed and not raising._states


# ====================================================================================
# CP-C (r20): component 3 — dedup-as-inference (design §7), the pairwise same-entity
# hypothesis comparison. Oracle: TabularBrain — an independent categorical +
# tabular_log_density reimplementation, not the module's own math.



class TabularBrain:
    """Categorical-state oracle for the CP-C wire shape: log-weight accumulation from
    declared tabular log-density kernels, softmax on ``weights``."""

    def __init__(self) -> None:
        self._states: dict[str, tuple[list[float], list[float]]] = {}
        self._n = 0
        self.conditions = 0
        self.destroyed: list[str] = []

    def create_state(self, spec: dict) -> str:
        assert spec["type"] == "categorical", spec
        assert spec["space"]["type"] == "finite", spec
        vals = [float(v) for v in spec["space"]["values"]]
        lw = [float(w) for w in spec.get("log_weights") or [0.0] * len(vals)]
        self._n += 1
        sid = f"c_{self._n}"
        self._states[sid] = (vals, lw)
        return sid

    def destroy_state(self, sid: str) -> None:
        self._states.pop(sid, None)
        self.destroyed.append(sid)

    def condition(self, sid: str, *, kernel: dict, observation: float) -> float:
        assert kernel["type"] == "tabular_log_density", kernel
        vals, lw = self._states[sid]
        assert [float(v) for v in kernel["source_vals"]] == vals
        ti = [float(t) for t in kernel["target_vals"]].index(float(observation))
        self._states[sid] = (vals, [w + float(kernel["densities"][si][ti])
                                    for si, w in enumerate(lw)])
        self.conditions += 1
        return 0.0

    def weights(self, sid: str) -> list[float]:
        _, lw = self._states[sid]
        mx = max(lw)
        es = [math.exp(w - mx) for w in lw]
        z = sum(es)
        return [e / z for e in es]


class RaisingTabularBrain(TabularBrain):
    """Poisoned weights read — proves the categorical state dies in the finally."""

    def weights(self, sid: str) -> list[float]:
        raise RuntimeError("wire read refused")


REAL_SHAPE = PairCovariates(period="same", amount=UNREADABLE, entity="same", kind="same")
ADJACENT_SHAPE = PairCovariates(period="adjacent", amount=UNREADABLE, entity="same",
                                kind="same")


# --- c-t1: choreography — one condition per readable covariate, destroy both paths ---

def test_pair_choreography_and_destroy() -> None:
    brain = TabularBrain()
    post = same_entity_posterior(brain, REAL_SHAPE)
    assert brain.conditions == 3  # period, entity, kind; amount unreadable
    assert brain.destroyed and not brain._states
    assert post.conditioned == ("period", "entity", "kind")
    raising = RaisingTabularBrain()
    with pytest.raises(RuntimeError, match="wire read refused"):
        same_entity_posterior(raising, REAL_SHAPE)
    assert raising.destroyed and not raising._states


# --- c-t2: the real-pair shape reads one entity -------------------------------------

def test_real_pair_shape_reads_one_entity() -> None:
    post = same_entity_posterior(TabularBrain(), REAL_SHAPE)
    l_one = 0.98 * 0.97 * 0.99
    l_two = 0.15 * 0.70 * 0.80
    assert post.p_one == pytest.approx(l_one / (l_one + l_two))
    assert post.p_one > 0.5


# --- c-t3: the adjacent-period control shape reads two entities ---------------------

def test_adjacent_period_shape_reads_two() -> None:
    post = same_entity_posterior(TabularBrain(), ADJACENT_SHAPE)
    l_one = 0.01 * 0.97 * 0.99
    l_two = 0.45 * 0.70 * 0.80
    assert post.p_one == pytest.approx(l_one / (l_one + l_two))
    assert post.p_one < 0.5


# --- c-t4: unreadable covariates are skipped and named ------------------------------

def test_unreadable_covariate_skipped_named() -> None:
    post = same_entity_posterior(TabularBrain(), REAL_SHAPE)
    assert post.skipped == ("amount",)


# --- c-t5: the posterior is a distribution ------------------------------------------

def test_pair_posterior_sums_to_one() -> None:
    readable = PairCovariates(period="adjacent", amount="different", entity="same",
                              kind="same")
    post = same_entity_posterior(TabularBrain(), readable)
    assert post.p_one + post.p_two == pytest.approx(1.0)
    assert post.skipped == ()
    assert post.conditioned == ("period", "amount", "entity", "kind")


# --- c-t6: an unknown bucket is loud (closed vocabularies) --------------------------

def test_unknown_bucket_loud() -> None:
    bad = PairCovariates(period="overlapping", amount="equal", entity="same",
                         kind="same")
    with pytest.raises(ValueError, match="overlapping"):
        same_entity_posterior(TabularBrain(), bad)


# ====================================================================================
# CP-D phase 2 (r21): component 2 — the missing-mass composition (design §6, the
# prereg's frozen v0: refusals -> dedup -> branch -> interval). Deterministic host
# composition of recorded observations; the only wire consult is component 3 on the
# proposal pairs. compose_total returns one TotalPosterior per currency (mixtures are
# refused as subtotals, §4.3).



def _addend(**over: Any) -> Addend:
    base: dict[str, Any] = dict(
        doc_key="d1", kind="deposit", basis="monthly", as_of="2025-01-31",
        amount=100.0, currency="ILS", amount_raw="100.00", label_raw="Deposit",
        entity="fund-a", flagged=False)
    base.update(over)
    return Addend(**base)


def _series(months: list[int], amount: float = 100.0) -> list[Addend]:
    return [_addend(doc_key=f"d{m}", as_of=f"2025-{m:02d}-28", amount=amount + m)
            for m in months]


DEPOSIT_SCOPE = Scope(key="deposits", start=date(2025, 1, 1), end=date(2025, 9, 30))


def _recall(missed: tuple[str, ...] = (), estimated: bool = True) -> RecallPosterior:
    return RecallPosterior(mean=0.7, variance=0.01, estimated=estimated,
                           n_slots=9, n_hits=9 - len(missed), expected=(),
                           hit=(), missed=missed, extra_hits=(),
                           prior=_RECALL_PRIOR)


# --- the roll-up branch --------------------------------------------------------------

def test_rollup_at_scope_end_is_the_single_observation() -> None:
    rollup = _addend(doc_key="stmt", basis="other", as_of="2025-09-30",
                     amount=31937.0, amount_raw="31,937")
    months = _series([7, 8, 9])
    [tp] = compose_total(TabularBrain(), [rollup, *months], DEPOSIT_SCOPE,
                         target_kind="deposit", recall=_recall())
    assert (tp.point, tp.lo, tp.hi) == (31937.0, 31937.0, 31937.0)
    assert "roll-up" in tp.basis_note
    assert tp.k == 1


def test_competing_rollups_fall_back_to_the_series_named() -> None:
    r1 = _addend(doc_key="stmt", basis="other", as_of="2025-09-30", amount=31937.0)
    r2 = _addend(doc_key="stmt", basis="other", as_of="2025-09-30", amount=283886.0)
    months = _series([7, 8, 9])
    [tp] = compose_total(TabularBrain(), [r1, r2, *months], DEPOSIT_SCOPE,
                         target_kind="deposit", recall=_recall())
    assert tp.point == pytest.approx(sum(a.amount for a in months))
    assert "competing" in tp.basis_note
    assert tp.k == 3


# --- the same-doc issuer fold (the stated-total row) ---------------------------------

def test_same_doc_stated_total_is_the_issuer_fold() -> None:
    parts = [_addend(doc_key="cert", basis="point_in_time", as_of="2025-11-29",
                     amount=352094.25, kind="balance"),
             _addend(doc_key="cert", basis="point_in_time", as_of="2025-11-29",
                     amount=7785.11, kind="balance")]
    total = _addend(doc_key="cert", basis="point_in_time", as_of="2025-11-29",
                    amount=359879.36, kind="balance")
    scope = Scope(key="balances", start=date(2025, 11, 29), end=date(2025, 11, 29))
    [tp] = compose_total(TabularBrain(), [*parts, total], scope,
                         target_kind="balance", recall=_recall(estimated=False))
    assert tp.point == pytest.approx(359879.36)  # the issuer's own fold, once
    assert tp.k == 1
    assert "issuer" in tp.basis_note


# --- the series branch + imputation --------------------------------------------------

def test_series_imputes_named_missed_slots() -> None:
    months = _series([1, 2, 3, 4, 5, 6, 7, 8])  # amounts 101..108
    missed = ("g:2025-09",)
    [tp] = compose_total(TabularBrain(), months, DEPOSIT_SCOPE,
                         target_kind="deposit", recall=_recall(missed=missed))
    s = sum(a.amount for a in months)
    vals = sorted(a.amount for a in months)
    q = statistics.quantiles(vals, n=10)
    assert tp.imputed_slots == missed
    assert tp.point == pytest.approx(s + statistics.mean(vals))
    assert tp.lo == pytest.approx(s + q[0]) and tp.hi == pytest.approx(s + q[-1])
    assert "exchangeab" in tp.basis_note  # the disclosed assumption


def test_no_misses_degenerates_to_the_observed_sum() -> None:
    months = _series([7, 8, 9])
    [tp] = compose_total(TabularBrain(), months, DEPOSIT_SCOPE,
                         target_kind="deposit", recall=_recall())
    s = sum(a.amount for a in months)
    assert (tp.point, tp.lo, tp.hi) == (s, s, s)
    assert tp.imputed_slots == ()


def test_unmodelled_recall_never_imputes() -> None:
    months = _series([7, 8])
    [tp] = compose_total(TabularBrain(), months, DEPOSIT_SCOPE,
                         target_kind="deposit",
                         recall=_recall(missed=("g:2025-09",), estimated=False))
    s = sum(a.amount for a in months)
    assert (tp.point, tp.lo, tp.hi) == (s, s, s)
    assert tp.imputed_slots == () and tp.unmodelled_recall


# --- refusals ------------------------------------------------------------------------

def test_off_kind_addends_are_excluded_by_name() -> None:
    months = _series([7, 8])
    stray = _addend(doc_key="dx", kind="balance", amount=999999.0)
    [tp] = compose_total(TabularBrain(), [*months, stray], DEPOSIT_SCOPE,
                         target_kind="deposit", recall=_recall())
    assert tp.point == pytest.approx(sum(a.amount for a in months))
    assert ("dx", "balance") in tp.excluded_kind


def test_currency_mixture_refused_as_subtotals() -> None:
    ils = _series([7, 8])
    usd = [_addend(doc_key="du", as_of="2025-09-28", amount=50.0, currency="USD")]
    tps = compose_total(TabularBrain(), [*ils, *usd], DEPOSIT_SCOPE,
                        target_kind="deposit", recall=_recall())
    assert {t.currency for t in tps} == {"ILS", "USD"}
    assert len(tps) == 2


def test_coarser_leftover_basis_is_excluded_by_name() -> None:
    months = _series([7, 8, 9])
    q2 = _addend(doc_key="q2", basis="other", as_of="2025-06-30", amount=16107.0)
    [tp] = compose_total(TabularBrain(), [*months, q2], DEPOSIT_SCOPE,
                         target_kind="deposit", recall=_recall())
    assert tp.point == pytest.approx(sum(a.amount for a in months))
    assert ("q2", "other") in tp.excluded_basis


# --- component-3 integration (dedup on proposal pairs) -------------------------------

def test_equal_value_cross_doc_pair_contributes_once() -> None:
    a = _addend(doc_key="da", as_of="2025-07-31", amount=500.0, entity="fund-a")
    b = _addend(doc_key="db", as_of="2025-07-31", amount=500.0, entity="fund-a")
    [tp] = compose_total(TabularBrain(), [a, b], DEPOSIT_SCOPE,
                         target_kind="deposit", recall=_recall())
    assert tp.point == pytest.approx(500.0)  # one latent transaction, counted once
    assert tp.k == 1 and len(tp.dedup_resolutions) == 1


def test_adjacent_period_equal_value_pair_keeps_both() -> None:
    a = _addend(doc_key="da", as_of="2025-07-31", amount=500.0)
    b = _addend(doc_key="db", as_of="2025-08-31", amount=500.0)
    [tp] = compose_total(TabularBrain(), [a, b], DEPOSIT_SCOPE,
                         target_kind="deposit", recall=_recall())
    assert tp.point == pytest.approx(1000.0)  # two transactions (period discriminates)
    assert tp.k == 2 and tp.dedup_resolutions == ()


def test_pair_covariates_mapping() -> None:
    a = _addend(as_of="2025-07-31", entity=None)
    b = _addend(doc_key="d2", as_of="2025-08-31", entity=None)
    cov = pair_covariates(a, b)
    assert cov.period == "adjacent" and cov.amount == "equal"
    assert cov.entity == UNREADABLE and cov.kind == "same"
    far = _addend(doc_key="d3", as_of="2024-01-31")
    assert pair_covariates(a, far).period == "other"
    undated = _addend(doc_key="d4", as_of=None)
    assert pair_covariates(a, undated).period == UNREADABLE


# ====================================================================================
# CP-D phase 2: the read-side amounts projection — project_amounts mirrors
# temporal.project_dates (§18.10 currency, §18.11 demand log, never derives; the
# underived are NAMED with their pkm-derive remedy — the D2 coverage contract).

@pytest.fixture
def migrated_root(tmp_path: Path) -> Path:
    (tmp_path / "cache").mkdir()
    (tmp_path / "logs").mkdir()
    run_migrations(tmp_path)
    return tmp_path


def _write_art(root: Path, conn: duckdb.DuckDBPyConnection, *, key: str,
               input_hash: str, producer: str, content: bytes,
               lineage: list[dict[str, str]] | None = None) -> None:
    write_artifact(
        root, conn, cache_key=key, input_hash=input_hash,
        producer_name=producer, producer_version="1", producer_config={},
        result=ProducerResult(status="success", content=content,
                              content_type="application/json",
                              content_encoding="utf-8", error_message=None,
                              producer_metadata={}),
        lineage=lineage, cache_key_schema_version=1 if lineage is None else 3,
    )


def _amounts_content(items: list[dict[str, Any]], *, unreadable: bool = False,
                     majority_unlabelled: bool = False) -> bytes:
    return json.dumps({
        "format_version": 1, "currency_default": "ILS", "unreadable": unreadable,
        "majority_unlabelled": majority_unlabelled, "items": items,
    }).encode("utf-8")


def test_project_amounts_partitions_and_names(migrated_root: Path) -> None:
    a, b, c, d = "aa" * 32, "bb" * 32, "cc" * 32, "dd" * 32
    item = {"kind": "deposit", "basis": "monthly", "as_of": "2025-07-31",
            "amount": 500.0, "currency": "ILS", "amount_raw": "500.00",
            "label_raw": "Deposit", "entity": "fund-a"}
    with open_catalogue(migrated_root) as conn:
        for key, ih, producer in ((a, "11" * 32, "docling"), (b, "22" * 32, "docling"),
                                  (c, "33" * 32, "tesseract"), (d, "44" * 32, "email")):
            _write_art(migrated_root, conn, key=key, input_hash=ih,
                       producer=producer, content=b"src")
        _write_art(migrated_root, conn, key="a1" * 32, input_hash="55" * 32,
                   producer=ExtractAmountsProducer.name,
                   content=_amounts_content([item], majority_unlabelled=True),
                   lineage=[{"cache_key": a, "role": "source_text"}])
        _write_art(migrated_root, conn, key="b1" * 32, input_hash="66" * 32,
                   producer=ExtractAmountsProducer.name,
                   content=_amounts_content([], unreadable=True),
                   lineage=[{"cache_key": b, "role": "source_text"}])
        _write_art(migrated_root, conn, key="d1" * 32, input_hash="77" * 32,
                   producer=ExtractAmountsProducer.name,
                   content=_amounts_content([]),
                   lineage=[{"cache_key": d, "role": "source_text"}])
        hits = project_amounts(conn, migrated_root, [a, b, c, d])
    by_key = {h.artifact_cache_key: h for h in hits}
    assert by_key[a].state == "amounts"
    (ad,) = by_key[a].addends
    assert ad.doc_key == a and ad.amount == 500.0 and ad.flagged is True
    assert by_key[b].state == "unreadable" and by_key[b].addends == ()
    assert by_key[c].state == "underived"
    assert by_key[c].remedy == f"pkm derive extract_amounts_tesseract --input {c}"
    assert by_key[d].state == "empty"


# --- C2 (r22): the projection must find what the DEPLOYED producer actually writes ------
# The standing lesson, applied to a test: a census must read the deployed rule end-to-end
# and never re-implement the constant it prices. The fixtures above insert the producer
# name as a literal, so they cannot see a filter that names a producer which does not
# exist. These two read it off the producer class instead.

def test_amounts_producers_names_the_deployed_producer_class() -> None:
    """AMOUNTS_PRODUCERS filters `artifacts.producer_name`, which pkm writes as
    `producer.name` (transform_run: producer_name=producer.name). Every
    extract_amounts_*.yaml declaration maps to ONE class, so exactly one name can
    ever be recorded. Compare against `temporal.DOC_DATE_PRODUCERS`, which correctly
    lists class names for a transform with two classes."""
    assert set(AMOUNTS_PRODUCERS) == {ExtractAmountsProducer.name}, (
        "AMOUNTS_PRODUCERS names a producer that cannot exist: the projection filters "
        "producer_name (a CLASS name) with values from the DECLARATION namespace"
    )


def test_project_amounts_reads_the_name_the_producer_writes(migrated_root: Path) -> None:
    """End-to-end: an artifact recorded under the name pkm actually writes must project
    as `amounts`. Under the declaration-namespace filter it reads `underived` forever,
    and the printed remedy produces this very artifact - a closed loop."""
    src = "ee" * 32
    item = {"kind": "deposit", "basis": "monthly", "as_of": "2025-07-31",
            "amount": 500.0, "currency": "ILS", "amount_raw": "500.00",
            "label_raw": "Deposit", "entity": "fund-a"}
    with open_catalogue(migrated_root) as conn:
        _write_art(migrated_root, conn, key=src, input_hash="88" * 32,
                   producer="docling", content=b"src")
        _write_art(migrated_root, conn, key="e1" * 32, input_hash="99" * 32,
                   producer=ExtractAmountsProducer.name,
                   content=_amounts_content([item]),
                   lineage=[{"cache_key": src, "role": "source_text"}])
        (hit,) = project_amounts(conn, migrated_root, [src])
    assert hit.state == "amounts", (
        f"projection missed the deployed producer name "
        f"{ExtractAmountsProducer.name!r}; read {hit.state!r}"
    )
    (ad,) = hit.addends
    assert ad.amount == 500.0


# ====================================================================================
# CP-D phase 2: the second-stage router + the family body (ONE body — terminals and
# the bridge both call it). Router: own prompt/schema/cache key, cached via D.record,
# conservative default (aggregate only on a confident sum-shaped verdict with a kind).



class DualBrain(ConjugateBrain):
    """Beta (recall) + categorical (dedup) oracle — the body drives both."""

    def create_state(self, spec: dict) -> str:
        if spec["type"] == "categorical":
            self._n += 1
            sid = f"c_{self._n}"
            vals = [float(v) for v in spec["space"]["values"]]
            lw = [float(w) for w in spec.get("log_weights") or [0.0] * len(vals)]
            self._states[sid] = ("cat", vals, lw)  # type: ignore[assignment]
            return sid
        return super().create_state(spec)

    def condition(self, sid: str, *, kernel: dict, observation: float) -> float:
        st = self._states[sid]
        if isinstance(st, tuple) and st and st[0] == "cat":
            _, vals, lw = st
            ti = [float(t) for t in kernel["target_vals"]].index(float(observation))
            self._states[sid] = (  # type: ignore[assignment]
                "cat", vals,
                [w + float(kernel["densities"][si][ti]) for si, w in enumerate(lw)])
            self.conditions += 1
            return 0.0
        return super().condition(sid, kernel=kernel, observation=observation)

    def weights(self, sid: str) -> list[float]:
        _, _, lw = self._states[sid]  # type: ignore[misc]
        mx = max(lw)
        es = [math.exp(w - mx) for w in lw]
        return [e / sum(es) for e in es]


class _RouteClient:
    engine_version = "fake-1"

    def __init__(self, output: dict[str, Any]) -> None:
        self._output = output
        self.calls = 0

    def complete(self, prompt: str, schema: dict[str, Any]) -> Any:
        self.calls += 1
        from pkm.transform import ModelResponse
        return ModelResponse(raw_text=json.dumps(self._output), input_tokens=1,
                             output_tokens=1, latency_ms=1, cost_usd=0.001)
def test_winkler_sharp_covering_reads_near_one() -> None:
    x, excludes = GATE.realised_aggregate(31900.0, 31980.0, 31937.0)
    assert not excludes and x > 0.99


def test_winkler_width_pays_linearly() -> None:
    g = 1000.0
    x_wide, exc = GATE.realised_aggregate(0.0, 2.0 * g, g)  # width == 2|g| ⇒ x = 0
    assert not exc and x_wide == 0.0
    x_half, _ = GATE.realised_aggregate(500.0, 1500.0, g)   # width |g| ⇒ x = 0.5
    assert x_half == pytest.approx(0.5)


def test_winkler_miss_is_the_wrong_class_and_pays_distance() -> None:
    x, excludes = GATE.realised_aggregate(100.0, 200.0, 1000.0)
    assert excludes and x == 0.0
    # A near miss still fires the categorical class; its continuous score follows
    # the frozen arithmetic exactly: W = 9 + 10*1 = 19, x = 1 - 19/2000.
    x2, exc2 = GATE.realised_aggregate(990.0, 999.0, 1000.0)
    assert exc2 and x2 == pytest.approx(1.0 - 19.0 / 2000.0)


def test_winkler_rides_realised_utility() -> None:
    u = {"u_correct": 1.0, "u_wrong": -5.0, "u_abstain": 0.0, "u_hedged": 0.4,
         "u_wrong_scoped": -1.0, "lambda_int": 1.0, "lambda_usd": 0.0}
    sharp = GATE.RealisedResponse(action="report", correct=True, cost_usd=0.0, x=1.0)
    assert GATE.realised_utility(sharp, u, oracle_p=0.5) == pytest.approx(1.0)
    half = GATE.RealisedResponse(action="report", correct=True, cost_usd=0.0, x=0.5)
    assert GATE.realised_utility(half, u, oracle_p=0.5) == pytest.approx(-2.0)
    plain = GATE.RealisedResponse(action="report", correct=True, cost_usd=0.0)
    assert GATE.realised_utility(plain, u, oracle_p=0.5) == pytest.approx(1.0)
