# r17 — collapse M7: the register pinned; Appendix A prepared for signature

> Pre-registration, committed BEFORE any src change. Design: §8's M7 row ("the
> register (§6) pinned by its tests; the vocabulary derivations (D-6) + label-views
> (D-4/D-5); config surface (D-13); Appendix A signed here, not before"), §5.2, §6.
> Gate: **7.1 only** (the row's letter); an ADVISORY $0 `m5-base` replay is run
> beside it (not a frozen gate — reported either way). The signature itself is an
> OWNER KEYPRESS and is not delegated.

## STATE (verified 2026-08-26 on master `7d20f2d`)

- **The §6 register holds thirteen entries (6.1–6.13)**, each with a *Pinned by:*
  clause; the pin artefacts verified present: 6.1
  `tests/test_brain.py::test_live_skin_serves_draw_but_not_for_the_utility_posterior_s_measures`
  (system-marked, self-revising) + the gate tests; 6.2 the membrane
  host-declaration register + `tests/test_membrane_world.py`; 6.3 `core/reliability.py`'s
  one prior table + its M3 drift gates; 6.4 the same wire-shape test as 6.1; 6.5 the
  `m5-base-seam-executor-down` fixture + the seal-aware driver test (PR #91); 6.6
  the `sealed()` suite in `tests/test_collapse_record.py`; 6.7/6.8 the checkpoint
  scripts' gate sequence + `tests/test_collapse_compare.py`; 6.9
  `tests/test_probes.py`'s three corroborate-order tests; 6.10
  `tests/test_gate_tree_pin.py`; 6.11 `scripts/carrier_audit.py` (frozen docstring);
  6.12 `scripts/replace_audit.py` (frozen docstring); 6.13 the r08 SQL-side declared
  order in `src/pkm/retrieval.py` (`round(scored.score, 9)`).
- **D-6 (one vocabulary):** `DEC.ACTIONS`/`FAMILIES`/`*_ACTION_ORDER` are the one
  vocabulary; `BR._TERMINAL_ACTIONS` already DERIVES
  (`frozenset(DEC.LOOKUP_ACTION_ORDER)`); the gate partition is invariant-gated
  (`tests/test_decide.py:99-100`: union == ACTIONS, disjoint). Underived remainder:
  `EX._WITHHOLD = frozenset({"miss", "abstain", "hedge", "ask_clarify"})` — exactly
  `{"miss"} ∪ (ACTIONS − {report, report_scoped})`, i.e. the non-full-report
  terminals plus the miss reason. The membrane's views (`W.AFFORDANCES`,
  `CO._ENACT_EFFECTOR`, `categorical._INFO_ACTS`) are the SECOND world's declared
  vocabulary (§6.2 — deliberately distinct); what is gateable is the MAPPING's
  domain (`REAL_TO_MEMBRANE` keys, `_ENACT_EFFECTOR` values ⊆ the real vocabulary).
- **D-4 (one label-view):** three identical stable leader sorts live at `LK:1187`
  (render order), `BR:909` (the poster's leader-first record convention) and
  `EX:636` (`render_view`'s reorder); `W:89-91` documents its `max()` as the same
  leader (the membrane mirror, measurement-side). `CO._respond` died with the M3
  lane at M5.
- **D-5** landed at M5 (`DEC.withhold_reason`). **D-13** landed at M6 (a permitted
  interleave — DISCLOSED here as M7's config-surface item executed early).
- **Appendix A** (§8's letter: signed at M7, not before): three verbatim amendments
  — A.1 the §16 three-verdict rule; A.2 the §15 spine-is-transport replacement;
  A.3 the §14 adoption entry (date of signature).

## MANDATE

1. **P-I — the re-listing guard** (`tests/test_m7_register.py`): a curated census
   {6.1…6.13} → pin artefact; one test asserts the §6 headings in the design equal
   the census's keys (a new register entry without a censused pin fails loudly —
   the next census re-lists nothing); one test asserts every pin artefact EXISTS
   (test node by source scan, script by path, grep-pin by content).
2. **P-II — D-6 closes:** `EX._WITHHOLD` becomes the derivation
   `frozenset({"miss"}) | (DEC.ACTIONS - {"report", "report_scoped"})` (same
   members, spelled from the one vocabulary); the membrane mapping domain gains its
   drift gate (`REAL_TO_MEMBRANE` keys and `_ENACT_EFFECTOR` values ⊆
   `DEC.ACTIONS`).
3. **P-III — D-4 closes:** `DEC.leader_order(weights) -> list[int]` (the one
   stable weight-desc index view, labels only); LK/BR/EX bind it; W's documented
   mirror stays (the second world measures, §6.2).
4. **P-IV — the signature package:** a conferral document
   (`docs/unification/conferrals/appendix-a-conferral.md`) with the three verbatim
   amendments, the evidence (the ladder's M2–M6 readings), the price (docs-only)
   and the decline branch. Then **STOP — the keypress is the owner's.**

Out of scope: everything else. No behaviour change anywhere (P-II/P-III are
same-value respellings; the advisory replay checks it).

## GATES (frozen)

- **G1 (7.1):** full suite + ruff + `uv run mypy` (CI's exact invocation) green.
- **ADVISORY:** `collapse_replay.py --checkpoint m5-base` — expected 314/314 pure
  equality; reported either way; a diff is a STOP-and-disclose finding.
- **G5:** PII-free; hooks armed.

## PREDICTIONS (frozen blind)

- **P1:** the advisory replay reads 314/314 (the respellings are value-identical).
- **P2:** the register census finds all thirteen pins present with zero
  re-listings.
- **P3:** `EX._WITHHOLD`'s derivation equals the literal it replaces (asserted in
  its own pin).

## Consequence branches (frozen)

G1 green → commit, PR, merge, deploy; then the conferral is delivered and **work
STOPS for the Appendix A keypress** — the signature enacts A.1–A.3 on
PRINCIPLES.md/§14 as a separate owner-authorised commit; declining leaves the
structure standing and the constitution unchanged (the completion programme's DONE
item 1 requires the signature, so a decline re-opens the plan at that item).

## RESULTS (read 2026-08-26, appended after the gates ran — nothing above changed)

- **P-I:** `tests/test_m7_register.py` — the census {6.1…6.13} with every pin
  artefact named; BOTH predicates verified RED by mutation before landing (a fake
  6.99 census row; a mangled 6.13 needle), then green on the real tree. P2
  CONFIRMED: thirteen pins present, zero re-listings.
- **P-II:** `EX._WITHHOLD` now DERIVES (`{"miss"} ∪ (ACTIONS − {report,
  report_scoped})` — same members, P3 CONFIRMED by its own pin); the membrane
  mapping domain is drift-gated (`REAL_TO_MEMBRANE` keys == ACTIONS ∪ {gather,
  miss}; `_ENACT_EFFECTOR` values ⊆ ACTIONS).
- **P-III:** `DEC.leader_order` is the one label-view; LK (render order), BR (the
  poster's leader-first convention) and EX (`render_view`) bind it; W's documented
  `max()` mirror stays measurement-side (§6.2).
- **P-IV:** the conferral is delivered
  (`docs/unification/conferrals/appendix-a-conferral.md`) with the three verbatim
  amendments, their anchors verified against PRINCIPLES.md's live text (A.2's
  target sentence matches across a line wrap; A.1's insertion sentence found at its
  §16 home).
- **Disclosure:** D-13 (M7's config-surface item) landed at M6 as a permitted
  interleave; D-5 landed at M5. Both verified still in place by their own pins.

### Gate readings

- **G1 (7.1) — GREEN.** 2726 passed, 35 deselected; ruff clean (two auto-fixed
  style findings); `uv run mypy` (CI's exact invocation) clean, 222 files.
- **ADVISORY replay — 314/314 pure equality on `m5-base`** (P1 CONFIRMED: the
  respellings are value-identical).
- **G5 — GREEN.** No corpus values; hooks armed.

### Verdict

**M7's delegated half is DONE; the checkpoint completes at the signature.** The
register is pinned by a guard that fails on a new unlisted entry or a rotted pin;
the vocabulary partitions derive from or gate on the one vocabulary; the leader is
one label-view. Work STOPS here for the owner's Appendix A keypress — the
signature is the ladder's last act and is not delegated.
