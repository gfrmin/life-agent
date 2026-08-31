# r41 / P0 — the engine, pinned and provenanced: PRE-REGISTRATION

Arc C's first rung, scoped by [`r40-arc-c-preconditions.md`](./r40-arc-c-preconditions.md) and
`GD-10`. **Committed before anything is built or installed** (`M-3`). No `src/` change.

## What P0 is

r40 measured that **no `proplang-host` binary exists on this machine**, so every bar §18 freezes
is currently unreadable. P0 puts one there — **with the provenance §15 established as the
standard, and not one step less**, because an engine binary is the thing every later number is
produced by.

The local proplang checkout has moved far past the `1a0cea7` §15 records. So **installing HEAD
is an engine change, not a restoration**, and it inherits §15's discipline rather than
bypassing it on the grounds that there is nothing to overwrite.

## The instrument: a control arm, then the arm under test

§15 verified byte-compatibility by comparing **old binary vs new**. There is no old binary here,
so that exact comparison is unavailable. The substitute is stronger where it can be had: the
shadow ledger recorded **6 683 records** produced by the `ebc06c81…` binary, including boot
records and decide traffic. So:

- **Arm A (control) — build `1a0cea7`**, the commit §15 names, and check it against the
  recorded wire. This arm's job is to prove the *harness*, not the engine: if the commit the
  ledger was produced by cannot reproduce the ledger, the comparison is broken and nothing
  downstream can be trusted.
- **Arm B (under test) — build the pinned current commit** and check it the same way. Its
  differences from the recorded wire are then attributable to **engine evolution**, which is
  legitimate and expected, rather than to the build.

Without arm A, arm B's differences are uninterpretable — the r36 failure mode exactly (a
comparison whose baseline differs by more than the thing under test, `M-18`).

## Frozen criteria

| id | criterion | kill? |
|---|---|---|
| **P0-1** | Both arms are built from a **named commit**, and each installed artefact's **sha256 is recorded** beside it. A binary whose provenance cannot be stated is not installed. | **KILL** |
| **P0-2** | **Arm A reproduces the recorded wire**: for the recorded handshake and at least one recorded decide exchange, the reply is identical under sorted-JSON compare. | **KILL** |
| **P0-3** | Arm B is checked against the **same** exchanges, and every difference is **enumerated and attributed** — to a named grammar/wire change — never summarised as "the engine moved on". | **KILL** |
| **P0-4** | The `test_membrane_live.py` system smokes pass against the binary that ends up installed. | **KILL** |
| **P0-5** | **Nothing is enabled.** P0 installs and verifies; it does **not** set `MEMBRANE_COMMAND` and does not restart the shadow. That is P1, with its own segmentation declaration. | **KILL** |

## Declared failure modes, so they are not surprises

- **Arm A may not compile** under this machine's GHC 9.10.3 — `1a0cea7` predates it. If so,
  **P0-2 is unreadable, not passed**: the report says the control arm is unavailable, arm B's
  differences stay unattributed, and P0 lands the binary **only if P0-3 can still be met by
  another means** (e.g. the recorded wire's own schema). If neither, P0 stops and says so
  rather than installing an unverified engine.
- **Arm B may differ from the recorded wire on every exchange.** That is not a failure; it is
  P0-3's subject. What would be a failure is not being able to say *why*.

## What P0 does not do

It does not enable the shadow, file a proplang issue, or touch `src/`. It does not adopt a
commit as "the" engine beyond recording which one was installed and why.

## Cost

$0 in model spend; local compile time only.

---

## Amendment 1 — P0-2's comparison, changed blind before any run (2026-08-31)

**P0-2 names an artefact that does not contain what it asks for.** It requires the recorded
handshake and decide **replies** to compare byte-for-byte under sorted-JSON. The shadow ledger
records **outcomes, not the wire**: a `decide` record carries `action`, `readouts`, `summary`,
`t`, `question_id` and `latency_ms`, and its `raw_internal` field is a **boolean flag**, not a
payload. No request and no reply is stored anywhere in the 6 683 records.

This is `GD-7` again, one arc later: a criterion frozen against an artefact without checking
that the artefact carries the quantity. Amended the same way — **blind, prospectively, in
public, and without weakening what is being asked**:

> **P0-2, amended.** The check is **behavioural reproduction**, not byte equality. The recorded
> `summary` **is** `world.DecideSummary` — `n_candidates`, `leader_credence`, `p_none`,
> `n_obs`, `era_split`, `owner_scoped`, `grow_pass` — which is the engine's own input. So a
> recorded decide is replayed by submitting its recorded summary through the shadow's own
> submission path against the binary, and comparing the **`action` and the `readouts`**
> (`p1`, `entropy_bits`) with the recorded ones. Arm A must reproduce them.

This is **stronger than the byte compare it replaces**, and the report must not pretend
otherwise: byte equality tests a serialization, while this tests the decision. It is also the
only form the evidence supports.

## Amendment 2 — arm A is already built, and its sha does not match (2026-08-31)

Checked before compiling anything (`M-20`): a `proplang-host` built from **`1a0cea7` already
exists on this machine**, under GHC 9.10.3, dated 2026-08-17, in a pre-existing proplang
worktree. So the pre-registration's declared "arm A may not compile under GHC 9.10.3" risk is
**retired by evidence** — it does compile, and did.

Its sha256 is **`1d008643…`**, and the ledger's boot records carry **`ebc06c81…`**. Same commit,
different bytes. That is expected and is recorded as a standing fact rather than a discrepancy:
**a Haskell binary is not byte-reproducible across machines and toolchains**, so a sha is a
*provenance record* (P0-1) and never an identity test across hosts. P0-2's behavioural check is
what carries identity — which is precisely why amendment 1's substitution is not a downgrade.

## Status note — where P0 stands (2026-08-31, recorded before the work continues)

Three things are established, and the fourth is specified but not executed.

**1. Arm A exists and compiles.** `proplang-host` at `1a0cea7`, GHC 9.10.3, built 2026-08-17
(amendment 2). No compile risk remains.

**2. `1a0cea7` and the current HEAD are both present** in the local checkout, and arm B's
worktree is prepared at the pinned current commit. Nothing is built for arm B yet and nothing
is installed for either.

**3. P0-2's replay needs a warm session, and the ledger's decides are all warm.** Measured:
**0 of 3 761** recorded decides are cold-start — every one sits at `t = 13` (2 200) or
`t = 193` (1 561), i.e. after a warm replay of that many source records. So no recorded decide
is reproducible from its `summary` alone, and a replay that pretended otherwise would compare
a cold engine against a warm record and call the difference a regression.

**4. The warm history is reconstructible, so P0-2 is readable — it is not blocked.** The source
records live under the fair-fight run directories (`shadow_calibration/decisions.jsonl`), which
is exactly what `shadow.boot()` replays; the last boot record names its own count (**2 188**).
The replay must therefore **drive `shadow.boot()`**, not re-implement the warm-up — `M-7` is at
seven instances and every one of them is a re-implementation of a rule that was already
available to call.

**Next step, specified:** spawn a session against arm A, warm it through the shadow's own boot
path from the named source records, replay a recorded decide at its recorded `t`, and compare
`action` + `readouts` against the record. Then the same for arm B, with every difference
attributed (P0-3).

**Not done, deliberately:** nothing installed, nothing enabled, no proplang issue filed. P0-5
stands.
