# RULINGS — the standing-ruling register

**What this is.** One row per owner ruling that still determines a future choice. It exists so
that a session facing a fork can answer *"is this already ruled?"* in one read instead of
searching ~30 documents — the same anti-relitigation function the §6 register performs for
defects (`docs/module-collapse-design.md` §6), applied to decisions.

**Why it exists.** On 2026-08-31 an agent put two questions to the owner — the scope of the norm
lever and its measurement instrument. Both were already determined: by r30b's
one-lever-per-reading precedent, by conferral 2's ruling 3 delegation, and by r29's finding about
the gate corpus. Both came back as the recommendation. The cause was mechanical: 158 ruling
references across ~30 documents with no index, so asking the owner cost less than searching.
This register removes that cost.

**How to use it.** Before escalating any fork: read §1–§4 here. A fork this register determines
is not a question — it is execution. A fork it does not determine is resolved by $0 evidence,
then by the current utility posterior, then **decided and published** in
[`DECISIONS.md`](./DECISIONS.md). The only class that reaches the owner is §5.

**How to maintain it.** Append-only in spirit: a ruling is superseded by a later ruling, never
edited away. Every conferral or report that takes a ruling registers it here in the same commit
— `tests/test_rulings_register.py` fails if a document carrying a `RULING`/`RULINGS` section is
not cited below.

---

## §1 Method — binds every arc

| id | date | source | what it determines |
|---|---|---|---|
| **M-1 · the hard clause** | 2026-08-24 | `r09d-window-conferral` RULINGS-2 §5; reaffirmed `conferral-2` | **No lever ships while it makes a named wrong-commit class worse.** An inversion on a named wrong-commit class is blocking *on its own*, whatever the aggregate counts say. Baseline today: zero wrong commits in 69 asks. |
| **M-2 · $0 before priced** | 2026-08-30 | `conferral-2` ruling 1 | $0 counterfactuals precede builds, and a $0 reading that is a *precondition* for a class opens before the lever for that class. |
| **M-3 · pre-registration first** | 2026-08-24 | `run13-join-conferral` ruling 1; carried by `r09b-sweep-conferral`, `r09c-sweep-conferral`, `r09d-disposition-conferral` | Criteria, directional claims and the consequence branches are committed **before any `src/` change**. A frozen clause is re-read against the artefact it names before it is applied. |
| **M-4 · never silently weaken** | 2026-08-18 | `r03-merge`; `r15-collapse-m5` amendment A5 | A frozen criterion is amended only blind, prospectively, and in public. Retroactive edits to a live criterion are the one thing that compromises the record. |
| **M-5 · price the firing direction first** | 2026-08-24 | `r09d-window-conferral` ruling 2 | Registered as standing practice: *price a lever's firing direction on the whole battery before buying a sweep.* |
| **M-6 · cap the arc** | 2026-08-23 | `r07-recorded-replay` ruling 4 | An anomaly found en route is a **disclosure item in the checkpoint that finds it**, never a new diagnostic arc. |
| **M-7 · read the deployed rule** | standing lesson, ≥5 instances | `r05-carrier-identity`, r10, `r30-units-lever`, `r31-integration-gate`, r34 | A census must read the deployed rule end-to-end, **never re-implement the constant it prices**. Its signature: byte-identical numbers before and after a change — or, as at r34, a characterisation inferred from outputs without checking which predicate produced them. |
| **M-8 · name a class, not rows** | 2026-08-25 | `run14-conferral` lesson | A criterion names a **class + a bar + the cold-row consequence**. Naming specific rows fails when a row goes unreadable between two passes of the same instrument. |
| **M-9 · state the frame** | 2026-08-27 | `cp-d-routing-conferral` ruling | A conferral must state the frame it assumes and name what would falsify it. Otherwise it spends the owner's attention on a detail and launders the assumption underneath. |
| **M-10 · rehearse in a worktree** | 2026-08-19 | `r00-lineage-writer`, "henceforth required" | Prepared scripts are rehearsed in a throwaway worktree, transcript retained. Measurement branches live in worktrees; **nothing reverts on the strength of a contaminated run** (`r04-collapse-m1` ruling 8). |
| **M-11 · pin the tree** | 2026-08-21 | `r04-collapse-m1` ruling 7 → §6.10 | A gate run must pin its tree, not just its recipe. |
| **M-12 · declared order, never `tx_time`** | 2026-08-18 | `r00-census` Q4 | Never order across sources on `tx_time`. A fold that needs a cross-source order **declares** one. |
| **M-13 · never auto-drop** | 2026-08-19 | `r00-lineage-writer` Q3 | `malformed` keys stay queued. No N-pass auto-drop, ever — "a timer-shaped policy concealing a deletion". |
| **M-14 · segment the stream** | 2026-08-26 · 2026-08-31 | `cp-a-aggregate-conferral` Q4 (= `r18-aggregate-cp-a`); `r33-instrument-defects` RC-1 | A verdict on something that is not the quantity being learned is **recorded, not folded**. Applied to aggregate verdicts, to `regime="miss"` coverage failures, and to governance decisions in `DECISIONS.md`. |
| **M-16 · no landing branch sits behind `origin/master`** | 2026-08-31 | owner, standing instruction | After every merge, fast-forward local `master` and remove the merged worktree and its branch. A branch **intended to land** is never left behind the remote. **Declared exception: measurement branches** (`run11-minus-nullread`, `run12-minus-69`, and any successor) — `r04-collapse-m1` ruling 8 requires them to live in worktrees and **never merge**; they are permanently unmerged by design, not neglect, and a future session must not "fix" them. |
| **M-17 · never stop; decide or interview** | 2026-08-31 | owner, standing instruction | Open work is executed, not reported back. Escalate **only** when the fork cannot be decided from the stated objectives — i.e. it is §5 residue — and then **interview** (`AskUserQuestion` with priced options and a recommendation), never a paragraph. "Blocked" means the objective cannot decide it, not that it is expensive or irreversible. |
| **M-18 · pin the comparison tree, not just the deciding tree** | 2026-08-31 | `r37-live-census` §6 | A criterion of the form *"rows whose action differs from run X must lie in set S"* is only about the lever if **run X's tree differs from the arm's by the lever alone**. r36's K3 named a set and a baseline and checked only the set: run 21's tree differed from run 20's by the lever **and** r33 **and** #127, and two of its three changed rows belonged to the other two. `M-11` pins the deciding tree; this pins the comparison. |
| **M-15 · passive preference learning** | design commitment | `core/utility.py` preamble | The agent **never probes preferences** until the governor can price the sequential value. Preferences arrive from owner behaviour and owner-initiated elicitation only. This is why §2's default is *decide and publish*, not *ask better*. |

## §2 Delegation — what does NOT come back to the owner

| id | date | source | what it determines |
|---|---|---|---|
| **D-1 · full delegation on PASS** | 2026-08-24/25 | `r07-recorded-replay` §4, `run13-join-conferral` §3, `r09b-sweep-conferral` §3, `r09c-sweep-conferral` §4, `run14-conferral` §4 | PASS on the frozen conjuncts ⇒ merge **and** deploy to live, no further keypress. Ruled five consecutive times on the recommended branch. |
| **D-2 · consequence defaults** | 2026-08-31 | r34 (generalising membrane-shadow §18) | PASS ships. **FAIL** reverts from the deploy path, publishes the FAIL report, and opens a successor pre-registration. A **second FAIL on the same frozen criterion** parks the lever, publishes why, and advances to the next queued item. No branch stops for a keypress. Supersedes the per-arc "FAIL ⇒ STOP for a ruling" of `r07-recorded-replay` §4 / `run14-conferral` §4. |
| **D-3 · decide, do not ask** | 2026-08-31 | r34 | A fork is resolved by this register → $0 evidence → the current utility posterior. A fork surviving all three is **decided and published** in `DECISIONS.md`, not escalated. Supersedes the "interview for every owner-side choice" practice. |
| **D-4 · the agent is a user** | 2026-08-30 | `r31-integration-gate` ruling 2 | The owner granted the coding agent **standing use of every surface the owner is invited to use**. Agent-origin asks are first-class evidence. |
| **D-5 · spend** | 2026-08-31 | owner, r34 | Spend is capped externally by Anthropic. Per-arc budget caps are retired; a priced run needs no budget keypress. |
| **D-6 · merge green PRs** | 2026-08-31 | owner, standing instruction | **A green PR that has been reviewed positively with no blockers may be merged without a keypress.** All three conjuncts bind: CI green, a review actually taken, and no blocker outstanding. A review is a review — a PR is not merged on green CI alone, and "no blockers" is a finding, not an assumption. |

## §3 Arc dispositions — standing

| id | date | source | what it determines |
|---|---|---|---|
| **A-1 · queue order** | 2026-08-30 | `conferral-2` ruling 4 | Levers from the Stage-4 measurement first, **then** proplang. The named risk — levers on the credence seam may be reshaped by the ruled successor — is accepted explicitly. |
| **A-2 · proplang is mandatory** | 2026-08-25 | `run14-conferral` ruling 5 (= `run17-conferral`'s direction); membrane-shadow §18 | Proplang is the ruled successor of credence at the decide seam: **gated-mandatory** (frozen bars pace the swap, FAIL = iterate, refusal retired) and **deferred**. Nothing in tree may presuppose the swap until it lands. |
| **A-3 · C gets no lever** | 2026-08-30 | `conferral-2` ruling 2, resolved by `r32-bar-reading` | The deployed bar p† = 0.8369 is *more* permissive than the declared 0.90, and only 2 of 70 abstains sit within 0.05 of it. C is a **dispersion** problem, not a threshold problem. Bar-move levers are closed; the bar itself is MONITOR ONLY (r33 A6). |
| **A-4 · carrier-side family closed** | 2026-08-25 | r10; `r09d-entity-anchor` | A terse gold carrier omits qualifiers, so **any** carrier-side requirement damps it — exact or fuzzy, hard or soft. The whole family is closed, as is any decide-side rule scoring documents by question-vocabulary overlap (r09d). |
| **A-5 · §6.11 licenses no code** | 2026-08-22 | `r05-carrier-identity` ruling 2 | Carrier identity is a standing *known-and-uncovered* source. A future grouping design does not inherit its BUILD — it needs its own pre-registration and its own priced run. |
| **A-6 · r06 criterion 8 frozen, unread-again** | 2026-08-22 | `r06-replace-branch` ruling 2 | Criterion 8's mechanical BUILD on S1/S3/S4/S5 stands as frozen with its noise-floor bound published beside it. Nothing was bought; it is not reopened, narrowed or re-scored. |
| **A-7 · r30b measured-dormant** | 2026-08-30 | `r31-integration-gate` ruling 1 | The interval claim stays in tree, entering the action set and losing the argmax. The `extra_actions` wire is generic infrastructure. Nothing reverts; nothing deploys. |
| **A-8 · extract-side entity field retired** | 2026-08-25 | `entity-key-conferral` ruling 2 | Retired from the queue. Re-opens only under its own pre-registration, and only for a reason specifically about extraction. |
| **A-9 · shape scales stay at 1.0** | 2026-08-29 | `conferral-1` ruling 1 | The `quantity` scale opt-in is declined; every shape ships inert. The units-lever arc (r28–r31) subsequently **closed** — r31 FAIL on K6, nothing deployed. |
| **A-10 · sequencing is continuous** | — | PRINCIPLES §9 as amended | Eval-gated, not dogfood-gated. Open the next checkpoint as soon as its preconditions are met. |

## §4 CARRIED AND UNSETTLED — RESOLVED 2026-08-31

Conferral 1 (2026-08-29) carried two items to Conferral 2 by name; Conferral 2 (2026-08-30)
took four rulings and addressed neither. Both were put to the owner on **2026-08-31** and both
are now ruled — see `G-1`…`G-3` below.

**A correction to this register's own first census, recorded rather than edited away.** The
first version of this section said `U-1` — the completion-audit definition and "DONE items 3–5"
— was wholly unsettled and blocked Arc C. **That was wrong.** It read conferral 1's
carry-forward and Conferral 2's silence, and did not check whether an intervening report had
closed it: **`r27` (K4) resolved the stage map on 2026-08-28** and `ROADMAP.md` carries the
resolved table (Stages 0–4; items 3–5 are Stages 3 and 4; "five" is the stage count, not an
item count). The register's own failure mode on day one was `M-7` in miniature — a census that
read two sources and inferred the state of a third. What was genuinely open was narrower, and
is ruled below.

| id | date | source | what it determines |
|---|---|---|---|
| **G-1 · Stage 2 is RETIRED from the completion programme** | 2026-08-31 | owner, interviewed | Stage 2 (Phase 1.6 items 4–5, the aggregate and thread families) is retired, not redefined. As written it could not close: specified as *builds* while `bayesian-foundations.md` §12 gives it *gates*; K1 deleted the aggregate family as "family routing in disguise"; the remainder dies with `/route` at migration M5, inside a stage ruled out of the programme. **Capability work is continuous and eval-gated under PRINCIPLES §9 as amended, so it needs no programme stage.** The thread transformations may still be built when evidence calls for them — never as a completion condition. The programme closes at Stages 0, 1 and 4. |
| **G-2 · the completion audit is DEFINED, and proplang opens after it** | 2026-08-31 | owner, interviewed | The completion audit is **a $0 reconciliation of the four disagreements `r26` recorded** — what Stage 0 consisted of; DONE item 1's wording; which numbering discharges the family stage; and what opens the proplang migration — read against this register, leaving one definition of record for each. It is not a new instrument and buys nothing. Once it reads, **Arc C opens** under membrane-shadow §18's own frozen bars (`A-2`). |
| **G-3 · the guard method is RULED** | 2026-08-31 | owner, interviewed | **A guard must name the universe it checked and fail when that universe is empty; and a control counts as a control only if removing what it controls for turns it RED — demonstrated by mutation, never asserted by shape.** Rows 12, 22 and 23 follow from it mechanically and G4 (the adversary pass) is unblocked. The rule is deliberately *semantic*, because all three of row 22's defeats worked by re-spelling a syntactic narrowing while the guard stayed green: a universe that must be **named and non-empty** cannot be silently widened or narrowed, since both change a reported number. |

## §5 The residue — what still reaches the owner

Exactly one class: **changes to the objective.** PRINCIPLES, the kernel, and the utility gauge
(`u_correct = +1`, `u_abstain = 0`). What the system is *for* cannot be learned from inside it —
the gauge is convention, not evidence, and no volume of reaction data identifies whether the
objective is the right one. The same applies when the ruled queue empties and the question is
what to build next, and to §4's two carried items.

Everything else — scope, sequencing, method, measurement design, consequence branches, FAIL
handling, spend — is derivable and is delegated.

*(Distinct from governance, and unchanged: acts that touch third parties or destroy data are
confirmed before they are taken. That is ordinary operating caution, not a keypress this project
owns.)*

## §6 Enacted and closed — history, not live rules

Recorded so they are not re-litigated, and so a reader can tell a closed ruling from a live one.

- **Appendix A SIGNED** (`appendix-a-conferral`, 2026-08-26, owner keypress) — PRINCIPLES §16 gains the three-verdict
  rule, §15 the no-space/policy-preference clause, §14 the module collapse. The collapse ladder
  is CLOSED.
- **§6.12 deployment block CLOSED** (2026-08-25, run 14 PASS; `run14-conferral`) — the parked tree merged and
  deployed; two standing wrong rows ride in production, priced and published.
- **M1 ACCEPTED, checkpoint closed** (`r04-collapse-m1` ruling 3, released via `r05-carrier-identity` ruling 3) — run 12 refuted
  the hold's live hypothesis. M1.5 unblocked and since DONE.
- **The null-read fail-open EXONERATED** (`r04-collapse-m1` rulings 1/5/6 → run 11) — master keeps it.
- **§6.9's declared probe order CONVICTED but NOT reverted** (run 12) — the old order was a
  luckier ticket, not a better rule.
- **§6.13 REPAIRED** (`r08-window-determinism`; scoped by `r07-recorded-replay` ruling 3) — the declared total order goes into the SQL before `LIMIT`.
  Commit-wobble floor 2, not 14.
- **The JOIN** — reverted after run 13's FAIL (r09), re-landed tempered (`r09b-sweep-conferral`, `r09c-sweep-conferral`, `r09d-window-conferral`, `r09d-disposition-conferral`), PASSED as run 14.
- **A2's grow-offer enactment REVERTED** (`r15-collapse-m5` ruling, option A; conferred in `run17-conferral`) — run 18 reproduced run 16, so
  run 17's collapse is attributed to the grow-offer alone. The successor arc ("ground the grow
  priors in the gather-outcome stream") is registered in foundations §14, not open.
- **The aggregate family DELETED** (`cp-d-routing-conferral` ruling, K1/`r22-k1-family-deletion`) — `decisions.FAMILIES` back to
  `{lookup, narrative}`. The question was mis-framed and the object it argued about is gone.
- **Instrument defects 1–5 + the bar-drift item FIXED** (`conferral-2` ruling 3 → `r33-instrument-defects`).
- **Reviewer rulings on the unified-ledger design** (2026-08-18/19) — `r00-census`,
  `r00-collapse-census`, `r00-lineage-writer`, `r01-design`, `r01-collapse-design`,
  `r01-lineage-sweep`, `r03-merge`, `r04-stocktake`, `r04-collapse-m1`: Q1–Q8, Q-R1–Q-R5
  and the Phase-A/B acceptances, all applied and folded into
  `docs/unified-ledger-design.md` and `docs/module-collapse-design.md`.
