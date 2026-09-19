# r01 — design doc — 2026-08-18

Phase 1 of the ledger-unification tranche 1: the design document
`docs/unified-ledger-design.md`, drafted under the owner-signed Phase-1 brief (rulings
R1–R8, the four-citation research injection, the section-level requirements). No code
changed; no `PRINCIPLES.md`/SPEC edit (proposals only, Appendix A); no `$LIFE_AGENT_KB` reads
(the PII guard was run in `--shapes-only` mode for that reason). Two files delivered, then
STOP: owner approval of the design doc gates Phase 2.

## STATE

```
$ git rev-parse HEAD
873860a9b651fdc528bcd6b5f17f669205bca54a
$ git status --short
?? docs/2026-08-agent-litsweep-dispositions.m      # not mine (owner's, mis-saved; untouched — see r00 addendum 2)
?? docs/unification/                                # r00 + this report
?? docs/unified-ledger-design.md                    # this phase's deliverable
$ uv run ruff check src tests
All checks passed!
exit=0
$ TMPDIR=~/.cache/census-r01/tmp uv run pytest -q --basetemp=~/.cache/census-r01/basetemp -p no:cacheprovider
…
2317 passed, 34 deselected in 138.59s (0:02:18)
exit=0
$ uv run python .githooks/pii_check.py --shapes-only docs/unified-ledger-design.md
exit=0
$ wc -l docs/unified-ledger-design.md ; grep -c "^## " docs/unified-ledger-design.md
597 docs/unified-ledger-design.md
14        # §0–§12 + Appendix A
```

The suite was again run with temp storage on the root disk (`/tmp` is still over its user
quota — r00 STATE; the owner's item). No source file changed at this HEAD, so the suite result
is unchanged from r00's addendum. Files touched: `docs/unified-ledger-design.md` (new),
`docs/unification/reports/r01-design.md` (new). Not committed.

## DONE

**Design doc written to the R7 heading list** (0–12 + Appendix A). Section by section, the
rulings and census rows each rests on:

| § | Content | Rests on |
|---|---|---|
| 0 | scope, non-goals, prior-art positioning (ESAA arXiv:2602.23193; OpenHands SDK arXiv:2511.03690), one-sentence summary | tranche brief; research injection 1; R1–R8 named |
| 1 | the **scope table**: every census a.1 row 1–20 and a.2 row 1–18 dispositioned as migrates / dual-written / excluded (R8, reviewer R8a) / identity-not-event (R5) / projection-config-cache; the ten non-fold mutable stores each dispositioned; the twelve migrating `source_id`s enumerated; telemetry named as candidate (R8); `FAILURES.md` noted (R8) | r00 a.1, a.2, a.4; R5, R6, R8; reviewer R8a, R10 |
| 2 | typed `UnifiedEvent` (`event_id`, `source_id`, per-source `seq`, `tx_time_raw` verbatim, derived `tx_time`, `kernel_id`, `inputs`, `output`, `author`, `recorded_draw`, `record` verbatim, `format_version`); serialisation; **`seq` assignment at migration and at write for every live writer, and the sweep for the writer-less sources**; per-flavour `author`/`kernel_id`/`inputs`/`output`/`recorded_draw` table; bitemporality posture | R4, R5, reviewer R11 (identity), r00 a.4 (no `seq`, four clocks, six flavours without `format_version`), r00 a.1 #7/#10/#12, a.2 #14 |
| 3 | R4 interleave; **the corrected invariant** ("each fold's declared ordering key remains computable from the stream" — reviewer correction ii); the declared-per-fold merge-order table, incl. the utility fold's exact evidence order (elicitations `seq`, then reactions in first-appearance/latest-value order — `load_reactions :183-187`, `current_u_bar :981-1001`) and `boot_snapshot`'s owner-then-Claude precedent | R4; r00 (c) #7, #10, #12, #21, #27; reviewer correction ii |
| 4 | R5 written as the resolution; `kernel_id` = cache-key payload minus `input_hash` (foundations §2); replay of pkm = index replay + read replay, never re-execution; TOKI (arXiv:2606.06240) + GTD bitemporal precedent | R5; r00 a.2 #4–#5, a.3; research injection 3 |
| 5 | recorded-draw rule made precise: replay-as-recording vs re-execution (OpenHands); re-execution = new occurrence, never substituted; per-kind `recorded_draw` | `act-layer-events.md`; research injection 2; r00 (c) #23 (regrades append) |
| 6 | the derive/act predicate (`derived(e)` / `act(e)`), the diagnostic in one-question form, two census edge cases dispositioned (Claude verdicts; tasks asserted-by-agent/disposed-by-owner) | PRINCIPLES §7; r00 a.1 #4, #10 |
| 7 | **one adapter row per read-model** A1–A14 (existing fold, stream inputs, ordering key, identity kind) | r00 (c) #2, #5–#8, #10–#14, #19, #26–#28 |
| 8 | checkpoints C0–C6, each green/bisectable/one move; dual-write as end-state; sweeps for `utility.elicitations`, `pkm.demand`, `pkm.artifact` (pkm untouched, meta.json-last commit marker) | tranche brief Phase 3; r00 a.2 #4 (pkm writer not atomic), a.1 #13 |
| 9 | **pre-stated criteria** per artefact with comparator and command (`golden compare <artefact>`); R1 byte for `state.md`; R2 semantic for `gtd.db` with the exact column list (and the `created_at` finding: `store.apply` writes `tx_time`, so it stays); R3 dual criterion with the pinned credence digest and the parity-datum note; the **seeded-defect obligation** (reordered / dropped / substituted, each with the criterion it must kill) | R1, R2, R3, R5, R6; reviewer R2a, R10; r00 (c) note on `created_at`; `brain._SKIN_PINNED :40-43` |
| 10 | **durability contract**: segment per source, single writer per segment under a lock, fsync-per-line, loud torn-line reading, crash promise, temp+rename for derived files; OpenHands sub-ms marked "preprint figure, unverified"; SSGM as the against-heavy-in-path-verification citation | R7 addition; r00 a.0/a.4 (three regimes); research injection 4 |
| 11 | change surface: `src/life_agent/ledger/` only + one mirror call per writer; no pkm/brain/spine change; no new format/dep; PII posture; out-of-scope list | tranche refusal list |
| 12 | thirteen open questions, each with the evidence that decides it | — |
| A | A.1 PRINCIPLES §7 replacement text (verbatim); A.2 retire "governor" — evidence lines from r00 (e), replacement text for PRINCIPLES §14's bullet, engine-design §12, system-design L3 row and three prose sites, and the three vestigial code comments listed as follow-up | r00 (e); PRINCIPLES `:122-123`, `:148`; engine-design `:400-402` |

**Research injection, verified to exist** (abstract pages fetched 2026-08-18; nothing beyond
title/abstract entered the doc):

```
arXiv:2602.23193  ESAA: Event Sourcing for Autonomous Agents in LLM-Based Software Engineering (Feb 2026)
arXiv:2511.03690  The OpenHands Software Agent SDK … (Nov 2025, rev. Apr 2026) — abstract: "negligible event-sourcing overhead"
arXiv:2606.06240  TOKI: A Bitemporal Operator Algebra for Contradiction Resolution in LLM-Agent Persistent Memory (Jun 2026)
arXiv:2603.11768  Governing Evolving Memory in LLM Agents … (SSGM) (Mar 2026, rev. May 2026)
```

**Code facts the design leans on, read this phase** (transcript excerpts):

```
$ sed -n 981,1001p src/life_agent/core/lookup.py       # current_u_bar: elicitations then load_reactions
    events: list[UT.Evidence] = list(UT.load_elicitations(config.UTILITY_ELICITATIONS, model))
    events += R.load_reactions(config.REACTIONS_LOG, config.DECISIONS_LOG)
    version = UT.fold_version(model, events)
$ sed -n 103,142p src/life_agent/tasks/store.py         # apply: created_at/completed_at come from event.tx_time
    "INSERT OR IGNORE INTO tasks (identity, user_id, text, list, due_date, is_today, origin, created_at) VALUES (…, event.tx_time)"
    "UPDATE tasks SET completed_at = ?, is_today = 0 WHERE identity = ?"  (event.tx_time, …)
$ sed -n 33,62p src/life_agent/trips/store.py           # reservation: identity TEXT PRIMARY KEY (no autoincrement)
$ sed -n 38,50p src/life_agent/core/brain.py            # _SKIN_PINNED = ghcr image @sha256:… ; PROTOCOL_MAJOR = "1"
$ sed -n 176,205p src/life_agent/core/reactions.py      # latest[(decision_id, kind)] = r ; out from latest.values()
```

## DEVIATIONS

1. **Reviewer corrections carried forward, verbatim as context** (per the brief): (i) the
   tranche brief's candidate decider list included `decide.py`, `executor.py`, `pricing.py`;
   the census disposition stands — they are a pure atom, an enactment body, and a price
   table. (ii) The brief's merge requirement "preserves each original ledger's internal order"
   is refined: the invariant is that **each fold's declared ordering key remains computable
   from the stream** (the trips fold orders by fidelity then `received_at`, not file order).
   §3 states the invariant in this corrected form.
2. **Reviewer rulings relayed on 2026-08-18 but not in the signed Phase-1 brief were followed
   and cited distinctly** (as *reviewer R2a / R8a / R9 / R10 / R11*) rather than dropped:
   trips in scope (R10); unified `event_id` = hash over `(source_id, seq, verbatim record)`
   (R11); the full exclusion list incl. dogfood/owner.md/deliberate/snapshots/fair-fight
   (R8a); the `created_at`-comparator refinement (R2a — noted moot because `store.apply`
   writes `tx_time`); harness scratch outside tree and KB (R9). Each is a QUESTIONS item for
   signature below. If the owner intended the signed R1–R8 to be exhaustive, the affected
   text is §1 (trips row, exclusion rows), §2 (`event_id`), §9 (A1 comparator note, A3), and
   they can be struck without touching the rest.
3. **`kernel_id` for pkm occurrences is a digest computed outside `compute_cache_key`.** Not a
   cache key; named in §4 and §12 Q4 rather than assumed permitted.
4. **The stream and golden snapshots are placed under `$LIFE_AGENT_KB/ledger/`.** The tranche
   brief's refusal 7 forbids touching KB contents "beyond read-only replay"; Phase 3's
   dual-write necessarily writes a new KB subtree, and snapshots of real projections hold
   personal data so cannot live in the tree or `~/.cache`. Flagged in §9 and QUESTIONS 1;
   nothing was written to the KB in this phase.
5. **SSGM citation.** The owner's dispositions characterise SSGM as "the warning against heavy
   in-path verification"; the abstract-level check I ran did not itself surface that warning
   (the abstract describes consistency verification, temporal decay, access control). §10
   cites it *as characterised by the dispositions*; the owner may want the body-of-paper
   page reference before the doc is adopted.
6. **`superpowers:brainstorming` not invoked** for the design phase — the census → questions →
   signed rulings sequence is the repo's own, more rigorous, equivalent, and the brief
   prescribes the section content.
7. `/tmp` remains over quota; the suite ran with root-disk temp (as in r00).

## REFUSED

- No code changes; no edits to `PRINCIPLES.md`, any pkm SPEC, `docs/derivation-engine-design.md`,
  or `docs/system-design.md` — Appendix A proposes replacement text only.
- No `$LIFE_AGENT_KB` reads (PII guard in `--shapes-only`; the denylist mode is the owner's
  commit hook).
- No research beyond the four injected citations; the tool-contract literature and any
  restructuring around it did not enter the doc (nothing arose that needed the QUESTIONS
  escape hatch).
- No commit.

## QUESTIONS

**Needing the owner's signature:**

1. **KB write authorisation for Phase 3.** Confirm that `$LIFE_AGENT_KB/ledger/` (segments,
   `MANIFEST.json`, `golden/<T0>/` snapshots) is the sanctioned write, given tranche refusal 7.
   Without it Phase 3 has nowhere PII-safe to put the stream.
2. **Sign or strike the relayed reviewer rulings** followed in DEVIATIONS 2: R10 (trips in
   scope), R11 (`event_id` definition), R8a (full exclusion list), R2a (moot as designed),
   R9 (harness scratch under `~/.cache/life-agent/basetemp`, outside tree and KB).
3. **A4b's single Julia run** — the credence image digest and `PROTOCOL_MAJOR` are pinned in
   the transcript (R3); confirm the run may pull/run the pinned skin on this machine (it is a
   `docker run` per `brain.py`).
4. **`created_at` in the A1 comparator** — keep (fold-determined, as designed) or exclude
   (R2a's letter)? A design choice, per the reviewer; the doc keeps it.
5. **Appendix A.2 (iii)** touches `docs/system-design.md` wording — within "retire the word",
   or beyond Appendix A's two jobs? If beyond, strike (iii)-(iv) and the retirement is
   PRINCIPLES + engine-design only.

**Needing a reviewer ruling:**

6. **§12 Q1** — logical union of per-source segments as "one stream", or one physical file?
7. **§12 Q4** — does pkm's "never hash outside `compute_cache_key`" reach the `kernel_id`
   digest (which is not a cache key)?
8. **§12 Q13** — reader policy at cutover (loud vs the act ledgers' silent skip) — a design
   intent question the reviewer can settle now so C0's unparseable count is interpreted
   correctly.
9. **§9's seeded-defect list** — sufficient as the minimum, or should the harness also seed a
   *cross-source* defect (a reaction whose `decision_id` points at no decision — an unrouted
   verdict, which today folds to nothing and must stay so)?

## PROPOSED

On the owner's approval of `docs/unified-ledger-design.md` (and rulings on Q1–Q9): open Phase
2 — build the golden-replay harness against the **legacy stores first** (snapshot + replay
through the existing folds, comparators exactly as §9 states them, the three seeded red runs
demonstrated with transcripts), then report `r02-harness.md` and STOP.

## RULINGS RECEIVED — addendum (2026-08-18, reviewer via the owner; recorded, and the design doc revised)

**Verdict, as relayed:** approve the design doc, **conditional on one clarification to §10**
(the torn-tail repair protocol), plus rulings on r01 Q6–Q9 and recommendations to the owner
on Q1–Q5. The reviewer's note that DEVIATIONS 5 (SSGM's abstract not carrying the attributed
warning) is "the verification discipline working against my input" is recorded; the
verify-before-cite list now holds the OpenHands figures and the SSGM characterisation.

**Applied to `docs/unified-ledger-design.md` in this session** (allowed by the reviewer as
"the agent's first act of Phase 2, or a one-line r01 addendum — either, so long as it lands
before the harness is built"; done as a dated *Revision* note under the doc's Status block, so
the change is visible, and recorded here). Transcript of the edit (each replacement applied
exactly once):

```
$ python3 - <<'EOF'   # twelve exact-string replacements, each asserted to match once
1 × Status block — Revision 2026-08-18 note
1 × §2 seq = ordinal among PARSEABLE lines (torn tail is not a line)
1 × §2 schema comment — kernel_id namespace-tagged `instrument:sha256:<hex>`, never computed inside pkm
1 × §2 table — pkm.artifact kernel_id = `instrument:sha256:<hex>`
1 × §4 — Q7 ruling: rule not engaged, two conditions adopted; verbatim-fields fallback unnecessary
1 × §8 C0 — flag duplicate-key JSON lines separately (json.loads keeps the last value)
1 × §9 — "kill categories" wording
1 × §9 — kill category 4 (cross-source retarget: repoint a folded reaction's decision_id at a different EXISTING decision → kills A6, A4a) + pinned-invariance fixture (unrouted reaction stays inert, outputs identical) + crash fixture for the torn tail
1 × §10 — Torn tail protocol (the required clarification)
1 × §12 Q1 — RESOLVED: segments
1 × §12 Q4 — RESOLVED: not engaged (conditions)
1 × §12 Q13 — RESOLVED: loud
done
632 docs/unified-ledger-design.md
```

**The §10 clarification, as now written (one paragraph, quoted):** *A torn line was never an
event.* On open-for-append the writer checks the tail; if the last physical line is
unterminated or unparseable, it records the torn bytes in the manifest (segment, byte offset,
length, bytes hex-encoded, detected-at) — quarantined, never erased — and terminates the
physical line with a newline so no later append concatenates onto it; the segment is never
truncated. `seq` is the ordinal among *parseable* lines, so the parseable-line count is the
sweep's resume point, the re-appended canonical line reuses the torn ordinal (its `event_id`
is what the torn line's would have been — dedup stays well-defined), and density holds.
Readers skip exactly the manifest-quarantined byte ranges and read every other line loudly.
(One implementation choice made explicit here because the reviewer's sentence left it open:
"never truncation" is honoured *physically* — the torn bytes stay in the segment, terminated
by a newline and listed in the manifest — rather than by moving them out of the file; if the
reviewer intended physical removal-after-quarantine, that is a one-line change to §10 and
the crash fixture, not to any criterion.)

**Rulings Q6–Q9 (reviewer, binding), as applied:**
- **Q6 — segments.** "One stream" names the logical object (one schema, one total order, one
  manifest). §12 Q1 marked RESOLVED.
- **Q7 — `kernel_id` digest: pkm's hashing rule not engaged**, with two conditions (never
  computed inside pkm; namespace-tagged) — §2 and §4 amended; §12 Q4 RESOLVED.
- **Q8 — reader policy: loud**, ruled now; consequence in this tranche interpretive only;
  C0 additionally flags duplicate-key JSON lines. §8 and §12 Q13 amended.
- **Q9 — the proposed unrouted-reaction defect is a pinned-invariance fixture, not a kill**;
  the genuine cross-source kill is the retargeted `decision_id` (kills A6, A4a). §9 amended
  with both, in named categories.

**Owner items — reviewer's recommendations, awaiting the owner's signature (Q1–Q5):**
Q1 authorise KB writes narrowly, confined to `$LIFE_AGENT_KB/ledger/` (stream + golden
snapshots are owner data and belong under backup; R9 kept only *test scratch* out); Q2 sign
R2a/R8a/R9/R10/R11; Q3 sign the single Julia run of the pinned skin (`docker run`, digest and
`PROTOCOL_MAJOR` in the transcript — the first credence→proplang parity datum); Q4 keep
`created_at` in the A1 comparator (R2a's letter yields to its intent; a future `apply` that
omits it *should* turn A1 red); Q5 keep Appendix A.2 (iii) — the word surviving in
system-design's L3 row would leave the contradiction alive; the code comments stay deferred.

**Status.** Design doc revised as above; **Phase 2 opens on the owner's signatures on Q1–Q5**
("Phase 2 opens on the brief as written: harness against the legacy stores first, three kill
categories plus the invariance fixture, seeded red runs with transcripts, `r02-harness.md`,
STOP"). Nothing else was started. STOP.
