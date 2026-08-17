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
hermetically testable (the executor's own seam, PRINCIPLES §5). A down stack is NAMED,
never silently substituted (the contract's invariant 3).
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from life_agent.core import config as CFG
from life_agent.core import decisions as DEC
from life_agent.core import executor as EX
from life_agent.core import shadow_mirror as SM
from life_agent.membrane import coarse as CRS

BRIDGE = os.environ.get("LIFE_AGENT_BRIDGE_URL", "http://127.0.0.1:8798")
DAEMON = os.environ.get("ANSWER_BRAIN_URL", "http://127.0.0.1:8799")
GROW_LANE = os.environ.get("LIFE_AGENT_GROW_LANE", "") == "1"
DOWN = ("No answer asserted — the executor is unavailable (the answer-brain "
        "daemon/bridge is not up; start it: bin/answer-brain).")
# The fold-fate vocabulary — ask-live's /react wording, one voice across surfaces.
FATE_FOLDS = "folds into the utility posterior on the next gate run"
FATE_RECORDED = "recorded — not folded (only abstain verdicts move the fold)"


# The narrative path (cold expand + 150-chunk rerank + synthesize, all cloud) can
# legitimately outrun the default read timeout; a client that hangs up mid-read
# leaves the single-threaded bridge writing to a dead socket (run-6 void).
_SLOW_ENDPOINTS = ("/narrative",)
_SLOW_TIMEOUT = 900


def post_json(url: str, payload: dict[str, Any], *,
              timeout: int | None = None) -> dict[str, Any] | None:
    """The ONE bridge/daemon POST transport (every client delegates here — three
    near-identical copies once hid the same defect). The bridge RETURNS a seam
    failure's name in the error body (server.py: "visible to the caller, never
    swallowed"); carry it in the raised error — the exception type stays HTTPError,
    so the fail-open transport contract is untouched. ``timeout=None`` picks the
    endpoint's budget (the slow narrative path gets more headroom)."""
    if timeout is None:
        timeout = _SLOW_TIMEOUT if url.endswith(_SLOW_ENDPOINTS) else 300
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            out: dict[str, Any] | None = json.loads(r.read())
            return out
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace") if e.fp else ""
        raise urllib.error.HTTPError(
            req.full_url, e.code, f"{e.reason} — {detail}" if detail else str(e.reason),
            e.hdrs, None) from e


def _post(url: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    return post_json(url, payload)


def _get(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=300) as r:
        out: dict[str, Any] = json.loads(r.read())
        return out


def _ready() -> bool:
    """Both services must answer /ready — a down stack is named, never guessed around."""
    for base in (BRIDGE, DAEMON):
        try:
            urllib.request.urlopen(f"{base}/ready", timeout=3)
        except Exception:
            return False
    return True


def answer(question: str, k: int = 20, *, post: Any = None, get: Any = None,
           check_ready: bool = True) -> tuple[str, str | None]:
    """Answer one question through the executor read-path; return
    ``(rendered reply, decision_id | None)``. The reply is the shared credence-grammar
    rendering (``executor.render_view``); the ``decision_id`` is the bridge's
    content-addressed id for the logged terminal decision — ``None`` when there is nothing
    foldable to bind (a miss / narrative / down stack). Logging is fail-open by contract:
    a calibration-log write never breaks the answer."""
    if check_ready and not _ready():
        return DOWN, None
    post = post if post is not None else _post
    get = get if get is not None else _get
    # The ONE question_id derivation (core.decisions.question_id) — the same key /log_decision
    # stamps on the decision below, so a mirrored decide tick and its decision join.
    question_id = DEC.question_id(question)
    if CFG.membrane_live():
        # M3: the live consult records its own enact tick — the decide mirror stays off
        # (one engine, one consult per tick), matching ask.py's read-path.
        live, wrapped = CRS.live_decide(BRIDGE, question_id), post
    else:
        live, wrapped = None, SM.shadow_wrapped_post(post, BRIDGE, question_id)
    view = EX.decide_via_loop(question, k, bridge=BRIDGE, daemon=DAEMON,
                              post=wrapped, get=get,
                              grow_lane=GROW_LANE, live=live)
    decision_id: str | None = None
    if (view["route"] is not None and view["effector"] in DEC.LOOKUP_ACTION_ORDER
            and view["credences"]):
        try:
            resp = post(f"{BRIDGE}/log_decision", {
                "question": question,
                "retrieval_keys": [h["artifact_cache_key"] for h in view["hits"]],
                "decision": {"effector": view["effector"], "credences": view["credences"],
                             "candidates": view["candidates"],
                             "p_none": view["p_none"] if view["p_none"] is not None else 0.0,
                             "eu": view["eu"] if view["eu"] is not None else 0.0,
                             "n_obs": view.get("n_obs", 0),
                             "n_indeterminate": view.get("n_indeterminate", 0),
                             "n_competing": view.get("n_competing", 0)}})
            decision_id = (resp or {}).get("decision_id")
        except Exception:
            decision_id = None  # fail-open: the verdict simply has nothing to bind to
    return EX.render_view(view), decision_id


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
