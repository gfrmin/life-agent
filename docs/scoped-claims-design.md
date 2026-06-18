# Scoped claims — design draft

Status: **draft for owner review** (2026-06-18). Not yet built; nothing implemented until this
is approved. Replaces the exhausted retrieval-lever sweep
([[principled-rag-agent-answer-brain]] calibration) with the decision-layer fix the sweep
pointed to. Builds on the Bayesian foundations (§4 lookup family, §4.1 covariates) and the
interaction contract.

## 1. Problem

The lookup posterior asks one question — *"what is V **now**?"* — and scores every document as
a noisy measurement of that. An old document is a *bad* measurement of "now," but the posterior
cannot tell **stale** from **wrong**: with recency off (or mis-routed off), corroboration-count
makes a superseded value win; with recency on, a stale-but-only value decays below the assert
bar and the agent abstains. So the agent is trapped between two bad moves:

- **assert-current** → the cardinal sin when the value is stale (the founding mobile case; the
  calibration's q-014: the owner's old Hong-Kong number hedged at 0.76 over his current Israeli
  one, which was beyond retrieval);
- **abstain** → throws away a true fact ("you did have that number, as of 2019").

The dichotomy is false. A third answer is true and useful: **"as of `<date>`, V was X; nothing
more recent on file."** It is not untrue regardless of today's value (owner's framing). This
design makes that the agent's move when the current value is uncertain but the historical record
is solid.

## 2. The reframe: two probabilities from one posterior

A document is a clean measurement of **value-at-its-date**, and only a *decaying* measurement of
value-now. The existing kernel already encodes the decay: `lookup.time_factor(date, time_indexed=True)
= 0.5^(age/5yr)` discounts an old doc's reliability about the present (`lookup.py:229`,
`_TIME_HALF_LIFE_YEARS=5`). Run the **same** posterior two ways (pure credence math, no new model
calls):

- **p_current(V)** — recency **on** (`time_indexed=True`): `P(V is the value now)`. Stale support
  → low.
- **p_attested(V)** — recency **off** (`time_factor=1`): `P(the documents attest V)` — what is on
  file, ignoring currency. Stale-but-clear support → high.

A value with **low p_current but high p_attested** is exactly the scoped-claim sweet spot: we are
unsure it is current, but sure the record says it (as of the freshest supporting doc's date).

## 3. The decision change: one new action, `report_scoped`

Add `report_scoped` to `DEC.LOOKUP_ACTION_ORDER` (today: report, hedge, ask_clarify, abstain).
It asserts the leader value **scoped to the date of its freshest supporting document** ("as of
`<D>`: X"). Its correctness target is the *attestation*, not the currency — so it is graded on
`p_attested`, and its failure mode is a **citable misread** of the doc, not a catastrophic
current-value error. Utilities (gauge `u_correct=+1`, `u_abstain=0`; `decide.u_assert`):

```
EU(report)        = p_current(V*)·u_correct  + (1 − p_current)·u_wrong            # the gamble
EU(report_scoped) = p_attested(V*)·u_hedged  + (1 − p_attested)·u_wrong_scoped     # the true partial
EU(hedge)         = … u_hedged over the set …                                      # unchanged
EU(ask_clarify)   = ρ·u_correct − lambda_int                                       # unchanged
EU(abstain)       = 0                                                              # gauge zero
```

`decide` = `optimise` over the action set, **unchanged in shape** — we only add a row. No
hand-coded "is this stale" gate: the EU comparison decides. The behaviour falls out:

- **recent / corroborated-current** value → `p_current` high → **report** plainly (as today).
- **stale-but-on-file** value → `p_current` < the 0.95 bar (from `u_wrong=−19`) so `report`
  loses, but `p_attested` high and `u_hedged>0` so **report_scoped** beats abstain → a true
  partial answer. **q-014 stops being a confident-wrong; salary-2019 becomes "as of 2019, X."**
- **nothing clearly attested / dispersed** → both lose → **abstain**, as today.

### 3.1 Why `report_scoped` needs its own wrong-cost `u_wrong_scoped`

This is the one **new utility latent**, and it is load-bearing. A scoped claim is wrong only if we
misquote the document — a bounded, *citable* error ("the doc you can click says Y, not X"), not
the catastrophic act-on-a-stale-current-value error that `u_wrong=−19` prices. If we reused −19,
then at a realistic `p_attested≈0.9` we'd get `0.9·u_hedged − 0.1·19 < 0` and the agent would
**never** scope — the 10% misread risk would swamp a partial credit `< 1`. So `u_wrong_scoped`
must be its own, much smaller magnitude (the "normal mistake" cost), exactly the *claim-type-indexed
u_wrong* promised in the foundations. **Proposed prior: `u_wrong_scoped ~ N(μ=−2, σ=1.5)`,
truncated ≤ 0**, distinct from the −19 current-value cost. (Open choice — §7.)

## 4. The trigger: only time-varying facts

Scoping must not touch **permanent** facts (DOB, ID number, place of birth) — for those any
attestation *is* current, and decaying an old-but-valid doc would be wrong. The split is the
router's `time_indexed` flag, with the `era_split` fallback that gather already uses to catch the
local router's mis-flags (e.g. "mobile number" → permanent; `lookup.era_split`, `gather.py:26`):

```
time_varying = route.time_indexed  OR  era_split(observations, doc_date)
```

- **permanent** → `p_current == p_attested`, no decay; `report_scoped` is dominated by `report`
  and never fires. Path unchanged.
- **time_varying** → compute both probabilities; `report_scoped` is in play.

## 5. Render (interaction contract)

A new render branch for `report_scoped`, conforming to the credence grammar (claims with
credences, a citation per observation, nothing silent):

```
As of <D>: X  (p_attested) [n][m]
  — most recent source on file; no later record found. A current figure would need <upgrade>.
```

The currency gap is **named, not hidden** — the same "show what you withheld" discipline the
abstain branch already follows. `<upgrade>` names the unused, deferred upgrade (§6).

## 6. The deferred upgrade hook (cheap now, free option later)

The cost-aware *upgrade-to-current* layer is **deferred** (owner-agreed): it is a separable §16
VOI-governor decision — `EU(current) − EU(scoped) > cost(effector)` — over costed effectors
(**Opus** = pay-compute for a better local read; **assistant-email** = `ask_clarify` generalised
from owner→delegate, priced in latency + attention). We build none of it now. We only **preserve
the option for free**: when the agent answers scoped, it (a) names the available upgrade in the
render (§5) so the owner can trigger it by hand, and (b) records `decision=report_scoped,
upgrade_available=true, taken=false` in the decision log — the future governor's training data.

## 7. Open choices (flagged for override)

1. **`u_wrong_scoped` as a new latent** (§3.1) vs folding scoping into `hedge`'s existing
   `u_hedged`/`u_wrong` split. Recommend the new latent — it is the honest "citable misread is a
   cheap error" statement, and without it scoping never fires. Its prior (`μ=−2`) is a second
   small preference elicitation, like `u_wrong`.
2. **`p_attested` = recency-off posterior** (recommended; reuses everything) vs a separate
   per-document attestation model. Recommend recency-off — it is the same machinery run twice.
3. **As-of date = the freshest supporting document's date** (recommended; simple, honest) vs a
   per-era claim set ("2019: X; 2022: Y"). Recommend freshest-only for v0; per-era is a later
   extension.

## 8. Scope of v0 and how it is measured

- **In:** the **lookup (point-fact) family only** — the owner's focus. New action +
  `u_wrong_scoped` latent + two-pass posterior + render branch + the decision-log field.
- **Out:** narrative family; the upgrade VOI layer (§6); per-era claim sets; any new dependency
  or model call (it is pure credence math over the existing observations).
- **Measure:** the triage harness gets a **`SCOPED`** outcome (a true partial: not CONFIDENT_WRONG,
  not WRONGLY_WITHHELD). Expected effect on the calibration corpus: **q-014 moves CONFIDENT_WRONG →
  SCOPED** (the headline), salary/address-class misses move WRONGLY_WITHHELD → SCOPED, and the
  **hard gate holds: zero new confident-wrong** (a scoped misread is graded against `p_attested`
  and is, by construction, a true claim about the record). Watch specifically for any value that
  scoping asserts where the freshest doc does **not** in fact attest it — that *would* be a new
  sin and reverts the increment.

## 9. Discipline

`u_wrong=−19` (and `u_wrong_scoped` once chosen) are **declared standing preferences**, set blind
to the eval and narrowed only from real verdicts — never fitted to the gate. Frozen-blind at every
step. Zero new confident-wrong is the hard gate. The lookup posterior is credence-shaped and is
being ported to the Julia answer-brain, so this change lands here first and ports with parity. No
new dependency; `pkm` untouched.

## Change surface (for the implementation plan, after approval)

- `core/decide.py` — `LOOKUP_ACTION_ORDER` += `report_scoped`; the action's utility row.
- `core/utility.py` — `REQUIRED_LATENTS` += `u_wrong_scoped`; gauge/grid/prior; the example model.
- `core/lookup.py` — two-pass posterior (p_current / p_attested); `action_utilities` row;
  `decide`; `LookupResult` (as-of date, p_attested, the scoped flag); `render` branch; reuse
  `era_split` + `time_factor`.
- `core/gather.py` — inherits the new action through `decide_and_record` (no change to its loop).
- `scripts/triage_grading.py` + `triage_answers.py` — the `SCOPED` bucket.
- decision-log schema — `upgrade_available` / `taken` fields.
- tests — hermetic: a stale-but-attested fixture scopes; a recent fixture reports; a permanent
  fact never scopes; a misread does not assert.
```
