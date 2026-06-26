"""The probe library — discriminating signals the answer-brain selects by VOI.

A *probe* gathers evidence over the candidate posterior. The brain prices each by
``net_voi - cost`` and applies the arg-max (the govern+steer loop); none is a
hand-set covariate or a rank heuristic. Every re-weighting probe lands on ONE seam —
the group-noisy-channel reliability ``r_d = rho · authority · subject_factor ·
time_factor`` (the covariate :func:`life_agent.core.lookup.lookup_posterior` ships per
document). Two kinds:

    re-weight   project a §4.1 covariate over the EXISTING hit set (read-side,
                cached) → :class:`life_agent.core.lookup.HitCovariates` →
                ``observe_hits`` → ``r``
    gather      fetch NEW evidence (targeted retrieval) → new observations → re-run

The probes REUSE the projection machinery (:mod:`life_agent.core.temporal`,
:mod:`life_agent.core.subject`, :func:`life_agent.core.lookup.authority_for`, the
``pkm.retrieval`` seam) — they never rebuild it, and they are read-only over the
catalogue (they project current artifacts; they never derive). They are the
permanent life-agent capabilities the pi-mono answer agent exposes as tools; the
Stage-0 loop driver and the eventual Julia brain both call exactly these.

Each probe pairs an impure projection edge with a pure mapping core (the
``project_dates``/``apply_temporal`` split already in the codebase): the pure cores
(``_recency_covariate`` / ``_subject_covariate`` / :func:`probe_authority` /
``_fresh_hits``) carry the testable logic; the edges only do I/O.

Finding (2026-06-16, real-probe validation): for "my current X" point facts the brain
selects **{recency, authority, corroborate}** and DESELECTS **{subject}** —
"is the document *about* the owner" penalises the administrative records that merely
*carry* the owner's current contact (a National-Insurance form's subject is not the
owner, yet it lists his live number). ``probe_subject`` therefore WEIGHTS, never
FILTERS (unlike ``ask._apply_subject_to_hits``, which drops ``not_owner``): a
deselected weight degrades gracefully where a filter would delete the truth. Kept for
the classes where whose-document IS the discriminator (the partner-ID class).
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

import duckdb

from life_agent.core import subject as S
from life_agent.core import temporal as T
from life_agent.core.lookup import authority_for
from pkm.cache import content_file

# --- recency probe (re-weight): doc_date → time_factor decays stale evidence ----------


def _recency_covariate(dated: list[T.DatedHit]) -> dict[str, str | None]:
    """Pure: the ``HitCovariates.doc_date`` map from a temporal projection. A dated hit
    carries its ISO date; an undated/underived hit maps to ``None`` — the probe DID
    project, so an absent date is "projected but unknown" (the kernel's stated
    ``_A_TIME_UNKNOWN`` attenuation), distinct from a key the probe never touched
    (absent → factor 1.0)."""
    return {h.artifact_cache_key: (h.date.isoformat() if h.date is not None else None)
            for h in dated}


# The email producer's name (pkm.producers.email_producer.EmailProducer.name): a hit
# whose artifact this produced carries a Date header in its rendered content, so a missing
# doc_date projection can be filled from it read-side (the stale-vs-current discriminator).
_EMAIL_PRODUCER = "email"


def _date_from_email_text(text: str) -> str | None:
    """Pure: the ISO date from an email artifact's rendered ``Date:`` header — the fixed
    header block the email producer emits first (``headers + "\\n\\n" + body``). None if
    absent or unparseable. Mirrors what ``doc_date_email`` would derive; the read-only
    fallback used where the projection is absent."""
    header_block = text.split("\n\n", 1)[0]
    for line in header_block.splitlines():
        if line.lower().startswith("date:"):
            try:
                dt = parsedate_to_datetime(line[len("date:"):].strip())
            except (TypeError, ValueError):
                return None
            return dt.date().isoformat() if dt is not None else None
    return None


def _email_header_date(root: Path, key: str) -> str | None:
    """Read-only edge: the email ``Date`` header for one artifact, or None on any read
    failure (the fallback must never break the loop)."""
    try:
        text = content_file(root, key).read_text("utf-8", errors="replace")
    except OSError:
        return None
    return _date_from_email_text(text)


def probe_recency(conn: duckdb.DuckDBPyConnection, root: Path, hit_keys: list[str], *,
                  caller: str = "probe.recency") -> dict[str, str | None]:
    """Project the current ``doc_date`` over each hit → the ``doc_date`` covariate that
    re-weights time-indexed candidates by document age (``lookup.time_factor``). Read-only
    (reuses :func:`life_agent.core.temporal.project_dates`); never derives.

    The derived projection covers only a sliver of the corpus today, yet the dates that
    discriminate stale-from-current evidence live in email ``Date`` headers. So for any
    EMAIL-produced hit the projection left dateless, fill the gap from a read-only parse of
    that header — exactly the date ``doc_date_email`` would derive, without a write. A
    projected date always wins (it is authoritative); the fallback only ADDS dates where
    there were none, and only for email artifacts (a PDF that merely starts "Date:" is left
    alone)."""
    dated = T.project_dates(conn, root, hit_keys, caller=caller)
    cov = _recency_covariate(dated)
    for h in dated:
        if cov[h.artifact_cache_key] is None and h.extractor == _EMAIL_PRODUCER:
            cov[h.artifact_cache_key] = _email_header_date(root, h.artifact_cache_key)
    return cov


# --- authority probe (baseline signal; here surfaced as an inspectable feature) -------


def probe_authority(hits: list[Mapping[str, Any]]) -> dict[str, tuple[str, float]]:
    """The declared v0 source-authority class per hit (document 0.95 / email 0.90 /
    note 0.80), keyed on origin path. Already applied unconditionally inside
    ``observe_hits``; surfaced here as a first-class, inspectable signal — the brain's
    feature extractor reads it ("do the candidates differ in authority?") and it is the
    seam to enrich source-type later. Pure; reuses
    :func:`life_agent.core.lookup.authority_for`."""
    return {str(h["artifact_cache_key"]): authority_for(str(h.get("origin", "")))
            for h in hits}


# --- subject probe (re-weight): whose-document → subject_factor ------------------------

# project_subjects state + owner verdict → the subject_factor partition vocabulary
# (lookup.subject_factor: owner→1.0, other/generic→0.05, unclear/underived→0.525).
_VERDICT_TO_STATE: dict[str, str] = {
    "owner": "owner", "not_owner": "other", "unclear": "unclear",
}


def _subject_covariate(subs: list[S.SubjectedHit],
                       verdict_of: Mapping[str, str]) -> dict[str, str]:
    """Pure: the ``HitCovariates.subject_state`` map from a subject projection plus the
    cached owner verdicts. ``underived``/``generic`` pass through as themselves; a named
    hit maps through its verdict; a named hit with an empty subject or no verdict is
    ``unclear`` (indeterminate, never dropped). The probe WEIGHTS — it never excludes."""
    state: dict[str, str] = {}
    for h in subs:
        if h.state == "underived":
            state[h.artifact_cache_key] = "underived"
        elif h.state == "generic":
            state[h.artifact_cache_key] = "generic"
        else:  # "named"
            verdict = verdict_of.get(h.subject or "")
            state[h.artifact_cache_key] = _VERDICT_TO_STATE.get(verdict or "", "unclear")
    return state


def probe_subject(conn: duckdb.DuckDBPyConnection, root: Path, hit_keys: list[str], *,
                  profile: str, client: Any | None = None,
                  caller: str = "probe.subject") -> dict[str, str]:
    """Project the current ``doc_subject`` over each hit and classify its subject against
    the owner ``profile`` (cached local verdict, bounded by distinct subjects) → the
    ``subject_state`` covariate. WEIGHTS, never filters — the deselect-for-contact-facts
    finding (module docstring). Read-only; reuses
    :func:`life_agent.core.subject.project_subjects` + ``owner_verdict``."""
    subs = S.project_subjects(conn, root, hit_keys, caller=caller)
    verdict_of: dict[str, str] = {}
    for h in subs:
        subj = h.subject if h.state == "named" else None
        if subj and subj not in verdict_of:
            verdict_of[subj] = S.owner_verdict(root, subj, profile, client=client)
    return _subject_covariate(subs, verdict_of)


# --- corroborate probe (gather): targeted re-retrieval on the leading candidate -------


def _fresh_hits(hits: list[dict[str, Any]],
                exclude_keys: Iterable[str]) -> list[dict[str, Any]]:
    """Pure: drop hits whose document we already hold, so corroboration counts only
    INDEPENDENT new ancestry groups (the §4.2 temper rewards independent documents, not
    more chunks of one we have)."""
    seen = set(exclude_keys)
    return [h for h in hits if h["artifact_cache_key"] not in seen]


def probe_corroborate(conn: duckdb.DuckDBPyConnection, question: str, leader_value: str,
                      *, k: int = 20,
                      exclude_keys: Iterable[str] = ()) -> list[dict[str, Any]]:
    """Re-retrieve for the current leading candidate (its value appended as a query term)
    to surface MORE corroborating documents than the question alone found — the lever from
    abstain-with-clear-leader toward a confident report (more independent recent /
    high-authority observations concentrate the posterior). Returns new hit dicts
    (``artifact_cache_key`` / ``chunk_text`` / ``score`` / ``origin``), excluding documents
    already in hand. Mirrors ``ask._retrieve_set`` over the ``pkm.retrieval`` seam."""
    from pkm.retrieval import SearchResult, search

    best: dict[str, SearchResult] = {}
    for h in search(conn, f"{question} {leader_value}", k=k * 4):
        prev = best.get(h.chunk_text)
        if prev is None or h.score > prev.score:
            best[h.chunk_text] = h
    top = sorted(best.values(), key=lambda h: h.score, reverse=True)[:k]
    hits = [{"artifact_cache_key": h.artifact_cache_key, "chunk_text": h.chunk_text,
             "score": h.score, "origin": h.source_path} for h in top]
    return _fresh_hits(hits, exclude_keys)
