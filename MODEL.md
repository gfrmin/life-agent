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
argmax of expected utility over one flat list of rows, ties to the first-listed. Every
choice is a row: one `abstain`, one `gather` per open transform, one `ask`, one `cite` per
document, and one `respond` per candidate (at that candidate's own credence). `gather` and
`ask` are evaluated at `p1`,
the MAP candidate's credence (P(asserting now is right)):

| action | effect | loss / price |
|---|---|---|
| `respond` | commit a candidate span (one row each) with its citation | `u_correct = +1` if right, `u_wrong = −9` if wrong |
| `cite` | name the document believed to hold the answer, without asserting the value (one row per document) | `u_cite_right = +0.5` if the document attests the answer, `u_cite_wrong = −1` if not |
| `abstain` | decline | `u_abstain = 0` |
| `gather` | run an unapplied evidence transform (one row each), then decide again | the transform's price; the measured value of the gather sequence (below) |
| `ask` | ask the owner a clarifying question | the owner's attention; recovers the answer at the measured rate `r_a` |
| `escalate@r` | hand the question to rung `r` (J1–J2) | the rung's price, and its learned reliability `p_r` |

**A partial answer: the document, not the value.** `cite` names one document and says what is
held back; it never asserts a value. A document is one observation group (`group` on the
wire, one per artifact, which is how the posterior already tempers correlated chunks). The
chance that document `g` holds the answer is the credence of the candidates its observations
report, `P(g) = Σ p_i` over those candidates `i`, and

```
EU(cite g) = P(g)·u_cite_right + (1 − P(g))·u_cite_wrong
```

The two utilities are latents with declared priors, N(0.5, 0.3) on [−1, 1.5] and N(−1, 0.7)
on [−6, 0.5] ("a right pointer is half a right answer; a wrong one costs one read"). They are
optional in a model file and read their prior means, 0.5 and −1, when absent. `cite` is graded
by attestation: right iff the cited document attests the gold (`eval/withheld.attesting_artifacts`,
the grader's own matcher over the catalogue). It is deliberately not a hedge over a set of
values (the retired `hedge` row was priced independently of how many values it named, so
widening the set could only raise it): a cite names exactly one document, and `P(g)` is a
probability of that document, so a wider set of candidates cannot buy a better row. Cite
undercuts `respond` between its bar against abstaining and `respond`'s: where one document
holds the answer at `P(g)` above 2/3 (at the declared gauge) and no candidate is certain enough
to state, the act points to it. The derived respond bar, which now also has to outbid `cite`,
rises accordingly; `respond_threshold` reads the cite row at `P(g) = p1`, a lower bound on the
bar the decider applies (a document's `P(g)` is at least the credence of the candidate it
holds). A reaction to a cite reply is recorded and not folded into the utility posterior: "bad"
may mean the wrong document or "I wanted the value". The executor flags which observations stand behind a retrieved document; the decider lists a
cite row only for groups holding one (a synthesised read is not a document).

**A state with no candidate is decided like any other.** When extraction finds nothing the
executor still asks `bayes_act`, with no candidate and no observation: the posterior is
NONE with certainty, `p1` is 0, and the rows are `abstain`, one `gather` per open probe and
`ask` (there is nothing to respond with). The gather row is read in its leader-wrong state,
the same measured row as everywhere else. At today's gauge that row is worth less than
abstaining, so the state ends declined and no rescue probe runs; a gauge with a smaller
`|u_wrong|` would buy the probes, and a candidate one of them mints is decided on like any
other, entering at the rescue reliability (`min(0.5, its stated confidence)`).

**The route is a state too.** Before any retrieval the router (`core/lookup.route_question`)
says what the question asks for: one value to read off a document (`lookup`), or one of four
answer types (`kind`): a `list` or set, an `aggregate` the reader must compute, a `summary`
(or comparison, or explanation), several values at once (`multiple`). Each of the four is an
answer that is not a single span, so it lies outside the world of §1 (candidate spans, or
`NONE`) and attempting it cannot end right. The verdict is an observation of the answer type,
and the only uncertainty is whether the router is right. The verdict and the kind are two
separate readings (the kind is asked only of a rejection), so that naming the kind cannot move
the verdict. `route_options` lists `abstain` and
`attempt`, and the same argmax ranks them:

```
EU(attempt) = q·V_lookup + (1 − q)·V_other − price
V_lookup    = r·u_correct + w·u_wrong + (1 − r − w)·u_abstain
V_other     = w_other·u_wrong + (1 − w_other)·u_abstain      (never right)
```

Measured (`core/route_row.py`, `scripts/fit_route_row.py`): `q`, one per verdict, is P(a
single-span answer | verdict), a Beta(1, 1) mean over the labelled route audit; `r` and `w` are
the right and wrong rates of attempted lookups in the pinned archives; `price` is the first
pass's metered dollars (`pricing.FIRST_PASS_USD`) at `lambda_usd`. `w_other` is an assumption,
not a measurement: it is set to `w`. Unfitted, a KB starts from the shipped row
(`config/route-row.example.json`); with no row at all the prior declines every question. At the
shipped row an accepted question is attempted and a rejected one declined, at `u_wrong` of −9
and of −5.13; a rejection is attempted only where `q@reject` exceeds about 0.44 and 0.27. A
declined question writes a `route` decision row (the router's verdict and kind), kept out of
the utility fold like a `miss`.

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
0.5 unmeasured). A preposterior over the current posterior is a door (ROADMAP).

Measured once against the gate grades (2026-09-22; the newest 300 lookup decides, 267 graded,
three runs over one question set): the exact one-step preposterior, run on the corroborate
tiers' declared reliabilities (`pricing.TIER_RHO`, 0.80/0.90/0.95), agrees with the fitted row
on 251 of 300 (the row re-decided at step 0 on each final posterior; the ledger keeps nothing
earlier). On the 31 where it would gather and the row responds, every `p1` is above the
0.837 respond bar (the upper end is unmeasured) and the graded ones were 28 right, 0 wrong: the
channel says a gather is worth buying where the answer was already right. Either the declared
tier ρ overstate what a corroboration buys, or the posterior is underconfident there. That is
a calibration job, not a decision one: the tiers have no edge in `core/reliability.py` yet, and
the gate archives are its data. The other 18 disagreements (the row abstains, the preposterior
would gather) are undetermined: 15 had the gold in the corpus, but whether a gather reaches it
was not measured.

**Escalation.** A rung fires only when `p_r·u_correct + (1 − p_r)·u_wrong − λ$·price`
beats every local action, so at `u_wrong = −9` a rung needs `p_r` above 0.90 net of price.
Rungs: (1) a strong model over a wide retrieval window with a citation audit; (2) Claude Code
over the corpus (`claude -p` with the pkm MCP server). Each rung's `p_r` is learned from
verdicts (a Beta per rung).

**What leaves the machine.** No document is withheld from a model on privacy grounds.
Extraction sends the retrieved chunks to a cloud model on every question, and the
deliberative rung can search the whole corpus. Every model call that carries corpus text is
recorded in `$LIFE_AGENT_KB/calibration/disclosures.jsonl` (`core/disclosure.py`): one row per
call on the `extract`, `joint`, `rerank` or `deliberate` path, holding the time, run and
question ids, the model, the artifact cache keys, the chunk and character counts, and
`outcome` (`ok` or `failed`); never a document's text, never the question. A failed or
refused call writes its row; a cache hit calls no model and writes none. The deliberate
rung's row is read off the pkm tool log it leaves behind, and a rung's reply names how many
documents were disclosed to it (the decision record's `disclosed`).

**Division of labour.** `core/posterior.py` computes the candidate posterior;
`core/utility.py` folds the loss; `core/decide.bayes_act` takes the act, each open transform
and each candidate being its own row of the one argmax; `core/enact.py` lists the open
transforms and turns the winning row into a reply. With one measured gather row shared by
every transform the rows differ only by price, so the cheapest transform wins, and with
`u_correct > u_wrong` the respond rows rise with credence, so the MAP candidate wins: both
follow from the argmax, neither is a rule.

## 5. Laws

Each is a test or a failing check, not a guideline; the test that enforces it is named, or the
law is marked **unenforced**.

1. **Never invent.** A `respond` names a candidate with at least one grounded observation;
   otherwise the act is not available. Tests: `tests/test_lookup.py::test_ungrounded_quote_is_indeterminate_and_recorded`
   (an ungrounded quote is no observation), `tests/test_decider.py::test_a_certain_leader_is_reported_and_an_uncertain_one_withheld`.
2. **String-blind.** The decider receives indices and numbers, never candidate text.
   Tests: `tests/test_decider.py::test_the_act_is_blind_to_candidate_text` (reversed, random or
   identical candidate strings leave the act and its view unchanged) and
   `::test_the_decider_modules_never_read_a_candidate_string` (an AST check).
3. **One argmax.** No module but `core/decide.bayes_act` ranks actions; its callers are
   drift-gated. Test: `tests/test_decider.py::test_only_the_decider_takes_the_act`.
4. **Provenance.** Every reply carries its origin; every commit, its citation and credence.
   Tests: `tests/test_executor.py::test_the_view_carries_its_origin_and_the_render_leads_with_it`,
   `tests/test_decisions.py::test_origin_is_documents_rung_or_declined`.
5. **Write-once records.** Decision, disclosure and verdict rows are never edited; a
   retraction is a new row. Tests: `tests/test_outcomes.py::test_append_appends_never_truncates_and_order_is_preserved`,
   `tests/test_derivations.py::test_record_is_write_once`, `tests/test_disclosure.py::test_the_log_is_opened_in_append_mode_only`;
   `tests/test_write_once.py` (the five logs' modules open nothing for writing and write through
   `jsonl_log.append_line`); a re-posted decision leaves one row
   (`tests/test_bridge_server.py::test_log_decision_reposted_leaves_one_row`).
6. **One home per constant.** Channel constants, prices and the action vocabulary are each
   declared once (`core/pricing.py`) and bound everywhere else. Test:
   `tests/test_pricing_table.py::test_no_priced_constant_is_declared_outside_the_table` (prices only).
7. **Named degradation.** Bridge down ⇒ the reply says so; there is no fallback decider. A
   failed rung ⇒ a disclosure row and no answer. Tests: `tests/test_ask_client.py::test_answer_names_a_down_stack`,
   `tests/test_executor.py::test_the_body_side_cascade_is_gone`; the failed-rung clause:
   `tests/test_disclosure.py::test_a_failed_rung_leaves_a_row_and_no_answer`.
8. **Correlated evidence is tempered.** Copies of one attestation never count as independent.
   Tests: `tests/test_posterior.py::test_the_temper_counts_chunks_and_documents_below_their_number`,
   `tests/test_bridge.py::test_same_document_shares_one_ancestry_group`.
9. *(Retired 2026-09-30, ruling 5: SEALED documents were never built. The number is not reused.)*
10. **Calibration is measured.** A-CAL is read off the verdict stream, never assumed.
    **Unenforced:** `outcomes.ece` and the edge curves are unit-tested
    (`tests/test_outcomes.py`, `tests/test_calibration.py`), but nothing fails when calibration goes unread.

## 6. Scoreboard

`eval/score.py` → `SCOREBOARD.md`. Per set and arm: rows · right · wrong · escalated-right ·
escalated-wrong · cite-right · cite-wrong · declined · $/q · U/q · s/q. `right` and `wrong`
count value answers only; `cite-right` and `cite-wrong` count partial answers (neither right,
wrong nor declined), priced at `u_cite_right` and `u_cite_wrong` in U/q. The router recombination
treats a cite as any other non-assertion (it escalates), so the router row carries none. Sets: `owner` (the owner's 104 questions, typed arm; `owner-0920` keeps the frozen 2026-09-20 outside and router rows),
`generated` (212 questions extracted from the corpus by `make golden`), `atm` (ATM-Bench
email-only number-typed, 198), `live` (the stream since the reset), `sample` (synthetic, CI). Every row is graded by exact match. Rule 5: the loss
decides and the board is evidence. A pinned set is one biased draw, so a row whose utility
fell against the committed board is listed (`eval.score --falls`) and explained, not vetoed.

The board also prints calibration (`eval/calibration.py`): for the typed arm, `p1` — the
probability the decider gave its leading candidate — against whether that candidate matched
the gold, as a mean log score, an ECE and a reliability table. It is scored on every row with
at least one candidate, whatever the act (an abstain still has a leader). Rows with no
candidate are counted and not scored; rows where no candidate matches the gold are scored
(the leader is wrong) and counted as truth-absent. An archive that predates the recorded
fields takes its calibration from the decision log, joined to the set's questions.

A **withheld-source** set (`python -m eval.run --withhold-source`, `eval/withheld.py`) re-asks
each generated question with every document that contains its answer (any chunk the grader's
matcher finds the gold in, plus the question's own source) taken out of retrieval, and the
deliberative rung off. The answer is then absent: a decline is right, an assertion is wrong, and
an assertion of the gold is a leak (a missed attestation), counted and flagged; it scores as a
`typed` set. It exists because the answerable-only sets cannot fit the channel: there "a leading
candidate exists" and "the leader is right" are nearly one event, and a fit on them absorbs that
base rate.

## 7. The read path

```
scripts/ask.py / reach/jarvis.py
  └─ core/ask_client.drive
       └─ core/executor.run_pass     the loop; holds NO posterior and picks NO action
            └─ bridge/server.py      :8798 gathers and SHAPES evidence, and hosts the decider
                 ├─ /route           the router's verdict for every question (core/lookup.route_question);
                 │                   /decide then attempts it or declines it (the route state, §4)
                 ├─ /retrieve        BM25 over DuckDB FTS
                 ├─ probes           subject, recency, corroborate, deliberate
                 ├─ /extract         LLM per chunk → candidates + integer observations
                 └─ /decide          core/decider.py: core/posterior.py → decide.bayes_act → enact
```

The bridge gathers evidence and hosts the one decider. With the bridge down the reply says the
decider is unavailable; nothing answers in its place (law 7).
