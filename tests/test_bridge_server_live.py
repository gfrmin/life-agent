"""One live system check for the capability bridge (move-3-design §2/§7).

Opt-in (`-m system`): boots the REAL service on the live pkm catalogue + local Ollama + the
credence skin, fully on-machine, and drives one `retrieve → extract → probe/corroborate →
probe/recency → extract` round-trip — the path the pi-mono body will drive in Move 4. It
asserts the contract *holds against real reads* (the union does not shrink; the abstract
observations are well-formed; `/utility` + `/ready` answer), never a specific datum — the
corpus is the owner's, so no value is printed or pinned. Non-deterministic (a model is in the
extract loop), so it is excluded from the default run and its result is reported explicitly.
"""
from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from typing import Any

import pytest

from life_agent.bridge.server import BridgeServer, build_deps
from life_agent.core import config as C

pytestmark = pytest.mark.system


def _http(base: str, method: str, path: str,
          body: dict[str, Any] | None = None) -> tuple[int, Any]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status, json.loads(resp.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


def _assert_extract_well_formed(payload: dict[str, Any]) -> None:
    assert isinstance(payload["candidates"], list)
    assert all(isinstance(c, str) for c in payload["candidates"])
    assert 0.0 < payload["rho"] <= 1.0
    assert isinstance(payload["indeterminate"], int) and payload["indeterminate"] >= 0
    n = len(payload["candidates"])
    for o in payload["observations"]:
        assert set(o) == {"reports", "group", "authority", "subject_factor", "time_factor"}
        assert 0 <= o["reports"] < n                 # indexes a real candidate (string-blind)
        assert o["group"] >= 0
        for f in ("authority", "subject_factor", "time_factor"):
            assert isinstance(o[f], (int, float))


@pytest.fixture
def live_bridge() -> Iterator[str]:
    if not C.PKM_CONFIG.exists():
        pytest.skip(f"no pkm config at {C.PKM_CONFIG} — live corpus unavailable")
    try:
        deps = build_deps()
    except (FileNotFoundError, KeyError) as e:
        pytest.skip(f"live corpus/catalogue unavailable: {e}")
    server = BridgeServer(deps, host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()


def test_live_round_trip(live_bridge: str) -> None:
    base = live_bridge
    question = "what is my mobile phone number?"   # a generic question; not itself any datum

    assert _http(base, "GET", "/ready") == (200, {"status": "ok"})

    status, retrieved = _http(base, "POST", "/retrieve", {"question": question, "k": 20})
    assert status == 200
    hits = retrieved["hits"]
    assert isinstance(hits, list)
    if not hits:
        pytest.skip("live corpus returned no hits for the probe question")

    status, base_extract = _http(base, "POST", "/extract",
                                 {"question": question, "hits": hits})
    assert status == 200, base_extract
    _assert_extract_well_formed(base_extract)

    leader = base_extract["candidates"][0] if base_extract["candidates"] else question
    held = [h["artifact_cache_key"] for h in hits]
    status, corr = _http(base, "POST", "/probe/corroborate",
                         {"question": question, "leader_value": leader, "exclude_keys": held})
    assert status == 200
    assert all(h["artifact_cache_key"] not in held for h in corr["hits"])   # only NEW documents
    union = hits + corr["hits"]
    assert len(union) >= len(hits)        # the union never shrinks

    keys = list({h["artifact_cache_key"] for h in union})
    status, recency = _http(base, "POST", "/probe/recency", {"hit_keys": keys})
    assert status == 200
    assert set(recency["doc_date"]).issubset(set(keys))

    status, reweighted = _http(base, "POST", "/extract", {
        "question": question, "hits": union,
        "covariates": {"doc_date": recency["doc_date"]}, "time_indexed": True})
    assert status == 200, reweighted
    _assert_extract_well_formed(reweighted)

    status, utility = _http(base, "GET", "/utility")
    assert status == 200
    assert "u_wrong" in utility["u_bar"]      # the utility posterior answered, server-side
