# Literature report — setting the utility of a selective, escalating answerer

**Date:** 2026-09-06. **Companion to:** `life-agent/docs/LITERATURE-AND-HARNESSES.md`,
`DR-DECISION-1-action-space-and-utility.md`, `OPEN-QUESTIONS-utility.md`.
**Status:** report, not spec. Nothing here is a ruling.

**Method and its limits.** This is a search-and-fetch pass (≈15 queries, 3 primary
sources read in full: AbstentionBench v1, Bouchard 2026 abstract+§6–7, CRAG scoring).
It is not a systematic review. Each claim carries one of three tags:

- **[P]** primary source read, claim checked against it
- **[S]** secondary — abstract, citing paper, or survey; not the primary text
- **[NF]** searched, no precedent found in this pass

Where a source contradicts something in the specs, the contradiction is stated in §5,
not smoothed over in the body.

---

## 1. The theoretical options, and what each one buys

There are seven families. life-agent already lives in the first, borrows from the
third and seventh, and has been rediscovering the fourth.

### 1.1 The cost model — Chow's rule **[S, formula verified across three sources]**

Chow (1957, 1970) gives the reject rule as a threshold on the maximum posterior with
`t = (Cr − Cc)/(Ce − Cc)` where `Ce`, `Cr`, `Cc` are the costs of error, rejection, and
correct recognition. Under the life-agent gauge (`Cc = −1`, `Cr = 0`, `Ce = |u_wrong|`)
this is `gate.py:317` identically; R-1 is right that it is an identity, not an analogy.

**Three results from the same literature that the specs do not yet carry:**

1. **Chow's rule is optimal only against true posteriors.** Fumera, Roli & Giacinto
   (2000) show it does not give the optimal error–reject tradeoff when posteriors are
   estimated with error, and the remedy they propose is **class-specific thresholds**.
   Transported: A-CAL is not a nice-to-have, it is the hypothesis of the theorem; and
   if it fails partially, the literature's fix is *per-lane bars*, which the spec's
   `p_r conditioned on lane at minimum` already gestures at for escalation but not for
   the commit bar itself. **[S]**
2. **The monotone error–reject relation** (Chow 1970) *is* the risk-coverage curve.
   LIT §3's AURC re-cut is Chow's companion result under another name. **[S]**
3. **Plug-in consistency.** Herbei & Wegkamp (2006) prove the plug-in rule (estimate
   posteriors, then threshold) is consistent — but consistency is asymptotic, and the
   104-row set is not. **[S]**

### 1.2 The bounded-improvement model — a third basis for OQ-0 **[S]**

There are two classical models of selective classification, not one: the cost model
(Chow 1970) and the **bounded-improvement model** (Pietraszek 2005), in which no
reject cost is elicited at all; instead one fixes a **target risk** and maximises
coverage (or fixes coverage and minimises risk). Geifman & El-Yaniv (2017) give the
SGR algorithm that returns a selective classifier with a high-probability guarantee
on selective risk for a stated target. **Franc & Průša (2019) establish the
equivalence of the cost-based and bounded-improvement models.**

**Why this matters for OQ-0.** Option (c) — "a third basis is required" — currently
names nothing. This is the something. The owner can rule a *target selective risk*
(e.g. "no more than 3% of asserted answers may be wrong") instead of a `u_wrong`, and
by the Franc–Průša equivalence the implied `u_wrong` falls out as a derived quantity
rather than an elicited or folded one. That converts OQ-0 from "which estimate of a
latent" into "which observable do you want to bound," which is a different and
arguably better-posed question. Conformal abstention (Yadkori et al. 2024) is the
distribution-free version of the same move. **This is the single most useful thing
in the pass for the OQ-0 ruling.**

### 1.3 Learning to defer — what it gives, what it assumes **[S]**

- Madras, Pitassi & Zemel (2018): learning to defer generalises rejection learning by
  modelling the downstream decision-maker's accuracy. `escalate_r` with `p_r` is this
  framing exactly (R-2 holds).
- Mozannar & Sontag (2020): first consistent surrogate; reduction to cost-sensitive
  learning. Verma & Nalisnick (2022): one-vs-all surrogate giving *calibrated*
  deferral probabilities. Mao et al. (2024): H-consistency bounds for general cost
  functions — i.e. the surrogate theory has been extended to non-0/1 costs, so
  "reject-option theory carries a single error cost" (R-7) is true of Chow but no
  longer true of the L2D line.
- **Training requires precomputed costs for every expert on the training set**
  (standard full-information assumption; restated in Montreuil 2026). life-agent
  does not have this and does not want it.

**The two precedents R-7 said were not found:**

- **`p_r` learned from the act's own outcome stream.** Online L2D under bandit
  feedback (arXiv 2605.12340, May 2026): "it only requires feedback from the experts
  that are actually queried," with a dynamically varying expert pool and drifting
  reliability, and sublinear regret. That is the guard-on-writable-name mechanism,
  stated as a learning problem with a guarantee. Expert-Agnostic L2D (arXiv
  2502.10533) uses a **Bayesian Beta-Binomial model of expert accuracy** with priors —
  which is what "the posterior earns `p_r` from outcomes" means when written down.
  **Verdict: precedent exists; the spec's contribution is doing it inside the same
  inference as the answer posterior, not the idea.** **[S]**
- **Computing rather than training the deferral policy.** "No Need for Learning to
  Defer? A Training-Free Deferral Framework … through Conformal Prediction" (arXiv
  2509.12573) is the closest statement of R-3's position — and it obtains its guarantee
  from conformal coverage rather than from calibration. That is the alternative to
  A-CAL: swap the calibration assumption for exchangeability and get a
  distribution-free guarantee. Worth reading in full before A-CAL is tested. **[S]**

### 1.4 Set-valued and imprecise prediction — the family the spec rediscovered **[S]**

This is the literature `set_m`, `interval_ab`, `x = 1/m`, and `u_vague` belong to,
and it is more developed than the spec knows.

- **Prefix optimality is a theorem, with a name.** Mortier, Wydmuch, Dembczyński,
  Hüllermeier & Waegeman (2021, *Data Mining and Knowledge Discovery* 35:1435–1469;
  arXiv 1906.08129) formalise set-valued prediction as maximising expected utility
  over subsets, and show that for utilities depending on set size and containment the
  Bayes-optimal set is a **prefix of the posterior-sorted classes**, reducing 2^K to
  K. Del Coz, Díez & Bahamonde (2009, JMLR) did the F_β case. **This is the canonical
  citation for §3.3, and it also answers O-6:** for a *single* gold label, F1 against
  the predicted set is `2/(m+1)` if contained and 0 otherwise — size-only — so the
  prefix result survives. It fails only for multi-label gold *sets*, which is a
  different problem (Nguyen & Hüllermeier 2019, "partial abstention" in multilabel
  classification, is that literature).
- **`x = 1/m` has a name and a uniqueness result.** Zaffalon, Corani & Mauá (2012,
  *IJAR* 53:1282–1301) call it **discounted accuracy** and show, in a betting
  framework, it is the *only* score satisfying a set of basic properties for
  comparing determinate and indeterminate predictions. **They also show its defect:**
  a classifier that answers randomly and one that always returns the full set have
  the same expected discounted accuracy (the "doctor random vs doctor vacuous"
  argument), so a risk-averse decision-maker should prefer the vacuous one — and
  they introduce **utility-discounted accuracy** (`u65`, `u80`) to encode that.
  **That is `u_vague`, ten years early, with the argument for why it must be
  elicited rather than defaulted already made.** DR-DECISION-1 §7.3's k-independent
  hedge is exactly the doctor-vacuous failure.
- **Warning for the measurement layer.** Impossibility results (Seidenfeld et al.
  2012; Mayo-Wilson & Wheeler 2015; Schoenfield 2017, as summarised in arXiv
  2503.16395) show no continuous scoring rule over imprecise forecasts can be
  simultaneously strictly proper, calibrated, and non-dominated. If the AURC/ECE
  layer is ever extended to score set and interval outputs *as forecasts*, this bites.
  It does not bite the decision layer, which scores actions.
- Winkler (1972) interval score is the interval-shaped member; the spec has it.

### 1.5 Explicit-threshold penalties **[P for Kalai; S for Wu]**

Kalai, Nachum et al. (OpenAI, Sept 2025) argue the field's leaderboards penalise
abstention, and propose that each task state a confidence threshold `t` with a
penalty of `t/(1−t)` for wrong answers, so the optimal policy answers only above `t`;
report curves across `t ∈ {0.5, 0.75, 0.9}` ("behavioral calibration"). At `t = 0.9`
the penalty is 9.0. **The elicitation-only estimate is the OpenAI 0.9-threshold
convention to four figures.** They also say explicitly that the *ideal* penalty would
reflect real-world harm but that is impractical because it is specific to the
problem, application, and user group — so thresholds should be stated up front even
if somewhat arbitrary. That is a published argument that `u_wrong` is a policy
parameter to be ruled, not a latent to be estimated — the opposite of the s18
conferral's "identified latent" position. **Both positions are defensible; OQ-0
should name the disagreement rather than assume the conferral's side.**

Wu et al. (2025, "Answer, Refuse, or Guess?") vary `(r_cor, r_inc, r_ref)` over
`(1,−8), (1,−4), (4,−1), (8,−1)` and find LMs over-answer in high-risk settings and
over-defer in low-risk ones. Their grid brackets both candidate estimates. **[S]**

### 1.6 Multi-attribute utility and the cost of asking **[S]**

- Keeney & Raiffa (1976): additive scalarisation `λ$·c$ + λt·ct + λp·d` assumes
  mutual preferential independence; a hard constraint (SEALED) is the lexicographic
  exception. Standard; no search needed.
- **`gather`/`ask` as one-step lookahead is value of information** (Lindley 1956;
  Howard 1966). Horvitz's line of work (e.g. US 7,428,521, "cost of interruption")
  prices exactly `lambda_int` and computes whether the reduction in expected cost
  exceeds the cost of asking. Rao & Daumé (2018) rank clarification questions by
  expected value of perfect information. arXiv 2605.07937 (2026) surveys clarification
  timing for long-horizon agents under the VOI framing. **§4.4 is standard VOI and
  should cite it; `net_voi` needs no novelty claim.**

### 1.7 Cascades **[P for Bouchard §6–7 and abstract; S for the rest]**

- FrugalGPT (Chen, Zaharia & Zou 2023); AutoMix (Aggarwal, Madaan et al. 2024);
  Jitkrittum et al. (2024) "When does confidence-based cascade deferral suffice?";
  Zellinger & Thomson (2025) "Rational tuning of LLM cascades" — a Markov-copula model
  of joint calibrated confidences across cascade stages, tunable with ~300 examples.
  **This last one is a method for setting rung thresholds from data that the spec
  does not have and OQ-8 could use.**
- Zellinger, Liu & Thomson (2025, arXiv 2502.09054): early abstention reduces test
  loss 2.2% on average across six benchmarks, trading +4.1% abstention rate for −13.0%
  cost and −5.0% error. R-6 is correctly stated.
- **Bouchard (2026, arXiv 2605.06350; ICML 2026):** piecewise-concave two-model
  frontiers, pairwise envelope over a pool, stagewise first-order conditions with one
  shadow price. Empirically, full fixed chains underperform the pairwise envelope, and
  **a lightweight pre-generation router beats the best cascade on four of five
  datasets, mainly because it avoids paying the cheap model on queries sent directly
  upward.** Conclusion: cascade performance is limited by structural cost, not by a
  shortage of intermediate stages. **See §5.1 — this is not merely a caveat on OQ-8.**

---

## 2. Practical examples with a stated utility

| System / paper | u_correct | partial | u_abstain | u_wrong | Notes |
|---|---|---|---|---|---|
| Kalai et al. 2025 (OpenAI) | 1 | — | 0 | −t/(1−t) | t=0.9 → −9; report curve over t **[P]** |
| CRAG / KDD Cup 2024 (Meta) | 1 | 0.5 ("acceptable") | 0 ("missing") | −1 | Truthfulness = perfect + 0.5·acceptable − hallucination; judge F1 vs human 94.7–98.9% **[S]** |
| Wu et al. 2025 | 1 or 4 or 8 | — | 0 | −8/−4/−1 | four risk regimes **[S]** |
| Zaffalon et al. 2012 | 1 | discounted 1/m; u65/u80 risk-averse | — | 0 | the `u_vague` precedent **[S]** |
| RouterBench 2024 | quality metric | — | — | — | AIQ = area under cost–quality curve; 405k precomputed rows **[S]** |
| VB benchmark 2026 (CAA) | confidence ĉ | — | α = 0.25 | 0 | one recent example of a non-zero abstain payoff **[S]** |
| AbstentionBench 2025 | accuracy | — | recall/precision/F1 on abstention | — | **no utility**; judge 88% vs human (v1 §3.4) **[P]** |
| LongMemEval / LoCoMo | accuracy | — | abstention accuracy on flagged items | — | no utility **[S]** |

Three observations. (i) Every published convention pins `u_abstain = 0` and
`u_correct` positive; the only free parameter is the ratio, exactly as in the gauge.
(ii) The published range of the ratio is 1:1 (CRAG) to 9:1 (Kalai at 0.9) to 8:1
(Wu); both life-agent estimates sit inside it. (iii) Only CRAG and Zaffalon have any
partial-credit term, and Zaffalon's is the only one with an argument for its value.

---

## 3. R-7 revisited — the "no precedent found" items

| Item | Verdict after this pass | Nearest precedent |
|---|---|---|
| String-blind NONE-atom posterior | **Precedent for the atom; not for the combination** | Open-set recognition's explicit "other class" / N+1 class (Geng et al. survey, OpenMax); SQuAD 2.0's null-answer score as a first-class candidate. Flat-escalate-over-a-simplex-with-NONE is not found. |
| Shape-dependent `u_err` with `u_vague` | **Precedent, strong** | Zaffalon–Corani–Mauá 2012 utility-discounted accuracy; Mortier 2021 general utilities over sets; Winkler 1972; Nguyen–Hüllermeier 2019 partial abstention. What may be ours: charging `u_vague` vs `u_wrong` by *containment* inside one argmax alongside point claims. |
| `p_r` learned via a guard on the writable name | **Precedent** | Online L2D with bandit feedback (2605.12340); EA-L2D Beta-Binomial (2502.10533). Ours: same inference as the answer posterior. |
| SEALED as feasibility, not price | **Precedent in practice; thin in theory** | Privacy-flag-forces-edge is the stated production pattern ("sensitivity constraints override all other routing factors"); PRISM (AAAI-26) is the *priced* soft-gating version. Workload-constrained L2D (2403.06906) treats capacity as a constraint. A hard feasibility mask inside a deferral argmax is not found as a theoretical object. |
| Top-m prefix dominance | **Theorem exists** | Mortier et al. 2021 (canonical); Del Coz 2009. |

Net: the individual components each have a home. **What has no precedent found is
the assembly** — one argmax over point/set/interval/pointer/escalate/abstain with a
NONE atom, shape-dependent error costs, outcome-learned rung reliability, and a
feasibility mask — and that is a fair thing to claim once the components are cited.

---

## 4. Public corpora, by fit to a private personal store

| Corpus | Size / shape | Has abstention items | Has evidence gold | Has cost | Fit | What it can test |
|---|---|---|---|---|---|---|
| **ATM-Bench** (Mar 2026, HF) | ~4 yrs personal data: 6,741 emails, 3,759 images, 533 videos; 1,038 human QA with gold evidence; -Hard subset avg 6.3 evidence items | yes (ABS) | **yes** | no | **closest** | `citation.audit`; retrieval reach; abstention on a personal corpus; email-only subset is text-only |
| LongMemEval-S (2024) | 500 q over ~115k-token chat histories; 30 false-premise `_abs` items; knowledge-update items | yes | session-level | no | medium | `scoped_j` (knowledge update); abstention; not document-shaped |
| LoCoMo (2024) | 10 dialogues, ~1.5–2k QA | yes (adversarial) | no | no | low | small; dialogue |
| **CRAG** (2024) | 5 domains, 8 question types, dynamism/popularity strata; val + public test released | "missing" is scored | no | no | medium | L2 grading with a **published utility**; question taxonomy ≈ shapes |
| **AbstentionBench** (NeurIPS 2025) | 20 datasets, 6 scenarios, ≤3,500/dataset; 88% judge | yes, by scenario | some | no | medium | L3 boundary; **False Premise subsets (FalseQA, (QA)², KUQ, CoCoNot) give `p_prem` data now** |
| **RouterBench** (2024) | 405k precomputed inference rows, 8 tasks | no | no | **yes ($)** | medium | escalate ladder; AIQ; the only one with a price axis |
| SQuAD 2.0 / NQ unanswerable | large | yes | span | no | low-medium | NONE atom calibration on extractive QA |

**No public corpus has privacy classes or metered spend on a personal store.** SEALED
and `lambda_priv` stay internal. RouterBench has cost but no NONE; ATM-Bench has NONE
and evidence but no cost. A benchmark protocol needs both, so it needs two harnesses.

---

## 5. What this changes in the specs

### 5.1 `DR-DECISION-1` §4.3 vs Bouchard — a disagreement, not a caveat
A-2 recorded Bouchard as "do not expand the rung set." His headline is stronger and
points the other way: routing *before* paying the cheap stage wins. §4.3 moves
escalation *after* retrieval and extraction. §6's lane classifier is question-only and
therefore *is* a pre-generation router in his sense. **Decision required:** does L3
skip retrieval? If yes, §4.3 needs an exception and `pointer` is unavailable in that
path; if no, the spec is choosing to pay the structural cost and should say why
(transfer caveat: retrieval ≠ cheap model). Neither answer is wrong; the absence of
one is.

### 5.2 `OPEN-QUESTIONS` OQ-0 — add a named option (c′)
"Rule a target selective risk; derive `u_wrong` by the Franc–Průša equivalence."
Record that Kalai et al. argue the number is a per-application policy choice, which
disagrees with the conferral's "identified latent" framing; the ruling should pick a
side explicitly.

### 5.3 `DR-DECISION-1` §2.1 A-CAL — cite the theorem it is the hypothesis of
Fumera et al. 2000; note per-lane thresholds as the literature's partial remedy; note
conformal deferral (2509.12573) as the assumption-swap alternative.

### 5.4 `DR-DECISION-1` §3.3 — cite Mortier et al. 2021; close O-6
Single-gold F1 is size-only; prefix dominance survives.

### 5.5 `DR-DECISION-1` §5.2 — cite Zaffalon 2012 for `u_vague`
And carry their argument: discounted accuracy alone cannot distinguish random from
vacuous, so `u_vague` is not optional.

### 5.6 `DR-DECISION-1` §4.1 — cite online L2D for `p_r`; §4.4 — cite VOI
Withdraw any novelty framing for both.

### 5.7 `LITERATURE-AND-HARNESSES` §2.2 — replace the unverified figures
Judge accuracy is **88%** (v1 §3.4), not 82.3%. Dataset count is 17 + 3 = 20; six
scenarios; "31 subsets" does not appear in v1.

### 5.8 `LITERATURE-AND-HARNESSES` §3 — AURC has known evaluation flaws
Traub et al. (NeurIPS 2024, "Overcoming Common Flaws in the Evaluation of Selective
Classification Systems") argue selective risk is unsuitable for aggregation across
thresholds and propose AUGRC. Report both E-AURC and AUGRC, or expect the number to
be challenged. Also: 104 rows is too few for either to carry a decision alone.

### 5.9 OQ-8 (rung set) — there is a data-driven method
Zellinger & Thomson 2025's Markov-copula threshold tuning from ~300 examples. Not a
substitute for Bouchard's optimality conditions, but a procedure that exists.

---

## 6. Where this pass is thin

- Bouchard read only via abstract and §6–7; the first-order conditions were not
  checked against his statement.
- Zaffalon 2012, Mortier 2021, Franc & Průša 2019, Fumera 2000, and 2605.12340 are
  cited from abstracts and citing papers, not read in full. The Franc–Průša
  equivalence in particular should be read before OQ-0 (c′) is offered as an option.
- No search was run on: hierarchical/temporal abstention for `scoped_j`; provenance
  ledgers for escalated answers (tannen §9); metered-spend accounting in routers.
- The privacy-routing precedent is production folklore plus one AAAI paper; the
  theory side (constraints inside deferral) was not searched beyond one hit.

---

## Sources (arXiv IDs where they exist)

Chow 1957, 1970 · Herbei & Wegkamp 2006 · Bartlett & Wegkamp 2008 · Fumera, Roli &
Giacinto 2000 · Pietraszek 2005 · Geifman & El-Yaniv 2017 (1705.08500), 2019 ·
Franc & Průša 2019 · Yadkori et al. 2024 (2405.01563) · Traub et al. NeurIPS 2024 ·
Madras, Pitassi & Zemel 2018 · Mozannar & Sontag 2020 · Verma & Nalisnick 2022
(2202.03673) · Mao et al. 2024 (2407.13732) · Montreuil 2026 (2603.14324) · online
L2D 2605.12340 · EA-L2D 2502.10533 · training-free deferral 2509.12573 ·
workload-constrained L2D 2403.06906 · Del Coz et al. 2009 · Mortier et al. 2021
(1906.08129) · Zaffalon, Corani & Mauá 2012 · Nguyen & Hüllermeier 2019 (1904.09235) ·
imprecise scoring impossibility summary 2503.16395 · Kalai et al. 2025 (2509.04664) ·
Wu et al. 2025 (2503.01332) · Keeney & Raiffa 1976 · Lindley 1956 · Howard 1966 ·
Rao & Daumé 2018 · clarification timing 2605.07937 · FrugalGPT 2305.05176 ·
AutoMix · Jitkrittum et al. 2024 · Zellinger & Thomson 2025 (2501.09345) ·
Zellinger, Liu & Thomson 2025 (2502.09054) · Bouchard 2026 (2605.06350) · CRAG
2406.04744 · RouterBench 2403.12031 · AbstentionBench 2506.09038 · ATM-Bench
2603.01990 · LongMemEval 2410.10813 · LoCoMo · PRISM 2511.22788 · VB 2603.06680 ·
open-set recognition survey 1811.08581.
