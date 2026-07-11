"""``scripts/fairfight/arm_synthesis.py`` — the ``synthesis`` arm.

**Verified against the actual code (task-8 brief instruction — do not trust the plan's
guess).** The plan's interface comment reads ``def answer_synthesis(q, k) -> RawAnswer
# monolithic path run_eval --synthesis exercises``, conflating two DIFFERENT things that
exist in this codebase under similar names:

1. The **"monolithic instrument"** (``ask.answer(..., families=False)``) — raw synthesize
   prose with the typed lookup/narrative families switched OFF. This is the §8 adoption
   gate's BASELINE, used by ``scripts/run_eval.py``'s ``gate_paired_outcomes`` (the
   ``--gate`` flag), NOT by ``--synthesis``.
2. What ``scripts/run_eval.py --synthesis`` ACTUALLY calls, in ``synthesis_grade``::

       text, cards, _ = ask.answer(conn, q["question"], k, no_cache=fresh)

   — the DEFAULT production ``ask.answer`` call: ``families=True`` (implicit default,
   typed lookup/narrative families ON), ``gather=False``, ``rerank=False``. ``fresh``
   is only ``True`` under the CLI's own ``--fresh`` flag; a normal run passes
   ``no_cache=False``, i.e. the plain default call. ``synthesis_grade`` then grades
   this answer end-to-end with a cross-provider LLM judge (faithfulness +
   citation_fidelity) — an instrument this arm module does NOT reproduce (that is
   ``scripts/fairfight/judge.py``'s job; this module is only the raw capture).

``answer_synthesis`` mirrors (2), the ACTUAL ``--synthesis`` call, exactly: same entrypoint,
same flags (gather/rerank both off — the one config axis distinguishing this arm from
``arm_baseline.answer_baseline(path="inprocess")``, which turns gather ON). Despite the
plan's "monolithic" label, this arm's decisions ARE typed-family decisions when the lookup
or narrative family fires — same as any other ``ask.answer`` call — so ``decision_view``
is built the same way as the ``inprocess`` arm (see ``arm_baseline._inprocess_decision``),
not left as free text.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # scripts/: ask, triage_answers

from life_agent.core.llm import meter_read, reset_meter

from .arm_baseline import RawAnswer, _inprocess_decision


def answer_synthesis(q: dict, k: int) -> RawAnswer:
    """Answer one question exactly as ``scripts/run_eval.py --synthesis``'s
    ``synthesis_grade`` does (``ask.answer(conn, question, k)`` — the default in-process
    typed-families path, gather and rerank both off), metered. Never raises — see
    ``arm_baseline``'s module docstring for why ``SystemExit`` is caught alongside
    ``Exception`` (the same ``core/llm.py`` failure signal ``core/expansion.py`` and
    ``core/rerank.py`` already catch explicitly)."""
    import ask  # sibling script; sys.path set at module load, above

    question_id = str(q["id"])
    reset_meter()
    ask.EFFORT_LAST = {}  # see arm_baseline.answer_baseline: guards against cross-question leak
    t0 = time.monotonic()
    text = ""
    declined = False
    decision_view: dict | None = None
    lineage_keys: tuple[str, ...] = ()
    status = "ok"
    notes = ""
    cards: list[dict[str, Any]] = []

    try:
        conn = ask.connect()
        try:
            text, raw_cards, _scores = ask.answer(conn, q["question"], k)
            cards = [{"n": c.n, "text": c.text, "origin": c.origin} for c in raw_cards]
        finally:
            conn.close()
        decision_view, declined, lineage_keys = _inprocess_decision(ask)
    except (Exception, SystemExit) as e:
        status = "error"
        notes = f"{type(e).__name__}: {e}"
        text = ""
        declined = False
        decision_view = None
        lineage_keys = ()
        cards = []

    effort = dict(ask.EFFORT_LAST)
    llm_calls = meter_read()
    latency_s = time.monotonic() - t0
    return RawAnswer(
        question_id=question_id, text=text, declined=declined, latency_s=latency_s,
        llm_calls=llm_calls, decision_view=decision_view, lineage_keys=lineage_keys,
        status=status, notes=notes, effort=effort, cards=tuple(cards),
    )
