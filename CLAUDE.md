# CLAUDE.md — operating manual for `life-agent`

You are an agent working in `.`, the composition root of a personal life-management
assistant. This file is your orientation; **read [`ROADMAP.md`](./ROADMAP.md) for the plan and
[`GETTING_STARTED.md`](./GETTING_STARTED.md) for the immediate tasks.** The owner is a strong
engineer (builds Julia DSLs, TS, Python data platforms) — be precise, terse, and don't over-build.

## Mission

An assistant that **remembers** everything the owner has seen/said/filed, **reasons** under
uncertainty about what matters, **acts** across their tools, is reachable anywhere, and is proactive
— privacy is *not* the local-vs-cloud axis (choose by cost/latency/capability). The seed task —
*"find my Israeli ID across all my data"* — generalises to *"ask/find anything about my life, with
citations."*

## Prime directive: compose, don't rebuild

~90% of the building blocks already exist as the owner's own projects. Your job is **integration + a
retrieval layer + wiring**, not greenfield. Before writing anything new, check whether one of the
repos below already does it.

## Architecture

> **Reality check (2026-06): the diagram below is the *aspiration*, not the current state.**
> What exists today is the **memory faculty in Python**: a `life_agent` package + `scripts/ask.py`
> retrieval/synthesis layer over pkm's DuckDB catalogue, dogfooded via `bin/ask-live`. There is **no
> pi-mono app, no credence wiring, and no live MCP server** (the `pkm-memory` MCP server was built
> then torn down). The owner's steer: **mature memory first**; treat the **agent-loop spine as an
> open decision** (pi-mono vs a Python loop vs Claude Code as interim — *not* pre-committed); think
> **polyglot — each faculty in its best language, integrated over language-neutral seams (MCP / HTTP
> / CLI)**, rather than one TS app. See `ROADMAP.md` → Architecture + Open decisions. The text below
> describes where this is *heading* and the building blocks to reuse.
>
> **Update (2026-06): the GTD is now the agent's own act layer.** jarvis-lite was absorbed, then
> **dissolved** — there is no separate GTD faculty. The GTD (lists, tasks, the event ledger, the command
> logic) lives in **`life_agent.tasks`** (event-sourced); Telegram is a dumb transport the brain drives,
> in **`life_agent.reach`** ("Jarvis" is just the persona). Two in-tree Python packages — `pkm` (memory)
> and `life_agent` (reason + act + reach) — in a **derive → project → reach** shape:
> - **derive (pkm):** sources → primary artifacts → **transforms** → cited, cached, idempotent artifacts.
>   Transforms **compose** — `input.producer` may name another transform (SPEC §18.7) — so behaviour is
>   built from small, generic, chained, *independently-auditable* steps, never one mega-transform.
> - **project (life_agent):** a thin immutable→mutable bridge (`src/life_agent/tasks/project.py`) — read
>   terminal `action_items` artifacts, file each **once** into the GTD inbox with a `[src:email <id>]` citation.
>   "Already handled" is `fold` of an **append-only event ledger** (`src/life_agent/tasks/events.py`):
>   `Asserted`/`Disposed`/`Superseded`, keyed on a content+grounding **assertion identity** (not
>   `message_id#index`) — the task set is a projection of the ledger, and a cleared task never resurrects.
>   See `docs/act-layer-events.md` and the `reconciliation-as-transformation` design.
> - **reach (`life_agent.reach`):** the Telegram channel (`telegram.py` transport) + the loop/NLU/persona
>   (`jarvis.py`) + `digest.py`. Human commands (add/complete/delete/move) are **first-class events** into
>   the same ledger; the read-model (SQLite) is a fold of it — no capture/diff.
>
> So **email→GTD** is just the `action_items` transform (local Ollama, grounded quotes) + a thin projector:
> new mail is **auto-filed** to the inbox — the grounding gate is the safety, you triage in Telegram — run
> off a `systemd --user` timer, *not* a hand-run CLI (`bin/mail-to-tasks` is the timer/debug entrypoint).

`life-agent` is intended to be a **pi-mono (TypeScript) application** — the spine. It **imports**
`pi-agent-core` and loads the **credence-pi** governor (same language); it **composes** the
cross-language capabilities as **MCP tools** via a new **MCP-bridge extension**. A small **Python
side** of this repo imports `pkm` directly for batch ingestion.

```
            ┌────────────────────── life-agent (this repo, TS app) ──────────────────────┐
            │  pi-mono runtime (agent loop, pi-ai LLM)                                    │
            │     └─ credence-pi governor extension  ── ask / proceed / block (Bayesian)  │
            │     └─ MCP-bridge extension ── connects to the MCP servers below            │
            └───────────────┬───────────────┬───────────────┬───────────────┬────────────┘
                            │               │               │               │
                      pkm-memory        jarvis           email           calendar     ← MCP servers
                      (pkm, new)      (src/jarvis)     (msmtp/JMAP)   (CalDAV/Google)
                            │
                   PKM content-addressed cache + DuckDB catalogue (the memory)
```

Claude Code talks to the *same* MCP servers directly — that's why MCP is the integration boundary.

## The component repos — what to reuse, and the key files

### `src/pkm` (now in-tree) — the memory core (Python, uv, DuckDB)
Content-addressed extraction cache + DuckDB catalogue + format producers + Phase-2 Anthropic entity
extraction. Retrieval is the part we add. **It already nails content-addressing and a *semantic*
(not bitwise) determinism contract — don't "fix" that.**
- **Producer protocol:** `src/pkm/producer.py` (`Producer` Protocol, `ProducerResult`).
- **Clone this for the OCR producer:** `src/pkm/producers/pandoc.py` (subprocess + version parse, never raises).
- **Wiring ladders (edit to add a producer):** `src/pkm/routing.py`, `src/pkm/extract.py`
  (`_PRODUCER_NAMES`, `_needed_producer_names`, `_ensure_constructed`), `src/pkm/cli.py`
  (`--producer` choices, `_SUBCOMMANDS`).
- **Catalogue + migrations:** `src/pkm/catalogue.py`, `src/pkm/migrations/0001..0003_*.py` (hash-verified;
  never edit a landed migration — add `0004`).
- **Cache key:** `src/pkm/hashing.py` (`compute_cache_key`, `compute_model_identity_hash`).
- **Transforms:** `src/pkm/transform.py`, `src/pkm/transforms/{entity_extraction,action_items}.py`;
  they **chain** (`_find_eligible_sources` resolves `input.producer` over `artifacts`, so a transform
  may consume another transform's output — SPEC §18.7). Live model calls gated behind markers
  (`-m 'not llm and not system'` is the default; both are non-deterministic, opt-in only).
- **Docling (OCR-capable, but no image extensions yet):** `src/pkm/producers/docling.py`.
- **Tests:** `tests/conftest.py` (`tmp_root`, `migrated_root`); Stage-A hermetic pattern; live calls
  gated behind markers and skipped by default (`addopts = "-m 'not llm'"`).
- **Governance — READ FIRST:** `SPEC.md` (semantic determinism §7.1; out-of-scope §12) and the repo's
  own `CLAUDE.md`. Rules: **SPEC-first** (amend the SPEC before code), **TDD** (test before impl),
  **every cache op proven idempotent by a double-run**, and **ask before adding a dependency / a new
  top-level directory / a new file format.** Adding retrieval requires bumping **SPEC → v0.3.0**.
- Verified: **DuckDB 1.5.2** here loads both `fts` and `vss` (HNSW cosine + `array_cosine_distance`).

### `../credence/apps/credence-pi` — the brain (TS body + Julia daemon)
A **Bayesian governor**, *not* a task-doer: a pi extension (`extension/src/index.ts`) hooks each
tool call, ships features over HTTP `POST /sensor` to a Julia daemon (`daemon/server.jl`) holding a
posterior (BDSL programs in `bdsl/{capabilities,features,prior,kernel,decide}.bdsl`), which returns
**ask / proceed / block** via `SSE /signals` (value-of-information driven). Pass-1 works end-to-end.
- **This is the confidence-gated autonomy.** New capabilities get governed by declaring them and
  extending `bdsl/capabilities.bdsl`.
- Design rule from its SPEC: *"the brain does not invent tentacles; it selects from those the body
  declares."* So **register capabilities body-side (pi tools); keep the brain pure.**
- `credence-proxy` (`../credence/apps/python/credence_router`, OpenAI-compatible LLM router) and
  `credence_agents` (`../credence/apps/python/credence_agents`) are separate and not yet wired in.

### `../pi-mono` — the runtime (TypeScript, pnpm, Node ≥20)
- `packages/agent/src/types.ts` — `AgentTool` (the runtime tool type).
- `packages/coding-agent/src/core/tools/index.ts` — built-in tool registry (`createAllTools`).
- `packages/coding-agent/src/core/extensions/types.ts` — `ToolDefinition` + `registerTool` (how
  extensions add tools); `loader.ts` loads extensions.
- **No native MCP** (by design). To use MCP servers, **write an extension that is an MCP client and
  wraps each MCP tool as a `ToolDefinition`** — this is the MCP-bridge we build in this repo.

### `life_agent.tasks` — the GTD, event-sourced (Python, SQLite, the act layer)
The GTD *is* the agent's act layer (the former standalone `jarvis` package is dissolved). One append-only
**event ledger** is the source of truth; the SQLite is a rebuildable projection. See `docs/act-layer-events.md`.
- **Ledger:** `src/life_agent/tasks/events.py` — `Asserted`/`Disposed`/`Superseded`/`Amended`, keyed on a
  content+grounding **assertion identity** (human commands mint a unique identity; email-derived use content).
- **Read-model:** `src/life_agent/tasks/store.py` — the `tasks` table (lists inbox/next/scheduled/someday;
  `@tags`; `is_today`; due); `apply(event)` folds one event, `rebuild(events)` replays the ledger. DB path
  `JARVIS_DB_PATH` (default `$LIFE_AGENT_KB/jarvis/jarvis.db`, outside the repo) — kept for continuity.
- **Commands (write seam):** `src/life_agent/tasks/commands.py` → `commands.add/complete/delete/move/...`
  (append event(s) → fold the read-model → return the reply). The email projector (`project.py`) is just
  another producer of `Asserted(origin="email")` events.

### `life_agent.reach` — the Telegram channel + persona (transport only, no truth)
- **Transport:** `src/life_agent/reach/telegram.py` (poll/send; knows only Telegram).
- **Loop + NLU + persona:** `src/life_agent/reach/jarvis.py` — Ollama parses a message → intent → routes to
  `tasks.commands`/`tasks.store`. Runs as `systemd --user jarvis.service` via `python -m life_agent.reach.jarvis`.
- **Digest:** `src/life_agent/reach/digest.py` (`python -m life_agent.reach.digest`).
- **Owner's Telegram id:** `JARVIS_USER_ID` (env / gnome-keyring) — never hard-code it.

## Conventions & constraints
- **Functional style preferred.** Small, single-purpose units with clear interfaces.
- **MCP everywhere** — a capability is an MCP server, so interfaces stay swappable.
- **Provenance on every answer** — cite source path / date / account.
- **Local embeddings + cloud reasoning** by default: embeddings via local Ollama `nomic-embed-text`
  (free, GPU); heavy reasoning via Claude. This is an engineering choice, *not* privacy.
- **Tailscale-only** for any networked surface; never expose publicly (and never use
  `tailscale serve`/funnel — bind directly to the Tailscale IP).
- **In `pkm`:** obey its SPEC-first + TDD + idempotency rules above.
- **Secrets** live in **gnome-keyring**, never in `.env`. Read one with
  `secret-tool lookup service env key VARNAME`; load all into a shell with `load_secrets_from_keyring`.
  Fastmail tokens: keyring `service=carddav` / `service=jmap`; sending email: `~/.msmtprc` (passwordeval).
- **Tooling preferences:** `rclone` (not s3cmd) for R2; `gh` (not a GitHub MCP) for GitHub; don't pipe
  long-running commands through `head`/`tail` (use native verbosity).
- **Commit/push only when the owner asks.** This repo was scaffolded without an initial commit.

## Resolved decisions (do not relitigate without reason)
- **First win:** ask-anything search. **Scope:** text-first (skip 1.2M photos + the 661 GB encrypted
  `more/` for v1). **Brain:** credence (the Bayesian governor). **Memory:** extend `pkm`. (Agent-loop
  *spine* is an open decision — not pre-committed to pi-mono.)
- **Phase-0 strategy:** do the Karpathy-wiki measurement **and** the OCR+grep needle-finder in parallel.
- **OCR:** standalone **Tesseract producer** in pkm (`tesseract -l heb+eng`), not extending Docling —
  chosen for speed and predictable Hebrew.
- **Repo layout:** this umbrella app is the composition root; capabilities stay in their own repos,
  composed over MCP.

## Build-vs-adopt verdicts (from the research report — see `docs/nix-for-documents-report.md`)
- **Do NOT adopt Hamilton now** — pkm's bespoke content-addressed cache is justified until multi-step
  DAGs exist (revisit Phase 3; `artifact_lineage` is already Hamilton-ready).
- **DuckDB `vss` + `fts`** is the right vector/keyword store (no Qdrant/Chroma/pgvector). Gotchas:
  filtered top-k is broken (HNSW runs before `WHERE`) → **over-fetch k·10 then filter**;
  `SET hnsw_enable_experimental_persistence=true`; back up the `.duckdb` (borg already runs).
- **DSPy** = offline prompt tuning only; **freeze tuned prompts in YAML** (runtime MIPRO would break cache stability).
- **Determinism:** `temperature=0` is *not* bitwise-deterministic on Ollama; rely on memoisation
  (a content-addressed cache hit is deterministic regardless), pin model snapshots, never `latest`.
- **Karpathy wiki** is a warm-cache + measurement layer, not a competitor to retrieval.

## Environment (Arch Linux, this machine)
- **GPU:** RTX 4060 (8 GB). **Ollama** running with: `qwen2.5:7b-instruct`, `qwen3.5:9b`,
  `llama3.1`, **`nomic-embed-text`** (768-dim embeddings), 2 vision models. API at `localhost:11434`.
- **OCR/docs:** `tesseract 5.5.2` (langs incl. **`heb`** + `eng`), `pdftotext`, `exiftool`,
  ImageMagick 7, ghostscript, libreoffice.
- **Search:** `rg 15.1`, **`rga 0.10.10`** (ripgrep-all, searches inside PDFs), `sqlite3 3.53` (FTS5),
  `pandoc`, `jq`. (No `fd`/`fzf`/`recoll`.) **DuckDB 1.5.2.**
- **Langs:** Python 3.14 + `uv`; Node 26 + `pnpm`/`bun`; Julia (for credence).
- **Running services:** `jarvis.service`, PhotoPrism, Tuwunel + mautrix bridges + `matrix-archiver`,
  n8n, miniflux, invidious; timers `mbsync` (mail) + `renavon-inbox-ingest`; bi-hourly borg backup.

## Start here
1. Read [`ROADMAP.md`](./ROADMAP.md) (phases) and `$LIFE_AGENT_KB/docs/data-seams.md` (the verified,
   machine-specific data map — out of tree; saves you a re-exploration).
2. Follow [`GETTING_STARTED.md`](./GETTING_STARTED.md). Current phase: **Phase 0** (measure + needle-find).
