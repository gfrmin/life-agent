# E1 — the categorical outcome (deliberation doc, 2026-07-20; re-grounded same day)

**Status: DELIBERATION — a frozen-layer decision paused for conferral (pixel6), not a
build order.** This is the life-agent side of the E1 design: how our membrane world
adopts a K-ary outcome on the proplang wire, what evidence says it is the binding
lever, and the specific decisions the conferral must settle.

**Re-grounded 2026-07-20 against proplang HEAD `1a0cea7`:** the engine side is no
longer merely staged — **W3 (K-ary observations) LANDED and CLOSED** (OB-5 discharged),
along with W4 (full priced grammar + optional said@1 pricing) and R1 (the purchasable
refine lattice, engine-internal). The wire our world would declare against **exists**.
What did NOT land is equally load-bearing: no per-code posterior readout, no per-sensor
reliability (OB-12 still ruling-pending), a declared null-mass cap (R-D23), and the
refine lattice is not wire-reachable (the p1 grid ceiling 0.9 stands on the wire).
§3 states the landed surface exactly; §4–§5 are designed against it, not against the
draft.

All numbers below are aggregates from `$LIFE_AGENT_KB` eval/membrane artifacts; no
corpus content. Candidate examples are synthetic.

## 1. The decision

Whether — and in what shape — life-agent's membrane world moves from the binary latent

> y = "asserting now would be correct" (posterior readout `p1`)

to a **categorical outcome over {NONE, candidate_1..K}**, so that:

- the engine conditions on **which candidate** the evidence supports and holds the
  no-answer mass itself (the M4 prerequisite: today p_none is the credence daemon's),
- **respond becomes value-indexed** (`respond_j`, the M5 prerequisite): the engine
  prices asserting candidate j against being wrong, instead of a single "respond" whose
  value the host picks by MAP after the fact (the D7 remnant M3 ships flagged),
- extraction hits and owner verdicts become **sensor observations with declared
  likelihoods** (roadmap ruling 2: "model verdicts are sensors — their decision-effect
  flows only through declared likelihoods, never a host `continue`").

This is expensive to reverse: it changes the handshake world, the evidence stream's
meaning (today's binary verdict ticks do not replay into a categorical world), and the
session topology (per-question candidate sets). Hence deliberation-doc-first.

## 2. Evidence that this is the binding lever

1. **The engine structurally cannot assert.** 1,757 decide ticks, **0 respond chosen**;
   max p1 ever observed 0.339 against a whole-menu respond bar of 0.994 (live u_bar;
   vs-abstain alone would be 0.856 — cleared, but gather outbids it; register §7). The
   respond act prices a *nameless* assert: the engine never knows which value would be
   asserted, only bucketed `leader-credence` features about it.
2. **The disagreement ledger prices the gap.** `respond→gather` disagreements: n=111,
   Σ eu_delta +432.8 in the engine's world — the engine second-guesses every incumbent
   assert because its own y-posterior is starved (`abstain→gather`: n=407, Σ +123.6).
3. **M3 flag-on enacted the consequence** (`ff-v2-baseline-m3on`, n=104, advisory
   publication): the engine chose gather on **all 547 consults**; at menu exhaustion its
   live p1 was ≤0.1 on nearly every tick → 134 abstains, 1 ask, **0 correct / 0 CW /
   100% withheld, 25 daemon would-asserts overridden** (23 of them correct in the
   flag-off run). Honest, and honestly useless as an answerer until the engine can hold
   a belief about *answers* rather than about a pooled binary proposition.
4. **The corpus gap is extraction/assertion, not retrieval** (n=104: recall@20 0.99,
   correct 24.5%, over-abstention 73.5%; deliberative π* 92.3%). The categorical outcome
   is what lets the engine consume extraction evidence *per candidate* — the actual
   bottleneck — instead of `n-obs` buckets.
5. **Why the binary world starves.** Its verdict stream pools across questions
   (P(correct | bucketed features), ~tens of one-bit verdicts total), so p1 moves at
   owner-verdict speed. The categorical world gets its per-question posterior from that
   question's own extraction observations (dozens per question, machine-speed) and
   spends owner verdicts on the *shared* parameters — the same inversion that made the
   daemon's lookup family work.

## 3. The landed wire (proplang HEAD `1a0cea7`, verified 2026-07-20)

**Landed (W3/W4), conformance-ready:**

- **`"obs_arity": K`** — optional flat key in the handshake `world`; K integral ≥ 2;
  absent = the shipped binary channel, byte-identically. Codomain = atoms `0..K-1`
  with **atom 0 the NULL emission** — the NONE convention is the wire's own.
- **Evidence ticks name the code**: `{"tick": {"features": ..., "evidence": j}}` — the
  existing scalar now carries the observed atom; reply echoes `observed: j`.
- **Emission family**: the symmetric concentration channel P(y=j)=θ, P(y≠j)=(1−θ)/(K−1),
  θ from the frozen grid {0.1..0.9}, enumerated over the same const/walk/guard families
  as binary bern with the distinguished atom as an outer loop.
- **Utility grammar (W4)**: `said@1` now parses the full priced grammar — if, >, +, −,
  ×, ÷, log, exp, neg, c, var, get (no `<`: swap arguments of `>`). Optional `cgrid`
  buys priced constants (`utility_bits` in the hello reply); omitted = pre-W4
  byte-identical behaviour. Per-tick utility revision is explicitly unshipped (folded
  into OB-11's class) — utility is declared once, which is what our session does.
- **Compatibility**: our existing binary declaration handshakes and ticks **byte-for-byte
  unchanged** at HEAD (all additions are optional keys). A rebuild of the deployed
  binary (prod runs a 2026-07-19 build of `7da274b`, pre-W3) is a *lawful upgrade* —
  conformance binds to membrane-wire.md, not the artifact (register §10).

**Not landed — and binding on our design:**

- **Readouts are unchanged**: the decide reply still carries a single scalar `p1`, now
  meaning "predictive mass of atom 1 against the declared obs-space." **No per-code
  posterior, no argmax code, no P(y=0).** The engine can *choose* `respond_j` without
  any of that; what we lose is host-side observability (honest footer rendering,
  report pricing). A per-code readout is a small observability-only wire need → §5.4.
- **Per-sensor reliability did not land** (OB-12, increment B, still RULING-PENDING):
  θ is one shared latent axis; an observation cannot carry its own channel fidelity.
  Extraction hits and owner verdicts flow through the *same* learned channel until B.
- **R-D23 null-mass cap**: the null atom's predictive mass is capped at 1/(K−1); a
  NONE-dominant sparse channel at K≥3 "has no good hypothesis" — the two-parameter
  family is its *demand-gated* heir. Our over-abstention corpus (73.5% no-assert) may
  be exactly that demand — evidence to send, not a blocker to shadow-first (§5.6).
- **The refine lattice (R1) is engine-internal** (`runPurchase`), not wire-reachable:
  **the θ/p1 grid ceiling 0.9 still stands on the wire**; OB-4 ruled out an
  emission-grid key permanently — purchased refinement is the declared heir.
- **OB-11 (mid-episode K growth) still RULING-PENDING** → K fixed per episode,
  published at tick 0, remains the sanctioned shape → session-per-question (§5.2).
- No boundary is currently open; pending OBs await author rulings. Per roadmap ruling 3,
  our needs travel as evidence on the existing issues, not as new mid-flight asks.

## 4. The proposed life-agent world (v3 of `world.py`'s declaration)

### 4.1 Outcome and observations

Declare `obs_arity = K + 1` where 1..K are the tick's candidates **in candidate order**
and **atom 0 = NONE (the wire's own null emission)**. Observations are code-valued
evidence ticks:

- **extraction hit**: a grounded observation supporting candidate j → `evidence: j`
  (~13/question at machine speed);
- **owner verdict, natively mappable now**: (assert of value v_j, "good") →
  `evidence: j`; (abstain, "good") → `evidence: 0`;
- **owner verdict, NOT expressible until OB-12**: (assert v_j, "bad") = evidence
  *against* j — the shared symmetric channel has no anti-report, and with one shared θ
  a "refute channel" cannot be declared. Named exclusion, mirroring today's
  `_VERDICT_Y` rule: ambiguous is not evidence. Revisit at increment B.

One honest weakening vs the draft design: until OB-12, extraction hits and owner
verdicts are **indistinguishable in reliability** — one θ serves both. Acceptable for
shadow-first (θ is learned from the pooled stream); increment B is our first follow-up
need, with measured per-channel error rates as its evidence.

### 4.2 Acts

One writable name `act`, grid `[abstain, gather, ask, respond_1..respond_K]` (grid
order normative, abstain first = wait, ties first-listed — unchanged wire rules).
K-dependent grid size is per-episode data, consistent with K-at-tick-0. Acts are
already value-indexed natively on this wire (a name's grid points price log2|grid|).

### 4.3 Utility (expressible in the landed grammar)

With `RB` = the grid value of `respond_1` and outcome `y = ["var",1]`:

```
u(act) = if act < RB:   the existing abstain/gather/ask rows (constant / info-priced)
         else:          if (= y (− (get act) (c RB−1))) then u_correct else u_wrong
```

one `if (= y ⟨act's own candidate code⟩)` arm — well inside even the pre-W4 subset;
W4's ÷, log, and exp are available if a later utility wants them. The abstain row can now
distinguish y=0 (correct abstention) if the owner's utility wants it (a u_bar question,
deferred; gauge today says u_abstain regardless). `cgrid` is omitted at first
(byte-identical pre-W4 pricing); adopting it later is additive.

Note the outcome semantics honestly: `["var",1]` is the **predictive next observation**,
not a latent truth — "respond_j is correct" is proxied by "the channel would next
report j." With the θ ceiling at 0.9 on the wire, max attainable P(next = j) is
grid-bounded; whether respond_j clears its whole-menu bar under this proxy is an
**empirical question the shadow answers first** (the same discipline as register §7,
which is exactly why staging is shadow-first).

### 4.4 What dissolves

- `p_none` as a daemon output (engine-held null mass replaces it) — M4. Until a
  per-code readout lands, the *host-visible* p_none for rendering stays daemon-side —
  a named observability gap, not a decision-path one (the engine decides).
- The host-MAP transitional rule in `membrane/coarse.py` (`respond → argmax credence`)
  — M5: the engine's chosen `respond_j` carries the value.
- The `leader-credence` / `p-none` indicator buckets (the posterior they summarize
  becomes engine-native; features shrink to the genuinely contextual: era-split,
  owner-scoped, n-obs, grow-pass).

## 5. The decisions the conferral must settle

**5.1 Adopt the two-layer learning split?** Proposal: per-question posteriors from that
question's own code-valued observations; owner verdicts calibrate the *shared* channel
concentration (and, at increment B, per-channel fidelities) carried across questions
via the warm boot. This is the central architectural choice — it decides what the
evidence stream means, what warm-boot persists (channel counts, not tick replay), and
it is what makes verdict-starved p1 stop binding. Alternative: keep pooled
cross-question learning (status quo shape, K-ary-ified) — rejected in draft because it
reproduces the starvation (§2.5).

**5.2 Session-per-question.** OB-11 confirms K-at-tick-0 as the sanctioned shape ⇒ one
handshake per question (the E2 probe: ~420ms fresh session, ~50ms marginal tick —
viable now; replay grows ~26ms/verdict ⇒ **warm-counts file is a needed companion**,
already a B4 need-note). This *dissolves* E2's rider problem (per-question act sets
arrive for free) rather than requiring a rider change. Confirm this composition.

**5.3 The bad-verdict exclusion (§4.1) until OB-12** — accept, or push evidence for
increment B now? Draft position: accept the exclusion, but **send the demand evidence
immediately** (§5.4): our two channels have measurably different error rates, which is
the increment's own stated gate.

**5.4 What we send to `gfrmin/proplang`** (ruling 3; W3 shipped, so this is follow-up
evidence, not a feature ask): (a) on the K-ary issue (#9, closed): a consumer
conformance report once our shadow world speaks `obs_arity` live; (b) on OB-12's issue:
the measured per-channel error-rate evidence (extraction vs owner-verdict) as the
demand its ruling waits for; (c) on OB-11's issue (#10): K-at-tick-0 suffices for us
given 5.2 — the bounded-reserved-tail option is not needed on our account; (d) a **new
small issue: observability-only per-code posterior readout** (or argmax code + null
mass) — decide-reply telemetry, no decision-path semantics; our honest-rendering and
report-pricing need. (e) R-D23 heir: our 73.5% over-abstention corpus as the
NONE-dominant demand, when the shadow shows the cap binding in practice. PII:
aggregates and synthetic examples only, throughout.

**5.5 Staging.** E1 does not land as one flip. Proposed ladder, each eval-gated:
**(0) rebuild + redeploy the engine binary from HEAD** — lawful upgrade, our current
binary world is byte-compatible (verify: same handshake, same smoke) — then
**(1) shadow-first**: a categorical world (`obs_arity = K+1`, session-per-question)
mirrors beside the binary said@1 world on the same decide stream, no decision path;
its ledger measures whether respond_j clears its bar under the θ ceiling (§4.3) →
**(2) M4**: engine conditions on raw per-candidate observations; daemon posterior
retired; `:8799` down → **(3) M5**: value-indexed respond live; `coarse.py`'s
transitional rules retire on schedule. The binary world's verdict ledger stays as the
calibration corpus for channel priors — it is not replayed as ticks.

**5.6 Risk register for the conferral**: (i) the θ ceiling may cap P(next=j) below
respond_j's whole-menu bar — measured at stage 1 before anything depends on it;
(ii) R-D23's null cap may misfit unanswerable questions — same measurement, and the
evidence feeds its declared heir; (iii) one shared θ conflates channels until OB-12 —
named, evidenced, accepted for the shadow.

## 6. What this doc is not

Not a build plan (that follows conferral; stage 0–1 are buildable immediately after),
not a proplang feature request (W3 shipped; our sends are evidence + one
observability-only readout issue), and not a commitment to numbers (channel priors,
K caps, readout names are all post-conferral detail).

---

## 7. Re-grounded 2026-09-03 against proplang HEAD `94fd4eb` (arm B) + Arc C `r43`–`r46`

**What this section is.** The third dated re-ground, in the doc's own convention (§0 is
2026-07-20 against arm A `1a0cea7`). **Everything above is preserved verbatim** as the
owner-approved 2026-07-21 record — this section states what has moved under it, never edits
it. The doc was stranded on `feat/e1-design` while `docs/membrane-shadow.md` §15 named it the
governing design, so the link was broken on master; salvaging it is `GD-23`. Nothing here is a
build order: `r47` (the enablement) and `r48` (the re-earn measurement) each carry their own
pre-registration (`M-3`).

### 7.1 The dependency sweep — six of the eight named issues have closed

Read live 2026-09-03 (`gh issue view`, read-only; the proplang repo is never edited from here).
**§3's "not landed — and binding on our design" list is materially stale**, and three of its
four items moved:

| issue | doc's premise (2026-07-20) | state 2026-09-03 |
|---|---|---|
| **#20** per-code readout | "no per-code posterior, no argmax code, no P(y=0)" — §5.4(d)'s ask, §4.4's named observability gap | **CLOSED / shipped** (`readout-freeze-r0/r1`; ledger row `OB-25` LANDED) |
| **#21** R-D23 null-mass cap | "capped at 1/(K−1) … the two-parameter family is its demand-gated heir" | **CLOSED** at the `OB-19` heir boundary — the minority-cell tie **breaks** via declared `breadth` pairs |
| **#19** θ ceiling / refine lattice | "the θ/p1 grid ceiling 0.9 still stands on the wire"; R1 engine-internal | **CLOSED** — but the ceiling **changed owner rather than dissolving**: θ is REQUIRED hello data priced by mention mass, **finiteness remains**, and the frontier door is deferred + demand-gated |
| **#11** OB-12 per-sensor reliability | "still RULING-PENDING … increment B is our first follow-up need" | **CLOSED, `OB-12` DISCHARGED — and increment B stays OUT**, underpowered *by measurement* (`n_inv = 0`) |
| **#15** act-conditional outcome hypotheses | §16's named exit for the gather binder | **OPEN** |
| **#24** un-defer `OB-24` | our own demand (`GD-14`) | **OPEN** |
| **#10** mid-episode K growth (`OB-11`) | "still RULING-PENDING → K fixed per episode, published at tick 0"; §5.4(c): the bounded-reserved-tail option "is not needed on our account" | **CLOSED — ruled bounded, option 3**: K at tick 0 **with a reserved unallocated tail**, priced from tick 0 |
| #9 K-ary observations | already reflected in §3 | CLOSED 2026-07-22 (unchanged) |

Two of these closes carry a rider the table cannot hold:

- **#11 names the only thing that can re-open increment B, and we half-hold it.** The close
  states B "cannot be powered by running the shadow longer" — there is no passive verdict
  stream, so powering it "requires first deploying a second verdict source (an LLM-judge or
  reviewer channel), *which is exactly the evidence shape B itself would model*." That channel
  is **built here and dormant**: `core/claude_verdicts.py` (membrane-shadow §17) holds **180
  verdicts, none written since 2026-07-22** (checked 2026-09-03). So the supply exists as code
  and as one fold, **not as a running stream** — re-opening B means restarting it and pricing
  the deliberation, not pointing at the file. §4.1's bad-verdict exclusion **stands** (B is
  out, by the counterparty's measurement); what changed is that the re-opener is named, and the
  demand would be ours to file rather than theirs to derive (`M-23`, and `GD-14`'s rider: a
  deferral is a judgement about demand).
- **#19 moved the ceiling to us, and the number is not the doc's.** Because θ is now world
  data, the grid is our declaration — `world.theta_grid`, r44's one rule, which r46 leg D
  measured **K-independent** (`GD-22`), so the categorical world binds the same object. Read
  under the deployed boot Ū on 2026-09-03: **8 rungs, top rung 0.990634** — not the doc's
  engine-frozen 0.9, and not the 0.95 endpoint (the top rung is an argmax crossing).

### 7.2 What Arc C adds that the doc could not know

- **The four-item enablement spec** (`r46` leg D, `GD-22`): a categorical world at HEAD must
  carry (1) `codebooks.theta` = `theta_grid`, unchanged; (2) a **clock** row; (3) a
  **menu-bearing** tick; (4) **full indicator coverage** on every tick. Items 2–4 are new
  constraints on §4's declaration; item 1 is #19's consequence.
- **Without a clock the world is inert** (`r43` / `OB-24` / `#24`): `chooseEU` compares two
  beliefs under one common utility row, so per-action **levels never enter** and selection
  returns the menu head. §4.2's act grid is necessary and **not sufficient**.
- **`act` is written XOR observed** (`r45`): it cannot be both a menu name and a tick
  feature. `r46` leg C then measured that act-conditioning is nonetheless real and choosable
  via a **mirrored non-writable guard** — and **inert for the commit ceiling** (`GD-21`).
  That is live evidence bearing on **#15**, which remains the named exit for §16 finding 3.
- **One evidence-tick declaration** (`r45`): `session.evidence_tick_body`. `cat_features`'s
  "dormancy is free" is **false at HEAD** — arm B refuses a dormant-omitting tick.
- **The bar has drifted** (`r32`, confirmed `GD-21`): the deployed vs-abstain bar reads
  **0.836894** (u_wrong −5.13099), so every bar figure in §2/§4.3/§5.6 above (0.856, 0.899,
  0.994) is **era-stamped, not current**. §17.6's rule is untouched — the fix is a sharper
  `p1`, never a softer bar — but any arithmetic re-run must use the Ū of its own day
  (§17.6's whole finding).

### 7.3 What stands unchanged

§5.1 (the two-layer learning split), §5.2 (session-per-question — unaffected by #10's
ruling, though the sanctioned shape is now K-at-tick-0 **plus a reserved tail** and every atom
mention prices against the declared breadth *including reservations*, so declaring a tail is a
cost from tick 0 and §5.4(c)'s "not needed on our account" was not the ruling taken), §5.3
(the bad-verdict exclusion — now standing on #11's *measurement* rather than on a pending
ruling), §5.5's shadow-first staging, and §6 (this is not a build plan).
Stages 0–1 remain LANDED (membrane-shadow §15/§16); `src/life_agent/membrane/categorical.py`
is in tree, env-gated OFF and byte-inert by default, and nothing in this section deploys it.

### 7.4 What this re-ground does NOT settle

**Whether §16 finding 3's binder still binds.** Finding 3 held that the
myopic-perfect-information gather row makes `respond_j` unreachable *by construction*
(crossing `p_j > 0.9942` at that era's Ū, against a 0.9 ceiling). Two of its three terms have
moved — the ceiling is now our 0.990634 top rung, and the Ū is a different one — while
`r45`'s C3 measured the gather pathology **standing** in the binary world at v2 (`gather` the
argmax across 96–98% of the credence range under both the declared and deployed Ū). The
remaining gap is small enough that it must be **measured, not inferred**: recomputing the
categorical crossing needs the engine, under the deployed Ū, which is `r48`'s job. Nothing
here concludes it, in either direction.

Also open for `r48`: §16 finding 4's cost (session-per-question ran minute-scale at K≳10, a
K-cap or episode budget owed **before** any live enablement), and #20's now-landed readout,
which makes §16 finding 5 (R-D23 cap-binding, previously unobservable) readable for the first
time. `GD-16`'s rider is inherited: an enabled categorical world re-reads before its first
backfill.
