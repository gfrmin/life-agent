# MODEL.md — how a question becomes an answer

The design authority for **how** a question becomes an answer. `CLAUDE.md` governs rules and
working method; nothing here overrides it. The vocabulary (`World`, `Prior`, channel, `Loss`)
is the entity-resolution core's, so that when the core is extracted from hkaddresses into its own public repo, this repo
and hkaddresses are two conforming instances of it.

One sentence: **an answer is a Bayes act under a stated loss (`core/decide.bayes_act`), over a
posterior on candidate spans, where the likelihood is a noisy channel of typed extraction
observations.**

## 1. The world

For one question `q` the world is a finite set of hypotheses:

- `c_1 … c_K` — **candidate spans**: distinct values (an ID, date, number, name, reference)
  proposed by extraction over retrieved chunks, keyed by a canonical form so format variants
  of one value are one candidate (`core/lookup._candidate_key`);
- `NONE` — the answer is not among them (not in the corpus, or not retrieved).

The claim lattice over a candidate has three levels: the **span** (exact value), the
**scoped** claim (value plus the qualifier it was found under), the **pointer** (the document
that holds it). The MVP commits only spans.

**Proposal.** Retrieval (BM25 over pkm's FTS, reranked) → extraction per chunk → candidates.
The proposal is not the posterior: a gold value not proposed is `NONE`'s mass.

**Lane.** `core/answer_shape.py` classifies the question (`exact`, `quantity`, `threshold`,
`set`). Anything that is not a verbatim point fact skips this world and goes straight to the
escalation menu (§4).

## 2. The channel: P(observation | ω)

Each extraction observation `o` says "chunk `d` supports candidate `k`". Its reliability

```
r = ρ(edge) · authority · subject · time · competition
```

is a product of typed factors: `ρ` the extraction edge's learned reliability
(`core/reliability.py`), `authority` the document class, `subject` whether the chunk is about
the owner, `time` date-projection agreement, `competition` a same-shape competitor in the
quote window. The channel over `A = 10` effective alternatives:

```
P(o | ω = k)      = r + (1 − r)/A            (the observation names k)
P(o | ω = j ≠ k)  = (1 − r)/A
P(o | ω = NONE)   = (1 − r)/A
```

**Tempering** (`β_ancestry = 0.3`, `β_model = 0.7`): `m` observations sharing one ancestry
(forwarded or quoted copies of one attestation) count as `(1 + β_anc(m − 1))/m` each, and
observations from `n` model groups as `(1 + β_model(n − 1))/n`, so correlated evidence is not
counted as independent. Duplicates are removed first (§5 dedup: quote, document, value).

## 3. Inference

Prior: `P(NONE) = 0.5`, the rest uniform over the `K` candidates. Posterior by conditioning on
each observation in order, in log space (`prob_eps = 1e-12`). The fold runs in
`core/posterior.py`, pinned to the Julia engine's 605 recorded decides (within 1e-15; the last
ulp differs), and J5 replaces it with the published core.

**A-CAL — the posterior is calibrated.** The commit bar is a threshold on the posterior's
value, so the argmax is only sound if the credences mean what they say. It is measured
(reliability diagram, ECE), never assumed.

## 4. Decision

`core/decide.bayes_act` chooses one action per question from the **declared menu**: the
argmax of expected utility at `p1`, the MAP candidate's credence (P(asserting now is right)),
ties to the first-listed row:

| action | effect | loss / price |
|---|---|---|
| `respond` | commit the leader span with its citation | `u_correct = +1` if right, `u_wrong = −9` if wrong |
| `abstain` | decline | `u_abstain = 0` |
| `gather` | run the open evidence transform worth most, then decide again | that transform's own price and its own measured effect (below) |
| `ask` | ask the owner a clarifying question | the owner's attention; recovers the answer at the measured rate `r_a` |
| `escalate@r` | hand the question to rung `r` (J1–J2) | the rung's price, and its learned reliability `p_r` |

**The loss is data.** `u_correct = +1` and `u_abstain = 0` are the gauge's two pins;
`u_wrong` is a posterior (prior mean −9, the owner's 10:1, folded from reactions) and
`lambda_usd` converts spend. The decider reads the folded means. With `respond` vs `abstain`
alone the commit bar is `p* = |u_wrong|/(1 + |u_wrong|)` — Chow's reject rule, 0.90 at the
prior (the same α/β = 9 as hkaddresses' `loss.yaml`), 0.84 folded today. The bar is derived,
never set.

**Evidence rows are measured, never perfect information.** `gather` is priced by what the
gather sequence was observed to end in: per leader state (right or wrong), the chances of a
correct report, a wrong one, or a withhold (`core/gather_row.py`: a two-component mixture
over every recorded decide that chose to gather, weighted by its `p1`, fit by EM under a
Dirichlet(2, 2, 2) prior; `scripts/fit_gather_row.py` fits it from the m5-base sequences).
The row is linear in `p1` like the others. Unfitted, both states read the prior mean and
gathering never pays. `ask` recovers the answer at a measured rate `r_a` (Beta(1, 1) mean
0.5 unmeasured).

**Which gather is the same ranking.** The options differ in what they do — a corroboration
lifts the leader's credence, a retrieval adds candidates and lowers it — so each is valued
on its own: one step of lookahead over its measured transition (how often it lifts the
leader, and by how much), landing in a state worth the best row of the menu at the next
step, less its own price (`core/decide.option_eu`, `best_gather`). The best option's value
is the gather row the act ranks, so an option is reached on its value and never on being
the cheapest. The transition is measured, not the final outcome: every option in one
question shares that question's outcome and the recording policy fixed the order, so only
what an option did to the posterior is attributable to it. An option nobody has run reads
the step row, so an unmeasured menu ranks by price. The closed-form preposterior over the
current posterior remains a door (ROADMAP).

**Escalation.** A rung fires only when `p_r·u_correct + (1 − p_r)·u_wrong − λ$·price`
beats every local action, so at `u_wrong = −9` a rung needs `p_r` above 0.90 net of price.
Rungs: (1) a strong model over a wide retrieval window with a citation audit; (2) Claude Code
over the corpus (`claude -p` with the pkm MCP server). Each rung's `p_r` is learned from
verdicts (a Beta per rung).

**Privacy is a constraint, not a price.** A document marked SEALED makes every disclosing
rung infeasible for that question: the host withholds those menu rows. Every chunk that
crosses to a rung is a disclosure record.

**Division of labour.** `core/posterior.py` computes the candidate posterior;
`core/utility.py` folds the loss; `core/decide.bayes_act` takes the act; `core/enact.py`
turns it into a reply (the MAP candidate on `respond`, the cheapest open transform on
`gather`). proplang, as an engine for the act, is deferred until it beats this on the board
(ROADMAP).

## 5. Laws

Each is a test or a failing check, not a guideline.

1. **Never invent.** A `respond` names a candidate with at least one grounded observation;
   otherwise the act is not available.
2. **String-blind.** The decider receives indices and numbers, never candidate text.
3. **One argmax.** No module but `core/decide.bayes_act` ranks actions; its callers are
   drift-gated (`tests/test_decider.py`).
4. **Provenance.** Every reply carries its origin; every commit, its citation and credence.
5. **Write-once records.** Decision, disclosure and verdict rows are never edited; a
   retraction is a new row.
6. **One home per constant.** Channel constants, prices and the action vocabulary are each
   declared once (`core/pricing.py`) and bound everywhere else.
7. **Named degradation.** Bridge down ⇒ the reply says so; there is no fallback decider. A
   failed rung ⇒ a disclosure row and no answer.
8. **Correlated evidence is tempered.** Copies of one attestation never count as independent.
9. **Feasibility is structural.** A SEALED document can never reach a disclosing rung.
10. **Calibration is measured.** A-CAL is read off the verdict stream, never assumed.

## 6. Scoreboard

`eval/score.py` → `SCOREBOARD.md`. Per set and arm: rows · right · wrong · escalated-right ·
escalated-wrong · declined · $/q · U/q · s/q. Sets: `owner` (the owner's 104 questions),
`atm` (ATM-Bench email-only number-typed, 198), `live` (the stream since the reset), `sample`
(synthetic, CI). Every row is graded by exact match. Rule 5: a change merges when no row's
expected utility falls against the committed board, both priced at the folded gauge
(`eval.score --gate`; the expectation is the mean over the runs taken).
