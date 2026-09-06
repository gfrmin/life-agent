"""r51b (2e) — ATM-Bench's evaluator, vendored at a pinned sha (`scripts/atm_bench/vendored/`).

The verdict on the external corpus is the benchmark's OWN matcher, never the harness's
token-run substring rule (r51 pre-registration, `GD-30` (1)): a substring matcher on dates and
currency manufactures false "wrong"s, and every false wrong lowers a cell's realised rate while
leaving `p1` untouched — a bias toward the very branch that posts evidence upstream.

A copy is a copy. The upstream originals' sha256 are recorded in `SOURCE`; the vendored files
are pinned here; and for the two copied modules the ONLY edit is the import path — reversing
that rewrite must reproduce the upstream bytes exactly. Code is MIT (`LICENSE-ATM-Bench`),
compatible with this repo's AGPL with the notice kept.
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import atm_bench.vendored as V  # noqa: E402

VENDORED = ROOT / "scripts" / "atm_bench" / "vendored"
UPSTREAM_SHA = "ef4e5dff1a47ec71213a06e359f02753defa8fb1"  # JingbiaoMei/ATM-Bench, = HEAD of main
UPSTREAM_SHA256 = {
    "memqa/utils/evaluator/normalizer.py":
        "1980cce4fbd572d11d2317725cb955d99cf55cf20e8645cd4ba6908fbdcf0e3d",
    "memqa/utils/evaluator/qtype_utils.py":
        "9186fe0f409b99384a0d78c988d1dbdfd66a74546f254ce1f1ed46e3cc115518",
    "memqa/utils/evaluator/evaluate_qa.py":
        "0581963c1c6b9729398d8007f3d40664b2c026499c9cbf0436a92f77dcb1b66e",
    "memqa/utils/evaluator/config.py":
        "2a72ab0c4b18a31570bcfe014d877dac3be648de85393d67f0b09d3e6b9fc179",
    "LICENSE":
        "e0de4445f9fdc0a5189592d7c97c6de1add6b63887fe7110509fc7957b7bcf1f",
}
# the post-rewrite pins — a copy is a copy, and the rewrite is exactly the diff named
VENDORED_SHA256 = {
    "normalizer.py": "94ea230f8175b5a595b25ca863f2040bdb13b4ccb83a4850d852438db8e546cf",
    "qtype_utils.py": "4496c003de8a2d71bc4f10b245b9e0f2902764fdb45143e9c1783a0a9703faf3",
    "abstention.py": "a8745b2020992a942843d9bdf38a43efc534ee0ccdf1bbe590f2f5529f8f3a75",
    "matcher.py": "b2fcb976c1b678c29cc57560f8cc4de423f39e62255319c0d1bfe4349a3343c7",
    "LICENSE-ATM-Bench": UPSTREAM_SHA256["LICENSE"],
}
# the one edit, per copied module: (vendored spelling, upstream spelling)
REWRITE = {
    "normalizer.py": ("from .abstention import ABSTENTION_PHRASES",
                      "from memqa.utils.evaluator.config import ABSTENTION_PHRASES"),
    "qtype_utils.py": ("from .normalizer import (",
                       "from memqa.utils.evaluator.normalizer import ("),
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --- the public surface, on synthetic ATM-Bench-shaped values -----------------------------
# PII-OK: every value in this file is synthetic (invented dates, amounts, ids and phrases)


def test_detect_qtype_number_on_date_currency_and_count() -> None:
    assert V.detect_qtype("14 December 2023") == "number"
    assert V.detect_qtype("$1,250") == "number"
    assert V.detect_qtype("3") == "number"


def test_detect_qtype_open_on_place_name_and_on_a_count_with_a_noun() -> None:
    # gradeability is a property of the ANSWER: a bare count is a number, a count with a
    # noun is prose — the benchmark's own rule, the reason the lane regex cannot decide it
    assert V.detect_qtype("the lakeside cabin") == "open_end"
    assert V.detect_qtype("3 apples") == "open_end"


def test_detect_qtype_list_recall_is_an_evidence_id_list() -> None:
    # PII-OK: synthetic ATM-Bench email ids (12 digits by the benchmark's own pattern)
    assert V.detect_qtype("email000000000001, email000000000002") == "list_recall"
    assert V.detect_qtype("apples, pears, plums") == "open_end"


def test_is_abstention_phrases() -> None:
    assert V.is_abstention("Unknown")
    assert V.is_abstention("There is no evidence of that")
    assert not V.is_abstention("14 December 2023")
    assert len(V.ABSTENTION_PHRASES) == 7  # upstream count at the pinned sha, typo-duplicate kept


def test_number_match_resolves_relative_date_from_the_today_anchor() -> None:
    q = "Today is 2024-03-10. When did the parcel arrive?"
    assert V.atm_number_match("2024-03-09", "yesterday", q)
    assert not V.atm_number_match("2024-03-09", "yesterday", "When did the parcel arrive?")


def test_number_match_iso_vs_long_date() -> None:
    assert V.atm_number_match("14 December 2023", "2023-12-14", None)
    assert not V.atm_number_match("14 December 2023", "2023-12-15", None)


def test_number_match_parenthetical_breakdown_stripped() -> None:
    assert V.atm_number_match("$1,250", "$1,250 (deposit $250 + balance $1,000)", None)


def test_number_match_code_must_appear_exactly() -> None:
    assert V.atm_number_match("Booking reference ABC123", "ABC123", None)
    assert not V.atm_number_match("Booking reference ABC123", "ABC124", None)


def test_number_match_is_not_a_substring_rule() -> None:
    assert not V.atm_number_match("12", "123", None)
    assert V.atm_number_match("12", "12", None)


def test_number_match_abstention_matches_only_abstention() -> None:
    assert V.atm_number_match("unknown", "no information available", None)
    assert not V.atm_number_match("14 December 2023", "unknown", None)


# --- a copy is a copy ---------------------------------------------------------------------


def test_vendored_files_match_pinned_sha256() -> None:
    for name, pin in VENDORED_SHA256.items():
        assert _sha((VENDORED / name).read_bytes()) == pin, name


def test_reversing_the_import_rewrite_reproduces_the_upstream_bytes() -> None:
    """The ONLY edit to a copied module is its import path: putting the upstream spelling
    back must hash to the upstream original recorded in SOURCE."""
    for name, (ours, theirs) in REWRITE.items():
        text = (VENDORED / name).read_text(encoding="utf-8")
        assert text.count(ours) == 1, f"{name}: the rewritten import must appear exactly once"
        restored = text.replace(ours, theirs)
        assert _sha(restored.encode("utf-8")) == UPSTREAM_SHA256[f"memqa/utils/evaluator/{name}"]


def test_source_records_the_upstream_sha_and_every_original_hash() -> None:
    src = (VENDORED / "SOURCE").read_text(encoding="utf-8")
    assert UPSTREAM_SHA in src
    for path, digest in UPSTREAM_SHA256.items():
        assert path in src and digest in src, path


def test_no_network_or_judge_dependency_in_the_vendored_package() -> None:
    """`evaluate_qa.py` imports requests/openai/tqdm for the LLM judge; the extraction must not."""
    for p in VENDORED.glob("*.py"):
        text = p.read_text(encoding="utf-8")
        assert not re.search(r"^\s*(import|from)\s+(requests|openai|tqdm|memqa)\b", text, re.M), p.name
