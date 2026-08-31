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
