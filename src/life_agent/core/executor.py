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

# A withholding/miss terminal — the daemon declined to assert. Grow escalates recall on these.
_WITHHOLD = frozenset({"miss", "abstain", "hedge", "ask_clarify"})


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
                    transforms: list[dict[str, Any]] | None = None) -> View:
    """Drive one question through the live loop: route, then a cheap pass, then a single ``grow``
    escalation (gated) when the cheap pass withholds.

    A declined route (``/route`` → null) is the NARRATIVE family — synthesize a cited answer,
    audit each claim, include only grounded + EU-positive claims; gate-safe by construction. A
    typed route runs :func:`run_pass`; if ``grow`` and the cheap pass WITHHOLDS, escalate recall
    breadth once (rerank, then native-script expansion) and adopt a grown report (or any grown
    decision when the cheap pass found no candidates at all)."""
    transforms = DEFAULT_TRANSFORMS if transforms is None else transforms
    route = post(f"{bridge}/route", {"question": question})
    if route is None:
        nv = _obj(post, f"{bridge}/narrative", {"question": question})
        return {"effector": nv["action"], "asserted": nv["asserted"], "candidates": [],
                "credences": [], "p_none": None, "eu": None, "n_obs": 0,
                "hits": nv.get("hits", []), "route": None, "rendered": nv.get("rendered")}
    view = run_pass(question, k, route, bridge=bridge, daemon=daemon, post=post, get=get,
                    rerank=rerank, expand=rerank, transforms=transforms)
    if grow and not rerank:
        # Escalating recall breadth (cheapest-first, stop at the first report). Each tier fires
        # only if the prior still WITHHOLDS — pay for breadth only when narrower recall failed:
        #   tier 1  rerank(raw)   — over-fetch + listwise reorder surfaces a buried literal hit
        #   tier 2  rerank+expand — native-script (Hebrew) expansion bridges the English↔Hebrew
        #                           lexical gap; expansion dilutes strong literals, so it follows
        #                           raw rerank rather than replacing it.
        for rr, ex in ((True, False), (True, True)):
            if view["effector"] not in _WITHHOLD:
                break
            grown = run_pass(question, k, route, bridge=bridge, daemon=daemon, post=post, get=get,
                             rerank=rr, expand=ex, transforms=transforms)
            if grown["effector"] == "report" or not view["candidates"]:
                view = grown
    return view


def run_pass(question: str, k: int, route: dict[str, Any], *, bridge: str, daemon: str,
             post: Post, get: Get, rerank: bool, expand: bool = False,
             transforms: list[dict[str, Any]] | None = None) -> View:
    """One retrieve→probe→extract→decide pass at a given recall breadth, enacting each
    net_voi-scheduled transform the daemon returns. Returns the normalized view
    ``{effector, asserted, candidates, credences, p_none, eu, hits, route}``."""
    transforms = DEFAULT_TRANSFORMS if transforms is None else transforms
    hits = _obj(post, f"{bridge}/retrieve",
                {"question": question, "k": k, "rerank": rerank, "expand": expand})["hits"]
    hit_keys = list(dict.fromkeys(h["artifact_cache_key"] for h in hits))
    subj = _obj(post, f"{bridge}/probe/subject", {"hit_keys": hit_keys})["subject_state"]
    recency = _obj(post, f"{bridge}/probe/recency", {"hit_keys": hit_keys})["doc_date"]
    # construct ⇒ the bridge decays time_factor at its volatility half-life
    ext = _obj(post, f"{bridge}/extract", {
        "question": question, "hits": hits, "time_indexed": route["time_indexed"],
        "construct": route["construct"],
        "covariates": {"subject_state": subj, "doc_date": recency}})
    if not ext["candidates"]:  # zero grounded observations → the local edge declined
        return {"effector": "miss", "asserted": [], "candidates": [], "credences": [],
                "p_none": None, "eu": None, "n_obs": 0, "hits": hits, "route": route}
    u_bar = get(f"{bridge}/utility")["u_bar"]
    candidates = ext["candidates"]
    owner = owner_scoped(question)
    obs, rho, era = ext["observations"], ext["rho"], ext["era_split"]

    def _decide(observations: list[Any], r: float, era_split: bool, applied: list[str]) -> View:
        return _obj(post, f"{daemon}/decide", {
            "candidates": candidates, "observations": observations, "rho": r, "u_bar": u_bar,
            "era_split": era_split, "owner_scoped": owner, "applied_probes": applied,
            "transforms": transforms})

    applied: list[str] = []
    dec = _decide(obs, rho, era, applied)
    for _ in range(2 + sum(t["kind"] == "voi" for t in transforms)):  # bounded: each probe once
        if dec["effector"] != "gather":
            break
        probe = dec.get("probe") or ""
        if probe == "recency":
            # recency is PRE-APPLIED in /extract (obs already decayed) → acknowledge and re-decide.
            applied = list(dict.fromkeys([*applied, "recency"]))
            dec = _decide(obs, rho, era, applied)
        elif probe.startswith("corroborate"):
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
        else:
            break
    asserted = [dec["value"]] if dec["effector"] == "report" and dec["value"] else []
    return {"effector": dec["effector"], "asserted": asserted, "candidates": ext["candidates"],
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
