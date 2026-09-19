#!/usr/bin/env python3
"""Opus-combiner + ADVERSARIAL VERIFY — does a refute-by-default grounding pass kill the
confident-wrong while keeping the corrects? (owner-autonomous, 2026-06-18.)

probe_opus_answer showed Opus joint-reading the retrieved docs lifts CORRECT 0→3 but produces
1 confident-wrong (q-020: a plausible-distractor grabbed when the true answer was absent —
"Ben Craft @ smartodds" for a horse-race-data inquiry whose real sender wasn't retrieved). The
fix the calibration pointed at: after Opus PROPOSES (value, confidence), a second SKEPTICAL Opus
pass must produce the exact quote proving that value answers THIS question; refute by default.
A proposal that can't be grounded is withheld, not asserted — so the same hard gate (zero
confident-wrong) is enforced by EVIDENCE, not by trusting the proposer's confidence.

This is the adversarial-verify quality pattern, single-model. Measures the (CORRECT @ 0-CW,
rejection behaviour, cost) row. PII: question + snippets to the API (synthesize boundary); the
console prints ids/verdicts only.

    ANTHROPIC_API_KEY=$(secret-tool lookup service env key ANTHROPIC_API_KEY) \\
        uv run --project . python scripts/probe_opus_verified.py [--k N] [--pstar P]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_grading import answer_matches
from probe_opus_answer import _ask_opus, _complete
from run_eval import load_questions

_VERIFY_SYSTEM = (
    "You are a STRICT fact-checker. Given a QUESTION, a PROPOSED ANSWER, and DOCUMENTS, decide "
    "whether the documents EXPLICITLY prove the proposed answer is the answer to THIS question. "
    'Return ONLY JSON: {"proven": <true|false>, "quote": "<the exact sentence from a document '
    'that proves it, or empty>"}. Refute by default: proven=true ONLY if a document directly '
    "names the proposed answer AS the answer to this specific question. If the support is "
    "indirect, adjacent (a different but related entity), inferred, or absent, proven=false. A "
    "wrongly-confirmed answer is far worse than a rejected one."
)


def _verify(question: str, value: str, pool: list[dict], *, model: str, k: int):
    chunks = "\n".join(
        f"[{i + 1}] {h['chunk_text'][:400].strip().replace(chr(10), ' ')}"
        for i, h in enumerate(pool[:k]))
    user = f"QUESTION: {question}\n\nPROPOSED ANSWER: {value}\n\nDOCUMENTS:\n{chunks}"
    res = _complete(_VERIFY_SYSTEM, user, model=model, max_tokens=400)
    m = re.search(r"\{.*\}", res.text, re.DOTALL)
    try:
        obj = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        obj = {}
    quote = str(obj.get("quote") or "")
    # accept only if the checker says proven AND its quote actually contains the value (the
    # grounding gate: a "proof" that does not mention the value is not proof)
    proven = bool(obj.get("proven")) and bool(quote) and answer_matches(str(value), [], quote)
    return proven, quote, res


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default=os.environ.get(
            "PKM_CONFIG", str(Path("~/.config/life-agent/pkm.yaml").expanduser())))
    parser.add_argument("--model", default="claude-opus-4-8")
    parser.add_argument("--k", type=int, default=20)
    parser.add_argument("--pstar", type=float, default=0.90)
    parser.add_argument("--rerank", action="store_true",
                        help="rerank a wide lexical pool to top-k before Opus (stacks the "
                             "proven retrieval lever under the verified combiner)")
    args = parser.parse_args()

    import duckdb
    import yaml

    questions = load_questions()
    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    conn = duckdb.connect(str(Path(cfg["root_dir"]).expanduser() / "catalogue.duckdb"))
    conn.execute("INSTALL fts; LOAD fts;")
    import ask

    print(f"Opus verified-combiner: model={args.model} k={args.k} p*={args.pstar}\n")
    print(f"{'id':<8} {'conf':>5} {'proposed':>8} {'verify':>8} {'bucket':<16}")
    n_correct = n_cw = n_withheld = 0
    n_rescued = 0  # confident proposals the verify REJECTED (the sin-killer count)
    tot_in = tot_out = 0
    for q in questions:
        gold = q.get("answer", "")
        if not gold:
            continue
        variants = q.get("answer_variants", [])
        terms = ask._expand_terms(q["question"], root=ask._pkm_root())
        pool = ask._retrieve_set(conn, ask.build_query(q["question"], terms), args.k)
        obj, res = _ask_opus(q["question"], pool, model=args.model, k=args.k)
        tot_in += res.in_tokens
        tot_out += res.out_tokens
        value = obj.get("value")
        conf = float(obj.get("confidence") or 0.0) if value else 0.0
        match = bool(value) and answer_matches(gold, variants, str(value))
        proposes = bool(value) and conf >= args.pstar
        verdict = "—"
        asserts = proposes
        if proposes:
            proven, _quote, vres = _verify(q["question"], str(value), pool,
                                            model=args.model, k=args.k)
            tot_in += vres.in_tokens
            tot_out += vres.out_tokens
            verdict = "proven" if proven else "REJECT"
            asserts = proven
            if not proven:
                n_rescued += int(not match)  # a rejected WRONG proposal = a sin averted
        if asserts:
            if match:
                n_correct += 1
                bucket = "CORRECT"
            else:
                n_cw += 1
                bucket = "CONFIDENT_WRONG"
        else:
            n_withheld += 1
            bucket = "withheld(would-match)" if match else "withheld"
        print(f"{q['id']:<8} {conf:>5.2f} {('Y' if proposes else '·'):>8} "
              f"{verdict:>8} {bucket:<16}")

    n_ans = n_correct + n_cw + n_withheld
    print(f"\nAt p*={args.pstar} + verify: CORRECT {n_correct}/{n_ans} · "
          f"CONFIDENT_WRONG {n_cw} (gate: 0) · withheld {n_withheld}")
    print(f"Verify rejected {n_rescued} wrong confident proposal(s) — sins averted")
    print(f"Cost: {tot_in} in + {tot_out} out tokens (~{tot_in // max(1, n_ans)} in/question, "
          "2 calls each)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
