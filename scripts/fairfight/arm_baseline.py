"""``scripts/fairfight/arm_baseline.py`` — the ``baseline`` arm: the executor surface.

Wraps ``ask.answer_via_executor`` (the bridge's decider, over the capability bridge) into one
raw capture shape, :class:`RawAnswer`, that the fair-fight runner logs uniformly per (arm,
question). The bridge's own spend is out-of-process and invisible from here (the runner marks
``cost_status="partial"`` for this arm); the readiness probe (``ask._executor_ready``) is
checked FIRST and a down stack is a NAMED ``status="error"`` — never a silent fallback.

``decision_view`` is mapped from the executor's structured ``View`` (``ask.EXECUTOR_VIEW_LAST``)
by :func:`_executor_decision` into the decision_view shape ``grading.grade_channels`` reads,
so ``asserted``/``declined`` derive structurally instead of by pattern-matching rendered text.
A declined route (``view["route"] is None``) carries no candidate list, so grading falls back
to ``grading.detect_decline`` over the rendered text — never a fabricated candidate list.
``declined`` follows ``scripts/fairfight/grading.py``'s ONE convention: a structured view
derives it as ``not asserted and not scoped`` (:func:`_view_declined`).

``lineage_keys`` is the bridge's content-addressed decision id (``ask.EXECUTOR_LAST``).

Every exception inside the underlying answer call — including ``SystemExit``, which
``core/llm.py``'s ``anthropic_complete``/``openai_complete``/``secret`` raise on API/secret
failure — is caught and mapped to ``status="error"``, never propagated: the runner must
survive one bad question. The cost meter is still read in that case (a partial call may have
billed).
"""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # scripts/: ask

from life_agent.core.llm import LLMResult, meter_read, reset_meter

from .grading import detect_decline

# the sibling script ask.py is imported lazily inside the functions
# below, AFTER the sys.path insert above has run at module load — matching the established
# cross-script pattern (scripts/fairfight/grading.py's ``detect_decline`` imports ``ask``
# the same way, lazily, for the same reason: keep this module's own import light and avoid
# a hard import-time dependency on the live corpus config ``ask`` resolves at import).


@dataclass
class RawAnswer:
    """One arm's raw capture for one question — the ``answers.jsonl`` row payload before
    ``scripts/fairfight/grading.py`` grades it into an ``OutcomeVector``.

    ``cards`` (task 10 addition): the retrieved ``core.sources.SourceCard`` set
    ``ask.answer_via_executor`` returned, as JSON-safe dicts
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
    effort: dict[str, int]  # ask.TERM.EFFORT_LAST snapshot; {} when this arm's effort is unknown
    cards: tuple[dict[str, Any], ...]


def _view_declined(view: dict) -> bool:
    """The ONE declined convention this harness uses for a structured decision view
    (``scripts/fairfight/grading.py``'s ``grade_channels``): a decision that neither
    asserts nor scopes IS a withholding, whatever its ``action`` is named."""
    return not bool(view.get("asserted", False)) and not bool(view.get("scoped", False))


def _executor_decision(view: dict[str, Any]) -> dict[str, Any] | None:
    """Build the harness's decision_view convention (``grading.grade_channels``'s
    contract) from the executor's own structured ``View`` (``ask.EXECUTOR_VIEW_LAST``).

    A declined route (``view["route"] is None``) returns ``None``: there is no candidate
    list, so the caller grades the rendered text via ``grading.detect_decline``. Otherwise
    a ``report`` or a ``hedge`` is an assertion-class act; ``scoped`` is always ``False``
    (the executor's effector vocabulary has no scoped report).
    """
    if view["route"] is None:
        return None
    action = str(view["effector"])
    candidates = list(view["candidates"])
    credences = list(view["credences"])
    asserted = action in ("report", "hedge")
    if action == "report":
        asserted_values = list(view["asserted"][:1])
    elif action == "hedge":
        asserted_values = list(candidates)
    else:  # ask_clarify | abstain | miss — a withholding
        asserted_values = []
    return {
        "family": "lookup", "action": action, "effector": action,
        "asserted": asserted, "scoped": False,
        "asserted_values": asserted_values, "candidates": candidates,
        "credences": credences, "p_none": view["p_none"],
    }


def answer_baseline(q: dict, k: int) -> RawAnswer:
    """Answer one question through the executor surface, metered. Never raises — an
    underlying failure becomes ``status="error"`` with the exception named in ``notes``
    (see the module docstring for why ``SystemExit`` is caught alongside ``Exception``).
    The executor has no cache knob (``ask.answer_via_executor`` is a pure HTTP driver over
    the bridge — its cache lives server-side); the bridge's own spend is disclosed as
    out-of-band (this module's docstring, cost_status=partial)."""
    import ask  # sibling script; sys.path set at module load, above

    question_id = str(q["id"])
    reset_meter()
    # Explicit reset here (not just relying on answer_via_executor's own top-of-function
    # reset): the executor-down branch below raises BEFORE that function runs, so
    # without this a down-daemon question would read the PRIOR question's EFFORT_LAST —
    # exactly the cross-question leak the harness must not have.
    ask.TERM.EFFORT_LAST = {}
    t0 = time.monotonic()
    text = ""
    declined = False
    decision_view: dict | None = None
    lineage_keys: tuple[str, ...] = ()
    status = "ok"
    notes = ""
    cards: list[dict[str, Any]] = []

    try:
        if not ask._executor_ready():
            raise RuntimeError(
                "executor unreachable — the bridge or its decider is down "
                f"(bridge={ask.EXECUTOR_BRIDGE!r}); "
                "no silent in-process fallback for the baseline arm — the runner decides")
        text, raw_cards, _scores = ask.answer_via_executor(q["question"], k)
        cards = [{"n": c.n, "text": c.text, "origin": c.origin} for c in raw_cards]
        decision_view = (
            _executor_decision(ask.EXECUTOR_VIEW_LAST)
            if ask.EXECUTOR_VIEW_LAST is not None else None)
        declined = (
            _view_declined(decision_view) if decision_view is not None
            else detect_decline(text))
        lineage_keys = (ask.EXECUTOR_LAST,) if ask.EXECUTOR_LAST else ()
    except (Exception, SystemExit) as e:
        status = "error"
        notes = f"{type(e).__name__}: {e}"
        text = ""
        declined = False
        decision_view = None
        lineage_keys = ()
        cards = []

    effort = dict(ask.TERM.EFFORT_LAST)
    llm_calls = meter_read()
    latency_s = time.monotonic() - t0
    return RawAnswer(
        question_id=question_id, text=text, declined=declined, latency_s=latency_s,
        llm_calls=llm_calls, decision_view=decision_view, lineage_keys=lineage_keys,
        status=status, notes=notes, effort=effort, cards=tuple(cards),
    )
