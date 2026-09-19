# r34 — the value-join unification: THE READING (C1–C4, $0)

Pre-registration: [`r34-value-join-preregistration.md`](./r34-value-join-preregistration.md),
committed before any `src/` change. This report reads **C1–C4**, all at $0. **C5 — the paired
live reading — is OPEN**; it is the remaining conjunct and this report claims nothing about it.

Append-only. Nothing below is edited when C5 lands; C5's reading is appended.

---

## The lever

`bridge/server._lattice_join`'s exact-match test binds `lookup._candidate_key` (the §4.2
declared candidate identity) instead of `_norm_value`. Two lines.

It **invents no rule.** M6 declared `_lattice_join` the ONE value-join (`[§3.3 · D-11/BR-2]`),
but it tested identity with `_norm_value` while `candidates_from`, `render`, `era_split`, the
executor's S2 grow join and the confirm probe all use `_candidate_key`. Two declarations of one
relation, surviving M6 because they are numbered under different clauses — `_norm_value` itself
carries the stamp `[§3.3 · L-4] candidate identity`.

Deliberately unchanged: `_joined_observation`'s `value_norm` (the §5 dedup key — a different
relation, and a derivation-cache key component) and `_candidate_key` itself (B2, scoped out
with reasons in the pre-registration §3).

## The instrument

`scripts/join_census.py`. The pre-registration's §2(b) forced it: `_lattice_join` runs
**bridge-side**, and the fixtures record `/probe/deliberate` and `/probe/corroborate` as `http`
exchanges with frozen responses, so replaying a fixture serves the recorded answer and never
runs the changed code. The census instead lifts `(value, candidates, allow_new)` off the
recorded wire and replays them through the **deployed** join, so the same instrument run on two
trees yields the firing surface exhaustively.

`engine_join` BINDS `_lattice_join`; nothing is re-implemented (`M-7`). Four load-bearing
predicates verified RED by mutation before the read: the binding itself, `c1_violation`'s
licensing, `diff`'s arm-alignment refusal, and the census's skip of a valueless exchange.

## The reading — m5-base, 234 recorded joins over 97 fixtures

| criterion | reading | verdict |
|---|---|---|
| **C1-as-frozen** | 2 violations of 5 differences | **FAIL** |
| **C1-identity** (corrected) | 0 violations of 5 | pass |
| **C2** every difference predicted by the declared key | **5/5** | pass |
| **C3** readable firing surface | **2 questions** (q2-027, q2-090) | pass |
| **C4** replay no-harm | **288/314**, errored set **element-identical** to r33's recorded 26 | pass |

## C1 as frozen is DEFECTIVE — and the defect is in the pre-registration, not the lever

C1 froze *"zero differences where OLD joined `i` and NEW joins `j ≠ i`"*. **Indices are not
comparable across the two arms by construction**: the lever's whole effect is to stop minting,
which SHORTENS the lattice. On q2-027 the old arm minted at slot 3 and the new arm joins slot 1
— and both slots carry one declared key, so it is *the same answer, reindexed*. The census
replays each exchange against its RECORDED payload, which still lists the candidate the old
trajectory minted; the "different join" is the merge appearing downstream.

Per `M-4` the frozen criterion is **not quietly relaxed**. Both readings stand, the instrument
prints both on every difference, and `c1_identity_violation` — compare the ANSWER, not the slot
— is the criterion a successor should freeze. This is the r05 precedent exactly: a defect in
the measure, caught before the verdict, with both quantities published.

The chronology, for the record: C1-as-frozen was read first and returned FAIL with 2
violations; the two were inspected; both were shown to carry one declared key; the corrected
measure was written under TDD, mutation-verified, and both arms re-recorded with it.

## C3 corrects the pre-registration's blindness estimate — upward, onto a named class

§2(a) estimated the gate's blindness by counting duplicate-key candidate lists in recorded
**outputs**: 1 of 104. The direct census finds **2**. The second is **q2-090**, which run 8
named as one of its two curve-evolution wrong-leader commits — a **named wrong-commit class**,
so the hard clause (`M-1`) binds it.

**And the replay cannot say what the lever does to that decision.** q2-090's fixtures are among
the standing 26 that error, so its decision is unreadable here. Named as a gap. It is the first
thing C5 must look at, and the reason C5 is not optional.

Two questions is also *exactly* §6.13's commit-wobble floor of 2 — at the floor, not above it.
The gate run remains a no-harm regression, not the reading.

## What is NOT claimed

- **No decision-layer effect is demonstrated.** The census proves the merge happens and is
  correct on every firing; it says nothing about whether any argmax moves. Per §2(b) the replay
  structurally cannot say either.
- **The registered expectation stands unrevised:** naive merged mass crosses p† = 0.8369 on
  none of the six live signature rows (best 0.750). "Correct but inert" remains a live and
  acceptable outcome (the r30b precedent).

## Gates

Full suite **3079 passed** / 35 deselected · `ruff check .` clean · mypy clean (233 files) ·
PII guard exit 0.

## Deviations disclosed

1. **C1's defect**, above — the criterion contradicted the artefact it names. Third instance of
   the standing lesson that a frozen clause must be re-read against its artefact before it is
   applied.
2. **The D-11 spelling pin matched the wrong line.** Updating M6's
   `src.count("LK._candidate_key(c) == vk") == 1` produced 2, because the bare substring also
   matches the confirm probe's `== vkey`. Converted to a word-bounded regex and the poison
   census's baseline moved 2 → 1 in the same commit, as that guard instructs. The pin's job is
   to forbid a SECOND spelling, not to freeze which one.
3. **The firing surface is A-loop only** — both firings are in the `aloop` lane; the `poster`
   and `blookup` lanes of the same questions record no differing join. Not investigated; a
   disclosure item under `M-6`, not a new arc.
