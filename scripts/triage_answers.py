#!/usr/bin/env python3
"""Answer baseline + miss-triage over the PRODUCTION path (owner directive, 2026-06-18).

Runs the production answer path (``ask.answer`` — real expansion, real retrieval, the
route/extract/posterior/decide) over the PII eval corpus, and for every
question crosses the RETRIEVAL channel (was the truth retrievable?) with the DECISION
channel (did the agent assert, and was it right?) to bucket the outcome by the lever
that would fix it:

    CORRECT · CONFIDENT_WRONG · RIGHTLY_WITHHELD · WRONGLY_WITHHELD
                                  {retrieval_miss | extraction_miss | pooling_loss}

The headline is **correct-answer rate at ZERO confident-wrong**; the WRONGLY_WITHHELD
histogram is the retrieval roadmap (which upgrade buys the most correct answers). The
classification is in scripts/triage_grading.py (pure, unit-tested); this module is the
IO shell that runs the path and emits a rich per-question evidence packet.

The packet (triage.jsonl) is what the Opus oracle adjudicates on the rows flagged
``needs_judgment`` (every assertion + every pooling_loss); the mechanical buckets stand
for the rest. Why an oracle and not a token match: a token match cannot tell a current
value from a stale-but-grounded one (the 2015-number trap), nor a genuine ambiguity from
a recoverable answer. That is the owner's call to make me — Opus — the grader.

Output lands under $LIFE_AGENT_KB/eval/triage/ — PII, stays in the KB, never the repo.

    uv run --project . python scripts/triage_answers.py [--config PATH] [--k N] [--limit N]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from answer_labels import Label, load_labels, verdict
from eval_grading import answer_matches, chunk_matches_any
from run_eval import _answer_in_corpus, _kb_root, load_questions
from triage_grading import triage

# --- normalize the family decision to one view the classifier + packet read -------------


def _lookup_view(lk) -> dict:
    """Decision view from a LookupResult (the point-fact family — the owner's focus)."""
    scoped = lk.action == "report_scoped"
    if lk.action == "report":
        asserted_values = list(lk.candidates[:1])
    elif lk.action == "hedge":
        asserted_values = list(lk.candidates)
    elif scoped:  # the claimed value is the freshest record's, scoped to its date
        asserted_values = [lk.scoped_value] if lk.scoped_value else []
    else:  # abstain | ask_clarify — a withholding
        asserted_values = []
    observations = [
        {"value": o.value_raw, "value_norm": o.value_norm, "card_n": o.card_n,
         "authority_class": o.authority_class, "authority": round(o.authority, 3),
         "time_factor": round(o.time_factor, 3), "subject_factor": round(o.subject_factor, 3),
         "quote": o.quote[:160].replace("\n", " ")}
        for o in lk.observations
    ]
    return {
        "family": "lookup", "construct": lk.construct, "action": lk.action,
        "asserted": lk.action in ("report", "hedge"), "scoped": scoped,
        "scoped_value": lk.scoped_value, "as_of": lk.as_of,
        "asserted_values": asserted_values,
        "candidates": list(lk.candidates),
        "credences": [round(c, 4) for c in lk.credences],
        "p_none": round(lk.p_none, 4), "n_hits": lk.n_hits,
        "n_indeterminate": lk.n_indeterminate, "observations": observations,
    }


def _narrative_view(nv) -> dict:
    """Decision view from a NarrativeResult (report | abstain over a scored claim set)."""
    asserted = nv.action == "report"
    return {
        "family": "narrative", "construct": "narrative", "action": nv.action,
        "asserted": asserted,
        "asserted_values": [c.text for c in nv.claims if c.included] if asserted else [],
        "candidates": [c.text for c in nv.claims],
        "credences": [round(c.credence, 4) for c in nv.claims],
        "p_none": None, "n_hits": None, "n_indeterminate": None, "observations": [],
    }


def _withheld_view() -> dict:
    """No family decided: the shared weak-retrieval abstention (asserted nothing)."""
    return {"family": None, "construct": None, "action": "abstain", "asserted": False,
            "asserted_values": [], "candidates": [], "credences": [],
            "p_none": None, "n_hits": None, "n_indeterminate": None, "observations": []}


def triage_one(conn, q: dict, k: int, ask, *, gather: bool = False,
               rerank: bool = False, labels: list[Label] | None = None) -> dict:
    """Run one question through the production path and build its triage packet."""
    gold = q.get("answer", "")
    variants = q.get("answer_variants", [])
    distractors = q.get("distractors", []) if q.get("subject", "n/a") != "n/a" else []
    answerable = bool(gold)
    labels = labels or []

    text, cards, scores = ask.answer(conn, q["question"], k, gather=gather, rerank=rerank)
    lk, nv = ask.LOOKUP_LAST, ask.NARRATIVE_LAST  # capture before the next call resets them
    view = _lookup_view(lk) if lk is not None else (
        _narrative_view(nv) if nv is not None else _withheld_view())

    # retrieval channel: is the gold reachable, and where? (production retrieved set = cards)
    retrieved_texts = [c.text for c in cards]
    gold_in_topk = answerable and chunk_matches_any(gold, variants, retrieved_texts)
    gold_in_corpus = gold_in_topk or (answerable and _answer_in_corpus(conn, gold, variants))

    # decision channel: did a surfaced candidate / an assertion match the gold / a distractor?
    gold_in_candidates = answerable and any(
        answer_matches(gold, variants, c) for c in view["candidates"])
    asserted_correct = answerable and any(
        answer_matches(gold, variants, a) for a in view["asserted_values"])
    asserted_distractor = any(
        answer_matches(d, [], a) for d in distractors for a in view["asserted_values"])
    # the owner's temporal verdict on what was actually asserted — authoritative when present
    # (correct / stale / wrong), None where unlabeled (the classifier falls back to token-match)
    asserted_verdict = next(
        (v for a in view["asserted_values"]
         if (v := verdict(labels, q["id"], a)) is not None), None)

    t = triage(
        answerable=answerable, asserted=view["asserted"],
        asserted_correct=asserted_correct, asserted_distractor=asserted_distractor,
        gold_in_candidates=gold_in_candidates, gold_in_topk=gold_in_topk,
        gold_in_corpus=gold_in_corpus, scoped=view.get("scoped", False),
        asserted_verdict=asserted_verdict)

    retrieved = [
        {"rank": i + 1, "card_n": c.n, "source": Path(c.origin).name,
         "score": round(scores.get(c.n, 0.0), 3) if scores else None,
         "gold_here": answerable and chunk_matches_any(gold, variants, [c.text]),
         "distractor_here": any(answer_matches(d, [], c.text) for d in distractors),
         "text": c.text[:200].replace("\n", " ")}
        for i, c in enumerate(cards)
    ]

    return {
        "id": q["id"], "question": q["question"], "subject": q.get("subject", "n/a"),
        "answerable": answerable, "gold": gold, "answer_variants": variants,
        "distractors": distractors, "mode_hint": q.get("mode_hint"),
        "bucket": t.bucket, "cause": t.cause, "needs_judgment": t.needs_judgment,
        "channel": {
            "gold_in_topk": bool(gold_in_topk), "gold_in_corpus": bool(gold_in_corpus),
            "gold_in_candidates": bool(gold_in_candidates),
            "asserted_correct": bool(asserted_correct),
            "asserted_distractor": bool(asserted_distractor)},
        "decision": view, "rendered": text[:240].replace("\n", " "),
        "retrieved": retrieved, "notes": q.get("notes", ""),
    }


# --- reporting --------------------------------------------------------------------------

# the lever each WRONGLY_WITHHELD / coverage cause points at, ordered by where the owner's
# focus should land first (the decision-side recency/gather fix, then retrieval, then
# extraction, then ingestion)
_ROADMAP = [
    ("pooling_loss", "decision: recency/authority probe + the gather loop (the mobile class)"),
    ("retrieval_miss", "retrieval: ranking / query expansion / embeddings"),
    ("extraction_miss", "extraction: the local-model extract prompt / model"),
    ("coverage_gap", "ingestion: the source is not in the corpus (not a retrieval fix)"),
]


def render_report(packets: list[dict], k: int, elapsed: float) -> str:
    buckets = Counter(p["bucket"] for p in packets)
    causes = Counter(p["cause"] for p in packets if p["cause"])
    answerable = [p for p in packets if p["answerable"]]
    n_correct = buckets["CORRECT"]
    n_cw = buckets["CONFIDENT_WRONG"]

    def _pct(a: int, b: int) -> str:
        return "n/a" if not b else f"{100 * a / b:.0f}%"

    lines = [
        "# Answer triage (production path) — correct rate at zero confident-wrong",
        "",
        f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}   k={k}   "
        f"elapsed={elapsed:.1f}s   n={len(packets)}",
        "",
        f"**Correct-answer rate: {_pct(n_correct, len(answerable))}** "
        f"({n_correct}/{len(answerable)} answerable).",
        f"**Confident-wrong: {n_cw}** (the hard gate is 0).",
        "",
        "Buckets: " + " · ".join(f"{b}={c}" for b, c in sorted(buckets.items())),
        "",
        "## Retrieval roadmap — where the recoverable answers are being lost",
        "",
    ]
    for cause, lever in _ROADMAP:
        ids = [p["id"] for p in packets if p["cause"] == cause]
        if ids:
            lines.append(f"- **{cause}** ({len(ids)}): {lever}")
            lines.append(f"  - {', '.join(str(i) for i in ids)}")
    other = [c for c in causes if c not in {c for c, _ in _ROADMAP}]
    for cause in other:
        ids = [p["id"] for p in packets if p["cause"] == cause]
        lines.append(f"- _{cause}_ ({len(ids)}): {', '.join(str(i) for i in ids)}")

    lines += [
        "",
        "## Rows the Opus oracle must adjudicate (needs_judgment)",
        "",
        "Token-match cannot read currency or genuine ambiguity; the oracle grades these.",
        "",
        "| ID | bucket | cause | action | top candidate | p | Q |",
        "|---|---|---|---|---|---|---|",
    ]
    for p in packets:
        if not p["needs_judgment"]:
            continue
        d = p["decision"]
        top = (d["candidates"][0][:30] if d["candidates"] else "—")
        topp = f"{d['credences'][0]:.2f}" if d["credences"] else "—"
        lines.append(f"| {p['id']} | {p['bucket']} | {p['cause'] or ''} | {d['action']} "
                     f"| {top} | {topp} | {p['question'][:40]} |")

    lines += ["", "## All questions", "",
              "| ID | bucket | cause | act | gold@topk | gold@cand | Q |",
              "|---|---|---|---|---|---|---|"]
    for p in packets:
        ch = p["channel"]
        lines.append(
            f"| {p['id']} | {p['bucket']} | {p['cause'] or ''} | {p['decision']['action']} "
            f"| {'✓' if ch['gold_in_topk'] else '·'} | {'✓' if ch['gold_in_candidates'] else '·'} "
            f"| {p['question'][:40]} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default=os.environ.get(
            "PKM_CONFIG", str(Path("~/.config/life-agent/pkm.yaml").expanduser())),
        help="pkm config.yaml (default: $PKM_CONFIG or ~/.config/life-agent/pkm.yaml)")
    parser.add_argument("--k", type=int, default=20, help="top-k per query")
    parser.add_argument("--limit", type=int, default=0,
                        help="triage only the first N questions (0 = all; for a smoke run)")
    parser.add_argument("--gather", action="store_true",
                        help="run the gather-augmented lookup loop (re-retrieve corroboration on "
                             "the top candidates + re-weight by recency/subject) — calibrates the "
                             "concentrate lever against the single-pass default")
    parser.add_argument("--rerank", action="store_true",
                        help="over-fetch a wide lexical pool and listwise-rerank to top-k — "
                             "calibrates the retrieval-recall lever (rescues golds BM25 buried "
                             "below word-overlapping noise) against the single-pass default")
    args = parser.parse_args()

    import duckdb
    import yaml

    questions = load_questions()
    if args.limit:
        questions = questions[: args.limit]
    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    db_path = Path(cfg["root_dir"]).expanduser() / "catalogue.duckdb"
    conn = duckdb.connect(str(db_path))
    conn.execute("INSTALL fts; LOAD fts;")

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import ask

    mode = f"k={args.k}{', gather' if args.gather else ''}{', rerank' if args.rerank else ''}"
    print(f"Triaging {len(questions)} questions through the production path ({mode}) …")
    t0 = time.monotonic()
    labels = load_labels(_kb_root() / "eval" / "labels.jsonl")
    if labels:
        print(f"  (grading against {len(labels)} owner label(s), token-match fallback)")
    packets: list[dict] = []
    for q in questions:
        p = triage_one(conn, q, args.k, ask, gather=args.gather, rerank=args.rerank,
                       labels=labels)
        packets.append(p)
        j = " ⚖" if p["needs_judgment"] else ""
        print(f"  {p['id']}: {p['bucket']}"
              + (f"/{p['cause']}" if p["cause"] else "") + j)
    elapsed = time.monotonic() - t0

    out_dir = _kb_root() / "eval" / "triage"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "triage.jsonl").write_text(
        "".join(json.dumps(p, ensure_ascii=False, sort_keys=True) + "\n" for p in packets),
        encoding="utf-8")
    (out_dir / "triage_log.md").write_text(
        render_report(packets, args.k, elapsed), encoding="utf-8")

    buckets = Counter(p["bucket"] for p in packets)
    answerable = sum(1 for p in packets if p["answerable"])
    print(f"\nTriage → {out_dir}/triage_log.md  (+ triage.jsonl, {len(packets)} packets)")
    print(f"  correct {buckets['CORRECT']}/{answerable} answerable · "
          f"confident-wrong {buckets['CONFIDENT_WRONG']} (gate: 0) · "
          f"wrongly-withheld {buckets['WRONGLY_WITHHELD']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
