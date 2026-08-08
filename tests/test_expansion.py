"""Hermetic tests for the native-script query expander (core.expansion).

`clean_terms` is pure (no model, no corpus): it flattens an LLM reply to a BM25 term string while
preserving Hebrew (the whole point — the Hebrew spelling is the discriminative term against a Hebrew
doc). The cache-key identity test pins that ask.py and the bridge share ONE expander + ONE cache
(the prompt template is the cache key, so a divergence would silently orphan recorded expansions).
"""
from __future__ import annotations

from life_agent.core import expansion as EXP


def test_clean_terms_preserves_hebrew_and_drops_punctuation() -> None:
    # a model reply with bullets/commas/quotes/newlines → a clean space-separated term string;
    # Hebrew word chars survive (the native-script terms are the lexical-gap bridge).
    raw = "income, salary;\n- 'invoice'  עוסק מורשה\nמשכורת."  # noqa: RUF001
    assert EXP.clean_terms(raw) == "income salary invoice עוסק מורשה משכורת"


def test_clean_terms_is_idempotent_on_clean_input() -> None:
    s = "arnona ארנונה עירייה bill"
    assert EXP.clean_terms(s) == s


def test_expander_is_single_source_shared_with_ask() -> None:
    # ask.py aliases the core constants, so the cache key (= the prompt template) is identical
    # and the
    # two read paths reuse one cache. A copy-paste divergence would break this.
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import ask
    assert ask.EXPAND_SYSTEM is EXP.EXPAND_SYSTEM
    assert ask.EXPAND_MODEL == EXP.EXPAND_MODEL
    assert ask._clean_terms is EXP.clean_terms


# --- issue #56: expander refusals must not become the BM25 query --------------------- #
# Observed live (Δ2 gate runs, 2026-08-06): on out-of-domain questions the expand model
# REFUSES, and the refusal prose flowed through clean_terms into the BM25 query. The fix
# is a pure refusal gate applied post-cache (the clean_terms seam), so cached refusal
# replies are re-gated on read and every caller falls back to the raw-question query.

OBSERVED_REFUSAL = ("I cannot help with this query. I'm a language model without access "
                    "to personal documents or files.")
REFUSAL_VARIANT = "I don't have access to personal information about individuals."


def test_refusal_detects_the_observed_boilerplate() -> None:
    assert EXP.refusal(OBSERVED_REFUSAL)


def test_refusal_detects_first_person_no_access_prose() -> None:
    assert EXP.refusal(REFUSAL_VARIANT)


def test_refusal_passes_keyword_expansions_through() -> None:
    # the prompt's own example outputs (incl. native-script Hebrew) and a bulleted reply
    for raw in (
        "income salary invoice contractor self-employed freelance fee earnings employer "
        "עוסק מורשה משכורת חשבונית",
        "arnona property-tax municipal rates bill ארנונה עירייה חשבון תשלום",
        "income, salary;\n- 'invoice'  עוסק מורשה\nמשכורת.",  # noqa: RUF001
    ):
        assert not EXP.refusal(raw)


def test_refusal_requires_first_person_not_just_markers() -> None:
    # a (contrived) keyword list sharing marker words is NOT a refusal — the detector is
    # conservative: first-person prose is the diagnostic, markers alone never fire.
    assert not EXP.refusal("cannot unable sorry apology complaint letter")


def test_clean_terms_flattens_a_refusal_to_empty() -> None:
    # '' is the existing fail-open contract: the caller falls back to the raw-question query.
    assert EXP.clean_terms(OBSERVED_REFUSAL) == ""


def test_cached_refusal_is_regated_on_read(tmp_path) -> None:
    # A refusal recorded BEFORE the gate existed must be re-gated on read (clean_terms is
    # post-cache by design) — no EXPAND_VERSION bump, no orphaned recordings, zero model calls
    # (the cache hit returns before anthropic_complete).
    import life_agent.core as C
    from life_agent.core import derivations as D
    question = "what colour is the number seven"
    key = D.expand_key(question, model=EXP.EXPAND_MODEL, prompt_template=EXP.EXPAND_SYSTEM,
                       temperature=C.TEMPERATURE, max_tokens=120)
    D.record(tmp_path, key, OBSERVED_REFUSAL.encode("utf-8"), lineage=[], metadata={})
    assert EXP.expand_terms(question, root=tmp_path) == ""


def test_ask_wrapper_counts_a_cached_refusal(tmp_path) -> None:
    # the v0 signal (issue #56 second ask): a refusal is logged, not silently discarded —
    # surfaced as expand_refusal.hit/.miss in CACHE_STATS (run_eval's report reads these).
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import ask

    import life_agent.core as C
    from life_agent.core import derivations as D
    question = "what colour is the number seven"
    key = D.expand_key(question, model=EXP.EXPAND_MODEL, prompt_template=EXP.EXPAND_SYSTEM,
                       temperature=C.TEMPERATURE, max_tokens=120)
    D.record(tmp_path, key, OBSERVED_REFUSAL.encode("utf-8"), lineage=[], metadata={})
    ask.reset_cache_stats()
    assert ask._expand_terms(question, root=tmp_path) == ""
    assert ask.cache_stats()["expand_refusal.hit"] == 1
