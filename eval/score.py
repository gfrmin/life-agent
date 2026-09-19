"""The scoreboard: one table, every set, the columns rule 5 is read from.

    uv run python -m eval.score                 # print the board
    uv run python -m eval.score --write         # also write SCOREBOARD.md + eval/scoreboard.json
    uv run python -m eval.score --gate          # exit 1 if ΔU < 0 on any row (rule 5)

Sets are declared in `eval/sets.yaml`; their files live under `$LIFE_AGENT_KB` and are
pinned by sha256.

Columns, per (set, arm):
  rows · right · wrong · esc-right · esc-wrong · declined · $/q · U/q · s/q
`right`/`wrong` count every delivered answer (answered locally or escalated); the esc-
columns are the escalated share of each. `declined` = no answer delivered. `s/q` is blank
until the rows carry latency. The counts need no gauge; `U/q` prices them at the folded
utility mean (:class:`Gauge`): U = u_right·right + u_wrong·wrong + u_declined·declined -
lambda_usd·$. Rule 5 compares U, not a wrong-rate: a row whose U fell against the committed
board, both priced at today's gauge, does not merge.
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


@dataclass(frozen=True)
class Gauge:
    """The utility rule 5 prices a row at: the folded posterior means of the owner's utility
    (``lookup.current_u_bar``), so the merge rule and the decider read one loss."""

    u_right: float
    u_wrong: float
    u_declined: float
    lambda_usd: float

    def total(self, counts: Mapping[str, Any]) -> float:
        """U summed over a row's questions, from its counts (a :class:`Row` as a dict, or a
        committed board row)."""
        return (self.u_right * counts["right"] + self.u_wrong * counts["wrong"]
                + self.u_declined * counts["declined"]
                - self.lambda_usd * counts["usd_per_q"] * counts["rows"])


def folded_gauge() -> Gauge:
    """Today's gauge: the utility posterior folded over the owner's elicitations and
    reactions (needs ``$LIFE_AGENT_KB``)."""
    from life_agent.core import lookup as LK

    u, _version, _policy = LK.current_u_bar()
    return Gauge(u_right=u["u_correct"], u_wrong=u["u_wrong"], u_declined=u["u_abstain"],
                 lambda_usd=u["lambda_usd"])


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


def score_typed(set_name: str, lines: Iterable[str]) -> list[Row]:
    """The typed row alone, from a typed-only archive (``scripts/score_typed.py``): a set
    with no recorded oracle. Censored rows are excluded."""
    typed = [_response(r["typed"]) for ln in lines if ln.strip()
             for r in [json.loads(ln)] if not r.get("censored")]
    return [summarise(set_name, "typed", typed)]


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
        scorer = {"paired": score_paired, "typed": score_typed}.get(spec["kind"])
        if scorer is None:
            raise SystemExit(f"{name}: unknown kind {spec['kind']!r}")
        rows += scorer(name, data.decode("utf-8").splitlines())
    return rows, skipped


def _pct(k: int, n: int) -> str:
    return f"{k} ({100.0 * k / n:.1f}%)" if n else "0"


def render(rows: Sequence[Row], skipped: Mapping[str, str], gauge: Gauge | None = None
           ) -> str:
    priced = ("unpriced (no gauge)" if gauge is None else
              f"priced at the folded gauge u_right {gauge.u_right:g}, u_wrong "
              f"{gauge.u_wrong:.4f}, u_declined {gauge.u_declined:g}, lambda_usd "
              f"{gauge.lambda_usd:g}/$")
    out = ["# Scoreboard", "",
           "`python -m eval.score --write`. Counts over each set's rows; `right`/`wrong` "
           "include escalated answers, the esc- columns are their escalated share. "
           f"`U/q` is {priced}. Rule 5: a change merges when no row's U falls against the "
           "committed board at today's gauge (`--gate`).", "",
           "| set | arm | rows | right | wrong | esc-right | esc-wrong | declined | $/q | U/q "
           "| s/q |",
           "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in rows:
        s = "—" if r.s_per_q is None else f"{r.s_per_q:.1f}"
        u = "—" if gauge is None or not r.rows else f"{gauge.total(asdict(r)) / r.rows:+.3f}"
        out.append(f"| {r.set} | {r.arm} | {r.rows} | {_pct(r.right, r.rows)} | "
                   f"{_pct(r.wrong, r.rows)} | {r.esc_right} | {r.esc_wrong} | "
                   f"{_pct(r.declined, r.rows)} | {r.usd_per_q:.4f} | {u} | {s} |")
    if skipped:
        out += ["", "Not scored:", ""]
        out += [f"- `{k}` — {v}" for k, v in skipped.items()]
    return "\n".join(out) + "\n"


def unscored_pins(sets: Mapping[str, Mapping[str, Any]], skipped: Mapping[str, str]
                  ) -> list[str]:
    """Pinned (non-pending) sets that were not scored. The committed board is written only
    when this is empty, so a clone without the data can never overwrite it with less."""
    return sorted(k for k in skipped if sets[k]["kind"] != "pending")


def gate(rows: Sequence[Row], baseline: Sequence[Mapping[str, Any]], gauge: Gauge
         ) -> list[str]:
    """Rule 5 violations: rows whose U fell against the committed board, both priced at
    ``gauge`` — ΔU = U(new) - U(old) < 0. A row scored over a different number of questions
    is not paired with its baseline and is named too (re-pin the baseline deliberately)."""
    base = {(b["set"], b["arm"]): b for b in baseline}
    out: list[str] = []
    for r in rows:
        b = base.get((r.set, r.arm))
        if b is None:
            continue
        if b["rows"] != r.rows:
            out.append(f"{r.set}/{r.arm}: {b['rows']} -> {r.rows} rows, not paired")
            continue
        d = gauge.total(asdict(r)) - gauge.total(b)
        if d < -1e-9:
            out.append(f"{r.set}/{r.arm}: ΔU {d:+.3f} over {r.rows} rows "
                       f"(right {b['right']}->{r.right}, wrong {b['wrong']}->{r.wrong}, "
                       f"declined {b['declined']}->{r.declined})")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true",
                    help="write SCOREBOARD.md and eval/scoreboard.json")
    ap.add_argument("--gate", action="store_true",
                    help="ΔU against the committed eval/scoreboard.json at today's gauge "
                         "(rule 5)")
    a = ap.parse_args(argv)
    kb_env = os.environ.get("LIFE_AGENT_KB")
    rows, skipped = score(Path(kb_env) if kb_env else None, load_sets())
    gauge: Gauge | None
    try:
        gauge = folded_gauge() if kb_env else None
    except Exception as e:  # the counts still print; the gate below refuses without a gauge
        print(f"(no gauge: {type(e).__name__}: {e})", file=sys.stderr)
        gauge = None
    text = render(rows, skipped, gauge)
    print(text)
    if a.gate and BOARD_JSON.is_file():
        if gauge is None:
            print("RULE 5: no gauge to price ΔU with (set LIFE_AGENT_KB)", file=sys.stderr)
            return 2
        bad = gate(rows, json.loads(BOARD_JSON.read_text(encoding="utf-8"))["rows"], gauge)
        if bad:
            print("RULE 5: expected utility fell — does not merge:\n  "
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
