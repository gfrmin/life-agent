# Orientation — the five-minute tour

`CLAUDE.md` (rules, working method), `MODEL.md` (how a question becomes an answer) and
`ROADMAP.md` (J0–J5) are the entry points. This file is the tour of the code as it runs today.
Unfamiliar word? → `docs/GLOSSARY.md`. History → `archive/` (tag `archive/unification-arc-v0`).

## What this is

A personal-knowledge system over the owner's own corpus. It retrieves, extracts candidate
facts with an LLM, then a **separate string-blind decision layer** chooses whether to assert,
withhold, gather more, or ask. The decision layer never sees the answer text — only a
posterior over candidate indices. That separation is the design commitment.

## The two packages

| Path | What |
|---|---|
| `src/pkm` | Ingest → extract → transform → DuckDB catalogue. Content-addressed, with lineage. |
| `src/life_agent` | Retrieval shaping, citation verification, the decision loop, GTD, trips, Telegram. |

## The read path today

```
scripts/ask.py / reach/jarvis.py
  └─ core/ask_client.drive
       └─ core/executor.run_pass     the loop; holds NO posterior and picks NO action
            └─ bridge/server.py      :8798 gathers and SHAPES evidence, and hosts the decider
                 ├─ /route           lane classifier (core/answer_shape.py); not a point fact ⇒ declined
                 ├─ /retrieve        BM25 over DuckDB FTS
                 ├─ /probe/*         subject, recency, corroborate, deliberate
                 ├─ /extract         LLM per chunk → candidates + integer observations
                 └─ /decide          core/decider.py: core/posterior.py → decide.bayes_act → enact
```

The bridge gathers evidence and hosts the one decider: the candidate posterior is computed in
`core/posterior.py`, `core/decide.bayes_act` takes the expected-utility argmax over
{abstain, gather, ask, respond} at the folded utility, and `core/enact.py` turns the act into
a reply. With the bridge down the reply says the decider is unavailable; nothing answers in
its place. proplang (`make engine`) is deferred behind the MVP.
**J2** added the origin on every reply; escalation rungs and tannen records wait; a question that is not a verbatim point fact
is declined until then.

## Entry points

| Command | What it does |
|---|---|
| `bin/ask-live` | Ask one question. |
| `bin/jarvis` | Telegram bot (GTD + questions), event-sourced. |
| `bin/daily-digest` | Morning brief; systemd timer with a dead-man check. |
| `make check` / `make score` | Tests; the scoreboard. |

## The gauge

- `u_correct = +1`, `u_abstain = 0` — the two pins.
- `u_wrong` — a posterior with prior mean −9 (the owner's 10:1), folded from reactions; the
  decider reads the folded mean (−5.13 today, so the Chow bar `|u_wrong|/(1+|u_wrong|)` is
  0.837; 0.90 at the prior). Re-eliciting it is the owner's call.
- `lambda_usd ≈ 1.33` — the $↔utility rate, imputed from token counts, not metered.

## Where it stands

[`SCOREBOARD.md`](../SCOREBOARD.md) is the answer; these numbers are a snapshot of
2026-09-20. Every row is graded on the answer it commits, by exact match, and priced at the
menu's declared prices whether or not a cache served the call.

- **owner** (104 authored questions): typed 48 right / 0 wrong / 56 declined, U/q **+0.443**.
- **generated** (212 questions `make golden` extracted from the corpus, answered cold):
  85 / 4 / 123, U/q **+0.284** — the first pin, so its own baseline.
- The **outside option** (a strong model over the same corpus) reads 87 / 13 / 4 on that one
  grader: **−0.355**. At a gauge where a wrong answer costs about five right ones, being
  wrong one time in eight is worth less than declining, however good the prose.

So the MVP's shape is the **typed row** — answer from your documents with provenance, or
decline — not a router that escalates what it withholds. Escalation ships when a rung beats
abstaining on the board, which no rung does today.

Two things the board does not yet cover: `atm` (an external corpus, J3) and `live` (what the
deployed arm does for its owner, J4 — the production readout is a dead-man over that stream,
and `make live` reads it).

**A-CAL — the posterior is calibrated** — is the assumption everything rests on: the commit
bar is a threshold on the posterior's value. Nothing yet establishes it; a reliability
diagram and ECE over the verdict stream would.

## Conventions

- **Pins** are exact expected values in tests. A failing pin means drift, not flakiness.
- **Poison fixtures** (`tests/poison/`) must be rejected; a passing poison test is a broken
  guard.
- **Cite the symbol; treat the line number as a hint.**
- Python 3.13 via `uv` (`uv sync --frozen`). mypy strict on `src/`, lenient on `scripts/`.
