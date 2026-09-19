# r48 — the E1 re-earn measurement: PRE-REGISTRATION

**Frozen and committed BEFORE the instrument runs** (`M-3`). Every number below that is
already known is labelled as such; every criterion is decided by the run.

- **Arc**: C, `GD-10`'s ladder — §17.6's E1 re-earn, the measurement half. `r47` (`GD-24`)
  built the enablement; this reads it.
- **Cost**: $0 (engine CPU on the deployed binary; no API, no restart, no deployment).
- **Deployment**: NONE, and this checkpoint cannot cause one. A live enablement is a separate
  decision that `M-27` makes a measurement in its own right.

## The question

§17.6 ruled that the re-earn path is **not lattice surgery but E1** — a per-candidate
posterior the engine can sharpen from the same evidence — and that the fix is always a sharper
`p1`, **never a softer bar**. §16 then found the sharpening works (`p1` climbing to 0.867 with
evidence) but that **`respond_j` can never be the argmax**, because the
myopic-perfect-information `gather` row is priced above it *by construction*: at that era's Ū
the crossing sat at `p_j > 0.9942` against a θ ceiling of 0.9.

*Two of those three terms have since moved.* The ceiling is now **ours** (#19 changed its
owner; our declared grid's top rung reads **0.990634**), and the Ū has drifted (the deployed
vs-abstain bar reads **0.836894**, `u_wrong` −5.13099). `r45`'s C3 measured the gather
pathology **standing** in the binary world at v2, and every episode `r47` ran chose `gather`.

**So: under today's Ū, on the deployed enabled world at arm B, does `respond_j` ever become
the argmax — and if not, by how much does it miss, and what does the episode cost demand
before anything is enabled live?**

This is the checkpoint `GD-23` §7.4 and `GD-24` both deferred here. It settles it by
**measurement through the deployed rule**, never by re-deriving §16's algebra (`M-7`).

## The instrument, and why it reads rather than computes

`scripts/membrane/reearn_audit.py` (new). It calls `categorical.decide_categorical` — the
deployed episode `r47` built and the shadow supervisor binds — against the deployed arm B
binary. **It contains no EU arithmetic of its own.** The crossing question is answered by
*watching the deployed engine's own argmax move*, not by recomputing §16's inequality with
today's constants: re-implementing the comparison would price a constant through a
re-implementation of the rule that assembles it, which is exactly `M-7`'s trap and the reason
`GD-24` ordered the build first.

## The corpus (a census over distinct inputs, not a sample)

The shadow ledger's recorded `cat` rows carry each episode's **full `summary`**, so the
deployed `CatSummary` is reconstructed verbatim from the record. Known before the run: **2 012
`cat` rows over 78 questions reduce to 129 DISTINCT summaries** (k ranging 1–14). The episode
is a pure function of `(u_bar, summary)`, so replaying the 129 is a **census**, not a
truncation — nothing is dropped and no cap is applied. Population statements are
**frequency-weighted** by the 2 012 rows and reported alongside the per-summary view.

Two facts about the recorded arm, stated now so they cannot be presented later as findings:
the rows were recorded on **arm A, pre-enablement**, and **all 2 012 recorded actions are
`gather`**. They are the baseline, not the result.

## Criteria (J1–J9; **J1 is KILL**)

- **J1 (KILL) — the replay runs.** All 129 distinct summaries complete through
  `decide_categorical` at arm B and decode to a declared action. Any refusal is a KILL: it
  means `r47`'s enablement is not exercised by the real corpus, and the reading stops.
- **J2 — the action census, published whole.** Counts of `respond_j` / `gather` / `ask` /
  `abstain`, per-summary and frequency-weighted. **This criterion has no pass condition** —
  it is the reading. Whatever it says is published, including "gather everywhere".
- **J3 — the binder, measured not inferred.** For each of a declared set of k values, a
  **monotone evidence sweep**: append supporting observations for one candidate, one at a
  time, up to a declared bound, and record `p_argmax` and the chosen action at every step.
  The reading is the **flip point if one exists**, and otherwise the **maximum `p_argmax`
  attained and the fact that no flip occurred within the bound**. The sweep bound and k set
  are frozen here: **k ∈ {1, 2, 3, 5, 10}, up to 40 supporting observations**.
- **J4 — §16 finding 5, answerable for the first time.** #20's per-code readout is live on arm
  B (`GD-23` §7.5), so `p0` IS P(y = 0). Report the `p0` distribution against R-D23's declared
  null-mass cap of `1/(K−1)`, and state plainly whether the cap binds. No pass condition;
  §16 recorded this as unobservable and it no longer is.
- **J5 — the cost, and the K-cap decision it forces.** Per-episode latency by k on the
  deployed enabled world, against the recorded arm A latencies (known: median 76 ms at k=1
  rising to 86.8 s at k=14). §16 finding 4 owes a **K-cap or episode budget before any live
  enablement**; this criterion produces the number that decision needs. A recommendation is
  permitted; enabling anything is not.
- **J6 — the arms are named and the trees pinned.** The engine binary's path and sha, the
  repo HEAD, and `--acknowledge-src-drift`-style stamping if the tree moves mid-run (`M-28`:
  a measurement pins its tree for the whole run).
- **J7 — every load-bearing predicate RED by mutation** before the reading is believed
  (`r05`).
- **J8 — PII-clean.** `CatSummary` is numbers by construction and no candidate string enters
  the instrument; `question_id`s are opaque hashes and no question text is read.
- **J9 — nothing is deployed or enabled**, and no `src/` decision-path change is made. If the
  reading argues for one, that is a *successor's* pre-registration, not this one's licence.

## Blind predictions (reasoning only — the replay has not run)

1. **J2 reads `gather` on all 129.** `r45`'s C3, `r47`'s episodes and the 2 012 recorded rows
   all point one way; I expect no exception.
2. **J3 finds no flip within the bound**, with `p_argmax` asymptoting near the grid's top rung
   (0.990634) and the action never leaving `gather` — i.e. §16 finding 3's binder **still
   binds**, now for a measured rather than an analytic reason.
3. **J4 finds the cap does NOT bind** at small k and may bind at large k, where `1/(K−1)`
   becomes tight.
4. **J5 finds arm B's enabled episodes FASTER than the recorded arm A ones**, because the
   declared 8-rung θ grid gives a smaller model space than arm A's default enumeration
   (`r47` measured `models` 688/1032/1720 at k=2/3/5 against arm A's 3202/4803/8005).
5. If prediction 2 holds, **the E1 re-earn does not clear on this ledger under this Ū**, and
   the named exit is #15 / E3 (act-conditional outcome hypotheses — the engine-held stop rule),
   exactly as §16 staged it. Predicting the consequence is not taking it; see below.

## Consequence branches (frozen before the reading)

- **A flip exists (J3 finds one)** → the re-earn is live evidence, and the successor is a
  §18-class differential gate under its own pre-registration. **Nothing is enabled on this
  reading alone**; `M-27` makes the enabling restart its own measurement.
- **No flip within the bound (predicted)** → **publish the refusal**, with the maximum
  `p_argmax` and the gap to the flip beside it. §17.6's rule binds: the fix is a sharper
  `p1` or an engine-side change (#15 / E3), **never a softer bar** — and this checkpoint may
  not propose one. The E1 re-earn is then recorded as **not cleared on this ledger under this
  Ū**, with the standing exit named.
- **J1 KILL** → stop and re-read `r47`: the enablement would not be exercised by the real
  corpus, which is a finding about the build, not about the binder.
- **In every branch**, the §18 bars remain unread and gain whatever precondition this reading
  establishes.

## Scope, explicit

This does **not** re-open the utility gauge (`u_abstain` is the owner's, priced in its own
conferral and untouched here), does **not** enable the categorical world, and does **not**
file anything upstream. `M-1`'s hard clause is not engaged: no lever ships from this
checkpoint at all.
