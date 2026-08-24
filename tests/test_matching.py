"""matching.numeric_spans / competing_value_count — the competing-values detector.

The §14 wrong-commit class (2026-08-17, runs 7/8): a chunk that carries a SECOND value of
the same numeric shape as the extracted one (q2-090's two dollar figures, q2-105's fax/tel
row, q2-053's two-era percentages). The detector is pure, host-side and model-free; its
count feeds ``lookup.competition_factor`` (the §4.2 competition term at the terminal).
"""
from __future__ import annotations

from life_agent.core import matching as M
from life_agent.core.matching import competing_value_count, numeric_spans


def test_numeric_spans_keep_grouped_numbers_whole() -> None:
    # commas/dots join digits into ONE span — "$1,234,567" is a 7-digit shape, not three
    # 1-3 digit fragments (the FTS tokenizer splits on commas; the detector must not).
    assert numeric_spans("$1,234,567") == ["1,234,567"]
    assert numeric_spans("74.2%") == ["74.2"]
    # spaces break spans (adjacent spreadsheet columns never merge)
    assert numeric_spans("(852) 5550 0143") == ["852", "5550", "0143"]  # PII-OK
    assert numeric_spans("no digits here") == []


def test_q2_090_shape_two_dollar_figures_compete() -> None:
    chunk = "Total prize money $1,234,567 for the season; career total $7,654,321 listed."
    assert competing_value_count("$1,234,567", chunk) == 1


def test_q2_105_shape_fax_and_tel_in_one_row_compete() -> None:
    chunk = "Ms A. EXAMPLE  Tel: (852) 5550 0143  Fax: (852) 5550 0187"  # PII-OK
    # the fax's two 4-digit spans are distinct competing canons for the tel value
    assert competing_value_count("(852) 5550 0143", chunk) >= 1  # PII-OK: synthetic phone shape


def test_percent_class_competes_across_digit_counts() -> None:
    # q2-053's two-era pair: 74.2% and 97% differ in digit count — the percent class
    # matches them anyway.
    chunk = "Partial coverage in Sep 2025 (74.2%); as of 30 Mar it is now at 97%."
    assert competing_value_count("97%", chunk) >= 1
    assert competing_value_count("74.2%", chunk) >= 1


def test_repeats_of_the_same_figure_never_compete() -> None:
    chunk = "prize $1,234,567 … again $1,234,567 … and $1,234,567 " * 6
    assert competing_value_count("$1,234,567", chunk) == 0


def test_format_variants_of_one_value_collapse() -> None:
    # same canon (digits, leading zeros stripped) — a format variant is not a competitor
    assert competing_value_count("1,234,567", "total 1234567 HKD") == 0
    assert competing_value_count("042", "value 42 recorded") == 0


def test_different_shape_adjacency_does_not_compete() -> None:
    # the q-011 fix, kept: an expiry date's 2- and 4-digit spans beside a 6-digit id
    chunk = "Passport number PL-900001, expires 23 May 2032"
    assert competing_value_count("PL-900001", chunk) == 0


def test_digit_free_values_have_no_shape() -> None:
    assert competing_value_count("Alice Cohen", "Alice Cohen and Bob Levi, 42 St") == 0


def test_many_distinct_same_shape_values_count_high() -> None:
    figures = ", ".join(f"$1,{i:03d},000" for i in range(20))
    assert competing_value_count("$1,000,000", figures) == 19


def test_correction_sentence_competes_same_shape_successor() -> None:
    # the bridge's correction-shaped-read case, now on the shared span detector
    assert competing_value_count(
        "PL-900001", "PL-900001 was renewed; the new number is PL-800002") == 1


# ── r09d D1: the entity anchor's detector (pure, model-free) ─────────────────────────────
# The r09c wire class: an observation carries a value but not the qualifier that says what
# the value is OF (a class-scoped question answered with the file-scoped row; a fax question
# answered with the telephone beside it). The discriminating terms are computed FROM the
# channel — a question token that some window carries and another does not — so the rule is
# relative by construction and never fires when no window separates them.

def test_quote_window_is_the_quote_plus_the_frozen_margin() -> None:
    chunk = "x" * 400 + "THE QUOTE" + "y" * 400
    win = M.quote_window(chunk, "THE QUOTE")
    assert "THE QUOTE" in win
    assert len(win) == len("THE QUOTE") + 2 * M._QUOTE_MARGIN
    assert "x" * 200 not in win


def test_quote_window_falls_back_to_the_quote_then_the_chunk() -> None:
    assert M.quote_window("a chunk", "a quote not present") == "a quote not present"
    assert M.quote_window("a chunk", "") == "a chunk"


def test_discriminating_terms_are_present_in_one_window_and_absent_from_another() -> None:
    terms = M.discriminating_terms(
        "What is the statement coverage for the TaskRequest class?",
        ["TaskRequest class 100.00%", "the file total 0.00%"])
    assert "taskrequest" in terms


def test_discriminating_terms_drop_a_term_every_window_carries() -> None:
    terms = M.discriminating_terms(
        "What is the coverage for the TaskRequest class?",
        ["coverage TaskRequest", "coverage total"])
    assert "coverage" not in terms


def test_discriminating_terms_drop_a_term_no_window_carries() -> None:
    terms = M.discriminating_terms(
        "What is the coverage percentage for the TaskRequest class?",
        ["TaskRequest 100.00", "the file total 0.00"])
    assert "percentage" not in terms


def test_discriminating_terms_drop_stopwords_and_short_tokens() -> None:
    terms = M.discriminating_terms(
        "Which fax did they list?", ["fax 1234", "tel 5678"])
    assert "which" not in terms and "did" not in terms
    assert "fax" in terms


def test_discriminating_terms_keep_first_seen_question_order() -> None:
    terms = M.discriminating_terms(
        "beta alpha gamma", ["alpha", "beta gamma"])
    assert terms == ("beta", "alpha", "gamma")


def test_anchor_score_counts_token_boundary_hits_not_substrings() -> None:
    assert M.anchor_score("the TaskRequest class", ("taskrequest",)) == 1
    # substring-only: the term must not match inside a longer token
    assert M.anchor_score("TaskRequestBuilder", ("taskrequest",)) == 0
    assert M.anchor_score("fax 1234 tel 5678", ("fax", "tel")) == 2


def test_quote_scoped_competitors_uses_the_shared_window() -> None:
    # one window definition (§6.8): a competitor OUTSIDE the margin does not count
    chunk = "value 1234" + "z" * 400 + "other 5678"
    assert M.quote_scoped_competitors("1234", chunk, "value 1234") == 0
    near = "value 1234 and other 5678"
    assert M.quote_scoped_competitors("1234", near, "value 1234") == 1


def test_anchor_window_is_the_whole_document_not_the_value_neighbourhood() -> None:
    # r09d ruling 1: the entity qualifier is a DOCUMENT-level property — a subject named in a
    # header far from the value still anchors it. The competition term keeps the ±120 window
    # (a competing value must be adjacent to compete); the anchor does not.
    chunk = "ACME HOLDINGS LIMITED annual return" + "z" * 500 + "Company Number 1234567"
    assert M.anchor_window(chunk, "Company Number 1234567") == chunk
    assert "acme" not in M.tokenize(M.quote_window(chunk, "Company Number 1234567"))
    assert "acme" in M.tokenize(M.anchor_window(chunk, "Company Number 1234567"))
