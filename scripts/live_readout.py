#!/usr/bin/env python3
"""Live readout — what the DEPLOYED arm is actually doing for the owner.

Every other instrument in this repo reads the eval corpus. This one reads only the
LIVE stream: the decision rows whose ``run_id`` is not a ``gate-*`` id, joined to the
owner's one-bit verdicts on ``decision_id`` (the §4.4 join key — ``question_id`` is not
unique across runs). It exists because the MVP exit test (ROADMAP 3c) is stated in live
terms — "a week of the owner asking Jarvis instead of the incumbent harnesses" — and a
week of use cannot be read off a benchmark.

The headline is deliberately the least flattering number available: DAYS SINCE THE LAST
LIVE DECISION. An adoption that no one exercises is an unmeasured configuration wearing
the gate's evidence, and this makes that visible in one line instead of hiding it in a
rate that only counts the days someone showed up.

Read-only and pure at the core (``summarize`` takes rows and a date, touches nothing), so
the numbers can be pinned by hermetic tests rather than by a screenshot.

Usage:
  uv run python scripts/live_readout.py [--days 30] [--decisions PATH] [--reactions PATH]
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from life_agent.core import config as LCFG

_ASSERTS = ("report", "report_scoped", "hedge")


def is_live(row: dict[str, Any]) -> bool:
    """A live row is one no eval run produced. The gate stamps ``run_id`` on every row
    it writes precisely so in-gate decisions can never masquerade as live."""
    return not str(row.get("run_id") or "").startswith("gate-")


def _day(row: dict[str, Any]) -> str:
    return str(row.get("tx_time") or "")[:10]


@dataclass
class Readout:
    n_live: int = 0
    first_day: str = ""
    last_day: str = ""
    days_since_last: int | None = None
    active_days: int = 0
    by_family: dict[str, int] = field(default_factory=dict)
    by_action: dict[str, int] = field(default_factory=dict)
    answer_rate: float | None = None          # asserts / rows carrying a posterior
    n_posterior: int = 0
    spend_usd: float = 0.0
    latency_p50: float | None = None
    n_verdicts: int = 0
    n_verdicts_joined: int = 0                # verdicts that bind a live decision
    verdict_split: dict[str, int] = field(default_factory=dict)
    verdict_coverage: float | None = None     # joined verdicts / live decisions
    recent_days: list[tuple[str, int]] = field(default_factory=list)


def summarize(decisions: list[dict[str, Any]], reactions: list[dict[str, Any]],
              today: date, *, window_days: int = 30) -> Readout:
    live = [r for r in decisions if is_live(r)]
    out = Readout(n_live=len(live))
    if not live:
        return out
    days = sorted({_day(r) for r in live if _day(r)})
    out.first_day, out.last_day, out.active_days = days[0], days[-1], len(days)
    out.days_since_last = (today - date.fromisoformat(out.last_day)).days
    out.by_family = dict(Counter(str(r.get("family") or "?") for r in live))
    out.by_action = dict(Counter(str(r.get("chosen_action") or "?") for r in live))
    posted = [r for r in live
              if (r.get("posterior_summary") or {}).get("n_obs") is not None]
    out.n_posterior = len(posted)
    if posted:
        asserts = sum(1 for r in posted if str(r.get("chosen_action")) in _ASSERTS)
        out.answer_rate = asserts / len(posted)
    out.spend_usd = sum(float(r.get("cost_usd") or 0.0) for r in live)
    lat = [float(r["latency_s"]) for r in live if r.get("latency_s") is not None]
    out.latency_p50 = statistics.median(lat) if lat else None

    live_ids = {str(r.get("decision_id")) for r in live}
    out.n_verdicts = len(reactions)
    joined = [v for v in reactions if str(v.get("decision_id")) in live_ids]
    out.n_verdicts_joined = len(joined)
    out.verdict_split = dict(Counter(str(v.get("valence")) for v in joined))
    out.verdict_coverage = (len(joined) / len(live)) if live else None

    # CALENDAR days, not active days: a window built from the days that happen to have
    # rows can only ever read 100% used, which is the flattering metric this instrument
    # exists to refuse. Gaps must show as zeros.
    counts = Counter(_day(r) for r in live if _day(r))
    out.recent_days = [((today - timedelta(days=n)).isoformat(),
                        counts.get((today - timedelta(days=n)).isoformat(), 0))
                       for n in range(window_days - 1, -1, -1)]
    return out


def render(r: Readout, *, exit_test_days: int = 7) -> str:
    if not r.n_live:
        return "# Live readout\n\nNo live decision rows. The deployed arm has never run.\n"
    stale = r.days_since_last if r.days_since_last is not None else -1
    verdict = ("LIVE" if stale <= 1 else
               f"IDLE — {stale} days since the last live decision")
    out = ["# Live readout — the deployed arm", "",
           f"**{verdict}**", "",
           f"- live decisions: {r.n_live} over {r.active_days} active days "
           f"({r.first_day} → {r.last_day})",
           "- families: " + ", ".join(f"{k} {v}" for k, v in sorted(r.by_family.items())),
           "- actions: " + ", ".join(f"{k} {v}" for k, v in sorted(r.by_action.items())),
           f"- rows carrying a posterior: {r.n_posterior}"
           + (f"; answer rate {r.answer_rate:.2f}" if r.answer_rate is not None else ""),
           f"- spend: ${r.spend_usd:.2f}"
           + (f"; median latency {r.latency_p50:.1f}s" if r.latency_p50 is not None
              else ""),
           f"- verdicts: {r.n_verdicts} logged, {r.n_verdicts_joined} bound to a live "
           f"decision "
           + (f"({r.verdict_coverage:.1%} coverage)"
              if r.verdict_coverage is not None else "")
           + (" — " + ", ".join(f"{k} {v}" for k, v in sorted(r.verdict_split.items()))
              if r.verdict_split else ""),
           ""]
    window = r.recent_days[-exit_test_days:]
    used = sum(1 for _, n in window if n)
    out += [f"## MVP exit test (ROADMAP 3c): {used}/{exit_test_days} of the last "
            f"{exit_test_days} CALENDAR days carried live use", "",
            "  (a live row is any non-eval decision, so developer smoke tests count "
            "here too — this measures whether the arm ran, not whether the owner "
            "chose it; that is the defection counter's job)", ""]
    for d, n in r.recent_days[-14:]:
        out.append(f"  {d}  {'█' * min(n, 40)} {n}")
    return "\n".join(out) + "\n"


def _load(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--decisions", type=Path, default=None)
    ap.add_argument("--reactions", type=Path, default=None)
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    decisions = _load(args.decisions or Path(LCFG.DECISIONS_LOG))
    reactions = _load(args.reactions or Path(LCFG.REACTIONS_LOG))
    r = summarize(decisions, reactions, datetime.now().date(), window_days=args.days)
    report = render(r)
    print(report)
    if args.out:
        args.out.write_text(report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
