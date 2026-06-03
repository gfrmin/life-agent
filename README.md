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

Try it on the bundled **synthetic** corpus first — no real data, no API key to
build it ([full guide: `SETUP.md`](./SETUP.md)):

```bash
scripts/bootstrap-sample.sh                   # build a throwaway corpus (markdown + pandoc only)

export LIFE_AGENT_KB=$PWD/examples/.sandbox/kb
export PKM_CONFIG=$PWD/examples/.sandbox/pkm.yaml
export ANTHROPIC_API_KEY=sk-ant-...           # only needed to *ask* (synthesis)

bin/ask-live "what is my national ID number?" # cited answer over the live corpus
```

**`bin/ask-live`** is the entrypoint: it retrieves from the live pkm catalogue
(BM25, Hebrew-aware), synthesises a `[n]`-cited answer, and **verifies every
cited fact appears in its source** before showing it. Point it at your own data
by editing `config/data-sources.example.yaml` into `$LIFE_AGENT_KB` — see
[`SETUP.md`](./SETUP.md). Contributors: [`CONTRIBUTING.md`](./CONTRIBUTING.md).

> `bin/ask` + `scripts/needle.sh` are the earlier **Phase-0** wiki/grep tools
> (load a compiled wiki, no retrieval); `bin/ask-live` superseded them.

## Layout

```
SETUP.md              clone → cited answer (start here as a user)
CONTRIBUTING.md       dogfood loop, the PII guard, the two-package rules
ROADMAP.md            the approved plan (phases 0–3)
CLAUDE.md             operating manual for an agent working in this repo
GETTING_STARTED.md    concrete first-session checklist
LICENSE               AGPL-3.0-or-later
bin/
  ask-live            THE entrypoint: cited answers over the live corpus, fact-verified
  ask                 Phase-0 legacy: answer from a compiled wiki (no retrieval)
src/
  pkm/                memory faculty — content-addressed extraction + DuckDB catalogue
  life_agent/         reasoning faculty — retrieval, citation guard, owner profile
examples/
  README.md           the sample-corpus guide + the identity-guard demo
  sample-corpus/      synthetic markdown docs (Ada Lovelace) to try before your own data
config/
  pkm.example.yaml            pkm content store + extractor versions
  data-sources.example.yaml   which folders to ingest
  pii-patterns.txt.example    private denylist for the PII guard (copy to $LIFE_AGENT_KB)
scripts/
  bootstrap-sample.sh   build the sample corpus into a throwaway sandbox
  smoke-fresh-clone.sh  CI: clone → sample → cited retrieval, no key
  ask.py                the ask-live implementation (retrieve → synthesise → verify)
  ingest_sources.py     register + extract + chunk your declared data roots into pkm
  needle.sh             Phase-0 OCR+grep "find any document"
docs/
  kb-schema.md                  the knowledge-base schema (what lives under $LIFE_AGENT_KB)
  pkm/                          pkm's SPEC + phase docs
  nix-for-documents-report.md   commissioned research on the memory-core architecture
  pkm-retrieval-design.md       code-grounded design for extending pkm
  brain-design.md               pi-mono + credence-pi findings and how the app composes them
```
