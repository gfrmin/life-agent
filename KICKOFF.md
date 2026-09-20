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

1. **Production on the host act.** The owner's step runs as a rehearsed script right after
   J1 merges: pull master, `systemctl --user daemon-reload` (the bridge unit changed), disable
   the answer-brain daemon, restart the bridge and jarvis, `/ready` on :8798 shows
   `"decider": {"kind": "host"}`. If it does not, run that script first.
2. **J2 — origin on every reply.** PR #193 (`j2-origin`) is built and green: retarget to
   master, undraft, merge. Disclosure records wait with the rung.
3. **J3 — the stranger.** `make data` over any maildir or filetree; `make sets` builds
   ATM-Bench on-machine (the `atm` row); fresh-clone smoke in CI; `SETUP.md` current.
4. **J4 — live.** jarvis serving asks; the production readout as a dead-man over the
   decision log; the `live` row.

Open for the owner (ask-first): the menu's probe prices understate what the probes meter
cold — +$0.046 a row on the golden run, extraction unpriced — and `u_wrong` re-elicitation.

Tests that need owner data skip and say what they need. `make check` stays under two minutes.
