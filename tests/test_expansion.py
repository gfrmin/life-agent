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
