"""Ask-stage derivations, recorded into the pkm cache (pkm SPEC §18.9).

The north star (PRINCIPLES §1, §2): ``answer = f(corpus_state, question)`` is a
content-addressed derivation in the same DAG as every other artifact. This module is the
write/read seam for the ask pipeline's three cacheable stages —

    expand     question → BM25 terms            (LLM, schema-3 key)
    retrieve   (query, corpus_digest) → hit set (deterministic, schema-1 key)
    synthesize (question, retrieval-set content hash, profile hash) → answer
                                                (LLM, schema-3 key)

— keyed through ``pkm.hashing.compute_cache_key`` (the ONE key function, SPEC §4.3) and
written **file-first**: content → ``lineage.json`` → ``meta.json`` in pkm's §6.2 order,
without a catalogue connection (the ask path deliberately holds a *read-only* one so a
running extraction never blocks an answer). ``meta.json`` is authoritative and the
catalogue is a rebuildable index (SPEC §13.1); :func:`reconcile` inserts the lagging
catalogue rows opportunistically, fed by a pending queue under ``<root>/external/``.

Only successes are recorded — a transient model failure must never be frozen as the
replayed result. The stage content types are deliberately NOT chunk-eligible: a derived
answer must not re-enter retrieval before staleness tooling exists (SPEC §18.9).
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from pkm.cache import (
    META_FORMAT_VERSION,
    content_file,
    content_path_rel,
    lineage_file,
    meta_file,
)
from pkm.hashing import canonical_json, compute_cache_key

# The runtime identity for schema-3 keys (SPEC §18.4): the call path is the stdlib HTTP
# client in life_agent.core.llm, pinned as a constant (the Ollama-precedent option).
ENGINE_VERSION = "life_agent.core.llm/1"

# Stage producer versions — bump ONE deliberately to orphan that stage's cache when its
# semantics change (e.g. the dedupe rule in retrieve, the rendering in synthesize).
EXPAND_VERSION = "1"
RETRIEVE_VERSION = "1"
SYNTHESIZE_VERSION = "1"
OWNER_MATCH_VERSION = "1"
LOOKUP_ROUTE_VERSION = "1"
LOOKUP_EXTRACT_VERSION = "1"
LOOKUP_ANSWER_VERSION = "1"
NARRATIVE_ANSWER_VERSION = "1"

# Free-text output contract for both LLM stages (schema-3 keys require an output schema).
TEXT_OUTPUT_SCHEMA: dict[str, Any] = {"type": "string"}

# Distinct content types per stage. None of these may EVER enter pkm's
# CHUNKABLE_CONTENT_TYPES — that is the retrieval gate of SPEC §18.9.
CONTENT_TYPE_EXPAND = "application/x-ask-expand"
CONTENT_TYPE_RETRIEVAL_SET = "application/x-ask-retrieval-set+json"
CONTENT_TYPE_ANSWER = "application/x-ask-answer"
CONTENT_TYPE_OWNER_MATCH = "application/x-ask-owner-match+json"
CONTENT_TYPE_LOOKUP_ROUTE = "application/x-ask-lookup-route+json"
CONTENT_TYPE_LOOKUP_OBSERVATION = "application/x-ask-lookup-observation+json"
CONTENT_TYPE_LOOKUP_ANSWER = "application/x-ask-lookup-answer+json"
CONTENT_TYPE_NARRATIVE_ANSWER = "application/x-ask-narrative-answer+json"

_PENDING_QUEUE = Path("external") / "pending.txt"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def content_hash(content: bytes) -> str:
    """SHA-256 hex of stage content bytes — e.g. the retrieval-set hash that keys the
    synthesize stage (the early-cutoff hinge: it hashes what was retrieved, not the
    corpus digest, so a corpus change that retrieves the same evidence replays)."""
    return hashlib.sha256(content).hexdigest()


@dataclass(frozen=True)
class StageKey:
    """Everything that identifies one stage derivation: the cache key plus the readable
    inputs and producer identity needed to record it with jq-inspectable provenance."""

    cache_key: str
    input_hash: str
    producer_name: str
    producer_version: str
    producer_config: dict[str, Any]
    schema_version: int
    inputs: dict[str, Any]
    content_type: str


def _llm_identity(model: str, temperature: float, max_tokens: int) -> dict[str, Any]:
    return {
        "provider": "anthropic",
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }


def expand_key(question: str, *, model: str, prompt_template: str,
               temperature: float, max_tokens: int) -> StageKey:
    """Key for the query-expansion stage. Corpus-independent by construction — corpus
    growth never invalidates an expansion."""
    inputs = {"question": question}
    input_hash = _sha256(canonical_json(inputs))
    cache_key = compute_cache_key(
        input_hash, "life_agent.ask.expand", EXPAND_VERSION, {},
        schema_version=3,
        model_identity=_llm_identity(model, temperature, max_tokens),
        engine_version=ENGINE_VERSION,
        prompt_template_hash=_sha256(prompt_template),
        output_schema=TEXT_OUTPUT_SCHEMA,
    )
    return StageKey(cache_key=cache_key, input_hash=input_hash,
                    producer_name="life_agent.ask.expand",
                    producer_version=EXPAND_VERSION, producer_config={},
                    schema_version=3, inputs=inputs, content_type=CONTENT_TYPE_EXPAND)


def retrieve_key(query: str, corpus_digest: str, *, k: int) -> StageKey:
    """Key for the retrieval stage: deterministic given (query, corpus state, k), so a
    schema-1 (extractor-style) key — no model identity."""
    inputs = {"corpus": corpus_digest, "query": query}
    input_hash = _sha256(canonical_json(inputs))
    config = {"k": k}
    cache_key = compute_cache_key(
        input_hash, "life_agent.ask.retrieve", RETRIEVE_VERSION, config,
        schema_version=1,
    )
    return StageKey(cache_key=cache_key, input_hash=input_hash,
                    producer_name="life_agent.ask.retrieve",
                    producer_version=RETRIEVE_VERSION, producer_config=config,
                    schema_version=1, inputs=inputs,
                    content_type=CONTENT_TYPE_RETRIEVAL_SET)


def synthesize_key(question: str, retrieval_set_hash: str, profile_hash: str, *,
                   model: str, prompt_template: str,
                   temperature: float, max_tokens: int) -> StageKey:
    """Key for the synthesis stage. Keyed on the retrieval set's CONTENT hash (early
    cutoff) and the owner-profile hash (a ``/i`` teach invalidates exactly this stage)."""
    inputs = {"profile": profile_hash, "question": question,
              "retrieval_set": retrieval_set_hash}
    input_hash = _sha256(canonical_json(inputs))
    cache_key = compute_cache_key(
        input_hash, "life_agent.ask.synthesize", SYNTHESIZE_VERSION, {},
        schema_version=3,
        model_identity=_llm_identity(model, temperature, max_tokens),
        engine_version=ENGINE_VERSION,
        prompt_template_hash=_sha256(prompt_template),
        output_schema=TEXT_OUTPUT_SCHEMA,
    )
    return StageKey(cache_key=cache_key, input_hash=input_hash,
                    producer_name="life_agent.ask.synthesize",
                    producer_version=SYNTHESIZE_VERSION, producer_config={},
                    schema_version=3, inputs=inputs, content_type=CONTENT_TYPE_ANSWER)


def owner_match_key(subject: str, profile_hash: str, *, model: str,
                    prompt_template: str, engine_version: str,
                    output_schema: dict[str, Any]) -> StageKey:
    """Key for one owner-match verdict (D2): is this projected document subject
    the owner? Keyed on the subject STRING (verdicts are shared across every
    document naming the same subject) and the profile hash (a ``/tell`` or
    profile edit invalidates exactly the verdicts). Local model — the profile
    never leaves the machine and never enters pkm."""
    inputs = {"profile": profile_hash, "subject": subject}
    input_hash = _sha256(canonical_json(inputs))
    cache_key = compute_cache_key(
        input_hash, "life_agent.ask.owner_match", OWNER_MATCH_VERSION, {},
        schema_version=3,
        model_identity={"provider": "ollama", "model": model,
                        "inference_params": {"temperature": 0.0}},
        engine_version=engine_version,
        prompt_template_hash=_sha256(prompt_template),
        output_schema=output_schema,
    )
    return StageKey(cache_key=cache_key, input_hash=input_hash,
                    producer_name="life_agent.ask.owner_match",
                    producer_version=OWNER_MATCH_VERSION, producer_config={},
                    schema_version=3, inputs=inputs,
                    content_type=CONTENT_TYPE_OWNER_MATCH)


def lookup_route_key(question: str, *, model: str, prompt_template: str,
                     engine_version: str, output_schema: dict[str, Any]) -> StageKey:
    """Key for one lookup-route verdict (foundations §4.1): is this question a typed
    point-fact lookup? Local model, cached per question — a confusion-matrix-class
    instrument whose misroutes fall to the narrative path (§9 no-hard-zeros)."""
    inputs = {"question": question}
    input_hash = _sha256(canonical_json(inputs))
    cache_key = compute_cache_key(
        input_hash, "life_agent.ask.lookup_route", LOOKUP_ROUTE_VERSION, {},
        schema_version=3,
        model_identity={"provider": "ollama", "model": model,
                        "inference_params": {"temperature": 0.0}},
        engine_version=engine_version,
        prompt_template_hash=_sha256(prompt_template),
        output_schema=output_schema,
    )
    return StageKey(cache_key=cache_key, input_hash=input_hash,
                    producer_name="life_agent.ask.lookup_route",
                    producer_version=LOOKUP_ROUTE_VERSION, producer_config={},
                    schema_version=3, inputs=inputs,
                    content_type=CONTENT_TYPE_LOOKUP_ROUTE)


def lookup_extract_key(question: str, chunk_sha: str, *, model: str,
                       prompt_template: str, engine_version: str,
                       output_schema: dict[str, Any]) -> StageKey:
    """Key for one question-parameterised grounded extraction (foundations §4.1): the
    per-hit instrument observation. life_agent-side because the prompt binds the
    question — pkm transforms stay question-free. Keyed on (question, chunk content),
    so the same evidence answers the same question from cache forever."""
    inputs = {"chunk": chunk_sha, "question": question}
    input_hash = _sha256(canonical_json(inputs))
    cache_key = compute_cache_key(
        input_hash, "life_agent.ask.lookup_extract", LOOKUP_EXTRACT_VERSION, {},
        schema_version=3,
        model_identity={"provider": "ollama", "model": model,
                        "inference_params": {"temperature": 0.0}},
        engine_version=engine_version,
        prompt_template_hash=_sha256(prompt_template),
        output_schema=output_schema,
    )
    return StageKey(cache_key=cache_key, input_hash=input_hash,
                    producer_name="life_agent.ask.lookup_extract",
                    producer_version=LOOKUP_EXTRACT_VERSION, producer_config={},
                    schema_version=3, inputs=inputs,
                    content_type=CONTENT_TYPE_LOOKUP_OBSERVATION)


def lookup_answer_key(question: str, observations_hash: str,
                      utility_fold_version: str,
                      params: dict[str, Any]) -> StageKey:
    """Key for the lookup family's answer artifact (the claim set + posterior +
    decision): deterministic given the observations, the utility fold, and the stated
    channel parameters (schema-1 — no model identity; the models live upstream in the
    observation keys this artifact's lineage names)."""
    inputs = {"observations": observations_hash, "question": question,
              "utility_fold": utility_fold_version}
    input_hash = _sha256(canonical_json(inputs))
    cache_key = compute_cache_key(
        input_hash, "life_agent.ask.lookup_answer", LOOKUP_ANSWER_VERSION, params,
        schema_version=1,
    )
    return StageKey(cache_key=cache_key, input_hash=input_hash,
                    producer_name="life_agent.ask.lookup_answer",
                    producer_version=LOOKUP_ANSWER_VERSION, producer_config=params,
                    schema_version=1, inputs=inputs,
                    content_type=CONTENT_TYPE_LOOKUP_ANSWER)


def narrative_answer_key(question: str, claims_hash: str,
                         utility_fold_version: str,
                         params: dict[str, Any]) -> StageKey:
    """Key for the narrative family's answer artifact (foundations §7: the scored
    claim set + per-claim inclusion decisions + the coverage tail): deterministic
    given the parsed claims, the utility fold, and the stated scorer parameters
    (cell posteriors, coverage posterior — schema-1, no model identity; the
    generator lives upstream in the synthesize artifact this lineage names)."""
    inputs = {"claims": claims_hash, "question": question,
              "utility_fold": utility_fold_version}
    input_hash = _sha256(canonical_json(inputs))
    cache_key = compute_cache_key(
        input_hash, "life_agent.ask.narrative_answer", NARRATIVE_ANSWER_VERSION,
        params, schema_version=1,
    )
    return StageKey(cache_key=cache_key, input_hash=input_hash,
                    producer_name="life_agent.ask.narrative_answer",
                    producer_version=NARRATIVE_ANSWER_VERSION,
                    producer_config=params,
                    schema_version=1, inputs=inputs,
                    content_type=CONTENT_TYPE_NARRATIVE_ANSWER)


# --- file-first cache I/O --------------------------------------------------- #
def lookup(root: Path, cache_key: str) -> bytes | None:
    """The recorded content for a cache key, or None on a miss. ``meta.json`` is the
    commit marker (written last), so a half-written artifact reads as a miss."""
    if not meta_file(root, cache_key).exists():
        return None
    cf = content_file(root, cache_key)
    if not cf.exists():
        return None
    return cf.read_bytes()


def _write_atomic(path: Path, data: bytes) -> None:
    tmp = path.parent / f".{path.name}.{os.getpid()}.tmp"
    tmp.write_bytes(data)
    os.replace(tmp, path)


def record(root: Path, key: StageKey, content: bytes, *,
           lineage: list[dict[str, str]],
           metadata: dict[str, Any] | None = None) -> bool:
    """Record one stage derivation file-first (SPEC §18.9): content → lineage.json →
    meta.json, each atomic, then append the cache key to the pending queue for catalogue
    reconciliation. Write-once: an existing meta.json makes this a no-op returning False.

    ``lineage`` entries are ``{"cache_key": ..., "role": ...}`` pointing at the upstream
    pkm artifacts that contributed (empty for the corpus-independent expand stage).
    """
    mf = meta_file(root, key.cache_key)
    if mf.exists():
        return False

    adir = mf.parent
    adir.mkdir(parents=True, exist_ok=True)

    _write_atomic(content_file(root, key.cache_key), content)
    _write_atomic(
        lineage_file(root, key.cache_key),
        json.dumps({"format_version": 1, "inputs": lineage},
                   indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8"),
    )

    meta: dict[str, Any] = {
        "format_version": META_FORMAT_VERSION,
        "cache_key": key.cache_key,
        "input_hash": key.input_hash,
        "producer_name": key.producer_name,
        "producer_version": key.producer_version,
        "producer_config": key.producer_config,
        "producer_config_hash": _sha256(canonical_json(key.producer_config)),
        "status": "success",
        "produced_at": datetime.now(UTC).replace(tzinfo=None).isoformat(),
        "size_bytes": len(content),
        "error_message": None,
        "content_type": key.content_type,
        "content_encoding": "utf-8",
        "producer_metadata": {"inputs": key.inputs, **(metadata or {})},
    }
    if key.schema_version >= 2:
        meta["cache_key_schema_version"] = key.schema_version
    _write_atomic(mf, json.dumps(meta, indent=2, sort_keys=True,
                                 ensure_ascii=False).encode("utf-8"))

    queue = root / _PENDING_QUEUE
    queue.parent.mkdir(parents=True, exist_ok=True)
    with queue.open("a", encoding="utf-8") as fh:
        fh.write(key.cache_key + "\n")
    return True


# --- catalogue reconciliation ----------------------------------------------- #
def reconcile(root: Path) -> int:
    """Insert the lagging catalogue rows for queued file-first artifacts. Opportunistic:
    returns 0 (queue intact) when the catalogue is absent or its writer lock is held —
    the files remain authoritative (SPEC §13.1) and a later call catches up. Idempotent:
    a key whose row already exists is dropped from the queue without inserting."""
    db = root / "catalogue.duckdb"
    queue = root / _PENDING_QUEUE
    if not db.exists() or not queue.exists():
        return 0
    keys = [k for k in dict.fromkeys(queue.read_text(encoding="utf-8").split()) if k]
    if not keys:
        return 0
    try:
        conn = duckdb.connect(str(db))
    except duckdb.Error:
        return 0  # writer lock held (an extraction is running) — retry next time

    inserted = 0
    remaining: list[str] = []
    try:
        for key in keys:
            try:
                if _reconcile_one(root, conn, key):
                    inserted += 1
            except Exception:
                remaining.append(key)  # half-written or schema-less catalogue; retry later
    finally:
        conn.close()

    # Rewrite the queue, preserving keys appended by another process meanwhile.
    processed = set(keys) - set(remaining)
    current = ([k for k in dict.fromkeys(queue.read_text(encoding="utf-8").split()) if k]
               if queue.exists() else [])
    _write_atomic(queue, ("".join(f"{k}\n" for k in current if k not in processed))
                  .encode("utf-8"))
    return inserted


def _reconcile_one(root: Path, conn: duckdb.DuckDBPyConnection, cache_key: str) -> bool:
    """Insert the artifacts + artifact_lineage rows for one file-complete artifact,
    preserving the recorded ``produced_at``. True iff a row was inserted."""
    mf = meta_file(root, cache_key)
    if not mf.exists():
        raise FileNotFoundError(mf)  # mid-write by another process; keep queued
    if conn.execute("SELECT 1 FROM artifacts WHERE cache_key = ?", [cache_key]).fetchone():
        return False
    meta = json.loads(mf.read_text(encoding="utf-8"))
    lf = lineage_file(root, cache_key)
    lineage = (json.loads(lf.read_text(encoding="utf-8"))["inputs"]
               if lf.exists() else [])
    conn.execute("BEGIN TRANSACTION")
    try:
        conn.execute(
            "INSERT INTO artifacts "
            "(cache_key, input_hash, producer_name, producer_version, "
            " producer_config_hash, status, produced_at, size_bytes, "
            " error_message, content_type, content_encoding, content_path) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                meta["cache_key"], meta["input_hash"], meta["producer_name"],
                meta["producer_version"], meta["producer_config_hash"], meta["status"],
                datetime.fromisoformat(meta["produced_at"]), meta["size_bytes"],
                meta["error_message"], meta["content_type"], meta["content_encoding"],
                content_path_rel(cache_key),
            ],
        )
        for entry in lineage:
            conn.execute(
                "INSERT INTO artifact_lineage "
                "(artifact_cache_key, input_cache_key, role) VALUES (?, ?, ?)",
                [cache_key, entry["cache_key"], entry["role"]],
            )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return True
