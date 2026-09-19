"""terminals.py — the ask REPL's retrieval helpers and per-question state.

Retrieval over the live catalogue (the corpus digest, the lexical set, query expansion, the
listwise reranker), the owner-possessive trigger, the temporal and subject footers, and the
``*_LAST`` module state the REPL's render and the instrument arms read. Answers come from the
one executor (:func:`life_agent.core.ask_client.drive`); nothing here decides.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import duckdb

import life_agent.core as C
import life_agent.core.derivations as D
import life_agent.core.expansion as EXP
import life_agent.core.subject as S
import life_agent.core.temporal as T
import life_agent.core.temporal_intent as TI
from life_agent.core.retrieval import retrieve_set

_retrieve_set = retrieve_set

EXPAND_MODEL = EXP.EXPAND_MODEL
EXPAND_SYSTEM = EXP.EXPAND_SYSTEM

# Reranking: BM25 ranks by surface-word overlap, so for ~8 of the eval's retrieval misses
# the gold sits at lexical rank 36-132 (probe_gold_rank) — buried below literary PDFs that
# share the question's words but not its fact. A listwise reranker reads a WIDE lexical pool
# and selects the chunks that actually carry the answer, pulling the buried gold into the
# top-k (measured: Sonnet rescued 7/8 with zero regression, ~20k input tokens/question).
# Sonnet (not the synthesis default) because it reads the whole pool and accepts temperature.
RERANK_MODEL = "claude-sonnet-4-6"
RERANK_POOL = 150  # lexical chunks fed to the reranker (covers the deepest addressable gold)
RERANK_SYSTEM = (
    "You are a retrieval reranker for a personal-assistant corpus (English AND Hebrew). "
    "Given a QUESTION and a numbered list of document SNIPPETS, identify the snippets most "
    "likely to contain the EXACT fact needed to answer it. Prefer the specific, current, "
    "authoritative source (an official record, a form, a bill) over generic or incidental "
    "mentions of the same words. Return ONLY a JSON array of the {k} most relevant snippet "
    "numbers, best first — no prose."
)

# --- retrieval over the LIVE corpus --------------------------------------- #
def _pkm_root() -> Path | None:
    """The pkm knowledge root, or None when unresolvable. None disables derivation
    caching only (fail open) — answering itself goes through connect(), which raises.
    Delegates to the hoisted core resolution (shared with the render seam's lane)."""
    return C.pkm_root()


def connect() -> duckdb.DuckDBPyConnection:
    """Open the live catalogue read-only (so a running extraction never blocks us)
    and load FTS. Mirrors phase1_answer._connect()."""
    root = _pkm_root()
    if root is None:
        raise FileNotFoundError(f"unresolvable pkm root (config: {C.PKM_CONFIG})")
    conn = duckdb.connect(str(root / "catalogue.duckdb"), read_only=True)
    conn.execute("INSTALL fts; LOAD fts;")
    return conn


# --- the cached derivation DAG (pkm SPEC §18.9) ----------------------------- #
# Each ask is a DAG of content-addressed stages — expand → retrieve → synthesize —
# recorded file-first into the pkm cache (life_agent.core.derivations). Re-asking an
# unchanged question against an unchanged corpus replays every stage from cache at zero
# marginal cost; a changed input invalidates exactly the stages downstream of it (the
# synthesize key hashes the retrieved CONTENT, so corpus growth that retrieves the same
# evidence still replays the answer — early cutoff). Caching is strictly fail-open:
# no resolvable root / no digest / a lock just means a fresh computation, never a failure.
CACHE_STATS: dict[str, int] = defaultdict(int)


def _count(stage: str, *, hit: bool) -> None:
    CACHE_STATS[f"{stage}.{'hit' if hit else 'miss'}"] += 1


def reset_cache_stats() -> None:
    CACHE_STATS.clear()


def cache_stats() -> dict[str, int]:
    """A copy of the per-stage hit/miss counters (consumed by run_eval's report)."""
    return dict(CACHE_STATS)


def _corpus_digest(conn: duckdb.DuckDBPyConnection) -> str | None:
    """corpus_digest, fail-open: None (caching off for this question) on any failure —
    the cache must never break answering."""
    from life_agent.core.corpus import corpus_digest

    try:
        return corpus_digest(conn)
    except Exception:
        return None


def _is_lock_error(msg: str) -> bool:
    """True if a DuckDB error message means the catalogue is held by another process (a running
    extraction). Pure, so it's unit-tested in place of an un-reproducible live lock."""
    m = msg.lower()
    return "lock" in m or "conflict" in m or "being used" in m


_clean_terms = EXP.clean_terms  # the canonical cleaner now lives in core.expansion

# --- temporal (D1): /recent · /since · the nothing-vanishes footer --------- #
# The ask path is READ-ONLY (§18.9), so temporal answers PROJECT current
# doc_date artifacts (SPEC §18.12) over the hits and never derive in-band;
# underived hits are named with their remedy and `/derive` materialises them
# explicitly (closing the read connection around the write). The report of the
# most recent temporal answer travels via TEMPORAL_LAST (the CACHE_STATS
# pattern).
@dataclass(frozen=True)
class TemporalReport:
    footer: str                                   # '' when nothing to say
    targets: list[tuple[str, str]] = field(default_factory=list)
    # targets: (declaration name, input artifact cache key) for /derive


TEMPORAL_LAST: TemporalReport | None = None

# The last answer's §18.9 stage cache keys; absent entries mean the stage never keyed.
# Travels like TEMPORAL_LAST; the eval harness reads it for outcome lineage attribution
# (bayesian-foundations §8 — the outcomes log).
STAGES_LAST: dict[str, str] = {}

# The last answer's cheap EFFORT counters — the fair-fight harness's raw-capture "effort"
# axis (scripts/fairfight/arm_baseline.py). ``answer_via_executor()`` resets it to {}
# (genuinely absent, not a guessed 0): the decider's retrieve/grow rounds are not observable
# in the ``View`` it returns.
EFFORT_LAST: dict[str, int] = {}

# --- subject (D2): the owner filter + the same nothing-vanishes contract --- #
# A first-person possessive question ("my X") filters hits by projected
# doc_subject (SPEC §18.13) matched against the owner profile — consumer-side,
# the profile never enters pkm. Only determinate non-owner subjects and
# generic documents (templates, blank forms) are excluded, each named; an
# absent or unclear classification is indeterminate — KEPT and named (the D2
# gate). The report travels like TEMPORAL_LAST; /derive consumes both.
SUBJECT_LAST: TemporalReport | None = None

# The question's temporal SCOPE (present / historical / as_of / unscoped), classified once per
# question and SURFACED in the footer (it changes no decision yet — the scope-aware inclusion
# slice is gate-adjacent and frozen-blind). Travels like TEMPORAL_LAST; None when unresolved.
INTENT_LAST: TI.Scope | None = None
INTENT_FOOTER = "temporal scope: {scope}"

# The trigger: an UNCHAINED first-person possessive. "my X" fires; a
# relational possessive — "my partner's X" — hands the subject to someone
# else, where filtering for the owner would exclude exactly the right answer.
_OWNER_POSSESSIVE = re.compile(
    r"\b(?:my|mine|the owner'?s)\b(?!\s+\S+['’]s\b)",  # noqa: RUF001 — typographic apostrophe is deliberate
    re.IGNORECASE)


def owner_question(question: str) -> bool:
    """Pure: does the question ask about the owner's own things?"""
    return _OWNER_POSSESSIVE.search(question) is not None


def temporal_footer(view: T.TemporalView, name_of: dict[str, str]) -> str:
    """Pure: render the total partition — every retrieved artifact is either
    admitted, excluded (with the date that failed), undated, or underived
    with its remedy. Nothing vanishes silently (the D1 coverage contract)."""
    def names(keys: list[str]) -> str:
        return ", ".join(name_of.get(k, k[:12] + "…") for k in keys)

    parts = [f"{len(view.admitted)} admitted"]
    if view.excluded:
        listed = ", ".join(
            f"{name_of.get(k, k[:12] + '…')} ({d.isoformat()})"
            for k, d in view.excluded)
        parts.append(f"{len(view.excluded)} excluded by date ({listed})")
    if view.undated:
        parts.append(f"{len(view.undated)} no extractable date "
                     f"({names(view.undated)})")
    if view.underived:
        parts.append(f"{len(view.underived)} not yet date-derived "
                     f"({names(view.underived)})")
    footer = "date filter: " + " · ".join(parts)
    if view.remedies:
        footer += ("\n  /derive to materialise, or run:\n    "
                   + "\n    ".join(view.remedies))
    return footer


def subject_footer(view: S.SubjectView, name_of: dict[str, str]) -> str:
    """Pure: render the total partition — every retrieved artifact is either
    admitted, someone else's (named with the subject as written), generic
    (template/blank — determinately nobody's), subject-unclear (KEPT), or
    underived (KEPT, with its remedy). Indeterminates are never dropped
    (the D2 coverage contract)."""
    def names(keys: list[str]) -> str:
        return ", ".join(name_of.get(k, k[:12] + "…") for k in keys)

    parts = [f"{len(view.admitted)} admitted"]
    if view.excluded_other:
        listed = ", ".join(
            f"{name_of.get(k, k[:12] + '…')} ({s})"
            for k, s in view.excluded_other)
        parts.append(f"{len(view.excluded_other)} someone else's ({listed})")
    if view.excluded_generic:
        parts.append(f"{len(view.excluded_generic)} generic/template "
                     f"({names(view.excluded_generic)})")
    if view.unclear:
        parts.append(f"{len(view.unclear)} subject unclear — kept "
                     f"({names(view.unclear)})")
    if view.underived:
        parts.append(f"{len(view.underived)} not yet subject-derived — kept "
                     f"({names(view.underived)})")
    footer = "owner filter: " + " · ".join(parts)
    if view.remedies:
        footer += ("\n  /derive to materialise, or run:\n    "
                   + "\n    ".join(view.remedies))
    return footer


def _expand_terms(question: str, *, model: str = EXPAND_MODEL,
                  root: Path | None = None, no_cache: bool = False) -> str:
    """Impure edge: ask a cheap model for extra BM25 keywords. Returns a space-joined
    term string, or '' on any failure OR refusal (caller falls back to the raw question —
    expansion must never break the REPL; issue #56).

    Cached derivation (corpus-independent: keyed on question + model + prompt template
    only, so corpus growth never invalidates it). The RAW model reply is what is recorded;
    ``EXP.usable_terms`` (the ONE shared refusal gate + ``_clean_terms``) is applied
    post-cache, so a cleanup/detector tweak changes behaviour without orphaning recorded
    expansions; the counter callback keeps expand_refusal beside expand.miss (the
    refusal/attempt ratio must hold). Failures are never recorded."""
    key = D.expand_key(question, model=model, prompt_template=EXPAND_SYSTEM,
                       temperature=C.TEMPERATURE, max_tokens=120)
    if root is not None and not no_cache:
        cached = D.lookup(root, key.cache_key)
        if cached is not None:
            _count("expand", hit=True)
            return EXP.usable_terms(
                cached.decode("utf-8"),
                on_refusal=lambda: _count("expand_refusal", hit=True))
    try:
        r = C.anthropic_complete(EXPAND_SYSTEM, question, model=model, max_tokens=120)
    except SystemExit:
        return ""
    if root is not None:
        _count("expand", hit=False)
        D.record(root, key, r.text.encode("utf-8"), lineage=[],
                 metadata={"in_tokens": r.in_tokens, "out_tokens": r.out_tokens})
    return EXP.usable_terms(  # the fresh path's single gate call (the cached branch has
        r.text,               # its own — different raw, different hit-bucket counter)
        on_refusal=((lambda: _count("expand_refusal", hit=False))
                    if root is not None else None))


def _rerank_hits(question: str, pool: list[dict[str, Any]], k: int, *,
                 model: str = RERANK_MODEL) -> list[dict[str, Any]]:
    """Impure edge: a listwise reranker reads the wide lexical POOL and returns its top-k
    hits, reordered so the chunk that actually carries the answer leads. Fail-open — any
    error (API down, unparseable reply) returns the lexical top-k unchanged, so reranking
    can only improve recall, never break the path. The returned dicts are the pool's own
    (same artifact_cache_key / chunk_text / origin / score), so every downstream key and
    citation is unaffected. A short or garbled reply is backfilled from the lexical head, so
    the result is never fewer (or worse on the tail) than lexical retrieval alone."""
    if len(pool) <= k:
        return pool[:k]
    snippets = "\n".join(
        f"[{i + 1}] {h['chunk_text'][:280].strip().replace(chr(10), ' ')}"
        for i, h in enumerate(pool))
    user = f"QUESTION: {question}\n\nSNIPPETS:\n{snippets}"
    try:
        r = C.anthropic_complete(RERANK_SYSTEM.format(k=k), user, model=model, max_tokens=400)
    except SystemExit:
        return pool[:k]
    m = re.search(r"\[[\s\d,]*\]", r.text)
    picks = [int(n) for n in re.findall(r"\d+", m.group(0))] if m else []
    seen: set[int] = set()
    ordered: list[dict[str, Any]] = []
    for n in picks:  # reranker order first, valid + de-duplicated
        if 1 <= n <= len(pool) and n not in seen:
            seen.add(n)
            ordered.append(pool[n - 1])
    for i, h in enumerate(pool, 1):  # backfill from the lexical head to guarantee k
        if len(ordered) >= k:
            break
        if i not in seen:
            ordered.append(h)
    return ordered[:k]


def _cards_from_set(hits: list[dict[str, Any]],
                    dates: dict[str, str | None] | None = None
                    ) -> list[tuple[C.SourceCard, float]]:
    """Pure: render a retrieval set (live or replayed from cache) as numbered cards. ``dates``
    (artifact_cache_key → ISO doc_date) attaches each card's ``as_of`` for the temporal-scope
    render; omitted ⇒ undated (back-compat — the retrieve() convenience seam stays date-blind)."""
    return [(C.SourceCard(n=i + 1, text=h["chunk_text"].strip(), origin=h["origin"],
                          as_of=(dates.get(h["artifact_cache_key"]) if dates else None)),
             h["score"]) for i, h in enumerate(hits)]


def retrieve(conn: duckdb.DuckDBPyConnection, question: str,
             k: int) -> list[tuple[C.SourceCard, float]]:
    """FTS query → top-k (numbered SourceCard, score) pairs. Composition of the two
    halves above; kept as the uncached convenience seam."""
    return _cards_from_set(_retrieve_set(conn, question, k))


