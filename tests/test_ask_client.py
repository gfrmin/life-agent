"""The reach→know client (core/ask_client.py) — hermetic.

Jarvis's `question` intent routes to the SAME executor read-path the terminal uses
(interaction-contract: asking about your life is *know*, whatever transport carried it):
one call answers (decide_via_loop → render_view), logs the terminal decision through the
bridge's /log_decision (so the one-bit verdict folds through the existing reaction loop),
and returns the decision_id the in-chat verdict binds to. `react` posts the verdict and
names the fold fate in ask-live's own vocabulary — never implying every verdict counts.
"""
from __future__ import annotations

import hashlib
from typing import Any

from life_agent.core import ask_client as AC
from life_agent.core import executor as EX


def _answer(question: str, k: int = 20, **kw):
    """What every surface does since M3: drive, then render — the inline that replaced
    the AC.answer shim (jarvis and the A-loop driver spell exactly this)."""
    r = AC.drive(question, k, **kw)
    if r.down:
        return AC.DOWN, None
    assert r.view is not None
    return EX.render_view(r.view), r.decision_id

def _fake_view(effector: str = "report") -> dict[str, Any]:
    return {"effector": effector, "asserted": ["P123"] if effector == "report" else [],
            "candidates": ["P123"], "credences": [0.92], "p_none": 0.05, "eu": 0.8,
            "n_obs": 2, "hits": [{"artifact_cache_key": "d0", "chunk_text": "No: P123"}],
            "route": {"construct": "passport number"}}


def test_answer_renders_and_binds_the_decision(monkeypatch: Any) -> None:
    posted: list[tuple[str, dict[str, Any]]] = []
    monkeypatch.setattr(EX, "decide_via_loop", lambda *a, **k: _fake_view())

    def post(url: str, payload: dict[str, Any]) -> dict[str, Any]:
        posted.append((url, payload))
        assert url.endswith("/log_decision")
        return {"decision_id": "ab-cafe"}

    reply, decision_id = _answer("what is my passport number?",
                                   post=post, get=lambda u: {}, check_ready=False)
    assert "P123" in reply                       # the shared credence grammar rendering
    assert decision_id == "ab-cafe"              # the id the in-chat verdict binds to
    assert posted and posted[0][1]["decision"]["effector"] == "report"
    # the replayability fields (§14, 2026-08-17) ride the posted decision, zero-default
    assert posted[0][1]["decision"]["n_indeterminate"] == 0
    assert posted[0][1]["decision"]["n_competing"] == 0
    # the ONE body (M2, r12 DIR-1): no accounting field is optional on the poster's side,
    # and the two M0 fields are STATED — the reach surface's decisions become priced rows
    dec = posted[0][1]["decision"]
    assert dec["instrument"] == "" and dec["cost_usd"] == 0.0 and dec["latency_s"] == 0.0
    assert dec["run_id"] == "answer-brain"
    assert dec["regime"] == "full" and dec["policy"] == "all-to-date"


def test_answer_route_null_binds_nothing(monkeypatch: Any) -> None:
    # the route-null question's decision is the NARRATIVE family's, recorded by that leaf —
    # the poster stays silent. (The routed miss used to sit here too; since r33 RC-1 it
    # binds a reactable regime="miss" row — pinned below.)
    view = _fake_view("miss")
    view["candidates"], view["credences"], view["route"] = [], [], None
    monkeypatch.setattr(EX, "decide_via_loop", lambda *a, **k: view)
    reply, decision_id = _answer("q?", post=lambda u, p: {"decision_id": "x"},
                                   get=lambda u: {}, check_ready=False)
    assert decision_id is None                   # nothing foldable to bind
    assert reply                                 # still a named reply, never empty


def test_answer_wires_the_shared_shadow_mirror(monkeypatch: Any) -> None:
    # Jarvis's real traffic is a production caller of EX.decide_via_loop too — its post must
    # be shadow-wrapped through the SAME shared mirror scripts/ask.py installs, unconditionally.
    # The mirror's own behaviour (URL gating, fail-open, timeout, breaker, body shape) is
    # exercised once, directly, in tests/test_shadow_mirror.py — this is a wiring pin only.
    def bare_post(url: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        return {"ok": True}

    wrap_calls: list[tuple[Any, str, str]] = []

    def sentinel_wrapped(url: str, body: dict[str, Any]) -> dict[str, Any] | None:
        return {"sentinel": True}

    def fake_shadow_wrapped_post(post: Any, bridge: str, question_id: str) -> Any:
        wrap_calls.append((post, bridge, question_id))
        return sentinel_wrapped

    monkeypatch.setattr(AC.SM, "shadow_wrapped_post", fake_shadow_wrapped_post)

    captured: dict[str, Any] = {}

    def fake_decide_via_loop(question: str, k: int, **kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return _fake_view("miss")  # not a LOOKUP_ACTION_ORDER effector — no extra /log_decision

    monkeypatch.setattr(EX, "decide_via_loop", fake_decide_via_loop)
    _answer("what is my passport number?", post=bare_post, get=lambda u: {},
             check_ready=False)

    assert len(wrap_calls) == 1
    post_arg, bridge_arg, qid_arg = wrap_calls[0]
    assert post_arg is bare_post  # the real (unwrapped) transport goes in
    assert bridge_arg == AC.BRIDGE
    assert qid_arg == hashlib.sha256(b"what is my passport number?").hexdigest()[:16]
    assert captured["post"] is sentinel_wrapped  # decide_via_loop gets the WRAPPED post back


def test_answer_names_a_down_stack(monkeypatch: Any) -> None:
    monkeypatch.setattr(AC, "_ready", lambda: False)
    reply, decision_id = _answer("q?")
    assert "unavailable" in reply and decision_id is None


def test_post_surfaces_the_500_body(monkeypatch: Any) -> None:
    # The bridge RETURNS a seam failure's name in the 500 body (server.py: "visible to
    # the caller, never swallowed") — the PRODUCTION transport (jarvis → ask_client)
    # must carry it into the raised error, exactly like scripts/ask.py's _http_post
    # (review Major: the fix landed on one of three near-identical transports).
    import io
    import urllib.error
    import urllib.request

    import pytest

    def fake_urlopen(req: Any, timeout: int = 0) -> Any:
        raise urllib.error.HTTPError(
            "http://b/probe/corroborate", 500, "Internal Server Error", None,
            io.BytesIO(b'{"error": "ValueError: Invalid isoformat string"}'))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(urllib.error.HTTPError, match="isoformat"):
        AC._post("http://b/probe/corroborate", {"question": "q"})


def test_react_names_the_fold_fate() -> None:
    def post_folds(url: str, payload: dict[str, Any]) -> dict[str, Any]:
        assert payload == {"decision_id": "ab-1", "valence": "good"}
        return {"valence": "good", "family": "lookup", "chosen_action": "abstain",
                "folds": True}

    assert "folds into the utility posterior" in AC.react("ab-1", "good", post=post_folds)

    def post_report(url: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {"valence": "bad", "family": "lookup", "chosen_action": "report",
                "folds": False}

    assert "recorded — not folded" in AC.react("ab-1", "bad", post=post_report)


def test_react_failure_is_named_not_silent() -> None:
    def post_boom(url: str, payload: dict[str, Any]) -> dict[str, Any]:
        raise OSError("connection refused")

    assert "not recorded" in AC.react("ab-1", "good", post=post_boom)


def test_post_json_gives_the_narrative_path_more_headroom(monkeypatch) -> None:
    # the slow endpoint (cold expand + rerank + synthesize) outran the flat 300s
    # budget and the hung-up client wedged the bridge (run-6 void, 2026-08-17)
    import io
    import json as _json

    from life_agent.core import ask_client as AC

    seen: dict = {}

    class _R(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=None):
        seen[req.full_url] = timeout
        return _R(_json.dumps({"ok": True}).encode())

    monkeypatch.setattr(AC.urllib.request, "urlopen", fake_urlopen)
    AC.post_json("http://b/narrative", {})
    AC.post_json("http://b/route", {})
    AC.post_json("http://b/extract", {}, timeout=42)
    assert seen["http://b/narrative"] == AC._SLOW_TIMEOUT > 300
    assert seen["http://b/route"] == 300
    assert seen["http://b/extract"] == 42


def test_answer_offers_the_deliberate_menu_by_default(monkeypatch: Any) -> None:
    # §13 adoption: the surface the owner talks to runs the MEASURED arm — the priced
    # menu (deliberate row included) rides every decide_via_loop call by default
    captured: dict[str, Any] = {}

    def fake_loop(question: str, k: int, **kw: Any) -> dict[str, Any]:
        captured.update(kw)
        return _fake_view()

    monkeypatch.setattr(EX, "decide_via_loop", fake_loop)
    monkeypatch.delenv("LIFE_AGENT_DELIBERATE", raising=False)
    _answer("q?", post=lambda u, p: {}, get=lambda u: {}, check_ready=False)
    names = [t["name"] for t in captured["transforms"]]
    assert "deliberate" in names and "corroborate_opus" in names


def test_answer_deliberate_rollback_reverts_to_the_bare_menu(monkeypatch: Any) -> None:
    # LIFE_AGENT_DELIBERATE=0 is the named rollback: no transforms, no curve fold —
    # byte-for-byte the pre-adoption call
    captured: dict[str, Any] = {}

    def fake_loop(question: str, k: int, **kw: Any) -> dict[str, Any]:
        captured.update(kw)
        return _fake_view()

    monkeypatch.setattr(EX, "decide_via_loop", fake_loop)
    monkeypatch.setenv("LIFE_AGENT_DELIBERATE", "0")
    _answer("q?", post=lambda u, p: {}, get=lambda u: {}, check_ready=False)
    assert captured["transforms"] is None and captured["curves"] is None


# --- the one driver (M2, r12 D2/D3) --------------------------------------------------------

def test_answer_passes_realised_accounting_through(monkeypatch: Any) -> None:
    """A priced firing's instrument/cost/latency ride the reach surface's body verbatim —
    the ledger change M2 pre-registered (design §5.1)."""
    view = _fake_view()
    view["instrument"] = "deliberate@synthetic-model"  # PII-OK: synthetic
    view["cost_usd"], view["latency_s"] = 0.0123, 2.5
    monkeypatch.setattr(EX, "decide_via_loop", lambda *a, **k: view)
    posted: list[dict[str, Any]] = []

    def post(url: str, payload: dict[str, Any]) -> dict[str, Any]:
        posted.append(payload)
        return {"decision_id": "x"}

    _answer("q?", post=post, get=lambda u: {}, check_ready=False)
    dec = posted[0]["decision"]
    assert dec["instrument"] == "deliberate@synthetic-model"
    assert dec["cost_usd"] == 0.0123 and dec["latency_s"] == 2.5


def test_answer_down_stack_commits_the_gate_mirrors_and_records(monkeypatch: Any) -> None:
    """B-2/A-1 die (r12 D2): the reach surface's seam-less DOWN bypass is gone — the one
    driver commits the declared gate, mirrors it, and appends the §6.5 unavailability
    record. The reply string is untouched (interaction contract)."""
    from life_agent.core import recorder as REC
    from life_agent.core import seam as SEAM

    monkeypatch.setattr(AC, "_ready", lambda: False)
    mirrored: list[tuple[str, str, str]] = []
    recorded: list[dict[str, Any]] = []
    monkeypatch.setattr(AC.SM, "mirror_gate",
                        lambda bridge, qid, gate: mirrored.append((bridge, qid, gate)))
    monkeypatch.setattr(REC, "record_unavailable",
                        lambda question, **kw: recorded.append({"question": question, **kw}))
    reply, decision_id = _answer("q?")
    assert reply == AC.DOWN and decision_id is None
    assert mirrored == [(AC.BRIDGE, AC.DEC.question_id("q?"), SEAM.GATE_EXECUTOR_DOWN)]
    assert len(recorded) == 1 and recorded[0]["question"] == "q?"


def test_the_m2_shims_are_dead() -> None:
    # r13 mandate 3 (as amended): AC.answer and ask._edge_curves are deleted — callers
    # take the one driver directly; no old-poster spelling survives in core
    assert not hasattr(AC, "answer")


# --- r33 A1: the transport retries transient failures (signature E) ----------------------
# One live 5xx killed a whole ask during the Stage-4 measurement (conferral 2 §3.5). The
# transport retries 5xx / connection errors / timeouts with bounded backoff; a 4xx is the
# bridge speaking and is NEVER retried.

class _FakeResp:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self) -> "_FakeResp":
        return self

    def __exit__(self, *a: Any) -> bool:
        return False

    def read(self) -> bytes:
        return self._body


def _urlopen_seq(monkeypatch: Any, outcomes: list[Any]) -> tuple[dict[str, int], list[float]]:
    """Serve `outcomes` in order (an Exception raises, bytes answer); record sleeps."""
    calls = {"n": 0}
    sleeps: list[float] = []

    def urlopen(req: Any, timeout: Any = None) -> _FakeResp:
        out = outcomes[min(calls["n"], len(outcomes) - 1)]
        calls["n"] += 1
        if isinstance(out, Exception):
            raise out
        return _FakeResp(out)

    import urllib.request as _ur
    monkeypatch.setattr(_ur, "urlopen", urlopen)
    monkeypatch.setattr("time.sleep", lambda s: sleeps.append(s))
    return calls, sleeps


def _http_err(code: int) -> Exception:
    import urllib.error
    return urllib.error.HTTPError("http://x/decide", code, "boom", None, None)


def test_post_json_retries_5xx_then_succeeds(monkeypatch: Any) -> None:
    calls, sleeps = _urlopen_seq(
        monkeypatch, [_http_err(500), _http_err(503), b'{"ok": true}'])
    assert AC.post_json("http://x/decide", {}) == {"ok": True}
    assert calls["n"] == 3                       # two retries bought the answer
    assert len(sleeps) == 2 and sleeps == sorted(sleeps)   # bounded, backing off


def test_post_json_never_retries_4xx(monkeypatch: Any) -> None:
    import urllib.error

    import pytest
    calls, sleeps = _urlopen_seq(monkeypatch, [_http_err(400)])
    with pytest.raises(urllib.error.HTTPError):
        AC.post_json("http://x/decide", {})
    assert calls["n"] == 1 and sleeps == []      # the bridge spoke; that is the answer


def test_post_json_exhaustion_reraises_the_5xx(monkeypatch: Any) -> None:
    import urllib.error

    import pytest
    calls, _ = _urlopen_seq(monkeypatch, [_http_err(502)] * 9)
    with pytest.raises(urllib.error.HTTPError) as ei:
        AC.post_json("http://x/decide", {})
    assert ei.value.code == 502
    assert calls["n"] == 3                       # bounded: never an unbounded loop


def test_post_json_retries_connection_error_and_timeout(monkeypatch: Any) -> None:
    import urllib.error
    calls, _ = _urlopen_seq(
        monkeypatch, [urllib.error.URLError("refused"), TimeoutError(), b'{"ok": true}'])
    assert AC.post_json("http://x/decide", {}) == {"ok": True}
    assert calls["n"] == 3


def test_get_retries_5xx_then_succeeds(monkeypatch: Any) -> None:
    calls, _ = _urlopen_seq(monkeypatch, [_http_err(500), b'{"pong": 1}'])
    assert AC._get("http://x/state") == {"pong": 1}
    assert calls["n"] == 2


# --- r33 RC-1: the poster mints the miss row (the lane that was silent for 69 asks) -----

def _miss_view() -> dict[str, Any]:
    return {"effector": "miss", "asserted": [], "candidates": [], "credences": [],
            "p_none": None, "eu": None, "n_obs": 0, "n_indeterminate": 2,
            "hits": [{"artifact_cache_key": "d0", "chunk_text": "irrelevant"}],
            "route": {"construct": "passport number"}}


def test_a_miss_writes_a_local_row_and_returns_its_id(monkeypatch: Any) -> None:
    from life_agent.core import config as CFG
    monkeypatch.setattr(EX, "decide_via_loop", lambda *a, **k: _miss_view())
    posted: list[Any] = []
    r = AC.drive("what is my passport number?",
                 post=lambda u, p: posted.append((u, p)),
                 get=lambda u: {}, check_ready=False)
    assert r.decision_id and r.decision_id.startswith("ab-")
    assert not posted                                    # local append, never a bridge post
    import json as _json
    rows = [_json.loads(line) for line in CFG.DECISIONS_LOG.read_text().splitlines()]
    assert [row["regime"] for row in rows] == ["miss"]
    assert rows[0]["decision_id"] == r.decision_id
    assert rows[0]["posterior_summary"]["n_indeterminate"] == 2
