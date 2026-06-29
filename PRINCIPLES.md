# PRINCIPLES — the stable, cross-phase principles of life-agent

This is the single source of principles for the whole repository. Other documents defer to it
and do not restate it: [`CLAUDE.md`](./CLAUDE.md) is the operating manual for an agent working
here, [`ROADMAP.md`](./ROADMAP.md) holds the plan and status, [`README.md`](./README.md) the
public pitch. PKM's own foundations live in
[`docs/pkm/SPEC-PRINCIPLES.md`](./docs/pkm/SPEC-PRINCIPLES.md) and are referenced, not
duplicated. This document is not phase-scoped; changing it is a deliberate act, not a side
effect of a feature.

**§1. The kernel.** A **knowledge base created from DAGs of trustworthy transformations**, and
a **personal assistant — the "life agent" — making rational, utility-maximising decisions based
on it**. Two layers: the KB *derives* (pkm); the agent *decides* (life_agent). Every component
belongs to exactly one. The agent is, exactly, a **belief**, a **utility**, and a **decision
space**, acting by **argmax expected utility** — under the Bayesian paradigm every autonomous
agent is this one machine, and ours differs only in *which* utility it serves (the owner's) and
*which* decisions it ranges over. **credence** holds the belief and runs the optimisation; the
body supplies the utility and the decisions. credence + (our utility, our decisions) *is* the
agent — not a library it calls (§16).

**§2. The KB layer — trustworthy transformations.** Trust is structural, not aspirational.
Every derived artifact is **cited** (traceable to source bytes), **content-addressed**
(identity = hash of inputs — SPEC-PRINCIPLES §2), **idempotent** (re-running is a no-op),
**independently auditable** (small, generic, chained steps — never one mega-transform), and
**composable** (a transform may consume another transform's output — pkm SPEC §18.7). The
recording layer makes no truth claims; reliability is assessed downstream (SPEC-PRINCIPLES §4).

**§3. The agent layer — decisions over the KB.** The agent answers, prioritises, and —
eventually — acts, to maximise the owner's expected utility. It reads the KB; it never silently
mutates it. Its decision space is not only how to *answer* (report / scope / hedge / ask /
abstain) but **which transformation to run next** — retrieve deeper, rerank, gather, extract
with a stronger model, derive a new artifact, route to another model — each an action with a
cost and a *modelled, uncertain* outcome, ranked by value of information (§16). Believing,
computing, and answering are one EU ranking over one space; only outward **write-actions** wait
on the goals/utility model. The destination is decision-theoretic autonomy:
value-of-information-driven ask / proceed / block. That is why **credence** is the brain and not
optional, and why a **goals/utility model is owed before any autonomous write-action**.

**§4. Prime directive — compose, don't rebuild.** ~90% of the building blocks exist in the
owner's own projects. New work is integration plus thin layers. Before writing anything, check
whether a producer, a transform, or an existing script already does it.

**§5. Polyglot faculties over language-neutral seams.** Each faculty lives in the language that
serves it (Memory = Python, Brain = Julia, spine = undecided); they integrate over stable,
language-neutral seams — MCP / HTTP / CLI — so implementations behind a seam stay swappable.
MCP is an **endorsed seam whose live server is deferred**: `src/pkm/mcp_server.py` is retained
dormant-by-design and revives when the spine decision (§15) forces it.

**§6. derive → project → reach.** Immutable derivations (pkm) flow through a thin, one-way
bridge into mutable state (*project* — each fact filed once, with its citation), and out to the
owner through dumb transports (*reach*). Transports hold no truth and no business logic.

**§7. Ledger as truth; the derive/act boundary.** Where state is legitimately mutable, truth is
`fold(append-only events)`: every read-model is a rebuildable projection, and a cleared item
never resurrects. The boundary test: **a fact derivable from sources is a pkm transform or a
read-time projection — never a new ledger.** Only human-authored mutable state (a task
completed, a note written) warrants act-layer events. This principle dissolved the bespoke CRM
faculty — see [`docs/crm-architecture-decisions.md`](./docs/crm-architecture-decisions.md) and
[`docs/act-layer-events.md`](./docs/act-layer-events.md).

**§8. Provenance on every answer.** Every asserted fact carries a citation to its source.
Value-bearing facts (IDs, numbers, proper nouns) are deterministically verified against the
cited source before display; anything unverifiable is flagged, not presented as true. Weak
retrieval abstains rather than guesses.

**§9. Dogfood — evidence-driven building.** The failure log (`$LIFE_AGENT_KB/FAILURES.md`)
is the system's evidence stream: every dogfood miss is logged, and every shipped change
names the failure(s) it addresses or the design section it executes. Since 2026-06-11
(owner directive) the log no longer *gates* sequencing: the adopted system design
([`docs/system-design.md`](./docs/system-design.md),
[`docs/derivation-engine-design.md`](./docs/derivation-engine-design.md)) executes
continuously, phase by phase, verified by answer-grounded eval gates. Speculative features
outside the adopted design still go to a backlog, not a PR. **Research reports are
candidate inputs, never mandates** — they inform decisions and bind nothing
(e.g. [`docs/nix-for-documents-report.md`](./docs/nix-for-documents-report.md)).

**§10. Determinism is semantic, defined in pkm.** The determinism contract (semantic
equivalence, not byte-equality; a cache hit is deterministic regardless of model behaviour on a
miss) is owned by [`docs/pkm/SPEC-PRINCIPLES.md`](./docs/pkm/SPEC-PRINCIPLES.md) and pkm's SPEC
§7.1. Do not redefine it elsewhere, and do not "fix" it.

**§11. Two rigors.** `src/pkm` is the frozen foundation: SPEC-first (amend the SPEC before the
code), TDD, every cache operation proven idempotent by a double-run, ask before a new
dependency / top-level directory / file format. Above pkm, rigor is **answer-grounded
evaluation**: facts graded against expected answers, failure-mode-classified, robust to corpus
growth. pkm records what happened; the layers above are accountable for what is true.

**§12. Local/cloud is engineering, not privacy.** Choose execution venue by cost, latency, and
capability (local embeddings, cloud reasoning — today's choice, not a commitment). Privacy is
handled **structurally** instead: this public repo holds the system, never the data. Corpus,
evals, failure log, and identity live under `$LIFE_AGENT_KB`, outside the tree, enforced by a
fail-closed PII guard on every commit. Identity/PII knowledge belongs in out-of-tree config —
and not in the derive layer at all.

**§13. Tailscale-only.** Any networked surface binds to the Tailscale IP. Never expose
publicly; never use `tailscale serve`/funnel.

**§14. Resolved decisions.** Do not relitigate without new evidence:
- **First win:** ask-anything search with citations. **Scope:** text-first.
- **Memory = pkm extended**; **brain = credence**; this repo is the composition root —
  capabilities compose over seams (§5), they don't merge into one app.
- **The Phase-0 compiled wiki is retired**: built, measured against retrieval
  ([`SPEC-comparison.md`](./SPEC-comparison.md) is the frozen record), and rejected — compiling
  a summary of everything does not scale and hallucinates; answers ground in retrieved,
  cited extractions (§8).
- **The derivation framework is adopted (2026-06-11):**
  [`docs/system-design.md`](./docs/system-design.md) (the whole-system view) and
  [`docs/derivation-engine-design.md`](./docs/derivation-engine-design.md) (the derivation
  leg). Demand-driven materialisation; deterministic operators executor-side, LLM only in
  cached per-document projections; GTD/CRM/ask converge on one substrate; act ledgers gain
  knowledge projections.
- **The Bayesian foundations are adopted (2026-06-12):**
  [`docs/bayesian-foundations.md`](./docs/bayesian-foundations.md) — the knowledge layer's
  probabilistic semantics. Every derivation edge is a measurement instrument with a
  declared error model; every answer is a claim set with posteriors; the response is an
  expected-utility decision; calibration is measured (the outcomes log + proper scoring
  rules; adoption gates are decision-weighted with Bayesian comparison). The engine's
  D3–D4 are re-scoped as Ask's aggregate and thread families. Adopted with a binding
  rider: the document's §14 open questions are a live ledger of what we don't know, each
  entry naming the evidence that will decide it.
- **The executor unification is adopted (2026-06-28):** an autonomous agent *is* (belief,
  utility, decision space) ranked by expected utility (§1) — there is no separate "governor" to
  build later. The **VOI executor** — one argmax-EU over the terminal responses **and** the
  transformations, every belief and optimisation carried by credence — is the spine, built now
  and conservative-first, and it *is* its own data loop (it calibrates by running, §16).
  "Confident-wrong" is not a category: confidence is P(truth), calibrated against truth. This
  re-grounds the staged plan ([`docs/bayesian-foundations.md`](./docs/bayesian-foundations.md)
  §12) — its "stage 6 governor" is the spine itself, not a deferred stage.

**§15. Open decisions.** Decided when their phase arrives, not before:
- **The spine** (Phase 2): pi-mono (TS) vs a Python loop vs Claude Code as interim. Criteria:
  openness/extensibility vs lock-in; whether it consumes the §5 seams unchanged; the cost of
  always-on operation. The owner is neutral; nothing in the tree may presuppose the answer.
  **Under §16 the spine is transport** — it feeds events in and executes the chosen action's
  *how*; the agent itself lives in the belief-core (credence + U + A), so this is a reversible
  engineering choice, not an architectural fork.
- **The goals/utility representation** (Phase 2): the form the expected-utility model takes.
- **The CRM rebuild**: of the seven decisions in
  [`docs/crm-architecture-decisions.md`](./docs/crm-architecture-decisions.md), #1, #2, #5
  and #6 were resolved by the adopted framework (noted there); #3 (mutable notes/reminders)
  and #4 (alias dedup) remain open.

**§16. The asymptote — one optimiser, learning by running.** *Believing, computing, and acting
are the same move: a single argmax of expected utility over one decision space — the terminal
responses **and** the transformations — under one belief, with the owner's utility, every
probability and every optimisation carried by credence, over an immutable log whose only
invariant is that truth is the fold.* This is **the executor**; §1 makes plain it is not a
deferred final stage — an autonomous agent simply *is* (belief, utility, decisions) ranked by
EU, so there is no separate "governor" to build afterwards. There is only this optimiser: built
now, thin first, grown.

There is no "confident-wrong" category. **Confidence is P(truth)**, scored against the realised
truth by proper scoring rules — calibration. A confident assertion that proves wrong is a
*calibration miss*, repaired in the **belief** (model the structure that should have lowered p —
correlated duplicates, the wrong subject, a stale source) or in the **utility** (the loss),
never by a bolted-on rule. With calibrated p and a faithful `u_wrong`, EU-maximisation declines
a low-p assertion of its own accord: safe behaviour is *derived*, not patched.

**The executor is its own data loop.** It cold-starts on conservative priors — scoping or
abstaining until evidence earns confidence, *safe before it is calibrated* — and every decision
it takes and outcome it observes (did the transformation yield the truth? was the answer right?)
conditions the very beliefs it ranks over: the transformations' yields, and the owner's utility.
Building it and calibrating it are one act; there is nothing to sequence between them. Two lines
hold: the binding corollary — **every derivation, model call, and decision is a content-addressed
node with lineage on one DAG**, no off-ledger computation in the answer path
([`docs/system-design.md`](./docs/system-design.md) §3) — and the one safety floor (§3):
**outward write-actions** (email, calendar) wait on the goals/utility model; the
read/compute/answer loop does not. Knowledge grows from the loop — act ledgers project back into
the KB, and answers are themselves artifacts.

## Diagnostics (one-question tests)

**Derive or act?** *Could this state be recomputed as a pure function of sources + config?* If
yes, it is a pkm transform or a read-time projection. If no — a human authored or mutated it —
it is act-layer events (§7). There is no third category.

**KB or agent concern?** *Am I asking "what is recorded?" or "what should be done?"* The first
belongs to pkm (§2); the second to the agent (§3). Do not conflate them: the KB does not decide,
and the agent does not re-derive.

**Report or principle?** *Would this text be deleted if the research behind it were retracted?*
If yes, it is an input (§9), and belongs in a report with a status header — not here.

**Seam or implementation?** *If the component were rewritten in another language tomorrow,
would its consumers change?* If yes, the boundary is not a seam yet (§5).
