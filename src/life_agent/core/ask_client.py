"""The reach→know client: answer a question through the ONE executor, from any transport.

Interaction contract: *asking about your life is know*, whatever surface carried the
question — so a reach transport (Jarvis/Telegram) never re-implements the read-path; it
calls this. One function answers (``executor.decide_via_loop`` → ``render_view``, the same
credence grammar every surface renders), logs the terminal decision through the bridge's
``/log_decision`` (so the owner's one-bit verdict folds through the EXISTING reaction
loop), and returns the content-addressed ``decision_id`` the in-session verdict binds to.
``react`` posts that verdict to ``/log_reaction`` and names the fold fate in ask-live's
own vocabulary — a report verdict is recorded-not-folded, said so, never implied to count.

Transport is urllib by default; ``post``/``get`` are injectable so the whole client is
hermetically testable (the executor's own seam, PRINCIPLES §5). A down stack — the bridge,
or the decider it hosts — is NAMED, never substituted: no other code answers in its place
(the contract's invariant 3).
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from life_agent.core import calibration as CAL
from life_agent.core import config as CFG
from life_agent.core import decisions as DEC
from life_agent.core import executor as EX
from life_agent.core import lookup as LK
from life_agent.core import recorder as REC
from life_agent.core import seam as SEAM

BRIDGE = os.environ.get("LIFE_AGENT_BRIDGE_URL", "http://127.0.0.1:8798")
DOWN = ("No answer asserted — the decider is unavailable (the bridge or its engine is "
        "not up; start the bridge, and run `make engine` if no engine is installed).")
# The fold-fate vocabulary — ask-live's /react wording, one voice across surfaces.
FATE_FOLDS = "folds into the utility posterior on the next gate run"
FATE_RECORDED = "recorded — not folded (only abstain verdicts move the fold)"


# r33 A1 (conferral 2 §3.5, signature E): one live 5xx used to kill a whole ask — the ONE
# transport now retries transient failures with bounded backoff. A 4xx is the bridge
# SPEAKING (a named refusal), never retried; retrying it would re-ask a settled question.
_RETRY_SLEEPS = (0.5, 2.0)


def _retrying[T](attempt: Callable[[], T]) -> T:
    """Run ``attempt``; on a TRANSIENT failure (HTTP 5xx, connection error, timeout)
    sleep and retry, once per entry in :data:`_RETRY_SLEEPS`; the final attempt's error
    propagates with its own name. HTTPError < 500 re-raises immediately, and so does 503:
    the bridge saying its decider is unavailable, which a retry would only make re-boot."""
    for delay in _RETRY_SLEEPS:
        try:
            return attempt()
        except urllib.error.HTTPError as e:
            if e.code < 500 or e.code == 503:
                raise
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(delay)
    return attempt()


def post_json(url: str, payload: dict[str, Any], *,
              timeout: int | None = None) -> dict[str, Any] | None:
    """The ONE bridge/daemon POST transport (every client delegates here — three
    near-identical copies once hid the same defect). The bridge RETURNS a seam
    failure's name in the error body (server.py: "visible to the caller, never
    swallowed"); carry it in the raised error — the exception type stays HTTPError,
    so the fail-open transport contract is untouched."""
    if timeout is None:
        timeout = 300
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")

    def attempt() -> dict[str, Any] | None:
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                out: dict[str, Any] | None = json.loads(r.read())
                return out
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace") if e.fp else ""
            raise urllib.error.HTTPError(
                req.full_url, e.code, f"{e.reason} — {detail}" if detail else str(e.reason),
                e.hdrs, None) from e

    return _retrying(attempt)


def _post(url: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    return post_json(url, payload)


def _get(url: str) -> dict[str, Any]:
    def attempt() -> dict[str, Any]:
        with urllib.request.urlopen(url, timeout=300) as r:
            out: dict[str, Any] = json.loads(r.read())
            return out

    return _retrying(attempt)


def _ready() -> bool:
    """The bridge must answer /ready with a decider configured — a down stack is named,
    never guessed around. (A configured decider whose engine has died re-boots on the next
    ``/decide``; if that fails, ``/decide`` answers 503 and :func:`drive` names it.)"""
    try:
        with urllib.request.urlopen(f"{BRIDGE}/ready", timeout=3) as r:
            status = json.loads(r.read())
    except Exception:
        return False
    return bool((status.get("decider") or {}).get("enabled"))


def _edge_curves(hold_out_question_id: str | None = None
                 ) -> dict[str, CAL.ReliabilityCurve] | None:
    """The per-edge reliability curves folded from the outcomes log — ONE fold for every
    surface (M2: the CLI's and the reach surface's copies merged; the LOO hold-out is the
    gate's run-4 machinery, threaded by the caller). **None when the fold yields nothing**:
    an empty curves dict is NOT a no-op — it would flatten every corroborate tier to the
    cold start — so no attributed evidence ⇒ the declared constants stand. Curve-fold
    failure degrades fail-open and NAMED, never a silent behaviour fork."""
    try:
        held_out = (frozenset({hold_out_question_id})
                    if hold_out_question_id is not None else frozenset())
        rows = CAL.edge_outcomes_from_log(CFG.OUTCOMES_LOG,
                                          exclude_question_ids=held_out)
        if not rows:
            return None
        return CAL.fit_edge_curves(rows)
    except Exception as e:
        print(f"  (edge curves unavailable — declared constants stand: {e})")
        return None


def _menu(hold_out_question_id: str | None = None
          ) -> tuple[list[dict[str, Any]] | None, Any]:
    """The priced transform menu — the SAME configuration on every surface (§13 adoption:
    the deliberate edge is on by default; the surface the owner talks to must be the
    measured arm). ``(None, None)`` only when the edge is explicitly rolled back
    (``LIFE_AGENT_DELIBERATE=0``)."""
    if not CFG.deliberate_enabled():
        return None, None
    curves = _edge_curves(hold_out_question_id)
    return EX.menu_transforms(curves), curves


class DriveResult:
    """The one driver's return: the loop's ``view`` (``None`` on a down stack), the
    ``decision_id`` a verdict can bind to (``None`` when nothing foldable was posted), the
    ``down`` fact, and ``text`` (unused by the decided path; kept for the render seam)."""

    __slots__ = ("decision_id", "down", "text", "view")

    def __init__(self, view: dict[str, Any] | None, decision_id: str | None,
                 down: bool = False, text: str | None = None) -> None:
        self.view, self.decision_id, self.down, self.text = view, decision_id, down, text


def post_decision(post: Any, bridge: str, question: str, view: dict[str, Any], *,
                  run_id: str | None = None) -> str | None:
    """The one poster (M2, design §5.1): post the committed lookup-family terminal with
    the ONE body — every accounting key present (0.0/"" honest defaults), ``regime`` and
    ``policy`` STATED. Posts iff the loop committed a lookup terminal through the seam
    (route ran, terminal effector, a ranked posterior). A MISS (route ran, nothing
    grounded, the loop returned before ``/decide``) appends the r33 RC-1 row LOCALLY —
    ``regime: "miss"``, a real id the verdict can bind to, excluded from the fold — never
    a bridge post (the bridge derives ids for ranked decisions and stamps the current
    fold version, both wrong here). A route-null question's decision is the narrative
    question (declined as not a point fact) posts nothing. Fail-open by contract and NAMED: a
    calibration-log write never breaks the answer."""
    if view["route"] is not None and view["effector"] == "miss":
        try:
            return REC.record_miss(
                question,
                retrieval_keys=[h["artifact_cache_key"] for h in view["hits"]],
                n_indeterminate=view.get("n_indeterminate", 0), run_id=run_id)
        except Exception as e:  # fail-open: the verdict simply has nothing to bind to
            print(f"  (decision not logged: {e})")
            return None
    if (view["route"] is None or view["effector"] not in DEC.LOOKUP_ACTION_ORDER
            or not view["credences"]):
        return None
    payload = REC.body(
        question=question,
        retrieval_keys=[h["artifact_cache_key"] for h in view["hits"]],
        effector=view["effector"], credences=view["credences"],
        candidates=view["candidates"], p_none=view["p_none"], eu=view["eu"],
        n_obs=view.get("n_obs", 0),
        n_indeterminate=view.get("n_indeterminate", 0),
        n_competing=view.get("n_competing", 0),
        instrument=view.get("instrument"), cost_usd=view.get("cost_usd"),
        latency_s=view.get("latency_s"), run_id=run_id,
        # regime is a FACT of availability (§2.3): the decider decided, so the space was
        # full; policy derives from the decider's one declared regime — the same constant
        # current_u_bar folds under, so record and fold cannot diverge (M3, r13)
        regime="full", policy=LK.U_BAR_POLICY)
    try:
        return REC.record_via_bridge(post, bridge, payload)
    except Exception as e:  # fail-open: the verdict simply has nothing to bind to
        print(f"  (decision not logged: {e})")
        return None


def drive(question: str, k: int = 20, *, bridge: str | None = None,
          post: Any = None, get: Any = None,
          run_id: str | None = None, ready: Any = None,
          hold_out_question_id: str | None = None,
          check_ready: bool = True) -> DriveResult:
    """THE one driver (M2, design §5.1/Q-O6): the reach surface and the CLI answer through
    this one function with one ``/log_decision`` body. Ready-gate → the priced menu →
    ``EX.decide_via_loop`` → the one poster. On a down stack (the bridge not answering, no
    decider configured, or ``/decide`` answering 503) the seam commits the DECLARED gate
    observation and the §6.5 unavailability record is appended (``regime: unavailable``,
    nothing to bind a verdict to)."""
    bridge = bridge if bridge is not None else BRIDGE
    if check_ready and not (ready if ready is not None else _ready)():
        return _down(question, run_id)
    post = post if post is not None else _post
    get = get if get is not None else _get
    transforms, curves = _menu(hold_out_question_id)
    try:
        view = EX.decide_via_loop(question, k, bridge=bridge, post=post, get=get,
                                  transforms=transforms, curves=curves)
    except urllib.error.HTTPError as e:
        if e.code != 503:
            raise
        print(f"  (decider unavailable: {e.reason})")
        return _down(question, run_id)
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"  (stack unreachable mid-question: {e})")
        return _down(question, run_id)
    return DriveResult(view, post_decision(post, bridge, question, view, run_id=run_id))


def _down(question: str, run_id: str | None) -> DriveResult:
    gated = SEAM.commit(None, gates=(SEAM.GATE_EXECUTOR_DOWN,))
    assert gated.action == "abstain"
    REC.record_unavailable(question, run_id=run_id)
    return DriveResult(None, None, down=True)


def react(decision_id: str, valence: str, *, post: Any = None) -> str:
    """Record the owner's one-bit verdict on a logged decision (``/log_reaction``) and name
    the fold fate — the in-session counterpart of ask-live's ``/react``. The verdict is one
    bit, never prose (the owner's free text is the loop's only expensive resource); a write
    failure is named, never silent."""
    post = post if post is not None else _post
    try:
        resp = post(f"{BRIDGE}/log_reaction",
                    {"decision_id": decision_id, "valence": valence}) or {}
    except Exception as e:
        return f"verdict not recorded: {e}"
    fate = FATE_FOLDS if resp.get("folds") else FATE_RECORDED
    return f"verdict {valence} on a {resp.get('chosen_action', '?')} decision — {fate}"
