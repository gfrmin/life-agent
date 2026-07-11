# The membrane shadow — host-declaration register (life-agent)

Status: as-built, 2026-07-12 (branch `feat/membrane-shadow`, Tasks 1–9 + the final-review fix
wave). This is the question→resolution→why register for every host-declared value and rule the
membrane shadow feature fixes. Everything here is life-agent-side DATA or transport; nothing
binds the frozen proplang engine — we never edit that repo, or the sibling credence-governor
repo whose own register (`docs/membrane-shadow.md` there) this one is modeled on and
cross-checked against. Items marked **FLAG** are ones where a defensible alternative existed
and the owner may re-decide.

Two of this register's own claims were FALSE as first published and are corrected in place,
with the correction left visible rather than quietly overwritten (§7: the respond-unreachable
demand rested on a fallback constant, not on the live posterior; §10: "an unknown form fails
loudly at construction" was aspirational). §2 item 5 records a defect in the world itself —
the information actions were priced as pure costs, which made them unfirable at any credence —
and the honest bake-in that replaces it.

Conformance source: the frozen proplang-govhost wire protocol. This register states
only life-agent's OWN declarations against that wire (the world, the utility forms, the
evidence mapping); it does not restate the wire's own conformance sources — those live
in the sibling repo's register and in the frozen engine's own docs, neither of which we
edit or duplicate here.

Code map: `src/life_agent/membrane/world.py` (the answer-domain world — menu, features,
utility declarations), `session.py` (one booted session, evidence mapping),
`shadow.py` (the multi-form supervisor, records, warm replay), `client.py` (the wire
transport), `core/shadow_mirror.py` (the fan-out poster), `bridge/server.py` (wiring +
shutdown), `scripts/membrane/report.py` (the differential + demand report).

## 0. The stated field prediction (read first)

`life_agent.membrane.world.latent_utility_decl` sends `said: ["var", 1]` — utility is a
pointer into the learned latent, not a function of the fired action. Under the frozen
chooser, information about that pointer moves every terminal's value together, so no
choice among the terminal affordances can ever be distinguished by it; only `ask`
carries a residual (θ) charge, so it strictly loses to a same-valued alternative. With
`AFFORDANCES` in `gather(4), ask(3), abstain(2), respond(1)` order and first-listed
ties winning, the tie among `{gather, abstain, respond}` (all tied at value 0 once
`ask`'s charge is subtracted from its own row) resolves to **`gather`**, unconditionally.

**Stated prediction, on the record before the field run: the `latent@1` shadow fires
`gather` on every tick, and the engine reports `sensitivity: false`.** This is
**CONFIRMED IN FIELD** (Task 8's live smokes against the real binary, and the 2026-07-11
field run below): `latent@1` chose `gather` 6/6 in the field, and the pre-field system
smoke pinned constant `gather` with `sensitivity: false` across varied feature vectors.

Consequence, not blocker: `latent@1` is therefore the **falsification instrument** — its
live action-rate confirms or falsifies the reading above, and if it is ever seen to vary,
our reading of the frozen driver is wrong somewhere, which is equally a result, surfaced
by `scripts/membrane/report.py`. `table@1` is the **real challenger policy** — the
non-degenerate form the demand ledger actually scores.

**A trap this prediction set, worth naming.** `latent@1`'s degeneracy makes it fire `gather`
unconditionally — and until the final review, `table@1` fired `abstain` unconditionally, for
a completely unrelated reason (its information rows were priced as pure costs, so abstain
dominated them at every credence; §2 item 5). Two constant policies, two different causes, one
of them a defect — and the field numbers were consistent with both being "as predicted". A
prediction confirmed by a degenerate mechanism confirms nothing; the fix is to derive what the
declared utility ACTUALLY implies at each credence (`world.argmax_action`, published per form
in the report's §1b) and check the engine against it, which is now done on every live tick.

## 1. The affordance menu and feature vocabulary (`world.py`)

1. **Menu — `gather(4), ask(3), abstain(2), respond(1)`, listing order NORMATIVE.**
   `argmaxEU` ties resolve first-listed (the wire's own rule), so this order is a live
   policy declaration, not cosmetic. It encodes two stacked preferences at exact
   indifference: information-buying beats committing (`gather`/`ask` before
   `abstain`/`respond`), and among the two terminals, withholding beats asserting
   (`abstain` before `respond`) — a fail-safe polarity: when genuinely undecided between
   silence and a claim, the world defaults to silence. **FLAG:** reordering to engineer
   an outcome would be adapter-side steering; we keep this order because it is the
   direct translation of the executor's own risk posture (bayesian-foundations §8), not
   because it was tuned against any observed run.
2. **A menu option literally named `ask` carries the θ charge — name-keyed, not
   position-keyed.** `latent_utility_decl`'s sole residual is named `theta_ask`
   (`world.py:239`); the sibling governor's own register (its item 2) states the SAME
   convention for a menu whose `ask` IS first-listed. Life-agent's `ask` is
   second-listed (id 3), yet the charge still binds correctly by name — the frozen
   engine's v2 wire keys the charge off the literal affordance name `ask`, not its menu
   position. Convenient alignment for us: our own `ask` doctrinally means "pay to
   interrupt the owner" (`world.py`'s module docstring — "the daemon's own
   interrupt-cost affordance"), which is exactly the wire's own reserved meaning for a
   thing named `ask`. Not independently verified against the frozen engine's source
   (out of tree); inferred from the two registers' matching behavior.
3. **Features — one-hot indicator families, buckets from `world._CANDIDATES_BUCKETS`
   etc., absent = 0.0.** `n-candidates∈{0,1,2plus}`, `leader-credence∈{lt50,50to70,
   70to80,80to90,ge90}`, `p-none∈{lt20,20to50,ge50}`, `n-obs∈{0,1to2,3plus}`, plus three
   singleton flags `era-split=1`/`owner-scoped=1`/`grow-pass=1`. Every guard is declared
   with a singleton `[0.5]` grid (a plain is-this-bucket-set boolean); an unset bucket is
   simply omitted from the tick rather than sent at `0.0` (dormancy is free on the wire).
4. **Why no integer/ordinal codes.** Bucketing to one-hot indicators, rather than an
   ordinal integer per family (e.g. `leader_credence_bucket: 0..4`), avoids asserting a
   metric the guard learner would otherwise exploit: nothing here claims that
   `80to90` is "closer" to `70to80` than to `lt50`. Each bucket is an independent binary
   feature the engine conditions on separately — a declaration, not an accident.

## 2. `table@1` — the utility declaration (`world.utility_rows`)

5. **`u_bar → rows` mapping — the information actions are priced as MYOPIC PERFECT
   INFORMATION.** `u_correct`/`u_abstain` are the posterior's gauge constants (1.0 / 0.0);
   `u_wrong = u_bar["u_wrong"]` (fallback −9.0); `q = |u_bar["lambda_int"]|` (fallback 0.1);
   `g = |u_bar["kappa_att"]|` (fallback 0.02). Rows:
   `gather → [u_abstain − g, u_correct − g]`, `ask → [u_abstain − q, u_correct − q]`,
   `abstain → [u_abstain, u_abstain]`, `respond → [u_wrong, u_correct]`, plus the required
   `internal: "think"` sentinel one unit below the minimum entry of every real row (so it is
   strictly worse at EVERY p1, by construction — never hand-checked per call).

   The information rows read "having gathered (or asked), you then take the CORRECT act:
   withhold if y=0, respond if y=1". That is the **credence-governor's own declared
   convention** (its HOSTS_PLAN register item 8.4: "u(ask,·) = −q bakes 'a resolved ask makes
   the correct act free' (myopic perfect information)"), transposed to this world's gauge,
   where the correct act is worth `u_correct` rather than 0.

   **FLAG — it OVERVALUES information, knowingly.** A real gather round does not guarantee
   the correct act: it grows recall, and the executor may still be wrong or still withhold.
   The gap between this pricing and reality is exactly what the shadow's differential
   MEASURES; it is never to be tuned away to make an action distribution look better. The
   alternative is not "more conservative" but degenerate, and this world shipped it: with the
   pure-cost rows `gather → [−g, −g]` and `ask → [−q, −q]` (constant in y), `EU(gather) = −g <
   0 = EU(abstain)` at EVERY p1 and every u_bar — abstain strictly dominates the whole
   information menu, so `table@1` could never emit `gather` or `ask` at all, and the menu's
   entire point (effort allocation) was unreachable by construction. Owner-re-decidable: a
   discounted-information pricing (gather is worth some ρ<1 of the correct act) is the obvious
   successor once there is a measured ρ.
6. **The exchange rates, FLAGged.** `q` is sourced from `lambda_int` — the SAME latent
   `core/decide.py`/`core/lookup.py` already use to price `ask_clarify`
   (`U(ask_clarify) = ρ·u_correct − lambda_int`), so pricing this world's `ask`
   affordance off it is a clean semantic reuse, not a new assignment. `g` is sourced
   from `kappa_att` — the latent `core/narrative.py` uses to price per-claim inclusion
   attention (`EU(include|p) = p·u_assert(p) − kappa_att`). **FLAG:** repurposing
   `kappa_att` to price `gather` (fetching more evidence) rather than its native meaning
   (attention spent reviewing one more included claim) is defensible by analogy — both
   are "further effort" costs — but not independently validated; a dedicated latent
   sourced from measured recall-growth cost was a live alternative the owner may prefer.
7. **`u_bar` is read server-side; PII never crosses.** The bridge's `_build_membrane`
   passes a lazy `u_bar` closure (`bridge/server.py`) that reads the real
   `UtilityPosterior` (owner data) INSIDE the bridge process; only the resulting
   floats (utility means) enter the world declaration sent to the govhost subprocess —
   no owner profile text, no corpus content, ever reaches the wire.

## 3. `latent@1` — the utility declaration (`world.latent_utility_decl`)

8. **`said → ["var", 1]`.** Utility is the learned pointer latent, not the fired action
   (`["var", 0]` would be nonsense here — same reasoning the governor's register gives
   for its own world). Degeneracy consequence in §0.
9. **`theta_ask` grid — fixed OFFSETS above a computed floor, not the wire golden's
   absolute points.** Floor `= max(|lambda_int_mean|, 1e-6)`; grid `=
   [floor, floor+0.1, floor+0.2, floor+0.4]`. The wire's own golden example uses an
   absolute floor of 0.05, which is unsafe here: this world's real `lambda_int` prior
   mean is 1.0 (`config/utility-model.example.yaml`), well above 0.05, so points
   declared relative to it (offsets) keep strict ascent for ANY non-negative posterior
   mean, at the cost of no longer being byte-identical to the wire's own golden grid.
   The floor is clamped to a tiny epsilon so a measure-zero exactly-0.0 posterior mean
   still satisfies the wire's positive-grid rule.
10. **`tau` — adopted verbatim from the wire's golden example (`{points: [0.5,1,2],
    weights: [0.5,0.3,0.2]}`), never fit.** **FLAG:** no measured life-agent-side
    owner-noise source exists; same posture the governor's register takes for its own
    world (its item 4), same caveat here — the owner may want to confirm or replace it
    once a real noise estimate exists.
11. **`price → "tick-price"`, deliberately dormant.** The wire requires the name; no
    measured per-tick deliberation cost exists at decide time, and sending a declared
    constant into a measured-price slot would violate the stratification rule
    (measured-vs-declared). **FLAG:** dormant until a measured source exists.
12. **`gauge → {zero: "status-quo", scale: "answer-utility"}`.** Parsed and required by
    the wire; the frozen `latent@1` chooser does not consume it operationally — a
    declaration for the record, naming the scale this world's utility numbers live in
    (an answer's realized utility, not USD as the governor's world declares).

## 4. Evidence mapping (one host rule, live and warm alike)

13. **The `verdict_y` table** (`session.py`): `(report, good)→1`, `(report, bad)→0`,
    `(report_scoped, good)→1`, `(report_scoped, bad)→0`, `(abstain, good)→0`,
    `(abstain, bad)→1`. Every other `(chosen_action, valence)` pair — `hedge`,
    `ask_clarify`, and any `report`/`report_scoped`/`abstain` combination not listed
    above — is a **named exclusion**: `verdict_y` returns `None`, the caller counts a
    skip. Ambiguous is not evidence.
14. **The `latent@1` verdict double-feed.** One owner verdict emits two ticks at the
    SAME `t` (the evidence-stream index advances once, after both): an untagged tick
    (world-report role) then a `stream: "verdict"` tick (owner-response/pointer role).
    Adopted verbatim from the governor's own precedent (its item 9) — the two ticks move
    disjoint agents, so nothing is double-counted within one agent.
15. **The honest live-verdict skip — a FIELD FINDING.** In-process family decisions
    (`core/narrative.py:516`, `core/lookup.py:926`) append their own `DecisionEvent`
    rows directly to the calibration log, with `decision_id = ` the answer's own §18.9
    artifact cache key — but they do this WITHOUT ever calling the bridge's
    `/log_decision`. `MembraneShadow.submit_decision` is the only thing that populates
    `_bindings[decision_id]`, so a later reaction on one of these decisions (via
    `/log_reaction`) finds no binding and `submit_reaction` counts it a skip
    (`stats()["skips"]`), never fabricating a verdict for it. **This gap is
    self-healing and bounded**: `boot_snapshot` replays the decisions⋈reactions join
    straight off the logs at the NEXT boot, so any skipped live verdict is picked up
    then — the shadow's live coverage is executor/bridge-logged decisions only; the
    in-process families' verdicts arrive one boot cycle late. **FLAG:** wiring
    `narrative.py`/`lookup.py` to also post through `/log_decision` would close this
    gap at live speed instead of at next-boot speed — a live alternative the owner may
    want, traded against adding an HTTP round-trip to those code paths.

    Note what this is NOT: the verdict's own transport. Every ask-live verdict now posts to
    `/log_reaction` (see §8), so the shadow sees the reaction live; the residual gap is
    narrower — a reaction on an IN-PROCESS family decision still finds no `_bindings` entry
    (nothing posted that decision to `/log_decision`), so `submit_reaction` counts an honest
    skip and the evidence lands at the next boot instead.

## 5. Warm segmentation

16. **Per-tick replay only; no counts-collapse file exists yet.** `shadow.boot_snapshot`
    reads `decisions.jsonl` ⋈ `reactions.jsonl` (plus, optionally, one fair-fight run's
    warm vectors) and replays each row as an individual tick through
    `MembraneSession.boot`'s `verdict_replay`/`outcome_replay` — the same per-event path
    live traffic uses, never a batched summary.
16a. **TWO id namespaces, bridged in exactly one place.** A decision/decide record's
    `question_id` is the **mirror id** (`core.decisions.question_id` — sha256 of the question
    TEXT, [:16], now the single derivation, drift-gated in `tests/test_decisions.py`). A
    fair-fight `OutcomeVector.question_id` is the **corpus id** (`q-001`). They do not join,
    and a join across them yields ZERO rows always — which is indistinguishable from "no data
    yet" unless something says so. Both warm joins (boot replay, and the report's grounded
    section) now map corpus → mirror through the run's own `run_meta.json → questions_path`
    (`shadow.warm_question_id_map`), and **an empty join is reported as an empty join,
    loudly**, never as an under-powered sample. Consequence for the published warm-corpus
    size: `BootSnapshot.n_source_records` counts VERDICT-source rows only (decisions +
    reactions); warm fair-fight rows are accounted separately as read-vs-joined
    (`BootSnapshot.warm`), because a row that cannot join teaches the shadow nothing and must
    not pad the figure.
17. **`observe_counts` is spoken by the transport but unused here.** `MembraneClient`'s
    wire is a generic `request(dict)` — it can carry any tick shape the frozen engine
    accepts, including a batched `observe_counts`-style evidence tick (the shape the
    governor's own warm corpus collapses to, per its register item 11). Nothing in
    `session.py`/`shadow.py` constructs one today, because the corpus here is tiny
    (hundreds, not tens-of-thousands, of rows) — the named successor if the corpus grows
    to where per-tick warm replay becomes an expensive boot cost.

## 6. Transport and observability

18. **Shadow supervisor knobs** (`bridge/server.py`'s `_MEMBRANE_*` constants): queue
    size 1024, ≤3 respawn ATTEMPTS total over the process lifetime (the ported governor
    posture — every attempt counts, whether triggered by a boot failure or a tick death,
    and whether it then succeeds or fails; the initial boot is free), then dead until
    the daemon itself restarts; 60s backoff between attempts; a 300s per-read timeout
    (`config.membrane_read_timeout_s`, `LIFE_AGENT_MEMBRANE_READ_TIMEOUT`) so a wedged
    driver surfaces as an error and enters respawn instead of parking the worker
    forever.
19. **The mirror's own timeout + breaker** (`core/shadow_mirror.py`): the fan-out poster
    that feeds `/decide-support` from every real call site (`scripts/ask.py`,
    `core/ask_client.py`, `scripts/eval_executor.py`) uses its OWN short timeout
    (`MIRROR_TIMEOUT_S = 2.0`, deliberately far below the daemon's own 300s decide-tick
    budget) plus a one-strike circuit breaker per question — the first failure or
    timeout on a question trips the breaker for the rest of that question, so a wedged
    shadow can never repeatedly stall an already-computed real answer.
20. **Readouts are logged, never branched on.** `p1`/`entropy_bits`
    (`table@1`)/`residual_mean`/`sensitivity` (`latent@1`) land in
    `ShadowChoice.readouts` and are copied verbatim onto the shadow's own `decide`
    record — `MembraneSession.decide` is a pure choice-relay over them; no adapter code
    path reads them back into control flow (HOSTS_PLAN 8.12(b): observation, never a
    host-side decision fork). Test-pinned: two replies differing only in readouts yield
    the identical chosen action.

## 7. `respond` is unreachable — but NOT for the reason first published

**Correction (final review).** This section previously read: "at `u_wrong = −9`, `u_correct =
1` (this posterior's current means), `respond` needs `p1 > 0.9` strictly to beat
`EU(abstain) = 0`; the grid ceilings at 0.9; therefore respond is unreachable." Two things
were wrong with it, and both are instructive:

1. **−9.0 was never "this posterior's current means".** It is `world.utility_rows`' FALLBACK,
   used only when no posterior is available. The live posterior (GET `:8798/utility`) reads
   **`u_wrong = −5.9395`** — the reaction loop has already narrowed it. (§3 item 9 gets the
   analogous point right for `lambda_int`; §7 did not.) The threshold is a FUNCTION of the
   utility, not a constant, and it was published as a constant.
2. **Respond-vs-abstain is the wrong comparison.** The engine argmaxes over the WHOLE menu.

The arithmetic, derived (`world.respond_threshold`, `world.argmax_action` — and the whole
declared table is now persisted per boot, so the report derives from it instead of guessing):

| bar | fallback `u_wrong = −9.0` | **live `u_wrong = −5.9395`** |
|---|---|---|
| respond beats `abstain` at p1 > `(u_abstain−u_wrong)/(u_correct−u_wrong)` | 0.9000 | **0.8559** |
| respond beats `gather` at p1 > `1 − g/(u_abstain−u_wrong)` | 0.9978 | **0.9942** |
| **binding (whole-menu) threshold** | 0.9978 | **0.9942** |
| engine's attainable p1 (40 y=1 verdicts, live) | 0.8918 | 0.8918 |

So under the live posterior **respond-vs-abstain is CLEARED** (0.8918 > 0.8559 →
`EU(respond) = +0.249 > 0`): the claim "respond cannot beat silence" is simply false, and it
was false the moment the reaction loop moved `u_wrong`. Respond is nevertheless still
unreachable, because **`gather` — priced as myopic perfect information (§2 item 5) — outbids
it** until p1 > 0.9942, which the engine's own grid (ceiling 0.9) cannot reach.

**The demand therefore still fires, but it now has two named owners, and one of them is us.**
Part of it is the frozen refine lattice (proplang Boundary V/R): a richer lattice that let p1
exceed 0.9942 would make respond reachable. The other part is life-agent's own declared
overvaluation of information (§2 item 5's FLAG): under a discounted-information pricing the
gather bar drops and respond becomes reachable far earlier. Neither is a bug; both are
declarations, and the report (`respond_unreachable_p1_ceiling`) prints both thresholds side by
side, per form, off each boot's own `u_bar`, rather than asserting a constant.

**Live-verified, three utilities, 120 ticks against the real binary**
(`tests/test_membrane_live.py`): the host-side model of the frozen chooser
(`world.argmax_action` over the declared table at the engine's own reported p1) predicted the
engine's fired action on EVERY tick, with zero mispredictions — which is what earns the right
to derive any of the above offline. The parametrised test includes a falsification case
(`u_wrong = −0.1`, whole-menu threshold 0.80 < 0.8918) under which respond **does** fire, so
"respond never fires" is not an unfalsifiable artifact of the fixture.

## 8. The 2026-07-11 field-smoke numbers

Run against the real `proplang-govhost` binary, both forms (`table@1,latent@1`), off an
isolated copy of the real, warm knowledge base (production KB verified untouched by the
run: decision/reaction counts unchanged, no membrane subtree written there). The two
questions asked during the run were real and personal — neither their text nor their
answers is recorded here; only shapes and counts are.

- **Handshake**: `models=2393`, `namespace_bits=4.169925` (18 named indicators),
  `ulatents=2`.
- **Boot**: `n_source_records=827` (the decisions⋈reactions replay), world digests
  recorded per form.
- **Traffic**: 2 real questions produced 6 decide ticks per form (the mirror fires on
  every gather round, not just the terminal one, so multiple decide ticks per question
  is expected). Decide latency: p50 15–17ms, p95 18–26ms.
- **Shadow choices — RE-MEASURED under the fixed world (§2 item 5).** The 2026-07-11 field
  run was taken under the pure-cost information rows, where abstain strictly dominated
  `gather`/`ask`, so its `table@1` numbers measured that defect and not the policy. The SAME
  field traffic — the same boot snapshot (an isolated KB copy), the same six recorded feature
  vectors, replayed through the real binary at the LIVE `u_bar` — was re-driven under the
  fixed world:

  | | before (pure-cost rows) | **after (perfect-information rows)** |
  |---|---|---|
  | `table@1` choices | `abstain` 6/6 | **`gather` 6/6** |
  | `table@1` agreement with the real effector | 1/6 | **4/6** |
  | `latent@1` choices | `gather` 6/6 | `gather` 6/6 (degenerate — unchanged) |
  | `latent@1` agreement | 4/6 | 4/6 |
  | shadow `p1` | ~0.337 | ~0.365 (the isolated KB accrued 2 more verdicts) |

- **Real effectors, same 6 ticks**: 4× `gather`, 1× `abstain`, 1× `report`. Both forms now
  disagree on exactly the same 2 ticks (the real `abstain` and the real `report`), enumerated
  in the rendered report.
- **A caveat that matters for the differential's power**: at the field's observed credence
  (p1 ≈ 0.365) `table@1` and `latent@1` fire the same action, so on THIS sample the two forms
  are behaviourally indistinguishable and the dual shadow discriminates nothing. They are
  still different policies — `latent@1` is constant across every feature vector (degenerate),
  while `table@1` fires `abstain` below p1 = 0.034 and `respond` above p1 = 0.994 (§7) — but
  the field has not yet visited a credence where they part.
- **The key reading: `table@1`'s live `p1` (~0.337) does not track the retrieval
  leader's credence.** A real `report` fired at leader-credence 0.985 — at which the
  shadow's own `p1` would still counsel `abstain`. **13 usable verdict ticks against
  2,393 declared hypotheses have not yet taught the guards that "a strong retrieval
  leader predicts correctness."** The warm-corpus size is the binding constraint here —
  empirically observed, not a theoretical limit of the design.
- **Verdict loop closed live**: a reaction on a real executor decision produced
  `stream: "verdict"` evidence rows in BOTH forms (`y=1`), advancing `t` from 6 to 7 — proof
  the fold path works end-to-end, not just at boot replay. **Which surfaces close it live**
  (the original wording implied all of them): the bridge's `/log_reaction` is the ONLY caller
  of `MembraneShadow.submit_reaction`, so a verdict reaches the shadow live only if it is
  posted there. Jarvis/Telegram always did (`core/ask_client.react`). `bin/ask-live` — the
  PRIMARY dogfood surface — did NOT: it appended straight to the reaction log, so its verdicts
  reached the shadow only at the next boot's snapshot replay (late, never lost). Fixed:
  `scripts/ask.py`'s `submit_reaction` now posts to `/log_reaction` when the bridge is
  reachable and falls back to the direct append when it is not (fail-open — the reaction log
  is the source of truth and a verdict must survive a down bridge), never writing both.
- **The honest skip** (§4, item 15) was observed live during this same run: `skips=1`,
  from an in-process family decision's verdict with no live binding.
- **Drops**: correctly reported "not observable" by the report — 14 total items is
  under the periodic stats cadence (every 100 processed items) and the run had no clean
  `close()` to force a final flush (see Part A below).
- **No leaked subprocesses**: the two long-running `proplang-govhost` processes visible
  on this box during the run belong to the sibling credence-governor's own shadow (a
  separate, pre-existing deployment) — this run's own govhost children exit cleanly on
  stdin EOF and left nothing behind.

## 9. The coordination contract

This register, together with `scripts/membrane/report.py`'s rendered differential and
demand ledger (written to `$LIFE_AGENT_KB/membrane/report.md`), is what the frozen
proplang repo's `HOSTS_PLAN` reads at two gates: its §9 A-gate ("life-agent differential
vs the credence brain") and its §5 B-gate. We never edit `HOSTS_PLAN`, the frozen
proplang repo, or the sibling credence-governor repo — this document and the report are
the whole of life-agent's side of that contract.

## 10. Deployment provenance

The binary is a copied build artifact of the frozen proplang repo, installed at
`~/.local/bin/proplang-govhost`, sha256
`96ec3de7a59100c8d46d569452af0f379ee6f0e44036f7706e8282af1ffd6c18` — **the SAME
artifact the sibling credence-governor repo field-deploys**: one engine binary, two
independent hosts (this shadow and the governor's own), one upgrade path. Selection is
`LIFE_AGENT_MEMBRANE_COMMAND` (absence = disabled = zero behavior change on the bridge);
forms via `LIFE_AGENT_MEMBRANE_UTILITY` (default `table@1`; field deploy
`table@1,latent@1`, the dual shadow). An unknown form raises `ValueError` in
`ShadowConfig.__post_init__` — at construction, before anything is spawned or served — and the
bridge's `_build_membrane` catches it, prints it, and serves with the membrane DISABLED
(never a half-running dual shadow). *This claim was previously false in both this register and
`config.membrane_utility_forms`'s docstring: nothing validated the forms, and an unknown one
died later and quieter, per-form, on the worker thread, leaving a permanently dead form inside
a supervisor that still reported healthy. It is now the code's, and test-pinned.*
