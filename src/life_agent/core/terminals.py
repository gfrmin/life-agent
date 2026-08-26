"""terminals.py — the terminals-only regime's body (M5, r15; design §2.3).

The in-process family orchestration ABSORBED from ``scripts/ask.py`` (§2.2: the
dispatch dies; the families survive as leaves): retrieve over the live catalogue →
temporal/subject covariates → the typed lookup leaf, falling through to the narrative
leaf (§9 no-hard-zeros) — the same seam and the same engine family as the full
regime, ranked over ``T`` by the skin instead of ``the full space`` by the daemon. Reached by
(i) the one driver's down-branch — an unavailable daemon answers over ``T`` with the
regime honestly recorded rather than going mute (Q1, signed) — and (ii) the ask
REPL, whose ``ask_once`` no longer chooses a path (B-1/B-5 died).

The ``*_LAST`` module state is the per-question travel contract the REPL's render and
the instrument arms read; it lives here because the regime body populates it.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date as _date
from pathlib import Path
from typing import Any, TypeGuard, cast

import duckdb

import life_agent.core as C
import life_agent.core.aggregate as AGG
import life_agent.core.derivations as D
import life_agent.core.expansion as EXP
import life_agent.core.lookup as LK
import life_agent.core.narrative as N
import life_agent.core.probes as P
import life_agent.core.subject as S
import life_agent.core.synthesis as SYN
import life_agent.core.temporal as T
import life_agent.core.temporal_intent as TI
import life_agent.owner as owner
from life_agent.core.retrieval import build_query, retrieve_set
from pkm.hashing import canonical_json

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

# Synthesis prompt. Deliberately NOT the comparison harness's CITATION_INSTRUCTION (in
# scripts/comparison/_common.py): that is a frozen eval artifact, hardened against
# identity-confusion for blind grading — it demands a value be asserted "only if it is the
# subject the question asks about". In the dogfood loop that backfired: the model disowned the
# owner's OWN un-name-stamped documents (a contract they signed, their tax certificate) and read
# "how do i make money" as a request for generic advice. So this prompt reads questions in the
# first person and attributes the corpus to the owner by default.
#
# But that default *over*-corrected on 2026-06-02: "what is my name?" returned a family member's
# health report (a partner's name + ID) as the owner's. The fix is the OWNER block — authoritative
# identity facts (see life_agent.owner) injected by answer() — which this prompt treats as the
# authority on whose document a SOURCE is, so a partner's/relative's name or ID is never asserted
# as the owner's. (The OWNER block may be empty; the rules then degrade to the old behaviour.)
# The synthesis prompt + synthesizer now live in core (`life_agent.core.synthesis`) so the answer-
# brain bridge and this REPL share ONE synthesizer + ONE cache (the prompt is the cache key, kept
# byte-identical). The alias keeps ask.py's surface unchanged.
ANSWER_SYSTEM = SYN.ANSWER_SYSTEM

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
# pattern) so answer()'s public 3-tuple stays unchanged for run_eval/tests.
@dataclass(frozen=True)
class TemporalReport:
    footer: str                                   # '' when nothing to say
    targets: list[tuple[str, str]] = field(default_factory=list)
    # targets: (declaration name, input artifact cache key) for /derive


TEMPORAL_LAST: TemporalReport | None = None

# The last answer's §18.9 stage cache keys ({"retrieve": ..., "synthesize": ...}; absent
# entries mean the stage never keyed — e.g. no synthesize on an abstention). Travels like
# TEMPORAL_LAST so answer()'s public 3-tuple stays unchanged; the eval harness reads it
# for outcome lineage attribution (bayesian-foundations §8 — the outcomes log).
STAGES_LAST: dict[str, str] = {}

# The last answer's cheap EFFORT counters — the fair-fight harness's raw-capture "effort"
# axis (scripts/fairfight/arm_baseline.py, arm_synthesis.py). Same *_LAST travel pattern as
# STAGES_LAST: reset to {} at the top of each dispatch, populated ONLY at a seam that
# already knows the count (never a new probe, never a guess). ``answer()`` populates both
# keys below every call it reaches retrieval (``retrieve_passes`` — always exactly 1: this
# driver retrieves once per question, even under ``rerank=True``, which re-orders an
# over-fetched pool rather than re-querying) and ``gather_tiers`` (constant 0 since M5:
# the gather-augmented loop died with core/gather.py — the key survives so the
# raw-capture record shape is stable across the deletion). Keys are present
# (0 or more) whenever ``answer()`` runs; ``answer_via_executor()`` resets this to {}
# (empty — genuinely absent, not a guessed 0) because the daemon's internal retrieve/grow
# rounds are not observable in the ``View`` it returns, and ``core/executor.py`` must not
# be edited to expose them.
EFFORT_LAST: dict[str, int] = {}

# The last answer's lookup-family result (foundations §4), or None when the narrative
# path answered (not routed as a lookup, zero grounded observations, or a named
# fail-open). Travels like TEMPORAL_LAST; run_eval's --lookup grader consumes it.
LOOKUP_LAST: LK.LookupResult | None = None

# The last answer's narrative-family result (foundations §7), or None when the lookup
# path answered, the answer abstained pre-synthesis, or narrative scoring failed
# (named fail-open). run_eval's claim + coverage graders consume it.
NARRATIVE_LAST: N.NarrativeResult | None = None

# The last answer's aggregate-family result (design §2, r21), or None when another
# family answered. Verdicts on it are recorded, never folded (the CP-A ruling).
AGGREGATE_LAST: AGG.AggregateResult | None = None

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


def _apply_temporal_to_hits(
    conn: duckdb.DuckDBPyConnection, root: Path | None,
    hits: list[dict[str, Any]], *, since: _date | None, until: _date | None,
    recent: bool,
) -> tuple[list[dict[str, Any]], TemporalReport]:
    """Project + filter the chunk hits by ARTIFACT date. Chunks of one
    artifact share its fate; admitted chunks keep admitted-artifact order
    (newest first). Fail-open: an unresolvable root disables the filter with
    an explicit notice, never silently."""
    if root is None:
        return hits, TemporalReport(
            footer="date filter UNAVAILABLE (no pkm root) — showing all hits")
    keys = list(dict.fromkeys(h["artifact_cache_key"] for h in hits))
    view = T.apply_temporal(
        T.project_dates(conn, root, keys),
        since=since, until=until, recent=recent)
    name_of = {h["artifact_cache_key"]: Path(h["origin"]).name for h in hits}
    rank = {k: i for i, k in enumerate(view.admitted)}
    admitted_hits = sorted(
        (h for h in hits if h["artifact_cache_key"] in rank),
        key=lambda h: rank[h["artifact_cache_key"]])
    targets = []
    for remedy in view.remedies:  # "pkm derive <decl> --input <ck>"
        words = remedy.split()
        targets.append((words[2], words[4]))
    return admitted_hits, TemporalReport(
        footer=temporal_footer(view, name_of), targets=targets)

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


def _apply_subject_to_hits(
    conn: duckdb.DuckDBPyConnection, root: Path | None,
    hits: list[dict[str, Any]], *, profile: str,
) -> tuple[list[dict[str, Any]], TemporalReport, dict[str, str]]:
    """Project + owner-filter the chunk hits by ARTIFACT subject. Chunks of
    one artifact share its fate; admitted chunks keep their retrieval order
    (the filter excludes, it does not rank). Fail-open at every seam, never
    silently: no pkm root or no profile disables the filter with an explicit
    notice; a failed owner-match verdict leaves that subject unclear (kept
    and named in the footer). The third return value maps each admitted
    artifact key to its partition state ("owner" | "unclear" | "underived")
    — the lookup family's §4.1 subject covariate (carried OUTSIDE the hit
    dicts, so the retrieval-set bytes stay untouched)."""
    if root is None:
        return hits, TemporalReport(
            footer="owner filter UNAVAILABLE (no pkm root) — showing all hits"), {}
    if not profile:
        return hits, TemporalReport(
            footer="owner filter UNAVAILABLE (no owner profile — "
                   "/tell who you are) — showing all hits"), {}
    keys = list(dict.fromkeys(h["artifact_cache_key"] for h in hits))
    shits = S.project_subjects(conn, root, keys)
    verdicts: dict[str, str] = {}
    for subj in sorted({h.subject for h in shits
                        if h.state == "named" and h.subject}):
        try:
            verdicts[subj] = S.owner_verdict(root, subj, profile)
        except Exception as e:  # fail-open per subject: unclear, kept, named
            print(f"  owner match failed for {subj!r} ({e}) — kept as unclear")
    view = S.apply_owner_filter(shits, verdicts)
    name_of = {h["artifact_cache_key"]: Path(h["origin"]).name for h in hits}
    admitted = set(view.admitted)
    admitted_hits = [h for h in hits if h["artifact_cache_key"] in admitted]
    indeterminate = {**dict.fromkeys(view.unclear, "unclear"),
                     **dict.fromkeys(view.underived, "underived")}
    state_of = {k: indeterminate.get(k, "owner") for k in admitted}
    targets = []
    for remedy in view.remedies:  # "pkm derive <decl> --input <ck>"
        words = remedy.split()
        targets.append((words[2], words[4]))
    return admitted_hits, TemporalReport(
        footer=subject_footer(view, name_of), targets=targets), state_of


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


def _set_content(hits: list[dict[str, Any]]) -> bytes:
    """Pure: the canonical bytes of a retrieval set — what gets recorded, and what the
    synthesize key hashes (the early-cutoff hinge: equal evidence ⇒ equal hash, whatever
    the corpus digest did)."""
    return canonical_json({"format_version": 1, "hits": hits}).encode("utf-8")


def retrieve(conn: duckdb.DuckDBPyConnection, question: str,
             k: int) -> list[tuple[C.SourceCard, float]]:
    """FTS query → top-k (numbered SourceCard, score) pairs. Composition of the two
    halves above; kept as the uncached convenience seam."""
    return _cards_from_set(_retrieve_set(conn, question, k))


def _typed_lookup_applies(lk: LK.LookupResult | None) -> TypeGuard[LK.LookupResult]:
    """The routing criterion (§9 no-hard-zeros): the lookup family answered iff it returned a
    result. It returns None in exactly two cases — the question was not classified as a typed
    lookup, or it produced zero grounded observations — and both are coverage failures, not
    abstentions: the narrative path covers what lookup can't, by design. Naming the predicate
    keeps the dispatch a stated rule, not a bare ``is not None`` at the call site. The
    ``TypeGuard`` lets the name narrow ``lk`` to a ``LookupResult`` for the type-checker exactly
    as the bare ``is not None`` did — wrapping it in a function must not cost that narrowing."""
    return lk is not None

def _generators() -> tuple[AGG.LoadedRegistry | None, str]:
    """The generator registry via config paths — inadmissibility is fail-open with the
    reason NAMED in the render (the §9 refusal guards the denominator, not the answer)."""
    from life_agent.core import config as _cfg
    try:
        return AGG.load_registry(_cfg.GENERATORS_PATH,
                                 evidence_root=_cfg.EVIDENCE_ROOT), ""
    except FileNotFoundError:
        return None, "generator registry absent — retrieval recall unmodelled"
    except AGG.RegistryError as e:
        return None, f"generator registry inadmissible: {e}"


def answer(conn: duckdb.DuckDBPyConnection, question: str,
           k: int, *, expand: bool = True,
           no_cache: bool = False,
           families: bool = True,
           rerank: bool = False,
           since: _date | None = None, until: _date | None = None,
           recent: bool = False) -> tuple[str, list[C.SourceCard], dict[int, float]]:
    """Retrieve then synthesise a cited answer. The authoritative owner profile (who "I"/"my"
    is) is prepended as an OWNER block so the model never mistakes a relative's document for the
    owner's. Retrieval uses the question expanded with cheap-model keywords by default
    (``expand=False`` for the raw-question A/B baseline).

    Every stage is a cached, content-addressed derivation (SPEC §18.9): expand keyed on the
    question; retrieve keyed on (query, corpus digest, k); synthesize keyed on (question,
    retrieval-set content hash, owner-profile hash). ``no_cache`` recomputes every stage
    (recording stays write-once, so existing derivations stand). Caching is fail-open.

    ``families=False`` is the **monolithic instrument** seam (the adoption-gate baseline,
    bayesian-foundations §8): skip the typed lookup route AND the narrative scorer, so the
    raw synthesize prose is returned — the pre-Bayesian answer the gate weighs the typed
    families against. Default ``True`` preserves the production path exactly.

    ``rerank=True`` over-fetches a wide lexical pool and lets a listwise reranker
    (:func:`_rerank_hits`) pick the top-k — the recall lever for golds BM25 buried below
    word-overlapping noise (measured: rescues ~7/8 of the eval's addressable retrieval
    misses). Default ``False``. Returns (answer_text, cards, {card_n: score})."""
    global TEMPORAL_LAST, SUBJECT_LAST, STAGES_LAST, LOOKUP_LAST, NARRATIVE_LAST
    global INTENT_LAST, AGGREGATE_LAST
    global EFFORT_LAST
    TEMPORAL_LAST = None
    SUBJECT_LAST = None
    STAGES_LAST = {}
    LOOKUP_LAST = None
    NARRATIVE_LAST = None
    INTENT_LAST = None
    EFFORT_LAST = {"retrieve_passes": 0, "gather_tiers": 0}
    root = _pkm_root()
    profile = owner.load_profile()
    # temporal-scope intent (cached, question-only): surfaced + recorded, decision-neutral.
    # Gated on a live session (conn) — the cache-replay / eval path (conn=None) skips it, as the
    # keystone's date probe does. Fail-open and NAMED (interaction contract): a classifier failure
    # leaves no label, never a wrong one; the scope-aware inclusion that would USE it is the next,
    # gate-adjacent slice.
    if conn is not None and root is not None:
        try:
            INTENT_LAST = TI.intent_verdict(root, question)
        except Exception as e:
            print(f"  (temporal scope: unclassified — {e})")
    terms = _expand_terms(question, root=root, no_cache=no_cache) if expand else ""
    if terms:
        print(f"  ↳ expanded: {terms}")
    query = build_query(question, terms)

    # retrieve — deterministic given the corpus state, so keyed on its digest. With
    # rerank=True, over-fetch a wide pool and let a listwise reranker pick the top-k (the
    # recall lever for golds BM25 buried below word-overlapping noise); the reranked set is
    # computed fresh — its content differs from the lexical top-k, so the retrieve key would
    # not match — and the wider, content-keyed synthesize cache below still applies.
    hits: list[dict[str, Any]] | None = None
    rkey = None  # the reranked set is not recorded under a retrieve key (its content is the
    # reranker's, not a pure corpus+query function); synthesize lineage falls back to sources
    if rerank:
        pool = _retrieve_set(conn, query, RERANK_POOL)
        hits = _rerank_hits(question, pool, k)
        STAGES_LAST["rerank"] = f"{RERANK_MODEL}/{RERANK_POOL}->{k}"
    else:
        digest = _corpus_digest(conn) if root is not None else None
        rkey = D.retrieve_key(query, digest, k=k) if digest is not None else None
        if rkey is not None:
            STAGES_LAST["retrieve"] = rkey.cache_key
        if root is not None and rkey is not None and not no_cache:
            cached = D.lookup(root, rkey.cache_key)
            if cached is not None:
                _count("retrieve", hit=True)
                hits = json.loads(cached.decode("utf-8"))["hits"]
        if hits is None:
            hits = _retrieve_set(conn, query, k)
            if root is not None and rkey is not None:
                _count("retrieve", hit=False)
                lineage = [{"cache_key": ck, "role": "retrieved"}
                           for ck in dict.fromkeys(h["artifact_cache_key"] for h in hits)]
                D.record(root, rkey, _set_content(hits), lineage=lineage)
    # exactly one retrieval round happened above (rerank re-orders an over-fetched pool; it
    # does not re-query) — the effort axis's cheapest, most honest count for this driver.
    EFFORT_LAST["retrieve_passes"] = 1

    # temporal (D1): filter/rank the hits by projected doc_date BEFORE cards
    # and the synthesize key — the admitted set IS the evidence, so the key's
    # early-cutoff hinge hashes exactly what synthesis sees. The full retrieval
    # set was already recorded above (retrieval is a corpus+query function;
    # the date predicate is consumer-side policy).
    if since is not None or until is not None or recent:
        hits, report = _apply_temporal_to_hits(
            conn, root, hits, since=since, until=until, recent=recent)
        TEMPORAL_LAST = report

    # subject (D2): owner-filter the (possibly already date-filtered) hits by
    # projected doc_subject when the question is an unchained first-person
    # possessive. Same placement reasoning as temporal: BEFORE cards and the
    # synthesize key, so the admitted set IS the evidence. The predicates
    # compose — each footer names its own partition over what reached it; the
    # full retrieval set is already recorded above.
    subject_state_of: dict[str, str] = {}
    if owner_question(question):
        hits, sreport, subject_state_of = _apply_subject_to_hits(
            conn, root, hits, profile=profile)
        SUBJECT_LAST = sreport

    # attach each card's freshest doc_date (probe_recency adds the email-Date-header fallback
    # for the
    # un-projected sliver) so the narrative render surfaces "as of <date>" — the temporal-scope
    # keystone. Read-only; display only (the synthesize key hashes hits, not cards).
    card_dates = (P.probe_recency(conn, root, list(dict.fromkeys(
        h["artifact_cache_key"] for h in hits)))
        if conn is not None and root is not None and hits else None)
    pairs = _cards_from_set(hits, card_dates)
    cards = [c for c, _ in pairs]
    scores = {c.n: s for c, s in pairs}
    # B-4 died at M5 (S-1 split, r15): weak retrieval is BELIEF — few/weak observations
    # withhold by EU inside the ranking (typed) or the per-claim inclusion (narrative),
    # never by a host threshold pre-empting the ranking.
    # The lookup family (Ask v0, foundations §4): typed point-fact questions take the
    # Bayesian path — grounded per-hit observations → tempered mixture posterior → EU
    # response under the utility posterior — and its decision IS the answer. Routed
    # conservatively: a declined route or zero grounded observations falls to the
    # narrative path (the §9 no-hard-zeros routing), and any failure is fail-open and
    # NAMED (interaction contract), never silent.
    if families and root is not None:
        try:
            # §4.1 covariates, projected read-side and carried OUTSIDE the hit
            # dicts (the retrieval-set bytes — and every key hashed from them —
            # stay untouched): the owner-filter partition states from above, and
            # the doc_date projection (None = projected but undated/underived).
            hit_keys = list(dict.fromkeys(h["artifact_cache_key"] for h in hits))
            date_of: dict[str, str | None] = {
                d.artifact_cache_key:
                    (d.date.isoformat() if d.date is not None else None)
                for d in T.project_dates(conn, root, hit_keys,
                                         caller="ask.lookup")}
            cov = LK.HitCovariates(subject_state=subject_state_of,
                                   doc_date=date_of)
            lk = LK.lookup_answer(root, question, hits, covariates=cov,
                                  scope=INTENT_LAST or "unscoped")
        except Exception as e:  # fail-open by contract, reason printed
            print(LK.GRAMMAR["fallthrough"].format(reason=f"failed: {e}"))
            lk = None
        if _typed_lookup_applies(lk):
            LOOKUP_LAST = lk
            STAGES_LAST["lookup_answer"] = lk.answer_cache_key
            return (lk.rendered, cards, scores)

    # The aggregate family (design §8, r21): the second-stage router runs ONLY on the
    # declined path — ROUTE_PROMPT stays byte-identical, lookup admissions never
    # re-mint — and admits to aggregate only on a confident sum-shaped verdict;
    # anything else (including every failure, named) falls to narrative as today.
    if families and root is not None:
        try:
            ag_route = AGG.route_aggregate(root, question)
        except Exception as e:  # fail-open by contract, reason printed
            print(f"aggregate route failed: {e} — narrative answers")
            ag_route = None
        if ag_route is not None:
            try:
                registry, reg_note = _generators()
                ag = AGG.aggregate_answer(root, conn, question, hits, ag_route,
                                          brain=LK.shared_brain(),
                                          registry=registry,
                                          registry_note=reg_note)
            except Exception as e:  # fail-open by contract, reason printed
                print(f"aggregate failed: {e} — narrative answers")
            else:
                AGGREGATE_LAST = ag
                STAGES_LAST["aggregate_answer"] = ag.answer_cache_key
                return (AGG.render_aggregate(ag), cards, scores)

    # synthesize — keyed on the retrieved CONTENT (early cutoff) and the profile hash; the
    # synthesizer lives in core.synthesis (shared with the bridge). The retrieval_set lineage is
    # ask-side (rerank has no retrieve key), threaded through as extra lineage.
    extra = [{"cache_key": rkey.cache_key, "role": "retrieval_set"}] if rkey else []
    text, scache, scached = SYN.synthesize(root, question, hits, profile, no_cache=no_cache,
                                           extra_lineage=extra)
    if root is not None:  # caching telemetry only when a cache is in play (root resolved)
        _count("synthesize", hit=scached)
    STAGES_LAST["synthesize"] = scache
    if not families:  # the monolithic instrument: raw synthesize prose, unscored
        return (text, cards, scores)
    return (_narrative_scored(root, question, text, cards,
                              scope=INTENT_LAST or "unscoped"), cards, scores)


def _narrative_scored(root: Path | None, question: str, text: str,
                      cards: list[C.SourceCard], *, scope: str = "unscoped") -> str:
    """The narrative family's scorer (foundations §7) over the synthesize proposal:
    parse → audit cells → population credences → per-claim EU decision → labeled
    render. Read-side policy — the proposal artifact and its keys are untouched —
    rerun on every call so scorer/fold movement re-scores cached prose. Any failure
    is fail-open and NAMED: the raw prose still reaches the owner, marked unscored
    (interaction contract — nothing silent)."""
    global NARRATIVE_LAST
    if root is None:
        return text
    try:
        # cast: the seam may be stubbed to None (the conftest hermetic fixture)
        nv = cast("N.NarrativeResult | None",
                  N.narrative_answer(root, question, text, cards, scope=scope,
                                     synthesize_cache_key=STAGES_LAST.get("synthesize")))
    except Exception as e:  # fail-open by contract, reason printed
        print(N.GRAMMAR["fallthrough"].format(reason=f"failed: {e}"))
        return text
    if nv is None:  # the disabled seam (hermetic tests stub the family to None)
        return text
    NARRATIVE_LAST = nv
    STAGES_LAST["narrative_answer"] = nv.answer_cache_key
    return nv.rendered

