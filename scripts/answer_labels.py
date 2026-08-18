"""Owner-adjudicated answer labels — the trustworthy gold (owner directive, 2026-06-18).

A single pre-written gold per question marks co-valid answers wrong (q-020 "Ben Craft" *did*
ask about HKJC data; q-015 "partner visa" *is* an A5) — single-gold token-matching manufactures
false confident-wrongs. The fix the owner chose: show him each confident ANSWER the system
actually asserted and capture one bit — correct / not. Those verdicts are ground truth by
construction (they grade the real assertion, not a guessed key), and they double as the §4.4
reaction-loop signal that calibrates u_wrong.

This module is the pure store + lookup; the interactive capture is ``scripts/label_answers.py``.
Labels live append-only in ``$LIFE_AGENT_KB/eval/labels.jsonl`` (PII — out of the repo). A label
is keyed on (question_id, the asserted value); lookup is robust to small value variants via the
shared token matcher, so a re-run that phrases the value slightly differently still resolves.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from eval_grading import answer_matches

# The three temporal verdicts (owner directive 2026-06-18): a value is right NOW, was right
# THEN (stale — wrong now but true at its time, the scoped-claims case), or never right. They
# map onto the utility atoms: correct→u_correct, stale→u_wrong_scoped, wrong→u_wrong.
CORRECT, STALE, WRONG = "correct", "stale", "wrong"
VERDICTS = (CORRECT, STALE, WRONG)


def norm(value: str) -> str:
    """The label's identity key: whitespace-collapsed, case-folded."""
    return " ".join(str(value).split()).casefold()


@dataclass(frozen=True)
class Label:
    question_id: str
    value: str
    verdict: str  # one of VERDICTS
    note: str = ""


def load_labels(path: Path) -> list[Label]:
    """Every label in file order (last write wins on a re-label — see :func:`verdict`).
    Back-compatible with the pre-trichotomy schema (a bare ``correct: bool``)."""
    if not path.exists():
        return []
    out: list[Label] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        o = json.loads(line)
        v = o.get("verdict") or (CORRECT if o.get("correct") else WRONG)
        out.append(Label(o["question_id"], o["value"], v, o.get("note", "")))
    return out


def verdict(labels: list[Label], question_id: str, value: str) -> str | None:
    """The owner's temporal verdict (one of VERDICTS) for an asserted value, or None if
    unlabeled. Matches on exact norm first, then bidirectional token-containment (a labeled
    value that contains, or is contained by, the asserted one) so minor phrasing drift still
    resolves. Later labels override earlier ones (the owner can correct himself — e.g. wrong→
    stale once a value turns out to have been true at its time)."""
    nv = norm(value)
    found: str | None = None
    for lab in labels:
        if lab.question_id != question_id:
            continue
        if norm(lab.value) == nv or (
                value and lab.value
                and (answer_matches(lab.value, [], value)
                     or answer_matches(value, [], lab.value))):
            found = lab.verdict  # keep scanning so the LAST matching label wins
    return found


def is_labeled(labels: list[Label], question_id: str, value: str) -> bool:
    return verdict(labels, question_id, value) is not None


def append_label(path: Path, question_id: str, value: str, verdict: str, note: str = "") -> None:
    """Append one owner verdict durably (the canonical replay order is file order)."""
    if verdict not in VERDICTS:
        raise ValueError(f"verdict {verdict!r} not in {VERDICTS}")
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps({"question_id": question_id, "value": value, "value_norm": norm(value),
                       "verdict": verdict, "note": note}, ensure_ascii=False)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    from life_agent.ledger import mirror as _mirror  # C5 dual-write: after the legacy append
    _mirror.after_legacy_append("eval.labels", path)
