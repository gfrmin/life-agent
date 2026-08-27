# r22 · K1 — the aggregate family dies; the amounts projection is repaired

> **Status: PRE-REGISTRATION FROZEN.** Everything above the RESULTS rule is committed
> BEFORE any `src/` change. Results append below it; nothing above is edited afterwards.
> Part 1 of the plan approved 2026-08-27.

## Why this milestone exists

`PRINCIPLES.md` §16 (signed 2026-08-26) declares one argmax over one decision space —
the terminal responses and the transformations — and rules that any mechanism which
*selects among alternatives* goes into the argmax or dies. The aggregate arc (r18–r21)
added a second classifier (`/route_family`) that partitions questions into families
before any argmax runs. That is decision-shaping outside the argmax, so it dies.

`docs/membrane-shadow.md` §11 already inventories this class: **i-13** names the
route-null→narrative fork as *"family routing in disguise"*. `/route_family` is a fresh
instance of it. Deleting it now means one fewer decision for the proplang migration to
carry across — this milestone's purpose is to make the migrated surface smaller, not to
build on the credence skin.

## Scope change from the approved plan, recorded before the work

The plan gave K1 two deliverables: the family deletion, and `extract_amounts` as a priced
row on the transform menu. **The menu row is moved to migration stage E3 and is not built
here.** The reason is the same one that moved K3/K4 to M5/E3 under the owner's 2026-08-27
ruling, applied consistently:

- A new menu row needs a price. Every price on the menu today is a hand-set literal
  (`pricing.DEFAULT_TRANSFORMS`' `rho`/`cost`, `GROW_ACTUATORS`' `alpha0`/`beta0`).
- **E3 exists to un-hand-price exactly those.** Run 17 (`gate-20260826T025059`) measured
  the hand-set grow priors over-valuing re-reads: FAIL 0.743/+0.238, answer rate
  0.62→0.49, dispersed 37→51.
- Adding a hand-priced row now increases the debt E3 must pay and would be built twice.

Consequence, stated so it is not renegotiated later: **K1 buys no priced gate run**,
because the daemon's offer set is byte-identical after it. C4 tests that claim rather
than assuming it.

## The defect this milestone repairs (confirmed end-to-end, $0, before any change)

`core/aggregate.AMOUNTS_PRODUCERS` filters `artifacts.producer_name` on four names that
can never appear there. `project_amounts` therefore reports **every** hit as `underived`,
permanently.

Evidence, read from the deployed artefacts rather than re-derived:

1. `src/pkm/transform_run.py:318` writes `producer_name=producer.name` — the producer
   *class's* declared name, which also enters the cache key.
2. All four live `extract_amounts_*.yaml` declarations carry
   `producer_class: pkm.transforms.extract_amounts.ExtractAmountsProducer`, whose
   `name = "extract_amounts"` (`extract_amounts.py:44`). One class, one recorded name.
3. `AMOUNTS_PRODUCERS` is built as `f"extract_amounts_{p}"` over four extractors — the
   *declaration* namespace, a different namespace from `producer_name`.
4. The parallel case proves the rule. Four `doc_date_*` declarations map to two classes;
   the live catalogue holds `doc_date` (108 rows) and `doc_date_email` (115), and
   `core/temporal.DOC_DATE_PRODUCERS` correctly lists those two **class** names. The
   module `project_amounts` documents itself as mirroring got this right.
5. The loop is closed: the `remedy` string is correct, so running it produces an artifact
   named `extract_amounts`, which the same filter still misses.

**Why no test caught it.** All 37 tests in `tests/test_aggregate.py` pass. Their fixtures
insert `producer="extract_amounts_docling"` directly (lines 600, 604, 608, 713, 752), so
the test's universe is derived from the same wrong constant as the code. This is the
standing lesson in its fourth instance — *a census must read the deployed rule
end-to-end, never re-implement the constant it prices* — here with a test as the census.
It is also the defect class named in the owner's *Fifteen Ways Past My Own Gate*: the
checker's universe derived from somewhere other than the thing being checked, with
nothing measuring the gap.

The class is registered as entry 1 of `docs/guards.md`.

## FROZEN CRITERIA

**C1 — deletion completeness.** After K1, none of the deleted symbols resolves anywhere
in `src/`, `scripts/` or `tests/`: `_route_family`, `_aggregate` (bridge handler),
`ROUTE2_PROMPT`, `ROUTE2_SCHEMA`, `AggregateRoute`, `route_aggregate`, `AggregateResult`,
`aggregate_answer`, `render_aggregate`, `AGGREGATE_ACTION_ORDER`, `aggregate_route_key`.
`decisions.FAMILIES == frozenset({"lookup", "narrative"})`. The bridge's `_POST` table
contains neither `/route_family` nor `/aggregate`. Enforced by a re-listing guard,
verified RED by mutation before landing.

**C2 — the naming defect is closed and cannot recur.** `AMOUNTS_PRODUCERS` is *derived
from* the deployed producer class rather than restated as a literal. A test imports
`ExtractAmountsProducer` and asserts the projection's producer filter equals exactly
`{ExtractAmountsProducer.name}`. Verified RED by mutation: restoring the suffixed tuple
must fail that test with a named marker, not merely fail somehow.

**C3 — no behaviour change on the 104.** The 314-fixture replay reads **PURE EQUALITY**
on every non-aggregate fixture. Frozen as pure equality, not direction-asserted: K1
removes only the declined-path aggregate branch, and the C0b sweep of 2026-08-26 measured
that path as unreachable for the 104 (11 of the 15 aggregate questions are admitted by
stage 1; the 104 are all lookup/narrative). **Anything other than pure equality is a FAIL
and a STOP for an owner ruling**, because it would mean the aggregate branch was on the
104's path after all — which would falsify the C0b reading.

**C4 — the offer set is unchanged, tested not assumed.** `menu_transforms` returns rows
byte-identical to a frozen snapshot taken from master at `4ddc469`. If this fails, K1 has
moved the argmax and C4 converts into a demand for a priced gate run before merge.

**C5 — the register lands.** `docs/guards.md` exists; every guard in the tree carries one
of `unenforced` / `instrumented` / `resolved`; the `AMOUNTS_PRODUCERS` class is entry 1;
the eval-universe gap is recorded as written English, outside every count.

**C6 — the adversary pass fires last.** A fresh session, throwaway worktree, the single
question, findings reproduced by running. Its findings become poison fixtures written by
a later session and verified RED by mutation. A finding that implicates the deployed tree
is surfaced to the owner rather than silently fixed.

## Gates

G1 suite + ruff + mypy green · G2 the 314-fixture replay per C3 · **G3 not bought** (C4
is the evidence that it is not needed) · G4 the adversary pass per C6.

---
## RESULTS

*(appends here; nothing above is edited)*

**Read 2026-08-27, $0. All six frozen criteria MET. No priced run bought.**

### C1 — deletion completeness: MET

Deleted: the bridge's `_route_family` / `_aggregate` handlers and their `_POST` rows;
`aggregate.py`'s `ROUTE2_PROMPT`, `ROUTE2_SCHEMA`, `AggregateRoute`, `route_aggregate`,
`AggregateResult`, `aggregate_answer`, `render_aggregate` (the module drops 889 → 602
lines); `decisions.AGGREGATE_ACTION_ORDER` and the `"aggregate"` family; `reactions.py`'s
third arm; `executor.py`'s declined-path branch; `terminals.py`'s `AGG` import,
`AGGREGATE_LAST`, `_generators()` and the declined-path hook; `derivations.py`'s
`aggregate_route_key`, `aggregate_answer_key` and their version/content-type constants;
`scripts/route2_audit.py`; `docs/aggregate-family-design.md`.

Beyond the frozen list, and disclosed rather than assumed: the four derivation constants
(`AGGREGATE_ROUTE_VERSION`, `AGGREGATE_ANSWER_VERSION`, `CONTENT_TYPE_AGGREGATE_ROUTE`,
`CONTENT_TYPE_AGGREGATE_ANSWER`) and `scripts/ask.py`'s `TERM.AGGREGATE_LAST` reset went
with their subjects.

`tests/test_k1_family_deletion.py` enforces it as a re-listing guard over `src/`,
`scripts/` and `tests/`. **Verified RED by mutation**: reintroducing
`AGGREGATE_ACTION_ORDER` into `decisions.py` fails with
`K1 deleted these but they still resolve: {'AGGREGATE_ACTION_ORDER': [...]} — the
aggregate family is half-removed`.

Kept, untouched: `extract_amounts` (+ SPEC §18.14 + the dispatch entry), the recall
posterior and generator registry, the same-entity posterior, `compose_total` /
`project_amounts` / `pair_covariates`, and `gate.realised_aggregate`.

### C2 — the naming defect is closed and cannot recur: MET

`AMOUNTS_PRODUCERS` is now `(_ExtractAmountsProducer.name,)` — derived from the deployed
class, never restated. Two tests read the name off the producer: a constant guard and an
end-to-end projection test.

**Verified RED by mutation**: restoring the suffixed tuple fails with
`AMOUNTS_PRODUCERS names a producer that cannot exist: the projection filters
producer_name (a CLASS name) with values from the DECLARATION namespace`, and the
end-to-end test fails with `projection missed the deployed producer name
'extract_amounts'; read 'underived'`.

The three pre-existing tests that broke on the fix were exactly the fixtures that had
encoded the defect (`producer="extract_amounts_docling"` etc.); two died with the family,
and the third's fixture now uses `ExtractAmountsProducer.name`.

### C3 — no behaviour change on the 104: MET, pure equality

`scripts/collapse_replay.py --checkpoint m5-base`, `PYTHONHASHSEED=0`: **314/314 fixtures
replay identically**, exit 0. The declined-path aggregate branch was provably never on the
104's path — which is what C3 predicted and what it would have STOPPED on had it been false.

### C4 — the offer set is unchanged: MET

`menu_transforms(None)` returns the frozen probe sequence, and `GROW_ACTUATORS` is
unchanged. **Verified RED by mutation**: adding one `extract_amounts` row to
`DEFAULT_TRANSFORMS` fails with `the transform menu changed — K1 moved the argmax and owes
a priced gate run`. This is the evidence for buying no priced run, not an assumption.

### C5 — the register lands: MET

`docs/guards.md`. Sixteen guard rows; **four read *resolved*, twelve read *instrumented***
— the honest state and the number this programme exists to move. Six known-and-uncovered
items are recorded in English, outside every count, including the measured universe gap:
the gate reads **104 authored questions** while the live surfaces have already asked **186
distinct ones** (`ask`/`jarvis`) plus **91** through `answer-brain`, with the overlap
unmeasured and no guard that would notice divergence.

Two rows earned their state from real events rather than ceremony: the one-recorder leaf
census has now fired on a real change in **both** directions (a writer added at r21,
removed here), and the replay oracle is recorded as *instrumented* with r06's measurement
attached — three of four decision-path changes were invisible to it by construction, so a
314/314 pure-equality replay is compatible with a decision-path change it cannot see.

### C6 — the adversary pass: fires last, after this section

### Gates

G1 `pytest -m "not llm and not system"` **2780 passed**, 35 deselected; `ruff check .`
clean; `mypy` clean on 226 files; `pii_check.py --shapes-only` exit 0.
G2 **314/314 pure equality** on `m5-base`.
G3 **not bought** — C4 is the evidence.
G4 below.

### Disclosures

1. **The scope change was made before the work and is recorded above**, not discovered
   after: the `extract_amounts` menu row moved to migration stage E3 because every menu
   price today is a hand-set literal and E3 exists to ground them. Adding one now would be
   built twice — the same argument the owner ruled on for K3/K4.
2. **The defect in C2 means the aggregate family never worked end to end.** Run 19 aborted
   on two earlier instrument defects and never reached a leg that would have exercised the
   projection, so the family was merged, gated and reported without any run in which
   `project_amounts` could return an addend. This is independent evidence for deleting it
   rather than repairing it.
3. **The M5 leaf-census guard fired** on the removed recorder writer and was updated, not
   waived. A guard that fires on your own change is the guard working.
