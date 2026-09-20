"""The lookup family's evidence shaping (life_agent.core.lookup) — foundations §4, hermetic.

The model is faked (the subject.py client pattern) and §18.9 records land under
``migrated_root``.

Run: uv run --project . python -m pytest tests/test_lookup.py
"""
from __future__ import annotations

import dataclasses
import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from life_agent.core import config
from life_agent.core import lookup as LK
from life_agent.core.lookup import (
    Observation,
    authority_for,
    candidates_from,
    observe_hits,
    route_question,
)
from pkm.transform import ModelResponse


@pytest.fixture
def migrated_root(tmp_path: Path) -> Path:
    # §18.9 records are file-first (content → lineage → meta + pending queue); no
    # catalogue is touched, so bare cache/logs dirs suffice.
    (tmp_path / "cache").mkdir()
    (tmp_path / "logs").mkdir()
    return tmp_path


class FakeClient:
    """The subject.py fake-client pattern: scripted JSON replies, call counting."""

    engine_version = "fake-1"

    def __init__(self, replies: list[dict] | dict) -> None:
        self._replies = replies if isinstance(replies, list) else [replies]
        self.calls = 0

    def complete(self, prompt: str, schema: dict[str, Any]) -> ModelResponse:
        reply = self._replies[min(self.calls, len(self._replies) - 1)]
        self.calls += 1
        return ModelResponse(raw_text=json.dumps(reply), input_tokens=1,
                             output_tokens=1, latency_ms=1, cost_usd=0.0)


def _hit(key: str, chunk: str, origin: str = "/data/doc.pdf") -> dict[str, Any]:
    return {"artifact_cache_key": key, "chunk_text": chunk, "score": 9.0,
            "origin": origin}


# --- route (cached §18.9 verdict) ---------------------------------------------------------

def test_route_lookup_returns_route_and_caches(migrated_root: Path) -> None:
    client = FakeClient({"lookup": True, "construct": "passport number"})
    c1 = route_question(migrated_root, "what is my passport number?", client=client)
    c2 = route_question(migrated_root, "what is my passport number?", client=client)
    # a reply without time_indexed defaults to False (permanent fact — no attenuation)
    assert c1 == c2 == LK.Route(construct="passport number", time_indexed=False)
    assert client.calls == 1  # replayed from cache


def test_route_time_indexed_classification(migrated_root: Path) -> None:
    client = FakeClient({"lookup": True, "construct": "home address",
                         "time_indexed": True})
    r = route_question(migrated_root, "what is my home address?", client=client)
    assert r == LK.Route(construct="home address", time_indexed=True)


def test_route_non_lookup_is_none(migrated_root: Path) -> None:
    client = FakeClient({"lookup": False})
    assert route_question(migrated_root, "summarise my year", client=client) is None


def test_prompt_templates_are_single_braced() -> None:
    # These templates are substituted with .replace(), NOT .format(): a doubled
    # brace reaches the model verbatim as a malformed JSON example. The 7b extract
    # model answered found:false on trivially present values until this was fixed
    # — drift-gated so the defect class cannot silently return.
    for template in (LK.ROUTE_PROMPT, LK.EXTRACT_PROMPT):
        assert "{{" not in template and "}}" not in template


# --- observe (grounding gate, caching, authority) -----------------------------------------

def test_observe_grounded_extraction(migrated_root: Path) -> None:
    chunk = "Passport No: P1234567 issued 2019"  # PII-OK: synthetic passport
    client = FakeClient({"found": True, "value": "P1234567",
                         "quote": "Passport No: P1234567"})  # PII-OK: synthetic passport
    obs, ind = observe_hits(migrated_root, "passport number?",
                            [_hit("a" * 64, chunk)], client=client)
    assert ind == 0 and len(obs) == 1
    assert obs[0].value_norm == "p1234567"
    assert obs[0].card_n == 1
    assert obs[0].authority_class == "document"


def test_ungrounded_quote_is_indeterminate_and_recorded(migrated_root: Path) -> None:
    client = FakeClient({"found": True, "value": "X99",
                         "quote": "this text is not in the chunk"})
    obs, ind = observe_hits(migrated_root, "q?", [_hit("a" * 64, "real content")],
                            client=client)
    assert obs == [] and ind == 1
    # the ⊥ observation is recorded (deterministic replay), so no second model call
    obs2, ind2 = observe_hits(migrated_root, "q?", [_hit("a" * 64, "real content")],
                              client=client)
    assert (obs2, ind2) == ([], 1)
    assert client.calls == 1


def test_scrambled_quote_with_present_value_is_grounded(migrated_root: Path) -> None:
    # RTL PDF extraction scrambles visual order: the chunk reads "<value> : תעודת
    # זהות" while the model quotes in logical order. The VALUE is verbatim in the
    # chunk — the gate's anti-hallucination construct holds, so the observation
    # stands. The number is synthetic (checksum-invalid).
    chunk = "999999991 :\nתעודת זהות\nאישור יתרה"  # noqa: RUF001 — deliberate RTL fixture
    client = FakeClient({"found": True, "value": "999999991",
                         "quote": "תעודת זהות\n999999991"})
    obs, ind = observe_hits(migrated_root, "tax id?", [_hit("a" * 64, chunk)],
                            client=client)
    assert ind == 0 and len(obs) == 1 and obs[0].value_raw == "999999991"


def test_not_found_is_indeterminate(migrated_root: Path) -> None:
    client = FakeClient({"found": False})
    obs, ind = observe_hits(migrated_root, "q?", [_hit("b" * 64, "irrelevant")],
                            client=client)
    assert obs == [] and ind == 1


def test_observation_cache_is_per_chunk(migrated_root: Path) -> None:
    client = FakeClient({"found": True, "value": "42", "quote": "42"})
    hits = [_hit("a" * 64, "the answer is 42"), _hit("b" * 64, "still 42 here")]
    observe_hits(migrated_root, "q?", hits, client=client)
    assert client.calls == 2
    observe_hits(migrated_root, "q?", hits, client=client)
    assert client.calls == 2  # both replayed


def test_observe_hits_collapses_correlated_duplicate_documents(migrated_root: Path) -> None:
    # Two DIFFERENT documents carrying the same quoted value (a forwarded / re-filed copy) are
    # correlated witnesses, not independent — observe_hits, the shared evidence SHAPER, collapses
    # them to one. The §5 dedup must live here, not only in the host lookup_posterior: the
    # decouple split shaping from deciding, so a dedup in the host decider never reached the
    # daemon path (bridge /extract → to_abstract_observations) and the q-002/q-014 confident-wrong
    # regression stayed latent in the executor.
    quote = "Passport No: P1234567"  # PII-OK: synthetic passport
    client = FakeClient({"found": True, "value": "P1234567", "quote": quote})
    hits = [_hit("a" * 64, f"{quote} issued 2019"),
            _hit("b" * 64, f"FWD: {quote} issued 2019")]
    obs, ind = observe_hits(migrated_root, "passport number?", hits, client=client)
    assert ind == 0
    assert len(obs) == 1  # the correlated duplicate collapses to a single witness


def test_observe_hits_keeps_independent_value_only_corroboration(migrated_root: Path) -> None:
    # Same value, but each document quotes ONLY the bare value (no shared surrounding context):
    # genuine independent corroboration, not a copy — both witnesses are kept. Over-dedup would
    # discard real evidence and understate confidence.
    client = FakeClient({"found": True, "value": "P1234567", "quote": "P1234567"})
    hits = [_hit("a" * 64, "the passport is P1234567"),
            _hit("b" * 64, "P1234567 on file")]
    obs, ind = observe_hits(migrated_root, "passport number?", hits, client=client)
    assert ind == 0
    assert len(obs) == 2  # value-only quotes don't collapse — independent corroboration stands


def test_daemon_abstract_observations_collapse_correlated_duplicates(
        migrated_root: Path) -> None:
    # The executor's evidence shaping end-to-end: observe_hits → to_abstract_observations is
    # exactly what the daemon (Move 2) consumes. A correlated duplicate must not reach it as two
    # witnesses (which saturated the §4.2-less posterior — the regression). This is the daemon-seam
    # lock: it would also fail if to_abstract_observations ever re-expanded a collapsed cluster.
    from life_agent.bridge.observations import to_abstract_observations
    quote = "Passport No: P1234567"  # PII-OK: synthetic passport
    client = FakeClient({"found": True, "value": "P1234567", "quote": quote})
    hits = [_hit("a" * 64, f"{quote} issued 2019"),
            _hit("b" * 64, f"FWD: {quote} issued 2019")]
    obs, _ = observe_hits(migrated_root, "passport number?", hits, client=client)
    _candidates, abstract = to_abstract_observations(obs)
    assert len(abstract) == 1  # the daemon sees one witness, not a saturating duplicate


def test_extractor_reliability_learns_from_eval_outcomes(tmp_path: Path) -> None:
    from life_agent.core import outcomes as O

    log = tmp_path / "outcomes.jsonl"
    # no evidence => the wide Beta(4,4) prior
    assert LK.extractor_reliability(log) == (4.0, 4.0)
    identity = {"producer_name": "life_agent.ask.lookup_answer",
                "extract_prompt_hash": LK.extract_instrument_hash()}
    for grade in ("INCORRECT", "INCORRECT", "CORRECT"):
        O.append(log, O.OutcomeEvent(
            tx_time="t", run_id="r", question_id="q", claim="v", construct="c",
            grade=grade, grader="eval_lookup", instrument_identity=identity,
            probability=0.9))
    # the none-claim grades the posterior, not the instrument: excluded
    O.append(log, O.OutcomeEvent(
        tx_time="t", run_id="r", question_id="q", claim="(none of the retrieved)",
        construct="c", grade="CORRECT", grader="eval_lookup",
        instrument_identity=identity, probability=0.1))
    # an outcome from a SUPERSEDED instrument (different prompt hash, or none at
    # all) never conditions the current posterior — §2's exact-identity keying
    O.append(log, O.OutcomeEvent(
        tx_time="t", run_id="r", question_id="q", claim="v", construct="c",
        grade="INCORRECT", grader="eval_lookup",
        instrument_identity={"producer_name": "life_agent.ask.lookup_answer"},
        probability=0.9))
    # 1 correct + 2 incorrect on the current instrument → Beta(4+1, 4+2) (mean 5/11)
    assert LK.extractor_reliability(log) == (5.0, 6.0)


def test_authority_classes() -> None:
    # synthetic placeholder paths, never real corpus locations
    assert authority_for("/x/statement.pdf") == ("document", 0.95)  # PII-OK
    assert authority_for("/x/mail/cur/12345") == ("email", 0.90)  # PII-OK
    assert authority_for("/x/todo.md") == ("note", 0.80)  # PII-OK
    assert authority_for("/x/blob") == LK._AUTHORITY_DEFAULT  # PII-OK


# --- §4.1 covariates on a_i (doc_subject / doc_date enter the likelihood) ------------------

def test_subject_factor_partition() -> None:
    assert LK.subject_factor(None) == 1.0      # channel absent — no covariate
    assert LK.subject_factor("owner") == 1.0
    assert LK.subject_factor("other") == LK._A_SUBJECT_OTHER
    assert LK.subject_factor("generic") == LK._A_SUBJECT_OTHER
    indet = (LK._P_OWNER_GIVEN_INDET
             + (1 - LK._P_OWNER_GIVEN_INDET) * LK._A_SUBJECT_OTHER)
    assert LK.subject_factor("unclear") == pytest.approx(indet)
    assert LK.subject_factor("underived") == pytest.approx(indet)
    with pytest.raises(ValueError):  # junk from the annotation seam surfaces, loud
        LK.subject_factor("admitted")


def test_time_factor_decay() -> None:
    today = date(2026, 6, 13)
    # a permanent construct never attenuates, whatever the doc age
    assert LK.time_factor("2010-01-01", time_indexed=False, today=today) == 1.0
    # projected-but-unknown date under a time-indexed construct: stated attenuation
    assert LK.time_factor(None, time_indexed=True, today=today) == LK._A_TIME_UNKNOWN
    assert LK.time_factor("2026-06-13", time_indexed=True, today=today) == 1.0
    one_half_life = LK.time_factor("2021-06-13", time_indexed=True, today=today)
    assert one_half_life == pytest.approx(0.5, abs=0.01)
    # future-dated documents clamp to 1.0 — no covariate bonus
    assert LK.time_factor("2030-01-01", time_indexed=True, today=today) == 1.0


def test_observe_hits_carries_covariates(migrated_root: Path) -> None:
    chunk = "Address: 1 Old Road"
    client = FakeClient({"found": True, "value": "1 Old Road",
                         "quote": "Address: 1 Old Road"})
    cov = LK.HitCovariates(subject_state={"a" * 64: "underived"},
                           doc_date={"a" * 64: "2016-06-13"})
    obs, _ = observe_hits(migrated_root, "my address?", [_hit("a" * 64, chunk)],
                          client=client, covariates=cov, time_indexed=True,
                          today=date(2026, 6, 13))
    assert obs[0].subject_factor == pytest.approx(LK.subject_factor("underived"))
    assert obs[0].time_factor == pytest.approx(0.25, abs=0.01)  # two half-lives


def test_observe_hits_absent_covariates_are_unit(migrated_root: Path) -> None:
    client = FakeClient({"found": True, "value": "v", "quote": "v"})
    obs, _ = observe_hits(migrated_root, "q?", [_hit("a" * 64, "v here")],
                          client=client, time_indexed=True)
    assert obs[0].subject_factor == 1.0 and obs[0].time_factor == 1.0
    assert obs[0].n_competing == 0 and obs[0].competition_factor == 1.0


# --- §4.2's competition term at the source (foundations §14, 2026-08-17) -------------------

def test_observe_hits_detects_a_quote_window_competitor(migrated_root: Path) -> None:
    # the q2-105 shape: the extractor's own quote carries the fax AND the tel — the
    # dangerous competitor is inside the anchor, and the observation's r is halved
    chunk = "Ms X  Tel: (852) 5550 0143  Fax: (852) 5550 0187  (row 113)"  # PII-OK
    client = FakeClient({"found": True, "value": "(852) 5550 0143",  # PII-OK: synthetic phone shape
                         "quote": "Tel: (852) 5550 0143  Fax: (852) 5550 0187"})  # PII-OK
    obs, _ = observe_hits(migrated_root, "fax number?", [_hit("a" * 64, chunk)],
                          client=client)
    assert obs[0].n_competing >= 1
    assert obs[0].competition_factor == 0.5


def test_observe_hits_competition_survives_a_warm_replay(migrated_root: Path) -> None:
    # detection is consumer-side over the RAW cached record (the grounding-gate
    # precedent): a warm replay re-detects without any model call, and the extraction
    # cache key is untouched by the temper (the §18.9 record predates it)
    chunk = "prize $1,234,567 for the season; career $7,654,321 listed"
    client = FakeClient({"found": True, "value": "$1,234,567",
                         "quote": "prize $1,234,567 for the season; career $7,654,321"})
    obs1, _ = observe_hits(migrated_root, "prize?", [_hit("a" * 64, chunk)], client=client)
    assert client.calls == 1 and obs1[0].competition_factor == 0.5
    cold = FakeClient({"found": False, "value": "", "quote": ""})   # must never be asked
    obs2, _ = observe_hits(migrated_root, "prize?", [_hit("a" * 64, chunk)], client=cold)
    assert cold.calls == 0
    assert obs2[0].n_competing == obs1[0].n_competing
    assert obs2[0].obs_cache_key == obs1[0].obs_cache_key


# --- the posterior's pure parts -----------------------------------------------------------

def _obs(key: str, value: str, n: int = 1, authority: float = 0.95,
         quote: str | None = None, time_factor: float = 1.0,
         subject_factor: float = 1.0) -> Observation:
    return Observation(card_n=n, artifact_cache_key=key, obs_cache_key="o" * 64,
                       value_raw=value, value_norm=" ".join(value.split()).casefold(),
                       quote=quote if quote is not None else value,
                       authority_class="document", authority=authority,
                       time_factor=time_factor, subject_factor=subject_factor)


# --- §5 dedup-as-inference: correlated duplicates count as ONE witness ---------------------
# The decouple (c71481f) retired the §4.2 ancestry temper; the reliability_categorical group
# model then counted correlated DUPLICATE documents (forwarded/replied chains carrying an
# identical quote) as independent witnesses, saturating credence on duplicated wrong/stale
# values (the confident-wrong regression: q-002 6 emails→0.99, q-014 9 stale→0.80). dedup
# collapses each correlated cluster to one witness — restoring the temper PRINCIPLEDLY (only
# true duplicates collapse; genuine independent corroboration still accumulates).


def test_dedup_correlated_collapses_identical_quotes_across_documents() -> None:
    q = "your 2019 passport number is WRONGVAL per our records"
    dup = [_obs(chr(97 + i) * 64, "WRONGVAL", quote=q) for i in range(6)]
    gold_q = "passport no GOLDVAL appears on the official application form"
    gold = [_obs("y" * 64, "GOLDVAL", quote=gold_q),
            _obs("z" * 64, "GOLDVAL", quote=gold_q)]
    kept = LK.dedup_correlated(dup + gold)
    # six identical-quote copies → one witness; two identical-quote gold copies → one witness
    assert sum(o.value_raw == "WRONGVAL" for o in kept) == 1
    assert sum(o.value_raw == "GOLDVAL" for o in kept) == 1


def test_dedup_correlated_keeps_independent_corroboration() -> None:
    # DIFFERENT quotes for the same value are independent witnesses, not duplicates — real
    # corroboration must still accumulate; only correlated copies collapse.
    obs = [_obs("a" * 64, "V", quote="the value V appears on my tax return"),
           _obs("b" * 64, "V", quote="my accountant recorded V in the summary"),
           _obs("c" * 64, "V", quote="V is printed on the official certificate")]
    assert len(LK.dedup_correlated(obs)) == 3


def test_dedup_correlated_one_document_attests_one_value_once() -> None:
    # r09c A1: within ONE document, every observation of the SAME value is one attestation —
    # identical quotes, near-duplicate boilerplate, or repeated page headers alike. The old
    # rule skipped within-document rows on the premise that the per-document group "already
    # counts it once"; the group mechanism counts them CORRELATED, not once (q2-105: twelve
    # same-doc same-value rows rode the coarsening to 0.989).
    obs = [_obs("a" * 64, "V", quote="a sufficiently long shared sentence of text"),
           _obs("a" * 64, "V", quote="a sufficiently long shared sentence of text")]
    assert len(LK.dedup_correlated(obs)) == 1


def test_dedup_within_document_collapses_near_duplicate_quotes_too() -> None:
    # the boilerplate/page-repetition class: the same value under VARYING quotes in one
    # document is still one attestation — the key is (document, value), not the quote.
    obs = [_obs("a" * 64, "V", quote=f"page {i} footer: contact V for details")
           for i in range(12)]
    kept = LK.dedup_correlated(obs)
    assert len(kept) == 1


def test_dedup_within_document_keeps_the_max_covariate_row() -> None:
    obs = [_obs("a" * 64, "V", quote="weak copy of the value V", authority=0.5),
           _obs("a" * 64, "V", quote="strong copy of the value V", authority=0.95)]
    kept = LK.dedup_correlated(obs)
    assert len(kept) == 1 and kept[0].authority == 0.95


def test_dedup_within_document_tie_keeps_first_seen() -> None:
    # the declared total order (M0.5): at equal covariate the FIRST row survives.
    obs = [_obs("a" * 64, "V", quote="first copy of the value V"),
           _obs("a" * 64, "V", quote="second copy of the value V")]
    kept = LK.dedup_correlated(obs)
    assert len(kept) == 1 and kept[0].quote == "first copy of the value V"


def test_dedup_within_document_keeps_different_values() -> None:
    # one document may genuinely attest two DIFFERENT values (a table with many rows) —
    # the collapse is per (document, value), never per document.
    obs = [_obs("a" * 64, "V1", quote="row one carries value V1"),
           _obs("a" * 64, "V2", quote="row two carries value V2")]
    assert len(LK.dedup_correlated(obs)) == 2


def test_dedup_within_document_then_cross_document_compose() -> None:
    # q2-105's shape: twelve same-doc same-value repetitions vs one other-document gold —
    # the competitor collapses to ONE witness and the gold survives untouched.
    rep = [_obs("a" * 64, "WRONGVAL", quote=f"header {i}: fax WRONGVAL")
           for i in range(12)]
    gold = [_obs("b" * 64, "GOLDVAL", quote="the official form lists GOLDVAL")]
    kept = LK.dedup_correlated(rep + gold)
    assert sum(o.value_raw == "WRONGVAL" for o in kept) == 1
    assert sum(o.value_raw == "GOLDVAL" for o in kept) == 1


def test_dedup_correlated_keeps_max_covariate_representative() -> None:
    # the surviving witness is the strongest/freshest copy (max authority·subject·time), so a
    # recent re-attestation keeps its recency rather than inheriting a stale duplicate's age.
    q = "a sufficiently long shared sentence of text"
    weak = _obs("a" * 64, "V", quote=q, authority=0.5, time_factor=0.2)
    strong = _obs("b" * 64, "V", quote=q, authority=0.95, time_factor=1.0)
    kept = LK.dedup_correlated([weak, strong])
    assert len(kept) == 1 and kept[0].authority == 0.95


def test_dedup_correlated_breaks_a_covariate_tie_by_first_seen_document() -> None:
    # M0.5: at EQUAL covariate the survivor is the FIRST-SEEN document — a declared total
    # order. The tie was resolved by `max()` over a *set* of artefact keys, whose iteration
    # order depends on the interpreter's per-process string hash seed, so which duplicate
    # survived — and therefore which observations reached the posterior, which candidates
    # existed, and in what order — varied between two runs of the same code on the same
    # corpus (17.6% of the recorded battery at one seed, 24.5% across five). Swept over many
    # key pairs because a single pair can agree with hash order by luck.
    q = "a sufficiently long shared sentence of text"
    for i in range(64):
        first, second = f"{i:064x}", f"{i + 1000:064x}"
        kept = LK.dedup_correlated([_obs(first, "V", quote=q), _obs(second, "V", quote=q)])
        assert len(kept) == 1
        assert kept[0].artifact_cache_key == first, f"pair {i} took the second document"


def test_dedup_correlated_first_seen_does_not_override_a_stronger_later_copy() -> None:
    # The declared order is a TIE-BREAK, not a policy change: a strictly stronger later
    # document still wins, so a recent re-attestation keeps its recency (the rule the
    # max-covariate test pins, restated here against first-seen).
    q = "a sufficiently long shared sentence of text"
    weak, strong = f"{1:064x}", f"{2:064x}"
    kept = LK.dedup_correlated([_obs(weak, "V", quote=q, time_factor=0.2),
                                _obs(strong, "V", quote=q, time_factor=1.0)])
    assert len(kept) == 1 and kept[0].artifact_cache_key == strong


def test_dedup_correlated_keeps_value_only_quotes() -> None:
    # a quote that is ONLY the value carries no shared CONTEXT, so identical copies may be
    # genuine independent corroboration rather than duplicates — keep them (don't erase evidence).
    obs = [_obs("a" * 64, "A5", quote="A5"), _obs("b" * 64, "A5", quote="A5")]
    assert len(LK.dedup_correlated(obs)) == 2


def test_dedup_correlated_collapses_short_quotes_with_context() -> None:
    # the q-002/q-014 regression: a SHORT but contextful quote ("Israeli <id>") identical across
    # many documents (a forwarded/batch maildir chain) is a duplicate cluster — context beyond the
    # value is the signal, not quote length. Collapse to one witness.
    obs = [_obs(chr(97 + i) * 64, "WRONGID", quote="Israeli WRONGID") for i in range(6)]
    assert len(LK.dedup_correlated(obs)) == 1


def test_candidates_dedupe_by_normalised_value() -> None:
    obs = [_obs("a" * 64, "P 1234"), _obs("b" * 64, "p  1234"), _obs("c" * 64, "X9")]
    assert candidates_from(obs) == ["P 1234", "X9"]


def test_candidate_key_collapses_leading_zero_and_format_variants() -> None:
    # one identifier written three ways (extra leading zero, hyphens) is ONE candidate —
    # otherwise the OCR/format split disperses posterior mass below the report bar.
    # (synthetic, non-real digit strings throughout these tests)
    obs = [_obs("a" * 64, "07654321"), _obs("b" * 64, "7654321"),
           _obs("c" * 64, "76-54-321")]
    assert candidates_from(obs) == ["07654321"]  # first raw form, single candidate


def test_candidate_key_keeps_distinct_identifiers_separate() -> None:
    # the confident-wrong boundary: values with DIFFERENT significant digits never merge.
    # two distinct identifiers and an OCR-truncated form all stay separate candidates.
    obs = [_obs("a" * 64, "7654321"), _obs("b" * 64, "1234567"),
           _obs("c" * 64, "765432")]
    assert candidates_from(obs) == ["7654321", "1234567", "765432"]


def test_candidate_key_short_numbers_fall_back_to_norm() -> None:
    # below the identifier digit threshold: unchanged whitespace+case dedupe
    assert candidates_from(
        [_obs("a" * 64, "P 1234"), _obs("b" * 64, "p  1234")]) == ["P 1234"]


def test_candidate_key_observation_maps_to_a_candidate() -> None:
    # the lookup_posterior index invariant: every observation's key is among the
    # candidate keys, so the conditioning never raises on a missing index
    obs = [_obs("a" * 64, "07654321"), _obs("b" * 64, "7654321"),
           _obs("c" * 64, "1234567")]
    keys = [LK._candidate_key(c) for c in candidates_from(obs)]
    assert all(LK._candidate_key(o.value_raw) in keys for o in obs)


def test_candidate_key_collapses_date_formats() -> None:
    # the SAME calendar date in several formats is one candidate — extraction was already
    # correct (q-003), only the format split the posterior mass. Includes the ordinal +
    # abbreviated-month spellings (e.g. "14th Mar 1990") that a dogfood ask surfaced as
    # competing with the numeric form and forcing an abstain. (synthetic date)
    obs = [_obs("a" * 64, "1990-03-14"), _obs("b" * 64, "14/03/1990"),
           _obs("c" * 64, "14.03.1990"), _obs("d" * 64, "14th Mar 1990"),
           _obs("e" * 64, "Mar 14th 1990")]
    assert candidates_from(obs) == ["1990-03-14"]


def test_candidate_key_distinct_dates_stay_separate() -> None:
    obs = [_obs("a" * 64, "1990-03-14"), _obs("b" * 64, "20 September 2019")]
    assert candidates_from(obs) == ["1990-03-14", "20 September 2019"]


def test_candidate_key_ambiguous_numeric_date_not_merged() -> None:
    # both components <= 12: D/M vs M/D is ambiguous — NEVER merge (could be different dates)
    obs = [_obs("a" * 64, "05/06/1991"), _obs("b" * 64, "06/05/1991")]
    assert len(candidates_from(obs)) == 2


def test_parse_date_unambiguous_and_ambiguous() -> None:
    assert LK._parse_date("1990-03-14") == "1990-03-14"
    assert LK._parse_date("14/03/1990") == "1990-03-14"      # 14>12 → D/M/Y
    assert LK._parse_date("03/14/1990") == "1990-03-14"      # 14>12 → M/D/Y
    assert LK._parse_date("20 September 2019") == "2019-09-20"
    assert LK._parse_date("September 20, 2019") == "2019-09-20"
    assert LK._parse_date("05/06/1991") is None              # ambiguous → unparsed
    assert LK._parse_date("1234567") is None                 # not a date
    assert LK._parse_date("13/13/1990") is None              # invalid


# --- the credence grammar -----------------------------------------------------------------

def test_grammar_templates_all_render() -> None:
    # drift gate: every template formats with its declared slots
    LK.GRAMMAR["report"].format(value="v", p=0.5, cites="[1]")
    LK.GRAMMAR["report_scoped"].format(value="v", as_of="2019-01-01", p=0.5, cites="[1]")
    LK.GRAMMAR["hedge"].format(alts="a")
    LK.GRAMMAR["ask_clarify"].format(alts="a")
    LK.GRAMMAR["abstain"].format(reason="r")
    LK.GRAMMAR["abstain_withheld"].format(reason="r", alts="a")
    LK.GRAMMAR["footer"].format(n_hits=1, n_obs=1, n_ind=0, p_none=0.1,
                                action="report", eu=0.5)
    LK.GRAMMAR["fallthrough"].format(reason="r")
    LK.GRAMMAR["origin_documents"].format()
    LK.GRAMMAR["origin_rung"].format(rung="deliberate@m", n_hits=3)
    LK.GRAMMAR["origin_declined"].format(reason="r")
    # the fallback_lane templates were removed at §13 adoption (honest-withhold-only)
    assert "fallback_lane" not in LK.GRAMMAR and "fallback_lane_failed" not in LK.GRAMMAR


MODEL_YAML = """\
format_version: 1
gauge: {u_correct: 1.0, u_abstain: 0.0}
latents:
  u_wrong:    {grid: {lo: -10.0, hi: 0.0, n: 11}, prior: {type: gaussian, mu: -4.0, sigma: 3.0}}
  u_wrong_scoped: {grid: {lo: -6.0, hi: 0.0, n: 7}, prior: {type: gaussian, mu: -2.0, sigma: 1.0}}
  u_hedged:   {grid: {lo: -1.0, hi: 1.0, n: 5},  prior: {type: gaussian, mu: 0.4, sigma: 0.4}}
  lambda_int: {grid: {lo: -0.5, hi: 4.0, n: 10}, prior: {type: gaussian, mu: 1.0, sigma: 1.0}}
  kappa_att:  {grid: {lo: -0.2, hi: 1.0, n: 7},  prior: {type: gaussian, mu: 0.05, sigma: 0.1}}
  lambda_usd: {grid: {lo: 0.0, hi: 8.0, n: 9},   prior: {type: gaussian, mu: 1.0, sigma: 1.0}}
tau: {grid: {lo: 0.5, hi: 2.0, n: 4}, prior: {type: gaussian, mu: 1.0, sigma: 0.5}}
endpoint_mass_warn: 0.01
"""


# --- r30 step 2: current_u_bar shapes per question and folds the posterior ONCE -----------

def test_current_u_bar_defaults_to_the_anchor_shape(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    model_path = tmp_path / "model.yaml"
    model_path.write_text(MODEL_YAML, encoding="utf-8")
    monkeypatch.setattr(config, "UTILITY_MODEL", model_path)
    monkeypatch.setattr(config, "UTILITY_ELICITATIONS", tmp_path / "elicit.jsonl")
    monkeypatch.setattr(LK, "_U_BAR_RAW", None)
    monkeypatch.setattr(LK, "_U_BAR_SHAPED", {})
    u_bar, _version, policy = LK.current_u_bar()
    assert policy == LK.U_BAR_POLICY
    assert u_bar == LK.current_u_bar(shape="exact")[0]


def test_current_u_bar_folds_the_posterior_once_across_shapes(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    model_path = tmp_path / "model.yaml"
    model_path.write_text(MODEL_YAML, encoding="utf-8")
    monkeypatch.setattr(config, "UTILITY_MODEL", model_path)
    monkeypatch.setattr(config, "UTILITY_ELICITATIONS", tmp_path / "elicit.jsonl")
    monkeypatch.setattr(LK, "_U_BAR_RAW", None)
    monkeypatch.setattr(LK, "_U_BAR_SHAPED", {})
    folds: list[int] = []
    real_posterior = LK.UT.posterior

    def _counting(*args, **kwargs):
        folds.append(1)
        return real_posterior(*args, **kwargs)

    monkeypatch.setattr(LK.UT, "posterior", _counting)
    LK.current_u_bar(shape="exact")
    assert len(folds) == 1
    LK.current_u_bar(shape="quantity")  # a DIFFERENT shape, same fold_version
    # the raw posterior is memoised per fold_version — a second SHAPE must not re-fold it;
    # only decide.shaped_u_bar's cheap host arithmetic runs again.
    assert len(folds) == 1


def test_current_u_bar_undeclared_scales_give_the_same_u_bar_for_every_shape(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # MODEL_YAML declares none of the six optional latents — every shape must read
    # byte-identically until the owner's file opts one in (C4/C10's no-op claim).
    model_path = tmp_path / "model.yaml"
    model_path.write_text(MODEL_YAML, encoding="utf-8")
    monkeypatch.setattr(config, "UTILITY_MODEL", model_path)
    monkeypatch.setattr(config, "UTILITY_ELICITATIONS", tmp_path / "elicit.jsonl")
    monkeypatch.setattr(LK, "_U_BAR_RAW", None)
    monkeypatch.setattr(LK, "_U_BAR_SHAPED", {})
    from life_agent.core import answer_shape as AS
    exact, version_e, _ = LK.current_u_bar(shape="exact")
    for shape in AS.SCALED_SHAPES:
        shaped, version_s, _ = LK.current_u_bar(shape=shape)
        assert shaped == exact
        assert version_s == version_e


# --- confirm (value-targeted independent confirmation — §14 confirm_indep) ----------------

def test_confirm_prefilter_is_independence_and_carrier_gated() -> None:
    hits = [_hit("home", "the fee is 1,234,567 due at signing"),
            _hit("indep", "schedule total: fee is 1,234,567 confirmed"),
            _hit("noise", "an unrelated paragraph with no figures")]
    picked = LK.confirm_prefilter("1,234,567", hits, {"home"})
    # supporter excluded, non-carrier excluded, original hit index preserved
    assert [(i, h["artifact_cache_key"]) for i, h in picked] == [(1, "indep")]


def test_confirm_hits_grounded_confirm_becomes_observation(migrated_root: Path) -> None:
    client = FakeClient({"confirms": True, "quote": "fee is 1,234,567 confirmed"})
    hits = [_hit("home", "the fee is 1,234,567 due at signing"),
            _hit("indep", "schedule total: fee is 1,234,567 confirmed",
                 origin="/mail/cur/msg.eml")]  # PII-OK: synthetic maildir
    obs, indet = LK.confirm_hits(migrated_root, "what is the fee?", "1,234,567", hits,
                                 exclude_artifacts={"home"}, client=client)
    assert indet == 0 and client.calls == 1  # the supporter is never even attempted
    (o,) = obs
    assert o.artifact_cache_key == "indep"
    assert o.card_n == 2                      # citation card = original hit position
    assert o.value_norm == LK._norm_value("1,234,567")
    assert o.authority_class == "email"       # its OWN covariates, no hand-set 1.0
    assert o.competition_factor == 1.0


def test_confirm_hits_decline_and_ungrounded_are_indeterminate(migrated_root: Path) -> None:
    # decline honoured: confirms false ⇒ no observation, counted
    client = FakeClient({"confirms": False})
    hits = [_hit("indep", "schedule total: fee is 1,234,567 confirmed")]
    obs, indet = LK.confirm_hits(migrated_root, "what is the fee?", "1,234,567", hits,
                                 exclude_artifacts=set(), client=client)
    assert obs == [] and indet == 1
    # ungrounded: token-boundary prefilter passes ("1 234 567" tokenizes to the value)
    # but neither the hallucinated quote nor the exact value string is in the chunk
    client2 = FakeClient({"confirms": True, "quote": "fee is 1,234,567"})
    hits2 = [_hit("indep2", "totals fee 1 234 567 end")]
    obs2, indet2 = LK.confirm_hits(migrated_root, "what is the fee?", "1,234,567", hits2,
                                   exclude_artifacts=set(), client=client2)
    assert obs2 == [] and indet2 == 1


def test_confirm_hits_warm_replay_makes_no_calls(migrated_root: Path) -> None:
    client = FakeClient({"confirms": True, "quote": "fee is 1,234,567 confirmed"})
    hits = [_hit("indep", "schedule total: fee is 1,234,567 confirmed")]
    for _ in range(2):
        obs, _ = LK.confirm_hits(migrated_root, "what is the fee?", "1,234,567", hits,
                                 exclude_artifacts=set(), client=client)
        assert len(obs) == 1
    assert client.calls == 1  # second pass replays the §18.9 record


def test_confirm_hits_own_competition_factor_never_inherited(migrated_root: Path) -> None:
    # the confirming chunk carries a same-shape competitor beside the quote — the
    # observation enters tempered by ITS OWN quote window (§2: competition is a
    # property of the corpus row), regardless of any candidate_competition upstream
    client = FakeClient({"confirms": True, "quote": "totals: 1,234,567"})
    hits = [_hit("indep", "totals: 1,234,567 (previous figure 7,654,321)")]
    obs, _ = LK.confirm_hits(migrated_root, "what is the fee?", "1,234,567", hits,
                             exclude_artifacts=set(), client=client)
    (o,) = obs
    assert o.n_competing >= 1 and o.competition_factor == 0.5


def test_confirm_hits_m_bounds_spend(migrated_root: Path) -> None:
    client = FakeClient({"confirms": True, "quote": "fee is 1,234,567"})
    hits = [_hit(f"indep{i}", f"copy {i}: fee is 1,234,567 stated") for i in range(4)]
    obs, _ = LK.confirm_hits(migrated_root, "what is the fee?", "1,234,567", hits,
                             exclude_artifacts=set(), client=client, m=2)
    assert client.calls == 2 and len(obs) == 2  # first-in-hit-order, spend bounded


def test_confirm_hits_meter_accrues_cold_calls_only(migrated_root: Path) -> None:
    class PricedClient(FakeClient):
        def complete(self, prompt: str, schema: dict[str, Any]) -> ModelResponse:
            r = super().complete(prompt, schema)
            return dataclasses.replace(r, cost_usd=0.002)

    client = PricedClient({"confirms": True, "quote": "fee is 1,234,567 stated"})
    hits = [_hit("indep", "copy: fee is 1,234,567 stated")]
    meter: list[float] = []
    LK.confirm_hits(migrated_root, "what is the fee?", "1,234,567", hits,
                    exclude_artifacts=set(), client=client, meter=meter)
    LK.confirm_hits(migrated_root, "what is the fee?", "1,234,567", hits,
                    exclude_artifacts=set(), client=client, meter=meter)
    assert meter == [0.002]  # the warm replay appends nothing
