# life-agent

The composition root for a **personal life-management agent** — an assistant that *remembers* your
whole digital life, *reasons* under uncertainty, *acts* across your tools, and is reachable anywhere.
It doesn't reinvent anything; it **composes systems you already run**.

> **New here (human or agent)?** Read [`CLAUDE.md`](./CLAUDE.md), then [`ROADMAP.md`](./ROADMAP.md),
> then [`GETTING_STARTED.md`](./GETTING_STARTED.md). Design background lives in [`docs/`](./docs/).

## What this is

`life-agent` is a **TypeScript application built on pi-mono** (the agent runtime) that loads the
**credence-pi** Bayesian governor (the "brain") and **composes capabilities — memory, tasks, email,
calendar — as MCP tools**. Polyglot underneath (TS + Python + Julia); one application on top.

| Faculty | System | Path | Role |
|---|---|---|---|
| **Memory** | pkm | `~/git/pkm` | content-addressed extraction + retrieval; `pkm-memory` MCP server |
| **Brain** | credence-pi | `~/git/credence/apps/credence-pi` | Bayesian VOI governor: ask / proceed / block per tool call |
| **Runtime** | pi-mono | `~/git/pi-mono` | agent loop, multi-provider LLM, tool registry (TS) |
| **Tasks** | jarvis-lite | `~/git/jarvis-lite` | GTD; MCP server (13 tools) |
| **Application + glue** | **this repo** | `~/git/life-agent` | the app, the pi **MCP-bridge** extension, small MCP servers (email/calendar/chat), scheduling, and the Phase-0 knowledge base |

The unifying trick: **every capability is an MCP server**, so the interface (Claude Code, the pi app,
later Telegram/OpenClaw) is a swappable detail.

## Status

**Phase 0 done; retrieval-substrate foundation locked.** You can ask questions about your life and get
cited answers today (`bin/ask`), and find any document including inside scans (`scripts/needle.sh`).
Underneath, pkm's cache key is hardened and migration `0004` (chunks + embeddings) has landed; the
Phase-1 retrieval spec is the measured failure log. Begin at [`GETTING_STARTED.md`](./GETTING_STARTED.md).

## Data layout — the repo is the system; your knowledge is yours

**This repo contains the system, never your data.** Your corpus, the compiled wiki, the eval set, and
the failure log are personal — they live **outside the repo**, at a path you choose:

```
LIFE_AGENT_KB     # default: $HOME/.life-agent/kb
```

`export LIFE_AGENT_KB=~/somewhere` and point it wherever you keep your stuff; the tooling reads from
there. The same separation pkm already uses (code in the repo, the content-addressed cache on your
disk). Nothing personal is ever committed. See [`docs/kb-schema.md`](./docs/kb-schema.md) for the
layout the tooling expects under `$LIFE_AGENT_KB` (`raw/`, `wiki/`, `FAILURES.md`, `eval/`).

## Usage

```bash
export LIFE_AGENT_KB=~/.life-agent/kb        # wherever your kb lives

scripts/build_corpus.sh                       # assemble $LIFE_AGENT_KB/raw from docs, notes, OCR, parsed text
scripts/needle.sh "תעודת זהות"                # find any document, incl. text inside scans (OCR'd on demand)
bin/ask "when does my passport expire?"       # answer from the wiki, with (raw/...) citations
```

`bin/ask` uses Claude (`ANTHROPIC_API_KEY` from env or gnome-keyring; model via `ASK_MODEL`).

## Layout

```
ROADMAP.md            the approved plan (phases 0–3)
CLAUDE.md             operating manual for an agent working in this repo
GETTING_STARTED.md    concrete first-session checklist
bin/
  ask                 answer a question from the wiki, with citations (Phase-0 MVP)
scripts/
  needle.sh           OCR+grep "find any document" (the repeatable "find my Israeli ID")
  build_corpus.sh     assemble $LIFE_AGENT_KB/raw from your documents, notes, OCR, and parsed text
eval/
  README.md           the eval-set schema (real, populated set lives under $LIFE_AGENT_KB)
  questions.example.yaml   illustrative/fake example
docs/
  kb-schema.md                  the knowledge-base schema (what lives under $LIFE_AGENT_KB)
  failures-template.md          how to author the Phase-1 failure log
  data-seams.md                 verified integration points (don't re-explore — read this)
  nix-for-documents-report.md   commissioned research on the memory-core architecture
  pkm-retrieval-design.md       code-grounded design for extending pkm
  brain-design.md               pi-mono + credence-pi findings and how the app composes them
```
