# Ask as a general Credence `Connection` — offloading the decision, deleting the adapter

> **Status: conferred (frozen-layer) — ruling recorded 2026-07-01; ready to build.** This rewrites the
> answer-brain daemon's decision core against the engine's general three-channel contract. The confer
> returned (§4): the A-vs-B fork was a **false binary** — the meta-decision **factors by derivability**
> (report/abstain stays an exact app-side threshold; only the gather VOI is offloaded), making 0-CW
> *structural*. Realises the owner directive (2026-07-01): *offload as much of the Bayesian
> machinery to the Credence engine as possible.* Supersedes `docs/autonomous-recall-design.md` (the
> hand-priced `:grow` menu — now an engine-scheduled actuator) and subsumes `aggregate-family-design.md`
> §1a–§3 (per-slot extraction — now sensor emission).

**Phase-0 baseline (confirmed 2026-07-01, clean run, quota restored):** CORRECT **6/18**,
**0 confident-wrong** (gate held). Residual is **extraction-dominant**: 6 extraction-misses
(q-005, q-007, q-010, q-012, q-013, q-015 — the `aggregate-family §1a` six exactly), 5
retrieval-misses (q-004, q-006, q-009, q-014, q-020), 1 pooling (q-011); RIGHTLY_WITHHELD:
q-016/017/018. This is the parity+conversion target (§5). (Master baseline; the `voi-scheduler`
branch's retrieval wins are unmerged/owner-only and are subsumed here as sensors + `retrieve-wider`.)

## 1. The contract, and where it already lives

Credence SPEC §6 is the brain/body boundary: *the brain receives sensor signals (feature vectors) and
sends effector signals (action symbols); it is causally independent of the world given its sensors.*
§6.3 names the registration unit — a `Connection` offers **named features (sensors)**, **named actions
(effectors)**, and **declared events** (propositions over the feature space the brain may condition on).
§6.5: an **LLM is a prosthetic connection** — it registers features it can provide and actions it can
perform; the brain decides when to call it by EU. This is the whole contract: *you provide the
vocabulary (sensors, actuators) and the values (reactions); the brain provides every decision built
from them.*

It is not aspirational — it ships on the skin wire (protocol v1.9, `apps/skin/protocol.md`):
- `create_state` takes `features` + `action_space` (register sensors + actuators; protocol l.240,308).
- `structure_bma` / `structure_observe` / `structure_decide` (v1.2, l.467–534): the engine builds a
  structure-BMA over feature buckets and returns the VOI-gated EU decision — *"the client ships only
  feature buckets and utility scalars; the arithmetic stays engine-side."* This is the
  **credence-governor's** decision path (proceed/block/ask).
- `logistic_reaction` (v1.4, continuous-τ v1.9, l.930): folds a binary owner reaction into a latent
  belief. **life-agent already uses it** (`core/utility.py:279–285`) — the utility (u_wrong) channel is
  *already engine-side*; the only gap is batch-vs-live timing.
- `routing_*` (v1.5): EU-max model routing — the sibling that prices model choice over the wire.

`answer_brain.jl:28-30` imports the same engine primitives (`condition`, `optimise`, `net_voi`) these
verbs are built on — **one engine, no separate build**.

## 2. What the answer-brain reinvents vs. what the engine provides

The daemon is a **narrow categorical adapter** hand-coded on top of the general engine:

| answer-brain hand-codes | file | the engine's general form |
|---|---|---|
| fixed `Obs(atom, group, authority, subject, time)` | `answer_brain.jl:53-59` | a named `features::Dict{Symbol,Float64}` merged from connections (§6.3) |
| corroborate-only `DEFAULT_TRANSFORMS` menu | `executor.py:49-64` | any `action` in the `action_space`, priced uniformly by `net_voi`/`optimise` |
| `:grow` excluded; body cascade | `answer_brain.jl:253`, `executor.py:126-144` | a gather **actuator** the engine schedules like any other |
| pre-computed `u_bar` dict, post-hoc fold | `server.py:290`, `reactions.py` | `logistic_reaction` folded live per decision (already the machinery) |
| `owner_scoped` string routing; family/narrative fork | `executor.py` | a 0/1 **sensor** the brain conditions on; or an LLM **proposer** (§6.5) |

**Nuance that scopes the work (do not over-read the offload):** `structure_decide` is the *governance*
decision shape — a binary proceed/block/ask over **discrete** feature buckets. The answer-brain's
decision is a **categorical over dynamically-extracted candidate values + NONE**, then
report_j/hedge/abstain. That is a *legitimately different* decision shape; the offload is **not** "swap
in `structure_decide`." It is: generalise the *observation shape* to named sensors, register the gather
*actuators*, fold *reactions* live — all on the shared primitives — and keep the candidate categorical
as the app's belief. (Whether the report/abstain/gather *meta*-decision factors onto `structure_decide`
is the open fork, §4.)

## 3. The offload — the three channels for ask

**Sensors — emit everything measurable (the cardinal rule; this *is* the extraction fix).**
Generalise `Obs` → `features::Dict{Symbol,Float64}`. Per decision tick the body emits **every slot as
its own sensor** (`:slot_<name>_present`, `:slot_<name>_confidence`, `:slot_<name>_grounded` for *all*
slots in the chunk, not just the queried one) plus every retrieval feature (`:rank`, `:fts_score`,
`:native_script_match`, `:doc_date_recency`, `:subject_match`, `:on_topic_coverage`, `:authority`,
`:era_split`). Dormant sensors read harmlessly; a richer set is a larger space the brain reasons over.
**The crux:** with all slots emitted, the queried slot's emptiness is an *honest sensor reading* — the
confident wrong slot can no longer *mask* it (the escalation-suppression bug, `aggregate-family §2`).
And the sensors let the engine **distinguish the miss**: other slots populated + queried slot empty ⇒
price `re-extract`; retrieval features low ⇒ price `retrieve-wider`. Which one fires is the **gather
VOI**, priced by the engine over the miss-type sensors (§4's B half) — not hand-coded. The per-slot
sensors thus serve **two consumers**: the queried slot's own candidate posterior (the terminal half,
whose honest `p_none` is what the wrong slot used to mask) and the miss-type sensors (the gather half).

**Actuators — register the gather moves.** Add `retrieve-wider[s]`, `re-extract[c]` (keep
`corroborate[ρ]`) to the `action_space`; the engine schedules them by the *same* `optimise`/`net_voi`
as corroborate. The body's `execute!` performs the retrieval/extraction and returns success/`false`
honestly — a precondition failure is feedback, not a substitution. Delete the body's grow cascade and
the never-written `grow_value`.

**Reactions — fold live, not batch.** The `logistic_reaction` machinery is already engine-side
(`utility.py`); the change is to fold verdicts *through the decision call* against a live `u_wrong`
posterior rather than recomputing a frozen `u_bar` dict in a side batch — keeping the passivity /
e-process firewalls (abstain-rows clean-fold; report-rows recorded-not-folded).

**The brain supplies the rest** — the belief over the queried slot's candidates + NONE, the
VOI-schedule of gather-vs-answer, the utility — from primitives it already runs.

## 4. The resolved factoring (confer ruling, 2026-07-01)

The A-vs-B fork below was a **false binary**. The meta-decision is not monolithic; it **factors by
derivability**, and drawing that cut correctly dissolves both the 0-CW risk and the `g`-calibration
problem at once.

**Report/abstain stays exact and app-side (the "A half" — non-negotiable).** It is a closed-form
EU-max on the candidate posterior: `report_j` iff `p_j > −u_wrong / (u_correct − u_wrong)` (the
`−p/(1−p)` threshold). Routing *this* through a structure-BMA over sensors would ask the engine to
re-discover, from `:rank`/`:fts_score`/`:slot_present` correlations, a boundary already held in closed
form — a learned surrogate for an exact computation (unsound by the R2 *derive-don't-learn* standard),
and the precise origin of the 0-CW hazard. So `terminal_decide` — the threshold rule — stays
**untouched**; the only terminal-side change is that the candidate posterior is built **per queried
slot**, so its `p_none` is honest rather than masked by a confident wrong slot (the extraction fix, §3).

**The gather VOI is the learnable half (the "B half").** `g_mechanism(sensors) = P(this actuator
recovers the answer | sensors)` is a posterior over the miss-type sensors — exactly the `g`-term
`autonomous-recall-design.md` was stuck hand-calibrating. *That* belongs in the governor's
`structure_bma`/`structure_decide`. B decides **gather-or-not and which-gather; it never decides
report.**

**0-CW is therefore structural, not something to demonstrate empirically.** The learned belief does
not own reporting, so no path through it can emit a confident-wrong. A gather either produces more
evidence (whereupon the exact threshold re-decides) or returns `false` honestly (whereupon the exact
threshold decides on what it has). The only way to reintroduce the hazard is to let B swallow the
terminal decision — which is what the draft's "B" did, and exactly what is refused.

**The trade-off dissolves.** The terminal half reuses the answer-brain's existing `terminal_decide`
untouched (A's "smallest change"); the gather half reuses the governor's shipping `structure_decide`
client (B's "largest offload"). New code is only the **seam**.

**The seam (this answers q3).** One-directional: emit the candidate posterior's uncertainty summary
(`p_none`, max-credence, entropy) as **sensors** into the gather structure-BMA; nothing crosses back
into the threshold. The queried construct is **both** a categorical (it owns reporting) **and** a
source of sensors (it feeds gather) — two roles, no tension; the two beliefs meet only in the gather
VOI.

**Two honest caveats (the live work items — §6).**
1. **The `g`-prior is demoted, not dissolved.** At cold start `g_mechanism` sits at its prior (= A's
   hand-set constant) and sharpens only as gather outcomes fold in. `autonomous-recall-design.md`'s
   open math survives as the *prior*, not the answer — budget it; the data now corrects it. It still
   strictly dominates A (a permanent constant).
2. **Gather-outcome instrumentation is the one genuinely new work item** (beyond the seam and the
   actuators' `execute!`): after `re-extract`/`retrieve-wider` fires, did the queried slot become
   populated with a candidate that led to a correct answer? Fold that as a **structure-observe**
   stream — the price of making `g` learned rather than guessed. B earns its keep specifically on the
   *which-gather* discrimination (re-extract vs retrieve-wider); the miss-type sensors (§3) already
   carry that signal — *other slots populated + queried empty* = extraction, *retrieval features low*
   = retrieval. The *whether* is mostly settled by candidate uncertainty, so optimise the sensor list
   (q2) for discriminating miss **type**, not for re-deriving how unsure the belief already is.

> Superseded fork, kept for the record: **(A)** widen the categorical's observation kernel to consume
> features and price gather in one EU; **(B)** re-express the *whole* report/abstain/gather
> meta-decision as a structure-BMA over sensors. The ruling takes **A's terminal half and B's gather
> half** — not one or the other.

## 5. Parity-safe cutover, and what stays deferred

**Build alongside the adapter behind a flag.** The general Connection path and the narrow adapter both
run; cut over only on **parity** (the Connection path reproduces the adapter on today's CORRECT set)
**+ conversion** (the six extraction-misses via sensor emission, the five retrieval-misses via the
`retrieve-wider` actuator) **at 0 confident-wrong**. Then delete the adapter (Phase 3).

**Deferred — coincides with the engine's own roadmap.** Sensor *invention/adoption beyond emitted* and
a novel-feature **proposer** are the engine's *expansion* class, deferred to its **Exploration-Budget
arc** (`docs/exploration-budget/master-plan.md`, ratified 2026-06-28, not started). The current
residual needs only rich sensors + priced gather (the *compression* class, shipping). The LLM proposer,
when wanted, wires in as a §6.5 prosthetic connection — the seam `sem_map`/`route`/narrative already
are. The aggregate family (Σ/recall/missing-mass, `aggregate-family §5-§8`) and Arc A (temporal belief)
stay in their named slots.

## 6. Confer outcome (resolved 2026-07-01) and the residual work items

1. **The factoring** — **RESOLVED.** Not A-vs-B; factor by derivability (§4). A owns the exact
   terminal threshold; B owns the gather VOI. 0-CW is structural.
2. **The sensor list** — refined: optimise for discriminating miss **type** (extraction vs retrieval),
   *not* for re-deriving candidate uncertainty (the closed-form threshold already holds that). Still
   lean toward *more*; still audit for leakage (citation-shape, gold-adjacency).
3. **Belief shape** — **RESOLVED.** Both: the queried construct stays a categorical (owns reporting)
   *and* emits an uncertainty summary (`p_none`, max-credence, entropy) as sensors (feeds gather). The
   two beliefs meet only in the gather VOI; the seam is one-directional.
4. **Template reuse** — the governor's `structure_bma`/`structure_decide` client is the reference for
   the **gather half only**; the terminal half reuses the answer-brain's own `terminal_decide`.
5. **`re-extract` as actuator** — **RESOLVED (yes).** The reverted stronger-extractor was a fallback
   gated on withhold that the wrong-slot candidate suppressed (`aggregate-family §2`). As an
   engine-priced actuator over an *honest empty-slot sensor*, the suppression cannot recur — but its
   `execute!` must invoke the **stronger** extraction capability, not re-run the same extractor
   (per-field alone did not convert the six — [[per-field-extraction-disconfirmed]]; the gather is
   what converts).

**The two live work items** (from §4's caveats): (a) the `g_mechanism` **prior** (cold-start = A's
constant; `autonomous-recall-design.md`'s open math is now the prior, not the answer), and (b)
**gather-outcome instrumentation** as a structure-observe stream (did the gather populate the queried
slot → correct answer?) — the price of making `g` learned rather than guessed.
