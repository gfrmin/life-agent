#!/usr/bin/env python3
"""Replace-branch audit — does a probe DISCARDING a grounded channel decide the answer?

The executor's enactment loop holds the grounded channel in ``obs`` / ``rho`` / ``era`` and,
at five sites, a probe's reply REPLACES those bindings outright rather than joining its
observations to them (design §6.12). r05's redirection is the first evidence that names this
mechanism rather than suspecting it: run 10's one wrong commit was taken by a view carrying
``instrument: deliberate@<opus>`` at n_obs = 1 over a grounded channel of five observations
across four documents whose sole candidate — the gold — sat at 0.985.

This audit reads that class at zero spend, from the run's OWN records.

FROZEN CRITERIA (stated before any result is read; §14 carries the mirror):

1. SCOPE — every replace/override site on run 10's decision path, enumerated from
   `core/executor.py` and not from the suspicion. Ruled by the owner on 2026-08-22 to be the
   class rather than the registered NULL-as-disagreement hypothesis alone, on r05's own
   lesson: an instrument written around the presumed fix measures the fix, not the defect.

     S1  the `corroborate_*` tiers          guard: `not _null_read(cr)`   discards obs, era
     S2  the retrieval grows                guard: `bool(n_ext["candidates"])`
                                                        discards hits, ext, candidates, obs, rho
     S3  the `deliberate` edge              guard: `status == "ok"` ONLY — no null-read guard
     S4  in-loop `re_extract_strong`        guard: `not _null_read(cr)`   discards obs, era
     S5  the k=0 rescue walk                reached only with nothing grounded — mints, never
                                            discards

   A site's exposure is read off the run's attributed-edge stream. **S2 emits no edge event**
   (it changes retrieval, not the answer-proposing edge), so its exposure is NOT READABLE from
   these records and is reported as unmeasured — never as zero. The `extract@<opus>` spelling
   is shared by S1's opus tier, S4 and S5, so it is reported as an AMBIGUITY CLASS; S5 is
   separable, because it is reached only when nothing grounded.

2. EXPOSURE — per site, the number of run questions on which it fired. Exposure 0 is reported
   as *untaken*, never as *clean*.

3. CHANNEL LOSS — per firing, the grounded channel's n_obs against the committed posterior's
   n_obs. Loss <= 0 is not a discard.

4. DELIVERED REACH — the counterfactual is RETIRE-NOT-REPLACE: the probe retires fail-open and
   the grounded channel stands, which is exactly the treatment S1 and S4 already give a null
   read, generalised. It is therefore a deployable rule and not an invented one. Reach = the
   number of questions whose committed action differs between the two arms.

5. THE SPLIT — every reach row classified against the run's own gold as REPAIR (a wrong commit
   becomes right, or becomes an honest withholding), REGRESSION (a right commit becomes wrong,
   or becomes a withholding) or NEUTRAL. Reach is published as the triple, never as a total.
   *Completed before any reading, because the frozen text left the direction unnamed:* a
   withholding that becomes a CORRECT commit is a REPAIR; a withholding that becomes a WRONG
   commit is a REGRESSION. A row either arm cannot grade is NAMED, never bucketed.

6. CONSERVATISM — for each disagreement, which side the DEPLOYED rule falls on: conservative
   (it withholds where the counterfactual commits) or aggressive (it commits where the
   counterfactual withholds). Both directions counted.

7. THE ASYMMETRY — S1 and S4 were taught in 2026-08-18 that a joint re-read naming nothing is
   ABSENCE of evidence and must not erase a grounded posterior. S3 was not. *Amended before any
   reading (a feasibility fact, not a result):* the eval writer emits an edge-outcome row only
   when the firing carried BOTH a value and a self-report, so a reply that named nothing leaves
   no row. The asymmetry is therefore read off a CONJUNCTION of the run's own records — the
   terminal decision row's `instrument` field is set only by the deliberate branch (the
   `extract@` siblings go through `_edge_event`, which never touches it), so `instrument`
   naming deliberate WITH no `deliberate@` outcome row for that question AND a terminal n_obs
   of 0 over a base channel with n_obs > 0 is the signature of S3 collapsing a grounded channel
   on an empty ok reply. That conjunction is also the signature the registered n_obs=0 cluster
   was described by (candidates at exactly uniform credences), so this criterion doubles as the
   first test of whether that cluster IS S3.

8. THE VERDICT, applied mechanically per site:
     - reach >= 1 AND repairs > regressions  => BUILD the retire-not-replace guard for that
       site AND buy one isolated gate run under §6.10;
     - reach >= 1 AND repairs <= regressions => REFUSE — the deployed rule is not worse; record
       the bound;
     - reach 0 with exposure >= 5            => KNOWN-AND-UNCOVERED (the §6.11 precedent), no
       code;
     - exposure < 5                          => NO-GO, too few load-bearing questions to read.
   The bar of 5 is inherited from r05 deliberately, so the two checkpoints are comparable.

9. THE INSTRUMENT'S OWN LIMITS, published and never averaged away:
   (a) Only ONE of the two arms is recomputed. The DEPLOYED arm is READ from the run's terminal
       decision row (its `chosen_action`, its leader the argmax over the recorded
       candidates/credences), never re-derived — so r05's 70-of-102 layer gap applies to the
       counterfactual arm alone, and it is bounded here by a DIRECT CONTROL rather than
       inherited: on every question where no edge fired the terminal IS the base channel, so
       audit-base against recorded-terminal on those rows measures the layer agreement on this
       very run. Published as a rate, with the disagreeing rows named. Both arms are graded by
       the SAME matcher; where that matcher disagrees with the run's judge grade on the
       deployed arm, the row is flagged.
   (b) The JOIN counterfactual (pool base + probe observations under §5 dedup) is NOT read
       here — the probe's observations are not in the records and reading them needs a live
       bridge replay. It is named as the escalation, not silently dropped.
   (c) Any question whose base channel cannot be recomputed without spend is EXCLUDED BY NAME.

10. NO DECISION-PATH CODE. Nothing under `src/` changes in this checkpoint; a commit gate
    refuses if `src/` is dirty.

Usage:
  uv run python scripts/replace_audit.py --run-id gate-20260821T094545 \
      --paired $KB/eval/gate-outside-option/paired-gate-20260821T094545.jsonl \
      --decisions $KB/calibration/decisions.jsonl \
      --outcomes $KB/calibration/outcomes.jsonl \
      --questions $KB/eval/questions_v2.yaml [--k 20] [--out F.md] [--out-yaml F.yaml]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from carrier_audit import Arm, committed, correct, decide_arm  # the shared decision tail
from carrier_audit import _run_date as run_date
from gate_splice import load_paired
from run_eval import load_questions

import life_agent.core.decisions as DEC
import life_agent.core.deliberate as DL
import life_agent.core.executor as EX
import life_agent.core.lookup as LK
import life_agent.core.probes as PR
import life_agent.core.retrieval as RET
import life_agent.owner as owner
from life_agent.collapse.taps import RefusingClient, WouldSpendError
from life_agent.core import config as LCFG

# The five sites §6.12 enumerates, with the guard that decides whether the replace is taken.
SITES: dict[str, str] = {
    "S1": "corroborate_* tiers — guard: not _null_read(cr)",
    "S2": "retrieval grows (retrieve_rerank / retrieve_expand) — guard: new candidates",
    "S3": "the deliberate edge — guard: status == 'ok' ONLY (no null-read guard)",
    "S4": "re_extract_strong, in-loop — guard: not _null_read(cr)",
    "S5": "the k=0 rescue walk — mints from zero, discards nothing",
}
# S2 changes retrieval, not the answer-proposing edge, so it lands in no attribution stream.
UNREADABLE_SITES = ("S2",)


def _edge_sites() -> dict[str, tuple[str, ...]]:
    """Edge spelling -> the sites that could have emitted it, MIRRORED from the executor's own
    constants. A hand-copied tier list rots the moment a tier is added, and the shared
    `extract@<opus>` spelling is an ambiguity the records cannot resolve — so it is returned as
    a class rather than guessed at."""
    m: dict[str, list[str]] = {}
    for model in EX._TIER_MODEL.values():
        m.setdefault(EX.extract_edge(model), []).append("S1")
    m.setdefault(EX.extract_edge(EX._RE_EXTRACT_MODEL), []).extend(("S4", "S5"))
    m.setdefault(DL.instrument(EX._DELIBERATE_MODEL), []).append("S3")
    return {e: tuple(dict.fromkeys(s)) for e, s in m.items()}


EDGE_SITES: dict[str, tuple[str, ...]] = _edge_sites()


def site_of_edge(edge: str) -> tuple[str, ...]:
    """`("?",)` for an unrecognised spelling — named, never silently dropped."""
    return EDGE_SITES.get(edge, ("?",))


# --- the two arms ----------------------------------------------------------------------

def deployed_arm(row: dict[str, Any]) -> Arm:
    """The DEPLOYED arm, READ off the run's own terminal decision row — never re-derived
    (criterion 9a). The leader is the argmax over the recorded credences, which is how the
    view's own render picks the asserted value."""
    ps = dict(row.get("posterior_summary") or {})
    cands = [str(c) for c in (ps.get("candidates") or [])]
    creds = [float(c) for c in (ps.get("credences") or [])]
    n = min(len(cands), len(creds))
    leader = max(range(n), key=lambda i: creds[i]) if n else None
    return Arm(action=str(row.get("chosen_action") or ""),
               leader=cands[leader] if leader is not None else "",
               n_obs=int(ps.get("n_obs") or 0), n_docs=0,
               p_none=float(ps.get("p_none") or 0.0),
               eu=float(row.get("predicted_eu") or 0.0),
               credences=creds[:n])


def channel_loss(base: Arm | None, deployed: Arm) -> int:
    """Criterion 3 — observations the committed posterior no longer holds. Never negative:
    a channel that GREW was not discarded."""
    if base is None:
        return 0
    return max(0, base.n_obs - deployed.n_obs)


def action_differs(deployed: Arm, counterfactual: Arm | None) -> bool:
    """Criterion 4 — reach is a difference in the COMMITTED ACTION, not in the posterior."""
    if counterfactual is None:
        return False
    return (committed(deployed) != committed(counterfactual)
            or (committed(deployed)
                and deployed.leader != counterfactual.leader))


def classify(deployed: Arm | None, counterfactual: Arm | None,
             gold: str, variants: list[str]) -> str:
    """Criterion 5, including the direction the frozen text left unnamed."""
    if deployed is None or counterfactual is None:
        return "ungradeable"
    dep_c, cf_c = committed(deployed), committed(counterfactual)
    dep_r = correct(deployed, gold, variants)
    cf_r = correct(counterfactual, gold, variants)
    if dep_c and not dep_r:                      # the deployed arm commits WRONGLY
        return "repair" if (cf_r or not cf_c) else "unchanged"
    if dep_c and dep_r:                          # the deployed arm commits CORRECTLY
        return "unchanged" if cf_r else "regression"
    if cf_c:                                     # the deployed arm withholds
        return "repair" if cf_r else "regression"
    return "unchanged"


def conservative_side(deployed: Arm, counterfactual: Arm | None) -> str:
    """Criterion 6 — which side the DEPLOYED rule falls on when the two disagree."""
    if counterfactual is None or committed(deployed) == committed(counterfactual):
        return "none"
    return "conservative" if not committed(deployed) else "aggressive"


def s3_collapse(*, instrument: str, graded_edge: bool,
                dep_n_obs: int, base_n_obs: int) -> bool:
    """Criterion 7's conjunction: the deliberate branch fired (only it sets `instrument`), the
    firing left no gradeable row (it named nothing), the committed posterior holds no
    observation, and there WAS a grounded channel to lose."""
    return (instrument.startswith("deliberate@") and not graded_edge
            and dep_n_obs == 0 and base_n_obs > 0)


def verdict(*, exposure: int, reach: int, repairs: int, regressions: int) -> tuple[str, str]:
    """Criterion 8, applied mechanically — no reading of a borderline row."""
    if exposure < 5:
        why = ("untaken on this run — exposure 0, which is not the same as clean"
               if exposure == 0 else
               f"exposure {exposure} < 5, the bar inherited from r05")
        return "NO-GO", why
    if reach == 0:
        return "KNOWN-UNCOVERED", (
            f"exposure {exposure} >= 5 but delivered reach 0 — real, measured, and left "
            "uncovered (the §6.11 precedent); no decision-path code")
    if repairs > regressions:
        return "BUILD+PRICE", (
            f"reach {reach}, repairs {repairs} > regressions {regressions} — build the "
            "retire-not-replace guard for this site and buy one isolated run under §6.10")
    return "REFUSE", (
        f"reach {reach}, repairs {repairs} <= regressions {regressions} — the deployed rule "
        "is not worse, only different; record the bound")


# --- the run's own records --------------------------------------------------------------

def load_decisions(path: Path, run_id: str) -> dict[str, dict[str, Any]]:
    """The run's TERMINAL decision per question (last row wins — the log is append-only and a
    re-decide appends). Keyed on `decisions.question_id`, the sha of the question text."""
    out: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get("run_id") == run_id and r.get("question_id"):
                out[str(r["question_id"])] = r
    return out


def load_edges(path: Path, run_id: str) -> dict[str, list[dict[str, Any]]]:
    """The run's attributed-edge firings per question, in firing order. Keyed on the EVAL
    question id (the spelling `edge_outcome` stamps), which is NOT the decisions key."""
    out: dict[str, list[dict[str, Any]]] = {}
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get("run_id") != run_id or r.get("grader") != "eval_edge":
                continue
            edge = str((r.get("instrument_identity") or {}).get("edge") or "")
            if not edge:
                continue
            out.setdefault(str(r.get("question_id")), []).append(
                {"edge": edge, "grade": str(r.get("grade") or ""),
                 "lineage": list(r.get("lineage_keys") or [])})
    return out


# --- the reading -------------------------------------------------------------------------

@dataclass
class Row:
    qid: str
    gold: str
    edges: list[str] = field(default_factory=list)
    sites: list[str] = field(default_factory=list)
    graded_edge: bool = False
    instrument: str = ""
    base: Arm | None = None
    dep: Arm | None = None
    loss: int = 0
    outcome: str = ""
    side: str = "none"
    reach: bool = False
    collapse: bool = False
    judge_correct: bool | None = None
    matcher_correct: bool = False
    judge_flip: bool = False
    no_edge_control: bool = False   # criterion 9(a)'s direct control row
    control_agrees: bool = False


def audit_rows(paired: dict[str, dict[str, Any]], questions: list[dict[str, Any]],
               decisions: dict[str, dict[str, Any]],
               edges: dict[str, list[dict[str, Any]]],
               conn: Any, root: Path, *, k: int, today: date, client: Any, brain: Any,
               profile: str) -> tuple[list[Row], list[str]]:
    by_id = {str(q["id"]): q for q in questions}
    rows: list[Row] = []
    excluded: list[str] = []
    for qid, p in sorted(paired.items()):
        q = by_id.get(qid)
        if q is None:
            excluded.append(f"{qid} (not in the questions file)")
            continue
        gold = str(q.get("answer") or "")
        if not gold:
            excluded.append(f"{qid} (unanswerable by construction — no gold)")
            continue
        question = str(q["question"])
        drow = decisions.get(DEC.question_id(question))
        if drow is None:
            excluded.append(f"{qid} (no terminal decision row for this run)")
            continue
        variants = [str(v) for v in (q.get("answer_variants") or [])]
        fired = edges.get(qid, [])
        row = Row(qid=qid, gold=gold,
                  edges=[e["edge"] for e in fired],
                  sites=list(dict.fromkeys(s for e in fired
                                           for s in site_of_edge(e["edge"]))),
                  graded_edge=any(e["edge"].startswith("deliberate@") for e in fired),
                  instrument=str(drow.get("instrument") or ""),
                  dep=deployed_arm(drow))
        typed = dict(p.get("typed") or {})
        row.judge_correct = typed.get("correct") if "correct" in typed else None
        # the counterfactual arm: the grounded channel with every replace retired
        try:
            route = LK.route_question(root, question, client=client)
        except WouldSpendError:
            excluded.append(f"{qid} (route derivation cold — no-spend mode)")
            continue
        if route is None:
            excluded.append(f"{qid} (not routed as a lookup — the narrative family answers)")
            continue
        hits = RET.retrieve_set(conn, question, k)
        if not hits:
            excluded.append(f"{qid} (no hits at k={k})")
            continue
        keys = [str(h["artifact_cache_key"]) for h in hits]
        doc_date = PR.probe_recency(conn, root, keys)
        try:
            subject_state = (PR.probe_subject(conn, root, keys, profile=profile,
                                              client=client) if profile else {})
        except WouldSpendError:
            excluded.append(f"{qid} (an owner verdict is cold — no-spend mode)")
            continue
        cov = LK.HitCovariates(subject_state=subject_state, doc_date=doc_date)
        try:
            row.base = decide_arm(root, question, hits, cov,
                                  time_indexed=route.time_indexed, today=today,
                                  client=client, brain=brain)
        except WouldSpendError:
            excluded.append(f"{qid} (an extraction is cold — no-spend mode)")
            continue
        assert row.dep is not None
        row.loss = channel_loss(row.base, row.dep)
        row.outcome = classify(row.dep, row.base, gold, variants)
        row.side = conservative_side(row.dep, row.base)
        row.reach = action_differs(row.dep, row.base)
        row.collapse = s3_collapse(instrument=row.instrument, graded_edge=row.graded_edge,
                                   dep_n_obs=row.dep.n_obs,
                                   base_n_obs=row.base.n_obs if row.base else 0)
        row.matcher_correct = correct(row.dep, gold, variants)
        row.judge_flip = (row.judge_correct is not None
                          and bool(row.judge_correct) != row.matcher_correct)
        # criterion 9(a)'s direct control: with no edge fired the terminal IS the base channel
        row.no_edge_control = not fired
        row.control_agrees = row.no_edge_control and not row.reach
        rows.append(row)
    return rows, excluded


def site_tally(rows: list[Row], site: str) -> dict[str, int]:
    """Per-site counts. A row is attributed to every site in its ambiguity class — an
    `extract@<opus>` firing is counted under S1, S4 and S5 alike, and the overlap is stated
    rather than resolved by a guess."""
    hit = [r for r in rows if site in r.sites]
    reach = [r for r in hit if r.reach]
    return {"exposure": len(hit),
            "loss_rows": sum(1 for r in hit if r.loss > 0),
            "loss_total": sum(r.loss for r in hit),
            "reach": len(reach),
            "repairs": sum(1 for r in reach if r.outcome == "repair"),
            "regressions": sum(1 for r in reach if r.outcome == "regression"),
            "conservative": sum(1 for r in reach if r.side == "conservative"),
            "aggressive": sum(1 for r in reach if r.side == "aggressive")}


def render(rows: list[Row], excluded: list[str], run_id: str, k: int, today: date) -> str:
    o: list[str] = []
    o.append(f"# Replace-branch audit — {run_id} (k={k}, decay as of {today.isoformat()})\n")
    o.append(f"{len(rows)} question(s) read, {len(excluded)} excluded by name.\n")

    o.append("\n## Criterion 1-2 — the sites and their exposure\n")
    o.append("| site | what it is | exposure | rows with loss | obs discarded | reach |")
    o.append("|---|---|---|---|---|---|")
    tallies = {s: site_tally(rows, s) for s in SITES}
    for s, desc in SITES.items():
        t = tallies[s]
        exp = ("**not readable** from these records" if s in UNREADABLE_SITES
               else str(t["exposure"]))
        o.append(f"| {s} | {desc} | {exp} | {t['loss_rows']} | {t['loss_total']} "
                 f"| {t['reach']} |")
    o.append("")
    o.append(f"S2 emits no attributed edge event, so its exposure is UNMEASURED on this run "
             f"— not zero. The `{EX.extract_edge(EX._RE_EXTRACT_MODEL)}` spelling is shared "
             "by S1's opus tier, S4 and S5; rows carrying it are counted under all three and "
             "the overlap is stated, never resolved by a guess.")

    o.append("\n## Criterion 4-6 — delivered reach, the split, and which side it falls on\n")
    reach_rows = [r for r in rows if r.reach]
    split = Counter(r.outcome for r in reach_rows)
    sides = Counter(r.side for r in reach_rows)
    o.append(f"Delivered reach **{len(reach_rows)}** of {len(rows)} — repairs "
             f"**{split['repair']}**, regressions **{split['regression']}**, neutral "
             f"{split['unchanged']}, ungradeable {split['ungradeable']}.")
    o.append(f"Deployed rule conservative on {sides['conservative']}, aggressive on "
             f"{sides['aggressive']}.\n")
    if reach_rows:
        o.append("| question | sites | loss | deployed | counterfactual | outcome | side |")
        o.append("|---|---|---|---|---|---|---|")
        for r in sorted(reach_rows, key=lambda r: r.qid):
            d, b = r.dep, r.base
            o.append(f"| {r.qid} | {','.join(r.sites) or '—'} | {r.loss} "
                     f"| {d.action if d else '—'} n_obs={d.n_obs if d else 0} "
                     f"| {b.action if b else '—'} n_obs={b.n_obs if b else 0} "
                     f"| {r.outcome} | {r.side} |")
        o.append("")

    o.append("\n## Criterion 7 — the S1/S4-vs-S3 asymmetry\n")
    collapses = [r for r in rows if r.collapse]
    o.append(f"S3 collapse signature on **{len(collapses)}** question(s) "
             f"({', '.join(r.qid for r in collapses) or 'none'}) — the deliberate branch "
             "fired, left no gradeable row, and the committed posterior holds no observation "
             "over a grounded channel that did.")
    if not collapses:
        o.append("Zero here means the asymmetry is STRUCTURAL-ONLY on this corpus: the guard "
                 "S3 lacks was never the guard that would have fired. It does not mean S3 is "
                 "safe — see the reach table above.")

    o.append("\n## Criterion 9(a) — the layer bound, as a direct control\n")
    ctrl = [r for r in rows if r.no_edge_control]
    agree = sum(1 for r in ctrl if r.control_agrees)
    rate = f"{agree}/{len(ctrl)}" if ctrl else "no control rows"
    o.append(f"On {len(ctrl)} question(s) NO edge fired, so the terminal IS the base channel "
             f"and the audit's counterfactual should reproduce it: **{rate}** agree.")
    dis = [r.qid for r in ctrl if not r.control_agrees]
    if dis:
        o.append(f"Disagreeing control rows (named, never averaged away): {', '.join(dis)}.")
    flips = [r.qid for r in rows if r.judge_flip]
    o.append(f"\nMatcher-vs-judge flips on the DEPLOYED arm: {len(flips)}"
             + (f" — {', '.join(flips)}." if flips else "."))

    o.append("\n## Criterion 8 — the verdict, per site\n")
    o.append("| site | verdict | why |")
    o.append("|---|---|---|")
    for s in SITES:
        t = tallies[s]
        if s in UNREADABLE_SITES:
            o.append(f"| {s} | NOT READ | emits no attributed edge event; exposure is "
                     "unmeasured on this run, and a live bridge replay is the escalation |")
            continue
        v, why = verdict(exposure=t["exposure"], reach=t["reach"],
                         repairs=t["repairs"], regressions=t["regressions"])
        o.append(f"| {s} | **{v}** | {why} |")

    o.append("\n## Excluded, by name (criterion 9c)\n")
    for e in excluded:
        o.append(f"- {e}")
    if not excluded:
        o.append("- none")
    o.append("\n*Not read here (criterion 9b): the JOIN counterfactual — pooling the base and "
             "probe observations under §5's dedup. The probe's observations are not in these "
             "records; reading them needs a live bridge replay, which is the escalation.*")
    return "\n".join(o) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--paired", required=True, type=Path)
    ap.add_argument("--decisions", required=True, type=Path)
    ap.add_argument("--outcomes", required=True, type=Path)
    ap.add_argument("--questions", type=Path, default=None)
    ap.add_argument("--k", type=int, default=20)
    ap.add_argument("--only", default=None, help="comma-separated question ids")
    ap.add_argument("--today", default=None, help="ISO date; default = the run's own date")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--out-yaml", type=Path, default=None)
    args = ap.parse_args(argv)

    questions = load_questions(args.questions) if args.questions else load_questions()
    paired = load_paired(args.paired)
    if args.only:
        want = {s.strip() for s in args.only.split(",") if s.strip()}
        paired = {q: v for q, v in paired.items() if q in want}
    root = LCFG.pkm_root()
    if root is None:
        print("REFUSED: no pkm root (PKM_CONFIG unresolvable)")
        return 2
    today = date.fromisoformat(args.today) if args.today else run_date(args.run_id)

    import anthropic
    import duckdb
    client = RefusingClient(engine_version=str(anthropic.__version__))
    conn = duckdb.connect(str(root / "catalogue.duckdb"), read_only=True)
    brain = LK.shared_brain()
    try:
        rows, excluded = audit_rows(
            paired, questions, load_decisions(args.decisions, args.run_id),
            load_edges(args.outcomes, args.run_id), conn, root, k=args.k, today=today,
            client=client, brain=brain, profile=owner.load_profile())
    finally:
        conn.close()
    report = render(rows, excluded, args.run_id, args.k, today)
    print(report)
    if args.out:
        args.out.write_text(report, encoding="utf-8")
    if args.out_yaml:
        import yaml
        args.out_yaml.write_text(yaml.safe_dump(
            {"run_id": args.run_id, "k": args.k, "today": today.isoformat(),
             "excluded": excluded,
             "sites": {s: site_tally(rows, s) for s in SITES},
             "rows": [{**{f: v for f, v in r.__dict__.items() if f not in ("base", "dep")},
                       "base": r.base.__dict__ if r.base else None,
                       "dep": r.dep.__dict__ if r.dep else None}
                      for r in rows]},
            sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
