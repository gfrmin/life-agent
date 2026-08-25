"""The recorder/replayer taps — the seams a decision-equivalence fixture is recorded at.

Four seams, chosen because each is the boundary between the HOST (what the collapse moves)
and something the host does not compute:

* ``skin`` — the credence engine's JSON-RPC wire (:mod:`life_agent.core.brain`);
* ``http`` — the bridge/daemon wire (``executor.Post`` / ``executor.Get``);
* ``instrument`` — a cache-MISSING model call (the cached instruments' one live path);
* ``cache`` — a §18.9 derivation read (:func:`life_agent.core.derivations.lookup`).

Recording wraps each seam and passes through; replaying serves the recorded responses and
raises :class:`CassetteMissError` on anything the record never saw. Replay therefore needs no
daemon, no engine, no API key and no corpus — the fixture is self-contained, which is what
makes it usable as a bisection oracle (§8).

Nothing here is imported by the decision path.
"""
from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from life_agent.collapse import fixture as FX


class CassetteMissError(LookupError):
    """Replay asked the engine something the record never asked — a real divergence (the
    host changed which question it puts to the engine), not a fixture defect. Loud by
    design: a tap that invented a reply would turn an equivalence oracle into a rubber stamp.
    """


class WouldSpendError(RuntimeError):
    """A cache miss reached the model seam while recording under the no-spend default."""


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _shape(seam: str, request: dict[str, Any]) -> str:
    """The near-match bucket: requests that could be confused for one another. Never the
    whole request (that is the exact key) — only the part no float can perturb."""
    if seam == "skin":
        return str(request.get("method", ""))
    if seam == "http":
        return f"{request.get('method', '')} {request.get('url', '')}"
    if seam == "cache":
        return str(request.get("cache_key", ""))
    return seam


def _numeric_near(a: Any, b: Any, tol: float) -> bool:
    """True when a and b differ ONLY in numeric leaves, each within tol."""
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) <= tol
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_numeric_near(a[k], b[k], tol) for k in a)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(_numeric_near(x, y, tol)
                                        for x, y in zip(a, b, strict=True))
    return bool(a == b)


class Cassette:
    """Recorded exchanges, served back by request.

    Exact key first; then a UNIQUE numeric near-match within
    :data:`life_agent.collapse.fixture.FLOAT_TOL` (a last-ulp difference in a re-derived
    float is not a behaviour change) — an AMBIGUOUS near-match stays a miss, because two
    exchanges that cannot be told apart cannot be replayed honestly. Identical requests are
    a FIFO queue: `create_state` answers a new state id every call.
    """

    def __init__(self, exchanges: Iterable[FX.Exchange], *,
                 tol: float = FX.FLOAT_TOL) -> None:
        self._all: list[FX.Exchange] = list(exchanges)
        self._used: list[bool] = [False] * len(self._all)
        self._tol = tol
        self.notes: list[str] = []

    def serve(self, seam: str, request: dict[str, Any]) -> Any:
        want = _canonical(request)
        for i, ex in enumerate(self._all):
            if self._used[i]:
                continue
            if ex.seam == seam and _canonical(ex.request) == want:
                self._used[i] = True
                return ex.response
        shape = _shape(seam, request)
        near = [i for i, ex in enumerate(self._all)
                if not self._used[i] and ex.seam == seam
                and _shape(seam, ex.request) == shape
                and _numeric_near(ex.request, request, self._tol)]
        if len(near) == 1:
            self._used[near[0]] = True
            self.notes.append(f"near-match served for {seam} {shape} "
                              f"(numeric leaves within {self._tol})")
            return self._all[near[0]].response
        if len(near) > 1:
            raise CassetteMissError(
                f"ambiguous near-match: {len(near)} unused {seam} exchanges for {shape!r} "
                "are all within tolerance — the record cannot be replayed honestly")
        raise CassetteMissError(
            f"no recorded {seam} exchange for {shape!r} (request {want[:200]})")

    def unused(self) -> list[FX.Exchange]:
        """Exchanges replay never asked for — a NOTE for the checkpoint's report (a path
        that stops asking a question has not necessarily changed a decision)."""
        return [ex for ex, used in zip(self._all, self._used, strict=True) if not used]


# --- the credence-engine (skin) wire --------------------------------------------------------

class RecordingTransport:
    """Wraps a :class:`life_agent.core.brain.Transport`, capturing every call.

    The JSON-RPC ``id`` is dropped from both sides: it is a per-process counter, so keeping
    it would make every request miss the moment a checkpoint adds or removes one engine call.
    """

    def __init__(self, inner: Any, sink: list[FX.Exchange]) -> None:
        self._inner, self._sink = inner, sink
        self._pending: dict[str, Any] | None = None

    def send(self, line: str) -> None:
        req = json.loads(line)
        self._pending = {"method": req["method"], "params": req.get("params", {})}
        self._inner.send(line)

    def recv(self) -> str:
        line: str = self._inner.recv()
        resp = {k: v for k, v in json.loads(line).items() if k not in ("id", "jsonrpc")}
        self._sink.append(FX.Exchange(seam="skin", request=self._pending or {},
                                      response=resp))
        return line

    def close(self) -> None:
        self._inner.close()


class ReplayTransport:
    """Serves a recorded skin session — no engine process, no docker, no julia."""

    def __init__(self, cassette: Cassette) -> None:
        self._cassette = cassette
        self._req: dict[str, Any] | None = None
        self.closed = False

    def send(self, line: str) -> None:
        self._req = json.loads(line)

    def recv(self) -> str:
        req = self._req or {}
        resp = self._cassette.serve("skin", {"method": req.get("method"),
                                             "params": req.get("params", {})})
        return json.dumps({"jsonrpc": "2.0", "id": req.get("id"), **resp})

    def close(self) -> None:
        self.closed = True


# --- the bridge / daemon wire -----------------------------------------------------------

def _path_of(url: str) -> str:
    """The endpoint path, base stripped — a fixture must replay when the service moves port."""
    for sep in ("://",):
        if sep in url:
            rest = url.split(sep, 1)[1]
            return "/" + rest.split("/", 1)[1] if "/" in rest else "/"
    return url


def recording_http(inner_post: Callable[[str, dict[str, Any]], dict[str, Any] | None],
                   inner_get: Callable[[str], dict[str, Any]],
                   sink: list[FX.Exchange]) -> tuple[Callable[..., Any], Callable[..., Any]]:
    """Wrap the executor's injected transport seam (``Post`` / ``Get``), capturing both."""

    def post(url: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        reply = inner_post(url, payload)
        sink.append(FX.Exchange(
            seam="http",
            request={"method": "POST", "url": _path_of(url), "payload": payload},
            response=reply))
        return reply

    def get(url: str) -> dict[str, Any]:
        reply = inner_get(url)
        sink.append(FX.Exchange(seam="http",
                                request={"method": "GET", "url": _path_of(url)},
                                response=reply))
        return reply

    return post, get


def replay_http(cassette: Cassette) -> tuple[Callable[..., Any], Callable[..., Any]]:
    """Serve the recorded bridge/daemon replies — the shallow replay the loop's host runs
    under (the bridge's own leaves are pinned by their own trace-B fixtures)."""

    def post(url: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        served: dict[str, Any] | None = cassette.serve(
            "http", {"method": "POST", "url": _path_of(url), "payload": payload})
        return served

    def get(url: str) -> dict[str, Any]:
        served: dict[str, Any] = cassette.serve(
            "http", {"method": "GET", "url": _path_of(url)})
        return served

    return post, get


# --- the cached instruments' live path ----------------------------------------------------

@dataclass(frozen=True)
class InstrumentReply:
    """The two fields the cached instruments read off a completion (``raw_text``, and
    ``cost_usd`` for the spend meter)."""

    raw_text: str
    cost_usd: float = 0.0


class RecordingClient:
    """Wraps an instrument client; ``engine_version`` passes through because it is part of
    the §18.9 cache-key identity (a replay under a different SDK version keys differently and
    must therefore MISS, loudly, rather than silently answer a different question)."""

    def __init__(self, inner: Any, sink: list[FX.Exchange]) -> None:
        self._inner, self._sink = inner, sink
        self.engine_version = inner.engine_version

    def complete(self, prompt: str, schema: dict[str, Any]) -> Any:
        reply = self._inner.complete(prompt, schema)
        self._sink.append(FX.Exchange(
            seam="instrument",
            request={"prompt": prompt, "schema": schema,
                     "engine_version": str(self.engine_version)},
            response={"raw_text": str(reply.raw_text),
                      "cost_usd": float(getattr(reply, "cost_usd", 0.0) or 0.0)}))
        return reply


class RecordBudgetExceeded(BaseException):
    """A priced record blew its cap. Derives from BaseException so the recorder's
    per-trace absence handlers (``except Exception``) cannot swallow it into 300 named
    absences — a blown budget aborts the whole record."""


class MeteredRecordingClient(RecordingClient):
    """A :class:`RecordingClient` that sums ``cost_usd`` at the instrument seam and aborts
    past ``max_usd`` — the O2 gap (the recorder never metered spend) closed. The call that
    blows the cap is still recorded first: it was spent, so it belongs on the wire."""

    def __init__(self, inner: Any, sink: list[FX.Exchange], *, max_usd: float) -> None:
        super().__init__(inner, sink)
        self.max_usd, self.spent_usd = float(max_usd), 0.0

    def complete(self, prompt: str, schema: dict[str, Any]) -> Any:
        reply = super().complete(prompt, schema)
        self.spent_usd += float(getattr(reply, "cost_usd", 0.0) or 0.0)
        if self.spent_usd > self.max_usd:
            raise RecordBudgetExceeded(
                f"record budget exhausted: ${self.spent_usd:.2f} > ${self.max_usd:.2f}")
        return reply


class ReplayClient:
    def __init__(self, cassette: Cassette, *, engine_version: str) -> None:
        self._cassette = cassette
        self.engine_version = engine_version

    def complete(self, prompt: str, schema: dict[str, Any]) -> InstrumentReply:
        got = self._cassette.serve("instrument", {"prompt": prompt, "schema": schema,
                                                  "engine_version": self.engine_version})
        return InstrumentReply(raw_text=str(got["raw_text"]),
                               cost_usd=float(got.get("cost_usd") or 0.0))


class RefusingClient:
    """The recorder's default model seam: a cache miss REFUSES rather than spending.

    The M0 baseline is recorded from warm §18.9 derivations, so it costs nothing and needs
    no key; a question whose derivations are cold becomes a NAMED absence in the report
    instead of a silent live call at the owner's expense.
    """

    def __init__(self, *, engine_version: str) -> None:
        self.engine_version = engine_version

    def complete(self, prompt: str, schema: dict[str, Any]) -> Any:
        raise WouldSpendError(
            "a §18.9 derivation is cold and the recorder is in no-spend mode "
            f"(prompt {len(prompt)} chars, schema keys {sorted(schema)[:4]})")


# --- the §18.9 derivation cache -------------------------------------------------------------

class RecordingCache:
    """Reads the LIVE root read-only and captures the bytes.

    The recorder drives the families against a STAGING root (nothing is ever written to the
    live pkm root), so the cached derivations they replay must ride in the cassette. This is
    also what makes replay independent of the corpus.
    """

    def __init__(self, live_lookup: Callable[[Any, str], bytes | None], *,
                 live_root: Any, sink: list[FX.Exchange]) -> None:
        self._lookup, self._live_root, self._sink = live_lookup, live_root, sink

    def __call__(self, root: Any, cache_key: str) -> bytes | None:
        got = self._lookup(self._live_root, cache_key)
        self._sink.append(FX.Exchange(
            seam="cache", request={"cache_key": cache_key},
            response=None if got is None else got.decode("utf-8")))
        return got


class ReplayCache:
    def __init__(self, cassette: Cassette) -> None:
        self._cassette = cassette

    def __call__(self, root: Any, cache_key: str) -> bytes | None:
        got = self._cassette.serve("cache", {"cache_key": cache_key})
        return None if got is None else str(got).encode("utf-8")


def exchanges_of(sink: Sequence[FX.Exchange], seam: str) -> list[FX.Exchange]:
    return [e for e in sink if e.seam == seam]
