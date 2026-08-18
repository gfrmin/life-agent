#!/usr/bin/env python3
"""Corroborate audit — the measured off-gate reading behind `confirm_indep` (§14, the
post-adoption lever decided by the reach audit: independent-document corroboration,
buildable ceiling 40/69).

Over the audited gate run's withheld questions, this drives the PRODUCTION
`/probe/confirm` handler (`bridge.server._probe_confirm` — the same function run 10
will enact: supporter exclusion, prefilter, the cached haiku confirm instrument, the
grounding gate, the §5 correlated-copy guard) and measures, per question:

  rescue        the leader gate-matches gold AND ≥1 independent grounded confirm
  wrong-rescue  the leader does NOT match gold AND ≥1 independent grounded confirm —
                the headline safety number
  no-confirm    a leader exists but no confirm survived (decline/ungrounded/correlated)
  no-leader     no decision row or an empty candidate lattice (the n_obs=0 cluster) —
                NAMED EXCLUDED: the confirm probe structurally cannot help these, so
                the effective ceiling this audit reports is already net of them

FROZEN READING CRITERIA (stated here, before any result is read):
- Wire the probe iff (a) ZERO wrong-rescues whose predicted posterior flips to report
  at the commit bar, and (b) predicted correct rescues (flips on gold-matching
  leaders) >= 5.
- m (the per-question chunk budget) = the smallest of {1,2,3} whose predicted correct
  rescues >= 0.9 x m=3's.
- The tier stays haiku; if ANY wrong-confirm (a grounded confirm on a non-gold leader,
  flip or not) appears, a sonnet re-check is a NEW pre-registered sweep, never a
  silent retry.
- No-go => stop, register the negative reading in §14.

Prediction mode (disclosed, the temper_audit precedent — no daemon replay off-gate):
each kept confirm appends one independent witness to the recorded leader credence by
an analytic odds update, LR = (r + (1-r)/A) / ((1-r)/A) at r = rho_base * authority *
subject * time * competition, scaled by the daemon's cross-group temper exponent
s = (1 + beta_model*(G-1))/G (beta_model 0.7, G counting the appended group). The
recorded base credence is NOT down-weighted as the daemon would when G grows, so p'
is modestly OPTIMISTIC — conservative for the wrong-rescue safety check (an optimistic
p' over-predicts wrong flips), optimistic for the rescue count (run 10 is the test).

Blindness disclosure: the sweep sees the golds (the router-v2/temper precedent); the
confirm calls are LIVE haiku and warm the §18.9 cache run 10 will replay (the run-9
warm-deliberate precedent, disclosed in the registration). Base-channel replays are
content-addressed cache hits — the report names any base-replay spend > $0.

Usage:
  uv run python scripts/corroborate_audit.py --run-id gate-20260817T195737 \
      --paired $KB/eval/gate-outside-option/paired-gate-20260817T195737.jsonl \
      --questions $KB/eval/questions_v2.yaml \
      [--out FILE.md] [--out-yaml FILE.yaml] [--synth-dir DIR]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gate_splice import load_paired
from run_eval import load_questions
from temper_audit import COMMIT_BAR, load_decisions

import life_agent.core.lookup as LK
import life_agent.core.matching as MATCH
from life_agent.bridge import server as BS
from life_agent.core import config as LCFG
from life_agent.core.decisions import question_id as _qhash

_WITHHELD = ("abstain", "ask_clarify", "miss")
_A = 10.0            # the channel's a_alternatives (lookup._A_ALTERNATIVES)
_BETA_MODEL = 0.7    # the daemon's cross-group temper (CANONICAL_CHANNEL)
_MS = (1, 2, 3)      # the m sweep grid (largest runs first: cold calls once, rest warm)


def predicted_p(leader_p: float, confirm_obs: list[dict[str, Any]],
                n_base_groups: int, rho_base: float) -> float:
    """Analytic append (module docstring): fold each kept confirm into the recorded
    leader credence as one cross-group-tempered independent witness. Pure."""
    p = min(max(leader_p, 1e-9), 1.0 - 1e-9)
    odds = p / (1.0 - p)
    groups_seen = max(n_base_groups, 1)
    seen_new: set[int] = set()
    for o in confirm_obs:
        g = int(o.get("group", -1))
        if g >= n_base_groups and g not in seen_new:
            seen_new.add(g)
            groups_seen += 1
        r = (rho_base * float(o.get("authority", 1.0))
             * float(o.get("subject_factor", 1.0)) * float(o.get("time_factor", 1.0))
             * float(o.get("competition_factor", 1.0)))
        r = min(max(r, 0.0), 1.0 - 1e-9)
        lr = (r + (1.0 - r) / _A) / ((1.0 - r) / _A)
        s = (1.0 + _BETA_MODEL * (groups_seen - 1)) / groups_seen
        odds *= lr ** s
    return odds / (1.0 + odds)


@dataclass
class Row:
    qid: str
    action: str
    leader: str
    leader_p: float
    gold_match: bool | None       # None = no leader
    klass: str                    # rescue | wrong-rescue | no-confirm | no-leader
    n_prefilter: int = 0
    n_base_groups: int = 0
    cost_usd: float = 0.0
    per_m: dict[int, dict[str, Any]] = field(default_factory=dict)
    #        m -> {n_kept, n_grounded, n_correlated_dropped, p_prime, flips}

    def flips(self, m: int) -> bool:
        return bool(self.per_m.get(m, {}).get("flips"))


def audit_rows(paired: dict[str, dict], decisions: dict[str, dict],
               questions: list[dict], probe: Any, *,
               rho_base: float) -> list[Row]:
    """One Row per withheld question. ``probe(question, value, candidates)`` returns
    the per-m replies ``{m: reply}`` — injected so tests stay hermetic (the real one
    drives ``bridge.server._probe_confirm``)."""
    by_id = {str(q["id"]): q for q in questions}
    rows: list[Row] = []
    for qid, p in sorted(paired.items()):
        typed = p.get("typed") or {}
        if typed.get("action") not in _WITHHELD:
            continue
        q = by_id.get(qid)
        if q is None:
            continue
        gold = str(q.get("answer") or "")
        variants = [str(v) for v in (q.get("answer_variants") or [])]
        if not gold:
            continue
        dec = decisions.get(_qhash(str(q["question"])))
        ps = (dec or {}).get("posterior_summary") or {}
        cands = [str(c) for c in (ps.get("candidates") or [])]
        creds = [float(c) for c in (ps.get("credences") or [])]
        if not cands:
            rows.append(Row(qid=qid, action=str(typed.get("action")), leader="",
                            leader_p=0.0, gold_match=None, klass="no-leader"))
            continue
        leader, leader_p = cands[0], (creds[0] if creds else 0.0)
        match = MATCH.answer_matches(gold, variants, leader)
        replies = probe(str(q["question"]), leader, cands)
        r3 = replies[max(_MS)]
        per_m: dict[int, dict[str, Any]] = {}
        any_kept = False
        for m in _MS:
            rep = replies[m]
            kept = list(rep.get("observations") or [])
            any_kept = any_kept or bool(kept)
            pp = predicted_p(leader_p, kept, int(rep.get("n_base_groups") or 0),
                             rho_base)
            per_m[m] = {"n_kept": len(kept),
                        "n_grounded": int(rep.get("n_grounded") or 0),
                        "n_correlated_dropped": int(
                            rep.get("n_correlated_dropped") or 0),
                        "p_prime": pp, "flips": bool(kept) and pp >= COMMIT_BAR}
        klass = (("rescue" if match else "wrong-rescue") if any_kept else "no-confirm")
        rows.append(Row(
            qid=qid, action=str(typed.get("action")), leader=leader,
            leader_p=leader_p, gold_match=match, klass=klass,
            n_prefilter=int(r3.get("n_prefilter") or 0),
            n_base_groups=int(r3.get("n_base_groups") or 0),
            cost_usd=sum(float(replies[m].get("cost_usd") or 0.0) for m in _MS),
            per_m=per_m))
    return rows


def verdict(rows: list[Row]) -> dict[str, Any]:
    """The frozen criteria applied mechanically (module docstring — never re-judged)."""
    wrong_flip = {m: sorted(r.qid for r in rows
                            if r.klass == "wrong-rescue" and r.flips(m)) for m in _MS}
    rescues = {m: sorted(r.qid for r in rows if r.klass == "rescue" and r.flips(m))
               for m in _MS}
    wrong_confirms = sorted(r.qid for r in rows if r.klass == "wrong-rescue")
    best = len(rescues[max(_MS)])
    frozen_m = next((m for m in _MS if len(rescues[m]) >= 0.9 * best), max(_MS))
    go = not wrong_flip[frozen_m] and len(rescues[frozen_m]) >= 5
    return {"rescue_flips": rescues, "wrong_rescue_flips": wrong_flip,
            "wrong_confirms": wrong_confirms, "frozen_m": frozen_m, "go": go}


def render(rows: list[Row], v: dict[str, Any], run_id: str) -> str:
    by_class = Counter(r.klass for r in rows)
    spend = sum(r.cost_usd for r in rows)
    out = [f"# Corroborate audit — {run_id} (confirm_indep, live haiku, "
           f"${spend:.2f})", "",
           f"Withheld questions audited: {len(rows)}; classes: "
           + " · ".join(f"{k} {by_class.get(k, 0)}"
                        for k in ("rescue", "wrong-rescue", "no-confirm",
                                  "no-leader")), "",
           "## Verdict (frozen criteria in the module docstring)", "",
           f"- wrong-confirms (any grounded confirm on a non-gold leader): "
           f"{v['wrong_confirms'] or '—'}"]
    for m in _MS:
        out.append(f"- m={m}: predicted rescues {len(v['rescue_flips'][m])} "
                   f"{v['rescue_flips'][m]}; wrong-rescue flips "
                   f"{len(v['wrong_rescue_flips'][m])} {v['wrong_rescue_flips'][m]}")
    out += [f"- frozen m = {v['frozen_m']}; **{'GO' if v['go'] else 'NO-GO'}**", "",
            "## Per-question", "",
            "| qid | action | leader | p | gold | class | pre | grpB | "
            + " | ".join(f"kept@{m}" for m in _MS) + " | "
            + " | ".join(f"p'@{m}" for m in _MS) + " |",
            "|" + "---|" * (8 + 2 * len(_MS))]
    order = {"wrong-rescue": 0, "rescue": 1, "no-confirm": 2, "no-leader": 3}
    for r in sorted(rows, key=lambda r: (order[r.klass], r.qid)):
        g = {True: "✓", False: "✗", None: "·"}[r.gold_match]
        kept = " | ".join(str(r.per_m.get(m, {}).get("n_kept", 0)) for m in _MS)
        pps = " | ".join(
            f"{r.per_m[m]['p_prime']:.3f}" + ("←flip" if r.flips(m) else "")
            if m in r.per_m else "—" for m in _MS)
        out.append(f"| {r.qid} | {r.action} | {r.leader[:24]} | {r.leader_p:.3f} "
                   f"| {g} | {r.klass} | {r.n_prefilter} | {r.n_base_groups} "
                   f"| {kept} | {pps} |")
    return "\n".join(out) + "\n"


def synth_paired(paired: dict[str, dict], rows: list[Row], m: int,
                 out_dir: Path) -> Path:
    """The counterfactual input for gate_splice: every predicted flip rewritten to a
    typed report graded by the audit's gold match, its confirm spend added. (A
    wrong-rescue flip would grade ✗ — the frozen criteria refuse the wiring before
    any such synth is read as a floor.)"""
    flips = {r.qid: r for r in rows if r.flips(m)}
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"paired-confirm-m{m}.jsonl"
    with out.open("w", encoding="utf-8") as fh:
        for qid in sorted(paired):
            row = json.loads(json.dumps(paired[qid]))  # deep copy
            r = flips.get(qid)
            if r is not None:
                t = row["typed"]
                t.update({"action": "report", "correct": bool(r.gold_match),
                          "withheld": None,
                          "cost_usd": float(t.get("cost_usd") or 0.0) + r.cost_usd})
            fh.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--paired", required=True, type=Path)
    ap.add_argument("--questions", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--out-yaml", type=Path, default=None)
    ap.add_argument("--synth-dir", type=Path, default=None)
    args = ap.parse_args(argv)

    questions = load_questions(args.questions) if args.questions else load_questions()
    paired = load_paired(args.paired)
    decisions = load_decisions(args.run_id)
    root = LCFG.pkm_root()
    if root is None:
        print("REFUSED: no pkm root (PKM_CONFIG unresolvable)")
        return 2
    import duckdb
    conn = duckdb.connect(str(root / "catalogue.duckdb"), read_only=True)
    scratch = Path(LCFG.KB) / "tmp" / "corroborate-audit"
    scratch.mkdir(parents=True, exist_ok=True)
    deps = BS.BridgeDeps(
        root=root, conn=conn, client=LK._client(),
        profile="", u_bar=lambda: {},
        decisions_path=scratch / "decisions.jsonl",
        reactions_path=scratch / "reactions.jsonl",
        fold_version=lambda: "corroborate-audit",
        gather_outcomes_path=scratch / "gather_outcomes.jsonl")

    def probe(question: str, value: str, candidates: list[str]) -> dict[int, dict]:
        import life_agent.core.retrieval as RET
        hits = RET.retrieve_set(conn, RET.build_query(question, ""), 20)
        payload = {"question": question, "value": value, "candidates": candidates,
                   "hits": hits}
        # largest m first: its cold calls warm the cache; the smaller m's replay free
        return {m: BS._probe_confirm(deps, {**payload, "m": m})
                for m in sorted(_MS, reverse=True)}

    try:
        rows = audit_rows(paired, decisions, questions, probe,
                          rho_base=LK.extractor_reliability_mean())
    finally:
        conn.close()
    v = verdict(rows)
    report = render(rows, v, args.run_id)
    print(report)
    if args.out:
        args.out.write_text(report, encoding="utf-8")
    if args.out_yaml:
        import yaml
        args.out_yaml.write_text(yaml.safe_dump(
            {"run_id": args.run_id, "verdict": {
                "go": v["go"], "frozen_m": v["frozen_m"],
                "wrong_confirms": v["wrong_confirms"],
                "rescue_flips": {m: v["rescue_flips"][m] for m in _MS},
                "wrong_rescue_flips": {m: v["wrong_rescue_flips"][m] for m in _MS}},
             "rows": [{**r.__dict__, "per_m": {str(m): d for m, d in r.per_m.items()}}
                      for r in rows]},
            sort_keys=True), encoding="utf-8")
    if args.synth_dir:
        for m in _MS:
            print(f"synth: {synth_paired(paired, rows, m, args.synth_dir)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
