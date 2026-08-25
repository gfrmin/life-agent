#!/usr/bin/env python3
"""Record the decision-equivalence baseline from THIS tree — the pre-collapse truth.

    uv run python scripts/collapse_record.py --checkpoint m0 --limit 5

Writes fixtures to ``$LIFE_AGENT_KB/eval/collapse-fixtures/<checkpoint>/`` (M0-S1), each a
self-contained cassette: the credence-engine wire, the §18.9 cache reads, any model call, and
the bridge/daemon wire, together with the act and the ``/log_decision`` body it produced.
``scripts/collapse_replay.py`` replays them at every later checkpoint.

**Two rules this recorder keeps, and the report states with evidence.**

*No live ledger is touched.* Every writer is ROUTED, not marked: the bridge runs in THIS
process against a ``BridgeDeps`` whose decisions/reactions/gather paths are under the
fixture set's ``staging/``, the family leaves are driven with an explicit
``decisions_path`` and a throwaway pkm root, and the §18.9 cache is read through a tap that
reads the live root read-only and writes nothing back. Nothing of this run reaches
``$LIFE_AGENT_KB/calibration/`` or the live pkm cache.

*No spend.* The M0 baseline replays warm §18.9 derivations. EVERY model seam is sealed
(:func:`life_agent.collapse.drive.sealed`), not just the schema-constrained instrument
client: `joint_extract`, `rerank`, `expansion`, `synthesis` and `/probe/deliberate` each
reach Anthropic through their own import-bound binding, and gating only the client leaves
them free to spend. Under the seal a cold derivation raises and the question becomes a NAMED
absence in the report rather than a silent charge. ``--allow-spend`` opts in deliberately.

The credence engine (docker) and the answer-brain daemon must be up for the ``A-loop``
trace; ``--traces`` records a subset when one of them is not.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import yaml

from life_agent.collapse import drive as DR
from life_agent.collapse import fixture as FX
from life_agent.collapse import taps as T
from life_agent.core import ask_client as AC
from life_agent.core import brain as B
from life_agent.core import config as CFG
from life_agent.core import derivations as D
from life_agent.core import narrative as NARR

ALL_TRACES = ("A-loop", "A-poster", "B-lookup", "B-narrative", "seam")


def _questions(path: Path, ids: list[str] | None, limit: int | None) -> list[dict[str, Any]]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    qs = raw if isinstance(raw, list) else raw["questions"]
    if ids:
        wanted = set(ids)
        qs = [q for q in qs if str(q["id"]) in wanted]
    return qs[:limit] if limit else qs


def _classes(outputs: dict[str, Any], *, trace: str,
             extra: tuple[str, ...] = ()) -> tuple[str, ...]:
    """Label the fixture by what it EXERCISES, so `fixture.coverage` can name every hole."""
    eff = outputs.get("effector") or "none"
    body = outputs.get("log_decision") or {}
    dec = body.get("decision", {}) if isinstance(body, dict) else {}
    classes = [f"trace:{trace}", f"terminal:{eff}"]
    withheld = eff in ("abstain", "hedge", "ask_clarify", "miss")
    classes.append("outcome:withheld" if withheld else "outcome:committed")
    if eff == "abstain" and outputs.get("candidates"):
        classes.append("outcome:dispersed")
    if eff == "miss" or (not outputs.get("candidates") and withheld):
        classes.append("outcome:miss")
    creds = list(outputs.get("credences") or [])
    if len(creds) >= 2 and abs(creds[0] - creds[1]) <= FX.FLOAT_TOL:
        classes.append("posterior:two-equal-credences")   # the tie-break kill (§7.5)
    audit = outputs.get("audit") or {}
    n_obs = dec.get("n_obs", audit.get("n_obs", audit.get("n_observations")))
    if n_obs == 0:
        classes.append("posterior:n_obs=0")               # the E-7 replace-branch cluster
    if dec.get("regime"):
        classes.append(f"regime:{dec['regime']}")
    if dec.get("policy"):
        classes.append(f"policy:{dec['policy']}")
    if outputs.get("gate"):
        classes.append(f"gate:{outputs['gate']}")
    return tuple(classes) + extra


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--checkpoint", default="m0")
    ap.add_argument("--out", default=None)
    ap.add_argument("--questions", default=None)
    ap.add_argument("--ids", default=None, help="comma-separated question ids")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--k", type=int, default=20,
                help="top-k retrieval (default 20 — the eval recipe's k, so the "
                     "recorded chunk sets hit warm derivations)")
    ap.add_argument("--traces", default=",".join(ALL_TRACES))
    ap.add_argument("--run-id", default=None, help="default: collapse-<checkpoint>")
    ap.add_argument("--allow-spend", action="store_true",
                    help="permit live model calls on a COLD derivation (default: refuse)")
    ap.add_argument("--relabel-only", action="store_true",
                    help="recompute every fixture's class labels from its recorded outputs "
                         "and rewrite the manifest — no engine, no corpus, no recording. A "
                         "class list may be refined without re-recording; the OUTPUTS the "
                         "comparator comes from are never touched.")
    ap.add_argument("--allow-existing", action="store_true",
                    help="record into a checkpoint directory that already holds fixture files "
                         "(default: refuse — the manifest globs the directory, so a leftover "
                         "fixture from an aborted run would be published as part of this set)")
    ap.add_argument("--deliberate", default="1", choices=("0", "1"),
                    help="the deliberate edge's deployed state (§13 adoption: on)")
    ap.add_argument("--max-usd", type=float, default=8.0,
                    help="hard cap on a priced record's metered spend; blowing it ABORTS "
                         "the whole record (RecordBudgetExceeded escapes the per-trace "
                         "absence handlers by design). Ignored without --allow-spend.")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    traces = tuple(t.strip() for t in args.traces.split(",") if t.strip())
    run_id = args.run_id or f"collapse-{args.checkpoint}"
    out = Path(args.out) if args.out else CFG.KB / "eval" / "collapse-fixtures" / args.checkpoint
    qpath = Path(args.questions) if args.questions else CFG.KB / "eval" / "questions_v2.yaml"
    questions = _questions(qpath, args.ids.split(",") if args.ids else None, args.limit)

    import os
    os.environ["LIFE_AGENT_DELIBERATE"] = args.deliberate
    if os.environ.get("PYTHONHASHSEED") is None:
        print("refusing: set PYTHONHASHSEED (e.g. 0) before recording — the decision path "
              "has a hash-order-dependent tie-break (lookup.dedup_correlated, "
              "docs/unification/reports/r02-collapse-m0.md), so an unpinned recording is "
              "not reproducible", file=sys.stderr)
        return 2

    if args.relabel_only:
        return _relabel(out, args.checkpoint)

    stale = FX.existing_fixtures(out)
    if stale and not args.allow_existing:
        shown = ", ".join(stale[:4]) + (f", … (+{len(stale) - 4} more)" if len(stale) > 4 else "")
        print(f"refusing: {out} already holds {len(stale)} fixture file(s) — {shown}. The "
              "manifest is built by globbing this directory, so a leftover fixture from an "
              "aborted run would be published as part of this set and the mixture would present "
              "as a whole artefact (R8). Move the directory aside, or pass --allow-existing if "
              "adding to it is what you mean.", file=sys.stderr)
        return 2

    print(f"== recording {args.checkpoint} → {out}")
    print(f"   {len(questions)} question(s), traces {traces}, k={args.k}, run_id={run_id}")
    snapshot = DR.take_snapshot(out / "snapshots", CFG.KB)
    print(f"   KB snapshot: {json.dumps(snapshot.provenance())}")

    live_root = CFG.pkm_root()
    if live_root is None:
        print("no pkm root — the recorder reads the live corpus read-only", file=sys.stderr)
        return 2

    sink: list[FX.Exchange] = []
    inner_brain = B.Brain.spawn()
    # wrap the spawned transport rather than re-deriving spawn's argv: one spelling of how
    # the engine is reached (brain.spawn), one tap around it
    brain = B.Brain(T.RecordingTransport(inner_brain._transport, sink))
    brain.initialize()
    client: Any = (T.MeteredRecordingClient(__import__(
        "life_agent.core.lookup", fromlist=["_client"])._client(), sink,
        max_usd=args.max_usd)
        if args.allow_spend else T.RefusingClient(engine_version=_engine_version()))
    cache = T.RecordingCache(D.lookup, live_root=live_root, sink=sink)

    provenance = {
        "tree_sha": _git_sha(), "recorded_at": _now(), "checkpoint": args.checkpoint,
        "engine_version": str(getattr(client, "engine_version", "")),
        "skin_image": B.CREDENCE_SKIN_IMAGE, "protocol_major": B.PROTOCOL_MAJOR,
        "daemon": AC.DAEMON, "bridge": AC.BRIDGE, "k": args.k,
        "deliberate": args.deliberate == "1", "grow_lane": True,  # retired at M1: one lane
        "snapshots": snapshot.provenance(), "questions_file": str(qpath),
        "allow_spend": bool(args.allow_spend),
        # PINNED, and recorded so replay can refuse a mismatch. `lookup.dedup_correlated`
        # breaks a covariate TIE with `max()` over a set of artefact keys (lookup.py:806),
        # so which duplicate document survives — and therefore which observations reach the
        # posterior — depends on the interpreter's per-process string hashing. Measured at
        # M0: it moves the decision on a real fraction of the battery. Until that tie-break
        # has a declared home (M6), a fixture is only reproducible at a fixed seed.
        "python_hash_seed": os.environ.get("PYTHONHASHSEED"),
    }

    deps = DR.staging_deps(client, snapshot.staging)
    rig = DR.Rig(brain=brain, post=None, get=None, client=client, cache=cache)  # type: ignore[arg-type]
    # the bridge runs IN THIS PROCESS (so its own leaves — extraction's grounding gate, the
    # narrative leaf — sit inside the recorded envelope), the daemon over real HTTP (it is the
    # ranking, a separate process by design). Both go through the recording tap, so the
    # cassette holds the wire the loop's host saw as well as the engine traffic underneath it.
    live_post, live_get = T.recording_http(
        DR.local_stack_post(deps, AC.DAEMON, AC.post_json), DR.local_stack_get(deps), sink)

    recorded: list[FX.Fixture] = []
    absences: list[str] = []

    # the narrative leaf's arguments, captured off the bridge handler so the B-narrative
    # fixture replays the SAME proposal the executor path scored (no second spelling)
    captured_narrative: dict[str, Any] = {}
    inner_narr = NARR.narrative_answer

    def _capturing_narrative(root, question, text, cards, **kw):
        captured_narrative[question] = {"text": text, "cards": list(cards)}
        return inner_narr(root, question, text, cards, **kw)

    NARR.narrative_answer = _capturing_narrative
    seal = DR.sealed(snapshot.staging / "pkm", allow_spend=bool(args.allow_spend))
    seal.__enter__()
    try:
        if "seam" in traces:
            outputs = DR.drive_seam_unavailable("the stack is down")  # PII-OK: synthetic
            recorded.append(DR.fixture_from(
                f"{args.checkpoint}-seam-executor-down", args.checkpoint, "seam",
                question="the stack is down",  # PII-OK: synthetic
                classes=_classes(outputs, trace="seam"), inputs={},
                outputs=outputs, wire=[], provenance=provenance,
                expected_change={
                    "checkpoint": "M2/M5",
                    "direction": ("the same unavailability becomes a RECORD carrying "
                                  "regime=unavailable with no decision_id — never an "
                                  "abstain verdict (design §6.5)")}))
            print(f"  seam: {outputs['effector']} gate={outputs['gate']}")

        for q in questions:
            qid, question = str(q["id"]), str(q["question"])
            t0 = time.time()
            view: dict[str, Any] | None = None
            if "A-loop" in traces:
                sink.clear()
                captured_narrative.clear()
                try:
                    with DR.installed(rig_with(rig, live_post, live_get), snapshot):
                        outputs = DR.drive_executor_loop(rig, snapshot, question=question,
                                                         k=args.k, run_id=run_id)
                    view = rig.last_view
                    recorded.append(DR.fixture_from(
                        f"{args.checkpoint}-aloop-{qid}", args.checkpoint, "A-loop",
                        question=question, classes=_classes(outputs, trace="A-loop"),
                        inputs={"k": args.k, "run_id": run_id},
                        outputs=outputs, wire=list(sink), provenance=provenance))
                    print(f"  {qid} A-loop {outputs['effector']:<12} "
                          f"{time.time() - t0:5.1f}s  {len(sink)} exchanges")
                except T.WouldSpendError as e:
                    absences.append(f"{qid} A-loop: cold derivation ({e})")
                    print(f"  {qid} A-loop ABSENT — cold derivation")
                    continue
                except Exception as e:
                    absences.append(f"{qid} A-loop: {type(e).__name__}: {e}")
                    print(f"  {qid} A-loop ABSENT — {type(e).__name__}: {e}")
                    continue

            if view and "A-poster" in traces:
                outputs_p = DR.drive_ask_poster(question, view, run_id=run_id)
                recorded.append(DR.fixture_from(
                    f"{args.checkpoint}-poster-{qid}", args.checkpoint, "A-poster",
                    question=question,
                    classes=_classes(outputs_p, trace="A-poster",
                                     extra=("poster:ask._log_executor_decision",)),
                    inputs={"view": view, "run_id": run_id},
                    outputs=outputs_p, wire=[], provenance=provenance,
                    expected_change={
                        "checkpoint": "M2",
                        "direction": ("one poster: the reach surface's absent accounting "
                                      "keys become present at 0.0/'' — never absent "
                                      "(design §5.1)")}))

            hits = view["hits"] if view else None
            if hits is None and "B-lookup" in traces:
                # the cheap retrieval pass is pure DuckDB (no expand, no rerank — those are
                # the priced grow lane), so a B-trace fixture can be recorded at $0 even when
                # the A-loop's priced probes are cold and the seal refuses them
                try:
                    with DR.installed(rig, snapshot):
                        hits = (live_post(f"{AC.BRIDGE}/retrieve",
                                          {"question": question, "k": args.k,
                                           "rerank": False, "expand": False}) or {}).get("hits")
                except Exception as e:
                    absences.append(f"{qid} retrieve: {type(e).__name__}: {e}")
                    hits = None
            if hits and "B-lookup" in traces:
                sink.clear()
                try:
                    with tempfile.TemporaryDirectory(prefix="collapse-rec-") as tmp, \
                            DR.installed(rig, snapshot):
                        from life_agent.core import lookup as LK
                        outputs_b = DR.drive_lookup_leaf(
                            rig, snapshot, question=question, hits=hits,
                            covariates=LK.HitCovariates(), scope="unscoped",
                            root=Path(tmp), run_id=run_id)
                    recorded.append(DR.fixture_from(
                        f"{args.checkpoint}-blookup-{qid}", args.checkpoint, "B-lookup",
                        question=question, classes=_classes(outputs_b, trace="B-lookup"),
                        inputs={"hits": hits, "scope": "unscoped",
                                "run_id": run_id, "subject_state": {}, "doc_date": {}},
                        outputs=outputs_b, wire=list(sink), provenance=provenance))
                    print(f"  {qid} B-lookup {outputs_b['effector']:<10} "
                          f"{len(sink)} exchanges")
                except Exception as e:
                    absences.append(f"{qid} B-lookup: {type(e).__name__}: {e}")
                    print(f"  {qid} B-lookup ABSENT — {type(e).__name__}: {e}")

            if question in captured_narrative and "B-narrative" in traces:
                cap = captured_narrative[question]
                sink.clear()
                try:
                    with tempfile.TemporaryDirectory(prefix="collapse-rec-") as tmp, \
                            DR.installed(rig, snapshot):
                        outputs_n = DR.drive_narrative_leaf(
                            rig, snapshot, question=question, text=cap["text"],
                            cards=cap["cards"], scope="unscoped", root=Path(tmp),
                            run_id=run_id)
                    recorded.append(DR.fixture_from(
                        f"{args.checkpoint}-bnarr-{qid}", args.checkpoint, "B-narrative",
                        question=question,
                        classes=_classes(outputs_n, trace="B-narrative",
                                         extra=("terminal:report(claims)",)
                                         if outputs_n["effector"] == "report" else ()),
                        inputs={"text": cap["text"], "scope": "unscoped", "run_id": run_id,
                                "cards": [{"n": c.n, "text": c.text, "origin": c.origin,
                                           "as_of": c.as_of} for c in cap["cards"]]},
                        outputs=outputs_n, wire=list(sink), provenance=provenance))
                    print(f"  {qid} B-narrative {outputs_n['effector']:<8} "
                          f"{len(sink)} exchanges")
                except Exception as e:
                    absences.append(f"{qid} B-narrative: {type(e).__name__}: {e}")
                    print(f"  {qid} B-narrative ABSENT — {type(e).__name__}: {e}")
    finally:
        seal.__exit__(None, None, None)
        NARR.narrative_answer = inner_narr
        with __import__("contextlib").suppress(Exception):
            brain.shutdown()

    for fx in recorded:
        FX.write(out, fx)
    man = FX.manifest(args.checkpoint, recorded, provenance)
    man["absences"] = absences
    (out / "manifest.json").write_text(json.dumps(man, indent=1, sort_keys=True),
                                       encoding="utf-8")
    print(f"\n== {len(recorded)} fixture(s) written to {out}")
    print(f"== metered spend: ${man['spent_usd']:.4f}"
          + (f" (cap ${args.max_usd:.2f})" if args.allow_spend else " (no-spend run)"))
    if absences:
        print(f"== {len(absences)} NAMED absence(s):")
        for a in absences:
            print(f"   - {a}")
    empty = [k for k, v in man["coverage"].items() if not v]
    if empty:
        print(f"== coverage holes (named, never silent): {', '.join(empty)}")
    return 0


def _relabel(out: Path, checkpoint: str) -> int:
    """Recompute class labels in place. Outputs, wire and provenance are untouched — only the
    labels coverage reads."""
    import dataclasses as _dc

    fixtures = FX.read_all(out)
    relabelled = []
    for fx in fixtures:
        classes = _classes(fx.outputs, trace=fx.trace)
        extra = tuple(c for c in fx.classes
                      if c.startswith(("poster:", "terminal:report(claims)")))
        new = _dc.replace(fx, classes=tuple(sorted(set(classes) | set(extra))))
        FX.write(out, new)
        relabelled.append(new)
    man_path = out / "manifest.json"
    man = json.loads(man_path.read_text()) if man_path.exists() else {}
    provenance = man.get("provenance", {})
    absences = man.get("absences", [])
    man = FX.manifest(checkpoint, relabelled, provenance)
    man["absences"] = absences
    man_path.write_text(json.dumps(man, indent=1, sort_keys=True), encoding="utf-8")
    print(f"== relabelled {len(relabelled)} fixture(s) in {out}")
    empty = [k for k, v in man["coverage"].items() if not v]
    if empty:
        print(f"== coverage holes (named, never silent): {', '.join(empty)}")
    return 0


def rig_with(rig: DR.Rig, post: Any, get: Any) -> DR.Rig:
    rig.post, rig.get = post, get
    return rig


def _engine_version() -> str:
    try:
        import anthropic
        return str(anthropic.__version__)
    except Exception:
        return ""


def _git_sha() -> str:
    import subprocess
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception:
        return ""


def _now() -> str:
    from datetime import UTC, datetime
    return datetime.now(UTC).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
