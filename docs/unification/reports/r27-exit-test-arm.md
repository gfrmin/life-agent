# r27 · K4 — the exit test gets an arm, and the oracle gets fit to read it

> **Status: PRE-REGISTRATION FROZEN.** Committed BEFORE any `src/`, `tests/`, `scripts/` or
> `.githooks/` change. Results append below the rule; nothing above it is edited afterwards.

## Why this exists

The completion programme's last stage is the MVP exit test — *"a week of the owner asking
Jarvis instead of the incumbent harnesses for life-data questions + morning triage, misses
logged to `FAILURES.md`"* (`ROADMAP.md:161`). Asked on 2026-08-28 whether it is running, the
owner said it is **not used**, and gave the reason: a general coding agent does the same
job.

That is a claim about expected utility, it is the premise the whole system rests on, and
**nothing in tree has ever tested it.** The §8 gate's `monolithic` arm is a single model
call over the same retrieval hits — it cannot search, run a derivation, iterate, or re-read.
The comparator the owner actually uses has never been an arm. So the exit test does not need
the owner to change their behaviour; it needs the missing arm.

The rest of this milestone is what has to be true for that reading to mean anything: an
oracle that cannot be shown a green it did not earn, and two guard holes that are live in
merged master with no plant.

## What was verified before this pre-registration

Each of these was read off the deployed artefact, not inferred.

| | Finding | How |
|---|---|---|
| **V1** | The real asked questions are recoverable as text. 189 distinct `question_id`s on the non-gate lanes (`ask` 1313 rows, `answer-brain` 506); the text survives at `producer_metadata.inputs.question` in the pkm cache's `meta.json` (written at `core/derivations.py:485-500`), for the question-keyed `life_agent.ask.*` producers | walked the cache, decoded three records, confirmed a non-empty `question` string on each |
| **V2** | Production is unobservable from the authoring box, **and the watch reports green anyway.** No life-agent unit runs here. The post-deploy non-gate rows in this KB are local test traffic — a burst in a four-minute window, all `regime=terminals-only`, all carrying a posterior that does not vary with the question. `production_readout.py` nonetheless reported one root, a fresh newest row, and no staleness flag | ran the readout; cross-read the decision rows by lane, day and `chosen_action` |
| **V3** | **Row 25 can detect a stale source but not an absent one.** A root that was never declared cannot be stale, so an entire deployment's silence is invisible to the instrument built to watch it | read `readout`'s window derivation against its `sources` handling |
| **V4** | The oracle's control set is structurally distinguishable from every real fixture: it omits `provenance.python_hash_seed` (deliberately, to dodge the seed refusal at `scripts/collapse_replay.py:134-141`) and carries a distinct `engine_version`, so the compare loop can be gated on a control-only tell | read the control constructor against the recorder's |
| **V5** | `bad = len(failed) + len(errored)` (`collapse_replay.py:168`), and the control set contains **zero** fixtures that raise — so the mirror mutation `bad = len(failed)` exits 0 on unreplayable fixtures with every control green | read the loop; enumerated the control set |
| **V6** | The comparator's field classes are hand-written literals (`collapse/fixture.py:42-63`) constrained only by disjointness and subset-of-union. Nothing constrains **which** class a field lands in; five of the twelve value-compared decision fields have no value-pinning test | read the sets, the branch at `compare.py:95-110`, and every test that names them |
| **V7** | The replay never reads its own manifest. `FX.read_all` globs `*.json` and explicitly skips `manifest.json` (`fixture.py:190-194`); `n_fixtures`/`fixture_ids` are never compared to the globbed set | grepped the replay for `manifest`: absent |
| **V8** | `read_text_or_refuse` (`.githooks/pii_check.py:195-206`) returns "skip" on **file extension, before the NUL refusal**, so the bytes are never inspected. `_BINARY_SUFFIXES` (20 entries) is pinned by nothing and announced never; `announce_skips` reports only `_SKIP_PATHS` | read the decode funnel and all three intake paths |
| **V9** | **The hole at V8 is open, not exploited.** Four tracked files carry a declared-binary suffix; all four are genuinely compressed binary that merely contain no NUL byte. The exposure is prospective: a text-layer PDF or a plain-text `.db` would ride every leg green, and the directory it aims at is the extractor-fixture tree | scanned every tracked file with a declared-binary suffix for NUL bytes and read the survivors' headers |
| **V10** | The substring-proof census (`tests/poison/test_guard_shape_poison.py:29-53`) matches one spelling; **that spelling appears nowhere in tree**, while at least seven other spellings of the identical proof are live | enumerated the matching form and the evading forms across `tests/` |

**V9 is stated because the tempting version of V8 is wrong.** "PII is leaking" would be a
false alarm; "a guard's universe is narrower than the property it stands for, and the gap is
prospective" is the finding. Both quantities are published so the reader can check the
distinction rather than take it.

## What this milestone is NOT

- **It does not adopt the agent arm.** Strand A's pilot is a *sizing* read. Its own frozen
  consequence (C3) forbids it from adopting, retiring, deploying or routing anything.
- **It does not patch the census rules.** Register rows 22, 23 and 12 stay defeated. The
  map made before this prereg shows row 22's own discriminator is a one-line spelling
  census of exactly the kind row 22 forbids, and row 23 matches a single literal while
  being blind to function annotations. Patching them is the fourth consecutive pass over
  the same class; three passes running have defeated most *resolved* rows. **That is a
  ruling to be taken, not a fix to be reflexed**, and it is carried to the owner as K5.
- **It does not add a deployment origin to the record.** Deferred with the reason recorded:
  it moves all 314 replay fixtures and buys nothing while one deployment serves and the
  exit test is not being run by hand. It stays as known-and-uncovered and reopens the moment
  a second live stream exists.

## FROZEN CRITERIA

**C1 — the harvest leaks nothing.** The real-ask set lands only under `$LIFE_AGENT_KB`. In
tree: counts, family mix and date span. **No question text, no corpus value, and no count
paired with an identifier that could single one out.**

**C2 — the agent arm is priced on the same terms as every other arm.** It answers the same
question under the same rubric; `λ_usd` spend is recorded per question; a missing latent
fails loud rather than defaulting (M4's E-5 rule).

**C3 — the pilot is a sizing read, and says so before it reads.** Sample frame, δ, level and
conjuncts committed before the run. The report states in its own results that it adopts
nothing. Whether a full run follows is a keypress, not an inference.

**C4 — the oracle's control cannot be told apart from a real fixture.** Either the control is
produced by the recorder's own constructor, or the replay refuses to read any field outside
the declared fixture contract. RED under a mutation that gates the compare loop on a
control-only tell and still prints a full pass.

**C5 — an unreplayable fixture is a failure.** The control set contains a fixture that
raises. RED under `bad = len(failed)`.

**C6 — the comparator's universe is the recorded body.** Every key the recorder emits is
classified; an unclassified key fails. `VALUE_COMPARED` is pinned by equality, and each of
the five fields with no value-pinning test today gains a kill test. The never-silently-weaken
rule already *stated* at `fixture.py:20-23` and enforced nowhere becomes enforced.

**C7 — the replay reads its own manifest.** A set mismatch against `n_fixtures`/`fixture_ids`
is a refusal. RED under a doctored fixture set of the same size.

**C8 — one skip registry.** The NUL refusal precedes any extension skip; the whole registry
is pinned by equality and announced on every run. RED on adding an entry, and RED on a
plain-text file carrying a declared-binary suffix.

**C9 — the substring-proof rule is an AST rule.** It flags the in-tree spellings V10 named,
and its universe includes `src/` and `scripts/`, not `tests/` alone.

**C10 — a declared-but-absent readout root is a failure.** RED by declaring a root that does
not exist. Absence stops being indistinguishable from silence.

**C11 — the decision path does not move.** Strand B changes the *oracle*, not the path. The
replay reads **PURE EQUALITY** on `m5-base`. If the fixture *contract* change alters any
fixture, C11 re-opens and the change is disclosed, never absorbed.

**C12 — K4's own work obeys the two rules K3 landed**, even though both are currently
defeated: every new poison fixture names its mutation in its own docstring, and every new
control discriminates a rejected violation from a gate that rejects everything.

## Register row numbers

New guard rows land at **26 and above**. K3's frozen criteria named rows already taken by
r25 and had to be renumbered after the fact; the highest row in `docs/guards.md` at the time
of this prereg is 25, and this sentence is the check.

## Gates

**G1** suite + `ruff` + `mypy` + the PII guard with the private name layer live ·
**G2** the 314-fixture replay on `m5-base` at `PYTHONHASHSEED=0`, pure equality per C11 ·
**G3** the pilot, read against this pre-registration, ~$25 cap, fired as a transient
`systemd --user` unit (run 16's ops lesson: a priced run launched as an agent-session
background task dies with the session) · **G4** deferred to K5 with the census ruling.

## Order of work (fixed here, so the report cannot be written to fit the result)

1. This pre-registration, committed.
2. Strand C — the two live holes (C8, C9). Cheapest, and they are live in master.
3. Strand D — the watch can fail (C10).
4. Strand B — the oracle (C4–C7). Must precede any reading that leans on it.
5. G1 + G2.
6. Strand A1 — the harvest (C1). $0.
7. Strand A2 — the agent arm (C2). $0 to build, priced only when it runs.
8. The pilot's sample frame, δ, level and conjuncts, committed **before** the run (C3).
9. G3 — the pilot fires.
10. RESULTS appended below; `docs/guards.md` and `ROADMAP.md` updated last.

---
## RESULTS

*(appended after the work; nothing above this line is edited)*
