"""r34 — the wire census over the value-join (`bridge/server._lattice_join`).

The lever this prices runs BRIDGE-SIDE. The collapse fixtures record `/probe/deliberate` and
`/probe/corroborate` as `http` exchanges with frozen responses, so replaying a fixture serves
the recorded answer and never runs the join at all (r34 pre-registration §2b). This census is
the instrument that can read it: it lifts `(value, candidates, allow_new)` off the recorded
wire and replays them through the **deployed** join, so the same instrument run on two trees
yields the lever's firing surface exhaustively.

    uv run python scripts/join_census.py <fixture-dir> --out arm.json
    uv run python scripts/join_census.py --diff old.json new.json

**r37** adds the live half. `--live <tap-log>` reads the observation-only tap
(`bridge/server._join_tap`) into the SAME row shape, `--superset` checks L3 (every recorded
firing must appear live on the questions both cover), and `--equivalence` is GD-7's added
verifier for L1/L2 — the tap flag ON vs OFF over this population, byte-identical.

Since r37 the join takes its identity as a parameter, so ONE pass reads both arms: the census
no longer diffs two trees, it asks the deployed rule both questions. `--diff` is retained for
the r34 record.

`engine_join` BINDS `_lattice_join` — the census never re-implements the rule it prices
(RULINGS `M-7`, the standing lesson at five instances).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import life_agent.core.lookup as LK
from life_agent.bridge.server import _JOIN_TAP_ENV, _lattice_join
from life_agent.core import config as CFG

#: The one join, imported. A census that re-spells the predicate measures its own spelling.
engine_join = _lattice_join

#: The endpoints whose payload carries a candidate lattice and whose reply carries a value.
JOIN_URLS = ("/probe/deliberate", "/probe/corroborate")

#: The DECLARED §4.2 identity — the counterfactual arm. Imported, never re-spelled (`M-7`).
DECLARED_KEY = LK._candidate_key


def both_arms(value: str, candidates: list[str], allow_new: bool
              ) -> tuple[tuple[int | None, str | None], tuple[int | None, str | None]]:
    """``(deployed, declared)`` — the one join asked under both identities. Both arms run
    the same function; the only difference is the key, which is why this can be trusted to
    price the lever rather than the instrument."""
    return (engine_join(value, candidates, allow_new),
            engine_join(value, candidates, allow_new, key=DECLARED_KEY))


def joined_key(idx: int | None, minted: str | None,
               candidates: list[str]) -> str | None:
    """The DECLARED key of the answer this join attributed the observation to.

    C1 must compare which ANSWER was joined, not which slot: the lever's whole effect is to
    stop minting, which shortens the lattice, so indices are not comparable across arms by
    construction. A mint returns ``(len(candidates), value)`` — a non-None index — so the
    mint's key is the minted value's; a join's is the joined candidate's; no join has none."""
    if minted is not None:
        return LK._candidate_key(minted)
    if idx is None or not (0 <= idx < len(candidates)):
        return None
    return LK._candidate_key(candidates[idx])


def c1_identity_violation(d: dict[str, Any]) -> str | None:
    """C1, corrected. A violation is the arms attributing an observation to a DIFFERENT
    answer. Same key at a different slot is the merge itself appearing downstream."""
    o, n = d["old"].get("joined_key"), d["new"].get("joined_key")
    if o == n:
        return None
    if n is None:
        return "joined answer became no-join"
    return "joined a DIFFERENT answer" if o is not None else None


def recorded_joins(root: Path) -> Iterator[dict[str, Any]]:
    """Every recorded join under ``root``, in a stable order — the ONE walk of the wire.

    `census` and the equivalence population both consume this. Two walks would be two
    definitions of "the recorded population", and the whole reason r37 exists is a surface
    that turned out to be defined by its instrument rather than by the world."""
    for fx in sorted(Path(root).glob("*.json")):
        try:
            doc = json.loads(fx.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        wire = doc.get("wire")
        if not isinstance(wire, list):
            continue
        qid = str(doc.get("question_id") or fx.stem)
        for n, ex in enumerate(wire):
            if not isinstance(ex, dict) or ex.get("seam") != "http":
                continue
            req = ex.get("request") or {}
            url = str(req.get("url") or "")
            if url not in JOIN_URLS:
                continue
            rsp = ex.get("response")
            if not isinstance(rsp, dict):
                continue
            value = rsp.get("value")
            if value is None or str(value).strip() == "":
                # no value came back — there is no join to replay, and inventing one
                # would put the instrument's guess into the arm it is measuring
                continue
            payload = req.get("payload") or {}
            yield {"key": f"{fx.name}#{n}", "fixture": fx.name, "question_id": qid,
                   "url": url, "value": str(value).strip(),
                   "candidates": [str(c) for c in (payload.get("candidates") or [])],
                   "allow_new": bool(payload.get("allow_new", False))}


def census(root: Path) -> list[dict[str, Any]]:
    """Replay every recorded join through BOTH identities, in a stable order."""
    rows: list[dict[str, Any]] = []
    for j in recorded_joins(root):
        (idx, minted), (d_idx, d_minted) = both_arms(
            j["value"], j["candidates"], j["allow_new"])
        rows.append({"key": j["key"], "fixture": j["fixture"],
                     "question_id": j["question_id"], "url": j["url"],
                     "n_candidates": len(j["candidates"]),
                     "allow_new": j["allow_new"], "idx": idx, "minted": minted,
                     "joined_key": joined_key(idx, minted, j["candidates"]),
                     "declared": {"idx": d_idx, "minted": d_minted},
                     "fires": (d_idx, d_minted) != (idx, minted)})
    return rows


def diff(old: list[dict[str, Any]], new: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The arms' disagreements. Refuses misaligned arms: two censuses over different
    corpora produce a difference list that means nothing."""
    ok, nk = [r["key"] for r in old], [r["key"] for r in new]
    if ok != nk:
        raise ValueError(
            f"arms disagree on their exchange set ({len(ok)} vs {len(nk)} rows) — the two "
            "censuses must cover the same corpus in the same order")
    out = []
    for o, n in zip(old, new, strict=True):
        if (o["idx"], o["minted"]) != (n["idx"], n["minted"]):
            out.append({**{k: o.get(k) for k in ("key", "fixture", "question_id", "url")},
                        "old": {"idx": o["idx"], "minted": o["minted"],
                                "joined_key": o.get("joined_key")},
                        "new": {"idx": n["idx"], "minted": n["minted"],
                                "joined_key": n.get("joined_key")}})
    return out


def c1_violation(d: dict[str, Any]) -> str | None:
    """C1's shape test. The lever is a monotone COARSENING, so the only licensed movement is
    *the old arm minted (or found nothing) and the new arm joins an existing index*. A join
    that moves to a different index, or a join that becomes a mint, refutes the coarsening
    argument the whole lever rests on — one of either is a kill."""
    o, n = d["old"], d["new"]
    if o["idx"] is None:
        return None if n["idx"] is not None else "no-join→no-join (not a difference)"
    return "join→mint" if n["idx"] is None else "join→different-join"


def live(tap_log: Path) -> list[dict[str, Any]]:
    """Read the tap's stream into the census row shape. The tap records EVERY call, so the
    denominator is the file's length and the surface is the rows with ``fires`` — `G-3`."""
    rows: list[dict[str, Any]] = []
    for n, line in enumerate(Path(tap_log).read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        r = json.loads(line)
        cands = [str(c) for c in r.get("candidates") or []]
        idx, minted = r["deployed"]["idx"], r["deployed"]["minted"]
        rows.append({"key": f"live#{n}", "fixture": "",
                     "question_id": r.get("question_id", ""),
                     "url": r.get("url", ""),
                     "n_candidates": r.get("n_candidates", len(cands)),
                     "allow_new": r.get("allow_new", False), "idx": idx, "minted": minted,
                     "joined_key": joined_key(idx, minted, cands),
                     "declared": r["declared"], "fires": bool(r["fires"])})
    return rows


def superset(recorded: list[dict[str, Any]], observed: list[dict[str, Any]]
             ) -> dict[str, Any]:
    """L3. On the questions BOTH instruments cover, every recorded firing must appear live.
    A recorded firing missing live means the two instruments disagree about the deployed rule
    and neither can be trusted — which is why L3 kills in both directions.

    Questions are matched on ``decisions.question_id`` — the ONE declared derivation of a
    question's identity, which the m5-base fixtures already key on (verified: it reproduces
    all 308 recorded fixture ids from the payload question, 0 disagreements). No second hash
    exists on either side (`M-7`)."""
    r_q = {r["question_id"] for r in recorded if r["question_id"]}
    o_q = {r["question_id"] for r in observed if r["question_id"]}
    shared = r_q & o_q
    r_fire = {r["question_id"] for r in recorded if r["fires"] and r["question_id"] in shared}
    o_fire = {r["question_id"] for r in observed if r["fires"] and r["question_id"] in shared}
    return {"recorded_calls": len(recorded), "live_calls": len(observed),
            "recorded_questions": len(r_q), "live_questions": len(o_q),
            "shared_questions": len(shared),
            "recorded_firings_total": sum(1 for r in recorded if r["fires"]),
            "live_firings_total": sum(1 for r in observed if r["fires"]),
            "recorded_firing_questions_shared": sorted(r_fire),
            "live_firing_questions_shared": sorted(o_fire),
            "missing_live": sorted(r_fire - o_fire),
            "new_live": sorted(o_fire - r_fire)}


def equivalence(root: Path) -> dict[str, Any]:
    """GD-7's added verifier for L1/L2. The m5-base replay serves /probe/* from cassettes and
    so never enters the join at all — it cannot tell tap-on from tap-off. This can: every
    recorded triple through the deployed join with the flag ON and with it OFF, byte-identical
    verdicts required. An empty population fails (`G-3`'s universe clause)."""
    triples = [(j["value"], j["candidates"], j["allow_new"])
               for j in recorded_joins(root)]
    if not triples:
        return {"population": 0, "ok": False,
                "reason": "empty population — nothing was checked"}
    os.environ.pop(_JOIN_TAP_ENV, None)
    off = [engine_join(v, c, a) for v, c, a in triples]
    declared_log = CFG.JOIN_TAP_LOG
    with tempfile.TemporaryDirectory() as tmp:
        CFG.JOIN_TAP_LOG = Path(tmp) / "join-tap.jsonl"
        os.environ[_JOIN_TAP_ENV] = "1"
        try:
            on = [engine_join(v, c, a) for v, c, a in triples]
            written = (sum(1 for _ in CFG.JOIN_TAP_LOG.open(encoding="utf-8"))
                       if CFG.JOIN_TAP_LOG.exists() else 0)
        finally:
            # the declared path is module state — leaving it pointed at a deleted
            # tempdir would silently disarm the tap for anything later in this process
            os.environ.pop(_JOIN_TAP_ENV, None)
            CFG.JOIN_TAP_LOG = declared_log
    bad = [i for i, (o, n) in enumerate(zip(off, on, strict=True)) if o != n]
    return {"population": len(triples), "divergences": len(bad),
            "tap_rows_written": written, "ok": not bad and written == len(triples)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", type=Path, help="fixture directory to census")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--diff", nargs=2, type=Path, metavar=("OLD", "NEW"))
    ap.add_argument("--live", type=Path, default=None,
                    help="read a tap log (bridge/server._join_tap) instead of fixtures")
    ap.add_argument("--superset", nargs=2, type=Path, metavar=("RECORDED", "LIVE"),
                    help="L3: every recorded firing must appear live on shared questions")
    ap.add_argument("--equivalence", type=Path, default=None, metavar="FIXTURE_DIR",
                    help="L1/L2 (GD-7): tap ON vs OFF over the census population")
    a = ap.parse_args(argv)

    # the census calls the deployed join, so an armed tap would record the INSTRUMENT's own
    # calls into the surface it is measuring. Disarm first, always.
    os.environ.pop(_JOIN_TAP_ENV, None)

    if a.equivalence is not None:
        res = equivalence(a.equivalence)
        print(json.dumps(res, indent=1))
        print(f"L1/L2 paired equivalence: {'PASS' if res['ok'] else 'FAIL'}")
        return 0 if res["ok"] else 1

    if a.superset:
        rec = json.loads(a.superset[0].read_text(encoding="utf-8"))
        obs = json.loads(a.superset[1].read_text(encoding="utf-8"))
        res = superset(rec, obs)
        print(json.dumps(res, indent=1))
        empty = not res["shared_questions"]
        ok = not res["missing_live"] and not empty
        print(f"L3 superset: {'PASS' if ok else 'FAIL'}"
              + (" — no shared questions, nothing was checked" if empty else ""))
        print(f"L4 surface size: live firings {res['live_firings_total']} over "
              f"{res['live_calls']} calls"
              + ("  — EMPTY, the run fails" if not res["live_firings_total"] else ""))
        return 0 if ok and res["live_firings_total"] else 1

    if a.live is not None:
        rows = live(a.live)
        print(f"{len(rows)} live joins · {sum(1 for r in rows if r['fires'])} firings · "
              f"{len({r['question_id'] for r in rows})} questions")
        if a.out:
            a.out.write_text(json.dumps(rows, indent=1), encoding="utf-8")
            print(f"wrote {a.out}")
        return 0

    if a.diff:
        old = json.loads(a.diff[0].read_text(encoding="utf-8"))
        new = json.loads(a.diff[1].read_text(encoding="utf-8"))
        ds = diff(old, new)
        print(f"exchanges {len(old)} · differences {len(ds)}")
        for d in ds:
            lit, ident = c1_violation(d), c1_identity_violation(d)
            print(f"  {d['question_id']} {d['url']} {d['old']} -> {d['new']}")
            print(f"      C1-as-frozen: {lit or 'ok (mint->join)'}"
                  f"   |   C1-identity: {ident or 'ok (same answer)'}")
        lit_v = [d for d in ds if c1_violation(d)]
        id_v = [d for d in ds if c1_identity_violation(d)]
        # BOTH readings are published: C1 as frozen compares slots, which the lever changes
        # by construction; C1-identity compares answers. See r34's chronology (M-4).
        print(f"\nC1-as-frozen  {'FAIL' if lit_v else 'pass'} — {len(lit_v)} violation(s)")
        print(f"C1-identity   {'FAIL' if id_v else 'pass'} — {len(id_v)} violation(s)")
        return 1 if id_v else 0

    if a.root is None:
        ap.error("a fixture directory is required unless --diff is given")
    rows = census(a.root)
    print(f"{len(rows)} recorded joins over {len({r['fixture'] for r in rows})} fixtures · "
          f"{sum(1 for r in rows if r['fires'])} firings")
    if a.out:
        a.out.write_text(json.dumps(rows, indent=1), encoding="utf-8")
        print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
