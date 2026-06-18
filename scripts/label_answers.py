#!/usr/bin/env python3
"""Adjudicate the confident answers — build the owner-graded gold (owner directive 2026-06-18).

Two modes:

  --generate   gather every CONFIDENT answer the system actually asserted (across the saved
               triage configs, plus optionally the Opus joint-combiner with --opus), attach a
               corpus evidence snippet, and write the to-label queue. No verdicts written.

  (default)    show each un-labeled confident answer — the question, the asserted VALUE, the
               evidence, the source — and capture ONE bit: [y] correct / [n] wrong. Appends the
               owner's verdict to $LIFE_AGENT_KB/eval/labels.jsonl (the trustworthy gold, which
               also feeds the u_wrong reaction loop). [s] skip, [q] quit, idempotent on re-run.

The owner runs the default mode (it reads stdin); this script never writes a verdict itself.

    uv run --project . python scripts/label_answers.py --generate [--opus]
    uv run --project . python scripts/label_answers.py            # then label
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from answer_labels import CORRECT, STALE, WRONG, append_label, is_labeled, load_labels, norm
from eval_grading import answer_matches
from run_eval import _kb_root, load_questions

PENDING = "pending_labels.jsonl"
LABELS = "labels.jsonl"


def _evidence(conn, ask, value: str) -> tuple[str, str]:
    """A corpus chunk that carries the value → (snippet, source) for the owner to eyeball."""
    for h in ask._retrieve_set(conn, str(value), 30):
        if answer_matches(str(value), [], h["chunk_text"]):
            return " ".join(h["chunk_text"].split())[:280], Path(h["origin"]).name
    return "(value not located in a single retrieved chunk)", ""


def _asserted_values(packet: dict) -> list[str]:
    d = packet.get("decision", {})
    if d.get("action") == "report_scoped" and d.get("scoped_value"):
        return [d["scoped_value"]]
    return [v for v in d.get("asserted_values", []) if v]


def generate(use_opus: bool) -> int:
    import duckdb
    import yaml
    out_dir = _kb_root() / "eval"
    triage_dir = out_dir / "triage"

    # (question_id -> {value_norm -> (value, origin)}) collected from every saved config
    seen: dict[str, dict[str, tuple[str, str]]] = {}
    for f in sorted(triage_dir.glob("triage*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            p = json.loads(line)
            for v in _asserted_values(p):
                seen.setdefault(p["id"], {}).setdefault(norm(v), (v, f.stem))

    cfg = yaml.safe_load(Path("~/.config/life-agent/pkm.yaml").expanduser().read_text())
    conn = duckdb.connect(str(Path(cfg["root_dir"]).expanduser() / "catalogue.duckdb"))
    conn.execute("INSTALL fts; LOAD fts;")
    import ask

    if use_opus:
        from probe_opus_answer import _ask_opus
        for q in load_questions():
            if not q.get("answer"):
                continue
            terms = ask._expand_terms(q["question"], root=ask._pkm_root())
            pool = ask._retrieve_set(conn, ask.build_query(q["question"], terms), 20)
            obj, _ = _ask_opus(q["question"], pool, model="claude-opus-4-8", k=20)
            v = obj.get("value")
            if v and float(obj.get("confidence") or 0) >= 0.7:
                seen.setdefault(q["id"], {}).setdefault(norm(str(v)), (str(v), "opus-combiner"))

    qtext = {q["id"]: q["question"] for q in load_questions()}
    items = []
    for qid, by_norm in seen.items():
        for value, origin in by_norm.values():
            snippet, source = _evidence(conn, ask, value)
            items.append({"question_id": qid, "question": qtext.get(qid, ""),
                          "value": value, "origin": origin,
                          "evidence": snippet, "source": source})
    (out_dir / PENDING).write_text(
        "".join(json.dumps(i, ensure_ascii=False) + "\n" for i in items), encoding="utf-8")
    print(f"Wrote {len(items)} confident answers to {out_dir / PENDING}")
    print("Now run:  uv run --project . python scripts/label_answers.py")
    return 0


def label() -> int:
    out_dir = _kb_root() / "eval"
    pending_path, labels_path = out_dir / PENDING, out_dir / LABELS
    if not pending_path.exists():
        print("No pending queue — run with --generate first.")
        return 1
    items = [json.loads(x)
             for x in pending_path.read_text(encoding="utf-8").splitlines() if x.strip()]
    labels = load_labels(labels_path)
    todo = [it for it in items if not is_labeled(labels, it["question_id"], it["value"])]
    choice = {"c": CORRECT, "s": STALE, "w": WRONG}
    print(f"{len(items)} confident answers · {len(items) - len(todo)} already labeled · "
          f"{len(todo)} to go.\n"
          "[c]=correct now  [s]=stale (was right, wrong now)  [w]=wrong  [k]=skip  [q]=quit\n")
    for i, it in enumerate(todo, 1):
        print(f"── {i}/{len(todo)}  [{it['question_id']}]  (asserted via {it['origin']})")
        print(f"   Q: {it['question']}")
        print(f"   ANSWER: {it['value']}")
        print(f"   evidence [{it['source']}]: {it['evidence']}")
        try:
            ans = input("   verdict? [c]orrect [s]tale [w]rong [k]skip [q]uit ").strip().lower()
        except EOFError:
            ans = "q"
        if ans == "q":
            break
        if ans in choice:
            append_label(labels_path, it["question_id"], it["value"], choice[ans])
            print(f"   ✓ {choice[ans]}\n")
        else:
            print("   skipped\n")
    print(f"Labels → {labels_path}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--generate", action="store_true", help="build the to-label queue")
    ap.add_argument("--opus", action="store_true",
                    help="also include the Opus joint-combiner's answers")
    args = ap.parse_args()
    return generate(args.opus) if args.generate else label()


if __name__ == "__main__":
    sys.exit(main())
