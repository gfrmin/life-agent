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
