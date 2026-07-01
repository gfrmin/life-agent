# Autonomous recall — lifting `:grow` onto the agent's missing-mass-priced menu

> Status: design / deliberation (frozen-layer math — not yet built). Realises
> `bayesian-foundations.md §5` (the missing-mass / recall term). Owner's directive
> (2026-06-30): *the Bayesian agent should autonomously try different transformations* —
> recall strategies among them — not a body cascade, and not a human/Claude hand-picking
> "build semantic retrieval next."

## The gap (why retrieval misses persist)

The daemon already lets the agent autonomously try transformations — but only two **kinds**
(`answer_brain.jl:241-254`):

- `:voi` — priced by `net_voi`; output is a likelihood **over the fixed candidate set**
  (corroborate re-reads). The agent prices the menu and arg-maxes. Autonomous. ✓
- `:guard` — mandatory, defends an out-of-model risk (recency, owner-attribution). ✓
- `:grow` — recall/discovery that **enlarges K** (new candidates). Line 253-254, verbatim:
  *"cannot be priced by VOI over a closed categorical … a non-VOI action the BODY triggers
  … never a registry probe."*

So **recall is the one kind the agent does NOT decide.** When the answer is missing, the body
runs a hardcoded cascade (`executor.decide_field`: rerank → rerank+expand, fired off
`_truth_likely_missing`). That is why per-field extraction didn't convert the misses
([[per-field-extraction-disconfirmed]]) and why "improve retrieval" keeps presenting as a
hand-built pipeline: the agent **can't try retrieval transforms**, so a human supplies them.

## The principle: price recall by the missing mass, not by VOI

`net_voi` genuinely can't price a hypothesis-enlarging move (it integrates a kernel over the
*current* atoms; new candidates aren't in the space — line 253 is correct, not a shortcut to
remove). The principled price is the **missing-mass posterior** the agent already holds:
`P(NONE)` = mass on the NONE atom `k` (`candidate_posterior`, `answer_brain.jl:97,112`) =
the agent's belief the truth is **outside** the retrieved set.

A recall transform `t` proposes to enlarge the set so the truth can enter. Its expected value:

```
grow_value(state, u_bar, t) = P(NONE) · g_t · ( u_correct − value(state) )  −  cost_t
```

- `P(NONE)` — posterior mass on atom `k` (the only mass a recall move can convert; if the
  truth is already in-set, recall adds only distractors → its value is gated to ~0 by P(NONE)).
- `g_t` = `P(t surfaces the missing truth | strategy)` — a per-transform **recall-gain prior**,
  exactly analogous to the corroborate `rho` priors (stated, monotone, calibrated later from
  the outcome stream — a grown report that the owner verdicts correct ⇒ g_t earned trust).
- `u_correct − value(state)` — the gain from converting NONE-mass into a correct report over
  the agent's *current* best terminal EU (`value`). A withhold has low `value` ⇒ large gain; a
  confident in-set report has `value ≈ u_correct` ⇒ ~0 gain (don't grow a solved question).
- `cost_t` — cost-in-utility, commensurate with `value` (a local rerank ≪ a cloud embed).

This is the missing-mass analogue of `voi_gather`: same shape (expected Δvalue − cost), priced
against the SAME terminal preference, so **grow competes with answer / corroborate / abstain in
one EU**. It is NOT a binary `p_none ≥ leader` gate (the de-patch's `_truth_likely_missing`) —
that gate is subsumed: it falls out as `grow_value > 0`, and now the agent also **selects which**
recall transform (the arg-max), and **stops** when no grow clears its cost.

## Scheduler + wire

`schedule_decide` gains a third stanza after `:voi` (guards → :voi argmax → :grow argmax):

```
best_grow = argmax_t  grow_value(state, u_bar, t)   over eligible, unapplied :grow transforms
if best_grow_value > max(0, best_voi_value):  return ("gather", probe=t.probe, …)   # grow wins
```

`Transform` gains `kind = :grow`, carrying `g` (recall-gain prior) in place of a `kernel_fn`
(grow has no candidate-space kernel — that's the whole point). `registry_from_wire` accepts
`{name, probe, kind:"grow", trigger, g, cost}`. A new trigger `"missing"` ⇒
`(action,ctx) -> action != "report"` is **not** needed — `grow_value` self-gates on `P(NONE)`,
so a `:grow` transform `applies` whenever unapplied (the pricing does the gating). The gather
response names the probe; the body enacts it.

## Body enactment (the cascade dissolves into the menu)

`executor.DEFAULT_TRANSFORMS` gains `:grow` entries; `decide_field`'s hardcoded
`for rr,ex in ((T,F),(T,T))` cascade is **deleted**. When the daemon returns a `:grow` gather,
the body enacts it like any probe: re-`/retrieve` with that strategy (the probe name selects
rerank / expand / semantic / …), re-`/extract`, hand the enlarged candidate set back to
`/decide`. `applied_probes` dedups (each recall strategy fires at most once ⇒ termination). The
body still SHAPES evidence (it runs the retrieval); the agent DECIDES which to run and when to
stop. This is the de-patch ([[agent-autonomy-over-body-patches]]) completed for recall.

## The menu (recall strategies become data, added without touching the scheduler)

| probe | g prior | cost | capability (body) |
|---|---|---|---|
| `rerank` | mid | low | over-fetch + listwise rerank (existing) |
| `expand` | mid | low | native-script (Hebrew) query expansion (existing) |
| `semantic` | **new** | mid | bge-m3 embeddings + DuckDB `vss` (migration 0004 schema; bge-m3 pulled) |
| `value_aware` | later | mid | retrieve by the asked value's *kind*, not the topic |
| `subject_aware` | later | mid | down-rank wrong-subject docs at retrieval |

Each is one row. The agent tries them by `grow_value` arg-max — semantic-retrieve is **not** a
hand-built pipeline, it's a menu item the agent reaches for when `P(NONE)` is high and its
`g·u_gain` beats a cheap rerank. This is what "autonomously try different transformations" means.

## First slice (autonomy refactor; behaviour-checked, no new capability)

Port the EXISTING recall (`rerank`, `expand`) onto the `:grow` menu, priced by `grow_value`;
delete the body cascade. The agent now OWNS the recall decision with today's capabilities.
Verify against the current loop: on the retrieval-miss questions the agent should still escalate
recall (now because it priced it), and a solved question should not grow. THEN add `semantic`
as a second slice (pure menu addition), re-run the triage, count conversions at 0 confident-wrong.

## Open questions (the math to get right — confer these)

1. **Bound vs exact.** `grow_value` uses `u_correct` as the post-recall report value — an
   optimistic bound (the post-recall posterior might still disperse). Is the bound the right
   conservatism (over-tries recall) or should it discount by an expected post-recall
   concentration? Lean: the bound, with `g_t` (calibrated) carrying the realism — recall is
   cheap-ish and the cost term + `g_t` already temper it.
2. **`g_t` prior + calibration.** Stated monotone priors (rerank < expand < semantic?) then
   conditioned on the outcome stream (grown-report verdicts). Same machinery as `extractor_rho`.
3. **Interaction with corroborate.** Grow enlarges then a `:voi` corroborate may re-read the
   enlarged set — the loop must re-price both each round (it does; `applied_probes` only blocks
   re-firing the SAME probe). Confirm no oscillation.
4. **`P(NONE)` after a grow that finds nothing.** A grow that adds only distractors should
   *raise* `P(NONE)` (truth still missing) ⇒ the next grow is still priced, but `applied_probes`
   has retired the cheap ones ⇒ escalation to the costlier, then stop. Confirm termination.
