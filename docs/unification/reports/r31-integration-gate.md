# r31 — the integration and do-no-harm gate — PRE-REGISTRATION (2026-08-30)

> **Committed BEFORE the run fires.** Move 4 of the roadmap approved 2026-08-29, as re-scoped
> by the owner's rulings of 2026-08-29 (r31a's RULINGS and `conferrals/conferral-1.md`).

## What this run IS, and what it is not

r31a already knows this lever's effect on this population, at $0: **predicted reach 0, predicted
`interval-excludes-gold` 0, exactly one changed row — a displacement on `q2-059` whose realised
utility falls 1.000 → 0.903, about −0.001 on the 104-question mean.** A priced run cannot
improve on that as a measurement of benefit, and **this report may not be written as one.**

What the sweep cannot exercise is the **integration**: the `extra_actions` wire, the daemon
ranking body-priced rows, the executor's refusal when a decider cannot rank them, the render, and
the whole path end to end under a live stack. That — plus the standing rule that an argmax change
never deploys unread (§6.12's closing precedent, run 14) — is what this run buys.

**Pop B is OUT** by owner ruling: the 15 computed questions have never produced a lookup-family
decision (all 15 recorded a narrative abstain; the fallthrough is at extraction, not routing), so
an interval claim has nothing to range over. The composition question that finding names is
PARKED with the exit week's FAILURES entries as its trigger.

**Scales stay at 1.0** by owner ruling: the `quantity` opt-in was declined until the exit week
forms the belief. So this run measures the claim space at the anchor price — deliberately.

## Frozen conjuncts

| | Conjunct |
|---|---|
| **K1** | **Integration.** The run completes against a live stack carrying the `extra_actions` wire: on every question where the lever can fire the payload carries the rows and the daemon echoes `n_extra_actions`. **Zero executor refusals** — a refusal means the deployed decider predates the wire, which VOIDS the run rather than failing it. |
| **K2** | **Zero NEW wrong commits**, baselined on run 18's typed arm: a wrong commit is NEW iff that row was not wrong in run 18 (run 14's precedent, carried). |
| **K3** | **Zero `interval-excludes-gold` commits** — the class r30b creates, counted from birth (r30b C6). |
| **K4** | **No named wrong-commit class worse than run 18** — the owner's hard clause. The two standing rows may ride; neither may worsen, and no new class may open. |
| **K5** | **The gate's own frozen bar**: P(Δ > 0.05) ≥ 0.90 under the production Ū, δ and level unchanged from every reading in the §14 series. |
| **K6** | **The sweep's prediction is met** (r31a S1): the set of rows whose action differs from run 18 is exactly `{q2-059}`. Any other row that moves is a finding to be disclosed and attributed, not narrated into agreement. |

**Registered expectation, on the page before the run:** PASS at ≈0.959, Δ̄ ≈ +0.513, one changed
row, Δ moving by roughly −0.001 against run 18. A reading materially away from that is itself the
finding.

## Frozen consequence

- **PASS on all six** → the §6.12-style block does not apply; **r30b deploys to live**
  (`bin/ask-live` / jarvis on the live box), and the **exit week starts** under the protocol
  signed at Conferral 1.
- **FAIL on any conjunct** → published append-only, **STOP for an owner ruling**. No deploy.
- **VOID (K1)** → the stack is wrong, not the tree; fix the stack and re-fire. A void run is
  reported as void and its numbers are not read.

## Budget

The typed arm cost $0.37 on run 18 and the comparator arm is a pre-recorded replay. **Cap $3.**
Fired as a transient `systemd --user` unit (the run-16 lesson: a priced run launched as an
agent-session background task dies with the session).

---

## BLOCKING DEFECT, found by firing r31 — and its frozen criteria

**Committed BEFORE the `src/` change that fixes it.** r31's first firing crashed on its first
question at `GET /utility` with

```
ValueError: unknown family 'aggregate' (declared: ['lookup', 'narrative'])
```

**It is not r30b's.** A plain `GET /utility` — no shape parameter, the pre-r30 URL — 500s
identically. The cause is in the ledger, not the tree under test:

- `$LIFE_AGENT_KB/calibration/decisions.jsonl` holds **3,391 rows: 2,459 `lookup`, 930
  `narrative`, and 2 `aggregate`** — written 2026-08-26 by run 19's aggregate arm.
- K1 (`r22`) then deleted `aggregate` from `decisions.FAMILIES`.
- `DecisionEvent.__post_init__` raises on an undeclared family, and `decisions.read()` builds
  every row eagerly — so **two rows of history make the whole log unreadable**, the utility
  fold dies, `/utility` 500s, and since that is the **first call of every executor pass**, the
  executor lane is dead on this box for every question.

Production may be unaffected — those rows were written here — but r27 V2 (production is
unobservable from the authoring box) means that is stated as unverified, not as reassurance.

**This is the integration value r31 was pre-registered to buy, delivered before it read a
single question:** no $0 instrument in this arc could have found it, because every one of them
reads archived artefacts rather than driving the live stack.

### The fix, ruled by the owner 2026-08-29

A **declared retired vocabulary**: the reader accepts it, no writer may emit it, and the skip is
NAMED. Chosen over a blanket skip-unknown because tolerance should be *enumerated* — a blanket
rule would also swallow typos and corruption — and over quarantining the rows, which would mean
mutating an append-only ledger, the one thing the event-sourcing discipline forbids.

| | Criterion |
|---|---|
| **R1** | `RETIRED_FAMILIES` is a declared closed set, DISJOINT from `FAMILIES`. RED under a mutation that lets a label sit in both. |
| **R2** | A writer still cannot emit one: `DecisionEvent(family="aggregate", …)` raises at construction. RED under a mutation that admits retired families at construction. |
| **R3** | `decisions.read()` accepts a retired-family row, skips it, and **names the count** — never silently. RED under a mutation that drops either the skip or the naming. |
| **R4** | A genuinely unknown family still raises on read. Tolerance is enumerated, not blanket. RED under a mutation that skips every unrecognised label. |
| **R5** | On the live log: 3,391 rows read as 3,389 folded + 2 named skips, and `GET /utility` returns 200. |

### The class, registered

This is the **second** append-only stream in this arc poisoned by a vocabulary that was retired
after the rows were written — r29's rider names the same shape for the gather-outcome stream,
contaminated by run 17 and pooled permanently with no policy segmentation. Registered as a named
open item with both instances as its evidence: **an append-only stream outlives the vocabulary
that wrote it, so every retirement must say what happens to the history that used it.** The next
retirement is to be designed, not discovered.

---

# r31 — RESULTS (2026-08-30, $0.24) — **FAIL on K6**

`gate-20260830T012730`, tree `1d11560`, 104 questions, 42 deliberates fired (all warm).

## The headline numbers, and why they are not the finding

| | |
|---|---|
| P(Δ > 0.05) | **0.959** (bar 0.90) |
| Δ̄ | **+0.515** [+0.076, +1.000] |
| typed | 0.61 answer rate · wrongs `{q2-018, q2-071}` — the two standing rows, unchanged |
| π\* | 0.97 answer rate |
| spend | **$0.24** |

Against the expectation registered before the run (PASS ≈0.959, Δ̄ ≈ +0.513): the verdict and
the Δ land where predicted. **That is not the reading.**

## The conjuncts

| | | |
|---|---|---|
| **K1** integration | **PASS** | zero executor refusals; the wire carried body-priced rows and the daemon ranked them |
| **K2** zero NEW wrong commits | **PASS** | wrongs are exactly run 18's `{q2-018, q2-071}` |
| **K3** zero `interval-excludes-gold` | **PASS, vacuously** | **zero interval claims were committed at all** |
| **K4** no named class worse | **PASS** | |
| **K5** the frozen bar | **PASS** | 0.959 ≥ 0.90 |
| **K6** the sweep's prediction | **FAIL** | predicted `{q2-059}`; observed `{q2-015, q2-049}` |

**Frozen consequence enacted: STOP for an owner ruling. Nothing deployed.**

## What actually happened: the interval is dominated on both sides

The lever was priced on exactly the 5 rows r31a predicted — the population was right. **The
argmax chose it on none of them.** Reading the run's own recorded posteriors:

| row | k | p_none | acted | best interval EU | abstain EU |
|---|---:|---:|---|---:|---:|
| q2-004 | 5 | 0.105 | abstain | **−5.69** | 0.00 |
| q2-029 | 5 | 0.409 | abstain | **−7.02** | 0.00 |
| q2-056 | 7 | 0.409 | abstain | **−6.72** | 0.00 |
| q2-090 | 6 | 0.263 | abstain | **−4.49** | 0.00 |
| q2-059 | 2 | 0.071 | **report** (EU 0.218) | +0.195 | 0.00 |

**The structure, stated plainly:**

- Where the posterior is **dispersed**, the interval loses to *abstain*, and not marginally —
  by 4.5 to 7 gauge units. Two forces stack: a wide candidate spread pays the Winkler width
  term, and the NONE atom pays `u_wrong` at a mass of 0.26–0.41 (≈ −2.4 to −3.7 on its own).
- Where the posterior is **sharp**, the interval loses to the *crisp report* — on q2-059, its
  best row, it was genuinely competitive (+0.195 against abstain's 0) and still came second to
  the report at 0.218.

**There is no region between them where an interval wins.** That is a structural result about
the claim space under this gauge, not a shortage of population — and it is a better
explanation of r30b's inertness than r31a's 5-of-104 count was.

## Why the sweep predicted wrongly — attributed, not narrated

r31a's deviation 3 named the limitation that produced this: the sweep prices the **in-process
action table** with the **archived flat Ū** (`u_wrong` −8.9993), while the live lane decides on
the daemon's fuller action set under the **live Ū** (`u_wrong` ≈ −8.71 after the reaction fold).
On q2-059 that gap is the whole story: the same row, priced two ways, ranks the interval first
in one and second in the other.

The two rows that *did* move, `{q2-015, q2-049}`, sit inside the standing §6.13
commit-wobble floor of **2** — and `q2-049` is one of the two rows r31a's own S0 control had
already flagged as unreproducible. So K6's observed set is consistent with noise plus a
row the instrument had already disclaimed; it is not evidence of a second lever.

**K6 did its job.** A conjunct that only checked the verdict would have recorded a clean PASS
and shipped a lever that never fires.

## Disclosures

1. **`decider_git` is null for this run.** The §6.10 rider I added records
   `"CREDENCE_DIR unset — the decider's tree is unpinned for this run"`: the fire script sets
   `credence=` locally but never exports it. The pin honestly recorded its own ignorance rather
   than guessing, which is what it was built to do — but r31's record cannot name the decider
   tree. One-line fix (`export CREDENCE_DIR`) before any successor run.
2. **The first firing was stopped by the operator on a mis-read clock**, not by a stall. It had
   run 2.5 minutes and written 2 decisions — run 18's exact rate. Recorded because the stop
   also produced an owner interview framed on a premise that did not exist.
3. K3 passes **vacuously**. It must not be quoted as evidence that interval claims are safe;
   nothing exercised the class.
