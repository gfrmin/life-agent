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
**Active phase = the derivation framework (Phase 1.6):** the typed Bayesian ask arm is
the **deployed default since 2026-08-25** (run 14 PASS; ROADMAP item 3f). What remains is
the approved completion programme: the collapse ladder M2–M7
(`docs/module-collapse-design.md` §8), then the aggregate + thread families (ROADMAP items
4–5), then the proplang graduation — each eval-gated; dogfood misses still go to
`$LIFE_AGENT_KB/FAILURES.md` as evidence, but no longer gate the next phase (PRINCIPLES §9
as amended). The agent loop / brain / spine are later phases (spine = open decision,
PRINCIPLES §15).

**Knowledge lives outside this repo**, at `$LIFE_AGENT_KB` (default `$HOME/.life-agent/kb`) —
see [`docs/kb-schema.md`](./docs/kb-schema.md).

**Local config:** copy `.env.example` → `.env` (gitignored) and set `LIFE_AGENT_KB` +
`PKM_CONFIG` for your machine, then `set -a; source .env; set +a` once per shell before running
the tooling. `.env` is for **non-secret paths only** — secrets stay in your secret store and
are read via `secret-tool`, never from `.env`.

## Prerequisites (verify, don't assume)

- ANTHROPIC_API_KEY resolves (`secret-tool lookup service env key ANTHROPIC_API_KEY`) —
  the instruments, transforms, and NLU run on the Anthropic seam (local Ollama
  deprecated 2026-08-17; nothing checks `localhost:11434` any more).
- OCR ready: `tesseract --list-langs` includes `heb` and `eng`.
- `rga --version` works (ripgrep-all; searches inside PDFs).
- Secrets, if needed, come from gnome-keyring (`secret-tool lookup service env key VARNAME`);
  never read `~/.env`.

## The loop (Phase 1.6 — the active work)

1. **Execute the program** in order ([`docs/system-design.md`](./docs/system-design.md) §8);
   each phase lands SPEC-first/TDD where it touches pkm and must pass its eval gate
   ([`docs/derivation-engine-design.md`](./docs/derivation-engine-design.md) §11).
2. **Keep asking real questions** (`bin/ask-live "…"`) and **log every miss** to
   `$LIFE_AGENT_KB/FAILURES.md` per the template
   ([`docs/failures-template.md`](./docs/failures-template.md)) — evidence, not a gate
   (PRINCIPLES §9): it shapes priorities within the program and verifies phases against
   reality.
3. **Measure**: `uv run python scripts/run_eval.py` grades answers against the eval set
   (`$LIFE_AGENT_KB/eval/questions.yaml`); add a question when a new answer shape appears.
4. Anything outside the adopted design goes to the backlog, not the tree.

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
