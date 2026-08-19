# r01-collapse — design doc — 2026-08-19

The design-doc phase of tranche 2 (the module collapse): `docs/module-collapse-design.md`,
drafted under the tranche-2 brief against the census + placement addendum
(`r00-collapse-census.md`) and the binding rulings (Q-R1…Q-R5; Q-O1…Q-O6 and r04 Q4 as
signed with the reviewer's sharpenings). No code changed; no `PRINCIPLES.md`/SPEC edit
(Appendix A proposes); `$LIFE_AGENT_KB` not read beyond what the PII guard's denylist needs
(the guard ran in default mode with the KB path set — the tranche-1 convention). Two files
delivered, then **STOP**: review of the design doc briefs the implementation phases.

## STATE

```
$ git rev-parse HEAD
5b2ec9084683c6fc44dc4156986ab6da52fd96e6   # 5b2ec90 (master; docs-only since b83dbc0 — no src change since the addendum's b83dbc0)
$ git status --short
?? docs/module-collapse-design.md
?? docs/unification/reports/r01-collapse-design.md
$ env -u LIFE_AGENT_KB TMPDIR=$HOME/.cache/life-agent/pytest-tmp uv run pytest -q --basetemp=$HOME/.cache/life-agent/pytest-tmp/bt-main -p no:cacheprovider
2419 passed, 34 deselected in 157.36s (0:02:37)
exit=0
$ uv run ruff check src tests
All checks passed!
$ LIFE_AGENT_KB=<kb> python3 .githooks/pii_check.py docs/module-collapse-design.md
guard exit=0
$ wc -l docs/module-collapse-design.md ; grep -c "^## " docs/module-collapse-design.md
719 docs/module-collapse-design.md
11        # §0–§9 + Appendix A
```

Suite and ruff are the main tree at HEAD (no source change in this phase; the run is the
STATE convention, not evidence of anything new). Files touched: `docs/module-collapse-design.md`
(new), this report (new). Not committed — the prepared script is
`~/.cache/life-agent/r01-collapse-design-commit.sh` (one docs commit; rehearsed, transcript beside
it), owner executes; push separate.

## DONE

**The design doc, written to the brief's ten sections + Appendix A.** Section by section, the
rulings and census rows each rests on:

| § | Content | Rests on |
|---|---|---|
| 0 | scope, non-goals (no reader cutover, no seam swap, no daemon changes, no new host folds), thesis, inputs of record, how to read a verdict | the brief; Q-R3; Q-O4; PRINCIPLES §15–§16 |
| 1 | **1.1 E-14 worked example** (`GO:9-11` vs `EX:190-205 → :203-218`, dies; the sensor stays); **1.2 the rule** stated once; **1.3 the table** — 85 mechanisms + D-1…D-15, one row each: verdict · disposition · locator (census → b83dbc0); **1.4 tallies** 36 / 27 / 22 and 5 / 4 / 6 | Q-R1 + Q-O1 (the rule and its exemplars); the reviewer's E-14 sharpening; census §4, §5; the addendum's correction table + F1 (the finer map) + F2 (E-7's rewritten lines) |
| 2 | **the one decision site**: the ranking (space `T ∪ K`, inputs, output, rule); **2.2 the fate of every census-§1 entry point** (18 rows: kept-as-site / one function / absorbed / leaves / dies / exception / shadow-only); **2.3 regimes** full vs terminals-only as *declared decision spaces* recorded on the decision, and the narrative terminal as a nested specification; **2.4 the daemon-wire contract table** (five wires, request/reply from `EX:459-465 → :472-478`, `EX:48-49`, `BR:635/:639 → :646/:650`); **2.5 `brain.value` claimed** as the terminals-only regime's VOI wire, dormant-keep iff the M0 wire-shape test | census §1.0, §1.1, §1.5 (the five `SEAM.commit` sites), §1.6, §3 traces A/B; Q-R3 (wire = boundary; daemon census → seam tranche); Q-R4; Q-O6 |
| 3 | **the one fold**: `posterior(policy=frozen-elicitations ∣ all-to-date)` as a regime indicator, `fold_version` covering the policy; **D-2's survivor** — `reliability(edge, cell)` unifying `LK.extractor_reliability` + `NR.population_posteriors`; `CAL` the debt (retirement path per the sharpening); `O.reliability_bins`/`ece` views; **3.3 the observation model declared once** (the 36 clauses named) | Q-O5 (with the Dawid reading); Q-O4 (+ sharpening: one reliability posterior behind the seam, declared views for the rest); census §2, D-2, D-8 |
| 4 | **the atom** `decide.u_assert` as source, `LK.action_utilities` and `GATE.realised_utility` derived (Q-O3 direction), the membrane world excluded; **the one price table** — every priced constant of census §6 with its home, incl. the finding that `lambda_usd` is defaulted `1.0` at `EX:434 → :447` and `0.0` at `GATE:171` (both die: Ū is the source) | Q-O3 (+ sharpening); census D-1, D-7, §6 literals; `UT:64-65` REQUIRED_LATENTS |
| 5 | **one driver + one poster** (Q-O6): the union body + two new fields `regime`, `policy`; no optional accounting field; A-3/D-10 die; the leaves return their decision, the driver records once (`decision_id = akey.cache_key` preserved); **one vocabulary** (D-6 partitions → derived views), **one label-view** (D-4), **one reason** (D-5); D-11…D-15 dispositioned | Q-O6 (+ sharpening: closes D-9, D-10, B-2/A-1); census D-4…D-6, D-9…D-15, `BR:765-830 → :776-841`, `AC:143-149` |
| 6 | **the register**: 6.1 G-1 (verdict mechanism only), 6.2 the membrane world, 6.3 `calibration.py` (+ 6.3b proposed: `GATE._sample_u`), 6.4 `brain.value` (conditional), 6.5 proposed: the seam's unavailability record — each with reason, non-coverage, pinning test | Q-O2 (+ sharpening: scoped to the verdict mechanism), Q-O3, Q-O4, Q-R4; census G-1…G-3, M-8, S-1 |
| 7 | **behaviour preservation, pre-stated**: 7.1 the suite; **7.2 the decision-equivalence fixture set** (view→decision pairs recorded once from the pre-collapse paths, replayed old vs new at the pure-function boundary; comparator = identical chosen action AND identical `/log_decision` body; command `scripts/collapse_replay.py --checkpoint`; pre-registered *direction* where the design intends a change); 7.3 the eval battery in the frozen regime (wrong commits must stay 0); 7.4 tranche-1 golden harness where a store is touched; **7.5 seven seeded defects** each with the instrument that kills it; never-silently-weaken carried over | the brief §7; Q-O2/Q-O5 (frozen regime); tranche 1 §9 (harness, kill list, the rule) |
| 8 | **migration**: M0 instrument → M1 E-14 → M2 poster → M3 fold (+ D-2) → M4 atom + table → M5 absorption (M5a/M5b split allowed) → M6 observation model (E-7 gated on Q3) → M7 register/vocabulary/config; per checkpoint: what moves, what stays dual (M2's shims for one step, else nothing), which instruments must be green, seeded defects re-run; S12 form | the brief §8 (recommended order followed, one addition M0, one argued split at M5) |
| 9 | ten open questions, each with the evidence that decides it: Q1 terminals-only on reach (O); Q2 6.5 register vs regime value (R); Q3 E-7 measurement first (O/R); Q4 G-3 (R); Q5 volatility (R); **Q6 the census pin sha is unreferenced** (O, F3); **Q7 the addendum under-reports six files' shifts** (R, F1); Q8 M3 lane delete vs flag-dead (O); Q9 the nested narrative terminal (R); Q10 monolithic B-7 (O) | F1–F3; census; the operating manual's §14 n_obs=0 entry (named as evidence for Q3, not cited as an input of record) |
| A | PRINCIPLES amendments, verbatim replacement text: A.1 §16 the three-verdict rule + the register pointer; A.2 §15 "the spine is transport" with mechanics recorded-not-priced and the no-host-preference-between-spaces/policies clause; A.3 a §14 resolved-decision entry (adoption, on signature) | Q-R1; the mechanics column's size (§1.4); Q-O5/§2.3 |

**Fresh transcripts (the four claims not in the census + addendum).**

*F1 — the finer line map for the six C5-hooked files* (the addendum lists them as changed with
no shift; census cites past the hook lines move):

```
$ python3 ~/.cache/life-agent/tranche2/linemap.py <file>   # hunks (old_start, old_len, new_start, new_len)
core/decisions.py [(141, 1, 141, 2), (142, 0, 144, 2)]        → cites ≥ :143 shift +3 (append :140 unshifted; read :145 → :148)
core/outcomes.py [(150, 1, 150, 2), (151, 0, 153, 2)]         → cites ≥ :152 shift +3 (reliability_bins :208 → :211; ece :230 → :233)
core/reactions.py [(110, 1, 110, 2), (111, 0, 113, 2)]        → cites ≥ :112 shift +3 (load_reactions :176 → :179; :185-187 → :188-190; :194 → :197)
core/claude_verdicts.py [(127, 1, 127, 2), (128, 0, 130, 2)]  → cites ≥ :129 shift +3 (latest_by_decision :137 → :140)
core/gather_outcomes.py [(84, 0, 85, 2)]                      → cites ≥ :85 shift +2 (warm_counts :87 → :89; grow_block :111 → :113)
core/joint_extract.py [(122, 2, 122, 4)]                      → cites ≥ :124 shift +2 (extract_joint :350 → :352)
```

The mapper is the same `git diff -U0 873860a HEAD` the addendum's table was read from, applied
per line rather than per range; every arrow in the design's §1.3 table comes from it (41 of the
100 rows carry a shifted locator).

*F2 — E-7's current form.* The census (pinned before it) describes the re-read as replacing the
channel at `EX:515`, `:585` and unconditionally at `:605-608`. The addendum marks `:512-519`
and `:605-610` *rewritten*; what rewrote them:

```
$ git log --format='%h %ad %s' --date=short -1 e4bb311
e4bb311 2026-08-18 fix(executor): a null re-read is absence of evidence, not disagreement
$ sed -n 525,546p src/life_agent/core/executor.py        # (excerpt)
            if _null_read(cr):
                # §14 (2026-08-18): the joint NAMED NOTHING. … retire the probe fail-open
                # and keep the posterior … A DISAGREEING read is untouched.
                applied = list(dict.fromkeys([*applied, probe]))
                dec = _decide(obs, rho, era, applied)
            else:
                …
                obs, era = cr["observations"], False                    # :540
$ sed -n 630,640p src/life_agent/core/executor.py        # (excerpt)
            # A DISAGREEING strong re-read replaces … A NULL read … retires fail-open …
            if not _null_read(cr):
                obs, era = cr["observations"], False                    # :636
```

So at `b83dbc0` a *null* re-read no longer replaces (retires fail-open); a *disagreeing* read
still replaces (`:540-541`, `:610`, `:635-637`). E-7's verdict and disposition in the design are
unchanged by this (a second channel, combined by likelihood — the disagreeing-replace is the
remaining host rule); its measurement is §9 Q3.

*F3 — the census pin is an unreferenced object:*

```
$ git merge-base --is-ancestor 873860a HEAD ; echo $?          → 1   (NOT an ancestor of master)
$ git rev-parse 873860a^{tree} 1ea9df8^{tree}
2a705c55adb67d14a9a0989604e42b45db2a23e5
2a705c55adb67d14a9a0989604e42b45db2a23e5                          (tree-identical: 1ea9df8 = "fix(pii-guard): close the HK/name gap …" on master)
$ git for-each-ref --contains 873860a ; git branch --contains 873860a ; git tag --contains 873860a ; git worktree list
(no ref; the census worktree at ~/.cache/life-agent-census/wt no longer exists)
```

The PII history rewrite re-created the pin's commit as `1ea9df8` (same tree); `873860a` still
resolves today only as a loose object. The drift table is a content diff and holds; the
*citation* needs a durable anchor — §9 Q6.

*F4 — the mapper reproduces the addendum's ranges for the four load-bearing files* (a
consistency check, not a new claim):

```
core/executor.py [(101, 0, 102, 13), (512, 8, 525, 20), (605, 6, 630, 9)]        → +13 / rewritten / +25 / rewritten / +28  (addendum ✓)
core/lookup.py [(658,1,658,1), (784,1,784,1), (847,1,847,1), (1109,0,1110,3), (1111,2,1114,2)]  → ≤1109 unshifted; ≥1110 +3  (✓)
bridge/server.py [(352,0,353,8), (353,0,362,1), (398,0,408,1), (410,0,421,1)]     → +8 / +9 / +10 / +11  (✓)
scripts/ask.py [(28,0,29,1), (1307,0,1309,3), …]                                     → ≥29 +1; nothing cited in :1307+  (✓)
```

**Locator discipline.** Every `file:line` in the design is a census cite (with the census's
abbreviations) followed by `→ :new` where F1/F4 move it; two cites the addendum could not map
(inside rewritten hunks) carry † and F2's lines. Spot-checked by hand this sitting:
`BR._utility :635 → :646`, `BR._grow_menu :639 → :650`, `EX.SEAM.commit :470-471 → :483-484`,
`LK.decide_and_record :1041 → :1044`, `LK:1074-1076` (unshifted — corrected once during
drafting), `EX._null_read :102` (new symbol, F2).

## DEVIATIONS

1. **The design cites two things beyond the census + addendum:** PRINCIPLES §15–§16 (the object
   of the tranche — unavoidable) and, in §7/§8, the eval battery's run-9 recipe and tranche 1's
   golden harness/§9 rule (the brief itself names them as candidate instruments). No corpus
   value, no `$LIFE_AGENT_KB` content.
2. **Two fields added to the poster's body** (`regime`, `policy`) — the brief's Q-O6 says "no
   optional accounting fields"; these are not accounting fields but the record of *which*
   decision space and *which* evidence policy ranked the decision (§2.3, §3.1). Flagged so the
   reviewer can strike them; without them the equivalence instrument cannot tell the two
   regimes apart.
3. **A fifth register entry is proposed** (6.5, the seam's unavailability record) beyond the
   brief's four; and a 6.3b (the gate's host sampler). Both are *proposed*, each with the
   question that decides it (§9 Q2, Q4).
4. **The migration order adds M0** (the instrument) before the brief's recommended E-14-first
   and argues an M5a/M5b split as *allowed*, not adopted.
5. **The classification's granularity is the census's** (one row per census id; where a census
   row bundles clauses, one verdict + the other clause's home named — §0's reading rule); the
   tallies (§1.4) are handles at that granularity, per the census's own DEVIATIONS 4.

## REFUSED

- No code, no test, no script written into the tree (the `collapse_replay.py` of §7.2 and the
  fixture recorder are M0 deliverables, named not built).
- No `PRINCIPLES.md`, SPEC, or daemon change; Appendix A is proposal text.
- No re-verification of unchanged census rows; no `$LIFE_AGENT_KB` read.
- No touching of the two gated witnesses, the Q4/Q7 prepared commits, or the pin alignment.
- No commit, no push; the prepared script waits for the owner.

## QUESTIONS

Owner: the design's §9 Q1 (terminals-only on reach), Q3 (E-7's measurement gates M6), Q6 (tag
the census pin or re-cite `1ea9df8`), Q8 (M3 lane delete vs flag-dead), Q10 (monolithic B-7
harness-only) — and **Q-O7: sign Appendix A.1–A.3** (verbatim replacement text; strike or
amend inline).

Reviewer: §9 Q2 (6.5), Q4 (G-3), Q5 (volatility), Q7 (append the six-file shift correction to
the addendum, or let §1.3 stand as the correction of record), Q9 (the nested narrative
terminal); DEVIATIONS 2 (the two poster fields) and 3 (the proposed register entries); and
**R-1: are 7.2's comparator and 7.5's kill list sufficient as the pre-stated instrument**, or
should the fixture recorder also capture the *daemon's* request/reply verbatim (Q-R3's
contract) so the seam tranche inherits a wire corpus?

## PROPOSED

Review of `docs/module-collapse-design.md`; on the owner's and reviewer's rulings (the
questions above), the implementation phases are briefed from the reviewed design — M0 (the
instrument) first, alone; M1 (E-14) second. Nothing else is proposed here. **STOP.**
