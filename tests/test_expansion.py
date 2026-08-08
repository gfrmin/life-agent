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
# REFUSES, and the refusal prose flowed through clean_terms into the BM25 query. The gate
# is STRUCTURAL — function-word density, not marker blocklists (PR #61 review confirmed
# blocklists fail in BOTH directions: apostrophe variants and uncontracted phrasings slip
# through, dual-use keywords get nuked) — and it is applied post-cache at the expand_terms
# seam, so cached refusal replies are re-gated on read and every caller falls back to the
# raw-question query. clean_terms itself stays the pure lossless flattener.

OBSERVED_REFUSAL = ("I cannot help with this query. I'm a language model without access "
                    "to personal documents or files.")

REFUSAL_SHAPES = (
    OBSERVED_REFUSAL,
    "I don't have access to personal information about individuals.",
    "I don’t have access to personal information about individuals.",  # noqa: RUF001
    "I do not have access to personal documents or files.",            # uncontracted
    "I'm an AI assistant without access to your files.",
    "Sorry, this is beyond my capabilities.",                          # possessive, no 'I'
    "This falls outside my area of expertise, sorry.",
    "Unfortunately this request is outside my scope as a language model.",
    # PR #63 review: verified evaders one contraction/hedge-word away from the pinned
    # shapes (I'd/you'd/haven't/wasn't were missing from the fused-contraction set)
    "I'd need more information to answer that question.",
    "I haven't found any relevant keywords for this.",
    "You'd need to consult a professional for this request.",
    "I wasn't able to generate keywords for this request.",
)

KEYWORD_SHAPES = (
    # the prompt's own example outputs (incl. native-script Hebrew) and a bulleted reply
    "income salary invoice contractor self-employed freelance fee earnings employer "
    "עוסק מורשה משכורת חשבונית",
    "arnona property-tax municipal rates bill ארנונה עירייה חשבון תשלום",
    "income, salary;\n- 'invoice'  עוסק מורשה\nמשכורת.",  # noqa: RUF001
    # dual-use tokens in legitimate expansions (PR #61 review): 'id' is a domain word,
    # 'unable'/'sorry' echo the question — none may fire without majority prose density
    "unable renew id card identity passport appointment תעודת זהות",
    "apology letter sorry regret complaint מכתב התנצלות",
    "cannot unable sorry apology complaint letter",  # exactly ½ density — held OUT (strict >)
    # a hedged preamble around real keywords keeps its keywords, never nuked wholesale
    "I don't have specific context, but likely keywords: arnona property-tax ארנונה עירייה",
    # the round-2 prose additions (need/able/id/…) never fire inside a keyword list
    "need-to-know clearance authorization form security-id badge",
)


def test_refusal_detects_every_observed_shape() -> None:
    for raw in REFUSAL_SHAPES:
        assert EXP.refusal(raw), raw


def test_refusal_passes_every_keyword_shape() -> None:
    for raw in KEYWORD_SHAPES:
        assert not EXP.refusal(raw), raw


def test_clean_terms_stays_a_pure_flattener_even_on_prose() -> None:
    # the lossless-flatten invariant is clean_terms' whole contract; the refusal gate lives
    # at the expand_terms seam, NOT here (PR #61 review: a gate inside the flattener would
    # silently discard hedged replies' keywords for every caller, forever).
    assert EXP.clean_terms(OBSERVED_REFUSAL).startswith("I cannot help with this query")


def _seed_cached_refusal(root, question: str = "what colour is the number seven") -> str:
    import life_agent.core as C
    from life_agent.core import derivations as D
    key = D.expand_key(question, model=EXP.EXPAND_MODEL, prompt_template=EXP.EXPAND_SYSTEM,
                       temperature=C.TEMPERATURE, max_tokens=120)
    D.record(root, key, OBSERVED_REFUSAL.encode("utf-8"), lineage=[], metadata={})
    return question


def _no_model(monkeypatch) -> None:
    # hermeticity pin (PR #61 review): on a cache-key drift these tests must FAIL LOUDLY,
    # not fall through to a live paid Anthropic call or a SystemExit-shaped '' false-pass.
    import life_agent.core as C

    def boom(*a: object, **k: object) -> None:
        raise AssertionError("expansion test must not reach the model")
    monkeypatch.setattr(C, "anthropic_complete", boom)


def test_cached_refusal_is_regated_on_read(tmp_path, monkeypatch) -> None:
    # A refusal recorded BEFORE the gate existed is re-gated on read (the gate is applied
    # post-cache) — no EXPAND_VERSION bump, no orphaned recordings, zero model calls.
    _no_model(monkeypatch)
    question = _seed_cached_refusal(tmp_path)
    assert EXP.expand_terms(question, root=tmp_path) == ""


def test_fresh_refusal_is_gated_and_still_recorded(tmp_path, monkeypatch) -> None:
    # the RAW refusal is recorded (the out-of-domain audit trail) but never returned.
    import life_agent.core as C
    from life_agent.core import derivations as D
    from life_agent.core.llm import LLMResult
    monkeypatch.setattr(C, "anthropic_complete", lambda *a, **k: LLMResult(
        text=OBSERVED_REFUSAL, in_tokens=1, out_tokens=1, seconds=0.0))
    question = "what colour is the number seven"
    assert EXP.expand_terms(question, root=tmp_path) == ""
    key = D.expand_key(question, model=EXP.EXPAND_MODEL, prompt_template=EXP.EXPAND_SYSTEM,
                       temperature=C.TEMPERATURE, max_tokens=120)
    assert D.lookup(tmp_path, key.cache_key) == OBSERVED_REFUSAL.encode("utf-8")


def test_ask_wrapper_counts_a_cached_refusal(tmp_path, monkeypatch) -> None:
    # the v0 signal (issue #56 second ask): a refusal is logged, not silently discarded —
    # surfaced as expand_refusal.hit/.miss in CACHE_STATS (run_eval's cache line reads it).
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import ask
    _no_model(monkeypatch)
    question = _seed_cached_refusal(tmp_path)
    ask.reset_cache_stats()
    assert ask._expand_terms(question, root=tmp_path) == ""
    assert ask.cache_stats()["expand_refusal.hit"] == 1


def test_ask_wrapper_gates_through_the_shared_seam_never_silently(
        tmp_path, monkeypatch, capsys) -> None:
    # PR #63 review: the gate must not be hand-mirrored in ask.py — both surfaces run
    # ONE usable_terms (single source, no drift), and the fallback is NAMED on the
    # REPL surface too (the interaction contract's never-silent rule), not only in
    # the bridge journal.
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import ask
    _no_model(monkeypatch)
    question = _seed_cached_refusal(tmp_path)
    ask.reset_cache_stats()
    assert ask._expand_terms(question, root=tmp_path) == ""
    assert "raw-question fallback" in capsys.readouterr().out
