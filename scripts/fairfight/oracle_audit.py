#!/usr/bin/env python3
"""``scripts/fairfight/oracle_audit.py`` — the oracle-vs-gold validation audit (roadmap A1).

Before the oracle arm's answers may referee anything, the oracle itself is validated
against the existing owner-authored gold: this script reads one fair-fight run's
``arms/<arm>/{vectors,answers}.jsonl``, measures agreement, and writes the disagreement
list the owner adjudicates **by exception, one bit per row** — the whole point of the
gold-standard roadmap is that these rows are the ONLY per-answer attention the owner
spends. It never edits ``questions.yaml`` (owner-authored, out of bounds); the report is
evidence, the adjudication is his.

Reading, not re-grading: agreement comes verbatim from the vectors' triage buckets
(``CORRECT``/``CONFIDENT_WRONG``/... — ``grading.grade_channels`` already graded the run;
this script never re-derives a verdict). The mapping to audit classes:

- ``CORRECT`` / ``RIGHTLY_WITHHELD``  -> **agree** (oracle matches gold / correctly
  declines an unanswerable question).
- ``CONFIDENT_WRONG``                 -> **disagree_value**: the oracle asserted a value
  token-mismatching the gold. THE adjudication case — exactly one of {oracle, gold,
  both} is wrong, and q-005's dissolved "gold conflict" (bank schedule vs insurance
  echo) shows either answer is live.
- ``WRONGLY_WITHHELD``                -> **oracle_miss**: the oracle declined though the
  question is answerable — evidence about the oracle's retrieval reach (or an
  unfindable gold), not a gold dispute.
- ``SCOPED``                          -> **scoped**: listed for visibility, adjudicated
  only if the owner cares about the scope.

Output: ``<run-dir>/audit/<arm>_vs_gold.{json,md}`` — the md carries one adjudication
checklist per disagreement (``[ ] oracle_right  [ ] gold_right  [ ] both_wrong``); the
owner ticks ONE box per row (his free text stays the loop's most expensive resource).
Corpus content stays inside the run dir under ``$LIFE_AGENT_KB`` — nothing here is
repo-committed output.

Usage::

    uv run --project . python scripts/fairfight/oracle_audit.py \\
        --run-dir "$LIFE_AGENT_KB/eval/fairfight/<run_id>" [--arm oracle]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from run_eval import load_questions

from life_agent.fairfight import records as REC

# bucket -> audit class (see module docstring). Unknown buckets map to "other" and are
# listed, never silently dropped.
_AUDIT_CLASS: dict[str, str] = {
    "CORRECT": "agree",
    "RIGHTLY_WITHHELD": "agree",
    "CONFIDENT_WRONG": "disagree_value",
    "WRONGLY_WITHHELD": "oracle_miss",
    "SCOPED": "scoped",
}

# The classes listed in the disagreement queue. Only _CHECKLIST classes get the three-way
# adjudication tick — a SCOPED answer is "an honest non-answer... never the sin"
# (triage_grading's own vocabulary), not a factual dispute, so it gets a lighter callout
# instead of pulling an owner bit that doesn't apply.
_ADJUDICATE = ("disagree_value", "oracle_miss", "scoped", "other")
_CHECKLIST = ("disagree_value", "oracle_miss", "other")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def audit_class(bucket: str) -> str:
    return _AUDIT_CLASS.get(bucket, "other")


def build_audit(
    vectors: list[dict[str, Any]],
    answers: list[dict[str, Any]],
    questions: list[dict[str, Any]],
    *, arm: str, run_id: str, arm_config: dict[str, Any] | None,
) -> dict[str, Any]:
    """The audit as one JSON-ready dict. Pure — no I/O, fully testable."""
    q_by_id = {str(q["id"]): q for q in questions}
    text_by_id = {str(a["question_id"]): a.get("text", "") for a in answers}

    scored = REC.scored(vectors)  # the ONE canonical scored-population filter
    excluded = [v for v in vectors if v.get("status") != "ok"]

    rows: list[dict[str, Any]] = []
    for v in scored:
        qid = str(v["question_id"])
        q = q_by_id.get(qid, {})
        rows.append({
            "question_id": qid,
            "in_gold": qid in q_by_id,
            "question": q.get("question", "(question not in the gold file)"),
            "gold": q.get("answer", ""),
            "oracle_text": text_by_id.get(qid, ""),
            "bucket": v.get("bucket", ""),
            "cause": v.get("cause"),
            "audit_class": audit_class(str(v.get("bucket", ""))),
            "answerable": bool(v.get("answerable")),
            "cost_usd": v.get("cost_usd"),
            "latency_s": v.get("latency_s"),
            "tool_calls": v.get("tool_calls"),
        })

    n = len(rows)
    n_agree = sum(1 for r in rows if r["audit_class"] == "agree")
    by_class: dict[str, int] = {}
    for r in rows:
        by_class[r["audit_class"]] = by_class.get(r["audit_class"], 0) + 1
    answerable = [r for r in rows if r["answerable"]]
    n_answerable_agree = sum(1 for r in answerable if r["audit_class"] == "agree")
    costs = [r["cost_usd"] for r in rows if r["cost_usd"] is not None]

    return {
        "run_id": run_id,
        "arm": arm,
        "arm_config": arm_config,
        "n_scored": n,
        "n_excluded_infra": len(excluded),
        "excluded_question_ids": [str(v.get("question_id")) for v in excluded],
        "agreement_rate": (n_agree / n) if n else None,
        "answerable_agreement_rate": (
            (n_answerable_agree / len(answerable)) if answerable else None),
        "by_class": by_class,
        "total_cost_usd": sum(costs) if costs else None,
        "disagreements": [r for r in rows if r["audit_class"] in _ADJUDICATE],
        "rows": rows,
    }


def render_md(audit: dict[str, Any]) -> str:
    cfg = audit.get("arm_config") or {}
    lines = [
        f"# Oracle-vs-gold audit — {audit['arm']} @ {audit['run_id']}",
        "",
        "The oracle arm's answers, graded against the owner-authored gold by the run's own "
        "triage buckets. Disagreements below are the owner's adjudication queue — **one "
        "tick per row**, nothing else. Until they are adjudicated, the oracle referees "
        "nothing.",
        "",
        f"- model: {cfg.get('model', '?')}  ·  scored: {audit['n_scored']}  ·  "
        f"infra-excluded: {audit['n_excluded_infra']} "
        f"{audit['excluded_question_ids'] or ''}".rstrip(),
        f"- agreement: {_pct(audit['agreement_rate'])} overall, "
        f"{_pct(audit['answerable_agreement_rate'])} on answerable",
        f"- classes: {json.dumps(audit['by_class'], sort_keys=True)}",
        f"- total cost: {_usd(audit['total_cost_usd'])}",
        "",
        "## Disagreements (the adjudication queue)",
    ]
    if audit["n_scored"] == 0:
        lines += ["", "**Nothing was scored (n=0)** — no evaluation happened; this is "
                       "NOT a clean bill of health."]
    elif not audit["disagreements"]:
        lines += ["", "None — the oracle agrees with the gold everywhere it was scored."]
    for r in audit["disagreements"]:
        gold_display = r["gold"] or (
            "(none — marked unanswerable)" if r["in_gold"] else "(not in the gold file)")
        lines += [
            "",
            f"### {r['question_id']} — {r['audit_class']} ({r['bucket']}"
            + (f" / {r['cause']}" if r["cause"] else "") + ")",
            "",
            f"**Q:** {r['question']}",
            f"**gold:** {gold_display}",
            f"**oracle said:** {r['oracle_text'] or '(empty)'}",
        ]
        if r["audit_class"] in _CHECKLIST:
            lines += ["", "adjudicate: `[ ] oracle_right   [ ] gold_right   [ ] both_wrong`"]
        else:
            lines += ["", "_scoped — no adjudication required; flag only if the scope "
                          "itself is wrong._"]
    lines += [
        "",
        "## All scored rows",
        "",
        "| question | class | bucket | cost | tool calls |",
        "| --- | --- | --- | ---: | ---: |",
    ]
    for r in audit["rows"]:
        lines.append(
            f"| {r['question_id']} | {r['audit_class']} | {r['bucket']} | "
            f"{_usd(r['cost_usd'])} | {r['tool_calls'] if r['tool_calls'] is not None else '—'} |")
    return "\n".join(lines) + "\n"


def _pct(x: float | None) -> str:
    return f"{100 * x:.0f}%" if x is not None else "—"


def _usd(x: float | None) -> str:
    return f"${x:.2f}" if x is not None else "—"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, help="the fair-fight run directory")
    parser.add_argument("--arm", default="oracle")
    args = parser.parse_args(argv)

    run_dir = Path(args.run_dir).expanduser()
    arm_dir = run_dir / "arms" / args.arm
    vectors = _read_jsonl(arm_dir / "vectors.jsonl")
    answers = _read_jsonl(arm_dir / "answers.jsonl")
    try:
        meta = json.loads((run_dir / "run_meta.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        # fail-open, same as arm_hermes's usage-file read: a missing OR truncated/corrupt
        # run_meta.json (run_fairfight's _write_json is not atomic — an interrupted run
        # is exactly what a post-hoc audit tool meets) costs the header fields, never
        # the audit.
        meta = {}
    audit = build_audit(
        vectors, answers, load_questions(), arm=args.arm,
        run_id=meta.get("run_id", run_dir.name),
        arm_config=(meta.get("arm_configs") or {}).get(args.arm),
    )

    out_dir = run_dir / "audit"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{args.arm}_vs_gold.json").write_text(
        json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path = out_dir / f"{args.arm}_vs_gold.md"
    md_path.write_text(render_md(audit), encoding="utf-8")
    print(md_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
