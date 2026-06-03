# Contributing to life-agent

Thanks for trying this on your own life and wanting to make it better. A few
things make contributing here unusual; please skim this before your first PR.

## The prime directive: compose, don't rebuild

~90% of the capability already exists as small, composable pieces. Before adding
anything, check whether a producer, a transform, or an existing script already
does it. New code should be **integration + a thin layer**, not a greenfield
subsystem. See [`CLAUDE.md`](./CLAUDE.md) for the architecture and the reuse map.

## This is a public repo holding tooling for *private* data — never commit PII

The whole repo is built to keep your personal data out of it. Two rules:

1. **Test/example data is synthetic.** Use obviously-fake values: emails on
   `@example.com`, national IDs chosen to *fail* their checksum (e.g.
   `123456789`), no real names/addresses/phones. The fictional people are Ada
   Lovelace and Charles Babbage — reuse them.
2. **The PII guard is mandatory and runs on every commit + push.** Enable it
   once per clone:

   ```bash
   git config core.hooksPath .githooks
   cp config/pii-patterns.txt.example "$LIFE_AGENT_KB/pii-patterns.txt"
   ```

   The guard (`.githooks/pii_check.py`) allows only safe *shapes* and blocks
   anything resembling real PII (the value is never printed, only `path:line:
   kind`). It is **fail-closed**: in default mode it refuses to run if
   `$LIFE_AGENT_KB/pii-patterns.txt` is missing — hence the copy above. For an
   ad-hoc scan without a KB: `python .githooks/pii_check.py --shapes-only`. A
   genuine, reviewed false positive can be marked with a trailing `# PII-OK` on
   the line (use sparingly).

## Working style

- **Dogfood.** This is built FAILURES-first: use it on real questions, and let
  the misses — logged to `$LIFE_AGENT_KB/FAILURES.md` — drive what you build.
  Speculative features without a traced failure belong in a backlog, not a PR.
- **Don't commit or push unless asked.** Make the change; let the maintainer
  decide when it lands.
- **Functional style** — small, single-purpose, well-typed units. Cite
  provenance on every answer path.

## Two packages, one repo

```
src/pkm/         the memory faculty — content-addressed extraction + DuckDB catalogue
src/life_agent/  the reasoning/synthesis faculty — retrieval, citation guard, owner profile
scripts/         the runnable layer (ask.py, ingest, eval, bootstrap, smoke)
tests/           life_agent + script tests;  tests/pkm/  is pkm's own suite
docs/pkm/        pkm's SPEC + phase docs
```

**`src/pkm` is governed by its own stricter rules** ([`src/pkm/CLAUDE.md`](./src/pkm/CLAUDE.md)):
SPEC-first (amend `docs/pkm/SPEC.md` before changing behaviour), TDD (test before
code), and **every cache operation proven idempotent by a double-run**. Adding a
dependency, a new top-level directory, or a new file format there needs a heads-up
first. `src/life_agent` is lighter but still test-first.

## Quality gates (run before opening a PR)

```bash
uv run --project . pytest                       # both suites (LLM tests are skipped by default)
uv run --project . ruff check src tests scripts # lint everything
uv run --project . mypy                          # strict on src/pkm
scripts/smoke-fresh-clone.sh                     # clone → sample → cited retrieval, no key
```

CI runs these on every PR (see `.github/workflows/ci.yml`) and they are blocking.
Tests that hit a live LLM are marked `llm` and excluded by default; don't add
unmarked tests that need network or an API key. Keep `src/`, `tests/`, and
`scripts/` ruff-clean, and `src/pkm` mypy-clean.

## Good first contributions

- A new pkm **producer** or **perspective transform** (small, grounded, cached).
- Retrieval-quality fixes traced to a logged `FAILURES.md` miss.
- Sample-corpus questions/docs that exercise an un-covered answer shape.
- Docs: anything that tripped you up in [`SETUP.md`](./SETUP.md).
