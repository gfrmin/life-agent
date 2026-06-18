#!/usr/bin/env python3
"""Does an LLM reranker pull the buried golds into the top-k? — the retrieval-lift ceiling.

probe_gold_rank showed 8 retrieval_misses sit at lexical rank 21-200: in the over-fetch
pool, ranked out of the top-k. A reranker is the candidate fix. This probe measures its
CEILING in isolation (pure retrieval recall, decoupled from extraction/decision): over the
wide lexical pool, an LLM listwise-selects the top-k most relevant chunks; we check whether
the gold-bearing chunk made that cut, and meter the token cost.

It is a recall measurement, NOT the gate: a reranker that surfaces the gold may also surface
a distractor extraction then asserts (a confident-wrong). That is measured downstream by the
full triage path. This answers only the precondition: is the lift even there, and what does
it cost — one row of the tool/transform calibration table (owner directive, 2026-06-18).

Sends question + corpus snippets to the model API — the same boundary the synthesize path
already crosses (ask.py → anthropic_complete). PII stays out of the repo and console (ids +
ranks only).

    ANTHROPIC_API_KEY=$(secret-tool lookup service env key ANTHROPIC_API_KEY) \\
        uv run --project . python scripts/probe_rerank_recall.py [--model M] [--pool N] [--k N]
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
from eval_grading import chunk_matches_any
from run_eval import _kb_root, load_questions

from life_agent.core.llm import LLMResult, secret


def _complete(system: str, user: str, *, model: str, max_tokens: int) -> LLMResult:
    """Anthropic completion that OMITS temperature — Opus 4.8 rejects the field the shared
    llm.anthropic_complete always sends (a real gap there; kept local to this probe)."""
    body = json.dumps({"model": model, "max_tokens": max_tokens,
                       "system": system,
                       "messages": [{"role": "user", "content": user}]}).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body,
        headers={"content-type": "application/json",
                 "x-api-key": secret("ANTHROPIC_API_KEY"),
                 "anthropic-version": "2023-06-01"})
    t0 = time.monotonic()
    with urllib.request.urlopen(req) as resp:
        data = json.load(resp)
    text = "".join(b["text"] for b in data.get("content", []) if b.get("type") == "text")
    u = data.get("usage", {})
    return LLMResult(text, u.get("input_tokens", 0), u.get("output_tokens", 0),
                     time.monotonic() - t0)

_RERANK_SYSTEM = (
    "You are a retrieval reranker. Given a QUESTION and a numbered list of document "
    "SNIPPETS, identify the snippets most likely to contain the exact fact needed to "
    "answer the question. Prefer the specific, current, authoritative source over generic "
    "or incidental mentions. Return ONLY a JSON array of the {k} most relevant snippet "
    "numbers, best first — no prose."
)


def _gold_rank(pool: list[dict], gold: str, variants: list[str]) -> int | None:
    for i, h in enumerate(pool):
        if chunk_matches_any(gold, variants, [h["chunk_text"]]):
            return i + 1
    return None


def _rerank(question: str, pool: list[dict], *, model: str, k: int):
    """Listwise top-k selection over the pool. Returns (selected 1-based ranks, LLMResult)."""
    snippets = "\n".join(
        f"[{i + 1}] {h['chunk_text'][:280].strip().replace(chr(10), ' ')}"
        for i, h in enumerate(pool))
    user = f"QUESTION: {question}\n\nSNIPPETS:\n{snippets}"
    res = _complete(_RERANK_SYSTEM.format(k=k), user, model=model, max_tokens=400)
    m = re.search(r"\[[\s\d,]*\]", res.text)
    picks = [int(n) for n in re.findall(r"\d+", m.group(0))] if m else []
    return picks[:k], res


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default=os.environ.get(
            "PKM_CONFIG", str(Path("~/.config/life-agent/pkm.yaml").expanduser())))
    parser.add_argument("--model", default="claude-opus-4-8", help="reranker model")
    parser.add_argument("--pool", type=int, default=150)
    parser.add_argument("--k", type=int, default=20)
    parser.add_argument("--only-miss", action="store_true",
                        help="rerank only the current retrieval_miss rows (cheaper)")
    args = parser.parse_args()

    import duckdb
    import yaml

    questions = load_questions()
    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    db_path = Path(cfg["root_dir"]).expanduser() / "catalogue.duckdb"
    conn = duckdb.connect(str(db_path))
    conn.execute("INSTALL fts; LOAD fts;")

    import ask

    triage_path = _kb_root() / "eval" / "triage" / "triage.jsonl"
    cause = {}
    if triage_path.exists():
        for line in triage_path.read_text(encoding="utf-8").splitlines():
            p = json.loads(line)
            cause[p["id"]] = p.get("cause") or ""

    print(f"Rerank-recall probe: model={args.model} pool={args.pool} k={args.k}\n")
    print(f"{'id':<8} {'cause':<15} {'lex':>5} {'rr':>5}  {'rescued':<8} tok(in/out)")
    n_addr = n_rescued = n_kept = n_lost = 0
    tot_in = tot_out = 0
    for q in questions:
        gold = q.get("answer", "")
        if not gold:
            continue
        c = cause.get(q["id"], "")
        if args.only_miss and c != "retrieval_miss":
            continue
        variants = q.get("answer_variants", [])
        terms = ask._expand_terms(q["question"], root=ask._pkm_root())
        query = ask.build_query(q["question"], terms)
        pool = ask._retrieve_set(conn, query, args.pool)
        lex = _gold_rank(pool, gold, variants)
        if lex is None:
            print(f"{q['id']:<8} {c:<15} {'—':>5} {'—':>5}  {'beyond':<8}")
            continue
        picks, res = _rerank(q["question"], pool, model=args.model, k=args.k)
        tot_in += res.in_tokens
        tot_out += res.out_tokens
        # the gold's NEW rank among the reranker's ordered picks (if any pool chunk
        # carrying gold was picked) — use the best-ranked gold-bearing pick
        gold_idxs = {i + 1 for i, h in enumerate(pool)
                     if chunk_matches_any(gold, variants, [h["chunk_text"]])}
        picked_gold = [pos for pos, n in enumerate(picks, 1) if n in gold_idxs]
        rr = picked_gold[0] if picked_gold else None
        rescued = "—"
        if lex > args.k:
            n_addr += 1
            if rr is not None:
                n_rescued += 1
                rescued = "RESCUED"
        elif rr is not None:
            n_kept += 1
            rescued = "kept"
        else:
            n_lost += 1
            rescued = "LOST"
        rr_s = str(rr) if rr is not None else "out"
        print(f"{q['id']:<8} {c:<15} {lex:>5} {rr_s:>5}  {rescued:<8} "
              f"{res.in_tokens}/{res.out_tokens}")

    print(f"\nReranker recall: rescued {n_rescued}/{n_addr} addressable misses · "
          f"kept {n_kept} already-retrieved · LOST {n_lost} (regression risk)")
    print(f"Cost: {tot_in} in + {tot_out} out tokens "
          f"(~{tot_in // max(1, n_addr + n_kept + n_lost)} in/question)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
