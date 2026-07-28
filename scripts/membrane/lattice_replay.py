"""lattice_replay.py — offline experiment: what does the FOLDED engine actually commit?

The seed for P3 (the pre-registered gate run) and the reproducer for register §17.4. It
answers the question `scripts/membrane/report.py` §2e could not: not the p1 the daemon
*logged* (those decide rows are pre-fold, cold at the marginal), but the p1 the engine
*would commit under* once the verdict stream is folded.

Method (offline; needs the real `proplang-host` binary; touches no frozen module): for a
chosen guard lattice (a subset of `world.indicator_names()`'s families), spawn the engine,
replay the real 193-tick verdict stream as evidence, then probe `decide()` on each verdicted
question and price the engine's ACTUAL exhaustion-commit policy (respond iff `world.eu_by_action`
picks respond at that question's own p1 — `coarse._gather`'s restricted argmax) against the
Claude verdict labels. The "full" variant's handshake/features are IDENTICAL to
`world.handshake_decl`/`world.shadow_features` by construction (a drift test in
`tests/test_lattice_replay.py` pins this), so the FULL run reproduces the live folded engine —
and it reproduces the §17.2 smoke's p1 to the digit.

Finding (2026-07-28, register §17.4): post-fold the FULL lattice p1 TRACKS leader_credence
(spread ~0.43, not the 0.003 §2e reads pre-fold); the engine's actual commit policy is
**+0.043 EU/q**, not the respond-ALL counterfactual -0.75; narrowing to leader-credence only
raises it to +0.284/q by *coarsening* into a ge90-only gate, not by identifying better. ALL of
this is IN-SAMPLE — each question's verdict is folded before its own p1 is probed and scored
against that same label — so it is a fit, not a forecast; P3's held-out gate is the arbiter.

Run (needs the engine): `uv run --project . python scripts/membrane/lattice_replay.py`
"""
from __future__ import annotations

import argparse
import statistics as st
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

sys.path.insert(0, "scripts")

import membrane.report as R
from life_agent.core import config as C
from life_agent.membrane import world as W
from life_agent.membrane.client import MembraneClient
from life_agent.membrane.shadow import boot_snapshot

DEFAULT_ENGINE = str(Path.home() / ".local/bin/proplang-host")

# The indicator FAMILIES, each mapped to its one-hot names (world.py's own bucket tuples —
# read, never re-spelled, so a variant cannot drift from the frozen vocabulary).
FAMILY_NAMES: dict[str, list[str]] = {
    "n-candidates": [f"n-candidates={b}" for b in W._CANDIDATES_BUCKETS],
    "leader-credence": [f"leader-credence={b}" for b in W._CREDENCE_BUCKETS],
    "p-none": [f"p-none={b}" for b in W._P_NONE_BUCKETS],
    "n-obs": [f"n-obs={b}" for b in W._OBS_BUCKETS],
    "flags": [f"{fam}=1" for fam in W._FLAG_FAMILIES],
}
ALL_FAMILIES: list[str] = list(FAMILY_NAMES)

_CREDENCE_EDGES: tuple[tuple[float, float, str], ...] = (
    (0.0, 0.5, "lt50"), (0.5, 0.7, "50-70"), (0.7, 0.8, "70-80"),
    (0.8, 0.9, "80-90"), (0.9, 1.01, "ge90"),
)


def indicator_names_for(families: Sequence[str]) -> list[str]:
    names: list[str] = []
    for fam in families:
        names += FAMILY_NAMES[fam]
    return names


def handshake_for(u_bar: Mapping[str, float], families: Sequence[str]) -> dict[str, Any]:
    """A narrowed handshake: only the chosen families' guards; menu + utility identical to
    `world.handshake_decl`. With `families == ALL_FAMILIES` this equals it byte-for-byte."""
    names = indicator_names_for(families)
    return {
        "membrane": 1,
        "world": {
            "namespace": ["t", *names, W.ACT_NAME],
            "guards": [{"name": n, "grid": [0.5]} for n in names],
            "menu": [{"name": W.ACT_NAME, "grid": list(W.ACT_GRID)}],
            "utility": {"form": "said@1", "said": W.utility_said(u_bar)},
        },
    }


def features_for(s: W.DecideSummary, t: float, families: Sequence[str]) -> dict[str, float]:
    """`world.shadow_features` filtered to the chosen families. With `families == ALL_FAMILIES`
    this equals it exactly (the drift test pins this)."""
    fam = set(families)
    feats: dict[str, float] = {"t": t}
    if "n-candidates" in fam:
        feats[f"n-candidates={W._candidates_bucket(s.n_candidates)}"] = 1.0
    if "leader-credence" in fam and s.leader_credence is not None:
        feats[f"leader-credence={W._credence_bucket(s.leader_credence)}"] = 1.0
    if "p-none" in fam and s.p_none is not None:
        feats[f"p-none={W._p_none_bucket(s.p_none)}"] = 1.0
    if "n-obs" in fam:
        feats[f"n-obs={W._obs_bucket(s.n_obs)}"] = 1.0
    if "flags" in fam:
        if s.era_split:
            feats["era-split=1"] = 1.0
        if s.owner_scoped:
            feats["owner-scoped=1"] = 1.0
        if s.grow_pass:
            feats["grow-pass=1"] = 1.0
    return feats


def commits_respond(u_bar: Mapping[str, float], p1: float) -> bool:
    """The engine's actual exhaustion commit (`coarse._gather` restricted argmax): respond iff
    it wins `{abstain, ask, respond}` at this p1 under the world's one utility."""
    eus = W.eu_by_action(u_bar, p1)
    return max((a for a in eus if a != "gather"), key=lambda a: eus[a]) == "respond"


def _p1(reply: Mapping[str, Any]) -> float | None:
    v = reply.get("p1")
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def run_variant(
    name: str, families: Sequence[str], u_bar: Mapping[str, float],
    replay: Sequence[tuple[W.DecideSummary, int]], engine: str,
) -> dict[str, Any]:
    client = MembraneClient.spawn([engine], log=lambda _m: None, read_timeout_s=300.0)
    try:
        hs = client.request(handshake_for(u_bar, families))
        if not hs.get("ok"):
            print(f"[{name}] handshake refused: {hs!r}")
            return {}
        models = hs.get("models")
        t = 0
        for s, y in replay:
            client.request({"tick": {"features": features_for(s, float(t), families),
                                     "evidence": int(y)}})
            t += 1
        rows: list[tuple[float, float | None, int]] = []
        for s, y in replay:
            if s.leader_credence is None:
                continue
            dec = client.request({"tick": {"features": features_for(s, float(t), families),
                                           "menu": [W.ACT_NAME]}})
            rows.append((s.leader_credence, _p1(dec), y))
    finally:
        client.shutdown()

    u0r, u1r = W.utility_by_action(u_bar)["respond"]
    ua = W.utility_by_action(u_bar)["abstain"][0]
    p1s = [p for _, p, _ in rows if p is not None]
    spread = (max(p1s) - min(p1s)) if p1s else 0.0
    print(f"\n=== {name}  (families={list(families)}, models={models}, n={len(rows)}) ===")
    print(f"{'bucket':>8} {'n':>3} {'correct':>8} {'mean_p1':>8} {'n_resp':>7} {'policyEU/q':>10}")
    pol_total = respond_all = 0.0
    for lo, hi, bname in _CREDENCE_EDGES:
        g = [r for r in rows if lo <= r[0] < hi]
        if not g:
            continue
        c = sum(y for *_, y in g) / len(g)
        nresp = 0
        pol = 0.0
        for _lc, p, y in g:
            respond_all += u1r if y else u0r
            if p is not None and commits_respond(u_bar, p):
                nresp += 1
                pol += u1r if y else u0r
            else:
                pol += ua
        pol_total += pol
        mp1 = st.mean(p for _, p, _ in g if p is not None)
        print(f"{bname:>8} {len(g):>3} {c:>8.3f} {mp1:>8.4f} {nresp:>7} {pol/len(g):>+10.3f}")
    n = len(rows)
    policy_eu = pol_total / n if n else 0.0
    respond_all_eu = respond_all / n if n else 0.0
    print(f"  p1 spread: {spread:.4f} (report §2e reads 0.0031 PRE-FOLD)")
    print(f"  ENGINE ACTUAL policy (respond iff p1>bar): {policy_eu:+.3f} EU/q  "
          f"vs respond-ALL: {respond_all_eu:+.3f}  vs abstain 0")
    return {"name": name, "models": models, "n": n, "p1_spread": spread,
            "policy_eu_per_q": policy_eu, "respond_all_eu_per_q": respond_all_eu}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", default=DEFAULT_ENGINE)
    args = parser.parse_args(argv)

    snap = boot_snapshot(C.DECISIONS_LOG, C.REACTIONS_LOG, None,
                         claude_verdicts_path=C.CLAUDE_VERDICTS_LOG)
    replay = snap.verdict_replay
    u_bar = R.latest_boot_u_bar(R.load_shadow_records(C.membrane_shadow_log()), "said@1")
    if u_bar is None:
        print("no boot u_bar on the shadow log; cannot run.")
        return 1
    n_lead = sum(1 for s, _ in replay if s.leader_credence is not None)
    print(f"verdict_replay: {len(replay)} ticks ({n_lead} with leader_credence)")
    run_variant("FULL (17 indicators)", ALL_FAMILIES, u_bar, replay, args.engine)
    run_variant("NARROW leader-credence", ["leader-credence"], u_bar, replay, args.engine)
    run_variant("NARROW leader-credence + p-none", ["leader-credence", "p-none"],
                u_bar, replay, args.engine)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
