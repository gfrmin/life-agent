#!/usr/bin/env python3
"""Can a strong model read the retrieved documents JOINTLY and answer confidently? — the
Opus-as-combiner calibration (owner directive 2026-06-18: "increase confident correctness
with more expensive tools like opus? why not retrieve more than one document?").

The typed lookup path extracts ONE value per chunk (local Qwen) then pools by corroboration
COUNT — which the calibration sweep proved amplifies confident-wrong (the frequent-stale value
beats the rare-current one). This probe tests the alternative COMBINER: give Opus the question
+ the top-k retrieved chunks TOGETHER and ask for (value, calibrated confidence, as-of). The
SAME u_wrong gate applies (report iff confidence ≥ p*), so a confident-wrong is possible only if
Opus is MISCALIBRATED — which is the thing this measures. One row of the tool calibration table:
(full-correct lift @ 0-CW, calibration, cost).

Crucially this is NOT the monolithic synthesize path (which the §8 gate found over-asserts): the
decision is still gated, and we grade Opus's confidence against truth rather than trusting it.

Sends question + corpus snippets to the API (same boundary as synthesize). PII stays out of the
repo and console — ids, confidences, buckets only, never the values.

    ANTHROPIC_API_KEY=$(secret-tool lookup service env key ANTHROPIC_API_KEY) \\
        uv run --project . python scripts/probe_opus_answer.py [--model M] [--k N] [--pstar P]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_grading import answer_matches
from run_eval import load_questions

from life_agent.core.llm import LLMResult, secret

_SYSTEM = (
    "You answer a question about the OWNER's life STRICTLY from the provided documents. The "
    "owner asks in the first person ('my'); the documents are the owner's own (English AND "
    "Hebrew). Read ALL the documents together and return ONLY a JSON object: "
    '{"value": <the exact answer string, or null if the documents do not contain it>, '
    '"confidence": <your CALIBRATED probability 0..1 that value is the correct CURRENT answer>, '
    '"as_of": <ISO date the value is valid as-of, or null>}. '
    "ATTRIBUTION IS CRITICAL: a document may mention OTHER people (a relative, a colleague, "
    "another party in an email thread — e.g. a thread asking about a family member's passport "
    "number, or a contact's address). A value that belongs to someone ELSE is NOT the owner's "
    "answer — return null rather than assign another person's value to the owner. Only return a "
    "value the documents attribute to the OWNER. "
    "Be honest and calibrated: if the documents are stale, ambiguous, weakly supported, or you "
    "cannot tell WHOSE value it is, LOWER the confidence; a confidently WRONG answer is far "
    "worse than admitting uncertainty. Never guess a value not in the documents — return null. "
    "No prose."
)


def _complete(system: str, user: str, *, model: str, max_tokens: int) -> LLMResult:
    """Anthropic completion that omits temperature (Opus 4.8 rejects it)."""
    body = json.dumps({"model": model, "max_tokens": max_tokens, "system": system,
                       "messages": [{"role": "user", "content": user}]}).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body,
        headers={"content-type": "application/json", "x-api-key": secret("ANTHROPIC_API_KEY"),
                 "anthropic-version": "2023-06-01"})
    t0 = time.monotonic()
    with urllib.request.urlopen(req) as resp:
        data = json.load(resp)
    text = "".join(b["text"] for b in data.get("content", []) if b.get("type") == "text")
    u = data.get("usage", {})
    return LLMResult(text, u.get("input_tokens", 0), u.get("output_tokens", 0),
                     time.monotonic() - t0)


def _ask_opus(question: str, pool: list[dict], *, model: str, k: int):
    chunks = "\n".join(
        f"[{i + 1}] {h['chunk_text'][:400].strip().replace(chr(10), ' ')}"
        for i, h in enumerate(pool[:k]))
    user = f"QUESTION: {question}\n\nDOCUMENTS:\n{chunks}"
    res = _complete(_SYSTEM, user, model=model, max_tokens=400)
    m = re.search(r"\{.*\}", res.text, re.DOTALL)
    try:
        obj = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        obj = {}
    return obj, res


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default=os.environ.get(
            "PKM_CONFIG", str(Path("~/.config/life-agent/pkm.yaml").expanduser())))
    parser.add_argument("--model", default="claude-opus-4-8")
    parser.add_argument("--k", type=int, default=20, help="documents read jointly")
    parser.add_argument("--pstar", type=float, default=0.90, help="assert iff confidence >= p*")
    args = parser.parse_args()

    import duckdb
    import yaml

    questions = load_questions()
    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    db_path = Path(cfg["root_dir"]).expanduser() / "catalogue.duckdb"
    conn = duckdb.connect(str(db_path))
    conn.execute("INSTALL fts; LOAD fts;")

    import ask

    print(f"Opus-joint-answer probe: model={args.model} k={args.k} p*={args.pstar}\n")
    print(f"{'id':<8} {'conf':>5} {'match':>5} {'bucket':<16} tok(in/out)")
    n_correct = n_cw = n_withheld = 0
    n_conf = n_conf_right = n_right = 0   # calibration tallies
    tot_in = tot_out = 0
    for q in questions:
        gold = q.get("answer", "")
        if not gold:
            continue
        variants = q.get("answer_variants", [])
        terms = ask._expand_terms(q["question"], root=ask._pkm_root())
        query = ask.build_query(q["question"], terms)
        pool = ask._retrieve_set(conn, query, args.k)
        obj, res = _ask_opus(q["question"], pool, model=args.model, k=args.k)
        tot_in += res.in_tokens
        tot_out += res.out_tokens
        value = obj.get("value")
        conf = float(obj.get("confidence") or 0.0) if value else 0.0
        match = bool(value) and answer_matches(gold, variants, str(value))
        n_right += int(match)
        asserts = bool(value) and conf >= args.pstar
        if asserts:
            n_conf += 1
            n_conf_right += int(match)
            if match:
                n_correct += 1
                bucket = "CORRECT"
            else:
                n_cw += 1
                bucket = "CONFIDENT_WRONG"
        else:
            n_withheld += 1
            # Opus right but under p* = under-confident (a calibration/coverage loss, not a sin)
            bucket = "withheld(would-match)" if match else "withheld"
        print(f"{q['id']:<8} {conf:>5.2f} {'✓' if match else '·':>5} {bucket:<16} "
              f"{res.in_tokens}/{res.out_tokens}")

    n_ans = n_correct + n_cw + n_withheld
    print(f"\nAt p*={args.pstar}: CORRECT {n_correct}/{n_ans} · CONFIDENT_WRONG {n_cw} (gate: 0) "
          f"· withheld {n_withheld}")
    if n_conf:
        print(f"Calibration: of {n_conf} confident (≥p*) answers, {n_conf_right} right "
              f"({100 * n_conf_right / n_conf:.0f}%) — the confident-wrong risk")
    print(f"Opus right on {n_right}/{n_ans} regardless of confidence "
          f"(the ceiling if perfectly calibrated)")
    print(f"Cost: {tot_in} in + {tot_out} out tokens (~{tot_in // max(1, n_ans)} in/question)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
