# Research dispositions — August 2026 agent-literature sweep

> **Status: DRAFT for owner signature (2026-08-18).** This is a report-derived input under
> PRINCIPLES §9: the sweep it dispositions is a candidate input, never a mandate, and every
> row below would be deleted if the research behind it were retracted. Destination: commit as
> `docs/research/2026-08-agent-litsweep-dispositions.md` after signature. The coding agent
> sees **only §6** of this document.

Verdict vocabulary: **CITE** (adopt as citation, no design change) · **INPUT** (feeds a named
design-doc section) · **HARDEN** (becomes an invariant or a seeded-defect test) ·
**VERIFY** (preprint figure; check final PDF before any quotation) · **DEFER** (named landing
site, later tranche) · **REJECT** (with reason).

## 1. Foundations — cite, never re-derive

| Finding | Verdict | Destination |
|---|---|---|
| Fritz 2020 (Markov categories); Cho–Jacobs 2019 (Bayesian inversion) | CITE | Paper programme / credence-spec §6.7 refs; no code impact |
| Fritz–Gonda–Perrone–Rischel 2023 (synthetic Blackwell–Sherman–Stein) | CITE | The "why lossy transforms" grounding; replaces any in-house derivation |
| Fritz et al. 2025 (categorical Bayes filter) | CITE | The theorem that "belief = fold(ledger)" is the inversion of the generative kernel; cite in bayesian-foundations at next amendment, not now |
| Di Lavore–Román(–Sobociński) 2025 (partial Markov categories; order enrichment) | CITE + DEFER | Conditioning/constraint semantics for the DSL — proplang's register, not life-agent's |
| Braithwaite–Hedges–Smithe 2023 (compositional Bayesian inference) | CITE | Underwrites well-definedness of composed folds; paper programme |
| Arumugam–Van Roy 2021–23; Grimm et al. 2020–21 (rate-distortion / value equivalence) | CITE | The cost-aware Blackwell reversal; kernel-catalogue design doc, later tranche |
| Dawid 2021 + Constantinou–Dawid 2017 (regime indicators, ECI) | CITE | Constitution-level causality reference |

## 2. Formal caveats — register entries

| Finding | Verdict | Destination |
|---|---|---|
| Richardson–Robins 2023: Dawid's proofs lean on mutual independence of regime indicators, not itself expressible in ECI | HARDEN (doctrinal) | Register entry on the brain seam: the "which-kernel-ran" indicators must not silently assume mutual independence; cite as subtlety, not refutation |
| Everitt–Leike–Hutter 2015: EDT splits (SAEDT vs SPEDT) for self-reading agents; CDT does not | DEFER | Constitution question: does the regime indicator screen the agent's own past actions off from its belief update? Lands with credence-spec/proplang doctrine, decided before the executor conditions on its own act events |
| VOC ≥ 0 violated in agent settings (arXiv:2605.06908): computations' results entangle with the environment and cannot be freely discarded | HARDEN | VOI-executor design (later tranche): the one-currency EU must not assume non-negative value of computation; add a seeded test when the executor lands |
| Armstrong–Mindermann; Skalse et al. 2023–24 (reward/planner degeneracy geometry) | CITE + HARDEN | Goals/utility design doc: the normative prior over the owner's utility must be explicit and auditable; already constitutional doctrine, now with sharper citations |
| Partially Observable Off-Switch Game (AAAI-25): ledger/owner information asymmetry can reduce deference | HARDEN (doctrinal) | PRINCIPLES-adjacent note: the owner-facing projection of the ledger is a safety-relevant interface, designed as such — lands with the goals/utility tranche |

## 3. Substrate prior art — bears on tranche 1

| Finding | Verdict | Destination |
|---|---|---|
| OpenHands SDK (arXiv:2511.03690): typed event hierarchy, append-only EventLog, replay-as-recording, per-event persistence | INPUT + VERIFY | Design doc §0/§1 (prior-art positioning), §5 (recorded-draw), durability-contract section. §5.2 latency/storage figures are preprint + third-party-summarised: verify before quoting. Verified 2026-08-18 (Table 3 verbatim; quote the table, not the prose — the prose's "under 20 ms" crash-recovery claim matches the replay row, not the crash-recovery row, whose max is 32.1 ms). Weighting: the 61% failure reduction is primarily a co-location result (inter-pod HTTP failure classes removed), not an event-sourcing result; cite as architecture-redesign evidence. |
| ESAA (arXiv:2602.23193): event sourcing as source of truth, verifiable projections via replay | INPUT | Design doc §0: prior art for "truth = fold(events)"; §9: the verifiable-projection pattern for golden replay criteria |
| TOKI (arXiv:2606.06240): bitemporal operator algebra over agent memory events | INPUT | Design doc §4 (identity vs occurrence): GTD events are already bitemporal; cite as the formal treatment |
| SSGM (arXiv:2603.11768): System-2 verification on every write incurs latency/stability trade-offs | INPUT (verified) | Durability-contract section: the latency–safety trade-off (§1 contribution 4; Principles 1–2) against heavy in-path verification. ADDITIONALLY: Principle 4 (Reversible Reconciliation — mutable active view anchored to an append-only immutable episodic log as operational source of truth) is supporting prior art for the unified ledger's design-doc §0 prior-art paragraph. Conceptual paper: no implementation or measurements; cite for pattern and trade-off taxonomy only. |
| Temporal (durable execution); Grädel–Tannen semiring provenance | CITE / DEFER | Engineering lineage note; semiring lineage only if the DAG ever needs valued provenance — no current demand |

## 4. Governance & tool-contract prior art — later tranches, do not leak into tranche 1

| Finding | Verdict | Destination |
|---|---|---|
| Contract2Tool / ToolGate / RACG / ContractGuard / PORTICO (typed preconditions, effects, capability revocation) | INPUT + VERIFY | Kernel-catalogue design doc (next tranche). Baseline to beat; differentiation = EU selection over admissible morphisms + one VOI/VOC currency. Babu–Iyer cluster is single-author-pair: prefer ToolGate + the provenance survey (arXiv:2606.04990) for load-bearing claims. Verified 2026-08-18 (abstract verbatim: 0.980 vs 0.990; tools 100→1; tokens 26,172→2,528). Third caveat added: evaluation is on the authors' own synthetic benchmark and self-published registry; no independent replication found as of 2026-08-18. Figures quotable only with the synthetic-benchmark qualifier attached. |
| RACG collapse under forged authorisation; ContractGuard: effect integrity is the load-bearing assumption | HARDEN | Kernel-catalogue invariants: admissibility inputs must be provenance-verified; the agent's own testimony is never an admissibility input (the Replit lesson, encoded) |
| Beta-Bernoulli per-tool reliability posteriors (arXiv:2512.18950, 2606.08348) | INPUT | Kernel yield models: adopt the pattern directly — it is credence's conjugate machinery independently rediscovered; cite rather than claim novelty |
| Wu et al. 2026: LLM self-assessed tool need/utility misaligned with true need | CITE | Supports externally-maintained posteriors overriding LLM self-assessment; kernel-catalogue doc |
| Kirchhof et al. ICML 2025 position (agentic UQ needs reassessment); no mature agentic-UQ benchmark exists | DEFER | Evaluation programme: a gap the approach-dominance benchmark could partially fill |
| OpenClaw 2026.8.1: hooks with idempotency keys, fail-closed egress; documented harness-registration failure class | INPUT | Governor integration tranche: `before_agent_finalize` (revise/finalize + idempotencyKey) is the shadow-mode seam; the failure class is demo material |

## 5. Framing

The sweep's synthesis — the programme is ahead on unification and the single decision
currency, behind on applied substrate/contract prior art — lands in the papers/positioning
programme only. **REJECT** any reframing work inside life-agent: code tranches do not
reposition; documents do.

## 6. Phase 1 injection — the ONLY section the coding agent receives

Addendum to the tranche-1 brief, Phase 1 (design doc). Four items, all bounded to citation
and sharpening; no schema or scope changes follow from them.

1. **Prior-art positioning (§0/§1).** Cite ESAA (arXiv:2602.23193) as published prior art
   for event-sourcing-as-source-of-truth with verifiable projections via replay, and the
   OpenHands SDK (arXiv:2511.03690) for the typed append-only event-log substrate. One
   short paragraph; the design doc's contribution is the *unification of existing
   in-repo flavours* and the decision-theoretic layer above, not the substrate pattern.
2. **Recorded-draw rule (§5).** Distinguish explicitly, citing OpenHands' replay design:
   *replay-as-recording* (a fold re-reads the logged output of a stochastic kernel) versus
   *re-execution* (re-invoking the kernel). The unified stream's folds ALWAYS do the
   former; re-execution is a new occurrence, appended, never substituted. State this as
   the rule; it is act-layer-events.md's recorded-draw made precise.
3. **Identity vs occurrence (§4).** Cite TOKI (arXiv:2606.06240) as the formal bitemporal
   treatment; note the GTD ledger's existing bitemporality as the in-repo precedent, per
   the r00 census.
4. **Durability contract (the Q7 section).** Note (marked "preprint figure, unverified")
   OpenHands' reported sub-millisecond per-event persistence as the order-of-magnitude
   target for the unified writer, and cite SSGM (arXiv:2603.11768) as the warning against
   heavy in-path verification. No figure is quoted as fact until verified against the
   final PDF.

Boundary line for the session: no other research findings are in scope; any temptation to
restructure the design around the tool-contract literature is out of scope for this tranche
and goes to QUESTIONS, not into the doc.
