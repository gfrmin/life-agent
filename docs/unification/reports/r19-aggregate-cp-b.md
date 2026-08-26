# r19 — aggregate family CP-B: component 1, the recall term + generator registry ($0)

*2026-08-26. The second checkpoint of Phase 1.6 item 4 (Stage 2a), opened by CP-A's RULING
(r18: "CP-B (r19) opens"). Library-only — nothing on the decision path imports what this
checkpoint builds; no SPEC change (§18.14 is CP-D's); no router change; no FAMILIES change.
The pre-registration below is committed BEFORE any `src/` change and nothing in it changes
after; results append under RESULTS.*

## Pre-registration (frozen)

### What CP-B builds

`src/life_agent/core/aggregate.py` — the design register's component 1
(`docs/aggregate-family-design.md` §5) and the registry contract (§9) — plus its test file
and an in-tree synthetic fixture. Out of tree: the real registry installed at
`$LIFE_AGENT_KB/generators.yaml` and verified to load through the same loader with
resolvable evidence. Nothing else. In particular NOT built here: the missing-mass
posterior (§6, CP-D), dedup-as-inference (§7, CP-C), the second-stage router (§8, CP-D),
any `reactions.py`/`recorder.py`/`terminals.py`/`executor.py` change (CP-D), any SPEC
amendment (CP-D).

### Frozen API surface

- `Cadence` — closed vocabulary `monthly | quarterly | annual`. An unknown cadence is a
  loud `RegistryError`, never a silent zero slots (§9).
- `Generator` (frozen dataclass): `generator_id`, `kind`, `cadence`, `active_from: date`,
  `active_to: date | None`, `scope_keys: frozenset[str]`, `evidence: tuple[str, ...]`
  (citation paths, resolved at load — below).
- `Scope` (frozen dataclass): `key: str`, `start: date`, `end: date` — the question-side
  binding. A generator **covers** a scope iff `scope.key ∈ generator.scope_keys` and its
  active window intersects `[start, end]`.
- `expected_slots(generator, scope) -> tuple[str, ...]` — deterministic calendar
  enumeration (host arithmetic, not inference) over the intersection of the scope period
  with the generator's active window: monthly `YYYY-MM`, quarterly `YYYY-Qn`, annual
  `YYYY`. A slot is expected iff its period intersects that intersection.
- `recall_posterior(brain, generators, scope, hits) -> RecallPosterior` — `hits` maps
  `generator_id → frozenset` of slot names claimed retrieved. The slot census unions the
  covering generators' expected slots **namespaced** `generator_id:slot` (two generators'
  calendars never collide).
- `RecallPosterior` (frozen dataclass): `mean`, `variance`, `estimated: bool`,
  `n_slots`, `n_hits`, `expected`, `hit`, `missed`, `extra_hits` (all slot-name tuples,
  namespaced; `missed` is the *named* misses — §5's "a missing month is 'month M absent'"),
  `prior: tuple[float, float]`.
- `load_registry(path, *, evidence_root) -> LoadedRegistry` — `entries: tuple[Generator,
  ...]`, `content_hash: str` (sha256 of the registry file's bytes). All validation errors
  are `RegistryError`, loud, naming the entry.

### Frozen fold choreography (design §5, Invariant 1 — no host math)

One Beta state on the wire (`brain.create_state({"type": "beta", ...})`); **one
`bernoulli` condition per expected slot** — 1.0 for a hit, 0.0 for a miss (misses are
observations, not absences: folding only hits reads nine-of-nine and reports r≈1.0 on a
75%-recall scope); reads = `brain.mean` + one `brain.expect({"type": "centered_power",
"n": 2, "mu": <mean>})` variance read (the `utility.py` variance convention); the state
destroyed in a `finally`. Conjugate, no grid, no host `a += 1`.

### Frozen prior

`_RECALL_PRIOR: tuple[float, float] = (3.0, 1.5)` — deliberately not Beta(1, 1) (§5:
uniform recall is a strong and false belief about retrieval, not a neutral one).
Rationale, frozen blind before any eval question touches the term: weakly **optimistic**
(mean 2/3 — on a scope a generator covers, retrieval hits more often than it misses; the
replay baseline's served-rate direction), and **weak** (total strength 4.5 pseudo-slots,
under half of one monthly annual scope's 12) so a single monthly scope overturns it — the
overturn is a frozen test, not prose. Nothing in CP-B prices this constant; CP-D's gate
is where it faces data.

### Frozen behavioural clauses

1. **Misses are observations.** Every expected slot folds exactly one Bernoulli
   observation; `n_slots` = the census size = the number of wire conditions.
2. **Extra hits are named, never folded.** A claimed hit outside the expected census (or
   for a non-covering generator) is not a sample of r under the declared denominator — it
   is evidence about the *schedule* — so it does not enter the fold; it is carried in
   `extra_hits` for the caller to disclose.
3. **No covering generator ⇒ prior-dominated, declared.** `estimated=False`, moments =
   the prior's, zero wire conditions, empty census. Rendering readout 2's
   unmodelled-recall sentence is the CALLER's contract (CP-D); the flag is CP-B's.
4. **Admissibility at load** (§9). Each `evidence` citation is a path resolved against
   the injected `evidence_root`; a citation that does not exist there fails the load
   loud — an uncited schedule never enters the denominator. The loader takes the root as
   an argument (no config binding, no catalogue dependency — CP-D wires config).
5. **Replay determinism** (§9). `content_hash` is returned by the loader; *recording* it
   onto decision records is CP-D's wiring — CP-B provides the hash and tests that a
   one-byte registry edit changes it.
6. **Scope-generic.** Nothing spending-specific in any signature; the non-financial
   generator test is the insurance (item 5's membership recall reuses the term).

### Tests (TDD, each watched RED before its code)

t1 misses-are-the-point: 12-slot monthly scope, 9 hits ⇒ 12 wire conditions; the
   posterior mean strictly below the fold-hits-only mean; exact conjugate value asserted
   against the oracle. · t2 prior-overturn: prior strength < 12 asserted on the constant,
   and 3/12 hits pulls the mean below 0.5 despite the optimistic prior. · t3 no covering
   generator ⇒ clause 3 exactly (flag, prior moments, zero conditions). · t4 extra hit ⇒
   clause 2 (census size unchanged, hit named). · t5 `expected_slots` calendar
   enumeration: monthly/quarterly/annual + active-window clipping. · t6 the synthetic
   fixture loads; `content_hash` = sha256 of bytes; a one-byte edit changes it. · t7
   unknown cadence ⇒ loud `RegistryError`. · t8 unresolvable evidence citation ⇒ loud
   `RegistryError` naming the entry. · t9 a non-financial generator behaves identically.
   · t10 the wire state is destroyed on the success path and when a read raises.
   Choreography verified hermetically by a local `ConjugateBrain` oracle (the
   `test_narrative.py` convention), extended with the `mu`-centred variance functional.

### Gate (frozen)

Full suite + `ruff check` + `mypy` green; `scripts/collapse_replay.py --checkpoint
m5-base` reads **314/314 pure equality** (nothing on the decision path changed — any
non-equality row is a FAIL, not a disclosure); the real `$LIFE_AGENT_KB/generators.yaml`
loads through the loader with every citation resolving. Anomalies en route are
disclosure items in this report (cap-the-arc); a gate miss STOPS.

## RESULTS

*(appends after the gate runs; nothing above this line changes.)*
