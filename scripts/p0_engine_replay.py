#!/usr/bin/env python3
"""r41 / P0-2 — replay a recorded shadow decide against a proplang-host binary.

    uv run python scripts/p0_engine_replay.py --binary <path> [--limit N]

Criteria P0-1..P0-5 are frozen in `docs/unification/reports/r41-p0-engine-preregistration.md`
(with amendments 1-2 and the `t` addendum). The comparison is **behavioural**: the ledger
records outcomes, not the wire, so a recorded decide is reproduced by warming a session with
the same verdicts and comparing `action` + `readouts`.

Everything load-bearing is IMPORTED, never re-implemented (`M-7`, seven instances):
the warm-up is `shadow.boot_snapshot` + `MembraneSession.boot`; the decide is
`MembraneSession.decide`; the summary type is `world.DecideSummary`.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import fields
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from life_agent.core import config as CFG
from life_agent.membrane import shadow as SH
from life_agent.membrane import world as W
from life_agent.membrane.client import MembraneClient
from life_agent.membrane.session import MembraneSession

#: The warm-up, imported. A replay that re-implements the boot measures its own boot.
boot_snapshot = SH.boot_snapshot

#: The one summary type; its field names are the ledger's `summary` keys verbatim.
SUMMARY_FIELDS = tuple(f.name for f in fields(W.DecideSummary))


def shadow_records(path: Path | None = None) -> list[dict[str, Any]]:
    """Every shadow record, in file order — boots and decides interleaved as written."""
    p = path or (CFG.KB / "membrane" / "shadow.jsonl")
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


def epochs(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Each boot paired with the decides that followed it, before the next boot.

    A decide is only reproducible against the `u_bar` and warm size of the boot it ran
    under, so the pairing is the unit of replay — not the decide alone."""
    out: list[dict[str, Any]] = []
    for r in records:
        if r.get("kind") == "boot":
            out.append({"boot": r, "decides": []})
        elif r.get("kind") == "decide" and out:
            out[-1]["decides"].append(r)
    return out


def summary_of(record: dict[str, Any]) -> W.DecideSummary:
    """The recorded `summary` rebuilt as the engine's own input type. Amendment 1's whole
    basis: the ledger's summary IS `world.DecideSummary`, so no reconstruction is invented."""
    s = record["summary"]
    missing = [f for f in SUMMARY_FIELDS if f not in s]
    if missing:
        raise ValueError(f"recorded summary is missing {missing} — not a DecideSummary")
    return W.DecideSummary(**{f: s[f] for f in SUMMARY_FIELDS})


def supersession_bound(boot_ts: float, reactions_path: Path | None = None) -> int:
    """An UPPER BOUND on how many replayed verdicts could have been rewritten since the boot
    being reproduced: reactions written after `boot_ts`.

    It is a bound, not an attribution — `verdict_replay` carries no `decision_id`, so which
    of the first N were touched cannot be said from here. Reported before the comparison so a
    mismatch is never explained away afterwards (the addendum's rule)."""
    p = reactions_path or CFG.REACTIONS_LOG
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except OSError:
        return 0
    n = 0
    for ln in lines:
        if not ln.strip():
            continue
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        tx = r.get("tx_time")
        if isinstance(tx, str) and tx > _iso(boot_ts):
            n += 1
    return n


def _iso(ts: float) -> str:
    """The boot's epoch seconds as an ISO string, for comparison against `tx_time`."""
    import datetime as _d
    return _d.datetime.fromtimestamp(ts).isoformat()


def replay_one(binary: str, epoch: dict[str, Any], decide: dict[str, Any]) -> dict[str, Any]:
    """Warm a fresh session to the decide's own `t`, then decide on its recorded summary.

    `t` is the verdict count and is a FEATURE of the decide (the addendum), so the warm-up is
    truncated to exactly `t` verdicts — never approximated."""
    t = int(decide["t"])
    snap = boot_snapshot(CFG.DECISIONS_LOG, CFG.REACTIONS_LOG, None)
    available = len(snap.verdict_replay)
    client = MembraneClient.spawn([binary], log=lambda _m: None)
    try:
        sess = MembraneSession(client, u_bar=dict(epoch["boot"]["u_bar"]),
                               utility_form=str(decide.get("form") or "said@1"),
                               log=lambda _m: None)
        sess.boot(verdict_replay=snap.verdict_replay[:t], outcome_replay=[])
        got = sess.decide(summary_of(decide))
        reached = sess.t
    finally:
        client.shutdown()
    return {"t_recorded": t, "t_reached": reached, "verdicts_available": available,
            "action_recorded": decide["action"], "action_replayed": got.action,
            "readouts_recorded": decide["readouts"], "readouts_replayed": got.readouts,
            "action_match": got.action == decide["action"],
            "readouts_match": _readouts_match(decide["readouts"], got.readouts)}


def _readouts_match(recorded: dict[str, Any], replayed: dict[str, Any]) -> bool:
    """Every recorded readout key reproduced to the precision the ledger stored it at.

    The ledger holds full float repr, so this is equality — a tolerance here would be the
    audit choosing how close is close enough, which is the frozen criterion's job, not the
    instrument's."""
    return all(k in replayed and replayed[k] == v for k, v in recorded.items())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--binary", required=True, help="path to a proplang-host")
    ap.add_argument("--limit", type=int, default=2, help="how many recorded decides to replay")
    ap.add_argument("--shadow", type=Path, default=None)
    a = ap.parse_args(argv)

    recs = shadow_records(a.shadow)
    eps = [e for e in epochs(recs) if e["decides"]]
    if not eps:
        print("no boot epoch carries a decide — nothing to replay", file=sys.stderr)
        return 1
    print(f"boot epochs with decides: {len(eps)} · total decides: "
          f"{sum(len(e['decides']) for e in eps)}")

    picked = []
    seen_t: set[int] = set()
    for e in eps:
        for d in e["decides"]:
            if d["t"] not in seen_t:
                seen_t.add(d["t"])
                picked.append((e, d))
            if len(picked) >= a.limit:
                break
        if len(picked) >= a.limit:
            break

    ok = True
    readable = unreadable = 0
    for e, d in picked:
        bound = supersession_bound(float(e["boot"]["ts"]))
        print(f"\n-- decide t={d['t']} under boot n_source_records="
              f"{e['boot'].get('n_source_records')}")
        print(f"   supersession UPPER BOUND (reactions after the boot): {bound} "
              f"— a bound, not an attribution")
        res = replay_one(a.binary, e, d)
        print(f"   t reached {res['t_reached']} of {res['t_recorded']} "
              f"(verdicts available {res['verdicts_available']})")
        print(f"   action  recorded={res['action_recorded']!r} "
              f"replayed={res['action_replayed']!r}  -> "
              f"{'MATCH' if res['action_match'] else 'DIFFER'}")
        print(f"   readouts {'MATCH' if res['readouts_match'] else 'DIFFER'}")
        if not res["readouts_match"]:
            print(f"     recorded={json.dumps(res['readouts_recorded'])}")
            print(f"     replayed={json.dumps(res['readouts_replayed'])}")
        if res["t_reached"] != res["t_recorded"]:
            # UNREADABLE, not failed: `t` is an INPUT feature, so a session that could not
            # reach the recorded `t` compared a different engine state. Calling that a
            # mismatch would blame the engine for the ledger's own shrinkage (G-3: a check
            # whose universe is absent reports absence, never a verdict).
            unreadable += 1
            print(f"   -> UNREADABLE: only {res['verdicts_available']} verdicts survive "
                  f"today, so t={res['t_recorded']} is unreachable. Any readout difference "
                  f"below is the t gap, NOT the engine.")
        else:
            readable += 1
            ok = ok and res["action_match"] and res["readouts_match"]
    print(f"\nreadable rows {readable} · unreadable {unreadable}")
    if not readable:
        print("P0-2: UNREADABLE — no recorded decide could be reproduced at its own t")
        return 2
    print(f"P0-2: {'PASS' if ok else 'FAIL'} on the {readable} readable row(s)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
