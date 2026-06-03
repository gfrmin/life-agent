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

A --synthesis flag runs the end-to-end grader: it synthesises via the production answer
path, audits citations deterministically (citation_guard), and judges faithfulness +
citation_fidelity with the cross-provider LLM judge (modal-of-N) → hallucination /
grounded-answer / abstention-honesty rates in eval/synthesis_log.md.

Usage (run in this monorepo's env for pkm.retrieval + DuckDB):
    uv run --project . python scripts/run_eval.py [--config PATH] [--k N] \
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
from eval_grading import answer_matches, chunk_matches_any, classify

# Effectively-unbounded k for the in-corpus set-membership check: we want "does the
# answer appear ANYWHERE", not a ranked top-k, so we take all FTS matches and confirm
# with the token-boundary matcher (specific answers match few chunks; this only runs
# for answers NOT already in top-k, i.e. rare/absent ones).
_MEMBERSHIP_K = 100_000

_JUDGE_N = 3  # modal-of-N judge calls for the synthesis grader (matches the comparison harness)


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


# --- synthesis grader (end-to-end: the advertisable hallucination-rate number) ----------
# Grades the PRODUCTION answer path (ask.answer) with two instruments: a deterministic
# citation audit (citation_guard, no LLM) + a single-answer cross-provider LLM judge
# (faithfulness + citation_fidelity, modal-of-N) reusing the blind-judge infra. The pure
# classification + rate math are split out so they are unit-tested without any API call.

def _classify_synthesis(*, faithfulness: int, citation_fidelity: int,
                        structural_unsupported: bool, answerable: bool) -> dict:
    """Pure: map modal judge scores + the deterministic audit to verdict booleans.

    - synthesis_pass: faithfulness>=2 AND citation_fidelity>=2 (honest abstention scores 3/3).
    - hallucinated: a fabricated / wrong-subject / mis-cited assertion — faithfulness<=1, OR
      citation_fidelity==0, OR the deterministic guard found an unsupported verbatim citation.
    - abstained_correctly (unanswerable only): the answer honestly declined (faithfulness>=2)."""
    return {
        "synthesis_pass": faithfulness >= 2 and citation_fidelity >= 2,
        "hallucinated": faithfulness <= 1 or citation_fidelity == 0 or structural_unsupported,
        "abstained_correctly": (not answerable) and faithfulness >= 2,
    }


def synthesis_rates(rows: list[dict]) -> dict:
    """Pure: the three headline reliability numbers from a list of graded rows."""
    answerable = [r for r in rows if r["answerable"]]
    unanswerable = [r for r in rows if not r["answerable"]]
    grounded = [r for r in answerable if r["synthesis_pass"]]
    hallucinated = [r for r in rows if r["hallucinated"]]
    honest = [r for r in unanswerable if r["abstained_correctly"]]

    def _rate(a: list, b: list) -> float | None:
        return (len(a) / len(b)) if b else None

    return {
        "n": len(rows),
        "n_answerable": len(answerable), "n_unanswerable": len(unanswerable),
        "n_grounded": len(grounded), "n_hallucinated": len(hallucinated), "n_honest": len(honest),
        "grounded_rate": _rate(grounded, answerable),
        "hallucination_rate": _rate(hallucinated, rows),
        "abstention_honesty": _rate(honest, unanswerable),
    }


def _synthesis_judge_once(q: dict, answer_text: str, sources: list[dict], rubric_text: str):
    """One single-answer judge call -> {faithfulness, citation_fidelity, _served} or None.
    Reuses the cross-provider judge (_common.judge_complete) and the frozen rubric."""
    import json

    sys.path.insert(0, str(Path(__file__).resolve().parent / "comparison"))
    import _common as JC

    src_block = "\n\n".join(f"[{s['n']}] {s['text']}" for s in sources) or "(no sources cited)"
    system = (
        "You are an impartial grader of ONE answer to a question about a person's own records. "
        "You are given the answer and the SOURCE TEXTS it cited (as [n]). Judge ONLY from what is "
        "shown. For citation_fidelity you MUST check the cited source text actually contains the "
        "asserted fact. Asserting a listed wrong-subject distractor caps faithfulness at 1. A "
        "correct 'not in the corpus' for a truly-absent fact is full marks. Return STRICT JSON "
        'only: {"faithfulness":int,"citation_fidelity":int}.\n\n' + rubric_text
    )
    user = (
        f"QUESTION: {q['question']}\n"
        f"CANONICAL ANSWER: {q.get('answer') or '(no single value)'}   "
        f"ACCEPTABLE VARIANTS: {q.get('answer_variants') or '[]'}\n"
        f"MUST-NOT-ASSERT (wrong-subject distractors): {q.get('distractors') or '[]'}\n"
        f"ANSWERABLE FROM CORPUS: {q.get('answerable', bool(q.get('answer')))}\n\n"
        f"ANSWER:\n{answer_text}\n\nCITED SOURCES:\n{src_block}\n"
    )
    r = JC.judge_complete(system, user, max_tokens=200)
    txt = r.text.strip()
    if txt.startswith("```"):
        txt = txt.strip("`").split("\n", 1)[-1].rsplit("```", 1)[0]
    try:
        obj = json.loads(txt[txt.index("{"): txt.rindex("}") + 1])
        return {"faithfulness": int(obj["faithfulness"]),
                "citation_fidelity": int(obj["citation_fidelity"]),
                "_served": r.served_model}
    except (ValueError, KeyError, TypeError):
        return None


def synthesis_grade(conn, q: dict, k: int) -> dict:
    """End-to-end grade for one question: synthesise via the production path, audit citations
    deterministically, then judge (modal-of-N). Returns a row consumed by ``synthesis_rates``."""
    here = str(Path(__file__).resolve().parent)
    sys.path.insert(0, here)
    sys.path.insert(0, str(Path(__file__).resolve().parent / "comparison"))
    import ask
    import citation_guard
    from blind_judge import _rubric_text, modal

    text, cards, _ = ask.answer(conn, q["question"], k)
    sources = [{"n": c.n, "text": c.text} for c in cards]
    audit = citation_guard.audit(text, cards)
    rubric = _rubric_text()

    faith: list[int] = []
    cite: list[int] = []
    served: set[str] = set()
    for _ in range(_JUDGE_N):
        j = _synthesis_judge_once(q, text, sources, rubric)
        if not j:
            continue
        faith.append(j["faithfulness"])
        cite.append(j["citation_fidelity"])
        served.add(j["_served"])

    f_modal, c_modal = modal(faith), modal(cite)
    answerable = bool(q.get("answerable", bool(q.get("answer"))))
    verdict = _classify_synthesis(
        faithfulness=f_modal, citation_fidelity=c_modal,
        structural_unsupported=bool(audit.unsupported), answerable=answerable,
    )
    return {
        "id": q["id"], "question": q["question"], "answerable": answerable,
        "faithfulness": f_modal, "citation_fidelity": c_modal, "structural_ok": audit.ok,
        "answer": text[:140].replace("\n", " "), "served": sorted(served), **verdict,
    }


def format_synthesis_report(rows: list[dict], rates: dict, k: int, elapsed: float) -> str:
    def _pct(x: float | None) -> str:
        return "n/a" if x is None else f"{100 * x:.0f}%"

    lines = [
        "# Synthesis eval log (end-to-end: grounded + hallucination rate)",
        "",
        f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}   k={k}   elapsed={elapsed:.1f}s   "
        f"judge=modal-of-{_JUDGE_N}",
        "",
        f"**Hallucination rate: {_pct(rates['hallucination_rate'])}** "
        f"({rates['n_hallucinated']}/{rates['n']} answers fabricated / wrong-subject / mis-cited).",
        f"**Grounded-answer rate: {_pct(rates['grounded_rate'])}** "
        f"({rates['n_grounded']}/{rates['n_answerable']} answerable questions).",
        f"**Abstention-honesty: {_pct(rates['abstention_honesty'])}** "
        f"({rates['n_honest']}/{rates['n_unanswerable']} known-unanswerable questions).",
        "",
        "Every emitted *verbatim* fact is additionally verified at answer time to appear in its "
        "cited source (deterministic citation guard); the rates above are the LLM-judge measure of "
        "semantic faithfulness.",
        "",
        "| ID | faith | cite | struct | verdict | Q |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        v = "HALLUCINATED" if r["hallucinated"] else ("PASS" if r["synthesis_pass"] else "weak")
        struct = "ok" if r["structural_ok"] else "⚠"
        lines.append(f"| {r['id']} | {r['faithfulness']} | {r['citation_fidelity']} | {struct} "
                     f"| {v} | {r['question'][:48]} |")
    return "\n".join(lines) + "\n"


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
        "--config",
        default=os.environ.get(
            "PKM_CONFIG", str(Path("~/.config/life-agent/pkm.yaml").expanduser())),
        help="pkm config.yaml (default: $PKM_CONFIG or ~/.config/life-agent/pkm.yaml)",
    )
    parser.add_argument("--k", type=int, default=20, help="top-k per query")
    parser.add_argument("--rebuild-index", action="store_true", help="rebuild FTS first")
    parser.add_argument(
        "--synthesis", action="store_true",
        help=(
            "run the end-to-end synthesis grader (LLM judge) → "
            "hallucination/grounded/abstention rates"
        ),
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
        import json

        print(f"Running synthesis grader (k={args.k}) over {len(questions)} questions "
              f"(production answer path + deterministic citation audit + modal-of-{_JUDGE_N} "
              f"LLM judge) …")
        t0 = time.monotonic()
        rows = [synthesis_grade(conn, q, args.k) for q in questions]
        elapsed = time.monotonic() - t0
        rates = synthesis_rates(rows)

        out = _kb_root() / "eval/synthesis_log.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(format_synthesis_report(rows, rates, args.k, elapsed), encoding="utf-8")

        sys.path.insert(0, str(Path(__file__).resolve().parent / "comparison"))
        import _common as JC
        served = sorted({s for r in rows for s in r["served"]})
        (_kb_root() / "eval/judge_meta.json").write_text(
            json.dumps({"judge_model": JC.JUDGE_MODEL, "served": served, "n_modal": _JUDGE_N,
                        "rubric": "rubric_v1.yaml"}, indent=2), encoding="utf-8")

        print(f"\nSynthesis report → {out}")
        print(f"  hallucination-rate={rates['hallucination_rate']}  "
              f"grounded-rate={rates['grounded_rate']}  "
              f"abstention-honesty={rates['abstention_honesty']}")
        return 0 if (rates["hallucination_rate"] or 0.0) == 0.0 else 1

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
