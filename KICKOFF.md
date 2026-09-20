# Kickoff — change of direction

Paste this to the agent at the start of a session. It replaces every earlier session brief.

---

We changed direction on 2026-09-19. The unification arc is over: its registers (RULINGS,
DECISIONS, GD-/M-/A- entries), pre-registrations, frozen bars and adoption gate are archived
under `archive/` (tag `archive/unification-arc-v0`). None of it binds. The scoreboard, git
history and `CHANGELOG.md` replace all of it. Read `CLAUDE.md`, `MODEL.md`, `ROADMAP.md`.

What survives is the model: a string-blind decider, a Bayes act under a stated loss
(`u_wrong` prior mean −9, folded from reactions; the bar derived), provenance on every answer,
never invent. The act is the host's `core/decide.bayes_act`; the posterior is
`core/posterior.py` until the **ER core** (its own public repo, extracted from hkaddresses)
replaces it; **proplang** and **tannen** are doors after the MVP (`ROADMAP.md`). One home per
responsibility; delete the duplicates.

The MVP is **reusable by a stranger**, answering **verbatim point facts only** (graded by
exact match) and escalating or declining everything else.

## Where J1 left the board (2026-09-20)

Two rows, both pinned in `eval/sets.yaml`, both on one grader and one price list: the owner
set, typed 48/0/56 at $0.014 a question (U/q +0.443), and the generated golden set (212
questions from the corpus, `make golden`), typed 85/4/123 cold at $0.015 a question (U/q
+0.284) — its first pin, so the baseline. The typed row is the MVP target; escalation does
not pay at this gauge (−0.50 a call), so a rung ships only when it beats abstaining.

## Next session (in order, one commit each)

0. **Read the live stream first** (`make live`): days since the last live decision, the
   action mix, the owner's verdicts, and the MVP exit test — calendar days out of seven
   carrying live use. `make live-archive` turns the same stream into the board-shaped
   archive that becomes set `live`. The production readout is now a dead-man: it exits
   non-zero when the stream stops, and the weekly timer pages on that.
1. **J3 — the stranger.** The ask path from a clone: `SETUP.md` never mentions the bridge,
   yet every ask goes through it. Then `make data` completing the ingest (it registers
   sources and stops), the fresh-clone smoke covering `/decide` and the origin lines with a
   stubbed extractor (it proves retrieval only today), `make sets` fetching ATM-Bench at a
   pinned revision, and the two pending rows — `sample` (synthetic, so its questions and
   archive can live in the repo) and `atm`.
2. **J4 — close it.** The dead-man is in. What remains is a week of live use: the exit
   test counts calendar days carrying it, and only the owner asking moves that. Then pin
   the `live` row from `make live-archive` with its coverage stated.

Production is already on the host act (2026-09-20 19:10): the answer-brain daemon is
disabled, bridge and jarvis serve, `/ready` on :8798 reports `"decider": {"kind": "host"}`.
Roll back by re-enabling the daemon BY PATH from the credence repo — disabling removed its
unit symlink.

Open for the owner (ask-first): the menu's probe prices understate what the probes meter
cold — +$0.046 a row on the golden run, extraction unpriced — and `u_wrong` re-elicitation.

Tests that need owner data skip and say what they need. `make check` stays under two minutes.
