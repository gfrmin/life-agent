"""Query expansion — the native-script (Hebrew) BM25 keyword expander.

The owner asks in English; the personal documents are English AND Hebrew. A raw BM25 query on the
question's own words cannot reach a Hebrew document (no lexical overlap) — the dominant retrieval-
miss mode (measured 2026-06-20: 10/18 eval questions are a LEXICAL_GAP — the gold IS in the corpus,
but the question's query never reaches it even in the top-150). This asks a cheap model for concrete
domain keywords plus their Hebrew equivalents; ``retrieval.build_query`` appends them to the raw
question, so expansion can only ADD recall (the original words are always retained). A cached,
corpus-independent derivation (keyed on question + model + prompt only). Lifted from ``ask.py`` so
the answer-brain bridge and the ask REPL share ONE expander and ONE cache.

Double-edged, by measurement: expansion closes the gap for the Hebrew-doc questions (q-005/q-010/
q-008/q-013 into the top-20) but DILUTES strong English/number literals (q-002/q-014/q-019 drop), so
it belongs as a :grow mode — raw retrieval first, expansion only when the cheap pass withholds.
"""
from __future__ import annotations

import re
from pathlib import Path

import life_agent.core as C
from life_agent.core import derivations as D

EXPAND_MODEL = "claude-haiku-4-5-20251001"
EXPAND_SYSTEM = (
    "You expand a personal-assistant question into keywords for a bag-of-words (BM25) "
    "search over the owner's personal documents, which are in English AND Hebrew. The "
    "owner asks in natural language but the documents use concrete domain vocabulary "
    "(an income question is answered by a doc that says 'invoice', 'salary', 'Contractor', "
    "'עוסק מורשה' — never the phrase 'make money'). Output ONLY a space-separated list of "
    "8-15 concrete search terms: synonyms, the specific nouns such documents contain, and "
    "their Hebrew equivalents. If a question word is itself a transliterated Hebrew or loan "
    "word (e.g. 'arnona'->ארנונה, 'vaad'->ועד, 'bituach'->ביטוח, 'mas'->מס), you MUST output "
    "its exact Hebrew spelling verbatim — that spelling is usually the single most "
    "discriminative term, and the English transliteration matches nothing in the Hebrew "
    "documents. No punctuation, no numbering, no explanation. "
    "Example — 'how do i make money' -> income salary invoice contractor self-employed "
    "freelance fee earnings employer עוסק מורשה משכורת חשבונית. "
    "Example — 'how much was my arnona' -> arnona property-tax municipal rates bill "
    "ארנונה עירייה חשבון תשלום."
)


# Refusal detection (issue #56): on out-of-domain questions the expand model refuses in
# first-person prose ("I cannot help with this query… I'm a language model without access
# to…") and that prose must never become the BM25 query. The detector is conservative by
# conjunction: a keyword list never contains a first-person token, and marker words alone
# ("cannot", "sorry" as domain keywords) never fire without one.
_FIRST_PERSON = frozenset({"i", "im", "ive", "id"})
_REFUSAL_MARKERS = frozenset({"cannot", "cant", "wont", "dont", "unable", "sorry",
                              "apologize", "apologise", "apologies"})


def refusal(raw: str) -> bool:
    """Pure: is an expansion reply a refusal (first-person prose instead of keywords)?
    True when a first-person token co-occurs with a refusal marker or with 'language model'
    self-description — the observed out-of-domain failure mode (issue #56)."""
    toks = frozenset(re.sub(r"[^\w]+", " ", raw.lower().replace("'", "")).split())
    if not (_FIRST_PERSON & toks):
        return False
    return bool(_REFUSAL_MARKERS & toks) or {"language", "model"} <= toks


def clean_terms(raw: str) -> str:
    """Pure: flatten an LLM expansion reply to a clean space-separated term string.
    Drops bullets/commas/quotes/newlines; keeps Unicode word chars (so Hebrew survives).
    A refusal (:func:`refusal`, issue #56) flattens to '' — the callers' existing fail-open
    contract falls back to the raw-question query. Applied post-cache, so already-recorded
    refusal replies are re-gated on read (no EXPAND_VERSION bump, nothing orphaned)."""
    if refusal(raw):
        return ""
    return " ".join(re.sub(r"[^\w]+", " ", raw, flags=re.UNICODE).split())


def expand_terms(question: str, *, model: str = EXPAND_MODEL,
                 root: Path | None = None, no_cache: bool = False) -> str:
    """Impure edge: ask a cheap model for extra BM25 keywords. Returns a space-joined term
    string, or '' on any failure OR refusal (the caller falls back to the raw question —
    expansion must never break retrieval; issue #56). Cached, corpus-independent (keyed on
    question + model + prompt). The RAW reply is recorded — refusals included, they are the
    out-of-domain audit trail; ``clean_terms`` is applied post-cache so a cleanup tweak (or the
    refusal gate) does not orphan recorded expansions. Failures are never recorded."""
    key = D.expand_key(question, model=model, prompt_template=EXPAND_SYSTEM,
                       temperature=C.TEMPERATURE, max_tokens=120)
    if root is not None and not no_cache:
        cached = D.lookup(root, key.cache_key)
        if cached is not None:
            return clean_terms(cached.decode("utf-8"))
    try:
        r = C.anthropic_complete(EXPAND_SYSTEM, question, model=model, max_tokens=120)
    except SystemExit:
        return ""
    if root is not None:
        D.record(root, key, r.text.encode("utf-8"), lineage=[],
                 metadata={"in_tokens": r.in_tokens, "out_tokens": r.out_tokens})
    return clean_terms(r.text)
