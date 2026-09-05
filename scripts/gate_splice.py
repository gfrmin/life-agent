#!/usr/bin/env python3
"""Gate arm-splice — deterministic counterfactuals from ARCHIVED gate artifacts (§14).

A gate run changes several things at once (an instrument, a grader, a pricing term);
its Δ alone cannot attribute the move. This tool re-runs the production Δ posterior
(``gate.delta_posterior`` — same MC, same seed, same frozen δ/level) over paired rows
SPLICED from archived runs: the typed arm's realised actions from one run, the mono
arm's from another, grades and per-question costs swapped in or zeroed by flag. Every
number it prints is arithmetic on frozen artifacts under the CURRENT production
utility posterior (model.yaml + elicitations) — never a gate reading, never a ledger
write. Sanity pins first: an archived run's own rows must reproduce its published
verdict before any splice is trusted.

The run-5 attribution counterfactual (2026-08-17, the run-6 entry's named next
computation): run 5's typed actions (qwen-era instruments, matcher = judge on that arm
per the shadow audit) against run 6's mono grades (the identical replay, judge-graded
under the corrected golds) with both arms' realised spend — i.e. run 6 minus the
instrument change. What run 6 read beyond that number is the instrument's.

Usage:
  uv run python scripts/gate_splice.py --typed-from <paired.jsonl> --mono-from <paired.jsonl>
      [--typed-cost-decisions RUN_ID] [--mono-cost-replay DIR] [--zero-cost]
      [--pin <paired.jsonl> P DELTA_MEAN]... [--label TEXT] [--out FILE]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_eval import load_questions, load_replay_answers

import life_agent.core.gate as GATE
import life_agent.core.lookup as LK
import life_agent.core.utility as UT
from life_agent.core import config as LCFG
from life_agent.core.decisions import question_id as _qhash


def load_paired(path: Path) -> dict[str, dict]:
    rows = [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return {str(r["question_id"]): r for r in rows}


def baseline_of(rows: dict[str, dict], path: Path) -> str:
    """The comparator arm an archived paired file was recorded against, read from the rows
    themselves (r28). The baseline is a property of the MONO source, so a splice inherits
    the mono archive's tag; rows that disagree are a corrupt archive and refuse loudly
    rather than letting one of them name the report."""
    tags = {str(r.get("baseline") or "") for r in rows.values()}
    if len(tags) != 1:
        raise SystemExit(f"{path}: rows disagree on their baseline arm: {sorted(tags)}")
    tag = tags.pop()
    if not tag:
        raise SystemExit(f"{path}: rows carry no baseline arm; the archive predates the "
                         "tag and cannot be rendered without naming its comparator")
    return tag


def _resp(arm: dict, *, cost: float | None) -> GATE.RealisedResponse:
    """A paired-row arm → RealisedResponse; ``cost`` None keeps the row's own cost_usd
    (0.0 when the archived row predates the spend field)."""
    return GATE.RealisedResponse(
        action=str(arm["action"]), correct=arm.get("correct"),
        cost_usd=float(arm.get("cost_usd") or 0.0) if cost is None else cost,
        withheld=arm.get("withheld"))


def splice(typed_rows: dict[str, dict], mono_rows: dict[str, dict], *,
           typed_cost: dict[str, float] | None, mono_cost: dict[str, float] | None,
           zero_cost: bool) -> list[GATE.PairedOutcome]:
    """Typed arm from one archive, mono arm from another, joined on question id (the
    intersection — a splice over differing question sets is refused loudly)."""
    ids = sorted(typed_rows)
    if set(ids) != set(mono_rows):
        raise SystemExit(f"question sets differ: typed {len(typed_rows)} vs mono "
                         f"{len(mono_rows)}; symmetric diff "
                         f"{sorted(set(typed_rows) ^ set(mono_rows))[:8]}")
    out = []
    for qid in ids:
        t, m = typed_rows[qid], mono_rows[qid]
        tc = 0.0 if zero_cost else (typed_cost.get(qid, 0.0) if typed_cost is not None else None)
        mc = 0.0 if zero_cost else (mono_cost.get(qid, 0.0) if mono_cost is not None else None)
        out.append(GATE.PairedOutcome(
            question_id=qid, answerable=bool(t["answerable"]),
            typed=_resp(t["typed"], cost=tc), mono=_resp(m["mono"], cost=mc)))
    return out


def decisions_cost(run_id: str, questions: list[dict]) -> dict[str, float]:
    """The typed arm's per-question realised spend for an archived run, from the
    decisions log (decisions-v2 ``cost_usd``, keyed by the question-text hash) — exact
    where the log has a row; a question with no decide call spent nothing there."""
    h2q = {_qhash(str(q["question"])): str(q["id"]) for q in questions}
    cost: dict[str, float] = defaultdict(float)
    for line in (LCFG.DECISIONS_LOG.read_text(encoding="utf-8").splitlines()):
        if not line.strip() or run_id not in line:
            continue
        r = json.loads(line)
        if r.get("run_id") != run_id:
            continue
        qid = h2q.get(str(r["question_id"]))
        if qid is not None:
            cost[qid] += float(r.get("cost_usd") or 0.0)
    return dict(cost)


def replay_cost(path: Path) -> dict[str, float]:
    return {qid: float((row.get("usage") or {}).get("estimated_cost_usd") or 0.0)
            for qid, row in load_replay_answers(path).items()}


def production_posterior() -> UT.UtilityPosterior:
    """Exactly the gate's fold (run_eval --gate): the frozen model + the elicitation
    ledger through the credence skin. Reactions fold elsewhere (the live decide path)."""
    brain = LK.shared_brain()
    model = UT.load_model(LCFG.UTILITY_MODEL)
    evidence: list[UT.Evidence] = list(UT.load_elicitations(LCFG.UTILITY_ELICITATIONS, model))
    return UT.posterior(brain, model, evidence, policy="frozen-elicitations")


def summarise(tag: str, paired: list[GATE.PairedOutcome],
              post: UT.UtilityPosterior) -> tuple[GATE.GateResult, str]:
    r = GATE.delta_posterior(paired, post, oracle_p=LK._ORACLE_P)
    ub = post.u_bar()
    n = len(paired)
    tu = sum(GATE.realised_utility(p.typed, ub, oracle_p=LK._ORACLE_P) for p in paired) / n
    mu = sum(GATE.realised_utility(p.mono, ub, oracle_p=LK._ORACLE_P) for p in paired) / n
    d = r.diagnostics
    line = (f"| {tag} | {r.p_delta_gt:.3f} | {'PASS' if r.passed else 'FAIL'} "
            f"| {r.delta_mean:+.3f} | [{r.delta_lo:+.3f}, {r.delta_hi:+.3f}] "
            f"| {tu:+.3f} | {mu:+.3f} "
            f"| {d.typed_answer_rate:.2f} / {d.mono_answer_rate:.2f} "
            f"| ${sum(p.typed.cost_usd for p in paired):.2f} / "
            f"${sum(p.mono.cost_usd for p in paired):.2f} |")
    return r, line


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--splice", nargs=4, action="append", default=[],
                    metavar=("LABEL", "TYPED_PAIRED", "MONO_PAIRED", "COST"),
                    help="one ladder rung: typed arm from TYPED_PAIRED, mono arm from "
                         "MONO_PAIRED; COST is `zero` (both arms at $0 — pre-run-6 "
                         "semantics), `archived` (each row's own cost_usd) or `priced` "
                         "(typed from --typed-cost-decisions, mono from --mono-cost-replay)")
    ap.add_argument("--typed-cost-decisions", metavar="RUN_ID",
                    help="typed per-question spend from the decisions log for RUN_ID "
                         "(for COST=priced)")
    ap.add_argument("--mono-cost-replay", type=Path,
                    help="mono per-question spend from a fairfight replay dir/answers.jsonl "
                         "(for COST=priced)")
    ap.add_argument("--pin", nargs=3, action="append", default=[],
                    metavar=("PAIRED", "P", "DMEAN"),
                    help="sanity pin: PAIRED's own rows (own costs) must reproduce "
                         "P(Δ>δ)=P and Δ̄=DMEAN to 3 dp — the whole run is refused otherwise")
    ap.add_argument("--questions", type=Path, default=None)
    ap.add_argument("--title", default="gate arm-splice")
    ap.add_argument("--report-for", metavar="LABEL", default=None,
                    help="which rung gets the full gate report appended (default: the last)")
    ap.add_argument("--out", type=Path, default=None,
                    help="write the report here (markdown)")
    args = ap.parse_args(argv)
    if not args.splice and not args.pin:
        ap.error("nothing to do: give --pin and/or --splice")

    questions = load_questions(args.questions) if args.questions else load_questions()
    post = production_posterior()
    ub = post.u_bar()
    lam = post.latents.get("lambda_usd")

    hdr = ("| variant | P(Δ>0.05) | verdict | Δ̄ | 90% interval | EU/q typed | EU/q mono "
           "| answer rate t/m | spend t/m |\n|---|---|---|---|---|---|---|---|---|")
    lines: list[str] = []
    results: dict[str, GATE.GateResult] = {}
    baselines: dict[str, str] = {}   # r28: each rung's comparator, from its mono archive

    # sanity pins: an archive's own rows → its published verdict, or refuse everything
    for pin_path, p_want, d_want in args.pin:
        rows = load_paired(Path(pin_path))
        paired = splice(rows, rows, typed_cost=None, mono_cost=None, zero_cost=False)
        r, line = summarise(f"pin `{Path(pin_path).name}` (own rows, own costs)", paired, post)
        lines.append(line)
        if round(r.p_delta_gt, 3) != round(float(p_want), 3) \
                or round(r.delta_mean, 3) != round(float(d_want), 3):
            print(hdr + "\n" + "\n".join(lines))
            print(f"\nPIN FAILED: {pin_path} reads {r.p_delta_gt:.3f}/{r.delta_mean:+.3f}, "
                  f"published {float(p_want):.3f}/{float(d_want):+.3f} — the posterior or "
                  f"the code has drifted from the archive; no splice is trusted.")
            return 2

    tcost = decisions_cost(args.typed_cost_decisions, questions) \
        if args.typed_cost_decisions else None
    mcost = replay_cost(args.mono_cost_replay) if args.mono_cost_replay else None
    inputs: list[str] = []
    for label, typed_path, mono_path, cost in args.splice:
        if cost not in ("zero", "archived", "priced"):
            ap.error(f"COST must be zero|archived|priced, got {cost!r}")
        if cost == "priced" and (tcost is None or mcost is None):
            ap.error("COST=priced needs --typed-cost-decisions and --mono-cost-replay")
        paired = splice(load_paired(Path(typed_path)), load_paired(Path(mono_path)),
                        typed_cost=tcost if cost == "priced" else None,
                        mono_cost=mcost if cost == "priced" else None,
                        zero_cost=cost == "zero")
        r, line = summarise(label, paired, post)
        lines.append(line)
        results[label] = r
        baselines[label] = baseline_of(load_paired(Path(mono_path)), Path(mono_path))
        inputs.append(f"- **{label}** — typed `{Path(typed_path).name}` "
                      f"(sha {_sha(Path(typed_path))}) x mono `{Path(mono_path).name}` "
                      f"(sha {_sha(Path(mono_path))}); costs {cost}")

    report = [f"# {args.title}", "",
              "**Not a gate reading.** Deterministic arithmetic on archived artifacts "
              "under the current production utility posterior "
              f"(u_wrong {ub['u_wrong']:+.4f}, lambda_usd "
              f"{'absent' if lam is None else f'{lam.mean:.4f} ± {lam.variance ** 0.5:.4f}'}, "
              f"fold {post.fold_version[:16]}); {GATE.DEFAULT_N_DRAWS} draws, seed "
              f"{GATE.DEFAULT_SEED}, δ={GATE.MATERIALITY_DELTA}, level={GATE.GATE_LEVEL}.", ""]
    if tcost is not None:
        report.append(f"- typed spend (priced rungs): decisions log for "
                      f"`{args.typed_cost_decisions}` — ${sum(tcost.values()):.4f} over "
                      f"{len(tcost)} question(s) with a decide row; the rest spent $0")
    if mcost is not None:
        report.append(f"- mono spend (priced rungs): `{args.mono_cost_replay}` — "
                      f"${sum(mcost.values()):.4f}")
    report += [*inputs, "", hdr, *lines, ""]
    if results:
        pick = args.report_for or list(results)[-1]
        if pick not in results:
            ap.error(f"--report-for {pick!r} names no rung")
        report += [f"## Full gate report — {pick}", "",
                   # not a gate reading (stated above): this splice re-scores archives under
                   # the current posterior and declares no pricing regime — the report says
                   # so rather than assuming the two agree (`M-33`/`M-34`)
                   GATE.render_report(results[pick], run_id=pick, elapsed=0.0,
                                      baseline=baselines[pick], pairing=None,
                                      reach_rate=None)]
    text = "\n".join(report)
    print(text)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
