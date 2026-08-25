#!/usr/bin/env python
"""verdict — a keystroke loop for verdicting proposed narrative answers (the flywheel's
frictionless capture).

I (the dev) curate a high-VOI battery of questions; the owner verdicts each proposed claim with
ONE keystroke. The **bit** (good/bad) folds straight into the narrative cells
(:func:`life_agent.core.narrative.record_owner_verdicts` → the verified/unsupported/unverifiable
Betas that gate the bucket). A **custom answer** (the ``c`` key) is recorded as a durable
CORRECTION — the truth plus a steering signal — and is NEVER force-folded (reaction-loop
economics: the bit calibrates, prose steers). Skips are disclosed, not folded.

  bin/verdict-live                 # the curated battery
  bin/verdict-live "my question?"  # verdict an ad-hoc question's claims

Reuses the live seams (no new machinery): ``ask.answer`` produces the claims, the claim verdicts
fold through the SAME core the daemon loop calibrates against. PII stays on the terminal + under
$LIFE_AGENT_KB; nothing is committed.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import re
import sys
import textwrap
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # import the sibling ask.py
import ask

import life_agent.core.config as config
import life_agent.core.lookup as LK
import life_agent.core.narrative as N
import life_agent.core.outcomes as O

# The curated high-VOI battery (narrative-family questions whose grounded claims calibrate the
# verified cell). Edit to steer what the next session verdicts; argv overrides it.
BATTERY: tuple[str, ...] = (
    "what companies have I owned or directed?",
    "what are my sources of income?",
    "what insurance policies do I hold?",
    "what professional qualifications do I have?",
    "what email addresses do I use?",
    "what properties or addresses are associated with me?",
    "which banks hold my accounts?",
)

_CORRECTIONS = config.OUTCOMES_LOG.parent / "corrections.jsonl"


def _worth_verdicting(claim: Any) -> bool:
    """The VOI filter: a grounded ``verified`` claim (the gating cell) or any dated claim is worth a
    bit; an UNDATED ``unverifiable`` claim is the generic hedge/caveat — skip the noise."""
    if claim.cell == "verified" or claim.cell == "unsupported":
        return True
    return claim.as_of is not None


def _getkey(prompt: str) -> str:
    """One lowercased command letter via plain line input (type the letter + Enter). Robust — no
    raw-mode terminal juggling (which broke Ctrl-C and ate buffered input); EOF/Ctrl-C ⇒ quit."""
    try:
        return (input(prompt).strip()[:1] or "").lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return "q"


_PREAMBLES = (
    "based on the sources, ", "based on your documents, ", "based on the sources available, ",
    "from the retrieved sources, ", "looking at the sources provided, i can see ",
    "looking at the sources provided, ", "here is what i can identify: ",
    "i can identify the following: ",
)


def _clean(text: str) -> str:
    """Make a parsed claim readable for verdicting: normalise whitespace, drop markdown (** ` #),
    strip a leading list marker and a known LLM preamble. The UNDERLYING claim (what folds) is
    unchanged — this only cleans the DISPLAY so the owner verdicts the substance, not the markup."""
    t = " ".join(text.split())
    t = t.replace("**", "").replace("`", "").replace("#", "")
    t = re.sub(r"^[\d.)\-*•\s]+", "", t)              # leading numbering / bullets
    low = t.lower()
    for pre in _PREAMBLES:
        if low.startswith(pre):
            t = t[len(pre):]
            break
    return t.strip()


def _show(pos: int, n: int, question: str, scope: str, claim: Any) -> None:
    bar = "─" * 64
    print(f"\n\033[2m{bar}\033[0m")
    print(f"verdict {pos}/{n}   \033[1mQ:\033[0m {question}   \033[2m(scope: {scope})\033[0m")
    asof = claim.as_of or "—"
    print(f"\033[2mcell {claim.cell} · as of {asof} · credence {claim.credence:.2f}\033[0m\n")
    for line in textwrap.wrap(_clean(claim.text), width=72) or ["(empty claim)"]:
        print(f"  \033[1m{line}\033[0m")
    print()


def run(questions: tuple[str, ...]) -> int:
    conn = ask.connect()
    opath = config.OUTCOMES_LOG
    # the wire holds every cell Beta; population_posteriors conditions through it
    brain = LK.shared_brain()
    before = N.population_posteriors(brain, opath)

    # build the queue: every worth-verdicting claim across the battery, verified cell first. The
    # pipeline's chatter (expansion lines, the kappa_att warning) is captured, not shown — a clean
    # progress line stands in, so the owner isn't staring at a flood before the first prompt.
    queue: list[tuple[str, Any, int, str]] = []
    print(f"\033[2mbuilding queue over {len(questions)} questions…\033[0m")
    for n, q in enumerate(questions, 1):
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                ask.answer(conn, q, 8)
        except Exception as e:
            print(f"  \033[2m[{n}/{len(questions)}] skipped — {e}\033[0m")
            continue
        nv = ask.TERM.NARRATIVE_LAST
        scope: str = ask.TERM.INTENT_LAST or "unscoped"
        claims = nv.claims if nv is not None else ()
        order = sorted(range(len(claims)),
                       key=lambda i: (claims[i].cell != "verified", -claims[i].credence))
        picked = [i for i in order if _worth_verdicting(claims[i])]
        for i in picked:
            queue.append((q, nv, i, scope))
        print(f"  \033[2m[{n}/{len(questions)}] {q[:48]:<48} → {len(picked)} claims\033[0m")

    if not queue:
        print("no claims to verdict (the battery produced no grounded narrative claims).")
        return 0

    print(f"\n\033[1m{len(queue)} claims queued.\033[0m  "
          "\033[2m[g]ood  [b]ad  [c]orrect…  [s]kip  [q]uit\033[0m")

    verdicts: dict[str, dict[int, bool]] = {}
    results: dict[str, Any] = {}
    corrections: list[dict[str, Any]] = []
    n = len(queue)
    for pos, (q, nv, i, scope) in enumerate(queue, 1):
        claim = nv.claims[i]
        _show(pos, n, q, scope, claim)
        key = _getkey("  [g/b/c/s/q] › ")  # noqa: RUF001
        if key == "q":
            print("  (stopping — folding what you've verdicted so far)")
            break
        if key == "s" or key not in ("g", "b", "c"):
            continue
        bit = key == "g"
        if key == "c":
            try:
                corr = input("    your answer › ").strip()  # noqa: RUF001
            except (EOFError, KeyboardInterrupt):
                print("\n  (correction cancelled — skipped)")
                continue
            if corr:
                corrections.append({
                    "tx_time": O.now_iso(), "question": q,
                    "claim": claim.text[:300], "cell": claim.cell,
                    "claim_as_of": claim.as_of, "correction": corr})
            bit = False  # a correction means the proposed claim was not the right answer
        qid = _slug(q)  # stable per question (a content slug) within this run
        verdicts.setdefault(qid, {})[i] = bit
        results[qid] = nv

    folded = 0
    for qid, vd in verdicts.items():
        folded += N.record_owner_verdicts(
            results[qid], qid, vd, run_id="verdict", outcomes_path=opath)
    for cr in corrections:
        with _CORRECTIONS.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(cr, ensure_ascii=False) + "\n")
        from life_agent.ledger import mirror as _mirror  # C5 dual-write: after the legacy append
        _mirror.after_legacy_append("calibration.corrections", _CORRECTIONS)

    after = N.population_posteriors(brain, opath)
    _summary(before, after, folded, corrections)
    return 0


def _slug(question: str) -> str:
    """A dogfood run's own id for one question — a DIFFERENT namespace from the decision
    log's ``question_id`` (namespaced ``dogfood-``, and shorter), but derived from the ONE
    question-id hash (``core.decisions.question_id``) rather than a fifth hand-rolled
    sha256 of the same text. Byte-identical to what it produced before (question_id is the
    first 16 hex chars of that digest, so its first 8 are these 8)."""
    from life_agent.core import decisions as DEC

    return "dogfood-" + DEC.question_id(question)[:8]


def _mean(ab: tuple[float, float]) -> float:
    a, b = ab
    return a / (a + b)


def _summary(before: dict[str, tuple[float, float]], after: dict[str, tuple[float, float]],
             folded: int, corrections: list[dict[str, Any]]) -> None:
    print(f"\n\033[1mfolded {folded} verdict(s).\033[0m")
    for cell in ("verified", "unsupported", "unverifiable"):
        b, a = _mean(before[cell]), _mean(after[cell])
        arrow = f"{b:.3f} → {a:.3f}" if before[cell] != after[cell] else f"{a:.3f} (unchanged)"
        print(f"  {cell:<12} {arrow}   \033[2m{after[cell]}\033[0m")
    if corrections:
        print(f"\n\033[1m{len(corrections)} correction(s) recorded\033[0m "
              f"\033[2m(→ {_CORRECTIONS}, not folded — steering signal):\033[0m")
        for cr in corrections:
            print(f"  • {cr['correction']}")


if __name__ == "__main__":
    args = tuple(a for a in sys.argv[1:] if a.strip())
    raise SystemExit(run(args or BATTERY))
