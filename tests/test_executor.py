"""The executor escalation policy (core/executor.py) — pure, hermetic (edges stubbed).

Pins the gate-relevant behaviours: the cheap path never touches the cloud; a calibrated floor
can demote a confident-but-unreliable local commit into escalation; the owner-scoped disagreement
check keeps a confirmed answer (q-001) and abstains on a withheld/contradicted one (q-002); a
local withhold lets the joint edge replace it.
"""
from __future__ import annotations

from life_agent.core import lookup as LK
from life_agent.core.calibration import ReliabilityCurve
from life_agent.core.executor import answer_question
from life_agent.core.joint_extract import JointResult

UB = {"u_correct": 1.0, "u_abstain": 0.0, "u_wrong": -9.0}   # p* = 9/10 = 0.90


def _flat(r: float) -> ReliabilityCurve:
    return ReliabilityCurve(bin_reliability=(r,) * 10)


def _lk(action: str = "report", value: str = "V1", cred: float = 0.95) -> LK.LookupResult:
    return LK.LookupResult(
        question="q?", construct="the value", action=action, eu=0.5,
        candidates=(value,), credences=(cred,), p_none=0.05, observations=(),
        n_hits=3, n_indeterminate=0, utility_fold_version="f" * 64,
        answer_cache_key="k" * 64, rendered="rendered")


def _jr(value: str | None, c: float = 0.95) -> JointResult:
    return JointResult(value=value, confidence=c, as_of=None, cache_key="j" * 64,
                       in_tokens=100, out_tokens=10)


class _Counter:
    def __init__(self, ret: object) -> None:
        self.ret = ret
        self.calls = 0
        self.last_args: tuple[object, ...] = ()

    def __call__(self, *a: object) -> object:
        self.calls += 1
        self.last_args = a
        return self.ret


def _run(*, owner_scoped: bool, local: LK.LookupResult | None, joint: JointResult,
         calib_local: float = 0.95, calib_joint: float = 0.95,
         joint_decide: LK.LookupResult | None = None):
    jx = _Counter(joint)
    jd = _Counter(joint_decide if joint_decide is not None else _lk(value="JV"))
    res = answer_question(
        owner_scoped=owner_scoped, u_bar=UB,
        calib_local=_flat(calib_local), calib_joint=_flat(calib_joint),
        local_fn=lambda: local, joint_extract_fn=jx, joint_decide_fn=jd)
    return res, jx, jd


def test_cheap_commit_never_touches_the_cloud() -> None:
    res, jx, _ = _run(owner_scoped=False, local=_lk(cred=0.95), joint=_jr("JV"))
    assert res.edge == "local" and res.cloud_tokens == 0
    assert jx.calls == 0  # the joint edge was never run


def test_calibration_demotes_a_confident_but_unreliable_local() -> None:
    # local reports at 0.95, but its calibrated reliability is 0.5 (< p*=0.90): escalate.
    res, jx, jd = _run(owner_scoped=False, local=_lk(cred=0.95), joint=_jr("JV"),
                       calib_local=0.5)
    assert jx.calls == 1 and res.edge == "joint" and jd.calls == 1


def test_owner_scoped_kept_when_joint_agrees() -> None:  # q-001
    res, jx, _ = _run(owner_scoped=True, local=_lk(value="VAL-A"),
                      joint=_jr("VAL-A"))
    assert res.edge == "local+verify" and res.result is not None
    assert res.result.action == "report" and res.result.candidates[0] == "VAL-A"
    assert jx.calls == 1 and res.cloud_tokens == 110


def test_owner_scoped_abstains_when_joint_withholds() -> None:  # q-002 (mother's passport)
    res, _, _ = _run(owner_scoped=True, local=_lk(value="VAL-A"), joint=_jr(None))
    assert res.edge == "verify_abstain"
    assert res.result is not None and res.result.action == "abstain"


def test_owner_scoped_abstains_when_joint_contradicts() -> None:
    res, _, _ = _run(owner_scoped=True, local=_lk(value="VAL-A"), joint=_jr("VAL-B"))
    assert res.edge == "verify_abstain" and res.result is not None
    assert res.result.action == "abstain"


def test_local_withhold_lets_joint_replace() -> None:
    res, jx, jd = _run(owner_scoped=False, local=_lk(action="abstain"), joint=_jr("JV"))
    assert res.edge == "joint" and jx.calls == 1 and jd.calls == 1


def test_joint_decide_receives_the_local_construct() -> None:
    # the joint edge folds at the local route's construct — the threading the live wiring needs
    # (decide_joint(root, question, construct, jr, ...) cannot be called without it).
    res, _, jd = _run(owner_scoped=False, local=_lk(action="abstain"), joint=_jr("JV"))
    assert res.edge == "joint" and jd.calls == 1
    assert jd.last_args[0].value == "JV"          # (jr, construct): the joint result first
    assert jd.last_args[1] == "the value"         # the local route's construct, threaded through


def test_local_withhold_and_joint_null_abstains() -> None:
    res, _, jd = _run(owner_scoped=True, local=_lk(action="abstain"), joint=_jr(None))
    assert res.edge == "joint_abstain" and jd.calls == 0
    assert res.result is not None and res.result.action == "abstain"


def test_no_lookup_route_is_a_miss() -> None:
    res, jx, _ = _run(owner_scoped=False, local=None, joint=_jr("JV"))
    assert res.edge == "miss" and res.result is None and jx.calls == 0
