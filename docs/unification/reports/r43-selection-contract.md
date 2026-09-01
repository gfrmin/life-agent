# r43 — the selection contract: why the declared utility is inert at HEAD

Opened by [`r42`](./r42-engine-door.md)'s closing line — *"the code path that produces it is
not identified here, and that is where a successor with a Haskell-level reading starts"* — and
by [`GD-11`](../DECISIONS.md), which made item 4 a **precondition for every §18 bar**: a bar read
in the measured state compares arm A's utility-driven policy against a constant `abstain` and
books the gap to the migration.

**$0. No `src/` change. Nothing installed, nothing enabled. The proplang repo is read and
executed, never written.**

---

## FROZEN BEFORE ANY PROBE RAN

Everything in this section — the hypotheses, the criteria, and the three consequence branches —
was committed **before the first probe of this checkpoint executed**. `M-3`'s spirit, by the r37
precedent of freezing criteria in the instrument itself. The reading follows below the rule.

### The hypotheses, from a read-only source pass

**H1 — the binary choice sentence carries two beliefs but only one feature environment.**
`Membrane.chooseEU` at HEAD (`94fd4eb`, `src/PropLang/Membrane.hs:161`) folds the option list
pairwise, and builds **one** environment from the **challenger's** features:

```haskell
step acc chal@(cFeats, bC) = do
  inc@(_, bI) <- acc
  env <- mkEnvIn ns (feats' cFeats) (bC :. bI :. VNil)   -- feats' = mergeCover of the CHALLENGER
  pure (if evalx pick env == 1 then chal else inc)
-- pick = If (Gt (Expect (Var Z) uB) (Expect (Var (S Z)) uB)) 1 0
```

Both `Expect` terms evaluate the same `uB` in that one env. Our `said@1` sentence dispatches on
the act (`life_agent/membrane/world.py`, `["get", ACT_NAME]`), so **the incumbent's expected
utility is read at the challenger's act**, and the comparison reduces to a comparison of
*beliefs* rather than of actions. With act-independent beliefs — the state with zero evidence —
every pair ties, `Gt` is False, the incumbent survives every step, and the fold returns `c0`:
the option-space head.

r42's menu-permutation table is exactly this prediction, already confirmed once.

**H2 — items 3 and 4 are coupled.** Under H1, even a correctly declared act-dependent utility
can only be discriminated at HEAD through belief differences across options, which require a
learned act→outcome dependence, which requires evidence ticks — **item 3**. If H2 holds, item 4
is not independently repairable.

A source pass is a claim about code, never a measurement of behaviour (`M-7`, `M-20`). H1 and
H2 are what this checkpoint **tests**.

### Criteria

| id | criterion | kill? |
|---|---|---|
| **C1** | H1 is confirmed **behaviourally**: a probe that makes the options' predictive beliefs **differ** moves the choice off the head, to the option H1 names **in advance**. If the head still fires under differing beliefs, H1 is **refuted** and published as such. | **KILL** |
| **C2** | H2 read: whether belief differentiation is reachable **without** evidence ticks (an informative prior, or the `observe_batch` / `observe_counts` warm channel of `membrane-wire` §6.3 — accepted or refused at HEAD is itself the measurement). | — |
| **C3** | The arm-A/arm-B selection difference is read from both trees and stated as **contract change** or **regression**, with the commit that made it named. | — |
| **C4** | Every load-bearing predicate is verified **RED by mutation** before the reading (`G-3`: a control counts only if removing what it controls for turns it RED). | **KILL** |
| **C5** | Each probe reads the **whole** reply stream, never only the last line (`M-22`). | **KILL** |
| **C6** | The universe of each claim is named **with its size**; an empty universe fails rather than reads (`G-3`). | **KILL** |

### Consequence — three branches, frozen

1. **Our declaration is wrong for HEAD's contract** → no upstream issue; item 4 folds into r44's
   world-declaration repair as a *declaration* change (which utility form, and how the act
   enters it).
2. **HEAD cannot express an act-dependent utility at all** → a well-formed upstream question,
   **drafted in-tree with its evidence and not filed by this checkpoint**; the §18 bars block
   behind it. `A-2` binds: the fix is engine work, never a softened bar. Filing is outward-facing
   and permanent on a repo someone else maintains — RULINGS §5's parenthetical makes it ordinary
   operating caution, so posting takes one confirmation.
3. **H1 refuted** → publish the refutation; the successor re-opens on whatever the probe showed.
   Nothing already frozen is renegotiated (`M-4`).

---

## THE READING

### C1's discriminating experiment and its named winner — frozen before it ran

Two probes had already established the ground (their results are in the reading below): the
writable name may **never** appear in a tick's features (`Host.hs:399`, `feature/assignment
collision`, both arms), so the only satisfiable evidence path at HEAD is a **menu-carrying**
evidence tick, on which the engine picks the act and the fold conditions at *its* choice. The
belief does move under it.

That makes H1 discriminable. Declare `u_abstain = 90`, `u_correct = 100`, `u_wrong = 0`, and
both information actions priced out (`lambda_int = kappa_att = 1000`, so `gather` and `ask` are
worth about −900). Then feed **`evidence = 0`** repeatedly, which drives the predictive down at
the act the engine keeps choosing — the head — while the other options keep a belief nearer the
prior.

At that point the two accounts of selection disagree, in opposite directions:

| account | rule it applies | act it names |
|---|---|---|
| **correct (arm A's `choose`)** | argmax over rows of `E_{b_a}[u(y; a)]`: abstain 90, respond ≈ 50, gather/ask ≈ −900 | **abstain** |
| **H1 (HEAD's `chooseEU`)** | every row rises in `y`, so `Gt vC vI` reduces to `p_chal > p_inc` — a comparison of **beliefs**, with the incumbent's own utility row never consulted | **gather** — the first challenger whose belief beats the depressed head's |

**The prediction, named in advance: arm A holds `abstain` at every tick; arm B leaves the head
for `gather`** — an option this utility prices at about −900 — as soon as the head's predictive
falls strictly below the others'. If arm B instead holds `abstain` throughout, H1 is **refuted**
under C1 unless the per-option beliefs are shown never to have separated, which C6 requires be
measured rather than assumed.

### Verdict

**Branch 1 fires. Item 4 is a defect in OUR world declaration, not in the engine — and its
repair is ONE declared row (a `clock`), measured to restore utility-driven selection at HEAD
on every case r42 read as dead.** A second row (an `act` guard) repairs a **distinct** defect
found here — an act-blind belief — and is not what makes the utility live; the two are gated
separately by r44. No upstream issue is filed, and the case for one collapsed rather than
strengthened: **the engine has already registered this exact finding as `OB-24` and ruled its
remedy**, which our world simply does not declare.

| what r42 measured | what r43 found |
|---|---|
| HEAD parses the utility, then decides as if absent | HEAD's `chooseEU` compares two **beliefs** under one **common** utility row, so per-action *levels* never enter |
| `abstain` under four different `u_bar`s | our world's beliefs are **act-blind** (`act` has no guard row), so every pair ties and the head wins |
| the head fires on every menu permutation | with a **`clock`** row declared, selection routes to `pickWire` — `OB-24`'s substitution route — and tracks `argmax_action` on **5 of 5** cases |

### C3 — the selection contract changed; it did not regress

`chooseEU` **does not exist at arm A**. Arm A selected in `Host.choose`, which evaluates each
candidate in **its own environment**:

```haskell
euAt a = expect (predictive (feats ++ a) ag)
                (\y -> evalx u (mkEnv (feats ++ a) (0 :. realToFrac y :. VNil)))
```

so each option is scored against **its own** utility row, and the row *levels* decide. HEAD
builds **one** environment, from the challenger, and reads the same `uB` for both sides. The two
selectors are different functions with different names; `Membrane.hs` differs by 985 lines
across the arms. **Contract change, not regression** — and `test-dyadic/freeze/`'s own install
note records `argmaxEU` being "deleted with the `Argmax` terminal (opening ruling 3)".

### C1 — the named winner was wrong; the mechanism it was named from was right

The frozen prediction was **arm A holds `abstain`, arm B leaves for `gather`**. Measured over 12
`evidence = 0` ticks (universe: 1 hello + 12 ticks × 2 arms, every reply read):

- **arm A held `abstain` at all 12** — as named. Its `p1` fell 0.500 → 0.156.
- **arm B held `abstain` at all 12 too** — *not* as named. Its `p1` fell 0.500 → 0.112.

By the frozen rule that is a refutation **unless the per-option beliefs never separated**, which
C6 required be measured. They never separated, and the measurement is exact.

### C6 — the beliefs are act-blind, and the cause is a missing guard row

Declaring the same world with an **empty menu** makes `act` an ordinary feature, so the
predictive can be conditioned at one act and read at another. Read as `2^(−loss_bits)` (positive
control: it reproduces the reported `p1` to full precision on a tick carrying both):

| arm | teach | P(y=1) at abstain / gather / ask / respond |
|---|---|---|
| A | none | 0.500000 · 0.500000 · 0.500000 · 0.500000 |
| A | 12 × `evidence=0` @abstain | 0.151433 · 0.151433 · 0.151433 · 0.151433 |
| B | none | 0.500000 · 0.500000 · 0.500000 · 0.500000 |
| B | 12 × `evidence=0` @abstain | 0.109666 · 0.109666 · 0.109666 · 0.109666 |

**Byte-identical across all four acts, on both arms, before and after conditioning.** Universe:
4 acts × 2 arms × 2 teaching levels = 16 readouts.

A census over the whole namespace then locates the cause. Flipping each of the 19 declared names
one at a time and re-reading the predictive after the same 12 ticks: **17 names move it; exactly
two do not — `t` and `act`** (identical result on both arms). Those two are precisely the names
`handshake_decl` gives **no guard row**: guards are declared only for `indicator_names()`.
Fragments are enumerated over the guard grids, so **no hypothesis in this world can condition on
the act**, and a belief-mediated chooser therefore has nothing to compare.

With a guard row for `act` on its own grid (`models` 345 → 425) the beliefs separate — and they
separate *monotonically in the act's grid value*, which is why the frozen prediction named the
wrong act:

| arm | teach @abstain | abstain | gather | ask | respond | belief-argmax | EU-argmax |
|---|---|---|---|---|---|---|---|
| B | 1 | 0.340000 | 0.340126 | 0.340251 | 0.340377 | **respond** | abstain |
| B | 3 | 0.210694 | 0.210921 | 0.211148 | 0.211375 | **respond** | abstain |

and arm B's live choice under the same conditioning **alternates `abstain, respond, abstain,
respond, …`** — chasing whichever act was not just conditioned. It takes `respond` at EU ≈ 34
over `abstain` at EU 90. **H1 is confirmed in substance and in its detail: the chooser maximises
the belief, and the incumbent's own utility row is never consulted.** The prediction's error was
in assuming only the head's belief would move; all four move together, ordered by grid value.

### The repair, and which row is load-bearing

`Host.hs` routes to `chooseEU` **only when no `clock` is declared**; with one it calls
`pickWire`, which is `policyPick` — and that identification is **read, not inferred**:
`policyPick`'s own header calls it *"chooseEU's K-ary successor … the whole menu compared
inside a single standing sentence with every candidate's belief bound in one env — the
charter's single chooser"*, and it builds each row as `Expect (Var Z) (substW asn uB)` —
**`substW asn`, each candidate's own assignment substituted in**, which is `OB-24`'s
remedy verbatim. `chooseEU` is left as "the frozen binary special case". r42 noted our world declares no `clock` and did
not pursue it. Declaring one (`{"name": "think", "price": p, "batch": 1}`; `think` is not a
namespace name, so it is admitted) reproduces r42's dead table alive:

| case | host `argmax_action` | arm A | B bare | B + act guard | **B + guard + clock** |
|---|---|---|---|---|---|
| deployed-ish (respond dear) | gather | gather | abstain | abstain | **gather** |
| respond-favouring | respond | respond | abstain | abstain | **respond** |
| ask-favouring (gather dear) | ask | ask | abstain | abstain | **ask** |
| info-dear (both dear) | abstain | abstain | abstain | abstain | **abstain** |
| abstain-dominant | abstain | abstain | abstain | abstain | **abstain** |

**Three of the five winners are not the option-space head**, so "it fires the head" is excluded
by the table itself rather than by argument — the control r42's own reading could not run.

Minimality, measured: **the clock row alone is sufficient** (`clock-only` reproduces
gather/respond/ask exactly); **the guard row alone is not** (abstain everywhere). They are two
repairs with two purposes — the clock restores *utility-driven selection*, the guard restores
*act-conditionable belief* — and r44 needs both for different reasons. The clock's `price` was
swept 0 → 10⁶ at this feature vector with the choice invariant and the internal `think` act
never winning; that is a statement about this vector, not a general one.

### Backwards compatibility of the two repair rows — an r44 precondition, measured here

r42 established that items 1–2 are free on the control (arm A ignores `codebooks` and answers a
full-coverage tick byte-identically), which is what lets one declaration serve both arms. The
same question for the two new rows, over a 5-tick session on arm A:

| row added | arm A `models` | arm A hello identical | arm A ticks byte-identical |
|---|---|---|---|
| **`clock`** | 2393 → **2393** | **yes** | **yes** |
| `act` guard | 2393 → 2681 | no | no — `entropy_bits` moves at the first tick |
| both | 2393 → 2681 | no | no |

**The clock row — the one that actually repairs item 4 — is a byte-identical no-op on the
control.** So it joins items 1–2 in the "verifiable before the swap, one declaration for both
arms" class. The act guard row is not: it enlarges the hypothesis space on both arms and moves
arm A's readouts (the chosen act held at `gather` in this session, but that is one session, not
a claim). r44 must therefore justify and gate the two rows **separately** — they are not a pair.

### What this changes for item 3 — the evidence path is narrower than r42 could see

Two facts, both measured on **both** arms:

- **The writable name may never appear in a tick's features.** `Host.hs:399` refuses any feature
  whose name is in the declared menu — `feature/assignment collision` — whether or not the tick
  carries a menu. So "supply the act" is not how item 3 is satisfied.
- **The only satisfiable evidence tick carries a `menu`.** Then the engine picks the act and the
  fold conditions at **its** choice. Measured learning under it: `p1` 0.5 → 0.66 → 0.742 at HEAD.

So an evidence tick is not a full experience tuple we author: **at HEAD you cannot tell the
engine which act a recorded verdict was taken under — it decides.** A replay *can* pin the act
by declaring a **one-point menu grid** (verified: grid `[1.0]` conditions at `abstain`, grid
`[4.0]` at `respond`, same belief trajectory), but the grid is declared at hello, so a mixed-act
verdict stream cannot be folded in one session. That is a constraint on **P1**, and it is
`GD-11` item 3 restated with numbers.

**And it composes with item 4 into a lock.** Unrepaired, the engine always chooses the head, so
it only ever conditions on the head, so the beliefs never acquire act structure, so the head
keeps winning. The loop closes on itself; neither half can be measured out of the other. That is
why `GD-11`'s H2 — items 3 and 4 are coupled — is **confirmed**, and why repairing item 4 is a
precondition for item 3 being worth anything.

### `OB-24` — the engine registered this before we measured it

`test-breadth/freeze/obligations-heir.patch` and `test-trampoline/freeze/obligations-rows.md`
carry the row verbatim:

> **OB-24** — the Get-of-writable utility ruling (register R4): under the shipped `chooseEU`
> fold **both sides of every comparison are served the CHALLENGER's assignment, so
> action-dependent utilities degenerate to ties** (demonstrated EXECUTED: oracle row g2.3, the
> divergence witness); the one-sentence route substitutes each option's own values. RULED at
> this freeze: SUBSTITUTION IS NORMATIVE; … `chooseEU` keeps its shipped fold this increment and
> migrates, with its own pin row, only at a named boundary.

The gate transcripts pin it as a passing oracle row (`g2.3 the substitution witness: a
writable-reading utility DIVERGES from the fold`). So the behaviour is **known, deliberate and
scheduled** upstream, the remedy is the route we failed to declare, and **filing would have
reported the maintainer's own registered obligation back to them.** `GD-10`'s reason for not
filing early was that an unmeasurable ask wastes someone's attention; this is the sharper
version — an unread one wastes it too.

### C4 — the mutation ladder, run before the reading

| id | predicate | mutation | result |
|---|---|---|---|
| M1 | exact namespace coverage is load-bearing | drop one declared name | RED — `tick refused: missing declared [...]` |
| M2 | the collision check forbids `act` as a feature | supply it | RED — `feature/assignment collision` |
| M3 | `M-22`: the whole reply stream is read | read the tail only | RED — `[abstain, respond, abstain, respond, abstain, respond]` collapses to `[respond]` |
| M4 | the belief readout is the reported quantity | positive control at a non-trivial value | RED-ok — `2^(−loss_bits)` = `p1` = 0.7893061224489796 |
| M5 | the control arm is not degenerate | vary `u_bar` | RED-ok — arm A picks `{abstain, ask, respond}` |

**5/5.** Every table above was produced by probes driving the **real** `handshake_decl` /
`shadow_features` / `utility_said` out of `life_agent.membrane.world` (`M-7`); only the JSON
around them varies. The proplang repo was read and executed, never written (verified: no tracked
file modified; the one untracked path, `bench/`, dates from 2026-08-18 and is not ours).

### Deviations, disclosed

- **C1's named act was wrong and its escape clause carried the criterion.** Published above in
  full: `gather` was named, `abstain` was observed, the beliefs were then measured never to have
  separated, and in the world where they *do* separate the winner is `respond`. The mechanism
  the prediction was derived from is confirmed; the act it named is not. Both are reported, as
  `M-4` requires and as r05 set the precedent for.
- **The repair search was not pre-named.** C1–C6 govern the diagnosis; finding the clock route
  came after `OB-24` was read, so its outcome carries no frozen prediction. Its control (three
  non-head winners) is what makes it a measurement rather than a hope, and r44 must re-freeze it
  properly before anything lands in `src/`.
- **The clock's price sweep is single-vector.** Invariance 0 → 10⁶ was read at one feature
  vector; `think`'s reachability at other vectors is unmeasured, and it is a **new affordance**
  the shadow's world does not model — r44's problem, named here.
- Findings were reproduced across the probes that share ground (the act-blindness table, the
  `p1` trajectories and the five-case table each appear twice from independent sessions).

### Consequence

**Branch 1**, enacted: no upstream issue; item 4 folds into r44 as a **declaration** repair with
its own pre-registration. `D-2` defaults, no keypress. r43 changes nothing in `src/` and nothing
on the machine.

`GD-11`'s four items are re-priced by this reading:

1. `codebooks.theta` — unchanged; still needs its grid chosen and justified.
2. Full-coverage ticks — unchanged, and now with the rider that the writable name is **excluded**
   from coverage, never padded into it.
3. The evidence tuple — **narrower than stated**: the act cannot be told to the engine at all,
   only pinned by declaring a one-point menu grid, which a mixed-act replay cannot use.
4. The dead utility — **solved, and it was ours**: a `clock` row routes selection to the
   substitution path and the world becomes utility-driven at HEAD; an `act` guard row is a
   second, independent repair without which the belief can never acquire act structure.

The §18 bars can be read once 4 is repaired — and **must not be read before**, which was
`GD-11`'s point and is now a fixed defect rather than an open mystery.
