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
import re
import sys
from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEPLOY_DATE = "2026-08-25"          # run 14's deploy — the default window start
EXCLUDED_RUN_PREFIXES = ("gate-", "collapse-")
#: A weekly timer plus a day of slack. Past this the watch is reporting about a stream
#: that stopped moving, which before K3 looked exactly like a watch with nothing to say.
STALE_AFTER_DAYS = 8
#: The repo whose governance registers A0.5 reports on. Module-level so a test can
#: point it at an absent tree and exercise the guard.
REPO = Path(__file__).resolve().parent.parent


def _rows(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def union(*streams: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One stream from several KB roots, order-preserving, each distinct row once.

    The calibration streams are append-only and every row is immutable, so a row present
    in two roots is one event seen twice (a copied or re-synced stream) — never two. There
    is no id to key on: a decision row carries `question_id` + `tx_time` but no decision
    id, so the row itself is the identity. **That is a K4 finding, not a K3 fix** — no
    record carries a deployment origin, which is why two roots' rows are indistinguishable
    in kind as well as unmergeable in principle. This union is exact for copies and honest
    about everything else.
    """
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for stream in streams:
        for row in stream:
            key = json.dumps(row, sort_keys=True)
            if key not in seen:
                seen.add(key)
                out.append(row)
    return out


def _production(row: dict[str, Any], since: str) -> bool:
    if str(row.get("tx_time", "")) < since:
        return False
    return not str(row.get("run_id", "")).startswith(EXCLUDED_RUN_PREFIXES)


def _instrument(row: dict[str, Any]) -> str:
    ps = row.get("posterior_summary") or {}
    return str(ps.get("instrument") or row.get("instrument") or "")


def readout(decisions: list[dict[str, Any]], outcomes: list[dict[str, Any]],
            reactions: list[dict[str, Any]], *, since: str,
            now: datetime | None = None,
            sources: Sequence[dict[str, Any]] = ()) -> dict[str, Any]:
    """Reduce the three streams to counts + the watch rows. Ids and instrument names only —
    a corpus value never leaves this function (the render test pins it).

    `sources` describes the KB roots the rows came from, **by index and row count only**:
    a KB root is an owner-specific absolute path and this report may be pasted anywhere.
    A dead root shows up as `0 rows` without naming anybody's filesystem.
    """
    dec = [r for r in decisions if _production(r, since)]
    out = [r for r in outcomes if _production(r, since)]
    rea = [r for r in reactions if str(r.get("tx_time", "")) >= since]
    wrong = [{"tx_time": str(r.get("tx_time", "")),
              "question_id": str(r.get("question_id", "")),
              "grader": str(r.get("grader", "")),
              "edge": str((r.get("instrument_identity") or {}).get("edge", ""))}
             for r in out if str(r.get("grade", "")).upper() == "INCORRECT"]
    stamp = (now or datetime.now(UTC)).astimezone(UTC)
    newest = max((str(r.get("tx_time", "")) for r in (*dec, *out, *rea)), default="")
    age_days: int | None = None
    if newest:
        try:
            age_days = (stamp - datetime.fromisoformat(newest)).days
        except ValueError:                      # an unparseable stamp is not a fresh one
            age_days = None
    return {
        "since": since,
        "window": {
            "since": since,
            "newest": newest,
            "age_days": age_days,
            "as_of": stamp.isoformat(timespec="seconds"),
            "stale": age_days is None or age_days > STALE_AFTER_DAYS,
        },
        "sources": [dict(s) for s in sources],
        "decisions": dict(Counter(str(r.get("chosen_action", "")) for r in dec)),
        "deliberate_commits": sum(
            1 for r in dec if _instrument(r).startswith("deliberate@")),
        "graded": dict(Counter(str(r.get("grade", "")) for r in out)),
        "wrong": wrong,
        "reactions": dict(Counter(str(r.get("valence", "")) for r in rea)),
    }


def bar_summary(*, now_iso: str | None = None) -> dict[str, Any]:
    """r33 A6 (owner-ruled MONITOR ONLY): the DEPLOYED assert bar p† beside the
    declared-prior bar, both through ``scripts/bar_audit.py``'s machinery — the fold and
    the bisection of the imported ``decide.u_assert``, never a re-implementation, so
    neither 0.90 nor the live value is ever hard-coded here. r32 priced the drift
    (0.900 → 0.837, monotone: only abstain-verdicts fold and nothing pushes back until a
    wrong commit); this line is its watch. GUARDED: the computation needs the live brain,
    and a watch must never be a dependency — any failure returns ``{"error": ...}`` and
    the report renders the unavailability by name."""
    try:
        import bar_audit as BA

        from life_agent.core import lookup as LK
        brain = LK.shared_brain()
        stamp = now_iso or datetime.now(UTC).isoformat()
        u_now, _version, n_events = BA.u_bar_as_of(brain, stamp)
        declared = BA.indifference_point(BA.u_bar_from(brain, []))
        return {"p_dagger": BA.indifference_point(u_now), "declared": declared,
                "n_events": n_events}
    except Exception as e:  # the watch degrades to a named line, never a dead report
        return {"error": str(e)[:200]}


def _window_line(w: dict[str, Any]) -> str:
    """What the readout actually covered — so a watch that stopped is visible IN the
    readout. Before K3 a stopped watch produced no file, and nothing reads an absent file."""
    if not w["newest"]:
        return (f"- window: since {w['since']}, as of {w['as_of']} — **STALE: no rows at "
                f"all.** Either nothing was served in the window, or the stream this "
                f"readout was pointed at is not the one being written.")
    age = f"{w['age_days']} day(s) ago" if w["age_days"] is not None else "age unknown"
    line = (f"- window: since {w['since']} → newest row {w['newest']} ({age}), "
            f"as of {w['as_of']}")
    if w["stale"]:
        line += (f" — **STALE: nothing newer than {STALE_AFTER_DAYS} days.** The watch, "
                 f"the stream, or the box serving it has stopped.")
    return line


def _sources_line(sources: Sequence[dict[str, Any]]) -> str:
    """KB roots by INDEX and row count. Never a path: a root is an owner-specific absolute
    path and this report may be pasted anywhere."""
    if not sources:
        return "- sources: (unrecorded — readout() was called without roots)"
    parts = [f"root {i}: {src.get('rows', 0)} rows"
             + ("" if src.get("rows", 0) else " (EMPTY)")
             for i, src in enumerate(sources, start=1)]
    noun = "root" if len(sources) == 1 else "roots"
    return f"- sources: {len(sources)} KB {noun} — " + "; ".join(parts)


def _bar_line(bar: dict[str, Any] | None) -> list[str]:
    """The p† bullet (A6): absent bar key = a pre-A6 summary, no line (back-compat);
    an error = the named unavailability; else the deployed bar BESIDE the declared one
    (r32's rule: never quote either alone) with the drift direction stated."""
    if bar is None:
        return []
    if "p_dagger" not in bar:
        return [f"- assert bar p† unavailable ({bar.get('error', 'unknown')})"]
    return [f"- assert bar p† {bar['p_dagger']:.4f} (declared prior {bar['declared']:.4f}; "
            f"{bar['n_events']} folded events — one-way drift downward until a wrong "
            f"commit folds, r32)"]


def governance_summary() -> dict[str, Any]:
    """Arc 0 A0.5 — the delegation's own watch, read off the two registers.

    ``D-3`` replaced the interview with decide-and-publish, which is only auditable if
    someone can see it happening: how many forks were decided, how many are still awaiting
    a reaction, and how many reached the owner anyway (``RULINGS.md`` §4). Counts only —
    this is a readout, never a diagnosis (the cap). Guarded like :func:`bar_summary`: any
    failure becomes a named absence, because a watch must never break the report."""
    try:
        decisions = (REPO / "docs" / "unification" / "DECISIONS.md").read_text(
            encoding="utf-8")
        rulings = (REPO / "docs" / "unification" / "RULINGS.md").read_text(encoding="utf-8")
        return {"decisions": len(re.findall(r"^## GD-", decisions, re.M)),
                "open": len(re.findall(r"\*\(open", decisions)),
                "escalated": len(re.findall(r"^\| \*\*U-", rulings, re.M))}
    except Exception as e:  # the watch degrades to a named line, never a dead report
        return {"error": str(e)[:200]}


def _governance_line(gov: dict[str, Any] | None) -> list[str]:
    """The delegation bullet: absent key = a pre-A0.5 summary, no line (back-compat)."""
    if gov is None:
        return []
    if "decisions" not in gov:
        return [f"- governance unavailable ({gov.get('error', 'unknown')})"]
    return [f"- governance: {gov['decisions']} decided · {gov['open']} awaiting a reaction "
            f"· {gov['escalated']} escalated to the owner (docs/unification/DECISIONS.md)"]


def render(s: dict[str, Any]) -> str:
    lines = [
        f"# Production readout — since {s['since']}",
        "",
        f"_Generated {datetime.now(UTC).isoformat(timespec='seconds')}. A readout,"
        " not a diagnosis (the cap): counts and ids only, no corpus values._",
        "",
        _window_line(s["window"]),
        _sources_line(s["sources"]),
        "",
        f"- decisions by action: {json.dumps(s['decisions'], sort_keys=True)}",
        f"- deliberate-edge commits: {s['deliberate_commits']}",
        f"- graded outcomes: {json.dumps(s['graded'], sort_keys=True)}",
        f"- owner reactions: {json.dumps(s['reactions'], sort_keys=True)}",
        *_bar_line(s.get("bar")),
        *_governance_line(s.get("governance")),
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
    ap.add_argument("--kb", action="append", default=None, metavar="PATH",
                    help="a KB root to read (repeatable; default: $LIFE_AGENT_KB). The "
                         "streams are unioned — the live stream accrues on whichever box "
                         "served, and this repo names no box.")
    ap.add_argument("--out", default=None,
                    help="report path (default: <first --kb>/calibration/readout.md)")
    args = ap.parse_args(argv)
    from life_agent.core import config as CFG
    roots = [Path(k).expanduser() for k in (args.kb or [])] or [CFG.KB]

    # r27 (C10): a DECLARED root that is absent is a failure, not a quiet zero. `_rows`
    # returns [] for a missing file, so a root that was never there reads exactly like a
    # root with no traffic — and a watch that cannot tell "nothing happened" from "I was
    # not looking there" is the failure mode row 25 exists to end. Measured on the
    # authoring box: this reported a fresh, unflagged, single-root window over a stream
    # carrying no production traffic at all.
    #
    # The ROOT is the declaration; what is inside it is data. A root that exists with no
    # stream yet is a fresh deployment and a legitimate zero.
    absent = [r for r in roots if not r.is_dir()]
    if absent:
        sys.stderr.write(
            f"production_readout: {len(absent)} declared KB root(s) absent or unreadable: "
            f"{', '.join(str(r) for r in absent)}\n"
            "A declared root that is not there is not an empty stream. Fix the "
            "declaration or the mount; a readout over the roots that happen to exist is "
            "a confident answer about a population it cannot see.\n"
        )
        return 2
    cals = [r / "calibration" for r in roots]
    per_root = [(_rows(c / "decisions.jsonl"), _rows(c / "outcomes.jsonl"),
                 _rows(c / "reactions.jsonl")) for c in cals]
    s = readout(union(*[p[0] for p in per_root]),
                union(*[p[1] for p in per_root]),
                union(*[p[2] for p in per_root]),
                since=args.since,
                sources=[{"rows": sum(len(x) for x in p)} for p in per_root])
    s["bar"] = bar_summary()   # A6: the drift watch — guarded, never a dependency
    s["governance"] = governance_summary()   # A0.5: the delegation watch
    text = render(s)
    out = Path(args.out) if args.out else cals[0] / "readout.md"
    out.write_text(text, encoding="utf-8")
    print(text)
    print(f"→ {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
