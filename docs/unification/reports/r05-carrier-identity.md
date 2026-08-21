# r05 — the carrier-identity checkpoint — 2026-08-22

> **IN PROGRESS.** Written as the checkpoint runs, not reconstructed afterwards. Sections
> appear in the order the work happened; nothing below is a plan.

Opened on r04 **RULING 4**: *"The carrier-identity finding gets its own register entry and
its own pre-registered criteria before anything changes in `retrieval.py` or `probes.py`. It
is not folded into R6 and it is not patched here."*

## STATE

Master at `fcfc8a3`, clean. The isolation ladder is closed (r04 DONE 12): §6.9's declared
probe order is **convicted** as what carried run 10's single wrong commit, and is
deliberately **not reverted** — the old order is nondeterministic, a luckier ticket rather
than a better rule. Master therefore knowingly carries the configuration that produces the
wrong commit, and **the arc is not deployed and must not be before this checkpoint closes.**
That is what makes this checkpoint the critical path rather than the next item on a list.

## DONE 1 — the register entry, before any measurement

`docs/module-collapse-design.md` **§6.11 — carrier identity: which document represents
duplicated text must not decide the answer.**

The mechanism, stated so the fix has a target. `core/retrieval.retrieve_set` dedupes the
over-fetched hits by `chunk_text` and keeps ONE; that survivor's `artifact_cache_key` becomes
the text's carrier for the whole decision. Everything downstream is keyed on it —
`observe_hits` reads the §4.1 covariates per artifact, and `lookup_posterior` **groups the
observations BY artifact**, one `group_noisy_channel` per document sharing r_d. So the choice
sets both the weight on an observation and the **correlation structure** of the evidence: two
chunks that would have shared a document, and been conditioned as one correlated group,
instead land in two documents and are conditioned as more nearly independent — purely because
different copies won their dedups.

Byte-identical text scores identically, so R2's declared key
`(-round(score, 9), artifact_cache_key, chunk_text)` resolves the tie on the lexicographically
smaller content hash. Deterministic, reproducible, and arbitrary: a coin flip frozen, not
resolved.

**Why a declared order is not the fix, which is what run 12 bought.** §6.9 declared exactly
this key one layer over, on the probe path, and the gate convicted it — and the conviction's
content is narrower than it sounds: the key did not add the wrong candidate and did not swap
the leader (the same competitor led in runs 10, 11 AND 12); it *concentrated* the posterior
enough to carry an already-wrong leader over the commit bar. A declared total order buys
reproducibility, not a right answer. Where the tie is between **witnesses of the same
content**, the decision must not depend on the choice at all — so the property under test is
**invariance**, not a better rule for choosing.

**The tell was already in the tree.** The same duplicate-witness question is answered twice,
by two different rules: §5's `lookup.dedup_correlated` collapses a cross-document duplicate
quote to the **max-covariate** document — substantive, and deliberately order-free — while
`retrieve_set` answers it with a content hash one layer earlier. `retrieve_set`'s answer is
the one that stands, because by the time §5 runs the losing carriers have already been
discarded. Only one of the two can be right.

## DONE 2 — the criteria, frozen before the instrument reads

`scripts/carrier_audit.py`'s module docstring carries the full text and predates its first
run; the §14 ledger carries the pre-registration. In summary:

- **Exposure is reported and is never a bar on its own** — the corroborate refusal's standing
  rule: a lever's ceiling is counted in QUESTIONS whose committed answer would change, never
  in artifacts, chunks or texts.
- **The alternative rule is named in advance** so it cannot be tuned to the reading: the §5
  max-covariate representative lifted one layer up, declared key within equal covariate. The
  adversarial permutations bound exposure and are never candidate rules.
- **BUILD** iff load-bearing exposure ≥ 5 questions AND regressions ≤ repairs;
  **REFUSE** iff regressions > repairs; **PRICE a gate run** iff delivered reach ≥ 1, else the
  fix lands on a hermetic permutation-invariance test with no run bought. Below 5 the entry
  converts to a standing known-and-uncovered source — §6.9's own fallback shape.
- **No spend.** Extractions are keyed on the chunk sha, so a re-carried byte-identical chunk
  is a cache hit; anything cold excludes its question **by name**.

**Named in advance, and it decides how a null reading may be read:** the audit decides at the
**lookup layer**, not the executor's (rerank/gather/deliberate sit above it and spend); an
uncached owner verdict degrades a carrier's subject state to `unclear`; and the over-fetch
window can truncate a carrier list. All three biases point toward **under**-detection, so a
BUILD reading is safe against them and a NO-GO reading is the provisional one.

## DEVIATION 1 — the instrument was written before its tests, and the smoke test paid for it

Recorded because it cuts against this repo's own rule. `scripts/carrier_audit.py` was built
first and a three-question `--only` smoke test run before the battery. That smoke test found
**two measurement bugs and one blind spot**, all fixed before any reading:

1. **Divergence was read off the carrier's provenance identity**, which includes the origin
   path — but two email copies at different paths share an authority class, so it reported
   divergence where the weight is bit-identical. It **over-stated** load-bearing exposure. It
   now compares the factor triple the posterior consumes.
2. **The partition was compared as a key SET**, but `lookup_posterior` groups by the
   *assignment* text → document; two assignments can share a key set and group differently.
   It **under-stated** the change. It now compares the assignment.
3. **The blind spot:** where the carriers' factor triples tie, `max` over a declared-order
   list returns the same first element — so the pre-registered rule degenerates to today's
   behaviour, and what survives is *grouping* arbitrariness, which nothing measured. Two
   grouping-adversarial permutations were added as **diagnostic bounds only**.

Tests came after and are honest about it: both regression tests were checked **RED against a
restored-bug build** before being kept. TDD would have caught (1) and (2); instead a reading
was nearly taken on a mis-measure.

**And a fourth, found after the first reading — disclosed here because it changes the
verdict.** Criterion 3 as frozen reads: *"questions with ≥ 1 multi-carried text whose carriers
DISAGREE on … the document partition the observations group by"*. The subject is **the
carriers**; the clause is rule-independent, exactly like its two siblings (covariate
divergence, `_fresh_hits` survival). The implementation instead measured *whether the named
rule of criterion 4 moves the partition* — criterion 5's question, not criterion 3's. Where
that rule is a no-op, as it is here, it reports an arbitrariness that is plainly present as
absent. The clause is now measured off the carriers: the partition the observations induce
under max-independence versus under max-correlation, compared as a *partition* (relabelling a
group is not a change; splitting or merging one is). **This correction was made after the
first battery reading and it flips surface (a) from NO-GO to BUILD.** It is recorded in this
position, in the chronology, rather than folded quietly into the numbers — and the report
below carries both quantities so the reader can score the correction rather than take it.

Three of the four defects were in the instrument's *measures*, not its plumbing, and every one
of them would have produced a confident number. That is the pattern worth carrying forward: an
audit that runs is not an audit that measures the thing its criteria name.

## DONE 3 — surface (a), the cheap first pass: **BUILD**, and the named fix is a no-op

`gate-20260821T094545` (run 10 — master's tree), k=20, decay as of the run's own date, $0.

| | |
|---|---|
| questions audited | **102** (2 excluded by name) |
| deduped texts in the top-k | 2040 |
| multi-carried texts | **57**, in 23 questions |
| …decided by the content hash alone | **57 of 57** |
| texts whose carriers diverge on the covariate triple | **0** |
| **questions whose carriers admit a different document partition** (criterion 3, as frozen) | **17** |
| …of which the NAMED rule of criterion 4 actually moves | **0** |
| **load-bearing exposure** | **17** |
| **delivered reach** (criterion 5, under the named rule) | **0** — every question unchanged |

**Verdict, applied mechanically: BUILD (17 ≥ 5, regressions 0 ≤ repairs 0), and no gate run
bought (delivered reach 0).** Under the instrument's first, unfaithful reading of criterion 3
the same battery said NO-GO at 0 — that is DEVIATION 1(4), and the two numbers are published
side by side above so the correction can be scored rather than taken.

**Why the named rule is a no-op, which is the substantive finding.** The covariate triple never
differs between carriers of byte-identical text on this corpus: duplicate copies sit in the
same authority class, share a subject state, and share their date-projection status. So
argmax-covariate always returns the declared-key first element — **the pre-registered fix
cannot move anything on this surface**, and the instrument says so on its own criteria rather
than on an argument. The amended pre-registration predicted exactly this before the run. What
this reading licenses is therefore *a* fix, not *the* fix that was named, and the difference is
the checkpoint's main open question.

**What is arbitrary is the grouping, and it is priced.** The carrier sets admit a different
document partition on 17 questions and a different document *count* on 8. Pushed to the
max-independence extreme the decision changes on one — and that one is the whole point:

| q2-059 | action | n_obs | n_docs | leader | credence | EU |
|---|---|---|---|---|---|---|
| as deployed | hedge | 7 | 3 | the gold | 0.683 | 0.369 |
| max-independence carriers | **report** | 6 | 4 | the gold | **0.975** | **0.755** |

Same corpus, same extractions, byte-identical text — only *which copy represents it* changed,
and a correct answer the arm withheld becomes a correct answer it gives. The mirror case is
q2-011, where the same permutation *lowers* the gold's credence (0.985 → 0.961, EU 0.858 →
0.618). One permutation helps one question and hurts another, which is exactly why
max-independence is a **bound and never a rule** — a rule chosen to maximise apparent
independence is the saturation §5 exists to prevent.

**Predictions, scored.** (1) *falsified* — multi-carriage is not the corpus's commonest shape
at this layer: 57 of 2040 texts, 2.8%. (2) *held exactly* — 57 of 57 are hash-decided.
(3) *held in direction, empty in content* — divergence is rarer than multi-carriage, but there
are **zero** instances, so "concentrated in `doc_date`" has nothing to describe.
(4) *held* — reach 0 is within "single digits". (5) *falsified as stated* — the
covariate-adversarial bound is 0, not "materially larger"; the bound that bites is the
grouping one, which was added after the smoke test.

**Named limitation, and it points one way.** The over-fetch window saturated on **all 102**
questions, so every carrier list is truncated at `search(k*4)` and 2.8% is a floor, not a
count. Two carriers had an uncached subject verdict and degraded to `unclear`, as the live
probe does. Both biases under-detect.

**Excluded by name (criterion 8):** q2-007 (not routed as a lookup — the narrative family
answers); q2-036 (an extraction is cold, and the audit spends nothing to warm it).

## DONE 4 — the cross-check that redirects the whole investigation

Run 10's single wrong commit is **q2-011**. The audit's base arm answers that question
**correctly**: 5 grounded observations across 4 documents, one candidate — the gold — at
credence 0.985, and **invariant under every carrier permutation measured** (named rule,
worst-covariate, max-independence, max-correlation). So whatever produced the wrong commit,
it is not the carrier choice at the retrieval layer.

Reading the run's own recorded decision row settles what it was, at $0:

| | run 10's committing decision | the audit's base arm |
|---|---|---|
| instrument | **`deliberate@<opus>`** | the local extractor |
| n_obs | **1** | **5** (over 4 documents) |
| candidates | 2 — competitor **0.902**, gold **0.033** | 1 — the gold at **0.985** |
| n_indeterminate | 10 | — |
| p_none | 0.066 | 0.015 |

The committing view carries **one** observation from a different instrument where the base
channel carries five, and the gold falls from leader to 0.033. The recorded wire agrees
independently: on the M0.5 baseline the base `/decide` for this question returns a **single**
candidate, and the two-candidate shape with the competitor leading (0.896 / 0.035) appears only
after the gather steps.

**So the wrong leader is introduced above the base pass, by a replace branch — and this is
a class already registered.** §14 carries it as the suspected mechanism behind the n_obs=0
cluster: *"a grounded channel a replace-branch probe erased … registered as NOT yet
measured — it needs its own frozen criteria + pre-registration."* Here it is at n_obs=**1**
rather than 0, on the one row that failed a gate.

**What this does and does not settle.**

- It does **not** overturn run 12: §6.9's declared key remains what carried the already-wrong
  leader over the commit bar (p_none 0.126 → 0.066; the run-10 row records 0.066). The
  ladder measured the *marginal* cause of the commit, and correctly.
- It **does** identify the cause of the wrong *leader*, which the ladder could not: a replace
  branch discarding a grounded five-observation channel in favour of a one-observation view.
- It therefore **refutes the premise of the standing deployment block**. §14 says master must
  not deploy *"until the carrier-identity checkpoint fixes the root cause."* Carrier identity
  is measurably **not** the root cause of this row. The block may still be right for other
  reasons — master does knowingly carry a configuration that commits this row wrongly — but
  it should be re-decided on its own terms rather than left waiting on a checkpoint that
  cannot deliver what it was asked for. **That is the owner's call, not mine: it reverses a
  constraint the owner set.**

**Honest bound on the comparison.** The audit's layer is not the arm's: its action agrees with
the run's terminal on **70 of 102** questions, exactly as criterion 5 warned. The claim above
does not rest on that agreement — it rests on the evidence *count* (5 grounded observations
versus 1), which is not a modelling difference between the host and the daemon, since both
consume the same observation set.

## DONE 5 — surface (b), the corroborate probe: **BUILD** on the criterion, and today's rule is on the safe side of it

`probes.probe_corroborate` was added to scope before surface (a) was read, on a mechanism the
code states outright: the probe ends in `_fresh_hits`, which drops a hit whose carrier is a
document already in hand. Where a text's carriers straddle the held set, the carrier choice
decides whether that corroboration **exists**, not what it weighs.

| | |
|---|---|
| questions firing a probe | **101** |
| multi-carried texts in the probe window | **55** of 2000 |
| **texts whose carriers straddle the held set** | **37**, in **17** questions |
| …resolved today by **dropping** the hit | **37** |
| …resolved today by **keeping** it | **0** |
| carriers diverging on the covariate triple | **0** |
| fresh corroboration, deployed vs the named rule | 180 vs 180 hits; the set differs on **0** questions |
| **load-bearing exposure** | **17** |

**Verdict, applied mechanically: BUILD (17 ≥ 5), no gate run bought.** And then the split that
matters: **37 of 37 straddles fall on the conservative side.** The declared key is the same
function on both surfaces and the carrier scores tie, so the probe re-picks exactly the carrier
the base pass already picked — which means the straddle is always resolved by *dropping* the
hit, and any alternative carrier would **add a second copy of text already in hand as if it
were independent corroboration**. That is the saturation §5 exists to prevent.

So on this surface the arbitrariness is real and today's rule never lands on the hazardous side
of it. The consistency of the declared key across both surfaces is doing load-bearing work that
"an arbitrary tie-break" undersells — and any fix must preserve it. A change here could only
move hits from *dropped* toward *kept*, which is the wrong direction.

**Named limitation.** The decision proxy covers **65 of 101** questions: on 36 the union of base
and fresh hits contains a chunk the audited run never extracted, and the audit spends nothing
to warm it. Every one is named in the artefact. q2-011 is among them, which is why DONE 4 reads
that question off the run's own recorded decision instead.

## REFUSED

- **No code on the decision path was touched.** RULING 4 forbids it before criteria exist, and
  a gate in the commit script refuses the commit if `src/` is dirty.
- **The pre-registered rule was not swapped for one that wins.** It was measured, found to be a
  no-op, and reported as refuted. The two grouping permutations that *do* move decisions are
  published as diagnostic bounds and are explicitly barred from becoming rules — one of them
  helps q2-059 and hurts q2-011, and the other would defeat §5.
- **No gate run was bought.** Delivered reach is 0 on both surfaces, and criterion 7 buys a run
  only at reach ≥ 1.
- **The verdict-flipping correction was not folded into the numbers.** Both the unfaithful and
  the faithful quantities are published, in the chronology.

## QUESTIONS

1. **The deployment block.** Its premise — "do not deploy until the carrier-identity checkpoint
   fixes the root cause" — is refuted by DONE 4: carrier identity is not q2-011's root cause,
   so this checkpoint cannot deliver what the block was waiting for. Options: **(a)** keep the
   block and re-point it at the replace branch (recommended — master still commits that row
   wrongly, which is what the block was *for*); **(b)** lift it, since the named blocker is
   discharged; **(c)** keep it unchanged until the row itself is fixed. This reverses a
   constraint the owner set, so it is not mine to take.
2. **What BUILD licenses.** Criterion 7 says BUILD at 17 ≥ 5 on both surfaces, but the fix that
   was named is a proven no-op and the arbitrariness that remains is the *grouping*. Options:
   **(a)** open a carrier-set grouping design with its own pre-registration and a priced run;
   **(b)** convert §6.11 to a standing known-and-uncovered source, record the grouping bound,
   and spend the next run on the replace branch instead (recommended — that is where the wrong
   answer comes from, and the grouping's measured decision effect is one question in each
   direction).
3. **M1's disposition** is unchanged by this checkpoint and remains held at r04.

## PROPOSED

Open **r06 — the replace branch**: a grounded channel discarded in favour of a
single-observation view from another instrument. It already has a registered §14 entry marking
it unmeasured, a first witness (q2-011, the row that failed run 10) and a population (the
n_obs=0 cluster). Same shape as this checkpoint: frozen criteria first, a $0 instrument reading
the run's own records, no decision-path code until the criteria exist.
