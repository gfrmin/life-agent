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
search; scope = text-first; **brain = Credence via `credence-pi`/`pi-mono`**; leverage existing
projects, especially **PKM**.

## Architecture

| Faculty | System | Reality / new work |
|---|---|---|
| **Memory** | **PKM** (`~/git/pkm`) | Extend with retrieval (OCR, chunks, embeddings, hybrid search, `pkm-memory` MCP). PKM already nails content-addressing + determinism. |
| **Runtime** | **pi-mono** (`~/git/pi-mono`, TS) | Agent loop + LLM abstraction (`pi-ai`) + tool registry. Tools are TS `ToolDefinition`s. **No native MCP.** |
| **Brain** | **credence-pi** (`~/git/credence/apps/credence-pi`, TS body + Julia daemon) | Pass-1: Bayesian VOI governor over each tool call → ask/proceed/block. *This is the confidence-gated autonomy.* Extend its `capabilities.bdsl`. |
| **Capabilities (hands)** | MCP servers | `pkm-memory` (new, in pkm), **Jarvis** (exists, 13 tools, `user_id 12365873`), email (`msmtp`/JMAP), calendar (CalDAV/Google MCP), chat (matrix-archiver sqlite). |
| **Application** | **`~/git/life-agent`** — a pi-mono app (composition root) + **MCP-bridge extension** (new) | Imports pi + credence-pi (TS); composes pkm/jarvis/email/calendar as MCP tools. The bridge lets credence-pi/pi use the same MCP servers Claude Code uses. Polyglot underneath, one app on top. |
| **Interfaces** | Claude Code + CLI now; pi coding-agent; later Telegram/OpenClaw (Tailscale-only) | Swappable; all point at the same MCP tools. |
| **Autonomic** | n8n + `systemd` timers (`mbsync`, `renavon-inbox-ingest` already run) | Ingestion, daily briefing, follow-ups. |

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
4. **(done)** DuckDB `fts` + `vss` hybrid query (over-fetch k·10); `pkm search` CLI; `pkm-memory` MCP (FastMCP,
   mirroring `jarvis-lite/mcp_server.py`).
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

> **Status — Phase 1 substrate is built and the live corpus is ingested + MCP-verified:**
> mail INBOX+Sent (8288 src / 37,439 chunks), documents (364 / 3,786), notes (69 / 211); a
> `pkm-memory__search` round-trip returns mail/doc/notes hits with `source_origin` provenance.
> **Next is a dogfood week** — use it, log failures, re-rank — *before* starting Phase 2 (the
> FAILURES-driven rule: build only what the failure log demands).

### Phase 2 — Brain + actions · ~2–4 weeks
- **pi MCP-bridge extension** → credence-pi/pi can call `pkm-memory` + Jarvis + email + calendar.
- Extend credence-pi `capabilities.bdsl` so the Bayesian governor gates autonomy per capability
  (e.g. ask before sending email, auto-proceed on a read-only memory search).
- Daily briefing + follow-up/deadline surfacing (n8n / `systemd` timer).

### Phase 3 — Omnichannel + autonomy · ongoing
Telegram/OpenClaw (Tailscale-only) as pi channels; draft replies, scheduling, GTD automation,
CRM/relationship nudges (`renavon`); scope expansion to photos (PhotoPrism + vision models), then the
661 GB encrypted `more/` (needs keys).

## Critical files
- **`~/git/life-agent` (this repo):** the pi-mono app (composition root) + MCP-bridge extension;
  Phase-0 tooling (`bin/ask`, `scripts/needle.sh`, `scripts/build_corpus.sh`) + `docs/kb-schema.md`;
  the configurable data layer (`scripts/data_source_registry.py`, `scripts/ingest_sources.py`,
  `config/data-sources.example.yaml`); email/calendar/chat MCP servers; agent system prompt +
  scheduling. (Knowledge + the *real* `data-sources.yaml` + `machine-config.md` live under
  `$LIFE_AGENT_KB`, outside the repo.)
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
  (double-run no-op); `pytest`/`ruff`/`mypy` green; `pkm-memory` MCP callable from Claude Code.
  **Data layer (done):** `python scripts/data_source_registry.py --report` prints the per-root census;
  `python scripts/ingest_sources.py` is idempotent (re-run = no new catalogue rows); `pkm-memory__search`
  returns mail/doc/notes hits carrying `source_origin` provenance.
- **Phase 2:** credence-pi asks before an email send, auto-proceeds on a read-only search; daily
  briefing renders.

## Resolved decisions
- **Phase-0 strategy:** Karpathy-wiki measurement **and** OCR+grep needle-finder, in parallel.
- **OCR:** standalone Tesseract producer (heb+eng).
- **Repo layout:** new umbrella application `~/git/life-agent` (working name) is the composition root
  (pi-mono spine); capabilities stay in their own repos and are composed over MCP.
