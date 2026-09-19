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

## Next session — after J1 (in order, one commit each)

1. **The board.** Run a side-port bridge from the worktree (`LIFE_AGENT_BRIDGE_URL`;
   production untouched), the typed arm (`scripts/fairfight/arm_baseline.py`) over the owner's
   104 questions at the folded Ū, paired with the recorded oracle; pin it in `eval/sets.yaml`;
   `make score`; rule 5 (ΔU ≥ 0 on every row) holds or the change does not merge.
2. **`make golden`.** Generate a golden set from the corpus: sample documents, extract
   verbatim point-fact spans, phrase one question per span, write (question, answer,
   citation) under `$LIFE_AGENT_KB/eval/`, pin it as set `generated`, grade by exact match.
3. **The owner's step** (a prepared script): stop the answer-brain daemon, restart the bridge
   and jarvis, one Telegram ask shows the host decider on `/ready`.
4. **J2**: escalation rungs as rows `bayes_act` ranks, origin on every reply.

Tests that need owner data skip and say what they need. `make check` stays under two minutes.
