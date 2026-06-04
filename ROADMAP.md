# Personal Life-Management Agent — Roadmap

*This is the approved plan. `life-agent` is the composition root described in [`CLAUDE.md`](./CLAUDE.md).*

## Context

Goal: an assistant that manages your digital life as well as or better than a human PA —
**remembers** everything, **reasons** under uncertainty, **acts** across your tools, is reachable
anywhere, and is proactive. The concrete seed task ("find my Israeli ID across all my data")
generalises to "ask/find anything about my life, with citations."

Key realisation from mapping the stack: **you already own ~90% of the building blocks** — the work is
integration + a retrieval layer + wiring, not greenfield. The commissioned "Nix for documents"
report ([`docs/nix-for-documents-report.md`](./docs/nix-for-documents-report.md)) confirms **PKM** is
already an instance of the right architecture (content-addressed, pure-function `(input, prompt,
model)` transforms) and warns against over-building: *measure what you actually need before building
the retrieval "cathedral."*

Locked decisions: local-vs-cloud is an engineering (not privacy) choice; first win = ask-anything
search; scope = text-first; **brain = credence** (the Bayesian governor); leverage existing
projects, especially **PKM**. The agent-loop *spine* is deliberately **not** locked — see
Architecture and Open decisions.

## North star

An agent that **maximises the owner's expected utility**: remembers everything, reasons under
uncertainty about what matters, acts across the owner's tools, and is proactive. The seed task
("find my Israeli ID across all my data") was the first rung; the destination is decision-theoretic
(value-of-information-driven ask/proceed/block), which is exactly why **credence** is the brain and
not optional.

## Architecture — faculties over language-neutral seams

The agent is **four faculties + a spine**, each in the language that serves it, integrated over
**language-neutral boundaries** (MCP / HTTP / CLI) — *not* a single-language monolith. Compose,
don't rebuild: ~90% already exists in the owner's repos.

| Faculty | System / language | Status |
|---|---|---|
| **Memory** — recall + retrieval | **PKM** (`src/pkm`, Python) + **`life_agent`** (this repo, Python) | **Live.** PKM: content-addressed extraction + DuckDB `fts`/`vss`. `life_agent` adds the retrieval/synthesis read path (`scripts/ask.py`, dogfooded via `bin/ask-live`). |
| **Brain** — beliefs under uncertainty; value-of-information → ask/proceed/block | **credence** (`../credence/apps/credence-pi`, Julia posterior) | Not wired. *The confidence-gated autonomy* — the core of "maximise expected utility". |
| **Hands** — capabilities/actions | MCP / HTTP servers: **Jarvis** (tasks, exists, 13 tools, `user_id 12365873`), email (`msmtp`/JMAP), calendar (CalDAV/Google), chat (matrix) | Not wired. |
| **Goals / Utility** — what the owner values | *(new, unbuilt)* | **The hardest missing piece.** EU-maximisation presupposes it; owed a design before any autonomous *action*. |
| **Spine** — the agent loop + routing | **TBD — open decision** | Deferred to Phase 2. Candidates: pi-mono (TS, open/extensible — the original pick), a Python loop, or Claude Code as an interim loop. |

**The seams are the architecture.** Each faculty is reachable over a stable, language-neutral
contract, so the spine — whatever language wins — can call Memory and Brain without caring how
they're built. MCP is endorsed *as a seam*; the earlier `pkm-memory` MCP server was built then
**torn down** (operational — a leaked process — not an architecture verdict). Today the memory read
path is dogfooded directly via `bin/ask-live`, and Claude Code itself is the only (manual) reasoning
loop. **Autonomic:** n8n + `systemd` timers (`mbsync`, `renavon-inbox-ingest`) already run ingestion.

## What the report changes (build-vs-adopt verdicts)
- **Determinism:** PKM already correct (semantic, not bitwise; cache keyed on inputs; SPEC §7.1). No change.
- **Orchestration:** keep PKM bespoke — **do NOT adopt Hamilton now** (over-engineering until multi-step
  DAGs; `artifact_lineage` already Hamilton-ready; revisit Phase 3).
- **Vectors:** DuckDB `vss`+`fts` (endorsed). Mind: filtered top-k is broken → **over-fetch k·10 then
  filter**; `SET hnsw_enable_experimental_persistence=true`; back up `.duckdb` (borg already runs).
- **Prompts:** DSPy **offline only** (freeze tuned prompts in YAML; never at runtime — would break cache).
- **Chunking/ingestion:** optional LlamaIndex `IngestionPipeline` as a wrapped Phase-1 chunker, or hand-roll.
- **Cache-key hardening (minor, Phase 1):** add `output_schema_hash`, inference-engine/SDK version, and
  split `prompt_template_hash` from filled bindings. Not blocking.
- **OCR:** standalone **Tesseract producer** (`tesseract -l heb+eng`, ~1-file clone of the pandoc
  producer, no new Python dep) — chosen for speed and predictable Hebrew over the heavier Docling path.
- **Karpathy wiki:** a warm-cache + measurement layer, not a competitor → Phase 0.

## Roadmap (each phase usable on its own)

### Phase 0 — Measure + needle-find · this weekend  *(both, in parallel)*
- **Karpathy-style LLM wiki** (under `$LIFE_AGENT_KB`, outside the repo): `raw/` (your notes +
  already-extracted text directories, plus a `tesseract -l heb+eng` pass over scanned images so scans
  like an ID card join the corpus) → the `docs/kb-schema.md` schema → Claude Code authors `wiki/` with
  `[[wikilinks]]` → ask ~20 real questions (`bin/ask`) → **log what it can't answer** (this defines the
  retrieval requirements). Near-zero code.
- **OCR+grep needle-finder** (`scripts/needle.sh`): OCRs images on demand and greps the corpus —
  answers document lookups immediately. The seed example (an ID-card scan in the documents directory)
  is found this way; the corpus roots are configured via env / the out-of-tree registry, not hardcoded.

### Phase 1 — PKM retrieval substrate · **substrate complete; corpus live**
1. **(done)** Bump PKM **SPEC → v0.3.0** authorising retrieval/embeddings/extensions/local MCP server (governance-first).
2. **(done)** **`TesseractProducer`** (`src/pkm/producers/tesseract.py`, heb+eng) wired into `routing.py` +
   `extract.py` + `cli.py`; migration `0004` (`chunks`, `embeddings FLOAT[768]`, `source_origin`).
3. **(done)** Local embeddings via Ollama `nomic-embed-text` (stdlib `urllib`, no new dep).
4. **(done)** DuckDB `fts` + `vss` hybrid query (over-fetch k·10); `pkm search` CLI; `pkm-memory` MCP
   (FastMCP, mirroring `jarvis-lite/mcp_server.py`) — **later retired**; retrieval now via `bin/ask-live`.
5. **(done) Source adapters — now a declarative registry, not ad-hoc scripts.** Sources are declared
   in a **`data-sources.yaml`** registry (real one under `$LIFE_AGENT_KB`, fake schema in
   `config/data-sources.example.yaml`) and enumerated from **plocate** (the system file index,
   repurposed via a one-line `/etc/updatedb.conf` change so it covers your data mount). Two pieces:
   - `scripts/data_source_registry.py` — loader + plocate census + `--report` (classifies every file
     by pkm producer coverage: "ingestable today" vs "no producer yet"); deferred roots (photos)
     counted, never ingested.
   - `scripts/ingest_sources.py` — promote step: `filetree` + `maildir` adapters (the latter reusing
     `mail_bridge.py`) → merge into pkm `sources.yaml` (dedupe by path, union tags) → `pkm ingest`.
   Adding **chat** (matrix-archiver SQLite) or **contacts** (Fastmail CardDAV → CRM people-seed) is
   now *a new `kind` adapter + a registry entry*, deferred to dogfood evidence / Phase 2.

> **Status — substrate built, corpus live, dogfooded via `bin/ask-live`:** the live catalogue
> (NVMe; ~13k sources / ~400k chunks incl. the Downloads root) answers cited questions end-to-end. The
> `pkm-memory` MCP server was built then **torn down** ("not a fan"); dogfood is now direct via
> `bin/ask-live`. Dogfooding surfaced a real retrieval miss (query-expansion, shipped) and a
> synthesis miss (own-corpus attribution, fixed) — exactly the FAILURES-driven signal the loop is for.

### Phase 1.5 — Mature memory · **ACTIVE, dogfood-driven**
Build **only what `$LIFE_AGENT_KB/FAILURES.md` demands**, dogfooding between changes (no speculative
build). Known candidate levers (not a fixed list — promote by evidence):
- **OCR the image-PDFs** — route the failed/empty-text extractions through the Tesseract producer so
  scanned docs become searchable (the standing extraction-quality frontier).
- **Retrieval ranking** — nudge `EXPAND_SYSTEM` to always emit document-type nouns
  (agreement/contract/certificate) so authoritative docs surface for status/identity phrasings.
- **Coverage** — new source `kind` adapters (matrix chat, CardDAV contacts) as dogfood calls for them.

### Phase 2 — Goals/utility model + first agent loop (read-only) · future
- Design the **goals/utility representation** (the unbuilt faculty) — how the agent learns and
  stores what the owner values. Owed before any write-action.
- Build the **first real agent loop over read-only capabilities** (daily briefing, "what needs
  attention"), reasoning over memory, gated by **credence** (VOI ask/proceed/block — safe because
  nothing is destructive). **The spine is chosen here** (see Open decisions).

### Phase 3 — Action layer + autonomy · future
Write-capabilities (Jarvis tasks, email drafts, calendar) under credence ask/proceed/block;
omnichannel (Telegram/Matrix, Tailscale-only); scope expansion to photos (PhotoPrism + vision),
then the 661 GB encrypted `more/` (needs keys).

### Open decisions (decide when the phase arrives, not before)
- **The spine** (Phase 2): pi-mono (TS, open/extensible) vs a Python agent loop vs Claude Code as an
  interim loop. Criterion: openness/extensibility vs lock-in. Owner is neutral; MCP-as-seam is not ruled out.
- **The goals/utility representation** (Phase 2): the form the EU model takes.

## Critical files
- **`.` (this repo):** the Python **memory layer** over pkm — `src/life_agent/core/` (shared infra:
  LLM calls, secrets, config, source rendering), `scripts/ask.py` (retrieval + synthesis, run via
  `bin/ask-live`), the configurable data layer (`scripts/data_source_registry.py`,
  `scripts/ingest_sources.py`, `config/data-sources.example.yaml`), and the frozen blind-comparison
  harness (`scripts/comparison/`). Future faculties (brain, loop, hands) compose over seams; the
  spine is not yet chosen. (Knowledge + the *real* `data-sources.yaml` live under `$LIFE_AGENT_KB`.)
- **pkm:** `SPEC-PRINCIPLES.md(done)`, `SPEC-v0.3.0.md(done)`, `migrations/0004_*.py(done)`,
  `hashing.py(hardened)`; still to come: `src/pkm/producers/tesseract.py(new)`,
  `src/pkm/{chunking,embeddings,retrieval,mcp_server}.py(new)`, `cli.py`, `routing.py`, `extract.py`.
- **credence-pi:** `bdsl/capabilities.bdsl` (gate new capabilities), `extension/src/index.ts`,
  `daemon/server.jl`.
- **jarvis-lite:** `mcp_server.py` (exists).

## Verification
- **Phase 0:** ask ~20 real questions to the wiki; record hit-rate + failure list (`$LIFE_AGENT_KB/FAILURES.md`).
  `tesseract -l heb+eng <id-card-scan> stdout` returns Hebrew text incl. the ID number.
- **Phase 1:** `uv run pkm search "תעודת זהות"` returns the ID with provenance; idempotent re-ingest
  (double-run no-op); `pytest`/`ruff`/`mypy` green; `bin/ask-live` returns cited answers from the corpus.
  **Data layer (done):** `python scripts/data_source_registry.py --report` prints the per-root census;
  `python scripts/ingest_sources.py` is idempotent (re-run = no new catalogue rows). Retrieval is
  dogfooded via `bin/ask-live` (the `pkm-memory` MCP server was retired); `pytest tests/` green.
- **Phase 1.5:** a `FAILURES.md`-traced change moves a real dogfood miss (e.g. an image-PDF becomes
  searchable after OCR routing); idempotent re-ingest; no FTS-ranking regressions.
- **Phase 2:** the read-only loop renders a daily briefing; credence asks/auto-proceeds appropriately
  on read-only capabilities; a goals/utility representation exists and is consulted.

## Resolved decisions
- **Phase-0 strategy:** Karpathy-wiki measurement **and** OCR+grep needle-finder, in parallel.
- **OCR:** standalone Tesseract producer (heb+eng).
- **Repo layout:** this repo is the composition root; capabilities stay in their own repos, composed
  over language-neutral seams. It currently *is* the Python memory layer over pkm; the spine that
  will run the agent loop is an **open decision** (Phase 2), so the repo doesn't yet assume one.
- **Polyglot by design:** each faculty in the language that serves it (Memory = Python, Brain =
  Julia); not everything is one language — the seams (MCP/HTTP/CLI) are what hold it together.
