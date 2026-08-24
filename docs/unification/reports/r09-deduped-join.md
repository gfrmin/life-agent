# r09 — the §5-deduped JOIN at the replace sites — PRE-REGISTRATION (2026-08-24)

> **Ruling 1 (owner, 2026-08-23, r07's RULINGS):** the JOIN-with-a-correlation-key fix
> opens as its own checkpoint. The §5 dedup key goes on the wire so a §5-deduped JOIN is
> computable at the replace sites. Frozen pre-registration first — criteria and predictions
> committed before any `src/` change — then implementation under TDD.
> **This document is that pre-registration. It is committed before any `src/` edit on this
> branch; git history is the proof.**

## STATE

- master `3d5435f` (r08 merged: §6.13 repaired; M1.5 census read). Suite 2638, ruff, mypy
  green; 7.2 green on every fixture set (311/311, 104/104, 2/2).
- **The mandate.** r07 read the harm on the DISAGREE path, which retire-not-replace cannot
  see by construction: enacted RETIRE = 0 repairs / 1 regression; **the JOIN upper bound =
  10 repairs / 2 regressions / 1 neutral on 66 rows**. On the blocking row (run 10's one
  wrong commit) S1 zeroes a five-observation grounded base and the deliberate edge re-mints
  a one-observation competitor. Confirmed dischargers across r07's double run: S1 ×10 +
  S2 ×2; S3/S4/S5 discard nothing on any replayed row.
- **The bound's exact semantics** (`scripts/replay_audit.py::join_observations`, the arm run
  13 validates against): the probe reply's `observations` are POOLED with the standing
  channel at the transport; the executor's site code then runs as deployed — the pooled
  channel rides the site's conditioned rho; a disagreeing empty reply pools nothing and the
  channel survives. The bound tolerated two defects the deployed JOIN must not: raw pooling
  (no §5 dedup — every copy an independent witness), and the probe observation's hardcoded
  `group: 0` colliding with the base channel's first document.

## The design, frozen

**D1 — the correlation key on the wire.** `bridge/observations.to_abstract_observations`
grows two fields on every abstract observation: `quote` (the raw grounding quote — §5's
cluster key via `lookup._quote_key`) and `doc_key` (the observation's `artifact_cache_key`).
Everything else §5 needs is already wire-resident or derivable: the covariate is
authority·subject·time (`lookup._covariate`), the value-only exemption's tokens come from
`candidates[reports]`. The daemon must never see the new fields: the executor strips them
from the decide payload (the brain stays string-blind — the parity boundary holds).
`replay_audit.dedup_key_available` — the pre-built activation predicate — turns the
instrument's deployed-rule branch on by itself, as r07 designed.

**D2 — the JOIN is computed bridge-side, where the deployed rule lives.** The executor
passes its standing channel (`observations`, now key-carrying) in the payload of every
S1/S4/S5 `/probe/corroborate` (reextract) call and every S3 `/probe/deliberate` call. The
bridge pools the probe's grounded observation(s) with the passed channel, applies **the**
§5 rule — one clustering function shared by `lookup.dedup_correlated` and the wire adapter,
the deployed rule called never re-implemented (r05's lesson; the dormant `/probe/confirm`
at `server.py:443-452` is the in-tree precedent) — re-derives group indices from `doc_key`
(D2 kills the bound's group-0 collision), and returns the JOINED set in `observations`.
The executor's site line (`obs = reply["observations"]`) is mechanically unchanged: the
replace becomes a join because the reply is the join.

**D3 — semantics adopted are the bound's, named not smuggled.**
- **Run 7's disagree⇒abstain contract is retired by this ruling's fix**: a corroborate
  DISAGREE (non-null read whose value does not join the lattice, `observations: []`) no
  longer erases the grounded channel — it joins nothing. A disagree that NAMES a
  lattice-joinable value contributes its observation against the leader instead.
- **The deliberate empty-ok collapse is retired the same way** (NOT_IN_CORPUS pooled with a
  grounded channel keeps the channel; r06 criterion 7 already read zero genuine collapses).
- **The single-rho coarsening is kept and named**: the pooled channel rides the site's
  conditioned rho exactly as the bound measured; per-observation instrument reliability is
  not modelled v0.
- **The S1 null-read guard stays** (run 11 exonerated it): a `read: "null"` reply bypasses
  the join entirely — channel AND rho untouched.
- **S2 (the grow retrievals) is untouched**: it is an evidence rebuild, not a probe reply;
  the bound never pooled it; its adopt-iff-grounded contract stands.

**D4 — instrument parity.** `replay_audit.join_observations` is updated to the shared rule
(consuming key-carrying wire observations); it remains off the decision path. The recorded
r07 artefacts are history and are not re-read.

## Frozen criteria

- **C1 — TDD, the iron law.** Every new predicate watched RED before its code; full suite,
  ruff, clean-cache mypy green at every commit on this branch.
- **C2 — one rule.** Property test: the wire-adapter join and `lookup.dedup_correlated`
  produce identical survivor sets on identical inputs. A second implementation of the
  clustering rule anywhere is a defect (§6.8).
- **C3 — a JOIN never lowers a grounded channel.** For every reply shape (null, disagree
  empty, disagree naming a value, confirm, new-candidate mint): committed
  `n_obs(joined) ≥ n_obs(channel)`. Unit-tested per shape; the property is the checkpoint's
  reason to exist.
- **C4 — group identity.** Pooled group indices are `doc_key`-derived; the probe
  observation joins its true document's group when it has one and its own fresh group
  otherwise; no collision with the base channel's groups. Tested.
- **C5 — warm policy, declared now (ruling 3's rider).** No §18.9 key changes: the join is
  computed after the derivation layer; probe payload fields do not enter `extract_joint`'s
  or deliberate's cache keys; warm entries keep serving. Verified by test on the key
  builders' inputs, not by assertion.
- **C6 — 7.2, read with a pre-registered direction.** Fixtures whose trace fires no
  S1/S3/S4/S5 probe replay IDENTICALLY (count published). Probe-firing fixtures are an
  INTENDED divergence (this checkpoint changes those decisions by design — why ruling 2
  re-records the baseline after r09): direction = committed n_obs never lower than
  recorded; a cassette request the tape cannot serve (the payload grew) is counted and
  published, never silently skipped. Zero unexplained divergences.
- **C7 — PII.** Quotes ride the wire and the fixtures (out of tree, `$LIFE_AGENT_KB`);
  nothing in tree carries a corpus value; this report stays classes-and-counts.
- **C8 — the priced validation is NOT this checkpoint.** r09 lands code + tests + the 7.2
  reading and STOPS. Run 13 (§6.10-pinned, ruling 4's frozen branches: PASS ⇒ the §6.12
  block closes and master deploys to live; FAIL on any conjunct ⇒ the JOIN reverts from the
  deploy path and work stops for a ruling) is fired separately, after the m0-5 re-record
  and O2 re-preparation (ruling 2).

## Blind predictions

1. Replaying the priced A-loop fixtures on the JOIN tree: at least one recorded
   S1-disagree erasure flips to channel-kept, and **no** fixture's committed n_obs reads
   lower than recorded.
2. The §5-dedup delta against raw pooling is nearly empty: the base channel arrives
   already deduped and the probes' observations are value-only (no shared context), so
   most joined sets equal the raw pool — the key's payoff is *readability* (instruments
   can verify the rule) more than decision-side delta.
3. Run 13 brackets inside the bound: ≥ 1 and ≤ 10 repairs, ≤ 2 regressions attributable
   to the JOIN, and the blocking-row class repairs (the ruled conjunct).
4. Zero §18.9 re-derivations attributable to the JOIN (C5 holds live).
5. No credence-side change is needed: the daemon never sees the key fields.

## REFUSED, in advance

- Re-implementing the §5 rule for the wire (C2 forbids it).
- Touching S2, the null-read guard, per-observation rho, or the gate's δ/level.
- Firing run 13 from this checkpoint (C8).

## THE READING (2026-08-24 — the criteria against their frozen text)

Implementation commits: the D1+D2 landing and the comment-hygiene commit, both on this
branch after the pre-registration (history is the proof C8 asked for).

**C1 — satisfied.** Every predicate was watched RED before its code (the wire key, the
strip, the shared rule, the four join shapes, the two endpoint joins, the instrument
delegation); the two C5 tests, which pin a structural invariant and so pass on arrival,
were each verified RED by mutation (the corroborate derivation key and the deliberate cache
key both made channel-dependent, each test failing, each mutation reverted). Full suite
**2653 passed**, ruff and clean-cache mypy green.

**C2 — satisfied.** The clustering rule now exists exactly once: `lookup.dedup_drop_rows`,
extracted from `dedup_correlated` (which delegates) and called by the wire join and the
instrument alike. The property test holds identical survivors across the object and wire
adapters.

**C3 — satisfied.** Per-shape unit tests: a null read and a lattice-refusing disagree pool
nothing (the channel survives, count unchanged); a confirm and a mint add one; nothing ever
lowers a grounded channel.

**C4 — satisfied.** Groups re-derive from `doc_key`; the synthesised read takes its own
fresh group; two chunks of one document stay one group. The bound's group-0 collision is
dead, tested.

**C5 — satisfied, mutation-verified.** The channel never enters `extract_joint`'s arguments
or the deliberate §18.9 key; warm entries keep serving. Both tests went RED under a
deliberate key-poisoning mutation and green on the real code.

**C6 — satisfied, with the counts.** On this tree: `m0-5` **216 of 311 replay identically,
95 unservable**; `m0-5-growlane` **9 of 104 identically, the same 95 unservable**; `m1-5`
**2 of 2 identically**. Every non-probe-firing fixture (B-lookup, A-poster, B-narrative,
seam, and the 9 A-loop rows that scheduled no S1/S3/S4/S5 probe) replays byte-identically —
the JOIN touches nothing it should not. Every unservable fixture is the SAME named class:
the executor's probe payload grew the `observations` field, so the tape has no matching
exchange (`CassetteMissError`, counted per fixture in the replay output). **Zero
unexplained divergences.** This is the intended-divergence reading the criterion froze —
and why ruling 2 re-records the baseline after r09.

**C7 — satisfied.** Quotes ride the wire and the fixtures only; this report and the tree
carry classes and counts.

**C8 — honoured.** No priced run was fired from this checkpoint.

### The blind predictions, scored

1. **NOT SCORED — the instrument is blind to it, a pre-registration miss disclosed as
   DEVIATION 3.** The prediction assumed probe-firing fixtures would replay to a comparable
   decision; they are unservable instead (the grown payload has no tape). Neither half of
   P1 is observable at the fixture layer. Run 13's frozen conjunct (the blocking-row class
   repairs) reads it live.
2. **CONFIRMED, and strengthened into a finding.** The base channel arrives already
   §5-deduped (`observe_hits` dedups at the shared shaper before abstraction) and every
   synthesised probe observation is value-only (empty quote — §5 never clusters it), so on
   today's wire shapes the deduped JOIN is **provably idempotent over the raw pool**: the
   deployed join and r07's "upper bound" coincide. The bound's 10 repairs / 2 regressions
   moves from most-favourable-case to the expected read for run 13 (modulo the group fix
   and the single-rho semantics, both named in D3). The key's payoff is what the
   pre-registration said: readability and the guard rail for any future multi-observation
   probe reply.
3. **Pending run 13** (the bracketing claim stands as frozen).
4. **CONFIRMED at the unit layer** (C5, mutation-verified). The live confirmation rides
   run 13's spend accounting.
5. **CONFIRMED.** No credence-side change: the daemon sees stripped observations only
   (tested), and the full suite's daemon-parity surface is green.

### DEVIATIONS

1. **D1 grew a third field.** The pre-registration froze `quote` + `doc_key` and derived
   the value-only exemption's tokens from `candidates[reports]`; C2's identity property
   refuted the derivation in TDD (an OCR-variant candidate's display form is not the
   observation's own normal form), so `value_norm` rides the wire too. Caught RED before
   any reading; the strip covers all three.
2. **A process slip, disclosed:** reverting mutation 1 with `git checkout` discarded the
   then-uncommitted server implementation; it was rebuilt from the session's own patch
   scripts and re-verified green by the same 115 tests before anything else ran. Lesson
   applied immediately: the implementation was committed before mutation 2.
3. **P1's instrument-blindness** (above): the criterion anticipated unservable requests as
   a count; it did not anticipate that the count would swallow the direction clause whole.
   The direction clause is therefore vacuous at the fixture layer and run 13 carries it.

### NEXT (the ruled sequence)

Merge; then ruling 2's riders — re-record the m0-5 baseline of record on this tree
(re-priced traces; the recorder's fixtures then carry the joined wire), re-prepare O2 —
then **run 13** under the §6.10 pin with ruling 4's frozen branches: PASS ⇒ the §6.12
deployment block closes and master deploys to live; FAIL on any conjunct ⇒ the JOIN reverts
from the deploy path and work stops for a ruling.

