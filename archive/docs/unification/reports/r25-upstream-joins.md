# r25 · K2's principle, applied upstream — and the controls that check a proxy

> **Status: PRE-REGISTRATION FROZEN.** Committed BEFORE any change. Results append below
> the rule; nothing above is edited afterwards.

## Why this exists

K2's G4 adversary pass (a fresh session, throwaway worktree, 21517d8) returned **17
findings**. Eight of the thirteen rows `docs/guards.md` called *resolved* were defeated,
including guards written the same day to close the previous pass.

Four findings needed **no plant at all** — they are live in merged master. Three are real
and are fixed here; one is refuted below.

The through-line, and the reason this is one milestone rather than four patches: **K2 fixed
one replace branch and left the upstream stages that do the same thing.** `_compose_one`
runs `_collapse_within_doc` → `_issuer_fold` → `_dedup_pairs` → the join. K2 rewrote the
last stage to keep both channels, and the first two still discard grounded observations —
two of them **silently**. Criterion J1 said *"no channel is discarded"*; it was verified
only at the stage being changed. That is the F10 error again: **a property treated as an
instance.**

## The three live defects (verified against merged master before this prereg)

| finding | input | truth | master reports |
|---|---|---|---|
| **K2-2** | two distinct 250 deposits, one doc, one day | 500 | **250**, `k=1`, `basis_note=''`, `dedup_resolutions=()` |
| **K2-5** | deposits 300 / 100 / 200, one doc, no stated total | 600 | **300**, note *asserts* "issuer-stated total row is the fold" |
| **K2-4** | roll-up dated 09-29, scope ends 09-30 | two reads | **324**, `k=3`; the 31937 read leaves via `excluded_basis`, outside `[lo, hi]` |

`_collapse_within_doc` keys on `(doc_key, kind, round(amount, 2), as_of)` — it ignores
`entity`, `label_raw`, `basis` and `amount_raw`, so two accounts or two line items in one
statement become one, and the total halves in silence. Its cross-document sibling
`_dedup_pairs` prices every drop through the §5 posterior and names it; this one is a
hard-coded `p_one = 1.0` that says nothing.

`_issuer_fold` treats *top == sum(rest)* in a ≥3-row cluster as proof of a stated total. At
exactly three rows that arithmetic coincidence is ordinary, and the note asserts the fold
reading as fact.

## REFUTED, and recorded rather than fixed

**K2-3 — "a `point_in_time` roll-up is summed into monthly flows"** is a mis-framing, and no
change is made for it. Verified: a closing balance recorded as `kind="balance"` is excluded
by the kind filter and **named** in `excluded_kind`; the adversary's case requires a balance
recorded as `kind="deposit"`, which is an *extraction* error, not a composition one. Summing
a deposit whose basis is `point_in_time` is correct — that is one deposit at one instant.

**K2-1 is narrowed.** The join was reported to be evadable by keying a replace branch on
`basis="annual"`. The deployed join is basis-generic — verified for all three members of
`_COARSE_BASES`, identical output. What survives is a genuine coverage complaint: the
fixtures exercise one basis literal, so a *planted* branch on a sibling value would not be
caught. L5 addresses that.

## FROZEN CRITERIA

**L1 — no within-doc drop is silent, and distinguishable rows are not merged.** Two rows
differing in `entity` or `label_raw` are two observations and both survive. Any collapse
that does happen appears in `dedup_resolutions` naming both doc key and value. Test: two
250 deposits with different `entity` in one document compose to `s_obs == 500` and `k == 2`.

**L2 — the issuer fold spans both readings.** *top == sum(rest)* is a hypothesis, not a
fact. The fold stays the point estimate (it is the likelier reading), the interval spans the
sum-all reading, and `basis_note` names the ambiguity. Test: 300/100/200 in one document
returns `point == 300` with `hi >= 600`, and the note says the fold is one of two readings.
This is K2's own rule — two readings, span both, name the disagreement — applied one stage
earlier.

**L3 — no grounded row leaves the composition unnamed.** Every row dropped by kind or by
basis is named in `basis_note` **with its value**, so a contradicting read is never
invisible. Deliberately NOT widened into the interval: a coarser-basis row may be a partial
roll-up, and this milestone does not invent a coverage model for one. Naming is what J4
requires; spanning would require a model that is not yet earned.

**L4 — the CI positive control requires a REPORTED FAILURE, not any non-zero exit.**
Measured: a real assertion failure exits **1**, a missing file exits **4**, and a control
renamed so nothing is collected exits **5** — and the job's `if pytest; then fail; else
pass` reads all three as "went red as required". The control can be deleted outright and CI
still records that it spoke. The step must require exit **1** AND a `1 failed` line naming
the expected test id. Verified by all three cases.

**L5 — the join fixtures cover the declared class, not one literal.** The roll-up fixtures
are parametrised over every member of `_COARSE_BASES`, and a test asserts that set is the
one the composition reads, so adding a basis without extending the fixtures fails.

**L6 — `_SKIP_PATHS` is pinned whole and every skip is announced.** Adding a tracked prose
file to the skip set exempted `README.md` from the PII guard with the gate green. The set is
pinned by equality (not by membership of known-good names) and every skipped path is printed
on every run — the property the F5 fixture's own message already claimed ("a skipped file is
reported, never silent") and which was never implemented.

**L7 — the decision path does not move.** `core/aggregate.py` is off it. The replay reads
**PURE EQUALITY**; anything else is a FAIL and a STOP.

**L8 — every new fixture names its mutation in its OWN docstring** (register row 19, whose
census concatenated the module docstring and so passed every fixture in a file whose header
carried a trigger phrase — defeated as K2-8; that census is repaired here too).

## NOT in this milestone, and why

The pass's central finding is structural: **eight of eleven defeats are a census whose
universe is a string** — a name, a literal, a docstring phrase, a set member, an argument
spelled `question`. Each is one alias, one concatenation, one rebinding or one adjacent enum
value wide, and each was written against the one instance last seen. That is entry 1's own
lesson describing the guards written *after* entry 1 was recorded.

Repairing individual evasions (K2-9's intermediate binding, K2-11's rebound `question`,
K2-12's computed attribute name) would produce more string censuses one alias wider. That is
a design question about how guards prove things at all, and it is surfaced to the owner
rather than answered by reflex here. L4 and L6 are included because they are the *other*
class — a control checking a proxy for failure — which has a clear, non-arbitrary fix.

## Gates

G1 suite + ruff + mypy + PII green · G2 the replay per L7 · G3 not bought — the module is off
the decision path · G4 deferred: this milestone answers a G4, and a third pass belongs after
the census question is ruled.

---
## RESULTS

**Read 2026-08-27, $0. All eight frozen criteria MET.**

### L1 — the within-doc collapse: MET

The key gains `entity` and `label_raw`; every collapse is named in `dedup_resolutions`.
Two distinguishable 250 deposits in one document now compose to `s_obs == 500`, `k == 2`
(was 250 / `k == 1` / silent). **Mutations:** narrowing the key back fails with *"two
distinguishable line items collapsed to k=1, s_obs=250.0"*; removing the resolution note
fails the silence fixture.

### L2 — the issuer fold spans both readings: MET

`top == sum(rest)` stays the point estimate and the sum-all reading now widens the
interval, with the note naming the competing reading explicitly. 300/100/200 returns
`point == 300`, `hi >= 600`. **Mutation:** dropping the alternative fails with *"interval
[300.0, 300.0] excludes the sum-all reading 600.00 — an arithmetic coincidence in a 3-row
cluster is ordinary, and the fold is a hypothesis"*.

### L3 — nothing leaves unnamed: MET

Every `excluded_basis` row is named with its value. **Mutation:** dropping the note fails
with *"a grounded row was excluded from the sum and its value is nowhere in the note"*.
`excluded_kind` rows are filtered by `compose_total` before `_compose_one` sees them, so
their values are out of scope there; the doc/kind pair already names them — disclosed
rather than silently narrowed.

### L4 — the CI control requires a reported failure: MET

Measured on this tree: a real assertion failure exits **1**, a missing file **4**, a control
renamed so nothing is collected **5**. The step now requires exit 1 **and** the expected
test id in the report, and rejects 4 and 5 with a message naming what each means.

### L5 — the fixtures cover the class: MET

The roll-up fixtures are parametrised over every member of `_COARSE_BASES`, and the set is
pinned whole. All three pass unchanged, confirming the narrowed K2-1: the deployed join was
always basis-generic; only the fixtures were one literal wide.

### L6 — `_SKIP_PATHS` pinned and skips announced: MET

Pinned by equality; `announce_skips` prints every skipped path on every run. **Mutation:**
adding `README.md` fails with the set printed.

### L7 — the decision path does not move: MET, pure equality

**314/314 fixtures replay identically.**

### L8 — the mutation rule reads the fixture's own docstring: MET, and the fix here is the
interesting one

Tightening the rule immediately caught **its own two fixtures**, which had been relying on
the module docstring. More importantly, the first attempt at this criterion **failed its own
mutation**: as a census over the real `tests/` tree it could only be exercised by mutating
the real tree, so restoring the concatenation went undetected. The rule was extracted as a
**pure function over synthetic source** (`fixtures_missing_mutation`), and the mutation then
failed correctly with *"it is reading the module docstring, so the census's universe is the
FILE, not the fixture"*.

That is the second time in two days that a control passed its own mutation, and both had the
same cause: **a guard that can only be tested by modifying the thing it guards cannot be
mutation-tested at all.** Extracting the rule as a pure function is the general fix, and it
is the one lever this milestone found that generalises beyond its own findings.

### Refuted, and recorded

**K2-3 is not a defect.** Verified: a closing balance recorded as `kind="balance"` is
excluded by the kind filter and named in `excluded_kind`; the reported case requires a
balance recorded as `kind="deposit"`, an *extraction* error. Summing a deposit whose basis
is `point_in_time` is correct — one deposit at one instant. No change made.

**K2-1 is narrowed.** The join is basis-generic across all of `_COARSE_BASES`, verified
directly. What survived is the coverage complaint, closed by L5.

### Gates

G1 **2828 passed**, 35 deselected; ruff clean; mypy clean on 226 files; PII exit 0.
G2 **314/314 pure equality** on `m5-base`. G3 not bought. G4 deferred pending the census
ruling below.

### Register

**16 resolved / 9 instrumented**, with rows 0 and 19 re-earned after being defeated, and
rows 20/21 new.

### Still open, and NOT patched here

Eight of K2's eleven defeats were **a census whose universe is a string**. Repairing each
evasion individually (an intermediate binding, a rebound `question`, a computed attribute
name) produces more string censuses one alias wider. The one general lever found here — make
the rule a pure function so it can be mutation-tested at all — is landed. Whether the
remaining censuses should be replaced by behavioural assertions is a design question carried
to the owner, not answered by reflex.
