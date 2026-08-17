#!/usr/bin/env python3
"""Reach audit — the $0 ceiling measurement behind the post-adoption lever choice (§14
adoption entry, 2026-08-17).

Run 9 closed the wrong-commit class at the price of reach (35 ✓ / 0 ✗ / 69 withheld,
answer rate 0.34). Two levers are named; each has an unknown ceiling this audit prices
BEFORE anything is built:

  (a) **independent-document corroboration** on the dispersed withholdings — the only
      rescue the temper permits (a same-doc re-read inherits the ambiguity). It can only
      rescue a question whose gold value exists in a SECOND artifact, independent of the
      gold's own provenance artifact — and without a retrieval change, only when that
      second artifact is already inside the deterministic top-k.
  (b) **the n_obs=0 cluster** — rows where the posterior saw zero grounded observations.
      A retrieval-side fix only helps where the gold is in the corpus but outside the
      top-k; an extraction-side fix only where a gold-bearing chunk WAS retrieved.

Every withheld question in the audited run's paired file lands in exactly one class:

  rescuable-retrieved    an independent gold-bearing artifact is already in the top-k —
                         the corroborate ladder could reach it today
  rescuable-unretrieved  an independent gold-bearing artifact exists in the corpus but
                         not in the top-k — corroboration needs a retrieval change first
  single-doc             the gold exists ONLY in its provenance artifact — corroboration
                         structurally cannot rescue it (the temper's standing price)
  gold-absent            no matcher-visible chunk anywhere carries the gold — either
                         unanswerable on this corpus or invisible to the token matcher;
                         NAMED, never dropped

"Carries the gold" means exactly what the gate's grading means: the shared
token-boundary matcher (``matching.answer_matches``, answer + variants), so a ceiling
counted here is denominated in the same currency as a gate ✓. The n_obs=0 rows are
additionally split retrieved-not-extracted / not-retrieved / absent.

FROZEN READING CRITERIA (stated before any result is read): the corroboration lever's
buildable ceiling is |rescuable-retrieved|; its ceiling WITH a retrieval change is
|rescuable-retrieved| + |rescuable-unretrieved|; the retrieval lever's ceiling is the
not-retrieved count among n_obs=0 rows. gold-absent rows are reachable by NO lever and
cap the answer rate honestly. Choose the lever with the larger buildable ceiling; a
ceiling under ~10 questions is not worth building ahead of live dogfood evidence.

Zero model calls by construction: pure SQL over the pinned catalogue plus the
deterministic FTS retrieval replay (rerank OFF — rerank is a live uncached call, never
taken here); no completing client is ever constructed.

Usage:
  uv run python scripts/reach_audit.py --run-id gate-20260817T195737 \
      --paired $KB/eval/gate-outside-option/paired-gate-20260817T195737.jsonl \
      --questions $KB/eval/questions_v2.yaml \
      [--k 20] [--out FILE.md] [--out-yaml FILE.yaml]
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gate_splice import load_paired
from run_eval import load_questions
from temper_audit import load_decisions

import life_agent.core.matching as MATCH
import life_agent.core.retrieval as RET
from life_agent.core import config as LCFG

_WITHHELD = ("abstain", "ask_clarify", "miss")

CLASSES = ("rescuable-retrieved", "rescuable-unretrieved", "single-doc", "gold-absent")
MISS_CLASSES = ("retrieved-not-extracted", "not-retrieved", "absent")


def _like_pattern(text: str) -> str | None:
    """A conservative ILIKE prefilter from the matcher's own tokens: any chunk the
    token-boundary matcher would accept also matches ``%tok1%tok2%…%`` (tokens appear
    in order with anything between), so the SQL scan can only over-select — the exact
    matcher then verifies. Literal LIKE metacharacters are escaped."""
    toks = MATCH.tokenize(text)
    if not toks:
        return None
    esc = [t.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") for t in toks]
    return "%" + "%".join(esc) + "%"


def gold_bearing_artifacts(conn: Any, gold: str, variants: list[str]) -> set[str]:
    """Every artifact_cache_key with at least one chunk the gate's matcher grades as
    carrying the gold. Prefilter in SQL (full-corpus ILIKE per answer form), verify with
    ``answer_matches`` — the scan can over-select, never under-select."""
    keys: set[str] = set()
    seen: set[tuple[str, str]] = set()
    for form in [gold, *variants]:
        pat = _like_pattern(str(form))
        if pat is None:
            continue
        rows = conn.execute(
            "SELECT artifact_cache_key, chunk_text FROM artifact_chunks "
            "WHERE chunk_text ILIKE ? ESCAPE '\\'", [pat]).fetchall()
        for key, text in rows:
            if (key, text) in seen or key in keys:
                continue
            seen.add((key, text))
            if MATCH.answer_matches(gold, variants, str(text)):
                keys.add(str(key))
    return keys


def classify(gold_docs: set[str], home_doc: str | None,
             retrieved_gold_docs: set[str]) -> str:
    """One class per question, from the frozen vocabulary (module docstring)."""
    if not gold_docs:
        return "gold-absent"
    independent = gold_docs - ({home_doc} if home_doc else set())
    if not independent:
        return "single-doc"
    return ("rescuable-retrieved" if independent & retrieved_gold_docs
            else "rescuable-unretrieved")


def classify_miss(gold_docs: set[str], retrieved_gold_docs: set[str]) -> str:
    """The n_obs=0 split: was the failure retrieval-side or extraction-side?"""
    if not gold_docs:
        return "absent"
    return "retrieved-not-extracted" if retrieved_gold_docs else "not-retrieved"


@dataclass(frozen=True)
class ReachRow:
    qid: str
    action: str
    n_obs: int | None            # None = no decision row logged for this question
    n_competing: int
    gold_docs: int               # distinct gold-bearing artifacts, corpus-wide
    independent_docs: int        # gold_docs excluding the provenance artifact
    retrieved_gold_docs: int     # gold-bearing artifacts inside the top-k
    retrieved_independent: int
    klass: str
    miss_klass: str | None       # only for n_obs == 0 rows


def audit_rows(paired: dict[str, dict], decisions: dict[str, dict],
               questions: list[dict], conn: Any, *, k: int = 20) -> list[ReachRow]:
    rows: list[ReachRow] = []
    by_id = {str(q["id"]): q for q in questions}
    for qid, p in sorted(paired.items()):
        typed = p.get("typed") or {}
        if typed.get("action") not in _WITHHELD:
            continue
        q = by_id.get(qid)
        if q is None:
            continue
        gold, variants = str(q.get("answer") or ""), list(q.get("answer_variants") or [])
        if not gold:
            continue  # an unanswerable-by-construction question prices no lever
        home = (q.get("provenance") or {}).get("artifact_cache_key")
        gold_docs = gold_bearing_artifacts(conn, gold, variants)
        hits = RET.retrieve_set(conn, RET.build_query(str(q["question"]), ""), k)
        retrieved = {str(h["artifact_cache_key"]) for h in hits
                     if MATCH.answer_matches(gold, variants, str(h["chunk_text"]))}
        retrieved &= gold_docs  # the exact matcher decides on both sides
        dec = decisions.get(qid) or decisions.get(str(q.get("id")))
        ps = (dec or {}).get("posterior_summary") or {}
        n_obs = int(ps["n_obs"]) if dec else None
        independent = gold_docs - ({home} if home else set())
        rows.append(ReachRow(
            qid=qid, action=str(typed.get("action")), n_obs=n_obs,
            n_competing=int(ps.get("n_competing") or 0),
            gold_docs=len(gold_docs), independent_docs=len(independent),
            retrieved_gold_docs=len(retrieved),
            retrieved_independent=len(independent & retrieved),
            klass=classify(gold_docs, home, retrieved),
            miss_klass=(classify_miss(gold_docs, retrieved)
                        if (n_obs == 0 or dec is None) else None)))
    return rows


def render(rows: list[ReachRow], run_id: str, k: int) -> str:
    by_class = Counter(r.klass for r in rows)
    miss_rows = [r for r in rows if r.miss_klass is not None]
    by_miss = Counter(r.miss_klass for r in miss_rows)
    out = [f"# Reach audit — {run_id} (k={k}, $0, deterministic)", "",
           f"Withheld questions audited: {len(rows)} "
           f"(n_obs=0 or unlogged among them: {len(miss_rows)})", "",
           "## Ceilings (frozen criteria in the module docstring)", ""]
    for c in CLASSES:
        out.append(f"- **{c}**: {by_class.get(c, 0)}")
    buildable = by_class.get("rescuable-retrieved", 0)
    with_retrieval = buildable + by_class.get("rescuable-unretrieved", 0)
    out += ["",
            f"Corroboration lever — buildable ceiling {buildable}, "
            f"with a retrieval change {with_retrieval}.",
            f"Unreachable by any lever (gold-absent): {by_class.get('gold-absent', 0)}.",
            "", "## The n_obs=0 cluster", ""]
    for c in MISS_CLASSES:
        out.append(f"- **{c}**: {by_miss.get(c, 0)}")
    out += ["", "## Per-question", "",
            "| qid | action | n_obs | n_comp | docs | indep | retr | class | miss |",
            "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| {r.qid} | {r.action} | "
                   f"{'—' if r.n_obs is None else r.n_obs} | {r.n_competing} | "
                   f"{r.gold_docs} | {r.independent_docs} | {r.retrieved_independent} | "
                   f"{r.klass} | {r.miss_klass or ''} |")
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
    import duckdb
    conn = duckdb.connect(str(root / "catalogue.duckdb"), read_only=True)
    try:
        rows = audit_rows(paired, decisions, questions, conn, k=args.k)
    finally:
        conn.close()
    report = render(rows, args.run_id, args.k)
    print(report)
    if args.out:
        args.out.write_text(report, encoding="utf-8")
    if args.out_yaml:
        import yaml
        args.out_yaml.write_text(yaml.safe_dump(
            {"run_id": args.run_id, "k": args.k,
             "classes": dict(Counter(r.klass for r in rows)),
             "miss_classes": dict(Counter(r.miss_klass for r in rows
                                          if r.miss_klass is not None)),
             "rows": [r.__dict__ for r in rows]},
            sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
