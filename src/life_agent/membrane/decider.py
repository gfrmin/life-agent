"""decider.py — the one place life-agent's actions are ranked.

A :class:`Decider` holds one booted :class:`~life_agent.membrane.session.MembraneSession`
over the pinned ``proplang-host`` engine and answers ``/decide`` synchronously:

    request → candidate posterior (core/posterior) → DecideSummary → engine act
            → enactment (membrane/coarse) → the executor's view

It boots from the decision ⋈ verdict join (:func:`life_agent.membrane.boot.boot_snapshot`)
and folds each later verdict as one evidence tick; a decision is folded at most once per
engine life, whether by the boot replay or live. The engine is the decider: when it is
down, :meth:`Decider.decide` raises :class:`DeciderUnavailableError` and nothing substitutes for
it. A failed engine is re-booted from a fresh snapshot on the next request.

**Stated limitations.** The utility is declared once, at the handshake, from the
default-shape Ū (per-tick utility is unshipped on the pinned wire; gfrmin/proplang#29 item
6). A second reaction to the same decision is not folded live; the next boot's snapshot
takes the latest one.
"""
from __future__ import annotations

import contextlib
import threading
from collections.abc import Callable, Mapping
from typing import Any

from life_agent.core import posterior as POST

from . import coarse as CO
from . import world as W
from .boot import BootSnapshot
from .client import MembraneClient
from .session import MembraneSession, verdict_y

# Remembered summaries are bounded: a verdict for a decision older than this many
# decisions still folds at the next boot, from the decision log.
_MAX_REMEMBERED = 4096


class DeciderUnavailableError(RuntimeError):
    """The engine could not rank this request. The reply says so; no host decider runs."""


def summary(payload: Mapping[str, Any], credences: list[float],
            p_none: float) -> W.DecideSummary:
    """The world's view of one request and its posterior, with gather's feasibility and the
    price of the gather that would be enacted."""
    base = W.summary_from_payload(dict(payload), {"credences": credences, "p_none": p_none})
    # grow_pass is False: recorded decisions do not carry it, so a live tick must not sit in
    # a feature cell the boot replay can never fill.
    return W.DecideSummary(**{**base.__dict__, "grow_pass": False,
                              "gather_open": CO.gather_open(dict(payload)),
                              "gather_cost": CO.gather_cost(dict(payload))})


class Decider:
    """One engine session, booted on first use, serving ``decide`` and verdict ticks."""

    def __init__(self, spawn: Callable[[], MembraneClient],
                 u_bar: Callable[[], Mapping[str, float]],
                 snapshot: Callable[[], BootSnapshot], *,
                 log: Callable[[str], None] = print) -> None:
        self._spawn = spawn
        self._u_bar = u_bar
        self._snapshot = snapshot
        self._log = log
        self._lock = threading.Lock()
        self._session: MembraneSession | None = None
        self._declared: Mapping[str, float] = {}  # the numbers the live handshake declared
        self._by_question: dict[str, W.DecideSummary] = {}
        self._by_decision: dict[str, tuple[str, W.DecideSummary]] = {}
        self._folded: set[str] = set()
        self._last_error = ""

    # --- lifecycle -------------------------------------------------------------------

    def _ensure(self) -> MembraneSession:
        if self._session is not None:
            return self._session
        client = self._spawn()
        try:
            declared = self._u_bar()
            session = MembraneSession(client, u_bar=declared, log=self._log)
            snap = self._snapshot()
            session.boot(verdict_replay=snap.verdict_replay,
                         outcome_replay=snap.outcome_replay)
            self._folded = set(snap.verdict_decision_ids)
        except Exception:
            with contextlib.suppress(Exception):
                client.shutdown()
            raise
        self._log(f"life-agent decider: booted, {len(snap.verdict_replay)} verdicts replayed, "
                  f"models={session.engine.get('models')}")
        self._session, self._declared = session, declared
        return session

    def _fail(self, e: Exception) -> DeciderUnavailableError:
        self._last_error = f"{type(e).__name__}: {e}"
        if self._session is not None:
            with contextlib.suppress(Exception):
                self._session.client.shutdown()
        self._session = None
        return DeciderUnavailableError(f"the decider engine is unavailable ({self._last_error})")

    def boot(self) -> None:
        """Boot now rather than on the first request. Raises on failure."""
        with self._lock:
            try:
                self._ensure()
            except Exception as e:
                raise self._fail(e) from e

    def close(self) -> None:
        with self._lock:
            if self._session is not None:
                with contextlib.suppress(Exception):
                    self._session.client.shutdown()
            self._session = None

    def status(self) -> dict[str, object]:
        """Never waits on the lock: ``booted`` is False while a boot is in progress."""
        s = self._session
        return {"booted": s is not None, "t": s.t if s is not None else None,
                "last_error": self._last_error}

    # --- the decision --------------------------------------------------------------

    def decide(self, question_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Rank one ``/decide`` request and return the executor's view: ``effector``,
        ``value``, ``probe``, ``credences``, ``p_none``, plus the engine's ``act``, its
        ``p1`` readout and ``eu`` (the enacted row's expected utility at that ``p1``, under the
        handshake's numbers and before any per-tick price)."""
        candidates = list(payload.get("candidates") or [])
        credences, p_none = POST.candidate_posterior(
            len(candidates), list(payload.get("observations") or []), float(payload["rho"]))
        s = summary(payload, credences, p_none)
        with self._lock:
            try:
                session = self._ensure()
                choice = session.decide(s)
            except Exception as e:
                raise self._fail(e) from e
            self._by_question[question_id] = s
            _trim(self._by_question)
        view = CO.enact(choice.action, dict(payload), credences, p_none)
        p1 = choice.readouts.get("p1")
        eu = (W.eu_by_action(self._declared, float(p1))[choice.action]
              if isinstance(p1, (int, float)) and not isinstance(p1, bool) else None)
        return {**view, "act": choice.action, "p1": p1, "eu": eu}

    # --- verdicts --------------------------------------------------------------------

    def bind(self, decision_id: str, question_id: str, event: Mapping[str, Any]) -> None:
        """Remember what a recorded decision was, so its verdict can be folded. The
        decide-time summary is used when this process ranked the question; otherwise the
        decision event's own posterior summary."""
        s = self._by_question.get(question_id) or W.summary_from_decision_event(dict(event))
        self._by_decision[decision_id] = (str(event.get("chosen_action") or ""), s)
        _trim(self._by_decision)

    def observe_reaction(self, decision_id: str, valence: str) -> bool:
        """Fold the owner's verdict on a bound decision as one evidence tick. Returns
        whether it folded now (an unbound decision, an undeclared (act, valence) pair or a
        second verdict on the same decision does not; with no engine booted, the next boot
        replays it from the reactions log, so it is not folded twice)."""
        bound = self._by_decision.get(decision_id)
        if bound is None:
            return False
        action, s = bound
        y = verdict_y(action, valence)
        if y is None:
            return False
        with self._lock:
            if decision_id in self._folded:
                return False
            self._folded.add(decision_id)
            if self._session is None:
                return False  # the next boot replays it from the reactions log
            try:
                self._session.observe_verdict(s, y)
            except Exception as e:
                raise self._fail(e) from e
        return True


def _trim[V](store: dict[str, V]) -> None:
    while len(store) > _MAX_REMEMBERED:
        del store[next(iter(store))]
