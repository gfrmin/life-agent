#!/usr/bin/env python3
"""The live stream as a board-shaped archive — the `live` row's producer.

Every other archive on the board is made by *asking questions*: `scripts/score_typed.py`
drives a question file through a bridge and records what the act did. The live row cannot
be made that way. Its questions were asked by the owner, once, in the past, and the only
record is the write-once decision log. So this reads that log instead of re-running it.

    uv run python scripts/live_archive.py [--since ISO] [--out PATH]

**The join.** A verdict binds a decision by ``decision_id``, never by ``question_id`` —
the same question asked twice is two decisions with one id each, and `question_id` is not
unique across runs (`scripts/live_readout.py` states the same rule). Eval traffic is
excluded by ``run_id`` prefix, through `live_readout.is_live`, so a gate run can never
masquerade as live use.

**What is scoreable, and what is only recorded.** A decision that ABSTAINED is scoreable
on its own: declining is an answer (rule 1) and the gauge prices it at `u_declined`,
whatever the owner would have said. A decision that ASSERTED is scoreable only if the
owner graded it — without a verdict there is no `correct`, and a row whose correctness is
unknown may not be counted right *or* wrong. Those rows are written with ``censored:
true``, which `eval/score.py` removes from the arm: present in the file, so the archive
describes the whole live population, absent from the counts, so the board never scores a
guess. That is the same discipline the pinned sets use — a row is named, never dropped.

**Counts only.** The printed summary and the archive itself carry no question text, no
candidate and no corpus value: actions, correctness, price, latency and ids that are
already content-addressed hashes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from live_readout import is_live

from life_agent.core import config as CFG

#: The actions that COMMIT an answer. Anything else withholds one, and a withhold is
#: scoreable without a verdict. Kept in step with `live_readout._ASSERTS`.
ASSERTS = ("report", "report_scoped", "hedge")


def _rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def verdicts_by_decision(reactions: list[dict[str, Any]]) -> dict[str, bool]:
    """The owner's one-bit grade per decision, latest wins. A verdict with no
    ``decision_id`` binds nothing and is dropped here rather than guessed at."""
    latest: dict[str, tuple[str, bool]] = {}
    for r in reactions:
        did = str(r.get("decision_id") or "")
        valence = str(r.get("valence") or "")
        if not did or valence not in ("good", "bad"):
            continue
        stamp = str(r.get("tx_time") or "")
        if did not in latest or stamp >= latest[did][0]:
            latest[did] = (stamp, valence == "good")
    return {k: v for k, (_, v) in latest.items()}


def archive(decisions: list[dict[str, Any]], reactions: list[dict[str, Any]],
            *, since: str = "") -> list[dict[str, Any]]:
    """One board row per live decision, in `typed` shape. Pure: no IO, no clock."""
    graded = verdicts_by_decision(reactions)
    out: list[dict[str, Any]] = []
    for r in decisions:
        if not is_live(r) or str(r.get("tx_time") or "") < since:
            continue
        action = str(r.get("chosen_action") or "")
        did = str(r.get("decision_id") or "")
        asserted = action in ASSERTS
        correct = graded.get(did) if asserted else None
        out.append({
            "question_id": str(r.get("question_id") or ""),
            "decision_id": did,
            "tx_time": str(r.get("tx_time") or ""),
            "answerable": True,
            # An assert the owner never graded has no correctness, so it may not be
            # counted right or wrong; the board drops a censored row from the arm.
            "censored": asserted and did not in graded,
            "typed": {"action": "report" if asserted else "abstain",
                      "correct": correct,
                      "cost_usd": float(r.get("cost_usd") or 0.0),
                      "withheld": None if asserted else (
                          r.get("posterior_summary") or {}).get("withheld"),
                      "latency_s": r.get("latency_s")},
        })
    return out


def summarise(rows: list[dict[str, Any]],
              graded: dict[str, bool] | None = None) -> dict[str, Any]:
    """Counts only — what the board will read, plus what it cannot.

    ``graded_withholds`` is the count the board deliberately does not use: a verdict the
    owner left on a DECLINE. It does not make the decline wrong — a withhold is priced at
    ``u_declined`` whatever the owner would have preferred, and only a committed answer
    can be wrong (rule 1) — but it is the owner saying "you should have answered", which
    is the loudest thing in this stream. It folds into the bar through `core/reactions.py`
    and is stated here so the archive never drops it silently.
    """
    scoreable = [r for r in rows if not r["censored"]]
    grades = Counter("right" if r["typed"]["correct"] is True else
                     "wrong" if r["typed"]["correct"] is False else "declined"
                     for r in scoreable)
    withhold_grades = Counter(
        "wanted_an_answer" if (graded or {}).get(r["decision_id"]) is False else "endorsed"
        for r in rows
        if r["typed"]["action"] == "abstain" and r["decision_id"] in (graded or {}))
    return {"rows": len(rows), "scoreable": len(scoreable),
            "ungraded_asserts": sum(1 for r in rows if r["censored"]),
            "right": grades["right"], "wrong": grades["wrong"],
            "declined": grades["declined"],
            "graded_withholds": dict(withhold_grades),
            "spend_usd": round(sum(float(r["typed"]["cost_usd"]) for r in rows), 4),
            "first": min((r["tx_time"][:10] for r in rows), default=""),
            "last": max((r["tx_time"][:10] for r in rows), default="")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--since", default="",
                    help="ISO stamp; only decisions at or after it (default: all)")
    ap.add_argument("--decisions", type=Path, default=None)
    ap.add_argument("--reactions", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None,
                    help="default: $LIFE_AGENT_KB/eval/live/live-<stamp>.jsonl")
    args = ap.parse_args(argv)

    rows = archive(_rows(args.decisions or Path(CFG.DECISIONS_LOG)),
                   _rows(args.reactions or Path(CFG.REACTIONS_LOG)),
                   since=args.since)
    if not rows:
        sys.stderr.write("live_archive: no live decisions in the window — the arm has "
                         "served nothing to archive. Nothing written.\n")
        return 1

    out = args.out or (Path(CFG.KB) / "eval" / "live"
                       / f"live-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    s = summarise(rows, verdicts_by_decision(
        _rows(args.reactions or Path(CFG.REACTIONS_LOG))))
    print(" · ".join(f"{k} {v}" for k, v in s.items()))
    print(f"→ {out} (sha256 {hashlib.sha256(out.read_bytes()).hexdigest()})",
          file=sys.stderr)
    if s["scoreable"] and not (s["right"] or s["wrong"]):
        sys.stderr.write("note: every scoreable row is a decline — the arm withheld on "
                         "all of them, or no assert has been graded yet. A row pinned "
                         "here measures the withhold rate and nothing else.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
