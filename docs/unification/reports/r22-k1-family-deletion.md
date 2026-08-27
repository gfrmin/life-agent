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
