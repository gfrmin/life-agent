"""r48 — the E1 re-earn measurement: does ``respond_j`` ever become the argmax?

Pre-registration: ``docs/unification/reports/r48-reearn-measurement-preregistration.md``
(frozen ``8f167b1``, before this instrument ran). Nine criteria, J1 KILL.

**This instrument contains no EU arithmetic.** §16 finding 3 answered the binder question
analytically, with an inequality written in that era's constants; two of its three terms have
since moved. Re-deriving it here would price a constant through a re-implementation of the
rule that assembles it — `M-7`'s trap, and the reason `GD-24` ordered `r47`'s build first. So
every reading below comes from **watching the deployed engine's own argmax**:
:func:`life_agent.membrane.categorical.decide_categorical` — the episode `r47` built and the
shadow supervisor binds — against the deployed arm B binary.

Legs:

``replay``  J1/J2/J4/J5 — the 129 distinct recorded summaries, a census over the 2 012 rows.
``sweep``   J3 — monotone evidence sweeps at the frozen k set, watching for the flip.

PII: :class:`CatSummary` is numbers by construction, ``question_id`` is an opaque hash, and no
question text or candidate string is read anywhere.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import membrane.report as R
from life_agent.core import config as C
from life_agent.membrane import categorical as CAT
from life_agent.membrane.client import MembraneClient, MembraneError

ARM_B_ENGINE = str(Path.home() / ".local/bin/proplang-host")

# Frozen in the pre-registration (J3): the sweep's k set and its observation bound.
SWEEP_KS: tuple[int, ...] = (1, 2, 3, 5, 10)
SWEEP_MAX_OBS: int = 40


def load_cat_summaries(path: Path) -> list[tuple[dict[str, Any], int]]:
    """Every recorded ``cat`` row's summary, deduplicated, with its row multiplicity.

    The episode is a pure function of ``(u_bar, summary)``, so the distinct set is a CENSUS
    over the recorded population — not a sample and not a cap. The multiplicity is what
    frequency-weighted population statements are built from."""
    counts: dict[str, int] = {}
    first: dict[str, dict[str, Any]] = {}
    with path.open() as fh:
        for line in fh:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get("kind") != "cat" or not isinstance(row.get("summary"), dict):
                continue
            key = json.dumps(row["summary"], sort_keys=True)
            counts[key] = counts.get(key, 0) + 1
            first.setdefault(key, row["summary"])
    return [(first[k], counts[k]) for k in sorted(counts)]


def summary_from_record(rec: Mapping[str, Any]) -> CAT.CatSummary:
    """Rebuild the DEPLOYED dataclass from a recorded summary — field for field, so the
    replay's input is the recorded one rather than a re-derivation of it."""
    return CAT.CatSummary(
        k=int(rec["k"]),
        obs_codes=tuple(int(c) for c in rec["obs_codes"]),
        n_obs=int(rec["n_obs"]),
        n_obs_unmapped=int(rec.get("n_obs_unmapped", 0)),
        daemon_map_index=(None if rec.get("daemon_map_index") is None
                          else int(rec["daemon_map_index"])),
        era_split=bool(rec.get("era_split", False)),
        owner_scoped=bool(rec.get("owner_scoped", False)),
        grow_pass=bool(rec.get("grow_pass", False)),
    )


def null_cap(k: int) -> float:
    """R-D23's declared null-mass cap, ``1/(K-1)`` — the engine's own published constant,
    quoted for comparison only. Nothing here recomputes a decision from it (J4)."""
    return 1.0 / (k - 1) if k > 1 else float("inf")


def run_episode(
    engine: str, u_bar: Mapping[str, float], s: CAT.CatSummary, *, read_timeout_s: float,
) -> dict[str, Any]:
    """One deployed episode, timed. Returns the choice and readouts, or the refusal."""
    started = time.monotonic()
    client = MembraneClient.spawn([engine], read_timeout_s=read_timeout_s)
    try:
        choice = CAT.decide_categorical(client, u_bar, s)
    except MembraneError as exc:
        return {"ok": False, "error": str(exc), "k": s.k,
                "latency_ms": (time.monotonic() - started) * 1000.0}
    finally:
        client.shutdown()
    ro = choice.readouts
    return {
        "ok": True, "k": s.k, "n_obs": s.n_obs, "action": choice.action, "j": choice.j,
        "models": choice.engine.get("models"),
        "p1": ro.get("p1"), "p0": ro.get("p0"),
        "argmax_code": ro.get("argmax_code"), "p_argmax": ro.get("p_argmax"),
        "daemon_map_index": s.daemon_map_index,
        "latency_ms": (time.monotonic() - started) * 1000.0,
    }


def replay(
    engine: str, u_bar: Mapping[str, float], corpus: Sequence[tuple[dict[str, Any], int]],
    *, read_timeout_s: float = 300.0,
) -> dict[str, Any]:
    """J1/J2/J4/J5 — every distinct recorded summary through the deployed episode."""
    rows: list[dict[str, Any]] = []
    for rec, weight in corpus:
        out = run_episode(engine, u_bar, summary_from_record(rec),
                          read_timeout_s=read_timeout_s)
        out["weight"] = weight
        out["null_cap"] = null_cap(out["k"])
        rows.append(out)
        print(f"  k={out['k']:>2} w={weight:>4} "
              f"{'OK ' if out['ok'] else 'REF'} {out.get('action', out.get('error'))} "
              f"p_argmax={out.get('p_argmax')} p0={out.get('p0')}", flush=True)
    return {"leg": "replay", "rows": rows, "n_distinct": len(rows),
            "n_rows_covered": sum(r["weight"] for r in rows)}


def sweep_codes(k: int, n: int) -> tuple[int, ...]:
    """``n`` supporting observations for candidate 1 — the monotone sweep's evidence."""
    return tuple(1 for _ in range(n))


def sweep(
    engine: str, u_bar: Mapping[str, float], *, ks: Sequence[int] = SWEEP_KS,
    max_obs: int = SWEEP_MAX_OBS, read_timeout_s: float = 300.0,
) -> dict[str, Any]:
    """J3 — the monotone evidence sweep: append supporting observations one at a time and
    watch the DEPLOYED argmax. The flip point, if one exists, is where ``action`` stops
    being the engine's constant choice; if none exists the reading is the maximum
    ``p_argmax`` attained and the fact that no flip occurred within the frozen bound."""
    out: dict[str, Any] = {"leg": "sweep", "ks": list(ks), "max_obs": max_obs, "runs": {}}
    for k in ks:
        steps: list[dict[str, Any]] = []
        for n in range(0, max_obs + 1, max(1, max_obs // 10)):
            s = CAT.CatSummary(
                k=k, obs_codes=sweep_codes(k, n), n_obs=n, n_obs_unmapped=0,
                daemon_map_index=0, era_split=False, owner_scoped=True, grow_pass=False,
            )
            r = run_episode(engine, u_bar, s, read_timeout_s=read_timeout_s)
            steps.append(r)
            print(f"  sweep k={k} n_obs={n:>3} -> {r.get('action', r.get('error'))} "
                  f"p_argmax={r.get('p_argmax')}", flush=True)
            if not r["ok"]:
                break
        acts = {st.get("action") for st in steps if st["ok"]}
        pmax = max((st["p_argmax"] for st in steps
                    if st["ok"] and st.get("p_argmax") is not None), default=None)
        out["runs"][str(k)] = {
            "steps": steps,
            "actions_seen": sorted(a for a in acts if a),
            "flipped": len(acts) > 1,
            "max_p_argmax": pmax,
        }
    return out


def run_stamp() -> dict[str, Any]:
    """`M-28` — the tree and the engine, pinned for the whole run."""
    def git(*a: str) -> str:
        return subprocess.run(["git", *a], capture_output=True, text=True).stdout.strip()
    sha = subprocess.run(["sha256sum", ARM_B_ENGINE], capture_output=True, text=True)
    return {
        "git_head": git("rev-parse", "HEAD"),
        "dirty": bool(git("status", "--porcelain")),
        "engine": ARM_B_ENGINE,
        "engine_sha256": sha.stdout.split()[0] if sha.returncode == 0 else None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("leg", choices=["replay", "sweep"])
    parser.add_argument("--out", required=True)
    parser.add_argument("--engine", default=ARM_B_ENGINE)
    parser.add_argument("--read-timeout-s", type=float, default=300.0)
    args = parser.parse_args(argv)

    u_bar = R.latest_boot_u_bar(R.load_shadow_records(C.membrane_shadow_log()), "said@1")
    if u_bar is None:
        print("no boot u_bar on the shadow log; cannot run.")
        return 1
    stamp = run_stamp()
    print(f"tree {stamp['git_head'][:12]} dirty={stamp['dirty']} leg={args.leg}")

    if args.leg == "replay":
        corpus = load_cat_summaries(Path(C.membrane_shadow_log()))
        print(f"corpus: {len(corpus)} distinct summaries "
              f"covering {sum(w for _, w in corpus)} recorded rows")
        result: dict[str, Any] = replay(args.engine, u_bar, corpus,
                                        read_timeout_s=args.read_timeout_s)
    else:
        result = sweep(args.engine, u_bar, read_timeout_s=args.read_timeout_s)

    result["run_stamp"] = stamp
    result["u_bar"] = {k: float(v) for k, v in u_bar.items()}
    Path(args.out).write_text(json.dumps(result, indent=2, sort_keys=True))
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
