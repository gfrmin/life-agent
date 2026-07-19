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
item (counted, `stats()["drops"]`); any submit-path exception (a malformed payload
reaching a `summary_from_*` reducer, etc.) is swallowed and separately counted at
`stats()["submit_errors"]`. ONE worker thread drains the queue for every form: each item
is replayed against every currently-alive session, in `cfg.forms` order. A session that
raises (a `MembraneError` or anything else, including a `read_timeout_s` wedge or a
crashed driver) marks its form dead — its client is shut down first
(`contextlib.suppress`d, since a shadow's own cleanup must never itself raise) so a dead
form never leaks its subprocess — then the worker respawns it, against a FRESH
`snapshot()` call, never the boot-time one, since the point of a respawn is to catch up
on whatever verdicts/outcomes landed while the form was down. `max_respawns` bounds the
TOTAL number of respawn ATTEMPTS over the process lifetime (not just failed ones, and
not reset on a success): once `respawn_count >= max_respawns`, the form is dead until
the daemon itself restarts. Backoff is a "not before clock() >= X" check against the
injected `clock`, never a `time.sleep`, so `close()` isn't blocked and tests can run it
instantly.

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
"membrane-shadow"` envelope, `kind` in {`boot`, `respawn`, `decide`, `gate`, `evidence`,
`stats`}. Every append is wrapped fail-open (a write error is swallowed, counted as a
drop — this is a shadow, its own I/O failing must never touch the real decision path);
the boot-record write itself (`_write_boot_record`, which calls the caller-supplied
`u_bar()` and the handshake encoder — both of which can raise) is fail-open the same
way, and so is the worker's own boot/respawn-scheduling loop, so no exception anywhere
can ever kill the worker thread out from under `stats()`. Three counters (`drops`,
`skips`, `submit_errors`) never write their OWN per-event log row: a drop, a skip, or a
submit-path error is, by construction, something the caller must never block or pay I/O
for at the moment it happens. Their running totals (and each form's `dead_drops`) ARE
periodically snapshotted, though: a `kind: "stats"` row carries `stats()`'s full payload
verbatim, written every `_STATS_EVERY` processed queue items (worker-thread-side, keyed
on item count, never wall-clock — see `_process_item`) and once more, unconditionally,
at `close()` (so a clean shutdown always flushes the last counters even if the item
count never crossed the next `_STATS_EVERY` boundary). This is how an offline, log-only
report (`scripts/membrane/report.py`) can see what a long-lived shadow actually accrued,
without needing to catch it live via `stats()`. `boot`/`respawn` rows ARE persisted
(they're rare, worker-thread-side events, not on any hot path).

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
from dataclasses import asdict, dataclass, fields
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
    AND the boot-record write order).

    `forms` is validated HERE, at construction, against `world.UTILITY_FORMS` — an
    unknown form raises `ValueError` before anything is spawned or served. It used to
    fail much later and much quieter: `handshake_decl` would raise on the worker thread,
    per form, leaving a permanently dead form inside a supervisor that otherwise looked
    healthy, while `config.membrane_utility_forms()`'s docstring and the register both
    claimed this validation already happened. A stated safety property has to be the
    code's, not the prose's. The bridge's `_build_membrane` catches this (as it catches
    every start-up failure) and serves with the membrane DISABLED — loudly printed, never
    a half-running dual shadow."""

    command: list[str]
    forms: tuple[str, ...]
    log_path: Path
    read_timeout_s: float = 300.0
    queue_size: int = 1024
    max_respawns: int = 3
    respawn_backoff_s: float = 60.0

    def __post_init__(self) -> None:
        unknown = [f for f in self.forms if f not in W.UTILITY_FORMS]
        if unknown:
            raise ValueError(
                f"unknown membrane utility form(s) {unknown} "
                f"(declared: {list(W.UTILITY_FORMS)})"
            )
        if not self.forms:
            raise ValueError("membrane utility forms must not be empty")


@dataclass(frozen=True)
class WarmJoin:
    """The warm-outcome join's own arithmetic, reported rather than folded away: how many
    fair-fight vector rows were read, how many calibration decisions they could join
    against, how many corpus-id→mirror-id mappings the run's questions file yielded, and
    how many rows actually JOINED (= `len(outcome_replay)`). `note` is non-empty exactly
    when something is wrong — above all the structural case this feature originally
    shipped broken: `vector_rows > 0` but `joined == 0`, which is an id-namespace
    mismatch, NOT "not enough data". A zero join must read as a zero join."""

    vector_rows: int
    calib_decisions: int
    id_map_size: int
    joined: int
    note: str = ""


@dataclass(frozen=True)
class BootSnapshot:
    """What a (re)boot replays into a fresh session, via `MembraneSession.boot`'s own
    `verdict_replay`/`outcome_replay` parameters — this dataclass's two list fields are
    that method's parameter types verbatim.

    `n_source_records` counts the VERDICT-source rows (decisions + reactions) read raw,
    BEFORE join/exclusion filtering — the gap between it and `len(verdict_replay)` is
    exactly how many were excluded (an unrouted reaction, a `verdict_y`-undeclared pair).
    It is surfaced at `stats()["snapshot_records"]` and persisted into that (re)boot's
    `kind: "boot"` row. It deliberately does NOT include the warm fair-fight rows: those
    live in `warm` (a :class:`WarmJoin`), with their own read-vs-joined split, because a
    warm row that cannot join contributes NOTHING to the shadow and counting it into a
    published "warm corpus size" inflates that figure with rows the shadow never saw."""

    verdict_replay: list[tuple[W.DecideSummary, int]]
    outcome_replay: list[tuple[str, W.DecideSummary, int]]
    n_source_records: int
    warm: WarmJoin | None = None


SnapshotFn = Callable[[], BootSnapshot]
SessionFactory = Callable[[str], MembraneSession]

# the executor's own vocabulary (core/executor.py's `dec["effector"]`): everything
# except "gather" is a terminal tick (the daemon has committed to an answer/withhold/ask
# for THIS round, as opposed to growing recall and re-asking).
_GATHER_EFFECTOR = "gather"

# The empty-evidence context a seam gate fires under (M2 advisory): at BOTH declared
# gates (`scripts/ask.py`'s weak-retrieval and executor-down observations into
# `core.seam.commit`) nothing has been retrieved or extracted yet, so zero candidates,
# no posterior, zero grounded observations is the FAITHFUL summary — not a degraded
# stand-in. The engine consulted under it says what IT would do where the host
# pre-empted it (register §11 i-4: "engine may abstain, host may not refuse the
# question"); the committed act at a gate is always abstain (the seam's gate contract,
# pinned by test_seam).
GATE_SUMMARY = W.DecideSummary(
    n_candidates=0, leader_credence=None, p_none=None, n_obs=0,
    era_split=False, owner_scoped=False, grow_pass=False,
)

_QUEUE_POLL_S = 0.05
_CLOSE_JOIN_TIMEOUT_S = 5.0

# how often (in PROCESSED QUEUE ITEMS, never wall-clock — stays inside the module's
# injected-clock discipline, keeps tests deterministic) the worker flushes a `kind:
# "stats"` row carrying the full `stats()` payload. The daemons this runs as
# (`systemd --user` services) are long-lived, so this periodic row — not the one written
# once at `close()` — is what actually fires in practice.
_STATS_EVERY = 100

# `_live_summaries`/`_bindings` are long-lived-daemon maps fed at submit-time — bounded so
# a shadow that runs for weeks doesn't grow them without limit. FIFO by insertion order
# (never reordered on lookup, so a `submit_reaction` that merely reads a binding can never
# keep it alive past its turn): the oldest entries are evicted once a map exceeds the cap.
_MAX_TRACKED_ENTRIES = 4096


def _bounded_put[V](store: dict[str, V], key: str, value: V, *, cap: int) -> None:
    store[key] = value
    while len(store) > cap:
        store.pop(next(iter(store)))


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


# --- per-form state: WRITTEN only by the worker thread; `stats()`/`close()` read it from
# --- whatever thread calls them (single attribute loads — GIL-atomic, best-effort, never
# --- a correctness requirement for the worker's own operation, so no lock here) ----------


@dataclass
class _FormState:
    session: MembraneSession | None = None
    respawn_count: int = 0
    next_attempt_at: float | None = None  # clock()-based; None = no attempt scheduled
    ticks: int = 0
    dead_drops: int = 0  # items that reached the worker while this form was dead


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


@dataclass(frozen=True)
class _GateItem:
    question_id: str
    gate: str


_QueueItem = _DecideItem | _VerdictItem | _GateItem


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
        self._submit_errors = 0
        self._snapshot_records = 0
        # worker-thread-owned, like `state.ticks` — only `_process_item` (on the worker)
        # ever increments it, so no lock is needed for that write; `close()`'s own
        # stats-record write only reads it after the worker has already been joined.
        self._processed_count = 0
        self._initial_snapshot: BootSnapshot = BootSnapshot(
            verdict_replay=[], outcome_replay=[], n_source_records=0,
        )

    # --- lifecycle -------------------------------------------------------------------

    def start(self) -> None:
        """Take the ONE snapshot every form's initial boot shares, synchronously (so a
        caller who immediately calls `stats()` sees a consistent `snapshot_records`),
        then hand off to the worker thread and return. Booting the sessions themselves
        happens on the worker (a handshake round-trip per form; must not block the
        caller). Raises `RuntimeError` on a second `start()` while a worker is already
        running — silently orphaning the first worker (and every client it booted) is
        never the right call for a lifecycle bug."""
        if self._worker is not None and self._worker.is_alive():
            raise RuntimeError("MembraneShadow.start() called while already running")
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
        wedged worker must never leave a subprocess dangling. Nulls `state.session` for
        every form (review finding: previously left `stats()["forms"][f]["alive"]`
        misreporting True after close(), since nothing else clears it once the worker
        has stopped touching form state) so a post-close `stats()` caller (e.g. GET
        /ready) is told the truth."""
        self._stop_event.set()
        if self._worker is not None:
            self._worker.join(timeout=_CLOSE_JOIN_TIMEOUT_S)
            self._worker = None
        self._write_stats_record()  # a clean shutdown always flushes the last counters
        for state in self._forms.values():
            session = state.session
            state.session = None
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
                    _bounded_put(
                        self._live_summaries, question_id, summary, cap=_MAX_TRACKED_ENTRIES,
                    )
            self._enqueue(_DecideItem(
                question_id=question_id, summary=summary, real_effector=effector,
            ))
        except Exception:
            self._count_submit_error()

    def submit_decision(self, decision_id: str, question_id: str, event: dict[str, Any]) -> None:
        try:
            chosen_action = str((event or {}).get("chosen_action", ""))
            with self._lock:
                summary = self._live_summaries.get(question_id)
            if summary is None:
                summary = W.summary_from_decision_event(event or {})
            with self._lock:
                _bounded_put(
                    self._bindings, decision_id, (chosen_action, summary), cap=_MAX_TRACKED_ENTRIES,
                )
        except Exception:
            self._count_submit_error()

    def submit_gate(self, question_id: str, gate: str) -> None:
        """One seam gate pre-emption (M2 advisory): the host committed abstain by declared
        policy before any engine saw the question. Enqueue-only, never raises — the worker
        consults every live form under :data:`GATE_SUMMARY` and logs what the engine would
        have done instead (`kind: "gate"`)."""
        try:
            self._enqueue(_GateItem(question_id=str(question_id), gate=str(gate)))
        except Exception:
            self._count_submit_error()

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
            self._count_submit_error()

    def _enqueue(self, item: _QueueItem) -> None:
        try:
            self._queue.put_nowait(item)
        except Exception:
            with self._lock:
                self._drops += 1

    def _count_skip(self) -> None:
        with self._lock:
            self._skips += 1

    def _count_submit_error(self) -> None:
        with self._lock:
            self._submit_errors += 1

    # --- stats -------------------------------------------------------------------------

    def stats(self) -> dict[str, object]:
        with self._lock:
            drops, skips, submit_errors, snapshot_records = (
                self._drops, self._skips, self._submit_errors, self._snapshot_records,
            )
        forms: dict[str, object] = {}
        for form in self._cfg.forms:
            state = self._forms[form]
            forms[form] = {
                "alive": state.session is not None,
                "respawns": state.respawn_count,
                "ticks": state.ticks,
                "dead_drops": state.dead_drops,
            }
        return {
            "forms": forms,
            "drops": drops,
            "skips": skips,
            "submit_errors": submit_errors,
            "queue_depth": self._queue.qsize(),
            "snapshot_records": snapshot_records,
        }

    # --- the worker thread ---------------------------------------------------------------

    def _run(self) -> None:
        # No exception anywhere in this method may ever escape: a worker-thread death
        # leaves `state.session` (and hence `stats()["alive"]`) frozen at whatever it
        # last was, so submits would silently fill the queue and drop forever with no
        # visible signal. Every step is independently guarded, per-form where relevant,
        # so one form's failure can never block another's boot or respawn.
        for form in self._cfg.forms:
            with contextlib.suppress(Exception):
                self._boot_form(form, self._forms[form], self._initial_snapshot)
        while not self._stop_event.is_set():
            with contextlib.suppress(Exception):
                self._maybe_respawn_dead_forms()
            try:
                item = self._queue.get(timeout=_QUEUE_POLL_S)
            except queue.Empty:
                continue
            except Exception:
                continue
            with contextlib.suppress(Exception):
                self._process_item(item)

    def _process_item(self, item: _QueueItem) -> None:
        now = time.time()
        for form in self._cfg.forms:
            state = self._forms[form]
            if state.session is None:
                state.dead_drops += 1
                continue
            if isinstance(item, _DecideItem):
                self._tick_decide(form, state, item, now)
            elif isinstance(item, _GateItem):
                self._tick_gate(form, state, item, now)
            else:
                self._tick_verdict(form, state, item, now)
        self._processed_count += 1
        if self._processed_count % _STATS_EVERY == 0:
            self._write_stats_record()

    def _tick_decide(self, form: str, state: _FormState, item: _DecideItem, ts: float) -> None:
        session = state.session
        assert session is not None
        t_before = session.t
        start = time.time()
        try:
            choice: ShadowChoice = session.decide(item.summary)
        except Exception as exc:
            self._handle_death(form, state, exc)
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

    def _tick_gate(self, form: str, state: _FormState, item: _GateItem, ts: float) -> None:
        """A decision tick under :data:`GATE_SUMMARY` — same engine semantics as
        `_tick_decide` (never advances `t`, a raise marks the form dead), logged as
        `kind: "gate"` so the decide differential never mixes a host pre-emption in with
        the ticks the credence engine actually decided. `real_effector` is the literal
        "abstain" — the act the seam's gate contract committed, not a mirrored reply."""
        session = state.session
        assert session is not None
        t_before = session.t
        start = time.time()
        try:
            choice: ShadowChoice = session.decide(GATE_SUMMARY)
        except Exception as exc:
            self._handle_death(form, state, exc)
            return
        latency_ms = (time.time() - start) * 1000.0
        state.ticks += 1
        self._append_record({
            "event_type": "membrane-shadow", "kind": "gate", "ts": ts,
            "question_id": item.question_id, "gate": item.gate, "form": form,
            "action": choice.action, "real_effector": "abstain", "latency_ms": latency_ms,
            "readouts": choice.readouts, "summary": asdict(GATE_SUMMARY), "t": t_before,
        })

    def _tick_verdict(self, form: str, state: _FormState, item: _VerdictItem, ts: float) -> None:
        session = state.session
        assert session is not None
        t_before = session.t
        try:
            session.observe_verdict(item.summary, item.y)
        except Exception as exc:
            self._handle_death(form, state, exc)
            return
        state.ticks += 1
        self._append_record({
            "event_type": "membrane-shadow", "kind": "evidence", "ts": ts,
            "stream": "verdict", "decision_id": item.decision_id, "y": item.y,
            "form": form, "t": t_before,
        })

    # --- boot / respawn ------------------------------------------------------------------
    #
    # `respawn_count` counts every respawn ATTEMPT against `max_respawns` — whether it was
    # triggered by a tick death or a boot failure, and whether it then succeeds or fails.
    # The initial boot is NOT a respawn (free, uncounted): a form that comes up cleanly and
    # only later starts dying on every tick must still exhaust its budget after
    # `max_respawns` real attempts, not respawn forever because only *failed* boots used to
    # count. Once `respawn_count >= max_respawns` the form is dead until the daemon itself
    # restarts — no reset, ever. The increment happens at the TOP of `_attempt_respawn`,
    # strictly before that attempt's own `snapshot()`/boot runs, and ONLY on the worker
    # thread — so there is no data race (a `stats()` reader on another thread may see the
    # incremented count slightly before the attempt it counts has finished, but that's a
    # benign visibility ordering, not a torn write or a double-count).

    def _boot_form(self, form: str, state: _FormState, snap: BootSnapshot) -> None:
        with self._lock:
            self._snapshot_records = snap.n_source_records
        session: MembraneSession | None = None
        try:
            session = self._session_factory(form)
            session.boot(verdict_replay=snap.verdict_replay, outcome_replay=snap.outcome_replay)
        except Exception as exc:
            # the factory may have already spawned a real subprocess before `boot()`
            # raised (e.g. a handshake refusal) — that client was never installed into
            # `state.session`, so `_handle_death` can't reach it; shut it down here.
            if session is not None:
                with contextlib.suppress(Exception):
                    session.client.shutdown()
            self._handle_death(form, state, exc)
            return
        if self._stop_event.is_set():
            # close() may have run the shutdown sweep over `self._forms` already, in the
            # window between this session existing and being installed below — don't
            # install a client close() will never see and thus never shut down.
            with contextlib.suppress(Exception):
                session.client.shutdown()
            return
        state.session = session
        state.next_attempt_at = None
        self._write_boot_record(form, session, state, snap)

    def _attempt_respawn(self, form: str, state: _FormState) -> None:
        state.respawn_count += 1
        try:
            snap = self._snapshot()
        except Exception as exc:
            self._handle_death(form, state, exc)
            return
        self._boot_form(form, state, snap)

    def _maybe_respawn_dead_forms(self) -> None:
        now = self._clock()
        for form in self._cfg.forms:
            state = self._forms[form]
            if state.session is not None or state.next_attempt_at is None:
                continue
            if now >= state.next_attempt_at:
                with contextlib.suppress(Exception):
                    self._attempt_respawn(form, state)

    def _handle_death(self, form: str, state: _FormState, exc: Exception) -> None:
        # a dying session's client is a live subprocess (or wedged one, in the
        # read-timeout case) — Popen's finalizer does not kill the child, so it must be
        # shut down here or it leaks/zombies forever. Exception-suppressed: a shadow's
        # own cleanup failing must never propagate.
        if state.session is not None:
            with contextlib.suppress(Exception):
                state.session.client.shutdown()
        state.session = None
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

    def _write_boot_record(
        self, form: str, session: MembraneSession, state: _FormState, snap: BootSnapshot,
    ) -> None:
        # fail-open: `self._u_bar()` reads a caller-supplied utility posterior that can
        # raise (missing/corrupt calibration), and `handshake_decl` raises on an unknown
        # form — neither may kill the worker thread just because a record couldn't be
        # written; the boot itself already succeeded and must stand.
        #
        # The `u_bar` DICT itself is persisted, not just its digest: the world_digest pins
        # WHICH world was declared but cannot be inverted back to the utility numbers, so
        # an offline reader (scripts/membrane/report.py) that only had the digest was left
        # scoring realized loss — and deriving the respond-reachability threshold — under
        # world.utility_rows' fallback DEFAULTS instead of the posterior the shadow
        # actually decided under. Those differ materially (the live u_wrong is ~-5.9, not
        # the -9.0 default), and the report published the difference as fact. It is seven
        # scalar utility means: no PII, no corpus content (register item 7).
        try:
            binary_sha256 = _binary_sha256(self._cfg.command[0]) if self._cfg.command else "unknown"
            u_bar = {k: float(v) for k, v in self._u_bar().items()}
            digest = world_digest(u_bar, utility_form=form)
            self._append_record({
                "event_type": "membrane-shadow", "kind": "boot", "ts": time.time(),
                "form": form, "engine": session.engine, "binary_sha256": binary_sha256,
                "forms": list(self._cfg.forms), "world_digest": digest, "u_bar": u_bar,
                "respawn_count": state.respawn_count,
                "n_source_records": snap.n_source_records,
                "warm": asdict(snap.warm) if snap.warm is not None else None,
            })
        except Exception:
            with self._lock:
                self._drops += 1

    def _write_stats_record(self) -> None:
        """A `kind: "stats"` row carrying `stats()`'s full payload verbatim — see the
        module docstring for when this fires (periodically, keyed on processed-item
        count, plus once at `close()`). Reuses `_append_record`'s existing fail-open
        path: a stats-write failure must never raise into the worker, same as every
        other record."""
        self._append_record({
            "event_type": "membrane-shadow", "kind": "stats", "ts": time.time(),
            **self.stats(),
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


# `DEC.read`/`RX.read` are documented to raise on ANY single malformed line — correct for
# their own callers, wrong here: a snapshot reader is fail-open by construction, and a
# whole-file catch around them would silently discard every OTHER, well-formed row too
# (one bad line ⇒ the entire replay vanishes, with only `n_source_records` reading a
# no-longer-honest 0). So this module reads + parses line-by-line itself, skipping only
# the bad line, the same idiom `_read_json_rows` already used.
_REACTION_FIELDS: frozenset[str] = frozenset(f.name for f in fields(RX.ReactionEvent))


def _read_lines_fail_open(path: Path) -> list[str]:
    try:
        return JL.read_lines(path)
    except Exception:
        return []


def _read_decisions(path: Path) -> list[DEC.DecisionEvent]:
    events: list[DEC.DecisionEvent] = []
    for line in _read_lines_fail_open(path):
        try:
            obj = json.loads(line)
            obj["action_set"] = tuple(obj.get("action_set", ()))
            events.append(DEC.DecisionEvent(**obj))
        except Exception:
            continue
    return events


def _read_reactions(path: Path) -> list[RX.ReactionEvent]:
    events: list[RX.ReactionEvent] = []
    for line in _read_lines_fail_open(path):
        try:
            obj = json.loads(line)
            events.append(
                RX.ReactionEvent(**{k: v for k, v in obj.items() if k in _REACTION_FIELDS})
            )
        except Exception:
            continue
    return events


def _read_json_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in _read_lines_fail_open(path):
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def warm_question_id_map(run_dir: Path) -> dict[str, str]:
    """`{corpus id -> mirror question_id}` for one fair-fight run — the ONE bridge between
    the two id namespaces this system speaks, and the reason it exists:

    * a fair-fight `OutcomeVector.question_id` is the CORPUS id (`"q-001"` —
      `scripts/fairfight/run_fairfight.py` stamps `str(q["id"])`), while
    * every decision/decide record's `question_id` is the MIRROR id
      (`core.decisions.question_id` — sha256 of the raw question TEXT, [:16]).

    Nothing joins those directly, and a join that silently yields zero rows is
    indistinguishable from "no data yet" — which is precisely how this feature originally
    shipped with a structurally impossible grounded join reported as merely under-powered.
    So the corpus ids are mapped through the questions file that ASSIGNED them: the run's
    own `run_meta.json` records `questions_path` (and `questions_sha256`); each question's
    `id` maps to `decisions.question_id(text)`.

    Fail-open to `{}` (no run_meta, no questions file — it holds PII and lives in
    `$LIFE_AGENT_KB`, so it may simply be absent on another machine; a corrupt YAML; a
    row with no id/question). An empty map is NOT silently equivalent to an empty join:
    every caller reports the map size beside the join count and says so out loud."""
    try:
        import yaml

        meta = json.loads((run_dir / "run_meta.json").read_text(encoding="utf-8"))
        questions_path = Path(str(meta["questions_path"]))
        data = yaml.safe_load(questions_path.read_text(encoding="utf-8"))
        rows = data.get("questions") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            return {}
        out: dict[str, str] = {}
        for q in rows:
            if isinstance(q, dict) and q.get("id") and q.get("question"):
                out[str(q["id"])] = DEC.question_id(str(q["question"]))
        return out
    except Exception:
        return {}


def _warm_outcomes(
    run_dir: Path,
) -> tuple[list[tuple[str, W.DecideSummary, int]], WarmJoin]:
    """One fair-fight run's warm outcome replay, plus the join's own arithmetic.

    `arms/baseline/vectors.jsonl` rows (`status == "ok" and asserted is True`, `y =
    asserted_correct`) are joined to that run's OWN shadow calibration log
    (`shadow_calibration/decisions.jsonl` — see the module docstring for why this is NOT
    `calibration/decisions.jsonl`) THROUGH :func:`warm_question_id_map`, since the two
    files speak different id namespaces. Latest decision per mirror id wins. The outcome
    event_id keeps the CORPUS id (`f"{run_id}:{corpus_id}"`, falling back to the bare
    corpus id) — it is a dedup key, not a join key, and the corpus id is the stabler name
    for the same question across runs.

    A zero join over a non-empty vector file is reported LOUDLY in `WarmJoin.note`, never
    as a bare 0."""
    vector_rows = _read_json_rows(run_dir / "arms" / "baseline" / "vectors.jsonl")
    calib_decisions = _read_decisions(run_dir / "shadow_calibration" / "decisions.jsonl")
    id_map = warm_question_id_map(run_dir)
    by_question: dict[str, DEC.DecisionEvent] = {d.question_id: d for d in calib_decisions}

    replay: list[tuple[str, W.DecideSummary, int]] = []
    for row in vector_rows:
        if row.get("status") != "ok" or row.get("asserted") is not True:
            continue
        corpus_id = row.get("question_id")
        if not isinstance(corpus_id, str):
            continue
        mirror_id = id_map.get(corpus_id)
        d = by_question.get(mirror_id) if mirror_id else None
        if d is None:
            continue
        run_id = row.get("run_id")
        event_id = f"{run_id}:{corpus_id}" if run_id else corpus_id
        replay.append((event_id, W.summary_from_decision_event(asdict(d)), 1
                       if row.get("asserted_correct") else 0))

    note = ""
    if vector_rows and not replay:
        note = (
            f"0 of {len(vector_rows)} vector rows joined — id-namespace mismatch or disjoint "
            f"corpora. Vector question_ids are CORPUS ids (q-001); decision question_ids are "
            f"MIRROR ids (sha256(text)[:16]); the bridge between them is this run's "
            f"run_meta.json -> questions_path (mapped {len(id_map)} ids) matched against "
            f"{len(calib_decisions)} calibration decisions. This is NOT 'not enough data': "
            f"no warm outcome reached the shadow."
        )
    return replay, WarmJoin(
        vector_rows=len(vector_rows), calib_decisions=len(calib_decisions),
        id_map_size=len(id_map), joined=len(replay), note=note,
    )


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

    If `warm_vectors_dir` is given (a fair-fight run directory), :func:`_warm_outcomes`
    also replays that run's baseline-arm outcomes — joined across the id namespaces, and
    accounted separately in `BootSnapshot.warm` rather than folded into
    `n_source_records` (see :class:`BootSnapshot`: an unjoinable warm row must never
    inflate a published warm-corpus size).

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
    warm: WarmJoin | None = None
    if warm_vectors_dir is not None:
        outcome_replay, warm = _warm_outcomes(warm_vectors_dir)

    return BootSnapshot(
        verdict_replay=verdict_replay, outcome_replay=outcome_replay,
        n_source_records=n_source, warm=warm,
    )
