#!/usr/bin/env python3
"""THROWAWAY probe (D3): does grounded faithful monetary-mention extraction hold on the
real RTL/OCR corpus, before we freeze any SPEC?  Not the production transform — calls the
local model directly with a *candidate* grammar and a grounding check, writes a report to a
scratch dir, never touches the pkm cache.

The candidate grammar is the schema-on-read faithful-observation list: each mention is what
the document *asserts* (amount as printed, dimension as printed, the verbatim label printed
next to it, the period/entity as stated, a source-span quote) — NO `kind`, NO normalisation,
NO summability.  Grounding (the metric that matters) is checked two ways:
  - amount: its normalised digit-run must appear among the source's digit-runs;
  - label & quote: §18.5 whitespace-normalised containment in the source.

Run:  uv run python scripts/probe_amount_extraction.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import duckdb
import yaml

from life_agent.core import config as C
from pkm.cache import content_file
from pkm.chunking import extract_text
from pkm.transforms._shared import OllamaClient, quote_is_grounded


def _live_root() -> Path:
    """The live pkm root, resolved from PKM_CONFIG exactly as scripts/ask.py does —
    no machine-specific path baked into this (public-repo) file."""
    cfg = yaml.safe_load(C.PKM_CONFIG.read_text(encoding="utf-8"))
    return Path(cfg["root_dir"]).expanduser()


LIVE_ROOT = _live_root()
CATALOGUE = LIVE_ROOT / "catalogue.duckdb"
OUT_DIR = C.KB / "eval" / "d3-amount-probe"
MODEL = "qwen2.5:7b-instruct"
MAX_INPUT_CHARS = 9000  # head-cap; financial figures lead these documents

# Candidate grammar — the faithful-observation list. `amount`/`dimension`/`label`/`quote`
# required; `basis_as_stated`/`entity_as_stated` nullable. `amount` is a STRING (the digit-run
# exactly as printed — faithful transcription; parsing to a number is above the seam).
SCHEMA = {
    "type": "object",
    "required": ["mentions"],
    "properties": {
        "mentions": {
            "type": "array",
            "maxItems": 12,
            "items": {
                "type": "object",
                "required": ["amount", "dimension", "label", "quote"],
                "properties": {
                    "amount": {"type": "string"},
                    "dimension": {"type": "string"},
                    "label": {"type": "string"},
                    "basis_as_stated": {"type": ["string", "null"]},
                    "entity_as_stated": {"type": ["string", "null"]},
                    "quote": {"type": "string"},
                },
            },
        }
    },
}

PROMPT = """You are a faithful transcriber of financial documents. The text below was \
extracted from one document (it may be Hebrew, right-to-left, or noisy OCR).

CRITICAL: the document may be in Hebrew. Copy every word EXACTLY as printed, in its \
ORIGINAL language and script. NEVER translate or transliterate a Hebrew label into English \
or Chinese — if the page prints "דמי ניהול" you write "דמי ניהול", never "management fee" \
or "管理费". A translated label is a wrong answer.

List every MONETARY figure and every PERCENTAGE the document states. For each, copy ONLY \
what the page actually prints — do not interpret, convert, translate, annualise, or total \
anything:
- "amount": the number EXACTLY as printed (keep its digits, separators, decimals).
- "dimension": the unit as printed next to it (e.g. "₪", "ש\\"ח", "ILS", "%", or "" if none).
- "label": the word or short phrase the page prints next to the number saying what it is \
(e.g. "ברוטו", "צבירה", "נטו לתשלום", "management fee") — copied verbatim from the text.
- "basis_as_stated": the period or date the page prints for this figure (e.g. "שנתי", \
"לחודש 03/2025", "ליום 30/06/2025"), or null if none is printed.
- "entity_as_stated": the employer / fund / provider / account the page prints, or null.
- "quote": a short verbatim span from the text that contains this number and its label.

Rules:
- Copy, never compute. If you cannot quote it from the text, do not list it.
- Every "amount", "label" and "quote" MUST be a substring you can find in the text. If the \
text is unreadable garbage, return an empty list.
- Do not invent a currency or label that is not printed.

Return JSON: {"mentions": [...]}.

--- DOCUMENT TEXT ---
__DOCTEXT__
--- END ---"""

_DIGITS = re.compile(r"\d+")


def digit_runs(text: str) -> set[str]:
    """Maximal digit sequences, separators stripped — the normalised digit-run basis.

    '₪123,456' / '123,456' / '123456' all reduce to the run '123456'. We compare an emitted
    amount's concatenated digits against the source's, so faithful transcription grounds
    regardless of currency glyph, thousands separator, or RTL ordering."""
    toks = (tok for tok in re.split(r"\s+", text) if any(c.isdigit() for c in tok))
    return set(_DIGITS.findall(text)) | {"".join(_DIGITS.findall(tok)) for tok in toks}


def amount_grounded(amount: str, source: str, source_digit_runs: set[str]) -> bool:
    """The amount's digits appear contiguously in the source (separators ignored)."""
    a = "".join(_DIGITS.findall(amount))
    if not a:
        return False
    # direct run match, or appears within the fully digit-stripped source stream
    if a in source_digit_runs:
        return True
    stripped_source = "".join(_DIGITS.findall(source))
    return a in stripped_source


# Filename markers that pick out the owner's real financial docs (provider names, payslip
# terms) and the OCR negative controls are PII — they reveal which funds/banks/accounts the
# owner holds — so they live out-of-tree, NOT in this public repo. We read them from
# $LIFE_AGENT_KB/eval/d3-amount-probe/targets.yaml (`financial`: a regexp-alternation string;
# `ocr_control`: a SQL LIKE pattern). Absent file => probe refuses rather than guess.
TARGETS_FILE = OUT_DIR / "targets.yaml"


def _load_markers() -> dict:
    if not TARGETS_FILE.exists():
        raise SystemExit(
            f"no marker file at {TARGETS_FILE} — write it (out-of-tree, PII):\n"
            "  financial: 'provider1|provider2|...'   # regexp alternation over lower(path)\n"
            "  ocr_control: '%PREFIX%'                 # SQL LIKE for negative controls\n"
        )
    spec = yaml.safe_load(TARGETS_FILE.read_text(encoding="utf-8"))
    return {"financial": str(spec["financial"]), "ocr_control": str(spec["ocr_control"])}


def select_targets(conn: duckdb.DuckDBPyConnection) -> list[dict]:
    """~20 real financial docs + OCR-soup negative controls, chosen by filename markers so
    the set is deterministic and inspectable. Markers are loaded out-of-tree (see above)."""
    markers = _load_markers()
    rows = conn.execute(
        """
        SELECT a.cache_key, a.producer_name, a.content_type, any_value(sp.path) AS path
        FROM artifacts a JOIN source_paths sp ON a.input_hash = sp.source_id
        WHERE a.status='success' AND a.producer_name IN ('docling','tesseract')
          AND regexp_matches(lower(sp.path), ?)
        GROUP BY a.cache_key, a.producer_name, a.content_type
        ORDER BY a.producer_name, path
        LIMIT 22
        """,
        [markers["financial"]],
    ).fetchall()
    targets = [{"key": r[0], "producer": r[1], "content_type": r[2], "path": r[3],
                "role": "financial"} for r in rows]
    # negative controls: garbled OCR scans (expect ~zero groundable mentions)
    ctrl = conn.execute(
        """
        SELECT a.cache_key, a.producer_name, a.content_type, any_value(sp.path) AS path
        FROM artifacts a JOIN source_paths sp ON a.input_hash = sp.source_id
        WHERE a.status='success' AND a.producer_name='tesseract' AND sp.path LIKE ?
        GROUP BY a.cache_key, a.producer_name, a.content_type ORDER BY path LIMIT 3
        """,
        [markers["ocr_control"]],
    ).fetchall()
    targets += [{"key": r[0], "producer": r[1], "content_type": r[2], "path": r[3],
                 "role": "ocr-control"} for r in ctrl]
    return targets


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(CATALOGUE), read_only=True)
    targets = select_targets(conn)
    client = OllamaClient(MODEL, {"temperature": 0.0})
    print(f"probing {len(targets)} documents with {MODEL}\n", flush=True)

    report: list[dict] = []
    for i, t in enumerate(targets, 1):
        cf = content_file(LIVE_ROOT, t["key"])
        if not cf.exists():
            print(f"[{i:2}] MISSING content {t['key'][:10]} {t['path']}", flush=True)
            continue
        # text projection (docling/unstructured artifacts are JSON; feed readable text,
        # not raw JSON) — the same extract_text the retrieval path uses for chunking.
        source = extract_text(cf.read_bytes(), t["content_type"] or "text/plain")
        head = source[:MAX_INPUT_CHARS]
        name = str(t["path"]).split("/")[-1]
        try:
            resp = client.complete(PROMPT.replace("__DOCTEXT__", head), SCHEMA)
            mentions = json.loads(resp.raw_text).get("mentions", [])
        except Exception as e:  # throwaway probe — record the failure, keep going
            print(f"[{i:2}] ERROR {name[:40]}: {e}", flush=True)
            report.append({**t, "error": str(e)})
            continue

        sruns = digit_runs(source)
        rows = []
        for m in mentions:
            amt = str(m.get("amount", ""))
            lbl = str(m.get("label", ""))
            q = str(m.get("quote", ""))
            rows.append({
                "amount": amt,
                "dimension": m.get("dimension", ""),
                "label": lbl,
                "basis": m.get("basis_as_stated"),
                "entity": m.get("entity_as_stated"),
                "amount_grounded": amount_grounded(amt, source, sruns),
                "label_grounded": quote_is_grounded(lbl, source) if lbl else False,
                "quote_grounded": quote_is_grounded(q, source) if q else False,
            })
        n = len(rows)
        ag = sum(r["amount_grounded"] for r in rows)
        lg = sum(r["label_grounded"] for r in rows)
        qg = sum(r["quote_grounded"] for r in rows)
        report.append({**t, "name": name, "n_mentions": n, "amount_grounded": ag,
                       "label_grounded": lg, "quote_grounded": qg,
                       "latency_ms": resp.latency_ms, "rows": rows})
        flag = "CTRL" if t["role"] == "ocr-control" else "    "
        print(f"[{i:2}] {flag} {name[:38]:38} n={n:2} amt✓={ag:2}/{n:<2} lbl✓={lg:2} q✓={qg:2} "
              f"{resp.latency_ms}ms", flush=True)

    (OUT_DIR / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))

    fin = [r for r in report if r.get("role") == "financial" and "n_mentions" in r]
    ctl = [r for r in report if r.get("role") == "ocr-control" and "n_mentions" in r]
    tot_m = sum(r["n_mentions"] for r in fin)
    tot_ag = sum(r["amount_grounded"] for r in fin)
    tot_lg = sum(r["label_grounded"] for r in fin)
    docs_with = sum(1 for r in fin if r["amount_grounded"] > 0)
    ctl_emit = sum(r["n_mentions"] for r in ctl)
    ctl_ground = sum(r["amount_grounded"] for r in ctl)
    print("\n========== SUMMARY ==========")
    print(f"financial docs: {len(fin)}  | with >=1 grounded amount: {docs_with}")
    print(f"mentions emitted: {tot_m}  | amount-grounded: {tot_ag} "
          f"({100*tot_ag//max(tot_m,1)}%)  | label-grounded: {tot_lg} "
          f"({100*tot_lg//max(tot_m,1)}%)")
    print(f"hallucination (emitted amount NOT in source): {tot_m - tot_ag}")
    print(f"OCR controls: {len(ctl)} docs | emitted {ctl_emit} | grounded {ctl_ground} "
          f"(want ~0 — safe silence on garbage)")
    print(f"\nfull report: {OUT_DIR / 'report.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
