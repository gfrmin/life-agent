# Conferral — the first §18 bar FAILed, and the gauge is the question (2026-09-04)

Evidence, options and prices, written **before** the interview (house rule). Everything here is
**$0** — arithmetic and censuses over artefacts `r49` already produced. Nothing is enacted, no
`src/` change is proposed, no successor rung is opened, and no bar is loosened in any option
below.

**Why this reaches the owner at all.** Two reasons, and the second is the real one.

1. **Procedurally**, `r49`'s own pre-registration froze it: §18's rule is *iterate, not park* —
   **except** that §17.6 (2026-08-17) already FAILed this same A3 criterion, and no A3 read has
   passed since. A second consecutive FAIL on one frozen criterion stops for an owner ruling
   rather than a unilaterally-chosen successor. That is execution of a frozen branch, not a
   judgement.
2. **Substantively**, the reading turned up a question that is **objective-class** and therefore
   `RULINGS.md` §5's residue by construction: **which utility is §18's bar quoted at?** The same
   24 commits, on the same rows, are worth **+0.075/question** at the utility the system actually
   decides with and **−0.080/question** at the utility the gate scores with. Nothing about the
   engine distinguishes these; the gauge does.

---

## 1. What was asked, and what came back

`r49` ran the A3 differential adoption gate — the membrane's held-out policy against the
credence baseline `ff-v2-baseline-m3off`, 20 000 draws, seed 8675309, δ = 0.05, bar
P(Δ>0.05) ≥ 0.90 — over three covariate variants, 141 leave-one-out questions each, 423 engine
spawns, 14h02m, **$0**.

| variant | verdict | P(Δ>0.05) | Δ̄ | 90% interval | answer rate (membrane · baseline) |
|---|---|---:|---:|---|---|
| FULL (17 indicators) | **FAIL** | 0.301 | −0.081 | [−0.482, +0.205] | 0.67 · 0.35 |
| leader-credence+p-none | **FAIL** | 0.301 | −0.081 | [−0.482, +0.205] | 0.67 · 0.35 |
| leader-credence-only | **FAIL** | 0.000 | −1.479 | [−2.297, −0.765] | 1.00 · 0.35 |

The full reading is `reports/r49-s18-bars.md`; the decision that published it without re-reading
the bar at the softer gauge is `GD-26`.

## 2. The three findings under the verdict

**(a) The failure is pure over-assertion, and it is 24 rows wide.** The membrane's report set
**strictly contains** the baseline's — there is not one question where the baseline commits and
the membrane withholds — and on the 26 shared commits the two arms never disagree about
correctness. The entire differential is **24 marginal commits: 21 right, 3 wrong, 0.875**.

**(b) The gauge decides the sign.** A committed answer breaks even at
`p* = −u_wrong/(1−u_wrong)`:

| gauge | `u_wrong` | break-even | the 24 marginal rows are worth | point Δ |
|---|---:|---:|---:|---:|
| deployed boot Ū — *what the system commits with* | −5.130990 | **0.836894** | +0.234/q | **+0.075** |
| gate's utility posterior — *what the gate scores with* | −8.9993 | **0.899993** | −0.250/q | **−0.080** |

The measured 0.875 lands **between them**. This is a *point* restatement of the gate's own
published action table, not a second gate reading — no posterior centred on the boot Ū exists,
and **`GD-26` declined to build one after seeing the FAIL** (§17.6: *a sharper `p1`, never a
softer bar*; `M-4`). The gap is registered as `M-31`.

**(c) One covariate family carries the whole policy.** `leader-credence` alone is degenerate —
mean `p1` **0.8584 in four of five buckets**, above the bar, so it commits on everything and *is*
respond-all. Adding `p-none` produces the entire working policy. Adding `n-candidates`, `n-obs`
and `flags` on top changes **no action on any of 238 ticks** (the paired files are
byte-identical; `p1` moves ~10⁻⁸), and **three of the seventeen declared indicators never fire at
all**. The lattice is 2 useful families wide, not 5 — while costing 960 models against 456.

**Two disclosed instrument gaps.** Δ_spend is **0.000 structurally**: all 104 baseline rows carry
`cost_usd: null` with every token counter zero, so unlike r28's π\* this arm's spend cannot even
be imputed (direction: it would favour the membrane arm; magnitude: fractions of a cent per
question in this era, so very unlikely to be material against δ = 0.05 — named, not leaned on).
And the harness timestamps no phase boundary, so 14 hours cannot be attributed across its three
arms (`M-32`) — which is what blocks sizing the parallel-harness successor.

## 3. The independent blocker, so no option is oversold

`M-1`'s hard clause bites regardless of Δ, at any gauge: the membrane arm commits **q2-019** —
the named truncated-leader **superset-confirm** class, currently *withheld* on deployed master —
**wrong**, along with two other new wrongs on rows the baseline abstains. **No option below
deploys anything.** The gauge question decides whether §18's bar is *met*, which gates Arc C's
progression to §11's exit; it does not by itself put this policy anywhere near production.

## 4. The options, with prices

| # | option | price | what it forecloses |
|---|---|---|---|
| **A** | **Rule the gauge prospectively, then continue** — the owner settles which Ū §18's bars are quoted at (the elicitation posterior, or the deployed boot Ū the system decides with), *for future reads only*; `r49` stands as FAIL either way. | **$0** ruling; the next read is priced by whichever of B/C follows it. | Nothing. It removes an ambiguity that will otherwise recur at every §18 read and at every future gate. |
| **B** | **Sharpen `p1` where it is measurably wrong** — the licensed direction. The defect has a precise address: the 70–90 leader-credence band, 55 rows, realised correctness **0.800**, committed at mean `p1` 0.863–0.873, against a needed 0.837 (deployed) / 0.900 (gate). The census says `p-none` and `leader-credence` are the only families carrying signal, so a family that separates that band is the concrete lever. | Build + one gate run: **$0 in model spend**, ~14h serial or ~2h on a parallel harness (see D). Own pre-registration. | Nothing; this is what §18's *iterate* branch means. It is the only option that can change the FAIL honestly. |
| **C** | **Repair the instrument before re-reading** — record the baseline arm's spend so Δ_spend is a measurement rather than a zero, and make the gate print both break-evens (`M-31`) and timestamp its phases (`M-32`). | **~$0–low**; a re-recorded baseline arm is a priced run of the credence executor lane over 104 questions (era cost: cents). | Nothing. Strictly additive, and cheap. It does not by itself move the verdict. |
| **D** | **Build the parallel harness first** — the 423 spawns are independent by construction (one fresh engine per question, no shared state). This is the sizing that `M-32` says `r49` cannot supply, so it would be built to a guess. | ~half a day of build; turns every future bar read from ~14h into ~2h. | Nothing, but it is infrastructure, not evidence — it makes B cheaper without making B more likely to pass. |
| **E** | **Park Arc C at §18** — declare the migration's evidence bar unmet and stop before §11's exit. | $0. | **This is the one option that touches a standing ruling**: proplang-replaces-credence is *gated-mandatory* — the bars pace the swap, a FAIL means iterate-and-re-run, and refusal was explicitly retired as an endpoint. Parking would amend that, which is why it is on this page rather than being taken. |

## 5. Recommendation

**A + B, in that order; C alongside; not D yet; not E.**

- **A first** because it is $0, it is genuinely the owner's (a gauge is convention, not
  evidence — `RULINGS.md` §5), and leaving it open means every future §18 read inherits the same
  ambiguity. Rule it **prospectively**: `r49` stands as FAIL under either answer, so the ruling
  costs nothing retroactively and cannot be accused of having been chosen for its result.
- **B** because §18's own rule is *iterate*, and for the first time the iteration has a measured
  address rather than a hypothesis: 55 rows, one band, a 0.037–0.100 correctness shortfall, and a
  covariate census saying which families have room in them.
- **C alongside** because both gaps are cheap and both are the kind of thing that silently
  invalidates the *next* reading rather than this one.
- **Not D yet** — it is real value (14h → 2h) and it is the right next infrastructure, but
  `M-32` means it would be sized by guess today; the timestamping in C is its precondition.
- **Not E** — nothing in this reading says the swap cannot clear a bar. It says the engine
  over-commits in one measurable band and that the bar's gauge was never pinned. Those are both
  repairable, and one of them is repairable for free.

## 6. The question, stated plainly

> **Which utility is §18's bar quoted at — the elicitation posterior (`u_wrong` −9.0, break-even
> 0.900), or the deployed boot Ū the system actually commits with (`u_wrong` −5.131, break-even
> 0.837)?** And, given the answer: iterate on `p1` in the 70–90 band (B), or something else?

Everything else in this document is delegated and does not need a keypress.
