# life-agent

Ask anything about your own life and get an answer that **cites the document each fact came from** —
with **no hallucination**. life-agent remembers your digital life, retrieves the records that bear on
your question, and **verifies every cited fact actually appears in its source** before showing you
the answer. Facts are grounded in your own documents, not a model's memory.

> **Use it →** [`SETUP.md`](./SETUP.md) (clone to a cited answer in minutes, on a bundled synthetic
> corpus first — no real data, no API key to build it).
> **Contribute →** [`CONTRIBUTING.md`](./CONTRIBUTING.md).
> **Understand the design →** [`PRINCIPLES.md`](./PRINCIPLES.md) · [`ROADMAP.md`](./ROADMAP.md) · [`CLAUDE.md`](./CLAUDE.md) · [`docs/`](./docs/).

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

## How it fits together

```
your files ──┐ ingest
your email ──┴──▶  pkm — cited, searchable memory ──▶  bin/ask-live     you ask; every fact cited
                    │
                    │  grounded action items (local model, cited, auto-filed)
                    ▼
                   GTD task ledger (event-sourced) ──▶  Telegram bot    you manage tasks in plain language
                                                   ──▶  morning digest  it pushes a summary to you
```

You interact in exactly **two places**: `bin/ask-live` to *know* (questions in, cited answers
out) and the Telegram bot to *act* (tasks). Everything else — email→tasks, the digest — runs
unattended on timers. Every command, intent, and reply across these surfaces is governed by one
contract: [`docs/interaction-contract.md`](./docs/interaction-contract.md). Setting up the task
half: [`SETUP.md`](./SETUP.md), step 4.

## Why the answers are trustworthy

The promise is **cited, no-hallucination** answers, and it is structural rather than aspirational:

- **Verbatim facts are gated.** Before an answer is shown, a deterministic guard
  (`scripts/citation_guard.py`) checks that every value-bearing cited fact — IDs, numbers, proper
  nouns — actually appears in the source it cites. Anything that doesn't is flagged `⚠ unverified`,
  not presented as true.
- **Weak retrieval abstains.** If nothing in your corpus is a strong enough match, it says so
  instead of guessing (tunable via `LIFE_AGENT_SCORE_FLOOR` / `LIFE_AGENT_MIN_HITS`).
- **Identity is pinned.** An owner profile (`bin/ask-live "/tell …"`) is the lens for who "I" is, so
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
"/tell My name is …"`. Step-by-step in [`SETUP.md`](./SETUP.md#3-point-it-at-your-own-data).

## What's live vs the vision

The kernel ([`PRINCIPLES.md`](./PRINCIPLES.md)): **a knowledge base built from DAGs of
trustworthy transformations, and a personal assistant — the life agent — making rational,
utility-maximising decisions over it.** What exists today is the KB and its first consumers:
the cited retrieval + synthesis read path (`bin/ask-live`) over [`pkm`](./src/pkm/)'s catalogue,
and an event-sourced GTD (`life_agent.tasks`, reached over Telegram) that email auto-files into
with citations. The decision-theoretic faculties (the Bayesian brain, the goals/utility model)
and the agent-loop spine are future work — the spine deliberately an open decision. Status of
every faculty: [`ROADMAP.md`](./ROADMAP.md).

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
PRINCIPLES.md         the stable cross-phase principles (the philosophy; other docs defer to it)
CONTRIBUTING.md       dogfood loop, the PII guard, the two-package rules
ROADMAP.md            the plan (phases 0–3)
CLAUDE.md             operating manual for an agent working in this repo
LICENSE               AGPL-3.0-or-later
bin/
  ask-live            THE entrypoint: cited answers over the live corpus, fact-verified
  mail-to-tasks       email→GTD timer entrypoint: grounded action items, auto-filed with citations
src/
  pkm/                the KB — content-addressed extraction + transforms + DuckDB catalogue
  life_agent/         the agent — retrieval/citation guard, event-sourced GTD (tasks), Telegram reach
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
  interaction-contract.md       every human-facing surface: one grammar per concept, nothing silent
  act-layer-events.md           the GTD's event-sourced design (ledger = truth, SQLite = projection)
  kb-schema.md                  the knowledge-base schema (what lives under $LIFE_AGENT_KB)
  failures-template.md          the dogfood log entry format (misses drive development)
  pkm/                          pkm's SPEC + phase docs
  nix-for-documents-report.md   commissioned research on the memory-core architecture
```

## License

[AGPL-3.0-or-later](./LICENSE). `pkm` (vendored as `src/pkm`) is AGPL too, so the whole repository is
AGPL: you may use, modify, and redistribute it, but if you run a modified version as a network
service you must offer its users the corresponding source.
