"""Unit tests for the fair-fight grading composition (scripts/fairfight/grading.py).

Hermetic: no real DuckDB connection. ``_answer_in_corpus`` is imported by name from
``run_eval`` into ``grading`` (matching the established ``eval_executor.py`` /
``triage_answers.py`` cross-script import pattern), so an autouse fixture monkeypatches
``grading._answer_in_corpus`` to a stub for every test (default: nothing found in the
corpus); individual tests override it when they need "gold IS in the corpus" without
being in top-k. ``conn`` is a sentinel that raises on any attribute access, so an
unmocked real DB call fails loudly instead of hanging.

Run from the repo root:
    uv run --project . python -m pytest ./tests/test_fairfight_grading.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from fairfight import grading as G


class _Conn:
    """A conn sentinel: any attribute access is a bug (an unmocked DB call)."""

    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"unexpected access to conn.{name} — mock _answer_in_corpus instead")


@pytest.fixture(autouse=True)
def _corpus_absent_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(G, "_answer_in_corpus", lambda conn, answer, variants: False)


def _q(**overrides: object) -> dict:
    base: dict = dict(
        id="q-001", question="what is my ID?", subject="n/a",
        answer="123456789", answer_variants=[], distractors=[],
        fuzzy=False, search_queries=[], mode_hint=None, notes="",
    )
    base.update(overrides)
    return base


# --- detect_decline ----------------------------------------------------------------


def test_detect_decline_not_in_corpus_prefix_line() -> None:
    assert G.detect_decline("NOT_IN_CORPUS: no such fact in the corpus")


def test_detect_decline_not_in_corpus_line_not_first() -> None:
    text = "Let me check the sources.\nNOT_IN_CORPUS: nothing found\n"
    assert G.detect_decline(text)


def test_detect_decline_not_in_corpus_requires_exact_prefix() -> None:
    # a mention of the marker mid-sentence is not the structural decline line
    assert not G.detect_decline("I looked but found NOT_IN_CORPUS somewhere in a doc.")


def test_detect_decline_ask_abstention_exact_match() -> None:
    from ask import ABSTENTION

    assert G.detect_decline(ABSTENTION)


def test_detect_decline_abstention_substring_alone_does_not_match() -> None:
    # a mere substring is not the exact-match check (#2) — pick a tail that also avoids
    # every fallback phrase (#3), unlike the ABSTENTION prefix ("I don't have a ...",
    # which legitimately trips the "don't have a" fallback and SHOULD be caught).
    from ask import ABSTENTION

    tail = ABSTENTION[ABSTENTION.index("the weak matches"):]
    assert not G.detect_decline(tail)


def test_detect_decline_phrase_not_in_the_corpus() -> None:
    assert G.detect_decline("That value is not in the corpus.")


def test_detect_decline_phrase_no_information_in() -> None:
    assert G.detect_decline("There is no information in your records about this.")


def test_detect_decline_phrase_i_dont_know() -> None:
    assert G.detect_decline("I don't know the answer to that.")
    assert G.detect_decline("i dont know")  # apostrophe-optional


def test_detect_decline_phrase_cannot_find() -> None:
    assert G.detect_decline("I cannot find that value anywhere.")


def test_detect_decline_phrase_dont_have_a_any_enough() -> None:
    assert G.detect_decline("I don't have a record of that.")
    assert G.detect_decline("I don't have any information here.")
    assert G.detect_decline("I don't have enough evidence to answer.")


def test_detect_decline_phrases_case_insensitive() -> None:
    assert G.detect_decline("NOT IN THE CORPUS.")
    assert G.detect_decline("I CANNOT FIND it.")


def test_detect_decline_plain_answer_does_not_decline() -> None:
    assert not G.detect_decline("Your ID number is 123456789.")


# near misses: phrases that must NOT trigger the fallback regexes -------------------


def test_near_miss_in_the_corpus_without_not() -> None:
    assert not G.detect_decline("This memo is filed in the corpus of legal precedents.")


def test_near_miss_information_present_without_no() -> None:
    assert not G.detect_decline("There is information in the attached statement.")


def test_near_miss_know_without_dont() -> None:
    assert not G.detect_decline("You should know this: the balance is 500.")


def test_near_miss_can_find_without_cannot() -> None:
    assert not G.detect_decline("You can find the invoice attached.")


def test_near_miss_have_enough_without_dont() -> None:
    assert not G.detect_decline("You have enough evidence already, the total is 500.")


def test_near_miss_dont_have_much_not_a_or_any_or_enough() -> None:
    assert not G.detect_decline("I don't have much time but the ID is 123456789.")


# --- hermes_citation_check -----------------------------------------------------------


def _rows(*source_paths: str) -> list[dict]:
    return [{
        "ts": "2026-07-11T00:00:00Z", "tool": "search", "args": {},
        "n_results": len(source_paths),
        "results": [{"source_path": p} for p in source_paths],
    }]


def test_hermes_citation_check_no_brackets_is_vacuously_true() -> None:
    assert G.hermes_citation_check("The answer is 42, no sources needed.", _rows("/tmp/a.txt"))


def test_hermes_citation_check_known_citation_matches_full_path() -> None:
    text = "Your ID is 123456789 [/tmp/corpus/id_card.txt]."
    assert G.hermes_citation_check(text, _rows("/tmp/corpus/id_card.txt"))


def test_hermes_citation_check_known_citation_matches_basename() -> None:
    text = "Your ID is 123456789 [id_card.txt]."
    assert G.hermes_citation_check(text, _rows("/tmp/corpus/id_card.txt"))


def test_hermes_citation_check_unknown_citation_fails() -> None:
    text = "Your ID is 123456789 [/tmp/corpus/other.txt]."
    assert not G.hermes_citation_check(text, _rows("/tmp/corpus/id_card.txt"))


def test_hermes_citation_check_comma_separated_bracket() -> None:
    text = "See [/tmp/a.txt, /tmp/b.txt] for details."
    assert G.hermes_citation_check(text, _rows("/tmp/a.txt", "/tmp/b.txt"))


def test_hermes_citation_check_comma_separated_bracket_one_unknown() -> None:
    text = "See [/tmp/a.txt, /tmp/missing.txt] for details."
    assert not G.hermes_citation_check(text, _rows("/tmp/a.txt", "/tmp/b.txt"))


def test_hermes_citation_check_multiple_consecutive_brackets() -> None:
    text = "Confirmed [/tmp/a.txt][/tmp/b.txt]."
    assert G.hermes_citation_check(text, _rows("/tmp/a.txt", "/tmp/b.txt"))


def test_hermes_citation_check_empty_tool_log_with_citation_fails() -> None:
    assert not G.hermes_citation_check("Answer [/tmp/a.txt]", [])


def test_hermes_citation_check_empty_tool_log_no_citation_is_vacuously_true() -> None:
    assert G.hermes_citation_check("No sources cited here.", [])


def test_hermes_citation_check_tolerates_rows_without_results_key() -> None:
    rows = [{"ts": "t", "tool": "search", "args": {}, "n_results": 0, "error": "locked"}]
    assert not G.hermes_citation_check("Answer [/tmp/a.txt]", rows)
    assert G.hermes_citation_check("No citation here.", rows)


# --- grade_channels: free-text arms (decision_view=None), the competitor shape -------


def test_free_text_asserted_correct_is_correct_bucket() -> None:
    q = _q()
    gr = G.grade_channels(
        q, "Your ID is 123456789.", ["id card text 123456789"], None, _Conn())
    assert gr.declined is False
    assert gr.asserted is True
    assert gr.asserted_correct is True
    assert gr.bucket == "CORRECT"
    assert gr.cause is None
    assert gr.gold_in_topk is True
    assert gr.gold_in_candidates is None  # no candidate stage: never imputed
    assert gr.n_retrieved == 1


def test_free_text_asserted_wrong_value_is_confident_wrong() -> None:
    q = _q(answer="123456789")
    gr = G.grade_channels(
        q, "Your ID is 999999999.", ["id card text 123456789"], None, _Conn())
    assert gr.asserted is True
    assert gr.asserted_correct is False
    assert gr.bucket == "CONFIDENT_WRONG"
    assert gr.cause == "wrong_value"


def test_free_text_asserted_distractor_is_confident_wrong() -> None:
    q = _q(answer="123456789", subject="owner", distractors=["987654321"])
    gr = G.grade_channels(
        q, "Your ID is 987654321.", ["some unrelated chunk"], None, _Conn())
    assert gr.asserted_distractor is True
    assert gr.bucket == "CONFIDENT_WRONG"
    assert gr.cause == "distractor"


def test_free_text_declined_coverage_gap_is_rightly_withheld_but_not_flagged_correct() -> None:
    # answerable=True (a real gold value exists) and the arm declined, but the value never
    # reached the corpus at all: bucket/cause name it coverage_gap, while the SIMPLE
    # correct_abstention/over_abstention channel (binding formula) only fires for
    # genuinely-unanswerable questions / gold-was-reachable respectively — neither applies
    # here, by construction, not an oversight.
    q = _q()
    gr = G.grade_channels(q, "NOT_IN_CORPUS: no such record", [], None, _Conn())
    assert gr.declined is True
    assert gr.asserted is False
    assert gr.bucket == "RIGHTLY_WITHHELD"
    assert gr.cause == "coverage_gap"
    assert gr.correct_abstention is False
    assert gr.over_abstention is False


def test_free_text_declined_unanswerable_is_correct_abstention() -> None:
    q = _q(answer="", answer_variants=[])
    gr = G.grade_channels(q, "NOT_IN_CORPUS: nothing to say", [], None, _Conn())
    assert gr.declined is True
    assert gr.correct_abstention is True
    assert gr.over_abstention is False
    assert gr.bucket == "RIGHTLY_WITHHELD"
    assert gr.cause == "unanswerable"


def test_free_text_declined_but_gold_was_in_corpus_is_over_abstention(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(G, "_answer_in_corpus", lambda conn, answer, variants: True)
    q = _q(answer="123456789")
    gr = G.grade_channels(
        q, "NOT_IN_CORPUS: nothing to say", ["unrelated chunk"], None, _Conn())
    assert gr.declined is True
    assert gr.gold_in_corpus is True
    assert gr.over_abstention is True
    assert gr.correct_abstention is False
    assert gr.bucket == "WRONGLY_WITHHELD"
    assert gr.cause == "retrieval_miss"  # in corpus, but not in top-k (retrieved has no gold)


def test_free_text_gold_in_candidates_stored_none_but_fed_as_gold_in_topk_to_triage() -> None:
    # gold IS in top-k but the arm withheld it anyway (no NOT_IN_CORPUS marker, no assert
    # either -> falls to the fallback decline phrasing) -> WRONGLY_WITHHELD/pooling_loss,
    # never extraction_miss (that bucket structurally can't fire without a candidate stage).
    q = _q(answer="123456789")
    gr = G.grade_channels(
        q, "I don't know who this belongs to.", ["id card text 123456789"], None, _Conn())
    assert gr.gold_in_topk is True
    assert gr.gold_in_candidates is None
    assert gr.bucket == "WRONGLY_WITHHELD"
    assert gr.cause == "pooling_loss"


def test_free_text_distractor_in_topk_reported() -> None:
    q = _q(answer="123456789", subject="owner", distractors=["987654321"])
    gr = G.grade_channels(
        q, "NOT_IN_CORPUS: nothing found", ["a card mentioning 987654321"], None, _Conn())
    assert gr.distractor_in_topk is True


# --- grade_channels: decision_view arms (lookup/narrative/withheld shapes) -----------


def _lookup_view(**overrides: object) -> dict:
    base: dict = dict(
        family="lookup", construct="id_number", action="report", asserted=True,
        scoped=False, scoped_value=None, as_of=None,
        asserted_values=["123456789"], candidates=["123456789"],
        credences=[0.9], p_none=0.05, n_hits=1, n_indeterminate=0, observations=[],
    )
    base.update(overrides)
    return base


def _withheld_view(**overrides: object) -> dict:
    base: dict = {"family": None, "construct": None, "action": "abstain", "asserted": False,
                  "asserted_values": [], "candidates": [], "credences": [],
                  "p_none": None, "n_hits": None, "n_indeterminate": None, "observations": []}
    base.update(overrides)
    return base


def test_decision_view_asserted_correct_is_correct() -> None:
    q = _q(answer="123456789")
    gr = G.grade_channels(
        q, "Your ID is 123456789.", ["id card text 123456789"],
        _lookup_view(), _Conn())
    assert gr.asserted is True
    assert gr.asserted_correct is True
    assert gr.bucket == "CORRECT"
    assert gr.gold_in_candidates is True  # real candidate stage: never None here


def test_decision_view_asserted_wrong_is_confident_wrong() -> None:
    q = _q(answer="123456789")
    view = _lookup_view(asserted_values=["999999999"], candidates=["999999999"])
    gr = G.grade_channels(
        q, "Your ID is 999999999.", ["id card text 123456789"], view, _Conn())
    assert gr.bucket == "CONFIDENT_WRONG"
    assert gr.cause == "wrong_value"


def test_decision_view_scoped_is_scoped_never_confident_wrong() -> None:
    q = _q(answer="123456789")
    view = _lookup_view(
        action="report_scoped", asserted=False, scoped=True, scoped_value="999999999",
        asserted_values=["999999999"], candidates=["999999999"])
    gr = G.grade_channels(
        q, "As of 2020, your ID was 999999999.", ["id card text 123456789"], view, _Conn())
    assert gr.bucket == "SCOPED"
    assert gr.cause == "as_of_record"
    assert gr.declined is False


def test_decision_view_abstain_action_is_declined() -> None:
    q = _q(answer="123456789")
    gr = G.grade_channels(
        q, "I can't determine this.", ["id card text 123456789"], _withheld_view(), _Conn())
    assert gr.declined is True
    assert gr.asserted is False
    assert gr.gold_in_topk is True
    assert gr.gold_in_candidates is False  # real candidate stage exists (empty) -> False
    assert gr.bucket == "WRONGLY_WITHHELD"
    assert gr.cause == "extraction_miss"


def test_decision_view_ask_clarify_action_is_declined() -> None:
    q = _q(answer="123456789")
    view = _withheld_view(action="ask_clarify")
    gr = G.grade_channels(q, "Which record do you mean?", [], view, _Conn())
    assert gr.declined is True
    assert gr.correct_abstention is False  # answerable=True, gold never reached corpus
    assert gr.bucket == "RIGHTLY_WITHHELD"
    assert gr.cause == "coverage_gap"


def test_decision_view_extraction_miss_when_gold_in_topk_not_candidates() -> None:
    q = _q(answer="123456789")
    gr = G.grade_channels(
        q, "not sure", ["id card text 123456789"], _withheld_view(), _Conn())
    assert gr.gold_in_topk is True
    assert gr.gold_in_candidates is False  # real candidate stage exists (empty) -> False
    assert gr.bucket == "WRONGLY_WITHHELD"
    assert gr.cause == "extraction_miss"


def test_decision_view_pooling_loss_when_gold_in_candidates_but_withheld() -> None:
    q = _q(answer="123456789")
    view = _withheld_view(candidates=["123456789"])
    gr = G.grade_channels(
        q, "not sure", ["id card text 123456789"], view, _Conn())
    assert gr.gold_in_candidates is True
    assert gr.bucket == "WRONGLY_WITHHELD"
    assert gr.cause == "pooling_loss"


def test_decision_view_asserted_distractor_is_confident_wrong() -> None:
    q = _q(answer="123456789", subject="owner", distractors=["987654321"])
    view = _lookup_view(asserted_values=["987654321"], candidates=["987654321"])
    gr = G.grade_channels(q, "It's 987654321.", [], view, _Conn())
    assert gr.asserted_distractor is True
    assert gr.bucket == "CONFIDENT_WRONG"
    assert gr.cause == "distractor"


def test_decision_view_without_action_key_still_reads_as_declined(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # declined is DERIVED (not asserted and not scoped), never an action-name allowlist:
    # a view missing `action` entirely must not silently read declined=False while
    # asserted is also False — correct_abstention/over_abstention would then diverge
    # from the bucket channel forever.
    monkeypatch.setattr(G, "_answer_in_corpus", lambda conn, answer, variants: True)
    q = _q(answer="123456789")
    view = _withheld_view()
    del view["action"]
    gr = G.grade_channels(q, "…", ["unrelated chunk"], view, _Conn())
    assert gr.declined is True
    assert gr.asserted is False
    assert gr.bucket == "WRONGLY_WITHHELD"  # gold in corpus (mocked), not in top-k
    assert gr.cause == "retrieval_miss"
    assert gr.over_abstention is True  # consistent with the bucket, not silently False


def test_decision_view_future_withholding_action_name_reads_as_declined() -> None:
    # a hypothetical future family withholding under a new action name ("defer"):
    # asserted=False + scoped=False is what makes it a decline, not the name.
    q = _q(answer="", answer_variants=[])
    view = _withheld_view(action="defer")
    gr = G.grade_channels(q, "I'll defer on that.", [], view, _Conn())
    assert gr.declined is True
    assert gr.correct_abstention is True  # unanswerable + declined
    assert gr.bucket == "RIGHTLY_WITHHELD"


def test_decision_view_n_retrieved_counts_retrieved_texts() -> None:
    q = _q(answer="123456789")
    gr = G.grade_channels(q, "x", ["a", "b", "c"], _withheld_view(), _Conn())
    assert gr.n_retrieved == 3


def test_unanswerable_question_never_gold_in_topk_even_with_matching_text() -> None:
    # answerable=False (no gold value exists) -> retrieval channel is False by construction,
    # regardless of what's in the retrieved texts.
    q = _q(answer="", answer_variants=[])
    gr = G.grade_channels(q, "no info", ["totally unrelated chunk"], _withheld_view(), _Conn())
    assert gr.gold_in_topk is False
    assert gr.gold_in_corpus is False


def test_answerable_override_key_respected() -> None:
    # q["answerable"] explicitly False even though "answer" is non-empty (e.g. a stale
    # placeholder value kept for documentation) -> treated as unanswerable.
    q = _q(answer="123456789", answerable=False)
    gr = G.grade_channels(
        q, "NOT_IN_CORPUS: n/a", ["id card text 123456789"], None, _Conn())
    assert gr.correct_abstention is True
