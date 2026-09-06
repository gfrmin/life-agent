# Conferral — what to build after r51's KILL (2026-09-06)

**Class.** `RULINGS` §5's "what to build next when the ruled queue empties". `r51` opened and
closed on 2026-09-06 (`GD-30`, `GD-31`): X1 KILLed at 198 email-only `number`-typed questions
against a bar of 200, and — the finding that matters more than the two rows — the corpus's
foldable supply is one decision per question per pass, ≈ 0.8× `r49`'s 238 ticks, not the ~10×
the checkpoint was opened for (`M-35`). The queue is empty again. Evidence first, then four
priced options, a recommendation first (`M-17`'s form).

## Evidence

- **The supply constraint is unchanged and now better understood** (`GD-28`, `M-35`): the band
  split needs ≈385 verdicted band rows; the owner accrues ≈7 a month; an external corpus adds
  at most one verdicted tick per gradeable question per pass, and repeated passes are not
  evidence.
- **ATM-Bench's usable email subset is 198 questions** (`r51-external-corpus.md` §2): the
  benchmark's own detector types them, its own matcher can grade them, 74 carry a relative-date
  anchor, 14 email-only rows are abstentions (all open-ended). The corpus is downloaded,
  revision-pinned, on-machine, and never enters the tree.
- **The pre-registered instrument is designed and unbuilt**: the vendored evaluator, the k-fold
  harness, the gold-verdict writer with its fail-closed manifest, the KB builder. Its cells
  assumed ~1,000 ticks; at ≤ 198 they must be re-cut blind to any outcome (quintiles at n ≥ 30,
  the fixed buckets as secondary) — a sample-size fact, not a result, so re-cutting is
  legitimate under `M-3`.
- **What the owner's own survey asked for** (pasted 2026-09-06) was the `u_wrong` curve on
  "ATM-Bench emails" — X7 — which does not need 10× n.

## Options

1. **`r51b` — the 1×-n replication on the 198, then the pooling recon (recommended).** Build the
   pre-registered instrument as designed, re-cut the cells to the known n blind to outcomes, one
   executor pass, K = 10. Delivers: the first reliability diagram + ECE for A-CAL
   (`DR-DECISION-1` §2.1) on a corpus the owner did not author; the A3 differential under
   `M-34` on a public corpus; the `u_wrong` curve with implied bar, coverage and selective risk
   (OQ-0′ (c′)'s first data); the lane regex measured against an answer-typed reference. Does
   NOT answer proplang#26's small-n objection — a second corpus at ~1× n showing the same shape
   is corroboration, not power. Cost: build ≈ a day of agent time, $0; executor pass ≤ $2;
   engine ≈ 15 min. Then option 2's recon at $0.
2. **Corpus pooling toward ~1,000 questions — $0 recon first.** LongMemEval (500 questions,
   labelled evidence sessions) and LoCoMo (≈1,986 QA over 10 conversations) are
   conversation-shaped: each needs a transcript producer in pkm, its own gradeability rule and
   its own grader; CRAG is web-QA, not personal memory. The recon prices the yield in the
   foldable unit (`M-35`) before anything is built. Cost: recon $0; the build unknown until
   then; the only route to the power #26's objection asks for.
3. **Re-supply the Claude verdict channel** on the owner's 104 unverdicted questions: +104
   ticks (≈ +44% on 238), ≈23 band rows against the ≈330 the split needs (`A-11` priced it and
   the owner did not choose it). A deliberated pass, agent time, appends verdict rows to the
   owner's KB.
4. **Hold.** proplang#26 is the open demand; nothing opens until it is answered or the owner
   supplies rows.

## RULING

*(open — awaiting the owner)*
