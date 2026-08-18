"""matching.numeric_spans / competing_value_count — the competing-values detector.

The §14 wrong-commit class (2026-08-17, runs 7/8): a chunk that carries a SECOND value of
the same numeric shape as the extracted one (q2-090's two dollar figures, q2-105's fax/tel
row, q2-053's two-era percentages). The detector is pure, host-side and model-free; its
count feeds ``lookup.competition_factor`` (the §4.2 competition term at the terminal).
"""
from __future__ import annotations

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
