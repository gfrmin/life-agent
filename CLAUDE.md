# CLAUDE.md — operating manual for `life-agent`

You are an agent working in `.`, the composition root of a personal life-management
assistant. **Read [`PRINCIPLES.md`](./PRINCIPLES.md) first** — it is the single source of the
philosophy (the kernel, the derive/act boundary, resolved and open decisions); this file is
only the operating manual. Then [`docs/system-design.md`](./docs/system-design.md) — the
adopted whole-system design (one DAG; everything is an edge on it; act ledgers project back
into knowledge) — then [`ROADMAP.md`](./ROADMAP.md) for the plan and
[`GETTING_STARTED.md`](./GETTING_STARTED.md) for the immediate tasks. The owner is a strong
engineer (builds Julia DSLs, TS, Python data platforms) — be precise, terse, and don't
over-build (PRINCIPLES §4: compose, don't rebuild).

## What exists (present tense, no aspiration)

Two in-tree Python packages — `pkm` (the KB: derive) and `life_agent` (the agent: decide) — in
a **derive → project → reach** shape (PRINCIPLES §6):

- **derive (`src/pkm`):** sources → primary artifacts → composable transforms → cited, cached,
  idempotent artifacts (SPEC §18.7 chaining; small auditable steps, never a mega-transform).
  `pkm derive` resolves one (input, transform-chain) target cache-first (SPEC §18.11) — a warm
  chain makes zero model calls — demand-logged under `logs/demand/`.
- **project (`src/life_agent/tasks/project.py`):** a thin immutable→mutable bridge — terminal
  `action_items` artifacts filed **once** into the GTD inbox with a `[src:email <id>]` citation.
- **reach (`src/life_agent/reach`):** Telegram as a dumb transport; "Jarvis" is just the persona.

The GTD is event-sourced: an append-only ledger is truth, the SQLite read-model is a fold of it
(PRINCIPLES §7; `docs/act-layer-events.md`). **email→GTD runs off a `systemd --user` timer**
(`bin/mail-to-tasks` is the timer/debug entrypoint): the `action_items` transform (haiku,
grounded quotes) auto-files cited tasks; the grounding gate is the safety; triage
happens in Telegram. The ask-anything read path is `scripts/ask.py`, dogfooded via
`bin/ask-live`; its temporal mode (`/recent`, `/since`, `/until`, `/derive` — one line
grammar, identical in the REPL and one-shot argv) filters by the `doc_date` projection
(SPEC §18.12) read-side, naming undated and not-yet-derived hits instead of dropping them.
Its subject mode (engine D2) owner-filters "my X" questions by the `doc_subject`
projection (SPEC §18.13) matched against the owner profile via cached model
verdicts (`life_agent.core.subject`; the profile never enters pkm) — determinate
non-owner and template hits are excluded by name, indeterminates kept and named.
**The GTD ledger projects into knowledge** (`tasks/knowledge.py` →
`$LIFE_AGENT_KB/tasks/state.md`, the mutable→knowledge mirror of `project.py`): the ask
path re-projects + re-ingests it demand-led when the ledger head moves (announced, never
silent), and pkm's path-currency rule (SPEC §15.4) keeps only the newest version
retrievable — so "what's next on my gtd list?" is an ordinary cited `QUESTION`.
Every human-facing surface is governed by
[`docs/interaction-contract.md`](./docs/interaction-contract.md) — read it before touching
a command, intent, flag, or reply string.

**Adopted, being built (Phase 1.6):** the derivation framework —
[`docs/system-design.md`](./docs/system-design.md) +
[`docs/derivation-engine-design.md`](./docs/derivation-engine-design.md) (D0–D2 and the
GTD ledger's knowledge projection + pkm path-currency landed) — and, adopted 2026-06-12,
the **Bayesian foundations**
([`docs/bayesian-foundations.md`](./docs/bayesian-foundations.md)): Ask re-derived as
inference (answers = claim sets with posteriors; responses = EU decisions; calibration
measured). Ask v0 slices 0–3 are landed: the outcomes + decision logs accrue under
`$LIFE_AGENT_KB/calibration/`; `core/brain.py` is the credence skin seam; the **utility
posterior** (`core/utility.py` — utility is a learned belief about the owner, §4.4/§10
as amended: one utility, the agent has none of its own); the **lookup family**
(`core/lookup.py` — §4 with §4.1 covariates); and **narrative subsumption**
(`core/narrative.py` — §7: synthesize is a proposal distribution; claims audited into
cells, population-calibrated per-cell from the eval_claim stream, per-claim EU inclusion
under Ū, the proposal-coverage tail named); and the **§8 decision-weighted adoption
gate** (`core/gate.py`, `run_eval --gate` → `$LIFE_AGENT_KB/eval/gate/`: a posterior
over Δ = EU(typed) − EU(monolithic) by MC over P(U) × the Bayesian bootstrap, P(Δ>δ)≥
level with δ/level frozen blind; the disagreement region + answer rates published). Six
runs so far (§14 ledger has each): the executor series read 0.002 → 0.010 → 0.065 →
0.092 → 0.098, then **run 6 (2026-08-17: judge-graded arms, λ_usd spend on both arms,
the post-Ollama cloud instruments): FAIL at P(Δ>0.05)=0.678, Δ̄=+0.180 [−0.244, +0.661]
— the first positive mean;** typed answer rate 0.47 (47 ✓ / 2 ✗) vs monolithic 0.97,
withholdings split miss 18 · dispersed 37 (the reach lever's first *direction*). The
run-5 attribution counterfactual (`scripts/gate_splice.py`, same day, not a reading)
settled what carried the sign: run 5's cautious typed arm, judge-graded and priced, reads
**0.905 / +0.343** — grading + spend did it; the new instrument's live arm gave back
Δ̄ −0.163 (corrects +0.192, two wrongs −0.173, spend −0.183). Audited the same day:
q2-053 was a stale gold (superseded in-corpus; corrected, disclosed), q2-105 a cached
opus coin-flip at 0.93 whose stale CORRECT curve rows the append-only regrade
(`scripts/regrade_edge_rows.py`) now supersedes; and run 6's nine cold deliberates
($10.87) never reached the corpus — the pkm MCP server failed to register (PKM_CONFIG
unset in the launcher) and blind declines were cached as evidence (voided; guarded at
`deliberate.answer`, the bridge cfg, and the gate preflight). **Run 7 (same day,
`gate-20260817T160244`: the run-6 recipe with a working deliberate, corrected golds,
regraded curves) — the series' first PASS: P(Δ>0.05)=0.945, Δ̄=+0.429 [+0.040,
+0.884]**, typed 50 ✓ / 1 ✗ / 53 withheld (miss 18 · dispersed 35) at $5.56 vs mono
0.97 at $39.01. **Run 8 (router v2,
`gate-20260817T164427`): FAIL 0.857, Δ̄ +0.344 [−0.109, +0.841]** — the router worked
(16 newly admitted: 6 ✓ / 10 dispersed / 0 wrong; miss 18→2; answer rate 0.57; $3.25)
but two curve-evolution wrong-leader commits on multi-value chunks (q2-053, q2-090)
pulled it back under. **Run 9 (the competing-values temper, `gate-20260817T195737`):
PASS 0.938, Δ̄ +0.390 [+0.032, +0.841] — zero wrong commits** (35 ✓ / 0 ✗ / 69 withheld,
answer rate 0.34, $4.10): a same-shape competitor in the extractor's quote window halves
the observation's r on both commit sites (`matching.quote_scoped_competitors` →
`competition_factor`, join channel inherits it — §2 lineage), registered blind off-gate
(`scripts/temper_audit.py`, counterfactual floor 0.945/+0.401 — the live run matched it
almost exactly and the sweep predicted the assert set perfectly). The wrong-commit class
was closed at the price of reach — and **reopened by run 10
(`gate-20260821T094545`): FAIL 0.861, Δ̄ +0.323 [−0.074, +0.787], 36 ✓ / 1 ✗ / 67
withheld** at $3.28. The failure is one row: spliced with that row withheld the same
run reads 0.952 / +0.410 — PASS, stronger than run 9. But it is **not an attributable
reading**: four decision-path changes were in the tree (the pre-registered null-read
fail-open, R2's declared retrieval order, §6.9's probe order, tranche-2 M1's executor
deletion) and three are invisible to the 7.2 oracle by construction. The named risk of
the null-read fail-open was the first suspect and was **refuted**. An isolation ladder
settled it: **run 11** (−fail-open) FAIL 0.880, same single wrong row → the fail-open is
**exonerated** and stays; **run 12** (−§6.9's declared probe order) **PASS 0.964, Δ̄
+0.434, 0 wrong — the best reading in the series and the first PASS on the priced lane**,
so §6.9's key is **convicted** as what moved the commit. It did not create the wrong
leader (the same competitor leads in runs 10–12); it concentrated the posterior enough to
carry an already-wrong leader over the bar. **§6.9 is NOT reverted** — pre-registered
before the run: the old order is nondeterministic, a luckier ticket rather than a better
rule, so master knowingly carries the wrong commit. **Do not deploy this arc** (it is not
deployed now) — the block is KEPT and, by owner ruling 2026-08-22, **re-pointed at the
replace branch (§6.12)**: the carrier-identity checkpoint ran and refuted the block's
original premise (below), but the tree still commits that row wrongly, which is what the
block was for. It closes when r06 reads and the row is fixed or priced. Also
found: **runs 7–9 all fired the LEGACY cascade lane** (the arm's flag defaulted off; each
run's `env_flags` records it), so run 10 was the first gate run ever on the priced lane
and M1's deletion switched the arm's lane rather than removing dead code from its path.
Registered: **§6.10 — a gate run must pin its tree, not just its recipe** (built, tiered,
used live in runs 11–12).
**§13 adoption RESOLVED (2026-08-17, on runs 7+9):
typed is the silent default, honest-withhold-only (the uncalibrated fallback lane is
REMOVED — `LIFE_AGENT_FALLBACK_LANE` is ignored), and the deliberate edge is ON by
default (`LIFE_AGENT_DELIBERATE=0` is the rollback)** — §14's adoption entry has the
evidence and rejected alternatives. The reach audit (`scripts/reach_audit.py`, $0)
priced the levers and pointed at independent-document corroboration (ceiling 40/69) —
**built (2026-08-18: `lookup.confirm_hits`, the `/probe/confirm` bridge endpoint,
`scripts/corroborate_audit.py`) and then REFUSED by its own frozen criteria: NO-GO
at 3 predicted rescues (< 5) with 1 wrong-rescue flip (q2-019, a truncated-leader
superset-confirm — the named defect class).** The 40-ceiling was carrier-count
inflation: 48/63 grounded confirms were forwarded/quoted copies of one attestation,
killed by the §5 dedup guard; true independent-corroboration ceiling ~6, under the
"not worth building pre-dogfood" line — the instrument + endpoint stay in-tree,
tested and dormant (nothing on the decision path calls them; no menu row).
**The n_obs=0 cluster is DECISION-side (`scripts/extraction_audit.py`, 2026-08-18,
$0): not retrieval (ceiling 0), not extraction (delivered reach 4) — 17 of the 19
rows carry candidates with n_obs=0 at EXACTLY uniform credences, i.e. a grounded
channel a replace-branch probe erased, with the gold already on the lattice in 14.
"retrieved-not-extracted" is retired as the cluster's name (wrong twice now); the
suspected over-strong inference is that a NULL re-read is treated as a
DISAGREEMENT (fail-open precedent one branch away), registered in §14 as NOT yet
measured — it needs its own frozen criteria + pre-registration.**
**The carrier-identity checkpoint is READ (r04 RULING 4 → `docs/unification/reports/r05-carrier-identity.md`,
register §6.11, instrument `scripts/carrier_audit.py`, criteria frozen in its docstring
before it ran, $0).** Two surfaces on run 10's tree: the cheap first pass and the
corroborate probe. **BUILD on exposure (17 load-bearing questions on each, ≥ the frozen 5)
with delivered reach 0, so no gate run bought — and the pre-registered fix REFUTED as a
provable no-op:** carriers of byte-identical text never differ in authority class, subject
state or date-projection status here, so argmax-covariate always returns what the declared
key already picked. What is arbitrary is the **grouping** (q2-059: the gold leads in every
arm, the deployed assignment hedges at 0.683, a max-independence assignment reports at
0.975 — and the mirror case lowers a gold), and on the probe surface **37 of 37 straddles
fall on the conservative side**, so the declared key's *consistency* is doing real work and
any fix must preserve it. **The redirection is the result that matters: run 10's wrong
commit is NOT carrier identity.** The base channel on that row carries 5 grounded
observations over 4 documents with the gold alone at 0.985, invariant under every carrier
permutation; the run's own decision row shows the committing view was
`instrument: deliberate@<opus>` with **n_obs = 1** and the gold demoted to 0.033, and the
recorded wire agrees that the competitor appears only after the gather steps. So the wrong
*leader* comes from a **replace branch discarding a grounded channel** — the same class as
the n_obs=0 cluster above, here at n_obs=1. This does not overturn run 12 (§6.9's key
remains the *marginal* cause of the commit); it names what the ladder could not. The audit
found **four defects in itself**, three in its measures — one found after the first reading,
flipping surface (a) NO-GO → BUILD, disclosed in r05's chronology with both quantities
published. **Rulings taken 2026-08-22 (r05's RULINGS section has all four):** the
deployment block is kept and re-pointed at §6.12; §6.11's BUILD licenses
**known-and-uncovered, not a fix** (the grouping bound in both directions and the 37/37
cross-surface conservatism are what the entry now stands for; `scripts/carrier_audit.py`
stays in-tree, tested and dormant); **M1 is ACCEPTED and its checkpoint closed** (run 12
carried the deletion and read 0.964 with zero wrong commits, so the hold had no live
hypothesis left — **M1.5, the coverage census, is unblocked**); and r06 is scoped to every
replace/override site rather than to one hypothesis.
**r06 IS OPEN (`docs/unification/reports/r06-replace-branch.md`, register §6.12, instrument
`scripts/replace_audit.py`, criteria frozen and committed BEFORE it reads).** §6.12
enumerates five replace sites from `core/executor.py` and names the asymmetry that makes
them readable: the corroborate tiers and in-loop `re_extract_strong` retire fail-open on a
null read; **the `deliberate` edge has no null-read guard at all** and collapses the channel
on an empty ok reply by design. The counterfactual is RETIRE-NOT-REPLACE (a deployable rule,
not an invented one), read at $0 off the run's own decision + attributed-edge records, with
the deployed arm READ rather than re-derived. Every mirror of the decision path is imported
from it, and every load-bearing predicate was verified RED by mutation before the read —
r05's lesson applied.
**r06 IS READ (2026-08-22, $0, 102 questions):** exposure S3 68 · S1 26 · S4/S5 12 · S2
unreadable; 59 grounded observations discarded over 27 questions; delivered reach 23 of the 73
questions where a site fired (12 repairs · 11 regressions). Criterion 8 reads **BUILD+PRICE on
S1, S3, S4 and S5** — and the instrument's own control contradicts it: on 29 questions NO site
fired, so retire-not-replace is provably a no-op, yet the arms differ on 8. **Noise floor 28%**,
against which S1 delivers +3.8 rows of excess, S4/S5 +0.7, and **S3 just +0.2 — nothing
distinguishable from the layer gap.** The criterion is left standing as frozen with the bound
published beside it; no run was bought. **The blocking row IS repaired** (deployed reports at
n_obs=1 on the competitor, the counterfactual at n_obs=5 over 4 documents on the gold) but four
sites fired on it and the records carry no ordering, so the attribution is unavailable.
**Criterion 7 retires a standing suspicion:** the S3-collapse signature fires once and a
cross-run dedup explains it — zero genuine null-read collapses, so the empty-ok collapse is
**not** what produced the n_obs=0 cluster, and the S1/S4-vs-S3 asymmetry is structural-only
here. The instrument shipped three defects in its measures and one in an interpretation, all
caught before a verdict and all published. **Registered en route: §6.13 — a declared total
order cannot restore determinism when the tie block is larger than the over-fetch window; the
window itself is the sampler** (found by r06's idempotency double-run: 1 of 104 questions
returns five different top-20s in five calls, 73 of its 80 over-fetched rows sharing one
quantised score; invisible to 7.2 and to a gate run alike).
**r07 IS READ (the recorded replay, `docs/unification/reports/r07-recorded-replay.md`,
instrument `scripts/replay_audit.py`, ten criteria frozen and committed before it read; pass 1
2026-08-22 three arms 67/104, pass 2 2026-08-23 deployed-only 73/104, $0):** fidelity 66/67
and 72/73 with the SAME divergent row both times, control 9/9 — **r06's 28% floor was its
decide-layer stand-in, not the evidence** (r06's 8 disagreeing control rows replay 7/7 with
the record). Attribution from the payload: **S1 ×10 + S2 ×2 confirmed** across the mandated
double run (7 S2 rows withheld as draw-unstable); **S3/S4/S5 discard nothing anywhere**; a
grounded channel was zeroed on 7 questions (S1 on 6, S3 on 1), and on the blocking row S1
zeroes the five-observation base before the deliberate edge re-mints the one-observation
competitor — stable across the double run. **The harm rides the DISAGREE path, which
retire-not-replace cannot see by construction: the enacted RETIRE arm reads 0 repairs / 1
regression while the JOIN upper bound reads 10 repairs / 2 regressions** — so §6.12's live
successor question is a correlation key on the wire (making a §5-deduped JOIN readable),
decision-path code needing its own frozen pre-registration. Every site KNOWN-AND-UNCOVERED
under the frozen bar (floor 0%); **nothing bought**; r06's criterion 8 untouched. En route:
**§6.13 re-measured at commit granularity** (across three draws, 14 of 104 questions wobble
in committed n_obs, 22 flap between readable and cold — a standing noise floor under every
gate reading) and the **§18.9 warm-through** (a $0 replay records composed derivations into
the live store — write-once and key-deterministic so undamaged, but coldness is
pass-order-dependent). Five further deviations disclosed in the report, including the volume
failure that interrupted pass 2 mid-read. Single-doc 12 is
the temper's standing price.
**Rulings 2026-08-23 (owner, interviewed — r07's RULINGS section):** the
JOIN-with-a-correlation-key fix **OPENS as r09**, pulled forward to immediately after M1.5
(E-7 at M6 becomes verify-only; the m0-5 baseline is re-recorded and O2 re-prepared after it
lands); **§6.13 is repaired first as r08** (own pre-registration, $0 multi-draw verification)
so run 13's Δ is attributable to the JOIN alone; **run 13's outcome branches are frozen at
full delegation** — PASS (the gate's frozen δ/level ∧ the blocking row repaired ∧ zero new
wrong commits) closes the §6.12 block and deploys master to live without a further keypress;
FAIL on any conjunct reverts the JOIN from the deploy path and STOPS for a ruling. The cap
stands: r07 was the last pure-diagnosis checkpoint — anomalies en route are disclosure items,
never a new diagnostic arc. Sequencing: **r08 → M1.5 → r09 → run 13**.
**r08 IS READ — §6.13 REPAIRED (2026-08-23/24,
`docs/unification/reports/r08-window-determinism.md`, $0):** fix (b) frozen blind and landed
under TDD (`src/pkm/retrieval.py`, SPEC 0.18.2 — the declared total order goes into the SQL
before `LIMIT`, so the engine cuts a declared prefix, never a sample). Baseline reproduced
and decomposed the defect (window layer order-unstable 75/74/75, set-unstable 15/14/28 per
surface; decision layer stable 103/104 with the witness the sole exception); post-fix **zero
draw-unstable questions everywhere at both layers**; blast radius **one question at one
surface** (the witness at base — §5 dedup absorbs the other 16 straddles); three replay
draws: action wobble 0, firing-order wobble 0, n_obs wobble 2 with
**retrieval-attributable component 0** — run 13's commit-wobble floor is 2, not 14, both
residue rows named (monotone accumulation, the §18.9 warm-through's signature). Predictions
2+4 confirmed, 3 refuted, 1 half, 5 an instructive containment-not-equality. Two deviations
disclosed: the C5 "instrument unmodified" clause contradicted the instrument's own §6.10 pin
on the fixed tree (resolved: `--acknowledge-src-drift` names the one expected tree, stamped
into every pin note), and the draws' render-stage 9(d) guard fired as in r07 (rows dumps are
the artefact of record). The 17/15/30 saturation census is the standing arbitrariness
record. **M1.5 IS DONE (2026-08-24, `docs/unification/reports/r05-collapse-m1-5.md`, $0, nothing moved):** 7.2 green on every set against post-r08 master (311/311 + 104/104 + 2/2); every declared class dispositioned; two of M0.5's three B-lookup absences closed free (warmed by the r07/r08 replays), q2-036 the named remainder — the fix's own footprint (its top-k changed, its new chunks never derived), closed by the post-r09 re-record; bridge-internal lanes each named with their actual oracle; the priced lane and seam path stamp neither regime nor policy (0/104 — M2's poster owns it). Also corrected: **O2 already ran and merged** (m0-5's manifest: 102 free + 209 priced, 2026-08-20) — the baseline of record is the merged m0-5. **r09 IS BUILT AND READ (2026-08-24,
`docs/unification/reports/r09-deduped-join.md`; pre-registration committed BEFORE any src
change):** the §5 dedup key (quote/doc_key/value_norm) rides every wire observation
(executor strips before decide — the brain stays string-blind); every S1/S3/S4/S5 probe
receives the standing channel and returns the §5-deduped JOIN (one rule:
`lookup.dedup_drop_rows`; groups doc-keyed). Disagree no longer erases; empty-ok no longer
collapses; null-guard kept; S2 untouched. Finding: the base arrives deduped + probe obs are
value-only ⇒ the JOIN is idempotent over the raw pool ⇒ **r07's 10/2 bound is run 13's
expected read, not a ceiling**. 7.2: non-probe fixtures byte-identical; 95 probe-firing
fixtures unservable (payload grew — the named class). Suite 2653, ruff, mypy green.
**Run 13 IS READ (2026-08-24, `gate-20260824T144002`): FAIL on two conjuncts —
0.895 < 0.90 and four new wrong commits — with the blocking row REPAIRED and the series'
best mean (Δ̄ +0.424, answer rate 0.71, $0.58).** All four wrong rows were run-10
dispersals (two are standing named classes: superset-confirm q2-019, warm-deliberate
q2-105) — the JOIN converts dispersals in both directions and dispersal was the
protection. **Ruling 4's FAIL branch enacted: the JOIN's code commits are REVERTED from
master (docs stay), the §6.12 block STANDS, the m0-5 re-record/O2 riders were sequenced
after the run and cost nothing, and work is STOPPED for an owner ruling** — re-open r09
with a temper for the named classes under a new pre-registration, or park the JOIN.
**The temper was re-opened and is now CLOSED: r09b → r09c → r09d, three sweep-gated
iterations (2026-08-24/25), each pre-registered before any `src/` change, each read on a
$0 replay of run 13's own record, each STOPPED on its own frozen consequence — total spend
$0, run 14 never fired.** What the wire settled, in order: the block is NOT synthesised
stacking (r09b: 0 of 4 wrong rows flipped), NOT covariate inflation (r09c: A2 fires exactly
as designed and the row never depended on it — its competitor is carried by two of three
genuinely distinct documents answering a file-scoped and a remainder-scoped question while
the question asks a class-scoped one), and NOT any decide-side rule that scores documents by
question-vocabulary overlap (r09d: three window/term variants moved the totals and left one
invariant set of five harmful rows, so the entity anchor is DONE by its own hard clause and
reverted). **The finding that constrains every successor: on the rows that matter the gold's
carrier is TERSE — a table row, a bare line — and the competitor's is DISCURSIVE.**
Surviving the arc: **D3, the S2 join** (the one replace site r09 left untouched now joins —
one correct commit recovered, none lost), parked unmerged pending a gate run (the parked
chain's head is `r10-entity-key` post-revert, tree-identical to the pre-E1 head). **Run 14 is
externally blocked: the Anthropic account hit its usage limit, access returns 2026-09-01.**
The blocked window was spent on $0 checkpoints: **r09e** read the tree of record on run 13's
record (66/104 readable under the §18.9 warm-through; two known-wrong rows still commit
wrong, one repaired to withheld, one cold — so run 14 on this tree would fail a zero-wrong
conjunct as-is, measured not predicted); the **entity-key conferral** took three rulings
(warm-then-read; the extract-side entity field RETIRES; E1's bar frozen at zero channel
harms AND ≥1 wrong-commit repair); and **r10 built E1 (exact typed identifier filter at the
base mint) and REFUSED it by its own frozen bar** — the sweep's marginal read is exactly one
row, the entity-qualifier row, wrong → correct (conjunct 2 met), but a channel-harm census
through the DEPLOYED rule found one gold-dropping *inversion* on a row the motivating census
had misread through its re-implemented carrier mapping, so E1 is reverted from the parked
tree. **The terse-carrier finding now closes the whole carrier-side family, exact or fuzzy,
hard or soft: a terse gold carrier omits qualifiers, so any carrier-side requirement damps
it.** The run-14 conferral (owner, 2026-08-25,
`docs/unification/conferrals/run14-conferral.md`) ruled option A at full delegation: fire on
the parked tree, conjunct 3 baselined on run 13's typed arm (a wrong commit is NEW iff the
row was not wrong there), cap raised. The ruled tail ran the same day. The warm pass fixed a
warm-instrument defect en route: the rerank lane is uncached with fail-open, so a refusing
replay takes the lexical branch wherever the deployed daemon's rerank moved the window — the
first warm minted the DEPLOYED trajectory's frontier, which the $0 lane never visits; the
priced pass became a hybrid (deployed client at every §18.9-recorded seam, refusal kept at
rerank/raw-llm), verified RED→GREEN. This also names the mechanism of r07's one persistently
fidelity-divergent row — disclosure, not a new arc. The $0 re-read on the warmed tree read
zero new wrong commits (both readable run-13 wrongs convert to withheld) and the refreshed
splice registered PASS 0.977 / Δ̄ +0.583 as the expectation. **Run 14
(`gate-20260825T102725`, 2026-08-25): PASS on all four frozen conjuncts — P(Δ>0.05)=0.907,
Δ̄ +0.421 [−0.046, +0.920]; the run-10 blocking row commits correct; zero NEW wrong commits
(the three wrongs are all run-13 rows: the two standing wrongs + the warm-deliberate row);
no named class worse (the superset-confirm row converts wrong → withheld).** Typed 60 ✓ +
2 ✓hedge / 3 ✗ / 39 withheld (miss 2 · dispersed 37) at $0.69 vs mono 0.97 at $39.01. The
live read sits under the registered expectation (0.907 vs 0.977); the gap is the
warm-deliberate row reporting wrong live where the warmed re-read had it withheld — a
run-13 row, carried not new; disclosed, not renegotiated. **Ruling 4's PASS branch is
ENACTED: the §6.12 deployment block is CLOSED, the parked tree is merged to master (src
tree-identical to `r10-entity-key` post-E1-revert), and master deploys to live
(`bin/ask-live` / jarvis).** The two standing wrongs ride in production, priced and
published. Hard clause carried
forward (owner ruling): **no lever ships while it makes a named wrong-commit class worse.**
Two standing lessons registered: a criterion naming specific rows can go unreadable between
two passes of the same instrument (14 in / 14 out), so name a class + a bar + the
cold-row consequence; and **a census must read the deployed rule end-to-end, never
re-implement the constant it prices** (four instances this arc — the fourth, r10's carrier
mapping, is the first to flip a verdict at a frozen bar; an earlier signature =
byte-identical numbers before and after a change).
**Stage 0 of the completion programme is DONE (2026-08-25): the collapse baseline is
re-recorded as `m2-base` (`docs/unification/reports/r11-baseline-rerecord.md` — one
single run on the deployed tree, 314/314 replay green, 0 absences, q2-036 served,
$0.0388 of the delegated $8 cap, live calibration surfaces byte-identical before/after;
r07 ruling 2's rider CLOSED, m0-5 stands as history), and a weekly production readout
watches the live calibration stream for the carried wrong-row classes
(`scripts/production_readout.py` + `packaging/production-readout.*`, installed on the
live box; report at `$LIFE_AGENT_KB/calibration/readout.md`).
M2 IS DONE (2026-08-25, `docs/unification/reports/r12-collapse-m2.md`, $0): the one
poster — `ask_client.post_decision` + `drive` own the reach surface's record;
`core/recorder.py` is the one recorder (family leaves write through it, the leaf-drift
gate pins it); the §6.5 unavailability RECORD lands locally with `decision_id=""`
(unfoldable — the bridge refuses an empty id, pinned). The pre-registered record change
shipped: reach decisions are priced rows (`regime`/`policy`/`run_id`/`instrument`
appear; `cost_usd`/`latency_s` become numbers). Gates: G1 2705 + clean lint/type; G2
314/314 twice, 105 direction-asserted, DIR-1 amended blind for the 102 posting A-loop
bodies; G3 golden green on both legs, counts identical; P5 live fingerprints
byte-identical to r11. `answer_via_executor`/`_edge_curves` are one-checkpoint shims
that die at M3.
M3 IS DONE (2026-08-25, `docs/unification/reports/r13-collapse-m3.md`, $0.68): ONE fold
entry point — `utility.posterior(brain, model, evidence, *, policy)`, the regime a
required indicator naming a declared conditioning set, structurally enforced
(frozen-elicitations refuses verdict-projected events), `fold_version` covering the
policy so no memo can cross regimes; six callers name their regime and the driver's
stamp derives from `LK.U_BAR_POLICY`. ONE reliability posterior — `core/reliability.py`
(`PRIORS` keyed (edge, cell)); `LK.extractor_reliability` + `NR.population_posteriors`
are drift-gated bindings. `AC.answer` and `ask._edge_curves` deleted; jarvis and the
A-loop driver inline drive + render; `answer_via_executor` is retained as ask's
executor-lane surface (amendment 4); the leaf write tails stay with the one recorder
until M5's single caller (amendment 5). Six blind amendments, three catching defects in
the pre-registration itself (a frozen G3 conjunct would have failed every row by
construction — re-read every frozen clause against the artefact it names). Gates: G1
2718 + clean; G2 314/314 pure equality; G3 = run 15 (`gate-20260825T215428`) PASS on
all four conjuncts — 0.907/+0.421, zero NEW wrongs, the same three carried rows as run
14.
M4 IS DONE (2026-08-26, `docs/unification/reports/r14-collapse-m4.md`, $0.60): ONE
price table — `core/pricing.py` (PRICING_VERSION 2) declares the corroborate tiers,
the transform menu, the deliberate seed, the grow actuators, the re-read model and the
D-2 reliability prior column; executor/gather/reliability BIND the same objects
(drift-gated — a second spelling cannot exist); `realised_utility`'s report branch is
spelled through the `u_assert` atom (exact); E-5: both silent `lambda_usd` defaults are
dead — the latent is REQUIRED and a missing one fails loud. Gates: G1 2724 + clean; G2
314/314 pure equality; G3 = run 16 (`gate-20260826T003710`) PASS on all four conjuncts
— 0.961/+0.519 [+0.081, +1.003], zero NEW wrongs (the two standing rows only; the
warm-deliberate row lands withheld this time — the headline's whole move off run 15 is
that one named wobble), $0.60, all-warm deliberates. Q8 DECIDED: the M3 lane deletes at
M5. The split SIGNED: single M5. Run 16 also settled an ops class: a priced run fired
as an agent-session background task dies with the session (two clean SIGTERM teardowns,
~$0) — priced runs launch as transient `systemd --user` units from here on.
M5 IS DONE (2026-08-26, `docs/unification/reports/r15-collapse-m5.md`, $4.88 across
runs 17+18): the argmax absorption — ONE decide surface. Ask's B-4 pre-emption, the
gather fork + `core/gather.py`, and the M3 live lane (membrane live half, /decide-live,
GATE_WEAK_RETRIEVAL) are deleted; `core/terminals.py` holds the absorbed orchestration;
drive's down-branch runs the in-process body under a DECLARED terminals-only regime
(§6.5 kept for no-engine-at-all); L-3's scoped rows are engine-picked; D-5:
`decisions.withhold_reason` is THE reason derivation. The arc's finding: A2's $0 probe
read the engine's preference for re-reads as real (62/63 recorded reports flip when
shown the grow block) and the frozen consequence landed the every-terminal grow offer —
which run 17 (`gate-20260826T025059`) then PRICED: **FAIL 0.743/+0.238, answer rate
0.62→0.49, dispersed 37→51** — the engine's hand-set grow priors over-value re-reads
(registered §14 as the **hand-priced-VOI arc**, the post-M5 successor: ground the grow
priors in the gather-outcome stream; the argmax cannot genuinely own recall while VOI
is hand-priced). Owner ruling (option A, conferral in-tree): revert A2's ENACTMENT
alone — the report-economy latch returns as measured protection — pre-registered blind
as A5 with directional claims and conjunct (b) restated CLASS-BASED (prospective only;
run 17's record untouched). **Run 18 (`gate-20260826T083356`): PASS on all four —
0.959/+0.514 [+0.077, +0.999], wrongs exactly the two standing rows, the wobble row
withheld, all three directional claims confirmed, $0.37** — reproducing run 16 almost
exactly, so run 17's collapse is attributed to the grow-offer alone. The ladder
resumes at M6 — the observation model declared once.** Old D3–D4 stay
re-scoped as Ask's
aggregate/thread families. The doc's §14 open questions are a **live empirical ledger**
(owner's adoption rider): each entry names the evidence that decides it — keep it
current. Sequencing is continuous and eval-gated, not dogfood-gated (PRINCIPLES §9 as
amended).

**Not built, deliberately:** the agent-loop spine (open decision — PRINCIPLES §15),
a separate VOI governor (there is none to build — the governor is the spine itself, PRINCIPLES §16), a live MCP server
(`src/pkm/mcp_server.py` is dormant-by-design — PRINCIPLES §5). One candidate spine+brain
composition is documented at
[`docs/candidates/brain-design.md`](./docs/candidates/brain-design.md) — a candidate, not the
plan; the related external repos (`../credence/apps/credence-pi`, `../pi-mono`) are reference
material for that candidate only.

- **Membrane shadow (`src/life_agent/membrane`, `src/life_agent/bridge`):** the frozen
  proplang-govhost engine mirrors live decide/verdict traffic off to the side, never on the
  decision path. Env-gated (absence = disabled); report at `$LIFE_AGENT_KB/membrane/report.md`,
  register at [`docs/membrane-shadow.md`](./docs/membrane-shadow.md). **Owner ruling
  (2026-08-25, superseding run-14 conferral ruling 5): proplang is the RULED successor of
  credence at the decide seam — the migration is MANDATORY, gated-mandatory
  (membrane-shadow §18: the frozen bars pace the swap and a FAIL means iterate-and-re-run,
  never park; refusal is retired as an endpoint) and DEFERRED (not a completion-programme
  condition; opens post-M7 after the completion audit). Nothing in tree may presuppose the
  swap until it lands.**

## `src/pkm` — the KB core (Python, uv, DuckDB): key files

Content-addressed extraction cache + DuckDB catalogue + format producers + transforms.
**It already nails content-addressing and a *semantic* (not bitwise) determinism contract —
don't "fix" that (PRINCIPLES §10).**
- **Producer protocol:** `src/pkm/producer.py` (`Producer` Protocol, `ProducerResult`).
- **Producer template (subprocess + version parse, never raises):** `src/pkm/producers/pandoc.py`.
- **Wiring ladders (edit to add a producer):** `src/pkm/routing.py`, `src/pkm/extract.py`
  (`_PRODUCER_NAMES`, `_needed_producer_names`, `_ensure_constructed`), `src/pkm/cli.py`
  (`--producer` choices, `_SUBCOMMANDS`).
- **Catalogue + migrations:** `src/pkm/catalogue.py`, `src/pkm/migrations/` (hash-verified;
  never edit a landed migration — add the next number).
- **Cache key:** `src/pkm/hashing.py` (`compute_cache_key`, `compute_model_identity_hash`).
- **Transforms:** `src/pkm/transform.py`, `src/pkm/transforms/{entity_extraction,action_items,email_triage}.py`;
  they **chain** (`_find_eligible_sources` resolves `input.producer` over `artifacts` — SPEC §18.7).
  Live model calls gated behind markers (`-m 'not llm and not system'` is the default; both are
  non-deterministic, opt-in only).
- **Tests:** `tests/conftest.py` (`tmp_root`, `migrated_root`); hermetic by default.
- **Governance — READ FIRST:** `docs/pkm/SPEC.md` and `src/pkm/CLAUDE.md`. The frozen-foundation
  rigor (PRINCIPLES §11): SPEC-first, TDD, idempotency double-runs, ask before a new
  dependency / top-level directory / file format.
- Verified: **DuckDB 1.5.2** here loads both `fts` and `vss` (HNSW cosine + `array_cosine_distance`).

## `life_agent.tasks` — the GTD, event-sourced (Python, SQLite, the act layer)

One append-only **event ledger** is the source of truth; the SQLite is a rebuildable
projection. See `docs/act-layer-events.md`.
- **Ledger:** `src/life_agent/tasks/events.py` — `Asserted`/`Disposed`/`Superseded`/`Amended`,
  keyed on a content+grounding **assertion identity** (human commands mint a unique identity;
  email-derived use content).
- **Read-model:** `src/life_agent/tasks/store.py` — the `tasks` table (lists
  inbox/next/scheduled/someday; `@tags`; `is_today`; due); `apply(event)` folds one event,
  `rebuild(events)` replays the ledger. Paths (`src/life_agent/core/config.py`): ledger at
  `$LIFE_AGENT_KB/tasks/events.jsonl`, read-model at `GTD_DB_PATH` (default
  `$LIFE_AGENT_KB/tasks/gtd.db` — derived, safe to delete and rebuild); the legacy
  `JARVIS_DB_PATH` (`$LIFE_AGENT_KB/jarvis/jarvis.db`) is a read-only pre-cutover snapshot.
- **Commands (write seam):** `src/life_agent/tasks/commands.py` →
  `commands.add/complete/delete/move/...` (append event(s) → fold the read-model → return the
  reply). The email projector (`project.py`) is just another producer of
  `Asserted(origin="email")` events.

## `life_agent.reach` — the Telegram channel + persona (transport only, no truth)

- **Transport:** `src/life_agent/reach/telegram.py` (poll/send; knows only Telegram).
- **Loop + NLU + persona:** `src/life_agent/reach/jarvis.py` — a haiku call parses a message →
  intent → routes to `tasks.commands`/`tasks.store`. Runs as `systemd --user jarvis.service`
  via `python -m life_agent.reach.jarvis`.
- **Digest:** `src/life_agent/reach/digest.py` (`python -m life_agent.reach.digest`).
- **Owner's Telegram id:** `JARVIS_USER_ID` (env / gnome-keyring) — never hard-code it.

## Conventions & constraints (operational)

The principles themselves (functional style, seams, provenance, local/cloud, Tailscale,
dogfood) live in [`PRINCIPLES.md`](./PRINCIPLES.md) — they are not restated here.
- **THIS REPO IS PUBLIC (`github.com/gfrmin/life-agent`) AND MUST STAY PII-FREE AND
  REUSABLE BY STRANGERS.** The owner's data lives out of tree under `$LIFE_AGENT_KB`
  (corpus, eval question files, audit artifacts, FAILURES.md) — keep it there. Nothing
  in tree may carry a real person's name, phone/fax number, email address, account or
  document id, or a verbatim value lifted from the corpus, **including in docs prose,
  §14 ledger entries, commit messages, and test fixtures.** When an example needs the
  *shape* of a real value (the competition detector's digit-count classes, a tel/fax
  pair), invent a synthetic value with the same shape and mark it
  `# PII-OK: synthetic <what>` — the existing convention. When a ledger entry must
  describe a real failure, describe the *class* ("the gold is a three-token personal
  name; the leader is its two-token suffix"), never the value. Equally: no
  owner-specific absolute paths, hostnames, or ids hard-coded in `src/` — they belong
  in config/env (`$LIFE_AGENT_KB`, `PKM_CONFIG`, `JARVIS_USER_ID`).
- **In `pkm`:** obey its SPEC-first + TDD + idempotency rules (see Governance above).
- **Secrets** live in **gnome-keyring**, never in `.env`. Read one with
  `secret-tool lookup service env key VARNAME`; load all into a shell with
  `load_secrets_from_keyring`. Fastmail tokens: keyring `service=carddav` / `service=jmap`;
  sending email: `~/.msmtprc` (passwordeval).
- **Tooling preferences:** `rclone` (not s3cmd) for R2; `gh` (not a GitHub MCP) for GitHub;
  don't pipe long-running commands through `head`/`tail` (use native verbosity).
- **Commit/push only when the owner asks.**

## Environment (Arch Linux, this machine)

- **GPU:** RTX 4060 (8 GB). **Local Ollama is DEPRECATED (2026-08-17, owner directive)** —
  the cached ask instruments, the pkm LLM transforms, and jarvis's NLU all run on the
  Anthropic seam (`core/instrument.py`, haiku); local inference returns only via a
  non-Ollama runtime (e.g. for embeddings, unbuilt). Do not assume `localhost:11434`.
- **OCR/docs:** `tesseract 5.5.2` (langs incl. **`heb`** + `eng`), `pdftotext`, `exiftool`,
  ImageMagick 7, ghostscript, libreoffice.
- **Search:** `rg 15.1`, **`rga 0.10.10`** (ripgrep-all, searches inside PDFs), `sqlite3 3.53`
  (FTS5), `pandoc`, `jq`. (No `fd`/`fzf`/`recoll`.) **DuckDB 1.5.2.**
- **Langs:** Python 3.14 system-wide, but **this project pins 3.13** via `uv`
  (`pyproject.toml` `requires-python`); Node 26 + `pnpm`/`bun`; Julia (for credence).
- **Running services:** `jarvis.service`, PhotoPrism, Tuwunel + mautrix bridges +
  `matrix-archiver`, n8n, miniflux, invidious; timers `mbsync` (mail) + `renavon-inbox-ingest`;
  bi-hourly borg backup.

## Start here

1. Read [`PRINCIPLES.md`](./PRINCIPLES.md), then [`ROADMAP.md`](./ROADMAP.md) (phases), then
   `$LIFE_AGENT_KB/docs/data-seams.md` (the verified, machine-specific data map — out of tree;
   saves you a re-exploration).
2. Follow [`GETTING_STARTED.md`](./GETTING_STARTED.md). Current phase: **Phase 1.6 — the
   derivation framework** (`docs/system-design.md` §8 is the program; FAILURES.md remains
   the evidence log, no longer the gate — PRINCIPLES §9).
