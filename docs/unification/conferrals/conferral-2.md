# Conferral 2 — the Stage-4 exit measurement reads (2026-08-30)

Evidence, options and prices, written BEFORE the interview (house rule). Every number here is
$0 arithmetic on artefacts already on disk — the decision log, the reaction stream and the
round manifests. Nothing was bought to produce it.

**The stopping rule fired.** Under the owner-ruled VOI stop (PR #120) the measurement closes
when two consecutive rounds of >=8 mixed-class asks add no new failure signature AND keep the
dominant-class ranking. Round 7 read dry; **round 8 read dry**; the measurement is **CLOSED at
69 lifetime asks on 2026-08-30**, six days inside the 2026-09-05 hard cap. Eight rounds ran,
each under a manifest frozen and hashed before its first ask.

**The headline number: zero wrong commits in 69 asks** — including on the strongest miscommit
trap built during the measurement (a question whose answer does not exist, with a plausible
wrong value sitting adjacent to the very field label the question names, in four documents).
The system's failure mode is uniformly *silence*, never *error*. That is the calibration
property the typed arm was adopted for, and it held across every round.

---

## 1. What the 69 asks say, by class

| class | instances | what it is | where it kills |
|---|---:|---|---|
| **C** gold-leads-below-bar | 13 | the right answer leads the posterior and the bar refuses it | decide |
| **norm** value-equivalence | 12 | one answer split across spellings, or one passage split across paraphrases | decide |
| **B** narrative inclusion | 9 | claims proposed, none included | decide |
| **pollution** retrieval | 7 | the target document is outside the top-k | retrieve |
| **A** grounding gap | 5 | grounded evidence exists but is not admitted | extract |
| **computed** | 4 | the answer must be derived, not quoted | mixed |
| **E** upstream fragility | 1 | one 5xx kills the whole ask, no retry anywhere on the path | transport |

**C and norm together are 25 of 51 classified misses — half.** Both are decide-layer, both are
about *equivalence*, and neither is a retrieval or extraction problem. This is the measurement's
central result and it has been stable since round 4.

**A is effectively closed.** Five instances, none since round 4, and contradicted three times in
round 5. Treat it as a per-document coverage property, not a gate defect.

---

## 2. The four findings that changed during the measurement

These are the reads that a shorter measurement would have gotten wrong. Each is recorded with
its refutation in `$LIFE_AGENT_KB/FAILURES.md`.

**(a) The commit boundary is empirically bracketed, and it sits BELOW the declared bar.**
Round 8's boundary rows, from the decision log:

| leader credence | p_none | n_obs | action | recorded EU |
|---:|---:|---:|---|---:|
| 0.943 | 0.057 | 2 | report | +0.615 |
| **0.875** | 0.125 | 3 | **report** | +0.152 |
| **0.828** | 0.172 | 2 | **abstain** | 0.000 |
| 0.650 (r7) | — | 6 | abstain | 0.000 |

The declared exchange rate is 10:1, i.e. an unqualified current-value claim asserts only above
**p\* = 0.90** (`utility/model.yaml`, owner-declared 2026-06-18). A report was nonetheless
issued at leader credence **0.875**. That is either the scoped/hedged branch legitimately
pricing lower — the action set on every row is `{report, hedge, ask_clarify, abstain,
report_scoped}` — or a bar leak. **This conferral does not resolve which, and deliberately did
not open an arc to find out** (r07's cap: anomalies en route are disclosure items). It is
item 1 for ruling: whether it gets its own pre-registered $0 reading.

**(b) The norm class is not a marginal-bar problem — it is an equivalence problem, and the
mass proves it.** Round 8's sharpest instance held back three spellings of one correct answer
summing to **0.750 with zero competitors on the board**. A second held the gold's two spellings
at **0.472** against a best competitor of 0.098, across 249 carrier documents. Merging either
would clear any bar in the bracket above. **The canonicaliser's boundary is now characterised
from both sides:** connector and punctuation variants between tokens MERGE; **affix** variants
SPLIT — currency symbol, unit suffix, thousands separator, currency-code placement and
country-code prefix, five types across rounds 7 and 8. Carrier multiplicity does not rescue it.

**(c) The narrative class is reachable, and its reachability rule was wrong twice before it was
right.** Round 6 concluded B was near-unreachable; round 7 reached it with prose phrasing and
concluded prose was the key; round 8 refuted that — the same prose phrasing routed lookup, while
a *counting* question routed narrative. **The rule is answer SHAPE, not phrasing: a question with
no typed answer shape reaches narrative.** When reached, B has killed 9 of 9 lifetime, and its
signature is a constant to the digit across four rounds spanning the whole measurement
(coverage 0.529, n=13). It is a real defect on a real slice, not an artefact.

**(d) Counting is not shielded by retrieval.** Two rounds concluded the counting sub-shape died
upstream and could never be seen by the decide layer. Round 8 built a probe on a string that is
unique to one document on the lattice, retrieval behaved, and the question died at narrative
inclusion instead. The earlier deaths were vocabulary artefacts.

---

## 3. Instrument defects found in the measurement itself

Recorded because they bear on how much weight the numbers carry.

1. **A carrier census taken from ONE spelling of one string is wrong** — four rounds running.
   Round 8 mis-stated two of its own nine golds this way (one claimed multiplicity 2 where a
   "carrier" was a substring inside a numeric coordinate array; one claimed a sole carrier where
   a second genuine document led retrieval). Both were caught before grading, published, and did
   not touch a gold value. **Any successor census must sweep spellings AND exclude substring
   hits.** This is the same class as the standing lesson that a census must read the deployed
   rule end-to-end rather than re-implement the constant it prices.
2. **Unfoldable misses: 6 sightings.** A lookup that grounds nothing writes no decision row, so
   the reaction stream cannot price the class. Round 8 produced the first unfoldable on a
   *correct* outcome — the system got the honesty trap right and cannot be credited for it.
3. **Narrative rows log `cost_usd: null`**, so every round's cost is a lower bound.
4. **`none-of-retrieved` reads 0.000** on exactly the rows where nothing was admitted, which is
   also how a true absence looks. The honesty trap therefore came out right for the wrong
   reason: the system cannot presently distinguish "this does not exist" from "I found nothing".
5. **Signature E**: `ask_client.post_json` is the one transport on the ask path and has no
   retry, backoff or 5xx handling. One transient upstream error kills an ask outright. Seen
   once live; it is a production defect, not an eval artefact.

---

## 4. What is on the table

$0 counterfactuals first, per the house rule. **Nothing below has been built** — the standing
ruling froze all construction until the measurement read, and it has only just read.

| # | candidate | what it targets | instances it could reach | why it is cheap or not |
|---|---|---|---:|---|
| 1 | **value-norm canonicalisation** (affix-aware equivalence at the extract/decide seam) | norm | 12 | the five splitting affix types are enumerated and each is a lexical rule; the merge side already works, so the change is to widen an existing predicate, not invent one |
| 2 | **narrative inclusion calibration** | B | 9 | the kill is one constant across four rounds; a per-cell recalibration is the registered §7 path |
| 3 | **the bar reading** (item 1(a) above) | C | 13 | $0, reads the deployed rule on rows already on disk; must be pre-registered |
| 4 | **transport retry** | E | 1 | small, contained, and a live-traffic defect rather than an eval one |
| 5 | **unfoldable rows get a record** | measurement itself | 6 | without it the reaction stream is structurally blind to a whole class, in both directions |

**The hard clause stands and binds every one of them: no lever ships while it makes a named
wrong-commit class worse.** With zero wrong commits in 69 asks, the baseline that clause
protects is currently perfect, which raises rather than lowers the bar on candidates 1 and 2 —
both of them *admit* answers that are presently withheld, and admitted answers are the only way
a wrong commit can enter.

---

## 5. Items for ruling

1. **Does the 0.875 report against a declared 0.90 bar get its own pre-registered $0 reading?**
   (Disclosure item today, not an arc.)
2. **Which candidate opens first**, and does it open as a pre-registered build or as a further
   $0 reading?
3. **Does the C class get a lever at all**, given that 13 instances are "the bar refused a
   leading correct answer" and the bar is the thing that has kept 69 asks free of wrong commits?
   This is a genuine preference question about the owner's exchange rate, not a defect report.
4. **Is the measurement's closure accepted** as the Stage-4 exit read, and does Stage 4 close
   with it?
5. **Do the five instrument defects in §3 get fixed before any successor measurement**, or are
   they carried as published caveats?

---

## 6. RULINGS (owner, interviewed 2026-08-30)

Four rulings taken. The interview was held on the evidence above, which was written and
committed in full before any option was put.

**RULING 1 — the $0 bar reading opens first.** Item 1 is not carried as a disclosure: it
becomes **r32**, a pre-registered $0 reading of why a report was issued at leader credence
0.875 against a declared p\* = 0.90. Rationale: the house rule puts $0 counterfactuals ahead
of builds, and this reading is a *precondition* for the largest class — if the deployed bar is
not the declared bar, some of C's 13 instances are a leak rather than a preference, and the
C question would otherwise be decided on the wrong premise. Nothing is built by r32.

**RULING 2 — the C class is HELD, not decided.** Whether C (13 instances, "the bar refused a
leading correct answer") gets a lever at all waits on r32's verdict. If r32 reads PRICED, C is
the bar working as declared and the question is a pure preference about the owner's exchange
rate; if it reads LEAK, C is partly a defect and the lever question re-opens under its own
pre-registration. Deciding now would decide before the premise is known.

**RULING 3 — all five instrument defects in §3 are fixed BEFORE any successor measurement.**
Not the two blinding ones only: all five. The measurement's numbers are the asset, and a
successor that inherits a single-spelling census, an unpriceable class, a lower-bound cost, an
undistinguishable absence and an unretried transport would produce a weaker read than this one
did. This is queued work, not a precondition for r32.

**RULING 4 — levers first, then proplang, in that order.** The Stage-4 closure is ACCEPTED as
the exit read. The next arc spends the measurement's own findings (the decide-layer equivalence
problem, half of all classified misses); the ruled-mandatory proplang migration opens after it.
The named risk is accepted explicitly: levers built on the credence seam are work the ruled
successor may reshape.

**Unchanged and binding on everything above:** the hard clause — *no lever ships while it makes
a named wrong-commit class worse* — against a baseline of zero wrong commits in 69 asks.

---

## 7. RULING 2 RESOLVES — r32 read the same day

[`r32-bar-reading.md`](../reports/r32-bar-reading.md): **PRICED**, $0. The deployed bar is
**p† = 0.8522** at the rows in question (0.8369 today), not the declared 0.90 — reproduced
3/3 on fold version, action and EU, with all four attenuation candidates refuted. The
declared 10:1 rate reproduces 0.9000 exactly *at the model prior*; the reaction stream is the
whole difference.

**Ruling 2 therefore resolves: C gets no lever.** Not because the bar is sacred, but because
the census says a bar move cannot reach the class — the window's highest abstained leader is
0.8282, below the deployed bar; the median is 0.3688; only 2 of 70 abstains sit within 0.05 of
it. **C is a dispersion problem, not a threshold problem**, which is the norm class's finding
arrived at from the other side. The lever that reaches C is candidate 1 (value-norm
canonicalisation), and the two classes are one problem, not two.

Registered by r32 and carried into ruling 3's work: **the measurement moved the bar it was
measuring** (0.900 → 0.837 while the ledger was collected), and the drift is monotone downward
because only abstain-verdicts fold and dogfood reacts `bad` to silence far more than `good`.
Its only brake is a wrong commit. This is a sixth item for §3's list, found after it was
written.
