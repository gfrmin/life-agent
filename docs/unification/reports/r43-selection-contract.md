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

*(follows; nothing above this line changes)*

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
