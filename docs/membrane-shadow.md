# The membrane shadow — host-declaration register (life-agent)

Status: as-built **v2, 2026-07-19** (branch `feat/membrane-v2`) — re-targeted at the
RE-DERIVED proplang engine ("IMPLEMENT THE BRIEF", steps 3–10, proplang `7da274b`): the
`proplang-govhost` executable this register was first written against was retired at
proplang's step-3 freeze, and the `table@1`/`latent@1` utility forms with it. v1 sections
that declared against the dead wire are kept, bracketed **[v1 — historical]**, because they
carry field findings; current declarations are the unbracketed ones. This is the
question→resolution→why register for every host-declared value and rule the membrane shadow
fixes. Everything here is life-agent-side DATA or transport; nothing binds the proplang
engine — we never edit that repo, or the sibling credence-governor repo whose own register
this one is modeled on. Items marked **FLAG** are ones where a defensible alternative existed
and the owner may re-decide.

Two of this register's own claims were FALSE as first published and are corrected in place,
with the correction left visible rather than quietly overwritten (§7: the respond-unreachable
demand rested on a fallback constant, not on the live posterior; §10: "an unknown form fails
loudly at construction" was aspirational). §2 item 5 records a defect in the world itself —
the information actions were priced as pure costs, which made them unfirable at any credence —
and the honest bake-in that replaces it.

Conformance source: **`membrane-wire.md` sections 1–3 as amended through step-10** in the
proplang repo (read at `7da274b`) — per proplang's own step-3 rider, "host conformance binds
to membrane-wire.md, never to GHC artifacts". Sections 4–6 of that file (the governor
encoding, `table@1`, `latent@1`) are bracketed there as the OLD roadmap's record, binding on
nothing current — exactly the forms this register's v1 declared. This register states only
life-agent's OWN declarations against the current wire (the world, the `said@1` sentence,
the evidence mapping); it does not restate the wire's own conformance sources.

Code map: `src/life_agent/membrane/world.py` (the answer-domain world — menu, features,
utility declarations), `session.py` (one booted session, evidence mapping),
`shadow.py` (the multi-form supervisor, records, warm replay), `client.py` (the wire
transport), `core/shadow_mirror.py` (the fan-out poster), `bridge/server.py` (wiring +
shutdown), `scripts/membrane/report.py` (the differential + demand report).

## 0. The stated field prediction **[v1 — historical]**

*(2026-07-19: the `latent@1` form this prediction instrumented died with the old wire; the
prediction, its field confirmation, and the trap it names are kept as the record of how the
v1 shadow earned its reading of the old engine.)*

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

1. **Menu — ONE writable name `act`, grid `[1.0, 2.0, 3.0, 4.0]` = `abstain, gather,
   ask, respond`; GRID ORDER NORMATIVE.** The re-derived wire's menu is names+grids (the
   step-5 shape; id/slots died); the agent's choice is a full assignment
   `{"act": {"act": <value>}}`, `wait` is every name at its grid's FIRST point, and
   argmaxEU ties resolve first-listed (membrane-wire.md §2, CL-3) — so wait keeps ties
   by construction. That forces a tie-posture change from v1: **`abstain` sits first**
   (the safe structural wait — when genuinely undecided, the world defaults to silence);
   v1's gather-wins-ties preference could not survive a wire whose wait keeps ties,
   because the only way to keep it would be to make `gather` the wait, and a shadow
   whose do-nothing default is "spend effort" is the wrong polarity. Then gather, ask,
   respond. **FLAG:** the order beyond the forced first slot is owner-re-decidable.
   `act` is a namespace member (RIDER 2: every writable name is; membership immutable)
   and DISJOINT from every tick feature name (ruling D-b2) by construction — indicators
   are `family=value` strings and `t`, never `act`.
2. **No name-keyed `ask` charge.** v1's `theta_ask` residual (the `latent@1` machinery,
   and the wire meaning it keyed off the literal name `ask`) died with the old wire; the
   interrupt cost now lives ONLY inside the `said@1` sentence's `ask` arm (§2), priced
   from `lambda_int` as before.
3. **Features — one-hot indicator families, buckets from `world._CANDIDATES_BUCKETS`
   etc., absent = 0.0.** `n-candidates∈{0,1,2plus}`, `leader-credence∈{lt50,50to70,
   70to80,80to90,ge90}`, `p-none∈{lt20,20to50,ge50}`, `n-obs∈{0,1to2,3plus}`, plus three
   singleton flags `era-split=1`/`owner-scoped=1`/`grow-pass=1`. Every guard is declared
   with a singleton `[0.5]` grid (a plain is-this-bucket-set boolean); an unset bucket is
   simply omitted from the tick rather than sent at `0.0` (dormancy is free on the wire).

> **Correction of record (2026-08-31, [`r42-engine-door`](./unification/reports/r42-engine-door.md)).**
> *"Dormancy is free on the wire"* describes the tree the shadow was written against
> (`1a0cea7`) and is **false at engine HEAD**. There the door requires the declared namespace
> covered exactly, and an under-specified tick is an error reply — measured:
> `{"error": "tick refused: missing declared [...13 names...]"}`. Sending every absent bucket
> explicitly at `0.0` is **provably a no-op on the old tree** (byte-identical reply), so this is
> a safe forward repair — but it is a repair, not a property. Two further door changes are
> measured in the same reading: `hello` requires `world.codebooks.theta`, and **evidence ticks
> are refused outright** for want of the writable name, which takes the shadow's whole learning
> path with them. §18's bars cannot be read until all three are repaired; see `GD-11`.
4. **Why no integer/ordinal codes.** Bucketing to one-hot indicators, rather than an
   ordinal integer per family (e.g. `leader_credence_bucket: 0..4`), avoids asserting a
   metric the guard learner would otherwise exploit: nothing here claims that
   `80to90` is "closer" to `70to80` than to `lt50`. Each bucket is an independent binary
   feature the engine conditions on separately — a declaration, not an accident.

## 2. `said@1` — the utility declaration (`world.utility_said`)

5. **`u_bar → sentence` mapping — the information actions are priced as MYOPIC PERFECT
   INFORMATION.** Utility crosses the re-derived wire as a SENTENCE of the priced grammar
   (step-8: `Util a y` is deleted engine-side; utility is a priced program evaluated at
   the tick's features — actions are features, so the sentence reads the chosen act via
   `["get", "act"]`). The program is nested `if (= (get act) (c <grid value>))` branches,
   one arm per affordance, each arm linear in the outcome residue `["var", 1]`:
   `u0 + var1·(u1 − u0)`. The (u0, u1) pairs are UNCHANGED from v1's table and live in
   ONE place, `world.utility_by_action` — the sentence is BUILT from those pairs and every
   host-side consumer (EU arithmetic, `respond_threshold`, the report's realized loss)
   reads the same function, so the wire declaration and the host arithmetic cannot drift
   (test-pinned by evaluating the sentence against the pairs). `u_correct`/`u_abstain`
   are the posterior's gauge constants (1.0 / 0.0); `u_wrong = u_bar["u_wrong"]`
   (fallback −9.0); `q = |u_bar["lambda_int"]|` (fallback 0.1); `g = |u_bar["kappa_att"]|`
   (fallback 0.02). Pairs: `gather → (u_abstain − g, u_correct − g)`,
   `ask → (u_abstain − q, u_correct − q)`, `abstain → (u_abstain, u_abstain)`,
   `respond → (u_wrong, u_correct)`. The v1 `internal: "think"` sentinel is GONE — the
   internal act died at the wire's step 5; no sentinel exists to dominate. Only the
   wire-accepted `parseSaid` subset is used (var, c, +, −, *, get, if, >, =; verified against the
   built engine in the B0 spike, 2026-07-19).

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

## 3. `latent@1` — the utility declaration **[v1 — historical]**

*(2026-07-19: `latent@1` is sections-4–6 machinery in `membrane-wire.md`, bracketed there as
"binding on nothing current"; `world.latent_utility_decl` is deleted. Items 8–12 record what
the v1 dual shadow declared.)*

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
14. **The `latent@1` verdict double-feed [v1 — historical; the `stream`-tagged tick died
    with the old wire — every verdict/outcome is now ONE untagged evidence tick].** One owner verdict emits two ticks at the
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
20. **Readouts are logged, never branched on.** `p1`/`entropy_bits` land in
    `ShadowChoice.readouts` (the reply minus its `act` assignment) and are copied
    verbatim onto the shadow's own `decide` record — `MembraneSession.decide` is a pure
    choice-relay over them; no adapter code path reads them back into control flow
    (observation, never a host-side decision fork). Test-pinned: two replies differing
    only in readouts yield the identical chosen action.
21. **The pty stdout shim — an engine defect carried host-side, until fixed there.**
    The re-derived `proplang-host`'s `hostMain` (`src/PropLang/Host.hs`) is
    `getLine`/`putStrLn` with no `hSetBuffering`, so GHC block-buffers stdout on a pipe
    and replies do not flush until stdin closes — measured in the B0 wire spike
    (2026-07-19); it breaks the wire's "one request, exactly one reply, synchronous" for
    any pipe-spawning host. `MembraneClient.spawn` therefore gives the child a PTY for
    stdout (a tty flips GHC to line buffering); the injectable-transport constructor is
    unchanged. The one-line fix belongs engine-side; this shim is carried until then and
    named in the demand ledger. The wire's escape-set constraint (`\"` `\\` `\n`
    only, `request_json` re-scan) is UNCHANGED on the re-derived wire and stays.

## 7. `respond` is unreachable — but NOT for the reason first published **[v1 analysis;
v2 status: EMPIRICAL, re-measured by the v2 shadow]**

*(2026-07-19: the arithmetic below is the v1 world's, against the retired govhost. What
carries over: the host-side pairs are unchanged (§2), `thetaPoints` is still the linear
`{0.1..0.9}` ladder in the re-derived engine (`src/PropLang/Enumerate.hs:118` at `7da274b`,
line never touched), so the gather-outbids-respond structure plausibly survives — but the
re-derived engine prices actions as E[ΔU] over its own learned transition model, and whether
respond stays unreachable under it is exactly what the v2 shadow's differential measures.
The B0/B1 smokes saw the engine fire `gather` at p1 0.5–0.63, agreeing with the host-side
argmax at those credences.)*

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

## 8. The 2026-07-11 field-smoke numbers **[v1 — historical field record, retired
govhost + dual forms]**

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
demand ledger (written to `$LIFE_AGENT_KB/membrane/report.md`), is life-agent's side of the
coordination contract with proplang. The old `HOSTS_PLAN` §9 A-gate is historical (that
roadmap was demolished by the re-derivation); the LIVE consumer is named in proplang's
`AGENT_PLAN.md` (§ K-ary observations, read at `7da274b:1256`): K-ary observation support is
"demand-gated on the life-agent differential — SURVIVES, UNCHANGED", and
`HOSTS_D_PACK.md:198` records "life-agent demand never materialized" — because the v1 shadow
never ran flag-on in production. The v2 shadow's accrued demand ledger is that materialization.
We never edit the proplang repo or the sibling credence-governor repo — this document and the
report are the whole of life-agent's side of that contract.

## 10. Deployment provenance

**Conformance binds to the wire SPEC, not the binary** (proplang's step-3 rider:
"host conformance binds to membrane-wire.md, never to GHC artifacts"): the v2 pin is
`membrane-wire.md` sections 1–3 as amended through step-10, read at proplang `7da274b`
(file sha256 `32ff980a0d83914bba07b190d1f53132307c354531f83f8c4fb9eac4f040b82f`). The
deployed engine at pin time: `~/.local/bin/proplang-host`, sha256
`16982176e13f0fa38c20980b3cd7f6705de65ec32bc161417a9835b2d19c7762` (built 2026-07-18 from
`7da274b`) — provenance, not conformance.
The engine executable is `proplang-host` (cabal target `proplang-host`,
`app/Main.hs → PropLang.Host.hostMain`), built from the same repo; its sha256 is recorded
live at every boot (`shadow._binary_sha256`, fail-open to "unknown") as PROVENANCE ONLY —
a rebuilt engine that still conforms to §§1–3 is a lawful upgrade, which is the point of
binding to the spec. The v1 pinned binary `proplang-govhost` sha256 `96ec3de7…` is
**orphaned** — its build target was retired at proplang's step-3 freeze and the hash is
unreproducible from master; the sibling credence-governor's live deployment still runs that
orphaned artifact (its repo's own concern, flagged to the owner 2026-07-19, not ours to
edit). Selection is `LIFE_AGENT_MEMBRANE_COMMAND` (absence = disabled = zero behavior
change on the bridge); forms via `LIFE_AGENT_MEMBRANE_UTILITY` (default and sole declared
form: `said@1`). An unknown form raises `ValueError` in `ShadowConfig.__post_init__` — at
construction, before anything is spawned or served — and the bridge's `_build_membrane`
catches it, prints it, and serves with the membrane DISABLED. *(The v1 correction note
stands: that validation was once aspirational; it is the code's, and test-pinned.)*

**The prod flip (prepared 2026-07-19, owner-gated on merging `feat/membrane-v2`).** The
sequencing is load-bearing: master's v1 world speaks the dead wire, so setting the env var
before the merge yields only a fail-open bad-hello loop (harmless to the answer path,
pointless as a shadow). After merge:

```ini
# ~/.config/systemd/user/life-agent-bridge.service.d/membrane.conf
[Service]
# proplang tag: re-derivation step-10, repo @7da274b
# binary sha256: 16982176e13f0fa38c20980b3cd7f6705de65ec32bc161417a9835b2d19c7762
Environment=LIFE_AGENT_MEMBRANE_COMMAND=%h/.local/bin/proplang-host
```

then `systemctl --user daemon-reload && systemctl --user restart life-agent-bridge.service`,
and verify `curl -s localhost:8798/ready` shows the `said@1` form `alive: true` under
`membrane.forms`. The
first live accrual (2026-07-19, worktree bridge :18798, real traffic): boot ok off 867 warm
source records, 2 decide ticks mirrored, differential enumerated its first real
disagreement (real `report` at leader-credence 0.98 vs shadow `gather` at its own p1 0.34),
and the `respond_unreachable_p1_ceiling` demand FIRED with both thresholds printed
(0.8559 vs-abstain cleared; 0.9942 whole-menu unreachable, binding competitor `gather`).
One first-spawn transient ("Extra data" JSON read glitch, non-reproducible, absorbed by
respawn 1/3 and clean thereafter) — WATCH on subsequent boots; if it recurs it will eat the
respawn budget and needs a root-cause pass.

## 11. The decision classification — "decisions ONLY by proplang" (rulings of 2026-07-19)

Owner rulings (the gold-standard roadmap plan of 2026-07-19, kept out of tree):
ALL non-deterministic/rule-based decisions on the answer path are made by the proplang
engine; credence is retired entirely (daemon :8799 + `core/brain.py` skin); proplang may be
adjusted based on need, and **every proplang change is first an issue on the public
`gfrmin/proplang` repo** (PII fail-closed: wire/grammar terms, synthetic examples only),
paired with a need-note here.

**The line:** deterministic computation (pure functions of inputs — parsing, scoring
arithmetic, folding a declared model, projecting a ledger) stays host. Anything that
**selects among alternatives** — a threshold fork, a rule gate, an ordering that changes
the outcome, a model-verdict-conditioned branch, an EU comparison — is a decision and
belongs to the engine. Model verdicts (the Qwen subject/route classifiers) are **sensors**:
observations with measured error; their decision-effect flows only through declared
likelihoods, never a host `continue`.

**Two buckets only.** (i) = engine decision, carries its migration stage (M0–M6 / E1–E3
per the roadmap). (ii) = sensor / deterministic computation, carries a one-line
justification. There is no third bucket; a fork found later is a doctrine bug.

### Bucket (i) — engine decisions (migrate)

| # | Decision (file:line at inventory time, 2026-07-19) | Today's mechanism | Stage |
| --- | --- | --- | --- |
| i-1 | Terminal act, P2 executor path — `core/executor.py:280` posts `{daemon}/decide`; effector obeyed at `run_pass:361` | EU-in-credence-daemon | M0 seam → M3 live |
| i-2 | Terminal act, P1 lookup — `core/lookup.py:705-719` `decide()` via `brain.optimise` over {report_j, hedge, ask_clarify, abstain, report_scoped} | EU-in-credence-skin | M0 seam → M3/M5 |
| i-3 | Terminal act, P1 narrative — `core/narrative.py:345-382` per-claim `brain.optimise` + host fold "report iff any included" | EU-in-skin + host fold | M0 seam → M5 (E1 per-claim acts) |
| i-4 | Weak-retrieval abstain gate — `scripts/ask.py:765` (`WEAK_SCORE_FLOOR=4.0`, `MIN_STRONG_HITS=1`) | threshold fork, pre-empts every engine | M0: becomes a declared retrieval-strength observation; engine may abstain, host may not refuse the question |
| i-5 | Executor-down ⇒ abstain — `scripts/ask.py:946-947` | liveness fork | M3: the declared engine-error safe default (abstain), a policy the register names, not a silent fork |
| i-6 | Family routing (lookup vs narrative) — `scripts/ask.py:774-807`, `core/lookup.py:461-488` `route_question` | model-verdict-conditioned branch | route verdict = sensor observation; the route CHOICE = an effort-allocation act (M5) |
| i-7 | Subject determinate exclusion — `core/subject.py:224-264` `apply_owner_filter` (`not_owner→excluded`, hard `continue`) | verdict-conditioned partition | `owner_verdict` = sensor; exclusion dissolves into the candidate's declared likelihood (M4); no candidate silently removed by host code |
| i-8 | Grow trigger + tier + stop-rule + cheapest-first order — `core/executor.py:88-103,154-173,219-261` | in-model comparison + host loop/ordering | E3 sequential decisions; tier menu = declared acts (B3) |
| i-9 | Grow re-ask gate — `core/executor.py:347-357` | host decides when to OFFER the grow block | E3 (engine-held "decide again") |
| i-10 | ask_clarify — `core/lookup.py:695` priced row, `_ORACLE_P=0.9` host constant | EU-in-skin; price is host | M3 menu (`ask` affordance exists); price from P(U) |
| i-11 | report_scoped / hedge choice — `core/lookup.py:675-698,807-842` | EU-in-skin over host-built utility rows | M5 (E1 outcome refinement, D1 exit) |
| i-12 | Grounding-gate USE — `core/lookup.py:536-540` (`continue` on ungrounded) | rule fork on observation admission | M4: whether an ungrounded quote is weak evidence is a likelihood declaration, not a host `continue` |
| i-13 | Retry/dispatch forks — `scripts/ask.py:1155-1162` executor-vs-inprocess; `core/executor.py:120-151` route-null→narrative, grow_lane branch | if-forks | NOT collapsed at M0 (re-staged at landing, see §12) — family routing in disguise; moves at M3+ |
| i-14 | Bridge fold-eligibility — `bridge/server.py:484-489,527` `folds = chosen_action=="abstain"` | rule fork on what enters calibration | M4 (what folds is part of the observation model the engine conditions on) |
| i-15 | (offline) adoption gate — `core/gate.py:243-283` `P(Δ>δ)≥level` | EU-in-host, frozen constants | stays host FOR NOW: it is the eval harness measuring the system, not the agent acting; FLAG — revisit when the engine can express meta-decisions |
| i-16 | escalate-to-frontier (new act, not in inventory) | absent today | B3: new affordance + lambda_cost latent (owner-elicited) |

### Bucket (ii) — sensors / deterministic computation (stay host, justified)

| # | Item (file:line) | Justification |
| --- | --- | --- |
| ii-1 | Retrieval scoring arithmetic (pkm FTS/BM25) | pure computation over the corpus; produces evidence, selects nothing |
| ii-2 | Qwen subject classifier — `core/subject.py:173-213` `owner_verdict` | a sensor with cached, measurable error; its USE migrates (i-7), the measurement stays |
| ii-3 | Qwen route classifier — `core/lookup.py:461-488` (the verdict itself) | sensor; its USE migrates (i-6) |
| ii-4 | `dedup_correlated` — `core/lookup.py:592-624` | deterministic collapse rule, declared as part of the observation model |
| ii-5 | Covariate factor computation — `subject_factor:220`, `time_factor:234`, `authority_for:369`, `era_split:330` | deterministic likelihood inputs; the engine weighs them |
| ii-6 | Narrative cell audit — `core/narrative.py:178-190` | deterministic classification feeding observations |
| ii-7 | `_competing_value_shape` + containment — `bridge/server.py:248-344` | deterministic observation-emission rule; FLAG: its conservative no-observation choice is a declared observation-model property, revisit under the joint-extract follow-up (PR #23 comment) |
| ii-8 | Currency source-of-truth override — `bridge/server.py:183` (`VOL.half_life`) | declared world knowledge (volatility table), not a choice among acts |
| ii-9 | GTD ledger folds, knowledge projection, demand logs | ledger projections — pure folds |

### Migration stages (the roadmap's M-ladder, for the Stage column)

M0 seam unification · M1 prod flip (owner) · M2 advisory (proplang beside credence,
disagreements logged) · M3 coarse menu live (abstain/gather/ask/respond) · M4 belief
migration (engine conditions on raw observations + measured reliabilities; `core/brain.py`
dies; :8799 decommissioned) · M5 fine acts (value-indexed report, scoped/hedge, per-claim)
· M6 sweep + CI enforcement (no-credence-import drift gate). Engine extensions: E1
categorical outcome over {candidates, NONE}; E2 per-question act sets (try
session-per-question handshake before touching RIDER 2); E3 sequential gather with an
engine stop-rule (pays down the §2/§7 myopic-information FLAG on the way).

Exit criteria for "credence fully retired" (checkable): no credence import in src/ or
scripts/ on the answer path; `answer-brain.service` decommissioned and `ANSWER_BRAIN_URL`
removed; exactly ONE act-committing seam, speaking only to proplang-host; every row above
either migrated or bucket-(ii)-justified; no EU regression vs the credence-era baseline on
the fairfight gate + loss ledger at n≥100 (the question factory is the prerequisite
instrument). *(Owner ruling 2026-08-25 — §18: reaching this exit is now MANDATORY;
refusal is retired as an endpoint, and the frozen bars pace the migration rather than
decide it.)*

## 12. M0 — seam unification: LANDED (2026-07-19)

`life_agent.core.seam` is the one act-committing function: `seam.commit()` takes either a
`SkinOptimise` request (a P1 in-process `brain.optimise` — the lookup family's response
decision and the narrative family's per-claim include/withhold), a `DaemonDecide` request
(the P2 executor loop's `POST {daemon}/decide`, over the caller's injected transport so the
membrane shadow mirror keeps wrapping it unchanged), or a **declared gate observation** —
and returns the committed act. Behaviour-preserving by construction: on every dispatch the
seam does exactly what the old call site did, byte-for-byte on the wire; the full hermetic
suite passed unchanged, and the fairfight baseline arm was re-run as the eval gate.

Status against the §11 rows:

- **i-1 / i-2 / i-3** — all three terminal-act commit sites now route through
  `seam.commit()`. The narrative host fold ("report iff any included") stays outside the
  seam: it is the exact powerset argmax under claim independence (the separability proof
  in `core/decide`) — deterministic given the per-claim acts, re-examined at M5/E1.
- **i-4** — the weak-retrieval abstain is now a **declared observation**
  (`GATE_WEAK_RETRIEVAL`) into the seam; the seam chooses abstain and the host obeys the
  returned act. The threshold *computation* (floor/min-hits arithmetic) stays host — a
  sensor producing the observation; the *fork* is data at the seam.
- **i-5** — the executor-down abstain is likewise declared (`GATE_EXECUTOR_DOWN`).
  Register note: against a down stack no other act is enactable, so the host asserts the
  seam's abstain rather than branching on it — an enactment constraint, not a second
  decision. The M3 obligation (the same declared safe default when the *proplang engine*
  errors on live traffic) remains open.
- **i-13** — NOT collapsed by this landing, re-staged: the executor-vs-inprocess dispatch
  fork and the route-null→narrative fork still stand outside the seam. They are family
  routing in disguise (i-6) and move when the route verdict becomes an observation the
  engine conditions on (M3+), not in a behaviour-preserving refactor.

Enforcement (prefiguring M6's drift gate): `tests/test_seam.py` fails if any module in
`src/life_agent` other than `seam.py`/`brain.py` calls `.optimise(`, or builds a
`/decide` URL outside `seam.py` — the decide path string is single-sourced as
`seam.DECIDE_PATH` (the shadow mirror recognises decide ticks by it). A fork found
outside the seam is a doctrine bug (§11), and now a red test.

## 13. M2 — advisory: LANDED (2026-07-19)

The roadmap's M2 deliverable — "proplang beside credence, `{proplang_act, credence_act,
agree?, EU delta}` published in the ledger; disagreements are the B4 need-note fuel" —
lands as **coverage completion plus pricing on the one existing record stream**, not a
second ledger: `shadow.jsonl` stays the single source, `scripts/membrane/report.py` stays
the pure reducer that publishes it. Nothing here touches the decision path, and nothing
here changes the engine or the wire — M2 requires zero proplang-side changes, so no
`gfrmin/proplang` issue accompanies it.

What landed:

- **EU delta on every disagreement** (`report.differential`, now priced under each form's
  own boot-recorded u_bar): `eu_delta = EU(would) - EU(real)` at the tick's own `p1` —
  the EU the engine believes the incumbent's choice left on the table, in the engine's
  own world — plus `disagreement_eu_by_class` aggregates per `real->would` class with
  `priced_n` honesty (a row with no `p1` readout or no boot u_bar is named unpriceable,
  never guessed or summed as 0).
- **Seam gate pre-emptions reach the shadow** — the M2 coverage the decide differential
  structurally cannot have: a question gated at the seam (`GATE_WEAK_RETRIEVAL`,
  `GATE_EXECUTOR_DOWN`) never produces a `/decide` tick, so until now the host's
  pre-emption was invisible to the membrane. Now `scripts/ask.py` mirrors each gate
  commit to the bridge's `POST /gate-support` (`shadow_mirror.mirror_gate` — fail-open,
  one-shot, short-timeout, fired after the abstain is already committed), the shadow
  consults every live form under the **faithful empty-evidence context**
  (`shadow.GATE_SUMMARY`: zero candidates, no posterior, zero grounded observations —
  which is exactly the state at both gates) and logs a `kind: "gate"` row: the gate
  name, the committed act (always abstain — the seam's gate contract), and what the
  engine would have done instead. The report's §2b reduces these per gate x would-action.
  A `would` other than abstain is M3's preview data: coarse-menu-live hands exactly this
  tick to the engine (i-4's "engine may abstain, host may not refuse the question").

Named coverage boundaries (decided, not discovered):

- **P1 lookup (i-2)** — not advisory-consulted: the in-process lookup path fires only
  under `--legacy` (never in production since the M1 executor default), and its decision
  context is already fully mirrored on the executor path it replaced. Revisit only if
  `--legacy` returns to production use.
- **P1 narrative per-claim (i-3)** — not advisory-consulted: a per-claim
  include/withhold does not reduce faithfully to this world's feature vocabulary
  (`summary_from_decision_event` already documents the narrative family degrading to
  "no candidates known"); a consult under a strained summary would manufacture
  disagreement noise, not evidence. Its migration stage is M5 (E1 per-claim acts);
  the loss ledger, not this log, sequences it.
- **Gate rows carry no `eu_delta`** — the engine's `p1` at the gate context prices the
  engine's OWN menu, but the host's abstain-by-policy has no EU claim to compare against
  (there was no competing engine act committed). The row's information is the would-act
  distribution itself.

E2 probe result (recorded here because M2's design depended on it): a fresh
session-per-decide against the live binary costs ~420ms end-to-end (spawn 0.4ms,
handshake + 14-round-trip replay ~370ms at ~26ms/round-trip, decide tick ~50ms); a
persistent session's marginal decide tick is ~50ms. Session-per-question handshakes are
viable at today's evidence volume but the replay grows linearly (~26ms per verdict), so
E2's per-question act sets need a warm-counts boot (or a rider change) before the
verdict stream reaches O(1k) — a need-note for B4, not a blocker for M2/M3.

## 14. M3 — the coarse menu live: LANDED (2026-07-19), flag-gated

The engine's coarse act — abstain / gather / ask / respond — IS the committed act on the
executor read-path when `LIFE_AGENT_MEMBRANE_LIVE=1`. Absence of the flag is byte-for-byte
the credence daemon's decision; **rollback is unsetting the flag**. No proplang/wire
change — the live consult is the same decide tick the shadow always sent, so no
gfrmin/proplang issue was needed.

**Prod flip: 2026-07-22, owner-authorized.** The flag is read CLIENT-side (the seam's
callers: `core/ask_client.py`, `scripts/ask.py`, `scripts/eval_executor.py`; the bridge
serves `/decide-live` unconditionally, and the mail→GTD timer never touches the ask
path), so the flip lives in the client environments: a `jarvis.service.d` drop-in plus
the repo's untracked `.env` (ask-live shells). First live decision confirmed the M3
override on the committed path: the daemon proposed report (leader credence 0.96); the
engine chose gather on every consult, hit `gather_exhausted`, and its own p1 (0.34,
binary world) fell below the respond threshold — committed act abstain, rendered as the
withheld "Held back" reply, `kind:"enact"` rows accruing in the shadow ledger. This is
exactly the "expected posture at flip" stated below when M3 landed — the honest
consequence of the young posterior, not a bug; the verdict stream (which the live path
keeps feeding) is what raises it.

**Rolled back: 2026-07-28, owner-authorized.** The flag is unset (drop-in removed, `.env`
line dropped, jarvis restarted; advisory decide-mirror resumed, no more `enact` rows). Not
because the flip regressed against its stated design, but because the fold that raised the
posterior (§17.1) turned out to raise a *population* dial, not per-question calibration —
so under the flag the engine committed `report` on essentially every question, a measured
negative-EU posture (§17.2). Rollback is the contain step of the containment plan (the
`contain-live-over-assertion` plan of 2026-07-22, kept out of tree); the flag goes back on
only after a pre-registered gate run, never another single-question smoke.

**The seam re-point (M0's promise kept).** `core.seam.DaemonDecide` gains an injected
`live` consult; `commit()` still posts the daemon `/decide` first (the posterior is the
engine's feature context AND the transitional value source), then commits the consult's
rewrite of the daemon view. The executor loop is unchanged — it reads one view shape
whichever decider produced it.

**The consult path.** Host closure (`membrane.coarse.live_decide`, its own
`LIVE_TIMEOUT_S=20s` transport) → bridge `POST /decide-live` → `MembraneShadow.
decide_live` (a reply-slot queue item; the worker still owns every session, bounded wait
`_LIVE_WAIT_S=10s`) → one engine decide on the PRIMARY form + the coarse mapping
(`membrane.coarse.map_action`) → the mapped view back to the seam. One `kind: "enact"`
row per consult on the one stream: `action` (engine), `daemon_effector` (what credence
would have done), `real_effector` (what the host enacted), `degraded` (named), the
summary, the readouts. A terminal enactment also feeds the reaction-binding summary map,
because under the flag the live path REPLACES the decide mirror (one engine, one consult
per tick — the wrapped post stays off).

**Transitional rules (each named, each with its exit):**

- **Agreement passes through** — engine coarse act == the daemon effector's coarse class
  (`world.REAL_TO_MEMBRANE`, now single-sourced in src; the report reads the same dict)
  ⇒ the daemon's finer selection stands (report vs hedge, which probe). Exit: M5
  fine-grained acts.
- **respond → host MAP** — the engine holds no per-candidate posterior (E1 not built);
  an engine respond over a daemon withhold asserts the argmax-credence candidate. No
  well-formed posterior ⇒ `respond_no_value` ⇒ abstain. Exit: E1.
- **gather → cheapest unapplied voi transform** (payload menu order — the k=0 walk's own
  precedent); guards never selected. Exhausted ⇒ `gather_exhausted`: argmax over the
  enactable remainder {abstain, ask, respond} at the engine's OWN p1 readout under the
  world's one utility source (`world.eu_by_action`); missing p1/u_bar ⇒ `no_p1` ⇒
  abstain. Exit: E3 (engine-held stop-rule).
- **Engine down/malformed ⇒ DECLARED abstain** — `seam.GATE_ENGINE_DOWN`, committed by
  policy at the seam with the posterior kept for an honest render; never a silent host
  fallback. Fires on: bridge down, membrane disabled, primary form dead, engine death
  mid-tick, full queue, either timeout.

**Named coverage boundaries (unchanged from §13, restated where M3 touches them):** the
narrative family and the P1 lookup stay outside the live path (route-declined questions
never reach `/decide`; `--legacy` never runs in production). The k=0 miss path (zero
extracted candidates) also stays host-held: the daemon requires k≥1, so there is no
decide tick to re-point; its grow walk is already the body's declared menu-order rule.
Staged with E2/M5.

**Report §2c** (`enactment()`): enact rows counted by engine action, by
`daemon->enacted` transition, and by degradation; they never enter the §2 differential
(an enactment is not a would-vs-did tick).

**Expected posture at flip, stated up front:** §13's ledger shows the engine's p1 ceiling
~0.34 on its 13-verdict evidence stream — under the flag the system will be
gather-then-withhold-heavy until verdicts accrue (respond's reachability bar is far above
0.34). That is the honest consequence of giving the act to a young posterior, not a bug;
the verdict stream (which the live path keeps feeding) is what raises it.

**Review round (PR #37, 2026-07-19):** no Critical/Important findings; flag-off inertness,
answer-path fail-closed layers, loop termination against an always-gather engine, the
reply-slot threading, and the EU arithmetic all independently verified. Two Minors, both
handled: (1) flag-branching wiring pins added for all three callers
(test_ask_mirror / test_ask_client / test_eval_executor_mirror); (2) a NAMED latent:
`coarse._gather` selects probes from the payload's transform menu without an assertion
that `run_pass`'s enactment branches recognise the name — safe under DEFAULT_TRANSFORMS
(all voi probes are `corroborate_*`), falls to a non-terminal `else: break` only if a
future voi transform ships an unrecognised probe (the same latency the daemon's own
schedule already has). Revisit when the transform menu next grows. Reviewer note kept
open-eyed for the prod flip: the single-threaded bridge serialises `/decide-live` behind
every other request — a stalled engine costs concurrent bridge callers up to
`_LIVE_WAIT_S` per tick; concurrency remains the deliberate Move-4 deferral.

## 15. E1 stages 0–1 — engine rebuilt at the W3/W4 wire; the categorical shadow world: LANDED (2026-07-22)

The E1 deliberation doc (`docs/candidates/e1-categorical-outcome.md`, owner-approved
2026-07-21) is the governing design; this section is its landing record for the first
two rungs of the §5.5 ladder.

**Stage 0 — the engine rebuild (a lawful §10 upgrade).** `~/.local/bin/proplang-host`
rebuilt from proplang local HEAD `1a0cea7` (W3 obs_arity + W4 full priced grammar +
R1, all engine-side; local master ahead of origin), sha256
`ebc06c81b954afb0f7b951548ed5d06d5b69cfc4e3f0f04b6597d55bcdd644d3`; the pre-W3 binary
kept beside it as `proplang-host-7da274b`. Byte-compatibility verified BEFORE the swap:
the existing binary world's handshake reply and a decide reply are IDENTICAL old-vs-new
(sorted-JSON compare), and all four `test_membrane_live.py` system smokes pass against
the new binary. Prod bridge restarted 2026-07-22; boot record carries the new sha256,
said@1 alive, 1364 source records replayed, respawn 0. The service drop-in's provenance
comment now reads `@1a0cea7`.

**Stage 1 — the categorical mirror (`membrane/categorical.py`), shadow-only,
flag-gated.** The world v3 declaration, against the LANDED wire only:

- **Outcome:** `obs_arity = K + 1` — atoms 1..K are the tick's candidates in candidate
  order, atom 0 the wire's own NULL emission (NONE). A 0-candidate tick is a NAMED SKIP
  (no lawful arity below 2, nothing to measure), counted at `stats()["cat"]["skips"]`.
- **Observations:** code-valued evidence ticks — the bridge's abstract-observation
  boundary already carries `reports` (the 0-based candidate index), so an extraction
  hit becomes `evidence: reports + 1`. Unmappable observations are a counted named
  exclusion (`n_obs_unmapped`), mirroring the `_VERDICT_Y` rule. No verdicts feed this
  world yet (the §4.1 bad-verdict exclusion stands until OB-12).
- **Acts:** one writable name, grid `[abstain=1, gather=2, ask=3,
  respond_1=4 .. respond_K=3+K]` — grid order normative, wait first. The engine's
  chosen `respond_j` names a candidate by VALUE — the M5 prerequisite.
- **Utility (§4.3, inside the shipped grammar — `if = - c var get`):** rows built from
  `world.utility_by_action` (ONE source with the binary world): abstain constant;
  gather/ask keep the declared myopic-perfect-information overvaluation, categorically
  split on y=0 (NONE side) vs any candidate code; `respond_j` pays `u_correct` iff
  `y = (get act) − 3`, else `u_wrong`. y is the PREDICTIVE NEXT OBSERVATION, not a
  latent truth — the doc's honest-semantics note carries into the row meanings.
- **Lifecycle:** SESSION-PER-QUESTION (OB-11's K-at-tick-0 shape): one fresh engine
  process per mirrored tick — handshake, this question's own evidence ticks (t
  advancing 0..n−1), one decide at t=n, shutdown. No cross-question learning in stage 1
  (the §5.1 two-layer split; shared channel counts arrive with the warm-counts
  companion, a named B4 need).
- **Supervision:** `ShadowConfig.categorical` (env `LIFE_AGENT_MEMBRANE_CAT=1`;
  absence = the default = BYTE-INERT — no reduction computed, no runner called, no rows
  written). The worker runs the cat episode strictly AFTER the binary forms on a decide
  item, and strictly AFTER the live waiter is released on an M3 `/decide-live` item —
  the mirror can never add answer-path latency. Any failure is one counted error
  (`stats()["cat"]["errors"]`), never a respawn (no persistent session exists) and
  never a dead binary form.
- **The ledger row (`kind: "cat"`, same shadow.jsonl stream):** question_id, k, the
  engine's action + j, `daemon_map_index` (does the engine's respond_j name the same
  candidate the daemon's posterior leads with — the M5 question), real_effector,
  readouts (NOTE: the landed wire's decide reply still carries only scalar `p1` = the
  predictive mass of ATOM 1 — the per-code readout is the §5.4(d) observability issue,
  not yet filed as landed), n_evidence, n_obs_unmapped, the handshake reply (`models`
  grows with K), latency, and the numeric summary. `CatSummary` is numbers-only by
  construction — no candidate string ever enters the mirror or its rows.
- **What stage 1 measures (the §5.6 risks, empirically):** whether `respond_j` ever
  clears its whole-menu bar under the wire's θ ceiling (0.9) at machine-speed evidence;
  whether R-D23's null-mass cap (1/(K−1)) binds on the over-abstention corpus; the
  per-tick cost of session-per-question at live K. These rows are also the §5.4
  evidence payloads for gfrmin/proplang (conformance report on the K-ary issue; OB-12
  per-channel demand; R-D23 heir demand) — aggregates only, per the PII rule.

**Cat rows never enter the §2 differential** (they are a different world's choices, not
the binary form's would-vs-did), and the offline report ignores unknown kinds by
construction. Stage 2 (M4) and stage 3 (M5) remain as staged in the doc.

**Review round (PR #38, 2026-07-22):** one Important, one should-fix, both folded in
before merge. (1) The cat episode runs inline on the ONE worker thread; with the
persistent sessions' `read_timeout_s` (300s) a wedged cat subprocess could have starved
live decides queued behind it (their callers time out at `_LIVE_WAIT_S` into the
engine-down abstain — answer-path degradation from shadow overhead). Fixed:
`ShadowConfig.cat_timeout_s` (default 20s, test-pinned `< read_timeout_s`) bounds the
mirror's own per-read wait; the residual worst case is one bounded stall per wedged
episode, and moving the mirror off the worker thread stays available if flag-on traffic
ever shows the bound binding. (2) `Callable[..., X]` aliases erased the two injectable
seams' signatures under the strict gate — both are now explicit `Protocol.__call__`s
(`categorical.SpawnFn`, `shadow.CatRunner`). Verified solid by the same review:
flag-off byte-inertness, worker survival on any cat failure, the t-convention,
counter thread-safety, numbers-only rows, and non-circular tests.

## 16. E1 stage-1 ledger analysis: the θ ceiling is not the binder — the gather row is (2026-07-22)

The stage-1 measurement run: one flag-off fairfight baseline pass over the v2 corpus
(`ff-v2-baseline-e1cat`, n=104, 101 ok + 3 infra-errored — the same class as m3on's
3/104), every daemon consult mirrored through the categorical world. **436 cat episodes
over 76 questions, 639 code-valued evidence ticks, 0 errors, 0 skips, 0 unmapped
observations** — the reduction was total on this corpus, and the eval side reproduced
the standing baseline (gold-in-candidates 57/77, asserts 24/25 correct), so the rows
were accrued under a normal, uncontaminated pass.

**Finding 1 — the categorical evidence stream BINDS.** The E1 claim was that code-valued
extraction hits at machine speed would move a posterior that verdict-starved binary p1
could not. Measured: at K=1 the predictive on the candidate atom climbs monotonically
with supporting evidence — p1 = 0.500 (0 obs) → 0.629 (1) → 0.703 (2) → 0.747 (3) →
0.775 (4) → 0.794 (5) → 0.848 (12) → 0.867 (18 obs, the run's global max) — asymptoting
exactly toward the wire's θ ceiling (0.9). The binary world's p1 ceiling on the same
traffic era was ~0.34 on 13 verdicts. The mechanism works.

**Finding 2 — at the observed maximum, respond BEATS ABSTAIN — the first time any
world's readout has cleared that bar.** Under the boot u_bar (u_wrong −5.94, u_correct
1.0), EU(respond_j) > EU(abstain) requires p_j > 0.856; the run's max 0.867 clears it
(EU +0.078). The binary world never came within a factor of 2.5 of this bar.

**Finding 3 — all 436 episodes chose gather, and that is ANALYTIC, not empirical.**
Under the myopic-perfect-information gather row (`world.utility_by_action`'s named
FLAG, register item 5), EU(gather) = 0.9656 − P(y=0) at the boot u_bar, so respond_j
overtakes gather only at p_j > 0.99504 − P(y=0)/6.94 — i.e. **p_j > 0.9942 even at the
feasibility limit** — while the θ grid caps any atom's predictive mass at ~0.9. The
whole-menu bar is unreachable BY CONSTRUCTION at any evidence volume; the §5.6(i) risk
("the θ ceiling may cap P(next=j) below respond's bar") is confirmed, but the binding
constraint is the deliberately-overvalued information row, not the ceiling: were gather
priced at its realized (not perfect-information) value, the observed 0.867 already
clears every remaining bar. This names E3 (engine-held stop rule) / proplang #15
(act-conditional outcome hypotheses) as the exit, exactly as staged — and it is what
the differential was built to measure, never to be tuned away silently.

**Finding 4 — session cost is linear in K via the model population, minute-scale at
K≳10.** models = 1601·K (one atom's said@1 sentence population per candidate); median
episode latency 71ms (K=1), 189ms (K=2), 514ms (K=3), 1.2s (K=5), 2.8s (K=7), 6.9s
(K=10); the two K=12 episodes ran 8.6s and 58.8s. Six episodes exceeded 20s (five at
K=10, one at K=12). `cat_timeout_s` (20s) never fired because it bounds a single read,
not the episode — the worst episode stalled the one worker thread for ~1 minute.
Shadow-only today (queue absorbed it, drops 0),
but stage 2 (M4, on the decision path) needs either a K cap with a named-skip, an
episode-level budget, or the warm-counts boot before minute-scale episodes can sit on
the answer path.

**Finding 5 — R-D23 cap-binding is UNOBSERVABLE without the per-code readout.** The
decide reply's scalar `p1` cannot show P(y=0), so whether the null-mass cap (1/(K−1))
binds on this 73.5%-over-abstention corpus is unanswerable from these rows. Filed as
gfrmin/proplang#20 (observability-only per-code readout: argmax code + its mass + null
mass); the R-D23 heir evidence (§5.4(e)) is blocked behind it.

§5.4 sends filed against this ledger: the OB-11 position (proplang#10 comment:
K-at-tick-0 suffices, session-per-question, bounded-reserved-tail not needed on our
account), proplang#20 (the per-code readout), the consumer conformance report on the
K-ary increment (proplang#9 comment), and the OB-12 per-channel demand evidence
(proplang#11 comment: dense fallible machine channel — 639 ticks/run, gold-in-candidates
0.74 — vs 14 owner verdicts lifetime under ONE shared θ). Aggregates only, throughout.

## 17. The Claude verdict channel — deliberative verdicts on the owner's behalf (2026-07-22)

Owner ruling (2026-07-22, in-session): **Claude Code — the in-session deliberative agent,
never a one-shot API call — may issue verdicts on answers on the owner's behalf**, and the
owner may overrule any of them; answer quality is **multidimensional** and objective;
conversion to a single score is **deferred**. This extends §11 ruling 1 (Claude-grade
deliberation is the gold standard) from adjudication to the verdict stream itself, and it
targets the system's named bottleneck directly: at the M3 flip the engine held **13
verdicted decisions lifetime** against 723 distinct unverdicted ones, and the live path's
gather-then-withhold posture (§14) is priced exactly by that starvation.

**The channel** (`core/claude_verdicts.py`, log at
`$LIFE_AGENT_KB/calibration/claude_verdicts.jsonl`, capture CLI
`scripts/claude_verdict.py`):

- **The record stores dimensions raw** — a closed vocabulary of independent objective bits
  (`correct` required; `complete`, `grounded` optional), plus `evidence` (what the
  deliberation read) and a free `note` (the agent's prose is cheap; the owner's stays the
  loop's one expensive resource). No combined scalar exists anywhere in the record: the
  deferred single-score question stays open.
- **The engine projection is `y = correct`** — "asserting the decision's leader candidate
  now would have been correct", exactly the fact `said@1` prices. This is a measured bit,
  not a scalarization. `boot_snapshot` merges the channel into `verdict_replay`
  (owner segment first, then the Claude segment); verdicts bind at the next boot replay
  (bridge restart) — **no live tick in v0**, disclosed.
- **Owner precedence is by source, not file order — and it belongs to an owner VERDICT,
  not a reaction row**: a decision whose latest owner reaction decodes through
  `verdict_y` takes the owner's verdict; every Claude verdict on it is superseded,
  whenever issued. An unrouted reaction (e.g. `good` on a `hedge`) contributes no owner
  verdict and blocks nothing (review round caught the presence-not-validity gate).
  Among Claude verdicts, latest per decision wins. Overrule therefore needs no new
  surface — the owner's existing one-bit reaction (`/react`, `/log_reaction`) IS the
  overrule.
- **Never the utility posterior.** P(U) is the owner's revealed preference; a Claude
  verdict is a truth measurement. The isolation is by construction —
  `core.reactions.load_reactions` reads a different file and is untouched.
- **A third reliability class** beside OB-12's two (proplang#11): denser than the owner's
  verdicts, more authoritative than the extraction ticks — today merged untagged under the
  one shared θ, which is additional demand evidence for the per-channel reliability ask
  already filed there.
- **Deliberated, never batch-derived.** Each verdict is the session agent reading the
  decision's actual leader candidate against the corpus. Mechanically projecting a
  grader's output through this log would re-create the extraction channel at owner-verdict
  authority — the CLI's contract forbids it, and the A-phase result (deliberative π\*
  92.3% correct, all failures adjudication-shaped) is the measured basis for granting the
  channel owner-behalf authority at all.

Scope v0: lookup-family decisions with a nameable leader (candidates + credences).
Narrative rows (no leader) are out of scope until the aggregate family's verdict shape is
designed. Question text for deliberation is recovered from the KB's eval question files by
`question_id`; ad-hoc live questions whose text is unrecovered are named as such, not
skipped silently.

### 17.1 First fold — measured (2026-07-22)

180 deliberated verdicts issued over the answer-brain decision log (every unverdicted
lookup decision whose question maps to a refereed eval question: 78 distinct
(question, leader-claim) pairs, one deliberation each, applied to the 180 decisions
asserting them). 140 correct / 40 incorrect. The 40 incorrect split into the two failure
shapes the A-phase named: corpus **distractors** (adjacent-field reads — the phone where
the fax was asked, a neighbouring row's IMEI, the volume number where the page range was
asked) and **extraction artifacts** (`io`, `]=`, `id`, `user`, `(852)` — a leader that
asserts no value at all). The multidimensional record earns its keep immediately on rows
where the two dimensions disagree: q2-007's leader `27,500` is `correct=1, complete=0` —
nothing false is asserted, but the question asked count *and* price per share. A scalar
verdict would have had to lie in one direction or the other.

The fold, measured end to end:

- `verdict_replay` 13 → **193** (49 y=0, 144 y=1); boot `n_source_records` 1463 → 1643.
- Same live question as the M3 flip smoke, same daemon proposal (leader credence 0.959):
  engine p1 **0.338 → 0.871**, and the committed act moved **abstain → report**. The
  engine still gathers on every consult and still exits via `gather_exhausted` (§16's
  analytic gather-row finding is untouched — that binder is E3/proplang#15), but its
  restricted argmax at exhaustion now clears the respond threshold instead of falling
  under it.

So the withhold posture recorded at the flip (§14) was verdict starvation, exactly as
priced — not a defect in the coarse mapping, and not a threshold that needed moving. The
channel is the lever E1 stage-1 said it was.

> **Correction (2026-07-28) — read §17.2 before relying on the paragraph above.** The
> claim "abstain → report is the channel working" was measured on a single question and is
> wrong as stated: the fold moved a population-level dial, not per-question calibration.
> The paragraph is preserved as-recorded; §17.2 states what the fuller measurement showed.

### 17.2 The fold moved a population dial, not calibration — the correction (2026-07-28)

§17.1's headline (p1 0.338 → 0.871, abstain → report) was confirmed on the same single
question the M3 flip smoke used. Planning the next step forced the measurement §17.1 should
have opened with — p1 *across* questions, and correctness *by* evidence bucket — and it
inverts the reading.

- **p1 does not track the question.** One post-fold smoke, four consults at retrieval-leader
  credences 0.870 / 0.965 / 0.944 / 0.959, returned p1 = 0.8683, 0.8706, 0.8706, 0.8706 — a
  0.002 spread across a 0.095 spread in the evidence. This is §11's own measurement
  (`p1` a rail, not tracking the leader) at the new operating point: 193 verdicts cannot
  identify 2,393 hypotheses over the 18-guard lattice, so the posterior sits at the marginal,
  which the fold moved from ~0.34 to ~0.87. The fold raised *one global number* past *one
  global threshold*.
- **Correctness is strongly bucketed, and the fold ignored it.** Over the 180 verdicts, the
  `correct` rate by leader-credence bucket is: lt50 0.50, 50–70 0.65, 80–90 0.79, ge90 1.00.
  The respond-beats-abstain break-even at the live `u_bar` is 0.8559, so at these rates only
  the ge90 bucket is EU-positive; 80–90 is already −0.46, 50–70 −1.43, lt50 −2.47. Weighted
  by the eligible population (ge90 is 100 of 342), asserting across all buckets — which the
  `gather_exhausted` restricted-argmax does, because the railed p1 clears 0.8559 everywhere —
  runs **≈ −0.58 EU/question vs abstaining**.
- **Why §17.1's smoke couldn't see it.** The M3-flip question (leader 0.959) is a
  ge90-bucket question — the one bucket where the engine is right 100% of the time. The
  instrument that confirmed the flip is precisely the instrument blind to its cost.

So §17.1's abstain → report is real and its cause diagnosis (the withhold was verdict
starvation) is also real — but "the channel is the lever E1 said it was" overclaims. The
channel produced clean, discriminative *data*; the engine cannot yet *use* the discrimination,
because the guard lattice is under-identified at n≈200. The four structural causes and their
owners (three are proplang's: the θ ceiling #19, the null-mass cap #21, the myopic-gather
overvaluation = the JP increment) are laid out in the containment plan (out of tree). The
immediate consequences:
the flag is rolled back (§14); the next flip is gated on a pre-registered gate run, not a
smoke; and the enact stream needs a priced detector so this class of regression is visible on
the ledger rather than in a plan (P1, being built alongside this correction).

### 17.3 The two standing instruments — enact detector (P1) and the calibration curve (2026-07-28)

§17.2 was a hand measurement in a plan. Both halves of it are now standing report sections,
so the regression is re-computable from the ledger, not re-derived by hand.

- **P1 — the enact realised-EU detector (§2d of the report, landed).** Prices the terminal
  `kind:"enact"` stream per question against the Claude verdict labels under the boot `u_bar`,
  with the `over_assertion` cell (daemon withheld, engine asserted, outcome wrong) as the
  headline. On the historical ledger it reads **0 over-assertion** — honestly, because every
  verdicted question flowed through the live path *before* the fold's report regime, so it was
  withheld. It is the forward instrument: it lights up if a verdicted question ever commits on
  the post-fold report path.

- **The per-bucket calibration curve (§2e of the report, landed 2026-07-28).**
  `calibration_by_leader_credence` bins the 74 verdict-grounded questions by their terminal
  decide row's `leader_credence` and prices each bucket under the world's one utility. This is
  where §17.2's −0.58 signal actually lives, and on the real data it is slightly worse than the
  hand estimate on this exact unit:
  - **respond-all realised EU = −0.688/question** vs abstaining (Δ −0.688/q);
  - engine-p1 spread **0.0031** (flat) while empirical correctness ranges **0.588 → 1.000**
    across the leader-credence buckets — §17.2's "population dial, not calibration" made a
    standing readout: the calibration probe. (The advisory p1 here sits at ~0.34, the marginal;
    the fold's ~0.87 was the live post-flip level — the *flatness*, not the level, is the
    finding.)
  - a leader-credence gate would have realised **+0.312/question** in-sample — the quantified
    target of P2 (narrow the guard lattice so p1 begins to track the leader per bucket). P2 is
    measured against this curve: after narrowing, the flat probe should widen and correlate.

### 17.4 The −0.688 was a respond-ALL counterfactual; the engine's IN-SAMPLE policy is ~neutral, pending P3 (2026-07-28)

Building P2 (narrow the guard lattice) forced the measurement §17.3 lacked: not the p1 the
daemon *logged*, but the p1 the folded engine *would commit under*. Replaying the real 193-tick
verdict stream through the actual `proplang-host` binary (the offline experiment
`scripts/membrane/lattice_replay.py`) and then probing `decide()` per verdicted question revises
the §17.2/§17.3 reading. **§17.3 is preserved above as-recorded; this states what the fuller
measurement showed — and, per the review of PR #50, its own limits.** Every figure below is
**in-sample** (each question's own verdict was folded before its p1 was probed and scored against
that same label); the held-out, pre-registered P3 gate is what confirms or refutes it, not this
replay.

- **Post-fold, the engine p1 TRACKS leader_credence (in-sample)** — 0.584 / 0.640 / 0.866 / 0.868
  / 0.871 across the lt50…ge90 buckets, correlating with the correctness 0.52 → 1.00. The
  individual-question p1 spread is **0.434** — vs the 0.003 §2e reads pre-fold, computed the same
  way (the five bucket *means* themselves span 0.287). The harness is faithful: it reproduces the
  §17.2 smoke's four values to the digit (leader 0.870 → 0.8682; 0.944/0.959/0.965 → 0.8706). The
  smoke's "flat 0.87" was **four high-bucket samples**; it never saw the 0.58 the low buckets sit
  at. Because each question's verdict was folded before probing it, the tracking is a *fit*, not a
  forecast.

- **§2e's "flat p1 = 0.0031" is a PRE-FOLD artifact.** All 74 terminal decide rows were written
  2026-07-22 07:48–08:05 — before the 180 verdicts were folded (~15:23 UTC that day). §2e's
  engine-p1 column therefore reads a cold session at the marginal 0.338; it does **not** reflect
  the folded commit-time p1. The `calibration_by_leader_credence` arithmetic is correct; its p1
  probe simply reads the wrong (pre-fold) session state, and the reader must not take "flat" as the
  engine's commit behaviour.

- **The −0.688 is the cost of respond-ALL, which the engine does not do.** At gather-exhaustion
  the host argmaxes `{abstain, ask, respond}` at the engine's OWN p1 (`coarse._gather` →
  `world.eu_by_action`), so respond fires only where p1 > 0.8559 — post-fold, the high buckets.
  Pricing the engine's *actual* commit policy (respond-iff-p1>bar, per-question) over the same
  190 ticks gives **+0.043 EU/question in-sample** (full lattice) vs the respond-all **−0.753/q**.
  So the respond-all magnitude is not what the engine commits — but the corrected figure is
  in-sample and awaits P3.
  **The enact ledger does NOT independently corroborate this** (an earlier draft of this section
  wrongly enlisted it, caught in review): 551 of the 555 live enacts are **pre-fold**, where p1 ≤
  0.1 at exhaustion makes the 82 daemon-`report` suppressions there automatic and mute about the
  post-fold policy — the same reason §2d reads 0. **Post-fold there are only 4 live enacts (3
  gather, 1 report)** — too thin to conclude anything, and the single `report` is one of them. The
  live enact stream is therefore neutral evidence here, not support.

- **P2(a) — "narrow the lattice to fix flat p1" — is disconfirmed as premised.** The full lattice
  is not flat post-fold; it already tracks (in-sample). Narrowing to `leader-credence` only *does*
  raise the in-sample policy EU to **+0.284/q** — but by *coarsening* into a ge90-only gate that
  refuses the break-even-region buckets, not by tracking better (it collapses lt50…80-90 to a
  single p1 0.681). So the residual lever is **conservative assertion-gating**, not lattice
  identification.

- **The one genuine residual:** the 70-80 and 80-90 buckets assert (p1 0.867 > the 0.856 bar) at
  only ~0.77 correct — below break-even, so a real (small) over-assertion there (−0.6/q on those
  ~48 questions). Because these buckets are already EU-negative in-sample, a held-out estimate can
  move the aggregate back toward the negative the containment finding named — which is exactly why
  P3, not this in-sample replay, is the arbiter. §17.2's error was attributing the respond-all
  counterfactual to the engine, not inventing this break-even-region cost.

**Caveats (so this does not overcorrect):** (1) **every number here is in-sample** — the held-out
P3 gate is the arbiter, and the EU-negative break-even buckets mean the held-out aggregate could
move back negative. (2) The replay folds all 193 verdicts at once in `boot_snapshot` order vs the
live incremental fold — if the engine's update is not order-exchangeable the end posterior could
differ (the exact smoke reproduction is strong evidence it does not). (3) Bucket n is 13–59;
correctness is the 74 Claude verdict labels; post-fold live enacts number only 4.

**Consequence — folded into P3, not a separate build.** P3's pre-registered, **held-out** gate run
must price the engine's *actual* commit policy (respond-iff-p1>bar over the folded posterior), not
respond-all, and watch the 70-80/80-90 break-even region; `lattice_replay.py` is its in-sample
seed. The P0 containment stands (it only returned to advisory and costs nothing) as the safe
default while P3 runs. What the fuller measurement changes is the *rationale* — the −0.688 was a
respond-all counterfactual, not the engine's commit policy — while leaving the **sign** of the
held-out regression for P3 to settle.

### 17.5 P3 — the held-out gate SETTLES it: the +0.043 was in-sample leakage; held-out the flip is EU-negative (2026-07-30)

P3 ran the pre-registered, **held-out** gate (protocol frozen blind at commit `f68eeef`,
`docs/membrane/p3-pre-registration.md`; harness `scripts/membrane/p3_gate.py`, **8** hermetic
tests atop `lattice_replay`'s 5 reused drift guards, `keyed_verdict_replay` drift-guarded
byte-identical to `boot_snapshot`'s projection).
It replays the same 193-tick / 84-question verdict stream through the real `proplang-host`, but
**grouped leave-one-question-out**: to price a question, its *entire* set of verdict ticks is
removed from the fold first. That single change — folding the label out before probing —
**reverses §17.4**.

**The result (n = 190 leader-credence-bearing ticks / 84 questions; artefacts under
`$LIFE_AGENT_KB/eval/p3/`):**

| variant (held-out) | EU/q @ engine Ū | EU/q under P(U) [q05, q95] | responds | reading |
| --- | ---: | --- | ---: | --- |
| **FULL (17 indicators)** | **−0.220** | **−0.526 [−1.021, −0.035]** | 90/190 | EU-negative — the whole 90% interval is below zero |
| leader-credence only | **+0.284** | +0.284 [degenerate] | 54/190 | the ONLY positive variant — responds *only* on ge90 (correct 1.00), so no u_wrong exposure |
| leader-credence + p-none | −0.383 | −0.689 [−1.184, −0.198] | 59/190 | p-none re-adds the noise that breaks the separation |

- **The §17.4 in-sample +0.043 was leakage.** Held-out, the FULL policy is **−0.220 at the
  engine's own Ū and −0.526 under the owner's P(U)** — worse than abstaining (0). The per-bucket
  table shows the mechanism directly: held-out, the 70-80 / 80-90 buckets sit at p1 ≈ 0.86 —
  **indistinguishable from ge90** — but their correctness is only 0.77, not 1.00. So the policy
  responds there (7/13, 16/35) at −1.06 / −1.13 EU/q, and the +1.00 from ge90's 54 correct
  responses cannot cover it. Folding each question's own verdict (§17.4) was *what created* the
  ge90-vs-middle discrimination; remove it and it collapses.

- **A3 — the differential adoption gate (FULL membrane held-out vs the credence baseline
  `ff-v2-baseline-m3off`, 74 joined questions, δ/level frozen in `core/gate.py`): FAIL.**
  P(Δ > 0.05) = **0.003** (gate ≥ 0.90), Δ̄ = **−0.338** [−0.826, −0.039]. The loss is carried by
  the disagreement region: **8 `report × abstain` questions at −2.75 EU/q each** — the membrane
  asserting where the baseline withholds; **3 of the 8 are confident-wrong**, the owner's −9 on
  those dominating the +1 on the 5 the membrane got right (against 3 `abstain × report`, −1.00).
  So the **A3 sign rests on those 3 confident-wrongs** — a thin, u_wrong-amplified margin, honestly
  the weaker leg. A1 does **not** rest on a handful: its negativity is 19 wrong of 90 responses
  across the low/mid buckets with the whole P(U) interval below zero, which is why A1 is the primary
  containment test and A3 corroborates it. This is proplang OB-12/#11's "single highest-leverage
  unexecuted measurement"; it is now executed, and it fails.

- **The coarsening (P2(a)) that §17.4 dismissed is the one thing that survives.** The
  leader-credence-only lattice is the only EU-positive variant held-out (+0.284/q, risk-free:
  its held-out p1 separates ge90 at 0.884 from every other bucket at ≈0.687, below the commit
  bar, so it responds only where correctness is 1.00). §17.4 called this "coarsening into a
  ge90-only gate, not identifying better" and treated it as a reason to dismiss P2(a); held-out,
  **coarsening IS the fix** — fewer, better-chosen guards identify at n≈190 where 2,393 hypotheses
  cannot. This does **not** license a flip: +0.284 is vs *abstain* (containment), not vs the
  baseline — the coarsened-lattice differential gate was **not** run (A3 used the FULL lattice, as
  pre-registered), and the win rests on this corpus's clean ge90 = 1.00 bucket (n = 54), whose
  robustness to corpus shift is untested.

- **Two utilities, stated.** The commit *policy* (respond-iff-p1>bar) runs under the engine's boot
  Ū (u_wrong ≈ −5.94, break-even 0.856) — what the flip would actually run. The *valuation*
  (A1's P(U) column, A3's gate) integrates the owner's true utility posterior (Ū u_wrong = −9.0).
  The engine booted **softer** than the owner's real aversion, so it responds *more* than the
  owner's utility warrants — which compounds the over-assertion, it does not mitigate it. Both
  reads (engine Ū: −0.220; owner P(U): −0.526) are negative.

**Verdict.** Per the pre-registration, **P3 does not flip `LIFE_AGENT_MEMBRANE_LIVE`** — and now
there is a decisive reason not to: the flip as it would ship (FULL lattice) is EU-negative
held-out and loses the differential gate against the credence baseline at P(Δ>0.05)=0.003. **P0
containment is vindicated on the evidence, not just as a default.** The re-earn path is not "flip
it back"; it is the coarsened (leader-credence-only) gate, and even that must clear its own
held-out differential-vs-baseline gate before any flip is considered — a measurement this run did
not make.

**The reversal count is the lesson.** −0.688 (respond-all counterfactual, §17.2) → +0.043
(in-sample actual policy, §17.4) → **−0.220 / −0.526 (held-out, §17.5)**. Three readings, each
from a rigor upgrade, the last two changing the *sign*. §17.4 named this exact risk ("every number
here is in-sample … the held-out aggregate could move back negative") and pre-registered P3 to
settle it — and it did. *In-sample is not a forecast*, confirmed the hard way, on our own number.

**Limits (up front).** One corpus (84 q / 190 ticks); verdict labels are the in-family Claude
channel (`correct` bit only) with owner precedence; per-bucket n = 13–59; the gate's
exchangeability-of-questions assumption is a proxy (as its docstring states). Two pre-registered
deliverables did **not** run and neither bears on the flip: **A4** (the membrane-independent
typed-vs-monolithic `run_eval --gate`) needs a read-write catalogue handle and a live service held
the lock; and the **loss-ledger-vs-oracle/π\*** arm was not produced (the A3 disagreement
decomposition already gives the where-it-loses picture). Both are deferrable. The coarsened-lattice
differential gate is the named next measurement, not run here. One pre-reg count reconciles: it
estimated 10 non-v2 questions; the run shows **8 membrane-only + 2 that produced no act** (no
leader-credence-bearing probe tick) = 10, with the load-bearing **74 joined** matching the pre-reg
exactly.

### 17.6 P3b — the coarsened-lattice differential gate: under the owner's CURRENT utility, the coarsening cannot respond at all (2026-08-17)

**Question → resolution → why.** *Does the coarsened (leader-credence-only) lattice — the one
EU-positive held-out variant of §17.5 — clear its own differential gate against the credence
baseline?* → **No: FAIL, P(Δ>0.05)=0.205, Δ̄=−0.078 [−0.312, +0.276] — and it FAILS BY TOTAL
ABSTENTION: 0/190 held-out ticks commit, 74/74 joined questions abstain.** → *Because the
owner's utility moved under it.* Pre-registered blind in
`docs/membrane/p3b-coarsened-pre-registration.md` (+ Amendment 1, also blind), harness
`scripts/membrane/p3_gate.py --gate-variants`, artifacts under `$LIFE_AGENT_KB/eval/p3b/`
(variant-suffixed; §17.5's FULL record untouched).

**The reversal this time was in Ū, and it was caught by the freeze.** The first execution's
FULL variant did **not** reproduce §17.5 (6/190 committed vs 90/190) and was **voided
mid-variant before any coarsened Δ existed** (`eval/p3b-VOID-ubar-drift-20260817/`, console
only). Diagnosis: §17.5 ran under the boot Ū then in force, **u_wrong = −5.94 (commit bar
p1 ≥ 0.856)**; the owner's 2026-08-06 u_wrong elicitation (stated −9) moved the boot Ū to
**u_wrong = −8.83 (bar 0.899)**. Same engine, same 193-tick ledger. The engine byte-compat
check that the amendment then froze — FULL under §17.5's *exact* Ū via the harness's
reproduction-only `--u-bar-override` — **reproduced §17.5 to four decimals** on the rebuilt
`1a0cea7` binary: FULL −0.2203 / 90 of 190, leader-credence-only +0.2842 / 54, +p-none −0.3834 /
59, A3-FULL P=0.001 Δ̄=−0.337 (`eval/p3b-engine-repro-20260817/`; §17.5's 0.003 / −0.338 —
the residual is the narrower P(U) from the three 2026-08-17 elicitation lines, disclosed). So
the binary is not the confound, and every §17.5 number stands as the 2026-07-30 reading.

**The reading, both arms under the CURRENT Ū (one bar, so they compare):**

| held-out arm (bar 0.899) | committed | policy EU/q @Ū | A3 vs baseline (74 joined) |
|---|---:|---:|---|
| FULL (17 indicators) | 6/190 | −0.279 | **FAIL** P=0.056, Δ̄=−0.201 [−0.366, +0.063]; typed 73 abstain + **1 wrong report** |
| leader-credence-only | **0/190** | 0.000 | **FAIL** P=0.205, Δ̄=−0.078 [−0.312, +0.276]; typed 74 abstain |

Baseline on the same 74: 24 correct reports, 2 wrong, 48 abstains (answer rate 0.35).

**Why the coarsening cannot respond now — the finding.** Under §17.5's Ū the coarsened arm
committed 54 `ge90` ticks at empirical correctness **1.00**; under the current Ū it commits
**none**. Those same ticks' engine posteriors sit **between 0.856 and 0.899** — the engine's
`ge90` belief is shrunk below the bucket's empirical rate by its guard prior, and the owner's
stated −9 wrong-cost puts the commit bar exactly above it. Two honest readings of one fact:
(a) the coarsened lattice's +0.284 was never *robustly* positive — it lived in a 0.04-wide
window of p1 that one elicitation line closed; (b) the engine is *conservative* relative to
the ledger — a policy that could have asserted 54 correct answers asserts zero because its
belief (not the world) says 0.87. That is a **belief-shrinkage** question for the engine
(E1's per-candidate posterior; a prior the guards can update faster), not a utility question:
the owner's utility is right by construction, and the fix is to earn a sharper p1, never to
loosen the bar. Both predictions the pre-registration recorded blind held: FAIL on both arms,
**by abstention** (a different mode from §17.5's FAIL-by-over-assertion), on a small
disagreement set (25–26/74).

**Verdict.** **The coarsening is closed as a re-earn route on this ledger under the owner's
current utility.** No flip; P0 containment stands. Note the FULL arm's own picture changed
too: at the corrected bar its over-assertion largely vanished (1 wrong report, not §17.5's
pattern) — the guard lattice's failure mode is now *reach*, the same lever the §8 gate names.
The re-earn path is therefore **not lattice surgery**: it is E1 (a per-candidate posterior the
engine can sharpen from the same evidence) and, in the meantime, the credence-daemon typed
policy — which on the same day cleared to Δ̄=+0.180 on the §8 gate (foundations §14, run 6) —
is the decider that is actually improving.

**Limits.** One ledger (193/84, unchanged since 2026-07-30); 74 joined; the `ge90 = 1.00` fact
is that ledger's; the p1 window is read from the harness's per-tick rows, not from a
sensitivity sweep over u_wrong (which would be a *reading of a Ū the owner did not state* —
declined, named).

## 18. Owner ruling (2026-08-25): the migration is MANDATORY — gated-mandatory, deferred

**Question → resolution → why.** *Is the proplang migration still an adopt-or-refuse
decision?* → **No. The owner ruled (2026-08-25, superseding run-14 conferral ruling 5's
"future gated adoption" phrasing): the endpoint is fixed — proplang WILL replace credence
at the decide seam, and a refusal by frozen criteria is retired as an endpoint.** → *The
bars pace the swap; they no longer decide whether it happens.*

What "gated-mandatory" binds, precisely:

- **The frozen bars all stand, un-loosened**: the 0.899 p3 commit bar (§17.6 — the bar is
  the owner's utility, and the fix is always a sharper p1, never a softer bar), the
  §8-class priced differential gate with blind pre-registration, and the hard clause (no
  lever ships while it makes a named wrong-commit class worse).
- **A FAIL at any gate means iterate, not park**: engine work (the E1 per-candidate
  posterior remains the named re-earn path — §17.6's verdict), a fresh pre-registration,
  and a re-run. Iteration under this loop is standing delegation, EXCEPT a second
  consecutive FAIL on the *same* frozen criterion, which stops for an owner ruling — a
  repeat-FAIL means the criterion itself is contested, and only the owner re-rules a
  frozen criterion.
- **The terminus is §11's exit criteria** ("credence fully retired", checkable), reached
  via the migration ladder through M6. Adoption happens when the bars pass — no separate
  adoption keypress remains.
- **Deferred**: the migration is NOT a completion condition of the 2026-08-25 completion
  programme (Stages 1–2–4 close without it); it opens as committed follow-on work after
  the programme's completion audit, and still after collapse-M7, so the seam migrated is
  the collapsed one.
- **Unchanged**: nothing in tree may presuppose the swap until it lands; the shadow keeps
  accruing; the proplang repo is never edited from here — engine asks are filed as issues
  on the public proplang repo.

> **Correction of record (2026-08-31, `r40-arc-c-preconditions`).** The "the shadow keeps
> accruing" clause above **is not true on this machine** and has not been since
> **2026-08-10T16:06:47**. Measured the day Arc C opened: no `proplang-host` binary exists
> here at all (§15's `ebc06c81…` is absent), the shadow is env-disabled, the stream ends at
> 6 683 records, and the local proplang checkout has moved `1a0cea7` → `94fd4eb`. Why it stops on that
> date is **open** — the production-role move was 2026-08-30, twenty days later, so that is
> not the cause. The ruling itself is untouched; what changed is the first rung. Arc C opens
> on **P0** (the engine, pinned, byte-compat-checked per §15's own procedure) and **P1**
> (accrual restored with the 21-day gap declared as a segmentation boundary — `M-14`), and
> reaches §17.6's E1 re-earn path only after. See `GD-10`.
>
> **Second correction (2026-09-01, `r43-selection-contract`; `GD-11` → `GD-12`).** The bars
> above could not have been read at all against the current engine, and the cause was **our own
> world declaration**. At HEAD, `Membrane.chooseEU` builds one environment from the
> *challenger*, so both sides of every comparison read the same utility row and per-action
> **levels** never enter — only beliefs can differ, and this world's beliefs cannot: `act` is
> one of exactly two names (with `t`) in the 19-name namespace with no guard row, so no
> enumerated hypothesis conditions on it. Every option ties and the option-space head fires.
> Declaring a **`clock`** row routes selection to the substitution path (`pickWire`) and the
> world becomes utility-driven at HEAD on 5 of 5 cases, three of whose winners are not the
> head; an **`act` guard row** is a second, independent repair restoring act-conditionable
> belief. Until both land in the declaration, **a §18 bar compares arm A's policy against a
> constant `abstain`.** The engine's own register carried the mechanism as `OB-24` throughout
> (`M-23`).
>
> **Third correction (2026-09-01, `r45-evidence-path`; `GD-16`).** Three things above are now
> measured rather than supposed, and two of them are corrections to the corrections.
>
> 1. **Why the stream stops is no longer open.** The first correction's *"why it stops on that
>    date is open"* is answered, and its framing was wrong: the stack did **not** keep running.
>    `decisions.jsonl` has a hole from **08-10 to 08-16** and resumes on **08-17** — stack and
>    shadow stopped **together** on 08-09. The shadow alone never returned, because its only
>    enablement was an environment variable held in no `.env`, no unit and no dotfile, and
>    absent from `.env.example` and `packaging/`. The 08-17 restart restored everything that
>    was written down. The former production box is still reachable and still carries
>    `ebc06c81…` byte-identically, so nothing was lost with the role move — which remains, as
>    `GD-10` suspected, not the cause. `.env.example` now documents the variable.
> 2. **The `act` guard row does NOT by itself restore act-conditionable belief.** The second
>    correction states it as "a second, independent repair restoring act-conditionable
>    belief". Measured: adding the guard row while `act` stays in the menu leaves `p1`
>    **byte-identical** across all four pinned acts on both arms. Act-conditioning needs the
>    guard on a **discriminating** grid (thresholds *between* the act values — a `[0.5]` grid
>    copied from the indicator rows cannot separate values 1–4) **and** `act` removed from the
>    menu, and that world has no writable name left, so it cannot decide. `act` is either
>    written or observed, never both.
> 3. **"A §18 bar compares arm A's policy against a constant `abstain`" is repaired but not
>    dissolved.** r44's clock made the engine track its declared utility; r45 then measured
>    what that utility fires: `gather` on **250 of 250** replayed rows, because `gather` is
>    the argmax across **96–98%** of the credence range under both the declared defaults and
>    the deployed `u_bar`. So the bar now compares against a near-constant **`gather`**
>    instead of a near-constant `abstain`. This is `world.utility_by_action`'s own flagged
>    bake-in — information priced as myopic perfect information, "OVERVALUES information,
>    deliberately and namedly", with the docstring naming it an **empirical** question whether
>    the v2 shadow dissolves the v1 gather-bar pathology. **It does not.** Note the raw
>    affordance is not what an enactment reads: `coarse.map_action` sends `gather` to the
>    cheapest unapplied VOI transform and, when exhausted, to a restricted argmax over
>    `{abstain, ask, respond}`. A bar reading the raw affordance compares against a constant;
>    one reading through `map_action` **need not** — but whether it actually varies is
>    **unmeasured**, because it depends on each payload's transform menu and on how often
>    the menu is exhausted, and r45 measured neither. Stated as the open quantity it is
>    rather than as the reassurance it would be convenient to be. **Which surface a §18 bar
>    reads, and what that surface's distribution actually is, are now preconditions for
>    reading it** — registered here rather than discovered mid-run.
