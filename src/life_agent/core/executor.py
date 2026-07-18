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

from life_agent.core import gather_outcomes as GO
from life_agent.core import lookup as LK
from life_agent.core import matching as MATCH

# The transport seams, injected by the caller (PRINCIPLES §5): ``post(url, payload)`` returns the
# decoded JSON object, or ``None`` for ``/route`` on a non-typed question; ``get(url)`` returns the
# decoded JSON object. The loop builds the URLs from the ``bridge`` / ``daemon`` base strings, so a
# fake can route on the suffix.
Post = Callable[[str, dict[str, Any]], "dict[str, Any] | None"]
Get = Callable[[str], dict[str, Any]]

View = dict[str, Any]  # {effector, asserted, candidates, credences, p_none, eu, n_obs, hits,
#                        route}; a narrative view also carries "rendered" (rendered bridge-side).

# The corroborate model-tier ladder: the body names the tier (the daemon schedules it by name);
# each tier carries the model it re-reads with and the reliability that re-read is conditioned at.
_TIER_MODEL = {"corroborate_haiku": "claude-haiku-4-5",
               "corroborate_sonnet": "claude-sonnet-4-6",
               "corroborate_opus": "claude-opus-4-8"}
_TIER_RHO = {"corroborate_haiku": 0.80, "corroborate_sonnet": 0.90, "corroborate_opus": 0.95}
_GATHER_RHO = 0.95  # the corroborate re-read's default reliability (the opus tier's)

# The per-question transform MENU the body offers the daemon (the daemon prices + schedules it;
# the body enacts the arg-max by probe name). Guards fire on a precondition (era_split / an
# owner-scoped report); :voi tiers fire when a leader is below the EU bar, each at a stated
# reliability + cost-in-utility (frozen-blind world-knowledge priors, monotone in model strength;
# calibrated from verdicts downstream).
DEFAULT_TRANSFORMS: list[dict[str, Any]] = [
    {"name": "recency", "probe": "recency", "kind": "guard", "trigger": "era_split"},
    {"name": "corroborate_owner", "probe": "corroborate_opus", "kind": "guard",
     "trigger": "owner_report"},
    {"name": "corroborate_haiku", "probe": "corroborate_haiku", "kind": "voi",
     "trigger": "below_bar", "rho": 0.80, "cost": 0.004},
    {"name": "corroborate_sonnet", "probe": "corroborate_sonnet", "kind": "voi",
     "trigger": "below_bar", "rho": 0.90, "cost": 0.012},
    {"name": "corroborate_opus", "probe": "corroborate_opus", "kind": "voi",
     "trigger": "below_bar", "rho": 0.95, "cost": 0.020},
]

# A withholding/miss terminal — the daemon declined to assert. Grow may escalate recall on these,
# but only when the agent's belief says the answer is MISSING (see _truth_likely_missing).
_WITHHOLD = frozenset({"miss", "abstain", "hedge", "ask_clarify"})

# The grow lane's retrieval actuators: probe name → the /retrieve recall flags its enactment
# re-runs the evidence build at. `re_extract_strong` is the third menu row (a whole-doc opus
# re-read with allow_new — the K-enlarging strong extractor); the menu itself is data
# (core/gather_outcomes.GROW_ACTUATORS, served by the bridge's /grow_menu).
_GROW_RETRIEVE = {"retrieve_rerank": (True, False), "retrieve_expand": (True, True)}
_RE_EXTRACT_MODEL = "claude-opus-4-8"
# The k=0 rescue channel's reliability CAP — a stated wide prior (mean of the local
# extractor's own Beta(4,4), core/lookup._RHO_PRIOR_*), declared blind, NOT the tier's
# 0.95 and NOT the model's self-stated confidence: a lone strong read with zero local
# corroboration is an unmeasured instrument, and the first field run showed fiat trust
# asserting a true-but-vague read at 0.866 (q-015, graded wrong). Under this cap the
# rescue NAMES candidates (hedge — EU-positive under u_hedged vs silence) and earns
# assert-grade trust only through conditioned verdicts, exactly as the local channel
# did after its own 0.85-fiat prior was refuted.
_RESCUE_RHO = 0.5


def _truth_likely_missing(view: View) -> bool:
    """The agent's belief that the answer is OUTSIDE the retrieved set — the principled trigger to
    GROW recall (discover a missing candidate), versus CORROBORATE a present-but-weak leader (which
    the daemon already prices by ``net_voi``). True iff nothing was extracted, or NONE ("the truth
    is not among the retrieved candidates") is the MAP hypothesis: P(NONE) ≥ the best present
    candidate's posterior. No magic threshold — the comparison is one the posterior itself defines.
    Grow can't be VOI-priced over the closed categorical (it enlarges K); P(NONE) is the in-model
    signal that replaces the old blind "grow on any withhold" cascade, so the body grows on the
    agent's belief, not the bare effector."""
    if not view["candidates"]:
        return True  # zero grounded observations — the truth is definitionally not in the set
    p_none = view["p_none"]
    if p_none is None:
        return False
    leader = max(view["credences"]) if view["credences"] else 0.0
    return bool(p_none >= leader)


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
                    grow: bool = True, rerank: bool = False,
                    transforms: list[dict[str, Any]] | None = None,
                    grow_lane: bool = False) -> View:
    """Drive one question through the live loop: route, then a cheap pass, then recall growth.

    A declined route (``/route`` → null) is the NARRATIVE family — synthesize a cited answer,
    audit each claim, include only grounded + EU-positive claims; gate-safe by construction.

    ``grow_lane=True`` (slice 6 — the conferred gather offload, flag-gated for the parity-safe
    cutover): recall is DECIDED BY THE DAEMON — the loop ships the sensor buckets + the grow
    menu (bridge ``/grow_menu``: actuators with body-persisted warm counts) into ``/decide``,
    the daemon prices the grow argmax by the engine gather VOI (``grow_value`` over the
    structure-BMA ``g``), and the body enacts the named probe and logs the outcome
    (``/log_gather`` — the structure-observe stream). No body-side cascade, no
    ``_truth_likely_missing`` gate: P(NONE) enters only as a bucketed *sensor*.

    ``grow_lane=False`` (the legacy adapter, deleted at cutover): a typed route runs
    :func:`run_pass`; if ``grow`` and the cheap pass withholds AND the agent's belief says the
    answer is outside the set (:func:`_truth_likely_missing`), escalate recall breadth (rerank,
    then native-script expansion) and adopt a grown report (or any grown decision when the
    cheap pass found no candidates at all)."""
    transforms = DEFAULT_TRANSFORMS if transforms is None else transforms
    route = post(f"{bridge}/route", {"question": question})
    if route is None:
        nv = _obj(post, f"{bridge}/narrative", {"question": question})
        return {"effector": nv["action"], "asserted": nv["asserted"], "candidates": [],
                "credences": [], "p_none": None, "eu": None, "n_obs": 0,
                "hits": nv.get("hits", []), "route": None, "rendered": nv.get("rendered")}
    if grow_lane:
        return run_pass(question, k, route, bridge=bridge, daemon=daemon, post=post, get=get,
                        rerank=False, expand=False, transforms=transforms, grow_lane=True)
    view = run_pass(question, k, route, bridge=bridge, daemon=daemon, post=post, get=get,
                    rerank=rerank, expand=rerank, transforms=transforms)
    if grow and not rerank:
        # Grow recall ONLY when the agent's BELIEF says the answer is outside the set — NONE is the
        # MAP hypothesis, or nothing was extracted (:func:`_truth_likely_missing`). A withhold with
        # a plausible present leader is the CORROBORATE case (re-read at higher reliability — priced
        # by net_voi in the daemon), NOT grow: widening recall there only adds distractors (and
        # risks growing into a confident-wrong). Grow is the discovery move VOI can't price over the
        # closed categorical; P(NONE) is its in-model trigger. Escalate breadth cheapest-first; stop
        # once a report lands or the belief no longer says missing:
        #   tier 1  rerank(raw)   — over-fetch + listwise reorder surfaces a buried literal hit
        #   tier 2  rerank+expand — native-script (Hebrew) expansion bridges the English↔Hebrew
        #                           lexical gap; expansion dilutes strong literals, so it follows
        #                           raw rerank rather than replacing it.
        for rr, ex in ((True, False), (True, True)):
            if view["effector"] not in _WITHHOLD or not _truth_likely_missing(view):
                break
            grown = run_pass(question, k, route, bridge=bridge, daemon=daemon, post=post, get=get,
                             rerank=rr, expand=ex, transforms=transforms)
            if grown["effector"] == "report" or not view["candidates"]:
                view = grown
    return view


def run_pass(question: str, k: int, route: dict[str, Any], *, bridge: str, daemon: str,
             post: Post, get: Get, rerank: bool, expand: bool = False,
             transforms: list[dict[str, Any]] | None = None,
             grow_lane: bool = False) -> View:
    """One retrieve→probe→extract→decide pass at a given recall breadth, enacting each
    scheduled transform the daemon returns. With ``grow_lane`` the daemon also prices the
    grow menu (recall actuators), and each enactment is logged to ``/log_gather``. Returns
    the normalized view ``{effector, asserted, candidates, credences, p_none, eu, hits, route}``."""
    transforms = DEFAULT_TRANSFORMS if transforms is None else transforms

    def _evidence(rr: bool, ex: bool) -> tuple[list[dict[str, Any]], dict[str, Any],
                                               dict[str, Any]]:
        hits = _obj(post, f"{bridge}/retrieve",
                    {"question": question, "k": k, "rerank": rr, "expand": ex})["hits"]
        hit_keys = list(dict.fromkeys(h["artifact_cache_key"] for h in hits))
        subj = _obj(post, f"{bridge}/probe/subject", {"hit_keys": hit_keys})["subject_state"]
        recency = _obj(post, f"{bridge}/probe/recency", {"hit_keys": hit_keys})["doc_date"]
        # construct ⇒ the bridge decays time_factor at its volatility half-life
        ext = _obj(post, f"{bridge}/extract", {
            "question": question, "hits": hits, "time_indexed": route["time_indexed"],
            "construct": route["construct"],
            "covariates": {"subject_state": subj, "doc_date": recency}})
        return hits, recency, ext

    hits, recency, ext = _evidence(rerank, expand)
    menu = get(f"{bridge}/grow_menu")["grow"] if grow_lane else None
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

    applied: list[str] = []
    if grow_lane and not ext["candidates"] and menu is not None:
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
                           "hits": hits, "candidates": [], "model": _RE_EXTRACT_MODEL,
                           "rho": _GATHER_RHO,
                           "time_indexed": route["time_indexed"],
                           "construct": route["construct"],
                           "covariates": {"doc_date": recency}})
                minted = bool(cr.get("new_candidate"))
                enacted.append((g_probe, sensors0, minted))
                applied.append(g_probe)
                if minted:
                    conf = cr.get("confidence")
                    rescue_rho = (min(_RESCUE_RHO, max(0.0, float(conf)))
                                  if conf is not None else _RESCUE_RHO)
                    ext = {"candidates": [str(cr["new_candidate"])],
                           "observations": cr["observations"], "rho": rescue_rho,
                           "era_split": False,
                           "indeterminate": ext.get("indeterminate", 0)}
                    break
    if not ext["candidates"]:  # zero grounded observations → the local edge declined
        _log_outcomes("miss")
        return {"effector": "miss", "asserted": [], "candidates": [], "credences": [],
                "p_none": None, "eu": None, "n_obs": 0, "hits": hits, "route": route}
    u_bar = get(f"{bridge}/utility")["u_bar"]
    candidates = ext["candidates"]
    owner = owner_scoped(question)
    obs, rho, era = ext["observations"], ext["rho"], ext["era_split"]

    def _decide(observations: list[Any], r: float, era_split: bool, applied: list[str],
                sensors: dict[str, str] | None = None) -> View:
        payload: dict[str, Any] = {
            "candidates": candidates, "observations": observations, "rho": r, "u_bar": u_bar,
            "era_split": era_split, "owner_scoped": owner, "applied_probes": applied,
            "transforms": transforms}
        if sensors is not None and menu is not None:
            payload["sensors"] = sensors
            payload["grow"] = menu
        return _obj(post, f"{daemon}/decide", payload)

    dec = _decide(obs, rho, era, applied)
    grow_probes = ({str(a["probe"]) for a in menu["actuators"]} if menu is not None else set())
    grow_asked = False
    last_sensors: dict[str, str] = {}
    # bounded: each registry probe and each grow actuator fires at most once (dedup on the
    # probe name); a grow costs two decides (the priced re-ask + the post-enactment decide).
    for _ in range(2 + sum(t["kind"] == "voi" for t in transforms) + 2 * len(grow_probes)):
        eff, probe = dec["effector"], str(dec.get("probe") or "")
        if eff == "gather" and probe == "recency":
            # recency is PRE-APPLIED in /extract (obs already decayed) → acknowledge and re-decide.
            applied = list(dict.fromkeys([*applied, "recency"]))
            dec = _decide(obs, rho, era, applied)
        elif eff == "gather" and probe.startswith("corroborate"):
            # a subject-aware whole-doc re-read at the scheduled TIER's model REPLACES the local
            # channel. The joint's value → one observation (or NONE ⇒ empty ⇒ abstain). Each tier
            # fires at most once (dedup on the probe name) ⇒ escalation across tiers terminates.
            model = _TIER_MODEL.get(probe, "claude-opus-4-8")
            tier_rho = _TIER_RHO.get(probe, _GATHER_RHO)
            cr = _obj(post, f"{bridge}/probe/corroborate",
                      {"reextract": True, "question": question, "hits": hits,
                       "candidates": candidates, "model": model, "rho": tier_rho,
                       # the re-read obs flows through the construct's volatility (the keystone):
                       # pass time_indexed + construct + doc_date so a stale re-read decays.
                       "time_indexed": route["time_indexed"], "construct": route["construct"],
                       "covariates": {"doc_date": recency}})
            obs, rho, era = cr["observations"], cr["gather_rho"], False
            applied = list(dict.fromkeys([*applied, probe]))
            dec = _decide(obs, rho, era, applied)
        elif eff == "gather" and probe in _GROW_RETRIEVE:
            # a DAEMON-SCHEDULED retrieval grow: rebuild the evidence at the named breadth and
            # adopt it iff it grounded candidates (else the prior evidence stands and the probe
            # is simply retired — a fruitless recall must not erase a posterior).
            rr, ex = _GROW_RETRIEVE[probe]
            n_hits, n_recency, n_ext = _evidence(rr, ex)
            changed = bool(n_ext["candidates"])
            if changed:
                hits, recency, ext = n_hits, n_recency, n_ext
                candidates = ext["candidates"]
                obs, rho, era = ext["observations"], ext["rho"], ext["era_split"]
            enacted.append((probe, last_sensors, changed))
            applied = list(dict.fromkeys([*applied, probe]))
            grow_asked = False
            dec = _decide(obs, rho, era, applied)
        elif eff == "gather" and probe == "re_extract_strong":
            # the K-ENLARGING strong re-extract: a whole-doc opus re-read with allow_new — a
            # value outside the local candidate set comes back as a NEW candidate (the bridge
            # indexes its observation at len(candidates)); the re-read REPLACES the channel
            # (same docs — nested dependence), exactly as corroborate does.
            cr = _obj(post, f"{bridge}/probe/corroborate",
                      {"reextract": True, "allow_new": True, "question": question,
                       "hits": hits, "candidates": candidates, "model": _RE_EXTRACT_MODEL,
                       "rho": _GATHER_RHO,
                       "time_indexed": route["time_indexed"], "construct": route["construct"],
                       "covariates": {"doc_date": recency}})
            changed = bool(cr.get("new_candidate")) or bool(cr["observations"])
            if cr.get("new_candidate"):
                candidates = [*candidates, str(cr["new_candidate"])]
            # unconditional — an EMPTY strong re-read also replaces (the strong model failed to
            # confirm any local candidate; the weak evidence must not survive it — disagree ⇒
            # NONE-dominant ⇒ abstain, the corroborate contract verbatim).
            obs, rho, era = cr["observations"], cr["gather_rho"], False
            enacted.append((probe, last_sensors, changed))
            applied = list(dict.fromkeys([*applied, probe]))
            grow_asked = False
            dec = _decide(obs, rho, era, applied)
        elif (eff in _WITHHOLD and grow_lane and not grow_asked
              and (grow_probes - set(applied))):
            # a withholding terminal with unapplied grow actuators: re-ask WITH the grow block
            # so the daemon prices recall (grow_value self-gates on the terminal EU — skipping
            # the re-ask after a report is transport economy, not a decision: a confident
            # report prices at about minus-cost by construction).
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
            "n_obs": len(obs), "hits": hits, "route": route}


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
    elif eff == "abstain" and cands:
        body = LK.GRAMMAR["abstain_withheld"].format(reason=LK.REASON_DISPERSED, alts=alts)
    else:  # abstain with no candidates, or miss (zero grounded observations)
        body = LK.GRAMMAR["abstain"].format(reason=LK.REASON_DISPERSED)
    p_none, eu = view["p_none"], view["eu"]
    footer = LK.GRAMMAR["footer"].format(
        n_hits=len(hits), n_obs=view.get("n_obs", 0), n_ind=0,
        p_none=p_none if p_none is not None else 0.0,
        action=eff, eu=eu if eu is not None else 0.0)
    return f"{body}\n\n{footer}"
