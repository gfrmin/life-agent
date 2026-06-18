"""The answer executor — VOI schedules, calibration defends the gate (answer-executor plan).

One step of the decision rule, made concrete for P1: run the cheap ``extract@local`` edge and
``decide``; if it commits **above the calibrated runtime floor**, take it — unless the question is
owner-scoped, where attribution risk lives (a multi-subject document). There, and whenever local
withholds or is sub-floor, consult the subject-aware ``extract@<model>`` joint edge:

  * local **withheld / sub-floor** → the joint edge REPLACES the local channel
    (``decide_joint``: its calibrated confidence folds against the prior — the nested-dependence
    rule, since the joint read sees the same documents);
  * local **committed**, owner-scoped → a DISAGREEMENT CHECK: keep the local answer only if the
    joint edge AGREES on the value; a withhold or a contradiction → abstain. This is the v0 form
    of the finding-1 disagreement model — restricted to where it earns its keep (owner-scoped
    attribution), so it catches the mother's-passport case without over-rejecting a co-valid
    relational answer.

The gate (zero confident-wrong) is held by the **calibrated floor** and this disagreement check,
not by the scheduling — the VOI selectivity (skip the joint edge when contradiction is unlikely)
and ``brain.value`` net-VOI are the named P2/P3 refinements. The model's self-reported confidence
is mapped through the per-edge calibration curve (``core.calibration``) before it ever reaches a
floor or a fold; raw confidence is never trusted.

The edges are injected as callables so the policy is pure (and the credence-pi daemon home later
is a callable-swap).
"""
from __future__ import annotations

import dataclasses
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from life_agent.core import lookup as LK
from life_agent.core.brain import Brain
from life_agent.core.calibration import ReliabilityCurve
from life_agent.core.joint_extract import JointResult
from life_agent.core.matching import answer_matches

_COMMITTING = ("report", "report_scoped", "hedge")


@dataclass(frozen=True)
class ExecutorResult:
    """The executor's committed answer: the lookup-family result (None ⇒ MISS, the caller falls
    through to the narrative path), the edge that produced it, and the cloud tokens it cost."""

    result: LK.LookupResult | None
    edge: str
    cloud_tokens: int


def committed(action: str) -> bool:
    return action in _COMMITTING


def p_star(u_bar: dict[str, float]) -> float:
    """The assertion floor implied by the utility: report beats abstain iff the (calibrated)
    leader credence exceeds ``w/(1+w)``, ``w = |u_wrong|`` (decide.py)."""
    w = -u_bar.get("u_wrong", 0.0)
    return w / (1.0 + w) if w > 0 else 0.0


def calibrated_lead(result: LK.LookupResult, calib: ReliabilityCurve) -> float:
    """The leader's credence mapped through the edge's calibration curve — the value the runtime
    floor actually tests (never the raw posterior credence)."""
    return calib.calibrate(result.credences[0]) if result.credences else 0.0


def _agrees(local_value: str, joint_value: str) -> bool:
    return bool(local_value) and bool(joint_value) and (
        answer_matches(local_value, [], joint_value)
        or answer_matches(joint_value, [], local_value))


def _abstain_like(lk: LK.LookupResult) -> LK.LookupResult:
    """An abstain that still shows the held-back candidate(s) (the abstain-show-withheld
    contract) — used when the disagreement check vetoes a committed local answer."""
    r = dataclasses.replace(lk, action="abstain", eu=0.0, rendered="")
    return dataclasses.replace(r, rendered=LK.render(r))


def decide_joint(root: Path, question: str, construct: str, jr: JointResult,
                 calib: ReliabilityCurve, *, n_hits: int, brain: Brain | None = None,
                 decisions_path: Path | None = None, run_id: str = "ask") -> LK.LookupResult:
    """Fold a non-null joint extraction as a K=1 posterior at its CALIBRATED reliability and
    decide. ``rho_override = calib(c)`` (never raw ``c``); ``time_indexed=False`` because the
    joint prompt already prices currency into ``c`` (the as-of is carried for the render). The
    single observation re-folds against the prior — the nested-dependence "replace", not a pool
    with the local channel (which would re-introduce corroboration-count stale amplification)."""
    assert jr.value is not None
    r = calib.calibrate(jr.confidence)
    obs = LK.Observation(
        card_n=1, artifact_cache_key=jr.cache_key, obs_cache_key=jr.cache_key,
        value_raw=jr.value, value_norm=LK._norm_value(jr.value), quote="",
        authority_class="joint", authority=1.0, subject_factor=1.0, time_factor=1.0,
        doc_date=jr.as_of)
    return LK.decide_and_record(root, question, construct, [obs], 0, n_hits=n_hits,
                                time_indexed=False, brain=brain,
                                decisions_path=decisions_path, run_id=run_id, rho_override=r)


def answer_question(*, owner_scoped: bool, u_bar: dict[str, float],
                    calib_local: ReliabilityCurve, calib_joint: ReliabilityCurve,
                    local_fn: Callable[[], LK.LookupResult | None],
                    joint_extract_fn: Callable[[], JointResult],
                    joint_decide_fn: Callable[[JointResult, str], LK.LookupResult],
                    ) -> ExecutorResult:
    """One escalation step (P1). Edges injected: ``local_fn`` (the typed lookup answer, None ⇒
    MISS), ``joint_extract_fn`` (run the joint edge), ``joint_decide_fn(jr, construct)`` (fold a
    non-null joint result at the local route's ``construct`` — :func:`decide_joint`).

    v0 limitation, stated not silent: the joint edge only escalates from a *decided* local (a
    commit or a withhold-with-observations). When ``local_fn`` returns None — the route declined,
    or zero grounded observations (the pure attribution miss where every chunk is judged
    "different subject") — there is no construct to escalate from, so the step is a MISS and the
    caller falls through to the narrative path. Reaching the joint edge from a routing miss is a
    P2 concern (it needs a construct source)."""
    floor = p_star(u_bar)
    lk = local_fn()
    if lk is None:
        return ExecutorResult(None, "miss", 0)

    local_ok = committed(lk.action) and calibrated_lead(lk, calib_local) >= floor
    if local_ok and not owner_scoped:
        return ExecutorResult(lk, "local", 0)   # trust the cheap edge off the attribution path

    jr = joint_extract_fn()
    cloud = jr.in_tokens + jr.out_tokens

    if local_ok:  # owner-scoped commit → the disagreement check
        lead = lk.candidates[0] if lk.candidates else ""
        if jr.value is not None and _agrees(lead, jr.value):
            return ExecutorResult(lk, "local+verify", cloud)   # the joint edge confirms → keep
        return ExecutorResult(_abstain_like(lk), "verify_abstain", cloud)  # disagree → abstain

    # local withheld / sub-floor → the joint edge replaces it (at the local route's construct)
    if jr.value is None:
        return ExecutorResult(_abstain_like(lk), "joint_abstain", cloud)
    return ExecutorResult(joint_decide_fn(jr, lk.construct), "joint", cloud)
