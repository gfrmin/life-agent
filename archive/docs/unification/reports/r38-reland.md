# r38 — the value-join unification, re-landed: READING

Pre-registration: [`r38-reland-preregistration.md`](./r38-reland-preregistration.md), committed
before the `src/` change (`M-3`). Decision to proceed: [`GD-8`](../DECISIONS.md).
Run 23 = `gate-20260831T195752`, $0.2x, 21m50s, on master `2dff035` with the tap armed.

## Verdict: PASS on all five frozen criteria

| id | criterion | reading | verdict |
|---|---|---|---|
| **K1** | zero NEW wrong commits vs run 22 | wrong set **identical** in runs 21, 22 and 23 — the two standing rows and nothing else | **PASS** |
| **K2** | no named wrong-commit class worse (`M-1`) | no row entered a named class; the standing two are unmoved | **PASS** |
| **K3** | rows differing from run 22 ⊆ the measured surface | **exactly one row differs: q2-027**, which is in `{q2-027, q2-028, q2-029, q2-090}` | **PASS** |
| **K4** | P(Δ>0.05) ≥ 0.90 | **0.969**, Δ̄ +0.545 [+0.106, +1.029] | **PASS** |
| **K5** | leader credence ≥ run 22's on any changed firing row | q2-027: **0.863** vs run 22's 0.346 | **PASS** |
| K6 | abstain→report on a gold: recorded | one — q2-027 | recorded |

Every frozen directional claim landed: exactly q2-027 moves (abstain → correct report);
q2-028 and q2-029 fire and stay inert; q2-090 unchanged; the aggregate sits at run 21's
0.969 / +0.544 (read: 0.969 / +0.545).

**Run 23 and run 21 agree on all 104 rows.** Run 21 was the lever on the pre-r37 tree; run 23
is the lever on master. Zero differences — the strongest reproduction in the series.

## What the decision record shows, and why the naive estimate was wrong

q2-027's posterior, from the two runs' own decision rows:

| | candidates | leader | p_none | action |
|---|---|---|---|---|
| run 22 (no lever) | **4** — two of them spellings of one answer, at 0.346 and 0.146 | 0.346 | 0.299 | abstain |
| run 23 (lever) | **3** — the two merged | **0.863** | 0.058 | report ✓ |

**A merge is not additive, and r34's registered expectation under-read the lever because it
assumed it was.** r34 predicted from *naive merged mass* — 0.346 + 0.146 = 0.493, which does
not cross p† = 0.8369 — and concluded "correct but inert" was the likely outcome. The actual
posterior is **0.863**. Merging two spellings does not just pool their mass: it removes a
competing atom, and the competitor count and `p_none` are re-normalised with it (0.299 →
0.058). The lever's effect on the argmax is therefore **larger than any additive estimate of
it**, and a successor pricing a merge must re-run the posterior, never sum the credences.

That is `M-7` in a new dress: r34 priced the lever with an arithmetic stand-in for the rule
instead of the rule.

## The live surface is trajectory-dependent — disclosed

Run 23's own tap: **214 calls over 98 questions · 3 firings over `{q2-027, q2-029, q2-090}`.**
r37's (run 22, no lever) read 219 calls · 8 firings over four questions, q2-028 included.

The two are not the same surface, and they should not be expected to be: once q2-027 reports,
the run stops probing it, so the lever changes the trajectory that generates the calls. K3 is
still sound — it is a **containment** test over the rows whose *action* changed, and one row
changed — but the surface itself must be treated as approximately stable, not fixed. A
successor that freezes a surface should say which run produced it and expect drift of a
question or two.

## An ops defect in this arc's own launcher — disclosed, and fixed

`run23-launch.sh` restores the live stack from an `EXIT` trap, unconditionally. Run 23 merged
before it fired, so the restore at 20:19:30 brought jarvis, the bridge and the daemon back up
**on the lever tree, before the verdict was read at ~20:22.**

Here it is harmless — the run PASSED and `D-1`/`D-2` deploy on PASS anyway. But had it FAILED,
the launcher would have left an unvalidated decide-path change serving live traffic: exactly
the "merged-but-unmeasured in the deploy tree, one restart from live" exposure this session
flagged at r36, reintroduced by the tool written to prevent the *other* ops failure. The
launcher now restores to the **pre-run tree** unless the run exits 0, and says which tree it
restored.

## Consequence — enacted

`D-1`/`D-2`'s PASS branch, no keypress: **merged (`2dff035`) and deployed.** The live bridge
restarted onto the lever tree at 20:19:30 and answers `/ready`.

What ships is one declaration of candidate identity where there were two. What it buys, on the
gate corpus, is one row — **below the wobble floor, as `GD-8` said before the run, and it is
not to be quoted as a statistical result.** What it does not cost is anything: the wrong set is
byte-identical across three runs.

## The arc, closed

r34 built it and K3 killed it · r36 reverted it and misdiagnosed why · r37 built the instrument,
measured the surface, and found the real defect was K3's **baseline** (`M-18`) · r38 re-landed
it against a baseline that differs by the lever alone. Four checkpoints, $0.2x + $0.22 + $0.19
of priced runs, and the thing that actually moved was a criterion's control, not the code.
