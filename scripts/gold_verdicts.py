#!/usr/bin/env python
"""gold_verdicts — gold verdicts for an EXTERNAL, labelled KB (r51b 2b; `GD-30` (4)).

On a public benchmark the human-annotated answer IS the truth measurement, so a verdict on
"asserting the decision's leader now would have been correct" can be derived from it — with
the benchmark's OWN matcher (`atm_bench.vendored.atm_number_match`: relative dates resolved
against the question's anchor, parentheticals and currency breakdowns stripped, codes exact),
never the harness's token-run substring rule, which manufactures false "wrong"s on dates and
currency and would bias the very read the rows exist for. `answer_matches` is still computed,
as a cross-tab bit in ``note``; it decides nothing.

THE ONE GUARD: rows are written only into a KB carrying ``external-corpus.json`` at its root.
`core.claude_verdicts` readers are issuer-blind, so a ``gold:*`` row on the OWNER's ledger
would supersede a deliberated ``claude-code`` row; the manifest refusal (rc 2) is what keeps
it off, and it fails closed. Rows carry issuer ``gold:<corpus>`` and ``evidence``
``<corpus>:<qa id>`` — ids, never values; nothing here prints a question, answer or leader
except into the audit file the caller names, outside the KB and outside the repo.

  uv run --project . python scripts/gold_verdicts.py grade --kb PATH
  uv run --project . python scripts/gold_verdicts.py audit-sample --kb PATH --n 60 --seed S \\
      --out FILE          # blind rows (question, gold, leader) + FILE.key.jsonl (the verdicts)
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from atm_bench.vendored import atm_number_match, detect_qtype
from claude_verdict import _leader, eligible_from
from run_eval import load_questions

import life_agent.core.claude_verdicts as CV
import life_agent.core.decisions as DEC
from life_agent.core.matching import answer_matches

MANIFEST = "external-corpus.json"
COUNT_KEYS = ("eligible", "no_question", "not_gradeable", "already_verdicted", "correct",
              "wrong", "harness_agrees", "harness_disagrees")


def gradeable(answer_text: str) -> bool:
    """THE gradeability predicate: a property of the ANSWER, by the benchmark's own detector
    — ``number`` rows are mechanically gradeable; ``list_recall`` / ``open_end`` are not."""
    return detect_qtype(str(answer_text)) == "number"


def read_manifest(kb: Path) -> dict[str, Any] | None:
    path = kb / MANIFEST
    if not path.is_file():
        return None
    doc = json.loads(path.read_text(encoding="utf-8"))
    return doc if isinstance(doc, dict) and doc.get("corpus") else None


def grade_decisions(decisions: Iterable[DEC.DecisionEvent],
                    questions_by_hash: Mapping[str, Mapping[str, Any]],
                    existing: Iterable[CV.ClaudeVerdictEvent], *,
                    issuer: str, corpus: str, now: str,
                    ) -> tuple[list[CV.ClaudeVerdictEvent], Counter[str]]:
    """The verdict rule. Eligible = the CLI's one rule; the question by recomputed hash;
    skip fuzzy / non-``number`` answers; dedupe on ``(decision_id, issuer)``; ``correct``
    from the vendored matcher; the harness bit recorded beside it."""
    counts: Counter[str] = Counter({k: 0 for k in COUNT_KEYS})
    done = {(e.decision_id, e.issuer) for e in existing}
    events: list[CV.ClaudeVerdictEvent] = []
    eligible = eligible_from(decisions)
    counts["eligible"] = len(eligible)
    for decision_id, d in eligible.items():
        q = questions_by_hash.get(d.question_id)
        if q is None:
            counts["no_question"] += 1
            continue
        if q.get("fuzzy") or not gradeable(str(q.get("answer", ""))):
            counts["not_gradeable"] += 1
            continue
        if (decision_id, issuer) in done:
            counts["already_verdicted"] += 1
            continue
        leader, _ = _leader(d)
        gold, question = str(q["answer"]), str(q["question"])
        correct = int(atm_number_match(gold, leader, question))
        alt = int(answer_matches(gold, [str(v) for v in (q.get("answer_variants") or [])],
                                 leader))
        counts["correct" if correct else "wrong"] += 1
        counts["harness_agrees" if alt == correct else "harness_disagrees"] += 1
        events.append(CV.ClaudeVerdictEvent(
            tx_time=now, question_id=d.question_id, decision_id=decision_id,
            dimensions={"correct": correct}, evidence=(f"{corpus}:{q['id']}",),
            note=f"harness-match:{alt}", issuer=issuer))
    return events, counts


def audit_sample(decisions: Iterable[DEC.DecisionEvent],
                 questions_by_hash: Mapping[str, Mapping[str, Any]],
                 existing: Iterable[CV.ClaudeVerdictEvent], *, issuer: str, n: int, seed: int,
                 ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """A seeded sample of gold-verdicted rows for the blind hand audit (X3d): the rows carry
    question, gold and leader; the verdicts ride a separate key list in the same order."""
    by_id = eligible_from(decisions)
    verdicts = {e.decision_id: CV.y(e) for e in CV.latest_by_decision(
        [e for e in existing if e.issuer == issuer]).values()}
    ids = sorted(d for d in verdicts if d in by_id)
    picked = random.Random(seed).sample(ids, min(n, len(ids)))
    rows, keys = [], []
    for decision_id in picked:
        d = by_id[decision_id]
        q = questions_by_hash[d.question_id]
        rows.append({"decision_id": decision_id, "question": str(q["question"]),
                     "gold": str(q["answer"]), "leader": _leader(d)[0]})
        keys.append({"decision_id": decision_id, "verdict": verdicts[decision_id]})
    return rows, keys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("grade", help="append gold verdicts for every eligible, gradeable decision")
    g.add_argument("--kb", required=True, type=Path)
    a = sub.add_parser("audit-sample", help="write a blind, seeded audit sample OUTSIDE the KB")
    a.add_argument("--kb", required=True, type=Path)
    a.add_argument("--n", type=int, default=60)
    a.add_argument("--seed", type=int, required=True)
    a.add_argument("--out", type=Path, required=True)
    return parser


def _jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.write_text("".join(json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n"
                            for r in rows), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    kb = Path(args.kb).expanduser()
    manifest = read_manifest(kb)
    if manifest is None:
        print(f"REFUSED: {kb} carries no {MANIFEST} — gold verdicts are written only into a KB "
              "that declares itself external (GD-30); the owner's ledger takes deliberated "
              "verdicts only.")
        return 2
    corpus = str(manifest["corpus"])
    issuer = f"gold:{corpus}"
    dec_path = kb / "calibration" / "decisions.jsonl"
    cv_path = kb / "calibration" / "claude_verdicts.jsonl"
    decisions = DEC.read(dec_path)
    existing = CV.read(cv_path) if cv_path.exists() else []
    questions = load_questions(kb / "eval" / "questions.yaml")
    by_hash = {DEC.question_id(str(q["question"])): q for q in questions}
    if args.cmd == "grade":
        now = datetime.now(UTC).isoformat(timespec="seconds")
        events, counts = grade_decisions(decisions, by_hash, existing, issuer=issuer,
                                         corpus=corpus, now=now)
        for e in events:
            CV.append(cv_path, e)
        print(f"gold verdicts ({issuer}): "
              + " ".join(f"{k}={counts[k]}" for k in COUNT_KEYS)
              + f" appended={len(events)}")
        return 0
    rows, keys = audit_sample(decisions, by_hash, existing, issuer=issuer, n=args.n,
                              seed=args.seed)
    out = Path(args.out).expanduser()
    if kb in out.resolve().parents:
        print("REFUSED: the audit file must live OUTSIDE the KB")
        return 2
    _jsonl(out, rows)
    _jsonl(Path(str(out) + ".key.jsonl"), keys)
    print(f"audit sample: {len(rows)} blind row(s) -> {out}; verdict key -> {out}.key.jsonl "
          f"(seed {args.seed}; delete both after the tally)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
