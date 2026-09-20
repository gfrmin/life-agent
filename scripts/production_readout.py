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

**It is a dead-man.** Exit 0 = a stream that moved inside the window; **exit 1 = STALE**,
the same condition the report's window line names; exit 2 = a declared KB root that is not
there. The report is written and printed either way — the exit code is what makes the
silence loud, because the wrapper (``bin/production-readout``) turns a non-zero run into a
monitor ``/fail`` ping. Before this, a stopped watch was a sentence in a file nobody opens
(the gap stated in ``docs/guards.md``: "nothing reads the production readout"). An empty
stream is stale too: an arm nobody exercises is an unmeasured configuration, not a pass.
``--allow-stale`` reads the report without the verdict; the timer must never pass it.
"""
from __future__ import annotations

import argparse
import json
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
    """r33 A6 (owner-ruled MONITOR ONLY): the live respond-vs-abstain bar p† beside the
    declared-prior bar. Both fold the owner's utility model through the deployed fold
    (``utility.posterior``, under the decider's declared policy) and read the break-even
    through ``gate.break_even`` — so neither 0.90 nor the live value is ever hard-coded
    here. The live fold takes the elicitations and reactions up to ``now_iso``; the
    declared bar folds none. GUARDED: a watch must never be a dependency — any failure
    returns ``{"error": ...}`` and the report renders the unavailability by name."""
    try:
        from life_agent.core import config as CFG
        from life_agent.core import gate as GATE
        from life_agent.core import lookup as LK
        from life_agent.core import reactions as RX
        from life_agent.core import utility as UT

        stamp = now_iso or datetime.now(UTC).isoformat()
        model = UT.load_model(CFG.UTILITY_MODEL)
        events: list[Any] = list(UT.load_elicitations(CFG.UTILITY_ELICITATIONS, model))
        events += RX.load_reactions(CFG.REACTIONS_LOG, CFG.DECISIONS_LOG)
        events = [e for e in events if str(e.tx_time) <= stamp]
        u_now = UT.posterior(model, events, policy=LK.U_BAR_POLICY).u_bar()
        u_declared = UT.posterior(model, [], policy=LK.U_BAR_POLICY).u_bar()
        return {"p_dagger": GATE.break_even(u_now), "declared": GATE.break_even(u_declared),
                "n_events": len(events)}
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
    ap.add_argument("--allow-stale", action="store_true",
                    help="read the report without the dead-man's verdict: exit 0 even when "
                         "the stream is stale. For reading by hand; the timer must not pass "
                         "it, or the watch stops being a watch.")
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
    text = render(s)
    out = Path(args.out) if args.out else cals[0] / "readout.md"
    out.write_text(text, encoding="utf-8")
    print(text)
    print(f"→ {out}", file=sys.stderr)

    # The dead-man. The report has said STALE since row 25; nothing ever asserted on it,
    # which is the same failure one layer up — a watch whose silence is only visible to
    # whoever opens the file. The window's own flag is the verdict, so the exit code and
    # the report can never disagree.
    if s["window"]["stale"] and not args.allow_stale:
        w = s["window"]
        age = ("no rows at all" if not w["newest"]
               else f"newest row {w['age_days']} day(s) old")
        sys.stderr.write(
            f"production_readout: STALE — {age}, past the {STALE_AFTER_DAYS}-day bar. "
            "The arm, the stream, or the box serving it has stopped; the report above is "
            "about a population that is not moving. Exit 1 so the timer's monitor hears "
            "it (--allow-stale to read without the verdict).\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
