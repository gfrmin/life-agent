# r51 — an external labelled corpus for §18's evidence problem — READ: **X1 KILLs**, nothing is built

**2026-09-06 · $0 · no build, no run · tree `401c494` · corpus `Jingbiao/ATM-Bench` at HF revision
`78e826dc07e97466b2f54443831ef9a83ab8b27c`, evaluator `JingbiaoMei/ATM-Bench` at `ef4e5dff`.**
Pre-registration frozen `62a880f` before the download, amended once before it (Amendment 1, line
pins) and once after the recon (Amendment 2, this reading). The recon instrument is a
counts-only script run in the project environment against the pinned upstream detector; no
question, answer, email field or id was printed, and none is quoted here.

> **Verdict.** The email-only, `number`-typed population of ATM-Bench is **198** questions
> against the frozen X1 bar of **200**, so **X1 KILLs by the letter** and, by the frozen branch,
> **nothing is built and the checkpoint closes as *cannot move the supply*.** Its ground holds
> more strongly than the bar expressed it: the unit the harness folds is a verdicted DECISION,
> and the owner's own log shows exactly **one decision per question per pass** on every gate run
> — so a pass over this corpus yields at most 198 verdicted ticks, **≈ 0.8× `r49`'s 238, not the
> ~10× the pre-registration claimed**. The 10× counted the corpus's 1,013 QA pairs as ticks and
> assumed most were usable; both were wrong, and `r49`'s own 238 / 141 already carries ≈ 1.7
> passes of the same questions, which the engine's fold treats as independent rows. Registered
> as `M-35`: size a supply in the unit the instrument folds.

## 1. What was asked

`GD-28` closed B because the verdict supply binds every evidence-side lever on §18's bar, and
`A-11` filed the pooled-prior hypothesis on proplang (#26) from 238 ticks / 141 questions. The
owner chose (`A-12`, `conferrals/external-corpus-conferral.md`) to read that hypothesis on an
external, public, labelled corpus at ~10× the supply, with the A3 differential and the
`u_wrong` curve as by-products. The pre-registration froze the population (QA whose evidence
ids are all emails), gradeability (the benchmark's own answer-typed `detect_qtype` = `number`),
the verdict path (the benchmark's own matcher, vendored), K = 10 folds, leader-credence decile
cells, X1–X10, eleven predictions and six branches — and X1 as the recon KILL: **≥ 200**
email-only `number`-typed QA, "≈ 2× the owner's 104".

## 2. The recon (counts only)

Downloaded 2026-09-06 with `snapshot_download` restricted to `data/raw_memory/email/*` and
`data/atm-bench/*.json` (≈ 5.5 MB; revision recorded beside the files in `REVISION.json`; the
files live under the owner's data volume, outside every git tree, and are never committed).

| what | count |
|---|---:|
| emails (`{id, timestamp, short_summary, detail}`; ids unique, all `email`-prefixed) · unparseable timestamps | 6,742 · 0 |
| QA, main set (`{id, question, answer, evidence_ids, notes, qtype}`) | 1,013 |
| QA, hard set (same keys) · of which email-only · of which `number` | 31 · 2 · 0 |
| evidence sets: media-only · email-only · mixed | 632 · 381 · 0 |
| `detect_qtype` over ALL 1,013 answers: number · list · open (**X3e**) | **360 · 139 · 514** |
| released `qtype` field vs the detector, disagreements | 0 of 1,013 |
| `is_abstention` over ALL answers · over email-only (all `open_end`) | 23 · 14 |
| **email-only ∧ `number` (X1)** · open · list | **198** · 182 · 1 |
| lane (`classify(question).space`) over the 381 email-only: exact · quantity · set · threshold | 274 · 104 · 2 · 1 |
| type × lane on email-only: number\|exact · number\|quantity · open\|exact · open\|quantity · open\|set · open\|threshold · list\|exact | 119 · 79 · 154 · 25 · 2 · 1 · 1 |
| evidence ids per email-only QA: 1 · 2 · 3 | 358 · 16 · 7 |
| "Today is …" anchor present, email-only `number` questions | 74 of 198 |

**Three things the files say that the frozen doc did not.** (i) The released schema carries a
`qtype` field (and an empty `notes` field) — the pre-registration's recon disclosure said it
did not, on the strength of `docs/data.md`; the field agrees with the detector on every row,
so the frozen rule (detector) and the benchmark's own rule (field first, detector fallback) are
the same rule here, and X3e is met exactly. (ii) The corpus has 6,742 emails and 31 hard rows
where the paper prints 6,741 and 25; the hard set has no email-only `number` row, so it moves
nothing. (iii) Abstention rows number 23, not 25, none of them `number`-typed.

## 3. Why the KILL holds — the unit of supply

`p3_gate.py`'s `keyed_verdict_replay` folds one tick per verdicted DECISION. On the owner's log,
every gate run since 2026-08-17 records **exactly 1.00 decisions per question** (102–103
questions each, `lookup` family only); `r49`'s 238 ticks over 141 questions are therefore
several runs' decisions on overlapping question sets, and the Claude verdict channel's 180
verdicts cover 74 distinct questions. One executor pass over the external corpus posts at most
one decision per question: ≤ 198 on the gradeable set, fewer after the eligibility filter
(non-empty candidates). Repeating the pass multiplies rows, not evidence — the same question on
the same corpus — and the fold cannot tell the difference. So even at 200 the corpus would have
supplied ≈ 0.8× `r49`'s ticks, and the "~10× n" that justified the checkpoint was never
available from this corpus's email modality. The KILL is right in letter and in ground.

## 4. Blind predictions, scored

| id | predicted | read | disposition |
|---|---|---|---|
| P1 | email-only ∧ `number` ∈ [120, 240] | 198 | **confirmed** (the interval contained the KILL bar, by design) |
| P1′ | `detect_qtype` reproduces 360 / 139 / 514 within ±5% | exact | **confirmed** |
| P2 | lane `quantity` on ≥ 60% of gradeable rows | 79 / 198 = 40% | **refuted** — the regex reads `exact` on three of five number-typed answers |
| P9 | ≤ 10 email-only abstention rows | 14 | **refuted** |
| P3–P8 | (need a run) | — | unread; no run was bought |

P2 is the reading worth keeping: on an answer-typed reference the lane regex under-calls
`quantity` more than the pre-registration expected, in the direction `core/answer_shape.py`
already documents (toward `exact`).

## 5. Consequence enacted

The X1 branch, as frozen: **no build; the recon counts published; the checkpoint closes as
*cannot move the supply*.** Nothing in `src/` changed — the `claude_verdicts.py` docstring
clause named for `M-3` was never made; the vendored evaluator, the k-fold harness, the gold
writer and the KB builder were not built (their designs stay in the pre-registration as the
build it *would* have licensed). No proplang comment (the branch says nothing). No production
unit touched; the owner's KB was not read beyond aggregate counts of its decision and verdict
logs. The corpus stays on-machine under its licence for any successor. `GD-31` records the
closure; `GD-30`'s reaction points at it.

## 6. What remains — named, for the owner

The ruled queue is empty again and `RULINGS` §5 says what to build next reaches the owner.
`conferrals/r51-successor-conferral.md` carries the evidence and four priced options: a 1×-n
replication on the 198 (the u_wrong curve and the first A-CAL reliability read on a public
corpus, without an answer to #26's small-n objection); a $0 recon of corpus pooling toward ~1,000
questions; the verdict re-supply on the owner's 104 unverdicted questions; a hold.

## 7. Method notes

- Every number above is a count or a cross-tab; the recon script prints keys, lengths and
  counters only, and was run once against the downloaded files.
- The pinned evaluator was exercised through an import shim in the session scratchpad (the two
  vendorable modules plus the seven-phrase constant, byte-copied from the pinned sha); nothing
  from it entered the tree.
- Amendment 1 (before download) corrected the evaluator line pins the plan's revision 3 had
  got wrong; the lesson — a line pin is verified only by a raw fetch at the sha — is in the
  amendment, not the register (not a governance rule).
- A process deviation, disclosed: the first attempt to write this closure ran in the main
  checkout because the worktree directory had not been renamed with its branch; the tracked
  files there were restored to HEAD and the edits moved here before anything was committed.
