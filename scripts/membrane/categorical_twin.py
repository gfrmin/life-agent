"""r46 leg D — the categorical twin: the diagnosis instrument.

Measures the E1 stage-1 categorical world (`membrane/categorical.py`) against both engine
arms, $0, and returns GD-13's decision — do the two worlds share one declaration of r44's
grid rule, or two. Every declaration a DELTA on the deployed `handshake_decl_cat`; the base
is the deployed rule, never re-implemented (`M-7`). Nothing deployed; the categorical world
stays env-disabled.

Legs (subcommands), each writing JSON to --out:
  handshake  K1  the categorical handshake, both arms, k in {2,3,5}, replies whole
  ladder     K2  the {codebooks, clock} declaration ladder on both arms
  grid       K3  GD-13: codebooks-required on arm B, and the theta grid's K-independence
  door       K4  the fourth menu-less evidence sender: refused on arm B, no-op repair on A
  inertness  K5  the r43 twin: menu-head firing without a clock, and clock routing

Arm B defaults to the deployed binary; arm A (the r41 pin) is a machine-local worktree path
with no baked default (PII) — pass --arm-a for the both-arm legs.
"""
from __future__ import annotations

import argparse
import copy
import json
import subprocess
import sys
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol

import membrane.report as R
from life_agent.core import config as C
from life_agent.membrane import categorical as CAT
from life_agent.membrane import world as W
from life_agent.membrane.client import MembraneClient, MembraneError

ARM_B_ENGINE = str(Path.home() / ".local/bin/proplang-host")
K_GRID: tuple[int, ...] = (2, 3, 5)


# --- declaration deltas (base = the deployed declaration; each pinned by a test) ---------


def base_cat_decl(u_bar: Mapping[str, float], k: int) -> dict[str, Any]:
    """A0 — the deployed categorical declaration, verbatim (the drift pin)."""
    return CAT.handshake_decl_cat(u_bar, k)


def theta_rule(u_bar: Mapping[str, float]) -> list[float]:
    """The ONE grid rule — r44's `theta_grid`, unchanged. It is K-INDEPENDENT (keyed on
    `u_bar` via the fixtures and the binary utility's crossings), which is the whole of
    GD-13's answer: the theta codebook parametrises the channel rate, not the candidate
    count. Re-exported here as the single declaration both worlds would bind."""
    return W.theta_grid(u_bar)


def cat_decl(
    u_bar: Mapping[str, float], k: int, *,
    codebooks: bool = False, clock: bool = False,
) -> dict[str, Any]:
    """The deployed categorical declaration plus optional r44 items — each an additive
    delta, so a mutation that drops one is visible."""
    decl = copy.deepcopy(base_cat_decl(u_bar, k))
    world = decl["world"]
    if codebooks:
        world["codebooks"] = {"theta": theta_rule(u_bar)}
    if clock:
        world["clock"] = [{"name": W.CLOCK_NAME, "price": W.clock_price(u_bar),
                           "batch": W.CLOCK_BATCH}]
    return decl


# --- wire helpers ------------------------------------------------------------------------


class _Client(Protocol):
    def request(self, obj: dict[str, Any]) -> dict[str, Any]: ...
    def shutdown(self) -> None: ...


def spawn(engine: str) -> MembraneClient:
    return MembraneClient.spawn([engine], log=lambda _m: None, read_timeout_s=900.0)


def hello(client: _Client, decl: dict[str, Any]) -> dict[str, Any]:
    """One handshake, its outcome recorded whole (`M-22`). A handshake refusal comes back
    as a parsed `{"error": ...}` object (valid JSON — NOT raised); a wire failure raises
    `MembraneError`. Both are captured, never a bare exception past the reading."""
    try:
        reply = client.request(decl)
    except MembraneError as e:
        return {"ok": None, "models": None, "error": None, "refused": str(e)}
    return {"ok": reply.get("ok"), "models": reply.get("models"),
            "error": reply.get("error"), "reply_keys": sorted(reply.keys())}


def tick(client: _Client, obj: dict[str, Any]) -> dict[str, Any]:
    """One tick, recorded whole. HEAD's tick refusals are invalid JSON (unescaped quotes,
    r45 A5), so they arrive as `MembraneError` under `"refused"` — captured verbatim."""
    try:
        return {"reply": client.request(obj)}
    except MembraneError as e:
        return {"refused": str(e)}


# --- K1: the handshake matrix ------------------------------------------------------------


def handshake_matrix(engines: Mapping[str, str], u_bar: Mapping[str, float]) -> dict[str, Any]:
    """Each arm and each k: the deployed categorical handshake, verbatim, reply recorded
    whole. Settles r45's 'cannot handshake at HEAD' claim either way."""
    out: dict[str, Any] = {}
    for arm, engine in engines.items():
        rows: dict[str, Any] = {}
        client = spawn(engine)
        try:
            for k in K_GRID:
                rows[str(k)] = hello(client, base_cat_decl(u_bar, k))
        finally:
            client.shutdown()
        out[arm] = rows
    return out


# --- K2: the {codebooks, clock} ladder ---------------------------------------------------


def ladder(engines: Mapping[str, str], u_bar: Mapping[str, float], k: int = 3) -> dict[str, Any]:
    """For each arm, the four declaration variants — which missing item actually bites.
    A delta that changes nothing is reported as a no-op, not dropped."""
    variants = {
        "base": cat_decl(u_bar, k),
        "codebooks": cat_decl(u_bar, k, codebooks=True),
        "clock": cat_decl(u_bar, k, clock=True),
        "codebooks+clock": cat_decl(u_bar, k, codebooks=True, clock=True),
    }
    out: dict[str, Any] = {}
    for arm, engine in engines.items():
        rows: dict[str, Any] = {}
        client = spawn(engine)
        try:
            for name, decl in variants.items():
                rows[name] = hello(client, decl)
        finally:
            client.shutdown()
        out[arm] = rows
    return out


# --- K3: GD-13 — one grid rule, and its K-independence -----------------------------------


def respond_arm_is_code_conditional() -> bool:
    """The structural fact GD-13's premise turns on: the categorical respond arm is
    `(= y (- act RESPOND_BASE))` — conditional on WHICH code y equals, NOT linear in a
    single scalar p1. So the binary `argmax_crossings` (which requires every row linear in
    one p1) has no categorical definition, and r44's crossings half does not transfer; the
    only defined theta rule is the K-independent one. Read off the deployed sentence."""
    said = CAT.utility_said_cat({"u_correct": 1.0, "u_wrong": -5.0})
    flat = json.dumps(said)
    # the respond arm compares y against (act - RESPOND_BASE): a code-conditional test.
    return '"-"' in flat and str(CAT.RESPOND_BASE) in flat and '"var", 1' in json.dumps(said)


def grid(engine_b: str, u_bar: Mapping[str, float]) -> dict[str, Any]:
    """GD-13's decision, measured. (a) does arm B REQUIRE codebooks for a categorical
    world (base refused ∧ base+codebooks ok)? (b) is the theta grid K-INDEPENDENT — the
    SAME rule/grid across k, models varying only through obs_arity? Plus the structural
    read that the categorical utility admits no crossings, so one rule is the only rule."""
    theta = theta_rule(u_bar)
    client = spawn(engine_b)
    try:
        base_k3 = hello(client, cat_decl(u_bar, 3))
        cb_k3 = hello(client, cat_decl(u_bar, 3, codebooks=True))
        # K-independence: same theta grid, varying k -> models moves ONLY via obs_arity.
        models_by_k = {
            str(k): hello(client, cat_decl(u_bar, k, codebooks=True)).get("models")
            for k in K_GRID
        }
        # the binary world's own count under the same rule, for the contrast.
        binary = hello(client, W.handshake_decl(u_bar))
    finally:
        client.shutdown()
    codebooks_required = (base_k3.get("ok") is not True) and (cb_k3.get("ok") is True)
    return {
        "codebooks_required_armB": codebooks_required,
        "base_reply": base_k3,
        "codebooks_reply": cb_k3,
        "theta_grid": theta,
        "theta_grid_len": len(theta),
        "theta_rule_is_k_independent": True,  # theta_rule takes no k; pinned by a test
        "models_by_k_with_codebooks": models_by_k,
        "binary_world_models": binary.get("models"),
        "respond_arm_code_conditional": respond_arm_is_code_conditional(),
    }


# --- K4: the fourth menu-less evidence sender --------------------------------------------


def _cat_summary(k: int, codes: tuple[int, ...]) -> CAT.CatSummary:
    return CAT.CatSummary(
        k=k, obs_codes=codes, n_obs=len(codes), n_obs_unmapped=0,
        daemon_map_index=None, era_split=False, owner_scoped=False, grow_pass=False,
    )


def door(engines: Mapping[str, str], u_bar: Mapping[str, float], k: int = 3) -> dict[str, Any]:
    """The categorical evidence tick is code-valued and menu-less. On arm B (codebooks
    added so the handshake passes) the menu-less tick must be REFUSED; the `menu:[act]`
    repair clears it and is a byte-identical no-op on arm A. Checked on the categorical
    tick itself, not inherited from leg C."""
    s = _cat_summary(k, (1,))
    feats = CAT.cat_features(s, 0.0)
    menuless = {"tick": {"features": feats, "evidence": 1}}
    withmenu = {"tick": {"features": feats, "evidence": 1, "menu": [W.ACT_NAME]}}
    out: dict[str, Any] = {}
    for arm, engine in engines.items():
        client = spawn(engine)
        try:
            hs = hello(client, cat_decl(u_bar, k, codebooks=True))
            row: dict[str, Any] = {"handshake_ok": hs.get("ok")}
            if hs.get("ok"):
                row["menuless"] = tick(client, menuless)
                # fresh session for the repaired tick (a refused tick can wedge the fold)
            client.shutdown()
            client = spawn(engine)
            hs2 = hello(client, cat_decl(u_bar, k, codebooks=True))
            if hs2.get("ok"):
                row["withmenu"] = tick(client, withmenu)
        finally:
            client.shutdown()
        out[arm] = row
    return out


# --- K5: the r43 inertness twin ----------------------------------------------------------


def _decide_once(
    client: _Client, decl: dict[str, Any], feats: Mapping[str, float],
) -> dict[str, Any]:
    """Handshake `decl`, then one decide tick (menu = [act]); return the reply whole."""
    hs = hello(client, decl)
    if hs.get("ok") is not True:
        return {"handshake": hs}
    return {"handshake_ok": True,
            "decide": tick(client, {"tick": {"features": dict(feats), "menu": [W.ACT_NAME]}})}


def inertness(engine_b: str, u_bar: Mapping[str, float], k: int = 3) -> dict[str, Any]:
    """r43's item-4 probe, categorical: permute the menu grid's ORDER. Without a clock the
    substituting chooser is not reached, so a utility-inert engine fires the menu HEAD
    regardless of order (r42/r43 signature). With a clock, selection should track the
    utility. Reported as the chosen act value under each permutation, no-clock vs clock."""
    s = _cat_summary(k, ())
    feats = CAT.cat_features(s, 0.0)
    grid_values = CAT.act_grid_cat(k)
    permutations = {
        "declared": list(grid_values),
        "respond_first": list(grid_values[3:]) + list(grid_values[:3]),
    }

    def chosen(decl_base: dict[str, Any], order: list[float]) -> Any:
        decl = copy.deepcopy(decl_base)
        decl["world"]["menu"] = [{"name": W.ACT_NAME, "grid": order}]
        client = spawn(engine_b)
        try:
            r = _decide_once(client, decl, feats)
        finally:
            client.shutdown()
        dec = r.get("decide", {}).get("reply", {})
        act = dec.get("act")
        return act.get(W.ACT_NAME) if isinstance(act, dict) else None

    no_clock = cat_decl(u_bar, k, codebooks=True)
    with_clock = cat_decl(u_bar, k, codebooks=True, clock=True)
    return {
        "grid_head_value": grid_values[0],
        "no_clock": {name: chosen(no_clock, order) for name, order in permutations.items()},
        "with_clock": {name: chosen(with_clock, order) for name, order in permutations.items()},
    }


# --- run stamp (M-28) --------------------------------------------------------------------


def run_stamp() -> dict[str, Any]:
    """The tree this run loaded, provable — head, dirty state, and the mtimes of every
    module on this leg's probe path, against the process start."""
    head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                          text=True, check=False).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain"], capture_output=True,
                           text=True, check=False).stdout.strip()
    mods = [__file__, W.__file__, CAT.__file__,
            sys.modules["life_agent.membrane.client"].__file__]
    return {"git_head": head, "dirty": bool(dirty),
            "mtimes": {str(m): Path(str(m)).stat().st_mtime for m in mods if m},
            "started": time.time()}


# --- driver ------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("leg", choices=["handshake", "ladder", "grid", "door", "inertness"])
    parser.add_argument("--out", required=True)
    parser.add_argument("--arm-a", default=None,
                        help="path to the arm-A (r41-pinned) engine binary")
    parser.add_argument("--arm-b", default=ARM_B_ENGINE)
    args = parser.parse_args(argv)

    u_bar = R.latest_boot_u_bar(R.load_shadow_records(C.membrane_shadow_log()), "said@1")
    if u_bar is None:
        print("no boot u_bar on the shadow log; cannot run.")
        return 1
    stamp = run_stamp()
    print(f"tree {stamp['git_head'][:12]} dirty={stamp['dirty']} leg={args.leg}")

    both = {"handshake", "ladder", "door"}
    if args.leg in both and args.arm_a is None:
        print("this leg reads both arms: pass --arm-a (the r41-pinned binary).")
        return 1

    engines = {"armA": args.arm_a, "armB": args.arm_b}
    if args.leg == "handshake":
        result: Any = handshake_matrix(engines, u_bar)
    elif args.leg == "ladder":
        result = ladder(engines, u_bar)
    elif args.leg == "grid":
        result = grid(args.arm_b, u_bar)
    elif args.leg == "door":
        result = door(engines, u_bar)
    else:
        result = inertness(args.arm_b, u_bar)

    stamp["finished"] = time.time()
    stamp["mtimes_at_end"] = {p: Path(p).stat().st_mtime for p in stamp["mtimes"]}
    Path(args.out).write_text(json.dumps(
        {"leg": args.leg, "u_bar": dict(u_bar), "stamp": stamp, "result": result},
        indent=1, sort_keys=True), encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
