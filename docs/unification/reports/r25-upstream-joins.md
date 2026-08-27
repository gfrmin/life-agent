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
