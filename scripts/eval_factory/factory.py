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

**v1.1 (2026-07-19, deliberative-audit findings):** three more mechanical gates —
``subject_voice`` (a first-person question whose fact belongs to a third party, the
q2-084 class), ``multi_slot`` (two interrogative clauses, one gold — the q2-007 class),
``source_cap`` (admissions per source_path bounded, the CSV-trivia class) — plus
``--merge`` (combine chunked runs: cross-run dedup, re-id, fresh audit sample).

**What this deliberately does not do (on the page, not hidden):** unanswerable-by-
construction questions (a verifier's failure to answer cannot certify absence — needs a
different protocol); date-stratified sampling (stratifies by ``source_origin`` only).
The regex gates are nets, not proofs: first-person detection still trips on a
roman-numeral "I" (fails safe — a rejection); the compound-question net catches
repeated interrogatives and slot-noun pairs across an "and", but a compound built from
nouns outside the slot-noun list, or two sentences joined by punctuation, passes to the
verifier. Each is a named follow-up, not an accident.

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
PROPOSER_V2 = """You write evaluation questions for a personal-records question-answering \
system. You are given ONE text chunk from the owner's private corpus, with its source path.

Propose at most ONE point-fact question about it, as strict JSON (no prose, no fences):
{"question": "...", "answer": "...", "answer_variants": ["..."], "subject": "...", \
"notes": "..."}

Rules, in order of importance:
- The answer MUST be a short factual value (a number, date, ID, name, amount) that appears \
VERBATIM in the chunk. Never invent, reformat-only variants go in answer_variants.
- Only ask about a fact whose OWNER is clear. If the fact belongs to the corpus owner, \
phrase the question in their voice ("What is my ...?") and set "subject" to exactly \
"owner". If it belongs to someone or something else, name that subject explicitly in the \
question, never use first-person phrasing, and set "subject" to the named third party.
- Ask about exactly ONE fact — one value slot. Never join two asks in one question \
("... and when ...", "... and how much ...").
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

# v1.1 gates (deliberative-audit findings 2026-07-19). Each mechanical check is the
# enforcement half of a PROPOSER_V2 contract line — prompt and gate move together.
SUBJECT_OWNER = "owner"
# "us" is case-SENSITIVE lowercase (PR-32 review: "US visa/bank/dollar" is common in a
# finance corpus and would false-fire the gate); "I" exact-case (bare lowercase "i" is
# not first person in edited text). Residual named edge: roman-numeral "I" ("Chapter I")
# still trips — the gate fails safe (a rejection, never contamination).
_FIRST_PERSON_RE = re.compile(r"\b(?:[Mm]y|[Mm]ine|[Mm]e|[Ww]e|[Oo]ur|I|us)\b")
# an interrogative that OPENS a clause (start of question, or after and/or/comma) marks a
# value slot; a relative "who/which" mid-phrase does not.
_SLOT_RE = re.compile(
    r"(?:^|\b(?:and|or)\b|,)\s*(what|when|who|whom|whose|which|where|why|how)\b",
    re.IGNORECASE)
# the single-wh two-noun-phrase compound ("what is the policy number and effective
# date?"): two DIFFERENT slot-typed nouns joined across an "and" is a second value slot
# even with one interrogative (PR-32 review Important-2). List-based, so imperfect by
# construction — the miss class is named in the module docstring.
_SLOT_NOUN = (r"\b(number|date|amount|total|balance|name|id|code|address|email|phone|"
              r"value|price|cost|rate|currency|term|duration)\b")
_SLOT_NOUN_RE = re.compile(_SLOT_NOUN, re.IGNORECASE)
_AND_RE = re.compile(r"\band\b", re.IGNORECASE)


def _is_first_person(question: str) -> bool:
    return _FIRST_PERSON_RE.search(question) is not None


def _slot_count(question: str) -> int:
    n = len(_SLOT_RE.findall(question))
    and_m = _AND_RE.search(question)
    if n < 2 and and_m:
        before = {m.lower() for m in _SLOT_NOUN_RE.findall(question[: and_m.start()])}
        after = {m.lower() for m in _SLOT_NOUN_RE.findall(question[and_m.end():])}
        if before and after and (before != after or len(before | after) > 1):
            n = max(n, 2)
    return n

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
    user = _fill(PROPOSER_V2,
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
                seed: int, per_source_cap: int = 2) -> FactoryResult:
    """The admission pipeline: sample → propose → ground + v1.1 gates → dedup → source
    cap → verify, until ``target`` admitted or ``max_proposals`` generator calls spent
    (the cost ceiling). ``per_source_cap`` bounds admissions per source_path (0 =
    uncapped) — the CSV-trivia guard: one dense file must not fill the corpus."""
    chunks = sample_chunks(conn, min_chars=min_chars, limit=max_proposals, seed=seed)
    result = FactoryResult()
    seen_questions: set[str] = set()
    admitted_per_source: Counter = Counter()

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
        subject = str(obj.get("subject", "")).strip()
        if _is_first_person(question) and subject.lower() != SUBJECT_OWNER:
            # the q2-084 class: a first-person question about a third party's fact reads
            # the owner's voice onto someone else's record — the gold then grades a
            # question the corpus never supports.
            result.rejections["subject_voice"] += 1
            continue
        if _slot_count(question) >= 2:
            # two interrogative clauses = two value slots; a single gold cannot grade a
            # compound question (the q2-007 class).
            result.rejections["multi_slot"] += 1
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
        if per_source_cap and admitted_per_source[chunk["source_path"]] >= per_source_cap:
            result.rejections["source_cap"] += 1
            continue
        result.n_verify_calls += 1
        ok, verifier_answer = verify(question, answer, variants, conn, verify_complete, k=k)
        if not ok:
            result.rejections["not_verified"] += 1
            continue
        admitted_per_source[chunk["source_path"]] += 1
        result.admitted.append(Admitted(
            question=question, answer=answer, answer_variants=tuple(variants),
            subject=subject, notes=str(obj.get("notes", "")),
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


def merge_corpora(corpora: list[tuple[str, dict[str, Any]]], *, seed: int,
                  audit_fraction: float) -> tuple[dict[str, Any], dict[str, Any]]:
    """Merge chunked factory runs into one corpus (the in-repo replacement for the
    2026-07-19 one-off scratchpad merge, for the nightly loop): cross-run dedup on
    normalised question text OR the (answer, source_path) pair (same fact re-asked in
    other words), sequential ``q2-NNN`` ids, per-question ``provenance.factory_run``
    tag, and a FRESH seeded audit sample over the merged set (inherited flags dropped —
    the owner audits the corpus that ships, not the chunks). Returns
    ``(merged_corpus, merge_meta)``."""
    merged: list[dict[str, Any]] = []
    seen_q: set[str] = set()
    seen_pair: set[tuple[str, str]] = set()
    dropped = 0
    kept_per_run: dict[str, int] = {}
    for run_name, corpus in corpora:
        kept = 0
        for q in corpus["questions"]:
            key_q = _normalise_question(str(q["question"]))
            key_pair = (str(q["answer"]), str(q["provenance"]["source_path"]))
            if key_q in seen_q or key_pair in seen_pair:
                dropped += 1
                continue
            seen_q.add(key_q)
            seen_pair.add(key_pair)
            merged_q = dict(q)
            merged_q.pop("audit", None)  # re-drawn over the merged set below
            merged_q["provenance"] = dict(q["provenance"])
            # no aliasing into the inputs (PR-32 review: the nightly loop may reuse
            # corpus objects in-process — a shared list would let a later mutation
            # reach back into a source corpus)
            merged_q["answer_variants"] = list(q.get("answer_variants") or [])
            merged_q["provenance"]["factory_run"] = run_name
            merged.append(merged_q)
            kept += 1
        kept_per_run[run_name] = kept
    for i, q in enumerate(merged):
        q["id"] = f"q2-{i + 1:03d}"
    rng = random.Random(seed)
    n_audit = max(1, round(len(merged) * audit_fraction)) if merged else 0
    for i in (rng.sample(range(len(merged)), n_audit) if n_audit else []):
        merged[i]["audit"] = True
    meta = {
        "runs": [name for name, _ in corpora],
        "kept_per_run": kept_per_run,
        "n_merged": len(merged),
        "n_dropped_duplicates": dropped,
        "audit_fraction": audit_fraction,
        "n_audit": n_audit,
        "seed": seed,
    }
    return {"format_version": FORMAT_VERSION, "questions": merged}, meta


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
        "_Limitations (named, not hidden): answerable questions only "
        "(unanswerable-by-construction needs a different protocol); origin-stratified "
        "sampling only; cross-run dedup happens at --merge, not here._",
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


def _run_merge(args: argparse.Namespace) -> int:
    """The --merge mode: no generation, no models, no catalogue — read the named run
    dirs' corpora, merge, write a run dir of its own (+ --publish like a generation run)."""
    from datetime import UTC, datetime

    corpora: list[tuple[str, dict[str, Any]]] = []
    for d in args.merge:
        path = Path(d).expanduser() / "questions_v2.yaml"
        if not path.exists():
            print(f"MISSING {path} — aborting so nothing partial is written")
            return 1
        corpora.append((Path(d).name, yaml.safe_load(path.read_text(encoding="utf-8"))))
    merged, meta = merge_corpora(corpora, seed=args.seed,
                                 audit_fraction=args.audit_fraction)
    run_id = args.run_id or f"factory-merged-{datetime.now(UTC):%Y%m%dT%H%M%SZ}"
    out_dir = _kb_root() / "eval" / "factory" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    ypath = out_dir / "questions_v2.yaml"
    ypath.write_text(yaml.safe_dump(merged, sort_keys=False, allow_unicode=True),
                     encoding="utf-8")
    (out_dir / "merge_meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"merge {run_id}: {meta['n_merged']} merged "
          f"(dropped {meta['n_dropped_duplicates']} dupes; per-run {meta['kept_per_run']}; "
          f"audit sample {meta['n_audit']})")
    print(ypath)
    if args.publish:
        canonical = _kb_root() / "eval" / "questions_v2.yaml"
        canonical.write_text(ypath.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"published → {canonical}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None,
                        help="pkm config.yaml (for the catalogue); required unless --merge")
    parser.add_argument("--target", type=int, default=100)
    parser.add_argument("--max-proposals", type=int, default=400,
                        help="generator-call ceiling (the cost bound)")
    parser.add_argument("--k", type=int, default=20, help="verifier retrieval depth")
    parser.add_argument("--min-chars", type=int, default=200)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--audit-fraction", type=float, default=0.10)
    parser.add_argument("--per-source-cap", type=int, default=2,
                        help="max admissions per source_path (0 = uncapped) — the "
                             "CSV-trivia guard")
    parser.add_argument("--propose-model", default="claude-sonnet-4-6")
    parser.add_argument("--verify-model", default="claude-sonnet-4-6")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--merge", nargs="+", default=None, metavar="RUN_DIR",
                        help="merge mode: combine these factory run dirs' corpora "
                             "(cross-run dedup, re-id, fresh audit sample) instead of "
                             "generating; only --seed/--audit-fraction/--run-id/--publish "
                             "apply")
    parser.add_argument("--publish", action="store_true",
                        help="ALSO overwrite $LIFE_AGENT_KB/eval/questions_v2.yaml (default: "
                             "run-dir only, inspect before it becomes the corpus)")
    args = parser.parse_args(argv)

    if args.merge:
        return _run_merge(args)
    if not args.config:
        parser.error("--config is required unless --merge is given")

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
                             k=args.k, min_chars=args.min_chars, seed=args.seed,
                             per_source_cap=args.per_source_cap)
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
        "per_source_cap": args.per_source_cap,
        "propose_model": args.propose_model, "verify_model": args.verify_model,
        "proposer_prompt_sha256": hashlib.sha256(PROPOSER_V2.encode()).hexdigest(),
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
