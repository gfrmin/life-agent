# The Bayesian agent (the ground-up spine)

*Status: architecture (2026-06-19). The apex frame the owner named: "a Bayesian agent — a prior
model of the world, appropriately updated through observations taken after actions; a range of tools
it can choose from; updating its world model rationally (including metareasoning) from consequent
observations; making me happy by giving the best answers possible — correct and appropriate, but not
too expensive in time or money." This doc makes that spine explicit so every other piece
(`bayesian-foundations.md`, `bayesian-documents-to-answers.md`, the answer-executor) is an instance
of it, not an accretion. It operationalises the `PRINCIPLES.md` kernel (EU-maximising agent over a
trustworthy transform DAG); it does not replace it.*

## One line

The agent holds a **belief about the world** `W`, has a **toolbox of actions** `A`, **updates `W` by
Bayes** from the **observations** its actions yield, and chooses actions — including *which* to run
and *when to stop* (**metareasoning**) — to maximise the **owner's expected utility** `U`: a correct,
appropriately-hedged answer, cheap in time and money.

Formally a bounded-rational POMDP: `(W, A, O, U, π)`. The five parts, each grounded in a seam.

## W — the world model (prior, rationally updated)

A **structured belief**, not a scalar — a joint posterior over the latents that actually move an
answer:

- **The owner's attributes as time-processes** `A_S(t)` — what we are usually asked for (DOB, phone,
  address, ID…). The value *and* its trajectory.
- **Fact volatility** `λ_A` — how fast each attribute changes. **World-knowledge prior** (elicited:
  DOB→∞, phone→8y, salary→2y), refined by corpus evidence. *(`bayesian-documents-to-answers.md`.)*
- **Tool reliability** `ρ_edge` — how often a tool reads what a document attests, as a function of its
  self-reported confidence. **Calibrated from verdicts, never self-report.** *(`core/calibration.py`.)*
- **Corpus coverage** — what the corpus contains and where (is the answer reachable? the retrieval
  model). Today implicit in retrieval; deserves to be an explicit belief (it is what distinguishes
  "I don't know" from "it isn't written down").
- **The owner's utility** `U` itself — a belief about the owner, not a constant. *(`core/utility.py`,
  the utility posterior; the agent has *no* utility of its own.)*

The "ground-up" demand on W: these are scattered today (a curve here, a prior there). They are one
belief. The agent should be able to answer "what do I believe, and how sure am I?" coherently —
because that is what every decision reads.

## A — the actions (the toolbox)

Two kinds, one currency (cost = time + money):

- **Information actions** move `W`: `retrieve`, `rerank`, `gather`, `extract@{local, haiku, sonnet,
  opus}`, `derive` (any pkm transform), `ask_human` (the slow, dear, high-authority oracle). Models
  are *actions*, picked by value — "use haiku/sonnet/opus, whatever earns its cost."
- **Terminal acts** end the episode: `report`, `report_scoped` ("as of `t`, `v`"), `hedge`,
  `ask_clarify`, `withhold`. *(`core/lookup.decide`, the EU decision under Ū.)*

Every action is an **edge on the DAG** (`system-design.md`); choosing one is the agent's move.

## O — the observation model (how actions update W)

An action `a` returns an observation `o` — chunks, a `(value, confidence)`, a verdict — through a
**noisy channel whose fidelity is the tool's reliability** `ρ_edge`. Bayes does the rest:
`W ← P(W | o)`. Three things this makes precise:

- **Calibration lives here, not in the decision.** `o`'s likelihood is `calib_edge(confidence)`, so an
  overconfident tool informs `W` weakly. This is why the gate is defended by calibration, not by the
  scheduler.
- **Reliability and currency are different updates.** A faithful read of a stale document updates the
  *value-then* strongly and the *value-now* weakly (the volatility decay). Stale ≠ unreliable.
- **The owner's verdict is the apex observation.** correct/stale/wrong updates `ρ_edge`, `U`, and the
  attribute belief at once. It is the most expensive observation (the owner's attention) — elicit one
  bit, spend it well.

## U — the utility (what "best answer" means)

Owner happiness, as a belief about the owner:

```
U(answer) = correctness  (assert iff true; a stale value asserted as current is wrong)
          + appropriateness (scope when only the past is known; withhold when unsure; right grain)
          − cost (time + money: a cheap right answer beats an expensive one)
```

`p* = w/(1+w)` from `u_wrong` is the assertion floor (the owner set `10:1`). Cost is first-class, not
an afterthought — "not too expensive in time or money" is *in* the objective, which is exactly what
makes metareasoning necessary.

## π — the policy (metareasoning, first-class)

At each step, choose the action of greatest **expected utility**, where *running another tool*
competes with *answering now*:

```
π:  a* = argmax_a [ E_W[ U after observing o(a) ] − cost(a) ]
    commit the best terminal act when no information action's value clears its cost.
```

This is **metareasoning** — reasoning about which computation to run and when to stop — and it needs
a **meta-level model**: *will this tool likely confirm, contradict, or withhold, given what I already
believe?* (the executor plan's "disagreement model", `F1`). VOI is high exactly where the agent is
both unsure and a tool can move it. Bounded rationality is the point: a cheap, certain question gets a
cheap answer; an expensive, uncertain one earns Opus or the human. The meta-level itself must be
cheap relative to the stakes — don't deliberate a dollar's worth over a cent.

`brain.value(state, actions, preference)` is the EU hinge this policy turns on (it exists; the
executor is its first caller).

## The loop

```
demand ─► [π: VOI over actions under W,U] ─► act ─► observe ─► update W ─► (repeat)
                                                                   │
                                          no action's value > cost ▼
                                                         terminal act ─► owner verdict ─► update W
```

Every arrow is content-addressed and on the ledger (`system-design.md`): the episode is auditable,
and the verdict re-enters as the highest observation. This *is* "updated through observations taken
after actions."

## What exists, mapped onto the spine

| part | exists today | seam |
|---|---|---|
| `W`: utility | yes (posterior) | `core/utility.py` |
| `W`: reliability | yes (calibration curves) | `core/calibration.py` |
| `W`: volatility | designed, slice 1 landed | `decide_joint` + `bayesian-documents-to-answers.md` |
| `W`: attributes / coverage | implicit (re-derived per query) | retrieval + `lookup` |
| `A`: tools + terminals | yes (edges + decide) | `joint_extract`, `gather`, `probes`, `lookup.decide` |
| `O`: update | partial (verdict→U, verdict→ρ) | `reactions`, `calibration` |
| `U` | yes | `core/utility.py` |
| `π`: policy | **v0 only** (hand-coded escalation) | `core/executor.py` |
| EU hinge | yes (uncalled until the executor) | `core/brain.value` |
| ledger | yes | `decisions`, `derivations`, `events` |

## The three gaps to ground-up coherence (the real work)

1. **`W` as one belief, not fragments.** Make the world model a first-class object the policy reads —
   especially a *coverage* belief (so "not written down" is a stated posterior, not a silent miss).
2. **`π` = VOI/metareasoning, not a ladder.** `core/executor.py` is a hand-coded escalation (cheap →
   floor → joint). That is a *scaffold*. The agent's policy is `argmax` of `value − cost` through
   `brain.value` under the meta-level (disagreement) model — the executor becomes π's v0 and is
   replaced edge-by-edge, eval-gated. This is the §16 governor, now with a reason to exist.
3. **Close the update loop.** One coherent `observe → update W` so a verdict sharpens reliability,
   utility, *and* the attribute/coverage belief together — not three side-channels.

## The incremental path (each slice a step toward the spine, eval-gated)

Compose, don't rebuild (`PRINCIPLES §4`); sequence by VOI, measured (`§9`). Near-term, in order of
value:

1. **Recall** (`O`/coverage): semantic rerank/embeddings so the local tool yields observations at all
   (13/18 in-corpus declines) — and the coverage belief that names true gaps.
2. **Per-construct volatility** (`W`): the elicited half-life as a cached derivation; joint returns
   its source citation so currency decays on the real document date.
3. **Reliability accrual** (`O`): dogfood; verdicts grow `ρ_edge` until permanent-fact commits clear
   the floor honestly (frozen-blind — no gate-fitting).
4. **π as VOI** (the spine): replace the escalation ladder with `brain.value` over `{tools} ∪
   {terminals}` under the disagreement model; the runtime confident-wrong floor stays as a named
   safety override. This is where "Bayesian agent" stops being aspirational.

## Discipline

EU under the *owner's* `U` (the agent has none of its own). Frozen-blind priors — volatility from
world knowledge, reliability from verdicts, neither from the gate. Cost is in the objective:
metareasoning must be cheap relative to the stakes. Everything on the ledger. Never fabricate a
verdict. The confident-wrong floor is a runtime override on `π`. Compose over the existing seams; pkm
stays frozen.
