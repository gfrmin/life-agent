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

**Bootstrap.** Nothing is built yet. This repo currently carries the plan, the design docs, and the
Phase-0 scaffold so a fresh session can start cold. Begin at [`GETTING_STARTED.md`](./GETTING_STARTED.md).

## Layout

```
ROADMAP.md            the approved plan (phases 0–3)
CLAUDE.md             operating manual for an agent working in this repo
GETTING_STARTED.md    concrete first-session checklist
docs/
  nix-for-documents-report.md   commissioned research on the memory-core architecture
  data-seams.md                 verified integration points (don't re-explore — read this)
  pkm-retrieval-design.md       code-grounded design for extending pkm
  brain-design.md               pi-mono + credence-pi findings and how the app composes them
kb/                   Phase-0 Karpathy-style LLM wiki (raw/ + wiki/ + CLAUDE.md)
scripts/
  needle.sh           OCR+grep "find any document" (the repeatable "find my Israeli ID")
  build_corpus.sh     assemble kb/raw from your documents, notes, OCR, and parsed text
```
