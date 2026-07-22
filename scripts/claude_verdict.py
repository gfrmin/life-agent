#!/usr/bin/env python
"""claude_verdict — the Claude verdict channel's capture CLI (owner-authorized 2026-07-22).

The verdict-giver is the in-session deliberative agent (Claude Code), issuing verdicts on
the owner's behalf; the owner overrules any of them with an ordinary reaction on the same
decision (owner precedence is by source — see ``core/claude_verdicts.py``). This CLI is
only the capture surface: ``list`` names the verdictable decisions, ``show`` prints one
decision's full context for deliberation, ``emit`` appends the deliberated record. The
deliberation itself — reading the decision's leader candidate against the corpus — happens
OUTSIDE this script, in the session; nothing here calls a model or grades mechanically
(batch-deriving verdicts from a grader would re-create the extraction channel at
owner-verdict authority).

Verdicts bind to the engine at the next boot replay (``shadow.boot_snapshot`` — restart
the bridge to fold a fresh batch); there is no live tick in v0, disclosed here rather
than hidden. PII stays on the terminal + under $LIFE_AGENT_KB; nothing is committed.

  uv run --project . python scripts/claude_verdict.py list [--limit N] [--all]
  uv run --project . python scripts/claude_verdict.py show DECISION_ID
  uv run --project . python scripts/claude_verdict.py emit DECISION_ID \\
      --correct|--incorrect [--complete 0|1] [--grounded 0|1] \\
      [--evidence "src ..."]... [--note "..."]
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from typing import Any

import yaml

import life_agent.core.claude_verdicts as CV
import life_agent.core.config as config
import life_agent.core.decisions as DEC
import life_agent.core.outcomes as O
import life_agent.core.reactions as RX
from life_agent.membrane.session import verdict_y


def _question_texts() -> dict[str, str]:
    """``question_id -> question text`` recovered from the KB's eval question files (the
    decision log stores only the hash). Fail-open per file; an unmapped id shows as
    ``(text unrecovered)`` rather than blocking the verdict."""
    id_map: dict[str, str] = {}
    root = str(config.KB / "eval")
    paths = sorted(glob.glob(root + "/*.yaml")) + sorted(glob.glob(root + "/*.jsonl"))
    for path in paths:
        try:
            with open(path, encoding="utf-8") as fh:
                if path.endswith(".jsonl"):
                    qlist: Any = [json.loads(line) for line in fh]
                else:
                    raw = yaml.safe_load(fh)
                    qlist = raw.get("questions", raw) if isinstance(raw, dict) else raw
            if not isinstance(qlist, list):
                continue
            for q in qlist:
                if not isinstance(q, dict):
                    continue
                text = q.get("question") or q.get("text")
                if isinstance(text, str) and text.strip():
                    id_map.setdefault(DEC.question_id(text), text)
        except Exception:
            continue
    return id_map


def _eligible() -> dict[str, DEC.DecisionEvent]:
    """Latest row per decision_id, for decisions a verdict can bind to: a ``decision_id``
    plus a nameable leader (non-empty candidates + credences). Narrative rows (no
    candidates) are out of scope — the ``correct`` dimension is about ASSERTING the
    leader, which needs a leader."""
    out: dict[str, DEC.DecisionEvent] = {}
    for d in DEC.read(config.DECISIONS_LOG):
        ps = d.posterior_summary or {}
        if d.decision_id and ps.get("candidates") and ps.get("credences"):
            out[d.decision_id] = d
    return out


def _owner_verdicted(eligible: dict[str, DEC.DecisionEvent]) -> set[str]:
    """Decisions whose LATEST owner reaction decodes to a verdict (`verdict_y` non-None)
    — only these supersede a Claude verdict. An unrouted reaction (e.g. `good` on a
    `hedge`) contributes no owner verdict, so it must not block the channel either."""
    try:
        latest: dict[str, str] = {}
        for r in RX.read(config.REACTIONS_LOG):
            latest[r.decision_id] = r.valence
    except FileNotFoundError:
        return set()
    return {
        did for did, valence in latest.items()
        if did in eligible and verdict_y(eligible[did].chosen_action, valence) is not None
    }


def _claude_verdicted() -> set[str]:
    try:
        return set(CV.latest_by_decision(CV.read(config.CLAUDE_VERDICTS_LOG)))
    except FileNotFoundError:
        return set()


def _leader(d: DEC.DecisionEvent) -> tuple[str, float]:
    ps = d.posterior_summary
    creds = [float(c) for c in ps["credences"]]
    cands = [str(c) for c in ps["candidates"]]
    i = max(range(len(creds)), key=lambda j: creds[j])
    cand = cands[i] if i < len(cands) else cands[0]
    return cand, creds[i]


def cmd_list(args: argparse.Namespace) -> int:
    texts = _question_texts()
    eligible = _eligible()
    reacted, verdicted = _owner_verdicted(eligible), _claude_verdicted()
    rows = sorted(eligible.values(), key=lambda d: d.tx_time, reverse=True)
    shown = 0
    for d in rows:
        done = d.decision_id in reacted or d.decision_id in verdicted
        if done and not args.all:
            continue
        if shown >= args.limit:
            break
        shown += 1
        cand, p = _leader(d)
        mark = ("R" if d.decision_id in reacted else
                "C" if d.decision_id in verdicted else " ")
        q = texts.get(d.question_id, "(text unrecovered)")
        print(f"[{mark}] {d.decision_id[:20]:<20} {d.tx_time[:10]} {d.run_id:<12} "
              f"{d.chosen_action:<13} p={p:.2f} {cand[:28]:<28} | {q[:60]}")
    print(f"\n({shown} shown; R = owner-reacted, C = claude-verdicted; "
          f"{len(rows)} eligible total)")
    return 0


def _find(decision_id: str) -> DEC.DecisionEvent | None:
    return _eligible().get(decision_id)


def cmd_show(args: argparse.Namespace) -> int:
    d = _find(args.decision_id)
    if d is None:
        print(f"no eligible decision with id {args.decision_id!r}", file=sys.stderr)
        return 1
    texts = _question_texts()
    print(json.dumps({
        "decision_id": d.decision_id, "tx_time": d.tx_time, "run_id": d.run_id,
        "question_id": d.question_id,
        "question": texts.get(d.question_id, "(text unrecovered)"),
        "family": d.family, "chosen_action": d.chosen_action,
        "posterior_summary": d.posterior_summary,
        "owner_verdicted": d.decision_id in _owner_verdicted(_eligible()),
        "claude_verdicted": d.decision_id in _claude_verdicted(),
    }, indent=2, ensure_ascii=False))
    return 0


def cmd_emit(args: argparse.Namespace) -> int:
    d = _find(args.decision_id)
    if d is None:
        print(f"no eligible decision with id {args.decision_id!r} "
              "(needs a decision_id + a nameable leader candidate)", file=sys.stderr)
        return 1
    dims: dict[str, int] = {"correct": 1 if args.correct else 0}
    if args.complete is not None:
        dims["complete"] = args.complete
    if args.grounded is not None:
        dims["grounded"] = args.grounded
    event = CV.ClaudeVerdictEvent(
        tx_time=O.now_iso(), question_id=d.question_id, decision_id=d.decision_id,
        dimensions=dims, evidence=tuple(args.evidence or ()), note=args.note or "")
    CV.append(config.CLAUDE_VERDICTS_LOG, event)
    fate = ("recorded but SUPERSEDED (an owner VERDICT exists on this decision — "
            "owner precedence)" if d.decision_id in _owner_verdicted({d.decision_id: d})
            else "recorded; joins the engine verdict replay at the next boot "
                 "(restart the bridge to fold)")
    print(f"claude verdict on {d.decision_id[:20]}…: dimensions={dims} — {fate}")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="claude_verdict", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    lp = sub.add_parser("list", help="verdictable decisions, newest first")
    lp.add_argument("--limit", type=int, default=20)
    lp.add_argument("--all", action="store_true",
                    help="include already-reacted/-verdicted decisions")
    lp.set_defaults(fn=cmd_list)

    sp = sub.add_parser("show", help="one decision's full context, for deliberation")
    sp.add_argument("decision_id")
    sp.set_defaults(fn=cmd_show)

    ep = sub.add_parser("emit", help="append one deliberated verdict")
    ep.add_argument("decision_id")
    g = ep.add_mutually_exclusive_group(required=True)
    g.add_argument("--correct", action="store_true",
                   help="asserting the leader candidate now would have been correct")
    g.add_argument("--incorrect", action="store_true")
    ep.add_argument("--complete", type=int, choices=(0, 1), default=None)
    ep.add_argument("--grounded", type=int, choices=(0, 1), default=None)
    ep.add_argument("--evidence", action="append", default=[],
                    help="what the deliberation read (repeatable)")
    ep.add_argument("--note", default="")
    ep.set_defaults(fn=cmd_emit)

    args = ap.parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
