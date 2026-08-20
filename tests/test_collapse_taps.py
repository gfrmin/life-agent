"""The recorder/replayer taps (module-collapse-design.md §7.2): the seams a fixture is
recorded at, and the cassette that serves them back.

Hermetic by construction — every double here speaks the real seam's shape against a
scripted inner, never a live engine. Values are SYNTHETIC (the repo is public, PII-free).

Run: uv run --project . python -m pytest tests/test_collapse_taps.py
"""
from __future__ import annotations

import json

import pytest

from life_agent.collapse import taps as T
from life_agent.core import brain as B

# --- the cassette ------------------------------------------------------------------------

def _ex(seam: str, req: dict, resp: object) -> T.FX.Exchange:
    return T.FX.Exchange(seam=seam, request=req, response=resp)


def test_cassette_serves_a_recorded_response_by_request() -> None:
    c = T.Cassette([_ex("skin", {"method": "mean", "params": {"state_id": "s1"}},
                        {"result": {"mean": 0.5}})])
    assert c.serve("skin", {"method": "mean", "params": {"state_id": "s1"}}) == \
        {"result": {"mean": 0.5}}


def test_cassette_serves_identical_requests_in_recorded_order() -> None:
    """`create_state` returns a NEW id every call, so identical requests must replay as a
    FIFO queue — content-keying alone would serve the first id twice and silently fuse two
    states into one."""
    req = {"method": "create_state", "params": {"type": "beta"}}
    c = T.Cassette([_ex("skin", req, {"result": {"state_id": "s1"}}),
                    _ex("skin", req, {"result": {"state_id": "s2"}})])
    assert c.serve("skin", req)["result"]["state_id"] == "s1"
    assert c.serve("skin", req)["result"]["state_id"] == "s2"


def test_cassette_miss_is_loud() -> None:
    c = T.Cassette([_ex("skin", {"method": "mean", "params": {}}, {"result": 1})])
    with pytest.raises(T.CassetteMissError, match="weights"):
        c.serve("skin", {"method": "weights", "params": {}})


def test_cassette_exhaustion_is_loud() -> None:
    req = {"method": "mean", "params": {}}
    c = T.Cassette([_ex("skin", req, {"result": 1})])
    c.serve("skin", req)
    with pytest.raises(T.CassetteMissError):
        c.serve("skin", req)


def test_cassette_serves_a_unique_near_match_and_notes_it() -> None:
    """A float that differs in the last ulp is not a behaviour change; an AMBIGUOUS
    near-match is (two candidate exchanges cannot be told apart), so it stays a miss."""
    c = T.Cassette([_ex("http", {"url": "/decide", "payload": {"rho": 0.8}},
                        {"effector": "report"})])
    got = c.serve("http", {"url": "/decide", "payload": {"rho": 0.8 + 1e-12}})
    assert got == {"effector": "report"}
    assert c.notes and "near-match" in c.notes[0]


def test_cassette_ambiguous_near_match_is_a_miss() -> None:
    c = T.Cassette([
        _ex("http", {"url": "/d", "payload": {"rho": 0.8}}, {"effector": "report"}),
        _ex("http", {"url": "/d", "payload": {"rho": 0.8 + 1e-13}}, {"effector": "hedge"}),
    ])
    with pytest.raises(T.CassetteMissError, match="ambiguous"):
        c.serve("http", {"url": "/d", "payload": {"rho": 0.8 + 5e-14}})


def test_cassette_reports_what_replay_never_asked_for() -> None:
    """An unused exchange is a NOTE, not a failure: a checkpoint that stops asking a
    question has not necessarily changed a decision — but the report must be able to say so."""
    c = T.Cassette([_ex("skin", {"method": "mean", "params": {}}, {"result": 1}),
                    _ex("skin", {"method": "weights", "params": {}}, {"result": 2})])
    c.serve("skin", {"method": "mean", "params": {}})
    assert [e.request["method"] for e in c.unused()] == ["weights"]


# --- the skin (credence engine) tap --------------------------------------------------------

class _ScriptedTransport:
    def __init__(self, results: dict[str, object]) -> None:
        self.results, self.sent, self.closed = results, [], False

    def send(self, line: str) -> None:
        self.sent.append(json.loads(line))

    def recv(self) -> str:
        req = self.sent[-1]
        return json.dumps({"jsonrpc": "2.0", "id": req["id"],
                           "result": self.results.get(req["method"], "ok")})

    def close(self) -> None:
        self.closed = True


def test_recording_transport_passes_through_and_captures_the_wire() -> None:
    inner = _ScriptedTransport({"mean": {"mean": 0.25}})
    sink: list = []
    b = B.Brain(T.RecordingTransport(inner, sink))
    assert b.mean("s1") == pytest.approx(0.25)
    assert [e.seam for e in sink] == ["skin"]
    assert sink[0].request == {"method": "mean", "params": {"state_id": "s1"}}
    assert sink[0].response == {"result": {"mean": 0.25}}


def test_recorded_wire_omits_the_jsonrpc_id() -> None:
    """The id is a per-process counter: keeping it in the key would make every request miss
    the moment a checkpoint adds or removes one engine call."""
    inner = _ScriptedTransport({"mean": {"mean": 0.25}})
    sink: list = []
    b = B.Brain(T.RecordingTransport(inner, sink))
    b.mean("s1")
    b.mean("s2")
    assert all("id" not in e.request and "id" not in e.response for e in sink)


def test_replay_transport_reproduces_a_recorded_session() -> None:
    inner = _ScriptedTransport({"create_state": {"state_id": "s7"},
                                "mean": {"mean": 0.75}})
    sink: list = []
    rec = B.Brain(T.RecordingTransport(inner, sink))
    sid = rec.create_state({"type": "beta", "alpha": 1.0, "beta": 1.0})
    recorded_mean = rec.mean(sid)

    replayed = B.Brain(T.ReplayTransport(T.Cassette(sink)))
    sid2 = replayed.create_state({"type": "beta", "alpha": 1.0, "beta": 1.0})
    assert sid2 == sid
    assert replayed.mean(sid2) == pytest.approx(recorded_mean)


def test_replay_transport_surfaces_a_recorded_engine_error() -> None:
    c = T.Cassette([_ex("skin", {"method": "mean", "params": {"state_id": "s9"}},
                        {"error": {"code": -32000, "message": "state not found: s9"}})])
    b = B.Brain(T.ReplayTransport(c))
    with pytest.raises(B.BrainError, match="state not found"):
        b.mean("s9")


def test_replay_transport_on_an_unrecorded_call_is_loud() -> None:
    b = B.Brain(T.ReplayTransport(T.Cassette([])))
    with pytest.raises(T.CassetteMissError):
        b.mean("s1")


# --- the http (bridge / daemon) tap ---------------------------------------------------------

def test_recording_http_captures_post_and_get_and_passes_through() -> None:
    sink: list = []
    calls: list = []

    def inner_post(url: str, payload: dict) -> dict:
        calls.append(url)
        return {"effector": "report", "eu": 0.5}

    def inner_get(url: str) -> dict:
        calls.append(url)
        return {"u_bar": {"u_correct": 1.0}}

    post, get = T.recording_http(inner_post, inner_get, sink)
    assert post("http://d/decide", {"candidates": ["A"]})["effector"] == "report"
    assert get("http://b/utility")["u_bar"]["u_correct"] == 1.0
    assert calls == ["http://d/decide", "http://b/utility"]
    assert [e.request["url"] for e in sink] == ["/decide", "/utility"]
    assert sink[0].request["method"] == "POST" and sink[1].request["method"] == "GET"


def test_recording_http_strips_the_base_url_so_a_moved_port_still_replays() -> None:
    sink: list = []
    post, _ = T.recording_http(lambda u, p: {"ok": True}, lambda u: {}, sink)
    post("http://127.0.0.1:8798/probe/subject", {"hit_keys": []})
    assert sink[0].request["url"] == "/probe/subject"


def test_replay_http_serves_recorded_replies() -> None:
    sink: list = []
    post, _ = T.recording_http(lambda u, p: {"hits": [{"artifact_cache_key": "k1"}]},
                               lambda u: {}, sink)
    post("http://b/retrieve", {"question": "q", "k": 8})  # PII-OK: synthetic question
    rpost, _rget = T.replay_http(T.Cassette(sink))
    assert rpost("http://b/retrieve", {"question": "q", "k": 8}) == \
        {"hits": [{"artifact_cache_key": "k1"}]}


def test_recording_http_preserves_a_null_route_reply() -> None:
    """`/route` returns null for a non-typed question — the narrative family's entry. A tap
    that coerced it to {} would silently re-route every narrative fixture to lookup."""
    sink: list = []
    post, _ = T.recording_http(lambda u, p: None, lambda u: {}, sink)
    assert post("http://b/route", {"question": "q"}) is None  # PII-OK: synthetic question
    rpost, _ = T.replay_http(T.Cassette(sink))
    assert rpost("http://b/route", {"question": "q"}) is None


# --- the instrument (cache-missing model call) tap --------------------------------------------

class _ScriptedClient:
    engine_version = "9.9.9"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def complete(self, prompt: str, schema: dict) -> object:
        self.calls.append(prompt)
        return T.InstrumentReply(raw_text='{"lookup": true}', cost_usd=0.002)


def test_recording_client_captures_completions_and_keeps_engine_version() -> None:
    sink: list = []
    inner = _ScriptedClient()
    c = T.RecordingClient(inner, sink)
    assert c.engine_version == "9.9.9"          # part of the cache-key identity
    reply = c.complete("prompt", {"type": "object"})
    assert reply.raw_text == '{"lookup": true}'
    assert [e.seam for e in sink] == ["instrument"]
    assert sink[0].request["engine_version"] == "9.9.9"


def test_replay_client_serves_the_recorded_completion() -> None:
    sink: list = []
    T.RecordingClient(_ScriptedClient(), sink).complete("prompt", {"type": "object"})
    r = T.ReplayClient(T.Cassette(sink), engine_version="9.9.9")
    reply = r.complete("prompt", {"type": "object"})
    assert reply.raw_text == '{"lookup": true}' and reply.cost_usd == pytest.approx(0.002)


def test_refusing_client_never_spends() -> None:
    """The recorder's default: a cache MISS is a named absence, not a silent model call —
    the baseline must cost nothing and must not depend on a live key."""
    c = T.RefusingClient(engine_version="9.9.9")
    with pytest.raises(T.WouldSpendError):
        c.complete("prompt", {"type": "object"})


# --- the §18.9 derivation-cache tap ------------------------------------------------------

def test_recording_cache_reads_the_live_root_and_captures_the_bytes() -> None:
    """Replay must not need the corpus: the cached derivation bytes ride in the cassette."""
    sink: list = []
    seen: list = []

    def live_lookup(root, cache_key):
        seen.append((root, cache_key))
        return b'{"lookup": true}' if cache_key == "warm" else None

    tap = T.RecordingCache(live_lookup, live_root="/fake/live", sink=sink)
    assert tap("/fake/staging", "warm") == b'{"lookup": true}'
    assert tap("/fake/staging", "cold") is None
    assert seen == [("/fake/live", "warm"), ("/fake/live", "cold")]
    assert [e.request["cache_key"] for e in sink] == ["warm", "cold"]
    assert sink[1].response is None


def test_replay_cache_serves_recorded_bytes_and_recorded_misses() -> None:
    sink: list = []
    tap = T.RecordingCache(lambda r, k: b"xy" if k == "warm" else None,
                           live_root="/fake/live", sink=sink)
    tap("/fake/staging", "warm")
    tap("/fake/staging", "cold")
    replay = T.ReplayCache(T.Cassette(sink))
    assert replay("/tmp/root", "warm") == b"xy"
    assert replay("/tmp/root", "cold") is None
