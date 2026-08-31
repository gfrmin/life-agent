# r41 / P0 — the engine, pinned and provenanced: READING

Pre-registration + amendments 1–2 + the `t` addendum:
[`r41-p0-engine-preregistration.md`](./r41-p0-engine-preregistration.md). Instrument:
`scripts/p0_engine_replay.py`. **$0 model spend. Nothing installed, nothing enabled.**

## Verdict

**P0-2 PASSES on the one readable row, and the control arm did exactly what a control arm is
for.** Arm A — `proplang-host` at `1a0cea7` — reproduces a recorded shadow decide **exactly**:

```
-- decide t=13 under boot n_source_records=867
   t reached 13 of 13 (verdicts available 70)
   action  recorded='gather' replayed='gather'  -> MATCH
   readouts MATCH
```

`readouts MATCH` is full-precision equality on both `p1` and `entropy_bits` — the ledger stores
float repr and the instrument compares it, with no tolerance, because choosing a tolerance is
the criterion's job and not the instrument's.

So the harness is proven: a decide recorded in July, replayed today from the shadow's own boot
path against the commit the ledger names, comes back identical. **Arm B's differences will
therefore be attributable** (P0-3), which was the entire point of insisting on a control.

## The second row is UNREADABLE, and the reason is a measurement

```
-- decide t=193 under boot n_source_records=1644
   t reached 70 of 193 (verdicts available 70)
   -> UNREADABLE: only 70 verdicts survive today, so t=193 is unreachable.
```

**The derived verdict stream has shrunk from ≥193 to 70 — a 64% loss — while its source logs
only ever grew.** That is not a contradiction, and the addendum half-predicted it: `boot_snapshot`
supersedes on `decision_id`, latest reaction wins. What the addendum said was that supersession
could **rewrite** a verdict. The measurement is stronger: it can **remove** one. A later reaction
whose `(chosen_action, valence)` pair is `verdict_y`-undeclared — a `good` on a `hedge`, say —
decodes to nothing, so the decision it superseded contributes **no** observation at all.

The instrument reports this as **UNREADABLE, never as FAIL**. `t` is an *input feature* of the
decide, so a session that cannot reach the recorded `t` is a different engine state; scoring
that as a mismatch would blame the engine for the ledger's own shrinkage. (`G-3`: a check whose
universe is absent reports absence, not a verdict. The first version of this instrument did fold
it into FAIL; that was fixed before the reading, and the fix is pinned by its own mutation.)

**Consequence beyond P0.** Most of the shadow's history is **not warm-reconstructible today**,
and the deficit grows with `t`. Any future reading of this ledger inherits that, and P1's
"declare the 21-day gap as a segmentation boundary" is now the *smaller* of two discontinuities:
the larger one is that the pre-existing record's own warm states cannot be rebuilt.

## Criteria

| id | verdict | evidence |
|---|---|---|
| **P0-1** | **PASS** | arm A is `1a0cea7`, sha `1d008643…` recorded; arm B's worktree prepared at the pinned current commit, unbuilt |
| **P0-2** | **PASS** on the readable row | exact action + readouts at `t=13`; the `t=193` row unreadable, with its cause measured |
| **P0-3** | **not reached** | arm B is not built; this reading buys the control, not the comparison |
| **P0-4** | **not reached** | nothing is installed, so there is nothing to smoke |
| **P0-5** | **PASS** | nothing enabled, no `MEMBRANE_COMMAND` set, no proplang issue filed |

The instrument's own ladder: **9/9 mutations RED**, run before the reading.

## What is deliberately left for the next step

Arm B (build the pinned current commit, replay the same row, attribute every difference), then
P0-4's smokes on whatever is installed. Both are cheap now that the control holds — which is
the only reason the control was worth buying first.

---

## P0-3 — arm B refuses the handshake, and the cause is named

Arm B built cleanly from the pinned current commit in ~2 minutes (sha `71998f65…`, GHC 9.10.3).
Driven with the **same** replay, against the same recorded decide:

```
arm A 1a0cea7: ok=True  proto=1  error=None
arm B 94fd4eb: ok=None  proto=None  error='bad hello'
```

The identical world declaration is accepted by the ledger's commit and **refused** by the
current one. Because arm A reproduces exactly (above), the refusal is **the engine's, not the
harness's** — which is the whole return on buying a control arm.

**The named change.** HEAD's `hello` parser requires a key the shadow does not send:

```haskell
-- THE WORLD'S CODEBOOKS (E3: the emission codebook is world data;
-- theta REQUIRED, rho optional — absent means no walk family)
cbs <- oGet "codebooks" w
thetaG <- pairGridNamed "theta" =<< oGet "theta" cbs
```

`oGet "codebooks" w` runs in the `Maybe` monad, so an absent `codebooks` collapses the whole
parse and yields `bad hello`. `codebooks` appears **0 times** in `1a0cea7`'s `Host.hs` and
**once** in `94fd4eb`'s. The shadow's `handshake_decl` sends exactly
`{guards, menu, namespace, utility}`.

So: **E3's emission codebook became required world data in the handshake between the two
commits, and the shadow's world declaration predates it.**

*One hypothesis tested and refuted en route*, recorded because a discarded guess is cheaper to
publish than to re-form: the diff shows `parseSaid` moving and a new *"unknown form = bad hello,
fail-closed"* comment, which suggested `said@1` had been retired. It has not — `said@1` is
still the only declared form at HEAD, and `Membrane.hs` gained a mention of it. The guess was
wrong and is not in the finding.

### What this means for Arc C

**Adopting HEAD is not a drop-in, and the work is host-side — which is the good news.** The fix
is `membrane/world.py`'s `handshake_decl` declaring `codebooks.theta` (and optionally `rho`).
That is this repo, not the proplang repo, so it needs no issue filed and no engine ask (§11's
constraint is not engaged).

**It is not plumbing, and it does not get done here.** A codebook is *world data* — it declares
what the engine believes about emissions, and `theta` is a grid the engine will condition on.
Choosing it changes the decisions the engine makes. So it gets its own pre-registration with
its own bars, exactly as `P0-5` demands of anything that would change behaviour, and exactly
as §18's "the bars pace the swap" requires.

### Criteria, closed

| id | verdict | evidence |
|---|---|---|
| **P0-1** | **PASS** | arm A `1a0cea7` sha `1d008643…`; arm B `94fd4eb` sha `71998f65…`, both recorded |
| **P0-2** | **PASS** on the readable row | exact action + readouts at `t=13` |
| **P0-3** | **PASS** | the one difference is enumerated and attributed to a named change: `codebooks` became required |
| **P0-4** | **not reached** | nothing installed — and on this evidence nothing *should* be, until the declaration is repaired |
| **P0-5** | **PASS** | nothing enabled, no issue filed |

**P0 closes.** The next rung is the world-declaration repair, pre-registered on its own, and
only then P1's accrual.

### What the successor must establish first — `theta` is not a formality

Bounded $0 look, so the next pre-registration starts from evidence rather than from the word
"codebook". At HEAD, `thetaG` is threaded straight into the world enumeration —
`enumerateWith nsN obsC thetaG gs mRhoG fragFull` — and `Membrane.hs` orders lattice children
by it (`sortOn nodeTheta (childrenOf n)`, with the path bits reading *"False = low-theta child,
True = high"*).

So **`theta` is the emission codebook's parameter grid, and it shapes the lattice the engine
enumerates over.** Declaring it is declaring the engine's emission hypothesis space: a
different grid is a different set of worlds considered, hence different decisions. `rho` is
optional and its absence means *no walk family* — itself a modelling choice, not a default.

That is why the repair is not a one-line plumbing fix and does not ride along with P0. Its
pre-registration has to say what grid is declared **and why that one**, with §18's bars
measuring the answer — which is exactly the discipline that made arm A's exact reproduction
worth having.
