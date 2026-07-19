#!/usr/bin/env python3
"""``scripts/eval_factory/factory.py`` — the verified question factory (roadmap A2).

Grows the eval corpus past the 21 hand-authored questions (debt D3) without the owner in
the authoring loop: a **generator** model proposes point-fact questions from stratified
corpus chunks, and an **independent verifier** must re-derive each gold from the corpus
before a question is admitted. The owner audits a seeded sample, one bit per row.

**The anti-circularity protocol** (eval-rigor memory: no circular gold sets):

1. **Propose.** The generator sees ONE chunk (+ its source path) and proposes a question
   whose answer is a value in that chunk — or skips. Its output is a strict-JSON object.
2. **Ground.** Two mechanical gates: the proposed gold must be token-present in the
   source chunk (``core.matching.answer_matches`` against the chunk text — a hallucinated
   gold never reaches verification), and must NOT be quoted in the question text itself —
   a self-quoting question ("what is my policy number P111222?") would smuggle the gold
   into the verifier's retrieval query AND its prompt's QUESTION line, so "independent"
   verification would never actually occur (rejected as ``gold_in_question``).
3. **Dedup.** Normalised question text must be new for this run.
4. **Verify (independent).** The verifier receives ONLY the question text; it retrieves
   its own top-k over the SAME pkm FTS surface the answer arms use
   (``pkm.retrieval.search``) and answers from that context alone — it never sees the
   generator's chunk, gold, or provenance. Admission iff its answer token-matches the
   gold (or a declared variant). ``NOT_FOUND`` or a mismatch rejects the question.

Every rejection is counted by reason; the report prints admission rates per stage —
silent truncation would read as coverage.

**What v1 deliberately does not do (on the page, not hidden):** unanswerable-by-
construction questions (a verifier's failure to answer cannot certify absence — needs a
different protocol); per-value dedup caps; date-stratified sampling (v1 stratifies by
``source_origin`` only). Each is a named follow-up, not an accident.

**Outputs (all under the out dir, PII fail-closed — corpus content never leaves
``$LIFE_AGENT_KB``):** ``questions_v2.yaml`` (the candidate corpus: id ``q2-NNN``,
question/subject/answer/answer_variants/notes + ``provenance`` {chunk_id, source_path}
+ ``audit: true`` on a seeded ~10% owner-audit sample), ``factory_meta.json`` (models,
prompt shas, seeds, counts, cost), ``report.md`` (the human summary + the audit list).
The canonical ``$LIFE_AGENT_KB/eval/questions_v2.yaml`` is only written under
``--publish`` — a run is inspectable before it becomes the corpus. The owner-authored
``questions.yaml`` is never touched.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

import pkm.retrieval as R
from life_agent.core import llm as LLM
from life_agent.core import pricing as PRICING
from life_agent.core.matching import answer_matches

FORMAT_VERSION = 1

# Frozen prompt contracts — sha256 of each goes into factory_meta.json; editing wording is
# a NEW version, never an in-place edit (the arm_hermes PROMPT_V1 discipline).
PROPOSER_V1 = """You write evaluation questions for a personal-records question-answering \
system. You are given ONE text chunk from the owner's private corpus, with its source path.

Propose at most ONE point-fact question about it, as strict JSON (no prose, no fences):
{"question": "...", "answer": "...", "answer_variants": ["..."], "subject": "...", \
"notes": "..."}

Rules, in order of importance:
- The answer MUST be a short factual value (a number, date, ID, name, amount) that appears \
VERBATIM in the chunk. Never invent, reformat-only variants go in answer_variants.
- Only ask about a fact whose OWNER is clear. If the fact belongs to the corpus owner, \
phrase the question in their voice ("What is my ...?"). If it belongs to someone or \
something else, name the subject explicitly in the question. Set "subject" to who/what \
the fact is about.
- The question must be answerable from records alone, unambiguous, and likely to have \
exactly this one answer (not a list, not an opinion, not something that changes daily).
- "answer_variants": other formats of the SAME value a grader should accept (with/without \
leading zeros, separators, date formats). Empty list if none.
- "notes": one line on where in the chunk the answer sits.
- If the chunk contains no suitable fact (boilerplate, navigation, fragments, tables of \
someone else's data you cannot attribute), reply exactly: {"skip": true}

SOURCE PATH: {source_path}

CHUNK:
{chunk}"""

VERIFIER_V1 = """You answer ONE question about the owner's personal records from the \
retrieved context below — and nothing else. Never use outside knowledge.

- If the context contains the answer, reply with the exact value ONLY (no sentence, no \
citation, no punctuation beyond the value itself).
- If it does not, reply exactly: NOT_FOUND

QUESTION: {question}

CONTEXT:
{context}"""

_NOT_FOUND_RE = re.compile(r"^not[_\s-]?found\b", re.IGNORECASE)

# complete(system, user) -> the model's text. Injected so tests never touch a network.
Complete = Callable[[str, str], str]


def _fill(template: str, mapping: dict[str, str]) -> str:
    """Single-pass placeholder substitution. Chained ``str.replace`` re-scans substituted
    content, so LLM/corpus text containing a literal ``{context}``/``{question}`` would be
    expanded on the next pass — one regex scan closes that injection class."""
    return re.sub(r"\{(" + "|".join(map(re.escape, mapping)) + r")\}",
                  lambda m: mapping[m.group(1)], template)


@dataclass(frozen=True)
class Admitted:
    """One verified question, ready for questions_v2.yaml."""

    question: str
    answer: str
    answer_variants: tuple[str, ...]
    subject: str
    notes: str
    chunk_id: int
    source_path: str
    source_origin: str | None
    verifier_answer: str


@dataclass
class FactoryResult:
    admitted: list[Admitted] = field(default_factory=list)
    rejections: Counter = field(default_factory=Counter)
    n_proposal_calls: int = 0
    n_verify_calls: int = 0


# --- sampling (read-only; path-current only, same rule as retrieval) -----------------------

def sample_chunks(conn: Any, *, min_chars: int, limit: int, seed: int) -> list[dict[str, Any]]:
    """Stratified sample of path-current chunks: round-robin over ``source_origin`` strata
    (seeded shuffle within each), so one dominant origin (mail) cannot crowd out the rest.
    Reuses retrieval's own path-currency CTE — the factory must never write questions
    against a superseded document version (the arm could then never retrieve the gold)."""
    rows = conn.execute(
        f"""
        WITH {R._PATH_CURRENT_CTE}
        SELECT c.chunk_id, c.chunk_text, c.source_origin, s.current_path
        FROM artifact_chunks c
        JOIN artifacts a ON c.artifact_cache_key = a.cache_key
        JOIN sources s ON a.input_hash = s.source_id
        JOIN path_current pc ON s.source_id = pc.source_id
        WHERE length(c.chunk_text) >= ?
        ORDER BY c.chunk_id
        """,
        [min_chars],
    ).fetchall()
    rng = random.Random(seed)
    strata: dict[str, list[dict[str, Any]]] = {}
    for chunk_id, chunk_text, origin, path in rows:
        strata.setdefault(str(origin), []).append(
            {"chunk_id": int(chunk_id), "chunk_text": str(chunk_text),
             "source_origin": origin, "source_path": str(path)})
    for members in strata.values():
        rng.shuffle(members)
    # round-robin across strata (stable order over stratum names) until `limit`
    out: list[dict[str, Any]] = []
    queues = [strata[name] for name in sorted(strata)]
    while queues and len(out) < limit:
        queues = [q for q in queues if q]
        for q in list(queues):
            if len(out) >= limit:
                break
            out.append(q.pop())
    return out


# --- propose + verify (pure over injected `complete` callables) ----------------------------

def _parse_json(text: str) -> dict[str, Any] | None:
    """Strict-JSON parse with fence tolerance; None on anything else."""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        obj = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def propose(chunk: dict[str, Any], complete: Complete) -> dict[str, Any] | None:
    """One proposal for one chunk: the parsed JSON dict, ``{"skip": true}``, or None on a
    malformed reply (counted, never raised)."""
    user = _fill(PROPOSER_V1,
                 {"source_path": chunk["source_path"], "chunk": chunk["chunk_text"]})
    return _parse_json(complete("You emit strict JSON only.", user))


def _normalise_question(q: str) -> str:
    return re.sub(r"[^\w]+", " ", q.lower()).strip()


def verify(question: str, answer: str, variants: list[str], conn: Any,
           complete: Complete, *, k: int) -> tuple[bool, str]:
    """The independent re-derivation: retrieve top-k for the QUESTION TEXT ONLY, answer
    from that context, admit iff the answer token-matches the gold. Returns
    ``(admitted, verifier_answer)``."""
    hits = R.search(conn, question, k=k)
    if not hits:
        return False, ""
    context = "\n\n".join(
        f"[{i + 1}] ({h.source_path})\n{h.chunk_text}" for i, h in enumerate(hits))
    reply = complete(
        "You answer from the provided context only.",
        _fill(VERIFIER_V1, {"question": question, "context": context}),
    ).strip()
    if not reply or _NOT_FOUND_RE.match(reply):
        return False, reply
    return answer_matches(answer, variants, reply), reply


def run_factory(conn: Any, propose_complete: Complete, verify_complete: Complete, *,
                target: int, max_proposals: int, k: int, min_chars: int,
                seed: int) -> FactoryResult:
    """The admission pipeline: sample → propose → ground → dedup → verify, until
    ``target`` admitted or ``max_proposals`` generator calls spent (the cost ceiling)."""
    chunks = sample_chunks(conn, min_chars=min_chars, limit=max_proposals, seed=seed)
    result = FactoryResult()
    seen_questions: set[str] = set()

    for chunk in chunks:
        if len(result.admitted) >= target or result.n_proposal_calls >= max_proposals:
            break
        result.n_proposal_calls += 1
        obj = propose(chunk, propose_complete)
        if obj is None:
            result.rejections["parse_error"] += 1
            continue
        if obj.get("skip"):
            result.rejections["skip"] += 1
            continue
        question = str(obj.get("question", "")).strip()
        answer = str(obj.get("answer", "")).strip()
        raw_variants = obj.get("answer_variants") or []
        if not isinstance(raw_variants, list):
            # a bare string here would iterate CHARACTERS into single-char "variants" —
            # eval-corpus contamination; the strict-JSON contract was violated, reject.
            result.rejections["parse_error"] += 1
            continue
        variants = [str(v) for v in raw_variants]
        if not question or not answer:
            result.rejections["parse_error"] += 1
            continue
        if answer_matches(answer, variants, question):
            # the question quotes its own gold: FTS on the question text would rank the
            # source chunk by the smuggled token and the verifier could read the answer
            # off its own QUESTION line — "independent" verification never happens.
            # The protocol's Critical hole (PR-29 review); mechanically gated out.
            result.rejections["gold_in_question"] += 1
            continue
        if not answer_matches(answer, variants, chunk["chunk_text"]):
            result.rejections["ungrounded"] += 1  # the gold is NOT in its own chunk
            continue
        norm = _normalise_question(question)
        if norm in seen_questions:
            result.rejections["duplicate"] += 1
            continue
        seen_questions.add(norm)
        result.n_verify_calls += 1
        ok, verifier_answer = verify(question, answer, variants, conn, verify_complete, k=k)
        if not ok:
            result.rejections["not_verified"] += 1
            continue
        result.admitted.append(Admitted(
            question=question, answer=answer, answer_variants=tuple(variants),
            subject=str(obj.get("subject", "")), notes=str(obj.get("notes", "")),
            chunk_id=int(chunk["chunk_id"]), source_path=chunk["source_path"],
            source_origin=chunk["source_origin"], verifier_answer=verifier_answer))
    return result


# --- outputs -------------------------------------------------------------------------------

def questions_yaml_dict(result: FactoryResult, *, audit_fraction: float,
                        seed: int) -> dict[str, Any]:
    """The questions_v2 corpus as a dict (ids ``q2-NNN`` in admission order; a seeded
    ~``audit_fraction`` sample carries ``audit: true`` — the owner's one-bit queue)."""
    rng = random.Random(seed)
    n_audit = max(1, round(len(result.admitted) * audit_fraction)) if result.admitted else 0
    audit_idx = set(rng.sample(range(len(result.admitted)), n_audit)) if n_audit else set()
    questions = []
    for i, a in enumerate(result.admitted):
        q: dict[str, Any] = {
            "id": f"q2-{i + 1:03d}",
            "question": a.question,
            "subject": a.subject,
            "answer": a.answer,
            "answer_variants": list(a.answer_variants),
            "notes": a.notes,
            "provenance": {"chunk_id": a.chunk_id, "source_path": a.source_path,
                           "source_origin": a.source_origin,
                           "verifier_answer": a.verifier_answer},
        }
        if i in audit_idx:
            q["audit"] = True
        questions.append(q)
    return {"format_version": FORMAT_VERSION, "questions": questions}


def report_md(result: FactoryResult, corpus: dict[str, Any], *, cost_usd: float | None) -> str:
    audit_rows = [q for q in corpus["questions"] if q.get("audit")]
    lines = [
        "# Question factory report",
        "",
        f"- admitted: **{len(result.admitted)}**  ·  generator calls: "
        f"{result.n_proposal_calls}  ·  verifier calls: {result.n_verify_calls}",
        f"- rejections: {dict(sorted(result.rejections.items()))}",
        f"- cost: {f'${cost_usd:.2f}' if cost_usd is not None else 'unmetered'}",
        "",
        "Every admitted question passed: grounding (gold token-present in its source "
        "chunk), dedup, and INDEPENDENT verification (the verifier saw only the question, "
        "retrieved its own top-k, and re-derived the gold).",
        "",
        f"## Owner audit sample ({len(audit_rows)} rows — one bit each: g/b)",
        "",
    ]
    for q in audit_rows:
        lines += [f"- **{q['id']}** {q['question']}  →  `{q['answer']}`  "
                  f"({q['provenance']['source_path']})"]
    lines += [
        "",
        "_v1 limitations (named, not hidden): answerable questions only "
        "(unanswerable-by-construction needs a different protocol); question-text dedup "
        "only; origin-stratified sampling only._",
    ]
    return "\n".join(lines) + "\n"


def write_outputs(out_dir: Path, result: FactoryResult, corpus: dict[str, Any],
                  meta: dict[str, Any], *, cost_usd: float | None) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "questions_v2.yaml").write_text(
        yaml.safe_dump(corpus, sort_keys=False, allow_unicode=True), encoding="utf-8")
    (out_dir / "factory_meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "report.md").write_text(
        report_md(result, corpus, cost_usd=cost_usd), encoding="utf-8")
    return out_dir / "questions_v2.yaml"


# --- CLI -----------------------------------------------------------------------------------

def _kb_root() -> Path:
    # the ONE canonical KB-root resolution (env + default) — never a path literal here
    from life_agent.core.config import KB
    return KB


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="pkm config.yaml (for the catalogue)")
    parser.add_argument("--target", type=int, default=100)
    parser.add_argument("--max-proposals", type=int, default=400,
                        help="generator-call ceiling (the cost bound)")
    parser.add_argument("--k", type=int, default=20, help="verifier retrieval depth")
    parser.add_argument("--min-chars", type=int, default=200)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--audit-fraction", type=float, default=0.10)
    parser.add_argument("--propose-model", default="claude-sonnet-4-6")
    parser.add_argument("--verify-model", default="claude-sonnet-4-6")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--publish", action="store_true",
                        help="ALSO overwrite $LIFE_AGENT_KB/eval/questions_v2.yaml (default: "
                             "run-dir only, inspect before it becomes the corpus)")
    args = parser.parse_args(argv)

    import duckdb

    cfg = yaml.safe_load(Path(args.config).expanduser().read_text(encoding="utf-8"))
    db_path = Path(cfg["root_dir"]).expanduser() / "catalogue.duckdb"
    conn = duckdb.connect(str(db_path), read_only=True)  # NEVER RW — pkm serve coexists
    conn.execute("INSTALL fts; LOAD fts;")

    def _propose_complete(system: str, user: str) -> str:
        return LLM.anthropic_complete(system, user, model=args.propose_model).text

    def _verify_complete(system: str, user: str) -> str:
        return LLM.anthropic_complete(system, user, model=args.verify_model).text

    LLM.reset_meter()
    try:
        result = run_factory(conn, _propose_complete, _verify_complete,
                             target=args.target, max_proposals=args.max_proposals,
                             k=args.k, min_chars=args.min_chars, seed=args.seed)
    finally:
        conn.close()
    calls = LLM.meter_read()
    priced = [c for c in (PRICING.cost_usd(r) for r in calls) if c is not None]
    cost = sum(priced) if priced else None

    corpus = questions_yaml_dict(result, audit_fraction=args.audit_fraction, seed=args.seed)
    from datetime import UTC, datetime
    run_id = args.run_id or f"factory-{datetime.now(UTC):%Y%m%dT%H%M%SZ}"
    meta = {
        "format_version": FORMAT_VERSION,
        "run_id": run_id,
        "target": args.target, "max_proposals": args.max_proposals, "k": args.k,
        "min_chars": args.min_chars, "seed": args.seed,
        "audit_fraction": args.audit_fraction,
        "propose_model": args.propose_model, "verify_model": args.verify_model,
        "proposer_prompt_sha256": hashlib.sha256(PROPOSER_V1.encode()).hexdigest(),
        "verifier_prompt_sha256": hashlib.sha256(VERIFIER_V1.encode()).hexdigest(),
        "n_admitted": len(result.admitted),
        "n_proposal_calls": result.n_proposal_calls,
        "n_verify_calls": result.n_verify_calls,
        "rejections": dict(result.rejections),
        "cost_usd": cost,
        "pricing_version": PRICING.PRICING_VERSION,
    }
    out_dir = _kb_root() / "eval" / "factory" / run_id
    ypath = write_outputs(out_dir, result, corpus, meta, cost_usd=cost)
    print(f"factory run {run_id}: admitted {len(result.admitted)} "
          f"(proposals {result.n_proposal_calls}, rejections {dict(result.rejections)}, "
          f"cost {f'${cost:.2f}' if cost is not None else 'unmetered'})")
    print(ypath)
    if args.publish:
        canonical = _kb_root() / "eval" / "questions_v2.yaml"
        canonical.write_text(ypath.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"published → {canonical}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
