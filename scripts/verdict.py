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

import json
import os
import sys
import textwrap
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # import the sibling ask.py
import ask  # noqa: E402

from life_agent.core import config  # noqa: E402
from life_agent.core import narrative as N  # noqa: E402
from life_agent.core import outcomes as O  # noqa: E402

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
    """One lowercased keystroke (no Enter) when stdin is a tty; a line's first char otherwise."""
    sys.stdout.write(prompt)
    sys.stdout.flush()
    if not sys.stdin.isatty():
        ch = (sys.stdin.readline().strip()[:1] or "").lower()
        print(ch)
        return ch
    import termios
    import tty
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    print(ch)
    return ch.lower()


def _show(pos: int, n: int, question: str, scope: str, claim: Any) -> None:
    bar = "─" * 64
    print(f"\n\033[2m{bar}\033[0m")
    print(f"verdict {pos}/{n}   \033[1mQ:\033[0m {question}   \033[2m(scope: {scope})\033[0m")
    asof = claim.as_of or "—"
    print(f"\033[2mcell {claim.cell} · as of {asof} · credence {claim.credence:.2f}\033[0m\n")
    for line in textwrap.wrap(" ".join(claim.text.split()), width=72):
        print(f"  {line}")
    print()


def run(questions: tuple[str, ...]) -> int:
    conn = ask.connect()
    opath = config.OUTCOMES_LOG
    before = N.population_posteriors(opath)

    # build the queue: every worth-verdicting claim across the battery, verified cell first
    queue: list[tuple[str, Any, int, str]] = []
    for q in questions:
        try:
            ask.answer(conn, q, 8)
        except Exception as e:  # noqa: BLE001 — a failed question is skipped, named
            print(f"  (skipped '{q}': {e})")
            continue
        nv = ask.NARRATIVE_LAST
        scope = ask.INTENT_LAST or "unscoped"
        if nv is None:
            continue
        claims = nv.claims
        order = sorted(range(len(claims)),
                       key=lambda i: (claims[i].cell != "verified", -claims[i].credence))
        for i in order:
            if _worth_verdicting(claims[i]):
                queue.append((q, nv, i, scope))

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
        key = _getkey("  [g/b/c/s/q] › ")
        if key == "q":
            print("  (stopping — folding what you've verdicted so far)")
            break
        if key == "s" or key not in ("g", "b", "c"):
            continue
        bit = key == "g"
        if key == "c":
            corr = input("    your answer › ").strip()
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
        folded += N.record_owner_verdicts(results[qid], qid, vd, run_id="verdict", outcomes_path=opath)
    for cr in corrections:
        with _CORRECTIONS.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(cr, ensure_ascii=False) + "\n")

    after = N.population_posteriors(opath)
    _summary(before, after, folded, corrections)
    return 0


def _slug(question: str) -> str:
    import hashlib
    return "dogfood-" + hashlib.sha256(question.encode("utf-8")).hexdigest()[:8]


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
