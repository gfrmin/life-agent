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
import os
import re
import signal
import sys
import time
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from json import JSONDecodeError, dumps, loads
from pathlib import Path
from typing import Any, cast
from urllib.parse import parse_qs

import duckdb

from life_agent import owner
from life_agent.bridge.observations import join_wire_observations, to_abstract_observations
from life_agent.core import answer_shape as AS
from life_agent.core import config
from life_agent.core import corpus as CORPUS
from life_agent.core import decisions as DEC
from life_agent.core import deliberate as DL
from life_agent.core import derivations as D
from life_agent.core import expansion as EXP
from life_agent.core import gather_outcomes as GO
from life_agent.core import joint_extract as JE
from life_agent.core import lookup as LK
from life_agent.core import matching as MATCH
from life_agent.core import narrative as NARR
from life_agent.core import outcomes as O
from life_agent.core import pricing as PRICING
from life_agent.core import probes as P
from life_agent.core import reactions as RX
from life_agent.core import rerank as RR
from life_agent.core import retrieval as RET
from life_agent.core import synthesis as SYN
from life_agent.core import volatility as VOL
from life_agent.core.llm import LLMResult
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
    client: Any                          # instrument client — route / observe / subject
    profile: str                         # owner profile, loaded server-side (never over the wire)
    # the utility posterior's u_bar, SHAPED for one requested answer shape (r30, lazy
    # brain) — /utility reads the shape off the request; every other caller (e.g.
    # _build_membrane) fixes its own.
    u_bar: Callable[[str], dict[str, float]]
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
    # [§3.3 · BR-1] volatility overrides the route model's verdict (Q5's transcript
    # reads this choice; override-vs-combine is its open question).
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
    meter: list[float] = []
    obs, indeterminate = LK.observe_hits(
        deps.root, _req_str(p, "question"), _req_list(p, "hits"),
        client=deps.client, covariates=cov,
        time_indexed=bool(p.get("time_indexed", False)), today=_opt_date(p.get("today")),
        half_life_years=hl, meter=meter)
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
            "indeterminate": indeterminate, "era_split": es, "half_life_years": hl,
            # §4.2's competition term, disclosed for the View + decision record: how many
            # grounded observations carry a same-shape competitor in their quote window
            "n_competing": sum(1 for o in obs if o.n_competing),
            # realised cache-miss model spend (the instruments are cloud-priced since the
            # Ollama deprecation — the gate's spend term must see it; warm replays are $0)
            "cost_usd": sum(meter)}


def _probe_recency(deps: BridgeDeps, p: Payload) -> Payload:
    return {"doc_date": P.probe_recency(deps.conn, deps.root, _req_list(p, "hit_keys"))}


def _probe_subject(deps: BridgeDeps, p: Payload) -> Payload:
    meter: list[float] = []
    state = P.probe_subject(
        deps.conn, deps.root, _req_list(p, "hit_keys"),
        profile=deps.profile, client=deps.client, meter=meter)
    return {"subject_state": state, "cost_usd": sum(meter)}


def _probe_authority(_deps: BridgeDeps, p: Payload) -> Payload:
    auth = P.probe_authority(_req_list(p, "hits"))
    return {"authority": {k: [klass, value] for k, (klass, value) in auth.items()}}


def _competing_value_shape(value: str, candidate: str) -> bool:
    """True when the re-read text carries a numeric span OUTSIDE the contained candidate
    whose shape matches one of the candidate's own — the signature of a correction-shaped
    read ("…PL-900001 was renewed; the new number is PL-800002") that mentions the stale
    value while naming a same-shaped successor. Containment alone would confirm the
    superseded value at the tier's trusted rho (a manufactured confident-wrong, the
    review's reproduced case). Adjacent facts of a DIFFERENT shape (an expiry date's
    2- and 4-digit spans beside a 6-digit id) stay confirmable — the q-011 confirming
    sentence keeps its fix. Digit-free values have no shape signature and never trip this
    (a prose correction of a word answer is out of this heuristic's reach — accepted).
    Delegates to the shared span detector (``matching.competing_value_count``, the §4.2
    competition term): spans keep comma-grouped figures whole, so "$1,234,567" is one
    7-digit shape here instead of three comma-split fragments."""
    return MATCH.competing_value_count(candidate, value) > 0


_PARTIAL_DATE = re.compile(r"^(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?$")


def _normalize_date_iso(v: str | None) -> str | None:
    """The instrument's self-reported ``as_of`` arrives as free text: a partial date
    ('2012', '2012-07') normalizes to the EARLIEST point of its stated period (maximal
    age ⇒ maximal decay — the keystone: a re-read value must never enter fresher than
    stated); a datetime-shaped or compact-ISO report keeps its full date (degrading it
    to the flat unknown attenuation would let an OLD stated date enter fresher than its
    true decay — the same keystone, from the other side); anything unparseable is None
    (the stated unknown-date attenuation), never a crash."""
    if v is None:
        return None
    s = v.strip()
    m = _PARTIAL_DATE.match(s)
    if m is None:
        try:
            return datetime.fromisoformat(s).date().isoformat()
        except ValueError:
            return None
    try:
        return date(int(m.group(1)), int(m.group(2) or 1), int(m.group(3) or 1)).isoformat()
    except ValueError:
        return None


def _source_time_factor(value: str | None, as_of: str | None, hits: list[Payload],
                        p: Payload) -> float:
    """The recency covariate for a re-read/whole-question observation — the construct's
    volatility decay, the same projection `/extract` applies (`LK.time_factor`). Recency is a
    document property, independent of WHOSE value it is, so the value is as current as its
    freshest SOURCE attestation: take the max doc_date among the hits whose text actually contains
    the value (the shared date-aware matcher), falling back to the instrument's self-reported
    `as_of` (normalized via `_normalize_date_iso` — free text, never trusted as clean ISO), then
    to None (undated time-indexed ⇒ the stated `_A_TIME_UNKNOWN` attenuation). A non
    time-indexed construct passes through at 1.0 (no decay)."""
    if not bool(p.get("time_indexed", False)):
        return 1.0
    hl = VOL.half_life(p.get("construct"))
    doc_date = dict((p.get("covariates") or {}).get("doc_date") or {})
    src_dates = [doc_date.get(h["artifact_cache_key"]) for h in hits
                 if MATCH.answer_matches(value or "", [], str(h.get("chunk_text", "")))]
    # D-14's one date-selection (LK.source_date_iso) — the ≻-chain is declared there.
    date_iso = LK.source_date_iso(src_dates, _normalize_date_iso(as_of))
    return LK.time_factor(date_iso, time_indexed=True, today=_opt_date(p.get("today")),
                          half_life_years=hl)


def _corroborate_time_factor(jr: JE.JointResult, hits: list[Payload], p: Payload) -> float:
    return _source_time_factor(jr.value, jr.as_of, hits, p)


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
        # Why the empty channel came back, so the body can tell absence of evidence from
        # evidence of absence (§14, 2026-08-18). `null` = the joint named NO value — a
        # lossy whole-document read over 400-char snippets declining to answer, which
        # says nothing about the per-chunk observations already grounded. `disagree` =
        # it named a value that would not join the lattice (outside the set, ambiguous
        # containment, or correction-shaped) — that IS evidence against the leader and
        # keeps run 7's disagree⇒abstain contract. `confirm` = it joined.
        read = "null"
        if jr.value is not None:
            read = "disagree"
            # THE value-join (D-11, one declaration — see _lattice_join for the full
            # confirm/correct/mint contract; the re-extract GROW actuator rides its
            # allow_new arm: an outside-set value ENLARGES K, indexed at
            # len(candidates), and the body appends it and re-decides).
            idx, new_candidate = _lattice_join(jr.value, candidates,
                                               bool(p.get("allow_new")))
            if idx is not None:
                # The keystone: the re-read obs flows through the SAME volatility projector
                # /extract uses — no transform may hand-set time_factor=1.0 and report a stale
                # value as current (the q-006 confident-stale bug that gated §2-A off). Recency is
                # attribution-independent (a document property), so the re-read value is as current
                # as its freshest SOURCE attestation. Ditto competition (§4.2/§2 lineage): a
                # re-read of the same competed row inherits the candidate's base factor —
                # the body posts it; a minted candidate (idx == len) reads 1.0.
                obs = [_joined_observation(
                    idx, candidates, new_candidate,
                    time_factor=_corroborate_time_factor(jr, hits, p),
                    competition_factor=_candidate_competition(p, idx))]
                read = "confirm"
        # the read's own stated confidence rides beside the tier rho: the k=0 strong rescue
        # conditions at min(tier, confidence), so the wire never discards the instrument's
        # uncertainty (a lone unsupported read must not enter at the tier's flat prior).
        # meter the re-read (PR #67 review): tier firings are real billed calls — the
        # gate's spend term must price them, or the typed arm's tier spend rides at $0
        # while the replay arm is fully priced. A §18.9 warm replay has zero tokens ⇒
        # $0 exactly; served_model falls back to the requested pin for pricing.
        priced = PRICING.cost_usd(LLMResult(
            text="", in_tokens=jr.in_tokens, out_tokens=jr.out_tokens, seconds=0.0,
            served_model=jr.served_model or model))
        # r09 D2 — the §5-deduped JOIN: a caller that hands its standing channel gets the
        # POOLED set back (a disagree or null read pools nothing and the channel survives —
        # run 7's disagree⇒abstain contract is retired by the ruling's fix); a caller with
        # no channel keeps the pre-r09 contract verbatim.
        channel = list(p.get("observations") or [])
        obs = _cap_synthesised_covariates(obs, channel)   # r09c A2, before the join
        if channel:
            joined_cands = (candidates if new_candidate is None
                            else [*candidates, new_candidate])
            obs = join_wire_observations(channel, obs, joined_cands)
        out: Payload = {"observations": obs, "gather_rho": tier_rho, "value": jr.value,
                        "confidence": jr.confidence, "cache_key": jr.cache_key,
                        "read": read,
                        "cost_usd": 0.0 if priced is None else priced,
                        "served_model": jr.served_model, "tokens": jr.in_tokens + jr.out_tokens}
        if new_candidate is not None:
            out["new_candidate"] = new_candidate
        return out
    hits = P.probe_corroborate(
        deps.conn, question, _req_str(p, "leader_value"),
        k=int(p.get("k", _DEFAULT_K)), exclude_keys=list(p.get("exclude_keys") or ()))
    return {"hits": hits}


# The confirm probe's per-question chunk budget (spend bound, first-in-hit-order).
# Provisional pending the off-gate corroborate audit's frozen m (§14 confirm_indep).
_CONFIRM_M = 2


def _independent_confirms(base: list[LK.Observation],
                          confirms: list[LK.Observation]) -> list[LK.Observation]:
    """Keep only confirms that are independent witnesses of the base channel (§5
    dedup-as-inference at the ONE seam): a confirm whose contextful quote duplicates a
    base observation's quote is a forwarded/re-filed copy — correlated, dropped — and
    the check is direction-blind (kept iff ``dedup_correlated`` over base+confirm
    leaves EVERY observation standing; a confirm that would displace a base witness is
    equally a copy). The base channel itself is never modified here (one-sided probe).
    Mutual duplicates among the confirms then collapse the ordinary way."""
    kept = []
    for c in confirms:
        surviving = {id(o) for o in LK.dedup_correlated([*base, c])}
        if id(c) in surviving and all(id(b) in surviving for b in base):
            kept.append(c)
    return LK.dedup_correlated(kept)


def _probe_confirm(deps: BridgeDeps, p: Payload) -> Payload:
    """Value-targeted INDEPENDENT-document confirmation (§14 confirm_indep): unlike the
    reextract corroborate (a same-hits whole-doc re-read that REPLACES the channel),
    this asks whether a chunk from an artifact NOT already supporting the target states
    the target as the current answer — each grounded yes is one more observation the
    body APPENDS (a genuinely new ancestry group, or the rival artifact's existing
    one). Independence is computed here, where hits and the raw observations coexist:
    the base channel is a warm content-addressed ``observe_hits`` replay ($0 when the
    executor's /extract just ran), which also reproduces the exact wire group order
    ``to_abstract_observations`` gave the executor. The confirm observation's
    competition factor is its OWN quote window's (§2: competition is a property of the
    corpus row) — deliberately NOT ``_candidate_competition`` inheritance, which is for
    same-ancestry re-reads."""
    question = _req_str(p, "question")
    value = _req_str(p, "value").strip()
    hits = _req_list(p, "hits")
    candidates = [str(c) for c in (p.get("candidates") or [])]
    vkey = LK._candidate_key(value)
    reports = next((j for j, c in enumerate(candidates)
                    if LK._candidate_key(c) == vkey), None)
    empty: Payload = {"observations": [], "value": value, "cost_usd": 0.0,
                      "n_prefilter": 0, "n_grounded": 0, "n_indeterminate": 0,
                      "n_correlated_dropped": 0, "n_base_groups": 0}
    if reports is None:
        # the target must already be on the lattice (the daemon steered at it) — the
        # confirm probe never mints candidates and never spends on an unknown target
        return empty
    cov = _covariates(p.get("covariates") or {})
    hl = VOL.half_life(p.get("construct"))
    time_indexed = bool(p.get("time_indexed", False))
    today = _opt_date(p.get("today"))
    meter: list[float] = []
    base_obs, _ = LK.observe_hits(
        deps.root, question, hits, client=deps.client, covariates=cov,
        time_indexed=time_indexed, today=today, half_life_years=hl, meter=meter)
    supporters = {o.artifact_cache_key for o in base_obs
                  if LK._candidate_key(o.value_raw) == vkey}
    n_prefilter = len(LK.confirm_prefilter(value, hits, supporters))
    confirms, indeterminate = LK.confirm_hits(
        deps.root, question, value, hits, exclude_artifacts=supporters,
        client=deps.client, covariates=cov, time_indexed=time_indexed, today=today,
        half_life_years=hl, m=int(p.get("m", _CONFIRM_M)), meter=meter)
    kept = _independent_confirms(base_obs, confirms)
    group_order: dict[str, int] = {}
    for o in base_obs:
        group_order.setdefault(o.artifact_cache_key, len(group_order))
    n_base_groups = len(group_order)
    obs: list[Payload] = []
    for o in kept:
        g = group_order.setdefault(o.artifact_cache_key, len(group_order))
        obs.append({"reports": reports, "group": g, "authority": o.authority,
                    "subject_factor": o.subject_factor, "time_factor": o.time_factor,
                    "competition_factor": o.competition_factor})
    return {"observations": obs, "value": value, "cost_usd": sum(meter),
            "cache_keys": [o.obs_cache_key for o in kept],
            "n_prefilter": n_prefilter, "n_grounded": len(confirms),
            "n_indeterminate": indeterminate,
            "n_correlated_dropped": len(confirms) - len(kept),
            "n_base_groups": n_base_groups}


def _deliberate_cfg() -> DL.DeliberateConfig:
    """The deliberative edge's server-side config: the claude CLI from the env (the same
    provenance caveat as the eval arm — the machine's Claude Code config is part of the
    reference policy), scratch under the KB (transient, never the ledger)."""
    # The SAME resolution the rest of the bridge uses (config.PKM_CONFIG: the env, else
    # ~/.config/life-agent/pkm.yaml) — run 6 (2026-08-17) read the raw env here, got ""
    # with PKM_CONFIG unset, and handed the claude CLI an MCP server command of
    # `pkm --config "" serve`, which crashed: nine cold deliberates never touched the
    # corpus. A config that does not resolve to a file is refused loudly, up front.
    pkm_cfg = config.PKM_CONFIG
    if not pkm_cfg.is_file():
        raise RuntimeError(
            f"deliberate: PKM_CONFIG does not resolve to a file ({pkm_cfg}) — the pkm "
            f"MCP server cannot start; set PKM_CONFIG (see .env) before enabling the "
            f"deliberate edge")
    return DL.DeliberateConfig(
        claude_bin=os.environ.get("LIFE_AGENT_CLAUDE_BIN", "claude"),
        scratch_dir=config.KB / "tmp" / "deliberate",
        pkm_config=str(pkm_cfg),
    )


# --- r37: the value-join tap ------------------------------------------------------------
#
# r36 killed r34's lever on K3 because the census that enumerated its firing surface read
# RECORDED wire, so the surface was a lower bound rather than an enumeration. The tap makes
# the LIVE surface readable. It is OFF unless `LIFE_AGENT_JOIN_TAP` is set, and — the whole
# safety argument, pinned by tests/test_join_tap.py — **the decision is always the deployed
# predicate's, flag on or flag off**. The tap only computes what the DECLARED identity would
# have returned and writes the pair aside.

#: The one flag. Absence is the off state; there is no config file and no default-on path.
_JOIN_TAP_ENV = "LIFE_AGENT_JOIN_TAP"

#: (url, question) for the request in flight, set once by :func:`dispatch`. The join itself
#: is several frames below the handler and has no question; a per-handler wiring would be a
#: second declaration of the same context, so the dispatcher is its one home. The row keys on
#: ``DEC.question_id`` — the ONE derivation of a question's identity — so the live surface and
#: the recorded one align without a second hash. (The tap first grew its own sha256; the
#: drift gate in tests/test_decisions.py caught it, which is what that gate is for.)
_TAP_CONTEXT: ContextVar[tuple[str, str]] = ContextVar("_TAP_CONTEXT", default=("", ""))


def _tap_context(path: str, payload: Payload) -> None:
    """Publish the in-flight request to the tap. Cheap and unconditional: the flag is read
    at the write, so arming the tap never depends on when this ran."""
    _TAP_CONTEXT.set((path, str(payload.get("question") or "")))


def _join_tap(value: str, candidates: list[str], allow_new: bool,
              deployed: tuple[int | None, str | None]) -> None:
    """Record one value-join call: the deployed verdict beside the counterfactual the
    RETIRED `_norm_value` identity would have given (r38 flipped which side is deployed;
    the disagreement measured is the same one). Never raises — a diagnostic that can take the
    decide path down is not a diagnostic — and never decides.

    The counterfactual re-runs :func:`_lattice_join` under the other key rather than
    re-implementing its rule: `M-7` is the standing lesson at five instances, and its
    signature is exactly an instrument that prices a constant it re-spelled itself.

    The stream is unfoldable by construction (`M-14`): no ``decision_id``, no credence, no
    writer into the calibration path. Non-firings are recorded too — a log of firings alone
    has no denominator, and `G-3` requires an instrument to name the universe it checked."""
    if not os.environ.get(_JOIN_TAP_ENV):
        return
    try:
        c_idx, c_minted = _lattice_join(value, candidates, allow_new,
                                        key=LK._norm_value)
        url, question = _TAP_CONTEXT.get()
        row = {"question_id": DEC.question_id(question), "url": url,
               "fires": (c_idx, c_minted) != deployed,
               "allow_new": allow_new, "n_candidates": len(candidates),
               "value": value, "candidates": candidates,
               "deployed": {"idx": deployed[0], "minted": deployed[1]},
               "counterfactual": {"idx": c_idx, "minted": c_minted}}
        log = config.JOIN_TAP_LOG
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as fh:
            fh.write(dumps(row) + "\n")
    except Exception:
        return


def _lattice_join(value: str, candidates: list[str], allow_new: bool,
                  *, key: Callable[[str], str] = LK._candidate_key
                  ) -> tuple[int | None, str | None]:
    """[§3.3 · D-11/BR-2] (with L-4): THE value-join — the observation-equivalence rule
    mapping an instrument's bare value onto the candidate lattice, one declaration for
    both edges (corroborate and deliberate bind it). Returns ``(idx, new_candidate)``.

    Exact match on the identity ``key`` first. **The deployed identity is the DEFAULT
    argument** — since r38, ``LK._candidate_key``, the §4.2 declared key — and every call on
    the decision path takes it; ``key`` is parameterised only so the tap can ask what the
    RETIRED ``_norm_value`` identity would have returned, by re-running THIS rule instead of
    writing a second copy of it (`M-7`). A non-default ``key`` never reaches the argmax — it
    is the counterfactual arm, and the tap call below is gated on the default so the two
    cannot recurse.

    **The arc, because the shape of it constrains anyone who touches this line.** This site
    is M6's ONE declaration of the value-join, and until r38 it tested identity with
    ``_norm_value`` while `candidates_from`, `render`, `era_split`, the S2 grow join and the
    confirm probe all used ``_candidate_key`` — two declarations of one relation, numbered
    under different clauses, which is how it survived M6. r34 bound the declared key and r36
    REVERTED it, not because the merge was wrong (run 21 converted q2-027 from a split
    0.346+0.146 lattice to a correct report at 0.863) but on a K3 attribution kill; r37 then
    showed K3's baseline, not its surface, was the defect (`M-18`), and measured the lever's
    whole effect as ONE correct row — **below the wobble floor, so this ships as a defect
    repair and never on its row count** (`GD-8`). ``_candidate_key`` falls back to
    ``_norm_value``, so the binding is a monotone COARSENING: it merges more, never splits
    more, and it inherits rather than widens the confident-wrong boundary (values with
    different significant digits never merge). `_joined_observation` keeps ``_norm_value``
    deliberately — that is the §5 dedup key, a different relation, and a derivation-cache
    key component. Else unique token-boundary containment — the join
    must not read a CONFIRMING sentence as a disagreement (the q-011 pooling loss),
    but nor may it read a CORRECTING sentence as a confirmation: containment alone
    cannot tell confirm from correct-while-mentioning, so a competing same-shaped
    token beside the contained candidate (``_competing_value_shape``) or a
    name/digit-group extending it (``_superset_extension``, r09b T1) keeps the
    conservative no-observation contract. Else, ``allow_new`` mints the value as a
    candidate indexed at ``len(candidates)`` (the grow contract) — gated on ``not
    contained``: a read that MENTIONS a known candidate (ambiguous or
    correction-shaped) must not be minted wholesale, the sentence is not a value.
    Else no join."""
    vk = key(value)
    idx = next((i for i, c in enumerate(candidates) if key(c) == vk), None)
    out: tuple[int | None, str | None]
    if idx is not None:
        out = idx, None
    else:
        contained = [i for i, c in enumerate(candidates)
                     if MATCH.answer_matches(str(c), [], value)]
        if (len(contained) == 1
                and not _competing_value_shape(value, candidates[contained[0]])
                and not _superset_extension(value, candidates[contained[0]])):
            out = contained[0], None
        elif not contained and allow_new:
            out = len(candidates), value
        else:
            out = None, None
    if key is LK._candidate_key:   # the deployed call; the tap's own re-run must not recurse
        _join_tap(value, candidates, allow_new, out)
    return out


def _joined_observation(idx: int, candidates: list[str], new_candidate: str | None,
                        *, time_factor: float, competition_factor: float) -> Payload:
    """[§3.3 · BR-4] The ONE builder for a joined edge observation (D-11's output
    shape) — the re-read edge's fixed authority/subject covariates are declared model
    content (learnable). r09 D1's
    uniform wire keys on every observation — a synthesised read has no verbatim quote
    and no single source document (value-only, so §5 never clusters it; the join gives
    it its own fresh group). ``value_norm`` is the REPORTED candidate's normal form,
    never the raw sentence's: the observation asserts the candidate it joined (a
    minted candidate asserts itself)."""
    return {"reports": idx, "group": 0, "authority": 1.0, "subject_factor": 1.0,
            "time_factor": time_factor, "competition_factor": competition_factor,
            "quote": "", "doc_key": "",
            "value_norm": LK._norm_value(candidates[idx]) if idx < len(candidates)
            else LK._norm_value(str(new_candidate))}


def _candidate_competition(p: Payload, idx: int) -> float:
    """The candidate's inherited §4.2 competition factor, posted by the body as
    ``candidate_competition`` (aligned with ``candidates``; competition is a property of
    the corpus evidence, not the instrument — the §2 lineage rule: a whole-doc re-read of
    the same competed row shares the pick ambiguity). Absent, or a minted candidate
    beyond the list ⇒ the neutral 1.0."""
    comp = list(p.get("candidate_competition") or [])
    return float(comp[idx]) if 0 <= idx < len(comp) else 1.0


def _superset_extension(value: str, candidate: str) -> bool:
    """r09b T1 — the strict-span guard: True when the candidate's matched token span in
    ``value`` is NOT at an entity boundary — the token immediately adjacent (either side)
    has the same token class as the candidate's own tokens (name-shaped beside name tokens,
    digit-group beside digit tokens). The superset-confirm class: a shorter personal-name
    candidate inside a longer name must not be confirmed. Prose (lowercase function words,
    punctuation-only tokens) beside the span is not an extension. Checked on the FIRST
    token-level span; a value with no token-level span (a different match route) is left to
    the existing guards."""
    def _strip(tok: str) -> str:
        return tok.strip(".,;:()[]{}<>\"'")

    def _norm(tok: str) -> str:
        return _strip(tok).casefold()

    def _tclass(tok: str) -> str:
        t = _strip(tok)
        if any(c.isdigit() for c in t):
            return "digit"
        if t[:1].isupper() and t.replace("-", "").isalpha():
            return "name"
        return "other"

    vt = value.split()
    ct = [_norm(c) for c in candidate.split()]
    if not ct:
        return False
    cclasses = {_tclass(c) for c in candidate.split()} - {"other"}
    if not cclasses:
        return False
    for i in range(len(vt) - len(ct) + 1):
        if [_norm(x) for x in vt[i:i + len(ct)]] == ct:
            left = vt[i - 1] if i > 0 else None
            right = vt[i + len(ct)] if i + len(ct) < len(vt) else None
            return any(adj is not None and _tclass(adj) in cclasses
                       for adj in (left, right))
    return False


def _cap_synthesised_covariates(obs: list[Payload], channel: list[Payload]) -> list[Payload]:
    """r09c A2 — a re-read cannot outrank the channel it re-read: every synthesised
    observation's minted authority/subject is capped at the per-component max over the
    channel's doc-keyed rows for the SAME value_norm, else over all doc-keyed rows. A
    channel with no doc-keyed rows caps nothing (the k=0 rescue mints from zero by
    design — the S5 exemption). time_factor is untouched: it is already the caller's
    computed projection, never a minted constant."""
    keyed = [c for c in channel if str(c.get("doc_key") or "")]
    if not keyed:
        return obs
    out: list[Payload] = []
    for o in obs:
        if str(o.get("doc_key") or ""):
            out.append(o)
            continue
        same = [c for c in keyed
                if str(c.get("value_norm") or "") == str(o.get("value_norm") or "")] or keyed
        out.append({**o,
                    "authority": min(float(o.get("authority") or 0.0),
                                     max(float(c.get("authority") or 0.0) for c in same)),
                    "subject_factor": min(float(o.get("subject_factor") or 0.0),
                                          max(float(c.get("subject_factor") or 0.0)
                                              for c in same))})
    return out


def _join_deliberate_value(value: str | None, candidates: list[str], allow_new: bool,
                           *, time_factor: float = 1.0,
                           competition: list[float] | None = None,
                           ) -> tuple[list[Payload], str | None]:
    """Map the edge's bare ANSWER value onto the candidate lattice — the corroborate
    join's contract verbatim: exact normalised match, else unique containment without a
    competing same-shaped token, else (``allow_new``) a minted candidate indexed at
    ``len(candidates)``, else NO observation (ambiguity keeps the conservative
    no-observation contract). ``time_factor`` is the caller-computed
    :func:`_source_time_factor` — the keystone holds here too: on a time-indexed
    construct no transform may hand-set 1.0 and report a stale value as current
    (the q-006 class); the deliberate observation is as current as its freshest
    retrieved source attestation. The lattice mapping itself is D-11's ONE
    declaration (:func:`_lattice_join`); this wrapper only shapes the observation."""
    if value is None:
        return [], None
    idx, new_candidate = _lattice_join(value, candidates, allow_new)
    if idx is None:
        return [], None
    comp = list(competition or [])
    return [_joined_observation(
        idx, candidates, new_candidate, time_factor=time_factor,
        # the confirmed candidate's inherited §4.2 factor (a minted candidate's idx
        # is beyond the list ⇒ the neutral 1.0)
        competition_factor=float(comp[idx]) if idx < len(comp) else 1.0)], new_candidate


def _deliberate_joined(p: Payload, obs: list[Payload], candidates: list[str],
                       new_candidate: str | None) -> list[Payload]:
    """r09 D2 at the S3 edge: pool the caller's standing channel with the deliberate
    observation (the §5 rule, one spelling). An empty ok reply pools nothing, so the
    grounded channel survives — the empty-ok collapse is retired (pre-registration D3).
    A caller with no channel keeps the pre-r09 contract verbatim."""
    channel = list(p.get("observations") or [])
    if not channel:
        return obs
    obs = _cap_synthesised_covariates(obs, channel)   # r09c A2, before the join
    joined_cands = candidates if new_candidate is None else [*candidates, new_candidate]
    return join_wire_observations(channel, obs, joined_cands)


def _probe_deliberate(deps: BridgeDeps, p: Payload) -> Payload:
    """The promoted A1b edge as a scheduled transform: run (or warm-replay) one
    deliberative answer, join its bare value onto the candidate lattice, and return the
    observation beside the RAW self-reported credence — a signal the BODY folds through
    the per-edge calibration curve (Δ1); the bridge scores nothing. Keyed pre-call on
    (question, corpus digest); a warm hit replays at zero model calls; only status="ok"
    results (including declines — a warm NOT_IN_CORPUS is valid evidence) are recorded."""
    question = _req_str(p, "question")
    candidates = [str(c) for c in (p.get("candidates") or [])]
    allow_new = bool(p.get("allow_new"))
    hits = list(p.get("hits") or [])
    cfg = _deliberate_cfg()

    try:
        digest: str | None = CORPUS.corpus_digest(deps.conn)
    except Exception:
        digest = None  # caching off for this question — named, never silent
    key = (D.deliberate_key(question, digest, model=cfg.model,
                            prompt_template=DL.PROMPT_DELIB_V2,
                            max_turns=cfg.max_turns)
           if digest is not None else None)

    cached = D.lookup(deps.root, key.cache_key) if key is not None else None
    if key is not None and cached is not None:
        c = loads(cached.decode("utf-8"))
        obs, new_candidate = _join_deliberate_value(
            c.get("value"), candidates, allow_new,
            time_factor=_source_time_factor(c.get("value"), None, hits, p),
            competition=list(p.get("candidate_competition") or []))
        obs = _deliberate_joined(p, obs, candidates, new_candidate)
        out: Payload = {"observations": obs, "value": c.get("value"),
                        "confidence": c.get("credence"), "declined": c.get("declined"),
                        "status": "ok", "text": c.get("text"), "model": c.get("model"),
                        "cost_usd": 0.0, "latency_s": 0.0,
                        "cache": "hit", "cache_key": key.cache_key}
        if new_candidate is not None:
            out["new_candidate"] = new_candidate
        return out

    r = DL.answer(question, cfg)
    if r.status == "ok" and key is not None:
        try:
            DL.record_answer(deps.root, key, r)
        except Exception as e:  # a ledger write must never break an answered question
            print(f"  (deliberate answer not recorded: {e})")
    obs, new_candidate = _join_deliberate_value(
        r.value, candidates, allow_new,
        time_factor=_source_time_factor(r.value, None, hits, p),
        competition=list(p.get("candidate_competition") or []))
    # [§3.3 · BR-8] the edge's failure semantics: ok-only yields an observation.
    if r.status != "ok":
        obs, new_candidate = [], None
    else:
        obs = _deliberate_joined(p, obs, candidates, new_candidate)
    out = {"observations": obs, "value": r.value, "confidence": r.credence,
           "declined": r.declined, "status": r.status, "text": r.text,
           "model": r.model, "cost_usd": r.cost_usd, "latency_s": r.latency_s,
           "cache": "miss" if key is not None else "off"}
    if key is not None:  # the cell's §18.9 identity — the caller's warm-replay dedup key
        out["cache_key"] = key.cache_key
    if new_candidate is not None:
        out["new_candidate"] = new_candidate
    return out


def _utility(deps: BridgeDeps, p: Payload) -> Payload:
    # r30: the requesting question's own answer shape prices its own u_bar (C5) — the
    # SAME seam current_u_bar's other callers route through, reached here via an
    # optional query param so executor.run_pass's grow-menu pricing is shaped too.
    shape = str(p.get("shape") or AS.DEFAULT_SHAPE)
    return {"u_bar": deps.u_bar(shape)}


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


def _gate_support(deps: BridgeDeps, p: Payload) -> Payload:
    """The shadow's seam-gate feed (M2 advisory): `scripts/ask.py` mirrors each declared
    gate pre-emption (`core.seam.commit(None, gates=...)` — weak-retrieval / executor-down)
    here so the ledger can say how often the host abstained before any engine saw the
    question, and what the engine would have done instead. Same contract as
    `/decide-support`: disabled fast-path before any parsing; `submit_gate` is enqueue-only
    and never raises, the suppress is defense-in-depth."""
    if deps.membrane is None:
        return {"ok": False, "disabled": True}
    question_id = _req_str(p, "question_id")
    gate = _req_str(p, "gate")
    with contextlib.suppress(Exception):
        deps.membrane.submit_gate(question_id, gate)
    return {"ok": True}


#: [r33 RC-1] the ONE content-addressed decision-id rule — declared in
#: ``core.decisions.decision_id_for``; the bridge BINDS it (a second spelling cannot
#: exist — the miss recorder derives ids through the same declaration).
_decision_id = DEC.decision_id_for


def _req_float_list(d: Payload, key: str) -> list[float]:
    v = d.get(key)
    if not isinstance(v, list) or not v:
        raise BridgeError(400, f"decision.{key} must be a non-empty list")
    try:
        return [float(x) for x in v]
    except (TypeError, ValueError) as e:
        raise BridgeError(400, f"decision.{key} must be numbers: {e}") from e


def _regime_and_policy(decision: Payload) -> tuple[str, str, tuple[str, ...]]:
    """The two module-collapse fields (design §2.3, §3.1), with honest defaults.

    A caller that STATES the field is recorded verbatim; one that omits it is recorded at
    the declared default and named in ``defaulted`` — an assumption must never be readable
    as a statement (the §6.5 unavailability record turns on exactly that distinction). A
    value outside either closed vocabulary is a 400: the bridge refuses rather than writing
    a decision nothing can interpret.
    """
    defaulted: list[str] = []
    values: dict[str, str] = {}
    for name, vocabulary, default in (("regime", DEC.REGIMES, DEC.REGIME_DEFAULT),
                                      ("policy", DEC.POLICIES, DEC.POLICY_DEFAULT)):
        raw = decision.get(name)
        if raw is None:
            values[name] = default
            defaulted.append(name)
            continue
        if raw not in vocabulary:
            raise BridgeError(
                400, f"decision.{name} {raw!r} is not one of {sorted(vocabulary)}")
        values[name] = str(raw)
    return values["regime"], values["policy"], tuple(sorted(defaulted))


# Terminal brain actions (DEC.LOOKUP_ACTION_ORDER) each map to one logged lookup decision; the
# steer `gather` is enacted by the body internally (re-extract + re-decide) and is never a
# terminal decision, so /log_decision rejects it.
_TERMINAL_ACTIONS: frozenset[str] = frozenset(DEC.LOOKUP_ACTION_ORDER)


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
    order = DEC.leader_order(credences)   # D-4: the one leader label-view
    creds_sorted = [credences[j] for j in order]
    cands_sorted = ([candidates[j] for j in order]
                    if len(candidates) == len(credences) else candidates)

    decision_id = _decision_id(question, retrieval_keys, creds_sorted, p_none)
    cost_usd = decision.get("cost_usd")
    latency_s = decision.get("latency_s")
    regime, policy, defaulted = _regime_and_policy(decision)
    event = DEC.DecisionEvent(
        # the body may tag the run (the gate's executor arm — in-gate decisions must
        # not masquerade as live traffic); absent ⇒ the live default
        tx_time=O.now_iso(), run_id=str(decision.get("run_id") or "answer-brain"),
        question_id=DEC.question_id(question),
        family="lookup", action_set=DEC.LOOKUP_ACTION_ORDER,
        # n_indeterminate/n_competing: the record's replayability fix (§14, 2026-08-17 —
        # run 8's single-candidate commits were blind to in-chunk competition; a future
        # sweep must read it off the archive, not re-join chunks). Defaults stay honest
        # for callers predating the fields.
        posterior_summary={"candidates": cands_sorted, "credences": creds_sorted,
                           "p_none": p_none, "n_obs": n_obs,
                           "n_indeterminate": int(decision.get("n_indeterminate", 0)),
                           "n_competing": int(decision.get("n_competing", 0))},
        utility_fold_version=deps.fold_version(),
        chosen_action=action, predicted_eu=eu, decision_id=decision_id,
        # decisions v2 (§10 accounting): the answer-proposing edge + its realised price,
        # posted by the body when a priced transform fired; defaults stay honest.
        instrument=str(decision.get("instrument") or ""),
        cost_usd=float(cost_usd) if cost_usd is not None else None,
        latency_s=float(latency_s) if latency_s is not None else None,
        # v3 (module-collapse M0): the declared decision space + evidence policy this act
        # was ranked under, with the defaults NAMED when the caller stated neither
        regime=regime, policy=policy, defaulted=defaulted)
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
    t0 = time.monotonic()
    text, _key, _cached, s_cost = SYN.synthesize(deps.root, question, hits, deps.profile)
    s_latency = time.monotonic() - t0
    dates = P.probe_recency(deps.conn, deps.root,
                            list(dict.fromkeys(h["artifact_cache_key"] for h in hits)))
    cards = SYN.cards_from_hits(hits, dates)
    nv = NARR.narrative_answer(deps.root, question, text, cards,
                               cost_usd=s_cost, latency_s=s_latency,
                               instrument=SYN.INSTRUMENT)
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
    "/probe/confirm": _probe_confirm,
    "/probe/deliberate": _probe_deliberate,
    "/log_decision": _log_decision,
    "/log_reaction": _log_reaction,
    "/log_gather": _log_gather,
    "/decide-support": _decide_support,
    "/gate-support": _gate_support,
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
            route, _, query = path.partition("?")
            if route == "/ready":
                return 200, {"status": "ok", "membrane": _membrane_ready_block(deps)}
            handler = _GET.get(route)
            if handler is None:
                raise BridgeError(404, f"no GET endpoint {route!r}")
            # a GET query string is the same Payload-dict shape a POST body already gets
            # (r30: /utility?shape=<shape> — no new parsing machinery).
            params = {k: v[0] for k, v in parse_qs(query).items()}
            return 200, handler(deps, params)
        if method == "POST":
            handler = _POST.get(path)
            if handler is None:
                raise BridgeError(404, f"no POST endpoint {path!r}")
            payload = _parse_body(body)
            _tap_context(path, payload)     # r37: the tap's one context home
            return 200, handler(deps, payload)
        raise BridgeError(405, f"method {method!r} not allowed")
    except BridgeError as e:
        return e.status, {"error": e.message}


# --- the warm HTTP service -------------------------------------------------------------

class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _respond(self, status: int, payload: Payload | None) -> None:
        data = dumps(payload).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            # the caller timed out and hung up while a slow read (a /narrative
            # rerank+synthesize) was in flight — there is no one to answer, and an
            # exception escaping here on a keep-alive connection wedged the whole
            # single-threaded server (run-6 void, 2026-08-17). Drop the connection;
            # the next accept() must still be served.
            self.close_connection = True

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
            categorical=config.membrane_categorical(),
        )
        warm_vectors_dir = config.membrane_warm_vectors_dir()
        shadow = MEM.MembraneShadow(
            cfg, u_bar=u_bar,
            snapshot=lambda: MEM.boot_snapshot(
                config.DECISIONS_LOG, config.REACTIONS_LOG, warm_vectors_dir,
                claude_verdicts_path=config.CLAUDE_VERDICTS_LOG),
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

    def _u_bar(shape: str) -> dict[str, float]:
        u_bar, _version, _policy = LK.current_u_bar(LK.shared_brain(), shape=shape)
        return u_bar

    def _fold_version() -> str:
        # current_u_bar caches per fold version in-process, so this rides the /utility fold.
        _u_bar, version, _policy = LK.current_u_bar(LK.shared_brain())
        return version

    return BridgeDeps(root=root, conn=conn, client=LK._client(),
                      profile=owner.load_profile(), u_bar=_u_bar,
                      decisions_path=config.DECISIONS_LOG,
                      reactions_path=config.REACTIONS_LOG, fold_version=_fold_version,
                      gather_outcomes_path=config.GATHER_OUTCOMES_LOG,
                      # the membrane shadow is off the decision path (docstring above) and
                      # classifies nothing itself — fixed at the anchor shape, decoupled
                      # from whatever shape a live /utility request asks for.
                      membrane=_build_membrane(lambda: _u_bar(AS.DEFAULT_SHAPE)))


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
    print("  POST /gate-support     (membrane shadow seam-gate feed; no-op unless enabled)")
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
