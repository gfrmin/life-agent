"""Component 1 of the aggregate family (life_agent.core.aggregate) — design §5/§9, hermetic.

The r19 pre-registration's t1-t10. No model, no engine: the wire choreography is verified
by the local :class:`ConjugateBrain` oracle (the ``test_narrative.py`` convention, extended
with the ``mu``-centred variance functional the recall read uses).

Run: uv run --project . python -m pytest tests/test_aggregate.py
"""
from __future__ import annotations

import hashlib
import math
from datetime import date
from pathlib import Path

import pytest

from life_agent.core.aggregate import (
    _RECALL_PRIOR,
    UNREADABLE,
    Generator,
    PairCovariates,
    RegistryError,
    Scope,
    expected_slots,
    load_registry,
    recall_posterior,
    same_entity_posterior,
)

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
