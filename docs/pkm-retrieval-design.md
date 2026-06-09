# PKM retrieval design (code-grounded)

> **Status: implemented (Phase 1); retained as the design record.** The MCP server it plans was
> built then retired — the seam stands, the live server is deferred
> ([`PRINCIPLES.md`](../PRINCIPLES.md) §5).

How to extend `src/pkm` into the memory core. PKM already has the data model for retrieval; it
lacks a retrieval reader, an embedding step, a non-file source path, and any server. Add those four
without touching the cache/catalogue/hashing invariants. **Governance: amend pkm `SPEC.md` → v0.3.0
first** (its rules forbid retrieval/servers/new-deps until the SPEC says otherwise), and follow
**TDD** + the **idempotency double-run** rule.

## 1. Producer interface + the OCR producer
- `Producer` is a `typing.Protocol` in `src/pkm/producer.py` (`name`, `version`, `handled_formats`,
  `produce(input_path, input_hash, config) -> ProducerResult`). **No registry** — producers are wired
  by explicit ladders in `routing.py` and `extract.py` (`_PRODUCER_NAMES`, `_needed_producer_names`,
  `_ensure_constructed`) and the `--producer` choices in `cli.py`.
- **`TesseractProducer`** (`src/pkm/producers/tesseract.py`) = a near-clone of `producers/pandoc.py`:
  - `handled_formats = {.jpg,.jpeg,.png,.tiff,.tif,.bmp}`; shell out to
    `tesseract <path> stdout -l <langs> --psm <n> --oem <n>`; return `ProducerResult(status="success",
    content=<bytes>, content_type="text/plain", content_encoding="utf-8")`; **never raise** (catch
    timeout/non-zero → failed).
  - Config `{"languages":"heb+eng","psm":3,"oem":3}` — part of the config dict, therefore part of the
    **cache key** (different langs ⇒ different key; correct). Pin the `tesseract` version like pandoc does.
  - **No new Python dependency** (call the binary; do not add `pytesseract`).
  - Wire: add the import + clause in `routing.py`; add to the three ladders in `extract.py`; add to
    `--producer` choices in `cli.py`. Add a SPEC §7.2 producer-table row + a Stage-A test **first**.

## 2. Source adapters (email/chat/notes/contacts) — Phase 1 later
The cache is already content-centric (`compute_cache_key` takes any sha256; `write_artifact` takes
bytes). File-centricity lives only in `ingest.py` (`sources.current_path NOT NULL`) and the
`produce(input_path)` signature. **Model each non-file source as "materialise canonical bytes":**
an adapter (`src/pkm/adapters/{email,chat,markdown,vcf}.py`) emits `(canonical_bytes, source_type,
provenance)`; write the bytes into a content-addressed **source store**
(`<root>/sources/objects/<aa>/<bb…>`), so `source_id = sha256(bytes)` and idempotency hold verbatim,  <!-- PII-OK: pkm cache layout, not a personal path -->
and `produce()` gets a real on-disk path. Give synthesised objects an explicit extension (`.eml`,
`.json`) so extension-based routing still works. Email canonical bytes = raw RFC822 (the
**unstructured** producer already extracts `.eml`). Add a normalised `source_origin` table (below).

## 3. Catalogue + migration `0004`
Schema is **only** numbered migrations in `src/pkm/migrations/` (hash-verified — never edit a landed
one). Current: `sources`, `source_paths`, `artifacts` (0001), `source_tags` (0002),
`artifact_lineage` + approval tables (0003). Extracted text/entities live in the **cache** (bytes via
`artifacts.content_path`), not DuckDB; there is **no entities table** (entities are JSON blobs). No
FTS yet. Add `0004_retrieval_substrate.py` (schema_version 4):
- `chunks(chunk_id PK, artifact_cache_key, source_id, ordinal, char_start, char_end, text,
  chunker_name, chunker_version, chunker_config_hash)` — text lives here (FTS needs it).
- `embeddings(chunk_id PK, model_name, model_version, dim, vector FLOAT[768])` — fixed-size array (HNSW needs it).
- `source_origin(source_id PK, source_type, account, external_id, origin_date, origin_path)` — provenance.
Make `chunks`/`embeddings` **rebuildable** (extend `rebuild.py`); `chunk_id`/embedding identity = sha256
of a canonical descriptor (idempotent).

## 4. Embeddings — stay in DuckDB
- **Do not add sqlite-vec / LanceDB / Qdrant.** DuckDB 1.5.2 here loads `vss` + `fts` (verified). One
  transaction writes chunk + vector; hybrid retrieval is one SQL query.
- Chunking: `src/pkm/chunking.py` — pure `chunk_text(text, max_chars, overlap) -> [Chunk]`.
- Embeddings: `src/pkm/embeddings.py` — POST to Ollama `localhost:11434/api/embeddings`
  (`nomic-embed-text`, 768-dim) via **stdlib `urllib`** (no new dep). Store `model_version` = the
  Ollama digest. This is *not* gated by the transform/approval machinery — keep it a small module.
- **Hybrid query** (`fts` BM25 + `array_cosine_distance`): join `chunks` ⨝ `embeddings` ⨝
  `source_origin`, blend scores, return text + provenance. **Gotcha from the report:** DuckDB filtered
  top-k is broken (HNSW runs before `WHERE`) → **over-fetch k·10 then filter**; ship brute-force cosine
  first (correct at personal scale), add HNSW behind `SET hnsw_enable_experimental_persistence=true` later.

## 5. Surfaces
- **CLI `pkm search "<q>"`** — add a parser + handler in `cli.py` (match `_SUBCOMMANDS`; import the
  retrieval module *inside* the handler). Calls `src/pkm/retrieval.py::search(root, config, query, k, mode)`.
- **`pkm-memory` MCP server** — `src/pkm/mcp_server.py`, **FastMCP**, mirroring
  `../jarvis-lite/mcp_server.py` (thin wrappers, `mcp.run(transport="stdio")`). Tools:
  `search`, `get_source` (returns provenance + extracted text via `cache.read_artifact`), `ask`
  (retrieval → return a cited context pack for the calling model to synthesise — simplest, no extra LLM cost).
  Read-only (sidesteps DuckDB single-writer). Add a `[project.scripts]` entry `pkm-memory`.

## 6. Tests & sequencing
- Tests mirror modules; `tests/conftest.py` has `tmp_root`/`migrated_root`. **Stage-A = hermetic**
  (hand-seeded `chunks`/`embeddings` with fixed vectors, no Ollama); gate live-Ollama tests behind a
  marker like the existing `-m 'not llm'`. Gates: `uv run pytest`, `ruff check`, `mypy` (strict).
- **Fastest path to the ID win:** (1) `TesseractProducer`; (2) migration `0004` + DuckDB `fts` +
  `pkm search` keyword-only over chunk text — **answers `pkm search "תעודת זהות"` with no embeddings/
  Ollama**. Then (3) chunking driver, (4) embeddings + hybrid, (5) `pkm-memory` MCP, (6) source adapters.

## Cache-key hardening (minor, optional in Phase 1)
PKM hashes the *full rendered prompt* and a `model_identity` (model name + temp/max_tokens). The
report suggests also: split `prompt_template_hash` from filled bindings; add `output_schema_hash`,
inference-engine/SDK version. Not blocking; do alongside the transform work if convenient.
