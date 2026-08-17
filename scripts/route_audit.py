#!/usr/bin/env python3
"""Router audit — the lookup router's confusion matrix on labelled questions (§14).

The router (``lookup.route_question``) is a confusion-matrix-class instrument: a false
negative sends a point-fact question down the narrative path, where the typed arm
withholds — in run 6 (2026-08-17) 17 of the 18 ``miss`` withholdings were route
refusals on plainly single-value questions ("What does GERT stand for?"), with the gold
chunk at FTS rank ≤ 4 for most. This tool measures a prompt's verdicts against two
labelled sets — the factory corpus (``questions_v2.yaml``, all-positive by construction)
and a separately labelled mixed set (``route-audit.yaml``: positives NOT from the factory
plus negatives in the shapes the owner types) — for the CURRENT prompt and, optionally, a
candidate template read from a file, so a prompt change is registered with both matrices
before it lands. Verdicts are cached under the same §18.9 key the live router uses (the
prompt hash is in the key), so re-runs are free and the current-prompt column costs
nothing after a gate run.

Usage:
  uv run python scripts/route_audit.py [--candidate PROMPT_FILE] [--questions Q.yaml]
      [--audit route-audit.yaml] [--out REPORT.md]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_eval import _kb_root, load_questions

import life_agent.core.derivations as D
from life_agent.core import config as LCFG
from life_agent.core import lookup as LK


def verdict(root: Path, question: str, prompt: str, client) -> dict:
    """route_question's body with the prompt injected — same key family (prompt hash in
    the key), same record shape, so a candidate that lands replays these verdicts."""
    key = D.lookup_route_key(question, model=LK.LOOKUP_MODEL, prompt_template=prompt,
                             engine_version=str(client.engine_version),
                             output_schema=LK.ROUTE_SCHEMA)
    cached = D.lookup(root, key.cache_key)
    if cached is not None:
        return dict(json.loads(cached.decode("utf-8")))
    response = client.complete(prompt.replace("{question}", question), LK.ROUTE_SCHEMA)
    parsed = json.loads(response.raw_text)
    if not isinstance(parsed.get("lookup"), bool):
        raise ValueError(f"lookup_route emitted junk: {parsed!r}")
    D.record(root, key, json.dumps({"format_version": 1, **parsed}, sort_keys=True,
                                   ensure_ascii=False).encode("utf-8"), lineage=[])
    return dict(parsed)


def matrix(items: list[tuple[str, bool]], verdicts: dict[str, dict]) -> dict:
    tp = sum(1 for q, y in items if y and verdicts[q]["lookup"])
    fn = sum(1 for q, y in items if y and not verdicts[q]["lookup"])
    fp = sum(1 for q, y in items if not y and verdicts[q]["lookup"])
    tn = sum(1 for q, y in items if not y and not verdicts[q]["lookup"])
    return {"tp": tp, "fn": fn, "fp": fp, "tn": tn,
            "fn_rate": fn / max(1, tp + fn), "fp_rate": fp / max(1, fp + tn)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--candidate", type=Path, default=None,
                    help="a candidate ROUTE_PROMPT template file ({question} placeholder)")
    ap.add_argument("--questions", type=Path, default=None)
    ap.add_argument("--audit", type=Path, default=_kb_root() / "eval" / "route-audit.yaml")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    root = LCFG.pkm_root()
    if root is None:
        print("REFUSED: PKM_CONFIG unresolvable")
        return 2
    client = LK._client()
    factory = [(str(q["question"]), True) for q in
               (load_questions(args.questions) if args.questions else load_questions())]
    audit_doc = yaml.safe_load(args.audit.read_text(encoding="utf-8"))
    audit = [(str(it["question"]), bool(it["lookup"])) for it in audit_doc["items"]]

    prompts = {"current": LK.ROUTE_PROMPT}
    if args.candidate:
        prompts["candidate"] = args.candidate.read_text(encoding="utf-8")
        if "{question}" not in prompts["candidate"]:
            ap.error("candidate template lacks the {question} placeholder")

    lines = [f"# Router audit — {len(factory)} factory positives · {len(audit)} labelled "
             f"mixed ({sum(1 for _, y in audit if y)} pos / "
             f"{sum(1 for _, y in audit if not y)} neg) — model {LK.LOOKUP_MODEL}", "",
             "| prompt | set | TP | FN | FP | TN | FN rate | FP rate |",
             "|---|---|---:|---:|---:|---:|---:|---:|"]
    detail: list[str] = []
    for name, prompt in prompts.items():
        for set_name, items in (("factory", factory), ("mixed", audit)):
            vs = {q: verdict(root, q, prompt, client) for q, _ in items}
            m = matrix(items, vs)
            lines.append(f"| {name} | {set_name} | {m['tp']} | {m['fn']} | {m['fp']} | "
                         f"{m['tn']} | {m['fn_rate']:.3f} | {m['fp_rate']:.3f} |")
            wrong = [(q, y) for q, y in items if bool(vs[q]["lookup"]) != y]
            if wrong:
                detail += [f"## {name} / {set_name} — {len(wrong)} disagreement(s)", ""]
                detail += [f"- {'FN' if y else 'FP'}: {q}" for q, y in wrong]
                detail.append("")
    text = "\n".join([*lines, "", *detail])
    print(text)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
