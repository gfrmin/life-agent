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

**PENDING below this line: the implementation commits, then the 7.2 reading.**
