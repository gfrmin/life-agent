"""The production readout — the standing watch on the deployed typed arm (stage 0.3).

Run 14 deployed the typed arm carrying two standing wrong-commit rows, priced and
published; nothing watched them in production. This is that watch: a READOUT of the live
calibration stream (decisions / outcomes / reactions), never a diagnostic arc — it counts,
it names ids, and it prints **no corpus value** (no claim text, no candidates; the live KB
is personal data and the report may be pasted anywhere).

    uv run python scripts/production_readout.py [--since ISO] [--out PATH]

Reads ``$LIFE_AGENT_KB/calibration/{decisions,outcomes,reactions}.jsonl``; excludes eval
traffic (run_id prefixes ``gate-``, ``collapse-``); writes the report beside the stream at
``$LIFE_AGENT_KB/calibration/readout.md`` and prints it. Default window: the deploy date
(2026-08-25). Wire it to a weekly timer (packaging/production-readout.timer) on the box
that carries the live stream.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEPLOY_DATE = "2026-08-25"          # run 14's deploy — the default window start
EXCLUDED_RUN_PREFIXES = ("gate-", "collapse-")


def _rows(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def _production(row: dict[str, Any], since: str) -> bool:
    if str(row.get("tx_time", "")) < since:
        return False
    return not str(row.get("run_id", "")).startswith(EXCLUDED_RUN_PREFIXES)


def _instrument(row: dict[str, Any]) -> str:
    ps = row.get("posterior_summary") or {}
    return str(ps.get("instrument") or row.get("instrument") or "")


def readout(decisions: list[dict[str, Any]], outcomes: list[dict[str, Any]],
            reactions: list[dict[str, Any]], *, since: str) -> dict[str, Any]:
    """Reduce the three streams to counts + the watch rows. Ids and instrument names only —
    a corpus value never leaves this function (the render test pins it)."""
    dec = [r for r in decisions if _production(r, since)]
    out = [r for r in outcomes if _production(r, since)]
    rea = [r for r in reactions if str(r.get("tx_time", "")) >= since]
    wrong = [{"tx_time": str(r.get("tx_time", "")),
              "question_id": str(r.get("question_id", "")),
              "grader": str(r.get("grader", "")),
              "edge": str((r.get("instrument_identity") or {}).get("edge", ""))}
             for r in out if str(r.get("grade", "")).upper() == "INCORRECT"]
    return {
        "since": since,
        "decisions": dict(Counter(str(r.get("chosen_action", "")) for r in dec)),
        "deliberate_commits": sum(
            1 for r in dec if _instrument(r).startswith("deliberate@")),
        "graded": dict(Counter(str(r.get("grade", "")) for r in out)),
        "wrong": wrong,
        "reactions": dict(Counter(str(r.get("valence", "")) for r in rea)),
    }


def render(s: dict[str, Any]) -> str:
    lines = [
        f"# Production readout — since {s['since']}",
        "",
        f"_Generated {datetime.now(UTC).isoformat(timespec='seconds')}. A readout,"
        " not a diagnosis (the cap): counts and ids only, no corpus values._",
        "",
        f"- decisions by action: {json.dumps(s['decisions'], sort_keys=True)}",
        f"- deliberate-edge commits: {s['deliberate_commits']}",
        f"- graded outcomes: {json.dumps(s['graded'], sort_keys=True)}",
        f"- owner reactions: {json.dumps(s['reactions'], sort_keys=True)}",
        "",
        "## Watch: wrong outcomes (the carried-risk classes ride here)",
        "",
    ]
    if not s["wrong"]:
        lines.append("(none in the window)")
    for w in s["wrong"]:
        lines.append(f"- {w['tx_time']}  q={w['question_id']}  grader={w['grader']}"
                     + (f"  edge={w['edge']}" if w["edge"] else ""))
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since", default=DEPLOY_DATE)
    ap.add_argument("--out", default=None,
                    help="report path (default: $LIFE_AGENT_KB/calibration/readout.md)")
    args = ap.parse_args(argv)
    from life_agent.core import config as CFG
    cal = CFG.KB / "calibration"
    s = readout(_rows(cal / "decisions.jsonl"), _rows(cal / "outcomes.jsonl"),
                _rows(cal / "reactions.jsonl"), since=args.since)
    text = render(s)
    out = Path(args.out) if args.out else cal / "readout.md"
    out.write_text(text, encoding="utf-8")
    print(text)
    print(f"→ {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
