"""``scripts/dominance/loss_triage.py`` — per-loss-cell question triage + ``LOSS_MAP.md``.

For every ``winmap`` cell whose verdict is ``"loss"`` (from ``arm_a``'s perspective),
names the top-5 questions responsible by ``|Δ question_utility|`` (``arm_a`` minus
``arm_b``, the same sign convention as the cell's own ``regret``), alongside both arms'
``bucket``/``cost_usd``/``latency_s`` for that question — the smallest slice a reader
needs to see *why* a loss happened without re-deriving it from raw vectors.

Two invariants the brief makes hard requirements:

- A loss cell with **zero** contributing questions (no ``question_id`` common to both
  arms' rows for that cell's scenario) is a HARD FAIL — :func:`triage_loss_cell` raises
  rather than silently emitting an empty section (a loss with no evidence would be a
  bug in this module or its caller, never a real outcome: welfare regret is a sum over
  exactly those rows).
- A run with **zero** loss cells at all is flagged prominently (not silently treated as
  "arm_a always wins") — plausible after a real regression fix, but also the classic
  instrumentation-bug signature (e.g. every ``cost_usd``/``latency_s`` accidentally
  identical across arms), so both ``LOSS_MAP.md`` and ``summary.md`` name it.
"""
from __future__ import annotations

from typing import Any

from .profiles import PERSONAS, PRESETS, Profile
from .utility import question_utility

TOP_N = 5


def _profile_by_name(name: str) -> Profile:
    profiles = {**PRESETS, **PERSONAS}
    return profiles[name]


def _index_by_question(vectors: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {v["question_id"]: v for v in vectors}


def _scenario_rows(vectors: list[dict[str, Any]], scenario: str) -> list[dict[str, Any]]:
    if scenario == "all":
        return vectors
    if scenario == "answerable":
        return [v for v in vectors if v["answerable"]]
    if scenario == "unanswerable":
        return [v for v in vectors if not v["answerable"]]
    raise ValueError(f"unknown scenario {scenario!r}")


def triage_loss_cell(
    cell: dict[str, Any],
    arm_a_vectors: list[dict[str, Any]],
    arm_b_vectors: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """The top-``TOP_N`` questions by ``|Δ question_utility|`` for one loss ``cell``.

    ``arm_a_vectors``/``arm_b_vectors`` are that cell's TWO arms' full vector lists
    (any scenario) — this function applies the cell's own ``scenario`` filter and the
    cell's ``profile`` before scoring, so the caller never has to pre-filter.

    Raises ``ValueError`` if no ``question_id`` is common to both arms under this
    cell's scenario (the hard-fail invariant — see the module docstring).
    """
    profile = _profile_by_name(cell["profile"])
    rows_a = _scenario_rows(arm_a_vectors, cell["scenario"])
    rows_b = _scenario_rows(arm_b_vectors, cell["scenario"])
    by_a = _index_by_question(rows_a)
    by_b = _index_by_question(rows_b)
    common = sorted(set(by_a) & set(by_b))
    if not common:
        raise ValueError(
            f"loss cell {cell['arm_a']!r} vs {cell['arm_b']!r} / profile={cell['profile']!r} "
            f"/ scenario={cell['scenario']!r} has zero contributing questions — a loss "
            "with no evidence should be impossible (regret is a sum over these rows)"
        )
    scored: list[dict[str, Any]] = []
    for qid in common:
        va, vb = by_a[qid], by_b[qid]
        delta = question_utility(profile, va) - question_utility(profile, vb)
        scored.append({
            "question_id": qid,
            "delta_utility": round(delta, 6),
            "arm_a_bucket": va["bucket"], "arm_a_cost_usd": va["cost_usd"],
            "arm_a_latency_s": va["latency_s"],
            "arm_b_bucket": vb["bucket"], "arm_b_cost_usd": vb["cost_usd"],
            "arm_b_latency_s": vb["latency_s"],
        })
    scored.sort(key=lambda r: abs(r["delta_utility"]), reverse=True)
    return scored[:TOP_N]


def build_loss_report(
    cells: list[dict[str, Any]], arms: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], bool]:
    """Triage every ``"loss"`` cell in ``cells``.

    Returns ``(sections, zero_losses)``: ``sections`` is one ``{"cell": ..., "top_questions":
    [...]}`` dict per loss cell (in ``cells``' own order); ``zero_losses`` is ``True`` iff
    ``cells`` contains no loss verdict at all (the run-wide flag).
    """
    loss_cells = [c for c in cells if c["verdict"] == "loss"]
    sections = [
        {
            "cell": cell,
            "top_questions": triage_loss_cell(
                cell, arms[cell["arm_a"]], arms[cell["arm_b"]]),
        }
        for cell in loss_cells
    ]
    return sections, (len(loss_cells) == 0)


ZERO_LOSS_FLAG = "**ZERO LOSSES across every cell — suspicious, verify instrumentation.**"


def loss_map_md(sections: list[dict[str, Any]], zero_losses: bool) -> str:
    """Render ``LOSS_MAP.md``: one section per loss cell, grouped by (pair, profile,
    scenario) in ``sections``' order, or the zero-loss flag when there is nothing to
    triage.
    """
    lines = ["# LOSS_MAP", ""]
    if zero_losses:
        lines += [ZERO_LOSS_FLAG, ""]
        return "\n".join(lines) + "\n"
    for section in sections:
        c, qs = section["cell"], section["top_questions"]
        lines.append(f"## {c['arm_a']} vs {c['arm_b']} — {c['profile']} — {c['scenario']}")
        lines.append("")
        lines.append(
            f"regret={c['regret']} (welfare_a={c['welfare_a']}, welfare_b={c['welfare_b']}, "
            f"cell_source={c['cell_source']}, n_questions={c['n_questions']})"
        )
        lines.append("")
        lines.append(
            "| question_id | Δutility | arm_a bucket | arm_a cost | arm_a latency_s | "
            "arm_b bucket | arm_b cost | arm_b latency_s |"
        )
        lines.append("|---|---|---|---|---|---|---|---|")
        for q in qs:
            lines.append(
                f"| {q['question_id']} | {q['delta_utility']:.4f} | {q['arm_a_bucket']} | "
                f"{q['arm_a_cost_usd']} | {q['arm_a_latency_s']} | {q['arm_b_bucket']} | "
                f"{q['arm_b_cost_usd']} | {q['arm_b_latency_s']} |"
            )
        lines.append("")
    return "\n".join(lines) + "\n"
