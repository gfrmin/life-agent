#!/usr/bin/env python3
"""Replay the decision-equivalence fixtures and compare — the module collapse's oracle.

    uv run python scripts/collapse_replay.py --checkpoint m0

Exit 0 iff every fixture replays to the SAME decision it was recorded with, under the
declared field classes (``docs/module-collapse-design.md`` §7.2); exit 1 on any mismatch,
with the diff printed field by field. Recorded once at M0 from the pre-collapse tree, this
is what every later checkpoint has to stay green against — and what bisects a checkpoint
that does not.

Replay is HERMETIC: no daemon, no credence engine, no API key, no corpus. The engine wire,
the model calls and the §18.9 cache reads all ride in the fixture, so a mismatch can only
come from the host — which is the only thing the collapse moves.

``--verbose`` also prints the cassette notes (near-matches served, exchanges replay never
asked for): not failures, but the sort of thing a checkpoint's report should say out loud.
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from life_agent.collapse import compare as CMP
from life_agent.collapse import drive as DR
from life_agent.collapse import fixture as FX
from life_agent.collapse import taps as T
from life_agent.core import brain as B
from life_agent.core import config as CFG
from life_agent.core import lookup as LK
from life_agent.core import sources as SRC


def fixtures_dir(checkpoint: str, override: str | None) -> Path:
    if override:
        return Path(override)
    return CFG.KB / "eval" / "collapse-fixtures" / checkpoint


def _rig(fx: FX.Fixture) -> tuple[DR.Rig, T.Cassette]:
    cassette = T.Cassette(fx.wire)
    post, get = T.replay_http(cassette)
    return DR.Rig(
        brain=B.Brain(T.ReplayTransport(cassette)),
        post=post, get=get,
        client=T.ReplayClient(cassette,
                              engine_version=str(fx.provenance.get("engine_version", ""))),
        cache=T.ReplayCache(cassette),
    ), cassette


def replay_fixture(fx: FX.Fixture, snapshot: DR.KBSnapshot) -> tuple[dict[str, Any],
                                                                    T.Cassette]:
    """Drive the fixture's trace through the SAME driver that recorded it, with replaying
    taps in place of live ones."""
    rig, cassette = _rig(fx)
    if fx.trace == "seam":
        return DR.drive_seam_unavailable(fx.question), cassette
    if fx.trace == "A-poster":
        return DR.drive_ask_poster(fx.question, fx.inputs["view"],
                                   run_id=fx.inputs.get("run_id")), cassette
    with tempfile.TemporaryDirectory(prefix="collapse-replay-") as tmp:
        root = Path(tmp)
        with DR.installed(rig, snapshot):
            if fx.trace == "B-lookup":
                cov = LK.HitCovariates(
                    subject_state=fx.inputs.get("subject_state") or {},
                    doc_date=fx.inputs.get("doc_date") or {})
                return DR.drive_lookup_leaf(
                    rig, snapshot, question=fx.question, hits=fx.inputs["hits"],
                    covariates=cov, scope=fx.inputs.get("scope", "unscoped"),
                    root=root, run_id=fx.inputs["run_id"]), cassette
            if fx.trace == "B-narrative":
                cards = [SRC.SourceCard(n=c["n"], text=c["text"], origin=c.get("origin", ""),
                                        as_of=c.get("as_of"))
                         for c in fx.inputs["cards"]]
                return DR.drive_narrative_leaf(
                    rig, snapshot, question=fx.question, text=fx.inputs["text"],
                    cards=cards, scope=fx.inputs.get("scope", "unscoped"),
                    root=root, run_id=fx.inputs["run_id"]), cassette
            if fx.trace == "A-loop":
                prior_env = os.environ.get("LIFE_AGENT_DELIBERATE")
                # the flag is RECORDED state, restored here rather than assumed from the
                # ambient environment: a fixture must replay the same way on any box.
                # `grow_lane` is no longer restorable — it retired at M1 (there is one lane),
                # so a pre-M1 A-loop fixture recorded on the legacy lane now raises
                # CassetteMissError on `/grow_menu`. Loud by design: that fixture pins a path
                # the code no longer has, and the M1 baseline (`m0-5-growlane`) replaces it.
                os.environ["LIFE_AGENT_DELIBERATE"] = (
                    "1" if fx.provenance.get("deliberate") else "0")
                try:
                    return DR.drive_executor_loop(
                        rig, snapshot, question=fx.question, k=fx.inputs["k"],
                        run_id=fx.inputs["run_id"]), cassette
                finally:
                    if prior_env is None:
                        os.environ.pop("LIFE_AGENT_DELIBERATE", None)
                    else:
                        os.environ["LIFE_AGENT_DELIBERATE"] = prior_env
    raise ValueError(f"no replay driver for trace {fx.trace!r}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--checkpoint", required=True,
                    help="the fixture set to replay (e.g. m0)")
    ap.add_argument("--fixtures", default=None,
                    help="override the fixture directory (default: "
                         "$LIFE_AGENT_KB/eval/collapse-fixtures/<checkpoint>)")
    ap.add_argument("--only", default=None, help="replay one fixture id")
    ap.add_argument("--verbose", action="store_true",
                    help="print cassette notes (near-matches, unused exchanges)")
    args = ap.parse_args(argv)

    directory = fixtures_dir(args.checkpoint, args.fixtures)
    if not directory.is_dir():
        print(f"no fixture set at {directory}", file=sys.stderr)
        return 2
    fixtures = [f for f in FX.read_all(directory)
                if args.only is None or f.fixture_id == args.only]
    if not fixtures:
        print(f"no fixtures{' matching --only' if args.only else ''} in {directory}",
              file=sys.stderr)
        return 2
    snapshot = DR.KBSnapshot(directory / "snapshots")

    recorded_seed = {str(f.provenance.get("python_hash_seed")) for f in fixtures}
    here = str(os.environ.get("PYTHONHASHSEED"))
    if recorded_seed - {"None"} and here not in recorded_seed:
        print(f"refusing: fixtures were recorded at PYTHONHASHSEED={sorted(recorded_seed)} "
              f"and this process has {here!r}. The decision path's duplicate-dedup tie-break "
              "is hash-order dependent (lookup.dedup_correlated), so a replay at a different "
              "seed compares two different runs, not two versions of one.", file=sys.stderr)
        return 2

    failed: list[str] = []
    errored: list[str] = []
    for fx in fixtures:
        try:
            outputs, cassette = replay_fixture(fx, snapshot)
        except Exception as e:  # a replay that cannot run is a FAILURE, never a skip
            errored.append(fx.fixture_id)
            print(f"{fx.fixture_id}: replay raised {type(e).__name__}: {e}")
            continue
        diffs = CMP.compare_fixture(fx, outputs)
        if fx.expected_change is not None:
            print(f"{fx.fixture_id}: expected-change fixture "
                  f"({fx.expected_change.get('checkpoint')}) — "
                  f"{fx.expected_change.get('direction')} — direction ASSERTED")
        if diffs:
            failed.append(fx.fixture_id)
        print(CMP.render_diffs(fx.fixture_id, diffs))
        if args.verbose:
            for note in cassette.notes:
                print(f"    note: {note}")
            unused = cassette.unused()
            if unused:
                print(f"    note: {len(unused)} recorded exchange(s) replay never asked for")

    total = len(fixtures)
    bad = len(failed) + len(errored)
    print(f"\n{total - bad}/{total} fixtures replay identically"
          f"{'' if not failed else '  ·  mismatched: ' + ', '.join(failed)}"
          f"{'' if not errored else '  ·  errored: ' + ', '.join(errored)}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
