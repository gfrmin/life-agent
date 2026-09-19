"""The scoreboard: one table, every set, the columns rule 5 is read from.

    uv run python -m eval.score                 # print the board
    uv run python -m eval.score --write         # also write SCOREBOARD.md + eval/scoreboard.json
    uv run python -m eval.score --gate          # exit 1 if wrong% rose > 0.2 pp on any row

Counts only: no utility, no gauge, no posterior, so a reader can check a row without first
accepting `u_wrong`. Sets are declared in `eval/sets.yaml`; their files live under
`$LIFE_AGENT_KB` and are pinned by sha256.

Columns, per (set, arm):
  rows · right · wrong · esc-right · esc-wrong · declined · $/q · s/q
`right`/`wrong` count every delivered answer (answered locally or escalated); the esc-
columns are the escalated share of each. `declined` = no answer delivered. `s/q` is blank
until the rows carry latency.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

from life_agent.core.gate import ASSERT_ACTIONS

REPO = Path(__file__).resolve().parent.parent
SETS = REPO / "eval" / "sets.yaml"
BOARD_MD = REPO / "SCOREBOARD.md"
BOARD_JSON = REPO / "eval" / "scoreboard.json"
#: Rule 5: wrong% on any row may not rise by more than this without the owner.
WRONG_TOLERANCE_PP = 0.2


@dataclass(frozen=True)
class Response:
    """One arm's realised answer on one question."""

    asserted: bool
    correct: bool | None
    cost_usd: float
    escalated: bool = False
    latency_s: float | None = None


@dataclass(frozen=True)
class Row:
    """One (set, arm) line of the board."""

    set: str
    arm: str
    rows: int
    right: int
    wrong: int
    esc_right: int
    esc_wrong: int
    declined: int
    usd_per_q: float
    s_per_q: float | None

    @property
    def wrong_pct(self) -> float:
        return 100.0 * self.wrong / self.rows if self.rows else 0.0


def _response(arm: Mapping[str, Any]) -> Response:
    return Response(asserted=arm["action"] in ASSERT_ACTIONS, correct=arm.get("correct"),
                    cost_usd=float(arm.get("cost_usd") or 0.0),
                    latency_s=arm.get("latency_s"))


def route(typed: Response, oracle: Response) -> Response:
    """The router: typed where typed asserted, otherwise the oracle. Cost is additive — an
    escalated question paid the typed attempt and the oracle call."""
    if typed.asserted:
        return typed
    latency = (None if typed.latency_s is None or oracle.latency_s is None
               else typed.latency_s + oracle.latency_s)
    return Response(asserted=oracle.asserted, correct=oracle.correct,
                    cost_usd=typed.cost_usd + oracle.cost_usd, escalated=True,
                    latency_s=latency)


def summarise(set_name: str, arm: str, responses: Sequence[Response]) -> Row:
    n = len(responses)
    right = [r for r in responses if r.asserted and r.correct]
    wrong = [r for r in responses if r.asserted and not r.correct]
    lat = [r.latency_s for r in responses]
    return Row(set=set_name, arm=arm, rows=n, right=len(right), wrong=len(wrong),
               esc_right=sum(r.escalated for r in right),
               esc_wrong=sum(r.escalated for r in wrong),
               declined=sum(not r.asserted for r in responses),
               usd_per_q=sum(r.cost_usd for r in responses) / n if n else 0.0,
               s_per_q=(sum(x for x in lat if x is not None) / n
                        if n and all(x is not None for x in lat) else None))


def score_paired(set_name: str, lines: Iterable[str]) -> list[Row]:
    """typed / oracle / router rows from a paired-rows archive. Censored rows (the typed arm
    could not read the corpus) are excluded from every arm alike."""
    typed, oracle = [], []
    for ln in lines:
        if not ln.strip():
            continue
        r = json.loads(ln)
        if r.get("censored"):
            continue
        typed.append(_response(r["typed"]))
        oracle.append(_response(r["mono"]))
    return [summarise(set_name, "typed", typed),
            summarise(set_name, "oracle", oracle),
            summarise(set_name, "router", [route(t, o) for t, o in zip(typed, oracle,
                                                                        strict=True)])]


def load_sets(path: Path = SETS) -> dict[str, dict[str, Any]]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))["sets"]


def score(kb: Path | None, sets: Mapping[str, Mapping[str, Any]]
          ) -> tuple[list[Row], dict[str, str]]:
    """Every scorable set's rows, plus a reason for each set not scored."""
    rows: list[Row] = []
    skipped: dict[str, str] = {}
    for name, spec in sets.items():
        if spec["kind"] == "pending":
            skipped[name] = spec.get("note", "pending")
            continue
        if kb is None:
            skipped[name] = "LIFE_AGENT_KB unset"
            continue
        f = kb / spec["path"]
        if not f.is_file():
            skipped[name] = f"absent: $LIFE_AGENT_KB/{spec['path']}"
            continue
        data = f.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != spec["sha256"]:
            raise SystemExit(f"{name}: sha256 {digest} != pinned {spec['sha256']} "
                             f"({f}) — the pinned bytes moved; re-pin deliberately")
        if spec["kind"] != "paired":
            raise SystemExit(f"{name}: unknown kind {spec['kind']!r}")
        rows += score_paired(name, data.decode("utf-8").splitlines())
    return rows, skipped


def _pct(k: int, n: int) -> str:
    return f"{k} ({100.0 * k / n:.1f}%)" if n else "0"


def render(rows: Sequence[Row], skipped: Mapping[str, str]) -> str:
    out = ["# Scoreboard", "",
           "`python -m eval.score --write`. Counts over each set's rows; `right`/`wrong` "
           "include escalated answers, the esc- columns are their escalated share. "
           f"Rule 5: `wrong` may not rise more than {WRONG_TOLERANCE_PP} pp on any row "
           "without the owner.", "",
           "| set | arm | rows | right | wrong | esc-right | esc-wrong | declined | $/q | s/q |",
           "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in rows:
        s = "—" if r.s_per_q is None else f"{r.s_per_q:.1f}"
        out.append(f"| {r.set} | {r.arm} | {r.rows} | {_pct(r.right, r.rows)} | "
                   f"{_pct(r.wrong, r.rows)} | {r.esc_right} | {r.esc_wrong} | "
                   f"{_pct(r.declined, r.rows)} | {r.usd_per_q:.4f} | {s} |")
    if skipped:
        out += ["", "Not scored:", ""]
        out += [f"- `{k}` — {v}" for k, v in skipped.items()]
    return "\n".join(out) + "\n"


def unscored_pins(sets: Mapping[str, Mapping[str, Any]], skipped: Mapping[str, str]
                  ) -> list[str]:
    """Pinned (non-pending) sets that were not scored. The committed board is written only
    when this is empty, so a clone without the data can never overwrite it with less."""
    return sorted(k for k in skipped if sets[k]["kind"] != "pending")


def gate(rows: Sequence[Row], baseline: Sequence[Mapping[str, Any]]) -> list[str]:
    """Rule 5 violations: rows whose wrong% rose more than the tolerance over the baseline."""
    base = {(b["set"], b["arm"]): 100.0 * b["wrong"] / b["rows"] for b in baseline
            if b["rows"]}
    return [f"{r.set}/{r.arm}: wrong {base[(r.set, r.arm)]:.1f}% -> {r.wrong_pct:.1f}%"
            for r in rows if (r.set, r.arm) in base
            and r.wrong_pct - base[(r.set, r.arm)] > WRONG_TOLERANCE_PP]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true",
                    help="write SCOREBOARD.md and eval/scoreboard.json")
    ap.add_argument("--gate", action="store_true",
                    help="compare against the committed eval/scoreboard.json (rule 5)")
    a = ap.parse_args(argv)
    kb_env = os.environ.get("LIFE_AGENT_KB")
    rows, skipped = score(Path(kb_env) if kb_env else None, load_sets())
    text = render(rows, skipped)
    print(text)
    if a.gate and BOARD_JSON.is_file():
        bad = gate(rows, json.loads(BOARD_JSON.read_text(encoding="utf-8"))["rows"])
        if bad:
            print("RULE 5: wrong rose beyond tolerance — needs the owner:\n  "
                  + "\n  ".join(bad), file=sys.stderr)
            return 1
    if a.write:
        missing = unscored_pins(load_sets(), skipped)
        if missing:
            print(f"refusing to write the board: pinned set(s) not scored: {missing}",
                  file=sys.stderr)
            return 1
        BOARD_MD.write_text(text, encoding="utf-8")
        BOARD_JSON.write_text(json.dumps({"rows": [asdict(r) for r in rows]}, indent=2)
                              + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
