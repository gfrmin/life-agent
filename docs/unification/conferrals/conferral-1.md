# Conferral 1 — five rulings, one sitting (2026-08-29)

Evidence, options and prices, written BEFORE the interview (house rule). Every number here is
$0 arithmetic on artefacts already on disk; nothing was bought to produce it.

Context: the completion programme has one open stage — **Stage 4, the MVP exit test**. r30b
built the claim space and r31a read the $0 evidence pack. This sitting settles what r31
measures, and what the exit week runs under.

---

## Item 1 — the `quantity` scale opt-in, and the number

**What it is.** r30 shipped six optional per-shape utility scales, all defaulting to 1.0, so
today every shape prices exactly as `exact` does. Opting `quantity` in means adding two lines
to `$LIFE_AGENT_KB/utility/model.yaml` and one elicitation row each to
`utility/elicitations.jsonl` — the existing stream's shape is
`{tx_time, latent, stated_value, noise_sigma}`, i.e. **a stated value with a stated
uncertainty**, which is the elicitation method already in use for the five live latents. No new
method needs inventing; "conjoint elicitation" was never in tree and is not proposed.

**What the two numbers mean, in words:**

- `voi_scale_quantity` multiplies `u_correct` — *how much more useful is a correct number than
  a correct exact fact?*
- `regret_scale_quantity` multiplies `u_wrong` — *how much worse is a wrong number than a wrong
  exact fact?*

Together they move the assert bar for quantity questions only, by Chow's rule
`bar = regret·|u_wrong| / (voi·u_correct + regret·|u_wrong|)`. At the deployed Ū
(`u_correct` 1.0, `u_wrong` −8.999) the bar is **0.900** today.

**The price, measured on run 18's own record.** 9 of its withheld rows are quantity-shaped.
Applying each candidate belief to those rows:

| your belief | bar | withholdings it admits | of which RIGHT | of which WRONG |
|---|---:|---:|---:|---:|
| no correction (today) | 0.900 | 0 | 0 | 0 |
| a wrong number is ¾ as bad | 0.871 | 0 | 0 | 0 |
| a wrong number is ½ as bad | 0.818 | 0 | 0 | 0 |
| a wrong number is ⅓ as bad | 0.748 | 0 | 0 | 0 |
| a wrong number is ¼ as bad | 0.692 | 1 | 1 | 0 |
| ½ as bad AND 3× as useful | 0.600 | **4** | **4** | **0** |
| ¼ as bad AND 2× as useful | 0.529 | 4 | 4 | 0 |

**Read this the right way round.** The table is what each *belief* would have done — it is not a
menu to pick the best row from. Choosing the number that maximises the retrodicted rescues is
tuning the utility to the eval, which is the one thing the frozen-elicitation discipline exists
to prevent. State the belief; the consequence follows.

**The finding worth saying out loud:** on this population the *units* lever, armed, is worth
strictly more than the *claim space* lever — 4 correct rescues and 0 wrong commits at the
aggressive setting, against r30b's single neutral displacement. r30b built the honest claim; r30
built the thing that moves the answer rate.

**Options.** (a) State a belief now and opt `quantity` in before r31, so the run measures the
lever armed — but then r31 carries two changes and needs the sweep re-read at the new scales
first to stay attributable. (b) Opt in after r31, so r31 stays a clean single-lever integration
gate. (c) Decline the opt-in: keep every shape at 1.0 and let the exit week say whether quantity
questions are worth a different price at all.

---

## Item 2 — K5, the census-method ruling

**What it is.** Guard register rows **12, 22 and 23** are deliberately left DEFEATED
(`docs/guards.md`). Row 22 says *no census takes a whole MODULE as its universe*; its own
discriminator is a one-line spelling census of exactly the kind row 22 forbids. Row 23 says
*every control discriminates*; it is annotation-blind and matches one literal. Row 12 is the
recorder's own integrity, never attacked. K3's G4 adversary defeated 22 and 23 by narrowing the
*deployed* rule while the *synthetic* mutation test stayed green.

**Why it is a ruling and not a fix.** r27 declined to patch them because it would be *the fourth
consecutive pass over one class*, and on this register's history three passes running have
defeated most previously-resolved rows. The question is method, not code: **what universe may a
guard take, and what makes a control a control** — answer that once and the rows follow.

**The price of leaving it.** Two register rows stand defeated, and known-and-uncovered 17 records
that r27's rows were earned by the author's own mutations and *have not faced an adversary*.
G4 (the adversary pass) is blocked behind this ruling.

**Options.** (a) Rule the method now, in a sentence, and let a later checkpoint implement it.
(b) Park K5 until after the exit week — the guard layer protects a tree whose *behaviour* is
about to be measured directly, which is a stronger check than any census. (c) Commission the G4
adversary pass first and let its findings define the method empirically.

---

## Item 3 — the completion-audit definition, and DONE items 3–5

**What it is.** `ROADMAP.md` records four unreconciled disagreements about what the completion
programme's DONE list actually said. Items 3–5 have **no in-tree text**; only the owner can say
what they were, or whether there were four. The roadmap itself states: *"The completion audit
reads against this list, so it should not read until this is settled."* Stage 3 (the proplang
migration) is gated behind that audit.

**The price of leaving it.** Nothing blocks today — Stage 3 is deferred by its own ruling. It
becomes blocking the moment the proplang ladder opens.

**Options.** (a) Reconstruct items 3–5 now from memory and freeze the list. (b) Declare the list
closed at the two attested items and record that 3–5 did not exist — a defensible ruling given
no text survives. (c) Defer to Conferral 2, when the exit week's result decides whether Stage 3
opens at all.

---

## Item 4 — P2, π\* on real asks

**What it is.** r27 pre-registered P2 — π\* run fresh on a stratified sample of **15 questions
drawn from the 250 real asks**, against the typed arm on the same 15. It **never ran**. It is the
only planned read on the population the gate has never covered (known-and-uncovered 9), and the
one place the arms should differ most: the typed arm reports on ~21% of real asks against ~58% of
authored ones.

**The price.** ~$6 (15 × π\*'s ~$0.38/question on run-18 pricing), inside r27's own $25 cap. Its
correctness column is advisory by its own pre-registration — no gold exists for real asks.

**Why it matters now.** r28 said 96% of the adoption margin is price, not answers. P2 is the read
that would say whether that holds on the questions you actually ask, rather than on authored
ones. The exit week is the alternative way to learn the same thing — for free, but slower and
without π\* as a comparator.

**Options.** (a) Run P2 before the exit week, so the week starts with a measured baseline on real
asks. (b) Park it — the exit week supersedes it, and the FAILURES entries give the same signal at
$0. (c) Run it after the week, as the comparator for what the week measured.

---

## Item 5 — the exit-test protocol

**What it is.** `ROADMAP.md:161`: *"a week of the owner asking Jarvis instead of the incumbent
harnesses for life-data questions + morning triage, misses logged to FAILURES.md."* The proposed
protocol, for sign-off:

- Seven days, starting at the r31 deploy. You route life-data questions and morning triage
  through Jarvis **first**.
- Misses go to `$LIFE_AGENT_KB/FAILURES.md` in the existing entry shape, **plus one new field:
  which tool answered it instead**. That field is what makes the week comparable to π\*.
- `g`/`b` reactions used as you go — they condition `u_wrong` through the live `load_reactions`
  fold, so the week is also the first real revealed-preference stream (which is what streams 3/5
  and the §14 elicitation question have been waiting for).
- Measurement = per-lane decision-log rows (`production_readout.py`) + the FAILURES entries.
- **Disclosed, not fixed this week:** nothing asserts on the readout (known-and-uncovered 12),
  and production on the live box is unobservable from the authoring box (r27 V2) — so your own
  log and the FAILURES entries are the record.
- Conferral 2 reads the verdict with FAILURES rows **classed by answer shape**. If
  computed-question misses dominate, that fires the composition arc's trigger (parked at r31a);
  if a different class dominates, that class is the next arc's evidence.

**Options.** (a) Sign as proposed. (b) Sign with changes. (c) Change the trigger conditions.

---

# RULINGS — taken 2026-08-29 (owner, interviewed against the evidence above)

**1 · The `quantity` scale opt-in is DECLINED for now.** Every shape stays at 1.0. The units
lever therefore continues to ship inert, and r31 measures the claim space at the anchor price.
The reason this is the right call even though the table retrodicts 4 rescues: the belief has not
been formed yet, and the only thing that would have formed it here is the table itself — which
is tuning. **The exit week is what forms it**: a week of real questions is evidence about how
much a wrong number actually costs you, and that is the input the elicitation needs. Re-opens at
Conferral 2 with the week's misses classed by shape.

**2 · K5 is PARKED until after the exit week.** Guard rows 12, 22 and 23 stay defeated and G4
stays blocked, both already published. The rationale is proportionality: the guard layer protects
a tree whose *behaviour* is about to be measured directly for seven days, which is a stronger
check than any census, and ruling the method now would be the fourth consecutive pass over one
class with no new evidence. The method gets ruled at Conferral 2.

**3 · The completion-audit definition and DONE items 3–5 were NOT put to the owner in this
sitting.** Not an oversight to be quietly absorbed: it blocks nothing today (Stage 3 is deferred
by its own ruling, and the audit gates only that), and it is the one item where the evidence does
not improve by waiting. **Carried to Conferral 2**, where it must be settled before the proplang
ladder opens.

**4 · P2 is PARKED — the exit week supersedes it.** ~$6 not spent. The week measures the same
population for $0, with the owner's own judgement instead of a judge, and its FAILURES entries
give the miss *classes* P2 could only approximate. Re-opens at Conferral 2 only if the week's
evidence is ambiguous.

**5 · The exit-test protocol is SIGNED as proposed.** Seven days from the r31 deploy; life-data
questions and morning triage through Jarvis first; misses to `$LIFE_AGENT_KB/FAILURES.md` in the
existing shape **plus the `which tool answered it instead` field**; `g`/`b` reactions used as they
occur; measurement = decision-log rows + FAILURES entries; the two disclosures (nothing asserts on
the readout — known-and-uncovered 12; production unobservable from the authoring box — r27 V2)
stand as stated. Conferral 2 reads the verdict with misses classed by answer shape, which fires or
parks the composition arc.

## What these rulings mean for r31

Unchanged: r31 fires on Pop A, at scales 1.0, as an **integration and do-no-harm gate**, with the
registered expectation from r31a on the page before it runs — **one changed row, a displacement,
Δ moving by roughly −0.001**. It is not a proof of benefit and may not be reported as one.
