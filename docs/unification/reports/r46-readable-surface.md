# r46 leg A — the readable surface: READING

Criteria frozen in
[`r46-readable-surface-preregistration.md`](./r46-readable-surface-preregistration.md)
before any `src/` change (`M-3`), with amendment 1 committed **before the instrument ran on
a single row** (`M-4`). Instrument: `scripts/membrane/mapped_surface.py`. **$0.**

## Disclosure — five deviations, all before any verdict

1. **The frozen population was unreachable and was corrected blind.** "The m5-base replay
   with the shadow live" is not a configuration that instrument has: `collapse_replay.py`
   holds zero membrane references, and `/decide-support` appears zero times in the corpus
   wire. Caught by re-reading the clause against the artefact it names, *before* it bound.
   Amendment 1 has the replacement and its reasoning.
2. **S2's verifier is weaker than its wording.** S2 names the m5-base replay, which reads
   its standing **288/314 with the same 26 named artefacts** — but that replay wires no
   membrane, which is the very fact that forced amendment 1, so it confirms the tree is
   unbroken and **not** that the tap is inert. The inertness evidence that does bear is
   structural (`submit_decide` is enqueue-only; `_decide_support` wraps it in
   `contextlib.suppress`; the tap runs in the worker thread behind the queue) plus the
   mutation battery below. Stated rather than allowed to read stronger than it is.
3. **The stream is live and grew during the read** — 6 628 action-bearing rows at
   16:10 HKT, 6 654 at 16:28 HKT on 2026-09-02. Every ledger figure below carries its
   read time. An instrument that quotes this stream without a timestamp is quoting a
   moving number.
4. **The p1 sweep was extended past its frozen range.** The pre-registration froze a sweep
   over the *recorded* p1 range; the full unit interval was swept as well. This is an added
   diagnostic that strengthens the reading rather than changing a criterion — and it is the
   leg that found §3 below, which the frozen range alone would have missed.
5. **The motivating census's first pass read field names it had inferred.** It counted
   `effector`/`degradation` — which do not exist — and got `None` for every row. Corrected
   by reading the deployed writers and `git show` of the deleted one. `M-7`'s signature, one
   step upstream of a verdict; caught before any criterion was written.

## 1. The population, with its size (S4)

**605 `/decide` request/reply exchanges across 102 of the 314 m5-base fixtures.** The other
212 carry none — they are poster, B-lookup and seam traces with no decide leg. Each exchange
supplies the exact pair the live seam forwards to `submit_decide`: the request's payload
(`candidates` / `transforms` / `applied_probes` / `u_bar`) and the response's daemon view
(`effector` / `credences` / `p_none` / `probe` / `value`). Recorded daemon effector over the
605: `gather` 385 · `abstain` 152 · `report` 64 · `hedge` 4.

Both legs' sizes are published and never merged: the corpus leg is 605 exchanges; the live
leg is the ledger census, 6 654 action-bearing rows at 16:28 HKT.

## 2. The mapped surface varies, and every disagreement is engine-contributed — **Branch A**

At the measured affordance (`gather`), over the 605:

| quantity | value |
|---|---|
| distinct mapped effectors | **2** (`gather` 489 · `abstain` 116) |
| echo (agreement branch fired) | **385 / 605 = 0.636** |
| rows where the mapped act differs from the daemon's | **118 / 605** |
| … of which the engine contributed (echo false) | **118 — all of them** |
| probes selected by the gather branch | 104 (plus 385 daemon probes carried through an echo) |
| `map_action` errors | 0 |

**Branch A's conjuncts are met**: ≥2 distinct mapped effectors, and `mapped_echo` false on
≥1 row where the mapped act differs from the daemon's. **Branch A′ is refused on evidence,
not on preference**: the echo fraction is 0.636 against a 0.95 bar, and — the stronger fact —
on **every one of the 118 disagreeing rows the echo is false**, so not one disagreement is an
artefact of the daemon varying underneath. The surface carries engine signal.

This is the quantity the deleted `enact` writer could not express. It recorded an agreement
pass-through and a probe selection **identically** (`real_effector: "gather", degraded: null`
covers both), which is why `mapped_echo` was frozen as a criterion rather than left to be
inferred from the effector distribution.

## 3. …but the surface cannot express a commit, and the reason is a number

The mapped terminal act is a **step function of the engine's `p1` with exactly one
threshold**, and the sweep locates it:

- Below the threshold the 116 exhausted rows map to `abstain`; at and above it they map to
  `report`. Nothing else moves — the 489 probe-selecting rows are p1-independent.
- The threshold is **p1 = 0.897015**, identical on all 605 rows because the corpus carries a
  single elicited `u_bar`. It is not a tuning constant: it is
  `|u_wrong| / (u_correct + |u_wrong|)` = 8.710166 / 9.710166, and it sits there **because
  `u_abstain = 0`** — the residue `r35` §3 records as owner-only and the ROADMAP names as the
  answer-utility gauge's one unrepresentable cost.
- **The engine's `p1` has never reached it: 0 of 6 654 action-bearing rows**, max **0.8706**
  (16:28 HKT). Segmented: old-era decide max 0.8706 · new-era decide 0.8621 · gate 0.6409 /
  0.8620 · cat 0.8672. Both engine arms, all four row kinds, the whole life of the stream.

**§17.6 found this first and must be cited for it** — *"those same ticks' engine posteriors
sit between 0.856 and 0.899 … the stated −9 wrong-cost puts the commit bar exactly above
it"* — on 193 ticks, against a bar of 0.899 from a `u_wrong` of −8.83. What r46 adds is the
extent and the surface: the near-miss holds over the **entire** ledger and **both** engine
arms, and it holds on the **mapped** surface too, not only on the raw commit policy. Our
corpus's `u_wrong` of −8.710 puts the same bar at 0.897015; the two numbers are one
quantity elicited twice.

**So the honest disposition is Branch A with a named ceiling.** The mapped surface is
readable and varies with engine signal, so a §18 bar **can** be read on it — but that bar can
only price *gather-more versus withhold*. **A commit is not in its range**, and no sharpening
of the instrument changes that: only a `p1` above 0.897 would, which is exactly §17.6's
*"the fix is always a sharper `p1`, never a softer bar"*, now carrying its distance — the
ceiling sits **0.0264 below** the threshold, and the new era's 0.8621 sits 0.0349 below.

## 4. `real_effector` names two different quantities depending on `kind`

Read from the writers, not the name. On `decide` it is `dec.get("effector")` — the deployed
daemon's act. On `gate` it is the literal `"abstain"`. On `cat` it is the decide item's, again
the daemon's. On `enact` — the lane deleted at M5 — it is `mapped.get("effector")`, the
**engine's** mapped act, with the daemon's carried separately as `daemon_effector`. An
instrument that reads the column across kinds compares the engine against itself on 555 rows
and the daemon against itself on the other 6 099. Registered as **`M-26`**.

## 5. Criteria dispositions

| id | disposition |
|---|---|
| **S1** additive | **MET.** Four new keys, `kind: "decide"` only; every pre-existing key unchanged. Guarded by two mutations (overwrite a pre-existing key; leak the keys onto gate rows) — both RED. |
| **S2** off the decision path | **MET, with deviation 2's caveat published.** Replay 288/314 with the same 26 named artefacts; the load-bearing evidence is structural plus the mutation battery, not the replay. |
| **S3** fail-open | **MET.** An injected raise leaves the form alive, the decide row written without mapped keys, and `stats()["map_errors"]` at 1. Mutation (let the raise propagate) RED. |
| **S4** size published | **MET.** 605 exchanges over 102 fixtures; live leg 6 654 rows at a stated time; neither merged. Non-zero on both. |
| **S5** mutation-verified | **MET.** Five mutations, each varying the dimension its own claim is about (`M-25`): pre-existing-key overwrite, raise propagation, echo-identity replaced by a constant, the rule restated instead of called, key leakage onto gate rows. All RED; restore GREEN. |
| **S6** echo published | **MET.** 0.636 over the corpus, and 0/118 on the disagreeing rows. The `map_action` identity contract it reads is pinned by a named test, itself mutation-verified (returning a copy on agreement turns every echo into an apparent contribution). |

Suite **3 143 passed / 1 failed**; `ruff` and `mypy` clean. **The failure is disclosed, not
rounded away:** `tests/pkm/test_extract.py`'s
`test_retry_failed_reruns_and_flips_failed_artifact_to_success`, a pkm extraction test this
leg does not touch (the diff is `src/life_agent/membrane/` only). It passes in isolation and
passes as a whole module on clean `master`, so it is a flake under full-suite load rather
than a regression — stated here because "3 143 passed" alone would read
as a clean run, and it was not one.

## 6. Consequence enacted, and what it does NOT license

**Branch A.** The §18 precondition r45 registered is **discharged**: the surface a §18 bar
reads is declared to be the **mapped** surface, its distribution is published above, and the
tap that writes it is deployed. The raw affordance is disqualified on measurement — 6 654 of
6 654 rows `gather`.

**No §18 bar is read here, and §3 constrains the one that will be.** A bar written against
this surface must state that a commit is outside its range and price only the
gather-versus-withhold margin, or it will be read as evidence about a decision the surface
cannot express. `M-1` is not engaged: nothing in this leg reaches a commit decision.

**Carried, not fixed:** the three other r46 items keep their own pre-registrations
(`M-3`) — act-conditioning as r45 reframes it, `GD-15`'s grid precision now with its
number, and the categorical twin. §3 hands the first of them a sharper question than it had:
the p1 ceiling, not the affordance constant, is what a commit-pricing bar is now blocked on.
