#!/usr/bin/env python3
"""r29 — the answer-shape census. A $0 read that adopts nothing.

The plan of 2026-08-28 proposes re-deriving the answer as *a claim about a quantity*, valued
by a loss whose shape is a property of the question. That opens two owner-adopted foundations
(§4.4's gauge, §5's claim space), so its size is bought with evidence first. This instrument
is that evidence. It makes zero model calls: every read is a fold over records that already
exist.

Three reads, each frozen in ``docs/unification/reports/r29-answer-shape-census.md`` before
this file was written:

  1. **the shape census** — every question on two axes, from surface form alone:
     *answer space* (``exact``/``quantity``/``threshold``/``set``) and *truth provenance*
     (``verbatim``: the answer stands as a span in some document · ``computed``: it must be
     derived). The axes are orthogonal and both bind. ``quantity ∧ verbatim`` is a recorded
     figure — today's 0-1 loss is attainable there, merely wasteful. ``quantity ∧ computed``
     is the class where the loss is structurally unreachable at any evidence budget.
  2. **the structural-abstention prediction** — ``computed`` questions should abstain at or
     above 0.95 and materially above the ``verbatim`` rate, because P(exact match) ≈ 0 for a
     figure no document carries.
  3. **run 17's collapse** — the grow actuators' hand-set cold Beta priors, priced against
     the realised gather-outcome stream, beside the run-17-vs-run-18 per-row flip set.

**Two populations, never pooled** (C4). The gate set was CONSTRUCTED from corpus facts chosen
to be answerable, so it is a census of the eval instrument, not of the owner's questions. The
owner-origin population is the harvest minus every ask whose normalised text matches a gate
question — and on this corpus that match is exact and total, so the contamination is not an
estimate.

**The default is the strict shape** (C3): an unmatched question reads ``exact`` + ``verbatim``,
the shape under which today's design is adequate. The census is therefore biased toward
"the generalisation is niche"; any other finding survives that bias.

**The deployed constants are read, never retyped** (C7): the grow priors come from
``life_agent.core.pricing.GROW_ACTUATORS`` by import and the warm fold is cross-checked
against ``life_agent.core.gather_outcomes.warm_counts``. r05's lesson, r10's flipped verdict.

Every output row keys on a question id and a class name. No question text, gold answer or
corpus value is ever written to a path this instrument controls inside the repo (C9).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from collections.abc import Iterable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

# --- the frozen classification rules -----------------------------------------------------
# Ordered; first match wins; no match falls to the conservative default. These patterns ARE
# the pre-registration's table, transcribed once. Editing one is a new checkpoint, not a fix.

_COMPARATORS = (
    r"\bmore than\b", r"\bless than\b", r"\bat least\b", r"\bat most\b",
    r"\bexceed(s|ed|ing)?\b", r"\bgreater than\b", r"\bhigher than\b", r"\blower than\b",
    r"\bover\s+\d", r"\bunder\s+\d", r"\babove\s+\d", r"\bbelow\s+\d",
)
_YES_NO = r"^(did|is|was|were|does|do|has|have|had|are|am|will|can)\b"

SPACE_RULES: list[tuple[str, list[str]]] = [
    ("threshold", list(_COMPARATORS)),
    ("set", [r"\blist\b", r"\bwhich ones\b", r"\ball of the\b", r"\bwhat are the\b",
             r"\bwho are the\b", r"\bname the\b", r"\benumerate\b", r"\bevery\s+\w+s\b"]),
    ("quantity", [r"\bhow many\b", r"\bhow much\b", r"\btotal\b", r"\bsum\b", r"\baverage\b",
                  r"\bmean of\b", r"\bcount of\b", r"\bnumber of\b", r"\bamount\b",
                  r"\bbalances?\b", r"\baggregate\b"]),
]
DEFAULT_SPACE = "exact"

COMPUTED_CUES: list[str] = [
    r"\bacross all\b", r"\bacross my\b", r"\bacross every\b", r"\bin total\b",
    r"\btotal of\b", r"\btotal across\b", r"\bsum of\b", r"\badded up\b", r"\badd up\b",
    r"\bcombined\b", r"\baltogether\b", r"\bon average\b", r"\baverage of\b",
    r"\boverall total\b", r"\bhow many\b.*\b(do i have|have i)\b", r"\beach of my\b",
    r"\ball of my\b.*\b(combined|together|total)\b",
]
DEFAULT_PROVENANCE = "verbatim"

AGREEMENT_BAR = 0.80  # C5: below this an axis publishes bounds, not point estimates


def normalise(text: str) -> str:
    """Lowercase, whitespace-collapsed. The one normalisation, shared by the classifier and
    the population split, so a question cannot be eval-derived for one and not the other."""
    return re.sub(r"\s+", " ", str(text).strip().lower())


def answer_space(text: str) -> str:
    """Axis 1, in the frozen precedence order threshold > set > quantity > exact."""
    t = normalise(text)
    for label, patterns in SPACE_RULES:
        if any(re.search(p, t) for p in patterns):
            return label
        if label == "threshold" and re.search(_YES_NO, t) and re.search(r"\d", t):
            return "threshold"
    return DEFAULT_SPACE


def truth_provenance(text: str) -> str:
    """Axis 2. ``computed`` iff an explicit aggregation or multi-source marker is present;
    a bare 'total' adjacent to a recorded field is NOT computed."""
    t = normalise(text)
    return "computed" if any(re.search(c, t) for c in COMPUTED_CUES) else DEFAULT_PROVENANCE


def classify(text: str) -> dict[str, str]:
    return {"space": answer_space(text), "provenance": truth_provenance(text)}


# --- C4: the population split ------------------------------------------------------------

def split_populations(gate: list[dict[str, Any]],
                      asks: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Exhaustive: every ask lands in exactly one side. Eval-derived ⇔ its normalised text
    is a gate question's."""
    gate_norm = {normalise(q["question"]) for q in gate}
    out: dict[str, list[dict[str, Any]]] = {"eval_derived": [], "owner_origin": []}
    for row in asks:
        side = "eval_derived" if normalise(row["question"]) in gate_norm else "owner_origin"
        out[side].append(row)
    return out


# --- C5: measured agreement --------------------------------------------------------------

def agreement(manual: list[dict[str, Any]],
              auto: dict[str, dict[str, str]]) -> dict[str, dict[str, Any]]:
    """Per-axis agreement between the blind manual reference and the classifier, with the
    direction of every disagreement named. Below ``AGREEMENT_BAR`` the axis is flagged
    ``bounds_only`` and its counts publish as bounds."""
    rep: dict[str, dict[str, Any]] = {}
    for axis, mkey in (("space", "space"), ("provenance", "prov")):
        n = agree = 0
        disagreements: list[dict[str, str]] = []
        for row in manual:
            got = auto.get(str(row["id"]))
            if got is None:
                continue
            n += 1
            if got[axis] == row[mkey]:
                agree += 1
            else:
                disagreements.append({"id": str(row["id"]), "pop": str(row.get("pop", "")),
                                      "manual": str(row[mkey]), "auto": str(got[axis])})
        rate = (agree / n) if n else 0.0
        rep[axis] = {"n": n, "agree": agree, "rate": rate,
                     "bounds_only": rate < AGREEMENT_BAR,
                     "directions": dict(Counter(f'{d["manual"]}->{d["auto"]}'
                                                for d in disagreements).most_common()),
                     "disagreements": disagreements}
    return rep


# --- read 2: the structural-abstention prediction ----------------------------------------

_ASSERTS = {"report", "report_scoped", "hedge"}


def _rate_block(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(rows)
    abstained = sum(1 for r in rows if r["chosen_action"] == "abstain")
    return {"n": len(rows), "abstained": abstained,
            "rate": (abstained / len(rows)) if rows else 0.0}


def abstention_by_provenance(asks: list[dict[str, Any]],
                             labels: dict[str, dict[str, str]]) -> dict[str, Any]:
    """Decided rows only — an undecided ask has no action to read, and is COUNTED rather
    than dropped."""
    decided = [r for r in asks if r.get("decided") and r.get("chosen_action")]
    out: dict[str, Any] = {"undecided": len(asks) - len(decided)}
    for prov in ("verbatim", "computed"):
        out[prov] = _rate_block(r for r in decided
                                if labels.get(str(r["question_id"]), {}).get("provenance") == prov)
    out["by_space"] = {
        space: _rate_block(r for r in decided
                           if labels.get(str(r["question_id"]), {}).get("space") == space)
        for space in ("exact", "quantity", "threshold", "set")}
    return out


# --- read 3: the hand-priced grow actuators ----------------------------------------------

def _fold(stream: Iterable[dict[str, Any]], probe: str) -> dict[tuple[str, ...], list[int]]:
    """(n1, n0) per context vector for one probe — the same fold shape the daemon replays."""
    counts: dict[tuple[str, ...], list[int]] = {}
    for row in stream:
        if str(row.get("probe")) != probe:
            continue
        key = tuple(str(v) for v in row["ctx"])
        n = counts.setdefault(key, [0, 0])
        n[0 if row.get("recovered") else 1] += 1
    return counts


def cross_check_warm_fold(stream: Iterable[dict[str, Any]],
                          deployed: dict[str, Any] | None, *, probe: str) -> None:
    """The census's fold must equal ``gather_outcomes.warm_counts``. Fails loud on drift —
    a census that quietly re-implements the fold it prices is r05's defect."""
    mine = {tuple(k): tuple(v) for k, v in _fold(stream, probe).items()}
    theirs = {tuple(str(v) for v in c["ctx"]): (int(c["n1"]), int(c["n0"]))
              for c in ((deployed or {}).get("contexts") or [])}
    if mine != theirs:
        raise ValueError(
            f"warm fold disagrees with the deployed one for probe {probe!r}: "
            f"census {sorted(mine.items())} vs deployed {sorted(theirs.items())}")


def grow_prior_gap(stream: list[dict[str, Any]],
                   actuators: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per DEPLOYED actuator: where its hand-set cold prior sits, where the realised
    stream sits, and where the warm posterior lands between them. Contexts sorted."""
    rows: list[dict[str, Any]] = []
    for act in actuators:
        probe = str(act["probe"])
        a0, b0 = float(act["alpha0"]), float(act["beta0"])
        counts = _fold(stream, probe)
        n1 = sum(v[0] for v in counts.values())
        n0 = sum(v[1] for v in counts.values())
        n = n1 + n0
        rows.append({
            "probe": probe,
            "cost": float(act["cost"]),
            "cold_prior_mean": a0 / (a0 + b0),
            "prior_strength": a0 + b0,
            "n": n, "n_recovered": n1,
            "realised_rate": (n1 / n) if n else None,
            "warm_posterior_mean": (a0 + n1) / (a0 + b0 + n),
            "contexts": [
                {"ctx": list(k), "n1": v[0], "n0": v[1],
                 "realised_rate": v[0] / (v[0] + v[1]),
                 "warm_posterior_mean": (a0 + v[0]) / (a0 + b0 + v[0] + v[1]),
                 "prior_weight": (a0 + b0) / (a0 + b0 + v[0] + v[1])}
                for k, v in sorted(counts.items())],
        })
    return rows


# --- read 3, extension: whose rows are these? --------------------------------------------
# Disclosed extension (added after the first reading). The realised rate a decision SAW is
# the rate BEFORE its own run appended to the stream — and the stream is append-only and
# unsegmented, so a run made under a policy later reverted leaves its rows behind for every
# later warm fold to learn from.

def run_window(meta: dict[str, Any], report_text: str) -> tuple[str, datetime, datetime]:
    """One run's UTC window, read from ITS OWN records. ``run_id`` carries a LOCAL timestamp;
    ``created_at`` is UTC — deriving the window from the id is wrong by the machine's offset."""
    m = re.search(r"elapsed=([\d.]+)s", report_text)
    if not m:
        raise ValueError("no elapsed= in the report — the window's end is unreadable")
    start = datetime.fromisoformat(str(meta["created_at"]).replace("Z", "+00:00"))
    return str(meta["run_id"]), start, start + timedelta(seconds=float(m.group(1)))


def _stream_block(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n1 = sum(1 for r in rows if r.get("recovered"))
    by: dict[str, dict[str, Any]] = {}
    for probe in sorted({str(r["probe"]) for r in rows}):
        sub = [r for r in rows if str(r["probe"]) == probe]
        k = sum(1 for r in sub if r.get("recovered"))
        by[probe] = {"n": len(sub), "n_recovered": k, "rate": k / len(sub)}
    return {"n": len(rows), "n_recovered": n1,
            "rate": (n1 / len(rows)) if rows else 0.0, "by_probe": by}


def window_attribution(stream: list[dict[str, Any]],
                       windows: list[tuple[str, datetime, datetime]]) -> dict[str, Any]:
    """Split the stream into each run's rows, everything before the earliest window, and the
    remainder. Windows are assumed disjoint; a row lands in the first window containing it."""
    def when(row: dict[str, Any]) -> datetime:
        return datetime.fromisoformat(str(row["tx_time"]))
    first = min((w[1] for w in windows), default=None)
    inside: dict[str, list[dict[str, Any]]] = {w[0]: [] for w in windows}
    before: list[dict[str, Any]] = []
    outside: list[dict[str, Any]] = []
    for row in stream:
        t = when(row)
        for label, a, b in windows:
            if a <= t <= b:
                inside[label].append(row)
                break
        else:
            (before if first is not None and t < first else outside).append(row)
    return {"windows": {k: _stream_block(v) for k, v in inside.items()},
            "before_first": _stream_block(before), "outside": _stream_block(outside)}


# --- C8: the per-row flip set ------------------------------------------------------------

def flip_set(arm_a: list[dict[str, Any]], arm_b: list[dict[str, Any]]) -> dict[str, Any]:
    """Per-row typed-action flips between two paired archives, over the Δ-included rows
    (censored dropped — r28's one declaration of the set Δ folds). ``a`` is the run under
    test, ``b`` the reference."""
    def keyed(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        return {str(r["question_id"]): r for r in rows if not r.get("censored")}
    ka, kb = keyed(arm_a), keyed(arm_b)
    if set(ka) != set(kb):
        raise ValueError("the two archives do not cover the same question set: "
                         f"{len(set(ka) ^ set(kb))} row(s) differ")
    ids = sorted(ka)
    flips = [{"question_id": i, "from_b": kb[i]["typed"]["action"],
              "to_a": ka[i]["typed"]["action"],
              "spend_a": float(ka[i]["typed"].get("cost_usd") or 0.0),
              "spend_b": float(kb[i]["typed"].get("cost_usd") or 0.0)}
             for i in ids if ka[i]["typed"]["action"] != kb[i]["typed"]["action"]]
    def mean(rows: dict[str, dict[str, Any]]) -> float:
        vals = [float(rows[i]["typed"].get("cost_usd") or 0.0) for i in ids]
        return sum(vals) / len(vals) if vals else 0.0
    def asserts(rows: dict[str, dict[str, Any]]) -> int:
        return sum(1 for i in ids if rows[i]["typed"]["action"] in _ASSERTS)
    na, nb = asserts(ka), asserts(kb)
    return {"n_rows": len(ids), "flips": flips, "n_flips": len(flips),
            "asserts_a": na, "asserts_b": nb,
            "answer_rate_a": (na / len(ids)) if ids else 0.0,
            "answer_rate_b": (nb / len(ids)) if ids else 0.0,
            "directions": dict(Counter(f'{x["from_b"]}->{x["to_a"]}' for x in flips).most_common()),
            "mean_spend_a": mean(ka), "mean_spend_b": mean(kb),
            "mean_spend_a_on_flips": (sum(f["spend_a"] for f in flips) / len(flips))
                                     if flips else None,
            "mean_spend_b_on_flips": (sum(f["spend_b"] for f in flips) / len(flips))
                                     if flips else None}


# --- the census -------------------------------------------------------------------------

def _counts(labels: Iterable[dict[str, str]]) -> dict[str, Any]:
    labels = list(labels)
    n = len(labels)
    both = sum(1 for c in labels if c["space"] == "exact" and c["provenance"] == "verbatim")
    return {"n": n,
            "space": dict(Counter(c["space"] for c in labels).most_common()),
            "provenance": dict(Counter(c["provenance"] for c in labels).most_common()),
            "joint": dict(Counter(f"{c['space']}|{c['provenance']}"
                                  for c in labels).most_common()),
            "exact_and_verbatim": both,
            "exact_and_verbatim_frac": (both / n) if n else 0.0}


def census(gate: list[dict[str, Any]], asks: list[dict[str, Any]]) -> dict[str, Any]:
    split = split_populations(gate, asks)
    gate_labels = {str(q["id"]): classify(q["question"]) for q in gate}
    ask_labels = {str(r["question_id"]): classify(r["question"]) for r in asks}
    owner = split["owner_origin"]
    return {
        "populations": {"gate": len(gate), "harvest": len(asks),
                        "eval_derived": len(split["eval_derived"]),
                        "owner_origin": len(owner)},
        "gate_labels": gate_labels, "ask_labels": ask_labels,
        "counts": {
            "gate": _counts(gate_labels.values()),
            "owner_origin": _counts(ask_labels[str(r["question_id"])] for r in owner),
        },
        "abstention": abstention_by_provenance(owner, ask_labels),
    }


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="r29 — the answer-shape census ($0)")
    ap.add_argument("--gate-questions", type=Path, required=True)
    ap.add_argument("--asks", type=Path, required=True)
    ap.add_argument("--manual", type=Path, required=True)
    ap.add_argument("--gather-outcomes", type=Path, required=True)
    ap.add_argument("--paired-a", type=Path, required=True, help="the run under test (run 17)")
    ap.add_argument("--paired-b", type=Path, required=True, help="the reference run (run 18)")
    ap.add_argument("--run", nargs=2, action="append", metavar=("RUN_META", "REPORT"),
                    default=[], help="attribute the stream to this run's own UTC window")
    ap.add_argument("--out", type=Path, required=True, help="out-of-tree result path (JSON)")
    args = ap.parse_args(argv)

    import yaml

    from life_agent.core import gather_outcomes as GO
    from life_agent.core import pricing as PRC

    gate = yaml.safe_load(args.gate_questions.read_text(encoding="utf-8"))["questions"]
    asks = _load_jsonl(args.asks)
    result = census(gate, asks)

    manual = _load_jsonl(args.manual)
    auto = {**result["gate_labels"], **result["ask_labels"]}
    result["agreement"] = agreement(manual, auto)

    stream = _load_jsonl(args.gather_outcomes)
    for act in PRC.GROW_ACTUATORS:                      # C7: the deployed fold, cross-checked
        cross_check_warm_fold(stream, GO.warm_counts(args.gather_outcomes, str(act["probe"])),
                              probe=str(act["probe"]))
    result["grow"] = grow_prior_gap(stream, PRC.GROW_ACTUATORS)
    if args.run:
        windows = [run_window(json.loads(Path(m).read_text(encoding="utf-8")),
                              Path(r).read_text(encoding="utf-8")) for m, r in args.run]
        result["stream_attribution"] = window_attribution(stream, windows)
    result["flip"] = flip_set(_load_jsonl(args.paired_a), _load_jsonl(args.paired_b))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
                        encoding="utf-8")

    p, c = result["populations"], result["counts"]
    print(f"populations: gate {p['gate']} · harvest {p['harvest']} "
          f"= eval-derived {p['eval_derived']} + owner-origin {p['owner_origin']}")
    for pop in ("gate", "owner_origin"):
        b = c[pop]
        print(f"{pop:13s} n={b['n']:3d}  space={b['space']}  prov={b['provenance']}  "
              f"exact&verbatim={b['exact_and_verbatim']} ({b['exact_and_verbatim_frac']:.2f})")
    for axis, a in result["agreement"].items():
        print(f"agreement[{axis}] {a['agree']}/{a['n']} = {a['rate']:.2f}"
              f"{'  BOUNDS-ONLY' if a['bounds_only'] else ''}  dirs={a['directions']}")
    ab = result["abstention"]
    print(f"abstention: computed {ab['computed']} · verbatim {ab['verbatim']} "
          f"· undecided {ab['undecided']}")
    for row in result["grow"]:
        print(f"grow[{row['probe']:18s}] cold {row['cold_prior_mean']:.3f} → "
              f"warm {row['warm_posterior_mean']:.3f} vs realised "
              f"{row['realised_rate']:.3f} (n={row['n']})")
    if "stream_attribution" in result:
        sa = result["stream_attribution"]
        for label, blk in sa["windows"].items():
            print(f"stream[{label}] n={blk['n']:4d} recovered={blk['n_recovered']:3d} "
                  f"rate={blk['rate']:.3f}")
        b = sa["before_first"]
        print(f"stream[before first window] n={b['n']:4d} rate={b['rate']:.3f} "
              + " ".join(f"{k}={v['rate']:.3f}" for k, v in b["by_probe"].items()))
    f = result["flip"]
    print(f"flips: {f['n_flips']}/{f['n_rows']} {f['directions']}  "
          f"asserts a {f['asserts_a']} vs b {f['asserts_b']}  "
          f"spend a {f['mean_spend_a']:.4f} vs b {f['mean_spend_b']:.4f}")
    print(f"→ {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
