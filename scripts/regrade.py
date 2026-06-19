#!/usr/bin/env python3
"""Re-grade the saved triage configs against the OWNER's temporal labels (no model re-runs).

The sweep's confident-wrong counts came from single-gold token-matching, which the owner's
labels proved manufactures false sins (q-020 "Ben Craft" was correct; q-015 "partner visa" is
STALE — true until his wife's citizenship this year — not wrong). This recomputes each saved
config with the owner's verdicts labels-first, splitting the old "confident-wrong" lump into:

    CORRECT          asserted a value the owner labels correct (or token-matches, unlabeled)
    STALE            asserted a value the owner labels stale — true at its time, the
                     scoped-claims case; a recoverable miss, NOT the cardinal sin
    CONFIDENT_WRONG  asserted a value the owner labels wrong (or an unlabeled token-mismatch)
                     — the real hard-gate sin
    SCOPED           the agent already scoped the answer ("as of <date>")

The hard gate counts only CONFIDENT_WRONG. Run after labelling (scripts/label_answers.py).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from answer_labels import CORRECT, STALE, WRONG, load_labels, verdict
from eval_grading import answer_matches
from run_eval import _kb_root


def _asserted(packet: dict) -> list[str]:
    d = packet.get("decision", {})
    if d.get("action") == "report_scoped" and d.get("scoped_value"):
        return [d["scoped_value"]]
    if d.get("asserted"):
        return [v for v in d.get("asserted_values", []) if v]
    return []


def _grade(labels, qid: str, vals: list[str], gold: str, variants: list[str]) -> str:
    """The trichotomy verdict for an assertion: owner label first (correct beats stale beats
    wrong across multiple asserted values), token-match only where every value is unlabeled."""
    vs = [verdict(labels, qid, v) for v in vals]
    if CORRECT in vs:
        return CORRECT
    if STALE in vs:
        return STALE
    if WRONG in vs:
        return WRONG
    return CORRECT if any(answer_matches(gold, variants, v) for v in vals) else WRONG


def main() -> int:
    labels = load_labels(_kb_root() / "eval" / "labels.jsonl")
    triage_dir = _kb_root() / "eval" / "triage"
    print(f"Re-grading against {len(labels)} owner labels (token-match fallback).\n")
    # a PLAINLY-asserted value that is not the current answer is a confident-wrong even if it
    # was true once (owner: "a stale answer is still wrong"); stale + hard both count, stale is
    # just the recency/scoping-fixable kind. Only report_scoped escapes (an honest non-answer).
    hdr = f"{'config':<24} {'correct':>7} {'CW(real)':>8} {'(stale)':>7} {'scoped':>6}"
    print(hdr + "   sin ids")
    for f in sorted(triage_dir.glob("triage*.jsonl")):
        packets = [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines() if x.strip()]
        n = {CORRECT: 0, STALE: 0, WRONG: 0}
        n_scoped = 0
        sin_ids: list[str] = []
        for p in packets:
            if p.get("decision", {}).get("action") == "report_scoped":
                n_scoped += 1
                continue
            vals = _asserted(p)
            if not vals:
                continue
            g = _grade(labels, p["id"], vals, p.get("gold", ""), p.get("answer_variants", []))
            n[g] += 1
            if g in (STALE, WRONG):
                sin_ids.append(f"{p['id']}{'(stale)' if g == STALE else ''}")
        n_sin = n[STALE] + n[WRONG]
        print(f"{f.stem:<24} {n[CORRECT]:>7} {n_sin:>8} {n[STALE]:>7} {n_scoped:>6}   "
              f"{' '.join(sin_ids)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
