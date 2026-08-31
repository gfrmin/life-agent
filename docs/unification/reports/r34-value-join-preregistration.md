# r34 — the value-join unification: PRE-REGISTRATION

**Committed BEFORE any `src/` change** (RULINGS `M-3`). Everything below — the change, the
instrument, the criteria, the directional claims and the consequence branches — is frozen at
this commit. The reading is `r34-value-join.md`.

**Consequence branches are not negotiated here.** They are RULINGS `D-2`'s standing defaults:
PASS ships (merge + deploy); FAIL reverts from the deploy path, publishes, and opens a
successor pre-registration; a SECOND FAIL on the same frozen criterion parks the lever and
advances to the next queued item.

---

## 1. The evidence this opens on ($0, 2026-08-31, read-only)

**Conferral 2's characterisation of the norm class is REFUTED, and is published rather than
quietly corrected.** It recorded five affix types that SPLIT candidate identity: currency
symbol, currency-code placement, thousands separator, unit suffix, country dial prefix. Probing
the deployed `lookup._candidate_key` shows its `>= _CANON_MIN_DIGITS` branch strips **all**
non-digits, so the first four already MERGE at 5+ significant digits. Round 8's sharpest
instance — three spellings of one amount summing to 0.750 with zero competitors — keys
**identically** on all three under the deployed rule, verified against the verbatim strings
recovered from its own decision row.

This is RULINGS `M-7` in a new form: the characterisation was inferred from observed outputs
without checking which predicate produced them.

**The real defect: two declarations of candidate identity that disagree.**

| site | identity test | stamp |
|---|---|---|
| `bridge/server._lattice_join` (M6's ONE value-join, bound by both edges) | **`_norm_value`** — whitespace + casefold | `[§3.3 · D-11/BR-2]` |
| `lookup.candidates_from`, `lookup.render`, `lookup.era_split`, `executor`'s S2 grow join, the confirm probe | **`_candidate_key`** — the §4.2 canonical key | §4.2 |

So the deliberate and re-read edges MINT spelling variants as new atoms that every other site
on the lattice considers one candidate. `_norm_value` itself carries the stamp
`[§3.3 · L-4] candidate identity`, which is how two declarations of one relation survived M6:
they are numbered under different clauses.

**The population.** 35 of 3555 live decision rows carry the signature (≥2 atoms sharing a
declared key): 29 abstain · 4 report · 2 hedge, all `lookup`. **Every duplicate group inspected
is genuinely one answer** — date-format variants, currency spellings, volume/issue spellings.
No harmful merge appears anywhere in the stream.

## 2. Two blindnesses, both measured before the criteria were written

**(a) The gate corpus cannot see this lever.** Across all 104 pinned questions in the 314
m5-base fixtures, exactly **one** (q2-027) carries a duplicate-key candidate list, in 2 of its
3 lanes. Against §6.13's commit-wobble floor of **2**, one question is not a reading. Same
shape as r30b's "fires on 5 of 104".

**(b) The m5-base replay cannot exercise the lever at all.** `_lattice_join` runs **bridge-side**,
and the fixtures record `/probe/deliberate` and `/probe/corroborate` as `http` exchanges with
frozen responses. A replay serves the recorded response; the changed code never runs. This is
stated up front so that the replay's expected pure equality is never reported as evidence that
the lever is harmless *in the decide layer* — it is evidence about everything else.

Consequence for the design: **the replay is demoted to a no-harm check (C4) and a purpose-built
wire census becomes the $0 instrument (C1–C3).**

## 3. The change — exactly one, and what is deliberately NOT changed

`bridge/server._lattice_join`'s exact-match test binds `_candidate_key` instead of
`_norm_value`. Two lines.

It **invents no rule**: it makes the join site agree with the five sites already using the
declared key. `_candidate_key` falls back to `_norm_value`, so the change is a **monotone
coarsening** — it can only merge more, never split more. That property is C1, and it is
falsifiable rather than assumed.

Deliberately unchanged, each with its reason:

- **`_joined_observation`'s `value_norm`** keeps `_norm_value`. That is the §5 dedup key — a
  different relation — and it is also a derivation-cache key component, so widening it would
  move cache keys and dedup semantics.
- **`_candidate_key` itself** (B2: a dial-prefix strip, a sub-`_CANON_MIN_DIGITS` affix canon).
  Scoped OUT, r30b-style: it invents a rule, it breaches the confident-wrong boundary the key's
  own docstring declares ("a misread truncation stays its own candidate"), and it would put a
  second lever on one reading. It reaches ~2 further instances and may open as its own arc.
- **`matching._span_canon`** — competition detection, checked and consistent.

## 4. The instrument — `scripts/join_census.py`

For every recorded `/probe/deliberate` and `/probe/corroborate` exchange in a fixture corpus,
take `(value, candidates, allow_new)` from the request payload and response and replay them
through the **deployed** `_lattice_join`, emitting `(idx, minted)`. Run on master and on this
branch; the diff is the lever's firing surface, exhaustively.

The census **imports the deployed function and re-implements nothing** (`M-7`); the OLD arm is
obtained by running the same instrument on the master tree, never by re-spelling the old
predicate. Every load-bearing predicate is verified RED by mutation before the read.

## 5. Frozen criteria

| id | criterion | kill? |
|---|---|---|
| **C1 · merge-only** | Every difference between trees has the shape *OLD minted (or found no join) → NEW joins an existing index*. **Zero** differences where OLD joined `i` and NEW joins `j ≠ i`; **zero** where OLD joined and NEW mints. | **KILL** — a single violation refutes the monotone-coarsening argument the whole lever rests on. |
| **C2 · every difference predicted** | For every differing exchange, `_candidate_key(value) == _candidate_key(candidates[new_idx])`. 100%, no exceptions. | **KILL** |
| **C3 · readable surface** | The census finds ≥1 firing on the fixture corpus. Registered prediction: **exactly q2-027**, where `358(14)` and `Volume 358, Issue 14` both key `35814`. | not a kill; a zero reading means the fixture evidence is silent and the reading rests on §6 alone |
| **C4 · replay no-harm** | The m5-base replay reads **288/314 with the same 26 named standing artefacts** — identical to master's baseline. Per §2(b) the lever cannot appear here, so a **27th** difference means something unintended changed. | **KILL** |
| **C5 · the paired live reading** | See §6. | see §6 |

## 6. The primary reading — a paired live re-ask

The six decision rows carrying the signature since 2026-08-26 are re-asked under master and
under the lever, same day, same corpus, graded against the frozen manifest golds in
`~/.cache/life-agent/dogfood-round*/manifest.md`. Conjuncts:

- **(a)** zero NEW wrong commits, **class-based and prospective**, baselined on the paired
  master arm (a wrong commit is NEW iff the row was not wrong there). **KILL.**
- **(b)** no named wrong-commit class worse — the standing hard clause, RULINGS `M-1`. **KILL.**
- **(c)** on every row where the census says the lever fires, the merged leader's credence is
  **≥** master's leader. A merge that *lowers* a leader contradicts the coarsening argument.
  **KILL.**
- **(d)** conversions abstain→report on a GOLD value: **recorded, not a kill.** See below.

**Registered expectation, written before the run, so the reading cannot be spun.** Naive merged
mass — the sum of the credences of atoms sharing a declared key — crosses the deployed bar
p† = 0.8369 on **none** of the six rows. The best is 0.750 (p_none 0.250); the rest run
0.139–0.493. The naive sum is a lower bound (merging pools observations onto one atom against a
smaller competitor set, and the posterior is recomputed rather than added), but **the honest
prior is that this lever raises leaders without necessarily converting any of them.**

**"Correct but inert" is therefore a live and acceptable outcome** — the r30b precedent, where
the interval claim was built, measured, and kept dormant. A PASS on (a)–(c) with zero
conversions ships the unification on its correctness, not on a reach claim, and the report says
so in those words.

**Directional claims** (each falsifiable, each recorded now):

1. **D1** — the round-8 q3 shape: three atoms become one; leader rises from 0.261.
2. **D2** — the round-8 q5 shape (bare vs `+`-dial-prefixed number) is **UNCHANGED**. That split
   is B2's, not B1's. If q5 moves, the change is not what this document says it is.
3. **D3** — no row whose candidates all carry distinct declared keys changes at all.

## 7. Disclosure protocol

Deviations, defects in the instrument, and any criterion found to contradict the artefact it
names are published in the reading (`M-4`: never silently weakened; amended blind and
prospectively, or not at all). The r05 lesson applies to this document too: **an instrument
written around the presumed fix measures the fix, not the defect** — which is why C1 and C2 are
stated as properties of the *difference set*, computed exhaustively, rather than as checks on
the rows this document already knows about.

PII: fixtures and examples use synthetic values marked `# PII-OK`; corpus values stay in
`$LIFE_AGENT_KB`.
