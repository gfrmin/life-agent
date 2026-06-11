# Getting started — first session

> **Audience note:** this is the maintainer's working checklist for an *agent
> session on the live deployment* — the status and prerequisites below describe
> that machine, not a fresh clone. A human setting up from scratch starts at
> [`SETUP.md`](./SETUP.md).

This is the concrete checklist for a fresh agent/session. Read
[`PRINCIPLES.md`](./PRINCIPLES.md) (the philosophy) and [`CLAUDE.md`](./CLAUDE.md) (the
operating manual) first; [`ROADMAP.md`](./ROADMAP.md) has the full plan.

**Status:** the retrieval substrate is built and the **live corpus is ingested and searchable**
(NVMe catalogue, ~13k sources / ~400k chunks). The read path is `scripts/ask.py`, dogfooded via
**`bin/ask-live`**. The GTD act layer is live and event-sourced (`life_agent.tasks`), reached
over Telegram (`life_agent.reach`); email→GTD auto-files cited tasks off a timer.
**Active phase = mature memory (Phase 1.5): dogfood, log misses to `$LIFE_AGENT_KB/FAILURES.md`,
build only what the failure log demands** (PRINCIPLES §9). The agent loop / brain / spine are
later phases (spine = open decision, PRINCIPLES §15).

**Knowledge lives outside this repo**, at `$LIFE_AGENT_KB` (default `$HOME/.life-agent/kb`) —
see [`docs/kb-schema.md`](./docs/kb-schema.md).

**Local config:** copy `.env.example` → `.env` (gitignored) and set `LIFE_AGENT_KB` +
`PKM_CONFIG` for your machine, then `set -a; source .env; set +a` once per shell before running
the tooling. `.env` is for **non-secret paths only** — secrets stay in your secret store and
are read via `secret-tool`, never from `.env`.

## Prerequisites (verify, don't assume)

- Ollama is up: `curl -s localhost:11434/api/tags | jq '.models[].name'` should list
  `nomic-embed-text` and a chat model.
- OCR ready: `tesseract --list-langs` includes `heb` and `eng`.
- `rga --version` works (ripgrep-all; searches inside PDFs).
- Secrets, if needed, come from gnome-keyring (`secret-tool lookup service env key VARNAME`);
  never read `~/.env`.

## The dogfood loop (Phase 1.5 — the active work)

1. **Ask real questions** you'd want a PA to answer: `bin/ask-live "…"`. Answers must cite;
   weak retrieval abstains.
2. **Log every miss** to `$LIFE_AGENT_KB/FAILURES.md`, one entry per the template
   ([`docs/failures-template.md`](./docs/failures-template.md)): the question, why it failed,
   what capability would fix it.
3. **Build only what the log demands** — trace every change to a logged failure; speculative
   features go to a backlog, not the tree.
4. **Measure**: `uv run python scripts/run_eval.py` grades answers against the eval set
   (`$LIFE_AGENT_KB/eval/questions.yaml`); add a question when a new answer shape appears.

Useful side-tools: `scripts/needle.sh "<term>"` (OCR+grep document finder, works on scans);
`python scripts/data_source_registry.py --report` (what's on the system vs what's ingested);
to add a source, edit `$LIFE_AGENT_KB/config/data-sources.yaml` and re-run
`scripts/ingest_sources.py`.

## House rules

- Don't commit unless the owner asks.
- Compose existing systems before writing new code (PRINCIPLES §4).
- Keep capabilities behind language-neutral seams — MCP / HTTP / CLI — so interfaces stay
  swappable (PRINCIPLES §5).
- In `src/pkm`, the frozen-foundation rigor applies (PRINCIPLES §11): SPEC-first, TDD,
  idempotency double-runs.
