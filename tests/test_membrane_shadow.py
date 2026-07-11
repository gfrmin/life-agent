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

from life_agent.core import decisions as DEC
from life_agent.core import reactions as RX
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
        forms=("table@1",),
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


def _wait_until(predicate: object, *, timeout_s: float = 2.0, poll_s: float = 0.01) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():  # type: ignore[operator]
            return True
        time.sleep(poll_s)
    return bool(predicate())  # type: ignore[operator]


# --- start(): boots off one synchronous snapshot, writes a boot record per form ----------


def test_start_boots_every_form_and_writes_a_boot_record_each(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path, forms=("table@1", "latent@1"))
    calls, snapshot = _snapshot_calls_counter()
    factory = _FakeFactory()
    sh = SH.MembraneShadow(
        cfg, u_bar=_u_bar, snapshot=snapshot, session_factory=factory, clock=_FakeClock(),
    )
    try:
        sh.start()
        ok = _wait_until(
            lambda: all(
                sh.stats()["forms"][f]["alive"] for f in ("table@1", "latent@1")  # type: ignore[index]
            )
        )
        assert ok
        records = _read_records(cfg.log_path)
        boots = [r for r in records if r["kind"] == "boot"]
        assert {b["form"] for b in boots} == {"table@1", "latent@1"}
        for b in boots:
            assert b["event_type"] == "membrane-shadow"
            assert b["engine"] == {"ok": True, "proto": 1, "form": b["form"]}
            assert b["binary_sha256"] == "unknown"  # command[0] doesn't exist
            assert set(b["forms"]) == {"table@1", "latent@1"}  # type: ignore[arg-type]
            assert b["respawn_count"] == 0
            expected_digest = SH.world_digest(_u_bar(), utility_form=str(b["form"]))
            assert b["world_digest"] == expected_digest
        assert len(calls) == 1  # ONE synchronous snapshot shared by the initial boot
    finally:
        sh.close()


# --- submit_decide -> worker drains -> decide record -------------------------------------


def test_decide_submit_is_drained_into_a_decide_record(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    _calls, snapshot = _snapshot_calls_counter()
    factory = _FakeFactory()
    sh = SH.MembraneShadow(cfg, u_bar=_u_bar, snapshot=snapshot, session_factory=factory)
    try:
        sh.start()
        assert _wait_until(lambda: sh.stats()["forms"]["table@1"]["alive"])  # type: ignore[index]
        payload = {"candidates": ["a"], "observations": [1, 2], "era_split": True}
        dec = {"credences": [0.8], "p_none": 0.1, "effector": "report"}
        sh.submit_decide("q-001", payload, dec)
        assert _wait_until(lambda: sh.stats()["forms"]["table@1"]["ticks"] >= 1)  # type: ignore[index]
        records = _read_records(cfg.log_path)
        decides = [r for r in records if r["kind"] == "decide"]
        assert len(decides) == 1
        row = decides[0]
        assert row["event_type"] == "membrane-shadow"
        assert row["question_id"] == "q-001"
        assert row["form"] == "table@1"
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
    factory = _FakeFactory({"table@1": [_FakeSession("table@1", boot_raises=True)]})
    # every subsequent respawn attempt also gets a boot_raises=True session (the
    # factory's fallback builds a plain fresh() session otherwise) — script enough.
    factory.sessions_for["table@1"] = [
        _FakeSession("table@1", boot_raises=True) for _ in range(6)
    ]
    sh = SH.MembraneShadow(
        cfg, u_bar=_u_bar, snapshot=snapshot, session_factory=factory, clock=_FakeClock(),
    )
    try:
        sh.start()
        assert _wait_until(
            lambda: sh.stats()["forms"]["table@1"]["respawns"] == cfg.max_respawns  # type: ignore[index]
        )
        stats = sh.stats()
        assert stats["forms"]["table@1"]["alive"] is False  # type: ignore[index]
        assert stats["forms"]["table@1"]["respawns"] == 3  # type: ignore[index]
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
    dying = _FakeSession("table@1", decide_raises=True)
    factory = _FakeFactory({"table@1": [dying, _FakeSession("table@1", boot_raises=True)]})
    sh = SH.MembraneShadow(
        cfg, u_bar=_u_bar, snapshot=snapshot, session_factory=factory, clock=_FakeClock(),
    )
    try:
        sh.start()
        assert _wait_until(lambda: sh.stats()["forms"]["table@1"]["alive"])  # type: ignore[index]
        sh.submit_decide("q-001", {"candidates": []}, {"credences": [], "effector": "report"})
        assert _wait_until(
            lambda: sh.stats()["forms"]["table@1"]["respawns"] == 1  # type: ignore[index]
        )
        stats = sh.stats()
        assert stats["forms"]["table@1"]["alive"] is False  # type: ignore[index]
        assert factory.calls["table@1"] == 2  # initial boot + the one respawn attempt
        assert len(calls) == 2  # 1 initial (start) + 1 fresh (the respawn)
    finally:
        sh.close()


def test_a_dead_form_recovers_when_its_respawn_succeeds(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path, max_respawns=2, respawn_backoff_s=0.0)
    _calls, snapshot = _snapshot_calls_counter()
    dying = _FakeSession("table@1", decide_raises=True)
    healthy = _FakeSession("table@1")
    factory = _FakeFactory({"table@1": [dying, healthy]})
    sh = SH.MembraneShadow(
        cfg, u_bar=_u_bar, snapshot=snapshot, session_factory=factory, clock=_FakeClock(),
    )
    try:
        sh.start()
        assert _wait_until(lambda: sh.stats()["forms"]["table@1"]["alive"])  # type: ignore[index]
        sh.submit_decide("q-001", {"candidates": []}, {"credences": [], "effector": "report"})
        # dies, then the respawn (with `healthy`) brings it back alive. Wait on the
        # factory having actually built the SECOND session, not merely on "alive" —
        # `dying` is also alive right up until the queued item kills it, so polling
        # "alive" alone could spuriously pass before the death/respawn cycle even ran.
        assert _wait_until(lambda: factory.calls.get("table@1", 0) == 2)
        assert _wait_until(lambda: sh.stats()["forms"]["table@1"]["alive"])  # type: ignore[index]
        # a SUCCESSFUL respawn doesn't consume budget (respawn_count counts failed
        # attempts only — see shadow.py's `_handle_death` docstring), so respawns stays 0.
        assert sh.stats()["forms"]["table@1"]["respawns"] == 0  # type: ignore[index]
        sh.submit_decide("q-002", {"candidates": []}, {"credences": [], "effector": "report"})
        assert _wait_until(lambda: len(healthy.decide_calls) == 1)
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
    session = _FakeSession("table@1")
    factory = _FakeFactory({"table@1": [session]})
    sh = SH.MembraneShadow(
        cfg, u_bar=_u_bar, snapshot=snapshot, session_factory=factory, clock=_FakeClock(),
    )
    try:
        sh.start()
        assert _wait_until(lambda: sh.stats()["forms"]["table@1"]["alive"])  # type: ignore[index]
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
        assert evidence[0]["form"] == "table@1"
        assert evidence[0]["t"] == 0  # the t sent on the wire, pre-increment
    finally:
        sh.close()


def test_reaction_falls_back_to_decision_event_summary_when_no_live_summary_was_seen(
    tmp_path: Path,
) -> None:
    cfg = _cfg(tmp_path)
    _calls, snapshot = _snapshot_calls_counter()
    session = _FakeSession("table@1")
    factory = _FakeFactory({"table@1": [session]})
    sh = SH.MembraneShadow(
        cfg, u_bar=_u_bar, snapshot=snapshot, session_factory=factory, clock=_FakeClock(),
    )
    try:
        sh.start()
        assert _wait_until(lambda: sh.stats()["forms"]["table@1"]["alive"])  # type: ignore[index]
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


def test_close_joins_worker_and_shuts_down_every_client(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path, forms=("table@1", "latent@1"))
    _calls, snapshot = _snapshot_calls_counter()
    factory = _FakeFactory()
    sh = SH.MembraneShadow(cfg, u_bar=_u_bar, snapshot=snapshot, session_factory=factory)
    sh.start()
    assert _wait_until(
        lambda: all(sh.stats()["forms"][f]["alive"] for f in ("table@1", "latent@1"))  # type: ignore[index]
    )
    worker = sh._worker  # white-box: confirm the worker thread actually stops
    assert worker is not None
    sh.close()
    assert not worker.is_alive()
    for sessions in factory.built.values():
        for s in sessions:
            assert s.client.shutdown_calls == 1


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


# --- stats() shape --------------------------------------------------------------------


def test_stats_shape(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path, forms=("table@1",))
    _calls, snapshot = _snapshot_calls_counter()
    sh = SH.MembraneShadow(cfg, u_bar=_u_bar, snapshot=snapshot, session_factory=_FakeFactory())
    stats = sh.stats()
    assert set(stats) == {"forms", "drops", "skips", "queue_depth", "snapshot_records"}
    assert set(stats["forms"]) == {"table@1"}  # type: ignore[arg-type]
    assert set(stats["forms"]["table@1"]) == {"alive", "respawns", "ticks"}  # type: ignore[index]


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


def test_boot_snapshot_warm_vectors_joins_baseline_vectors_to_shadow_calibration(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run-007"
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
    DEC.append(calib_path, _decision("dec-1", "q-001", "report"))
    DEC.append(calib_path, _decision("dec-2", "q-002", "report"))
    dpath, rpath = tmp_path / "decisions.jsonl", tmp_path / "reactions.jsonl"
    snap = SH.boot_snapshot(dpath, rpath, run_dir)
    assert len(snap.outcome_replay) == 2
    event_ids = sorted(eid for eid, _s, _y in snap.outcome_replay)
    assert event_ids == ["run-007:q-001", "run-007:q-002"]
    ys = {eid: y for eid, _s, y in snap.outcome_replay}
    assert ys["run-007:q-001"] == 1
    assert ys["run-007:q-002"] == 0
    # 0 decisions/reactions + 5 vector rows + 2 calib decisions
    assert snap.n_source_records == 7


def test_boot_snapshot_warm_vectors_dir_none_leaves_outcome_replay_empty(
    tmp_path: Path,
) -> None:
    dpath, rpath = tmp_path / "decisions.jsonl", tmp_path / "reactions.jsonl"
    snap = SH.boot_snapshot(dpath, rpath, None)
    assert snap.outcome_replay == []


def test_boot_snapshot_missing_warm_vector_files_fail_open(tmp_path: Path) -> None:
    dpath, rpath = tmp_path / "decisions.jsonl", tmp_path / "reactions.jsonl"
    run_dir = tmp_path / "nonexistent-run"
    snap = SH.boot_snapshot(dpath, rpath, run_dir)
    assert snap.outcome_replay == []
    assert snap.n_source_records == 0


def test_boot_snapshot_malformed_vector_line_is_skipped_not_raised(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-008"
    p = run_dir / "arms" / "baseline" / "vectors.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        '{"run_id": "run-008", "question_id": "q-001", "status": "ok", '
        '"asserted": true, "asserted_correct": true}\n'
        "not valid json at all\n",
        encoding="utf-8",
    )
    DEC.append(run_dir / "shadow_calibration" / "decisions.jsonl",
               _decision("dec-1", "q-001", "report"))
    dpath, rpath = tmp_path / "decisions.jsonl", tmp_path / "reactions.jsonl"
    snap = SH.boot_snapshot(dpath, rpath, run_dir)
    assert len(snap.outcome_replay) == 1
