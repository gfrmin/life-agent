"""The body's executor loop — enacts the credence answer-brain daemon's VOI schedule.

PRINCIPLES §16: there is one optimiser. The *decision* lives in the credence daemon
(``gather_decide`` / ``terminal_decide``) — it prices the per-question transform MENU by
``net_voi - cost`` and arg-maxes. This module is the **body** that enacts that schedule over
the life-agent capability bridge:

    route → retrieve → probe/{subject,recency} → extract → /decide

then, while the daemon returns ``gather`` (a scheduled transform), enact the named probe
(acknowledge recency, or re-read at the scheduled corroborate tier) and re-decide — until a
terminal effector. A cheap lexical pass runs first; a withholding terminal escalates recall
breadth once (``grow``: rerank, then native-script expansion).

Lifted verbatim from ``scripts/eval_executor.py`` so the eval harness AND the production
read-path drive the SAME executor, not two implementations (§4 compose, don't rebuild). The
two HTTP services are injected as ``post`` / ``get`` callables, so the whole control flow is
hermetically testable without a live daemon, and the caller owns the transport (urllib in the
eval harness; the same, or a pooled client, in production). The body holds NO posterior and
picks NO action; it only shapes evidence and enacts what the daemon scheduled.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from life_agent.bridge import observations as SO
from life_agent.core import calibration as CAL
from life_agent.core import decisions as DEC
from life_agent.core import deliberate as DL
from life_agent.core import gather_outcomes as GO
from life_agent.core import lookup as LK
from life_agent.core import matching as MATCH
from life_agent.core import pricing as PRC
from life_agent.core import seam as SEAM

# The per-edge reliability curves (calibration.fit_edge_curves over the outcomes log),
# injected by the caller. None (every legacy call site) keeps the declared constants —
# bit-identical behaviour; with curves, a read's self-stated confidence folds through
# curve_for (pessimistic cold start) instead of a flat cap.
Curves = dict[str, CAL.ReliabilityCurve] | None

# The transport seams, injected by the caller (PRINCIPLES §5): ``post(url, payload)`` returns the
# decoded JSON object, or ``None`` for ``/route`` on a non-typed question; ``get(url)`` returns the
# decoded JSON object. The loop builds the URLs from the ``bridge`` / ``daemon`` base strings, so a
# fake can route on the suffix.
Post = Callable[[str, dict[str, Any]], "dict[str, Any] | None"]
Get = Callable[[str], dict[str, Any]]

View = dict[str, Any]  # {effector, asserted, candidates, credences, p_none, eu, n_obs, hits,
#                        route}; a narrative view also carries "rendered" (rendered bridge-side).

# Every priced row below is a BINDING of the one price table (core/pricing — M4, r14):
# the ladder, the menu, the deliberate seed and the re-read model are declared there as
# data; this module enacts them. Same objects, so a second spelling cannot drift.
_TIER_MODEL = PRC.TIER_MODEL
_TIER_RHO = PRC.TIER_RHO
_GATHER_RHO = PRC.GATHER_RHO
DEFAULT_TRANSFORMS = PRC.DEFAULT_TRANSFORMS
_DELIBERATE_MODEL = PRC.DELIBERATE_MODEL
DELIBERATE_TRANSFORM = PRC.DELIBERATE_TRANSFORM
_DELIBERATE_FALLBACK_RHO = PRC.DELIBERATE_FALLBACK_RHO


def _null_read(reply: dict[str, Any]) -> bool:
    """True when a joint re-read NAMED NO VALUE — the absence-of-evidence case the body
    must not treat as a disagreement (§14, 2026-08-18).

    The bridge classifies its own empty channel as ``read``: ``null`` (named nothing),
    ``disagree`` (named a value that would not join the lattice — outside the set,
    ambiguously contained, or correction-shaped), or ``confirm``. A bridge predating
    the field reports no ``read`` at all, and this returns False — i.e. the OLD
    replace-everything behaviour, so a version-skewed pair degrades to the previously
    measured contract rather than to an unmeasured one."""
    return str(reply.get("read") or "") == "null"


def extract_edge(model: str) -> str:
    """The joint-read edge's attribution name — a binding of the one constructor
    (D-12: `decisions.edge_id`; the deliberate edge's `deliberate.instrument` is its
    sibling binding)."""
    return DEC.edge_id("extract", model)


def menu_transforms(curves: Curves) -> list[dict[str, Any]]:
    """The full voi menu with every row's rho re-priced through the same per-edge curve
    the body will condition at. Without curves — or for any edge the fold has no rows
    for (the regime is per-edge, `_conditioned_rho`) — the tiers keep their declared
    rho (legacy parity) and the deliberate row prices at the conservative cap — never
    the 0.92 seed by fiat. Priced-vs-enacted divergence is the C2 failure: the daemon buys
    a probe, the body folds it at a fraction of the priced reliability, and the spend
    converts nothing. HONESTY BOUND: with a FITTED (non-flat) curve this pricing is an
    UPPER-BOUND rule — the offer prices at curve(declared prior) while enactment folds
    at curve(actual self-report), which can be lower; exact pre-call identity is
    structurally impossible for a self-reporting instrument. The extract-tier writer
    now feeds these curves (every firing lands an eval_edge row via the view's
    edge_events stream); re-pricing at the curve's mean over the edge's observed
    confidence distribution — instead of curve(declared prior) — remains the named
    future refinement."""
    rows: list[dict[str, Any]] = []
    for t in DEFAULT_TRANSFORMS:
        if t["kind"] == "voi" and t["probe"] in _TIER_MODEL:
            edge = extract_edge(_TIER_MODEL[t["probe"]])
            rows.append({**t, "rho": _conditioned_rho(curves, edge, t["rho"], t["rho"])})
        else:
            rows.append(t)
    rows.append({**DELIBERATE_TRANSFORM,
                 "rho": _conditioned_rho(
                     curves, DL.instrument(_DELIBERATE_MODEL),
                     DELIBERATE_TRANSFORM["rho"], _DELIBERATE_FALLBACK_RHO)})
    return rows

# A withholding/miss terminal — the daemon declined to assert. It is the SENSOR condition for
# re-asking WITH the grow block (run_pass), never a body-side decision to grow (E-13/E-14, M1).
_WITHHOLD = frozenset({"miss", "abstain", "hedge", "ask_clarify"})

# The unpriced attribution defaults every no-edge View return site spreads — consumers
# INDEX these keys (never .get), so a new attribution key is ONE edit here plus the
# value-bearing terminal return, not N synchronized dict literals.
_UNPRICED_ATTRIBUTION: dict[str, Any] = {
    "instrument": "", "cost_usd": None, "latency_s": None,
    "instrument_value": None, "instrument_confidence": None,
    "instrument_lineage": None}

# The grow lane's retrieval actuators: probe name → the /retrieve recall flags its enactment
# re-runs the evidence build at. `re_extract_strong` is the third menu row (a whole-doc opus
# re-read with allow_new — the K-enlarging strong extractor); the menu itself is data
# (core/gather_outcomes.GROW_ACTUATORS, served by the bridge's /grow_menu).
_GROW_RETRIEVE = {"retrieve_rerank": (True, False), "retrieve_expand": (True, True)}
_RE_EXTRACT_MODEL = PRC.RE_EXTRACT_MODEL
# The k=0 rescue channel's reliability CAP — a stated wide prior (mean of the local
# extractor's own Beta(4,4), core/reliability.PRIORS), declared blind, NOT the tier's
# 0.95 and NOT the model's self-stated confidence: a lone strong read with zero local
# corroboration is an unmeasured instrument, and the first field run showed fiat trust
# asserting a true-but-vague read at 0.866 (q-015, graded wrong). Under this cap the
# rescue NAMES candidates (hedge — EU-positive under u_hedged vs silence) and earns
# assert-grade trust only through conditioned verdicts, exactly as the local channel
# did after its own 0.85-fiat prior was refuted.
_RESCUE_RHO = 0.5


def _conditioned_rho(curves: Curves, edge: str, confidence: Any, fallback: float) -> float:
    """Fold a read's self-stated confidence through the per-edge reliability curve
    (``edge`` is the attribution's one spelling — ``extract@<model>`` for the joint
    re-reads, ``deliberate.instrument(<model>)`` for the promoted arm). The regime
    boundary is PER-EDGE (§2: each edge declares its own error model, never pooled —
    evidence about deliberate@opus is not evidence about extract@haiku): ``curves=None``
    (every legacy call site) or an edge with no attributed rows returns the declared
    fallback — bit-identical to the constants; a global switch would have collapsed
    the whole corroborate ladder to the cold start the moment the first deliberate
    outcome landed, prod-wide and permanently. The extract-tier writer now earns the
    extract@ edges out: once rows accrue, the measured branch replaces the declared
    caps for EVERY call site sharing that edge string — including the k=0 rescue's
    blind-declared min(0.5, conf), earned out by corroborate-context evidence (a
    stated coarsening: edges pool per MODEL, not per calling context; split the
    namespace if rescue-context reliability measurably diverges). Within a MEASURED
    edge an ABSENT confidence folds at the curve's most pessimistic bin: no signal
    must never be trusted more than a stated one (letting silence keep the declared
    prior would invert the pessimism)."""
    if curves is None or edge not in curves:
        return float(fallback)
    c = 0.0 if confidence is None else max(0.0, float(confidence))
    return CAL.curve_for(curves, edge).calibrate(c)


def owner_scoped(question: str) -> bool:
    """A first-person possessive question ("my X") — the class whose-document can protect, so the
    daemon's ``owner_scoped`` slot may schedule the subject-aware corroborate guard."""
    return bool(re.search(r"\b(?:my|mine|the owner's)\b", question, re.IGNORECASE))


def _obj(post: Post, url: str, payload: dict[str, Any]) -> dict[str, Any]:
    """``post`` for endpoints that always answer a JSON object — every one but ``/route``,
    which can return null for a non-typed question (guarded at its one call site)."""
    out = post(url, payload)
    assert out is not None, f"{url} returned null"
    return out


def decide_via_loop(question: str, k: int, *, bridge: str, daemon: str, post: Post, get: Get,
                    transforms: list[dict[str, Any]] | None = None,
                    curves: Curves = None) -> View:
    """Drive one question through the live loop: route, then the daemon-priced pass.

    A declined route (``/route`` → null) is the NARRATIVE family — synthesize a cited answer,
    audit each claim, include only grounded + EU-positive claims; gate-safe by construction.

    A typed route runs :func:`run_pass`. Recall is DECIDED BY THE DAEMON — the loop ships the
    sensor buckets + the grow menu (bridge ``/grow_menu``: actuators with body-persisted warm
    counts) into ``/decide``, the daemon prices the grow argmax by the engine gather VOI
    (``grow_value`` over the structure-BMA ``g``), and the body enacts the named probe and logs
    the outcome (``/log_gather`` — the structure-observe stream). There is no body-side
    cascade and no ``p_none >= leader`` gate: P(NONE) enters only as a bucketed *sensor*
    (E-13/E-14 died at M1, and ``LIFE_AGENT_GROW_LANE`` retired with them — this is the lane).
    The M3 membrane live consult died at M5 (Q8): the daemon's decision is the act."""
    transforms = DEFAULT_TRANSFORMS if transforms is None else transforms
    route = post(f"{bridge}/route", {"question": question})
    if route is None:
        nv = _obj(post, f"{bridge}/narrative", {"question": question})
        return {"effector": nv["action"], "asserted": nv["asserted"], "candidates": [],
                "credences": [], "p_none": None, "eu": None, "n_obs": 0,
                "hits": nv.get("hits", []), "route": None, "rendered": nv.get("rendered"),
                "n_indeterminate": 0, "question": question,
                **_UNPRICED_ATTRIBUTION, "edge_events": [], "spend_usd": 0.0}
    return run_pass(question, k, route, bridge=bridge, daemon=daemon, post=post, get=get,
                    rerank=False, expand=False, transforms=transforms,
                    curves=curves)


def run_pass(question: str, k: int, route: dict[str, Any], *, bridge: str, daemon: str,
             post: Post, get: Get, rerank: bool, expand: bool = False,
             transforms: list[dict[str, Any]] | None = None,
             curves: Curves = None) -> View:
    """One retrieve→probe→extract→decide pass at a given recall breadth, enacting each
    scheduled transform the daemon returns. The daemon also prices the grow menu (recall
    actuators), and each enactment is logged to ``/log_gather``. Returns
    the normalized view ``{effector, asserted, candidates, credences, p_none, eu, hits, route}``."""
    transforms = DEFAULT_TRANSFORMS if transforms is None else transforms

    # the question's TOTAL metered spend — base instruments (subject/extract cache
    # misses, cloud-priced since the Ollama deprecation), tiers AND deliberate. The
    # gate's run-6 spend term reads THIS; an unmetered base call would ride at $0
    # while the replay arm is fully priced. (/route's cost is not wire-carried — its
    # null reply cannot carry a field; de minimis and cached, §14-disclosed.)
    spend_usd = 0.0

    def _evidence(rr: bool, ex: bool) -> tuple[list[dict[str, Any]], dict[str, Any],
                                               dict[str, Any]]:
        nonlocal spend_usd
        hits = _obj(post, f"{bridge}/retrieve",
                    {"question": question, "k": k, "rerank": rr, "expand": ex})["hits"]
        hit_keys = list(dict.fromkeys(h["artifact_cache_key"] for h in hits))
        subj_reply = _obj(post, f"{bridge}/probe/subject", {"hit_keys": hit_keys})
        subj = subj_reply["subject_state"]
        spend_usd += float(subj_reply.get("cost_usd") or 0.0)
        recency = _obj(post, f"{bridge}/probe/recency", {"hit_keys": hit_keys})["doc_date"]
        # construct ⇒ the bridge decays time_factor at its volatility half-life
        ext = _obj(post, f"{bridge}/extract", {
            "question": question, "hits": hits, "time_indexed": route["time_indexed"],
            "construct": route["construct"],
            "covariates": {"subject_state": subj, "doc_date": recency}})
        spend_usd += float(ext.get("cost_usd") or 0.0)
        return hits, recency, ext

    hits, recency, ext = _evidence(rerank, expand)
    menu = get(f"{bridge}/grow_menu")["grow"]
    # (probe, sensors-at-scheduling, evidence-changed) per enacted grow — logged at the terminal.
    enacted: list[tuple[str, dict[str, str], bool]] = []

    def _log_outcomes(final_effector: str) -> None:
        # recovered = this enactment grounded evidence AND the question ended in a report through
        # the exact 0-CW terminal threshold — the honest v0 proxy (gather_outcomes docstring); a g
        # learned from it can at worst over-try gathers, never mis-report. Fail-open by contract
        # (as /log_decision is): an instrumentation write never breaks an already-decided answer.
        for probe, sensors, changed in enacted:
            try:
                post(f"{bridge}/log_gather", {"probe": probe, "sensors": sensors,
                                              "recovered": bool(changed
                                                                and final_effector == "report")})
            except Exception as e:
                print(f"  (gather outcome not logged: {e})")

    # the attribution stream — one event per answer-proposing firing, in firing order.
    # The gate's writer grades each event's OWN raw proposal against gold, so the extract
    # tiers' curves accrue evidence too (not just deliberate's). Edges key on the
    # REQUESTED model: decide-time conditioning looks up extract_edge(requested), and
    # served_model is "" on §18.9 warm replays — stamping it would split the namespace.
    edge_events: list[dict[str, Any]] = []

    def _edge_event(edge: str, reply: dict[str, Any]) -> None:
        nonlocal spend_usd
        if "cache_key" not in reply:
            # a version-skewed bridge (predating the cache_key wire field) yields
            # lineage-less rows that dedup KEEPS by design — warm replays would then
            # double-count into the curves on every gate run. Loud, never silent.
            print(f"  ({edge} reply carried no cache_key — bridge version skew? "
                  "lineage-less rows re-grade on every warm replay)")
        spend_usd += float(reply.get("cost_usd") or 0.0)
        v = reply.get("value")
        edge_events.append({"edge": edge, "value": str(v) if v is not None else None,
                            "confidence": reply.get("confidence"),
                            "lineage": reply.get("cache_key")})

    applied: list[str] = []
    if not ext["candidates"] and menu is not None:
        # The k=0 degenerate case: nothing extracted ⇒ there is no candidate posterior to price
        # against (the daemon requires k ≥ 1), so the body walks the menu cheapest-first (menu
        # order) until candidates ground — the one place enactment order is body-held; every
        # enactment is still logged, so the counts teach g here too. Each walked probe is
        # APPLIED (the daemon must not re-offer it later in this pass — one outcome row per
        # enacted grow, never a double count). The walk's last rung is the strong re-extract
        # with allow_new: it MINTS a candidate from zero (the q-005 class — a chunk the local
        # edge cannot read at all), handing the decision straight back to the daemon at k ≥ 1.
        # Its decide conditions at min(tier rho, the read's own stated confidence): a lone
        # strong observation with no local support must not enter at the corroboration tier's
        # flat prior (measured: that asserted a 0.55-confident read at credence 0.995).
        sensors0 = GO.sensors_from(candidates=[], credences=[], p_none=None,
                                   indeterminate=int(ext.get("indeterminate") or 0))
        for actuator in menu["actuators"]:
            g_probe = str(actuator["probe"])
            if g_probe in _GROW_RETRIEVE:
                rr, ex = _GROW_RETRIEVE[g_probe]
                hits, recency, ext = _evidence(rr, ex)
                enacted.append((g_probe, sensors0, bool(ext["candidates"])))
                applied.append(g_probe)
                if ext["candidates"]:
                    break
            elif g_probe == "re_extract_strong" and hits:
                cr = _obj(post, f"{bridge}/probe/corroborate",
                          {"reextract": True, "allow_new": True, "question": question,
                           "observations": ext["observations"],
                           "hits": hits, "candidates": [], "model": _RE_EXTRACT_MODEL,
                           "rho": _GATHER_RHO,
                           "time_indexed": route["time_indexed"],
                           "construct": route["construct"],
                           "covariates": {"doc_date": recency}})
                _edge_event(extract_edge(_RE_EXTRACT_MODEL), cr)
                minted = bool(cr.get("new_candidate"))
                enacted.append((g_probe, sensors0, minted))
                applied.append(g_probe)
                if minted:
                    conf = cr.get("confidence")
                    legacy = (min(_RESCUE_RHO, max(0.0, float(conf)))
                              if conf is not None else _RESCUE_RHO)
                    rescue_rho = _conditioned_rho(
                        curves, extract_edge(_RE_EXTRACT_MODEL), conf, legacy)
                    ext = {"candidates": [str(cr["new_candidate"])],
                           "observations": cr["observations"], "rho": rescue_rho,
                           "era_split": False,
                           "indeterminate": ext.get("indeterminate", 0)}
                    break
    if not ext["candidates"]:
        # The wire's ENACTMENT CONSTRAINT, not a host decision (r15 A1): the daemon's
        # /decide hard-errors on empty candidates (server.jl: k >= 1 — verified), so a
        # k=0 state has no ranking to be inside of. Mechanics, the same logic as §6.5.
        _log_outcomes("miss")
        return {"effector": "miss", "asserted": [], "candidates": [], "credences": [],
                "p_none": None, "eu": None, "n_obs": 0, "hits": hits, "route": route,
                "n_indeterminate": int(ext.get("indeterminate", 0) or 0),
                "n_competing": int(ext.get("n_competing", 0) or 0),
                **_UNPRICED_ATTRIBUTION, "edge_events": edge_events,
                "spend_usd": spend_usd}
    u_bar = get(f"{bridge}/utility")["u_bar"]
    # price the menu in the OWNER'S utility (plan item C): transform rows and grow
    # actuators are AUTHORED in USD; the elicited exchange rate (lambda_usd, gauge
    # units per dollar — a learned latent, never a constant invented here) converts
    # them at the one place the daemon reads prices. A u_bar lacking the latent
    # (pre-elicitation prod) prices at the legacy $1 ≈ 1-gauge convention, unchanged.
    rate = float(u_bar["lambda_usd"])  # REQUIRED latent — a missing one fails loud (E-5)
    transforms = [dict(t, cost=float(t["cost"]) * rate) if "cost" in t else t
                  for t in transforms]
    if menu is not None:
        menu = {**menu, "actuators": [dict(a, cost=float(a["cost"]) * rate)
                                      if "cost" in a else a
                                      for a in menu["actuators"]]}
    candidates = ext["candidates"]
    owner = owner_scoped(question)
    obs, rho, era = ext["observations"], ext["rho"], ext["era_split"]

    def _cand_comp(extraction: dict[str, Any], cands: list[str]) -> list[float]:
        # §4.2: competition is a property of the corpus evidence, not the instrument — a
        # whole-doc re-read of the same competed row inherits the candidate's base factor
        # (the §2 lineage rule: same evidence ancestry ⇒ correlated pick error). A
        # candidate with no base observation (minted later) reads 1.0.
        base = list(extraction.get("observations") or [])
        return [min([float(o.get("competition_factor", 1.0))
                     for o in base if int(o.get("reports", -1)) == j] or [1.0])
                for j in range(len(cands))]

    cand_comp = _cand_comp(ext, candidates)

    def _decide(observations: list[Any], r: float, era_split: bool, applied: list[str],
                sensors: dict[str, str] | None = None) -> View:
        payload: dict[str, Any] = {
            # r09 D1: the correlation key (quote, doc_key) is wire-only — the brain stays
            # string-blind, so the decide post strips it while the loop's channel keeps it
            "candidates": candidates, "observations": SO.strip_wire_keys(observations),
            "rho": r, "u_bar": u_bar,
            "era_split": era_split, "owner_scoped": owner, "applied_probes": applied,
            "transforms": transforms}
        if sensors is not None and menu is not None:
            payload["sensors"] = sensors
            payload["grow"] = menu
        # committed through the ONE act seam (roadmap M0); the reply view is the
        # daemon's decision verbatim.
        dec = SEAM.commit(SEAM.DaemonDecide(post=post, daemon=daemon,
                                            payload=payload)).view
        assert dec is not None  # a DaemonDecide commit always carries the reply view
        return dec

    dec = _decide(obs, rho, era, applied)
    grow_probes = ({str(a["probe"]) for a in menu["actuators"]} if menu is not None else set())
    grow_asked = False
    last_sensors: dict[str, str] = {}
    # §10 accounting for the terminal decision (decisions v2): the answer-proposing edge
    # that fired this pass and its realised price — "" / None when only the local channel ran.
    edge_instrument = ""
    edge_cost: float | None = None
    edge_latency: float | None = None
    # the edge's RAW proposal + self-report + §18.9 lineage — what the attributed-outcome
    # writer grades against gold, independent of the committed act.
    edge_value: str | None = None
    edge_conf: float | None = None
    edge_lineage: str | None = None
    # bounded: each registry probe and each grow actuator fires at most once (dedup on the
    # probe name); a grow costs two decides (the priced re-ask + the post-enactment decide).
    for _ in range(2 + sum(t["kind"] == "voi" for t in transforms) + 2 * len(grow_probes)):
        eff, probe = dec["effector"], str(dec.get("probe") or "")
        if eff == "gather" and probe == "recency":
            # recency is PRE-APPLIED in /extract (obs already decayed) → acknowledge and re-decide.
            applied = list(dict.fromkeys([*applied, "recency"]))
            dec = _decide(obs, rho, era, applied)
        elif eff == "gather" and probe.startswith("corroborate"):
            # a subject-aware whole-doc re-read at the scheduled TIER's model, JOINED onto the
            # standing channel bridge-side (r09: the payload carries the channel; the reply is
            # the §5-deduped pool, so a disagree adds evidence instead of erasing). Each tier
            # fires at most once (dedup on the probe name) ⇒ escalation across tiers terminates.
            model = _TIER_MODEL.get(probe, _RE_EXTRACT_MODEL)  # the table's strong-read model
            tier_rho = _TIER_RHO.get(probe, _GATHER_RHO)
            cr = _obj(post, f"{bridge}/probe/corroborate",
                      {"reextract": True, "question": question, "hits": hits,
                       # r09 D2: the standing channel rides the payload so the bridge
                       # computes the §5-deduped JOIN where the deployed rule lives
                       "observations": obs,
                       "candidates": candidates, "model": model, "rho": tier_rho,
                       "candidate_competition": cand_comp,
                       # the re-read obs flows through the construct's volatility (the keystone):
                       # pass time_indexed + construct + doc_date so a stale re-read decays.
                       "time_indexed": route["time_indexed"], "construct": route["construct"],
                       "covariates": {"doc_date": recency}})
            _edge_event(extract_edge(model), cr)
            if _null_read(cr):
                # §14 (2026-08-18): the joint NAMED NOTHING. A lossy whole-document read
                # over 400-char snippets declining to answer is absence of evidence, not
                # evidence against the per-chunk channel already grounded — so retire the
                # probe fail-open and keep the posterior (the same treatment the
                # deliberate branch already gives an infrastructure failure below).
                # Erasing here collapsed 12 of run 9's 69 withholdings to the flat prior
                # with the gold still on the lattice. A DISAGREEING read is untouched.
                applied = list(dict.fromkeys([*applied, probe]))
                dec = _decide(obs, rho, era, applied)
            else:
                # with curves, the read's own stated confidence conditions through the
                # edge's calibration curve — the instrument's uncertainty is no longer
                # discarded on the regular tiers (rescue-path parity); without curves the
                # tier rho echoes.
                obs, era = cr["observations"], False
                rho = _conditioned_rho(curves, extract_edge(model), cr.get("confidence"),
                                       cr["gather_rho"])
                applied = list(dict.fromkeys([*applied, probe]))
                dec = _decide(obs, rho, era, applied)
        elif eff == "gather" and probe in _GROW_RETRIEVE:
            # [§3.3 · E-10] a DAEMON-SCHEDULED retrieval grow: rebuild the evidence at
            # the named breadth and adopt it iff it grounded candidates (L-1 applied; else
            # the prior evidence stands and the probe is simply retired — a fruitless
            # recall must not erase a posterior).
            rr, ex = _GROW_RETRIEVE[probe]
            n_hits, n_recency, n_ext = _evidence(rr, ex)
            changed = bool(n_ext["candidates"])
            if changed:
                # r09d D3 — S2 JOINS (the one replace site r09 left untouched). The standing
                # channel keeps its candidate indices, the grow's new values are appended, and
                # the pooled set goes through THE §5 rule (``join_wire_observations`` — called,
                # never re-implemented). A grow ADDS evidence; it must not discard a channel.
                # r09c measured the cost of replacing here: seven rows shrank at this site and
                # on two a five-observation channel became one, taking a correct leader under
                # the report bar with it.
                joined = list(candidates)
                slots = {LK._candidate_key(c): j for j, c in enumerate(joined)}
                remap: dict[int, int] = {}
                for j, c in enumerate(n_ext["candidates"]):
                    key = LK._candidate_key(c)
                    if key not in slots:
                        slots[key] = len(joined)
                        joined.append(c)
                    remap[j] = slots[key]
                grown = [{**o, "reports": remap.get(int(o.get("reports", -1)), 0)}
                         for o in (n_ext["observations"] or [])]
                obs = SO.join_wire_observations(obs, grown, joined)
                hits, recency, ext = n_hits, n_recency, n_ext
                # competition is a property of the evidence (§4.2), so the joined lattice
                # keeps the MOST conservative factor either build detected for a candidate.
                grown_comp = _cand_comp({**n_ext, "observations": grown}, joined)
                cand_comp = [min(g, cand_comp[j] if j < len(cand_comp) else 1.0)
                             for j, g in enumerate(grown_comp)]
                candidates = joined
                rho, era = ext["rho"], ext["era_split"]
            enacted.append((probe, last_sensors, changed))
            applied = list(dict.fromkeys([*applied, probe]))
            grow_asked = False
            dec = _decide(obs, rho, era, applied)
        elif eff == "gather" and probe == "deliberate":
            # The promoted A1b edge, daemon-scheduled: an agentic deliberative answer
            # over the corpus (bridge /probe/deliberate — warm-replayed when the corpus
            # is unchanged). Its bare ANSWER value is joined bridge-side; a new value
            # comes back as a minted candidate (allow_new — the edge exists FOR the
            # questions the local channel can't ground). On a SUCCESSFUL call the reply
            # is the §5-deduped JOIN of the standing channel with the deliberate
            # observation (r09 — the empty-ok collapse is retired: NOT_IN_CORPUS pooled
            # with a grounded channel keeps the channel; r06 criterion 7 read zero
            # genuine collapses). An INFRASTRUCTURE failure (CLI error/timeout,
            # transport raise) is
            # not evidence of anything: the grounded channel survives untouched and the
            # probe is simply retired (fail-open — instrumentation never breaks an
            # already-grounded answer). The raw self-report conditions only through the
            # per-edge curve (Δ1).
            try:
                dr: dict[str, Any] | None = _obj(
                    post, f"{bridge}/probe/deliberate",
                    {"question": question, "candidates": candidates, "allow_new": True,
                     "observations": obs,
                     "candidate_competition": cand_comp,
                     "hits": hits, "time_indexed": route["time_indexed"],
                     "construct": route["construct"],
                     "covariates": {"doc_date": recency}})
            except Exception as e:
                print(f"  (deliberate probe failed, channel kept: {e})")
                dr = None
            if dr is not None:
                # spend is real even when the call failed (an is_error result still
                # bills) — the §10 accounting must survive the ok-guard below
                edge_instrument = DL.instrument(
                    str(dr.get("model") or _DELIBERATE_MODEL))
                edge_cost = dr.get("cost_usd")
                edge_latency = dr.get("latency_s")
                v = dr.get("value")
                edge_value = str(v) if v is not None else None
                edge_conf = dr.get("confidence")
                edge_lineage = dr.get("cache_key")
                # ONE derivation: the event mirrors the legacy slot from the same
                # bound values — two coercion paths over one reply could drift and
                # split the decisions-v2 accounting from the gate writer's stream.
                edge_events.append({"edge": edge_instrument, "value": edge_value,
                                    "confidence": edge_conf, "lineage": edge_lineage})
                spend_usd += float(edge_cost or 0.0)
            if dr is not None and dr.get("status") == "ok":
                if dr.get("new_candidate"):
                    candidates = [*candidates, str(dr["new_candidate"])]
                    cand_comp = [*cand_comp, 1.0]
                conf = dr.get("confidence")
                legacy = (min(_DELIBERATE_FALLBACK_RHO, max(0.0, float(conf)))
                          if conf is not None else _DELIBERATE_FALLBACK_RHO)
                obs, era = dr["observations"], False
                rho = _conditioned_rho(curves, edge_instrument, conf, legacy)
            applied = list(dict.fromkeys([*applied, probe]))
            dec = _decide(obs, rho, era, applied)
        elif eff == "gather" and probe == "re_extract_strong":
            # the K-ENLARGING strong re-extract: a whole-doc opus re-read with allow_new — a
            # value outside the local candidate set comes back as a NEW candidate (the bridge
            # indexes its observation at len(candidates)); the reply is the §5-deduped JOIN
            # of the standing channel with the re-read (r09), exactly as corroborate does.
            cr = _obj(post, f"{bridge}/probe/corroborate",
                      {"reextract": True, "allow_new": True, "question": question,
                       "observations": obs,
                       "hits": hits, "candidates": candidates, "model": _RE_EXTRACT_MODEL,
                       "rho": _GATHER_RHO, "candidate_competition": cand_comp,
                       "time_indexed": route["time_indexed"], "construct": route["construct"],
                       "covariates": {"doc_date": recency}})
            _edge_event(extract_edge(_RE_EXTRACT_MODEL), cr)
            changed = bool(cr.get("new_candidate")) or bool(cr["observations"])
            if cr.get("new_candidate"):
                candidates = [*candidates, str(cr["new_candidate"])]
                cand_comp = [*cand_comp, 1.0]
            # A DISAGREEING strong re-read no longer erases: the bridge returns the joined
            # channel (r09 — run 7's disagree⇒abstain contract retired by the ruling's
            # fix; a disagree that NAMES a joinable value contributes evidence against
            # the leader instead). A NULL read — the model named nothing at all — is the
            # absence-of-evidence case (§14, 2026-08-18): the probe retires fail-open and
            # the grounded channel stands, rho untouched.
            if not _null_read(cr):
                obs, era = cr["observations"], False
                rho = _conditioned_rho(curves, extract_edge(_RE_EXTRACT_MODEL),
                                       cr.get("confidence"), cr["gather_rho"])
            enacted.append((probe, last_sensors, changed))
            applied = list(dict.fromkeys([*applied, probe]))
            grow_asked = False
            dec = _decide(obs, rho, era, applied)
        elif (eff in _WITHHOLD and not grow_asked
              and (grow_probes - set(applied))):
            # a WITHHOLDING terminal with unapplied grow actuators: re-ask WITH the grow
            # block so the daemon prices recall. The withhold-only latch is MEASURED
            # protection, not transport economy (r15 A5, the run-17 ruling): offering the
            # block after every terminal enacted a real engine preference (A2's 62/63)
            # and the priced gate read the exercised reach as harmful — answer rate
            # 0.62 -> 0.49, dispersal on marginal reports. The latch stands until the
            # hand-set grow priors are grounded in the gather-outcome stream
            # (foundations §14, the hand-priced-VOI arc).
            last_sensors = GO.sensors_from(
                candidates=candidates, credences=list(dec["credences"] or []),
                p_none=dec["p_none"], indeterminate=int(ext.get("indeterminate") or 0))
            grow_asked = True
            dec = _decide(obs, rho, era, applied, sensors=last_sensors)
        else:
            break
    _log_outcomes(dec["effector"])
    asserted = [dec["value"]] if dec["effector"] == "report" and dec["value"] else []
    return {"effector": dec["effector"], "asserted": asserted, "candidates": candidates,
            "credences": dec["credences"], "p_none": dec["p_none"], "eu": dec["eu"],
            "n_obs": len(obs), "hits": hits, "route": route, "question": question,
            "n_indeterminate": int(ext.get("indeterminate", 0) or 0),
            "n_competing": int(ext.get("n_competing", 0) or 0),
            "instrument": edge_instrument, "cost_usd": edge_cost,
            "latency_s": edge_latency, "instrument_value": edge_value,
            "instrument_confidence": edge_conf, "instrument_lineage": edge_lineage,
            "edge_events": edge_events, "spend_usd": spend_usd}


# --- render (the executor's decision in the shared credence grammar) --------------------

def _cites(value: str, hits: list[dict[str, Any]]) -> str:
    """Cite the hit cards whose text carries the value — 1-based, in hit order (the same
    numbering the card render uses), via the shared date/number-aware matcher."""
    ns = [i + 1 for i, h in enumerate(hits)
          if MATCH.answer_matches(value, [], str(h.get("chunk_text", "")))]
    return "".join(f"[{n}]" for n in ns)


def render_view(view: View) -> str:
    """Render an executor view in the SHARED credence grammar (``lookup.GRAMMAR``) — the same
    interaction-contract strings the in-process lookup family renders, so the owner sees one
    consistent reply whichever path answered, and the posterior is named in the footer (nothing
    silent). A narrative view is already rendered bridge-side and passes through verbatim; otherwise
    the asserted value is cited to the hit cards that carry it."""
    rendered = view.get("rendered")
    if rendered:
        return str(rendered)
    eff = view["effector"]
    cands, creds, hits = view["candidates"], view["credences"], view["hits"]
    asserted = view["asserted"]
    # The daemon returns credences in CANDIDATE order (server.jl w[1:k]), NOT weight-sorted, and
    # the reported value is the MAP/leader — usually not index 0. Reorder leader-first so creds[0]
    # is the leader's credence and `alts` is weight-ordered (as lookup.render + the bridge's
    # /log_decision guard do); else a report shows the first-extracted candidate's probability.
    if creds and len(creds) == len(cands):
        order = sorted(range(len(cands)), key=lambda j: creds[j], reverse=True)
        cands = [cands[j] for j in order]
        creds = [creds[j] for j in order]
    alts = " · ".join(f"{v} ({p:.3f}) {_cites(v, hits)}".rstrip()
                      for v, p in zip(cands, creds, strict=False))
    if eff == "report" and asserted:
        v = asserted[0]
        body = LK.GRAMMAR["report"].format(value=v, p=(creds[0] if creds else 0.0),
                                           cites=_cites(v, hits))
    elif eff == "hedge":
        body = LK.GRAMMAR["hedge"].format(alts=alts)
    elif eff == "ask_clarify":
        body = LK.GRAMMAR["ask_clarify"].format(alts=alts)
    else:
        # D-5 (M5, r15): the reason is the ONE derivation over the decision record;
        # this render maps it onto the interaction contract's grammar strings.
        reason = DEC.withhold_reason(effector=eff, candidates=cands)
        if reason == "dispersed":
            body = LK.GRAMMAR["abstain_withheld"].format(reason=LK.REASON_DISPERSED,
                                                         alts=alts)
        else:  # miss — no posterior ever existed
            body = LK.GRAMMAR["abstain"].format(reason=LK.REASON_NO_OBSERVATIONS)
    p_none, eu = view["p_none"], view["eu"]
    footer = LK.GRAMMAR["footer"].format(
        n_hits=len(hits), n_obs=view.get("n_obs", 0),
        # the extractor's own indeterminate count, carried on the View (was hard-coded 0 —
        # a footer that claimed "0 indeterminate" on every executor answer)
        n_ind=view.get("n_indeterminate", 0),
        p_none=p_none if p_none is not None else 0.0,
        action=eff, eu=eu if eu is not None else 0.0)
    return f"{body}\n\n{footer}"
