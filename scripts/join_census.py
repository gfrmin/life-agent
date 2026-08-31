"""r34 — the wire census over the value-join (`bridge/server._lattice_join`).

The lever this prices runs BRIDGE-SIDE. The collapse fixtures record `/probe/deliberate` and
`/probe/corroborate` as `http` exchanges with frozen responses, so replaying a fixture serves
the recorded answer and never runs the join at all (r34 pre-registration §2b). This census is
the instrument that can read it: it lifts `(value, candidates, allow_new)` off the recorded
wire and replays them through the **deployed** join, so the same instrument run on two trees
yields the lever's firing surface exhaustively.

    uv run python scripts/join_census.py <fixture-dir> --out arm.json
    uv run python scripts/join_census.py --diff old.json new.json

`engine_join` BINDS `_lattice_join` — the census never re-implements the rule it prices
(RULINGS `M-7`, the standing lesson at five instances).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import life_agent.core.lookup as LK
from life_agent.bridge.server import _lattice_join

#: The one join, imported. A census that re-spells the predicate measures its own spelling.
engine_join = _lattice_join

#: The endpoints whose payload carries a candidate lattice and whose reply carries a value.
JOIN_URLS = ("/probe/deliberate", "/probe/corroborate")


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


def census(root: Path) -> list[dict[str, Any]]:
    """Replay every recorded join in every fixture under ``root``, in a stable order."""
    rows: list[dict[str, Any]] = []
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
            if ex.get("seam") != "http":
                continue
            req = ex.get("request") or {}
            url = str(req.get("url") or "")
            if url not in JOIN_URLS:
                continue
            payload = req.get("payload") or {}
            rsp = ex.get("response")
            if not isinstance(rsp, dict):
                continue
            value = rsp.get("value")
            if value is None or str(value).strip() == "":
                # no value came back — there is no join to replay, and inventing one
                # would put the instrument's guess into the arm it is measuring
                continue
            candidates = [str(c) for c in (payload.get("candidates") or [])]
            allow_new = bool(payload.get("allow_new", False))
            idx, minted = engine_join(str(value).strip(), candidates, allow_new)
            rows.append({"key": f"{fx.name}#{n}", "fixture": fx.name, "question_id": qid,
                         "url": url, "n_candidates": len(candidates),
                         "allow_new": allow_new, "idx": idx, "minted": minted,
                         "joined_key": joined_key(idx, minted, candidates)})
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", type=Path, help="fixture directory to census")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--diff", nargs=2, type=Path, metavar=("OLD", "NEW"))
    a = ap.parse_args(argv)

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
    print(f"{len(rows)} recorded joins over {len({r['fixture'] for r in rows})} fixtures")
    if a.out:
        a.out.write_text(json.dumps(rows, indent=1), encoding="utf-8")
        print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
