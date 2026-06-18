"""The life-agent capability bridge — a stateless JSON-over-HTTP service (move-3-design).

Wraps life-agent's body-side reads — route / retrieve / extract / probe / utility — as
discrete endpoints, each a thin wrapper of an existing, tested function, so the answer-brain
pi-mono body (Move 4) has a warm, independently-tested backend beside the daemon's `/decide`
(Move 2). The split is load-bearing: the **bridge gathers and shapes evidence; the daemon
decides**. No posterior is built here; `gather.py`'s policy stays out (it becomes the brain's
VOI job) — `/extract` takes `time_indexed` + `covariates` as INPUTS, it never computes them.

The one write is `/log_decision` (the verdict-emission seam): the body posts the terminal
decision the governor enacted, and the bridge appends it to the calibration decision log
(`core.decisions`) shaped exactly as the lookup family's own decisions — so the owner's
one-bit verdict folds into u(wrong) through the EXISTING reaction loop (`core.reactions`) with
no new fold code. The bridge owns the write because the daemon is stateless and the body is
string-blind; it still does NOT decide (it records what it was told).

**Stateless reads**: every read endpoint is a pure function of (corpus, request); the body
holds the growing hit set + accumulated covariates and resends them each refinement (uniform
with `/decide`), so two questions interleaved in one process cannot perturb each other.
`/log_decision`'s append is content-addressed (a stable `decision_id`), so a re-post coalesces
rather than double-counting.

**PII stays server-side**: the owner profile and the utility posterior are read INSIDE the
bridge (`BridgeDeps`), so `/probe/subject` and `/utility` carry neither over the wire; the
service binds loopback only. `/extract` returns the candidate display strings + the abstract
integer observations (`to_abstract_observations`) the daemon consumes verbatim — the single
source of that mapping, so the brain stays string-blind.
"""
from __future__ import annotations

import hashlib
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from http.server import BaseHTTPRequestHandler, HTTPServer
from json import JSONDecodeError, dumps, loads
from pathlib import Path
from typing import Any, cast

import duckdb

from life_agent import owner
from life_agent.bridge.observations import to_abstract_observations
from life_agent.core import config
from life_agent.core import decisions as DEC
from life_agent.core import lookup as LK
from life_agent.core import outcomes as O
from life_agent.core import probes as P
from life_agent.core import retrieval as RET

HOST = os.environ.get("LIFE_AGENT_BRIDGE_HOST", "127.0.0.1")
PORT = int(os.environ.get("LIFE_AGENT_BRIDGE_PORT", "8798"))  # adjacent to the daemon's 8799
_DEFAULT_K = 20

Payload = dict[str, Any]


@dataclass(frozen=True)
class BridgeDeps:
    """The warm, server-side handles every endpoint reads through — opened once at boot
    (a read-only catalogue handle + the extraction client, as `core/lookup` does per
    ask-session). ``profile`` + ``u_bar`` are the PII the body never sends; they are read
    here and only their summaries cross the wire."""

    root: Path
    conn: duckdb.DuckDBPyConnection      # read-only catalogue (FTS loaded) — retrieval + probes
    client: Any                          # extraction client (Ollama) — route / observe / subject
    profile: str                         # owner profile, loaded server-side (never over the wire)
    u_bar: Callable[[], dict[str, float]]  # the utility posterior's u_bar (lazy brain)
    decisions_path: Path                 # calibration decision log — /log_decision appends here
    fold_version: Callable[[], str]      # current utility fold version (pins the logged decision)


class BridgeError(Exception):
    """A request the bridge rejects with a 4xx — malformed body, missing field, bad value,
    unknown route. Carries the status; ``dispatch`` maps it to a JSON error response (the
    bridge never lets one bad request crash the warm loop)."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


# --- request helpers (parse / validate; every 4xx originates here) ---------------------

def _parse_body(body: bytes) -> Payload:
    if not body:
        raise BridgeError(400, "empty request body")
    try:
        payload = loads(body)
    except (JSONDecodeError, UnicodeDecodeError) as e:
        raise BridgeError(400, f"malformed JSON body: {e}") from e
    if not isinstance(payload, dict):
        raise BridgeError(400, "request body must be a JSON object")
    return payload


def _req_str(p: Payload, key: str) -> str:
    v = p.get(key)
    if not isinstance(v, str) or not v:
        raise BridgeError(400, f"field {key!r} must be a non-empty string")
    return v


def _req_list(p: Payload, key: str) -> list[Any]:
    v = p.get(key)
    if not isinstance(v, list):
        raise BridgeError(400, f"field {key!r} must be a list")
    return v


def _opt_date(v: Any) -> date | None:
    if v is None:
        return None
    if not isinstance(v, str):
        raise BridgeError(400, "field 'today' must be an ISO date string")
    try:
        return date.fromisoformat(v)
    except ValueError as e:
        raise BridgeError(400, f"field 'today': {e}") from e


def _covariates(c: Payload) -> LK.HitCovariates:
    """The §4.1 covariates as INPUTS (move-3 §0): the body supplies the projected
    doc_subject / doc_date maps; the bridge never decides them."""
    return LK.HitCovariates(
        subject_state=dict(c.get("subject_state") or {}),
        doc_date=dict(c.get("doc_date") or {}),
    )


# --- the endpoints (each a thin wrapper of one named, tested read) ---------------------

def _route(deps: BridgeDeps, p: Payload) -> Payload | None:
    r = LK.route_question(deps.root, _req_str(p, "question"), client=deps.client)
    if r is None:
        return None                          # not a typed lookup → the brain's narrative case
    return {"construct": r.construct, "time_indexed": r.time_indexed}


def _retrieve(deps: BridgeDeps, p: Payload) -> Payload:
    query = RET.build_query(_req_str(p, "question"), str(p.get("terms", "")))
    return {"hits": RET.retrieve_set(deps.conn, query, int(p.get("k", _DEFAULT_K)))}


def _extract(deps: BridgeDeps, p: Payload) -> Payload:
    cov = _covariates(p.get("covariates") or {})
    obs, indeterminate = LK.observe_hits(
        deps.root, _req_str(p, "question"), _req_list(p, "hits"),
        client=deps.client, covariates=cov,
        time_indexed=bool(p.get("time_indexed", False)), today=_opt_date(p.get("today")))
    candidates, abstract = to_abstract_observations(obs)
    # era_split is the evidence shape the string-blind body cannot compute (the abstract obs
    # carry no value/date); the bridge projects it from the RAW obs + the doc_date covariate and
    # the daemon reads it as a bool (move-4-design §2C). No doc_date ⇒ False.
    es = LK.era_split(obs, dict(cov.doc_date)) if cov.doc_date else False
    return {"candidates": candidates, "observations": abstract,
            "rho": LK.extractor_reliability(), "indeterminate": indeterminate,
            "era_split": es}


def _probe_recency(deps: BridgeDeps, p: Payload) -> Payload:
    return {"doc_date": P.probe_recency(deps.conn, deps.root, _req_list(p, "hit_keys"))}


def _probe_subject(deps: BridgeDeps, p: Payload) -> Payload:
    return {"subject_state": P.probe_subject(
        deps.conn, deps.root, _req_list(p, "hit_keys"),
        profile=deps.profile, client=deps.client)}


def _probe_authority(_deps: BridgeDeps, p: Payload) -> Payload:
    auth = P.probe_authority(_req_list(p, "hits"))
    return {"authority": {k: [klass, value] for k, (klass, value) in auth.items()}}


def _probe_corroborate(deps: BridgeDeps, p: Payload) -> Payload:
    hits = P.probe_corroborate(
        deps.conn, _req_str(p, "question"), _req_str(p, "leader_value"),
        k=int(p.get("k", _DEFAULT_K)), exclude_keys=list(p.get("exclude_keys") or ()))
    return {"hits": hits}


def _utility(deps: BridgeDeps, _p: Payload) -> Payload:
    return {"u_bar": deps.u_bar()}


# Terminal brain actions (DEC.LOOKUP_ACTION_ORDER) each map to one logged lookup decision; the
# steer `gather` is enacted by the body internally (re-extract + re-decide) and is never a
# terminal decision, so /log_decision rejects it.
_TERMINAL_ACTIONS: frozenset[str] = frozenset(DEC.LOOKUP_ACTION_ORDER)


def _decision_id(question: str, retrieval_keys: list[str],
                 credences: list[float], p_none: float) -> str:
    """A stable, content-addressed id for one answer-brain decision: the question, the
    retrieval set it was grounded on, and the posterior it was taken under. Namespaced
    (``ab-``) so it never collides with the lookup family's §18.9 answer keys; the reaction
    loop binds verdicts to it (``core.reactions`` join key). Identical re-runs coalesce."""
    payload = dumps({"source": "answer-brain", "question": question,
                     "retrieval_keys": sorted(retrieval_keys),
                     "credences": credences, "p_none": p_none},
                    sort_keys=True, ensure_ascii=False)
    return "ab-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def _req_float_list(d: Payload, key: str) -> list[float]:
    v = d.get(key)
    if not isinstance(v, list) or not v:
        raise BridgeError(400, f"decision.{key} must be a non-empty list")
    try:
        return [float(x) for x in v]
    except (TypeError, ValueError) as e:
        raise BridgeError(400, f"decision.{key} must be numbers: {e}") from e


def _log_decision(deps: BridgeDeps, p: Payload) -> Payload:
    """Append one answer-brain terminal decision to the calibration decision log, shaped
    exactly as the lookup family's own decisions (:func:`core.lookup.decide_and_record`), so
    the owner's one-bit verdict folds into u(wrong) through the EXISTING reaction loop with no
    new fold code (:func:`core.reactions.load_reactions`). The body posts the decision the
    governor enacted; the bridge owns the write — the daemon stays stateless, the body
    string-blind. Returns the ``decision_id`` the owner reacts against."""
    question = _req_str(p, "question")
    retrieval_keys = [str(x) for x in _req_list(p, "retrieval_keys")]
    decision = p.get("decision")
    if not isinstance(decision, dict):
        raise BridgeError(400, "field 'decision' must be a JSON object")
    action = decision.get("effector")
    if action not in _TERMINAL_ACTIONS:
        raise BridgeError(
            400, f"decision.effector {action!r} is not a terminal action "
            f"{sorted(_TERMINAL_ACTIONS)} (gather is a steer, not a logged decision)")
    credences = _req_float_list(decision, "credences")
    candidates = [str(c) for c in (decision.get("candidates") or [])]
    p_none = float(decision.get("p_none", 0.0))
    eu = float(decision.get("eu", 0.0))
    n_obs = int(decision.get("n_obs", 0))

    # Leader-first: the daemon returns credences in CANDIDATE order (server.jl `w[1:k]`), but the
    # fold reads ``credences[0]`` as the leader (lookup orders by weight desc). Sort here, or an
    # abstain folds at the first candidate's p rather than the leader's.
    order = sorted(range(len(credences)), key=lambda j: credences[j], reverse=True)
    creds_sorted = [credences[j] for j in order]
    cands_sorted = ([candidates[j] for j in order]
                    if len(candidates) == len(credences) else candidates)

    decision_id = _decision_id(question, retrieval_keys, creds_sorted, p_none)
    DEC.append(deps.decisions_path, DEC.DecisionEvent(
        tx_time=O.now_iso(), run_id="answer-brain",
        question_id=hashlib.sha256(question.encode("utf-8")).hexdigest()[:16],
        family="lookup", action_set=DEC.LOOKUP_ACTION_ORDER,
        posterior_summary={"candidates": cands_sorted, "credences": creds_sorted,
                           "p_none": p_none, "n_obs": n_obs},
        utility_fold_version=deps.fold_version(),
        chosen_action=action, predicted_eu=eu, decision_id=decision_id))
    return {"decision_id": decision_id}


Handler = Callable[[BridgeDeps, Payload], "Payload | None"]

_POST: dict[str, Handler] = {
    "/route": _route,
    "/retrieve": _retrieve,
    "/extract": _extract,
    "/probe/recency": _probe_recency,
    "/probe/subject": _probe_subject,
    "/probe/authority": _probe_authority,
    "/probe/corroborate": _probe_corroborate,
    "/log_decision": _log_decision,
}
_GET: dict[str, Handler] = {"/utility": _utility}


def dispatch(deps: BridgeDeps, method: str, path: str,
             body: bytes) -> tuple[int, Payload | None]:
    """Route one request to its endpoint and return ``(status, payload)``. Holds no state;
    every 4xx is returned (never raised past here), so a bad request never crashes the loop.
    ``GET /ready`` is transport liveness — no reasoning, no deps touched."""
    try:
        if method == "GET":
            if path == "/ready":
                return 200, {"status": "ok"}
            handler = _GET.get(path)
            if handler is None:
                raise BridgeError(404, f"no GET endpoint {path!r}")
            return 200, handler(deps, {})
        if method == "POST":
            handler = _POST.get(path)
            if handler is None:
                raise BridgeError(404, f"no POST endpoint {path!r}")
            return 200, handler(deps, _parse_body(body))
        raise BridgeError(405, f"method {method!r} not allowed")
    except BridgeError as e:
        return e.status, {"error": e.message}


# --- the warm HTTP service -------------------------------------------------------------

class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _respond(self, status: int, payload: Payload | None) -> None:
        data = dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _handle(self, method: str) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        deps = cast("BridgeServer", self.server).deps
        try:
            status, payload = dispatch(deps, method, self.path, body)
        except Exception as e:
            # A seam (model/corpus) failure is RETURNED as 500, with its message — visible to
            # the caller, never swallowed, and never crashing the warm long-lived loop.
            status, payload = 500, {"error": f"{type(e).__name__}: {e}"}
        self._respond(status, payload)

    def do_GET(self) -> None:       # BaseHTTPRequestHandler dispatch name
        self._handle("GET")

    def do_POST(self) -> None:
        self._handle("POST")

    def log_message(self, format: str, *args: Any) -> None:
        return  # quiet: the bridge is a backend, not an access log


class BridgeServer(HTTPServer):
    """Single-threaded by design: the body drives the bridge with one sequential tool loop,
    so requests serialise (and the read-only DuckDB handle is touched by one request at a
    time). Concurrency — and with it duckdb thread-safety — is a Move-4 measurement, not a
    Move-3 guess (move-3 §5 Q2)."""

    def __init__(self, deps: BridgeDeps, host: str = HOST, port: int = PORT) -> None:
        super().__init__((host, port), _Handler)
        self.deps = deps


def build_deps() -> BridgeDeps:
    """Open the warm, server-side handles once (move-3 §1): the read-only catalogue (FTS
    loaded, so a running extraction never blocks the bridge and vice-versa), the extraction
    client, the owner profile, and a lazy u_bar (the credence skin spawns on first `/utility`
    only)."""
    from life_agent.tasks import read

    root = read.pkm_root()
    conn = duckdb.connect(str(root / "catalogue.duckdb"), read_only=True)
    conn.execute("INSTALL fts; LOAD fts;")

    def _u_bar() -> dict[str, float]:
        u_bar, _version = LK.current_u_bar(LK.shared_brain())
        return u_bar

    def _fold_version() -> str:
        # current_u_bar caches per fold version in-process, so this rides the /utility fold.
        _u_bar, version = LK.current_u_bar(LK.shared_brain())
        return version

    return BridgeDeps(root=root, conn=conn, client=LK._client(),
                      profile=owner.load_profile(), u_bar=_u_bar,
                      decisions_path=config.DECISIONS_LOG, fold_version=_fold_version)


def main() -> None:
    server = BridgeServer(build_deps())
    print(f"life-agent capability bridge → http://{HOST}:{PORT}")
    print("  POST /route /retrieve /extract /probe/{recency,subject,authority,corroborate}")
    print("  POST /log_decision   (answer-brain verdict-emission seam)")
    print("  GET  /utility /ready")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
