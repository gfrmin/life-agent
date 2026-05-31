#!/usr/bin/env python3
"""phase0_answer.py — the Phase-0 (compile) answerer (SPEC-comparison.md §2).

The `bin/ask` method: load the WHOLE compiled wiki into the PINNED answer model and answer with
citations. The only difference from Phase 1 is context assembly (whole wiki vs top-k chunks); the
citation SHAPE is normalised to the same `[n]` scheme (each wiki page is a numbered source) so the
blind judge cannot tell the systems apart by citation form (§6). Meters tokens / wall-clock.

Run:  uv run --project ../pkm python scripts/comparison/phase0_answer.py
Reads the compiled wiki at $LIFE_AGENT_KB/eval/comparison/wiki/ (run compile_wiki.py first).
"""
from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as C  # noqa: E402

WIKI_DIR = C.COMPARISON_DIR / "wiki"


def load_wiki_cards() -> list[C.SourceCard]:
    pages = sorted(WIKI_DIR.glob("*.md"))
    if not pages:
        raise SystemExit(f"no compiled wiki at {WIKI_DIR} — run compile_wiki.py first")
    # Keep the filename in `origin` (harness-only); do NOT put it in `text` — a `.md` filename
    # shown to the blind judge would identify Phase 0 (§6). The page body alone is the source.
    return [C.SourceCard(n=i + 1, text=p.read_text(encoding="utf-8").strip(), origin=p.name)
            for i, p in enumerate(pages)]


def answer_one(q: dict, cards: list[C.SourceCard]) -> C.Answer:
    system = ("You are the owner's personal assistant. Answer ONLY from the numbered SOURCES (the "
              "owner's life-wiki pages). " + C.CITATION_INSTRUCTION)
    user = f"QUESTION: {q['question']}\n\nSOURCES:\n{C.render_sources_block(cards)}"
    r = C.anthropic_complete(system, user, max_tokens=600)
    return C.Answer("phase0", q["id"], r.text.strip(), sources=cards,
                    in_tokens=r.in_tokens, out_tokens=r.out_tokens, seconds=r.seconds)


def main() -> int:
    questions = C.scored_questions()
    cards = load_wiki_cards()
    print(f"whole-wiki context: {len(cards)} pages")
    C.COMPARISON_DIR.mkdir(parents=True, exist_ok=True)
    out = C.COMPARISON_DIR / "phase0_answers.jsonl"

    answers = []
    for q in questions:
        a = answer_one(q, cards)
        answers.append(a)
        print(f"  {a.question_id}: {a.in_tokens} in / {a.out_tokens} out tok, {a.seconds:.1f}s")
    out.write_text("\n".join(json.dumps(dataclasses.asdict(a), ensure_ascii=False) for a in answers),
                   encoding="utf-8")
    tot_in = sum(a.in_tokens for a in answers)
    tot_out = sum(a.out_tokens for a in answers)
    print(f"\nwrote {out}  ({len(answers)} answers; {tot_in} in / {tot_out} out tokens, "
          f"{C.ANSWER_MODEL})")
    print(f"NOTE: every Phase-0 answer re-stuffs the whole wiki ({cards[0].n}..{cards[-1].n} pages) "
          f"into context — that per-query input cost is a divergence datum (§7a).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
