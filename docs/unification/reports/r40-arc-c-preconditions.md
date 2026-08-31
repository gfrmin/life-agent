# r40 — Arc C's preconditions: a $0 stocktake

Opened by `GD-9` (the queue advances to Arc C) under `A-2`/`G-2`. **$0, no `src/` change, no
verdict.** This is not a measurement with a kill — it is the live check that `M-10`'s spirit
and the standing "re-verify inherited state" rule require **before** an arc is planned on
inherited claims.

It found the arc's premise stale, so the useful output is a **re-scope**, not a plan.

## What Arc C was going to be

membrane-shadow §18 (owner ruling, 2026-08-25) makes the proplang migration **gated-mandatory
and deferred**: the bars pace the swap, a FAIL means iterate, and the terminus is §11's exit
criteria. §17.6 names the re-earn path precisely — **not lattice surgery, but E1: a
per-candidate posterior the engine can sharpen from the same evidence**, because the engine's
`ge90` belief sits at 0.856–0.899 where that ledger's empirical rate is **1.00**, and the fix
is a sharper `p1`, never a softer bar. §18 also states, as a standing condition, that **"the
shadow keeps accruing."**

## What is actually true on this machine, measured today

| claim | source | measured |
|---|---|---|
| the engine binary is installed at `~/.local/bin/proplang-host` | §15 (sha `ebc06c81…`, from proplang `1a0cea7`) | **absent** — no `proplang-host`, and no proplang binary anywhere on `PATH` |
| the shadow keeps accruing | §18 | **stopped 2026-08-10T16:06:47 — 21 days ago** |
| the shadow is enabled | env-gated, absence = disabled | **disabled** — no `MEMBRANE_COMMAND` in `.env` or any `systemd --user` unit |
| the proplang tree is at `1a0cea7` | §15 | the local checkout is at **`94fd4eb`** — far ahead |

The shadow's own record is intact and self-describing: **6 683 records, 2026-07-19T07:12:04 →
2026-08-10T16:06:47**, the last a boot record carrying binary sha `ebc06c81…` and 2 188 source
records replayed. So the stream is not corrupt; it simply **ends**.

**Why it ends is not established, and I am not going to guess.** The obvious candidate — the
production role moving to this machine — is **contradicted by the dates**: the move was
2026-08-30 and the stream stops 2026-08-10, twenty days earlier. Naming that as the cause would
be exactly the inference this arc has been punished for twice already (r36's misdiagnosis;
r39's point-estimate). It is an open question, recorded as one.

## What this changes

**Arc C's first step is not E1.** Every bar §18 freezes — the 0.899 `p3` commit bar, the
§8-class priced differential gate, the hard clause — is read against a *shadow ledger*, and on
this machine there is no engine to produce one and no accrual to feed it. E1 engine work
would be filed as proplang issues (§11: *"the proplang repo is never edited from here"*) against
a binary nobody here can run, and its effect would be unmeasurable.

So Arc C opens on **preconditions**, in this order:

1. **P0 — the engine, pinned and provenanced.** Build `proplang-host` from a *named* commit and
   record its sha256, following §15's own procedure: **byte-compatibility verified BEFORE any
   swap** (handshake reply and a decide reply identical old-vs-new under sorted-JSON compare,
   plus the `test_membrane_live.py` system smokes). Since proplang has moved `1a0cea7` →
   `94fd4eb`, adopting HEAD **is itself an engine change** and inherits that discipline rather
   than bypassing it — a rebuild is not a neutral act just because it is a rebuild.
2. **P1 — accrual restored, and the gap declared.** Re-enable the shadow and let it accrue. The
   ledger will then have a **21-day hole** with a binary change across it. That hole is a
   segmentation boundary, not a nuisance: `M-14` and r29's stream-contamination finding both
   say a stream whose generating policy changed mid-way must be **segmented or excluded before
   it is refit**, never silently pooled. Any successor reading this ledger declares the
   boundary.
3. **P2 — only then** the E1 re-earn path §17.6 names, with its own pre-registration and §18's
   bars.

## Two things this stocktake deliberately does not do

**It does not rebuild anything.** Installing an engine binary and re-enabling a shadow are
changes to a live machine, and they belong inside P0/P1 with their pins and checks recorded —
not as a side effect of looking.

**It does not re-open §18.** The migration is still mandatory, still gated, still deferred
behind nothing that remains. What moved is only the *first rung*: the ladder cannot start at E1
when the engine is not installed.

## The standing lesson, since this is the third time

r36 diagnosed a kill from a property of an instrument rather than from the instrument's
population. r39 priced a decision with a function its own docstring disclaims. r40 was about to
plan an arc on a doc sentence — *"the shadow keeps accruing"* — that stopped being true three
weeks ago. **A checkpoint's first act should be to measure the claims it is standing on**, and
the cost of doing so here was four commands.
