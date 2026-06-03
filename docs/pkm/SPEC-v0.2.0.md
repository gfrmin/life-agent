# SPEC v0.2.0 — Phase 2 addition

**Status:** draft
**Supersedes:** nothing in v0.1.x; extends.
**Scope:** adds LLM transforms as a new producer class, with one concrete
transform (entity extraction) specified end-to-end. The substrate seams
for transforms two and three are named; their specifications are
deferred.

This document is an addition to SPEC v0.1.x. All v0.1.x invariants
continue to hold. Where v0.2.0 introduces new invariants, they are
numbered continuing from v0.1.x.

## 15. Scope of this addition

v0.2.0 specifies:

1. The extension of the Producer abstraction to LLM-backed producers.
2. The cache-key extension for LLM outputs.
3. The storage layout for structured (JSON) artifacts.
4. The lineage tracking required for downstream invalidation.
5. The policy hook points that gate transform execution.
6. The HITL approval flow for running a transform over a subset.
7. One concrete LLM transform: entity extraction.

v0.2.0 does NOT specify:

- A transform registry beyond the per-transform YAML declaration.
- A query planner or query surface.
- Demand-driven transform discovery or an LLM planner.
- A taxonomy-promotion mechanism.
- A vector index or embedding transform.
- Transforms two and beyond.

Those are deferred to v0.3.0 or later. v0.2.0's job is to ship one
transform well and prove the seams before generalising them.

## 16. Core concepts (extensions to §2)

### 16.1 Transform

A transform is a Producer (§2.2) whose execution involves a
non-deterministic external process — in practice, an LLM call. All
§2.2 Producer invariants hold. Transforms additionally have:

- `prompt`: the rendered prompt text sent to the model.
- `model_identity`: a tuple `(provider, model_string, inference_params)`
  uniquely identifying the model invocation.

Transforms are a subclass of Producer, not a parallel concept. The
§7.1 Producer interface is the base; the transform interface (§20.1)
adds fields to `producer_metadata` and extends the cache key.

### 16.2 Transform declaration

A transform is declared in a YAML file under
`<root_dir>/transforms/<transform_name>.yaml`. The declaration
specifies the producer identity (name, version, config), the model
identity, the prompt template reference, the policy references, and
the output schema reference. See §19 for the schema.

Transform declarations are read by the system at invocation time.
They are NOT a plugin registry — the Python implementation is a
direct import, same as v0.1 Producers. The YAML is a declaration of
identity and configuration, not a dispatch mechanism.

### 16.3 Lineage

Lineage is the record, per artifact, of which input artifacts
contributed to its production. For v0.1.x extractor artifacts,
lineage is trivial: one source → one artifact. For transform
artifacts, lineage is one or more input artifacts (each itself a
cache key) → one output artifact. Lineage is used for invalidation
cascading when inputs change. See §21.

## 17. Cache-key extension (extends §4)

### 17.1 Cache-key composition for transforms

The §4.3 cache-key function uses `schema_version` inside the hashed
payload as a format discriminator. v0.1.x extractors use
`schema_version: 1` with a 5-field payload; transforms use
`schema_version: 2` with a 7-field payload. The two formats are
non-overlapping by construction (different `schema_version` values
guarantee no collision even on identical content).

**v0.1.x extractors (schema_version 1) — unchanged:**

```
cache_key = sha256(canonical_json({
    "schema_version":       1,
    "input_hash":           <sha256 of input content>,
    "producer_name":        <str>,
    "producer_version":     <semver>,
    "producer_config_hash": <sha256 of canonical config>,
}))
```

All existing v0.1.x cache keys are byte-identical under this scheme.
No recomputation, no migration.

**Transforms (schema_version 2):**

```
cache_key = sha256(canonical_json({
    "schema_version":       2,
    "input_hash":           <sha256 of input content>,
    "producer_name":        <str>,
    "producer_version":     <semver>,
    "producer_config_hash": <sha256 of canonical config>,
    "model_identity_hash":  <sha256 of canonical model_identity>,
    "prompt_hash":          <sha256 of rendered prompt text>,
}))
```

`schema_version` is monotonic across all cache-key format changes,
not bifurcated by producer type. A future change to the extractor
payload would use `schema_version: 3`, not reuse `2`.

The canonical-JSON serialisation rules from v0.1.x (§4.3) apply
unchanged to both payload formats.

**Inspectability.** Transform artifacts record
`cache_key_schema_version: 2` in their `meta.json` so the payload
format is inspectable with `jq` (§14.1). Extractor `meta.json` files
do not gain this field; its absence implies `schema_version: 1`.
The `meta.json` `format_version` stays at 1 — the file structure is
unchanged; only an optional field has been added.

### 17.2 Model identity

The `model_identity` structure is:

```json
{
    "provider": "anthropic",
    "model": "claude-haiku-4-5",
    "inference_params": {
        "temperature": 0.0,
        "max_tokens": 4096,
        "top_p": 1.0
    }
}
```

Serialised via the v0.1.x canonical-JSON rule (sorted keys, explicit
separators). Two invocations with identical `model_identity` share a
cache key; any change — provider, model string, or any inference
parameter — produces a new key.

The model string is an opaque identifier. The system does NOT attempt
to reason about whether `claude-haiku-4-5` and `claude-haiku-4-5-20251001`
are "the same model"; if the string differs, the cache key differs.
Deprecations are out of band.

### 17.3 Prompt hash

The prompt is rendered from a template file at
`<root_dir>/prompts/<prompt_name>_v<n>.txt` before hashing. The hash
is over the rendered text, not the template plus parameters. This
means two different templates that render to the same text share a
cache key, which is the correct behaviour: the cache records what
the model actually saw.

Prompt templates are versioned in their filenames (`_v1`, `_v2`).
Editing a prompt in place without bumping the version is a policy
violation; see §22.3.

### 17.4 Non-determinism contract

v0.1.x §7.1 established that producer outputs may differ bit-for-bit
across reruns (semantic equivalence, not byte equality). This
contract is inherited by transforms, but transforms make it
load-bearing in a way extractors did not.

LLM outputs are non-deterministic even at temperature 0 (provider-side
variance, tokenisation edge cases, model updates within the same
string identifier). The cache is keyed on inputs, not outputs; a
given cache key always returns the output that was produced the
first time the key was computed. Reruns with the same key are cache
hits regardless of whether a fresh call would produce the same
output.

Invariant 9 (new): **Transform outputs are not re-validated on cache
hit.** A cache hit returns the stored output. Detecting that the
model would now produce something different requires explicit
recomputation via a new cache key (new version, new prompt, new
model), not an automatic check. See §22.4 for how this interacts
with the HITL flow.

## 18. Storage layout for structured artifacts (extends §3, §6)

### 18.1 Artifact files

The cache layout from §3 is unchanged. An artifact directory
contains:

```
<aa>/<bb...>/
├── content        # canonical-JSON bytes for transform artifacts
│                  # (unchanged for v0.1.x extractor artifacts)
├── meta.json      # producer identity, timestamps, transform metadata
└── lineage.json   # NEW: input cache keys that contributed
```

`content` for transform artifacts is canonical-JSON bytes conforming
to the transform's output schema (§19.3). Canonical-JSON here means
the v0.1.x rule: sorted keys, `(',', ':')` separators, UTF-8, no
trailing newline.

Extractor artifacts from v0.1.x do not gain a `lineage.json`. The
absence of the file is the lineage (the artifact was produced from
a single source, recorded in the catalogue). Transform artifacts
MUST have `lineage.json`.

### 18.2 `meta.json` for transforms

v0.1.x `meta.json` contained producer identity and
`producer_metadata`. For transforms, `producer_metadata` gains
required fields:

```json
{
    "producer_name":      "entity_extraction",
    "producer_version":   "0.1.0",
    "producer_config_hash": "...",
    "producer_metadata": {
        "completion":     "complete",
        "model_identity": { ... },
        "prompt_name":    "entity_extraction_v1",
        "prompt_hash":    "...",
        "input_tokens":   1234,
        "output_tokens":  567,
        "latency_ms":     2341,
        "cost_usd":       0.0087
    }
}
```

`input_tokens`, `output_tokens`, `latency_ms`, and `cost_usd` are
recorded for telemetry (§23). They are not part of the cache key —
two runs that differ only in latency share a key.

### 18.3 `lineage.json`

```json
{
    "inputs": [
        {
            "cache_key": "...",
            "role":      "source_text"
        }
    ],
    "format_version": 1
}
```

For v0.2.0, entity extraction has exactly one input per artifact
(the extracted text of one source). The list structure is for
future transforms that may have multiple inputs (e.g. a
cross-document summarisation). `role` is a free-form string the
transform uses to label its inputs; v0.2.0's entity_extraction uses
`"source_text"`.

### 18.4 Atomicity (extends §6.2)

The §6.2 write order becomes: `content` → `lineage.json` → `meta.json`
→ catalogue row, all within one DuckDB transaction. Orphan cleanup
(§6.2) treats any directory missing any of the three files as
incomplete.

## 19. Transform declarations

### 19.1 Directory layout (extends §3)

```
<root_dir>/
├── transforms/
│   └── entity_extraction.yaml
├── prompts/
│   └── entity_extraction_v1.txt
├── schemas/
│   └── entity_extraction_v1.json
├── policies/
│   └── cost_gate.py
│   └── sensitive_doc_gate.py
└── ... (v0.1.x layout unchanged)
```

Python policy code lives under `<root_dir>/policies/`. It is
imported by the system at runtime. The same rule as v0.1.x
Producers applies: direct imports, no plugin registry, until
evidence demands otherwise.

### 19.2 Transform YAML schema

```yaml
name: entity_extraction
version: "0.1.0"
producer_class: pkm.transforms.entity_extraction.EntityExtractionProducer

model:
  provider: anthropic
  model: claude-haiku-4-5
  inference_params:
    temperature: 0.0
    max_tokens: 4096

prompt:
  name: entity_extraction_v1
  file: prompts/entity_extraction_v1.txt

output_schema:
  name: entity_extraction_v1
  file: schemas/entity_extraction_v1.json

policies:
  - cost_gate
  - sensitive_doc_gate

input:
  producer: pandoc  # or docling, or unstructured — one of the v0.1.x extractors
  required_status: success
```

`input.producer` constrains which extractor output feeds the
transform. v0.2.0's entity_extraction runs on pandoc output only;
changing this requires a new transform version.

The YAML is canonicalised (sorted keys, etc.) before its hash is
computed for `producer_config_hash`. Hand-editing the YAML in place
changes the hash and produces new cache keys, which is correct.

### 19.3 Output schema

The output schema is a JSON Schema document. Entity extraction's
v1 schema:

```json
{
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["entities", "format_version"],
    "properties": {
        "format_version": { "const": 1 },
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["text", "type", "span"],
                "properties": {
                    "text": { "type": "string" },
                    "type": {
                        "type": "string",
                        "enum": ["person", "organization", "location",
                                 "date", "money", "other"]
                    },
                    "span": {
                        "type": "object",
                        "required": ["start", "end"],
                        "properties": {
                            "start": { "type": "integer", "minimum": 0 },
                            "end":   { "type": "integer", "minimum": 0 }
                        }
                    },
                    "confidence": {
                        "type": "number",
                        "minimum": 0, "maximum": 1
                    }
                }
            }
        }
    }
}
```

Output validation against the schema is required on every transform
execution (§20.2). A schema violation is a producer failure
(§20.3), not a silent degradation.

## 20. Transform producer interface (extends §7.1)

### 20.1 Interface

```python
class TransformProducer(Producer):
    name: str
    version: str
    model_identity: dict
    prompt_name: str

    def render_prompt(
        self,
        input_content: bytes,
        input_metadata: dict,
    ) -> str:
        """Render the prompt template with inputs. Pure function."""

    def call_model(
        self,
        prompt: str,
    ) -> ModelResponse:
        """Make the model call. May raise on network/provider errors."""

    def parse_output(
        self,
        raw_output: str,
    ) -> dict:
        """Parse model output into schema-conforming dict. May raise."""

    def produce(
        self,
        input_path: Path,
        input_hash: str,
        config: dict,
    ) -> ProducerResult:
        """§7.1 contract: never raises, returns ProducerResult."""
```

`render_prompt`, `call_model`, and `parse_output` are exposed as
separate methods because the HITL flow (§22) needs to render a
prompt for cost estimation without calling the model, and to parse
a sample output independently.

### 20.2 Validation

Every transform execution validates its output against the declared
schema (§19.3) before writing to the cache. A validation failure
produces `ProducerResult(status="failed", ...)` with an error
message naming the schema violation.

Validation is done with `jsonschema` in strict mode. The system
does NOT attempt to repair malformed output; a failure is a
failure. This is the same principle as v0.1.x extractor failures
being recorded as failures, not silently papered over.

### 20.3 Failure modes

The §7.1 producer contract — "never raises; failures are returned
as `status='failed'`" — applies. Transform-specific failure modes
that MUST be caught and returned as failures:

- Model API errors (rate limit, auth, provider 5xx).
- Model timeout (configurable, default 120s).
- Malformed model output (JSON parse error).
- Schema validation failure.
- Budget violation at call time (§22.2) — recorded as
  `status="failed"` with error `"budget_exceeded"`.

Uncatchable failure modes (continuing the §7.1 v0.1.9 pattern):

- Process OOM-kill during model SDK deserialisation of a large
  response. The SDK is out-of-process for network I/O but
  in-process for response parsing; a pathologically large response
  could OOM. Not observed in Phase 1 extraction; flagged for
  surveillance in Phase 2.
- Silent model substitution by the provider (provider routes
  `claude-haiku-4-5` to a different weight internally). Not
  detectable from the client side. The model identity in the
  cache key is what the client requested, not what the provider
  served.

## 21. Lineage and invalidation

### 21.1 Lineage recording

Every transform artifact MUST record its input cache keys in
`lineage.json` (§18.3). The system does not permit a transform
artifact to exist without lineage.

### 21.2 Invalidation semantics

When a v0.1.x extractor artifact's cache key becomes unreferenced
(because its source file changed, producing a new input_hash and
thus a new extractor cache key), downstream transform artifacts
keyed on the old extractor output are NOT automatically deleted.

They become **stale**: still in the cache, still queryable, but
their `lineage.json` points to a cache key no longer associated
with the current source.

Invariant 10 (new): **Staleness is a detectable state, not an
enforced state.** A `pkm transform status` command MUST report
stale transform artifacts. A `pkm transform rerun --stale` command
MUST exist to recompute them. The system does NOT automatically
re-run stale transforms. The human decides when to pay the cost.

The rationale: in a personal-scale system, source changes are
infrequent and transform runs are potentially expensive. Automatic
invalidation-and-recomputation is the wrong default when the user
might want to defer the cost, compare old-vs-new outputs, or
decide the change doesn't warrant a re-run.

### 21.3 Invalidation of transforms themselves

When a transform version is bumped (YAML edit → new
`producer_config_hash`), the old transform artifacts are not
deleted. They remain queryable under the old cache key. The new
version's first invocation produces new artifacts under new keys.
Both coexist.

A `pkm transform prune <transform_name> --version <n>` command MAY
exist in a future version. v0.2.0 does not specify it.

## 22. Policies

### 22.1 Policy interface

A policy is a Python function:

```python
def policy_name(
    transform_decl: TransformDeclaration,
    sources: list[SourceRef],
    estimated_cost: CostEstimate,
    context: PolicyContext,
) -> PolicyDecision:
    ...
```

`PolicyDecision` is one of:

- `Allow()` — proceed.
- `Block(reason: str)` — refuse; reason is shown to the user.
- `RequireApproval(reason: str)` — pause for HITL approval with
  the given reason; see §22.4.

Policies are pure functions in the sense that they do not mutate
state. They may read from the catalogue (e.g. to check prior costs)
but may not write. Policy composition is sequential: policies are
evaluated in the order declared in the transform YAML; the first
`Block` short-circuits; `RequireApproval` from any policy promotes
the overall decision to require approval.

### 22.2 Required policies for v0.2.0

Every transform MUST declare at least one policy from this list:

- `cost_gate`: blocks if estimated cost exceeds the configured
  budget (default: $5 per invocation, $50 per day, $200 per month —
  configurable in `config.yaml`).
- `sensitive_doc_gate`: requires approval if any source is tagged
  `sensitive` or falls under a configured sensitive-path pattern.

The configuration surface for these policies lives in
`config.yaml` under a new `policies:` section. The schema is:

```yaml
policies:
  cost_gate:
    budget_per_invocation_usd: 5.00
    budget_per_day_usd: 50.00
    budget_per_month_usd: 200.00
  sensitive_doc_gate:
    tags: [sensitive, medical, financial]
    path_patterns: ["/path/to/medical/**"]
```

### 22.3 Policy on prompt edits

In-place edits to a versioned prompt file
(`prompts/entity_extraction_v1.txt` edited without being renamed
to `_v2`) are a policy violation. The system detects this by
storing the prompt hash at first-load and comparing on subsequent
loads. A mismatch aborts execution with an error instructing the
user to bump the version.

This is the v0.1.8 "migrations are immutable once applied" rule
(v0.1.x §14.8) applied to prompts.

### 22.4 HITL approval

`RequireApproval` pauses execution and writes a pending-approval
record to the catalogue. The user reviews via
`pkm transform approve <approval_id>` or
`pkm transform reject <approval_id> --reason "..."`.

For v0.2.0, approvals are per-invocation, not per-transform or
per-source. Each `pkm transform run` that triggers approval creates
one approval record covering the full source set. Granular
per-source approval is deferred.

The approval record includes:

- The transform declaration hash.
- The full list of source cache keys.
- The cost estimate.
- The sample output on up to 3 representative sources (computed
  eagerly before approval; see §22.5).
- The reason(s) from triggering policies.

Approval commits the user to the full run at the displayed cost
estimate. If actual cost exceeds the estimate by more than 2×, the
run aborts mid-execution and records partial results; further
execution requires a new approval.

### 22.5 Sample-for-approval

Before pausing for approval, the system runs the transform on up
to 3 sources from the requested set (chosen by deterministic
stratified sampling — one shortest, one median-length, one
longest). These runs are themselves subject to the non-sample
policies but NOT to `RequireApproval` policies (to avoid
recursion). Their outputs are written to the cache normally and
shown to the user as part of the approval record.

If sample runs fail (any of the 3), the approval is presented with
the failures visible, and the user decides whether to proceed.

## 23. Telemetry

### 23.1 Per-execution log

Every transform execution (sample or full) writes a log entry to
`<root_dir>/logs/transforms/<YYYY-MM-DD>.jsonl`:

```json
{
    "timestamp":        "2026-04-24T14:23:01Z",
    "transform_name":   "entity_extraction",
    "transform_version": "0.1.0",
    "cache_key":        "...",
    "input_cache_key":  "...",
    "model":            "claude-haiku-4-5",
    "prompt_name":      "entity_extraction_v1",
    "status":           "success",
    "input_tokens":     1234,
    "output_tokens":    567,
    "latency_ms":       2341,
    "cost_usd":         0.0087,
    "cache_hit":        false
}
```

Cache hits also log (with `cache_hit: true` and zero for tokens,
latency, cost). This is the data that future versions of the
system would use to train a cost estimator or query planner; it
is collected from day one regardless of whether such a planner
exists.

### 23.2 No aggregation in v0.2.0

The system does NOT compute rolling averages, trend lines, or
priors for planning purposes in v0.2.0. The logs are the raw
material; aggregation is deferred.

## 24. User-facing commands (extends v0.1.x)

```
pkm transform list
    List declared transforms.

pkm transform run <name> --sources <selector>
    Run a transform over selected sources. Sources can be selected
    by tag (tag:legal), path glob, or explicit source_id list.
    Returns approval_id if HITL approval is required, else the
    cache keys of produced artifacts.

pkm transform approve <approval_id>
    Approve a pending HITL approval.

pkm transform reject <approval_id> --reason <text>
    Reject a pending HITL approval.

pkm transform status
    Show transform coverage across sources: how many sources have
    artifacts for each transform, how many are stale.

pkm transform rerun --stale [--transform <name>]
    Recompute stale transform artifacts.

pkm transform show <cache_key>
    Display a transform artifact, its metadata, and its lineage.
```

No query command in v0.2.0.

## 25. Invariants added in v0.2.0

Continuing the v0.1.x numbering:

- **Invariant 9**: Transform outputs are not re-validated on cache
  hit. (§17.4)
- **Invariant 10**: Staleness is a detectable state, not an
  enforced state. (§21.2)
- **Invariant 11**: Every transform execution validates its
  output against the declared schema before writing. A validation
  failure is a producer failure. (§20.2)
- **Invariant 12**: Every transform artifact records its input
  cache keys in `lineage.json`. No transform artifact exists
  without lineage. (§21.1)
- **Invariant 13**: Prompt files are immutable once their hash
  has been recorded. Editing in place aborts execution. (§22.3)

## 26. Deliberately deferred

Things that would be reasonable to build but are explicitly NOT in
v0.2.0:

- A query surface. v0.2.0 has `pkm transform run`; it does not
  have `pkm query`. Deferred to v0.3.0 or later.
- A transform registry beyond YAML declarations. Adding a
  transform in v0.2.0 means: write Python, write YAML, write
  prompt, write schema, commit. No dynamic registration.
- An LLM planner that proposes new transforms. Deferred to v0.3.0
  when at least 3 transforms exist to generalise from.
- Rewrite rules (filter pushdown, batching, etc.). Deferred.
  Entity extraction in v0.2.0 runs one LLM call per source with
  no optimisation.
- Per-source granular approval. v0.2.0's approval is per-invocation.
- Automatic stale-artifact re-run. v0.2.0 requires explicit
  `rerun --stale`.
- Vector index / embeddings. Not in v0.2.0.
- Structured prior-tracking for cost estimation (Abacus-style).
  Telemetry is logged but not aggregated.
- Transform-proposes-transform (LLM planner). Explicitly a v0.3.0
  or later concern.
- A `prune` command for old transform versions.

## 27. What v0.2.0 proves

v0.2.0 is a working end-to-end transform with the seams that v0.3.0
will need. Specifically, it proves:

- The cache-key extension (§17) survives a real transform without
  schema churn.
- The lineage format (§18.3) can record what a transform actually
  needs to record.
- The policy interface (§22.1) can gate a real execution on both
  cost and content-sensitivity.
- The HITL approval flow (§22.4) is usable in practice for a
  transform that takes tens of minutes and costs single-digit
  dollars.
- The TransformProducer interface (§20.1) is the right
  specialisation of Producer for LLM work.

When v0.3.0 begins, the evidence for generalising the registry,
adding a second transform, and designing discovery will come from
the actual usage of v0.2.0 — not from speculation about what
future transforms might want.
