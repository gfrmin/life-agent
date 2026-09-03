"""act_conditioning.py — r46c: the admissible act-conditioning arrangement, measured.

Pre-registration: `docs/unification/reports/r46c-act-conditioning-preregistration.md`
(committed before any probe here ran). The question, from r45: can one world both
condition on the act and choose it — and if not, what two-world arrangement is
admissible? Leg A's sharpened target rides along: the p1 ceiling, not the affordance
constant, is what blocks a commit-pricing §18 bar.

Every declaration this instrument sends is a DELTA on the deployed one
(`world.handshake_decl`, `session.evidence_tick_body` — `M-7`), pinned by
`tests/test_act_conditioning.py`. Every reply stream is read whole (`M-22`): a refusal
arrives either as a parsed ``{"error": ...}`` or as the `MembraneError` r45's client
repair raises on HEAD's malformed refusal line — both are recorded verbatim.

Legs (subcommands), each writing JSON to --out:
  admissibility — K1: handshake / evidence / decide per arrangement, per arm
  inertness     — K2: A0 one-point-menu control + the M-25 discriminating control
  conditioning  — K3: act-distinct vs act-identical streams, mirrored + observer
  selection     — K4: act-separable teach, then decide vs `argmax_action`
  ceiling       — K5: prequential fold of the joined verdict universe (arm B)

Run: `uv run --project . python scripts/membrane/act_conditioning.py <leg> --out f.json`
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Protocol

sys.path.insert(0, "scripts")

import membrane.report as R
from life_agent.core import config as C
from life_agent.membrane import coarse as CO
from life_agent.membrane import world as W
from life_agent.membrane.client import MembraneClient, MembraneError
from life_agent.membrane.session import evidence_tick_body
from life_agent.membrane.shadow import boot_snapshot

MIRROR_NAME = "act-taken"
DISCRIMINATING_GRID: list[float] = [1.5, 2.5, 3.5]  # r45 A3's corrected grid, acts 1-4

ARM_B_ENGINE = str(Path.home() / ".local/bin/proplang-host")
# arm A (the r41 pin) lives in a machine-local worktree: no baked default — pass
# --arm-a explicitly for the both-arm legs (the run stamp records what was passed).


# --- the declared deltas (each pinned by a test; the base is the deployed declaration) ---


def base_decl(u_bar: Mapping[str, float]) -> dict[str, Any]:
    """A0 — the deployed declaration, verbatim (the drift pin)."""
    return W.handshake_decl(u_bar)


def mirrored_decl(u_bar: Mapping[str, float]) -> dict[str, Any]:
    """A1 — one world, one extra NON-writable name: `act-taken` guarded on the
    discriminating grid; menu untouched, so the world still decides."""
    decl = W.handshake_decl(u_bar)
    world = decl["world"]
    world["namespace"] = [*world["namespace"], MIRROR_NAME]
    world["guards"] = [*world["guards"],
                       {"name": MIRROR_NAME, "grid": list(DISCRIMINATING_GRID)}]
    return decl


def observer_decl(u_bar: Mapping[str, float]) -> dict[str, Any]:
    """A2's observer — r45 A4's shape: `act` out of the menu, guarded on the
    discriminating grid. It conditions; whether anything is READABLE is measured."""
    decl = W.handshake_decl(u_bar)
    world = decl["world"]
    world["menu"] = []
    world["guards"] = [*world["guards"],
                       {"name": W.ACT_NAME, "grid": list(DISCRIMINATING_GRID)}]
    return decl


def pinned_decl(u_bar: Mapping[str, float], act_name: str) -> dict[str, Any]:
    """A0's control shape — the deployed declaration with a ONE-POINT menu grid
    (r45 A2's method: one session per pinned act)."""
    decl = W.handshake_decl(u_bar)
    decl["world"]["menu"] = [{"name": W.ACT_NAME, "grid": [W._VALUE_FOR[act_name]]}]
    return decl


def act_value(chosen_action: str) -> float | None:
    """`_VALUE_FOR[REAL_TO_MEMBRANE[chosen_action]]` — the ONE declared projection.
    `None` names an unmapped action; the caller records the exclusion, never drops it."""
    name = W.REAL_TO_MEMBRANE.get(chosen_action)
    return None if name is None else W._VALUE_FOR[name]


def observer_tick(features: Mapping[str, float], y: int) -> dict[str, Any]:
    """The observer world's evidence tick: THE declared body minus its menu (the
    observer has no writable name; `act` arrives as a feature instead)."""
    body = evidence_tick_body(features, y)
    return {k: v for k, v in body.items() if k != "menu"}


def mirrored_tick(features: Mapping[str, float], y: int, value: float) -> dict[str, Any]:
    """A1's evidence tick: THE declared body, with the recorded act's value riding as
    the `act-taken` feature."""
    return evidence_tick_body({**dict(features), MIRROR_NAME: value}, y)


# --- wire helpers ------------------------------------------------------------------------


class _Client(Protocol):
    def request(self, obj: dict[str, Any]) -> dict[str, Any]: ...


def try_request(client: _Client, obj: dict[str, Any]) -> dict[str, Any]:
    """One request, its outcome recorded whole (`M-22`): the parsed reply, or the
    refusal/parse failure verbatim under `"refused"`."""
    try:
        return {"reply": client.request(obj)}
    except MembraneError as e:
        return {"refused": str(e)}


def spawn(engine: str) -> MembraneClient:
    return MembraneClient.spawn([engine], log=lambda _m: None, read_timeout_s=900.0)


def _summary(n: int, leader: float | None = 0.9) -> W.DecideSummary:
    return W.DecideSummary(
        n_candidates=n, leader_credence=leader, p_none=0.05, n_obs=n,
        era_split=False, owner_scoped=False, grow_pass=False)


def _fixed_stream() -> list[tuple[W.DecideSummary, int]]:
    """The fixed synthetic evidence stream (n=8, deterministic — no corpus content)."""
    return [(_summary(1 + (i % 4), leader=0.5 + 0.1 * (i % 4)), i % 2) for i in range(8)]


def _teach_stream(n: int = 24) -> list[tuple[W.DecideSummary, int, float]]:
    """A stream whose act-taken VARIES over the grid and CORRELATES with y (y=1 iff the
    act value is <= 2), so a world that conditions on act-taken can learn it. Synthetic,
    deterministic, no corpus content. The act-identical control folds ONE act value."""
    out = []
    for i in range(n):
        v = float(1 + (i % 4))
        out.append((_summary(1 + (i % 3), leader=0.6), 1 if v <= 2.0 else 0, v))
    return out


def decide_msg(s: W.DecideSummary, t: float,
               extra: Mapping[str, float] | None = None,
               menu: list[str] | None = None) -> dict[str, Any]:
    """`MembraneSession.decide`'s own message shape (features + the writable menu),
    with an optional extra feature (the conditional probe) or menu override."""
    feats = dict(W.shadow_features(s, t))
    if extra:
        feats.update(extra)
    return {"tick": {"features": feats,
                     "menu": [W.ACT_NAME] if menu is None else menu}}


def _p1(outcome: Mapping[str, Any]) -> float | None:
    reply = outcome.get("reply")
    if not isinstance(reply, Mapping):
        return None
    v = reply.get("p1")
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def run_stamp() -> dict[str, Any]:
    """M-28: the tree this run loaded, provable — head, dirty state, and the mtimes of
    every module on the probe path, recorded against the process start."""
    head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                          text=True, check=False).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain"], capture_output=True,
                           text=True, check=False).stdout.strip()
    mods = [__file__, W.__file__, CO.__file__,
            sys.modules["life_agent.membrane.session"].__file__,
            sys.modules["life_agent.membrane.shadow"].__file__]
    return {"git_head": head, "dirty": bool(dirty),
            "mtimes": {str(m): Path(str(m)).stat().st_mtime for m in mods if m},
            "started": time.time()}


# --- K1: admissibility -------------------------------------------------------------------


def admissibility_matrix(engines: Mapping[str, str],
                         u_bar: Mapping[str, float]) -> dict[str, Any]:
    """Handshake / evidence tick / decide / menu-less decide, per arrangement per arm.
    Every cell an outcome dict (reply or refusal, verbatim)."""
    s = _summary(2)
    worlds: dict[str, tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] = {
        "shipped": (base_decl(u_bar),
                    {"tick": evidence_tick_body(W.shadow_features(s, 0.0), 1)},
                    decide_msg(s, 1.0)),
        "mirrored": (mirrored_decl(u_bar),
                     {"tick": mirrored_tick(W.shadow_features(s, 0.0), 1, 2.0)},
                     decide_msg(s, 1.0)),
        "observer": (observer_decl(u_bar),
                     {"tick": observer_tick(
                         {**W.shadow_features(s, 0.0), W.ACT_NAME: 2.0}, 1)},
                     decide_msg(s, 1.0, extra={W.ACT_NAME: 2.0}, menu=[])),
    }
    out: dict[str, Any] = {}
    for arm, engine in engines.items():
        for wname, (decl, ev, dc) in worlds.items():
            client = spawn(engine)
            try:
                cell: dict[str, Any] = {"handshake": try_request(client, decl)}
                cell["evidence"] = try_request(client, ev)
                cell["decide"] = try_request(client, dc)
                # the door question P4 leaves open: a decide MISSING the new name
                if wname == "mirrored":
                    cell["decide_plain"] = cell.pop("decide")
                    cell["decide_conditional"] = try_request(
                        client, decide_msg(_summary(2), 2.0, extra={MIRROR_NAME: 2.0}))
            finally:
                client.shutdown()
            out[f"{arm}/{wname}"] = cell
    return out


# --- K2: the inertness null, and the control that can actually fail it -------------------


def inertness(engine: str, u_bar: Mapping[str, float]) -> dict[str, Any]:
    """A0: one session per pinned act over ONE fixed stream — distinct-p1 count must be
    1. Control (`M-25`, varying the ACT axis on a discriminating grid): observer-world
    sessions whose streams differ ONLY in act values — p1 must differ."""
    stream = _fixed_stream()
    p1s: dict[str, float | None] = {}
    for act_name, _v in W.AFFORDANCES:
        client = spawn(engine)
        try:
            client.request(pinned_decl(u_bar, act_name))
            for s, y in stream:
                client.request({"tick": evidence_tick_body(
                    W.shadow_features(s, 0.0), y)})
            p1s[act_name] = _p1(try_request(client, decide_msg(_summary(2), 8.0)))
        finally:
            client.shutdown()

    # M-25 control (the A4-shape observer world): fold ONE teach stream where act
    # correlates with y, then read the conditional p1 ACROSS the discriminating grid on
    # the SAME trained model — the alternative the null denies must be EXPRESSIBLE. A
    # constant-act stream cannot teach conditioning (that mis-build is disclosed in the
    # report), so the teach is what makes distinct>1 a real detector rather than noise.
    control_client = spawn(engine)
    try:
        control_client.request(mirrored_decl(u_bar))
        t_ev = 0.0
        for s, y, v in _teach_stream():
            control_client.request({"tick": mirrored_tick(
                W.shadow_features(s, t_ev), y, v)})
            t_ev += 1.0
        control = {str(v): _p1(try_request(control_client, decide_msg(
            _summary(2), t_ev, extra={MIRROR_NAME: v})))
            for v in W.ACT_GRID}
    finally:
        control_client.shutdown()
    control_distinct = len({round(v, 12) for v in control.values() if v is not None})
    return {"pinned_p1": p1s,
            "distinct": len({v for v in p1s.values() if v is not None}),
            "m25_control_conditional_p1": control,
            "m25_control_distinct": control_distinct}


# --- K3: conditioning existence ----------------------------------------------------------


def conditioning(engine: str, u_bar: Mapping[str, float]) -> dict[str, Any]:
    """K3, read via the conditional readout (the only shape arm B's door admits — a
    plain decide missing act-taken is refused). Fold two teach streams that DISAGREE on
    what act-taken predicts (hi: act<=2 -> y=1; lo: act<=2 -> y=0), then read the
    conditional p1 at a FIXED query act. Distinct across the two folds ⇒ the fold
    conditions on act-taken. An act-identical control (fold hi twice) must be identical."""

    def fold_and_probe(flip: bool) -> dict[str, Any]:
        client = spawn(engine)
        try:
            client.request(mirrored_decl(u_bar))
            t_ev = 0.0
            for s, y, v in _teach_stream():
                yy = (1 - y) if flip else y
                client.request({"tick": mirrored_tick(W.shadow_features(s, t_ev), yy, v)})
                t_ev += 1.0
            conditional = {
                str(cv): _p1(try_request(client, decide_msg(
                    _summary(2), t_ev, extra={MIRROR_NAME: cv})))
                for cv in W.ACT_GRID}
            return {"conditional": conditional, "t": t_ev}
        finally:
            client.shutdown()

    hi = fold_and_probe(flip=False)
    lo = fold_and_probe(flip=True)
    hi2 = fold_and_probe(flip=False)
    q = "1.0"  # the fixed query act: act-taken = abstain-value
    hi_q, lo_q, hi2_q = (d["conditional"][q] for d in (hi, lo, hi2))
    return {"teach_hi": hi, "teach_lo": lo, "teach_hi_again": hi2,
            "query_act": q,
            "p1_hi": hi_q, "p1_lo": lo_q, "p1_hi_again": hi2_q,
            "distinct_streams_differ": (hi_q is not None and lo_q is not None
                                        and hi_q != lo_q),
            "identical_streams_identical": hi_q == hi2_q}


# --- K4: the selection contract ----------------------------------------------------------


def selection(engine: str, u_bar: Mapping[str, float]) -> dict[str, Any]:
    """Teach an act-separable pattern in the mirrored world (y=1 iff act-taken ≤ 2),
    then decide: the chosen act must equal `argmax_action(u_bar, reply p1)` (#15 read
    forward — selection cannot see per-candidate conditionals)."""
    client = spawn(engine)
    try:
        client.request(mirrored_decl(u_bar))
        t = 0.0
        for i in range(12):
            v = float(1 + (i % 4))
            y = 1 if v <= 2.0 else 0
            client.request({"tick": mirrored_tick(
                W.shadow_features(_summary(1 + (i % 3)), t), y, v)})
            t += 1.0
        # the decide MUST carry act-taken (arm B's door), so selection is read at a
        # fixed conditioning value — the chosen act is the menu pick, act-taken is the
        # observed covariate; #15 says the covariate cannot reach the candidate ranking.
        outcome = try_request(client, decide_msg(_summary(2), t, extra={MIRROR_NAME: 1.0}))
        reply = outcome.get("reply") or {}
        chosen = (reply.get("act") or {}).get(W.ACT_NAME)
        p1 = _p1(outcome)
        expected = None if p1 is None else W.argmax_action(u_bar, p1)
        chosen_name = W.VALUE_TO_ACTION.get(chosen) if chosen is not None else None
        return {"outcome": outcome, "chosen": chosen_name, "p1": p1,
                "argmax_at_p1": expected,
                "contract_holds": chosen_name is not None and chosen_name == expected}
    finally:
        client.shutdown()


# --- K5: the ceiling leg -----------------------------------------------------------------


def ceiling_pass(client: _Client, rows: Sequence[tuple[W.DecideSummary, int, str]],
                 conditional_values: Sequence[float]) -> list[dict[str, Any]]:
    """Prequential over the joined universe: probe row i's decide (plain + one per
    conditional value) BEFORE folding row i's evidence. An unmapped recorded action is
    named and skipped — never folded, never silently dropped."""
    out: list[dict[str, Any]] = []
    t = 0.0
    for i, (s, y, action) in enumerate(rows):
        v = act_value(action)
        if v is None:
            out.append({"i": i, "recorded_action": action, "skipped": "unmapped-action"})
            continue
        feats = W.shadow_features(s, t)
        # every mirrored-world decide MUST carry act-taken (arm B's door refuses a decide
        # missing a declared name), so there is no "plain" mirrored decide — the
        # conditional readouts ARE the decides; the pooled (unconditional) ceiling comes
        # from pooled_pass over the deployed world. Probe BEFORE folding row i (K5).
        probes = {
            str(cv): try_request(client, {"tick": {
                "features": {**dict(feats), MIRROR_NAME: cv},
                "menu": [W.ACT_NAME]}})
            for cv in conditional_values}
        p1_by_value = {k: _p1(o) for k, o in probes.items()}
        client.request({"tick": mirrored_tick(feats, y, v)})
        t += 1.0
        refusals = {k: o["refused"] for k, o in probes.items() if "refused" in o}
        out.append({"i": i, "recorded_action": action, "y": y, "act_value": v,
                    "p1_by_value": p1_by_value,
                    "refused": refusals or None})
    return out


def pooled_pass(client: _Client,
                rows: Sequence[tuple[W.DecideSummary, int, str]]) -> list[dict[str, Any]]:
    """The A0 reference on the same universe: the deployed declaration, THE declared
    evidence body, a plain decide per row — the pooled p1 trace."""
    out: list[dict[str, Any]] = []
    t = 0.0
    for i, (s, y, _action) in enumerate(rows):
        feats = W.shadow_features(s, t)
        plain = try_request(client, {"tick": {"features": dict(feats),
                                              "menu": [W.ACT_NAME]}})
        client.request({"tick": evidence_tick_body(feats, y)})
        t += 1.0
        out.append({"i": i, "p1": _p1(plain)})
    return out


def locate_commit_bar(payload: dict[str, Any], dec: dict[str, Any]) -> float | None:
    """The mapped surface's commit bar, LOCATED by bisecting the deployed
    `coarse.map_action` on an exhausted exchange (leg A's method — swept, never spelled
    as a formula). None when no flip exists in [0, 1]."""
    def commits(p1: float) -> bool:
        view, _deg = CO.map_action(payload, dec, "gather", {"p1": p1})
        return view.get("effector") == "report"
    if commits(0.0) or not commits(1.0):
        return None
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2.0
        if commits(mid):
            hi = mid
        else:
            lo = mid
    return hi


def joined_rows() -> list[tuple[W.DecideSummary, int, str]]:
    """The universe (K6): boot_snapshot's verdict join with the K9 act field — the SAME
    join the deployed boot replays, never re-implemented."""
    snap = boot_snapshot(C.DECISIONS_LOG, C.REACTIONS_LOG, None,
                         claude_verdicts_path=C.CLAUDE_VERDICTS_LOG)
    return [(s, y, a) for (s, y), a in
            zip(snap.verdict_replay, snap.verdict_actions, strict=True)]


def ceiling(engine: str, u_bar: Mapping[str, float]) -> dict[str, Any]:
    rows = joined_rows()
    if not rows:
        raise SystemExit("K6: empty joined universe — the leg fails rather than reads")
    bar_payload = {"applied_probes": [], "transforms": [], "u_bar": dict(u_bar),
                   "candidates": ["a", "b"]}
    bar_dec = {"effector": "abstain", "credences": [0.9, 0.1], "p_none": 0.0}
    bar = locate_commit_bar(bar_payload, bar_dec)

    t0 = time.process_time(), time.time()
    client = spawn(engine)
    try:
        hs_m = try_request(client, mirrored_decl(u_bar))
        mirrored = ceiling_pass(client, rows, conditional_values=list(W.ACT_GRID))
    finally:
        client.shutdown()
    t1 = time.process_time(), time.time()
    client = spawn(engine)
    try:
        hs_p = try_request(client, base_decl(u_bar))
        pooled = pooled_pass(client, rows)
    finally:
        client.shutdown()
    t2 = time.process_time(), time.time()

    def mx(vals: list[float | None]) -> float | None:
        xs = [v for v in vals if v is not None]
        return max(xs) if xs else None

    cond_ceiling = mx([p for r in mirrored if "skipped" not in r
                       for p in r["p1_by_value"].values()])
    pooled_ceiling = mx([r.get("p1") for r in pooled])
    return {"universe": len(rows),
            "skipped": sum(1 for r in mirrored if "skipped" in r),
            "refused_probe_rows": sum(1 for r in mirrored if r.get("refused")),
            "handshakes": {"mirrored": hs_m, "pooled": hs_p},
            "commit_bar": bar,
            "respond_threshold_raw_menu": W.respond_threshold(u_bar),
            "ceilings": {"mirrored_conditional_max": cond_ceiling,
                         "pooled": pooled_ceiling},
            "gaps_to_bar": {k: (None if v is None or bar is None else bar - v)
                            for k, v in (("mirrored_conditional_max", cond_ceiling),
                                         ("pooled", pooled_ceiling))},
            "wall_s": {"mirrored": t1[1] - t0[1], "pooled": t2[1] - t1[1]},
            "rows_mirrored": mirrored, "rows_pooled": pooled}


# --- driver ------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("leg", choices=["admissibility", "inertness", "conditioning",
                                        "selection", "ceiling"])
    parser.add_argument("--out", required=True)
    parser.add_argument("--arm-a", default=None,
                        help="path to the arm-A (pinned) engine binary")
    parser.add_argument("--arm-b", default=ARM_B_ENGINE)
    args = parser.parse_args(argv)

    u_bar = R.latest_boot_u_bar(
        R.load_shadow_records(C.membrane_shadow_log()), "said@1")
    if u_bar is None:
        print("no boot u_bar on the shadow log; cannot run.")
        return 1
    stamp = run_stamp()
    print(f"tree {stamp['git_head'][:12]} dirty={stamp['dirty']} leg={args.leg}")

    if args.leg != "ceiling" and args.arm_a is None:
        print("this leg reads both arms: pass --arm-a (the r41-pinned binary).")
        return 1

    if args.leg == "admissibility":
        result: dict[str, Any] = admissibility_matrix(
            {"armA": args.arm_a, "armB": args.arm_b}, u_bar)
    elif args.leg == "inertness":
        result = {arm: inertness(eng, u_bar)
                  for arm, eng in (("armA", args.arm_a), ("armB", args.arm_b))}
    elif args.leg == "conditioning":
        result = {arm: conditioning(eng, u_bar)
                  for arm, eng in (("armA", args.arm_a), ("armB", args.arm_b))}
    elif args.leg == "selection":
        result = {arm: selection(eng, u_bar)
                  for arm, eng in (("armA", args.arm_a), ("armB", args.arm_b))}
    else:
        result = ceiling(args.arm_b, u_bar)

    stamp["finished"] = time.time()
    stamp["mtimes_at_end"] = {p: Path(p).stat().st_mtime for p in stamp["mtimes"]}
    Path(args.out).write_text(json.dumps(
        {"leg": args.leg, "u_bar": dict(u_bar), "stamp": stamp, "result": result},
        indent=1, sort_keys=True), encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
