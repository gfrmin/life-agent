"""Harvest the questions the owner actually asked, from the pkm derivation cache.

The §8 gate reads 104 **authored** questions. The live surfaces have asked a different
population, and the gap is `docs/guards.md` known-and-uncovered 9 — the gate's universe is
smaller than the one it stands for, recorded there under an owner ruling to widen the
corpus from real asks. This is that harvest.

**Where the text is.** A decision row carries a `question_id` and no text. The text
survives as an *input* to the question-keyed derivations: pkm records
`producer_metadata.inputs` in every `meta.json` (SPEC §18.9, `core/derivations.record`),
and thirteen `life_agent.ask.*` producers take a `question`. So the asked questions are
recoverable from the cache without ever having been logged in the clear.

**The join is the deployed derivation, not a re-implementation.** `question_id` is
`DEC.question_id(question)` — the one derivation (`core/decisions.py`). Re-computing the
hash here would be the register's entry 1 exactly: a census whose universe is derived from
somewhere other than the thing it prices.

**PII.** Every harvested question is a real question about a real corpus. The output goes
to `$LIFE_AGENT_KB` and NOTHING with question text is printed: the summary is counts,
family mix, action mix and a date span. This repo is public.

    uv run --project . python scripts/harvest_real_asks.py
    uv run --project . python scripts/harvest_real_asks.py --out /path/to/dir
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from life_agent.core import config as CFG
from life_agent.core import decisions as DEC

#: The producer namespace whose derivations are keyed on a question.
ASK_PREFIX = "life_agent.ask."


def cached_questions(cache_root: Path) -> dict[str, dict[str, Any]]:
    """Distinct asked questions from the derivation cache, keyed by question text.

    Value carries the producers that saw it and the earliest `produced_at` — enough to
    stratify a sample and to date the population, and nothing else.
    """
    found: dict[str, dict[str, Any]] = {}
    for dirpath, _dirnames, filenames in os.walk(cache_root):
        if "meta.json" not in filenames:
            continue
        try:
            meta = json.loads((Path(dirpath) / "meta.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        name = str(meta.get("producer_name", ""))
        if not name.startswith(ASK_PREFIX):
            continue
        inputs = (meta.get("producer_metadata") or {}).get("inputs") or {}
        question = inputs.get("question")
        if not isinstance(question, str) or not question.strip():
            continue
        at = str(meta.get("produced_at", ""))
        row = found.setdefault(question, {"producers": set(), "first_seen": at})
        row["producers"].add(name.removeprefix(ASK_PREFIX))
        if at and at < row["first_seen"]:
            row["first_seen"] = at
    return found


def decision_index(decisions_path: Path) -> dict[str, dict[str, Any]]:
    """`question_id` → what the deployed arm last did with it, excluding gate runs.

    Gate rows are the authored corpus replaying; they say nothing about what was ASKED.
    """
    index: dict[str, dict[str, Any]] = {}
    if not decisions_path.is_file():
        return index
    for line in decisions_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if str(row.get("run_id", "")).startswith("gate"):
            continue
        qid = row.get("question_id")
        if isinstance(qid, str):
            index[qid] = {"family": row.get("family"),
                          "chosen_action": row.get("chosen_action"),
                          "tx_time": row.get("tx_time"), "run_id": row.get("run_id")}
    return index


def harvest(cache_root: Path, decisions_path: Path) -> list[dict[str, Any]]:
    """One row per distinct asked question, joined to what the arm did with it."""
    index = decision_index(decisions_path)
    rows = []
    for question, meta in cached_questions(cache_root).items():
        qid = DEC.question_id(question)              # the ONE derivation, not a copy
        decided = index.get(qid, {})
        rows.append({
            "question_id": qid,
            "question": question,
            "producers": sorted(meta["producers"]),
            "first_seen": meta["first_seen"],
            "family": decided.get("family"),
            "chosen_action": decided.get("chosen_action"),
            "decided_at": decided.get("tx_time"),
            "decided": bool(decided),
        })
    return sorted(rows, key=lambda r: (r["first_seen"], r["question_id"]))


def summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """A PII-free description of the population. **No question text, and no count paired
    with an identifier that could single one out** — this is what may be quoted in tree."""
    seen = [r["first_seen"][:10] for r in rows if r["first_seen"]]
    return {
        "n_questions": len(rows),
        "n_decided": sum(1 for r in rows if r["decided"]),
        "families": dict(Counter(r["family"] for r in rows if r["family"])),
        "actions": dict(Counter(r["chosen_action"] for r in rows if r["chosen_action"])),
        "producers": dict(Counter(p for r in rows for p in r["producers"])),
        "first_seen": min(seen) if seen else None,
        "last_seen": max(seen) if seen else None,
    }


def render(s: dict[str, Any]) -> str:
    def mix(d: dict[str, Any]) -> str:
        return ", ".join(f"{k}={v}" for k, v in sorted(d.items())) or "(none)"
    return "\n".join([
        f"real asks harvested: {s['n_questions']} distinct question(s)",
        f"  decided by the arm: {s['n_decided']}",
        f"  families:  {mix(s['families'])}",
        f"  actions:   {mix(s['actions'])}",
        f"  producers: {mix(s['producers'])}",
        f"  span:      {s['first_seen']} → {s['last_seen']}",
    ])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache", default=None,
                    help="pkm cache root (default: <pkm root_dir>/cache)")
    ap.add_argument("--out", default=None,
                    help="output directory (default: $LIFE_AGENT_KB/eval/real-asks)")
    args = ap.parse_args(argv)

    if args.cache:
        cache_root = Path(args.cache).expanduser()
    else:
        pkm_root = CFG.pkm_root()
        if pkm_root is None:
            print("no pkm root: set PKM_CONFIG or pass --cache", file=sys.stderr)
            return 2
        cache_root = pkm_root / "cache"
    if not cache_root.is_dir():
        print(f"no pkm cache at {cache_root}", file=sys.stderr)
        return 2

    rows = harvest(cache_root, CFG.DECISIONS_LOG)
    if not rows:
        print(f"no question-keyed derivations under {cache_root}", file=sys.stderr)
        return 2

    out = Path(args.out).expanduser() if args.out else CFG.KB / "eval" / "real-asks"
    out.mkdir(parents=True, exist_ok=True)
    (out / "questions.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows),
        encoding="utf-8")
    s = summary(rows)
    (out / "summary.json").write_text(json.dumps(s, indent=1, sort_keys=True),
                                      encoding="utf-8")
    print(render(s))
    print(f"→ {out}/questions.jsonl  (out of tree: every row carries a real question)",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
