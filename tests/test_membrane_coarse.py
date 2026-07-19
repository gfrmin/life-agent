"""Hermetic tests for :mod:`life_agent.membrane.coarse` — M3, the coarse menu live.

Two pure surfaces, no wire and no subprocess:

* :func:`coarse.map_action` — the engine's coarse affordance mapped onto an ENACTABLE
  daemon-view rewrite, with every transitional rule and degradation named (agreement
  passthrough; override to abstain/ask; respond → host-MAP value; gather → the daemon's
  own probe on agreement, else the cheapest unapplied voi transform, else the restricted
  argmax over the enactable remainder at the engine's own p1 under the world's one
  utility source).
* :func:`coarse.live_decide` — the host-side consult closure the seam commits through:
  posts one `/decide-live`, and on ANY failure (down bridge, not-ok reply, malformed
  reply) returns the DECLARED abstain (`seam.GATE_ENGINE_DOWN`), never a silent host
  choice.

Fixture values are synthetic (public repo, PRINCIPLES §12) — no owner data.
"""
from __future__ import annotations

from typing import Any

from life_agent.core import seam as SEAM
from life_agent.membrane import coarse as CO

# The same hand-computable utility the report tests use: eu_by_action(p1) =
#   abstain: 0 · gather: p1 - 0.02 · ask: p1 - 0.1 · respond: 5*p1 - 4
_U_BAR = {"u_correct": 1.0, "u_abstain": 0.0, "u_wrong": -4.0,
          "lambda_int": 0.1, "kappa_att": 0.02}

_VOI_TRANSFORMS: list[dict[str, Any]] = [
    {"name": "recency", "probe": "recency", "kind": "guard", "trigger": "era_split"},
    {"name": "corroborate_haiku", "probe": "corroborate_haiku", "kind": "voi",
     "trigger": "below_bar", "rho": 0.80, "cost": 0.004},
    {"name": "corroborate_sonnet", "probe": "corroborate_sonnet", "kind": "voi",
     "trigger": "below_bar", "rho": 0.90, "cost": 0.012},
]


def _payload(**kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "candidates": ["alpha", "beta"], "observations": [1, 2], "rho": 0.8,
        "u_bar": dict(_U_BAR), "era_split": False, "owner_scoped": False,
        "applied_probes": [], "transforms": [dict(t) for t in _VOI_TRANSFORMS],
    }
    base.update(kw)
    return base


def _dec(**kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "effector": "abstain", "value": None, "probe": None,
        "credences": [0.2, 0.3], "p_none": 0.5, "eu": 0.0, "n_obs": 2,
    }
    base.update(kw)
    return base


# --- agreement: the engine's coarse class matches the daemon's — fine selection stays
# --- the daemon's (the transitional rule), the view passes through UNCHANGED -------------


def test_agreement_passes_the_daemon_view_through_verbatim() -> None:
    for effector, engine in (("report", "respond"), ("report_scoped", "respond"),
                             ("hedge", "respond"), ("ask_clarify", "ask"),
                             ("abstain", "abstain"), ("miss", "abstain")):
        dec = _dec(effector=effector, value="alpha" if engine == "respond" else None)
        view, degraded = CO.map_action(_payload(), dec, engine, {"p1": 0.3})
        assert view == dec, effector
        assert degraded is None


def test_gather_agreement_keeps_the_daemon_scheduled_probe() -> None:
    dec = _dec(effector="gather", probe="corroborate_sonnet")
    view, degraded = CO.map_action(_payload(), dec, "gather", {"p1": 0.3})
    assert view == dec
    assert degraded is None


# --- overrides: the engine chose a different coarse act ---------------------------------


def test_engine_abstain_overrides_a_daemon_report() -> None:
    view, degraded = CO.map_action(
        _payload(), _dec(effector="report", value="alpha"), "abstain", {"p1": 0.3})
    assert view["effector"] == "abstain"
    assert view["value"] is None
    assert degraded is None
    # the posterior fields survive the rewrite — the footer render stays honest
    assert view["credences"] == [0.2, 0.3]
    assert view["p_none"] == 0.5


def test_engine_ask_overrides_to_ask_clarify() -> None:
    view, degraded = CO.map_action(
        _payload(), _dec(effector="abstain"), "ask", {"p1": 0.3})
    assert view["effector"] == "ask_clarify"
    assert view["value"] is None
    assert degraded is None


def test_engine_respond_reports_the_host_map_value() -> None:
    # credences are in CANDIDATE order; the MAP value is the argmax, not index 0
    view, degraded = CO.map_action(
        _payload(candidates=["alpha", "beta"]),
        _dec(effector="abstain", credences=[0.2, 0.3]), "respond", {"p1": 0.99})
    assert view["effector"] == "report"
    assert view["value"] == "beta"
    assert degraded is None


def test_engine_respond_with_no_candidates_degrades_to_abstain() -> None:
    view, degraded = CO.map_action(
        _payload(candidates=[]), _dec(effector="abstain", credences=[]),
        "respond", {"p1": 0.99})
    assert view["effector"] == "abstain"
    assert degraded == "respond_no_value"


def test_engine_respond_with_mismatched_credences_degrades_to_abstain() -> None:
    view, degraded = CO.map_action(
        _payload(candidates=["alpha", "beta"]),
        _dec(effector="abstain", credences=[0.4]), "respond", {"p1": 0.99})
    assert view["effector"] == "abstain"
    assert degraded == "respond_no_value"


# --- engine gather on a daemon terminal: transitional fine selection ---------------------


def test_engine_gather_selects_the_cheapest_unapplied_voi_transform() -> None:
    view, degraded = CO.map_action(
        _payload(), _dec(effector="abstain"), "gather", {"p1": 0.3})
    assert view["effector"] == "gather"
    assert view["probe"] == "corroborate_haiku"  # menu order; guards are never selected
    assert degraded is None


def test_engine_gather_skips_already_applied_probes() -> None:
    view, degraded = CO.map_action(
        _payload(applied_probes=["corroborate_haiku"]),
        _dec(effector="abstain"), "gather", {"p1": 0.3})
    assert view["probe"] == "corroborate_sonnet"
    assert degraded is None


def test_gather_exhausted_falls_to_restricted_argmax_ask() -> None:
    # all voi probes applied; at p1=0.3 the enactable remainder prices
    # abstain 0 · ask 0.2 · respond -2.5 → ask
    view, degraded = CO.map_action(
        _payload(applied_probes=["corroborate_haiku", "corroborate_sonnet"]),
        _dec(effector="abstain"), "gather", {"p1": 0.3})
    assert view["effector"] == "ask_clarify"
    assert degraded == "gather_exhausted"


def test_gather_exhausted_low_p1_abstains() -> None:
    # p1=0.05: abstain 0 · ask -0.05 · respond -3.75 → abstain
    view, degraded = CO.map_action(
        _payload(applied_probes=["corroborate_haiku", "corroborate_sonnet"]),
        _dec(effector="report", value="alpha"), "gather", {"p1": 0.05})
    assert view["effector"] == "abstain"
    assert view["value"] is None
    assert degraded == "gather_exhausted"


def test_gather_exhausted_high_p1_responds_with_map_value() -> None:
    # p1=0.99: respond 0.95 beats ask 0.89 → report the MAP candidate
    view, degraded = CO.map_action(
        _payload(applied_probes=["corroborate_haiku", "corroborate_sonnet"]),
        _dec(effector="abstain", credences=[0.2, 0.3]), "gather", {"p1": 0.99})
    assert view["effector"] == "report"
    assert view["value"] == "beta"
    assert degraded == "gather_exhausted"


def test_gather_exhausted_without_p1_abstains_named() -> None:
    view, degraded = CO.map_action(
        _payload(applied_probes=["corroborate_haiku", "corroborate_sonnet"]),
        _dec(effector="abstain"), "gather", {})
    assert view["effector"] == "abstain"
    assert degraded == "no_p1"


def test_gather_exhausted_without_u_bar_abstains_named() -> None:
    p = _payload(applied_probes=["corroborate_haiku", "corroborate_sonnet"])
    del p["u_bar"]
    view, degraded = CO.map_action(p, _dec(effector="abstain"), "gather", {"p1": 0.3})
    assert view["effector"] == "abstain"
    assert degraded == "no_p1"


# --- live_decide: the seam's consult closure ---------------------------------------------


def test_live_decide_posts_the_tick_and_returns_the_bridge_view() -> None:
    posts: list[tuple[str, dict[str, Any]]] = []
    mapped = _dec(effector="ask_clarify")

    def post(url: str, body: dict[str, Any]) -> dict[str, Any]:
        posts.append((url, body))
        return {"ok": True, "dec": mapped, "action": "ask", "degraded": None}

    consult = CO.live_decide("http://b:1", "q-mirror-id", post=post)
    payload, reply = _payload(), _dec(effector="abstain")
    view, gate = consult(payload, reply)
    assert view == mapped
    assert gate is None
    (url, body), = posts
    assert url == "http://b:1/decide-live"
    assert body == {"question_id": "q-mirror-id", "payload": payload, "dec": reply}


def test_live_decide_down_bridge_is_the_declared_abstain() -> None:
    def post(url: str, body: dict[str, Any]) -> dict[str, Any]:
        raise OSError("connection refused")

    consult = CO.live_decide("http://b:1", "q-mirror-id", post=post)
    reply = _dec(effector="report", value="alpha", credences=[0.9, 0.1])
    view, gate = consult(_payload(), reply)
    assert view["effector"] == "abstain"
    assert view["value"] is None
    assert view["credences"] == [0.9, 0.1]  # the posterior survives for the footer
    assert gate == SEAM.GATE_ENGINE_DOWN


def test_live_decide_not_ok_reply_is_the_declared_abstain() -> None:
    for resp in ({"ok": False, "down": True}, {"ok": False, "disabled": True},
                 {"ok": True, "dec": "not-a-dict"}, None):
        consult = CO.live_decide(
            "http://b:1", "q-mirror-id", post=lambda u, b, _r=resp: _r)
        view, gate = consult(_payload(), _dec(effector="report", value="alpha"))
        assert view["effector"] == "abstain", resp
        assert gate == SEAM.GATE_ENGINE_DOWN, resp


def test_default_transport_is_the_short_lived_live_post() -> None:
    # the closure's default transport is coarse.py's own poster with its OWN timeout —
    # never a real-leg 300s poster (the consult IS on the answer path; a wedged bridge
    # must cost a bounded wait, not five minutes).
    import inspect

    sig = inspect.signature(CO.live_decide)
    assert sig.parameters["post"].default is CO._live_post
    assert CO.LIVE_TIMEOUT_S < 300.0
