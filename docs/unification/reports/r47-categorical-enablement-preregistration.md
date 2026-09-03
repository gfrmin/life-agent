# r47 — the four-item categorical enablement: PRE-REGISTRATION

**Frozen and committed BEFORE any `src/` change** (`M-3`). Nothing in this document is a
reading; every criterion below is decided by the run, not by the author. The instrument is the
deployed code path, not a re-implementation of it (`M-7`).

- **Arc**: C, `GD-10`'s ladder, the rung after `r46` — §17.6's E1 re-earn.
- **Governing design**: `docs/candidates/e1-categorical-outcome.md` (owner-approved
  2026-07-21; §7 re-ground 2026-09-03, `GD-23`).
- **The spec being built**: `GD-22`'s four items, verbatim.
- **Cost**: $0 (engine CPU on the two already-built binaries; no API, no restart).
- **Deployment**: NONE. The categorical world stays env-disabled
  (`LIFE_AGENT_MEMBRANE_CAT` absent = byte-inert). `M-1` is not engaged: this ships no lever
  onto the decision path and cannot make a named wrong-commit class worse.

## The question

*Can the deployed categorical episode — `categorical.decide_categorical` / `run_categorical`,
the code the shadow supervisor actually calls — speak the enabled world at arm B (HEAD), and
does doing so leave arm A and the binary world untouched?*

This is a BUILD checkpoint, not a measurement one. It does **not** ask whether `respond_j`
clears any bar; that is `r48`, and this pre-registration forbids reading it here (see C9).

## Why build before measuring — the ordering, frozen with its reason

The cheaper-looking order is to measure the binder first on an instrument and only build if it
has loosened. **Rejected, on two registered lessons.** `M-7`: a census must read the deployed
rule end-to-end and never re-implement the constant it prices — four instances, one of which
flipped a verdict at a frozen bar. An instrument that re-implemented the episode (session
lifecycle, t-convention, timeout bound, act decoding) to price the binder would be exactly
that trap. And `r30b`: a lever built only in-process is invisible to the measurement that
matters and absent from the deployed path. So the four items land in `categorical.py` — the
ONE declaration both the shadow supervisor and any replay bind — and `r48` then measures
through it.

## The four items (`GD-22`), and where each lands

| # | item | site | shape |
|---|---|---|---|
| 1 | `codebooks.theta` = `theta_grid(u_bar)` **unchanged** | `handshake_decl_cat` | bind `world.theta_grid` — the ONE rule, K-independent (`GD-22`); never a second spelling |
| 2 | a `clock` row | `handshake_decl_cat` | bind `world.CLOCK_NAME` / `clock_price` / `CLOCK_BATCH` — the binary world's row, same objects |
| 3 | a menu-bearing tick | `decide_categorical` | the **evidence** ticks gain `"menu": [ACT_NAME]`; the decide tick already carries it |
| 4 | full indicator coverage | `cat_features` | every name in `cat_indicator_names()` present, dormant at `0.0` — "dormancy is free" is FALSE at HEAD |

## The arms

- **arm A** — the `r41` pin (`1a0cea7`), permissive: the pre-enablement declaration handshakes
  there today with no codebooks at all.
- **arm B** — deployed HEAD (`94fd4eb`, `~/.local/bin/proplang-host`): enforces the door.

## Criteria (C1–C10; **C1, C4 and C7 are KILL**)

- **C1 (KILL) — arm B accepts the enabled episode end to end.** A full
  `decide_categorical` against arm B at k ∈ {2, 3, 5}: handshake `ok`, every evidence tick
  accepted, the decide tick accepted, and the reply's act decoding through
  `value_to_action_cat` to a declared action. Any refusal anywhere = KILL.
- **C2 — the pre-enablement episode is refused by arm B.** The same episode on the tree as it
  stands today must FAIL at arm B. If it already passes, item 3 or 4 was mis-specified by leg D
  and the build has no warrant; STOP and re-read.
- **C3 — arm A is unharmed.** The enabled episode completes at arm A at the same three k. Arm
  A's replies need not be byte-identical to its pre-enablement ones (items 1–2 change the
  declared world and therefore the model population — expected, not a defect); what is
  required is that arm A still completes and still decodes.
- **C4 (KILL) — the binary world is byte-untouched.** `world.handshake_decl(u_bar)` and
  `world.shadow_features` produce byte-identical output before and after, and no binary-world
  test changes. The two worlds share `theta_grid`/`clock_price` by BINDING; a copied constant
  is a fail.
- **C5 — one declaration each.** `theta_grid` and the clock row have exactly one spelling in
  `src/`, and `cat_features`' coverage rule has exactly one. Verified by reading, and pinned by
  a test that fails on a second spelling.
- **C6 — byte-inertness survives.** With `LIFE_AGENT_MEMBRANE_CAT` absent the shadow computes
  no categorical reduction, calls no runner and writes no `cat` row — the existing guarantee,
  re-pinned.
- **C7 (KILL) — every changed predicate is RED by mutation.** At least one mutation per item
  (four), each verified to fail the suite on the committed tree and pass when reverted. A
  predicate no mutation can kill is decoration (`r05`).
- **C8 — the suite, lint and types are green**, and the pre-existing categorical tests either
  pass unchanged or their changes are named here as expected (the declaration's shape is
  pinned by `test_membrane_categorical.py`, so item 1–2 fixtures move by construction).
- **C9 — no measurement is read.** This checkpoint publishes no bar, no crossing, no
  `respond_j` claim, and no `p0` reading. Observing one en route is a disclosure item for
  `r48`, never a finding here (`r07`'s cap).
- **C10 — PII-clean and costed.** Numbers-only rows (`CatSummary` is numbers by
  construction); synthetic summaries only; the tree pinned and the cost stated.

## Blind predictions (source reasoning only — no probe has run for these)

1. **C1 passes at all three k.** Leg D measured each item's necessity separately and the §7.5
   probe drove a codebooks+clock declaration with full-coverage menu-bearing ticks at k=3
   through arm B successfully — but never through `decide_categorical` itself, which is what
   C1 tests.
2. **C2 fails today on item 4 first**, not item 3: the evidence tick carries no menu AND no
   dormant names, and leg D's door leg showed arm B refuses the dormant-omitting tick even
   with a menu.
3. **C4 holds trivially** — nothing in the change reaches `world.py`'s declaration.
4. **C8 will require moving `test_membrane_categorical.py`'s declaration fixtures**, and
   nothing else.
5. **The act will be `gather` on every enabled episode** (C3's constant, `r45`; leg D's K5).
   This is a *prediction*, not a criterion: if it were false, that is `r48`'s to read, not
   this checkpoint's to claim.

## Consequence branches (frozen before the build)

- **All KILL criteria pass** → merge the enablement, publish the reading, and open `r48` under
  its own pre-registration. Still nothing deployed and nothing enabled.
- **C1 fails** → the four-item spec is incomplete. Do NOT patch toward a pass: record what arm
  B refused verbatim (`M-22`), revert, and re-read the spec — leg D's item list would then be
  wrong, which is a finding about `GD-22`.
- **C2 fails** → the build has no warrant (the pre-enablement episode already clears arm B).
  Revert, and re-read leg D's door result.
- **C4 or C7 fails** → revert. A shared-constant break or an unkillable predicate is a defect
  in the build, not a result to publish around.

## Disclosure carried in

The §7.5 probe (`GD-23`) already drove a codebooks+clock declaration with full-coverage,
menu-bearing ticks against arm B at k=3 and got accepted replies carrying
`p0`/`argmax_code`/`p_argmax`/`p_codes[]`. That is **prior evidence for prediction 1 and it is
disclosed here rather than presented later as a result** — it exercised a declaration built as
a delta in an instrument, NOT `decide_categorical`, which is exactly the gap C1 exists to
close.
