# r08 — window determinism (§6.13) — opened 2026-08-23

> **Status: pre-registration — criteria and predictions frozen and committed BEFORE any
> `src/` change or any measurement.** This is a FIX checkpoint, the first of the two the
> owner's 2026-08-23 rulings opened (r07's RULINGS section): §6.13 is repaired first so that
> r09's Δ is attributable to the JOIN alone. It is not a diagnosis — ruling 4's cap stands,
> and any anomaly found en route is a disclosure item here, never a new arc.

## STATE

- Base: master `fc43148` (the rulings commit). `src/` byte-identical to run 10's pinned tree
  plus nothing — r05/r06/r07 changed no decision-path code.
- The defect is **already registered and twice measured** — `docs/module-collapse-design.md`
  §6.13: pkm's FTS ends `ORDER BY scored.score DESC LIMIT ?`
  (`src/pkm/retrieval.py:184-185`, mirrored in SPEC ~§ "Search join structure"), so the
  declared total order R2 imposes in `core/retrieval.retrieve_set:53-54` — and the same
  declared key in `probes.probe_corroborate:206-213` — runs on rows the engine has ALREADY
  sampled. When a quantised tie block is larger than the over-fetch window, the window is the
  sampler: r06 measured 1 of 104 questions returning five different top-20s in five calls at
  k=20 (window 80, one 73-way block); r07 re-measured at commit granularity — 14 of 104
  wobble in committed n_obs across three draws, 22 flap between readable and cold.
- Decision-path callers inheriting the cut: `core/retrieval.retrieve_set` (base + grow
  surfaces, k=20, window 80; rerank pool k=150, window 600) and
  `core/probes.probe_corroborate` (S1's re-retrieve, k=20, window 80). Non-decision callers:
  `pkm search` CLI, the dormant MCP server, `scripts/comparison/phase1_answer.py`.

## The fix, chosen from the register's three named candidates

**(b) — push the declared total order into the SQL, before the `LIMIT`:**

```sql
ORDER BY round(scored.score, 9) DESC,
         scored.artifact_cache_key, scored.chunk_text, scored.chunk_id
```

The first three terms are EXACTLY R2's declared key, so "top-k of the window" becomes
"top-k of the corpus under the declared key" — one semantics end to end. The final term,
`chunk_id`, is the surrogate the catalogue re-issues on rebuild and is **confined by
construction to rows identical in every semantic column** (same quantised score, same
artefact, same text — twins that no downstream consumer can distinguish): it totalises the
row order at zero semantic cost, and across catalogue rebuilds twins permute only among
themselves.

*Why not (a) (grow the window until the score strictly drops):* unbounded without a cap, and
at the cap the cap is the sampler again — (a) reduces to (b) plus a moving window. *Why not
(c) (declare saturation and refuse):* it prices reach to avoid an arbitrariness (b) makes
deterministic and declared — the tree already resolves ties by the document key everywhere
else (R2; §6.9 at M1); making the window's ties uniquely refusable would need a reason no
entry states. (c)'s honesty survives as criterion C4's published census. The raw `score`
column returned to callers is unchanged — only the ordering the `LIMIT` cuts is declared.

## Criteria (frozen)

- **C1 — the baseline must reproduce the defect.** Pre-fix, the instrument
  (`scripts/window_audit.py`, Read A) runs every battery question at the deployed surfaces —
  base (raw question, k=20), expanded (cached expansion terms only; a cold expansion is
  skipped and named, $0), pool (k=150) — **5 identical calls per surface**, compared on the
  full row tuple `(artifact_cache_key, chunk_text, round(score, 9))`, order-sensitive.
  ≥1 question must be draw-unstable; if none is, the defect does not reproduce live and the
  checkpoint STOPS with the refutation published.
- **C2 — the fix's hard kill.** Post-fix, the same Read A reads **zero** draw-unstable
  questions on every surface. Any nonzero → the fix is reverted, the reading published,
  STOP for a ruling (ruling 4's consequence clause applied to r08).
- **C3 — across processes, not merely within one.** Read A's five calls span ≥2 fresh
  processes/connections (M0.5's finding was seed- and parallelism-dependence; in-process
  stability alone proves nothing).
- **C4 — the saturation census, published and not gated.** Per question and surface: the
  largest quantised tie block intersecting the window, and whether the block at the cut
  boundary extends beyond it (probed at 2× the window). This is the standing arbitrariness
  census (c) would have gated on; it composes with `carrier_audit` criterion 1.
- **C5 — the ruled multi-draw replay read.** Post-fix, three replay draws (deployed-only,
  `scripts/replay_audit.py` unmodified, staging KB, identical starting store, $0) compared
  at commit granularity with r07's own measures (committed n_obs wobble; readable↔cold
  flap). **Hard clause: the retrieval-attributable component of wobble = 0**, attribution
  per question by Read A — a wobbling question whose live retrieval is stable across 5 calls
  is NOT §6.13's, and is a named disclosure item, not a diagnosis. A wobbling question whose
  retrieval IS unstable post-fix fails C2 transitively → same consequence.
- **C6 — history is not rewritten, and the reading says so.** §18.9 keys are unchanged; warm
  entries keep serving the arbitrary draws they froze; the retrieved set may change pre→post
  exactly on straddling questions computed COLD — the reading publishes that count. No gate:
  that change is the fix working. Consequence named now: a later gate run on a warm store
  mostly never re-executes FTS, so this fix is the floor under FRESH draws, not a re-pricing
  of recorded ones.
- **C7 — governance.** pkm SPEC's documented search SQL is amended in the SAME commit as the
  code; the new pkm test is watched RED before the fix and GREEN after; full suite, ruff,
  mypy green; the caller comments that state "no tie-breaker in the SQL" are updated in the
  same commit (they become false).
- **C8 — PII.** The report carries classes and counts only; per-question artefacts (queries,
  hit identities) land under `$LIFE_AGENT_KB/eval/window/`, never in tree.

## Blind predictions

1. The baseline reproduces on ≥1 base-surface question (the §6.13 witness's shape: five
   distinct top-20s in five calls), and instability concentrates at the k=20 surfaces — the
   pool's window (600) swallows blocks the base window (80) cannot.
2. Post-fix: zero unstable questions, all surfaces, both processes.
3. The census finds one large straddling block (the witness's ~73-way class) and few others —
   ≤5 straddling questions at the base surface (r06 read the set-level tail at 1 of 104).
4. C5 reads total wobble **< 14** and retrieval-attributable wobble **= 0**; the
   readable↔cold flap does NOT vanish (the §18.9 warm-through is pass-order-dependent and
   untouched here).
5. On a cold pre→post comparison of base-surface sets, the changed questions are exactly
   C4's straddling questions.

## Disclosure — the interview shorthand, refined before any measurement

The owner's ruling 3 was taken on a question whose parenthetical read "frozen prediction:
wobble → 0". Frozen here, blind, as the two-level C5 instead: **retrieval-attributable
wobble → 0 (hard), total wobble ≤ the published baseline (prediction, not gate)** — on
arithmetic already public before the interview: r06 measured retrieval-set instability on 1
of 104 questions while r07 measured 14 wobbling in committed n_obs, so at most a few of the
14 can be §6.13's; betting the total to zero would bet on the absence of defects this
checkpoint neither measures nor fixes. The ruling's substance (repair §6.13 first, verify at
$0 by a multi-draw replay read, before r09) is unchanged.

## REFUSED

- No re-scoring of any prior reading (r06's criterion 8, r07's attribution) — this
  checkpoint prices nothing and reads no site.
- No cache invalidation: warm §18.9 entries are not touched, evicted, or recomputed.
- No fix at the callers: `retrieve_set` and `probe_corroborate` keep their post-hoc declared
  sort (defence in depth, now provably idempotent over an already-ordered window).
- No cold expansion calls: a question whose expansion is not cached is read at the base
  surface only and named ($0 discipline).
- No diagnosis of non-retrieval wobble residue (ruling 4's cap): named, counted, left.

## BASELINE (pre-fix, 2026-08-23 — C1)

Read A ran the full battery at all three surfaces, five identical calls each (3 + 2 across
two fresh processes, C3), $0, read-only. **C1 is satisfied, and the decomposition is the
finding:**

- **The decision layer (`retrieve_set`'s top-k) is stable on 103 of 104 — the single
  set-unstable question is q2-036, the §6.13 witness, at the base surface.** r06's 1-of-104
  replicates exactly, cross-process, on the instrument's first read. The expanded and pool
  surfaces are top-stable on all 104 (every one of the 104 expansions was cached — no
  surface was skipped).
- **The raw over-fetch window underneath is pervasively unstable:** order-unstable on
  75 / 74 / 75 questions (base / expanded / pool) and **set-unstable on 15 / 14 / 28** —
  the engine really is sampling tie blocks at every surface; R2's declared key masks it at
  the top-k everywhere except where the sampled block straddles the cut (the witness).
  The stability file's headline "104 unstable" is this window-layer noise; the number that
  reaches decisions is 1.
- Read B (C4, the census): straddling tie blocks on **17 / 15 / 30** questions per surface.
  The witness's boundary block spans **153 of 160 probed rows** at base (the probe itself
  saturates — the true block is larger than 2× the window), 102 at expanded; the largest
  pool block is 212 rows. The census is published beside the reading as the standing
  arbitrariness record; nothing gates on it.

Artefacts: `$LIFE_AGENT_KB/eval/window/baseline-{p1,p2,stability}.json` (fingerprints and
counts only, C8).

## DEVIATION 1 — C5's frozen clause is self-contradictory; the instrument amended, disclosed before any draw ran (2026-08-23)

C5 froze "`scripts/replay_audit.py` unmodified". The unmodified instrument REFUSED all three
draws at its own criterion-2 pin — HEAD's `src/` tree (which carries the r08 fix, by design)
no longer matches the replayed run's recorded tree. The two frozen clauses cannot both hold:
Read C exists to replay the run on the fixed tree, and the pin exists to refuse exactly
that. The contradiction is a pre-registration defect, caught before any measurement was
read (the r05 lesson again: the instrument's own clauses need the same adversarial read as
the measures).

Resolution, minimal and named: `verify_pin` gains an `acknowledged_src` parameter and the
CLI a `--acknowledge-src-drift TREE_SHA` flag — the pin passes only when HEAD's src tree
equals the ONE tree the caller explicitly declares (the fix commit's), any other mismatch
still refuses, and an empty acknowledgement changes nothing. The drift is stamped into the
pin notes of every rendered report, so no artefact of record can silently claim a clean
pin. No measure was touched. TDD: the test
(`test_an_acknowledged_src_drift_passes_the_pin_and_any_other_drift_still_refuses`)
was watched RED (TypeError) before the change; the file's 49 tests, ruff and the full mypy
gate are green after (one mypy run mid-change reported two phantom attr-defined errors on
untouched import lines — a poisoned incremental cache from a single-file invocation; a
clean-cache run is green, noted here because a false red on the instrument would have been
believed).

## DEVIATION 2 — the draws' render guard fired; the rows dumps are the artefact of record (2026-08-23)

All three replay draws completed their read and wrote their rows dumps, then exited nonzero
at the render stage: criterion 9(d)'s PII guard refused the `.md` report over one corpus
value (shape: a one-token numeric). This is the same firing r07's pass 2 accepted at its
stated limit, with the same resolution: the rows dump (`--out-yaml`), written before the
render, is the artefact of record; no draw report was rendered. The draws ran with the
acknowledged src drift of DEVIATION 1 stamped in their pin checks.

## THE READING (2026-08-23/24 — all eight criteria against their frozen text)

**C1 — PASS.** The baseline reproduced (BASELINE section above): the decision layer is
stable on 103 of 104 with the sole set-unstable question the §6.13 witness — r06's
1-of-104 replicated cross-process — while the window layer underneath is order-unstable on
75 / 74 / 75 questions (base / expanded / pool) and set-unstable on 15 / 14 / 28.

**C2 — PASS, the hard kill.** Post-fix, the same Read A (five calls across two fresh
processes) reads **zero draw-unstable questions on every surface at both layers** — the raw
over-fetch windows themselves are byte-stable, not merely the deduped top-k that reaches
decisions. The baseline's window noise replicated exactly, then vanished entirely.

**C3 — satisfied.** Both reads pooled 3 + 2 calls from two separate processes; the merge
takes the worse verdict per layer.

**C4 — published, not gated.** Straddling tie blocks on 17 / 15 / 30 questions per surface
(the census is order-independent, so the baseline numbers stand); the witness's boundary
block spans 153 of 160 probed rows at base and 102 at expanded; the largest pool block is
212 rows. This is the standing arbitrariness census; it composes with `carrier_audit`
criterion 1.

**C5 — PASS on the hard clause.** Three post-fix replay draws (deployed-only, staging KB
rebuilt from live before each, $0). At commit granularity, across the 56 questions readable
in all three draws: **committed-action wobble 0, firing-order wobble 0** (r07 baseline: 1),
**committed n_obs wobble 2** (r07 baseline: 14) — and **the retrieval-attributable
component is 0**: both wobbling questions are retrieval-stable across all five Read A
calls, so neither is §6.13's. The residue is named, not diagnosed (the cap): on both rows
the action and leader never change and n_obs drifts monotonically upward draw-over-draw
(6→7→8 and 11→12→12) — the accumulation signature of the §18.9 warm-through channel r07
registered, noted here as the suspected class only. The flap bucket reads 34 with 14 never
readable and 54 stable; readable rows shrink monotonically 76→73→69 as cold exclusions grow
28→31→35. The **identical-starting-store caveat**, named in the frozen criteria, is what
this bucket measures: the staging KB is rebuilt per draw but the live pkm store is shared
and its §18.9 warmth is pass-order-dependent (r07's registered deviation), so coldness
drifts across draws. Published beside the wobble numbers; r07's flap figure (22) was read
over a different pass structure and store state and is not directly comparable.

**C6 — history not rewritten, count published.** No §18.9 key changed; warm entries keep
serving the draws they froze. On a cold pre→post comparison of the decision-visible top-k,
**exactly one question changed at exactly one surface: the witness, at base** — zero at
expanded and pool — and it lies inside C4's straddling census. That one change is the fix
working; nothing gates on it.

**C7 — satisfied.** SPEC 0.18.2 amended in the fix commit; the two new pkm tests were
watched RED (the engine returned insertion order) before the fix and are GREEN after; the
stale "no tie-breaker in the SQL" caller comments were corrected in the same commit; full
suite 2637 passed, ruff and the clean-cache mypy gate green.

**C8 — satisfied.** This report carries classes and counts only. Artefacts of record at
`$LIFE_AGENT_KB/eval/window/`: `baseline-{p1,p2,stability}.json`,
`postfix-{p1,p2,stability}.json`, `p5-comparison.json`, `c6-pre-post.json`,
`draw-d{1,2,3}.yaml`, `draws-verdict.json`.

### The five blind predictions, scored

1. **Half-confirmed.** The witness reproduced in its predicted shape (distinct top-20s
   across calls; the sole decision-layer set-instability). The concentration claim was
   wrong at the window layer: pool window set-instability (28) is the *largest*, not the
   smallest — the 600-row window intersects more blocks, it does not swallow them.
2. **Confirmed, and stronger than predicted:** zero unstable questions on all surfaces in
   both processes — at both layers, where the prediction only claimed the top-k.
3. **Refuted.** 17 straddling questions at base against the predicted ≤5. The set-level
   tail r06 saw (1 of 104) was dedup absorbing the straddles, not their absence.
4. **Confirmed on both halves.** Total wobble 2 < 14; the readable↔cold flap did not
   vanish (34) — the warm-through is untouched, as stated.
5. **Refuted as an equality, confirmed as a containment.** Predicted: the cold pre→post
   changed set equals the straddling census. Observed: exactly one changed question (the
   witness), strictly inside the census — §5 dedup absorbs the other 16 straddles (their
   tie blocks collapse to the same documents), so straddling predicts *eligibility* to
   change, not change. No non-straddling question changed anywhere.

### Verdict

§6.13 is **REPAIRED**. The window is no longer the sampler: the engine's `LIMIT` now cuts
the declared total order (SPEC 0.18.2), the decision-visible effect of the change is
confined to the witness, and the post-fix tree carries **zero retrieval-attributable
nondeterminism** under the frozen two-level C5. Run 13's Δ will be read against a
commit-wobble floor of 2 (both rows named, neither retrieval's), not 14. The residual
channels stay open by design and are named: the §18.9 warm-through (pass-order-dependent
coldness; the flap bucket) and the two accumulation-signature wobble rows. Per the cap,
neither becomes a diagnostic arc; both ride to the next checkpoint as disclosure items.

