# Personal Life-Management Agent — Roadmap

*This is the plan and status. The principles it executes live in
[`PRINCIPLES.md`](./PRINCIPLES.md); the agent operating manual is [`CLAUDE.md`](./CLAUDE.md).*

## Context

The kernel (PRINCIPLES §1): a knowledge base of trustworthy transformation DAGs (pkm), and a
life agent making rational, utility-maximising decisions over it. The seed task ("find my
Israeli ID across all my data") generalises to "ask/find anything about my life, with
citations" — the first win (§14). The work is integration + a retrieval layer + wiring, not
greenfield (§4): ~90% of the building blocks already exist in the owner's repos.

## Architecture — faculties over language-neutral seams

Faculties compose over MCP / HTTP / CLI seams (PRINCIPLES §5); the table below is the **status
view** — what each faculty is and where it stands.

| Faculty | System / language | Status |
|---|---|---|
| **Memory** — recall + retrieval | **PKM** (`src/pkm`, Python) + **`life_agent`** (this repo, Python) | **Live.** PKM: content-addressed extraction + DuckDB `fts`/`vss` + **composable transforms** (chained, cited perspectives — SPEC §18.7). `life_agent` adds the retrieval/synthesis read path (`scripts/ask.py`, dogfooded via `bin/ask-live`). |
| **Brain** — beliefs under uncertainty; value-of-information → ask/proceed/block | **credence** (`../credence`, Julia; the skin's JSON-RPC-over-stdio seam) | **Adopted, being wired (Phase 1.6 / Ask v0):** [`docs/bayesian-foundations.md`](./docs/bayesian-foundations.md) — answers become claim sets with posteriors; responses are EU decisions through `src/life_agent/core/brain.py` (slice 1). The VOI governor stays last. |
| **Hands** — capabilities/actions | **GTD** (`life_agent.tasks`, event-sourced) reached via **`life_agent.reach`** (Telegram transport + persona); email (`msmtp`/JMAP), calendar (CalDAV/Google), chat (matrix) | GTD live, ledger-as-truth (PRINCIPLES §7); **email→GTD shipped (M2)** — the `action_items` transform (local model, grounded quotes) **auto-files** cited tasks to the inbox; you triage in Telegram. Rest not wired. |
| **Goals / Utility** — what the owner values | *(new, unbuilt)* | **The hardest missing piece.** EU-maximisation presupposes it; owed a design before any autonomous *action* (PRINCIPLES §3). |
| **Spine** — the agent loop + routing | **TBD — open decision** | Deferred to Phase 2 (PRINCIPLES §15). Candidates: pi-mono (TS), a Python loop, or Claude Code as an interim loop. |

The earlier `pkm-memory` MCP server was built then **torn down** (operational — a leaked
process — not an architecture verdict); `src/pkm/mcp_server.py` stays dormant-by-design (§5).
Today the memory read path is dogfooded directly via `bin/ask-live`, and Claude Code itself is
the only (manual) reasoning loop. **Autonomic:** n8n + `systemd` timers (`mbsync`,
`renavon-inbox-ingest`, email→GTD) already run ingestion.

## What the report changes (build-vs-adopt verdicts)

From the commissioned research ([`docs/nix-for-documents-report.md`](./docs/nix-for-documents-report.md))
— a candidate input, not a mandate (PRINCIPLES §9); these are the verdicts the plan *adopted*:
- **Determinism:** PKM already correct (semantic, not bitwise; cache keyed on inputs; SPEC §7.1). No change.
- **Orchestration:** keep PKM bespoke — **do NOT adopt Hamilton now** (over-engineering until multi-step
  DAGs; `artifact_lineage` is already Hamilton-ready; revisit Phase 3).
- **Vectors:** DuckDB `vss`+`fts` (endorsed). Mind: filtered top-k is broken → **over-fetch k·10 then
  filter**; `SET hnsw_enable_experimental_persistence=true`; back up `.duckdb` (borg already runs).
- **Prompts:** DSPy **offline only** (freeze tuned prompts in YAML; never at runtime — would break cache).
- **Chunking/ingestion:** optional LlamaIndex `IngestionPipeline` as a wrapped Phase-1 chunker, or hand-roll.
- **Cache-key hardening (minor, Phase 1):** add `output_schema_hash`, inference-engine/SDK version, and
  split `prompt_template_hash` from filled bindings. Not blocking.
- **OCR:** standalone **Tesseract producer** (`tesseract -l heb+eng`, ~1-file clone of the pandoc
  producer, no new Python dep) — chosen for speed and predictable Hebrew over the heavier Docling path.

## Roadmap (each phase usable on its own)

### Phase 0 — Measure + needle-find · **done and retired**
The compiled-wiki path was built, measured against retrieval in a blind pre-registered
comparison ([`SPEC-comparison.md`](./SPEC-comparison.md) is the frozen record), and **retired**
(PRINCIPLES §14): compiling a summary of everything does not scale and hallucinates. Its
deliverable survives as the dogfood discipline — `$LIFE_AGENT_KB/FAILURES.md` is the spec. The
OCR+grep needle-finder (`scripts/needle.sh`) survives as a standalone tool.

### Phase 1 — PKM retrieval substrate · **substrate complete; corpus live**
1. **(done)** Bump PKM **SPEC → v0.3.0** authorising retrieval/embeddings/extensions/local MCP server (governance-first).
2. **(done)** **`TesseractProducer`** (`src/pkm/producers/tesseract.py`, heb+eng) wired into `routing.py` +
   `extract.py` + `cli.py`; migration `0004` (`chunks`, `embeddings FLOAT[768]`, `source_origin`).
3. **(done)** Local embeddings via Ollama `nomic-embed-text` (stdlib `urllib`, no new dep).
4. **(done)** DuckDB `fts` + `vss` hybrid query (over-fetch k·10); `pkm search` CLI; `pkm-memory` MCP
   (FastMCP) — **later retired**; retrieval now via `bin/ask-live`.
5. **(done) Source adapters — a declarative registry, not ad-hoc scripts.** Sources are declared
   in a **`data-sources.yaml`** registry (real one under `$LIFE_AGENT_KB`, fake schema in
   `config/data-sources.example.yaml`) and enumerated from **plocate**. Two pieces:
   - `scripts/data_source_registry.py` — loader + plocate census + `--report` (classifies every file
     by pkm producer coverage); deferred roots (photos) counted, never ingested.
   - `scripts/ingest_sources.py` — promote step: `filetree` + `maildir` adapters → merge into pkm
     `sources.yaml` (dedupe by path, union tags) → `pkm ingest`.
   Adding **chat** (matrix-archiver SQLite) or **contacts** (Fastmail CardDAV) is *a new `kind`
   adapter + a registry entry*, deferred to dogfood evidence / Phase 2.

> **Status — substrate built, corpus live, dogfooded via `bin/ask-live`:** the live catalogue
> (NVMe; ~13k sources / ~400k chunks incl. the Downloads root) answers cited questions end-to-end.
> Dogfooding surfaced a real retrieval miss (query-expansion, shipped) and a synthesis miss
> (own-corpus attribution, fixed) — exactly the FAILURES-driven signal the loop is for (§9).

### Phase 1.5 — Mature memory · **superseded 2026-06-11**
Was dogfood-gated ("build only what FAILURES.md demands"); superseded by the adopted
framework below (owner directive; PRINCIPLES §9 as amended). Its open levers (OCR the
image-PDFs; `EXPAND_SYSTEM` ranking nudges; new source-`kind` adapters) remain valid
backlog items, promoted by evidence as before.

### Phase 1.6 — The derivation framework · **ACTIVE** (re-scoped 2026-06-12)
The adopted system design ([`docs/system-design.md`](./docs/system-design.md)) executed
continuously, eval-gated (engine design §11); engine D0–D2 and the GTD ledger's knowledge
projection are landed. On 2026-06-12 the owner adopted the **Bayesian foundations**
([`docs/bayesian-foundations.md`](./docs/bayesian-foundations.md)): Ask is re-derived as
inference — answers are claim sets with posteriors, responses are EU decisions,
calibration is measured — and the old D3/D4 are re-scoped as question families of
Bayesian Ask rather than deterministic pipelines. Remaining program, in dependency order
(the doc's §12 roadmap governs; gates per its §8):
1. **(done)** The act ledger becomes knowledge — currency rule (pkm SPEC §15.4),
   `tasks/knowledge.py`, demand-led refresh in the ask path.
2. **(done)** D2 — subject — `doc_subject` closed-enum transform + executor-side
   owner-profile filter (profile never enters pkm).
3. **Ask v0** — slice 0 **(done)**: outcomes log + scoring-rule eval (the evidence
   stream cannot be backfilled); slice 1 **(done)**: the credence seam
   (`src/life_agent/core/brain.py` over the skin's JSON-RPC-over-stdio; live Julia
   smoke green); slice 2: the lookup family + the **utility posterior v0** + the
   decision log (utility is a learned belief about the owner — foundations §4.4/§10 as
   amended 2026-06-12: one utility, the agent has none of its own); slice 3: narrative
   subsumption.
4. **The aggregate family** (subsumes D3): recall term + completeness priors,
   missing-mass posterior, dedup-as-inference — the spending question answered as a
   posterior with both coverage readouts.
5. **The thread family** (subsumes D4): `assemble` SPEC amendment, email `_VERSION` bump
   (budget the corpus-wide reclassification), `thread_state` instrument, membership
   recall ("awaiting reply?").

### Phase 2 — Goals/utility model + first agent loop (read-only) · future
- Design the **goals/utility representation** (the unbuilt faculty) — how the agent learns and
  stores what the owner values. Owed before any write-action (PRINCIPLES §3).
- Build the **first real agent loop over read-only capabilities** (daily briefing, "what needs
  attention"), reasoning over memory, gated by **credence** (VOI ask/proceed/block — safe because
  nothing is destructive). **The spine is chosen here** (see Open decisions).

### Phase 3 — Action layer + autonomy · future
Write-capabilities (GTD tasks, email drafts, calendar) under credence ask/proceed/block;
omnichannel (Telegram/Matrix, Tailscale-only); scope expansion to photos (PhotoPrism + vision),
then the 661 GB encrypted `more/` (needs keys).

### Open decisions (decide when the phase arrives, not before)
PRINCIPLES §15 is the canonical list, with criteria:
- **The spine** (Phase 2): pi-mono vs a Python agent loop vs Claude Code as an interim loop. One
  candidate composition is sketched in [`docs/candidates/brain-design.md`](./docs/candidates/brain-design.md).
- **The goals/utility representation** (Phase 2).
- **The CRM rebuild** — #1/#2/#5/#6 resolved by the adopted framework (recorded in
  [`docs/crm-architecture-decisions.md`](./docs/crm-architecture-decisions.md)); #3
  (mutable notes) and #4 (alias dedup) remain open.

## Critical files
- **`.` (this repo):** `src/life_agent/core/` (shared infra: LLM calls, secrets, config, source
  rendering), `scripts/ask.py` (retrieval + synthesis, run via `bin/ask-live`), the configurable
  data layer (`scripts/data_source_registry.py`, `scripts/ingest_sources.py`,
  `config/data-sources.example.yaml`), and the frozen blind-comparison harness
  (`scripts/comparison/`). (Knowledge + the *real* `data-sources.yaml` live under `$LIFE_AGENT_KB`.)
- **GTD (act layer):** `src/life_agent/tasks/{events,store,commands,project}.py`.
- **Reach:** `src/life_agent/reach/{telegram,jarvis,digest}.py`.
- **pkm:** `docs/pkm/SPEC.md` + `docs/pkm/SPEC-PRINCIPLES.md` (governance);
  `src/pkm/{routing,extract,cli}.py` (producer wiring ladders); `src/pkm/transform.py` + transforms.
- **credence-pi (candidate brain):** `bdsl/capabilities.bdsl`, `extension/src/index.ts`, `daemon/server.jl`.

## Verification
- **Phase 1:** `uv run pkm search "תעודת זהות"` returns the ID with provenance; idempotent re-ingest
  (double-run no-op); `pytest`/`ruff`/`mypy` green; `bin/ask-live` returns cited answers from the corpus.
  **Data layer:** `python scripts/data_source_registry.py --report` prints the per-root census;
  `python scripts/ingest_sources.py` is idempotent (re-run = no new catalogue rows).
- **Phase 1.5:** a `FAILURES.md`-traced change moves a real dogfood miss (e.g. an image-PDF becomes
  searchable after OCR routing); idempotent re-ingest; no FTS-ranking regressions.
- **Phase 2:** the read-only loop renders a daily briefing; credence asks/auto-proceeds appropriately
  on read-only capabilities; a goals/utility representation exists and is consulted.
