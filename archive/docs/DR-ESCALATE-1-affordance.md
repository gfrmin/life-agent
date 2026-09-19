> **SUPERSEDED by `DR-DECISION-1-action-space-and-utility.md`** (2026-09-05).
> The action space and the utility over it are not separable — a preference cannot be
> stated about an option that does not exist — so this document was folded into the
> consolidated decision-problem spec as §3–§4 (action space, escalate ladder, pointer floor). Kept only for its
> working; read DR-DECISION-1 instead.

# DR-ESCALATE-1 — the escalate affordance, and pointer-to-source as the floor

**Status:** specification. No implementation.
**Depends on:** `DR-UTILITY-1-graded-multiattribute.md` (the gauge and cost model).
**Blocking questions:** `OPEN-QUESTIONS-utility.md` — OQ-0, OQ-2, OQ-4, OQ-5, OQ-8.
**Citation policy:** symbols are load-bearing; line numbers are hints, verified against
local `master` 2026-09-05 and expected to drift.

## 0. Gauge-independence

Everything here is specified so it holds **whichever way OQ-0 rules**. The ruling
changes *when* the affordance fires, never *what it is*. Two places the spec would
differ are flagged inline as **[OQ-0]**; there are no others.

The affordance is worth specifying under either ruling, because the defect it fixes is
structural: **there is no escalate action in the action set at all.** At the deployed
boot Ū the preference to consult already exists and has nowhere to act; at the
elicitation Ū the preference does not yet exist but the affordance is still the thing
that would carry it once OQ-1 moves the number. Building the action is not a bet on the
ruling.

## 1. What escalation is

A priced action that hands one question to an external answerer and returns its answer,
instead of asserting from our own posterior or staying silent.

**Crucially it is not a second decision procedure.** It is one more row over the
existing K+1 simplex (K candidates + NONE), valued by the same `u_assert`
(`decide.py:64`) as every report row, ranked by the same argmax. This is the mechanism
r30b already proved when it added interval rows: one declaration, both decide surfaces,
no daemon arithmetic of its own.

**The escalate row is flat over the simplex.** The oracle is not reading our candidate
list, so its value does not vary by which of our candidates is true. That flatness is
the whole reason escalation can rescue a `dispersed` row (`gate.py:99`): it is the only
action whose value is independent of the posterior that failed to concentrate.

## 2. Host-side versus wire — the division that motivated this spec

The owner's correction stands and governs the design: **the host owns preferences, the
language owns inference** (`../proplang/appendage-spec.md`).

| Concern | Where it lives | Why |
|---|---|---|
| Which rungs exist, and their prices | **host** | A preference, not an inference |
| Multi-attribute scalarisation ($, latency, disclosure → one number) | **host** | The wire carries one scalar; `Expr` has no product sort |
| The SEALED prohibition | **host** | Enforced by withholding the menu name for that tick |
| Which rung the argmax picks | **wire / engine** | This is inference |
| The oracle's reliability | **learned by the engine** | See §4 — never asserted by the host |

What crosses the wire is therefore: a menu name with a grid (one point per rung), a
scalar utility sentence per row, and — for the reliability model — an ordinary guard on
the writable name. Nothing else. **No protocol change is required**; the appendage spec
prices this at 0h of proplang work.

## 3. The menu row

Declared once at handshake, published per tick. Under the current life-agent world
declaration this is a second writable name alongside the existing one
(`world.py`, `AFFORDANCES`), or additional grid points on the existing name — either is
protocol-legal, and the choice is ergonomic, not semantic.

```
escalate : grid = [E1, E2, E3]        # one point per rung; see OQ-8 for the rung set
```

Row value, per rung r:

```
EU(escalate_r) = u_assert(p_r)  −  λ$·c$(r)  −  λt·ct(r)  −  λp·d(q, r)
```

- `u_assert` is the existing atom (`decide.py:64`) — **not a new valuation rule.**
- `p_r` is the rung's *estimated* reliability (§4), never a constant. Contrast
  `_ORACLE_P = 0.9` (`lookup.py:200`), which is a fixed prior for the owner-as-oracle
  `ask_clarify` row and is the pattern to *not* repeat for a machine oracle whose
  accuracy is measurable.
- `c$`, `ct`, `d` are the three cost attributes from `DR-UTILITY-1` §3.2: metered
  dollars, latency seconds, and disclosure count. All scalarised host-side.

**[OQ-0]** Only the *sign* of `EU(escalate) − 0` depends on the ruling: +0.1365 at the
deployed Ū, −0.0933 at the elicitation Ū, at run-18 oracle values. The row's form is
identical either way.

## 4. Reliability is estimated, not asserted

**Requirement: no rung's `p_r` may be a written constant.**

Two admissible sources, in preference order:

1. **Learned on the wire.** Declare a guard on the writable name; the guard family over
   a writable is exactly the hypothesis family *the outcome depends on what I did*
   (`membrane-wire.md:363-383`, measured growth at `:386`). The posterior earns `p_r`
   from observed outcomes. This needs no protocol change and is the preferred path.
2. **Held-out measurement.** `p_r` estimated from graded outcomes on a held-out slice,
   refreshed on a schedule, with the estimate's own uncertainty carried — not a point
   estimate silently reused. Acceptable where (1) has too little data.

**Update rule.** Every escalation produces an outcome that is gradeable by the same
machinery as any other answer (`DR-UTILITY-1` §3.1 for L2; the LLM judge for L3). That
grade feeds back into `p_r`. **An escalation whose outcome is never graded must not
update `p_r`** — silence is not evidence of success, and this is the obvious way for a
reliability estimate to drift optimistic.

**Per-lane reliability.** `p_r` is almost certainly not constant across L1/L2/L3
(`DR-LANE-1`). Specify `p_r` as conditioned on lane at minimum. Whether it should also
condition on answer shape is an empirical question, deferred until the lane-conditioned
estimate has data.

## 5. Unavailable, barred, and the floor action

Three cases where escalation cannot fire, and what happens:

| Case | Detection | Result |
|---|---|---|
| **Unavailable** — offline, outage, rate limit | The rung's execution fails or times out | Row is **removed from the menu for that tick**, not scored low. Re-decide over the remaining actions. |
| **Over budget** — below willingness-to-pay | Priced in, loses the argmax | Ordinary loss. No special case. |
| **Barred** — question touches SEALED content | Host-side, before the tick (§2) | Name withheld. The action is not merely unattractive, it is **absent**. |

Availability is a **feasibility question, not a utility question**. Pricing an
unreachable oracle at a low utility invites the argmax to pick it anyway when everything
else is worse. Withholding the name is the protocol-supported mechanism and the correct
one (`membrane-wire.md:66-70`: publication toggles availability, not membership).

**A failed escalation still costs.** The attempt's spend and latency are real and must
be charged even though no answer arrived. Anything else makes retry free.

### 5.1 Pointer-to-source, the floor action

**Specified here rather than separately, because escalate and pointer-to-source
together are what remove the dead cells.**

The claim: *"I cannot answer this, but the answer is in these documents"* — a ranked
list of sources, no synthesised answer.

Why it belongs in the same spec:

- It is **available in every lane**, including L3 where no quality scalar exists.
- It requires **no oracle**, so it survives the unavailable case.
- It **discloses nothing**, so it survives the SEALED case — which is otherwise the one
  cell with no action at all: an open-ended question over sealed content can be neither
  graded nor escalated.
- It is **gradeable**, because it converts a generation problem into a retrieval
  problem: did the pointed-at documents contain the answer? That is measurable by the
  machinery L2 already needs.

Valuation: `u_assert(x_ptr)` where `x_ptr` is retrieval quality (containment of the gold
answer in the pointed set, discounted by set size so pointing at everything scores
badly — the same self-penalising construction as `DR-UTILITY-1` §5). Its error mode is
`u_vague`, not `u_wrong`: a pointer that misses wasted the reader's time; it did not
assert a falsehood.

**Open:** whether the owner would actually use this (OQ-4). If not, the SEALED +
open-ended cell has no action and that should be stated as a known hole rather than
papered over.

## 6. `/route` moves downstream of the posterior

**Part of this spec, not a separate item.**

Today `decide_via_loop` (`executor.py:186`) calls `POST /route`
(`executor.py:203`); a declined route returns null and the question goes to
`POST /narrative` (`executor.py:205`), which is rerank + LLM synthesis returned
verbatim. `_route` is one of the bridge's handlers (`server.py`, route table ~`:1102`).

So the typed-vs-narrative decision — *should this question be answered by our engine or
by an LLM?* — is made **before any posterior exists**, by the component with no
evidence. That is the same decision escalation is supposed to make, made earlier and
worse.

**Required change:** `/route` is demoted from a decision to a **lane classification**
(`DR-LANE-1`), which is a property of the question and legitimately precedes evidence.
The answer-vs-escalate decision moves after the posterior, into the argmax where the
escalate row competes with report, hedge, scoped, interval and abstain.

Consequences to specify before building:

1. **The narrative lane becomes a rung, not a bypass.** Today `/narrative` is an
   unpriced alternative path; under this spec it is an escalate rung with a cost and a
   measured reliability, competing on the same simplex.
2. **Cost accounting changes.** `executor.py:229` notes that `/route`'s cost is not
   wire-carried. Once routing is a priced decision, the evidence-gathering spend that
   precedes it must be attributed, or escalation looks cheaper than it is.
3. **Archived comparability breaks.** Every recorded run routed upstream. Readings
   across the change are not comparable and must not be spliced. This wants a
   pre-registration and a fresh baseline, not a migration.

## 7. Composition with the existing simplex

The action set becomes:

```
report_j (×K) | report_scoped_j | hedge | interval_a_b | ask_clarify | escalate_r | pointer | abstain
```

Invariants that must hold:

- **One valuation atom.** Every row derives from `u_assert` (`decide.py:64`). No row
  invents its own arithmetic. This is the existing r30b · C3 discipline.
- **Both decide surfaces or neither.** `action_utilities` (`lookup.py:940`) is *not*
  the deployed surface; the daemon's action set is built in the credence repo
  (`answer_brain.jl`, `decision_fpa`), and `report_scoped_j` already has no daemon
  counterpart. **An escalate row added only to `action_utilities` would change nothing
  for the owner.** Every item here lands in both or is not built.
- **`escalate` is not a withholding.** It delivers an answer. It must not be added to
  `WITHHOLD_ACTIONS` (`gate.py:88`), and adding it to `ASSERT_ACTIONS` (`gate.py:87`)
  silently changes the valuation of every archived row. A third partition member is
  required, with an explicit statement of how archived readings are affected.
- **Withheld reasons stay a closed vocabulary.** `WITHHELD_MISS` / `DISPERSED` /
  `UNAVAILABLE` (`gate.py:98-100`) annotate abstentions. Escalation is not one of them.

## 8. What this spec does not decide

- The rung set and prices — OQ-8.
- Whether latency is linear or has a cliff — OQ-2.
- Whether pointer-to-source is useful to the owner — OQ-4.
- The disclosure classes and the SEALED boundary — OQ-5.
- **[OQ-0]** whether the escalate row wins today or needs OQ-1 first.

## 9. Uncertainty in this spec

Stated rather than buried:

- **Whether `p_r` can be learned on the wire fast enough to be useful.** The cited
  posterior growth (9.09e-3 → 1.02e-1 over 60 rounds) is proplang's own measurement on
  a synthetic world, not on this workload. If real escalations are rare, the held-out
  path (§4.2) may be the only viable one, and it is weaker.
- **Whether the narrative lane can be priced at all.** Its cost is currently not
  wire-carried, and retrofitting attribution across an unpriced path may be harder than
  §6.2 implies.
- **Whether a third action partition can be added without invalidating archived
  readings.** §7 requires it; I have not verified that the gate's fold survives it.
