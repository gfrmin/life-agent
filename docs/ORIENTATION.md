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
                 └─ /decide          membrane/decider.py: core/posterior.py → proplang engine → act
```

The bridge gathers evidence and hosts the one decider: the candidate posterior is computed in
`core/posterior.py` and the proplang engine (`make engine`) picks the act from
{abstain, gather, ask, respond}; `membrane/coarse.py` enacts it. With no engine, `/decide`
answers 503 and the reply says the decider is unavailable; nothing answers in its place.
**J2** adds escalation rungs and tannen records; a question that is not a verbatim point fact
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
- `u_wrong = −9` — elicited (the owner's 10:1). Commit bar `|u_wrong|/(1+|u_wrong|) = 0.90`,
  Chow's reject rule. A reaction-conditioned fold of the same latent has read as soft as
  −5.13 (bar 0.837); the elicited value governs, and re-eliciting it is the owner's call.
- `lambda_usd ≈ 1.33` — the $↔utility rate, imputed from token counts, not metered.

## Where it stands

`SCOREBOARD.md`. On the owner's 104 questions (run 18): typed 61 right / 2 wrong / 41
declined at $0.0036/q; the recorded oracle (Claude Code over the corpus) 95 / 6 / 3 at
$0.375/q; the router — typed where it asserts, the oracle otherwise — 97 / 5 / 2 at $0.15/q.
The router is the MVP's shape. Under `u_wrong = −9` an escalation rung is chosen only if its
learned reliability clears 0.90 net of price, so rung 1 must be cheap and good.

**A-CAL — the posterior is calibrated** — is the assumption everything rests on: the commit
bar is a threshold on the posterior's value. Nothing yet establishes it; a reliability
diagram and ECE over the verdict stream would.

## Conventions

- **Pins** are exact expected values in tests. A failing pin means drift, not flakiness.
- **Poison fixtures** (`tests/poison/`) must be rejected; a passing poison test is a broken
  guard.
- **Cite the symbol; treat the line number as a hint.**
- Python 3.13 via `uv` (`uv sync --frozen`). mypy strict on `src/`, lenient on `scripts/`.
