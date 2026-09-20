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

## Where the board stands (2026-09-20, after J3)

Five pinned rows in `eval/sets.yaml`, all on one grader and one price list; `SCOREBOARD.md`
now prints each row's note under the table, because a U/q without the population it is over
is the clause a reader drops first. The typed row is the MVP target; escalation does not pay
at this gauge (−0.50 a call), so a rung ships only when it beats abstaining.

| set | rows | right/wrong/declined | $/q | U/q |
|---|---:|---|---:|---:|
| owner (typed) | 104 | 48 / 0 / 56 | 0.0139 | +0.443 |
| generated (typed) | 212 | 85 / 4 / 123 | 0.0151 | +0.284 |
| atm (typed) | 198 | 26 / 5 / 167 | 0.0102 | −0.012 |
| sample (typed) | 14 | 8 / 0 / 6 | 0.0119 | +0.556 |

`atm` is the only row the act did not choose the difficulty of, and the only negative one —
but read its note before quoting the number. All five of its wrongs were re-asked and none
is an invention: each names the gold fact in another surface form, and only 77 of its 198
golds are verbatim spans in their own cited document. **Open for the owner:** whether to
re-cut that set on the precondition this project's own bar states (an answer that stands as
a span in the document), which is an eval-question change and so not the agent's to take.

## Next session (in order, one commit each)

0. **Read the live stream first** (`make live`): days since the last live decision, the
   action mix, the owner's verdicts, and the MVP exit test — calendar days out of seven
   carrying live use. `make live-archive` turns the same stream into the board-shaped
   archive that becomes set `live`. The production readout is now a dead-man: it exits
   non-zero when the stream stops, and the weekly timer pages on that.
1. **J4 — close it.** The only milestone left, and the one no amount of building moves:
   the exit test counts calendar days out of seven carrying live use, so it needs the owner
   asking jarvis and grading the replies (`g`/`b`). Then pin the `live` row from
   `make live-archive` with its coverage stated (verdicts bound to decisions, not the whole
   stream), and `readout.md` stops saying STALE.
2. **J3 landed 2026-09-20** (PR #195): the bridge is in `SETUP.md`, `make data` completes
   the ingest, `make sets` fetches ATM-Bench at a pinned revision, the fresh-clone smoke
   reaches a decision keyless, and both pending rows are pinned. Its finding was in the
   decider: a KB with no fitted gather row never buys a gather, so a fresh install could
   only decline — `config/gather-row.example.json` is now the documented default.

Production is already on the host act (2026-09-20 19:10): the answer-brain daemon is
disabled, bridge and jarvis serve, `/ready` on :8798 reports `"decider": {"kind": "host"}`.
Roll back by re-enabling the daemon BY PATH from the credence repo — disabling removed its
unit symlink.

Open for the owner (ask-first): the menu's probe prices understate what the probes meter
cold — +$0.046 a row on the golden run, extraction unpriced — and `u_wrong` re-elicitation.

Tests that need owner data skip and say what they need. `make check` stays under two minutes.
