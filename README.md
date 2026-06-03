# life-agent

Ask anything about your own life and get an answer that **cites the document each fact came from** —
with **no hallucination**. life-agent remembers your digital life, retrieves the records that bear on
your question, and **verifies every cited fact actually appears in its source** before showing you
the answer. Facts are grounded in your own documents, not a model's memory.

> **Use it →** [`SETUP.md`](./SETUP.md) (clone to a cited answer in minutes, on a bundled synthetic
> corpus first — no real data, no API key to build it).
> **Contribute →** [`CONTRIBUTING.md`](./CONTRIBUTING.md).
> **Understand the design →** [`CLAUDE.md`](./CLAUDE.md) · [`ROADMAP.md`](./ROADMAP.md) · [`docs/`](./docs/).

## Quickstart

Requires [`uv`](https://docs.astral.sh/uv/), `pandoc`, and `git`. Try it on the bundled **synthetic**
corpus (the fictional Ada Lovelace) before pointing it at your own data:

```bash
git clone https://github.com/gfrmin/life-agent && cd life-agent
scripts/bootstrap-sample.sh                     # builds a throwaway corpus — markdown + pandoc only, no API key

export LIFE_AGENT_KB=$PWD/examples/.sandbox/kb
export PKM_CONFIG=$PWD/examples/.sandbox/pkm.yaml
export ANTHROPIC_API_KEY=sk-ant-...             # only needed to *ask* (answer synthesis), not to build

bin/ask-live "what is my national ID number?"   # cited answer over the corpus you just built
bin/ask-live "when does my passport expire?"
```

`bin/ask-live` is **the** entrypoint: it retrieves from a DuckDB catalogue (BM25, Hebrew-aware),
synthesises a `[n]`-cited answer, and runs the citation guard before printing. Full walkthrough,
prerequisites, and troubleshooting in [`SETUP.md`](./SETUP.md); more sample questions and the
identity-guard demo in [`examples/README.md`](./examples/README.md).

## Why the answers are trustworthy

The promise is **cited, no-hallucination** answers, and it is structural rather than aspirational:

- **Verbatim facts are gated.** Before an answer is shown, a deterministic guard
  (`scripts/citation_guard.py`) checks that every value-bearing cited fact — IDs, numbers, proper
  nouns — actually appears in the source it cites. Anything that doesn't is flagged `⚠ unverified`,
  not presented as true.
- **Weak retrieval abstains.** If nothing in your corpus is a strong enough match, it says so
  instead of guessing (tunable via `LIFE_AGENT_SCORE_FLOOR` / `LIFE_AGENT_MIN_HITS`).
- **Identity is pinned.** An owner profile (`bin/ask-live --tell "…"`) is the lens for who "I" is, so
  a relative's or co-signer's document is never reported as yours.

Answers are grounded in [`pkm`](./src/pkm/)'s content-addressed, source-cited extractions — *not* a
compiled summary. (The "compile a wiki from everything" approach is deliberately rejected: it does
not scale and it hallucinates.) What is **not** guaranteed: facts pkm extracted wrong upstream (e.g.
OCR garble) and the prose faithfulness of paraphrase — that is *measured* (`scripts/run_eval.py
--synthesis`), not hard-gated.

## Use it on your own data

Your data never enters the repo. Copy `config/data-sources.example.yaml` to `$LIFE_AGENT_KB/config/`,
point its roots at your folders, then `migrate → ingest → extract → chunk → rebuild-index` (one
script: `scripts/ingest_sources.py --extract --chunk`). Teach it who you are with `bin/ask-live
--tell "My name is …"`. Step-by-step in [`SETUP.md`](./SETUP.md#3-point-it-at-your-own-data).

## What's live vs the vision

The north star is an agent that **maximises the owner's expected utility** — remembers everything,
reasons under uncertainty (the *brain*), acts across tools, is proactive. The design is **four
faculties + a spine**, each in the language that serves it, integrated over language-neutral seams
(MCP / HTTP / CLI) — polyglot by design, not one app in one language.

**What exists today is the Memory faculty, in Python:** the retrieval + synthesis read path
(`src/life_agent/`, run via `bin/ask-live`) over [`pkm`](./src/pkm/)'s DuckDB catalogue. The other
faculties are future work, and the **agent-loop spine is an open decision** (see [`ROADMAP.md`](./ROADMAP.md)).

| Faculty | System | Status |
|---|---|---|
| **Memory** | pkm + `life_agent` | **Live** — content-addressed extraction + DuckDB `fts`/`vss`; this repo adds the retrieval/synthesis read path |
| **Brain** | credence | Not wired — Bayesian value-of-information governor: ask / proceed / block (Julia) |
| **Hands** | jarvis-lite, email, calendar, chat | Not wired — Jarvis is a 13-tool MCP server; others TBD |
| **Goals / Utility** | *(new)* | Unbuilt — what the owner values; owed before autonomous action |
| **Spine** | **TBD** | Open decision: pi-mono (TS) vs a Python loop vs Claude Code as interim |

The unifying idea is the **seam**: every capability is reachable over a stable, language-neutral
contract, so the spine and the interface (a CLI today, later Telegram/Matrix) stay swappable.

## Your data stays yours

**This repo contains the system, never your data.** Your corpus, the eval set, and the failure log
are personal — they live **outside the repo**, at a path you choose:

```
LIFE_AGENT_KB     # default: $HOME/.life-agent/kb
```

`export LIFE_AGENT_KB=/path/to/kb` and point it wherever you keep your stuff; the tooling reads from
there. (Same separation pkm already uses: code in the repo, the content-addressed cache on your
disk.) Nothing personal is ever committed — a PII guard in `.githooks/` enforces it on every commit
and push. See [`docs/kb-schema.md`](./docs/kb-schema.md) for the expected layout under
`$LIFE_AGENT_KB`.

## Repository layout

```
SETUP.md              clone → cited answer (start here as a user)
CONTRIBUTING.md       dogfood loop, the PII guard, the two-package rules
ROADMAP.md            the plan (phases 0–3)
CLAUDE.md             operating manual for an agent working in this repo
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
docs/
  kb-schema.md                  the knowledge-base schema (what lives under $LIFE_AGENT_KB)
  pkm/                          pkm's SPEC + phase docs
  nix-for-documents-report.md   commissioned research on the memory-core architecture
```

## License

[AGPL-3.0-or-later](./LICENSE). `pkm` (vendored as `src/pkm`) is AGPL too, so the whole repository is
AGPL: you may use, modify, and redistribute it, but if you run a modified version as a network
service you must offer its users the corresponding source.
