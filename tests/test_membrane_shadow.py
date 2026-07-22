"""Hermetic tests for the membrane shadow supervisor (life_agent.membrane.shadow).

No wire, no subprocess, no real sleeps over ~0.1s: `_FakeSession` stands in for
`MembraneSession` (records every call, can be told to raise on `boot`/`decide`), a
`_FakeSessionFactory` hands out fake sessions and counts how many times it was called
per form, and a plain counting function stands in for the injected `clock`. These pin
the supervisor's contract: `start()` boots every declared form off ONE synchronous
snapshot and writes a boot record per form; `submit_decide`/`submit_decision`/
`submit_reaction` never raise and are enqueue-only; a full queue drops (counted) without
blocking the caller; a session that raises marks its form dead and the worker respawns
it against a FRESH snapshot (`snapshot()` called again) up to `max_respawns`, then the
form stays permanently dead; a reaction that arrives before its decision is a counted
skip; a reaction that arrives after its decision produces an evidence record and calls
`observe_verdict` with the EXACT summary `submit_decide` remembered (not a
`summary_from_decision_event` reconstruction); `close()` joins the worker and force-
shuts-down every client. `boot_snapshot` is tested separately as a pure function over
tmp JSONL fixtures.

Fixture values are synthetic (public repo, PRINCIPLES §12) — no owner data.
"""
from __future__ import annotations

import json
import time
from collections.abc import Iterable, Mapping
from pathlib import Path

import pytest

from life_agent.core import decisions as DEC
from life_agent.core import reactions as RX
from life_agent.membrane import categorical as CAT
from life_agent.membrane import shadow as SH
from life_agent.membrane import world as W
from life_agent.membrane.client import MembraneError
from life_agent.membrane.session import ShadowChoice

# --- test doubles: fake session, fake client, fake clock, fake session factory -----------


class _FakeClient:
    def __init__(self) -> None:
        self.shutdown_calls = 0

    def shutdown(self) -> None:
        self.shutdown_calls += 1


class _FakeSession:
    """Duck-types `MembraneSession`'s surface the shadow actually calls: `boot`,
    `decide`, `observe_verdict`, `.engine`, `.client`, `.t`. `boot_raises`/
    `decide_raises` let a test script a session that fails at a chosen point."""

    def __init__(self, form: str, *, boot_raises: bool = False, decide_raises: bool = False):
        self.form = form
        self.client = _FakeClient()
        self.engine: dict[str, object] = {}
        self._t = 0
        self.boot_raises = boot_raises
        self.decide_raises = decide_raises
        self.boot_calls: list[tuple[list[object], list[object]]] = []
        self.decide_calls: list[W.DecideSummary] = []
        self.observe_verdict_calls: list[tuple[W.DecideSummary, int]] = []

    @property
    def t(self) -> int:
        return self._t

    def boot(
        self,
        *,
        verdict_replay: Iterable[tuple[W.DecideSummary, int]] = (),
        outcome_replay: Iterable[tuple[str, W.DecideSummary, int]] = (),
    ) -> None:
        self.boot_calls.append((list(verdict_replay), list(outcome_replay)))
        if self.boot_raises:
            raise MembraneError(f"boot failed for {self.form}")
        self.engine = {"ok": True, "proto": 1, "form": self.form}

    def decide(self, s: W.DecideSummary) -> ShadowChoice:
        if self.decide_raises:
            raise MembraneError(f"decide failed for {self.form}")
        self.decide_calls.append(s)
        return ShadowChoice(action="respond", raw_internal=False, readouts={"p1": 0.7})

    def observe_verdict(self, s: W.DecideSummary, y: int) -> None:
        self.observe_verdict_calls.append((s, y))
        self._t += 1


class _FakeFactory:
    """Records how many sessions it built per form; `sessions_for[form]` is a queue of
    pre-scripted `_FakeSession`s consumed in order (falls back to a fresh healthy
    session once exhausted)."""

    def __init__(self, sessions_for: dict[str, list[_FakeSession]] | None = None) -> None:
        self.sessions_for = sessions_for or {}
        self.calls: dict[str, int] = {}
        self.built: dict[str, list[_FakeSession]] = {}

    def __call__(self, form: str) -> _FakeSession:
        self.calls[form] = self.calls.get(form, 0) + 1
        queued = self.sessions_for.get(form) or []
        session = queued.pop(0) if queued else _FakeSession(form)
        self.built.setdefault(form, []).append(session)
        return session


class _FakeClock:
    """A clock the test fully controls: `advance(s)` moves it forward; `respawn_backoff_s
    = 0` (the tests' default) means "not before time X" is trivially satisfied on the
    very next worker-loop tick, so tests don't need to call `advance` at all unless they
    want to pin the backoff itself."""

    def __init__(self, start: float = 0.0) -> None:
        self._now = start

    def __call__(self) -> float:
        return self._now

    def advance(self, s: float) -> None:
        self._now += s


def _snapshot_calls_counter() -> tuple[list[int], SH.SnapshotFn]:
    calls: list[int] = []

    def snapshot() -> SH.BootSnapshot:
        calls.append(1)
        return SH.BootSnapshot(verdict_replay=[], outcome_replay=[], n_source_records=0)

    return calls, snapshot


def _u_bar() -> Mapping[str, float]:
    return {"u_wrong": -9.0, "lambda_int": 0.1, "kappa_att": 0.02}


def _summary(**kw: object) -> W.DecideSummary:
    defaults: dict[str, object] = dict(
        n_candidates=1, leader_credence=0.9, p_none=0.05, n_obs=1,
        era_split=False, owner_scoped=False, grow_pass=False,
    )
    defaults.update(kw)
    return W.DecideSummary(**defaults)  # type: ignore[arg-type]


def _cfg(tmp_path: Path, **kw: object) -> SH.ShadowConfig:
    defaults: dict[str, object] = dict(
        command=["/x/nonexistent-govhost-binary"],  # PII-OK: synthetic placeholder path
        forms=("said@1",),
        log_path=tmp_path / "shadow.jsonl",
        queue_size=64,
        max_respawns=3,
        respawn_backoff_s=0.0,
    )
    defaults.update(kw)
    return SH.ShadowConfig(**defaults)  # type: ignore[arg-type]


def _read_records(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _n_boot_records(path: Path) -> int:
    return sum(1 for r in _read_records(path) if r.get("kind") == "boot")


def _wait_until(predicate: object, *, timeout_s: float = 2.0, poll_s: float = 0.01) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():  # type: ignore[operator]
            return True
        time.sleep(poll_s)
    return bool(predicate())  # type: ignore[operator]


# --- start(): boots off one synchronous snapshot, writes a boot record per form ----------


def test_start_boots_every_form_and_writes_a_boot_record_each(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # the re-derived wire declares ONE form; two forms side by side is a test-only shape,
    # so widen the declared set (ShadowConfig + handshake_decl both validate against it).
    monkeypatch.setattr(W, "UTILITY_FORMS", ("said@1", "said@2"))
    cfg = _cfg(tmp_path, forms=("said@1", "said@2"))
    calls, snapshot = _snapshot_calls_counter()
    factory = _FakeFactory()
    sh = SH.MembraneShadow(
        cfg, u_bar=_u_bar, snapshot=snapshot, session_factory=factory, clock=_FakeClock(),
    )
    try:
        sh.start()
        ok = _wait_until(
            lambda: all(
                sh.stats()["forms"][f]["alive"] for f in ("said@1", "said@2")  # type: ignore[index]
            )
        )
        assert ok
        records = _read_records(cfg.log_path)
        boots = [r for r in records if r["kind"] == "boot"]
        assert {b["form"] for b in boots} == {"said@1", "said@2"}
        for b in boots:
            assert b["event_type"] == "membrane-shadow"
            assert b["engine"] == {"ok": True, "proto": 1, "form": b["form"]}
            assert b["binary_sha256"] == "unknown"  # command[0] doesn't exist
            assert set(b["forms"]) == {"said@1", "said@2"}  # type: ignore[arg-type]
            assert b["respawn_count"] == 0
            expected_digest = SH.world_digest(_u_bar(), utility_form=str(b["form"]))
            assert b["world_digest"] == expected_digest
            assert b["n_source_records"] == 0  # the fixture snapshot's own value
        assert len(calls) == 1  # ONE synchronous snapshot shared by the initial boot
    finally:
        sh.close()


def test_shadow_config_rejects_an_unknown_form_at_construction(tmp_path: Path) -> None:
    """M1: `config.membrane_utility_forms`'s docstring and the register both CLAIMED an
    unknown form fails loudly at construction, before serving. It didn't — a plain frozen
    dataclass took anything, and the form died much later and much quieter, on the worker,
    into a permanently dead form inside a supervisor that still looked healthy. A stated
    safety property has to be the code's."""
    with pytest.raises(ValueError, match="unknown membrane utility form"):
        _cfg(tmp_path, forms=("said@1", "table@2"))
    with pytest.raises(ValueError, match="must not be empty"):
        _cfg(tmp_path, forms=())
    _cfg(tmp_path, forms=W.UTILITY_FORMS)  # every declared form is accepted


def test_boot_record_persists_the_real_u_bar_not_just_its_digest(tmp_path: Path) -> None:
    """C3: the world_digest pins WHICH world was declared but cannot be inverted back to the
    utility numbers, so an offline report that had only the digest fell back to
    world.utility_rows' DEFAULTS (u_wrong=-9.0) — and published a respond-reachability claim
    that was an artifact of that constant, while the live posterior sat near -5.9. The boot
    record now carries the u_bar itself (seven scalar means; no PII)."""
    cfg = _cfg(tmp_path)
    sh = SH.MembraneShadow(
        cfg, u_bar=_u_bar, snapshot=_snapshot_calls_counter()[1],
        session_factory=_FakeFactory(), clock=_FakeClock(),
    )
    try:
        sh.start()
        assert _wait_until(lambda: _n_boot_records(cfg.log_path) >= 1)
        boots = [r for r in _read_records(cfg.log_path) if r["kind"] == "boot"]
        boot = boots[0]
        assert boot["u_bar"] == _u_bar()
        # and it is the SAME u_bar the declared world was digested under
        assert boot["world_digest"] == SH.world_digest(_u_bar(), utility_form="said@1")
    finally:
        sh.close()


def test_boot_record_persists_the_snapshots_n_source_records(tmp_path: Path) -> None:
    # Task 7 review, fix 1: the boot record must carry the REAL warm-evidence count the
    # boot snapshot found — an offline report has no other way to recover it (the field
    # only otherwise reaches the live stats()["snapshot_records"]).
    cfg = _cfg(tmp_path)
    factory = _FakeFactory()

    def snapshot() -> SH.BootSnapshot:
        return SH.BootSnapshot(verdict_replay=[], outcome_replay=[], n_source_records=250)

    sh = SH.MembraneShadow(
        cfg, u_bar=_u_bar, snapshot=snapshot, session_factory=factory, clock=_FakeClock(),
    )
    try:
        sh.start()
        # Wait on the boot RECORD itself, not the `alive` flag: `state.session` (which
        # drives `alive`) is set a moment before `_write_boot_record` runs, so polling
        # `alive` then immediately reading the log has a race window.
        assert _wait_until(lambda: _n_boot_records(cfg.log_path) >= 1)
        records = _read_records(cfg.log_path)
        boots = [r for r in records if r["kind"] == "boot"]
        assert len(boots) == 1
        assert boots[0]["n_source_records"] == 250
    finally:
        sh.close()


def test_respawn_boot_record_reflects_the_fresh_snapshots_n_source_records(
    tmp_path: Path,
) -> None:
    # Closes the same test gap as the verdict/outcome-replay respawn test: the boot
    # record's n_source_records must come from the FRESH (respawn-time) snapshot, not
    # the stale (initial-boot-time) one an implementation could accidentally re-use.
    cfg = _cfg(tmp_path, max_respawns=1, respawn_backoff_s=0.0)
    stale = SH.BootSnapshot(verdict_replay=[], outcome_replay=[], n_source_records=0)
    fresh = SH.BootSnapshot(verdict_replay=[], outcome_replay=[], n_source_records=99)
    remaining = iter([stale, fresh])

    def snapshot() -> SH.BootSnapshot:
        return next(remaining, fresh)

    dying = _FakeSession("said@1", decide_raises=True)
    healthy = _FakeSession("said@1")
    factory = _FakeFactory({"said@1": [dying, healthy]})
    sh = SH.MembraneShadow(
        cfg, u_bar=_u_bar, snapshot=snapshot, session_factory=factory, clock=_FakeClock(),
    )
    try:
        sh.start()
        assert _wait_until(lambda: sh.stats()["forms"]["said@1"]["alive"])  # type: ignore[index]
        sh.submit_decide("q-001", {"candidates": []}, {"credences": [], "effector": "report"})
        assert _wait_until(lambda: healthy.boot_calls != [])
        # Wait on the SECOND boot record's own arrival, not just `healthy.boot_calls`
        # (which is set inside `boot()`, still slightly before `_write_boot_record` runs).
        assert _wait_until(lambda: _n_boot_records(cfg.log_path) >= 2)
        records = _read_records(cfg.log_path)
        boots = [r for r in records if r["kind"] == "boot"]
        assert len(boots) == 2
        assert boots[0]["n_source_records"] == 0    # the initial (stale) boot
        assert boots[1]["n_source_records"] == 99   # the respawn's fresh snapshot
    finally:
        sh.close()


# --- kind:"stats" rows: periodic + on-close persistence of the live counters --------------


def test_periodic_stats_record_written_every_stats_every_processed_items(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(SH, "_STATS_EVERY", 3)
    cfg = _cfg(tmp_path)
    _calls, snapshot = _snapshot_calls_counter()
    session = _FakeSession("said@1")
    factory = _FakeFactory({"said@1": [session]})
    sh = SH.MembraneShadow(
        cfg, u_bar=_u_bar, snapshot=snapshot, session_factory=factory, clock=_FakeClock(),
    )
    try:
        sh.start()
        assert _wait_until(lambda: sh.stats()["forms"]["said@1"]["alive"])  # type: ignore[index]
        for i in range(3):
            sh.submit_decide(f"q-{i}", {"candidates": []}, {"credences": [], "effector": "report"})
        assert _wait_until(lambda: sh.stats()["forms"]["said@1"]["ticks"] >= 3)  # type: ignore[index]

        def has_stats_row() -> bool:
            return any(r["kind"] == "stats" for r in _read_records(cfg.log_path))

        assert _wait_until(has_stats_row)
        records = _read_records(cfg.log_path)
        stats_rows = [r for r in records if r["kind"] == "stats"]
        assert len(stats_rows) >= 1
        row = stats_rows[0]
        assert row["event_type"] == "membrane-shadow"
        assert "ts" in row
        # the FULL stats() payload, persisted verbatim.
        assert set(row) >= {
            "forms", "drops", "skips", "submit_errors", "queue_depth", "snapshot_records",
        }
        assert row["forms"]["said@1"]["ticks"] >= 3
    finally:
        sh.close()


def test_no_stats_row_written_before_stats_every_items_processed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(SH, "_STATS_EVERY", 100)
    cfg = _cfg(tmp_path)
    _calls, snapshot = _snapshot_calls_counter()
    session = _FakeSession("said@1")
    factory = _FakeFactory({"said@1": [session]})
    sh = SH.MembraneShadow(
        cfg, u_bar=_u_bar, snapshot=snapshot, session_factory=factory, clock=_FakeClock(),
    )
    try:
        sh.start()
        assert _wait_until(lambda: sh.stats()["forms"]["said@1"]["alive"])  # type: ignore[index]
        sh.submit_decide("q-1", {"candidates": []}, {"credences": [], "effector": "report"})
        assert _wait_until(lambda: sh.stats()["forms"]["said@1"]["ticks"] >= 1)  # type: ignore[index]
        records = _read_records(cfg.log_path)
        assert not any(r["kind"] == "stats" for r in records)  # below threshold: none yet
    finally:
        sh.close()  # close() itself writes one -- checked by the dedicated test below


def test_close_writes_a_final_stats_record(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    _calls, snapshot = _snapshot_calls_counter()
    session = _FakeSession("said@1")
    factory = _FakeFactory({"said@1": [session]})
    sh = SH.MembraneShadow(
        cfg, u_bar=_u_bar, snapshot=snapshot, session_factory=factory, clock=_FakeClock(),
    )
    sh.start()
    assert _wait_until(lambda: sh.stats()["forms"]["said@1"]["alive"])  # type: ignore[index]
    sh.submit_decide("q-1", {"candidates": []}, {"credences": [], "effector": "report"})
    assert _wait_until(lambda: sh.stats()["forms"]["said@1"]["ticks"] >= 1)  # type: ignore[index]
    sh.close()
    records = _read_records(cfg.log_path)
    stats_rows = [r for r in records if r["kind"] == "stats"]
    assert len(stats_rows) >= 1
    assert stats_rows[-1]["forms"]["said@1"]["ticks"] >= 1


def test_close_before_start_writes_a_stats_record_without_raising(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    _calls, snapshot = _snapshot_calls_counter()
    sh = SH.MembraneShadow(cfg, u_bar=_u_bar, snapshot=snapshot, session_factory=_FakeFactory())
    sh.close()  # never started -- must not raise
    records = _read_records(cfg.log_path)
    assert any(r["kind"] == "stats" for r in records)


def test_stats_record_write_failure_is_fail_open(tmp_path: Path) -> None:
    # log_path points at a directory -> every append (including the stats row) raises;
    # the worker must survive and keep draining, same as every other record kind.
    cfg = _cfg(tmp_path, log_path=tmp_path)
    monkeypatch_value = 2
    import life_agent.membrane.shadow as shadow_mod
    orig = shadow_mod._STATS_EVERY
    shadow_mod._STATS_EVERY = monkeypatch_value
    try:
        _calls, snapshot = _snapshot_calls_counter()
        factory = _FakeFactory()
        sh = SH.MembraneShadow(
            cfg, u_bar=_u_bar, snapshot=snapshot, session_factory=factory, clock=_FakeClock(),
        )
        try:
            sh.start()
            assert _wait_until(lambda: sh.stats()["forms"]["said@1"]["alive"])  # type: ignore[index]
            for i in range(monkeypatch_value):
                sh.submit_decide(
                    f"q-{i}", {"candidates": []}, {"credences": [], "effector": "report"},
                )
            assert _wait_until(
                lambda: sh.stats()["forms"]["said@1"]["ticks"] >= monkeypatch_value  # type: ignore[index]
            )
            assert sh.stats()["drops"] >= 1
        finally:
            sh.close()
    finally:
        shadow_mod._STATS_EVERY = orig


# --- submit_decide -> worker drains -> decide record -------------------------------------


def test_decide_submit_is_drained_into_a_decide_record(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    _calls, snapshot = _snapshot_calls_counter()
    factory = _FakeFactory()
    sh = SH.MembraneShadow(cfg, u_bar=_u_bar, snapshot=snapshot, session_factory=factory)
    try:
        sh.start()
        assert _wait_until(lambda: sh.stats()["forms"]["said@1"]["alive"])  # type: ignore[index]
        payload = {"candidates": ["a"], "observations": [1, 2], "era_split": True}
        dec = {"credences": [0.8], "p_none": 0.1, "effector": "report"}
        sh.submit_decide("q-001", payload, dec)
        assert _wait_until(lambda: sh.stats()["forms"]["said@1"]["ticks"] >= 1)  # type: ignore[index]
        records = _read_records(cfg.log_path)
        decides = [r for r in records if r["kind"] == "decide"]
        assert len(decides) == 1
        row = decides[0]
        assert row["event_type"] == "membrane-shadow"
        assert row["question_id"] == "q-001"
        assert row["form"] == "said@1"
        assert row["action"] == "respond"
        assert row["raw_internal"] is False
        assert row["real_effector"] == "report"
        assert row["readouts"] == {"p1": 0.7}
        expected_summary = W.summary_from_payload(payload, dec)
        assert row["summary"] == {
            "n_candidates": expected_summary.n_candidates,
            "leader_credence": expected_summary.leader_credence,
            "p_none": expected_summary.p_none,
            "n_obs": expected_summary.n_obs,
            "era_split": expected_summary.era_split,
            "owner_scoped": expected_summary.owner_scoped,
            "grow_pass": expected_summary.grow_pass,
        }
        assert isinstance(row["latency_ms"], (int, float))
        assert row["t"] == 0
    finally:
        sh.close()


# --- full queue -> drop counted, submit returns silently ---------------------------------


def test_full_queue_drops_and_counts_without_raising(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path, queue_size=1)
    _calls, snapshot = _snapshot_calls_counter()
    factory = _FakeFactory()
    # Never call start(): nothing drains the queue, so the second submit overflows it.
    sh = SH.MembraneShadow(cfg, u_bar=_u_bar, snapshot=snapshot, session_factory=factory)
    sh.submit_decide("q-001", {"candidates": []}, {"credences": [], "effector": "report"})
    sh.submit_decide("q-002", {"candidates": []}, {"credences": [], "effector": "report"})
    stats = sh.stats()
    assert stats["drops"] == 1
    assert stats["queue_depth"] == 1


# --- a session that raises on boot: dead, respawns against a FRESH snapshot up to max -----


def test_session_that_always_fails_to_boot_respawns_up_to_max_then_stays_dead(
    tmp_path: Path,
) -> None:
    cfg = _cfg(tmp_path, max_respawns=3, respawn_backoff_s=0.0)
    calls, snapshot = _snapshot_calls_counter()
    factory = _FakeFactory({"said@1": [_FakeSession("said@1", boot_raises=True)]})
    # every subsequent respawn attempt also gets a boot_raises=True session (the
    # factory's fallback builds a plain fresh() session otherwise) — script enough.
    factory.sessions_for["said@1"] = [
        _FakeSession("said@1", boot_raises=True) for _ in range(6)
    ]
    sh = SH.MembraneShadow(
        cfg, u_bar=_u_bar, snapshot=snapshot, session_factory=factory, clock=_FakeClock(),
    )
    try:
        sh.start()
        assert _wait_until(
            lambda: sh.stats()["forms"]["said@1"]["respawns"] == cfg.max_respawns  # type: ignore[index]
        )
        stats = sh.stats()
        assert stats["forms"]["said@1"]["alive"] is False  # type: ignore[index]
        assert stats["forms"]["said@1"]["respawns"] == 3  # type: ignore[index]
        # 1 initial snapshot (start()) + one fresh snapshot per respawn attempt (3)
        assert len(calls) == cfg.max_respawns + 1
        records = _read_records(cfg.log_path)
        respawn_rows = [r for r in records if r["kind"] == "respawn"]
        # one "respawn" record per DEATH: the initial boot failure (free — respawn_count
        # stays 0) plus one per respawn attempt (3), the last of which is permanent.
        assert len(respawn_rows) == cfg.max_respawns + 1
        assert respawn_rows[-1]["permanent"] is True
        assert all(r["permanent"] is False for r in respawn_rows[:-1])
    finally:
        sh.close()


def test_session_that_raises_during_a_live_tick_dies_and_respawns_against_fresh_snapshot(
    tmp_path: Path,
) -> None:
    # form boots fine, then the FIRST decide() raises; max_respawns=1 and the respawn's
    # own boot also fails -> exactly one respawn attempt, then permanently dead. This
    # exercises the live-tick death path (not the initial-boot-failure path above).
    cfg = _cfg(tmp_path, max_respawns=1, respawn_backoff_s=0.0)
    calls, snapshot = _snapshot_calls_counter()
    dying = _FakeSession("said@1", decide_raises=True)
    factory = _FakeFactory({"said@1": [dying, _FakeSession("said@1", boot_raises=True)]})
    sh = SH.MembraneShadow(
        cfg, u_bar=_u_bar, snapshot=snapshot, session_factory=factory, clock=_FakeClock(),
    )
    try:
        sh.start()
        assert _wait_until(lambda: sh.stats()["forms"]["said@1"]["alive"])  # type: ignore[index]
        sh.submit_decide("q-001", {"candidates": []}, {"credences": [], "effector": "report"})
        assert _wait_until(
            lambda: sh.stats()["forms"]["said@1"]["respawns"] == 1  # type: ignore[index]
        )
        stats = sh.stats()
        assert stats["forms"]["said@1"]["alive"] is False  # type: ignore[index]
        assert factory.calls["said@1"] == 2  # initial boot + the one respawn attempt
        assert len(calls) == 2  # 1 initial (start) + 1 fresh (the respawn)
    finally:
        sh.close()


def test_a_dead_form_recovers_when_its_respawn_succeeds(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path, max_respawns=2, respawn_backoff_s=0.0)
    _calls, snapshot = _snapshot_calls_counter()
    dying = _FakeSession("said@1", decide_raises=True)
    healthy = _FakeSession("said@1")
    factory = _FakeFactory({"said@1": [dying, healthy]})
    sh = SH.MembraneShadow(
        cfg, u_bar=_u_bar, snapshot=snapshot, session_factory=factory, clock=_FakeClock(),
    )
    try:
        sh.start()
        assert _wait_until(lambda: sh.stats()["forms"]["said@1"]["alive"])  # type: ignore[index]
        sh.submit_decide("q-001", {"candidates": []}, {"credences": [], "effector": "report"})
        # dies, then the respawn (with `healthy`) brings it back alive. Wait on the
        # factory having actually built the SECOND session, not merely on "alive" —
        # `dying` is also alive right up until the queued item kills it, so polling
        # "alive" alone could spuriously pass before the death/respawn cycle even ran.
        assert _wait_until(lambda: factory.calls.get("said@1", 0) == 2)
        assert _wait_until(lambda: sh.stats()["forms"]["said@1"]["alive"])  # type: ignore[index]
        # respawn_count counts every ATTEMPT against the budget, success or failure (the
        # Task 4 review's C2 fix — see shadow.py's `_boot_form`/`_attempt_respawn`
        # docstring), so a SUCCESSFUL respawn still consumes exactly 1.
        assert sh.stats()["forms"]["said@1"]["respawns"] == 1  # type: ignore[index]
        sh.submit_decide("q-002", {"candidates": []}, {"credences": [], "effector": "report"})
        assert _wait_until(lambda: len(healthy.decide_calls) == 1)
    finally:
        sh.close()


# --- C1: a dying session's client is shut down, never leaked ------------------------------


def test_a_dying_sessions_client_is_shut_down_when_its_form_dies(tmp_path: Path) -> None:
    # the live-tick death path: `state.session` IS the dying session at the moment
    # `_handle_death` runs, so its client must be shut down before being nulled out —
    # otherwise a read-timeout wedge or a crashed driver leaks the subprocess forever
    # (Popen's finalizer does not kill the child).
    cfg = _cfg(tmp_path, max_respawns=0, respawn_backoff_s=0.0)
    _calls, snapshot = _snapshot_calls_counter()
    dying = _FakeSession("said@1", decide_raises=True)
    factory = _FakeFactory({"said@1": [dying]})
    sh = SH.MembraneShadow(
        cfg, u_bar=_u_bar, snapshot=snapshot, session_factory=factory, clock=_FakeClock(),
    )
    try:
        sh.start()
        assert _wait_until(lambda: sh.stats()["forms"]["said@1"]["alive"])  # type: ignore[index]
        sh.submit_decide("q-1", {"candidates": []}, {"credences": [], "effector": "report"})
        assert _wait_until(lambda: not sh.stats()["forms"]["said@1"]["alive"])  # type: ignore[index]
        assert dying.client.shutdown_calls == 1
    finally:
        sh.close()


def test_a_session_whose_boot_fails_after_spawning_is_still_shut_down(tmp_path: Path) -> None:
    # a DIFFERENT leak path: `session_factory()` returns a live client, but `boot()`
    # itself raises (e.g. a handshake refusal). `state.session` is never assigned in this
    # case, so `_handle_death`'s shutdown of `state.session` is a no-op — the leaked
    # client is the LOCAL `session` variable in `_boot_form`, which must be shut down at
    # the point of failure.
    cfg = _cfg(tmp_path, max_respawns=0, respawn_backoff_s=0.0)
    _calls, snapshot = _snapshot_calls_counter()
    failing = _FakeSession("said@1", boot_raises=True)
    factory = _FakeFactory({"said@1": [failing]})
    sh = SH.MembraneShadow(
        cfg, u_bar=_u_bar, snapshot=snapshot, session_factory=factory, clock=_FakeClock(),
    )
    try:
        sh.start()
        assert _wait_until(lambda: not sh.stats()["forms"]["said@1"]["alive"])  # type: ignore[index]
        assert _wait_until(lambda: failing.client.shutdown_calls == 1)
    finally:
        sh.close()


# --- C2: the respawn budget bounds TOTAL attempts, not just failed boots ------------------


def test_a_form_that_boots_ok_but_dies_on_every_tick_exhausts_the_full_respawn_budget(
    tmp_path: Path,
) -> None:
    # the C2 motivating bug: a govhost that handshakes fine but rejects every tick
    # payload used to respawn FOREVER (only failed *boots* counted against the budget).
    # Each incarnation here boots cleanly and only dies on its first `decide()`.
    cfg = _cfg(tmp_path, max_respawns=3, respawn_backoff_s=0.0)
    _calls, snapshot = _snapshot_calls_counter()
    sessions = [_FakeSession("said@1", decide_raises=True) for _ in range(4)]
    factory = _FakeFactory({"said@1": list(sessions)})
    sh = SH.MembraneShadow(
        cfg, u_bar=_u_bar, snapshot=snapshot, session_factory=factory, clock=_FakeClock(),
    )
    try:
        sh.start()
        assert _wait_until(lambda: sh.stats()["forms"]["said@1"]["alive"])  # type: ignore[index]
        for i in range(4):
            sh.submit_decide(f"q-{i}", {"candidates": []}, {"credences": [], "effector": "report"})
            if i < 3:  # a respawn follows every death except the budget-exhausting last one
                assert _wait_until(lambda i=i: factory.calls.get("said@1", 0) == i + 2)
                assert _wait_until(lambda: sh.stats()["forms"]["said@1"]["alive"])  # type: ignore[index]
        assert _wait_until(lambda: sh.stats()["forms"]["said@1"]["alive"] is False)  # type: ignore[index]
        stats = sh.stats()
        assert stats["forms"]["said@1"]["respawns"] == 3  # type: ignore[index]
        assert factory.calls["said@1"] == 4  # 1 free initial boot + 3 respawn attempts
        # the budget is truly exhausted: one more submit builds no further session.
        sh.submit_decide("q-extra", {"candidates": []}, {"credences": [], "effector": "report"})
        assert not _wait_until(lambda: factory.calls["said@1"] > 4, timeout_s=0.3)
    finally:
        sh.close()


def test_respawn_boots_the_new_session_off_the_freshly_returned_snapshot_content(
    tmp_path: Path,
) -> None:
    # closes the test gap the review flagged: the old test only counted `snapshot()`
    # calls, so an implementation that called `snapshot()` again but still passed the
    # STALE boot-time snapshot into `boot()` would have passed too. Here the two
    # snapshots carry distinguishable CONTENT, and we assert the respawned session's
    # `boot()` received the fresh one, not the stale one.
    cfg = _cfg(tmp_path, max_respawns=1, respawn_backoff_s=0.0)
    stale = SH.BootSnapshot(verdict_replay=[], outcome_replay=[], n_source_records=0)
    fresh_summary = _summary(n_candidates=2, leader_credence=0.5)
    fresh = SH.BootSnapshot(
        verdict_replay=[(fresh_summary, 1)], outcome_replay=[], n_source_records=99,
    )
    remaining = iter([stale, fresh])

    def snapshot() -> SH.BootSnapshot:
        return next(remaining, fresh)

    dying = _FakeSession("said@1", decide_raises=True)
    healthy = _FakeSession("said@1")
    factory = _FakeFactory({"said@1": [dying, healthy]})
    sh = SH.MembraneShadow(
        cfg, u_bar=_u_bar, snapshot=snapshot, session_factory=factory, clock=_FakeClock(),
    )
    try:
        sh.start()
        assert _wait_until(lambda: sh.stats()["forms"]["said@1"]["alive"])  # type: ignore[index]
        assert dying.boot_calls[0] == ([], [])  # the STALE initial snapshot's content
        sh.submit_decide("q-001", {"candidates": []}, {"credences": [], "effector": "report"})
        assert _wait_until(lambda: healthy.boot_calls != [])
        got_verdict_replay, got_outcome_replay = healthy.boot_calls[0]
        assert got_verdict_replay == fresh.verdict_replay
        assert got_outcome_replay == fresh.outcome_replay
    finally:
        sh.close()


# --- I3: no exception on the worker thread can ever kill it -------------------------------


def test_a_raising_u_bar_does_not_kill_the_worker_and_the_boot_record_failure_is_counted(
    tmp_path: Path,
) -> None:
    cfg = _cfg(tmp_path)
    _calls, snapshot = _snapshot_calls_counter()
    factory = _FakeFactory()

    def bad_u_bar() -> Mapping[str, float]:
        raise RuntimeError("u_bar unavailable")

    sh = SH.MembraneShadow(
        cfg, u_bar=bad_u_bar, snapshot=snapshot, session_factory=factory, clock=_FakeClock(),
    )
    try:
        sh.start()
        # the worker survived `_write_boot_record`'s `u_bar()` call raising: the form is
        # alive (the session itself booted fine — only the boot RECORD write failed).
        assert _wait_until(lambda: sh.stats()["forms"]["said@1"]["alive"])  # type: ignore[index]
        # ... and it kept draining afterward — a decide submitted post-boot still reaches
        # the (unkilled) worker.
        sh.submit_decide("q-1", {"candidates": []}, {"credences": [], "effector": "report"})
        assert _wait_until(lambda: sh.stats()["forms"]["said@1"]["ticks"] >= 1)  # type: ignore[index]
        assert sh.stats()["drops"] >= 1  # the failed boot-record write, visible
        records = _read_records(cfg.log_path)
        assert not any(r["kind"] == "boot" for r in records)  # it never got written
    finally:
        sh.close()


def test_a_log_path_that_cannot_be_written_is_fail_open_and_the_worker_keeps_draining(
    tmp_path: Path,
) -> None:
    # log_path points at a directory (not a file) -> every append raises. The worker
    # must survive both the failed boot-record write AND the failed decide-record write.
    cfg = _cfg(tmp_path, log_path=tmp_path)
    _calls, snapshot = _snapshot_calls_counter()
    factory = _FakeFactory()
    sh = SH.MembraneShadow(
        cfg, u_bar=_u_bar, snapshot=snapshot, session_factory=factory, clock=_FakeClock(),
    )
    try:
        sh.start()
        assert _wait_until(lambda: sh.stats()["forms"]["said@1"]["alive"])  # type: ignore[index]
        sh.submit_decide("q-1", {"candidates": []}, {"credences": [], "effector": "report"})
        assert _wait_until(lambda: sh.stats()["forms"]["said@1"]["ticks"] >= 1)  # type: ignore[index]
        assert sh.stats()["drops"] >= 1
    finally:
        sh.close()


def test_one_dead_form_does_not_stop_another_form_from_ticking(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(W, "UTILITY_FORMS", ("said@1", "said@2"))
    cfg = _cfg(tmp_path, forms=("said@1", "said@2"), max_respawns=0, respawn_backoff_s=0.0)
    _calls, snapshot = _snapshot_calls_counter()
    dead = _FakeSession("said@1", boot_raises=True)
    factory = _FakeFactory({"said@1": [dead]})  # said@2 falls back to a healthy default
    sh = SH.MembraneShadow(
        cfg, u_bar=_u_bar, snapshot=snapshot, session_factory=factory, clock=_FakeClock(),
    )
    try:
        sh.start()
        assert _wait_until(lambda: not sh.stats()["forms"]["said@1"]["alive"])  # type: ignore[index]
        assert _wait_until(lambda: sh.stats()["forms"]["said@2"]["alive"])  # type: ignore[index]
        sh.submit_decide("q-1", {"candidates": []}, {"credences": [], "effector": "report"})
        assert _wait_until(lambda: sh.stats()["forms"]["said@2"]["ticks"] >= 1)  # type: ignore[index]
        assert sh.stats()["forms"]["said@1"]["ticks"] == 0  # type: ignore[index]
    finally:
        sh.close()


# --- I4: a dead-form drop is counted, not silently discarded ------------------------------


def test_dead_form_drops_are_counted(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path, max_respawns=0, respawn_backoff_s=0.0)
    _calls, snapshot = _snapshot_calls_counter()
    dying = _FakeSession("said@1", boot_raises=True)
    factory = _FakeFactory({"said@1": [dying]})
    sh = SH.MembraneShadow(
        cfg, u_bar=_u_bar, snapshot=snapshot, session_factory=factory, clock=_FakeClock(),
    )
    try:
        sh.start()
        assert _wait_until(lambda: not sh.stats()["forms"]["said@1"]["alive"])  # type: ignore[index]
        sh.submit_decide("q-1", {"candidates": []}, {"credences": [], "effector": "report"})
        sh.submit_decide("q-2", {"candidates": []}, {"credences": [], "effector": "report"})
        assert _wait_until(lambda: sh.stats()["forms"]["said@1"]["dead_drops"] >= 2)  # type: ignore[index]
    finally:
        sh.close()


# --- I5: the two submit-time maps are bounded, not unbounded daemon memory ----------------


def test_live_summaries_and_bindings_are_bounded(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    _calls, snapshot = _snapshot_calls_counter()
    sh = SH.MembraneShadow(cfg, u_bar=_u_bar, snapshot=snapshot, session_factory=_FakeFactory())
    cap = SH._MAX_TRACKED_ENTRIES
    overflow = 10
    for i in range(cap + overflow):
        sh.submit_decide(f"q-{i}", {"candidates": []}, {"credences": [], "effector": "report"})
        sh.submit_decision(f"d-{i}", f"q-{i}", {"chosen_action": "report"})
    assert len(sh._live_summaries) == cap
    assert len(sh._bindings) == cap
    for i in range(overflow):  # the oldest `overflow` entries were evicted
        assert f"q-{i}" not in sh._live_summaries
        assert f"d-{i}" not in sh._bindings
    for i in range(cap + overflow - overflow, cap + overflow):  # the newest survive
        assert f"q-{i}" in sh._live_summaries
        assert f"d-{i}" in sh._bindings


# --- double start() is guarded, not a silent orphan ----------------------------------------


def test_double_start_is_guarded(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    _calls, snapshot = _snapshot_calls_counter()
    sh = SH.MembraneShadow(
        cfg, u_bar=_u_bar, snapshot=snapshot, session_factory=_FakeFactory(), clock=_FakeClock(),
    )
    try:
        sh.start()
        with pytest.raises(RuntimeError):
            sh.start()
    finally:
        sh.close()


# --- reaction before its decision: a counted skip, never raises --------------------------


def test_reaction_before_its_decision_is_a_counted_skip(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    _calls, snapshot = _snapshot_calls_counter()
    factory = _FakeFactory()
    sh = SH.MembraneShadow(cfg, u_bar=_u_bar, snapshot=snapshot, session_factory=factory)
    sh.submit_reaction("dec-unknown", "good")
    assert sh.stats()["skips"] == 1


def test_reaction_with_no_verdict_y_mapping_is_a_counted_skip(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    _calls, snapshot = _snapshot_calls_counter()
    factory = _FakeFactory()
    sh = SH.MembraneShadow(cfg, u_bar=_u_bar, snapshot=snapshot, session_factory=factory)
    sh.submit_decision("dec-1", "q-1", {"chosen_action": "ask_clarify"})
    sh.submit_reaction("dec-1", "good")  # (ask_clarify, good) is outside verdict_y's table
    assert sh.stats()["skips"] == 1


# --- reaction after its decision: evidence row + observe_verdict w/ the SAME summary -----


def test_reaction_after_decision_feeds_the_remembered_live_summary_not_the_fallback(
    tmp_path: Path,
) -> None:
    cfg = _cfg(tmp_path)
    _calls, snapshot = _snapshot_calls_counter()
    session = _FakeSession("said@1")
    factory = _FakeFactory({"said@1": [session]})
    sh = SH.MembraneShadow(
        cfg, u_bar=_u_bar, snapshot=snapshot, session_factory=factory, clock=_FakeClock(),
    )
    try:
        sh.start()
        assert _wait_until(lambda: sh.stats()["forms"]["said@1"]["alive"])  # type: ignore[index]
        payload = {"candidates": ["a", "b"], "observations": [1], "owner_scoped": True}
        dec = {"credences": [0.6, 0.3], "p_none": 0.2, "effector": "report"}
        live_summary = W.summary_from_payload(payload, dec)
        # the decision-event fallback would reduce to a DIFFERENT summary (0 candidates,
        # no p_none) — proves observe_verdict used the remembered live one, not this.
        fallback_event = {"chosen_action": "report", "posterior_summary": {}}
        fallback_summary = W.summary_from_decision_event(fallback_event)
        assert fallback_summary != live_summary

        sh.submit_decide("q-42", payload, dec)
        sh.submit_decision("dec-42", "q-42", fallback_event)
        sh.submit_reaction("dec-42", "good")  # (report, good) -> y=1

        assert _wait_until(lambda: len(session.observe_verdict_calls) == 1)
        got_summary, got_y = session.observe_verdict_calls[0]
        assert got_summary == live_summary
        assert got_y == 1

        records = _read_records(cfg.log_path)
        evidence = [r for r in records if r["kind"] == "evidence"]
        assert len(evidence) == 1
        assert evidence[0]["stream"] == "verdict"
        assert evidence[0]["decision_id"] == "dec-42"
        assert evidence[0]["y"] == 1
        assert evidence[0]["form"] == "said@1"
        assert evidence[0]["t"] == 0  # the t sent on the wire, pre-increment
    finally:
        sh.close()


def test_reaction_falls_back_to_decision_event_summary_when_no_live_summary_was_seen(
    tmp_path: Path,
) -> None:
    cfg = _cfg(tmp_path)
    _calls, snapshot = _snapshot_calls_counter()
    session = _FakeSession("said@1")
    factory = _FakeFactory({"said@1": [session]})
    sh = SH.MembraneShadow(
        cfg, u_bar=_u_bar, snapshot=snapshot, session_factory=factory, clock=_FakeClock(),
    )
    try:
        sh.start()
        assert _wait_until(lambda: sh.stats()["forms"]["said@1"]["alive"])  # type: ignore[index]
        event = {"chosen_action": "abstain", "posterior_summary": {"credences": [0.4]}}
        sh.submit_decision("dec-99", "q-never-decided", event)
        sh.submit_reaction("dec-99", "bad")  # (abstain, bad) -> y=1
        assert _wait_until(lambda: len(session.observe_verdict_calls) == 1)
        got_summary, got_y = session.observe_verdict_calls[0]
        assert got_summary == W.summary_from_decision_event(event)
        assert got_y == 1
    finally:
        sh.close()


# --- close(): joins the worker, force-shuts-down every client ----------------------------


def test_close_joins_worker_and_shuts_down_every_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(W, "UTILITY_FORMS", ("said@1", "said@2"))
    cfg = _cfg(tmp_path, forms=("said@1", "said@2"))
    _calls, snapshot = _snapshot_calls_counter()
    factory = _FakeFactory()
    sh = SH.MembraneShadow(cfg, u_bar=_u_bar, snapshot=snapshot, session_factory=factory)
    sh.start()
    assert _wait_until(
        lambda: all(sh.stats()["forms"][f]["alive"] for f in ("said@1", "said@2"))  # type: ignore[index]
    )
    worker = sh._worker  # white-box: confirm the worker thread actually stops
    assert worker is not None
    sh.close()
    assert not worker.is_alive()
    for sessions in factory.built.values():
        for s in sessions:
            assert s.client.shutdown_calls == 1


def test_close_marks_every_form_dead_in_stats(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(W, "UTILITY_FORMS", ("said@1", "said@2"))
    # Review finding (Task 4 -> Task 5): close() shut down every client but never nulled
    # `state.session`, so `stats()["forms"][f]["alive"]` stayed True after close() — a
    # caller (e.g. GET /ready) reading stats() post-close would be told a dead shadow was
    # still alive.
    cfg = _cfg(tmp_path, forms=("said@1", "said@2"))
    _calls, snapshot = _snapshot_calls_counter()
    factory = _FakeFactory()
    sh = SH.MembraneShadow(cfg, u_bar=_u_bar, snapshot=snapshot, session_factory=factory)
    sh.start()
    assert _wait_until(
        lambda: all(sh.stats()["forms"][f]["alive"] for f in ("said@1", "said@2"))  # type: ignore[index]
    )
    sh.close()
    stats = sh.stats()
    assert stats["forms"]["said@1"]["alive"] is False  # type: ignore[index]
    assert stats["forms"]["said@2"]["alive"] is False  # type: ignore[index]


def test_close_is_safe_before_start(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    _calls, snapshot = _snapshot_calls_counter()
    sh = SH.MembraneShadow(cfg, u_bar=_u_bar, snapshot=snapshot, session_factory=_FakeFactory())
    sh.close()  # never started -> must not raise


# --- submit_* never raise, even on garbage input ------------------------------------------


def test_submit_methods_never_raise_on_malformed_input(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    _calls, snapshot = _snapshot_calls_counter()
    sh = SH.MembraneShadow(cfg, u_bar=_u_bar, snapshot=snapshot, session_factory=_FakeFactory())
    sh.submit_decide("q", None, None)  # type: ignore[arg-type]
    sh.submit_decision("d", "q", None)  # type: ignore[arg-type]
    sh.submit_reaction("d", "not-a-real-valence")
    # `submit_decide(None, None)` blows up inside `summary_from_payload` (`None.get(...)`)
    # — a genuine submit-path exception, now counted separately from a full-queue drop
    # (the module docstring's own claim used to be false here — see the Task 4 review).
    assert sh.stats()["submit_errors"] >= 1


# --- stats() shape --------------------------------------------------------------------


def test_stats_shape(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path, forms=("said@1",))
    _calls, snapshot = _snapshot_calls_counter()
    sh = SH.MembraneShadow(cfg, u_bar=_u_bar, snapshot=snapshot, session_factory=_FakeFactory())
    stats = sh.stats()
    assert set(stats) == {
        "forms", "drops", "skips", "submit_errors", "queue_depth", "snapshot_records",
    }
    assert set(stats["forms"]) == {"said@1"}  # type: ignore[arg-type]
    assert set(stats["forms"]["said@1"]) == {  # type: ignore[index]
        "alive", "respawns", "ticks", "dead_drops",
    }


# --- boot_snapshot(): pure function over tmp JSONL fixtures -------------------------------


def _decision(
    decision_id: str, question_id: str, chosen_action: str, *, n_obs: int = 1,
) -> DEC.DecisionEvent:
    return DEC.DecisionEvent(
        tx_time="t", run_id="run-1", question_id=question_id, family="lookup",
        action_set=("report", "hedge", "ask_clarify", "abstain", "report_scoped"),
        posterior_summary={"credences": [0.9], "p_none": 0.1, "n_obs": n_obs},
        utility_fold_version="fv1", chosen_action=chosen_action, predicted_eu=0.5,
        decision_id=decision_id,
    )


def _reaction(decision_id: str, question_id: str, valence: str) -> RX.ReactionEvent:
    return RX.ReactionEvent(
        tx_time="t", question_id=question_id, decision_id=decision_id,
        kind="verdict", valence=valence,
    )


def test_boot_snapshot_joins_decisions_and_reactions_on_decision_id(tmp_path: Path) -> None:
    dpath, rpath = tmp_path / "decisions.jsonl", tmp_path / "reactions.jsonl"
    DEC.append(dpath, _decision("dec-1", "q-001", "report"))
    DEC.append(dpath, _decision("dec-2", "q-002", "abstain"))
    RX.append(rpath, _reaction("dec-1", "q-001", "good"))  # (report, good) -> y=1
    RX.append(rpath, _reaction("dec-2", "q-002", "bad"))   # (abstain, bad) -> y=1
    snap = SH.boot_snapshot(dpath, rpath, None)
    assert len(snap.verdict_replay) == 2
    ys = sorted(y for _s, y in snap.verdict_replay)
    assert ys == [1, 1]
    assert snap.outcome_replay == []
    assert snap.n_source_records == 4  # 2 decisions + 2 reactions


def test_boot_snapshot_excludes_verdict_y_none_pairs_and_counts_via_the_gap(
    tmp_path: Path,
) -> None:
    dpath, rpath = tmp_path / "decisions.jsonl", tmp_path / "reactions.jsonl"
    DEC.append(dpath, _decision("dec-1", "q-001", "report"))
    DEC.append(dpath, _decision("dec-2", "q-002", "ask_clarify"))  # not in verdict_y's table
    RX.append(rpath, _reaction("dec-1", "q-001", "good"))
    RX.append(rpath, _reaction("dec-2", "q-002", "good"))  # (ask_clarify, good) -> None
    snap = SH.boot_snapshot(dpath, rpath, None)
    assert len(snap.verdict_replay) == 1  # dec-2's pair excluded, not raised
    assert snap.n_source_records == 4  # still counts both raw rows


def test_boot_snapshot_excludes_unrouted_reactions(tmp_path: Path) -> None:
    dpath, rpath = tmp_path / "decisions.jsonl", tmp_path / "reactions.jsonl"
    DEC.append(dpath, _decision("dec-1", "q-001", "report"))
    RX.append(rpath, _reaction("dec-999", "q-999", "good"))  # no matching decision
    snap = SH.boot_snapshot(dpath, rpath, None)
    assert snap.verdict_replay == []
    assert snap.n_source_records == 2


def test_boot_snapshot_skips_a_malformed_decision_line_not_the_whole_file(
    tmp_path: Path,
) -> None:
    # `DEC.read` raises on the FIRST malformed line, which would previously discard
    # every OTHER decision in the file too (whole-file fail-open) — this pins that only
    # the bad line is skipped.
    dpath, rpath = tmp_path / "decisions.jsonl", tmp_path / "reactions.jsonl"
    DEC.append(dpath, _decision("dec-1", "q-001", "report"))
    with dpath.open("a", encoding="utf-8") as fh:
        fh.write("not valid json at all\n")
    DEC.append(dpath, _decision("dec-2", "q-002", "abstain"))
    RX.append(rpath, _reaction("dec-1", "q-001", "good"))
    RX.append(rpath, _reaction("dec-2", "q-002", "bad"))
    snap = SH.boot_snapshot(dpath, rpath, None)
    assert len(snap.verdict_replay) == 2  # both dec-1 and dec-2 replayed despite the bad line


def test_boot_snapshot_skips_a_malformed_reaction_line_not_the_whole_file(
    tmp_path: Path,
) -> None:
    dpath, rpath = tmp_path / "decisions.jsonl", tmp_path / "reactions.jsonl"
    DEC.append(dpath, _decision("dec-1", "q-001", "report"))
    DEC.append(dpath, _decision("dec-2", "q-002", "abstain"))
    RX.append(rpath, _reaction("dec-1", "q-001", "good"))
    with rpath.open("a", encoding="utf-8") as fh:
        fh.write("not valid json at all\n")
    RX.append(rpath, _reaction("dec-2", "q-002", "bad"))
    snap = SH.boot_snapshot(dpath, rpath, None)
    assert len(snap.verdict_replay) == 2


def test_boot_snapshot_missing_files_is_an_empty_snapshot_not_a_raise(tmp_path: Path) -> None:
    snap = SH.boot_snapshot(
        tmp_path / "nope-decisions.jsonl", tmp_path / "nope-reactions.jsonl", None,
    )
    assert snap == SH.BootSnapshot(verdict_replay=[], outcome_replay=[], n_source_records=0)


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


# The two id namespaces, in the SAME shapes production writes them (nothing below fabricates
# a question_id on both sides of the join — that fabrication is exactly why a structurally
# impossible join shipped, reported as merely under-powered):
#   * a fair-fight OutcomeVector.question_id is the CORPUS id  ("q-001"),
#   * a DecisionEvent.question_id is the MIRROR id (DEC.question_id of the question TEXT),
#   * and the run's own run_meta.json -> questions_path is the only thing that relates them.
_QUESTIONS: dict[str, str] = {
    "q-001": "What colour is the shed?",
    "q-002": "When does the permit expire?",
    "q-003": "Who signed the lease?",
    "q-004": "How many keys are there?",
    "q-005": "Where is the meter?",
}


def _write_warm_run(run_dir: Path, questions: dict[str, str] | None = None) -> Path:
    """A fair-fight run dir with the real `run_meta.json` -> `questions_path` indirection
    (`scripts/fairfight/run_fairfight.py` writes both), and the questions YAML it points at.
    Returns the questions path."""
    qs = _QUESTIONS if questions is None else questions
    questions_path = run_dir / "questions.yaml"
    run_dir.mkdir(parents=True, exist_ok=True)
    questions_path.write_text(
        "questions:\n" + "".join(
            f'  - id: {qid}\n    question: "{text}"\n' for qid, text in qs.items()
        ),
        encoding="utf-8",
    )
    (run_dir / "run_meta.json").write_text(
        json.dumps({"questions_path": str(questions_path)}), encoding="utf-8",
    )
    return questions_path


def test_warm_question_id_map_bridges_corpus_ids_to_mirror_ids(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-006"
    _write_warm_run(run_dir)
    id_map = SH.warm_question_id_map(run_dir)
    assert id_map == {qid: DEC.question_id(text) for qid, text in _QUESTIONS.items()}
    # and the mirror ids really are what a live decision would carry (not a private spelling)
    assert id_map["q-001"] == DEC.question_id("What colour is the shed?")


def test_warm_question_id_map_missing_run_meta_is_empty_not_a_raise(tmp_path: Path) -> None:
    assert SH.warm_question_id_map(tmp_path / "no-such-run") == {}


def test_boot_snapshot_warm_vectors_joins_baseline_vectors_to_shadow_calibration(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run-007"
    _write_warm_run(run_dir)
    _write_jsonl(run_dir / "arms" / "baseline" / "vectors.jsonl", [
        {"run_id": "run-007", "question_id": "q-001", "status": "ok",
         "asserted": True, "asserted_correct": True},
        {"run_id": "run-007", "question_id": "q-002", "status": "ok",
         "asserted": True, "asserted_correct": False},
        {"run_id": "run-007", "question_id": "q-003", "status": "ok",
         "asserted": False, "asserted_correct": False},  # not asserted -> excluded
        {"run_id": "run-007", "question_id": "q-004", "status": "timeout",
         "asserted": True, "asserted_correct": True},  # infra failure -> excluded
        {"run_id": "run-007", "question_id": "q-005", "status": "ok",
         "asserted": True, "asserted_correct": True},  # no matching calib decision
    ])
    calib_path = run_dir / "shadow_calibration" / "decisions.jsonl"
    # calibration decisions carry MIRROR ids — the real derivation, as lookup.py writes them
    DEC.append(calib_path, _decision("dec-1", DEC.question_id(_QUESTIONS["q-001"]), "report"))
    DEC.append(calib_path, _decision("dec-2", DEC.question_id(_QUESTIONS["q-002"]), "report"))
    dpath, rpath = tmp_path / "decisions.jsonl", tmp_path / "reactions.jsonl"
    snap = SH.boot_snapshot(dpath, rpath, run_dir)

    assert len(snap.outcome_replay) == 2
    event_ids = sorted(eid for eid, _s, _y in snap.outcome_replay)
    assert event_ids == ["run-007:q-001", "run-007:q-002"]  # dedup key stays the corpus id
    ys = {eid: y for eid, _s, y in snap.outcome_replay}
    assert ys["run-007:q-001"] == 1
    assert ys["run-007:q-002"] == 0
    # n_source_records counts VERDICT-source rows only (0 decisions + 0 reactions); the warm
    # rows are accounted separately, read-vs-joined, so an unjoinable row can never pad it
    assert snap.n_source_records == 0
    assert snap.warm == SH.WarmJoin(
        vector_rows=5, calib_decisions=2, id_map_size=5, joined=2, note="",
    )


def test_boot_snapshot_warm_join_of_zero_is_named_loudly_not_reported_as_no_data(
    tmp_path: Path,
) -> None:
    """The regression that motivated the whole id-namespace fix: calibration decisions keyed
    on the CORPUS id (as no producer actually writes them, but as the join used to ASSUME)
    join nothing at all. A zero join must read as a zero join — loudly — never as an
    under-powered sample."""
    run_dir = tmp_path / "run-009"
    _write_warm_run(run_dir)
    _write_jsonl(run_dir / "arms" / "baseline" / "vectors.jsonl", [
        {"run_id": "run-009", "question_id": "q-001", "status": "ok",
         "asserted": True, "asserted_correct": True},
    ])
    DEC.append(run_dir / "shadow_calibration" / "decisions.jsonl",
               _decision("dec-1", "q-001", "report"))  # corpus id: joins NOTHING
    snap = SH.boot_snapshot(
        tmp_path / "decisions.jsonl", tmp_path / "reactions.jsonl", run_dir,
    )
    assert snap.outcome_replay == []
    assert snap.warm is not None
    assert snap.warm.joined == 0
    assert snap.warm.vector_rows == 1
    assert "0 of 1 vector rows joined" in snap.warm.note
    assert "NOT 'not enough data'" in snap.warm.note


def test_boot_snapshot_warm_vectors_dir_none_leaves_outcome_replay_empty(
    tmp_path: Path,
) -> None:
    dpath, rpath = tmp_path / "decisions.jsonl", tmp_path / "reactions.jsonl"
    snap = SH.boot_snapshot(dpath, rpath, None)
    assert snap.outcome_replay == []
    assert snap.warm is None  # no warm dir asked for => no warm arithmetic claimed


def test_boot_snapshot_missing_warm_vector_files_fail_open(tmp_path: Path) -> None:
    dpath, rpath = tmp_path / "decisions.jsonl", tmp_path / "reactions.jsonl"
    run_dir = tmp_path / "nonexistent-run"
    snap = SH.boot_snapshot(dpath, rpath, run_dir)
    assert snap.outcome_replay == []
    assert snap.n_source_records == 0
    assert snap.warm == SH.WarmJoin(
        vector_rows=0, calib_decisions=0, id_map_size=0, joined=0, note="",
    )


def test_boot_snapshot_malformed_vector_line_is_skipped_not_raised(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-008"
    _write_warm_run(run_dir)
    p = run_dir / "arms" / "baseline" / "vectors.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        '{"run_id": "run-008", "question_id": "q-001", "status": "ok", '
        '"asserted": true, "asserted_correct": true}\n'
        "not valid json at all\n",
        encoding="utf-8",
    )
    DEC.append(run_dir / "shadow_calibration" / "decisions.jsonl",
               _decision("dec-1", DEC.question_id(_QUESTIONS["q-001"]), "report"))
    dpath, rpath = tmp_path / "decisions.jsonl", tmp_path / "reactions.jsonl"
    snap = SH.boot_snapshot(dpath, rpath, run_dir)
    assert len(snap.outcome_replay) == 1


# --- submit_gate: a seam gate pre-emption becomes a per-form `kind: "gate"` tick (M2) ----


def test_gate_submit_is_drained_into_a_gate_record_per_form(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    _calls, snapshot = _snapshot_calls_counter()
    factory = _FakeFactory()
    sh = SH.MembraneShadow(cfg, u_bar=_u_bar, snapshot=snapshot, session_factory=factory)
    try:
        sh.start()
        assert _wait_until(lambda: sh.stats()["forms"]["said@1"]["alive"])  # type: ignore[index]
        sh.submit_gate("q-001", "weak_retrieval")
        assert _wait_until(lambda: sh.stats()["forms"]["said@1"]["ticks"] >= 1)  # type: ignore[index]
        records = _read_records(cfg.log_path)
        gates = [r for r in records if r.get("kind") == "gate"]
        assert len(gates) == 1
        row = gates[0]
        assert row["event_type"] == "membrane-shadow"
        assert row["question_id"] == "q-001"
        assert row["gate"] == "weak_retrieval"
        assert row["form"] == "said@1"
        assert row["action"] == "respond"  # the fake session's canned choice
        assert row["real_effector"] == "abstain"  # a gate's committed act is always abstain
        assert row["readouts"] == {"p1": 0.7}
        # the engine was consulted under the FAITHFUL empty-evidence context: nothing
        # retrieved/extracted at either declared gate, so zero candidates, no posterior.
        assert row["summary"] == {
            "n_candidates": 0, "leader_credence": None, "p_none": None, "n_obs": 0,
            "era_split": False, "owner_scoped": False, "grow_pass": False,
        }
        session = factory.built["said@1"][0]
        assert session.decide_calls == [SH.GATE_SUMMARY]
        assert row["t"] == 0
        assert isinstance(row["latency_ms"], (int, float))
    finally:
        sh.close()


def test_gate_submit_never_raises_and_full_queue_drops(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path, queue_size=1)
    _calls, snapshot = _snapshot_calls_counter()
    factory = _FakeFactory()
    # Never call start(): nothing drains the queue, so the second submit overflows it.
    sh = SH.MembraneShadow(cfg, u_bar=_u_bar, snapshot=snapshot, session_factory=factory)
    sh.submit_gate("q-001", "weak_retrieval")
    sh.submit_gate("q-002", "executor_down")
    stats = sh.stats()
    assert stats["drops"] == 1
    assert stats["queue_depth"] == 1


def test_gate_tick_that_raises_marks_the_form_dead_like_a_decide_tick(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path, max_respawns=0)
    _calls, snapshot = _snapshot_calls_counter()
    dying = _FakeSession("said@1", decide_raises=True)
    factory = _FakeFactory({"said@1": [dying]})
    sh = SH.MembraneShadow(cfg, u_bar=_u_bar, snapshot=snapshot, session_factory=factory)
    try:
        sh.start()
        assert _wait_until(lambda: sh.stats()["forms"]["said@1"]["alive"])  # type: ignore[index]
        sh.submit_gate("q-001", "weak_retrieval")
        assert _wait_until(lambda: not sh.stats()["forms"]["said@1"]["alive"])  # type: ignore[index]
        assert dying.client.shutdown_calls >= 1
    finally:
        sh.close()


# --- M3: decide_live — the synchronous coarse-menu consult on the answer path -------------
#
# The ONE synchronous surface: the bridge's /decide-live blocks on it. The worker still
# owns every session (single-threaded engine access is preserved); decide_live enqueues a
# reply-slot item and waits, bounded. A dead primary form, a full queue, or a timeout all
# return None — the host's declared engine-down abstain, never an exception.

_LIVE_PAYLOAD: dict[str, object] = {
    "candidates": ["alpha", "beta"], "observations": [1, 2], "rho": 0.8,
    "u_bar": {"u_correct": 1.0, "u_abstain": 0.0, "u_wrong": -4.0,
              "lambda_int": 0.1, "kappa_att": 0.02},
    "era_split": False, "owner_scoped": False, "applied_probes": [],
    "transforms": [{"name": "corroborate_haiku", "probe": "corroborate_haiku",
                    "kind": "voi", "trigger": "below_bar", "rho": 0.8, "cost": 0.004}],
}
_LIVE_DEC: dict[str, object] = {
    "effector": "abstain", "value": None, "probe": None,
    "credences": [0.2, 0.3], "p_none": 0.5, "eu": 0.0, "n_obs": 2,
}


def test_decide_live_returns_the_mapped_view_and_writes_an_enact_record(
    tmp_path: Path,
) -> None:
    cfg = _cfg(tmp_path)
    factory = _FakeFactory()  # _FakeSession decides "respond" at p1=0.7
    sh = SH.MembraneShadow(
        cfg, u_bar=_u_bar, snapshot=_snapshot_calls_counter()[1],
        session_factory=factory, clock=_FakeClock(),
    )
    try:
        sh.start()
        assert _wait_until(lambda: sh.stats()["forms"]["said@1"]["alive"])  # type: ignore[index]
        out = sh.decide_live("q-live-1", dict(_LIVE_PAYLOAD), dict(_LIVE_DEC))
        assert out is not None
        # engine respond over daemon abstain → host-MAP report of the leader (beta)
        assert out["action"] == "respond"
        assert out["degraded"] is None
        assert out["dec"]["effector"] == "report"
        assert out["dec"]["value"] == "beta"
        # the engine was consulted under the SAME reduction the shadow ticks use
        session = factory.built["said@1"][0]
        assert session.decide_calls == [W.summary_from_payload(_LIVE_PAYLOAD, _LIVE_DEC)]
        assert _wait_until(
            lambda: any(r.get("kind") == "enact" for r in _read_records(cfg.log_path)))
        rec, = [r for r in _read_records(cfg.log_path) if r.get("kind") == "enact"]
        assert rec["question_id"] == "q-live-1"
        assert rec["form"] == "said@1"
        assert rec["action"] == "respond"            # the engine's coarse choice
        assert rec["daemon_effector"] == "abstain"   # what credence would have done
        assert rec["real_effector"] == "report"      # what the host enacted
        assert rec["degraded"] is None
        assert rec["readouts"] == {"p1": 0.7}
        assert rec["summary"] == {
            "n_candidates": 2, "leader_credence": 0.3, "p_none": 0.5, "n_obs": 2,
            "era_split": False, "owner_scoped": False, "grow_pass": False,
        }
        assert rec["t"] == 0  # a decision tick never advances the evidence stream
    finally:
        sh.close()


def test_decide_live_terminal_enactment_binds_the_reaction_summary(
    tmp_path: Path,
) -> None:
    # the live path replaces submit_decide on the mirror leg, so IT must remember the
    # summary a later submit_decision/submit_reaction binds the verdict to.
    cfg = _cfg(tmp_path)
    factory = _FakeFactory()
    sh = SH.MembraneShadow(
        cfg, u_bar=_u_bar, snapshot=_snapshot_calls_counter()[1],
        session_factory=factory, clock=_FakeClock(),
    )
    try:
        sh.start()
        assert _wait_until(lambda: sh.stats()["forms"]["said@1"]["alive"])  # type: ignore[index]
        sh.decide_live("q-live-2", dict(_LIVE_PAYLOAD), dict(_LIVE_DEC))
        expected = W.summary_from_payload(_LIVE_PAYLOAD, _LIVE_DEC)
        sh.submit_decision("d-live-2", "q-live-2", {"chosen_action": "report"})
        sh.submit_reaction("d-live-2", "good")
        session = factory.built["said@1"][0]
        assert _wait_until(lambda: session.observe_verdict_calls == [(expected, 1)])
    finally:
        sh.close()


def test_decide_live_dead_form_returns_none(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path, max_respawns=0)
    factory = _FakeFactory(
        sessions_for={"said@1": [_FakeSession("said@1", boot_raises=True)]})
    sh = SH.MembraneShadow(
        cfg, u_bar=_u_bar, snapshot=_snapshot_calls_counter()[1],
        session_factory=factory, clock=_FakeClock(),
    )
    try:
        sh.start()
        assert _wait_until(
            lambda: not sh.stats()["forms"]["said@1"]["alive"])  # type: ignore[index]
        assert sh.decide_live("q-live-3", dict(_LIVE_PAYLOAD), dict(_LIVE_DEC)) is None
    finally:
        sh.close()


def test_decide_live_engine_death_returns_none_and_marks_the_form_dead(
    tmp_path: Path,
) -> None:
    cfg = _cfg(tmp_path, max_respawns=0)
    factory = _FakeFactory(
        sessions_for={"said@1": [_FakeSession("said@1", decide_raises=True)]})
    sh = SH.MembraneShadow(
        cfg, u_bar=_u_bar, snapshot=_snapshot_calls_counter()[1],
        session_factory=factory, clock=_FakeClock(),
    )
    try:
        sh.start()
        assert _wait_until(lambda: sh.stats()["forms"]["said@1"]["alive"])  # type: ignore[index]
        assert sh.decide_live("q-live-4", dict(_LIVE_PAYLOAD), dict(_LIVE_DEC)) is None
        assert not sh.stats()["forms"]["said@1"]["alive"]  # type: ignore[index]
    finally:
        sh.close()


def test_decide_live_timeout_returns_none(tmp_path: Path) -> None:
    # never start the worker: the item sits unprocessed, so the bounded wait expires.
    cfg = _cfg(tmp_path)
    sh = SH.MembraneShadow(
        cfg, u_bar=_u_bar, snapshot=_snapshot_calls_counter()[1],
        session_factory=_FakeFactory(), clock=_FakeClock(),
    )
    assert sh.decide_live(
        "q-live-5", dict(_LIVE_PAYLOAD), dict(_LIVE_DEC), wait_s=0.05) is None


def test_decide_live_full_queue_returns_none(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path, queue_size=1)
    sh = SH.MembraneShadow(
        cfg, u_bar=_u_bar, snapshot=_snapshot_calls_counter()[1],
        session_factory=_FakeFactory(), clock=_FakeClock(),
    )
    # worker never started; one submit fills the queue, the live consult can't enqueue
    sh.submit_gate("q-fill", "weak_retrieval")
    assert sh.decide_live(
        "q-live-6", dict(_LIVE_PAYLOAD), dict(_LIVE_DEC), wait_s=0.05) is None


# --- E1 stage 1: the categorical mirror (kind: "cat" rows, flag-gated, shadow-only) -------
#
# `ShadowConfig.categorical=True` runs the categorical world (membrane/categorical.py:
# session-per-tick, obs_arity = K+1) beside the binary forms on the SAME decide stream —
# never on the decision path. Default False is byte-inert: no reduction is computed, no
# runner is called, no rows appear. The runner is injected (`cat_runner`) so these tests
# never spawn a process.

_CAT_PAYLOAD: dict[str, object] = {
    "candidates": ["alpha", "beta"],
    "observations": [{"reports": 0}, {"reports": 1}, {"reports": 0}],
    "era_split": False, "owner_scoped": True,
}
_CAT_DEC: dict[str, object] = {
    "effector": "abstain", "credences": [0.6, 0.2], "p_none": 0.2,
}


class _FakeCatRunner:
    """Duck-types `categorical.run_categorical`: records every call, returns a scripted
    `CatChoice` (or raises when told to)."""

    def __init__(self, *, raises: bool = False) -> None:
        self.calls: list[tuple[list[str], dict[str, float], CAT.CatSummary]] = []
        self.raises = raises

    def __call__(
        self, command: list[str], u_bar: Mapping[str, float], s: CAT.CatSummary,
        *, read_timeout_s: float = 300.0,
    ) -> CAT.CatChoice:
        self.calls.append((list(command), dict(u_bar), s))
        if self.raises:
            raise MembraneError("cat engine died")
        return CAT.CatChoice(
            action="respond_1", j=1, readouts={"p1": 0.35, "entropy_bits": 1.1},
            engine={"ok": True, "models": 42},
        )


def test_categorical_default_off_is_inert(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)  # categorical not set -> False
    runner = _FakeCatRunner()
    sh = SH.MembraneShadow(
        cfg, u_bar=_u_bar, snapshot=_snapshot_calls_counter()[1],
        session_factory=_FakeFactory(), cat_runner=runner,
    )
    try:
        sh.start()
        assert _wait_until(lambda: sh.stats()["forms"]["said@1"]["alive"])  # type: ignore[index]
        sh.submit_decide("q-cat-0", dict(_CAT_PAYLOAD), dict(_CAT_DEC))
        assert _wait_until(lambda: sh.stats()["forms"]["said@1"]["ticks"] >= 1)  # type: ignore[index]
        assert runner.calls == []
        assert [r for r in _read_records(cfg.log_path) if r.get("kind") == "cat"] == []
        assert sh.stats()["cat"] == {"ticks": 0, "errors": 0, "skips": 0}
    finally:
        sh.close()


def test_categorical_enabled_writes_a_cat_row_beside_the_binary_decide(
    tmp_path: Path,
) -> None:
    cfg = _cfg(tmp_path, categorical=True)
    runner = _FakeCatRunner()
    sh = SH.MembraneShadow(
        cfg, u_bar=_u_bar, snapshot=_snapshot_calls_counter()[1],
        session_factory=_FakeFactory(), cat_runner=runner,
    )
    try:
        sh.start()
        assert _wait_until(lambda: sh.stats()["forms"]["said@1"]["alive"])  # type: ignore[index]
        sh.submit_decide("q-cat-1", dict(_CAT_PAYLOAD), dict(_CAT_DEC))
        assert _wait_until(
            lambda: any(r.get("kind") == "cat" for r in _read_records(cfg.log_path)))
        rec, = [r for r in _read_records(cfg.log_path) if r.get("kind") == "cat"]
        assert rec["event_type"] == "membrane-shadow"
        assert rec["question_id"] == "q-cat-1"
        assert rec["k"] == 2
        assert rec["action"] == "respond_1"
        assert rec["j"] == 1
        assert rec["daemon_map_index"] == 0
        assert rec["real_effector"] == "abstain"
        assert rec["readouts"] == {"p1": 0.35, "entropy_bits": 1.1}
        assert rec["n_evidence"] == 3
        assert rec["n_obs_unmapped"] == 0
        assert rec["engine"] == {"ok": True, "models": 42}
        assert isinstance(rec["latency_ms"], (int, float))
        # the binary mirror still ran beside it
        assert [r for r in _read_records(cfg.log_path) if r.get("kind") == "decide"]
        # the runner saw the exact reduction and the cfg command
        (command, u_bar, s), = runner.calls
        assert command == cfg.command
        assert s == CAT.summary_from_payload_cat(_CAT_PAYLOAD, _CAT_DEC)
        assert sh.stats()["cat"] == {"ticks": 1, "errors": 0, "skips": 0}
    finally:
        sh.close()


def test_categorical_zero_candidates_is_a_counted_skip(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path, categorical=True)
    runner = _FakeCatRunner()
    sh = SH.MembraneShadow(
        cfg, u_bar=_u_bar, snapshot=_snapshot_calls_counter()[1],
        session_factory=_FakeFactory(), cat_runner=runner,
    )
    try:
        sh.start()
        assert _wait_until(lambda: sh.stats()["forms"]["said@1"]["alive"])  # type: ignore[index]
        sh.submit_decide("q-cat-2", {"candidates": []}, {"credences": [], "effector": "abstain"})
        assert _wait_until(lambda: sh.stats()["cat"]["skips"] >= 1)  # type: ignore[index]
        assert runner.calls == []
        assert [r for r in _read_records(cfg.log_path) if r.get("kind") == "cat"] == []
    finally:
        sh.close()


def test_categorical_runner_error_is_counted_and_the_worker_survives(
    tmp_path: Path,
) -> None:
    cfg = _cfg(tmp_path, categorical=True)
    runner = _FakeCatRunner(raises=True)
    sh = SH.MembraneShadow(
        cfg, u_bar=_u_bar, snapshot=_snapshot_calls_counter()[1],
        session_factory=_FakeFactory(), cat_runner=runner,
    )
    try:
        sh.start()
        assert _wait_until(lambda: sh.stats()["forms"]["said@1"]["alive"])  # type: ignore[index]
        sh.submit_decide("q-cat-3", dict(_CAT_PAYLOAD), dict(_CAT_DEC))
        assert _wait_until(lambda: sh.stats()["cat"]["errors"] >= 1)  # type: ignore[index]
        assert [r for r in _read_records(cfg.log_path) if r.get("kind") == "cat"] == []
        # a cat failure never kills the binary mirror: a second submit still ticks
        sh.submit_decide("q-cat-4", dict(_CAT_PAYLOAD), dict(_CAT_DEC))
        assert _wait_until(lambda: sh.stats()["forms"]["said@1"]["ticks"] >= 2)  # type: ignore[index]
    finally:
        sh.close()


def test_categorical_mirrors_the_live_path_too(tmp_path: Path) -> None:
    # M3 flag-on replaces the mirror leg's submit_decide with decide_live — the
    # categorical mirror must see that traffic as well, AFTER the live reply is released.
    cfg = _cfg(tmp_path, categorical=True)
    runner = _FakeCatRunner()
    sh = SH.MembraneShadow(
        cfg, u_bar=_u_bar, snapshot=_snapshot_calls_counter()[1],
        session_factory=_FakeFactory(), clock=_FakeClock(), cat_runner=runner,
    )
    try:
        sh.start()
        assert _wait_until(lambda: sh.stats()["forms"]["said@1"]["alive"])  # type: ignore[index]
        out = sh.decide_live("q-cat-live", dict(_LIVE_PAYLOAD), dict(_LIVE_DEC))
        assert out is not None  # the live reply is never blocked on the cat mirror
        assert _wait_until(
            lambda: any(r.get("kind") == "cat" for r in _read_records(cfg.log_path)))
        rec, = [r for r in _read_records(cfg.log_path) if r.get("kind") == "cat"]
        assert rec["question_id"] == "q-cat-live"
        # real_effector is what the host ENACTED (the mapped view), not the daemon's plan
        assert rec["real_effector"] == "report"
    finally:
        sh.close()
