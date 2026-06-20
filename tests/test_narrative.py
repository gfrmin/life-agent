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
    include_eu,
    narrative_answer,
    parse_claims,
    population_posteriors,
    render,
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


@dataclass(frozen=True)
class Card:
    n: int
    text: str


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
    assert population_posteriors(tmp_path / "absent.jsonl") == N._CELL_PRIORS


def test_population_posteriors_condition_per_cell(tmp_path: Path) -> None:
    log = tmp_path / "outcomes.jsonl"
    for _ in range(3):
        O.append(log, _claim_event(cell="verified", grade="CORRECT"))
    O.append(log, _claim_event(cell="verified", grade="INCORRECT"))
    O.append(log, _claim_event(cell="unsupported", grade="INCORRECT"))
    post = population_posteriors(log)
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
    assert population_posteriors(log)["verified"] == N._CELL_PRIORS["verified"]


def test_population_fold_raises_on_junk_cell(tmp_path: Path) -> None:
    log = tmp_path / "outcomes.jsonl"
    O.append(log, _claim_event(cell="vibes"))
    with pytest.raises(ValueError, match="partition"):
        population_posteriors(log)


def test_coverage_posterior_conditions_on_misses(tmp_path: Path) -> None:
    log = tmp_path / "outcomes.jsonl"
    O.append(log, _coverage_event(grade="PROPOSED"))
    O.append(log, _coverage_event(grade="MISSED"))
    a0, b0 = N._COVERAGE_PRIOR
    assert coverage_posterior(log) == ((a0 + 1.0, b0 + 1.0), 2)


# --- M4: the inclusion decision -----------------------------------------------------------

def test_include_eu_reliance_linear_model() -> None:
    # at p=1 the crisp report EU is recovered (minus the per-claim attention cost)
    assert include_eu(1.0, U) == pytest.approx(1.0 - 0.05)
    # a coin-flip label has negative EU: no information value, attention cost paid
    assert include_eu(0.5, U) == pytest.approx(0.5 * (0.5 - 2.5) - 0.05)


def test_decide_claims_inclusion_and_posterior_order() -> None:
    scored = [("low", (), "unverifiable", 0.5), ("high", (1,), "verified", 0.9)]
    claims, action, eu, reason = decide_claims(scored, U)
    assert action == "report" and reason == ""
    assert [c.text for c in claims] == ["high", "low"]  # posterior order
    assert claims[0].included and not claims[1].included
    assert eu == pytest.approx(include_eu(0.9, U))


def test_decide_claims_all_withheld_abstains_named() -> None:
    _claims, action, eu, reason = decide_claims([("c", (), "unverifiable", 0.5)], U)
    assert action == "abstain" and eu == 0.0
    assert reason == N.REASON_ALL_WITHHELD


def test_decide_claims_empty_abstains_named() -> None:
    _, action, _, reason = decide_claims([], U)
    assert action == "abstain" and reason == N.REASON_NO_CLAIMS


# --- render (the credence grammar) --------------------------------------------------------

def test_render_report_labels_claims_and_counts_withheld() -> None:
    claims, action, eu, reason = decide_claims(
        [("The number is 999999991.", (1,), "verified", 0.9),
         ("It was renewed.", (), "unverifiable", 0.5)], U)
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
    claims, action, eu, reason = decide_claims(
        [("c 1234567.", (1,), "unsupported", 0.25)], U)
    r = N.NarrativeResult(
        question="q", action=action, eu=eu, abstain_reason=reason, claims=claims,
        coverage=(2.0, 3.0), coverage_n=1, cell_posteriors=dict(N._CELL_PRIORS),
        utility_fold_version="fold-1", answer_cache_key="k", rendered="")
    text = render(r)
    assert N.GRAMMAR["abstain"].format(reason=N.REASON_ALL_WITHHELD) in text
    assert "1 claims proposed → 0 included" in text


def test_grammar_is_closed() -> None:
    # drift gate: every rendered string comes from this table (interaction contract)
    assert set(N.GRAMMAR) == {"claim", "withheld", "abstain", "footer", "fallthrough"}


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
        N.Claim(text="ONE ZERO is your current bank", cites=(1,), cell="verified",
                credence=0.71, included=False, eu_include=-0.4),
        N.Claim(text="Hapoalim is your bank", cites=(2,), cell="verified",
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
    post = N.population_posteriors(out)
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
