# r03 — collapse M0.5 — tie determinism — 2026-08-20

> Checkpoint M0.5 of tranche 2 (`docs/module-collapse-design.md`, adopted at `5852e30`),
> briefed after M0's review as a live-defect finding rather than housekeeping. One conceptual
> move: **every tie on the decision path gets a declared total order**, so a decision is a
> function of the corpus rather than of the interpreter's hash seed or the FTS engine's
> execution order. The priced baseline (r02's O2) waits for this report's review — and, now,
> for a ruling on QUESTIONS R2.

## STATE

* **Tree:** `master` at `5852e30`; **M0's file set is still uncommitted** — the owner's signed
  run of the M0 commit script failed at its replay step (DEVIATIONS 4) and has not been re-run.
  M0.5 was therefore built in a throwaway git worktree (the standing pattern), verified
  byte-identical to the main tree before the fix was applied to it (DEVIATIONS 5). The main
  tree is untouched and commit-ready.
* **Suite / ruff / mypy:** `2498 passed, 35 deselected` (M0's 2,492 plus this checkpoint's
  six); `ruff` clean over `src tests scripts`; **`mypy` clean at 214 source files** — which
  it was not at M0 (DEVIATIONS 1).
* **Daemon:** the answer-brain daemon at `127.0.0.1:8799` was up throughout; it is needed to
  re-record, not to replay.
* **Live surfaces:** unmoved. The four fingerprints are identical before and after the
  re-recording, and identical to M0's:

  ```
  calibration/decisions.jsonl        8e7ecfb55a666076
  ledger/calibration.decisions       47228cb50c61c64b
  pkm external/pending.txt           134810 B
  pkm cache directories              30682
  ```

* **KB writes:** `$LIFE_AGENT_KB/eval/collapse-fixtures/m0-5/` only (M0-S1). The pre-fix set at
  `.../m0/` is retained, unmodified, as evidence. Nothing else under `$LIFE_AGENT_KB` was
  written; the O1 compensating record the owner wrote earlier is under `ledger/` (S1) and is
  not this checkpoint's.
* **Spend:** $0. Every instrument in this report is a cassette replay or a read-only DuckDB
  query; the recorder ran under `sealed()` in no-spend mode and named its three cold-derivation
  absences rather than paying for them.

## DONE

### 1. Pre-registration — the affected fixtures, named before the fix landed

The brief requires the affected ids to be pre-registered from the seed sweep *before* the fix
lands, with the direction stated. Both sweeps below ran on the pre-fix tree.

**The seed sweep (`~/.cache/life-agent/m0-5/seed-sweep.sh`, $0 — cassette replay: no engine,
no model, no corpus).** The replay refuses a seed mismatch by design, so each seed replays a
*copy* of the m0 set with `provenance.python_hash_seed` rewritten; the recorded decisions are
untouched, only the guard's expectation moves.

```
seed 0: 102/102   seed 1: 85/102   seed 2: 84/102   seed 3: 90/102   seed 4: 85/102
25 fixture(s) diverge on seed alone   (24.5% of the recorded battery)
```

M0 measured one seed (18/102 at seed 2); the union over five is half again as large. The
per-fixture list, with the seeds at which each diverges, is at
`~/.cache/life-agent/m0-5/sweep-before/divergence.txt`:

```
q2-002 [2,3,4]  q2-005 [1,4]    q2-006 [1,2,3]+[4]  q2-011 [1,2,4]  q2-014 [1,3]
q2-018 [1,3]*   q2-025 [1,2,3,4] q2-026 [1,2,3,4]   q2-027 [1,2]    q2-029 [2,4]
q2-039 [3,4]*   q2-045 [1,2]    q2-049 [1,2,4]      q2-053 [1,2,4]  q2-058 [2]
q2-059 [2,4]    q2-068 [2]      q2-075 [1,2,3,4]    q2-081 [1,2,3,4] q2-087 [1,3,4]
q2-089 [1,3,4]  q2-090 [1,4]    q2-091 [2,3]        q2-096 [2]      q2-105 [1,2,4]
   (seeds at which the fixture diverges; * = a field mismatch, + = both kinds at different
    seeds, unmarked = a cassette miss — see the direction note below)
```

**Direction, pre-registered.** At each of these sites the fix replaces an *arbitrary* survivor
with a *declared* one (first-seen at equal covariate). So: decisions identical everywhere the
tie did not bind; on these 25, the decision may change, and where it does the change is the
declared survivor's. No other fixture may move — a mismatch outside this set is a regression,
not the intended change.

**A limit of the instrument, stated rather than discovered.** 22 of the 25 diverge as *cassette
misses*, not field diffs: when a different duplicate document survives, the host asks the
engine to condition a group it never asked for during recording, so the recorded wire traffic
cannot answer. For those fixtures the old baseline cannot say "the new decision is the
intended one" — only that the wire traffic changed. That claim is carried instead by the
re-recorded baseline (§6) and by the unit tests (§2), and the old set's role for them ends at
"this is where the tie bound".

**An attribution the brief did not assume.** The seed sweep measures **finding 1 only**. At
replay `/retrieve` is served from the cassette, so `retrieve_set` never executes; finding 2
changes what gets *recorded*, not what replays. The two findings therefore have two separate
kills, and neither can mask the other.

### 2. The two fixes — a declared total order at each site

Both are TDD; the RED transcripts are below each. Neither changes a rule, only what happens
when a rule has nothing left to choose by.

**(a) `lookup.dedup_correlated` — the equal-covariate survivor is the first-seen document**
(`src/life_agent/core/lookup.py`). The cluster's documents were collected into a `set` and the
survivor taken with `max()`, so at equal covariate the winner was whichever key the
interpreter's string hash happened to order first. Now the distinct documents are collected in
first-seen order (`dict.fromkeys`), and `max` — which returns the *first* maximal element —
becomes a declared rule. A strictly stronger later copy still wins: the tie-break is a
tie-break, not a policy change, and there is a test that says so.

```
$ uv run pytest tests/test_lookup.py -k first_seen
>           assert kept[0].artifact_cache_key == first, f"pair {i} took the second document"
E           AssertionError: pair 0 took the second document
```

The test sweeps 64 key pairs rather than one, because a single pair agrees with hash order
half the time — a one-pair test would be a coin flip, not a kill.

**(b) `core/retrieval.py:retrieve_set` — the over-fetch is ordered before it is deduped.**
The declared key is `(-score, artifact_cache_key, chunk_text)`. Ordering *first* means the
dedupe's own tie — the same chunk text at the same score in two documents — resolves by the
declared key too, while the rule it implements is untouched: the order is score-major, so the
best-scoring copy of a chunk is still the one that survives. Four tests: order-invariance of
the output under a permuted input, the declared ranking, the duplicate-chunk case, and the
unchanged best-score rule (that last one passed before the fix and must keep passing).

### 3. What moved, and the proof that nothing else did

**7.2 against the pre-fix baseline** (`collapse_replay --checkpoint m0`, seed 0, the fixed
tree): `80/102`, **22 fixtures moved**, exit 1 — an intended, pre-registered difference, not a
regression. 20 of the 22 are in the pre-registered set; the other two are DEVIATIONS 2.

Two of the 22 moved as *field* diffs rather than cassette misses, and they are the ones worth
reading, because they show the direction concretely (values withheld — corpus):

* **q2-039**: `asserted` and `candidates` change **case only** — the surviving copy capitalises
  a proper noun that the previously-surviving copy had lower-cased. Same claim, different
  copy's rendering.
* **q2-006**: one of five candidates changes its **connective** — the same technical claim
  written with a different symbol by a different copy of the document.

That is exactly the pre-registered direction: where the tie bound, the fix swaps an arbitrary
surviving copy for a declared one, and what changes is that copy's surface rendering.

**Attribution, by two control runs rather than by argument:**

```
type fixes only, no tie fixes      → 102/102   (DEVIATIONS 1 is behaviourally inert)
retrieval fix only, dedup reverted → 102/102   (at replay /retrieve is served from the
                                                cassette; retrieve_set never executes)
both fixes                         →  80/102   (all 22 moves are dedup_correlated's)
```

So the seed sweep and the retrieval probe measure **one finding each**, and neither can mask
the other.

### 4. Kill 1 — the seed sweep, on the re-recorded baseline

The checkpoint's own kill: the defect re-demonstrated, then shown dead. **Before**, replaying
the m0 baseline at another seed (the pre-fix tree):

```
seed 0: 102/102   seed 1: 85/102   seed 2: 84/102   seed 3: 90/102   seed 4: 85/102
seed 5:  86/102   seed 6: 84/102   seed 7: 86/102   seed 8: 86/102   seed 9: 88/102
seed 10: 88/102   seed 11: 86/102  seed 12: 86/102          → 27 distinct fixtures diverge
```

Twenty-eight, counting q2-040, whose tie surfaced at exactly one of the 45 seeds tried
(DEVIATIONS 2). Twelve to eighteen fixtures decide differently at every seed but the one
the baseline was recorded at.

**After**, replaying the re-recorded `m0-5` baseline — the same 14 seeds, including seed 41,
the only one of 45 at which q2-040's tie ever surfaced:

```
seed 0..12: 102/102 each   ·   seed 41: 102/102   ·   0 fixture(s) diverge on seed alone
```

A fix whose defect was never re-demonstrated is a green that cannot fail; this one was
demonstrated at 13 seeds and is dead at 14.

### 5. Kill 2 — retrieval determinism, measured directly

Read-only against the live catalogue, question by locator (the text stays in the KB). Three
identical calls in one process, then one process per hash seed, at `k=80` — the eval pool.

**One question, before and after** (q2-002; `set_digest`/`order_digest` are sha-prefixes over
the returned `artifact_cache_key` + chunk digest, as a set and as a list):

```
before   order_digest  973d5e7c5a67 · 64e83e53869b · 64e83e53869b   → order UNSTABLE
         set_digest    8b44fa950e7a · 8b44fa950e7a · 8b44fa950e7a   → set stable, 1 tie of 80
after    set stable; order still varies — see §5b, this is a THIRD source
```

Across processes the picture is the same, and that is the informative part: the three seeds
draw from the *same two* order digests, so the instability is **not** seed-linked at this site —
it is run-linked, and a fresh process is no more reproducible than a second call in the same
one. Finding 1's kill needed a seed sweep; finding 2's does not, and would have been missed by
one.

**The whole battery, before and after** (104 questions, three identical calls each, k=80):

| | different ORDER | different SET | questions with ties | tied hits |
|---|---|---|---|---|
| before | **87 / 104 (84%)** | **45 / 104 (43%)** | 88 | 742 |
| after  | 48 / 104 | 22 / 104 | 88 | 742 |

The declared order roughly halves both and does not close either, for the reason in §5b. The
tie census is unchanged, as it must be — the fix orders ties, it does not remove them.

### 5b. A third unordered source, named and NOT fixed (the brief's standing instruction)

The declared order halves the instability and cannot close it. The cause is a third source,
different in kind from the first two, and it defeats a key whose leading term is the score:

```
$ 3 identical search() calls, one process, k=320   (question q2-002, text withheld)
hits: [320, 320, 320] · union: 320
keys whose SCORE differs between identical calls: 149
    …0a75  15.390347572563693  15.390347572563691  15.390347572563693
    …67cb  14.219356129465888  14.219356129465888  14.219356129465886
    …86f9  15.070991045033319  15.070991045033320  15.070991045033319
```

**pkm's BM25 scores are not reproducible to the last bits** — 149 of 320 hits scored
differently between identical calls, by ~1–2 ulp (relative ~1e-15). Floating-point addition is
not associative and DuckDB sums in a parallelism-dependent order, so `score` itself is a
noisy quantity. A sort key whose leading term is `-score` therefore cannot be a total order,
however good its tie-breakers: two hits whose true scores are equal (or closer than the noise)
still swap.

Per the brief — *"if the fix surfaces a third unordered source, it is a QUESTIONS item with its
locator, not a third change"* — it is **not fixed here**. Locator:
`src/life_agent/core/retrieval.py:retrieve_set`, the sort key's leading term; the source is
`pkm.retrieval.search`'s BM25 column, `src/pkm/retrieval.py`.

*The one-line fix, for the reviewer to rule on* — measured by applying it, running the whole
battery, and reverting it, so the number below is real and the shipped tree does **not** carry
it: quantise the leading term —
`key=lambda h: (-round(h.score, 9), h.artifact_cache_key, h.chunk_text)`. At BM25 magnitudes
of ~10–40 that discards ~1e-15 of noise and nothing else, turning near-ties into declared ties
resolved by the document key. It is one token on one line, at the site already being changed.

*What it costs to leave:* 22 of 104 questions still return a *different set* between identical
calls, so for those the evidence a decision reasons over is still not a function of the corpus;
and 48 return a different order, so the retrieval-set content hash — and the §18.9 chain keyed
on it (`retrieve_key` → `synthesize_key`) — still re-derives cold across runs. The fixtures
themselves are unaffected: they record the hits as an *input*, and 14 seeds × 102 fixtures
replay identically. **This is the same argument that put M0.5 before the priced baseline**, so
it is repeated for r02's O2: paying to record a priced baseline against a retrieval that still moves
for a fifth of the battery buys a fixture set that cannot be re-recorded to match itself.

### 6. The re-recorded baseline — and what changed in it

Recorded from the fixed tree with the same recorder, the same `k=20`, the same seal and the
same two free traces, seed pinned at 0 and stamped into every fixture's provenance:
`$LIFE_AGENT_KB/eval/collapse-fixtures/m0-5/` — **102 fixtures**, the same three named
absences as m0 (three questions whose §18.9 derivation is cold; the recorder refuses to buy
one), live surfaces unmoved. **This is the baseline of record for M1 onward.** The pre-fix set
stays at `.../m0/` as evidence and is never deleted; it is no longer replay-valid against the
tree, which is the point of retaining it.

**What changed, fixture by fixture.** Comparing the two sets on the same 102 keys, only **three
decisions changed their terminal**:

```
q2-059   hedge  -> report
q2-087   report -> abstain
q2-090   report -> abstain
```

Reach is flat to within one answer; the checkpoint claims *reproducibility*, not improvement,
and this table is the whole of its decision-level effect. The remaining 19 moved fixtures kept
their terminal and changed only which duplicate copy supplied the surviving observations (and,
in two cases, that copy's surface rendering — DONE 3).

**One coverage regression, named.** `terminal:hedge` had exactly one fixture (q2-059) and it is
now a `report`, so the re-recorded set has **no hedge fixture**. Against §7.2's Q9 coverage
condition ("at least one fixture per terminal type") that is a hole where m0 had none, and it
joins the holes m0 already named (`report_scoped`, `ask_clarify`, `report(claims)`, and the
three unrecorded traces). It is not repaired here: manufacturing a hedge would mean choosing a
question for its terminal, which is the coverage equivalent of fitting to the test. PROPOSED
carries it into M1's brief instead.

### 7. The register and the §14 ledger

* **§6.1 gains the Q4 citation (M0's R1, confirmed).** The reading — `draw` is served but has
  no method for the utility posterior's measures, so P(U) is not wire-samplable and G-3 stays
  inside the exception — is now recorded with the test that flips it, named in full, so the
  ruling revises itself if the engine ever gains the capability.
* **§6.6 is new: an instrument-design rule, not a decision-shaping exception** — *path
  redirection is not isolation; only sinking is.* A writer that takes no path argument falls
  through to `core/config.py`, so redirecting the configured path moves the instrument's writes
  onto whatever the config now names, and the C5 mirror faithfully mirrors them, because that
  path *is* the configured one; the guard that should have caught it cannot fire. It cites
  `drive.sealed()` and the fall-through test by name. It lives in the register because the
  register is what the next census reads.
* **`docs/bayesian-foundations.md` §14 gains the finding** as a live-defect entry, with the
  part that matters most for the ledger's own honesty: **what kept the readings comparable was
  the §18.9 cache, not the code.** `retrieve_key` is keyed on (query, corpus digest, k) and the
  answer stage on its content hash, so the first run to compute a stage froze one arbitrary
  draw and every later run was served it. Comparability held exactly as long as the cache entry
  survived; any recomputation — new question, corpus-digest change, different `k`, version bump,
  or a cache loss like the 2026-08-18 orphan sweep — silently re-rolled it. The entry states
  plainly that it does not repair the readings already in the ledger, which stand as recorded
  with it as their caveat.

## DEVIATIONS

**1. M0 was not mypy-clean, and its report is silent on it.** The M0 brief's discipline line
required "ruff/mypy/guard clean"; I ran the guard, the suite and ruff, and did not run mypy.
It reports **13 errors, all in M0's own files** (`collapse/{fixture,taps,drive}.py`,
`scripts/collapse_record.py`) — the rest of the tree is clean, as tranche 1 last recorded it.
Fixed here, type-only: annotations for three inferred-`None` slots, two `type: ignore`s that
mypy itself calls unused, the sunk-append module pair named as `Any` (mypy cannot see an
attribute on a union of module objects), and one `list.append(...) or {...}` idiom rewritten
as a named function. **Proven behaviourally inert by a control run:** the tree carrying the
type changes and *not* the tie fixes replays the M0 baseline `102/102`. I did not fold this
into M0's commit: M0 is the artefact the reviewer accepted, and it should land as reviewed.
The cost is stated plainly — master is mypy-red for exactly one commit. M0.5's commit script
runs mypy; M0's does not, which is how this was missed.

**2. The pre-registered fixture set is a lower bound, and I stated it as the set.** A seed
sweep enumerates the orders it samples, not the ties that exist. Under the fix, 22 fixtures
moved: 20 of the 25 pre-registered, plus **q2-008 and q2-040**, which agreed across seeds 0–4.
Both are the same class, proven by widening the sweep on the pre-fix tree: q2-008 diverges at
seed 6, q2-040 at seed 41 (of 45 seeds tried). The five pre-registered fixtures that did *not*
move are the ones whose declared first-seen survivor happens to equal their seed-0 winner. So
the correct pre-registration is the **class** — fixtures whose duplicate-quote cluster carries
an equal-covariate tie — with the sweep as its evidence rather than its definition. Every
fixture that moved is accounted for; none is unexplained.

**3. A reading on `retrieve_set`, not a transcription.** The brief named the sort key and said
"the over-fetch and dedupe-by-chunk-text behaviour is otherwise unchanged". Sorting *after*
the dedupe leaves a second tie at the same site live: identical chunk text at an identical
score in two documents — this corpus's commonest shape — was resolved by arrival order, and it
is what moves the retrieved *set* for 45 of 104 questions, not just its ranking. I therefore
ordered the over-fetch **before** deduping, which resolves that tie with the same declared key
while leaving the rule untouched (the best-scoring copy of a chunk still wins, since the order
is score-major). One change, one site, one declared order — but it is a reading, so it is
named here for the reviewer rather than assumed (QUESTIONS R1).

**4. The M0 commit script relied on an ambient `PYTHONHASHSEED`.** My rehearsal inherited the
variable from the shell I had recorded in, so it passed there and failed on the owner's signed
run at the replay step (`refusing: fixtures were recorded at PYTHONHASHSEED=['0'] and this
process has 'None'`). Nothing was committed; the guard, suite and ruff had all passed. Fixed
by pinning the seed at the invocation and verified from a scrubbed environment
(`env -u PYTHONHASHSEED …` → `102/102`, exit 0). The rehearsal proved less than it appeared
to — the same defect class this checkpoint exists to close, in the harness rather than the
decision path.

**5. M0.5 was built in a throwaway git worktree** (the standing pattern for a checkpoint whose
tree state is not yet committed),
because M0's file set is still uncommitted in the main tree and `src/life_agent/core/lookup.py`
carries both checkpoints' changes. Committing M0 with the fix present would have swept a
decision-path change into a reviewed checkpoint and broken its bisectability. The worktree was
verified byte-identical to the main tree before the fix was applied to it.

**6. The rehearsal's mypy pass was on a tree that no commit reproduces.** M0.5 was rehearsed
in a worktree carrying M0's file set as *uncommitted* working state, and DEVIATIONS 1's
type-only fixes live on those M0 files. The checkpoint's commit lists the M0.5 files, so the
script that moved the checkpoint onto master left the four fixed M0 files behind, and the
owner's signed run stopped at the mypy gate — 13 errors, exactly the ones DEVIATIONS 1
describes, against the versions M0 had by then committed. Fixed by carrying those four files
with the checkpoint and naming them in its commit message; nothing about the two tie fixes
changed, and the suite, ruff, guard and replay were re-run over the widened set. This is
DEVIATIONS 4's class a second time in one checkpoint — a rehearsal passing on state its
replay does not carry — which is an argument about the harness, not the decision path
(QUESTIONS R5).

## REFUSED

* **The third unordered source is not fixed** (§5b). The brief pre-decided this case — a third
  source is a QUESTIONS item with its locator, not a third change — and I have already read
  scope twice in this checkpoint. Doing it a third time, in the exact case the brief named,
  would be drift rather than judgement. The measurement and a ready patch are supplied instead
  (QUESTIONS R2).
* **No other tie was tidied.** Two sites changed, both named in the brief.
* **Nothing on the collapse path.** E-14 is alive; no entry point moved; `LIFE_AGENT_GROW_LANE`
  is untouched. That is M1.
* **The priced baseline was not run** — owner-executed (r02's O2), and now additionally gated
  on R2 below.
* **M0's report was not edited.** It was reviewed in the state it is in; DEVIATIONS 1's
  correction is recorded here, one checkpoint later, rather than folded back into it.
* **The coverage hole was not manufactured shut** (DONE 6).

## QUESTIONS

**Owner.**

* **O1 — hold the priced baseline (r02's O2) until R2 is ruled.** The reviewer's own reasoning for
  putting M0.5 before O2 applies again with a fifth of the battery still moving between
  identical retrievals. My advice: rule R2, apply or reject the one-liner, re-record, then pay
  once. If you would rather pay now, the script is unchanged and still refuses without
  `ALLOW_SPEND=1`.
* **O2 — the M0 commit still needs running** (`SIGN_M0=1 ~/.cache/life-agent/r02-collapse-m0-commit.sh`,
  seed defect fixed and verified). M0.5's commit script applies cleanly on top of it and is
  rehearsed; the two land in order, M0 then M0.5, and each pushes separately.
  *(Since run: M0 is committed and pushed; M0.5 followed after DEVIATIONS 6's fix.)*

**Reviewer.**

* **R1 — the `retrieve_set` scope reading** (DEVIATIONS 3): ordering the over-fetch *before*
  the dedupe, so the duplicate-chunk tie takes the same declared key. Within the named fix, or
  a change you would rather have seen as a QUESTIONS item?
* **R2 — the third unordered source** (§5b): BM25 scores differ by 1–2 ulp between identical
  calls, so a key led by the raw score cannot be total. Rule on `-round(h.score, 9)`. If it is
  in, it belongs in *this* checkpoint's commit rather than M1's, and the baseline is re-recorded
  before the priced run. Measured effect of the proposal, over the same 104 questions:
  **0 of 104 questions return a different order, 0 a different set** — where the
  shipped fix leaves 48 and 22. The tie census is unchanged (88 questions, 742 tied hits):
  it resolves ties, it does not erase them.
* **R3 — pre-registration as a class, not a list** (DEVIATIONS 2). A seed sweep enumerates the
  orders it samples, not the ties that exist. I propose that from M1 on, a pre-registered
  direction names the *mechanism* and cites the sweep as evidence of it, with the sampled list
  explicitly a lower bound. Confirm, or require an exhaustive enumerator (for the dedup site,
  that is a static check for clusters with an equal-covariate tie, which is buildable).
* **R4 — the `hedge` coverage hole** (DONE 6). Accept it as a named hole carried into M1, or
  require the M1 set to re-establish one fixture per terminal type before 7.2 is trusted for
  the cascade direction?

* **R5 — rehearsal fidelity** (DEVIATIONS 6). Twice now a prepared script has passed in
  rehearsal and failed on the owner's signed run, because the rehearsal inherited state the
  signed run does not have (an ambient seed; an uncommitted file set). I propose that from M1
  on, a checkpoint's commit script is rehearsed against a **clean checkout of exactly the file
  set it will commit**, in a scrubbed environment, and that the report states it was. Confirm,
  or rule the two instances harness noise not worth the extra step.

## PROPOSED

1. Rule R2. If it lands, it is one token on one line, then re-record `m0-5` and re-run both
   kills — an hour of machine time, $0.
2. Owner runs the M0 commit, then M0.5's, then pushes.
3. Then r02's O2, the priced baseline, against a tree whose retrieval is settled — the `A-loop`,
   `A-poster` and `B-narrative` traces M1's pre-registered direction needs underneath it.
4. M1 opens on the review of this report and that baseline, per its brief.

**STOP.**

---

## ADDENDUM — R2 applied (2026-08-20)

The review ruled R2 in: the quantisation lands, *"in this checkpoint's commit"*, on four
conditions. It arrived after `986faf7` was committed **and pushed**, so that phrase cannot be
honoured literally without rewriting published history. This programme's own precedent is a
compensating entry, never an edit (§6.6's provenance record; C6's void manifest), so R2 lands
as a **second commit on the same checkpoint** and this report gains an addendum rather than a
rewrite. That is the one place the ruling is read rather than followed; it is named here so the
reviewer can overrule it, but a force-push over a reviewed and published artefact would cost
more than the literal reading buys.

### A1 — what landed

`core.retrieval.retrieve_set` orders by `-round(score, 9)` in place of `-score`; the
tie-breakers `(artifact_cache_key, chunk_text)` are unchanged. One token on one line.

The quantisation is confined to the **ordering**. The hit dicts still carry `h.score` verbatim,
so every downstream consumer — the §4.1 covariates, the competition detector, the recorded
fixture inputs, every §18.9 key hashed from retrieval-set bytes — sees exactly the number the
engine returned. Nothing that reads a score reads a rounded one.

Three tests, written failing first (`tests/test_retrieval.py`): a one-ulp separation is ranked
as a declared tie; three calls whose scores wobble in the last bits return the same set **and**
the same order; and — the guard against over-quantising — a difference above the quantum still
decides the rank *against* the declared key's preference. The third passed before the change
and must keep passing: it is what pins "resolves ties, does not manufacture them" as a property
rather than a claim.

### A2 — kill 1, the seed sweep, re-run on the re-recorded baseline

`seed-sweep.sh`, widened past the briefed 0–4 to include **seeds 6 and 41** — the two that
DEVIATIONS 2 identified as the ones that broke the original pre-registration (`q2-008` diverges
at 6, `q2-040` at 41 on the pre-fix tree) — so the sweep samples orders known to catch this
class, not only convenient ones. Per R3 the list is evidence, not definition.

```
seed 0: 102/102   seed 1: 102/102   seed 2: 102/102   seed 3: 102/102
seed 4: 102/102   seed 5: 102/102   seed 6: 102/102   seed 41: 102/102
0 fixture(s) diverge on seed alone
```

The same instrument on the pre-M0.5 tree lost 12–18 fixtures per seed, 28 distinct over the
seeds tried.

### A3 — kill 2, retrieval determinism measured directly, with R2's added condition

`retrieval-determinism.sh`, extended with the per-hit score-equality check the ruling asked
for: the same query at k=80, three calls in one process, one process per hash seed, comparing
the **scores themselves** across the three identical calls.

```
q2-053, k=80, 80 hits, 10 tied, 70 distinct scores
  seed 0   raw_bit_stable false   raw_scores_moved 18/80   max_raw_delta 3.55e-15
           quantised_stable true  quantised_scores_moved 0
  seed 1   raw_bit_stable false   raw_scores_moved 16/80   quantised_stable true
  seed 2   raw_bit_stable false   raw_scores_moved 15/80   quantised_stable true
  set_digest    865363e10339   ×3 calls ×3 seeds
  order_digest  bc7f393ebe5a   ×3 calls ×3 seeds
```

The finding and the fix in two lines: the engine's noise is **still there** — 15 to 18 of 80
hits move between identical calls, by up to one ulp — and the sort key no longer sees it. A
reading of `raw_bit_stable true` would have meant the probe was broken, not that the problem
was gone.

### A4 — kill 2 over the population

`retrieval-population.sh`, the whole 104-question battery at k=80, three identical calls each,
run live against the committed tree:

| | order varies | set varies | questions with ties | tied hits |
|---|---|---|---|---|
| before M0.5 | 87 | 45 | 88 | 742 |
| M0.5 orderings only | 48 | 22 | 88 | 742 |
| **with the quantisation** | **0** | **0** | **88** | **742** |

The tie census is identical in all three columns: 48 questions and 22 retrieved sets moved from
"varies between identical calls" to "does not", and no new tie was created to do it. This is a
live re-measurement on the committed code, not r03's apply-and-revert reading.

### A5 — the fixture-level delta table (R2's third condition)

The shallow 7.2 replay **cannot see this fix**: at replay `/retrieve` is served from the
cassette, so `retrieve_set` never executes. The pre-R2 baseline replays `102/102` through the
quantised code and would do so whatever the sort key said. That is not a null result but a
structural blind spot — R3's boundary arriving early ("shallow is sufficient for M1–M4; deep
replay is required at M5"): a retrieval-side change is exactly the class only a deep replay
exercises. So the delta is measured where retrieval actually runs, by **re-recording** and
comparing the two fixture sets under the declared §7.2 comparator.

| of 102 fixtures | |
|---|---|
| retrieval identity unchanged | **85** |
| retrieval merely **reordered** | 8 |
| retrieval **set changed** | 9 |
| decision body changed | **6** |
| terminal class changed | **1** |

Five of the six decision changes differ **only** in `log_decision.retrieval_keys` — the
recorded citation provenance moved, the answer did not (`q2-011`, `q2-018`, `q2-024`, `q2-083`,
`q2-105`). The sixth is `q2-059`, which changed `asserted`, `credences` and `effector`: a real
decision change, and the terminal move below.

### A6 — the baseline of record, and whether it reproduces

`$LIFE_AGENT_KB/eval/collapse-fixtures/m0-5` is re-recorded from the quantised tree and is **the
baseline of record for M1 onward**. Same recorder, same k=20, same seal, same two free traces,
seed pinned at 0 and stamped into each fixture's provenance; 102 fixtures, the same three named
absences as before (`q2-036`, `q2-043`, `q2-095` — cold §18.9 derivations under no-spend), so
the set's membership is unchanged. The pre-R2 set is retained beside it at
`collapse-fixtures/m0-5-pre-r2`, and `m0/` still stands from M0 — evidence, never deleted.

**The claim that the baseline is now reproducible by construction is checkable, so it was
checked** rather than asserted. A third recording was taken from the same code
(`collapse-fixtures/m0-5-verify`, $0) and compared to the baseline of record:

```
m0-5 -> m0-5-verify   (102 common fixtures)
  retrieval: identical 102 · reordered 0 · set changed 0
  decision differs, excluding run_id: 0
  terminal moved: 0
```

The only field that differs is `log_decision.decision.run_id`, which is
`f"collapse-{checkpoint}"` by construction (`scripts/collapse_record.py:119`) and therefore
must differ when the verification is recorded under a different checkpoint name. Every other
field, on every fixture, is identical. Before M0.5 a re-record was one arbitrary draw from an
unordered engine; it now returns the same evidence twice.

A stale-file hazard was checked and is clean: the recorder writes fixtures by name into an
existing directory and **never clears it**, so a fixture that failed on a later run would leave
its predecessor in place and the manifest — which globs the directory — would list it as
current. All 103 files were rewritten in the run and none predates it. That deserves a guard in
the recorder rather than a check in a report; not taken here, since it is neither named fix
(**QUESTIONS R8**).

**`terminal:hedge` is no longer a coverage hole.** It was named as one at M0.5 and R4 accepted
it on the expectation that a hedge might arise in the priced set. One arose in the **free** set
instead: the quantised retrieval moved `q2-059` from `report` to `hedge`. The baseline now
covers abstain 61 · report 38 · hedge 1 · miss 2.

### A7 — the other four rulings, dispositioned

* **R1 — confirmed.** Recorded; no further work.
* **R3 — adopted as practice from M1.** A pre-registration names the **mechanism**, cites the
  sweep as evidence, and states the sampled list as a lower bound. No exhaustive enumerator is
  built: the ruling's test is whether a checkpoint's *direction* depends on completeness, and
  M1's depends on classification. A2 already applies the standard by sampling the seeds known
  to catch the class rather than the convenient ones.
* **R4 — the condition is met and the hole is closed** (A6). The ruling's own escape clause
  fired, in the free set rather than the priced one. M1 inherits a pinned hedge path and does
  not need the argued-claim fallback; the instruction stands anyway on its merits, and M1's
  report will still say whether the cascade deletion can reach that path — now with a fixture
  behind the answer.
* **R5 — confirmed, and built effective now rather than at M1** (A8).

### A8 — the clean-checkout rehearsal (R5), stated as run

The instrument is `~/.cache/life-agent/r2/rehearse-clean.sh`: a throwaway worktree at HEAD into
which **only the files the commit will contain** are copied, then the gate sequence under
`env -u` for every variable a gate depends on (`PYTHONHASHSEED`, `LIFE_AGENT_KB`), with the
replay's seed pinned at its own invocation. Anything the commit forgets to list is therefore
absent from the rehearsal — which is the check that would have caught both prior failures.

This commit is its first user, and it passed from a clean checkout at `986faf7`:

```
== the file set is complete? (nothing else differs from HEAD)
 M docs/bayesian-foundations.md · docs/module-collapse-design.md
 M docs/unification/reports/r03-collapse-m0-5.md
 M src/life_agent/core/retrieval.py · tests/test_retrieval.py
guard exit=0
2501 passed, 35 deselected            (2498 at M0.5; +3 is this addendum's tests)
ruff  All checks passed!
mypy  Success: no issues found in 214 source files
replay  102/102 fixtures replay identically     (against the RE-RECORDED baseline)
== clean-checkout rehearsal PASSED
```

The `git status` line is the load-bearing one: five files differ from HEAD and nothing else, so
the commit's file list is provably complete. That is the assertion neither prior rehearsal
could make, and the one whose absence produced both failures.

### A9 — a FOURTH unordered source, named not fixed

The standing instruction that governed the third source governs this one: if the fix surfaces
another, it is a QUESTIONS item with its locator, not another change. It did.

`life_agent.core.probes.probe_corroborate` (`src/life_agent/core/probes.py:189-208`) carries
the **pre-M0.5 shape at both layers**, in one function:

* it dedupes by chunk text keeping the best score with a strict `>` (`probes.py:203-204`), so
  at an equal score the **first-arrived** copy wins — the engine's order decides which document
  survives, which is finding (2) exactly;
* it then sorts on the **raw score with no tie-breakers at all** (`probes.py:205`) and cuts at
  top-k — so both the tie order and the ulp noise reach the cut.

It is **on the decision path** when the gather lane runs: `core/gather.py:94` calls it
per-candidate and `scripts/ask.py:803` takes that branch under `if gather:`. The bridge also
exposes it at `/probe/corroborate` (`bridge/server.py:427`). No recorded fixture exercises it —
the free baseline's B-lookup trace does not enter the gather lane — so neither the replay nor
the re-record can see it, and the population probe measures `retrieve_set`, not this.

I have not touched it. The fix is mechanically the same one line plus the declared key, and
"mechanically the same" is precisely the argument that would have justified taking the third
source silently at M0.5.

### A10 — deviations in this addendum

**A10.1 — I wrote a second oracle instead of using the declared one, and it gave a wrong
answer first.** The fixture-delta instrument initially hand-rolled a digest over whole hit
dicts and whole `outputs` bodies. It reported **91** retrieval moves and **99** decision moves;
both were artefacts. The 91 counted 1-ulp drift in the recorded *score value* as a retrieval
change, when the delivered set and order were identical; the 99 counted `run_id`, which differs
by construction under a renamed checkpoint. The true figures are 17 and 6. Fixed by comparing
the retrieval **identity** (the ordered `(document, chunk)` list) and by calling
`life_agent.collapse.compare.compare_outputs` — the §7.2 comparator that already existed and
already encodes the field classes, floats at 1e-9 and all. This is §6.7 in miniature: the check
existed, and a hand-rolled substitute reported a number that would have gone into a report
unchallenged had the two readings not disagreed with the population probe.

**A10.2 — the verification recording was not asked for.** R2's conditions are the two kills,
the re-record, the delta table and the §14 extension. The third recording (A6) is extra machine
time ($0, no-spend seal held) spent to convert "reproducible by construction" from a claim into
a measurement. It also produced the only reading that isolates the fix's effect from the
instability it removes, so the delta table in A5 can be read as the fix's effect rather than as
an upper bound.

### A11 — QUESTIONS carried forward

* **R6 — the fourth source** (A9). Rule it in or out. If in, it is R2's shape again and belongs
  in a third commit on this checkpoint with the same two kills, plus a decision on whether the
  gather lane needs its own fixture trace first — it currently has none, so no oracle would
  catch a regression there. If out, it should be named in the register as a known unordered
  source the fixture set does not cover, so the next census does not rediscover it as new.
* **R7 — the fixture set records the traces the recorder was told to run, and nothing else.**
  A9's blind spot is not specific to A9: the gather lane is unpinned, and `terminal:hedge` was
  unpinned until an unrelated change happened to produce one. Both were invisible to the
  shallow oracle for the same structural reason. Is the priced baseline the right place to
  widen trace coverage, or does that belong in its own checkpoint after M1?
* **R8 — the recorder does not clear its output directory** (A6). A failed fixture silently
  leaves its predecessor in the set, and the manifest globs the directory, so a mixed baseline
  would present as a whole one. Checked clean by hand this time. Worth a guard — refuse to
  write into a non-empty checkpoint directory without an explicit flag — or is a documented
  hazard enough?

**STOP.** The priced baseline (r02's O2) now runs against a settled retrieval; M1 opens on the
review of this addendum and that baseline.

## REVIEW 2 — dispositions applied (2026-08-20)

The addendum's review discharged **R2 in full** and ruled on the three questions the addendum
carried. This section records what was applied, and one correction to the sequence.

**The addendum's commit had already run.** The review's closing sequence names it as the next
step. It was not a separate commit: the addendum was written before `30da5f5` was signed and
rode that commit as one of its five files, because R2's ruling asked for the quantisation to
land *in this checkpoint's commit* and this report is one of the files that commit carried
(`git show --stat 30da5f5`). Master is at `30da5f5`, pushed, with the R5 clean-checkout
rehearsal proven on exactly that content. Nothing is outstanding there.

* **R6 — registered, sequenced to M1 behind a trace.** The fourth unordered source is now
  `module-collapse-design.md` **§6.9**: what it is, why M0.5 left it, the ruled disposition
  (record a gather-lane trace first, then the same declared key with the same two kills, at
  M1's checkpoint), and the pre-committed fallback (convert to a standing register entry naming
  it known-and-uncovered, and M1 proceeds without the fix). It is also named as source (4) in
  `bayesian-foundations.md` §14, whose entry is retitled *Four* unordered sources. No code
  changed here: the ruling is that a fix with no oracle is a hope, not a fix.
* **R7 — M1.5, the coverage census.** A new row in §8's table between M1 and M2, scoped as the
  review states it: enumerate every reachable lane and terminal, and for each either record a
  fixture or register it as known-and-uncovered. The row carries the structural reason —
  *the fixture set pins the traces the recorder was told to run, so coverage is a declared
  quantity, not an emergent one* — and the attribution argument for why it is not folded into
  the priced baseline. It inherits §6.9's gather trace as its first row.
* **R8 — a guard, riding M1's commit.** Recorded in §8's M1 row as part of that checkpoint's
  commit: refuse to write into a non-empty checkpoint directory without an explicit flag. Not
  built here — this checkpoint is closed, and the guard belongs to the commit that will next
  exercise the recorder.
* **A10.1 — its own register line.** `module-collapse-design.md` **§6.8**: *the declared
  comparator is the only oracle; a second one built for convenience is a defect even when it
  agrees.* It cites `compare_outputs`, the two artefact figures, and the fact that only a third
  contradicting reading caught it — agreement would have taught nothing and would have been
  quoted as corroboration.

**One more §6.7 instance, found preparing O2.** The priced-baseline script written at M0 (r02's
O2) was rehearsed before signing and refused twice on its own gates. It carried two defects
that a sentence would not have caught: its merge target was `m0/`, written before M0.5 existed
and therefore no longer the baseline of record, and it labelled the priced fixtures under a
second checkpoint name that would have put two labels inside one baseline directory; and it
**inherited** `PYTHONHASHSEED` rather than pinning it, which the recorder refuses only when the
variable is unset — an ambient non-zero value records cleanly and fails at replay, after the
spend. Both are R5's lesson with a bill attached. The replacement executes each of its
preconditions as a gate (settled tree; baseline labelled and seeded as expected; the five fold
inputs unmoved since the baseline was recorded, so both runs pin the same snapshot; R8's
hazard, executed rather than documented; `PKM_CONFIG` present; daemon up), and its merge step
gates snapshot byte-equality and fixture-id collisions and writes an undo list. Rehearsed at
$0: the live gates pass, three refusal paths were witnessed (stale staging directory,
wrong-checkpoint baseline, dirty worktree), and the full merge ran end to end on copies —
102 → 105 fixtures, manifest regenerated over the merged set, 105/105 replaying identically.
The real baseline was not touched.

**STOP.** This checkpoint is closed. Next is r02's O2 — the priced baseline against the settled
tree — after which M1 opens on the brief, with the three amendments this review names.
