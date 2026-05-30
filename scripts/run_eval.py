#!/usr/bin/env python3
"""Answer-grounded retrieval eval (supersedes run_phase1_eval.py's source-id grading).

Ground truth is the ANSWER (the fact), not a source_id. For each question we check
whether the answer surfaces in a top-k retrieved chunk (token-boundary match, §3 of the
plan), and classify the outcome by MODE:

    PASS            — answer in a top-k chunk
    RETRIEVAL_MISS  — answer is somewhere in the corpus but not in top-k
    ABSENT_COVERAGE — answer nowhere in corpus, source not ingested
    ABSENT_EXTRACTION — answer nowhere in corpus, extraction destroyed it (OCR)
    (ABSENT_UNSPECIFIED if no mode_hint)

SUBJECT_CONFUSION is reported as an ORTHOGONAL flag (set when a distractor — a confusable
wrong-subject value, e.g. the partner's ID — is retrieved in top-k); it is not a verdict.

The question fixture is PII-bearing and lives OUTSIDE this public repo, at
$LIFE_AGENT_KB/eval/questions.yaml (fail-fast if absent). The grading logic is in
scripts/eval_grading.py (unit-tested).

A --synthesis flag reserves the end-to-end grader (synthesized answer + citation
validity) for Phase 2 / pkm-memory; it is inert today (we have retrieval, not synthesis).

Usage (run in the pkm env for pkm.retrieval + DuckDB):
    uv run --project ~/git/pkm python scripts/run_eval.py [--config PATH] [--k N] \
        [--rebuild-index] [--synthesis]
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_grading import answer_matches, chunk_matches_any, classify  # noqa: E402

# Effectively-unbounded k for the in-corpus set-membership check: we want "does the
# answer appear ANYWHERE", not a ranked top-k, so we take all FTS matches and confirm
# with the token-boundary matcher (specific answers match few chunks; this only runs
# for answers NOT already in top-k, i.e. rare/absent ones).
_MEMBERSHIP_K = 100_000


def _kb_root() -> Path:
    env = os.environ.get("LIFE_AGENT_KB")
    return Path(env).expanduser() if env else Path.home() / ".life-agent/kb"


def load_questions() -> list[dict]:
    """Load the answer-grounded question set from the KB fixture; fail fast if absent
    (it holds PII and is not in this repo). Fills optional-field defaults."""
    import yaml

    fixture = _kb_root() / "eval/questions.yaml"
    if not fixture.exists():
        raise SystemExit(
            f"eval fixture not found: {fixture}\n"
            "It holds PII and lives in $LIFE_AGENT_KB, outside this public repo.\n"
            "Set LIFE_AGENT_KB or create it (schema: life-agent/eval/questions.example.yaml)."
        )
    data = yaml.safe_load(fixture.read_text(encoding="utf-8"))
    questions = data.get("questions") if isinstance(data, dict) else None
    if not questions:
        raise SystemExit(f"no 'questions:' list found in {fixture}")
    for q in questions:
        q.setdefault("subject", "n/a")
        q.setdefault("answer", "")
        q.setdefault("answer_variants", [])
        q.setdefault("distractors", [])
        q.setdefault("fuzzy", False)
        q.setdefault("search_queries", [])
        q.setdefault("mode_hint", None)
        q.setdefault("notes", "")
    return questions


def _answer_in_corpus(conn, answer: str, variants: list[str]) -> bool:
    """Set-membership via the FTS index (not a LIKE scan): search the answer's tokens
    unbounded, then confirm with the token-boundary matcher."""
    from pkm.retrieval import search

    for query in [answer, *variants]:
        if not query:
            continue
        hits = search(conn, query, k=_MEMBERSHIP_K)
        if chunk_matches_any(answer, variants, [h.chunk_text for h in hits]):
            return True
    return False


def grade_retrieval(conn, q: dict, k: int) -> dict:
    """Retrieval-level grade for one question (the active grader today)."""
    from pkm.retrieval import search

    answer = q["answer"]
    variants = q["answer_variants"]
    distractors = q["distractors"] if q["subject"] != "n/a" else []

    # Top-k chunks across all search_queries (union).
    topk_texts: list[str] = []
    top_snippet = ""
    for query in q["search_queries"]:
        for hit in search(conn, query, k=k):
            topk_texts.append(hit.chunk_text)
            if not top_snippet:
                top_snippet = (
                    f"[{hit.score:.2f}] {Path(hit.source_path).name}: "
                    + hit.chunk_text[:70].replace("\n", " ")
                )

    if answer:
        answer_in_topk = chunk_matches_any(answer, variants, topk_texts)
        answer_in_corpus = answer_in_topk or _answer_in_corpus(conn, answer, variants)
    else:
        # known-unanswerable (no ground-truth value) -> ABSENT by construction
        answer_in_topk = answer_in_corpus = False

    distractor_in_topk = any(
        answer_matches(d, [], t) for d in distractors for t in topk_texts
    )

    v = classify(
        answer_in_topk=answer_in_topk,
        answer_in_corpus=answer_in_corpus,
        distractor_in_topk=distractor_in_topk,
        mode_hint=q["mode_hint"],
    )
    return {
        "id": q["id"],
        "question": q["question"],
        "subject": q["subject"],
        "verdict": v.verdict,
        "subject_confusion": v.subject_confusion,
        "top_snippet": top_snippet,
        "notes": q["notes"],
    }


def synthesis_grade(conn, q: dict, k: int) -> dict:  # pragma: no cover - Phase 2
    """END-TO-END grader slot (Phase 2 / pkm-memory): retrieve -> agent synthesizes an
    answer + citation -> grade answer (LLM judge, modal of N=3, pinned snapshot, logged),
    citation-validity (cited chunk contains the answer), and subject (asserted value not a
    distractor). Inert until a synthesis path exists; see plan §2/§3."""
    raise NotImplementedError("synthesis grader is not wired until Phase 2 / pkm-memory")


def format_report(results: list[dict], k: int, elapsed: float) -> str:
    counts = Counter(r["verdict"] for r in results)
    in_corpus = [r for r in results if r["verdict"] in ("PASS", "RETRIEVAL_MISS")]
    n_pass = counts["PASS"]
    n_confused = sum(1 for r in results if r["subject_confusion"])

    lines = [
        "# Eval log (answer-grounded)",
        "",
        f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}   k={k}   elapsed={elapsed:.1f}s",
        "",
        f"**Retrieval: {n_pass}/{len(in_corpus)} of in-corpus answers surfaced in top-k.**",
        "",
        "Failure modes (by count):",
        f"- PASS: {counts['PASS']}",
        f"- RETRIEVAL_MISS (in corpus, not top-k): {counts['RETRIEVAL_MISS']}",
        f"- ABSENT_COVERAGE (not ingested): {counts['ABSENT_COVERAGE']}",
        f"- ABSENT_EXTRACTION (OCR destroyed): {counts['ABSENT_EXTRACTION']}",
        f"- ABSENT_UNSPECIFIED: {counts['ABSENT_UNSPECIFIED']}",
        f"- SUBJECT_CONFUSION flagged (orthogonal): {n_confused}",
        "",
        "| ID | Verdict | Subj | Conf | Question |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        conf = "⚠" if r["subject_confusion"] else ""
        lines.append(
            f"| {r['id']} | {r['verdict']} | {r['subject']} | {conf} | {r['question'][:54]} |"
        )
    lines += ["", "## Details", ""]
    for r in results:
        lines.append(f"### {r['id']} — {r['verdict']}"
                     + ("  (SUBJECT_CONFUSION)" if r["subject_confusion"] else ""))
        lines.append(f"**Q:** {r['question']}")
        lines.append(f"**Notes:** {r['notes']}")
        if r["top_snippet"]:
            lines.append(f"**Top hit:** {r['top_snippet']}")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", default=os.environ.get("PKM_CONFIG", str(Path("~/.config/life-agent/pkm.yaml").expanduser())),
        help="pkm config.yaml (default: $PKM_CONFIG or ~/.config/life-agent/pkm.yaml)",
    )
    parser.add_argument("--k", type=int, default=20, help="top-k per query")
    parser.add_argument("--rebuild-index", action="store_true", help="rebuild FTS first")
    parser.add_argument(
        "--synthesis", action="store_true",
        help="(Phase 2) run the end-to-end synthesis+citation grader — not yet wired",
    )
    args = parser.parse_args()

    import duckdb
    import yaml

    questions = load_questions()
    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    db_path = Path(cfg["root_dir"]).expanduser() / "catalogue.duckdb"
    conn = duckdb.connect(str(db_path))
    conn.execute("INSTALL fts; LOAD fts;")

    if args.rebuild_index:
        from pkm.retrieval import build_fts_index
        print("Building FTS index …")
        build_fts_index(conn)

    if args.synthesis:
        print(
            "NOTE: --synthesis grader is not wired until Phase 2 / pkm-memory; "
            "running retrieval-only.\n"
        )

    print(f"Running answer-grounded eval (k={args.k}) over {len(questions)} questions …")
    t0 = time.monotonic()
    results = [grade_retrieval(conn, q, args.k) for q in questions]
    elapsed = time.monotonic() - t0

    report = format_report(results, args.k, elapsed)
    out = _kb_root() / "eval/eval_log.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")
    print(f"\nReport written to {out}\n")

    # stdout summary
    counts = Counter(r["verdict"] for r in results)
    in_corpus = counts["PASS"] + counts["RETRIEVAL_MISS"]
    print(f"Retrieval: {counts['PASS']}/{in_corpus} in-corpus answers in top-k")
    for r in results:
        mark = {"PASS": "✓"}.get(r["verdict"], "·")
        conf = " ⚠CONFUSION" if r["subject_confusion"] else ""
        print(f"  {mark} {r['id']} [{r['verdict']}]{conf}: {r['question'][:52]}")
    return 0 if counts["PASS"] >= 1 else 1


if __name__ == "__main__":
    sys.exit(main())
