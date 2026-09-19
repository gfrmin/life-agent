# r28 — the Δ decomposition: what the adoption gate has actually been measuring

**Status: PRE-REGISTRATION (frozen).** Criteria C1–C4 below are committed BEFORE any
`src/` change and before the corrected reading is published. Results append after.

Register: bayesian-foundations §8 (the decision-weighted adoption gate), §14 (the live
empirical ledger). Instrument: `core/gate.py`. Cost: **$0** — this checkpoint reads the
existing paired records and changes what a report publishes. It buys no run.

---

## 1. Why

The §8 gate is the instrument every adoption ruling in the §14 ledger rests on. Its
headline is a posterior over `Δ = EU(typed) − EU(baseline)`. Twelve runs have been read
from that headline. **The headline has never been decomposed**, and the decomposition
changes what it means.

### Verified before freezing (each checked against the artefact named)

- **V1 — the baseline is the owner's outside option, and has been since run 6.**
  Every one of run 18's 104 rows in
  `paired-gate-20260826T083356.jsonl` carries `baseline: "raw-deliberative-replay"`.
  Confirmed by direct read, not inferred from prose.
- **V2 — that arm is Claude Code with corpus access.** The replayed fair-fight run's
  `run_meta.json` records `entrypoint: "claude -p"`,
  `claude_version: "2.1.215 (Claude Code)"`,
  `allowed_tools: "mcp__pkm__search,mcp__pkm__extract"`, `max_turns: 40`. It is the
  comparator the owner actually uses, replayed from 2026-07-19 on a model one generation
  behind today's — so it is a **floor** on the outside option, not a ceiling.
- **V3 — the baseline's spend is imputed, not metered.** That run's summary records
  `cost status: {'estimated': 104}`: the $39.01 comes from the CLI's own
  `total_cost_usd` token pricing. Under a flat-rate plan it is not money that left an
  account. (The typed arm's spend is metered the same way and is immaterial at $0.37.)
- **V4 — the entire Δ is the spend term.** Point-estimate arithmetic at the elicited
  latents (`u_wrong −9`, `lambda_usd 1.5`) over run 18's own rows:
  **Δ = +0.577 as run**, and **Δ = +0.014 with the baseline's spend uncharged**. On
  delivered answers the two arms are level; the baseline delivers **95 correct answers
  to typed's 61**. This is a sizing arithmetic at point values, NOT a gate reading —
  the real read marginalises over P(U) × the bootstrap, and is what C1 builds.
- **V5 — the report cannot show this.** `render_report` gained a `baseline` parameter in
  K4, so the arm is now named correctly. It publishes **no decomposition**: `Diagnostics`
  carries no spend field, and `realised_utility` folds the `−lambda_usd · cost_usd` term
  into a single number before any diagnostic sees it.
- **V6 — the split is exact, not an approximation.** `realised_utility` is affine in the
  sampled latents given the actions, so
  `Δ = Δ_answers + lambda_usd · (c̄_baseline − c̄_typed)` holds **per draw** and therefore
  in expectation at Ū. The decomposition is arithmetic, not a model.

### What this checkpoint is not

It does not re-price spend. Re-basing `lambda_usd` on the constraint actually faced (a
usage window rather than an imputed dollar) was offered to the owner on 2026-08-28 and
**declined**; spend stays at `lambda_usd × cost_usd` and abstention stays at the gauge
zero. This checkpoint makes the existing price **visible**, so that the successor arc's
readings can never again confound an answer-quality effect with a price effect. That is
the whole of its scope.

It also does not re-run anything. Every number it publishes is computable from records
already on disk.

---

## 2. Frozen criteria

| | Criterion | How it goes RED |
|---|---|---|
| **C1** | Every gate report publishes the decomposition `Δ = Δ_answers + Δ_spend` over **the same row set Δ is computed over** (the Δ-included set, i.e. after availability censoring), together with each arm's realised spend and its correct / wrong / abstain counts. | A mutation that drops the spend split from the rendered report, or that computes it over all rows instead of the included set, fails a named test. |
| **C2** | `Δ_answers` and `Δ_spend` are computed **independently** and their sum is asserted equal to the at-Ū mean gap over the same set. The identity is a test, not a comment. | A mutation that derives one term by subtracting the other from the total makes the identity vacuous; the test pins both against separately-computed quantities and fails. |
| **C3** | The value naming the baseline in the rendered report and the value stamped into every paired row are **the same object**, pinned by a drift gate — the divergence that made twelve reports quote the wrong arm cannot recur structurally. | A mutation that passes a different literal to `render_report` than to the paired-row writer fails a named test. |
| **C4** | The in-tree §14 prose naming the gate's baseline is corrected to name the arm the records carry. Where a summary describes a run's comparator, it says what `paired-gate-*.jsonl` says. | Verified by reading the corrected prose against the recorded tag; a residual "monolithic" describing a replay run is a defect, disclosed. |

**Non-goals, stated so they cannot be claimed later:** no change to Δ's value, to the
verdict, to `MATERIALITY_DELTA`, to `GATE_LEVEL`, to the utility model, or to any
decision path. C5 below is the pin.

| | |
|---|---|
| **C5** | **G2 — the 314-fixture replay, pure equality on `m5-base`.** This checkpoint touches the report and the diagnostics; it must move no fixture. |

---

## 3. Method

1. `Diagnostics` gains defaulted spend fields, so every existing construction of the
   dataclass is unchanged (the codebase's own convention for additive record change).
2. `_diagnostics` computes, over the **Δ-included** rows:
   - each arm's mean realised spend in dollars;
   - `Δ_spend` at Ū as `lambda_usd · (c̄_baseline − c̄_typed)`;
   - `Δ_answers` at Ū as the mean gap with the spend term zeroed — obtained by valuing
     both arms at `lambda_usd = 0`, which is the deployed `realised_utility` reading its
     own spend term, **never a re-implementation of it**.
3. `render_report` publishes the two terms beside the headline, with the arms' raw dollar
   totals and outcome counts, so a reader can reconstruct the arithmetic.
4. The §14 prose is corrected (C4).

The standing lesson is load-bearing here: **a census must read the deployed rule end to
end, never re-implement the constant it prices.** `Δ_answers` is therefore obtained by
calling `realised_utility` with the spend rate set to zero, not by writing out the
correctness terms a second time. A second spelling of the answer term is exactly the
defect class this project has shipped four times.

---

## 4. Verification

1. Full suite, ruff, mypy — evidence pasted.
2. PII check exit 0 with the private name layer live.
3. C1–C3 each demonstrated **RED by its named mutation, then restored**, transcript below.
4. `PYTHONHASHSEED=0 scripts/collapse_replay.py --checkpoint m5-base` — 314/314 pure
   equality (C5).
5. The corrected reading published for run 18 off its own record.

---

## RESULTS

_(appended after the reading — nothing above this line changes)_

**Read 2026-08-28, $0. Every criterion MET; scope exceeded on C3, disclosed below.**

### The corrected reading — run 18 through the deployed instrument

Produced by `scripts/gate_splice.py` re-reading `gate-20260826T083356`'s own rows under the
current production posterior. The identity splice reproduces the published verdict exactly
— **P(Δ>0.05) = 0.959, Δ̄ = +0.514** — so the chain is trusted before the split is read.

```
Δ_answers = 0.019  ·  Δ_spend = 0.495  ·  sum 0.514   (over the 104 rows Δ folds)

| arm                     | correct | wrong | abstain | mean $/q | total $ |
| typed                   |      61 |     2 |      41 |  $0.0036 |   $0.37 |
| raw-deliberative-replay |      95 |     6 |       3 |  $0.3751 |  $39.01 |

Ū: lambda_usd +1.3311 · u_wrong -8.9993 · u_hedged +0.3998 · u_wrong_scoped -2.0000
```

**96% of the adoption margin is the price term.** On delivered answers the two arms are
separated by 0.019 gauge units; the baseline delivers 95 correct answers to typed's 61 and
loses on EU almost entirely because its spend — *imputed from token counts, not metered* —
is priced at the elicited exchange rate. The pre-registration's V4 point-estimate arithmetic
(0.014 against +0.577, at `u_wrong −9` / `lambda_usd 1.5`) is superseded by this reading,
which uses the deployed rule and the production posterior; the conclusion is unchanged and
the magnitudes move as expected once Ū's actual latents replace the stated ones.

This is a **reading of what the gate measures, not a re-pricing.** Re-basing `lambda_usd`
on the constraint actually faced was offered to the owner on 2026-08-28 and declined; spend
stays priced as it is. What changes is that no future reading can present the total without
the split beside it.

### Criteria

| | Verdict | Evidence |
|---|---|---|
| **C1** | MET | `Diagnostics` carries `delta_answers`, `delta_spend`, `included_mean_d` and an `ArmSummary` per arm, all folded over the Δ-included rows; `_decomposition_lines` publishes them with each arm's counts and dollars. RED under M1 (block dropped) and M2 (row set = all rows). |
| **C2** | MET, with one disclosure | Three independent pins against hand-computed values on a fixture where the included mean (5.70) differs from the all-rows mean (3.80). RED under M3 (spend sign), M4 (one arm's cost for both) and M5 (answer term re-implemented). **Disclosure:** the literal mutation the criterion names — *deriving one term by subtracting the other* — is **behaviour-preserving on correct inputs** and therefore cannot be killed by any value test. What the pins do kill is an error in either term, which is the risk the criterion exists to cover. Stated rather than claimed. |
| **C3** | MET, **and exceeded** | See below. |
| **C4** | MET | The §14 prose and this report name the arm the records carry. |
| **C5** | MET | Replay 314/314 pure equality on `m5-base`, twice — before and after the required-argument change. |

### C3 exceeded: the defect was in three instruments, not one

The criterion asked for a drift gate on the two values in `run_eval.py`. Writing it found
that **the r27 defect had survived K4 in two further places**: `scripts/gate_splice.py:224`
and `scripts/membrane/p3_gate.py:338` both rendered gate reports through
`render_report`'s `baseline="monolithic"` **default**. K4 fixed the value at the one call
site it looked at and left the vector in place — guards.md entry 1 exactly: *the checker's
universe was derived from somewhere other than the thing being checked.*

So the default is **removed** and `baseline` made required. That is structural: a report
that does not know which arm it ran against no longer renders at all, and no census has to
keep re-finding call sites. `gate_splice` now reads its comparator from the mono archive's
own rows (refusing loudly when they disagree or carry none — the tag is data, not a flag);
`p3_gate` names the fair-fight arm it loaded. The AST guard is kept for the remaining
property a type system cannot express: that the report and the paired rows in `run_eval`
take their baseline from the **same value**. Its poison half plants both defect shapes — a
literal at one site, and a second variable — and requires each to be seen.

Doing more than a frozen criterion asked is disclosed here rather than absorbed.

### Also found, and fixed

`included = [p for p in paired if not p.censored()]` was written **twice** — once in
`delta_posterior`, once (newly) in `_diagnostics`. Two spellings of *"the rows Δ folds"*
that can drift, in a change whose whole point is that the split must fold the rows the
headline folds. Collapsed to one declaration, `_included`, which both bind. Found only
because a mutation anchor failed to be unique — the mutation harness caught a design defect
the tests would not have.

### Disclosed deviations

1. **A commit was made carrying an unverified claim.** The first message asserted a suite
   result measured *before* the required-argument change; that change broke three
   `test_p3_gate` callers. Caught by re-running G1 on the committed state, fixed, and the
   (unpushed) commit amended to carry verified numbers: **2894 passed / 35 deselected**.
   The gate here is the full suite on the final tree, not on an earlier one.
2. **Work was lost twice to the mutation harness**, which restored mutated files with
   `git checkout --` while the implementation was unstaged, silently reverting to HEAD and
   making three subsequent "RED" readings meaningless. Detected because a later run showed
   failures that should have been green. Harness fixed to stage first so restores come from
   the index; all six mutations re-run against the staged implementation.
3. **`p3_gate`'s report also mislabels its TYPED arm** — that arm is the membrane's
   held-out act, not the typed families. Out of r28's scope; recorded, not fixed.

