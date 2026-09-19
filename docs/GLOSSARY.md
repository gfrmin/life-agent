# Glossary

This repo uses a private vocabulary consistently and almost never defines it. That is
cheap for the author and expensive for everyone else — a reader hits `fold`, `bar`,
`arc` and `conferral` in the first paragraph of any report and has to reconstruct four
meanings from context before reaching the argument. Term counts across `docs/`,
`CLAUDE.md` and `ROADMAP.md`: census 677, bar 647, act 616, fold 585, ruling 456,
seam 353, membrane 324, reach 299, probe 291.

Much of this vocabulary (rounds, rulings, conferrals, bars, readings) belongs to the
unification arc archived on 2026-09-19 (`archive/`); those entries describe history, not the
way work is run now (`CLAUDE.md`). Each entry gives the standard term where one exists, then
what it means *here*. When
a standard term exists, prefer it in new prose and keep the local word only where it
carries something extra.

## Decision layer

| Term | Standard term | Meaning here |
|---|---|---|
| **act** | action | A decision the engine can take. The declared set is report / report_scoped / hedge / ask_clarify / abstain, plus interval rows (r30b). |
| **effector** | chosen action | The action the daemon returned for one question. |
| **atom** | outcome / support point | One element of the K candidates + NONE simplex the posterior lives on. |
| **bar** | decision threshold | The credence above which asserting beats withholding. Derived, not set: `-u_wrong / (1 - u_wrong)` (`gate.py:317`) — **0.8369 under the reaction-conditioned estimate, 0.9000 under the elicitation-only estimate; the gate uses the elicitation-only value and quotes **INCONCLUSIVE** when the measured reach falls strictly between them (RULED 2026-09-05, M-34/GD-29)**. |
| **gauge** | utility normalisation | The two pinned latents `u_correct = +1`, `u_abstain = 0` (`utility.py:54`). Everything else is measured relative to them. |
| **reach** | coverage | Whether the system can answer at all — as opposed to whether it answers correctly. |
| **dispersed** | low-confidence abstention | Withheld with candidates present and a real posterior that did not concentrate. |
| **miss** | retrieval failure | Withheld with no grounded candidate at all. |
| **unavailable** | out-of-corpus | The corpus on this machine cannot answer; censored from Δ because it measures the corpus, not the policy. |
| **correct_premise** | premise correction / presupposition failure | **Proposed, not built, not enabled.** States that the question presupposes something false. Feasibility-gated by a premise detector, flat over the answer simplex. Archived spec: `archive/docs/DR-DECISION-1-action-space-and-utility.md` §3.5. |
| **escalate** | deferral / routing to oracle | **Planned (J1–J2), not built.** Hand the question to a priced escalation rung. `MODEL.md` §4; archived spec `archive/docs/DR-DECISION-1-action-space-and-utility.md` §4.1. |

## Evaluation

| Term | Standard term | Meaning here |
|---|---|---|
| **typed** | the system under test | The structured retrieval + decision arm. |
| **mono** / **π\*** | baseline | Raw Claude Code with corpus access. π\* is the owner's *outside option* — what they'd do instead. |
| **arc** | workstream | A related run of rounds pursuing one hypothesis (e.g. "the equivalence arc"). |
| **round** (rNN) | experiment | One pre-registered change plus its reading. `archive/docs/unification/rNN-*.md`. |
| **reading** | results / analysis | The post-hoc interpretation of a round, written against its pre-registration. |
| **census** | descriptive survey | Counting a population without testing a hypothesis (e.g. the answer-shape census). |
| **band** | credence bucket | A slice of the credence range, e.g. "the 70–90 band". |
| **kill** | falsification | A pre-registered predicate that came out negative. A "KILL" is a hypothesis dying, and is a success of the instrument. |
| **pin** | regression test / golden | An exact expected value frozen in a test so drift fails loudly. |
| **poison fixture** | negative test | A deliberately-broken input that must be rejected; proves the guard is live. |
| **positive control** | mutation check | A test that must FAIL, proving the harness detects failure. |

## Governance

| Term | Standard term | Meaning here |
|---|---|---|
| **ruling** | precedent / ADR | A standing decision that bound later rounds (archived: `archive/docs/unification/RULINGS.md`). |
| **conferral** | elicitation session | A recorded exchange where the owner supplies a judgement the model cannot derive. |
| **sitting** | review session | A structured pass over a milestone, usually adversarial. |
| **readout** | report | The written output of a sitting or round. |
| **seam** | interface / boundary | The single point where two subsystems meet. "The one act seam" = all commits go through `core/seam.py`. |
| **fold** | aggregation (a left fold) | Reducing an event log to current state. Also "the rows Δ folds" = the rows included in the aggregate. |
| **lane** | code path | One of several parallel routes through the system (the typed lane, the narrative lane). |
| **spine** | orchestration loop | The autonomous loop that would run the system proactively. **Does not exist yet.** |
| **membrane** | sandbox / shadow harness | The env-gated seam where proplang runs as a passive shadow. Byte-inert by default. |
| **reland** | re-apply | Re-introducing a reverted change under a new pre-registration. |

## Terms that mean something non-obvious

- **"the one X"** — a deliberate single-source-of-truth constraint. "The ONE mapping",
  "the one written atom". Treat as: *do not add a second implementation of this.*
- **"byte-identical"** — a change that provably does not alter any archived output.
  Used as the acceptance criterion for refactors.
- **"priced"** — given an explicit cost in utility units, so it can be compared in an
  argmax. "The oracle price" is the utility cost of consulting, not a dollar amount.
- **"witnessed"** — demonstrated on specific recorded cases, explicitly *not* proven.
  When a doc says "witnessed, not proven", it is flagging the weaker claim on purpose.
- **"registration" / "pre-registration"** — criteria committed to before the data is
  seen. A result not covered by a registration is labelled "unregistered probe".

## Decision-record back-links

`DR-<AREA>-<n>` names a decision record from the unification arc. Code may still cite one
inline; the records are archived, and `MODEL.md` is the current design authority:

- **DR-DECISION-1** — `archive/docs/DR-DECISION-1-action-space-and-utility.md`: the action
  space and the utility over it, the lane classifier, escalation as a ladder, and what
  provenance must survive an escalation. Distilled into `MODEL.md`.
- **DR-UTILITY-1** — `archive/docs/DR-UTILITY-1-graded-multiattribute.md`: the gauge record
  and errata.
- Open questions and provenance: `archive/docs/OPEN-QUESTIONS-utility.md`,
  `archive/docs/SESSION-RECORD-2026-09-05.md`.
