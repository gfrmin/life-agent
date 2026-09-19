# r49b — the "gauge" was a misclassification, and the consistency rule collides with the gate's blind regime

**Date:** 2026-09-05 · **Cost:** $0 · **Tree:** master `cbfdc90` · **Decision path:** unchanged.

This is a $0 follow-up to [`r49-s18-bars.md`](./r49-s18-bars.md), written to discharge an owner
ruling on that checkpoint's conferral. It reads code and existing records only; it runs no
engine, buys no gate run, and changes nothing on the decision path.

The ruling's central correction is **accepted and enacted**. Two of its supporting claims are
**refuted by the code and the record**, and — because they are load-bearing for the remedy it
prescribes — the remedy is **escalated rather than implemented**. Everything that does not
depend on the escalated part is done here.

---

## 1. What was ruled

The conferral asked which utility §18's bar is quoted at, presenting `u_wrong` = −9.0 and
−5.131 as two *gauges*. The ruling held that:

1. **`u_wrong` is not a gauge.** The affine gauge is the two pins (`u_correct` = +1,
   `u_abstain` = 0), already fixed by convention. Once pinned, `u_wrong` is an **identified
   latent** — §4.4 lists it as exactly that, and `p* = −u_wrong/(1−u_wrong)` shows the number
   is fully determined inside the pinned gauge. So the two values are **two estimates of one
   quantity**, and the choice between them is **epistemic, not conventional**.
2. **The conferral therefore mis-routed the question** into `RULINGS` §5's conventional bucket,
   asking for a keypress on a question the constitution had already assigned to evidence.
3. **The remedy is a consistency rule, not a number:** *there is one utility — the current
   posterior mean — and the decision layer and the gate both read it.*
4. **B (sharpening `p1` in the 70–90 band) is the substantive move, not A**, because it is
   gauge-independent; **C should start now**, with `M-31` reframed from "print both
   break-evens" to "assert one Ū across decision layer and gate, and print it."

Items 1, 2 and 4 are enacted below. Item 3 is where the collision is.

---

## 2. The classification correction is correct, and the codebase already said so

Accepted without reservation. `core/utility.py`'s own docstring for `posterior()` states it
verbatim:

> "Two conditioning sets over one probability model; which set ranked a decision is part of that
> decision's record (§5.1)."

So the register was not merely imprecise — it contradicted the module it was describing.
`M-31` took a **dated correction** in this commit. The word "gauge" is withdrawn from it; what
survives is the operational half (publish both numbers and say which one the verdict is quoted
at), which is right for a reason the entry got wrong.

**This is the failure mode worth naming.** The two numbers were *never* a convention to be
chosen. Calling them a gauge converted an empirical question into an owner keypress — and the
keypress on offer was **result-relevant**: it flips the reading's headline sign in the
direction of adoption. (It would not by itself have produced a PASS — see §5.) That is not a bad answer;
it is a **bad question**, and the register is where the badness entered.

---

## 3. What the two numbers actually are — measured, not inferred

Both are posterior means of the **same latent** under the **same probability model**. They
differ by **declared conditioning set** (`utility.posterior(..., policy=)`), and the difference
is structurally enforced, not incidental:

| | conditioning set | folds reactions? | `u_wrong` | break-even `p*` |
|---|---|---|---|---|
| **Deployed decision layer** (and the boot Ū `r49`'s policy commits under) | `all-to-date` | **yes** — elicitations + the §4.4 verdict→evidence projection | **−5.131** | **0.836894** |
| **A3 gate scoring** (`r49` S5) | `frozen-elicitations` | **no** — refused by construction | **−8.9993** | **0.899993** |

`frozen-elicitations` does not merely omit reactions; it **raises** on one
(`utility.py:479-485`), so the gate's blindness is a guard, not a default.

**Why the guard exists is the part the conferral never surfaced.** Reactions are projected from
the owner's verdicts *on the decision log* — the very stream the gate scores. Folding them into
the gate's scoring utility lets a policy's own outcomes move the yardstick it is graded by. The
blind regime is an **anti-circularity guard**.

---

## 4. Three findings that cut against the ruling's mechanism

### (a) There is no stale side-store in the decision layer

The ruling diagnosed "a stale constant loaded at boot … the fold-not-store invariant violated,
a side-store drifting from the belief state." **The code does not do this.**
`lookup.current_u_bar` re-reads the model, the elicitations *and* the reactions on **every
call**, recomputes `fold_version` over them, and re-folds whenever that version moves; the
in-process cache is keyed on it. The bridge hands the membrane shadow **that same live fold**
(`server.py:1263-1264`, `membrane=_build_membrane(lambda: _u_bar(...))`).

So the "boot Ū" is a **snapshot of the live belief**, refreshed at each boot — not a constant
that drifted away from it.

### (b) The record proves it tracks: the boot Ū moves, and it is not monotone

Twenty boot records carry `u_bar`. `u_wrong` over the last three distinct values:

| boot | `u_wrong` | break-even `p*` |
|---|---|---|
| 2026-07-22 → 08-04 | −5.9395 | 0.855898 |
| 2026-08-06 → 08-10 | **−8.8301** | **0.898272** |
| 2026-09-01 → 09-02 | −5.1310 | 0.836894 |

**In August the deployed bar sat at 0.8983 — within 0.002 of the gate's 0.8999.** The two
regimes very nearly coincided, then diverged again. That is decisive for interpretation: the
gap is **volatility in a conditioned latent**, not a fixed offset between two ways of measuring.
A reading taken in August would have found no gap to report at all. (The drift itself is
already priced and monitored — `GD-21`/r32, r33's weekly readout, ruled MONITOR ONLY; what is
new here is the **non-monotonicity**, which is what rules out a structural explanation.)

### (c) The labels are the other way round, and this reverses the remedy's arithmetic

The ruling reasoned: *"Today that mean is ≈ −9; if the posterior is elicitation-dominated and
revealed preference pulls `u_wrong` toward −5, conditioning will move it there."*

The evidence is the reverse. **−9.0 is the elicitation-only number** (the gate's blind regime,
and also `world.py:247`'s hardcoded fallback). **−5.131 is the reaction-conditioned one** —
revealed preference has *already* pulled it there; that is what the §4.4 reaction loop is and
what r32 priced.

So "**the current posterior mean**", read as the most-conditioned estimate, is **−5.131**, and
the bar it names is **0.837** — the *softer* of the two.

---

## 5. The collision, stated plainly

Put (c) together with the ruling's remedy:

> *"There is one utility — the current posterior mean — and the decision layer and the gate both
> read it."*

Implemented literally, this makes the A3 gate score under `all-to-date`. On today's numbers that
moves the scoring break-even from 0.900 to **0.837**. `r49`'s entire differential is **24
marginal commits at 0.875** — which sits *between* the two. So the rule flips `r49`'s point Δ
from **−0.080 to +0.075** — from a negative headline to a positive one — and it does so by **deleting the
anti-circularity guard** described in §3.

**A sign is not a verdict, and the distinction matters here.** A3 passes on
P(Δ>0.05) ≥ 0.90, not on the point estimate. `r49` computed the point Δ at the deployed regime
(**+0.0748**) but never the posterior mass there, and at the interval width the reading actually
shows ([−0.482, +0.205] around −0.081) a mean of +0.075 would not come close to putting 0.90 of
the mass above δ. So the honest statement is that the regime choice **flips the headline sign
and is therefore result-relevant** — not that it would have delivered a PASS. That is enough to
engage §17.6 and `M-4`, which forbid re-reading at the softer regime *after* a FAIL regardless of
whether the softer reading would have cleared the bar.

This is the outcome the ruling was expressly designed to prevent — *"a number that isn't ruled
can't be ruled for its result"* — arriving through the rule itself rather than through a
keypress. It is not an objection to the principle; it is a report that **on today's evidence the
principle and the guard select opposite regimes**, and only one of them can hold.

**I am not resolving this.** It changes the gauge the objective is measured at, which is
`D-3`'s one escalating class, and resolving it in the direction the arithmetic favours after
seeing a FAIL is exactly what §17.6 and `M-4` forbid. It returns to the owner **with the fact
the conferral should have carried in the first place**.

The re-posed question is narrow, and it is no longer "which number":

> **Does the A3 gate keep its blind regime?** Scoring a policy under a utility conditioned on
> verdicts about that policy's own decisions is circular; scoring it under a utility the system
> does not hold is a second master. `frozen-elicitations` chose the first horn deliberately.
> The consistency rule chooses the second. Which one governs — and if the guard stands, what
> does "one utility" then mean for the decision layer?

Three sub-answers are available and none needs a new measurement:

- **Guard stands, consistency scoped to the decision path.** "One utility" binds every
  *decider*; the gate is a blind instrument and is exempt by declaration. Cheapest; keeps
  `r49`'s FAIL standing; leaves the two-regime disclosure permanent (which `M-31`, corrected,
  now requires).
- **Guard falls, gate reads `all-to-date`.** Restores one number everywhere, but the gate then
  grades policies with a yardstick their own outcomes moved, and every prior gate reading
  (runs 6–23) becomes non-comparable, since all were scored blind.
- **Guard stands and is made honest.** Keep blindness, but require the gate to *report* the
  deployed break-even alongside its own and refuse to publish when the measured reach falls
  between them — the r49 configuration — as an **inconclusive** verdict rather than a FAIL.
  This is the only option that changes what `r49` was entitled to conclude, and it is the one I
  would put first if the guard is kept.

> **RULED 2026-09-05 (owner, interviewed — `conferrals/a3-regime-conferral.md`): the third — the
> guard stands and is made honest.** Built as `M-34` (`core/gate.py` `verdict` /
> `marginal_commits`; `render_report` requires the pairing; `run_eval` declares the one the classic
> gate spans). `r49` takes the dated note in its §S5. `RULINGS` §5 has nothing live.

---

## 6. What is enacted here, and what is not

**Enacted** (this commit):

- `M-31` corrected — "gauge" withdrawn, the two-conditioning-sets fact substituted, the
  anti-circularity guard named so no successor re-derives it.
- `GD-26`'s **Reaction** field carries the ruling, per the house convention.
- `GD-27` publishes this reading and the escalation.
- The conferral gains a **RULING** section: the question as posed is withdrawn as
  mis-classified, and the narrow question in §5 replaces it.
- **C is built** — reframed as the ruling directed, and scoped so it does not prejudge the
  collision: see §7.

**Not done, deliberately:**

- The consistency rule is **not implemented**. §5.
- The bar is **not re-read** at the softer regime. §17.6, `M-4`.
- **B is not opened** here. The ruling is right that it is gauge-independent — the band's
  realised correctness is 0.80, below *both* 0.837 and 0.900, so a calibrated `p1` withholds
  those rows under either resolution — but it is a decision-path lever and needs its own
  pre-registration under `M-3`. It is the next rung, not a rider on this one.
- `M-1` is not engaged: nothing ships from this checkpoint.

---

## 7. What C becomes

The ruling reframed `M-31`'s check from "print both break-evens" to "assert one Ū across
decision layer and gate, and print it." Taken literally that check **presumes the collision is
already resolved** — it would fail today against a guard that is deliberate. So C is built to
the strongest form that is neutral between the resolutions:

> A differential reading must **declare both regimes and their break-evens**, and must **fail
> loud** when the regime a policy was priced at differs from the regime it is scored at *and*
> the measured reach falls **between the two break-evens** — the configuration in which the
> verdict is an artefact of the pairing rather than of the policy.

That is exactly the r49 configuration, and it would have fired **before** the 14-hour run rather
than after it. It asserts the *declaration*, not the *number*, so it stays correct under all
three sub-answers in §5; if the guard falls, the two regimes coincide and the check goes quiet
on its own.

Registered as **`M-33`**. Built and verified:

- `gate.break_even` derived **through** `decide.u_assert` rather than respelled as
  `-u_wrong/(1-u_wrong)` (`M-7`), so a change to the one atomic correctness utility moves it.
- `gate.regime_pairing` / `gate.RegimePairing` / `gate.render_regime_pairing`, and a **preflight**
  in `scripts/membrane/p3_gate.py` that prints the pairing before a single engine spawns.
- Reproduced on `r49`'s own artefacts (the boot record's Ū at full precision + the published
  gate report's scoring Ū): the preflight prints the divergence and names the interval
  `[0.8369, 0.9000]`; at the measured reach of 21/24 = 0.875 it flags the verdict
  **pairing-sensitive**.
- 16 tests; **6 of 6 mutations RED**.

Two of the build's own findings are worth recording, both caught by the mutation battery rather
than by review:

- **Three mutations initially SURVIVED.** The endpoint tests used *rounded* stand-ins (0.836894)
  rather than the exact break-evens, so an inclusive-endpoint mutation slipped through; nothing
  covered a pairing whose two regimes currently *coincide*; and nothing covered a pairing whose
  pricing bar is the *higher* one. All three are now tested — and the second is not a
  formality, since the August boot shows two regimes can coincide and part again, which is why
  divergence is a property of the **declaration** rather than of today's arithmetic.
- **One predicate was dead, not untested.** `straddles` carried a `not self.divergent` guard no
  mutation could kill: non-divergence implies equal break-evens, so the strict-between test is
  already False. It was removed rather than given a contrived test — an unkillable predicate is
  a redundant one.

**Two record gaps found en route, neither repaired here.** The shadow's boot record persists
`u_bar` but **not the policy name** that produced it, and `r49`'s own `a3_meta-*.json` stores
neither Ū nor either regime — so an offline reader cannot name the regimes a past run spanned
without inferring them, which is this checkpoint's finding in miniature. Both are additive
schema fixes. They are deferred deliberately: the shadow's writer is live, and a record-schema
change means a bridge restart, which `GD-20`/`M-27` established is a hazard that has already
killed the shadow once. The preflight closes the forward-looking half at zero risk.

> **Addendum 2026-09-05 — the harness-side half is repaired.** `a3_meta-{variant}.json` now
> records both regimes with both Ū at full precision and the marginal-commit table
> (`regime_record`, `marginal_commits`), and the harness re-prints the regime pairing at the
> *measured* marginal rate after each verdict. `M-32`'s phase marks land in the same change
> (`phases.json`; a boundary-stamped, line-buffered log; the wall/CPU split at the end). Twelve
> tests, 8/8 mutations RED. The boot record's policy name still waits for the next natural
> bridge restart.
