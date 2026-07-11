"""``scripts/fairfight/arm_baseline.py`` — the ``baseline`` (credence executor) and
``inprocess`` (typed-families, gather-augmented) arms.

Both wrap EXISTING life-agent answer entrypoints (never rebuilds them) into one raw
capture shape, :class:`RawAnswer`, that the fair-fight runner (a later task) can log
uniformly per (arm, question) regardless of which entrypoint answered:

- ``path="executor"`` (arm ``baseline``) drives ``ask.answer_via_executor`` — the credence
  answer-brain daemon over the capability bridge (``life_agent.core.executor``). Its own
  spend is out-of-process and invisible from here (the runner is expected to mark
  ``cost_status="partial"`` for this arm downstream); the readiness probe
  (``ask._executor_ready``) is checked FIRST and a down stack is a NAMED ``status="error"``
  — never a silent in-process fallback (that would mislabel the arm as the executor's own
  answer when it is really a different path's).
- ``path="inprocess"`` (arm ``inprocess``) drives ``ask.answer(conn, question, k,
  gather=True)`` — the in-process typed-families path WITH the gather-augmented lookup loop
  (foundations §4 gather.py), matching the ``gate_paired_outcomes`` "typed" pass
  (``scripts/run_eval.py``) and offering the fully-metered $ headline the executor arm
  cannot (its own LLM calls run in THIS process, bracketed by ``core.llm``'s meter).

``decision_view`` is built the SAME way ``scripts/triage_answers.py``'s ``triage_one`` does
(``_lookup_view``/``_narrative_view``/``_withheld_view`` over ``ask.LOOKUP_LAST`` /
``ask.NARRATIVE_LAST`` captured before the next call resets them) for the in-process arm,
and left ``None`` for the executor arm (its render is free text in the shared credence
grammar, with no structured candidate/asserted view surfaced to this module — see
``ask.answer_via_executor``'s ``View`` shape, which the executor's own body does not
expose past the rendered string). ``declined`` follows
``scripts/fairfight/grading.py``'s ONE convention throughout this harness, never a third:
a structured view derives it as ``not asserted and not scoped``; free text (the executor
arm) derives it via ``grading.detect_decline`` over the rendered text.

``lineage_keys`` for the in-process arm is EVERY key ``ask.STAGES_LAST`` recorded this call
(``tuple(ask.STAGES_LAST.values())``, in call order) — a superset of, and deliberately NOT,
``scripts/run_eval.py``'s ``synthesis_grade`` 2-key ``("retrieve", "synthesize")`` subset:
that subset silently drops the ``lookup_answer``/``narrative_answer`` cache key on exactly
the interesting case (a typed family decided), which would leave this harness's provenance
field empty for most point-fact questions. For the executor arm, lineage is the bridge's
own content-addressed decision id (``ask.EXECUTOR_LAST``), the sole "*_LAST" the executor
path binds a verdict to.

Every exception inside the underlying answer call — including ``SystemExit``, which
``core/llm.py``'s ``anthropic_complete``/``openai_complete``/``secret`` raise on API/secret
failure (the SAME signal ``core/expansion.py`` and ``core/rerank.py`` already catch
explicitly around their own completions) — is caught and mapped to ``status="error"``,
never propagated: the runner must survive one bad question. The cost meter is still read
in that case (a partial call may have billed).
"""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # scripts/: ask, triage_answers

from life_agent.core.llm import LLMResult, meter_read, reset_meter

from .grading import detect_decline

# sibling scripts (ask.py, triage_answers.py) are imported lazily inside the functions
# below, AFTER the sys.path insert above has run at module load — matching the established
# cross-script pattern (scripts/fairfight/grading.py's ``detect_decline`` imports ``ask``
# the same way, lazily, for the same reason: keep this module's own import light and avoid
# a hard import-time dependency on the live corpus config ``ask`` resolves at import).


@dataclass
class RawAnswer:
    """One arm's raw capture for one question — the ``answers.jsonl`` row payload before
    ``scripts/fairfight/grading.py`` grades it into an ``OutcomeVector``.

    ``cards`` (task 10 addition): the retrieved ``core.sources.SourceCard`` set
    ``ask.answer``/``ask.answer_via_executor`` returned, as JSON-safe dicts
    (``{"n", "text", "origin"}``) — the runner's ONLY source for ``grade_channels``'s
    ``retrieved_texts_full`` and the judge's cited-source block for these arms (the
    prior tasks' single return statement discarded this tuple element as ``_cards``;
    captured here instead of rebuilding retrieval). Always ``()`` on ``status="error"``
    (no call completed) and for the competitor arm, whose retrieved set lives in its
    tool-log rows instead — a different shape entirely (see ``arm_hermes.py``)."""

    question_id: str
    text: str
    declined: bool
    latency_s: float
    llm_calls: list[LLMResult]
    decision_view: dict | None
    lineage_keys: tuple[str, ...]
    status: str  # "ok" | "error" (timeout is a competitor-arm-only status)
    notes: str
    effort: dict[str, int]  # ask.EFFORT_LAST snapshot; {} when this arm's effort is unknown
    cards: tuple[dict[str, Any], ...]


def _view_declined(view: dict) -> bool:
    """The ONE declined convention this harness uses for a structured decision view
    (``scripts/fairfight/grading.py``'s ``grade_channels``): a decision that neither
    asserts nor scopes IS a withholding, whatever its ``action`` is named."""
    return not bool(view.get("asserted", False)) and not bool(view.get("scoped", False))


def _inprocess_decision(ask) -> tuple[dict, bool, tuple[str, ...]]:
    """Build (decision_view, declined, lineage_keys) from the just-completed in-process
    ``ask.answer(...)`` call, the same way ``triage_answers.triage_one`` does — captured
    from ``ask.LOOKUP_LAST``/``ask.NARRATIVE_LAST`` before any later call resets them."""
    from triage_answers import _lookup_view, _narrative_view, _withheld_view

    lk, nv = ask.LOOKUP_LAST, ask.NARRATIVE_LAST
    view = _lookup_view(lk) if lk is not None else (
        _narrative_view(nv) if nv is not None else _withheld_view())
    return view, _view_declined(view), tuple(ask.STAGES_LAST.values())


def answer_baseline(q: dict, k: int, *, path: Literal["executor", "inprocess"]) -> RawAnswer:
    """Answer one question via ``path``'s existing entrypoint, metered. Never raises — an
    underlying failure becomes ``status="error"`` with the exception named in ``notes``
    (see the module docstring for why ``SystemExit`` is caught alongside ``Exception``)."""
    import ask  # sibling script; sys.path set at module load, above

    question_id = str(q["id"])
    reset_meter()
    # Explicit reset here (not just relying on ask.answer/answer_via_executor's own top-of-
    # function reset): the executor-down branch below raises BEFORE either function runs, so
    # without this a down-daemon question would read the PRIOR question's EFFORT_LAST —
    # exactly the cross-question leak the harness must not have.
    ask.EFFORT_LAST = {}
    t0 = time.monotonic()
    text = ""
    declined = False
    decision_view: dict | None = None
    lineage_keys: tuple[str, ...] = ()
    status = "ok"
    notes = ""
    cards: list[dict[str, Any]] = []

    try:
        if path == "executor":
            if not ask._executor_ready():
                raise RuntimeError(
                    "executor unreachable — the answer-brain daemon/bridge is down "
                    f"(bridge={ask.EXECUTOR_BRIDGE!r} daemon={ask.EXECUTOR_DAEMON!r}); "
                    "no silent in-process fallback for the baseline arm — the runner decides")
            text, raw_cards, _scores = ask.answer_via_executor(q["question"], k)
            cards = [{"n": c.n, "text": c.text, "origin": c.origin} for c in raw_cards]
            declined = detect_decline(text)
            lineage_keys = (ask.EXECUTOR_LAST,) if ask.EXECUTOR_LAST else ()
        else:  # "inprocess"
            conn = ask.connect()
            try:
                text, raw_cards, _scores = ask.answer(conn, q["question"], k, gather=True)
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
