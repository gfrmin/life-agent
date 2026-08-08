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


# Refusal detection (issue #56): on out-of-domain questions the expand model answers in
# prose ("I cannot help with this query…", "Sorry, this is beyond my capabilities.")
# instead of keywords, and that prose must never become the BM25 query. Marker-word
# blocklists fail in BOTH directions (PR #61 review: apostrophe variants and uncontracted
# phrasings slip through; dual-use tokens like 'sorry'/'unable'/'id' appear in legitimate
# expansions), so the detector is STRUCTURAL: the prompt's contract output is a bare
# keyword list, which contains (almost) no English function words, while refusal prose is
# majority sentence furniture. No single token can fire it, and Hebrew/domain tokens only
# pull the density DOWN — the failure mode is biased toward keeping recall (a kept short
# refusal adds mild noise; build_query always retains the raw question either way).
# fuse contractions before tokenizing (don't -> dont): ASCII ' plus the typographic
# apostrophes U+2019 / U+2018 / U+02BC — the forms models actually emit in prose.
_APOSTROPHES = str.maketrans("", "", "'’‘ʼ")  # noqa: RUF001
_PROSE_TEXT = """
    a an the and or but nor so to of in on at by for with without from as about into over
    under outside inside beyond within is are am was were be been being do does did not no
    can cannot could will would should shall may might must have has had having this that
    these those there here it its i im ive me my mine we our us you your yours they them
    their he she his her what which who whom how when where why if then than just only also
    however instead rather such any some sorry unfortunately unable apologize apologise
    apologies please cant dont wont didnt doesnt isnt arent couldnt wouldnt shouldnt
"""
_PROSE_WORDS = frozenset(_PROSE_TEXT.split())
_MIN_PROSE_TOKENS = 4  # below one sentence's length density is meaningless — keep the reply


def refusal(raw: str) -> bool:
    """Pure: is an expansion reply prose (a refusal / hedge) rather than a keyword list?
    Fires iff STRICTLY more than half of its tokens (and at least 4) are English function
    words or refusal hedge vocabulary. Measured boundaries (pinned in tests): every
    observed refusal shape ≥ 0.53 density; a hedged preamble carrying real keywords
    ≤ 0.33; marker words inside a keyword list ('sorry', 'unable', 'id' …) top out at
    exactly ½ and never fire alone."""
    toks = re.sub(r"[^\w]+", " ", raw.translate(_APOSTROPHES).lower()).split()
    if len(toks) < _MIN_PROSE_TOKENS:
        return False
    return sum(t in _PROSE_WORDS for t in toks) / len(toks) > 0.5


def clean_terms(raw: str) -> str:
    """Pure: flatten an LLM expansion reply to a clean space-separated term string.
    Drops bullets/commas/quotes/newlines; keeps Unicode word chars (so Hebrew survives).
    Lossless by contract — the refusal gate (issue #56) lives at the expand_terms seam
    (:func:`_usable`), never here: a gate inside the flattener would silently discard a
    hedged reply's keywords for every caller."""
    return " ".join(re.sub(r"[^\w]+", " ", raw, flags=re.UNICODE).split())


def _usable(raw: str) -> str:
    """Post-cache finishing: gate refusal prose to '' (issue #56 — the callers' fail-open
    contract falls back to the raw-question query) with a journal-visible note (the bridge
    callers' v0 out-of-domain signal), else the pure flatten. Applied post-cache, so
    already-recorded refusal replies are re-gated on read — no EXPAND_VERSION bump."""
    if refusal(raw):
        print("  (expansion refused → raw-question fallback)")
        return ""
    return clean_terms(raw)


def expand_terms(question: str, *, model: str = EXPAND_MODEL,
                 root: Path | None = None, no_cache: bool = False) -> str:
    """Impure edge: ask a cheap model for extra BM25 keywords. Returns a space-joined term
    string, or '' on any failure OR refusal (the caller falls back to the raw question —
    expansion must never break retrieval; issue #56). Cached, corpus-independent (keyed on
    question + model + prompt). The RAW reply is recorded — refusals included, they are the
    out-of-domain audit trail; ``_usable`` (the refusal gate + ``clean_terms``) is applied
    post-cache so a detector tweak does not orphan recorded expansions. Failures are never
    recorded."""
    key = D.expand_key(question, model=model, prompt_template=EXPAND_SYSTEM,
                       temperature=C.TEMPERATURE, max_tokens=120)
    if root is not None and not no_cache:
        cached = D.lookup(root, key.cache_key)
        if cached is not None:
            return _usable(cached.decode("utf-8"))
    try:
        r = C.anthropic_complete(EXPAND_SYSTEM, question, model=model, max_tokens=120)
    except SystemExit:
        return ""
    if root is not None:
        D.record(root, key, r.text.encode("utf-8"), lineage=[],
                 metadata={"in_tokens": r.in_tokens, "out_tokens": r.out_tokens})
    return _usable(r.text)
