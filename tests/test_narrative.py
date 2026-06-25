"""The narrative family (life_agent.core.narrative) — foundations §7, hermetic.

The conftest autouse fixture stubs ``narrative.narrative_answer`` for every OTHER
test; this file binds the real functions by name at import time, which the attribute
patch deliberately does not reach. No model, no brain: Ū is passed explicitly, the
outcomes/decisions logs are tmp files, §18.9 records land under ``migrated_root``.

Run: uv run --project . python -m pytest tests/test_narrative.py
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pytest

from life_agent.core import decisions as DEC
from life_agent.core import derivations as D
from life_agent.core import narrative as N
from life_agent.core import outcomes as O
from life_agent.core.narrative import (
    audit_cell,
    coverage_posterior,
    decide_claims,
    freshest_as_of,
    include_eu,
    narrative_answer,
    parse_claims,
    population_posteriors,
    render,
    scope_decay,
)

# The utility posterior mean used throughout — explicit, so threshold arithmetic in
# these tests is exact and independent of the live fold.
U = {"u_correct": 1.0, "u_abstain": 0.0, "u_wrong": -5.0, "u_hedged": 0.4,
     "lambda_int": 1.0, "kappa_att": 0.05}


@pytest.fixture
def migrated_root(tmp_path: Path) -> Path:
    (tmp_path / "cache").mkdir()
    (tmp_path / "logs").mkdir()
    return tmp_path


@pytest.fixture(autouse=True)
def _oracle_brain(monkeypatch: pytest.MonkeyPatch) -> None:
    """``narrative_answer`` pulls ``LK.shared_brain()`` for the wire (cell/coverage Betas + the
    per-claim optimise); give it the in-process :class:`ConjugateBrain` oracle so the family
    stays hermetic (no engine spawn). Tests that drive a brain directly ignore it."""
    from life_agent.core import lookup as LK
    monkeypatch.setattr(LK, "shared_brain", ConjugateBrain)


@dataclass(frozen=True)
class Card:
    n: int
    text: str
    as_of: str | None = None


def _claim_event(*, cell: str, grade: str = "CORRECT",
                 identity: dict | None = None) -> O.OutcomeEvent:
    return O.OutcomeEvent(
        tx_time="2026-06-13T10:00:00+00:00", run_id="eval-test", question_id="q-x",
        claim="claim text", construct="claim", grade=grade, grader="eval_claim",
        instrument_identity=identity if identity is not None
        else N.instrument_identity(),
        probability=0.6, signals={"audit_cell": cell, "included": True})


def _coverage_event(*, grade: str) -> O.OutcomeEvent:
    return O.OutcomeEvent(
        tx_time="2026-06-13T10:00:00+00:00", run_id="eval-test", question_id="q-x",
        claim="gold", construct="proposal-coverage", grade=grade,
        grader="eval_coverage", instrument_identity=N.instrument_identity())


class ConjugateBrain:
    """A test-oracle brain double: an INDEPENDENT implementation of the engine math the
    narrative body now drives over the wire — Beta-Bernoulli conjugacy + the `centered_power`
    integrated claim-EU. It verifies the body's wire CHOREOGRAPHY (create→condition→read_params,
    optimise/expect/mean) hermetically, without the real engine. Not the production path; the
    real integration is covered by the engine's test_skin / test_centered_moment."""

    def __init__(self) -> None:
        self._states: dict[str, tuple[float, float]] = {}
        self._n = 0

    def create_state(self, spec: dict) -> str:
        assert spec["type"] == "beta", spec
        self._n += 1
        sid = f"s_{self._n}"
        self._states[sid] = (float(spec["alpha"]), float(spec["beta"]))
        return sid

    def destroy_state(self, sid: str) -> None:
        self._states.pop(sid, None)

    def condition(self, sid: str, *, kernel: dict, observation: float) -> float:
        assert kernel == {"type": "bernoulli"}, kernel
        a, b = self._states[sid]
        self._states[sid] = (a + observation, b + (1.0 - observation))  # Beta-Bernoulli
        return 0.0

    def read_params(self, sid: str) -> dict:
        a, b = self._states[sid]
        return {"type": "beta", "alpha": a, "beta": b}

    def mean(self, sid: str) -> float:
        a, b = self._states[sid]
        return a / (a + b)

    def _eval_fn(self, sid: str, fn: dict) -> float:
        a, b = self._states[sid]
        e1 = a / (a + b)
        e2 = a * (a + 1.0) / ((a + b) * (a + b + 1.0))   # raw second moment E[θ²]
        total = float(fn.get("offset", 0.0))
        for coeff, sub in fn.get("terms", []):
            if sub["type"] == "centered_power":
                assert sub.get("n") == 2 and sub.get("mu", 0.0) == 0.0, sub
                total += coeff * e2
            elif sub["type"] == "identity":
                total += coeff * e1
            else:
                raise AssertionError(f"oracle does not model {sub['type']!r}")
        return total

    def expect(self, sid: str, *, function: dict) -> float:
        return self._eval_fn(sid, function)

    def optimise(self, sid: str, *, actions: dict, preference: dict):
        assert preference["type"] == "functional_per_action", preference
        best_a, best_eu = None, float("-inf")
        for name, fn in preference["actions"].items():
            eu = self._eval_fn(sid, fn)
            if eu > best_eu:
                best_eu, best_a = eu, name
        return best_a, best_eu


# --- move 1: the deterministic parse + audit cells ----------------------------------------

def test_parse_claims_at_citation_boundaries() -> None:
    text = "Your tax ID is 999999991. [1] It was issued in Tel Aviv. [2][3]\nUncited tail."
    claims = parse_claims(text)
    assert claims == [
        ("Your tax ID is 999999991.", (1,)),
        ("It was issued in Tel Aviv.", (2, 3)),
        ("Uncited tail.", ()),
    ]


def test_parse_claims_drops_wordless_spans() -> None:
    assert parse_claims("---[1] Real claim 1234567. [2] ***") == [
        ("Real claim 1234567.", (2,))]


def test_audit_cell_partition() -> None:
    cards = {1: "the registered number 999999991 appears here", 2: "unrelated text"}
    # a value span contained in a cited card → verified
    assert audit_cell("ID 999999991.", (1,), cards) == "verified"
    # value spans + citations, no cited card contains any → unsupported
    assert audit_cell("ID 999999991.", (2,), cards) == "unsupported"
    # a dangling citation supports nothing
    assert audit_cell("ID 999999991.", (9,), cards) == "unsupported"
    # no value spans → the deterministic instrument is silent
    assert audit_cell("It was renewed recently.", (1,), cards) == "unverifiable"
    # value spans but no citations → equally silent
    assert audit_cell("ID 999999991.", (), cards) == "unverifiable"


# --- move 2: the population fold ----------------------------------------------------------

def test_population_posteriors_start_at_stated_priors(tmp_path: Path) -> None:
    # no evidence → the wire-conditioned posterior IS the stated prior (read back via read_params)
    assert population_posteriors(ConjugateBrain(), tmp_path / "absent.jsonl") == N._CELL_PRIORS


def test_population_posteriors_condition_per_cell(tmp_path: Path) -> None:
    log = tmp_path / "outcomes.jsonl"
    for _ in range(3):
        O.append(log, _claim_event(cell="verified", grade="CORRECT"))
    O.append(log, _claim_event(cell="verified", grade="INCORRECT"))
    O.append(log, _claim_event(cell="unsupported", grade="INCORRECT"))
    # the body conditions each cell's Beta over the wire (3 successes + 1 fail on verified);
    # the exact Beta-Bernoulli posterior comes back via read_params — never a host `a += 1`.
    post = population_posteriors(ConjugateBrain(), log)
    a0, b0 = N._CELL_PRIORS["verified"]
    assert post["verified"] == (a0 + 3.0, b0 + 1.0)
    a1, b1 = N._CELL_PRIORS["unsupported"]
    assert post["unsupported"] == (a1, b1 + 1.0)
    assert post["unverifiable"] == N._CELL_PRIORS["unverifiable"]


def test_population_fold_filters_on_exact_instrument_identity(tmp_path: Path) -> None:
    # §2: a superseded instrument's evidence never pools into the current posterior
    log = tmp_path / "outcomes.jsonl"
    stale = dict(N.instrument_identity(), narrative_version="0-superseded")
    for _ in range(5):
        O.append(log, _claim_event(cell="verified", identity=stale))
    assert population_posteriors(ConjugateBrain(), log)["verified"] == N._CELL_PRIORS["verified"]


def test_population_fold_raises_on_junk_cell(tmp_path: Path) -> None:
    log = tmp_path / "outcomes.jsonl"
    O.append(log, _claim_event(cell="vibes"))
    with pytest.raises(ValueError, match="partition"):
        population_posteriors(ConjugateBrain(), log)


def test_coverage_posterior_conditions_on_misses(tmp_path: Path) -> None:
    log = tmp_path / "outcomes.jsonl"
    O.append(log, _coverage_event(grade="PROPOSED"))
    O.append(log, _coverage_event(grade="MISSED"))
    a0, b0 = N._COVERAGE_PRIOR
    assert coverage_posterior(ConjugateBrain(), log) == ((a0 + 1.0, b0 + 1.0), 2)


# --- M4: the inclusion decision -----------------------------------------------------------

def test_include_eu_reliance_linear_model() -> None:
    # at p=1 the crisp report EU is recovered (minus the per-claim attention cost)
    assert include_eu(1.0, U) == pytest.approx(1.0 - 0.05)
    # a coin-flip label has negative EU: no information value, attention cost paid
    assert include_eu(0.5, U) == pytest.approx(0.5 * (0.5 - 2.5) - 0.05)


# cells with means 0.9 (high) / 0.5 (coin) / 0.25 (low) — the decision integrates the cell Beta.
_CELLS = {"verified": (9.0, 1.0), "unverifiable": (1.0, 1.0), "unsupported": (1.0, 3.0)}


def test_decide_claims_inclusion_and_posterior_order() -> None:
    # scored is now (text, cites, cell, as_of, tf); the credence is READ from the cell Beta and
    # the include/withhold decision is the engine's integrated-EU optimise (tf=1.0 unscoped).
    scored = [("low", (), "unverifiable", None, 1.0), ("high", (1,), "verified", None, 1.0)]
    claims, action, eu, reason = decide_claims(ConjugateBrain(), scored, _CELLS, U)
    assert action == "report" and reason == ""
    assert [c.text for c in claims] == ["high", "low"]  # posterior order by credence
    assert claims[0].included and not claims[1].included
    assert claims[0].credence == pytest.approx(0.9)  # displayed credence = cell mean × tf
    # answer EU = the included claim's integrated include-EU (E[θ²] over the cell Beta, not p̄²)
    a, b = _CELLS["verified"]
    e2 = a * (a + 1) / ((a + b) * (a + b + 1))
    assert eu == pytest.approx((U["u_correct"] - U["u_wrong"]) * e2
                               + U["u_wrong"] * (a / (a + b)) - U["kappa_att"])


def test_decide_claims_all_withheld_abstains_named() -> None:
    scored = [("c", (), "unverifiable", None, 1.0)]  # cell mean 0.5 → integrated EU < 0
    _claims, action, eu, reason = decide_claims(ConjugateBrain(), scored, _CELLS, U)
    assert action == "abstain" and eu == 0.0
    assert reason == N.REASON_ALL_WITHHELD


def test_decide_claims_empty_abstains_named() -> None:
    _, action, _, reason = decide_claims(ConjugateBrain(), [], {}, U)
    assert action == "abstain" and reason == N.REASON_NO_CLAIMS


# --- render (the credence grammar) --------------------------------------------------------

def test_render_report_labels_claims_and_counts_withheld() -> None:
    scored = [("The number is 999999991.", (1,), "verified", None, 1.0),
              ("It was renewed.", (), "unverifiable", None, 1.0)]
    claims, action, eu, reason = decide_claims(ConjugateBrain(), scored, _CELLS, U)
    r = N.NarrativeResult(
        question="q", action=action, eu=eu, abstain_reason=reason, claims=claims,
        coverage=(2.0, 2.0), coverage_n=0, cell_posteriors=dict(N._CELL_PRIORS),
        utility_fold_version="fold-1", answer_cache_key="k", rendered="")
    text = render(r)
    assert "- The number is 999999991. [1] — credence 0.900" in text
    assert "(1 claims withheld" in text
    assert "coverage 0.500 (n=0)" in text
    assert "decision report" in text


def test_render_abstain_names_reason_and_footer() -> None:
    scored = [("c 1234567.", (1,), "unsupported", None, 1.0)]  # cell mean 0.25 → withheld
    claims, action, eu, reason = decide_claims(ConjugateBrain(), scored, _CELLS, U)
    r = N.NarrativeResult(
        question="q", action=action, eu=eu, abstain_reason=reason, claims=claims,
        coverage=(2.0, 3.0), coverage_n=1, cell_posteriors=dict(N._CELL_PRIORS),
        utility_fold_version="fold-1", answer_cache_key="k", rendered="")
    text = render(r)
    assert N.GRAMMAR["abstain"].format(reason=N.REASON_ALL_WITHHELD) in text
    assert "1 claims proposed → 0 included" in text


def test_grammar_is_closed() -> None:
    # drift gate: every rendered string comes from this table (interaction contract)
    assert set(N.GRAMMAR) == {"claim", "as_of", "withheld", "abstain", "footer", "fallthrough"}


# --- the family, end to end ----------------------------------------------------------------

def _answer_fixture(tmp_path: Path) -> tuple[str, list[Card], Path, Path]:
    text = "Your registration number is 999999991. [1] It is renewed annually."
    cards = [Card(n=1, text="certificate: registration number 999999991")]
    return (text, cards, tmp_path / "outcomes.jsonl", tmp_path / "decisions.jsonl")


def test_narrative_answer_abstains_at_priors(migrated_root: Path,
                                             tmp_path: Path) -> None:
    # the honest §7 prediction: with an empty evidence stream the verified cell sits
    # at its wide prior (0.6), below the inclusion threshold at this Ū — the answer
    # abstains, names the reason, and still records + logs everything
    text, cards, opath, dpath = _answer_fixture(tmp_path)
    nv = narrative_answer(migrated_root, "what is my registration number?",
                          text, cards, u_bar=U, utility_fold_version="fold-1",
                          outcomes_path=opath, decisions_path=dpath)
    assert nv.action == "abstain" and nv.abstain_reason == N.REASON_ALL_WITHHELD
    assert [c.cell for c in nv.claims] == ["verified", "unverifiable"]
    assert N.GRAMMAR["abstain"].format(reason=N.REASON_ALL_WITHHELD) in nv.rendered
    # the answer artifact is on the ledger (§18.9)
    recorded = json.loads(D.lookup(migrated_root, nv.answer_cache_key))
    assert recorded["action"] == "abstain"
    assert recorded["cell_posteriors"]["verified"] == list(N._CELL_PRIORS["verified"])
    # no EU decision is ever made unlogged (§8)
    events = DEC.read(dpath)
    assert len(events) == 1 and events[0].family == "narrative"
    assert events[0].chosen_action == "abstain"


def test_narrative_answer_reports_once_evidence_deepens(migrated_root: Path,
                                                        tmp_path: Path) -> None:
    # 8 correct verified-cell outcomes move the cell to (11, 2) ≈ 0.846 — above the
    # inclusion threshold at this Ū: the gate opens with evidence, not fiat
    text, cards, opath, dpath = _answer_fixture(tmp_path)
    for _ in range(8):
        O.append(opath, _claim_event(cell="verified", grade="CORRECT"))
    nv = narrative_answer(migrated_root, "what is my registration number?",
                          text, cards, u_bar=U, utility_fold_version="fold-1",
                          outcomes_path=opath, decisions_path=dpath)
    assert nv.action == "report"
    included = [c for c in nv.claims if c.included]
    assert [c.text for c in included] == ["Your registration number is 999999991."]
    assert included[0].credence == pytest.approx(11.0 / 13.0)
    assert "— credence 0.846" in nv.rendered
    assert "(1 claims withheld" in nv.rendered  # the unverifiable tail stays out


def test_narrative_answer_key_moves_with_the_folds(migrated_root: Path,
                                                   tmp_path: Path) -> None:
    # the folds are decision inputs: new evidence ⇒ a new answer artifact; the same
    # state replays to the same key (file-first idempotency)
    text, cards, opath, dpath = _answer_fixture(tmp_path)
    nv1 = narrative_answer(migrated_root, "q?", text, cards, u_bar=U,
                           utility_fold_version="fold-1",
                           outcomes_path=opath, decisions_path=dpath)
    nv2 = narrative_answer(migrated_root, "q?", text, cards, u_bar=U,
                           utility_fold_version="fold-1",
                           outcomes_path=opath, decisions_path=dpath)
    assert nv1.answer_cache_key == nv2.answer_cache_key
    O.append(opath, _claim_event(cell="verified", grade="CORRECT"))
    nv3 = narrative_answer(migrated_root, "q?", text, cards, u_bar=U,
                           utility_fold_version="fold-1",
                           outcomes_path=opath, decisions_path=dpath)
    assert nv3.answer_cache_key != nv1.answer_cache_key


def test_owner_verdicts_move_the_verified_cell(tmp_path: Path) -> None:
    # The verdict → cell learning loop (the owner IS the gold): per-claim verdicts write eval_claim
    # outcomes that population_posteriors folds. The q-007 lesson — a grounded-but-stale claim
    # verdicted INCORRECT LOWERS the verified cell (grounded ≠ current-correct).
    claims = (
        N.Claim(text="Bank Zephyr is your current bank", cites=(1,), cell="verified",
                credence=0.71, included=False, eu_include=-0.4),
        N.Claim(text="Bank Aurum is your bank", cites=(2,), cell="verified",
                credence=0.71, included=False, eu_include=-0.4),
    )
    result = N.NarrativeResult(
        question="which banks hold my accounts?", action="abstain", eu=0.0,
        abstain_reason="all claims below threshold", claims=claims, coverage=(7.0, 6.0),
        coverage_n=13, cell_posteriors={}, utility_fold_version="v0", answer_cache_key="ak",
        rendered="")
    out = tmp_path / "outcomes.jsonl"
    n = N.record_owner_verdicts(result, "q-007", {0: True, 1: False}, outcomes_path=out)
    assert n == 2
    post = N.population_posteriors(ConjugateBrain(), out)
    assert post["verified"] == (4.0, 3.0)              # prior (3,2) +1 correct +1 incorrect
    assert post["unsupported"] == N._CELL_PRIORS["unsupported"]   # an unjudged cell is untouched


def test_owner_verdicts_only_emit_for_judged_claims(tmp_path: Path) -> None:
    # DISCLOSED selection — an unjudged claim casts no silent vote.
    claims = (N.Claim(text="x", cites=(1,), cell="verified", credence=0.6, included=False,
                      eu_include=-0.1),
              N.Claim(text="y", cites=(2,), cell="unverifiable", credence=0.5, included=False,
                      eu_include=-0.2))
    result = N.NarrativeResult(question="q", action="abstain", eu=0.0, abstain_reason="r",
                               claims=claims, coverage=(1.0, 1.0), coverage_n=0,
                               cell_posteriors={}, utility_fold_version="v0",
                               answer_cache_key="ak", rendered="")
    events = N.owner_claim_outcomes(result, "q-x", {0: True})   # only claim 0 judged
    assert len(events) == 1 and events[0].grade == "CORRECT"
    assert events[0].signals["audit_cell"] == "verified"


# --- temporal-scope keystone: the claim carries its freshest cited doc_date -----------------

def test_freshest_as_of_takes_the_max_cited_date() -> None:
    # ISO strings order chronologically; the freshest CITED date wins, undated cites are ignored
    as_of_by_n = {1: "2019-04-02", 2: "2025-11-03", 3: None}
    assert freshest_as_of((1, 2), as_of_by_n) == "2025-11-03"
    assert freshest_as_of((1, 3), as_of_by_n) == "2019-04-02"   # the dated one of the pair
    assert freshest_as_of((3,), as_of_by_n) is None             # all cited cards undated
    assert freshest_as_of((), as_of_by_n) is None               # no citations


def test_narrative_answer_threads_freshest_cited_date(migrated_root: Path,
                                                      tmp_path: Path) -> None:
    # a dated cited card surfaces its date on the claim and in the render ("as of <date>").
    # Deepen the verified cell so the claim is INCLUDED (the render only shows included claims).
    text = "Your registration number is 999999991. [1] It is renewed annually."
    cards = [Card(n=1, text="certificate: registration number 999999991",
                  as_of="2025-11-03")]
    opath, dpath = tmp_path / "outcomes.jsonl", tmp_path / "decisions.jsonl"
    for _ in range(8):
        O.append(opath, _claim_event(cell="verified", grade="CORRECT"))
    nv = narrative_answer(migrated_root, "what is my registration number?",
                          text, cards, u_bar=U, utility_fold_version="fold-1",
                          outcomes_path=opath, decisions_path=dpath)
    included = [c for c in nv.claims if c.included]
    assert included[0].as_of == "2025-11-03"
    assert "— credence 0.846, as of 2025-11-03" in nv.rendered


def test_undated_claim_renders_exactly_as_before(migrated_root: Path,
                                                 tmp_path: Path) -> None:
    # back-compat / drift: an undated claim is byte-identical to the pre-keystone render
    text, cards, opath, dpath = _answer_fixture(tmp_path)   # Card has no as_of → None
    for _ in range(8):
        O.append(opath, _claim_event(cell="verified", grade="CORRECT"))
    nv = narrative_answer(migrated_root, "what is my registration number?",
                          text, cards, u_bar=U, utility_fold_version="fold-1",
                          outcomes_path=opath, decisions_path=dpath)
    assert "— credence 0.846" in nv.rendered
    assert ", as of" not in nv.rendered


def test_owner_verdict_tags_claim_as_of_but_fold_reads_only_the_cell(tmp_path: Path) -> None:
    # the outcome carries claim_as_of for a FUTURE stale-vs-false separation; the keystone fold
    # is unchanged — population_posteriors still reads only the audit cell.
    claims = (N.Claim(text="Bank Aurum is your bank", cites=(1,), cell="verified", credence=0.71,
                      included=False, eu_include=-0.4, as_of="2019-04-02"),)
    result = N.NarrativeResult(
        question="which bank?", action="abstain", eu=0.0, abstain_reason="r", claims=claims,
        coverage=(7.0, 6.0), coverage_n=13, cell_posteriors={}, utility_fold_version="v0",
        answer_cache_key="ak", rendered="")
    out = tmp_path / "outcomes.jsonl"
    events = N.owner_claim_outcomes(result, "q-007", {0: False})
    assert events[0].signals["claim_as_of"] == "2019-04-02"
    N.record_owner_verdicts(result, "q-007", {0: False}, outcomes_path=out)
    post = N.population_posteriors(ConjugateBrain(), out)
    assert post["verified"] == (3.0, 3.0)   # prior (3,2) + 1 incorrect — folded on the cell alone


# --- scope-aware inclusion (slice 3): present-intent decays a DATED stale claim -------------

_TODAY = date(2026, 1, 1)


def test_scope_decay_only_present_and_dated() -> None:
    # gate-safe: present + an OLD dated claim decays below its cell credence...
    stale = scope_decay(0.9, "2010-01-01", "my address", "present", today=_TODAY)
    assert stale < 0.9
    # ...a RECENT dated claim is ~unchanged (factor ≈ 1)...
    fresh = scope_decay(0.9, "2025-12-01", "my address", "present", today=_TODAY)
    assert fresh == pytest.approx(0.9, abs=0.02)
    # ...an UNDATED claim is untouched (a derivation gap, never penalised)...
    assert scope_decay(0.9, None, "my address", "present", today=_TODAY) == 0.9
    # ...and a NON-present scope is untouched whatever the date.
    for sc in ("historical", "as_of", "unscoped"):
        assert scope_decay(0.9, "2010-01-01", "my address", sc, today=_TODAY) == 0.9


def test_scope_decay_never_raises_credence() -> None:
    # the gate-safety invariant: the factor is in [0, 1], so decay can only lower p
    for as_of in ("2000-01-01", "2025-06-01", "2026-01-01", None):
        assert scope_decay(0.8, as_of, "my salary", "present", today=_TODAY) <= 0.8


def _deep_verified(opath: Path, n: int = 8) -> None:
    for _ in range(n):
        O.append(opath, _claim_event(cell="verified", grade="CORRECT"))


def test_narrative_answer_present_decays_a_dated_stale_claim(migrated_root: Path,
                                                            tmp_path: Path) -> None:
    # a dated STALE claim, includable under unscoped (cell ≈ 0.846), is decayed by a present-intent
    # question — its rendered credence drops, and far enough back it falls below inclusion.
    text = "Your registration number is 999999991. [1] It is renewed annually."
    cards = [Card(n=1, text="certificate: registration number 999999991", as_of="2005-01-01")]
    opath, dpath = tmp_path / "o.jsonl", tmp_path / "d.jsonl"
    _deep_verified(opath)
    base = narrative_answer(migrated_root, "q?", text, cards, scope="unscoped",
                            u_bar=U, utility_fold_version="f", outcomes_path=opath,
                            decisions_path=dpath)
    pres = narrative_answer(migrated_root, "what is my registration number now?", text, cards,
                            scope="present", u_bar=U, utility_fold_version="f",
                            outcomes_path=opath, decisions_path=dpath)
    base_c = base.claims[0].credence
    pres_c = pres.claims[0].credence
    assert pres_c < base_c                       # the present-intent decay lowered it
    assert base.claims[0].as_of == "2005-01-01"  # the keystone date still threaded


def test_narrative_answer_non_present_scope_matches_unscoped(migrated_root: Path,
                                                            tmp_path: Path) -> None:
    text = "Your registration number is 999999991. [1]"
    cards = [Card(n=1, text="certificate: registration number 999999991", as_of="2005-01-01")]
    opath, dpath = tmp_path / "o.jsonl", tmp_path / "d.jsonl"
    _deep_verified(opath)
    un = narrative_answer(migrated_root, "q?", text, cards, scope="unscoped", u_bar=U,
                          utility_fold_version="f", outcomes_path=opath, decisions_path=dpath)
    hist = narrative_answer(migrated_root, "q?", text, cards, scope="historical", u_bar=U,
                            utility_fold_version="f", outcomes_path=opath, decisions_path=dpath)
    assert hist.claims[0].credence == un.claims[0].credence  # historical does NOT decay
