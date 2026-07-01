# Ask as a general Credence `Connection` — offloading the decision, deleting the adapter

> **Status: deliberation (frozen-layer). Not built.** This rewrites the answer-brain daemon's
> decision core against the engine's general three-channel contract. Confer before building
> (taildrop → pixel6). Realises the owner directive (2026-07-01): *offload as much of the Bayesian
> machinery to the Credence engine as possible.* Supersedes `docs/autonomous-recall-design.md` (the
> hand-priced `:grow` menu — now an engine-scheduled actuator) and subsumes `aggregate-family-design.md`
> §1a–§3 (per-slot extraction — now sensor emission).

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
price `re-extract`; retrieval features low ⇒ price `retrieve-wider`. The `grow[mechanism]` choice
falls out of `net_voi` over two actuators *informed by the sensors* — not hand-code.

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

## 4. The open design fork (the confer's core question)

Two factorings of the decision; the confer picks one (or a hybrid):

- **(A) Generalised categorical.** Keep the answer-brain's `candidate_posterior`/`terminal_decide`;
  widen only the observation kernel to consume arbitrary named features and widen `schedule_decide` to
  price gather actuators. Smallest change; the candidate belief and the meta-decision stay in one
  categorical EU. Risk: the observation kernel generalisation (noisy-channel → feature-conditioned) is
  real daemon work and could regress parity.
- **(B) Split belief / meta-decision.** Candidate identity stays an app-side categorical; the
  *report / abstain / gather / which-gather* meta-decision is re-expressed as a **structure-BMA over
  the sensors** (`structure_bma`/`structure_decide`, the governor's shipping path), so the engine
  learns *which sensors predict a good decision* and VOI-gates the gather. Maximal offload (the
  meta-decision is the governor's proven verb); the candidate categorical is the only app-specific
  piece left. Risk: the two-belief coupling (candidate confidence must feed the meta-decision) needs a
  clean seam.

Lean **B** — it is the larger offload and reuses a shipping, battle-tested decision verb — but it must
be shown to preserve **0 confident-wrong** (the meta-decision must never report when the candidate
categorical is unsure). Settle at confer with the governor integration as the reference client.

## 5. Parity-safe cutover, and what stays deferred

**Build alongside the adapter behind a flag.** The general Connection path and the narrow adapter both
run; cut over only on **parity** (the Connection path reproduces the adapter on today's CORRECT set)
**+ conversion** (the six extraction-misses via sensor emission, the four retrieval-misses via the
`retrieve-wider` actuator) **at 0 confident-wrong**. Then delete the adapter (Phase 3).

**Deferred — coincides with the engine's own roadmap.** Sensor *invention/adoption beyond emitted* and
a novel-feature **proposer** are the engine's *expansion* class, deferred to its **Exploration-Budget
arc** (`docs/exploration-budget/master-plan.md`, ratified 2026-06-28, not started). The current
residual needs only rich sensors + priced gather (the *compression* class, shipping). The LLM proposer,
when wanted, wires in as a §6.5 prosthetic connection — the seam `sem_map`/`route`/narrative already
are. The aggregate family (Σ/recall/missing-mass, `aggregate-family §5-§8`) and Arc A (temporal belief)
stay in their named slots.

## 6. Questions for the confer

1. **The factoring** (§4): (A) generalised categorical vs (B) split with `structure_decide` over
   sensors. Does B preserve 0-CW, and is the candidate↔meta coupling clean?
2. **The sensor list** (§3): lean toward *more*. Which retrieval/extraction features are cheap to emit
   and plausibly predictive? Any that leak (citation-shape, gold-adjacency)?
3. **Belief shape:** does the queried construct stay a categorical, or become a *sensor* that selects
   among per-slot posteriors?
4. **Template reuse:** how much of the credence-governor's `structure_bma`/`structure_decide` client
   and any credence-pi `Connection` wiring is liftable (compose-don't-rebuild)?
5. **`re-extract` as actuator:** the reverted stronger-extractor was a *fallback gated on withhold*
   that the wrong-slot candidate suppressed (`aggregate-family §2`). As an engine-priced actuator over
   an *honest empty-slot sensor*, does that failure mode close?
