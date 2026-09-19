#!/usr/bin/env python3
"""Extraction audit — why the n_obs=0 questions lost a gold-bearing chunk they had.

The reach audit (2026-08-17) retired "retrieval failure" as a name: all 19 of run 9's
n_obs=0 withholdings already had a gold-bearing chunk INSIDE the deterministic top-k.
The loss is extraction/observation-side. This audit reads the §18.9 extraction cache the
audited run itself wrote — zero model calls, zero new retrieval decisions — and puts
every (question, gold-bearing chunk) pair into exactly one class:

  declined          the instrument replied found:false on a chunk that carries the gold
  picked-other      found:true, but on a DIFFERENT value than the gold — the
                    one-value-per-chunk EXTRACT_SCHEMA spent its single slot elsewhere
  ungrounded        found:true on the gold, but the consumer-side grounding gate
                    (quote/value verbatim in chunk) refused it
  grounded          an anomaly here by construction (n_obs=0 says nothing grounded) —
                    NAMED, never silently dropped: it means the audited run's hit set
                    and this replay diverged
  no-cache-record   no cached extraction for this (question, chunk): the audited run
                    never read this chunk — a replay divergence, not an extractor defect

Each class implies a different lever: `declined` → the extract prompt/instrument;
`picked-other` → the one-value schema (a multi-value or value-targeted read);
`ungrounded` → the grounding gate, which is CONSUMER-SIDE and therefore re-gates every
cached record for free (the cheapest possible fix if the class is large).

FROZEN READING CRITERIA (stated before any result is read):

1. The build bar is DELIVERED REACH, not fixable chunks. The confirm_indep audit
   (2026-08-18) was refused after its predicted ceiling of 40 turned out to count
   forwarded copies of one attestation; the lesson is registered here as a rule: a
   lever's ceiling is the number of QUESTIONS whose committed answer would change,
   never the number of artifacts, chunks, or observations it touches.
2. A rescued extraction yields a candidate, not necessarily a commit. This audit
   measures the audited run's OWN empirical single-observation credence (the median
   recorded leader credence over its decision rows with n_obs == 1 and one candidate)
   and compares it to the commit bar. If that median is BELOW the bar, a question
   counts toward delivered reach only when its fixable chunks span >= 2 INDEPENDENT
   artifacts (one document cannot clear the bar alone in this run's own channel); if
   it is at or above the bar, one fixable artifact suffices. The comparison is made
   from the run's data, so the rule cannot be tuned after the fact.
3. Build a lever iff its delivered reach is >= 10 questions (the reach audit's
   standing "not worth building ahead of live dogfood evidence" line, unchanged).
   A class that is large but whose delivered reach is under the bar is reported as
   DIAGNOSIS ONLY and explicitly not a build.
4. Every excluded or unrecoverable row is named in the report (the no-silent-caps rule).

Usage:
  uv run python scripts/extraction_audit.py --run-id gate-20260817T195737 \
      --paired $KB/eval/gate-outside-option/paired-gate-20260817T195737.jsonl \
      --questions $KB/eval/questions_v2.yaml [--k 20] [--out F.md] [--out-yaml F.yaml]
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gate_splice import load_paired
from run_eval import load_questions
from temper_audit import COMMIT_BAR, load_decisions

import life_agent.core.derivations as D
import life_agent.core.lookup as LK
import life_agent.core.matching as MATCH
import life_agent.core.retrieval as RET
from life_agent.core import config as LCFG
from life_agent.core.decisions import question_id as _qhash

_WITHHELD = ("abstain", "ask_clarify", "miss")
CLASSES = ("declined", "picked-other", "ungrounded", "grounded", "no-cache-record")


def classify_chunk(record: dict[str, Any] | None, gold: str, variants: list[str],
                   chunk: str) -> tuple[str, str]:
    """One (question, gold-bearing chunk) pair → (class, the value the run extracted).
    Pure; mirrors observe_hits' own consumer-side gates (`_grounded`, the candidate
    canon) so a class here means exactly what it meant in the audited run."""
    if record is None:
        return ("no-cache-record", "")
    value = str(record.get("value") or "")
    quote = str(record.get("quote") or "")
    if not record.get("found"):
        return ("declined", "")
    is_gold = (LK._candidate_key(value) == LK._candidate_key(gold)
               or MATCH.answer_matches(gold, variants, value))
    if not is_gold:
        return ("picked-other", value)
    if not LK._grounded(quote, value, chunk):
        return ("ungrounded", value)
    return ("grounded", value)


@dataclass
class Row:
    qid: str
    action: str
    gold: str
    n_gold_chunks: int = 0
    n_gold_artifacts: int = 0
    counts: dict[str, int] = field(default_factory=dict)
    # artifacts carrying a chunk that a fix in each class would rescue
    artifacts_by_class: dict[str, list[str]] = field(default_factory=dict)
    picked: list[str] = field(default_factory=list)
    competed: int = 0          # gold chunks whose gold has a same-shape rival in-chunk

    def fixable_artifacts(self, classes: tuple[str, ...]) -> set[str]:
        out: set[str] = set()
        for c in classes:
            out.update(self.artifacts_by_class.get(c, ()))
        return out


def single_obs_credence(decisions: dict[str, dict]) -> tuple[float | None, int]:
    """The audited run's OWN answer to "what does one clean observation buy?" — the
    median recorded leader credence over decision rows with exactly one observation and
    one candidate. Criterion 2 reads this, so the delivered-reach rule is set by the
    run's data rather than by a number chosen here."""
    ps = [d.get("posterior_summary") or {} for d in decisions.values()]
    creds = [float((p.get("credences") or [0.0])[0]) for p in ps
             if int(p.get("n_obs") or 0) == 1 and len(p.get("candidates") or []) == 1
             and (p.get("credences") or [])]
    return (statistics.median(creds) if creds else None), len(creds)


def audit_rows(paired: dict[str, dict], decisions: dict[str, dict],
               questions: list[dict], conn: Any, root: Path, engine_version: str, *,
               k: int = 20) -> tuple[list[Row], list[str]]:
    """One Row per n_obs=0 withheld question (the reach audit's miss set: a decision row
    with n_obs == 0, or no decision row at all). Returns (rows, named exclusions)."""
    by_id = {str(q["id"]): q for q in questions}
    rows: list[Row] = []
    excluded: list[str] = []
    for qid, p in sorted(paired.items()):
        typed = p.get("typed") or {}
        if typed.get("action") not in _WITHHELD:
            continue
        q = by_id.get(qid)
        if q is None:
            excluded.append(f"{qid} (not in questions file)")
            continue
        gold = str(q.get("answer") or "")
        variants = [str(v) for v in (q.get("answer_variants") or [])]
        if not gold:
            excluded.append(f"{qid} (unanswerable by construction — no gold)")
            continue
        dec = decisions.get(_qhash(str(q["question"])))
        n_obs = int((dec or {}).get("posterior_summary", {}).get("n_obs") or 0)
        if dec is not None and n_obs != 0:
            continue                                   # not the miss set
        row = Row(qid=qid, action=str(typed.get("action")), gold=gold)
        for hit in RET.retrieve_set(conn, RET.build_query(str(q["question"]), ""), k):
            chunk = str(hit["chunk_text"])
            if not MATCH.answer_matches(gold, variants, chunk):
                continue
            row.n_gold_chunks += 1
            artifact = str(hit["artifact_cache_key"])
            key = D.lookup_extract_key(str(q["question"]), LK._sha(chunk),
                                       model=LK.LOOKUP_MODEL,
                                       prompt_template=LK.EXTRACT_PROMPT,
                                       engine_version=engine_version,
                                       output_schema=LK.EXTRACT_SCHEMA)
            cached = D.lookup(root, key.cache_key)
            record = json.loads(cached.decode("utf-8")) if cached is not None else None
            klass, value = classify_chunk(record, gold, variants, chunk)
            row.counts[klass] = row.counts.get(klass, 0) + 1
            row.artifacts_by_class.setdefault(klass, [])
            if artifact not in row.artifacts_by_class[klass]:
                row.artifacts_by_class[klass].append(artifact)
            if value and klass == "picked-other":
                row.picked.append(value)
            if MATCH.competing_value_count(gold, chunk) > 0:
                row.competed += 1
        row.n_gold_artifacts = len({a for arts in row.artifacts_by_class.values()
                                    for a in arts})
        rows.append(row)
    return rows, excluded


# The classes a per-chunk extraction fix could plausibly convert (a no-cache-record is a
# replay divergence, and a `grounded` row contradicts n_obs=0 — neither is a lever).
_FIXABLE = ("declined", "picked-other", "ungrounded")


def delivered_reach(rows: list[Row], classes: tuple[str, ...],
                    artifacts_needed: int) -> list[str]:
    """Criterion 1+2: the QUESTIONS a fix in ``classes`` would carry to a commit."""
    return sorted(r.qid for r in rows
                  if len(r.fixable_artifacts(classes)) >= artifacts_needed)


def render(rows: list[Row], excluded: list[str], run_id: str, k: int,
           median_p: float | None, n_single: int, artifacts_needed: int) -> str:
    totals: Counter[str] = Counter()
    for r in rows:
        totals.update(r.counts)
    out = [f"# Extraction audit — {run_id} (k={k}, $0, zero model calls)", "",
           f"n_obs=0 withheld questions audited: {len(rows)}", "",
           "## What one clean observation buys (criterion 2, from the run's own rows)",
           "",
           f"- median leader credence at n_obs=1, K=1: "
           f"{'—' if median_p is None else f'{median_p:.3f}'} over {n_single} rows; "
           f"commit bar {COMMIT_BAR}",
           f"- ⇒ a rescued question counts toward delivered reach only with "
           f"**>= {artifacts_needed} independent fixable artifact(s)**", "",
           "## Mechanism classes (per gold-bearing chunk)", ""]
    for c in CLASSES:
        out.append(f"- **{c}**: {totals.get(c, 0)}")
    out += ["", "## Delivered reach (criterion 1+3 — questions whose commit would change)",
            ""]
    for label, classes in (("all fixable", _FIXABLE),
                           ("declined only", ("declined",)),
                           ("picked-other only", ("picked-other",)),
                           ("ungrounded only", ("ungrounded",))):
        got = delivered_reach(rows, classes, artifacts_needed)
        verdict = "BUILD" if len(got) >= 10 else "diagnosis only (under the bar)"
        out.append(f"- **{label}**: {len(got)} — {verdict} {got if got else ''}")
    out += ["", f"NOT COVERED (named): {excluded or '—'}", "",
            "## Per-question", "",
            "| qid | gold | chunks | arts | "
            + " | ".join(CLASSES) + " | competed | picked |",
            "|" + "---|" * (5 + len(CLASSES) + 1)]
    for r in sorted(rows, key=lambda r: r.qid):
        picked = "; ".join(dict.fromkeys(p[:18] for p in r.picked))[:60]
        out.append(f"| {r.qid} | {r.gold[:20]} | {r.n_gold_chunks} "
                   f"| {r.n_gold_artifacts} | "
                   + " | ".join(str(r.counts.get(c, 0)) for c in CLASSES)
                   + f" | {r.competed} | {picked} |")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--paired", required=True, type=Path)
    ap.add_argument("--questions", type=Path, default=None)
    ap.add_argument("--k", type=int, default=20)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--out-yaml", type=Path, default=None)
    args = ap.parse_args(argv)

    questions = load_questions(args.questions) if args.questions else load_questions()
    paired = load_paired(args.paired)
    decisions = load_decisions(args.run_id)
    root = LCFG.pkm_root()
    if root is None:
        print("REFUSED: no pkm root (PKM_CONFIG unresolvable)")
        return 2
    import anthropic
    import duckdb
    conn = duckdb.connect(str(root / "catalogue.duckdb"), read_only=True)
    try:
        rows, excluded = audit_rows(paired, decisions, questions, conn, root,
                                    str(anthropic.__version__), k=args.k)
    finally:
        conn.close()
    median_p, n_single = single_obs_credence(decisions)
    artifacts_needed = 1 if (median_p is not None and median_p >= COMMIT_BAR) else 2
    report = render(rows, excluded, args.run_id, args.k, median_p, n_single,
                    artifacts_needed)
    print(report)
    if args.out:
        args.out.write_text(report, encoding="utf-8")
    if args.out_yaml:
        import yaml
        totals: Counter[str] = Counter()
        for r in rows:
            totals.update(r.counts)
        args.out_yaml.write_text(yaml.safe_dump(
            {"run_id": args.run_id, "k": args.k,
             "single_obs_median_credence": median_p, "n_single_obs_rows": n_single,
             "artifacts_needed": artifacts_needed, "commit_bar": COMMIT_BAR,
             "classes": dict(totals),
             "delivered_reach": {
                 "all_fixable": delivered_reach(rows, _FIXABLE, artifacts_needed),
                 "declined": delivered_reach(rows, ("declined",), artifacts_needed),
                 "picked_other": delivered_reach(rows, ("picked-other",),
                                                 artifacts_needed),
                 "ungrounded": delivered_reach(rows, ("ungrounded",),
                                               artifacts_needed)},
             "excluded": excluded,
             "rows": [r.__dict__ for r in rows]},
            sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
