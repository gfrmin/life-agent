# Conferral — does the A3 gate keep its blind regime, and what earns the next §18 rung (2026-09-05)

Two questions in `RULINGS.md` §5's class, put to the owner **by interview** (`M-17`'s form:
`AskUserQuestion`, priced options, a recommendation first) on 2026-09-05, after `r50` closed B on
its own KILL (`GD-28`). Evidence and prices were already in tree — `r49b` §5 for the first
question, `r50` §3/§6 for the second — so this document records the options as put, the rulings
as given, and what was enacted. Everything here is **$0**.

**Why these reach the owner at all.** The first is a question about what the instrument is
*for*: scoring a policy under a utility conditioned on verdicts about that policy's own decisions
is circular; scoring it under a utility the system does not hold is a second master. `r49b`
showed the owner's consistency rule and the gate's anti-circularity guard select opposite
regimes and opposite signs for `r49`, so only one can hold — that is the objective, not
evidence. The second is `RULINGS` §5's own clause: *"the same applies when the ruled queue
empties and the question is what to build next."*

---

## 1. Question one — does the A3 gate keep its blind regime?

**Evidence** (`r49b` §3–§5, unchanged): `frozen-elicitations` structurally refuses the §4.4
verdict→evidence projection; `all-to-date` folds it. No stale side-store exists — the deployed
boot Ū is a live snapshot. It tracks non-monotonically (−5.94 → −8.83 → −5.13 across 20 boot
records; within 0.002 of the gate's in August). The labels are reversed: −9.0 is the
elicitation-only number, −5.131 the reaction-conditioned one, so "the current posterior mean" is
the **softer** bar. Implemented literally, "one utility everywhere" scores the gate at 0.837,
flips `r49`'s headline sign (−0.080 → +0.075) and deletes the anti-circularity guard.

**Options as put** (all $0, none needing a measurement):

| option | what changes | price |
|---|---|---|
| **Guard stands, made honest** (recommended) | Gate stays blind. `core/gate.py` gains an **INCONCLUSIVE** verdict when the measured marginal reach falls strictly between the two break-evens (r49's exact case: 0.875 between 0.837 and 0.900); PASS/FAIL quoted only when the reach is on one side. `r49` takes a dated note, record untouched (`M-4`). | one small PR, no run; the only option that changes what `r49` was entitled to conclude |
| Guard stands, scoped to deciders | "One utility" binds every *decider*; the gate exempt by declaration. §5's live entry closes; `M-31`'s two-regime disclosure permanent; `r49`'s FAIL stands as a FAIL. | docs-only |
| Guard falls, gate reads `all-to-date` | One number everywhere — but the gate grades a policy with a yardstick that policy's own outcomes moved. Runs 6–23 and `r49` non-comparable (`M-18`); `r49` not re-read (`M-4`). | one PR; every prior reading re-labelled |

## 2. Question two — with B closed, what earns the next §18 iteration?

**Evidence** (`r50` §3/§6, plus one count taken for this interview): no frozen family separates
the 70–90 band (BF 0.229 / 0.253 / 0.212 vs 10); the split needs ≈385 band rows against 55;
owner verdicts add ≈7 a month; the Claude verdict channel is dormant since 2026-07-22. The
recorded pool holds **245 distinct questions, 141 already verdicted, 104 not** (all live-origin,
none from the eval corpus) — so a Claude re-supply is bounded today at ≈104 verdicts, ≈23 band
rows at the band's 22% share, against the ≈330 more the split needs. `r49` S4's held-out `p1` is
pulled toward ≈0.86 in both directions (0.863/0.873 vs 0.800 in the band; 0.862 vs 1.000 in
≥90; 0.646 vs 0.696 below 0.5): the shape of a pooled guard prior.

**Options as put** (multi-select; each would get its own pre-registration):

| option | what it is | price |
|---|---|---|
| **File the pooled-prior demand on proplang** (recommended) | The engine-side hypothesis with `r49` S4 attached, filed as demand (`M-23`/`GD-14`), never edited here. | $0; nothing to build; the counterparty's clock |
| Re-supply the Claude verdict channel | Deliberated verdicts by this agent (2026-07-22 ruling; engine evidence only, never P(U)). Cannot reach BF 10 on the existing pool; shortens the future clock. §4.4 rules re-read first. | $0 API; session time per verdict |
| C's spend re-record | `arm_baseline` over the 104 gate questions, priced, `M-18` rider; Δ_spend measured instead of structurally 0. | single dollars |
| Hold §18; K-cap and §11's exit | No §18 iteration until verdicts accrue; work moves to k ≤ 3 and §11's exit criteria. | $0 |

---

## RULING (owner, 2026-09-05, interviewed)

1. **The guard STANDS and is made honest.** The A3 gate keeps `frozen-elicitations` — the
   anti-circularity guard — and "one utility" binds every *decider*, the gate exempt by
   declaration. The gate publishes both break-evens beside the measured marginal reach and quotes
   **INCONCLUSIVE**, neither PASS nor FAIL, when the reach falls strictly between them.
   INCONCLUSIVE adopts nothing and does not advance the consecutive-FAIL stop rule; its remedy is
   evidence — a sharper `p1`, or the two estimates of `u_wrong` converging — never a softer bar
   (§17.6, `M-4`). `r49`'s record stands as quoted, with a dated note. → `RULINGS` **`M-34`**.
2. **The next §18 rung is the engine-side demand.** The pooled-prior hypothesis is filed on
   proplang with `r49` S4's evidence (**proplang#26**). Offered and **not chosen**: re-supplying
   the Claude verdict channel, C's baseline-spend re-record, and holding §18 for the K-cap /
   §11's exit — each stays named, none opens. → `RULINGS` **`A-11`**.

`RULINGS` §5 has nothing live after this ruling.

## What was enacted (same commit — `GD-29` has the detail)

- `core/gate.py`: the closed verdict vocabulary (`VERDICTS`), `verdict()`, the ONE
  `marginal_commits` table (the harness binds it), and `render_report` **requiring** the pairing
  (r28: a default is the vector) — publishing both break-evens, the reach, and why INCONCLUSIVE is
  not a FAIL. `scripts/membrane/p3_gate.py` quotes the gate's verdict in its log, record and
  report; `scripts/run_eval.py` declares the pairing the classic gate spans (the typed arm decides
  under the live `all-to-date` Ū); `scripts/gate_splice.py` declares none and its report says so.
- `r49` §S5 dated note; `r49b` §5 annotated; `GD-27`/`GD-28` Reactions filled; ROADMAP 3h and
  CLAUDE.md carry the rulings.
- proplang#26 filed (demand, with evidence; no edit to proplang).
- Nothing re-read, nothing deployed, `M-1` not engaged.
