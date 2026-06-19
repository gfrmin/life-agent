# Scaling documents → answers, the Bayesian way

*Status: design note (2026-06-19). Motivated by the answer-executor run; extends
[`bayesian-foundations.md`](./bayesian-foundations.md) and the answer-executor plan. The owner's
prompt: "think bigger — how to scale the path from documents to answers in the best way possible,
including using real-world knowledge like 'a DOB doesn't change, a phone number does'."*

## The question

A query asks for the **current value of an attribute `A` of a subject `S`** ("my phone number" →
`A` = phone, `S` = owner). The corpus is a pile of documents, each a noisy, **time-stamped**
witness. We want the best-calibrated answer — a posterior over the current value, then a decision
under the owner's utility — and we want it to **scale**: useful from few documents, gate-safe
(zero confident-wrong) always, better as evidence accrues.

The answer-executor run (21 questions, real Opus) gave us the empirical ground this note stands on:

- **The gate holds** — zero owner-graded confident-wrong, including the founding sins (the stale HK
  address and `+852` mobile were *withheld*, not asserted).
- **But it is inert** — `CORRECT 0/18`. Two causes, neither the decision math:
  1. **Recall.** 13/18 answerable questions had the gold *in the corpus* yet the local edge produced
     **zero observations** → declined to narrative. Retrieval/extraction, not decision.
  2. **The joint edge is currency-blind.** Where Opus ran, it read *faithfully* — got the DOB
     (`0.96`) and partner ID right, surfaced the stale HK address/phone — but its **self-report does
     not encode currency**: it *dated the permanent facts and left the stale values undated*, and was
     **underconfident (`0.40`) on a correct read**. So neither its confidence nor its `as_of`
     separates current from stale.

The separating signal was none of those. It was the **construct's volatility**: a DOB is permanent,
a phone is not. That is the thread to pull.

## The generative model

Treat each attribute as a **time process** `A_S(t)`, observed through documents:

- **Volatility.** `A_S(t)` changes at an attribute-specific rate. A DOB/national-ID is *constant*
  (`λ = 0`). A phone, address, employer, salary *drift or jump* at their own rates. This is a prior
  on the process, **indexed by the construct**.
- **Observation.** A document `d` at time `t_d` witnesses `A_S(t_d) = v_d` through a noisy channel:
  extraction reliability `ρ_edge`, subject attribution `s` (is this *S*'s value or a relative's?),
  authority. The channel is the edge (per-chunk local model, whole-doc joint model, …).
- **Query.** We want `P(A_S(today) = v | {(v_d, t_d)})` — and then the EU-maximising act.

Inference falls out cleanly:

- **Constant attribute** (DOB, ID): every witness observes the *same* value; evidence **pools** with
  no temporal discount. More agreeing documents → higher credence. A confident read should commit.
- **Volatile attribute** (phone, address): a witness at `t_d` attests `v_d`, but the probability it is
  **still current** decays with `today − t_d` at the attribute's rate. The freshest document
  dominates; an old one is weak evidence for *now* but strong evidence for *then* — i.e. the
  **scoped** claim ("as of `t_d`, `v_d`"). This is exactly `time_factor = 0.5^(age / half_life)` —
  **but the half-life must be per-construct**, not the single global constant the code uses today.

## Two axes, two sources of knowledge

The decisive move is to **separate two axes the current fold conflates**:

| axis | question | source of knowledge |
|---|---|---|
| **extraction reliability** `ρ` | did the edge read what the document *attests*? | **calibration from outcomes** (never self-report) |
| **currency** | is the attested value still true *now*? | **volatility prior** (elicited world knowledge) |

The HK address is the worked example: Opus **reliably read** a document that genuinely says "…Staunton
St" — that is a *correct extraction of a stale fact*. Folding it as "the edge was wrong" punishes the
edge for the world changing. The Bayesian-clean account: **`ρ` is high (faithful read); currency is
low (volatile attribute, old document) → scope or withhold.** Two different mechanisms, two different
knowledge sources.

### Currency is an elicitable world-knowledge prior — and it's cheap

We do not need data to learn that phones go stale faster than addresses. The model already knows it.
Asked for the half-life (years to a ~50% chance the value changed) it returns, blind to our corpus:

```
date_of_birth 9999 · national_id 9999 · passport 10 · email 10
mobile_phone 8 · home_address 7 · employer 4 · job_title 3 · marital_status 15 · annual_salary 2
```

This is the **"a DOB doesn't change, a phone does"** intuition, quantified — a per-construct prior
that drives the recency decay. It is a *prior*, not a fact (a specific person may move yearly), and
the corpus's own evidence (how often this subject's value actually changes) can refine it. But it
makes a volatile-fact answer **gate-safe from zero calibration data**: a years-old phone is scoped
or withheld because the *attribute* is known to churn, not because we waited to learn it.

### Reliability is *not* elicitable — it must be measured

The symmetric temptation is to ask the model "how reliable are you?" and use that as `ρ`. **No** —
two reasons, one principled, one measured:

- **Principled:** a model rating its own correctness is self-serving (optimism bias); the gate's whole
  job is to distrust confident-but-wrong, so its defense cannot be the suspect's own testimony.
- **Measured:** in this very run the joint edge reported `0.40` on a *correct* read and `0.72–0.78` on
  *stale* ones — its self-confidence is **non-monotone with correctness**. Calibrating on it directly
  would be calibrating on noise.

So `ρ_edge` stays a **calibration curve fit from owner/oracle verdicts** (the existing
`core/calibration.py`), pessimistic until earned. Its honest consequence — see below — is that
*permanent-fact* commits (where currency is a non-issue and only `ρ` gates) wait on accrued evidence.

## The honest arithmetic (why N≈4 commits nothing — and why that's correct)

With the owner's `10:1` `u_wrong`, the assertion floor is `p* ≈ 0.852`. A calibration curve fit from
`k` outcomes at a confidence bin returns, under any non-gate-fitted prior, roughly `(α + n_correct) /
(α + β + n)`. At `n ≈ 4` even an *all-correct* bin reaches only `≈ 0.62–0.67` — **below the floor**.
To clear `0.852` honestly takes ~17 corroborating outcomes. So at this data scale **the executor
withholds everything, and must** — frozen-blind forbids picking the prior that makes this eval pass.
This is not a bug; it is the safety margin being paid for in the only currency allowed: evidence.

The corollary is the design's load-bearing asymmetry:

- **Volatile facts become gate-safe immediately** — the *volatility prior* (no data) scopes/withholds
  stale values. The founding mobile-number sin is closed today.
- **Permanent facts commit only as reliability accrues** — DOB/ID have no currency risk, so only `ρ`
  gates them, and `ρ` is honestly thin. They are also the *lowest-risk* commits (a DOB cannot go
  stale; the disagreement check + grounding guard attribution), so the cost of waiting is small.

## The pipeline as one Bayesian DAG (and where each piece lives)

```
route(question) ─► (construct, subject, VOLATILITY)         ── world-knowledge prior (elicited, cached)
   │
retrieve(query) ─► documents                                ── the recall lever (13 declines)
   │
extract(doc…)   ─► {(value, t_d, ρ_edge)}                   ── local per-chunk OR joint whole-doc, picked by VOI
   │
temporal fold   ─► P(A_S(today) = v)                        ── per-construct half-life decay + pooling
   │
decide(U)       ─► report | report_scoped | withhold        ── EU under Ū, the p* floor
   │
calibrate       ─► ρ_edge curves                            ── from owner/oracle verdicts (never self-report)
```

Every arrow is an **edge the executor VOI-schedules** (run another transform vs. answer now). This is
the adopted system-design DAG, made specific to the documents→answers demand.

## Build slices (ordered by value)

1. **Time-awareness in the joint fold** — *landed.* `decide_joint` carries the route's `time_indexed`
   and decays through `time_factor(as_of, time_indexed)`; a permanent read survives, a stale volatile
   one attenuates. (The binary `time_indexed` is the degenerate case of slice 2.)
2. **Per-construct volatility** — replace the single global half-life with the elicited per-construct
   half-life (a cached `volatility(construct) → half_life` derivation, world-knowledge prior; the
   corpus refines it). Generalises slice 1 from `{0, ∞}` to the real spectrum.
3. **Joint-returns-source dating** — the joint edge reads a blob and loses the reliable *document*
   date (it offered no `as_of` for the stale values). Have it return the supporting citation `[n]` →
   map to the hit's artifact → project the real `doc_date` → decay on *that*, not on the model's
   missing self-report. This is what makes slice 2 bite for the joint edge.
4. **Recall** — the dominant near-term lever (13/18 declines on in-corpus gold): semantic rerank /
   embeddings so the local edge produces observations at all. Fattens the calibration bootstrap too.
5. **Reliability accrual** — dogfood; let owner/oracle verdicts grow `ρ_edge` until permanent-fact
   commits clear the floor. The slow, honest one.

## Discipline (unchanged)

Frozen-blind: **volatility** priors come from world knowledge, **reliability** from verdicts — neither
from the gate. The `p*` floor is the owner's risk knob (`u_wrong`), set blind. Stale ≠ unreliable:
currency is the temporal model's job, faithfulness the calibration's. Everything on the ledger
(volatility is a cached, content-addressed derivation like any other). Compose, don't rebuild — this
is policy + priors over the existing route/extract/fold/decide/calibrate seams.
