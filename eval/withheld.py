"""The withheld-source mode: each question re-asked with every document that attests its
answer taken out of retrieval.

The answer is then absent from everything the act can read, so the right behaviour is to
decline and anything asserted is wrong, unless the asserted value matches the gold, which
means an attestation leaked past the withholding (a document the finder missed). The pieces
here are pure or take a read-only catalogue connection; the run itself is ``eval.run
--withhold-source`` and ``scripts/fit_posterior.py capture --withhold-source``.

An attestation is any chunk the grader's own matcher (``matching.answer_matches``) finds the
gold or a variant in, so the withholding covers every document the act could have answered
from, not only the one the question was generated from. Nothing here prints a question, a
candidate or a gold.
"""
from __future__ import annotations

import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from life_agent.core import config as CFG
from life_agent.core.matching import answer_matches, tokenize

#: A gold attested by more documents than this is too common to withhold meaningfully.
MAX_ARTIFACTS = 500

RETRIEVE_SUFFIX = "/retrieve"
EXCLUDE_FIELD = "exclude_artifacts"


@dataclass(frozen=True)
class Withholding:
    """What to take out of retrieval for one question, or why the question is skipped."""

    keys: frozenset[str] = frozenset()
    skipped: str | None = None          # "empty_gold" | "too_many" | None = run it


def _chunks_with_tokens(conn: Any, tokens: Sequence[str]) -> list[tuple[str, str]]:
    """``(artifact_cache_key, chunk_text)`` of every chunk whose FTS tokens include all of
    ``tokens`` (conjunctive BM25 over the catalogue's own index)."""
    return [(str(k), str(t)) for k, t in conn.execute(
        """
        SELECT artifact_cache_key, chunk_text FROM (
            SELECT artifact_cache_key, chunk_text,
                   fts_main_artifact_chunks.match_bm25(
                       chunk_id, ?, fields := 'chunk_text', conjunctive := 1) AS score
            FROM artifact_chunks)
        WHERE score IS NOT NULL
        """, [" ".join(tokens)]).fetchall()]


def attesting_artifacts(conn: Any, gold: str, variants: Sequence[str]) -> frozenset[str]:
    """Every artifact with any chunk the grader's matcher finds the gold (or a variant) in.
    The index proposes the chunks that carry every token of a form; the matcher confirms
    the tokens sit contiguously, so a number inside a longer number is not an attestation.
    A chunk that is itself a date in another format than every form is not proposed."""
    forms = [f for f in [gold, *variants] if tokenize(f)]
    return frozenset(
        key for form in forms for key, text in _chunks_with_tokens(conn, tokenize(form))
        if answer_matches(gold, list(variants), text))


def plan(conn: Any, q: Mapping[str, Any], *, max_artifacts: int = MAX_ARTIFACTS) -> Withholding:
    """The artifacts to withhold for ``q``: its own provenance artifact, always, plus every
    other attestation. An empty gold, or one attested by more than ``max_artifacts``
    documents, is skipped and counted, not run."""
    gold, variants = str(q.get("answer") or ""), list(q.get("answer_variants") or [])
    if not tokenize(gold):
        return Withholding(skipped="empty_gold")
    own = (q.get("provenance") or {}).get("artifact_cache_key")
    keys = attesting_artifacts(conn, gold, variants) | ({str(own)} if own else frozenset())
    if len(keys) > max_artifacts:
        return Withholding(skipped="too_many")
    return Withholding(keys)


def with_exclusion(post: Callable[..., Any], keys: frozenset[str]) -> Callable[..., Any]:
    """``post`` carrying ``exclude_artifacts`` on every ``/retrieve`` request and nothing else."""
    def wrapped(url: str, payload: dict[str, Any]) -> Any:
        if url.endswith(RETRIEVE_SUFFIX):
            payload = {**payload, EXCLUDE_FIELD: sorted(keys)}
        return post(url, payload)
    return wrapped


def force_deliberate_off() -> None:
    """The deliberative rung searches the corpus through its own MCP server, where no
    withholding reaches; the mode runs with it off or not at all."""
    os.environ[CFG.DELIBERATE_ENV] = "0"
    if CFG.deliberate_enabled():
        raise SystemExit("REFUSED: the deliberative rung cannot be turned off; a "
                         "withheld-source run would leak the corpus through it")

