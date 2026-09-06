"""ATM-Bench's deterministic number matcher — ``_deterministic_accuracy_core`` and
``deterministic_accuracy`` from ``memqa/utils/evaluator/evaluate_qa.py`` (lines 181–307 at the
pinned sha) together with the four date/token helpers the core calls that live in that file
(lines 145–178: ``date_component_match``, ``date_token_match``, ``dates_match``,
``tokens_match``). Copied as exact line slices; only the imports below are ours — none of
upstream's ``requests``/``openai``/``tqdm``/``EVALUATOR_CONFIG`` (the LLM-judge path). See SOURCE.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import List, Optional

from .normalizer import (
    aggressive_preprocess,
    extract_codes,
    extract_currency_amounts,
    extract_dates,
    extract_numbers,
    extract_reference_date,
    extract_times,
    is_abstention,
    location_token_match,
    normalize_between_to_range,
    normalize_currency_codes,
    normalize_text,
    remove_date_time_text,
    resolve_relative_dates,
    semantic_units_match,
    split_list_items,
    strip_context_phrases,
    strip_currency_breakdowns,
    strip_leading_articles,
    strip_parenthetical_details,
    token_subset_match,
)


def date_component_match(gt: str, pred: str) -> bool:
    if len(gt) == 4 or len(pred) == 4:
        return gt[-4:] == pred[-4:]
    return gt == pred


def date_token_match(gt_token: str, pred_token: str) -> bool:
    if "-" in gt_token:
        if "-" not in pred_token:
            return False
        gt_start, gt_end = gt_token.split("-", 1)
        pred_start, pred_end = pred_token.split("-", 1)
        return date_component_match(gt_start, pred_start) and date_component_match(
            gt_end, pred_end
        )
    return date_component_match(gt_token, pred_token)


def dates_match(gt_tokens: List[str], pred_tokens: List[str]) -> bool:
    remaining = list(pred_tokens)
    for gt_token in gt_tokens:
        matched = False
        for idx, pred_token in enumerate(remaining):
            if date_token_match(gt_token, pred_token):
                matched = True
                remaining.pop(idx)
                break
        if not matched:
            return False
    return True


def tokens_match(expected: List, actual: List) -> bool:
    return Counter(expected) == Counter(actual)


def _deterministic_accuracy_core(
    ground_truth: str, prediction: str, question: Optional[str] = None
) -> tuple[bool, str]:
    is_abst_gt = is_abstention(ground_truth)
    is_abst_pred = is_abstention(prediction)

    reference_date = extract_reference_date(question or "")
    ground_truth_resolved = resolve_relative_dates(ground_truth, reference_date)
    prediction_resolved = resolve_relative_dates(prediction, reference_date)

    ground_truth_prep = aggressive_preprocess(ground_truth_resolved)
    prediction_prep = aggressive_preprocess(prediction_resolved)

    ground_truth_clean = strip_parenthetical_details(ground_truth_prep)
    prediction_clean = strip_parenthetical_details(prediction_prep)

    ground_truth_clean = strip_currency_breakdowns(ground_truth_clean)
    prediction_clean = strip_currency_breakdowns(prediction_clean)

    ground_truth_clean = normalize_between_to_range(ground_truth_clean)
    prediction_clean = normalize_between_to_range(prediction_clean)

    ground_truth_clean = strip_leading_articles(ground_truth_clean)
    prediction_clean = strip_leading_articles(prediction_clean)

    gt_normalized = normalize_text(ground_truth_clean)
    pred_normalized = normalize_text(prediction_clean)

    if is_abst_gt or is_abst_pred:
        return (is_abst_gt and is_abst_pred, pred_normalized)

    gt_codes = extract_codes(ground_truth_clean)
    if gt_codes:
        pred_upper = prediction_clean.upper()
        pred_stripped = re.sub(
            r"\b(?:CODE|ID|REFERENCE|REF|NUMBER|NUM|LABEL):\s*", "", pred_upper
        )
        if not all(code in pred_stripped for code in gt_codes):
            return False, pred_normalized

    gt_dates = [token.value for token in extract_dates(ground_truth_clean)]
    pred_dates = [token.value for token in extract_dates(prediction_clean)]

    if gt_dates:
        if not pred_dates:
            return False, pred_normalized
        if not dates_match(gt_dates, pred_dates):
            return False, pred_normalized

    gt_times = [token.value for token in extract_times(ground_truth_clean)]
    pred_times = [token.value for token in extract_times(prediction_clean)]
    if gt_times and pred_times:
        if not tokens_match(gt_times, pred_times):
            return False, pred_normalized

    if gt_dates or gt_times:
        gt_remainder = normalize_text(remove_date_time_text(ground_truth_clean))
        pred_remainder = normalize_text(remove_date_time_text(prediction_clean))

        gt_remainder_stripped = strip_context_phrases(gt_remainder)
        pred_remainder_stripped = strip_context_phrases(pred_remainder)

        if not gt_remainder_stripped:
            return True, pred_normalized
        if token_subset_match(gt_remainder_stripped, pred_remainder_stripped):
            return True, pred_normalized

    gt_clean = remove_date_time_text(ground_truth_clean)
    pred_clean = remove_date_time_text(prediction_clean)
    gt_numbers, gt_currencies = extract_numbers(gt_clean)
    pred_numbers, pred_currencies = extract_numbers(pred_clean)
    gt_currency_amounts = extract_currency_amounts(gt_clean)
    pred_currency_amounts = extract_currency_amounts(pred_clean)

    if gt_currencies:
        gt_norm = normalize_currency_codes(gt_currencies)
        pred_norm = normalize_currency_codes(pred_currencies)
        if pred_norm and not tokens_match(gt_norm, pred_norm):
            return False, pred_normalized

    if gt_currency_amounts:
        if not pred_currency_amounts:
            return False, pred_normalized
        if not tokens_match(gt_currency_amounts, pred_currency_amounts):
            return False, pred_normalized
        gt_numbers = [num for num in gt_numbers if num not in gt_currency_amounts]
        pred_numbers = [num for num in pred_numbers if num not in pred_currency_amounts]

    if gt_numbers:
        if not pred_numbers:
            return False, pred_normalized
        if not tokens_match(gt_numbers, pred_numbers):
            return False, pred_normalized

    gt_items = split_list_items(ground_truth_clean)
    if len(gt_items) >= 2:
        if not all(item in pred_normalized for item in gt_items):
            return False, pred_normalized
        return True, pred_normalized

    if gt_normalized.startswith("yes") or gt_normalized.startswith("no"):
        if pred_normalized in {"yes", "no"}:
            return gt_normalized.startswith(pred_normalized), pred_normalized

    if location_token_match(ground_truth_clean, prediction_clean):
        return True, pred_normalized

    if len(gt_normalized) >= 3 and gt_normalized in pred_normalized:
        return True, pred_normalized

    if len(pred_normalized) >= 3 and pred_normalized in gt_normalized:
        return True, pred_normalized

    if token_subset_match(ground_truth_clean, prediction_clean):
        return True, pred_normalized

    # Final fallback: semantic units match
    if semantic_units_match(ground_truth_clean, prediction_clean):
        return True, pred_normalized

    return gt_normalized == pred_normalized, pred_normalized


def deterministic_accuracy(
    ground_truth: str, prediction: str, question: Optional[str] = None
) -> bool:
    return _deterministic_accuracy_core(ground_truth, prediction, question)[0]
