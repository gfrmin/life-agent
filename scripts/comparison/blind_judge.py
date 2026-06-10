#!/usr/bin/env python3
"""blind_judge.py — blind, cross-provider grading (SPEC-comparison.md §6, rubric_v1.yaml).

For each scored question it takes the two answers (Phase 0, Phase 1), strips system labels,
presents both with citations in the SAME neutral `[n]` shape AND each answer's cited source TEXT
(so citation-fidelity is verifiable, not faked), randomises A/B order (seed recorded), and asks the
pinned cross-provider judge (gpt-5.1) to score each on faithfulness / completeness / citation-
fidelity per the versioned rubric. N=3 modal per dimension; the A/B map is reversed afterward so
scores attach to the right system. Output is per-question, broken down by order.

Blinding (§6): no labels; citation FORM normalised to `[n]`; Phase-0 page filenames kept out of the
shown text; A/B shuffled. Residual prose-style differences between an authored page and a raw chunk
are inherent to what's being compared and are noted as a limitation in the report, not laundered.

Run:  python scripts/comparison/blind_judge.py   (needs OPENAI_API_KEY in keyring)
"""
from __future__ import annotations

import json
import random
import sys
from collections import Counter
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as C

RUBRIC = Path(__file__).resolve().parent.parent.parent / "eval" / "rubric_v1.yaml"
SHUFFLE_SEED = 20260530  # recorded; makes the A/B assignment reproducible
DIMS = ("faithfulness", "completeness", "citation_fidelity")


def _load(name: str) -> dict[str, dict]:
    rows = [
        json.loads(line)
        for line in (C.COMPARISON_DIR / name).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return {r["question_id"]: r for r in rows}


def _sources_block(ans: dict) -> str:
    return "\n\n".join(f"[{c['n']}] {c['text']}" for c in ans["sources"]) or "(no sources cited)"


def _rubric_text() -> str:
    r = yaml.safe_load(RUBRIC.read_text(encoding="utf-8"))
    lines = ["Score each answer on these dimensions (integer 0-3):"]
    for dim, spec in r["dimensions"].items():
        lines.append(f"\n{dim}: {spec['question']}")
        for score, anchor in sorted(spec["anchors"].items(), reverse=True):
            lines.append(f"  {score} = {anchor}")
    return "\n".join(lines)


def judge_once(q: dict, ans_a: dict, ans_b: dict, rubric: str) -> dict | None:
    gold = q.get("answer") or "(no single value — see expected components)"
    system = (
        "You are an impartial grader comparing two answers to the same question about a person's "
        "records. You are given each answer and the SOURCE TEXTS it cited (as [n]). Judge ONLY "
        "from what is shown. For citation_fidelity you MUST check that the cited source text "
        "actually contains the asserted fact; a citation marker whose source lacks the fact "
        "scores low. "
        "A correct 'the answer is not in the sources' for a truly-absent fact is full marks on all "
        "dimensions. Return STRICT JSON only: "
        '{"A":{"faithfulness":int,"completeness":int,"citation_fidelity":int},'
        '"B":{"faithfulness":int,"completeness":int,"citation_fidelity":int}}.\n\n' + rubric
    )
    user = (
        f"QUESTION: {q['question']}\n"
        f"EXPECTED COMPONENTS (for completeness): {q.get('expected_components') or '[]'}\n"
        f"CANONICAL ANSWER: {gold}   ACCEPTABLE VARIANTS: {q.get('answer_variants') or '[]'}\n"
        f"MUST-NOT-ASSERT (wrong-subject distractors): {q.get('distractors') or '[]'}\n"
        f"ANSWERABLE FROM CORPUS: {q.get('answerable')}\n\n"
        f"===== ANSWER A =====\n{ans_a['text']}\n\nA's CITED SOURCES:\n{_sources_block(ans_a)}\n\n"
        f"===== ANSWER B =====\n{ans_b['text']}\n\nB's CITED SOURCES:\n{_sources_block(ans_b)}\n"
    )
    r = C.judge_complete(system, user, max_tokens=300)
    txt = r.text.strip()
    if txt.startswith("```"):
        txt = txt.strip("`").split("\n", 1)[-1].rsplit("```", 1)[0]
    try:
        obj = json.loads(txt[txt.index("{"): txt.rindex("}") + 1])
        obj["_served"] = r.served_model
        return obj
    except (ValueError, KeyError):
        return None


def modal(vals: list[int]) -> int:
    """Modal score; tie -> lower (conservative, SPEC §6 / rubric aggregation)."""
    if not vals:
        return 0
    c = Counter(vals)
    top = max(c.values())
    return min(v for v, n in c.items() if n == top)


def main() -> int:
    p0 = _load("phase0_answers.jsonl")
    p1 = _load("phase1_answers.jsonl")
    questions = C.scored_questions()
    rubric = _rubric_text()
    rng = random.Random(SHUFFLE_SEED)

    results = []
    served = set()
    for q in questions:
        qid = q["id"]
        a0, a1 = p0.get(qid), p1.get(qid)
        if not a0 or not a1:
            print(f"  {qid}: MISSING answer (p0={bool(a0)} p1={bool(a1)}) — skipped")
            continue
        a_is_p0 = rng.random() < 0.5            # randomise which system is shown as "A"
        ans_a, ans_b = (a0, a1) if a_is_p0 else (a1, a0)

        per_dim: dict[str, dict[str, list[int]]] = {
            "phase0": {d: [] for d in DIMS}, "phase1": {d: [] for d in DIMS}}
        for _ in range(C.JUDGE_N):
            j = judge_once(q, ans_a, ans_b, rubric)
            if not j:
                continue
            served.add(j.get("_served", ""))
            for sysname, slot in (("phase0", "A" if a_is_p0 else "B"),
                                  ("phase1", "B" if a_is_p0 else "A")):
                for d in DIMS:
                    v = j.get(slot, {}).get(d)
                    if isinstance(v, int):
                        per_dim[sysname][d].append(v)

        row = {"id": qid, "order": q["order"], "anticipated": q["anticipated"],
               "answerable": q["answerable"], "subject": q.get("subject"),
               "a_was_phase0": a_is_p0,
               "phase0": {d: modal(per_dim["phase0"][d]) for d in DIMS},
               "phase1": {d: modal(per_dim["phase1"][d]) for d in DIMS}}
        results.append(row)
        print(f"  {qid} [{q['order']}]  P0 {tuple(row['phase0'][d] for d in DIMS)}  "
              f"P1 {tuple(row['phase1'][d] for d in DIMS)}")

    out = C.COMPARISON_DIR / "judge_scores.jsonl"
    out.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in results), encoding="utf-8")
    meta = {"judge_model": C.JUDGE_MODEL, "served": sorted(served), "n_modal": C.JUDGE_N,
            "shuffle_seed": SHUFFLE_SEED, "rubric": "rubric_v1.yaml"}
    (C.COMPARISON_DIR / "judge_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"\nwrote {out} ({len(results)} graded); judge served: {sorted(served)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
