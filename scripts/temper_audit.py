#!/usr/bin/env python3
"""Temper audit — the competing-values sweep over ARCHIVED gate evidence (§14).

Run 8's wrong-commit class (2026-08-17): the terminal commits a leader whose own chunk
carries a second same-shape value (q2-090's two dollar figures, q2-105's fax/tel row) —
and for a single-candidate commit the decision record is blind to it. This audit measures
the registered temper OFF-gate at $0: every archived decide row is joined back to its
evidence chunk (extract-cache proof where possible — a §18.9 cache hit for (question,
chunk) is deterministic proof that run extracted that chunk; deliberate tool-call cache /
catalogue containment flagged as weaker rungs; unrecovered rows NAMED, never dropped),
the shared detector (``matching.competing_value_count``, whole-chunk D1 and ±400-char
windowed D2) counts in-chunk competitors, and the tempered leader is computed analytically
(odds scaling ``p' = f·p / (f·p + 1 - p)`` — an approximation of the per-observation
reliability temper, disclosed; the live channel math tempers slightly harder, so a
flip here is a flip there).

FROZEN CHOICE CRITERIA (stated before any result is read): pick the (detector, cap) that
(i) flips the in-chunk wrong commits, (ii) minimizes collateral flips among the correct
commits, (iii) ties break to the WEAKEST temper (largest factor). Blindness disclosure:
the golds for the audited questions are known and the sweep sees which flips are good —
the router-v2 precedent's form; the choice is frozen on the criteria above and the next
gate run is the test.

Zero model calls by construction: no completing client is ever constructed — the extract
cache key's ``engine_version`` comes straight from ``anthropic.__version__`` (the same
value ``_LazyInstrumentClient`` exposes) and only ``D.lookup`` reads are made.

Usage:
  uv run python scripts/temper_audit.py --run-id gate-20260817T164427 \
      --paired $KB/eval/gate-outside-option/paired-gate-20260817T164427.jsonl \
      [--caps 1,2,3] [--out FILE.md] [--out-yaml FILE.yaml] \
      [--synth DET CAP DIR]   # write floor+stressed counterfactual paired files
"""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gate_splice import load_paired
from run_eval import load_questions

import life_agent.core.derivations as D
import life_agent.core.lookup as LK
import life_agent.core.matching as MATCH
import life_agent.core.retrieval as RET
from life_agent.core import config as LCFG
from life_agent.core.decisions import question_id as _qhash

# The empirical commit bracket from the audited run's own records (run 8: leader 0.897
# abstained, 0.8997 committed) — the conservative end; the true bar is the emergent
# p* = -u_wrong/(1-u_wrong) ≈ 0.899 under the folded Ū.
COMMIT_BAR = 0.8997
_WINDOW = 400
_ASSERTS = ("report", "report_scoped", "hedge")


def analytic_temper(p: float, f: float) -> float:
    """Odds-scaled leader probability under a reliability factor ``f`` on its (single
    dominant) observation: p' = f·p / (f·p + (1-p))."""
    return (f * p) / (f * p + (1.0 - p)) if 0.0 < p < 1.0 else p


def detector_d1(leader: str, chunk: str, quote: str | None = None) -> int:
    return MATCH.competing_value_count(leader, chunk)


def detector_d2(leader: str, chunk: str, quote: str | None = None) -> int:
    """D1 restricted to ±400 chars around the leader's first span occurrence — tests
    whether whole-chunk scanning over-fires on long spreadsheet-shaped chunks."""
    pos = -1
    for span in MATCH.numeric_spans(leader):
        pos = chunk.find(span)
        if pos >= 0:
            break
    if pos < 0:
        return detector_d1(leader, chunk)
    return MATCH.competing_value_count(
        leader, chunk[max(0, pos - _WINDOW): pos + len(leader) + _WINDOW])


_QUOTE_MARGIN = 120


def detector_d3(leader: str, chunk: str, quote: str | None = None) -> int:
    """Quote-scoped: competitors within the extractor's own grounded quote (±120 chars
    of its position in the chunk) — the anchor the extractor disambiguated by. A
    competitor INSIDE the anchor (q2-105's fax beside the tel) is the dangerous shape;
    same-shape values in other rows of a table are what the quote already resolved.
    DISCLOSED: added to the candidate set after D1/D2's collateral was read (24-32/56)
    — a post-look candidate, measured on the same archived evidence, named in §14.
    Falls back to the D2 window when the quote is absent or not found in the chunk."""
    if quote:
        return MATCH.quote_scoped_competitors(leader, chunk, quote)
    return detector_d2(leader, chunk, quote)


DETECTORS: dict[str, Callable[[str, str, str | None], int]] = {
    "D1": detector_d1, "D2": detector_d2, "D3": detector_d3}


@dataclass
class Row:
    qid: str
    action: str
    correct: bool | None
    withheld: str | None
    leader: str
    leader_p: float
    n_candidates: int
    n_obs: int
    evidence_source: str          # extract-cache | deliberate-toolcalls | catalogue-scan
    #                               | unrecovered | no-decision
    counts: dict[str, int] = field(default_factory=dict)   # detector -> n_competing

    def tempered(self, det: str, cap: int) -> float:
        # the sweep owns its factor grid (1/(1+min(n,cap))) — independent of the FROZEN
        # production cap in lookup.competition_factor, so future sweeps can re-tune
        n = self.counts.get(det, 0)
        return analytic_temper(self.leader_p, 1.0 / (1.0 + min(max(n, 0), cap)))

    def would_flip(self, det: str, cap: int) -> bool:
        return (self.action in _ASSERTS and self.counts.get(det, 0) > 0
                and self.tempered(det, cap) < COMMIT_BAR)


def load_decisions(run_id: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for line in LCFG.DECISIONS_LOG.read_text(encoding="utf-8").splitlines():
        if not line.strip() or run_id not in line:
            continue
        r = json.loads(line)
        if r.get("run_id") == run_id:
            out[str(r["question_id"])] = r
    return out


def _engine_version() -> str:
    import anthropic
    return str(anthropic.__version__)


Evidence = tuple[str, str | None]      # (chunk_text, extractor quote when proven)


def extract_cache_chunks(root: Path, conn: Any, question: str, leader: str,
                         engine_version: str, *, k: int = 20) -> list[Evidence]:
    """Rung 1: replay the deterministic base FTS retrieval and keep every hit whose
    CACHED extraction (a) exists, (b) found the leader's value, (c) passes the grounding
    gate — deterministic proof the audited run extracted the leader from that chunk.
    Carries the cached quote (the extractor's own anchor) for the quote-scoped D3."""
    chunks: list[Evidence] = []
    for hit in RET.retrieve_set(conn, RET.build_query(question, ""), k):
        chunk = str(hit["chunk_text"])
        key = D.lookup_extract_key(question, LK._sha(chunk), model=LK.LOOKUP_MODEL,
                                   prompt_template=LK.EXTRACT_PROMPT,
                                   engine_version=engine_version,
                                   output_schema=LK.EXTRACT_SCHEMA)
        cached = D.lookup(root, key.cache_key)
        if cached is None:
            continue
        parsed = json.loads(cached.decode("utf-8"))
        value = str(parsed.get("value") or "")
        quote = str(parsed.get("quote") or "")
        if (parsed.get("found") and LK._norm_value(value) == LK._norm_value(leader)
                and LK._grounded(quote, value, chunk)):
            chunks.append((chunk, quote))
    return chunks


def toolcall_chunks(qhash: str, leader: str) -> list[Evidence]:
    """Rung 3: the deliberate CLI's logged retrievals — containment-flagged, not proof."""
    path = LCFG.KB / "tmp" / "deliberate" / "tool_calls" / f"{qhash}.jsonl"
    if not path.exists():
        return []
    chunks: list[Evidence] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        for res in rec.get("results") or []:
            text = str(res.get("chunk_text_full") or res.get("chunk_text") or "")
            if text and MATCH.answer_matches(leader, [], text):
                chunks.append((text, None))
    return chunks


def catalogue_chunks(conn: Any, leader: str, *, limit: int = 5) -> list[Evidence]:
    """Rung 4: a containment scan of the pinned corpus — the chunk may not be the one
    the audited run read; flagged."""
    pats = {f"%{leader}%"} | {f"%{s}%" for s in MATCH.numeric_spans(leader)
                              if sum(ch.isdigit() for ch in s) >= 5}
    chunks: list[str] = []
    for pat in sorted(pats):
        rows = conn.execute(
            "SELECT chunk_text FROM artifact_chunks WHERE chunk_text LIKE ? LIMIT ?",
            [pat, limit]).fetchall()
        chunks.extend(str(r[0]) for r in rows)
        if chunks:
            break
    return [(c, None) for c in chunks if MATCH.answer_matches(leader, [], c)]


def audit_rows(paired: dict[str, dict], decisions: dict[str, dict],
               questions: list[dict],
               recover: Callable[[str, str, str], tuple[list[Evidence], str]],
               ) -> list[Row]:
    """One Row per paired question. ``recover(qid, question, leader)`` returns
    (chunks, evidence_source) — injected so tests stay hermetic."""
    q_by_id = {str(q["id"]): str(q["question"]) for q in questions}
    rows: list[Row] = []
    for qid in sorted(paired):
        typed = paired[qid]["typed"]
        question = q_by_id.get(qid)
        dec = decisions.get(_qhash(question)) if question is not None else None
        if dec is None:
            rows.append(Row(qid=qid, action=str(typed["action"]),
                            correct=typed.get("correct"), withheld=typed.get("withheld"),
                            leader="", leader_p=0.0, n_candidates=0, n_obs=0,
                            evidence_source="no-decision"))
            continue
        ps = dec.get("posterior_summary") or {}
        cands = list(ps.get("candidates") or [])
        creds = list(ps.get("credences") or [])
        leader = str(cands[0]) if cands else ""
        leader_p = float(creds[0]) if creds else 0.0
        chunks, source = recover(qid, str(question), leader) if leader else ([], "no-leader")
        counts = {name: max((det(leader, c, q) for c, q in chunks), default=0)
                  for name, det in DETECTORS.items()} if chunks else {}
        rows.append(Row(qid=qid, action=str(typed["action"]), correct=typed.get("correct"),
                        withheld=typed.get("withheld"), leader=leader, leader_p=leader_p,
                        n_candidates=len(cands), n_obs=int(ps.get("n_obs") or 0),
                        evidence_source=source if chunks else "unrecovered",
                        counts=counts))
    return rows


def summary_matrix(rows: list[Row], caps: list[int]) -> list[dict[str, Any]]:
    commits = [r for r in rows if r.action in _ASSERTS]
    wrongs = [r for r in commits if r.correct is False]
    rights = [r for r in commits if r.correct is True]
    out: list[dict[str, Any]] = []
    for det in DETECTORS:
        for cap in caps:
            out.append({
                "detector": det, "cap": cap,
                "factor_at_1": 0.5,
                "wrong_flips": sorted(r.qid for r in wrongs if r.would_flip(det, cap)),
                "n_wrongs": len(wrongs),
                "collateral": sorted(r.qid for r in rights if r.would_flip(det, cap)),
                "n_rights": len(rights),
            })
    return out


def render(rows: list[Row], matrix: list[dict[str, Any]], caps: list[int],
           run_id: str) -> str:
    unrec = [r.qid for r in rows if r.evidence_source in ("unrecovered", "no-leader")]
    nodec = [r.qid for r in rows if r.evidence_source == "no-decision"]
    lines = [
        f"# Temper audit — {run_id}", "",
        "**Off-gate, $0, zero model calls.** " + __doc__.split("\n\n")[2], "",
        f"- rows: {len(rows)} ({sum(1 for r in rows if r.action in _ASSERTS)} commits, "
        f"{sum(1 for r in rows if r.withheld)} withheld); commit bar {COMMIT_BAR} "
        f"(the run's own empirical bracket)",
        "- evidence recovery: " + ", ".join(
            f"{src} {sum(1 for r in rows if r.evidence_source == src)}"
            for src in ("extract-cache", "deliberate-toolcalls", "catalogue-scan",
                        "unrecovered", "no-decision")),
        f"- NOT COVERED (named, per the no-silent-caps rule): "
        f"unrecovered {unrec or '—'}; no decision row {nodec or '—'}", "",
        "## Sweep matrix", "",
        "| detector | cap | f(1) | wrong flips | collateral (✓→withheld) |",
        "|---|---|---|---|---|",
    ]
    for m in matrix:
        lines.append(f"| {m['detector']} | {m['cap']} | {m['factor_at_1']} "
                     f"| {len(m['wrong_flips'])}/{m['n_wrongs']} {m['wrong_flips']} "
                     f"| {len(m['collateral'])}/{m['n_rights']} {m['collateral']} |")
    lines += ["", "## Per-question detail (commits first)", "",
              "| qid | action | ok | leader | p | n_cand | n_obs | source | "
              + " | ".join(DETECTORS) + " | " + " | ".join(
                  f"p'@{d}/cap{c}" for d in DETECTORS for c in caps) + " |",
              "|" + "---|" * (8 + len(DETECTORS) + len(DETECTORS) * len(caps))]
    for r in sorted(rows, key=lambda r: (r.action not in _ASSERTS, r.correct is not False,
                                         r.qid)):
        tempered = " | ".join(f"{r.tempered(d, c):.3f}" + ("←flip" if r.would_flip(d, c)
                                                           else "")
                              for d in DETECTORS for c in caps)
        ok = {True: "✓", False: "✗"}.get(r.correct, "·")
        lines.append(f"| {r.qid} | {r.action} | {ok} | {r.leader[:28]} | {r.leader_p:.3f} "
                     f"| {r.n_candidates} | {r.n_obs} | {r.evidence_source} | "
                     + " | ".join(str(r.counts.get(d, 0)) for d in DETECTORS)
                     + " | " + tempered + " |")
    return "\n".join(lines) + "\n"


def synth_paired(paired: dict[str, dict], rows: list[Row], det: str, cap: int,
                 out_dir: Path, *, extra_cost: float = 0.45) -> tuple[Path, Path]:
    """The counterfactual inputs for gate_splice: every would-flip typed commit rewritten
    to a dispersed abstain. Floor keeps the archived spend; stressed adds the re-opened
    VOI ladder's expected cold-deliberate cost per flip."""
    flips = {r.qid for r in rows if r.would_flip(det, cap)}
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for tag, extra in (("floor", 0.0), ("stressed", extra_cost)):
        out = out_dir / f"paired-temper-{det.lower()}-cap{cap}-{tag}.jsonl"
        with out.open("w", encoding="utf-8") as fh:
            for qid in sorted(paired):
                row = json.loads(json.dumps(paired[qid]))  # deep copy
                if qid in flips:
                    t = row["typed"]
                    t.update({"action": "abstain", "correct": None,
                              "withheld": "dispersed",
                              "cost_usd": float(t.get("cost_usd") or 0.0) + extra})
                fh.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
        paths.append(out)
    return paths[0], paths[1]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--paired", type=Path, required=True)
    ap.add_argument("--questions", type=Path, default=None)
    ap.add_argument("--caps", default="1,2,3")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--out-yaml", type=Path, default=None)
    ap.add_argument("--synth", nargs=3, metavar=("DET", "CAP", "DIR"), default=None,
                    help="write floor+stressed counterfactual paired files for the "
                         "frozen (detector, cap) choice")
    args = ap.parse_args(argv)

    caps = [int(c) for c in str(args.caps).split(",")]
    questions = load_questions(args.questions) if args.questions else load_questions()
    paired = load_paired(args.paired)
    decisions = load_decisions(args.run_id)
    root = LCFG.pkm_root()
    if root is None:
        print("REFUSED: no pkm root (PKM_CONFIG unresolvable)")
        return 2
    import duckdb
    conn = duckdb.connect(str(root / "catalogue.duckdb"), read_only=True)
    ev = _engine_version()

    def recover(qid: str, question: str, leader: str) -> tuple[list[str], str]:
        chunks = extract_cache_chunks(root, conn, question, leader, ev)
        if chunks:
            return chunks, "extract-cache"
        chunks = toolcall_chunks(_qhash(question), leader)
        if chunks:
            return chunks, "deliberate-toolcalls"
        chunks = catalogue_chunks(conn, leader)
        if chunks:
            return chunks, "catalogue-scan"
        return [], "unrecovered"

    try:
        rows = audit_rows(paired, decisions, questions, recover)
    finally:
        conn.close()
    matrix = summary_matrix(rows, caps)
    report = render(rows, matrix, caps, args.run_id)
    print(report)
    if args.out:
        args.out.write_text(report, encoding="utf-8")
        print(f"wrote {args.out}")
    if args.out_yaml:
        import yaml
        args.out_yaml.write_text(yaml.safe_dump(
            {"run_id": args.run_id, "commit_bar": COMMIT_BAR,
             "rows": [vars(r) for r in rows], "matrix": matrix},
            sort_keys=False, allow_unicode=True), encoding="utf-8")
        print(f"wrote {args.out_yaml}")
    if args.synth:
        det, cap, out_dir = args.synth[0], int(args.synth[1]), Path(args.synth[2])
        floor, stressed = synth_paired(paired, rows, det, cap, out_dir)
        print(f"synthesized {floor} and {stressed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
