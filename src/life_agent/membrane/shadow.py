"""shadow.py — the membrane shadow supervisor (Task 4 of the membrane-shadow feature).

Task 1 (:mod:`life_agent.membrane.client`) is the wire transport, Task 2
(:mod:`life_agent.membrane.world`) is the answer-domain world, Task 3
(:mod:`life_agent.membrane.session`) is `MembraneSession` — one booted world driving
decide/verdict/outcome ticks over an injected client, with no opinion on threading or
how many sessions run at once. This module is that opinion: :class:`MembraneShadow`
runs every declared utility form (`table@1`, `latent@1`, ...) as its OWN booted session,
side by side, off the SAME live traffic — never on the decision path itself (Task 5's
bridge wires `submit_*` calls in beside the real executor, not instead of it).

**The threading shape** (ported convention from the proven credence-governor
supervisor): every `submit_*` is enqueue-only and NEVER raises — a full queue drops the
item (counted, `stats()["drops"]`), any submit-path exception is swallowed the same way.
ONE worker thread drains the queue for every form: each item is replayed against every
currently-alive session, in `cfg.forms` order. A session that raises (a `MembraneError`
or anything else) marks its form dead; the worker respawns it — against a FRESH
`snapshot()` call, never the boot-time one, since the point of a respawn is to catch up
on whatever verdicts/outcomes landed while the form was down — up to `max_respawns`
times, with `respawn_backoff_s` between attempts. Backoff is a "not before clock() >= X"
check against the injected `clock`, never a `time.sleep`, so `close()` isn't blocked and
tests can run it instantly.

**Two bookkeeping paths never touch the queue at all** (`submit_decision`'s
`decision_id -> (chosen_action, summary)` bind and `submit_decide`'s terminal-tick
`question_id -> summary` remember): both are plain dict-puts under one lock, done
synchronously at submit time, so a later `submit_reaction` sees them regardless of how
deep the queue is. `submit_decide` remembers the SUBMIT-time summary — cheap, pure,
computed off `payload`/`dec` before anything is enqueued — so a same-question reaction
observes the exact context the live decision was made under, not a lossier
reconstruction off the decision log (:func:`life_agent.membrane.world.
summary_from_decision_event`, the fallback for a `submit_decision` that never saw a
live `submit_decide`, e.g. warm-replay or an out-of-process decider).

**Records are append-only JSON lines at `cfg.log_path`** — one `event_type:
"membrane-shadow"` envelope, `kind` in {`boot`, `respawn`, `decide`, `evidence`}. Every
append is wrapped fail-open (a write error is swallowed, counted as a drop — this is a
shadow, its own I/O failing must never touch the real decision path). Two counters
(`drops`, `skips`) are deliberately never persisted as their own log rows: a drop or a
skip is, by construction, something the caller must never block or pay I/O for — they
are visible only via `stats()`. `boot`/`respawn` rows ARE persisted (they're rare,
worker-thread-side events, not on any hot path).

**`boot_snapshot`** is the pure counterpart: given the decision/reaction logs (+
optionally a fair-fight run directory's warm vectors), it replays the SAME
`verdict_y`/`summary_from_decision_event` reductions session.py's `boot()` already knows
how to consume, so a freshly (re)spawned session starts caught up rather than blank.
Divergence from this feature's own brief, verified against the actual writer
(`scripts/fairfight/run_fairfight.py`): the calibration decisions log a fair-fight run
seeds outcome features from lives at `<run_dir>/shadow_calibration/decisions.jsonl`
(`_redirect_decisions_log`), not `<run_dir>/calibration/decisions.jsonl` — this module
follows the real layout.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import queue
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from life_agent.core import decisions as DEC
from life_agent.core import jsonl_log as JL
from life_agent.core import reactions as RX

from . import world as W
from .client import MembraneClient, request_json
from .session import MembraneSession, ShadowChoice, verdict_y

# --- config + the pure snapshot the worker boots (and re-boots) sessions off --------------


@dataclass(frozen=True)
class ShadowConfig:
    """One shadow run's static configuration. `command` is the `proplang-govhost`
    launch argv (the same shape `MembraneClient.spawn` takes); `forms` is every
    utility form to run side by side (declared order = the per-item processing order
    AND the boot-record write order)."""

    command: list[str]
    forms: tuple[str, ...]
    log_path: Path
    read_timeout_s: float = 300.0
    queue_size: int = 1024
    max_respawns: int = 3
    respawn_backoff_s: float = 60.0


@dataclass(frozen=True)
class BootSnapshot:
    """What a (re)boot replays into a fresh session, via `MembraneSession.boot`'s own
    `verdict_replay`/`outcome_replay` parameters — this dataclass's two list fields are
    that method's parameter types verbatim. `n_source_records` is a diagnostic total (raw
    rows read across every source file, BEFORE any join/exclusion filtering) surfaced at
    `stats()["snapshot_records"]` — the gap between it and `len(verdict_replay) +
    len(outcome_replay)` is exactly how many source rows were excluded (unrouted
    reactions, a `verdict_y`-undeclared pair, an unjoinable warm outcome — see
    :func:`boot_snapshot`)."""

    verdict_replay: list[tuple[W.DecideSummary, int]]
    outcome_replay: list[tuple[str, W.DecideSummary, int]]
    n_source_records: int


SnapshotFn = Callable[[], BootSnapshot]
SessionFactory = Callable[[str], MembraneSession]

# the executor's own vocabulary (core/executor.py's `dec["effector"]`): everything
# except "gather" is a terminal tick (the daemon has committed to an answer/withhold/ask
# for THIS round, as opposed to growing recall and re-asking).
_GATHER_EFFECTOR = "gather"

_QUEUE_POLL_S = 0.05
_CLOSE_JOIN_TIMEOUT_S = 5.0


def _is_terminal_effector(effector: object) -> bool:
    return effector != _GATHER_EFFECTOR


def world_digest(u_bar: Mapping[str, float], *, utility_form: str) -> str:
    """sha256 of the compact wire encoding of one form's handshake declaration — the
    world identity a boot record pins (a drift here means the shadow silently started
    grading a DIFFERENT world than the one it logged)."""
    encoded = request_json(W.handshake_decl(u_bar, utility_form=utility_form))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _binary_sha256(path: str) -> str:
    """The govhost binary's content hash, fail-open to `"unknown"` (a relative/missing
    path, a permission error, or a launcher that isn't a plain file at all must never
    stop the boot record from being written)."""
    try:
        p = Path(path)
        if not p.is_file():
            return "unknown"
        return hashlib.sha256(p.read_bytes()).hexdigest()
    except Exception:
        return "unknown"


def _default_session_factory(
    cfg: ShadowConfig, u_bar: Callable[[], Mapping[str, float]],
) -> SessionFactory:
    def factory(form: str) -> MembraneSession:
        client = MembraneClient.spawn(cfg.command, read_timeout_s=cfg.read_timeout_s)
        return MembraneSession(client, u_bar=u_bar(), utility_form=form)

    return factory


# --- per-form worker-thread-only state (never touched off-thread) ------------------------


@dataclass
class _FormState:
    session: MembraneSession | None = None
    respawn_count: int = 0
    next_attempt_at: float | None = None  # clock()-based; None = no attempt scheduled
    ticks: int = 0


@dataclass(frozen=True)
class _DecideItem:
    question_id: str
    summary: W.DecideSummary
    real_effector: object


@dataclass(frozen=True)
class _VerdictItem:
    decision_id: str
    summary: W.DecideSummary
    y: int


_QueueItem = _DecideItem | _VerdictItem


class MembraneShadow:
    """Boots + supervises one `MembraneSession` per declared form, off live traffic fed
    through `submit_decide`/`submit_decision`/`submit_reaction` — see the module
    docstring for the full contract."""

    def __init__(
        self,
        cfg: ShadowConfig,
        *,
        u_bar: Callable[[], Mapping[str, float]],
        snapshot: SnapshotFn,
        session_factory: SessionFactory | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._cfg = cfg
        self._u_bar = u_bar
        self._snapshot = snapshot
        self._session_factory = session_factory or _default_session_factory(cfg, u_bar)
        self._clock = clock

        self._lock = threading.Lock()
        self._queue: queue.Queue[_QueueItem] = queue.Queue(maxsize=cfg.queue_size)
        self._stop_event = threading.Event()
        self._worker: threading.Thread | None = None

        self._forms: dict[str, _FormState] = {form: _FormState() for form in cfg.forms}
        self._live_summaries: dict[str, W.DecideSummary] = {}
        self._bindings: dict[str, tuple[str, W.DecideSummary]] = {}
        self._drops = 0
        self._skips = 0
        self._snapshot_records = 0
        self._initial_snapshot: BootSnapshot = BootSnapshot(
            verdict_replay=[], outcome_replay=[], n_source_records=0,
        )

    # --- lifecycle -------------------------------------------------------------------

    def start(self) -> None:
        """Take the ONE snapshot every form's initial boot shares, synchronously (so a
        caller who immediately calls `stats()` sees a consistent `snapshot_records`),
        then hand off to the worker thread and return. Booting the sessions themselves
        happens on the worker (a handshake round-trip per form; must not block the
        caller)."""
        try:
            snap = self._snapshot()
        except Exception:
            snap = BootSnapshot(verdict_replay=[], outcome_replay=[], n_source_records=0)
        self._initial_snapshot = snap
        with self._lock:
            self._snapshot_records = snap.n_source_records
        self._stop_event.clear()
        self._worker = threading.Thread(
            target=self._run, name="membrane-shadow", daemon=True,
        )
        self._worker.start()

    def close(self) -> None:
        """Signal the worker to stop, join it (bounded wait), then force `shutdown()` on
        every session's client regardless of whether the worker exited cleanly — a
        wedged worker must never leave a subprocess dangling."""
        self._stop_event.set()
        if self._worker is not None:
            self._worker.join(timeout=_CLOSE_JOIN_TIMEOUT_S)
            self._worker = None
        for state in self._forms.values():
            session = state.session
            if session is None:
                continue
            with contextlib.suppress(Exception):
                session.client.shutdown()

    # --- submit_*: enqueue-only, never raises -----------------------------------------

    def submit_decide(self, question_id: str, payload: dict[str, Any], dec: dict[str, Any]) -> None:
        try:
            summary = W.summary_from_payload(payload, dec)
            effector = dec.get("effector")
            if _is_terminal_effector(effector):
                # remembered unconditionally (before the enqueue attempt below): a full
                # queue may drop the log tick, but must never degrade a later
                # submit_decision's binding to the lossier decision-event fallback.
                with self._lock:
                    self._live_summaries[question_id] = summary
            self._enqueue(_DecideItem(
                question_id=question_id, summary=summary, real_effector=effector,
            ))
        except Exception:
            pass

    def submit_decision(self, decision_id: str, question_id: str, event: dict[str, Any]) -> None:
        try:
            chosen_action = str((event or {}).get("chosen_action", ""))
            with self._lock:
                summary = self._live_summaries.get(question_id)
            if summary is None:
                summary = W.summary_from_decision_event(event or {})
            with self._lock:
                self._bindings[decision_id] = (chosen_action, summary)
        except Exception:
            pass

    def submit_reaction(self, decision_id: str, valence: str) -> None:
        try:
            with self._lock:
                binding = self._bindings.get(decision_id)
            if binding is None:
                self._count_skip()
                return
            chosen_action, summary = binding
            y = verdict_y(chosen_action, valence)
            if y is None:
                self._count_skip()
                return
            self._enqueue(_VerdictItem(decision_id=decision_id, summary=summary, y=y))
        except Exception:
            pass

    def _enqueue(self, item: _QueueItem) -> None:
        try:
            self._queue.put_nowait(item)
        except Exception:
            with self._lock:
                self._drops += 1

    def _count_skip(self) -> None:
        with self._lock:
            self._skips += 1

    # --- stats -------------------------------------------------------------------------

    def stats(self) -> dict[str, object]:
        with self._lock:
            drops, skips, snapshot_records = self._drops, self._skips, self._snapshot_records
        forms: dict[str, object] = {}
        for form in self._cfg.forms:
            state = self._forms[form]
            forms[form] = {
                "alive": state.session is not None,
                "respawns": state.respawn_count,
                "ticks": state.ticks,
            }
        return {
            "forms": forms,
            "drops": drops,
            "skips": skips,
            "queue_depth": self._queue.qsize(),
            "snapshot_records": snapshot_records,
        }

    # --- the worker thread ---------------------------------------------------------------

    def _run(self) -> None:
        for form in self._cfg.forms:
            self._boot_form(
                form, self._forms[form], self._initial_snapshot, from_respawn=False,
            )
        while not self._stop_event.is_set():
            self._maybe_respawn_dead_forms()
            try:
                item = self._queue.get(timeout=_QUEUE_POLL_S)
            except queue.Empty:
                continue
            try:
                self._process_item(item)
            except Exception:
                pass
            finally:
                self._queue.task_done()

    def _process_item(self, item: _QueueItem) -> None:
        now = time.time()
        for form in self._cfg.forms:
            state = self._forms[form]
            if state.session is None:
                continue
            if isinstance(item, _DecideItem):
                self._tick_decide(form, state, item, now)
            else:
                self._tick_verdict(form, state, item, now)

    def _tick_decide(self, form: str, state: _FormState, item: _DecideItem, ts: float) -> None:
        session = state.session
        assert session is not None
        t_before = session.t
        start = time.time()
        try:
            choice: ShadowChoice = session.decide(item.summary)
        except Exception as exc:
            self._handle_death(form, state, exc, from_respawn=False)
            return
        latency_ms = (time.time() - start) * 1000.0
        state.ticks += 1
        self._append_record({
            "event_type": "membrane-shadow", "kind": "decide", "ts": ts,
            "question_id": item.question_id, "form": form,
            "action": choice.action, "raw_internal": choice.raw_internal,
            "real_effector": item.real_effector, "latency_ms": latency_ms,
            "readouts": choice.readouts, "summary": asdict(item.summary), "t": t_before,
        })

    def _tick_verdict(self, form: str, state: _FormState, item: _VerdictItem, ts: float) -> None:
        session = state.session
        assert session is not None
        t_before = session.t
        try:
            session.observe_verdict(item.summary, item.y)
        except Exception as exc:
            self._handle_death(form, state, exc, from_respawn=False)
            return
        state.ticks += 1
        self._append_record({
            "event_type": "membrane-shadow", "kind": "evidence", "ts": ts,
            "stream": "verdict", "decision_id": item.decision_id, "y": item.y,
            "form": form, "t": t_before,
        })

    # --- boot / respawn ------------------------------------------------------------------
    #
    # `respawn_count` counts FAILED respawn attempts consumed against `max_respawns` —
    # NOT the initial boot (a form that never comes up on its first try gets the same
    # `respawn_backoff_s`-spaced retries as one that dies later; the initial attempt is
    # free) and not a successful respawn (recovering doesn't spend budget it didn't use).
    # This keeps the counter race-free: it only ever changes synchronously, inside
    # `_handle_death`, strictly AFTER the attempt that produced it (its own
    # `self._snapshot()` call included) has already returned — so a `stats()` reader
    # never observes `respawns == N` before the Nth respawn's `snapshot()` call has
    # actually happened.

    def _boot_form(
        self, form: str, state: _FormState, snap: BootSnapshot, *, from_respawn: bool,
    ) -> None:
        with self._lock:
            self._snapshot_records = snap.n_source_records
        try:
            session = self._session_factory(form)
            session.boot(verdict_replay=snap.verdict_replay, outcome_replay=snap.outcome_replay)
        except Exception as exc:
            self._handle_death(form, state, exc, from_respawn=from_respawn)
            return
        state.session = session
        state.next_attempt_at = None
        self._write_boot_record(form, session, state)

    def _attempt_respawn(self, form: str, state: _FormState) -> None:
        try:
            snap = self._snapshot()
        except Exception as exc:
            self._handle_death(form, state, exc, from_respawn=True)
            return
        self._boot_form(form, state, snap, from_respawn=True)

    def _maybe_respawn_dead_forms(self) -> None:
        now = self._clock()
        for form in self._cfg.forms:
            state = self._forms[form]
            if state.session is not None or state.next_attempt_at is None:
                continue
            if now >= state.next_attempt_at:
                self._attempt_respawn(form, state)

    def _handle_death(
        self, form: str, state: _FormState, exc: Exception, *, from_respawn: bool,
    ) -> None:
        state.session = None
        if from_respawn:
            state.respawn_count += 1
        permanent = state.respawn_count >= self._cfg.max_respawns
        if permanent:
            state.next_attempt_at = None
        else:
            state.next_attempt_at = self._clock() + self._cfg.respawn_backoff_s
        self._append_record({
            "event_type": "membrane-shadow", "kind": "respawn", "ts": time.time(),
            "form": form, "error": str(exc), "respawn_count": state.respawn_count,
            "max_respawns": self._cfg.max_respawns, "permanent": permanent,
        })

    def _write_boot_record(self, form: str, session: MembraneSession, state: _FormState) -> None:
        binary_sha256 = _binary_sha256(self._cfg.command[0]) if self._cfg.command else "unknown"
        digest = world_digest(self._u_bar(), utility_form=form)
        self._append_record({
            "event_type": "membrane-shadow", "kind": "boot", "ts": time.time(),
            "form": form, "engine": session.engine, "binary_sha256": binary_sha256,
            "forms": list(self._cfg.forms), "world_digest": digest,
            "respawn_count": state.respawn_count,
        })

    # --- log I/O: fail-open, counted as a drop ------------------------------------------

    def _append_record(self, record: dict[str, object]) -> None:
        try:
            line = json.dumps(record, sort_keys=True, ensure_ascii=False)
            JL.append_line(self._cfg.log_path, line)
        except Exception:
            with self._lock:
                self._drops += 1


# --- boot_snapshot(): pure file-reading, never raises -------------------------------------


def _read_decisions(path: Path) -> list[DEC.DecisionEvent]:
    try:
        return DEC.read(path)
    except Exception:
        return []


def _read_reactions(path: Path) -> list[RX.ReactionEvent]:
    try:
        return RX.read(path)
    except Exception:
        return []


def _read_json_rows(path: Path) -> list[dict[str, Any]]:
    try:
        lines = JL.read_lines(path)
    except Exception:
        return []
    rows: list[dict[str, Any]] = []
    for line in lines:
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def boot_snapshot(
    decisions_path: Path, reactions_path: Path, warm_vectors_dir: Path | None,
) -> BootSnapshot:
    """decisions.jsonl ⋈ reactions.jsonl on `decision_id` -> `verdict_y` (the same
    exclusion table `MembraneSession.observe_verdict`'s caller uses) -> `verdict_replay`;
    an unrouted reaction (no matching decision) or a `verdict_y`-undeclared
    (chosen_action, valence) pair is skipped, not raised — `n_source_records` still
    counts the raw row, which is how a caller notices the exclusion happened. Supersedes
    on `decision_id` the same way `core.reactions.load_reactions` does (latest reaction
    per decision_id wins, file order is replay order).

    If `warm_vectors_dir` is given (a fair-fight run directory), also joins
    `arms/baseline/vectors.jsonl` rows (`status == "ok" and asserted is True`, `y =
    asserted_correct`) to that run's OWN shadow calibration log
    (`shadow_calibration/decisions.jsonl` — see the module docstring for why this is NOT
    `calibration/decisions.jsonl`) by `question_id`, latest decision per question_id
    wins. An unjoinable vector row is skipped, counted the same way. The outcome
    event_id is `f"{run_id}:{question_id}"` (falling back to the bare question_id if a
    row carries no `run_id`) — deduped against replay-vs-live collisions the same way
    `MembraneSession.observe_outcome`'s `seen_outcomes` set does downstream.

    Missing/unreadable files anywhere (a fresh KB, a run directory that was never
    written, a corrupt line) never raise — the corresponding part of the snapshot is
    simply empty.
    """
    decisions = _read_decisions(decisions_path)
    reactions = _read_reactions(reactions_path)
    n_source = len(decisions) + len(reactions)

    by_decision_id = {d.decision_id: d for d in decisions if d.decision_id}
    latest_reaction: dict[str, RX.ReactionEvent] = {}
    for r in reactions:
        latest_reaction[r.decision_id] = r

    verdict_replay: list[tuple[W.DecideSummary, int]] = []
    for decision_id, r in latest_reaction.items():
        d = by_decision_id.get(decision_id)
        if d is None:
            continue
        y = verdict_y(d.chosen_action, r.valence)
        if y is None:
            continue
        verdict_replay.append((W.summary_from_decision_event(asdict(d)), y))

    outcome_replay: list[tuple[str, W.DecideSummary, int]] = []
    if warm_vectors_dir is not None:
        vector_rows = _read_json_rows(warm_vectors_dir / "arms" / "baseline" / "vectors.jsonl")
        calib_decisions = _read_decisions(
            warm_vectors_dir / "shadow_calibration" / "decisions.jsonl"
        )
        n_source += len(vector_rows) + len(calib_decisions)
        by_question: dict[str, DEC.DecisionEvent] = {}
        for d in calib_decisions:
            by_question[d.question_id] = d
        for row in vector_rows:
            if row.get("status") != "ok" or row.get("asserted") is not True:
                continue
            question_id = row.get("question_id")
            d = by_question.get(question_id) if isinstance(question_id, str) else None
            if d is None:
                continue
            run_id = row.get("run_id")
            event_id = f"{run_id}:{question_id}" if run_id else str(question_id)
            y = 1 if row.get("asserted_correct") else 0
            outcome_replay.append((event_id, W.summary_from_decision_event(asdict(d)), y))

    return BootSnapshot(
        verdict_replay=verdict_replay, outcome_replay=outcome_replay, n_source_records=n_source,
    )
