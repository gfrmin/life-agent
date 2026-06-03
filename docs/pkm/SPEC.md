# SPEC.md — technical specification

Version: 0.7.0 (draft)
Status: Phase 1 complete (extraction layer with content-addressed
caching, chunking, and FTS keyword retrieval); Phase 1.5 OCR-PDF
fallback applied to the live corpus; source paths are stored as
declared, not canonicalized (§8.2, §13.6); email (`.eml`) has a
dedicated stdlib producer (§7.2); a structural PII guard keeps
personal data out of this public repo (§14.9); a read-only MCP
query surface exposes FTS retrieval over stdio (§17). This spec is
the contract. Changes require a separate commit with justification.

This spec is intentionally strict. See §14 for the principles of
first-principles debuggability that govern every decision below.

## 1. Scope of this specification

This document specifies the foundation layer: content-addressed cache,
catalogue, canonicalisation rules, and the extraction pipeline that
runs over raw documents. It does not specify LLM transforms, query
planning, or any higher-layer concerns — those live in later spec
versions once the foundation is stable.

## 2. Core concepts

### 2.1 Source

A source is a file in the user's filesystem that the user considers
input material. Sources are immutable from the system's perspective:
the system never modifies source files. Sources are identified by
the SHA-256 hash of their byte content.

### 2.2 Producer

A producer is a named, versioned piece of code that consumes inputs
and produces outputs. Extractors are producers; LLM transforms (in
later phases) will also be producers. Every producer has:

- `name`: a stable identifier (e.g., `pandoc`, `docling`).
- `version`: a semantic version that changes whenever the producer's
  behaviour changes.
- `config`: a dict of parameters controlling the producer's behaviour.

### 2.3 Artifact

An artifact is the output of a producer applied to an input. Every
artifact has a cache key computed from its inputs and producer
identity. Artifacts are immutable once written.

### 2.4 Cache

The cache is the content-addressed store of all artifacts. Artifacts
are written to paths derived from their cache keys. The cache is an
append-only, content-addressed filesystem layout. Nothing in the cache
is ever modified in place.

### 2.5 Catalogue

The catalogue is a DuckDB database recording metadata about sources,
producers, and artifacts: what exists, where, produced by whom, when,
with what status. The catalogue is mutable and can be rebuilt from
the cache. The catalogue is the index; the cache is the storage.

## 3. Directory layout

All state lives under a single root directory, configured in
`config.yaml` as `root_dir`. Default: `~/.local/share/pkm/`.

```
<root_dir>/
├── sources/              # manifests describing source locations
│   └── sources.yaml      # registry of source paths (not the files
│                         # themselves — sources live where they live)
├── cache/                # content-addressed artifact storage
│   └── <aa>/             # first 2 hex chars of key
│       └── <bb...>/      # remaining 62 hex chars as directory
│           ├── content   # the artifact itself
│           └── meta.json # producer identity, timestamps
├── catalogue.duckdb      # metadata database
├── config.yaml           # configuration (single file)
└── logs/                 # structured logs
    └── <YYYY-MM-DD>.jsonl
```

Rationale for the cache layout: `<aa>/<bb...>/` prevents any single
directory from accumulating millions of entries (standard practice
from git, IPFS, Nix). Using `<bb...>/` as a directory with a `content`
file inside (rather than a file named `<bb...>`) allows producer
metadata to sit alongside the artifact without a separate index.

## 4. Cache key format

### 4.1 Canonicalisation

Any structured data entering a hash function MUST be canonicalised
using:

```python
json.dumps(obj, sort_keys=True, separators=(',', ':'),
           ensure_ascii=False)
```

Any deviation from this canonicalisation is a bug.

### 4.2 Cache key computation

The cache key for an artifact is:

```
cache_key = sha256(canonical_json({
    "schema_version": 1,
    "input_hash": <sha256 of the input content>,
    "producer_name": <string>,
    "producer_version": <string>,
    "producer_config_hash": <sha256 of canonicalised config dict>,
})).hexdigest()
```

Crucially, `input_hash` is the hash of the input's **content**, not
the cache key of the input (if the input is itself a cached artifact).
This ensures that two producers which happen to produce byte-identical
outputs are recognised as equivalent inputs to downstream transforms.

### 4.3 The single hashing function

All cache keys MUST be computed by a single utility function:

```python
def compute_cache_key(
    input_hash: str,
    producer_name: str,
    producer_version: str,
    producer_config: dict,
) -> str:
    ...
```

No other code path may construct cache keys. No ad-hoc hashing.

### 4.4 What must NOT be in the cache key

The following MUST be excluded from cache key construction:

- Timestamps, wall-clock times
- Request IDs, run IDs, session IDs
- User identity, hostname, IP address
- Paths to files (only content hashes)
- API keys, credentials
- Retry counts, latency measurements

These destroy hit rates without improving correctness.

## 5. Catalogue schema

Schema version: 1

### 5.1 Tables

```sql
CREATE TABLE schema_meta (
    schema_version INTEGER PRIMARY KEY,
    migration_id   VARCHAR NOT NULL,  -- migration filename, e.g. '0001_initial_schema.py'
    migration_hash VARCHAR NOT NULL,  -- SHA-256 hex of the migration file at apply time
    applied_at     TIMESTAMP NOT NULL
);
-- One row per applied migration. The "current" schema version is
-- MAX(schema_version); the full history of schema applications is
-- the full row set (see §14.8 on migration hash verification).

CREATE TABLE sources (
    source_id     VARCHAR PRIMARY KEY,  -- SHA-256 of content
    current_path  VARCHAR NOT NULL,      -- most recently declared path (absolute, symlinks not dereferenced; §8.2)
    first_seen    TIMESTAMP NOT NULL,
    last_seen     TIMESTAMP NOT NULL,
    size_bytes    BIGINT NOT NULL,
    mime_type     VARCHAR                -- as detected, nullable
);

CREATE TABLE source_paths (
    source_id     VARCHAR NOT NULL,
    path          VARCHAR NOT NULL,
    seen_at       TIMESTAMP NOT NULL,
    PRIMARY KEY (source_id, path),
    FOREIGN KEY (source_id) REFERENCES sources(source_id)
);
-- One source may have been seen at multiple paths over time
-- (moves, renames, copies). The history is kept.

CREATE TABLE source_tags (
    source_id  VARCHAR NOT NULL,
    tag        VARCHAR NOT NULL,
    PRIMARY KEY (source_id, tag),
    FOREIGN KEY (source_id) REFERENCES sources(source_id)
);
CREATE INDEX idx_source_tags_tag ON source_tags(tag);
-- See §13.5 for the modelling rationale.

CREATE TABLE artifacts (
    cache_key              VARCHAR PRIMARY KEY,
    input_hash             VARCHAR NOT NULL,
    producer_name          VARCHAR NOT NULL,
    producer_version       VARCHAR NOT NULL,
    producer_config_hash   VARCHAR NOT NULL,
    status                 VARCHAR NOT NULL,  -- 'success' | 'failed'
    produced_at            TIMESTAMP NOT NULL,
    size_bytes             BIGINT,            -- null if failed
    error_message          VARCHAR,           -- non-null iff failed
    content_type           VARCHAR,           -- MIME or producer-specific
    content_encoding       VARCHAR,           -- e.g. 'utf-8', null for binary
    content_path           VARCHAR NOT NULL   -- relative to cache dir
);

CREATE INDEX idx_artifacts_input ON artifacts(input_hash);
CREATE INDEX idx_artifacts_producer
    ON artifacts(producer_name, producer_version);
CREATE INDEX idx_artifacts_status ON artifacts(status);

CREATE SEQUENCE seq_chunk_id START 1 INCREMENT 1;

CREATE TABLE artifact_chunks (
    artifact_cache_key  VARCHAR NOT NULL,  -- FK → artifacts.cache_key
    chunk_index         INTEGER NOT NULL,
    chunk_text          VARCHAR NOT NULL,
    source_origin       VARCHAR,           -- producer_name that produced the artifact
    chunk_id            BIGINT DEFAULT nextval('seq_chunk_id'),
    PRIMARY KEY (artifact_cache_key, chunk_index),
    FOREIGN KEY (artifact_cache_key) REFERENCES artifacts(cache_key)
);
-- chunk_id is the FTS input_id. Must be unique per row (seq guarantees
-- this for inserts; write_chunks uses DELETE+INSERT idempotency).
-- See §15 for chunking and FTS configuration.
```

### 5.2 Invariants

- Every row in `artifacts` with `status='success'` has a
  corresponding file at `<root>/cache/<content_path>/content`.
- Every row in `artifacts` with `status='failed'` has a non-null
  `error_message` and a null `size_bytes`.
- `input_hash` in `artifacts` is either a `source_id` in `sources`
  or a `cache_key` in `artifacts` (we don't enforce this as a FK
  because the input might be a source we haven't ingested yet in
  some edge case — but it SHOULD resolve).
- `producer_config_hash` is `sha256(canonical_json(config_dict))`.

### 5.3 Rebuilding from the cache

There MUST be a `rebuild_catalogue` command that walks the cache
directory and reconstructs the `artifacts` table from the `meta.json`
files. Rebuild does NOT reconstruct the `sources` or `source_paths`
tables — those contain observational data (paths, timestamps, sizes,
MIME types, user tags) that cannot be recovered from the cache alone.
To repopulate `sources` after a rebuild, the user re-runs `pkm ingest`.

This keeps the responsibilities of rebuild and ingest crisply
separated: rebuild is for artifact derivations recorded in the cache,
ingest is for observations about source files on the filesystem.

## 6. Operations

### 6.1 Idempotency

Every operation MUST be idempotent. The test: running the operation
twice, the second run produces zero new writes to cache or catalogue.

Operations that may legitimately be non-idempotent (e.g., explicit
re-extraction with `--force`) must be flagged and require the flag
to be non-idempotent.

### 6.2 Atomicity

Writes to the cache and the corresponding catalogue row MUST be
logically atomic: on the next successful run of the system, no cache
directory exists without a matching catalogue row, and no catalogue
row exists without its cache files. This is the visible invariant that
downstream code relies on.

The filesystem and the DuckDB catalogue cannot share a single
transaction, so the invariant is maintained by ordering plus an
explicit orphan sweep. The write order is:

1. Write `content` (byte file) to its final location.
2. Write `meta.json` beside it.
3. Open a DuckDB transaction, insert the `artifacts` row, commit.

If the process is interrupted between any of these steps, the on-disk
state may contain an orphan cache directory (content and/or meta.json
present without a catalogue row). Orphans are removed by a consistency
sweep that runs at the start of every `pkm extract` and every
`pkm rebuild-catalogue` invocation. "Start of invocation" is the only
meaningful notion of startup here — there is no daemon (SPEC §14.6).
Other commands (`pkm ingest`, `pkm migrate`) do not touch the cache
and therefore do not run the sweep.

The sweep is conservative: a cache directory is considered orphaned
iff (a) it contains a `content` file or a `meta.json` file, and (b)
no row in `artifacts` has `cache_key` equal to the directory name.
Orphan directories are removed; the event is logged.

**Asymmetric recovery.** The sweep covers only the "files without a
row" direction. The reverse — a catalogue row whose `content` or
`meta.json` is missing on disk — is NOT auto-repaired, because
producing new bytes for a known cache key without comparing against
the missing originals would overwrite a data-loss signal with
output we cannot verify. The cache write and cache read paths both
detect this case explicitly: they abort the current operation with
a `CacheInconsistencyError`, log the mismatch at ERROR with the
cache key and the list of missing files, and leave the catalogue
untouched. The user's remedy is to run `pkm rebuild-catalogue`,
which reconciles the catalogue back to the filesystem's actual
state (dropping rows whose files are gone and recreating rows for
any files whose metadata is intact but unrecorded).

**Deletion is a single sanctioned pathway.** The cache is
append-only under normal operation: `write_artifact` is idempotent
(a second write with the same `cache_key` is a no-op), and no
command rewrites existing rows in place. The one legitimate way an
artifact is ever removed from the cache is `pkm extract
--retry-failed`, which uses `cache.delete_artifact(root, conn,
cache_key)` to clear a cached failure before re-running the
producer. Without this path, retry_failed would be a silent no-op:
`write_artifact`'s idempotency check sees the existing row and
short-circuits, leaving the failed row behind no matter how many
times the user retries.

`delete_artifact` removes the cache directory contents first, then
deletes the `artifacts` row inside a transaction. The file-first
ordering is deliberate: if `delete_artifact` is interrupted
mid-way, the worst-case residue is a cache directory without a
row, which the next consistency sweep collects as an orphan. The
reverse ordering would leave a row pointing at missing files —
the asymmetric-corruption case described above, which is much
harder to recover from.

`delete_artifact` is called only by the extract layer under
`retry_failed`, guarded by the routing-layer condition that the
producer in question is in the source's `failed` set. New call
sites for deletion MUST be considered carefully; the cache's
append-only invariant is load-bearing for SPEC §14.1
inspectability (an artifact that existed can be cited from logs
forever) and for Phase 2 query semantics (downstream consumers
trust that a cache_key once written stays valid until an explicit
producer-version bump).

### 6.3 Transactions

All multi-row catalogue operations use DuckDB transactions explicitly.
No implicit autocommit for multi-row logic.

## 7. Producers (Phase 1 extractors)

### 7.1 Common interface

Every producer implements:

```python
class Producer(Protocol):
    name: str
    version: str

    def produce(
        self,
        input_path: Path,
        input_hash: str,
        config: dict,
    ) -> ProducerResult:
        ...


@dataclass(frozen=True)
class ProducerResult:
    status: Literal["success", "failed"]
    content: bytes | None           # None iff failed
    content_type: str | None        # MIME or producer-specific; required on success
    content_encoding: str | None    # e.g. 'utf-8'; None for binary artifacts
    error_message: str | None       # None iff success
    producer_metadata: dict         # written to meta.json; may be empty
```

Producers MUST:

- Return `bytes` for `content` (never `str`). If the output is text,
  the producer encodes it and records the encoding in
  `content_encoding`.
- Never raise exceptions that escape `produce()`. Any failure is
  caught and returned as `status='failed'` with a message.

**Determinism contract.** Producers produce *semantically*
equivalent output given the same input content and config. Byte-
level determinism across runs is not required; ML-backed producers
may produce output that varies at sub-semantic levels (floating-
point layout coordinates, token-level timestamps, inference-noise
scores, and similar) between runs on the same input.

The cache is keyed on `(input_hash, producer_name, producer_version,
producer_config_hash)` — not on output bytes. A cache hit means
"we have already run this producer with these inputs; reuse the
cached output" — not "this is the canonical output that would be
reproduced bit-exactly if we ran it now." Output bytes written
once are preserved; the system never overwrites an artifact with a
fresh run of the same producer at the same version. Re-running
only happens via explicit `--retry-failed` after a recorded
failure (see §14.3).

`input_path` remains an I/O handle, not part of the cache key:
two machines with byte-identical content at different paths MUST
produce cache keys that agree. Non-deterministic producers (e.g.,
future LLM-backed producers with a nondet inference path) MUST
either make the randomness source appear in `config` (so it is
captured in the cache key) or accept that cross-machine cache
parity is not guaranteed and document that fact in the producer's
own spec.

**Note on hidden-input audits.** Producers that wrap external
libraries MUST audit those libraries for hidden dependencies that
would cause byte-identical inputs to be misidentified as different
inputs — specifically, anything that leaks path, time, hostname,
or ambient state into identifiers downstream consumers will use to
compare content. The Step 7e Unstructured case is the canonical
prior-art example: `Element.id_to_hash` baked the source filename
into element IDs, which meant downstream consumers keying on those
IDs would have observed the same content under different paths as
different content. The fix required nulling the path-dependent
metadata fields AND recomputing the element IDs before
serialisation, so that the content-derived identifiers in the
producer's output are path-independent.

This is distinct from byte-level output variance, which is
acceptable under the determinism contract above. The canonical
check is `test_cache_key_is_path_independent` — assert that
`compute_cache_key` returns the same value for the same content
at different paths. Byte-equality of producer output across paths
(or across runs on the same path) is neither required nor
expected.

**Uncatchable failure modes.** The `Producer.produce()` contract
guarantees no uncaught Python exceptions escape the method. This
guarantee holds for Python-level failures. It does not and cannot
hold for failures outside Python's reach: OS signals (notably
SIGKILL from the Linux OOM killer), kernel panics, hardware faults,
or parent process termination.

When such a failure occurs mid-extraction, the `pkm extract`
process terminates without recording a failed-artifact row for the
source in flight. The catalogue remains consistent (all prior
transactions committed atomically; no partial write exists);
however, the affected source will appear not-yet-processed on
subsequent runs and will be re-attempted. If the underlying
condition persists (e.g., a document whose extraction reliably
exhausts memory), the same outcome will recur.

Mitigating this class of failure is a Phase 2+ concern. Subprocess
isolation per producer call, per-document memory limits, and
pre-flight size estimation are all plausible approaches; none are
required by the Phase 1 contract. Until such mitigations exist,
operators of `pkm extract` on large corpora should expect
occasional silent process termination on pathological inputs and
rely on the idempotent re-run to recover.

### 7.2 Initial extractors

Phase 1 ships with five extractors:

- `pandoc` — fast, baseline, handles common formats
- `docling` — sophisticated, handles layout and tables
- `unstructured` — broad format coverage for the long tail (and `.msg`)
- `tesseract` — OCR for image formats (`.jpg`, `.jpeg`, `.png`,
  `.tif`, `.tiff`, `.bmp`); shells out to `tesseract <path> stdout
  -l <langs>`; config: `{languages, psm, oem}`.
- `email` — RFC822 (`.eml`) via the Python stdlib `email` module.
  Renders a fixed-order header block (From, To, Cc, Date, Subject,
  Message-ID; absent optional headers omitted) then the body as
  `text/plain`. The body is the message's `text/plain` part when
  present, else its `text/html` part stripped to text with
  `beautifulsoup4`. **Only `text/*` parts are decoded; attachment
  (`application/*`) payloads are never touched** — this both keeps
  large messages fast (a 59 MB attachment-heavy message parses in
  milliseconds) and scopes the email corpus to message *bodies*
  (attachment-as-source is a Phase-2 concern, §12). Output is
  path/time/host-independent per §7.1 (fixed header order,
  charset-aware decode, no filename in the rendering).

No plugin system. These are five concrete imports. The fourth
producer (Tesseract, v0.1.11) and now the fifth (`email`, v0.5.0)
have each been the moment to reconsider an extractor registry, per
the §14 principle of "no registry before it is needed." **Decision
at the fifth: still deferred.** Five concrete imports plus a
five-arm dispatch in `extract._ensure_constructed` remain trivially
readable and greppable; a registry would add indirection (dynamic
dispatch, registration order, discovery) with no payoff until
producers become pluggable or third-party — neither on the roadmap.
Revisit at a sixth producer or the first out-of-tree producer. The
`email` producer, like Tesseract before it, fills a gap (a fast,
bounded, body-only path for RFC822) rather than competing: `.eml`
previously went to Unstructured, whose `auto` strategy on large
MIME/attachment payloads is pathologically slow.

### 7.3 Routing

A single Python function decides which producers to run on a given
source. Not a rule engine, not configuration. Inputs: the source's
file extension, its tags (from `sources.yaml`), and the set of
producers already attempted on this source with their outcomes.
Output: the ordered list of producers that should still run.

Phase 1 policy:

1. **Pandoc** on every source whose extension Pandoc handles. Pandoc
   is fast and covers the common text-and-document baseline.

2. **Docling** on PDFs (always, format-based), and on any source
   whose extension Docling handles and which is tagged as
   layout-sensitive (`invoice`, `report`, `contract`). Docling also
   runs as a *fallback* when Pandoc has failed on a source Docling
   handles.

3. **Unstructured** on `.msg` email (always, format-based — Outlook
   OLE, which the stdlib `email` producer cannot parse). Unstructured
   also runs as a *fallback* in two cases: when neither Pandoc nor
   Docling handles the source's format (Unstructured is the catch-all
   for long-tail formats), and when both Pandoc and Docling have
   failed on a source Unstructured handles. As of v0.5.0 `.eml` is
   NOT in Unstructured's set — it has a dedicated producer (rule 5).

4. **Tesseract** on image formats (`.jpg`, `.jpeg`, `.png`, `.tif`,
   `.tiff`, `.bmp` — always, format-based) and on PDFs where Docling
   succeeded but extracted no text (the `empty_succeeded` fallback,
   see below). For images: no fallback from or to other producers —
   raw images have no alternative text-extraction path. For PDFs:
   Tesseract rasterises via `pdftoppm -r 300` and OCRs each page.

5. **Email** on `.eml` (always, format-based) — the dedicated stdlib
   RFC822 producer (§7.2). It is the *only* producer for `.eml`:
   there is no fallback to or from Unstructured. A malformed `.eml`
   the email producer cannot parse is a recorded `status="failed"`
   (fail-fast, §14.3), never handed to Unstructured — whose stall on
   large/complex MIME is precisely what motivated this producer.
   `pkm extract --retry-failed` re-attempts a failed `.eml` through
   the email producer (e.g. after a `_VERSION` bump fixes the parser).

**`empty_succeeded` routing signal.** If Docling has a `status="success"` artifact for a PDF
but `chunking.extract_text(content, "application/x-docling-json") == ""`, that Docling artifact
is recorded as `empty_succeeded` rather than `succeeded`. This means:

- Docling is *not* re-run (its artifact is valid — it correctly determined there is no text layer).
- Tesseract is added to the routing plan as a fallback, using the same source PDF as input via
  `pdftoppm` rasterization.
- This triggers for exactly the class of *image-only PDFs* (scanned documents with no embedded
  text): Docling's structured extraction correctly reports an empty text set; Tesseract then
  performs OCR on the rasterised page images.

The definition of "empty" is pinned to `chunking.extract_text(content, content_type) == ""`.
This is a load-bearing contract on that function: future changes to its whitespace-trimming or
format-handling behaviour change routing decisions, and must be evaluated against this invariant.

**Whole-document granularity for Tesseract-PDF.** When Tesseract processes a PDF, it operates
at whole-document granularity: a failure on any single page causes the entire producer to return
`status="failed"`. Partial results are not cached. This prevents ambiguity about artifact
completeness and keeps the success/failure semantics consistent with single-image processing.
The consequence is that the backfill conversion rate from empty-Docling PDFs will be less than
100% — some PDFs will fail on a single bad page — which is the correct tradeoff.

Rationale for format-based defaults. File extension is a strong,
mandatory signal of content shape. Tags are optional user metadata
and coverage will always be patchy. A routing policy that depends
on tags for the common cases (every PDF, every email) would
underextract whenever a tag is missing; format triggers ensure the
obvious structural cases are covered regardless of tagging
diligence. Tags are for *escalation* — pushing a `.md` invoice
through Docling because the user said so — not for gating defaults.

Fallback rules exist because each producer can fail on specific
documents even within its supported formats (malformed PDFs,
encoding quirks, tool bugs). A failure in one producer SHOULD
trigger the next applicable one, with the catalogue recording both
the failure and the recovery attempt.

Running the router on a source with no outstanding work returns an
empty list, which is how `pkm extract` achieves idempotency against
already-extracted sources. Successes are never re-run by routing
(cache invalidation is producer-version-bump territory, SPEC §14.5).
Re-running with `--retry-failed` includes previously-failed
producers back in the candidate set.

## 8. Source registration

### 8.1 The sources.yaml manifest

```yaml
version: 1
sources:
  - path: /path/to/legal/complaint.pdf
    tags: [legal, acme]
  - path: /path/to/career/cv.docx
    tags: [cv, career]
  - path: /path/to/medical/
    tags: [medical]
    recursive: true
```

Paths may be files or directories. If a directory with
`recursive: true`, all files within are sources.

### 8.2 Ingestion

The `ingest` command:

1. Reads `sources.yaml`.
2. For each path, computes the content hash.
3. If the `source_id` is new, creates a row in `sources`.
4. If the path is new for an existing `source_id`, records it in
   `source_paths`.
5. Updates `last_seen` on existing sources.

Ingestion does NOT run extractors. It only registers sources in
the catalogue.

**Stored path form (v0.4.0).** The string written to `current_path`
and `source_paths.path` is the **declared** path: `os.path.abspath`
applied to the `~`-expanded `sources.yaml` entry (and, for a
`recursive` directory, to each file enumerated beneath it). This makes
the path absolute and lexically normalizes `.`/`..`, but it does **not
dereference symlinks** — a symlinked entry keeps its own name, and
therefore its extension, which §7.3 routing depends on. Existence and
readability are still validated: an entry that does not resolve is
skipped per §13.4, and the bytes hashed are the symlink target's, so
`source_id` is independent of how the file was named or reached. When
several declared paths resolve to the same bytes there is a single
`sources` row (keyed by `source_id`); `current_path` is the most
recently declared one (last write wins) and every distinct declared
path is retained in `source_paths`. Rationale: §13.6.

## 9. Configuration

A single file, `config.yaml`:

```yaml
version: 1
root_dir: ~/.local/share/pkm
log_level: INFO
extractors:
  pandoc:
    version: "3.1.9"    # used in cache keys; must match installed
    config: {}
  docling:
    version: "2.14.0"
    config:
      ocr: true
      table_structure: true
  unstructured:
    version: "0.16.0"
    config:
      strategy: auto
  tesseract:
    version: "5.5.2"    # must match first line of `tesseract --version`
    config:
      languages: heb+eng
      psm: 3
      oem: 3
  email:
    version: "1"        # producer-logic version, hand-bumped (§14.5)
    config: {}
```

Version strings in config are used in cache keys. Mismatch between
config version and actually installed version is a startup error.

## 10. Logging

Structured JSON logs, one file per day, in `<root>/logs/`. Every
log line includes:

- `timestamp`: ISO 8601 with timezone
- `level`: DEBUG | INFO | WARNING | ERROR
- `component`: which module
- `event`: short event name (e.g., `cache_hit`, `extraction_started`)
- `source_id` or `cache_key` if applicable
- `message`: human-readable

No `print()` in library code. CLI entry points may print to stdout
for user output, but structured events still go to the log.

## 11. Backup and recovery

The cache, catalogue, and configuration are covered by BorgBackup.
The cache is reproducible from sources + code, but re-running all
extractors is expensive, so the cache is backed up rather than
regenerated on loss.

The catalogue is rebuildable from the cache via `rebuild_catalogue`.
This command MUST exist and MUST be tested.

Source files themselves are outside this system's scope for backup
(they live where they live, under the user's existing backup policy).

## 12. What is explicitly out of scope for this spec version

- LLM transforms (Phase 2)
- Query planning (Phase 2)
- Embeddings and hybrid vector+keyword search (Phase 2)
- Subject provenance on retrieved facts (Phase 2) — FTS search
  returns all matching chunks regardless of which person a fact
  describes; disambiguation requires a fact-extraction layer with an
  explicit `subject` field, not part of Phase 1 retrieval.
- Web UI, dashboards (not planned)
- Parallelism (not planned for Phase 1)
- Plugin architecture for extractors — reconsidered at the 4th
  (Tesseract) and 5th (`email`) producers and deferred each time
  (see §7.2); not planned until a 6th or a first out-of-tree producer
- Multi-user support (single-user system)
- Remote cache, distributed execution (local only)

## 13. Resolved design decisions

These were open questions during drafting; they are now fixed
decisions. Each carries a brief rationale because understanding
why we chose is as important as what we chose.

### 13.1 `meta.json` is authoritative; catalogue is rebuildable

Every cache entry stores its full metadata in `meta.json` alongside
the `content` file. The catalogue is a derived index that can be
rebuilt by walking the cache directory. This means:

- `meta.json` contains everything needed to reconstruct the
  `artifacts` row: `cache_key`, `input_hash`, `producer_name`,
  `producer_version`, `producer_config`, `producer_config_hash`,
  `status`, `produced_at`, `size_bytes`, `error_message`,
  `producer_metadata`.
- The catalogue is never the sole source of truth for artifact
  data. Losing the catalogue is inconvenient but not catastrophic.
- `rebuild_catalogue` walks `<root>/cache/`, reads every
  `meta.json`, and reconstructs the `artifacts` table from scratch.

Rationale: the cache is the foundational record; the catalogue
exists only to make it queryable. Keeping `meta.json` authoritative
means the system degrades gracefully under catalogue corruption
and that a user can forensically inspect any artifact without
touching the database.

### 13.2 Deleted sources remain as ghosts

If a source file disappears from its recorded path:

- The `sources` row is retained.
- `last_seen` is not updated (it records the last time we
  observed the file existed).
- No artifacts are cascade-deleted.
- `ingest` logs a WARNING when a recorded path no longer resolves.

Rationale: artifacts are valid derivations of content that existed
at a specific time. Deleting them because the source file was
moved or deleted destroys the derivation history. The catalogue
is a log, not a live index of the filesystem.

A future `prune` command MAY offer opt-in removal of ghost sources
and their artifacts, but only behind an explicit flag and with a
dry-run preview. Phase 1 does not implement this.

### 13.3 Artifacts are arbitrary bytes

The cache stores bytes. Producers may emit plaintext, JSON,
structured binary formats (Docling's native format), images,
embeddings (as binary arrays), audio, or anything else.

- The `content` file is written verbatim as bytes.
- `meta.json` records a `content_type` field (MIME type or a
  producer-specific identifier) to help consumers interpret it.
- No transformation (encoding normalisation, compression,
  re-serialisation) is applied between producer output and
  cache write.

Rationale: constraining Phase 1 to text would require rewriting
cache primitives when Phase 2 adds embeddings. Bytes is the
most general abstraction; interpretation belongs one layer up.

### 13.4 Paths that never resolved

Distinct from §13.2 (which covers sources that *were* seen and then
vanished): a `sources.yaml` entry whose path has never resolved to a
readable file produces a WARNING log event and is skipped. No
`source_id` is created, because there is no content to hash; the
`sources` and `source_paths` tables are unaffected.

A path resolving to something unreadable — file not found, permission
denied, broken symlink, device or socket file, a directory when
`recursive: true` is not set — is treated under this section rather
than as an ingest failure. The behaviour is uniform: WARNING + skip.
Ingest MUST NOT halt because of an unreadable entry; subsequent
entries are processed normally. If the path later becomes readable,
the next `ingest` run treats it as a first-time source and creates a
`source_id` at that point.

Rationale: sources are aspirational when declared in `sources.yaml`
and become real only when their bytes are read. A declaration that
never corresponded to readable bytes is noise, not a failure. Halting
ingest on the first bad path would block progress on the rest of the
manifest and invite ad-hoc retry mechanisms; a WARNING line in the
log is already sufficient debug evidence per §14.2.

### 13.5 Tags are many-to-many, not an embedded list

User-applied tags are modelled as the `source_tags(source_id, tag)`
table (see §5.1), not as an array column on `sources`. The
relationship between sources and tags is many-to-many: one source
may carry many tags and one tag may apply to many sources. Modelling
it as an embedded `VARCHAR[]` column on `sources` collapses the
relationship to one-to-many and hides the tag entity.

The normalised form keeps tag queries as ordinary SQL. "Find all
sources tagged `legal`" is `SELECT source_id FROM source_tags WHERE
tag = 'legal'`; "count sources per tag" is `SELECT tag, COUNT(*) FROM
source_tags GROUP BY tag`. Both are directly expressible in the
`duckdb` CLI and aligned with §14.1's inspectability promise — every
piece of state is a row in a named table, not an element of a
collection column that requires `UNNEST` gymnastics to interrogate.

Tag updates on re-ingest (declarative overwrite, per §8.2 and the
semantics of `sources.yaml`) are implemented as `DELETE FROM
source_tags WHERE source_id = ?` followed by a fresh `INSERT` of the
current tag set, inside the same transaction as any `sources` update.

### 13.6 Stored paths are declared, not canonical

`ingest` records the path the user *declared* (absolutized, symlinks
not dereferenced — §8.2), not the OS-canonical path. The earlier
behaviour called `resolve(strict=True)` and stored its result, which
silently rewrote a symlinked entry to its target's name. Because §7.3
routes on the file extension, a tree of extensionless files exposed
through `.eml`/`.pdf`/… symlinks would then store extension-less
paths, match no producer, and extract **nothing — with no error and no
WARNING**. That silent no-op is exactly the failure shape §14.3
forbids ("failures are recorded, not lost") and that the
`empty_succeeded` signal (§7.3) was added to give structural
attention; tolerating it for symlinked inputs was an over-specification
of the path, not a deliberate invariant. Storing the declared path
removes it and adds no format knowledge to the router.

A deliberate consequence: the declared file extension is **honoured**.
Exposing the same bytes as `x.eml` versus `x.pdf` routes them
differently, because the name is the user's declaration of intent — a
feature, not an ambiguity. Identity remains the content hash (§4.1), so
the cache key and any existing artifacts are untouched; only the path
recorded for provenance and the extension used for routing follow the
declaration. This is what lets a consumer (e.g. a mail bridge) expose
extensionless Maildir messages to the pipeline as `.eml` symlinks
without pkm needing to know anything about Maildir.

## 14. Strictness and first-principles debuggability

This project is intentionally strict. The following rules exist to
ensure that any state of the system can be understood and debugged
from first principles without recourse to tribal knowledge.

### 14.1 Every state is inspectable with standard tools

- The cache is a directory tree. Any artifact can be examined with
  `cat`, `file`, `jq`, `xxd`.
- The catalogue is a DuckDB file. Any state can be queried with
  the `duckdb` CLI.
- Logs are JSON Lines. Any event can be filtered with `jq` or
  `grep`.
- Configuration is a single YAML file. No environment variables,
  no runtime overrides, no magic.

At no point does the system rely on state that is not directly
visible in these four locations.

### 14.2 Every operation is traceable

Every cache write produces a log event that records the cache key,
input hash, producer identity, and the config hash. Given a cache
key, the user can always answer "why does this artifact exist?"
from logs alone.

### 14.3 Failures are recorded, not lost

A failed producer run writes a `meta.json` with `status: failed`
and an `error_message`. Failed artifacts occupy cache space so
that re-running the producer on the same input is a cache hit
(returning the failure) rather than a repeated attempt. An
explicit `--retry-failed` flag is required to re-attempt.

Rationale: implicit retry of failures is a debugging nightmare.
Explicit retry means the user always knows why work is happening.

**Unattempted sources.** A source may have no artifacts if routing
returned an empty producer list — typically because no available
producer claims to handle its format. This is distinct from
extraction failure (`status="failed"`), which records an attempted
extraction that did not succeed. Unattempted sources are a coverage
gap, not a failure state.

The catalogue has no explicit column representing unattempted
status. The canonical query to identify unattempted sources is:

```sql
SELECT s.source_id, s.current_path
FROM sources s
WHERE s.source_id NOT IN (SELECT a.input_hash FROM artifacts a);
```

A stricter variant, excluding sources whose only artifacts are
failures, identifies sources with no successful extraction:

```sql
SELECT s.source_id, s.current_path
FROM sources s
WHERE s.source_id NOT IN (
    SELECT a.input_hash FROM artifacts a WHERE a.status='success'
);
```

Making unattempted status a first-class catalogue representation
(via an explicit marker artifact, a flag on the `sources` table, or
a separate decisions table) is a Phase 2+ consideration.

### 14.4 Hash prefixes are unambiguous

All hashes are full SHA-256 hex (64 characters). No truncation
in identifiers, cache keys, or catalogue columns. Truncation
saves a few bytes and creates collision bugs.

Display code (log output, CLI output) MAY show truncated hashes
for readability, but always with a clear prefix convention
(e.g., `abc123…` with an ellipsis). Never silently truncate
in stored data.

### 14.5 Version strings are exact

Every version string in configuration is an exact match against
the installed tool's reported version. Startup verifies this and
fails loudly on mismatch:

- `pandoc --version` reports version; must match `config.yaml`.
- `python -c "import docling; print(docling.__version__)"` must
  match config.
- Similarly for every other producer.

Version matches are not "semver-compatible" or "at least this
version" — they are exact. Cache keys depend on them, so drift
without explicit acknowledgement is a correctness bug.

A producer with **no external tool** (the `email` producer, pure
stdlib) has no version to query. Its `version` is its own *logic*
version — a module constant `_VERSION`, hand-bumped on any behaviour
change (header set/order, body-part selection, HTML stripping). The
constructor still checks `config.version == _VERSION`, so config and
code cannot drift silently. But this is the one producer where
version correctness is a **code-review discipline, not a mechanism**:
there is no installed tool whose version would catch a forgotten
bump. The failure mode — changing the rendering without bumping
`_VERSION` — is that the cache silently mixes old- and new-format
artifacts under one key. Any change to the `email` producer's output
therefore requires a `_VERSION` bump; this is called out in CLAUDE.md
for reviewers.

### 14.6 No hidden state

The system maintains no hidden caches, no in-memory state that
survives a process, no background daemons. Every invocation starts
from the on-disk state and ends having written its changes to
the on-disk state. This guarantees that understanding the system
requires only understanding its on-disk layout.

### 14.7 No implicit conversions

Byte outputs are stored as bytes. Text outputs are stored with an
explicit declared encoding in `meta.json`. No auto-detection of
encoding at read time. No silent UTF-8 assumption. If a producer
emits Latin-1, that fact is recorded and consumers must handle it
explicitly.

### 14.8 Schemas are versioned, migrations are explicit

Every catalogue table has a `schema_version`. Every JSON format
has a `format_version`. Migrations between versions are explicit
Python functions in a `migrations/` directory, applied in order,
each logged. No automatic migration on startup — the user runs
`migrate` explicitly and sees what changes.

**Migration hash verification.** For every migration it has applied,
the `schema_meta` table stores the migration filename and the
SHA-256 hash of the migration file at the moment it was applied
(see §5.1). The migration runner recomputes the on-disk hash of
every previously-applied migration and compares it to the stored
hash before applying any new migrations. A mismatch — the file has
been edited after application, replaced with different content, or
removed — aborts with a clear error identifying the affected
migration and rejecting any further work. This is the same class of
paranoia as §14.5 version matching: the schema's derivation history
must remain reproducible from the source tree, so applied migrations
are immutable by policy. If a schema change is needed, a new
numbered migration is added in sequence.

### 14.9 Personal data never enters the repository

This repository is public. Personal data — the owner's or anyone
else's — never appears in a tracked file, in any commit, present or
historical. Sources live where they live (§2.1, §3); the repo carries
only code, schema, and **synthetic** examples and fixtures. Three
structural rules make a leak require deliberate effort, not a single
careless `git add`:

1. **Out-of-tree data.** Corpus, cache, catalogue, logs, and run
   retrospectives live under `root_dir` / `$LIFE_AGENT_KB`, outside the
   repo tree — `git add` cannot reach them. `.gitignore` additionally
   blocks their directory names defensively.
2. **Allowlist of safe shapes.** Tracked text may contain only
   obviously-synthetic data. `.githooks/pii_check.py` (committed and
   wired via `core.hooksPath` at pre-commit and pre-push; the pre-push
   hook scans every blob in every pushed commit, not just the net diff)
   rejects anything shaped like real personal data: a checksum-valid
   Israeli ID, a non-`@example.*` email, a passport or Israeli-mobile
   pattern, a **filesystem path under a non-placeholder root** (tracked
   text uses placeholder/system roots from `.githooks/pii-path-allow.txt`;
   the machine's real `$HOME` / `$LIFE_AGENT_KB` prefixes are derived from
   the environment at scan time — never stored in-tree — and rejected
   outright), or a literal from the private denylist at
   `$LIFE_AGENT_KB/pii-patterns.txt` (never in the repo). An allowlist
   catches *novel* PII, not just enumerated values. (A *bare* personal
   folder name with no path has no shape and stays the denylist's job.)
3. **Synthetic by construction.** Test and example identifiers are
   chosen to be unmistakably fake: synthetic Israeli IDs are
   deliberately **checksum-invalid** (e.g. `123456789`), synthetic
   emails use `@example.*`. A reviewed false positive may be exempted
   with an inline `PII-OK` marker, used sparingly.

The hooks are the whole gate — this is a solo repo with no server-side
CI by choice. They are still a net beneath the structure, not a
substitute (a hook can be skipped with `--no-verify`), so out-of-tree
data and synthetic-by-construction fixtures remain the real defence.

## 15. Retrieval (Phase 1 keyword search)

Phase 1 adds a two-stage retrieval pipeline on top of the extraction
layer: chunking (splitting artifact content into fixed-size text
windows) and FTS keyword search (BM25 over chunks via DuckDB's `fts`
extension). Embeddings and hybrid search are Phase 2 concerns.

### 15.1 Chunking

Chunking converts extracted artifact bytes into `artifact_chunks` rows.
It is a post-extraction step, not a Producer: it reads the existing
artifact cache, transforms content to text, and writes to the catalogue.

**Chunkable content types** (others are silently skipped):

| Content type                      | Extraction method                        |
|-----------------------------------|------------------------------------------|
| `text/plain`                      | Decode UTF-8 (replace on error)          |
| `application/x-docling-json`      | Concatenate `doc["texts"][*]["text"]`    |
| `application/x-unstructured-json` | Concatenate `items[*]["text"]`           |

**Chunk parameters** (defaults; not yet configurable in `config.yaml`):

- `max_chars = 1000` — maximum characters per chunk.
- `overlap = 100` — overlap between consecutive chunks (last 100 chars
  of chunk N are the first 100 chars of chunk N+1). Overlap ensures
  that a query term straddling a boundary is still reachable.

**Idempotency:** `write_chunks` begins with `DELETE FROM artifact_chunks
WHERE artifact_cache_key = ?` then inserts fresh rows. Running the
chunker twice on the same artifact leaves identical rows.

**Surrogate key:** each chunk carries a `chunk_id BIGINT` generated by
`seq_chunk_id` (migration 0005). This is the FTS `input_id` — it must
be unique per row, which `artifact_cache_key` alone is not (many chunks
share the same key). The surrogate key is an internal index detail; no
external system should depend on its value.

**Backfill:** `pkm chunk --backfill` iterates all `artifacts` rows with
`status='success'` that have no `artifact_chunks` rows, reads cached
content, and chunks it. This populates the index for the full pre-
existing corpus without re-running extraction. The backfill reports
two distinct skip categories: `file missing` (content file absent from
cache — catalogue inconsistency, investigate separately) and
`empty text` (content file present but `extract_text` returned `""`).
Empty-text skips for Docling-JSON artifacts indicate image-only PDFs;
these are handled by the Tesseract `empty_succeeded` routing path
(§7.3), not by the chunker.

**Empty-text detection contract (load-bearing).** The `empty_succeeded`
routing signal in §7.3 is defined as
`chunking.extract_text(content, content_type) == ""`. This makes
`extract_text`'s return value a routing contract, not merely a
utility function. Changes to its whitespace-trimming or
format-handling behaviour change which sources Tesseract is invoked
on, and must be evaluated against this invariant before merging.

### 15.2 FTS keyword search

DuckDB's `fts` extension provides BM25 full-text search over
`artifact_chunks`. The index is built with `PRAGMA create_fts_index`.

**Critical — Unicode tokeniser configuration.** DuckDB FTS's default
`ignore` regex is `'(\\.|[^a-z])+'`, which treats every non-ASCII
character as a token separator. Under this default, a chunk containing
Hebrew text such as `"תעודת זהות 123456789"` tokenises to *zero tokens*:
the index builds without error, queries return empty results, and no
diagnostic is produced. This behaviour is explicitly rejected.

The FTS index must be built with a Unicode-aware `ignore` pattern:

```python
conn.execute("""
    PRAGMA create_fts_index(
        'artifact_chunks', 'chunk_id', 'chunk_text',
        stemmer='none',
        ignore='[^\\p{L}\\p{N}]+',
        strip_accents=0,
        overwrite=1
    )
""")
```

Parameter rationale:

- `ignore='[^\\p{L}\\p{N}]+'` — DuckDB's regex engine is RE2, which
  supports `\\p{L}` (Unicode letter) and `\\p{N}` (Unicode digit). This
  splits on any character that is neither a letter nor a digit,
  correctly tokenising Hebrew (U+05D0–U+05EA), Arabic, CJK, and all
  other Unicode scripts alongside ASCII. **English-only `[a-z]`
  tokenisation is explicitly rejected for this corpus.**
- `stemmer='none'` — no stemmer handles Hebrew morphology; English
  stemmers corrupt Hebrew tokens. Queries must use exact lexical forms
  or numeric tokens (document numbers, account numbers, etc.).
- `strip_accents=0` — preserves niqud (Hebrew vowel marks) if present;
  can be reconsidered if niqud-bearing and niqud-stripped forms need to
  match.
- `overwrite=1` — allows rebuilding the index without a prior
  `drop_fts_index` call (which requires an explicit DuckDB sequence of
  drop-before-create and is brittle under transaction isolation).

**Known DuckDB FTS limitation:** the `stopwords='none'` parameter
causes `TransactionContext Error: Failed to commit: Could not commit
creation of dependency, subject 'stopwords' has been deleted` when used
against a disk database (reproducible on DuckDB 1.5.2). It is therefore
omitted; the default stopword list is English-only and has no harmful
effect on Hebrew or numeric tokens.

**Search join structure.** The `match_bm25` scalar function has a
DuckDB limitation: it cannot be called in a query that also performs
JOINs (raises "More than one row returned by a subquery"). The canonical
workaround is to compute BM25 scores in an inner subquery over
`artifact_chunks` alone, then join the scored results to `artifacts`
and `sources`:

```sql
SELECT scored.chunk_text, scored.score,
       s.current_path, scored.source_origin, scored.artifact_cache_key
FROM (
    SELECT chunk_id, artifact_cache_key, chunk_text, source_origin,
           fts_main_artifact_chunks.match_bm25(chunk_id, ?, fields := 'chunk_text') AS score
    FROM artifact_chunks
) scored
JOIN artifacts a ON scored.artifact_cache_key = a.cache_key
JOIN sources   s ON a.input_hash = s.source_id
WHERE scored.score IS NOT NULL
ORDER BY scored.score DESC
LIMIT ?
```

**`pkm chunk` CLI:**

```
pkm chunk --backfill
```

Iterates all unchunked artifacts with chunkable content types, extracts
text, chunks, and writes to `artifact_chunks`. Safe to run multiple
times (idempotent). Progress logged at INFO.

**`pkm search` CLI:**

```
pkm search "<query>" [--k 20] [--build-index]
```

Prints ranked results: BM25 score, source path, snippet (first 200
characters of chunk text). Diagnostics go to structured logging; user-
facing output goes to stdout.

**`pkm rebuild-index`** — standalone maintenance command that rebuilds
the FTS index. Called after `pkm chunk --backfill` when new chunks have
been added to `artifact_chunks`. Index rebuilding is a maintenance
operation, not a query parameter; the two are deliberately separated.

### 15.3 Phase 1 eval calibration

The Phase 1 eval (19 questions, `scripts/run_phase1_eval.py` in
`life-agent`) measures FTS retrieval quality for the personal document
corpus. Questions pass if the expected source is referenced by any
top-20 chunk. Grading categories:

- **PASS** — expected source in top-20 chunks.
- **FAIL** — source is in the corpus but not in top-20 (retrieval gap).
- **MISS_CORPUS** — source not yet ingested (data gap, not retrieval gap).

Phase 1 baseline (2026-05-24, 2132 sources, 300787 chunks):
**9/11 answerable questions pass; 8 corpus misses; 2 failures.**

The 2 failures are q-011 (partner's HKSAR passport) and q-019 (owner's
IL ID card). Both are image-quality failures, not FTS configuration
failures.

**Phase 1.5 outcome (2026-05-25, 2109 sources, 307766 chunks).** The
`empty_succeeded` Tesseract-PDF fallback (v0.3.1) was applied to the live
corpus: 660 image-only PDFs OCR'd at **100% conversion (0 Tesseract
failures** — the whole-document granularity policy never had to discard a
partial result), adding 6,639 chunks (300787 → 307766; the remainder are
the empty-Docling artifacts that correctly stay unchunked). **The eval was
unchanged: still 9/11 answerable, 9/19 total, 8 corpus misses.** Two
empirical findings:

1. **q-011 is NOT fixed by the routing change** — correcting the v0.3.1
   prediction. `<partner> passport.pdf` now has a Tesseract artifact whose
   `input_hash` matches the expected source exactly (the routing/plumbing
   is correct), but `heb+eng` Tesseract on a Chinese/HKSAR passport
   produces `CD7654321`, not the true `AB1234567`, with no legible expiry. <!-- PII-OK: synthetic passport codes -->
   The identifier is destroyed at OCR time, so FTS cannot match it. q-011
   is therefore reclassified from a coverage failure (Docling-empty) to an
   **OCR-quality failure, identical in class to q-019.**
2. **The empty-Docling backfill did not intersect the question set.** The
   658 silently-empty PDFs were real documents (company filings, bank
   scans) but answer none of the 8 corpus-miss questions; none flipped. The
   fix was justified for corpus completeness, not for this eval.

Both remaining answerable failures are now OCR-quality (FAILURES.md pattern
#1, the owner's top-ranked gap). Fixing them moves the eval by exactly 2;
the latent identity-document images (q-002/003/012/017) are missing-source
first and would hit the same OCR wall once ingested. They require image
preprocessing and/or a vision-model OCR producer (out of scope for
Phase 1).

**Deferred — subject-provenance gap.** Indexing scanned PDFs (including
passports) via the Tesseract fallback increases the corpus surface area
where person disambiguation is needed. A search for a passport number
will return chunks without indicating whose passport it is. This gap
exists in the text-PDF corpus already (Example Insurance health report contains
the partner's ID number, retrieved without subject annotation); the scanned-PDF
expansion widens it. Phase 2/3 fact-extraction must add a `subject`
field as a first-class attribute alongside `source_id`. See FAILURES.md
for tracking.

**Eval methodology superseded (2026-05-26).** The source-id matching above
("expected source in top-k") is retained here as the historical Phase-1
baseline, but it is **no longer the measurement of record**: it punishes
corpus growth (when a fact appears in newly-ingested sources, they displace
the pinned source from top-k and the question "fails" though the answer is
more available). The eval is now **answer-grounded** — ground truth is the
fact, graded by token-boundary presence in a top-k chunk — and classifies
failures by **mode**: PASS / RETRIEVAL_MISS (in corpus, not top-k) /
ABSENT_COVERAGE (not ingested) / ABSENT_EXTRACTION (OCR destroyed it), with
SUBJECT_CONFUSION as an orthogonal flag. The runner lives in **life-agent**
(`scripts/run_eval.py`) because it tests the composed agent (and, in Phase 2,
synthesis + citation validity), not just pkm retrieval; pkm's role is the
`pkm.retrieval.search` substrate it calls. Note this reclassified q-011 (the
HKSAR passport) from "OCR-unrecoverable" to PASS: the number is in the corpus
via typed sources (an email, a boarding card), which source-id matching —
pinned to the OCR-garbled `<partner> passport.pdf` — could not see.

## 17. Query surface (MCP server)

### 17.1 Purpose

`pkm` exposes a read-only MCP server (`pkm serve`) as its canonical external query interface.
The server wraps the FTS retrieval layer (§15) over the MCP stdio transport so that any MCP
client — Claude Code, pi-mono, or other local agents — can search the personal knowledge corpus
without needing direct Python imports or DuckDB access.

The server **retrieves only**. It does not synthesise answers, rank beyond BM25, or write to the
catalogue. Synthesis is the responsibility of the calling agent.

### 17.2 Tool contract

The server exposes exactly one tool: `search`.

**Input:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query`   | `str` | — | Keyword query string; Unicode (including Hebrew) is supported. |
| `k`       | `int` | 10 | Maximum number of chunks to return. |

**Output:** a JSON array of result objects, ordered by descending BM25 relevance:

```json
[
  {
    "chunk_text": "<extracted text snippet>",
    "score": 1.234,
    "source_path": "/path/to/source",
    "source_origin": "email" | "pandoc" | null,
    "artifact_cache_key": "<64-char hex>"
  }
]
```

`chunk_text` is a keyword-in-context (KWIC) snippet of ≤~300 chars centred on the
first matched query token. The full extracted text is in the catalogue but is not
returned to avoid saturating the caller's context window. Because KWIC centres on
the first matched token, the answer value may fall outside the window if it sits far
from the matched label in the same chunk.

The tool does not synthesise: the caller assembles a cited answer from the returned chunks.

On a retryable failure (catalogue locked by an active extraction), the tool returns a single-
element array with an `"error"` key rather than raising an exception:

```json
[{"error": "corpus temporarily locked by an active extraction; retry shortly"}]
```

### 17.3 Connection model

The server opens a **read-only** DuckDB connection (`read_only=True`) per request and closes it
immediately after the query. It holds no persistent connection between requests.

**Concurrency:**

- An *idle* server (between requests) holds no open DuckDB connection. `pkm extract` can acquire
  the write lock freely while the server is registered but not actively serving a request.
- DuckDB's cross-process model is *one read-write process OR multiple read-only processes —
  never both simultaneously*. A read request that arrives while `pkm extract` holds the write
  lock will fail with a lock conflict for the full duration of that extraction (which may be
  hours on a large corpus). The server catches this as a retryable error (§17.2) rather than
  crashing or hanging.

### 17.4 Transport

stdio only. The server's `stdout` carries the MCP JSON-RPC protocol stream; all logging goes to
`stderr` (and the configured JSONL log file) — never to `stdout`. Callers must not add any
`print()` calls to `mcp_server.py` that would corrupt the protocol stream.

### 17.5 Configuration

The corpus root (i.e. where `catalogue.duckdb` lives) is resolved **once** at server startup
from the `--config` flag passed to `pkm serve`, via the normal `load_config()` path. The
resolved root is stored in a module-level variable (`_ROOT`) and read by the `search` tool
closure at call time. This ensures `--config` actually reaches the tool and is not shadowed by
a default.

### 17.6 Classification

The MCP server is an *access surface*, not a producer or transform. It introduces no new cache
keys, no new extraction contracts, and no new migrations. Adding it does not change the
determinism or idempotency guarantees defined in §6 and §7.1.

## 16. Change log

- 0.7.0 (draft): §17 (new) — *read-only MCP query surface*. Adds `pkm serve` (stdio transport),
  a single `search` tool wrapping the §15 FTS retrieval, per-request DuckDB connections, and a
  structured retryable error for lock conflicts. New dependency: `mcp>=1.0`. No schema, cache-
  key, producer, or migration changes.
- 0.6.0 (draft): §14.9 (new) — *personal data never enters the
  repository*, made structural rather than detection-only: out-of-tree
  data, an **allowlist** of safe shapes enforced by
  `.githooks/pii_check.py` (a committed hook via `core.hooksPath`,
  pre-commit + pre-push; pre-push scans every pushed commit and is the
  whole gate — no server-side CI, by choice for a solo repo), and a
  synthetic-by-construction fixture rule (synthetic Israeli IDs are
  checksum-invalid; emails use `@example.*`). The safe-shapes allowlist
  also rejects **filesystem paths under a non-placeholder root**, so
  personal directory layout (mount paths, home subdirectories, project
  folder names) cannot leak: `.githooks/pii-path-allow.txt` lists the
  allowed placeholder/system roots and the real `$HOME`/`$LIFE_AGENT_KB`
  prefixes are derived from the environment at scan time, never stored
  in-tree (a bare folder name with no path stays the denylist's job).
  Adds the new top-level
  `.githooks/` directory and `tests/test_pii_guard.py`; extends
  `.gitignore` defensively; relocates the `notes/` run retrospectives
  out to `$LIFE_AGENT_KB` (run logs are data, not code). Doc + tooling
  only; no schema, cache-key, or producer change. Motivated by a
  2026-05 incident where real identifiers reached unpushed commits and
  a denylist-only pre-push hook missed unshaped corpus filenames.
- 0.5.0 (draft): §7.2 adds a fifth producer, `email` — a stdlib
  RFC822 (`.eml`) extractor that renders a fixed-order header block +
  body as `text/plain`, decoding only `text/*` parts (attachment
  payloads untouched, so the email corpus is body-only and large
  messages parse in milliseconds). §7.3 routes `.eml` to `email`
  (format-based eager, no fallback either way) and drops `.eml` from
  Unstructured (`.msg` stays). Motivation: Unstructured's `auto`
  strategy stalls in-process on large attachment-heavy messages
  (observed: 0 progress for 60 s at 89% CPU on the Sent corpus); the
  stdlib producer is fast and bounded because it never decodes
  attachments. §14.5 adds the versioning rule for a tool-less producer
  (`_VERSION` constant; code-review discipline). §12 records the
  plugin-registry reconsideration at the 5th producer (deferred
  again). Promotes `beautifulsoup4` (already transitive via
  `unstructured`, v4.14.3) to a direct dependency for HTML-body
  stripping. No schema change. Affects:
  `producers/email_producer.py` (new), `routing.py`,
  `producers/unstructured.py` (drops `.eml`), `extract.py`, `cli.py`,
  `pyproject.toml`, config, and tests.
- 0.4.0 (draft): §8.2 + new §13.6 — `ingest` stores the **declared**
  path (`os.path.abspath` of the `~`-expanded entry; symlinks not
  dereferenced) in `current_path` and `source_paths.path`, instead of
  the `resolve()`-canonicalized path. `resolve(strict=True)` is retained
  only as the existence/readability gate (§13.4) and to read bytes for
  hashing, so `source_id` and cache keys are unchanged. Motivation: a
  symlinked source tree previously stored extensionless paths, matched
  no producer, and extracted nothing **silently** — a §14.3 fail-fast
  violation; the declared file extension is now honoured for routing
  (§7.3). Minor bump, not patch: this is a breaking change to the
  path-persistence contract even though no consumer depends on the
  canonical form. **No migration required** — `source_paths` already
  exists (migration 0001), the `sources` schema is unchanged, existing
  rows remain valid, and newly observed/re-observed rows store declared
  paths. Affects: `ingest.py` (`_expand_entry`, `ingest_sources`) and
  its tests. No new dependencies.
- 0.3.2 (draft): Documentation only — records the empirical Phase 1.5
  eval outcome in §15.3. The v0.3.1 `empty_succeeded` fix was applied to
  the live corpus (660 image-only PDFs OCR'd, 100% conversion, +6,639
  chunks) but the eval was **unchanged** (9/11 answerable, 9/19 total).
  q-011 is reclassified from a coverage failure to an OCR-quality failure,
  correcting the v0.3.1 prediction: the passport is now indexed, with a
  source-id-matching artifact, but `heb+eng` Tesseract OCRs it to garbage.
  Whole-document granularity validated (0 partial-result discards). Both
  remaining answerable failures (q-011, q-019) are now OCR-quality. No code
  or schema change.
- 0.3.1 (draft): §7.3 adds `empty_succeeded` routing signal and the
  Tesseract-PDF fallback rule: image-only PDFs (Docling success with
  `chunking.extract_text == ""`) route to Tesseract via `pdftoppm`
  rasterization. Documents whole-document granularity for Tesseract-PDF
  (per-page failure = whole-producer failure; no partial caching). §15.1
  adds the empty-text detection contract (load-bearing coupling from
  routing to `extract_text`) and separates backfill skip counters into
  `file missing` and `empty text`. §15.2 adds `pkm rebuild-index` as a
  standalone maintenance subcommand; removes `--build-index` from
  `pkm search`. §15.3 updated to note q-011 is addressed by this fix;
  adds deferred subject-provenance gap note. Affects: `tesseract.py`
  (PDF support), `routing.py` (`empty_succeeded` param), `extract.py`
  (empty-text detection), `cli.py` (rebuild-index subcommand, backfill
  counter fix). No schema change.
- 0.3.0 (draft): Adds §15 (Retrieval), §5.1 `artifact_chunks` table
  + `seq_chunk_id` sequence (migration 0005). §12 updated: FTS keyword
  search moves in-scope; subject provenance and hybrid search remain
  Phase 2. §15.1 specifies the chunking pipeline: chunkable content
  types (`text/plain`, `application/x-docling-json`,
  `application/x-unstructured-json`), character-based splitting
  (1000 chars, 100-char overlap), delete-then-insert idempotency,
  surrogate `chunk_id` as FTS input_id, and `pkm chunk --backfill`.
  §15.2 specifies the FTS configuration: Unicode-aware tokeniser
  `ignore='[^\p{L}\p{N}]+'` is mandatory — English-only `[a-z]`
  tokenisation silently produces zero tokens for Hebrew and is
  explicitly rejected; `stemmer='none'` (no stemmer handles Hebrew
  morphology); `strip_accents=0`; `overwrite=1` (avoids drop-then-
  create brittleness). Documents the DuckDB `stopwords='none'` bug on
  disk databases (omit the parameter), and the BM25 subquery pattern
  required to work around the JOIN restriction. §15.3 records the
  Phase 1 eval baseline: 9/11 answerable questions pass (9/19 total,
  8 corpus misses, 2 image-quality failures). Schema change: migration
  0005. No new Python dependencies.
- 0.1.11 (draft): §7.2 adds `tesseract` as a fourth extractor
  (OCR for `.jpg/.jpeg/.png/.tif/.tiff/.bmp`), superseding the
  "exactly three" phrasing. §7.3 adds the Tesseract routing rule
  (format-based, no fallback — images have no alternative producer).
  §9 adds the `tesseract:` config block with `languages: heb+eng`,
  `psm: 3`, `oem: 3`, `version: "5.5.2"`. Abstraction still
  deferred; a fifth producer is the reconsideration point. No
  schema change; no new dependencies.
- 0.1.10 (draft): §14.3 gains an "Unattempted sources" paragraph
  naming the coverage-gap case surfaced by the Step 7h 1000-doc
  stratified run. Routing can legitimately return an empty
  producer list for sources whose format no producer claims to
  handle (observed: `.org` files silently skipped by pkm's
  Pandoc wrapper despite Pandoc supporting `org` natively, and
  `.xml` files which no producer handles). Such sources have
  no artifact row — neither `success` nor `failed` — so the
  catalogue's current schema cannot distinguish "unattempted" from
  "not yet processed". The addendum documents the distinction,
  names the canonical `NOT IN` query, and defers first-class
  representation (marker artifact, sources flag, decisions table)
  to Phase 2+. Pure documentation; no code or schema change. The
  concept is named so future sessions don't reinvent it under a
  different term.
- 0.1.9 (draft): §7.1 gains an "Uncatchable failure modes" paragraph
  acknowledging that the `Producer.produce()` "never raises"
  guarantee holds only for Python-catchable failures. OS signals
  (notably SIGKILL from the Linux OOM killer), kernel panics, and
  parent-process termination bypass Python entirely — there is no
  opportunity for the producer to return `status="failed"`. The
  Step 7h diagnostic surfaced this concretely: a third consecutive
  run of the Docling producer on the same 12 MB PDF OOM-killed the
  process at ~24 GB RSS, vapourising the Python interpreter. The
  new paragraph documents the consequence (the catalogue stays
  consistent, but there is no failed-artifact row for the killed
  source; subsequent `pkm extract` runs re-attempt the source and
  will recur on pathological inputs), and notes that mitigations
  (subprocess isolation, per-document memory limits, pre-flight
  size estimation) are Phase 2+ concerns not required by the
  Phase 1 contract. No code change; pure documentation of an
  operational reality the contract could not cover.
- 0.1.8 (draft): §7.1 determinism contract corrected. The prior
  wording required byte-level determinism ("be deterministic
  given the same input content and config"), which is neither
  achievable nor necessary for producers that wrap non-
  deterministic ML libraries. Step 7h's first real-corpus run
  surfaced this: Docling produced different floating-point bbox
  coordinates across three runs on the same PDF (crhk utility
  bills, 14% of 35 Docling extractions were non-stable at the
  byte level). The coordinates differ at the fourth-fifth decimal
  place — semantically meaningless, but byte-unequal.
  The corrected contract says producers produce *semantically*
  equivalent output; the cache is keyed on
  `(input_hash, producer_name, producer_version,
  producer_config_hash)` rather than on output bytes; once an
  artifact is written it is never overwritten except through
  explicit `--retry-failed`. The §7.1 Note on hidden-input audits
  is reframed around what *would* cause inputs to be
  misidentified as different inputs — path/time/hostname leaking
  into identifiers downstream consumers use to compare content —
  which remains a real discipline (the Unstructured `element_id`
  fix in 7e stays). The canonical path-independence test is
  renamed from `test_cached_bytes_are_path_independent` to
  `test_cache_key_is_path_independent`. The `--verify` flag on
  `pkm extract`, which implemented byte-equality verification, is
  removed in the corresponding code commit — it was asserting an
  invariant that no longer holds.
- 0.1.7 (draft): §6.2 gains a "Deletion is a single sanctioned
  pathway" paragraph. The cache's append-only discipline was
  implicit through v0.1.6; the `--retry-failed` implementation
  in 7g made it explicit that one code path does delete cache
  entries, and the spec now names it. Rationale for pinning:
  without the named exception, any future path tempted to DELETE
  from the `artifacts` table (a 7h triage helper, a maintenance
  command, a cleanup cron) would look equally legitimate. The
  §6.2 paragraph declares `cache.delete_artifact` the only
  sanctioned deletion call, documents the file-first ordering
  (interrupted deletion leaves at worst a sweep-collectable
  orphan, never a row-without-files case), and notes the
  append-only invariant as load-bearing for §14.1 inspectability
  and Phase 2 query semantics. No schema change, no code change.
- 0.1.6 (draft): Two edits, both prompted by Step 7 implementation
  findings. §7.1 gains a "Note on hidden state in wrapper producers"
  paragraph that codifies the lesson from Step 7e: the Unstructured
  library's default JSON serialisation embeds the input filename
  into element_id hashes, which would have silently fragmented the
  cache across byte-identical content at different paths. The note
  mandates a path-independence test for every wrapper producer and
  documents the canonical check pattern. §7.3 is rewritten to
  reflect format-based routing defaults (Docling eagerly on PDFs,
  Unstructured eagerly on email) with tags as an escalation
  mechanism rather than a gate. Prior §7.3 wording depended on tags
  for the common cases; implementation reasoning pointed out that
  tag coverage will always be patchy and file extension is a
  stronger mandatory signal. Fallback rules (Docling on Pandoc
  failures, Unstructured on both-failed) are promoted from implicit
  to explicit.
- 0.1.5 (draft): Tag storage normalised. §5.1 replaces the
  `tags VARCHAR[]` column on `sources` with a dedicated
  `source_tags(source_id, tag)` table, primary-keyed on the pair,
  with an index on `tag` and a foreign key to `sources`. §13 gains
  §13.5 with the modelling rationale: tags are many-to-many between
  sources and tag strings, and the embedded-list representation was
  modelling the relationship as one-to-many against its actual
  shape. The normalised form makes queries like "find all sources
  tagged X" and "count sources per tag" first-class SQL and keeps
  §14.1's inspectability promise intact — every piece of state is a
  row in a named table, not an element of a collection column.
- 0.1.0 (draft): Initial specification covering Phase 1 foundation.
- 0.1.1 (draft): Resolved §13 design decisions; added §14 on
  strictness and first-principles debuggability.
- 0.1.4 (draft): §6.2 extended with an "Asymmetric recovery"
  paragraph documenting how the reverse of an orphan — a catalogue
  row whose cache files are missing — is handled. The sweep covers
  only the files-without-row direction; the row-without-files
  direction aborts the current operation with
  `CacheInconsistencyError`, logs ERROR, and leaves the catalogue
  untouched. Reconciliation is the user's explicit call via
  `pkm rebuild-catalogue`. Rationale: silently producing new bytes
  for a known cache key would mask data loss with unverifiable
  output; an explicit abort preserves the forensic trail.
- 0.1.3 (draft): Migration hash verification and schema_meta
  extension. §5.1 extends `schema_meta` with `migration_id` and
  `migration_hash` columns so each row records which migration
  produced the schema version and what that migration file hashed to
  at apply time. §14.8 adds a new paragraph mandating that the
  migration runner re-hashes every previously-applied migration
  on every run and aborts loudly on mismatch — the same class of
  paranoia as §14.5 version matching. Rationale: without the stored
  filename + hash, "schema_meta records the current state" conflates
  with "schema_meta records the path taken to get here", and there
  is no way to detect an applied migration being edited in-place.
  The conflation is resolved by making `schema_meta` a true log of
  applications rather than a one-row version marker.
- 0.1.2 (draft): Four edits resolving ambiguities surfaced during
  Phase 1 implementation planning:
    - §5.3 narrowed to rebuild `artifacts` only; `sources` is
      repopulated by re-running `pkm ingest`. Rationale: `sources`
      rows carry observational data that cannot be reconstructed
      from cache alone, so the only honest rebuild is artifact-only.
    - §6.2 rewritten to state the visible invariant explicitly
      ("no catalogue row without files, no files without a catalogue
      row on next run") and to name the commands that run the orphan
      sweep (`pkm extract`, `pkm rebuild-catalogue`). Rationale: the
      previous "single transaction" phrasing conflated FS and DB
      atomicity, and "on next run" had no clear referent without a
      daemon.
    - §7.1 determinism contract clarified: deterministic given the
      same input *content* (by `input_hash`) and `config`;
      `input_path` is an I/O handle, not part of the contract.
      Rationale: paths differ by machine, so the old wording could
      be read to permit path-dependent behaviour, which would break
      cross-machine cache parity.
    - §13.4 added to cover paths that never resolved (including
      unreadable, permission-denied, broken-symlink, device-file
      cases). Rationale: previously conflated with §13.2 ghost
      behaviour; separating them prevents ad-hoc retry logic and
      clarifies that ingest never halts on bad manifest entries.
