# SPEC v0.3.0 — Phase 3 addition (retrieval substrate)

**Status:** draft
**Supersedes:** nothing in v0.1.x / v0.2.0; extends.
**Reads with:** [`SPEC-PRINCIPLES.md`](./SPEC-PRINCIPLES.md) — the cross-version foundation this
document instantiates. Where v0.3.0 makes a choice, it cites the principle it follows.

**Scope:** authorises the retrieval substrate (chunks, local embeddings, hybrid search, a local MCP
server), hardens the transform cache key to close reproducibility gaps, and commits source
granularity for the upcoming email/chat adapters. One migration (0004) lands the storage shape; the
retrieval *query* implementation and chunking *parameters* are deliberately deferred until the
Phase-0 failure log says what they must be.

This document extends v0.1.x and v0.2.0. All prior invariants hold. New invariants continue the
v0.2.0 numbering (last was 13).

## 28. Scope of this addition

v0.3.0 specifies:

1. The hardened transform cache key (§29) — `schema_version: 3`.
2. Source granularity for email and chat (§30).
3. Embedding identity (§31).
4. Authorisation of the retrieval substrate and a local MCP server (§32).
5. The storage shape for chunks + embeddings (§33, migration 0004).

v0.3.0 does NOT specify (deferred until the Phase-0 measurement says so):

- The chunking *strategy/parameters* (window sizes, token thresholds) beyond the defaults named in
  §30. The granularity is committed; the tuning is empirical.
- The hybrid-search ranking/fusion algorithm and the `pkm search` query surface internals.
- A re-ranking model, query planner, or prompt-tuning (DSPy) pipeline.
- `EmailNormalizationProducer` implementation (declared in §30, implemented when email ingestion lands).
- Any embedding/retrieval over photos or the encrypted archive.

The §12 (v0.1.x) out-of-scope lines "Embeddings and vector search (Phase 2)" and the v0.2.0 §26
"Vector index / embeddings — not in v0.2.0" are hereby lifted: embeddings and vector search are
**in scope for v0.3.0**, at the storage + identity level specified below.

## 29. Cache-key hardening (extends v0.2.0 §17)

### 29.1 Motivation (PRINCIPLES §2)

PRINCIPLES §2 defines an event's identity as the hash of *everything that defines what the event is*
— "model version, SDK version, prompt template hash, output schema hash, and any other input." The
v0.2.0 `schema_version: 2` transform payload (§17.1) omits three of these: the inference-engine/SDK
version, the output schema, and the prompt *template* (it hashes the rendered prompt instead). Each
omission is a way for two materially different events to collide on one cache key — a silently wrong
cache hit. v0.3.0 closes them with a new payload format.

### 29.2 The `schema_version: 3` transform payload

```
cache_key = sha256(canonical_json({
    "schema_version":        3,
    "input_hash":            <sha256 of input content>,
    "producer_name":         <str>,
    "producer_version":      <semver>,
    "producer_config_hash":  <sha256 of canonical config>,
    "model_identity_hash":   <sha256 of canonical model_identity>,
    "engine_version":        <inference-engine / SDK version string>,
    "prompt_template_hash":  <sha256 of the prompt TEMPLATE text, with placeholders>,
    "output_schema_hash":    <sha256 of canonical output schema>,
}))
```

Canonicalisation is the v0.1.x §4.1 rule, unchanged. `schema_version` remains the monotonic format
discriminator (§17.1): extractors are `1`, legacy transforms `2`, hardened transforms `3`. The three
formats are non-overlapping by construction.

- **`engine_version`** — the version string of the inference engine / SDK that produced the output
  (e.g. the `anthropic` SDK version for LLM transforms; the Ollama/engine version for local
  producers). Per PRINCIPLES §2 the engine is part of "what produced this": an SDK or engine change
  can change outputs, so it must count as a different event. (This is a software version, not a
  §4.4-excluded field — `producer_version` is already in the key for the same reason.)
- **`prompt_template_hash`** replaces v0.2.0's `prompt_hash`. §17.3 hashed the *rendered* prompt
  (template + substituted text). But the substituted text is the input, already captured by
  `input_hash`; hashing the rendered prompt therefore double-counts the input while giving the
  template no independent identity. The template — the part that is genuinely *the producer's
  configuration* — is hashed on its own. Two runs with the same template and input agree; a
  template edit changes the key; an input change changes the key via `input_hash`.
- **`output_schema_hash`** — `sha256(canonical_json(output_schema))`. If the declared schema changes,
  the event is different (it constrains and validates the output), so the key must differ.

### 29.3 Amendment to §17.3 and migration of existing artefacts

§17.3 ("the hash is over the rendered text") is superseded for `schema_version: 3` by §29.2's
template-hash rule. v0.2.0 `schema_version: 2` artefacts remain valid, queryable, and inspectable;
the system does not delete them. They are simply no longer *produced*: a transform run now computes a
`schema_version: 3` key, which misses the old `2` key, so the artefact recomputes **lazily on the
next run** (PRINCIPLES §3 — the cache is a view over the event record; a new event identity is a new
event). This strands the current transform artefacts (entity-extraction outputs); rebuilding them is
a small, lazy cost paid as extraction re-runs, and is far cheaper now than after email/chat multiply
the transform count.

`meta.json` records `cache_key_schema_version: 3` for hardened transform artefacts (extending the
§17.1 inspectability rule). The v0.2.0 `>= 2` checks in the cache/rebuild layer continue to apply.

## 30. Source granularity — email and chat (PRINCIPLES §1, §4)

Sources are **message-level**.

- An **email source** is one RFC 5322 message. Its `source_id` is `sha256` of the **raw message
  bytes as received**. De-quoting, header canonicalization, and other normalization are performed by
  `EmailNormalizationProducer` (`schema_version: 1`, **declared but not implemented in this phase**),
  which emits a *derivation* consumed by downstream transforms. Per PRINCIPLES §1 and §4, the raw
  bytes are the source; the normalized form is a derivation whose correctness is empirical.
- A **chat source** is one message, keyed by `(room_id, event_id)` for Matrix (equivalent for other
  protocols). Matrix events are protocol-defined canonical JSON and qualify as sources by §1 directly.

Threads and rooms are **attributes** of sources, not sources themselves. Thread reconstruction is a
query-time view via `In-Reply-To`/`References` (email) or reply relations (chat).

Chunking is a **separate axis** from source granularity. Defaults (parameters tunable post-Phase-0):
chat chunking groups same-author messages within a 5-minute window; email chunks at the message
boundary unless the body exceeds a configured token threshold. Citation always resolves to the
constituent message(s); a window is an indexing optimisation, never a source identity.

Rationale: citation precision; immutable content-addressing (a message is immutable, a thread
mutates); aggregation upward is cheap, disaggregation downward is impossible.

## 31. Embedding identity

Embeddings are **768-dimensional**, produced by `nomic-embed-text` via local Ollama. The model and
dimensionality are recorded here so they are not smuggled in as a bare column type. Changing the
embedding model or dimensionality requires a subsequent migration (the stored vectors are not
comparable across models). An embedding is a derivation (PRINCIPLES §1) over a chunk; its event
identity (PRINCIPLES §2) includes the embedding model identity and engine version, by the §29 rule.

## 32. Retrieval substrate + local MCP server (authorisation)

v0.3.0 authorises, at the storage and identity level:

- **Chunks** — derivations over extractor/normalization output, stored per §33.
- **Local embeddings** — per §31, over chunks.
- **Hybrid search** — DuckDB `fts` (keyword) + `vss` (HNSW cosine over `FLOAT[768]`). Implementation
  note (not a contract): `vss` filtered top-k runs the index before `WHERE`, so over-fetch k·10 then
  filter; set `hnsw_enable_experimental_persistence=true`; the `.duckdb` is backed up by borg.
- **A local MCP server** (`pkm-memory`) exposing read-only retrieval over the catalogue, bound to a
  Tailscale interface only. The tool surface and ranking are deferred (§28).

These are *seams named*, not fully specified — mirroring v0.2.0's discipline (§27): the query surface
and ranking are designed against the Phase-0 failure log, not speculation.

**Subject provenance is a first-class concern.** The Phase-0 measurement surfaced a structural
requirement: the *subject* of a fact (whom it is about — and in particular whether the subject is the
owner) is distinct from its *source* and is **not** derivable from `source_id`. Retrieval and any
fact-extracting transform must carry subject-of-fact alongside source provenance, so "the owner's ID"
disambiguates from "an ID in the owner's documents". Specification deferred (designed against the
failure log), but flagged here so it is not treated as derivable from `source_id`.

## 33. Storage shape for chunks + embeddings (migration 0004)

Migration `0004_chunks_and_embeddings.py` (additive; mirrors 0003's derived-table philosophy — a new
table, not columns on `artifacts`):

```sql
CREATE TABLE artifact_chunks (
    artifact_cache_key  VARCHAR     NOT NULL,   -- the derivation this chunk came from
    chunk_index         INTEGER     NOT NULL,
    chunk_text          VARCHAR     NOT NULL,
    embedding           FLOAT[768],             -- §31; NULL until embedded
    source_origin       VARCHAR,                -- provenance label (e.g. ocr, parsed-text, email)
    PRIMARY KEY (artifact_cache_key, chunk_index),
    FOREIGN KEY (artifact_cache_key) REFERENCES artifacts(cache_key)
);
CREATE INDEX idx_chunks_cache_key ON artifact_chunks(artifact_cache_key);
```

No existing table is modified. `embedding` is nullable so chunking and embedding can land as separate
steps. The HNSW (`vss`) index over `embedding` is created at retrieval-build time, not in this
migration (it is rebuildable and experimental-persistence-gated).

## 34. Invariants added in v0.3.0

Continuing the v0.2.0 numbering:

- **Invariant 14**: The transform cache key includes the inference-engine/SDK version, the prompt
  *template* hash, and the output schema hash (`schema_version: 3`). Omitting any of them is a
  silently-wrong-cache-hit bug. (§29)
- **Invariant 15**: A source's `source_id` is `sha256` of bytes that exist independently of PKM and
  is reproducible by `sha256sum` outside PKM. Normalized/derived forms are derivations, never
  sources. (§30, PRINCIPLES §1)
- **Invariant 16**: Embedding dimensionality and model are fixed by spec (§31); changing either
  requires a migration.

## 35. What v0.3.0 proves / defers

v0.3.0 lands the *identity and storage* foundation for retrieval — the parts that are painful to
retrofit once the cache grows — and defers the *behavioural* parts (chunking parameters, ranking,
the query surface, `EmailNormalizationProducer`) to be designed against the Phase-0 failure log. As
in v0.2.0 (§27), the evidence for those decisions will come from real usage, not speculation.

## 36. Change log

- 0.3.0 (draft): Initial Phase-3 addition. Adds SPEC-PRINCIPLES reference; hardens the transform
  cache key to `schema_version: 3` (engine version + prompt-template hash + output-schema hash),
  superseding §17.3's rendered-prompt hash and stranding `schema_version: 2` artefacts for lazy
  rebuild; commits message-level source granularity for email/chat with `EmailNormalizationProducer`
  declared-not-implemented; fixes embeddings at 768-dim `nomic-embed-text`; authorises the chunks +
  embeddings + hybrid-search + local-MCP retrieval substrate and lands migration 0004
  (`artifact_chunks`). Behavioural specifics (chunking parameters, ranking, query surface) deferred
  to design against the Phase-0 failure log.
