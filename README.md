# life-agent

The composition root for a **personal life-management agent** — an assistant that *remembers* your
whole digital life, *reasons* under uncertainty, *acts* across your tools, and is reachable anywhere.
It doesn't reinvent anything; it **composes systems you already run**.

> **New here (human or agent)?** Read [`CLAUDE.md`](./CLAUDE.md), then [`ROADMAP.md`](./ROADMAP.md),
> then [`GETTING_STARTED.md`](./GETTING_STARTED.md). Design background lives in [`docs/`](./docs/).

## What this is

The north star is an agent that **maximises the owner's expected utility** — remembers everything,
reasons under uncertainty (the *brain*), acts across tools, is proactive. The design is **four
faculties + a spine**, each in the language that serves it, integrated over **language-neutral seams
(MCP / HTTP / CLI)** — polyglot by design, not one app in one language.

**What exists today is the Memory faculty, in Python:** a retrieval + synthesis layer over pkm's
DuckDB catalogue (`src/life_agent/` + `scripts/ask.py`, run via `bin/ask-live`). The other faculties
are future work, and the **agent-loop spine is an open decision** (see `ROADMAP.md`).

| Faculty | System | Path | Status |
|---|---|---|---|
| **Memory** | pkm + `life_agent` | `../pkm`, `.` | **Live** — content-addressed extraction + DuckDB `fts`/`vss`; this repo adds the retrieval/synthesis read path |
| **Brain** | credence | `../credence/apps/credence-pi` | Not wired — Bayesian VOI governor: ask / proceed / block (Julia) |
| **Hands** | jarvis-lite, email, calendar, chat | `../jarvis-lite`, … | Not wired — Jarvis is a 13-tool MCP server; others TBD |
| **Goals / Utility** | *(new)* | — | Unbuilt — what the owner values; owed before autonomous action |
| **Spine** | **TBD** | — | Open decision: pi-mono (TS) vs a Python loop vs Claude Code as interim |

The unifying trick is the **seam**: every capability is reachable over a stable, language-neutral
contract, so the spine and the interface (Claude Code today, later Telegram/Matrix) are swappable.
MCP is endorsed as a seam (an earlier `pkm-memory` MCP server was built then retired).

## Status

**Phase 1 memory substrate done; corpus live; active phase = mature memory (Phase 1.5).** Ask
questions about your life and get cited answers over the whole live corpus today via **`bin/ask-live`**
(`bin/ask` + `scripts/needle.sh` are the earlier Phase-0 wiki/grep tools). Underneath: pkm's
content-addressed extraction + a DuckDB `fts`/`vss` catalogue (~13k sources / ~400k chunks). The work
now is dogfood-driven: use it, log misses to `FAILURES.md`, build only what they demand. Begin at
[`GETTING_STARTED.md`](./GETTING_STARTED.md).

## Data layout — the repo is the system; your knowledge is yours

**This repo contains the system, never your data.** Your corpus, the compiled wiki, the eval set, and
the failure log are personal — they live **outside the repo**, at a path you choose:

```
LIFE_AGENT_KB     # default: $HOME/.life-agent/kb
```

`export LIFE_AGENT_KB=/path/to/kb` and point it wherever you keep your stuff; the tooling reads from
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
  nix-for-documents-report.md   commissioned research on the memory-core architecture
  pkm-retrieval-design.md       code-grounded design for extending pkm
  brain-design.md               pi-mono + credence-pi findings and how the app composes them
```
