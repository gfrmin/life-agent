# CLAUDE.md — operating manual for `life-agent`

You are an agent working in `.`, the composition root of a personal life-management
assistant. **Read [`PRINCIPLES.md`](./PRINCIPLES.md) first** — it is the single source of the
philosophy (the kernel, the derive/act boundary, resolved and open decisions); this file is
only the operating manual. Then [`docs/system-design.md`](./docs/system-design.md) — the
adopted whole-system design (one DAG; everything is an edge on it; act ledgers project back
into knowledge) — then [`ROADMAP.md`](./ROADMAP.md) for the plan and
[`GETTING_STARTED.md`](./GETTING_STARTED.md) for the immediate tasks. The owner is a strong
engineer (builds Julia DSLs, TS, Python data platforms) — be precise, terse, and don't
over-build (PRINCIPLES §4: compose, don't rebuild).

## What exists (present tense, no aspiration)

Two in-tree Python packages — `pkm` (the KB: derive) and `life_agent` (the agent: decide) — in
a **derive → project → reach** shape (PRINCIPLES §6):

- **derive (`src/pkm`):** sources → primary artifacts → composable transforms → cited, cached,
  idempotent artifacts (SPEC §18.7 chaining; small auditable steps, never a mega-transform).
  `pkm derive` resolves one (input, transform-chain) target cache-first (SPEC §18.11) — a warm
  chain makes zero model calls — demand-logged under `logs/demand/`.
- **project (`src/life_agent/tasks/project.py`):** a thin immutable→mutable bridge — terminal
  `action_items` artifacts filed **once** into the GTD inbox with a `[src:email <id>]` citation.
- **reach (`src/life_agent/reach`):** Telegram as a dumb transport; "Jarvis" is just the persona.

The GTD is event-sourced: an append-only ledger is truth, the SQLite read-model is a fold of it
(PRINCIPLES §7; `docs/act-layer-events.md`). **email→GTD runs off a `systemd --user` timer**
(`bin/mail-to-tasks` is the timer/debug entrypoint): the `action_items` transform (haiku,
grounded quotes) auto-files cited tasks; the grounding gate is the safety; triage
happens in Telegram. The ask-anything read path is `scripts/ask.py`, dogfooded via
`bin/ask-live`; its temporal mode (`/recent`, `/since`, `/until`, `/derive` — one line
grammar, identical in the REPL and one-shot argv) filters by the `doc_date` projection
(SPEC §18.12) read-side, naming undated and not-yet-derived hits instead of dropping them.
Its subject mode (engine D2) owner-filters "my X" questions by the `doc_subject`
projection (SPEC §18.13) matched against the owner profile via cached model
verdicts (`life_agent.core.subject`; the profile never enters pkm) — determinate
non-owner and template hits are excluded by name, indeterminates kept and named.
**The GTD ledger projects into knowledge** (`tasks/knowledge.py` →
`$LIFE_AGENT_KB/tasks/state.md`, the mutable→knowledge mirror of `project.py`): the ask
path re-projects + re-ingests it demand-led when the ledger head moves (announced, never
silent), and pkm's path-currency rule (SPEC §15.4) keeps only the newest version
retrievable — so "what's next on my gtd list?" is an ordinary cited `QUESTION`.
Every human-facing surface is governed by
[`docs/interaction-contract.md`](./docs/interaction-contract.md) — read it before touching
a command, intent, flag, or reply string.

**Adopted, being built (Phase 1.6):** the derivation framework —
[`docs/system-design.md`](./docs/system-design.md) +
[`docs/derivation-engine-design.md`](./docs/derivation-engine-design.md) (D0–D2 and the
GTD ledger's knowledge projection + pkm path-currency landed) — and, adopted 2026-06-12,
the **Bayesian foundations**
([`docs/bayesian-foundations.md`](./docs/bayesian-foundations.md)): Ask re-derived as
inference (answers = claim sets with posteriors; responses = EU decisions; calibration
measured). Ask v0 slices 0–3 are landed: the outcomes + decision logs accrue under
`$LIFE_AGENT_KB/calibration/`; `core/brain.py` is the credence skin seam; the **utility
posterior** (`core/utility.py` — utility is a learned belief about the owner, §4.4/§10
as amended: one utility, the agent has none of its own); the **lookup family**
(`core/lookup.py` — §4 with §4.1 covariates); and **narrative subsumption**
(`core/narrative.py` — §7: synthesize is a proposal distribution; claims audited into
cells, population-calibrated per-cell from the eval_claim stream, per-claim EU inclusion
under Ū, the proposal-coverage tail named); and the **§8 decision-weighted adoption
gate** (`core/gate.py`, `run_eval --gate` → `$LIFE_AGENT_KB/eval/gate/`: a posterior
over Δ = EU(typed) − EU(monolithic) by MC over P(U) × the Bayesian bootstrap, P(Δ>δ)≥
level with δ/level frozen blind; the disagreement region + answer rates published). Six
runs so far (§14 ledger has each): the executor series read 0.002 → 0.010 → 0.065 →
0.092 → 0.098, then **run 6 (2026-08-17: judge-graded arms, λ_usd spend on both arms,
the post-Ollama cloud instruments): FAIL at P(Δ>0.05)=0.678, Δ̄=+0.180 [−0.244, +0.661]
— the first positive mean;** typed answer rate 0.47 (47 ✓ / 2 ✗) vs monolithic 0.97,
withholdings split miss 18 · dispersed 37 (the reach lever's first *direction*). The
run-5 attribution counterfactual (`scripts/gate_splice.py`, same day, not a reading)
settled what carried the sign: run 5's cautious typed arm, judge-graded and priced, reads
**0.905 / +0.343** — grading + spend did it; the new instrument's live arm gave back
Δ̄ −0.163 (corrects +0.192, two wrongs −0.173, spend −0.183). Audited the same day:
q2-053 was a stale gold (superseded in-corpus; corrected, disclosed), q2-105 a cached
opus coin-flip at 0.93 whose stale CORRECT curve rows the append-only regrade
(`scripts/regrade_edge_rows.py`) now supersedes; and run 6's nine cold deliberates
($10.87) never reached the corpus — the pkm MCP server failed to register (PKM_CONFIG
unset in the launcher) and blind declines were cached as evidence (voided; guarded at
`deliberate.answer`, the bridge cfg, and the gate preflight). **Run 7 (same day,
`gate-20260817T160244`: the run-6 recipe with a working deliberate, corrected golds,
regraded curves) — the series' first PASS: P(Δ>0.05)=0.945, Δ̄=+0.429 [+0.040,
+0.884]**, typed 50 ✓ / 1 ✗ / 53 withheld (miss 18 · dispersed 35) at $5.56 vs mono
0.97 at $39.01. **Run 8 (router v2,
`gate-20260817T164427`): FAIL 0.857, Δ̄ +0.344 [−0.109, +0.841]** — the router worked
(16 newly admitted: 6 ✓ / 10 dispersed / 0 wrong; miss 18→2; answer rate 0.57; $3.25)
but two curve-evolution wrong-leader commits on multi-value chunks (q2-053, q2-090)
pulled it back under. **Run 9 (the competing-values temper, `gate-20260817T195737`):
PASS 0.938, Δ̄ +0.390 [+0.032, +0.841] — zero wrong commits** (35 ✓ / 0 ✗ / 69 withheld,
answer rate 0.34, $4.10): a same-shape competitor in the extractor's quote window halves
the observation's r on both commit sites (`matching.quote_scoped_competitors` →
`competition_factor`, join channel inherits it — §2 lineage), registered blind off-gate
(`scripts/temper_audit.py`, counterfactual floor 0.945/+0.401 — the live run matched it
almost exactly and the sweep predicted the assert set perfectly). The wrong-commit class
is closed at the price of reach. **§13 adoption RESOLVED (2026-08-17, on runs 7+9):
typed is the silent default, honest-withhold-only (the uncalibrated fallback lane is
REMOVED — `LIFE_AGENT_FALLBACK_LANE` is ignored), and the deliberate edge is ON by
default (`LIFE_AGENT_DELIBERATE=0` is the rollback)** — §14's adoption entry has the
evidence and rejected alternatives. The named next lever is independent-document
corroboration on the 67 dispersed (ceiling audited at $0 first, alongside the
19-question n_obs=0 cluster). Old D3–D4 stay re-scoped as Ask's
aggregate/thread families. The doc's §14 open questions are a **live empirical ledger**
(owner's adoption rider): each entry names the evidence that decides it — keep it
current. Sequencing is continuous and eval-gated, not dogfood-gated (PRINCIPLES §9 as
amended).

**Not built, deliberately:** the agent-loop spine (open decision — PRINCIPLES §15),
the VOI governor (last on the geodesic — PRINCIPLES §16), a live MCP server
(`src/pkm/mcp_server.py` is dormant-by-design — PRINCIPLES §5). One candidate spine+brain
composition is documented at
[`docs/candidates/brain-design.md`](./docs/candidates/brain-design.md) — a candidate, not the
plan; the related external repos (`../credence/apps/credence-pi`, `../pi-mono`) are reference
material for that candidate only.

- **Membrane shadow (`src/life_agent/membrane`, `src/life_agent/bridge`):** the frozen
  proplang-govhost engine mirrors live decide/verdict traffic off to the side, never on the
  decision path. Env-gated (absence = disabled); report at `$LIFE_AGENT_KB/membrane/report.md`,
  register at [`docs/membrane-shadow.md`](./docs/membrane-shadow.md).

## `src/pkm` — the KB core (Python, uv, DuckDB): key files

Content-addressed extraction cache + DuckDB catalogue + format producers + transforms.
**It already nails content-addressing and a *semantic* (not bitwise) determinism contract —
don't "fix" that (PRINCIPLES §10).**
- **Producer protocol:** `src/pkm/producer.py` (`Producer` Protocol, `ProducerResult`).
- **Producer template (subprocess + version parse, never raises):** `src/pkm/producers/pandoc.py`.
- **Wiring ladders (edit to add a producer):** `src/pkm/routing.py`, `src/pkm/extract.py`
  (`_PRODUCER_NAMES`, `_needed_producer_names`, `_ensure_constructed`), `src/pkm/cli.py`
  (`--producer` choices, `_SUBCOMMANDS`).
- **Catalogue + migrations:** `src/pkm/catalogue.py`, `src/pkm/migrations/` (hash-verified;
  never edit a landed migration — add the next number).
- **Cache key:** `src/pkm/hashing.py` (`compute_cache_key`, `compute_model_identity_hash`).
- **Transforms:** `src/pkm/transform.py`, `src/pkm/transforms/{entity_extraction,action_items,email_triage}.py`;
  they **chain** (`_find_eligible_sources` resolves `input.producer` over `artifacts` — SPEC §18.7).
  Live model calls gated behind markers (`-m 'not llm and not system'` is the default; both are
  non-deterministic, opt-in only).
- **Tests:** `tests/conftest.py` (`tmp_root`, `migrated_root`); hermetic by default.
- **Governance — READ FIRST:** `docs/pkm/SPEC.md` and `src/pkm/CLAUDE.md`. The frozen-foundation
  rigor (PRINCIPLES §11): SPEC-first, TDD, idempotency double-runs, ask before a new
  dependency / top-level directory / file format.
- Verified: **DuckDB 1.5.2** here loads both `fts` and `vss` (HNSW cosine + `array_cosine_distance`).

## `life_agent.tasks` — the GTD, event-sourced (Python, SQLite, the act layer)

One append-only **event ledger** is the source of truth; the SQLite is a rebuildable
projection. See `docs/act-layer-events.md`.
- **Ledger:** `src/life_agent/tasks/events.py` — `Asserted`/`Disposed`/`Superseded`/`Amended`,
  keyed on a content+grounding **assertion identity** (human commands mint a unique identity;
  email-derived use content).
- **Read-model:** `src/life_agent/tasks/store.py` — the `tasks` table (lists
  inbox/next/scheduled/someday; `@tags`; `is_today`; due); `apply(event)` folds one event,
  `rebuild(events)` replays the ledger. Paths (`src/life_agent/core/config.py`): ledger at
  `$LIFE_AGENT_KB/tasks/events.jsonl`, read-model at `GTD_DB_PATH` (default
  `$LIFE_AGENT_KB/tasks/gtd.db` — derived, safe to delete and rebuild); the legacy
  `JARVIS_DB_PATH` (`$LIFE_AGENT_KB/jarvis/jarvis.db`) is a read-only pre-cutover snapshot.
- **Commands (write seam):** `src/life_agent/tasks/commands.py` →
  `commands.add/complete/delete/move/...` (append event(s) → fold the read-model → return the
  reply). The email projector (`project.py`) is just another producer of
  `Asserted(origin="email")` events.

## `life_agent.reach` — the Telegram channel + persona (transport only, no truth)

- **Transport:** `src/life_agent/reach/telegram.py` (poll/send; knows only Telegram).
- **Loop + NLU + persona:** `src/life_agent/reach/jarvis.py` — a haiku call parses a message →
  intent → routes to `tasks.commands`/`tasks.store`. Runs as `systemd --user jarvis.service`
  via `python -m life_agent.reach.jarvis`.
- **Digest:** `src/life_agent/reach/digest.py` (`python -m life_agent.reach.digest`).
- **Owner's Telegram id:** `JARVIS_USER_ID` (env / gnome-keyring) — never hard-code it.

## Conventions & constraints (operational)

The principles themselves (functional style, seams, provenance, local/cloud, Tailscale,
dogfood) live in [`PRINCIPLES.md`](./PRINCIPLES.md) — they are not restated here.
- **In `pkm`:** obey its SPEC-first + TDD + idempotency rules (see Governance above).
- **Secrets** live in **gnome-keyring**, never in `.env`. Read one with
  `secret-tool lookup service env key VARNAME`; load all into a shell with
  `load_secrets_from_keyring`. Fastmail tokens: keyring `service=carddav` / `service=jmap`;
  sending email: `~/.msmtprc` (passwordeval).
- **Tooling preferences:** `rclone` (not s3cmd) for R2; `gh` (not a GitHub MCP) for GitHub;
  don't pipe long-running commands through `head`/`tail` (use native verbosity).
- **Commit/push only when the owner asks.**

## Environment (Arch Linux, this machine)

- **GPU:** RTX 4060 (8 GB). **Local Ollama is DEPRECATED (2026-08-17, owner directive)** —
  the cached ask instruments, the pkm LLM transforms, and jarvis's NLU all run on the
  Anthropic seam (`core/instrument.py`, haiku); local inference returns only via a
  non-Ollama runtime (e.g. for embeddings, unbuilt). Do not assume `localhost:11434`.
- **OCR/docs:** `tesseract 5.5.2` (langs incl. **`heb`** + `eng`), `pdftotext`, `exiftool`,
  ImageMagick 7, ghostscript, libreoffice.
- **Search:** `rg 15.1`, **`rga 0.10.10`** (ripgrep-all, searches inside PDFs), `sqlite3 3.53`
  (FTS5), `pandoc`, `jq`. (No `fd`/`fzf`/`recoll`.) **DuckDB 1.5.2.**
- **Langs:** Python 3.14 system-wide, but **this project pins 3.13** via `uv`
  (`pyproject.toml` `requires-python`); Node 26 + `pnpm`/`bun`; Julia (for credence).
- **Running services:** `jarvis.service`, PhotoPrism, Tuwunel + mautrix bridges +
  `matrix-archiver`, n8n, miniflux, invidious; timers `mbsync` (mail) + `renavon-inbox-ingest`;
  bi-hourly borg backup.

## Start here

1. Read [`PRINCIPLES.md`](./PRINCIPLES.md), then [`ROADMAP.md`](./ROADMAP.md) (phases), then
   `$LIFE_AGENT_KB/docs/data-seams.md` (the verified, machine-specific data map — out of tree;
   saves you a re-exploration).
2. Follow [`GETTING_STARTED.md`](./GETTING_STARTED.md). Current phase: **Phase 1.6 — the
   derivation framework** (`docs/system-design.md` §8 is the program; FAILURES.md remains
   the evidence log, no longer the gate — PRINCIPLES §9).
