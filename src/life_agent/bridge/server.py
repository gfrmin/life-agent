"""The life-agent capability bridge — a stateless JSON-over-HTTP service (move-3-design).

Wraps life-agent's body-side reads — route / retrieve / extract / probe / utility — as
discrete endpoints, each a thin wrapper of an existing, tested function, so the answer-brain
pi-mono body (Move 4) has a warm, independently-tested backend beside the daemon's `/decide`
(Move 2). The split is load-bearing: the **bridge gathers and shapes evidence; the daemon
decides**. No posterior is built here; `gather.py`'s policy stays out (it becomes the brain's
VOI job) — `/extract` takes `time_indexed` + `covariates` as INPUTS, it never computes them.

The two writes are the verdict-emission seam: `/log_decision` (the body posts the terminal
decision the governor enacted, appended to the calibration decision log `core.decisions` shaped
exactly as the lookup family's own decisions) and `/log_reaction` (the owner's one-bit good/bad
verdict on a logged decision, appended to `core.reactions` — the in-session counterpart of
ask-live's `/react`). Together they let the owner's verdict fold into u(wrong) through the
EXISTING reaction loop with no new fold code. The bridge owns these writes because the daemon
is stateless and the body string-blind; it still does NOT decide (it records what it was told).

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

import contextlib
import hashlib
import os
import signal
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass
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
from life_agent.core import expansion as EXP
from life_agent.core import gather_outcomes as GO
from life_agent.core import joint_extract as JE
from life_agent.core import lookup as LK
from life_agent.core import matching as MATCH
from life_agent.core import narrative as NARR
from life_agent.core import outcomes as O
from life_agent.core import probes as P
from life_agent.core import reactions as RX
from life_agent.core import rerank as RR
from life_agent.core import retrieval as RET
from life_agent.core import synthesis as SYN
from life_agent.core import volatility as VOL
from life_agent.membrane import shadow as MEM

HOST = os.environ.get("LIFE_AGENT_BRIDGE_HOST", "127.0.0.1")
PORT = int(os.environ.get("LIFE_AGENT_BRIDGE_PORT", "8798"))  # adjacent to the daemon's 8799
_DEFAULT_K = 20
# the corroborate re-read's model + reliability. The cloud model is strong + subject-aware, so a
# high constant reliability for v0; Slice 3 calibrates this from verdicts (calib(c)) instead.
_JOINT_MODEL = "claude-opus-4-8"
_JOINT_RHO = 0.95

# The shadow supervisor's sizing (Task 5) — a long-lived-daemon queue/respawn budget, not
# tuned per-deployment (config.py governs WHICH engine/forms/paths; these three are fixed).
_MEMBRANE_QUEUE_SIZE = 1024
_MEMBRANE_MAX_RESPAWNS = 3
_MEMBRANE_RESPAWN_BACKOFF_S = 60.0

Payload = dict[str, Any]


@dataclass(frozen=True)
class BridgeDeps:
    """The warm, server-side handles every endpoint reads through — opened once at boot
    (a read-only catalogue handle + the extraction client, as `core/lookup` does per
    ask-session). ``profile`` + ``u_bar`` are the PII the body never sends; they are read
    here and only their summaries cross the wire.

    ``membrane`` is the shadow supervisor (Task 5 of the membrane-shadow feature) —
    ``None`` by default (and whenever `LIFE_AGENT_MEMBRANE_COMMAND` is unset), which is
    ZERO behaviour change on every endpoint below: `/decide-support` fast-paths to a
    disabled reply, and the `/log_decision`/`/log_reaction` folds are no-ops. It never
    decides anything on the real answer path — it only ever observes live traffic
    fed to it beside the real decision, off in its own worker thread."""

    root: Path
    conn: duckdb.DuckDBPyConnection      # read-only catalogue (FTS loaded) — retrieval + probes
    client: Any                          # extraction client (Ollama) — route / observe / subject
    profile: str                         # owner profile, loaded server-side (never over the wire)
    u_bar: Callable[[], dict[str, float]]  # the utility posterior's u_bar (lazy brain)
    decisions_path: Path                 # calibration decision log — /log_decision appends here
    reactions_path: Path                 # calibration reaction log — /log_reaction appends here
    fold_version: Callable[[], str]      # current utility fold version (pins the logged decision)
    gather_outcomes_path: Path           # gather-outcome log — /log_gather writes, /grow_menu reads
    membrane: MEM.MembraneShadow | None = None  # the shadow supervisor; None = disabled


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
    # Currency has ONE source of truth: the volatility table (the curated world-knowledge prior),
    # not
    # the route model's `time_indexed` guess. The model called "mobile phone number" permanent
    # (time_indexed=False) ⇒ a stale HK number never decayed and was reported as current (the q-014
    # confident-wrong). A construct IS time-indexed iff its half-life is not PERMANENT —
    # derive it, so
    # mobile/address/employer decay while DOB/national-id/tax-id do not. The model only
    # classifies the
    # CONSTRUCT; volatility decides whether it decays.
    time_indexed = VOL.half_life(r.construct) < VOL.PERMANENT
    return {"construct": r.construct, "time_indexed": time_indexed}


def _retrieve(deps: BridgeDeps, p: Payload) -> Payload:
    question = _req_str(p, "question")
    # Query expansion (a :grow recall mode): the owner asks in English, the docs are English AND
    # Hebrew, so a raw query can't reach a Hebrew doc — the dominant retrieval-miss (10/18).
    # `expand`
    # appends native-script keywords (build_query always keeps the raw words, so recall only grows).
    # It DILUTES strong literals, so the body uses it only on the grow pass, never the cheap first.
    terms = str(p.get("terms", ""))
    if p.get("expand"):
        terms = (terms + " " + EXP.expand_terms(question, root=deps.root)).strip()
    query = RET.build_query(question, terms)
    k = int(p.get("k", _DEFAULT_K))
    # the body's recall action (Slice 4): over-fetch a wide lexical pool and listwise-rerank to
    # top-k, surfacing a buried gold into extraction. A reorder, not a VOI gather — it grows the
    # evidence the next /decide sees; discovery over a closed candidate set is outside net_voi.
    if p.get("rerank"):
        pool = RET.retrieve_set(deps.conn, query, RR.RERANK_POOL)
        return {"hits": RR.rerank_hits(question, pool, k)}
    return {"hits": RET.retrieve_set(deps.conn, query, k)}


def _extract(deps: BridgeDeps, p: Payload) -> Payload:
    cov = _covariates(p.get("covariates") or {})
    # the construct's volatility half-life (the world-knowledge currency prior): a volatile
    # attribute's stale attestation decays in time_factor, a permanent one (DOB/id) does not.
    # The brain never sees it — it is folded into each observation's already-multiplied time_factor.
    hl = VOL.half_life(p.get("construct"))
    obs, indeterminate = LK.observe_hits(
        deps.root, _req_str(p, "question"), _req_list(p, "hits"),
        client=deps.client, covariates=cov,
        time_indexed=bool(p.get("time_indexed", False)), today=_opt_date(p.get("today")),
        half_life_years=hl)
    candidates, abstract = to_abstract_observations(obs)
    # era_split is the evidence shape the string-blind body cannot compute (the abstract obs
    # carry no value/date); the bridge projects it from the RAW obs + the doc_date covariate at
    # the construct's volatility, and the daemon reads it as a bool (move-4-design §2C). No
    # doc_date ⇒ False.
    es = LK.era_split(obs, dict(cov.doc_date), years=hl) if cov.doc_date else False
    return {"candidates": candidates, "observations": abstract,
            # the scalar rho the answer-brain consumes — the wire-read posterior mean (no host
            # alpha/(alpha+β); the full Beta drives the in-process lookup rho-latent, see
            # extractor_reliability).
            "rho": LK.extractor_reliability_mean(),
            "indeterminate": indeterminate, "era_split": es, "half_life_years": hl}


def _probe_recency(deps: BridgeDeps, p: Payload) -> Payload:
    return {"doc_date": P.probe_recency(deps.conn, deps.root, _req_list(p, "hit_keys"))}


def _probe_subject(deps: BridgeDeps, p: Payload) -> Payload:
    return {"subject_state": P.probe_subject(
        deps.conn, deps.root, _req_list(p, "hit_keys"),
        profile=deps.profile, client=deps.client)}


def _probe_authority(_deps: BridgeDeps, p: Payload) -> Payload:
    auth = P.probe_authority(_req_list(p, "hits"))
    return {"authority": {k: [klass, value] for k, (klass, value) in auth.items()}}


def _corroborate_time_factor(jr: JE.JointResult, hits: list[Payload], p: Payload) -> float:
    """The recency covariate for the corroborate re-read's observation — the construct's
    volatility decay, the same projection `/extract` applies (`LK.time_factor`). Recency is a
    document property, independent of WHOSE value it is, so the re-read value is as current as its
    freshest SOURCE attestation: take the max doc_date among the hits whose text actually contains
    the value (the shared date-aware matcher), falling back to the model's self-reported `as_of`,
    then to None (undated time-indexed ⇒ the stated `_A_TIME_UNKNOWN` attenuation). A non
    time-indexed construct passes through at 1.0 (no decay)."""
    if not bool(p.get("time_indexed", False)):
        return 1.0
    hl = VOL.half_life(p.get("construct"))
    doc_date = dict((p.get("covariates") or {}).get("doc_date") or {})
    value = jr.value or ""
    src_dates = [doc_date.get(h["artifact_cache_key"]) for h in hits
                 if MATCH.answer_matches(value, [], str(h.get("chunk_text", "")))]
    dated = sorted(d for d in src_dates if d)
    date_iso = dated[-1] if dated else jr.as_of
    return LK.time_factor(date_iso, time_indexed=True, today=_opt_date(p.get("today")),
                          half_life_years=hl)


def _probe_corroborate(deps: BridgeDeps, p: Payload) -> Payload:
    question = _req_str(p, "question")
    if p.get("reextract"):
        # The owner_scoped attribution guard's enactment (Slice 2b): a whole-document, SUBJECT-AWARE
        # re-read that REPLACES the local channel (nested dependence — the same documents). It
        # returns ONE abstract observation mapping the re-read value to an existing candidate index
        # — or NO observation when the re-read withholds / names a value outside the set (the
        # partner's-id case: the re-read says the leader is the OWNER's value, not the partner's).
        # The body re-decides on
        # this alone; an empty observation reverts the posterior to NONE-dominant ⇒ the report is
        # withheld (disagree ⇒ abstain, with no NONE-report atom needed). The string→abstract map
        # stays bridge-side (the brain stays string-blind).
        hits = _req_list(p, "hits")
        candidates = [str(c) for c in (p.get("candidates") or [])]
        model = str(p.get("model") or _JOINT_MODEL)
        # the scheduled tier's reliability (Slice 2): the re-decide conditions the re-read
        # obs at the tier's rho, so a weaker model's read is trusted less. Defaults to the
        # opus-tier _JOINT_RHO.
        tier_rho = float(p.get("rho") or _JOINT_RHO)
        jr = JE.extract_joint(deps.root, question, hits, model=model, k=len(hits))
        obs: list[Payload] = []
        new_candidate: str | None = None
        if jr.value is not None:
            vn = LK._norm_value(jr.value)
            idx = next((i for i, c in enumerate(candidates) if LK._norm_value(c) == vn), None)
            if idx is None:
                # The join must not read a CONFIRMING sentence as a disagreement (the q-011
                # pooling loss: the strong read confirmed the
                # grounded passport leader inside a full sentence; exact equality returned no observation and
                # the replace-contract erased the grounded channel). A candidate uniquely
                # contained in the re-read value — the graders' own token-boundary matcher —
                # is the confirmed leader; two contained candidates settle nothing and keep
                # the conservative outside-set ⇒ no-observation contract.
                contained = [i for i, c in enumerate(candidates)
                             if MATCH.answer_matches(str(c), [], jr.value)]
                if len(contained) == 1:
                    idx = contained[0]
            if idx is None and p.get("allow_new"):
                # The re-extract GROW actuator (slice 6): the strong re-read named a value
                # OUTSIDE the current candidate set — with allow_new it ENLARGES K (that is what
                # grow is for): the value comes back as a new candidate whose observation is
                # indexed at len(candidates); the body appends it and re-decides. Without
                # allow_new the corroborate contract is unchanged (outside-set ⇒ no observation
                # ⇒ disagree-abstain).
                new_candidate = jr.value
                idx = len(candidates)
            if idx is not None:
                # The keystone: the re-read obs flows through the SAME volatility projector
                # /extract uses — no transform may hand-set time_factor=1.0 and report a stale
                # value as current (the q-006 confident-stale bug that gated §2-A off). Recency is
                # attribution-independent (a document property), so the re-read value is as current
                # as its freshest SOURCE attestation.
                tf = _corroborate_time_factor(jr, hits, p)
                obs = [{"reports": idx, "group": 0, "authority": 1.0,
                        "subject_factor": 1.0, "time_factor": tf}]
        # the read's own stated confidence rides beside the tier rho: the k=0 strong rescue
        # conditions at min(tier, confidence), so the wire never discards the instrument's
        # uncertainty (a lone unsupported read must not enter at the tier's flat prior).
        out: Payload = {"observations": obs, "gather_rho": tier_rho, "value": jr.value,
                        "confidence": jr.confidence,
                        "served_model": jr.served_model, "tokens": jr.in_tokens + jr.out_tokens}
        if new_candidate is not None:
            out["new_candidate"] = new_candidate
        return out
    hits = P.probe_corroborate(
        deps.conn, question, _req_str(p, "leader_value"),
        k=int(p.get("k", _DEFAULT_K)), exclude_keys=list(p.get("exclude_keys") or ()))
    return {"hits": hits}


def _utility(deps: BridgeDeps, _p: Payload) -> Payload:
    return {"u_bar": deps.u_bar()}


def _grow_menu(deps: BridgeDeps, _p: Payload) -> Payload:
    """The `/decide` grow block, verbatim (slice 6): the declared sensor vocabulary + the menu
    actuators, each with its body-persisted warm counts (``None`` ⇒ the daemon's cold Beta
    prior). The bridge owns the store; the executor forwards the block to the daemon, which
    reads the learned ``g`` per actuator and prices the grow lane."""
    return {"grow": GO.grow_block(deps.gather_outcomes_path)}


def _log_gather(deps: BridgeDeps, p: Payload) -> Payload:
    """Append one gather outcome (the structure-observe stream — ask-as-connection §4 caveat 2).
    ``recovered`` is the honest v0 proxy: the grown question ended in a report through the exact
    0-CW terminal threshold. The bridge owns the write (as with the other logs); a probe outside
    the menu or a sensor outside its declared bucket fails loud — vocabulary drift must never be
    silently folded."""
    probe = _req_str(p, "probe")
    if probe not in {str(a["probe"]) for a in GO.GROW_ACTUATORS}:
        raise BridgeError(400, f"unknown grow probe {probe!r}")
    sensors = p.get("sensors")
    if not isinstance(sensors, dict):
        raise BridgeError(400, "field 'sensors' must be a JSON object")
    vocab = dict(GO.SENSOR_FEATURES)
    for name, values in vocab.items():
        if sensors.get(name) not in values:
            raise BridgeError(400, f"sensor {name!r} must be one of {values}, "
                                   f"got {sensors.get(name)!r}")
    GO.append_outcome(deps.gather_outcomes_path, probe,
                      {k: str(v) for k, v in sensors.items()},
                      recovered=bool(p.get("recovered")))
    return {"logged": True}


# --- /decide-support: the shadow's per-tick feed, off live traffic (never on the ---------
# --- decision path itself — MembraneShadow.submit_decide is enqueue-only and never raises) -

def _decide_support(deps: BridgeDeps, p: Payload) -> Payload:
    """The membrane shadow's per-tick feed: the executor posts the SAME `/decide`
    request/reply pair it just acted on, once per decide tick (a hot-path call). Disabled
    (the default) returns immediately, before any field parsing — no side effects, no
    validation cost, since there is nothing to feed. Enabled: parses `question_id`/
    `payload`/`dec` (a 400 on a malformed body, same shape every other handler uses) then
    hands them to `submit_decide`, itself guaranteed never to raise — the `try/except`
    below is defense-in-depth so this handler NEVER raises past itself regardless."""
    if deps.membrane is None:
        return {"ok": False, "disabled": True}
    question_id = _req_str(p, "question_id")
    payload = p.get("payload")
    dec = p.get("dec")
    if not isinstance(payload, dict):
        raise BridgeError(400, "field 'payload' must be a JSON object")
    if not isinstance(dec, dict):
        raise BridgeError(400, "field 'dec' must be a JSON object")
    with contextlib.suppress(Exception):
        deps.membrane.submit_decide(question_id, payload, dec)
    return {"ok": True}


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
    event = DEC.DecisionEvent(
        tx_time=O.now_iso(), run_id="answer-brain",
        question_id=DEC.question_id(question),
        family="lookup", action_set=DEC.LOOKUP_ACTION_ORDER,
        posterior_summary={"candidates": cands_sorted, "credences": creds_sorted,
                           "p_none": p_none, "n_obs": n_obs},
        utility_fold_version=deps.fold_version(),
        chosen_action=action, predicted_eu=eu, decision_id=decision_id)
    DEC.append(deps.decisions_path, event)
    if deps.membrane is not None:
        with contextlib.suppress(Exception):
            deps.membrane.submit_decision(decision_id, event.question_id, asdict(event))
    return {"decision_id": decision_id}


def _log_reaction(deps: BridgeDeps, p: Payload) -> Payload:
    """Append the owner's one-bit verdict on a logged decision (the in-session counterpart of
    ask-live's ``/react``). Looks the decision up by ``decision_id`` for its ``question_id`` (the
    linkage the fold copies), appends a ``ReactionEvent``, and reports the fold fate so the app
    can echo it. The fold (:func:`core.reactions.load_reactions`) still decides what *moves*:
    only an abstain verdict conditions u(wrong); a report verdict is recorded-not-folded. The
    verdict is one bit — ``good``/``bad``, never free text (the owner's prose is the loop's one
    expensive resource)."""
    decision_id = _req_str(p, "decision_id")
    valence = _req_str(p, "valence")
    if valence not in ("good", "bad"):
        raise BridgeError(400, f"valence must be 'good' or 'bad', got {valence!r}")
    match = [d for d in DEC.read(deps.decisions_path) if d.decision_id == decision_id]
    if not match:
        raise BridgeError(404, f"no decision with id {decision_id!r}")
    d = match[-1]  # latest row; identical decisions share a content-addressed id
    RX.append(deps.reactions_path, RX.ReactionEvent(
        tx_time=O.now_iso(), question_id=d.question_id, decision_id=decision_id,
        kind="verdict", valence=valence))
    if deps.membrane is not None:
        with contextlib.suppress(Exception):
            deps.membrane.submit_reaction(decision_id, valence)
    folds = d.chosen_action == "abstain"  # only abstain verdicts move the fold (reactions §4.4)
    return {"valence": valence, "family": d.family, "chosen_action": d.chosen_action,
            "folds": folds}


Handler = Callable[[BridgeDeps, Payload], "Payload | None"]

def _narrative(deps: BridgeDeps, p: Payload) -> Payload:
    """The narrative family (foundations §7) — the answer-brain's SECOND family, run when the typed
    router declines (a list / aggregate / compound question). Retrieve with the full recall
    (expansion + rerank), synthesize a CITED answer, then `narrative_answer` audits each claim
    against
    its cited card and includes it only if grounded AND EU-positive. Gate-safe by construction: an
    ungrounded or weak claim is dropped → abstain; it never confidently asserts a wrong value. The
    PII profile stays bridge-side (synthesis resolves "my"/"I" via it). `asserted` = the included
    claims' text, so the grader matches the gold inside a grounded claim."""
    question = _req_str(p, "question")
    k = int(p.get("k", _DEFAULT_K))
    terms = EXP.expand_terms(question, root=deps.root)
    pool = RET.retrieve_set(deps.conn, RET.build_query(question, terms), RR.RERANK_POOL)
    hits = RR.rerank_hits(question, pool, k)
    text, _key, _cached = SYN.synthesize(deps.root, question, hits, deps.profile)
    dates = P.probe_recency(deps.conn, deps.root,
                            list(dict.fromkeys(h["artifact_cache_key"] for h in hits)))
    cards = SYN.cards_from_hits(hits, dates)
    nv = NARR.narrative_answer(deps.root, question, text, cards)
    asserted = [c.text for c in nv.claims if c.included]
    return {"action": nv.action, "asserted": asserted, "rendered": nv.rendered,
            "hits": hits,  # the synthesis context, so the grader's channel diagnostics stay honest
            "claims": [{"text": c.text, "credence": c.credence, "included": c.included}
                       for c in nv.claims]}


_POST: dict[str, Handler] = {
    "/route": _route,
    "/retrieve": _retrieve,
    "/extract": _extract,
    "/narrative": _narrative,
    "/probe/recency": _probe_recency,
    "/probe/subject": _probe_subject,
    "/probe/authority": _probe_authority,
    "/probe/corroborate": _probe_corroborate,
    "/log_decision": _log_decision,
    "/log_reaction": _log_reaction,
    "/log_gather": _log_gather,
    "/decide-support": _decide_support,
}
_GET: dict[str, Handler] = {"/utility": _utility, "/grow_menu": _grow_menu}


def _membrane_ready_block(deps: BridgeDeps) -> Payload:
    """`GET /ready`'s membrane block: `stats()` when enabled, `{"enabled": false}`
    otherwise. `stats()` is documented never to raise, but this is a liveness endpoint —
    defense-in-depth so a membrane failure can never take `/ready` itself down."""
    if deps.membrane is None:
        return {"enabled": False}
    try:
        return deps.membrane.stats()
    except Exception:
        return {"enabled": True, "stats_error": True}


def dispatch(deps: BridgeDeps, method: str, path: str,
             body: bytes) -> tuple[int, Payload | None]:
    """Route one request to its endpoint and return ``(status, payload)``. Holds no state;
    every 4xx is returned (never raised past here), so a bad request never crashes the loop.
    ``GET /ready`` is transport liveness plus the membrane shadow's own liveness (its
    ``stats()``, guarded fail-open) — no other reasoning, no other deps touched."""
    try:
        if method == "GET":
            if path == "/ready":
                return 200, {"status": "ok", "membrane": _membrane_ready_block(deps)}
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


def _build_membrane(u_bar: Callable[[], dict[str, float]]) -> MEM.MembraneShadow | None:
    """Construct + start the shadow supervisor iff `LIFE_AGENT_MEMBRANE_COMMAND` is set —
    its absence (the default) returns `None`, which is ZERO behaviour change on the bridge
    (`BridgeDeps.membrane` docstring). Both construction and `start()` can raise (a Task 4
    review finding: `start()` raises `RuntimeError` on a double-start, and the underlying
    `Thread.start()` can also raise) — caught here so a shadow that fails to come up can
    NEVER prevent the bridge itself from serving; it only ever falls back to disabled."""
    command = config.membrane_command()
    if command is None:
        return None
    try:
        cfg = MEM.ShadowConfig(
            command=command, forms=config.membrane_utility_forms(),
            log_path=config.membrane_shadow_log(),
            read_timeout_s=config.membrane_read_timeout_s(),
            queue_size=_MEMBRANE_QUEUE_SIZE, max_respawns=_MEMBRANE_MAX_RESPAWNS,
            respawn_backoff_s=_MEMBRANE_RESPAWN_BACKOFF_S,
        )
        warm_vectors_dir = config.membrane_warm_vectors_dir()
        shadow = MEM.MembraneShadow(
            cfg, u_bar=u_bar,
            snapshot=lambda: MEM.boot_snapshot(
                config.DECISIONS_LOG, config.REACTIONS_LOG, warm_vectors_dir),
        )
        shadow.start()
        return shadow
    except Exception as e:
        print(f"life-agent bridge: membrane shadow failed to start, disabling "
              f"({type(e).__name__}: {e})")
        return None


def build_deps() -> BridgeDeps:
    """Open the warm, server-side handles once (move-3 §1): the read-only catalogue (FTS
    loaded, so a running extraction never blocks the bridge and vice-versa), the extraction
    client, the owner profile, and a lazy u_bar (the credence skin spawns on first `/utility`
    only). The membrane shadow (Task 5) is constructed last, off this same `_u_bar` — see
    `_build_membrane` for the disabled-by-default / never-blocks-boot contract."""
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
                      decisions_path=config.DECISIONS_LOG,
                      reactions_path=config.REACTIONS_LOG, fold_version=_fold_version,
                      gather_outcomes_path=config.GATHER_OUTCOMES_LOG,
                      membrane=_build_membrane(_u_bar))


def _shutdown(server: BridgeServer) -> None:
    """The SIGTERM/SIGINT cleanup: close the shadow (if one is running) so its on-close
    `stats` record — the counters the post-hoc report reads — actually flushes, then exit.
    systemd stops services with SIGTERM, and the OS's default disposition for that signal
    kills the process without ever unwinding into `main()`'s own code (no `finally`, no
    `atexit`) — so without an installed handler `deps.membrane.close()` never runs in
    production. `close()` is exception-suppressed: a shadow's own cleanup failing must
    never block shutdown (the same fail-open posture every other membrane call site
    takes). `sys.exit(0)` then unwinds normally back through `main()`'s own
    `try/finally` (`server.shutdown()`/`server_close()`) — the same SIGTERM convention
    `reach/jarvis.py` already uses."""
    if server.deps.membrane is not None:
        with contextlib.suppress(Exception):
            server.deps.membrane.close()
    sys.exit(0)


def _install_shutdown_handlers(server: BridgeServer) -> None:
    signal.signal(signal.SIGTERM, lambda *_: _shutdown(server))
    signal.signal(signal.SIGINT, lambda *_: _shutdown(server))


def main() -> None:
    server = BridgeServer(build_deps())
    _install_shutdown_handlers(server)
    print(f"life-agent capability bridge → http://{HOST}:{PORT}")
    print("  POST /route /retrieve /extract /probe/{recency,subject,authority,corroborate}")
    print("  POST /log_decision /log_reaction   (answer-brain verdict-emission seam)")
    print("  POST /decide-support   (membrane shadow per-tick feed; no-op unless enabled)")
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
