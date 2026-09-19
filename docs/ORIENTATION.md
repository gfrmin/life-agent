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
- `u_wrong` — a posterior with prior mean −9 (the owner's 10:1), folded from reactions; the
  decider reads the folded mean (−5.13 today, so the Chow bar `|u_wrong|/(1+|u_wrong|)` is
  0.837; 0.90 at the prior). Re-eliciting it is the owner's call.
- `lambda_usd ≈ 1.33` — the $↔utility rate, imputed from token counts, not metered.

## Where it stands

`SCOREBOARD.md`. On the owner's 104 questions (run 18): typed 61 right / 2 wrong / 41
declined at $0.0036/q; the recorded oracle (Claude Code over the corpus) 95 / 6 / 3 at
$0.375/q; the router — typed where it asserts, the oracle otherwise — 97 / 5 / 2 at $0.15/q.
The router is the MVP's shape. An escalation rung is chosen only if its learned reliability
clears the Chow bar net of price (0.837 at today's fold, 0.90 at the prior), so rung 1 must be
cheap and good. At the folded gauge the typed and router rows are level on U/q (+0.483 and
+0.482): the router's extra right answers are paid for by its three extra wrongs and its spend.

**A-CAL — the posterior is calibrated** — is the assumption everything rests on: the commit
bar is a threshold on the posterior's value. Nothing yet establishes it; a reliability
diagram and ECE over the verdict stream would.

## Conventions

- **Pins** are exact expected values in tests. A failing pin means drift, not flakiness.
- **Poison fixtures** (`tests/poison/`) must be rejected; a passing poison test is a broken
  guard.
- **Cite the symbol; treat the line number as a hint.**
- Python 3.13 via `uv` (`uv sync --frozen`). mypy strict on `src/`, lenient on `scripts/`.
