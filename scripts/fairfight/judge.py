"""``scripts/fairfight/judge.py`` — the single-answer, 3-dimension rubric judge.

Composes EXISTING judge machinery (never rebuilds it):

- ``scripts/run_eval.py``'s ``_synthesis_judge_once`` — the single-answer judge
  template this module is modeled on byte-for-byte: same system frame, strict-JSON
  discipline, fenced-JSON stripping, and the same ``comparison._common.judge_complete``
  call (the pinned cross-provider ``gpt-5.1`` judge).
- ``scripts/comparison/blind_judge.py`` — ``_rubric_text`` (loads the frozen
  ``eval/rubric_v1.yaml``), ``modal`` (modal-of-N, tie -> lower), and ``DIMS`` (the
  three rubric dimensions scored here, extending ``_synthesis_judge_once``'s two).
  Because completeness is new, this module also follows ``blind_judge.judge_once``'s
  precedent of putting ``expected_components`` in the user block —
  ``_synthesis_judge_once`` never scored completeness so never needed it.
- ``eval/rubric_v1.yaml`` (via ``_rubric_text``) — the frozen rubric text appended to
  the judge's system prompt. Not edited here.

``judge_answer`` differs from ``_synthesis_judge_once`` in one place: the SOURCES
block. The fair-fight harness's arms don't share one source-card shape — baseline/
synthesis cards carry ``n``/``text`` (``core.sources.SourceCard``-shaped dicts); the
hermes competitor's tool-returned chunks carry ``source_path``/``snippet``, no ``n``.
:func:`_sources_block` is one tolerant renderer for both, so the judge always sees
the cited source TEXT (required for citation_fidelity to be checkable at all) and a
visible name when the arm has one.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_COMPARISON_DIR = Path(__file__).resolve().parent.parent / "comparison"


def _sources_block(sources: list[dict]) -> str:
    """Render ``sources`` — a list of per-arm dicts of varying shape — as numbered
    entries the judge can check citation_fidelity against: the index from ``n`` when
    present else running position, a name from ``source_path``/``name`` when present,
    and the text body from ``text`` else ``snippet``. One tolerant renderer, no
    per-arm branch: every arm's source shape must render through this."""
    if not sources:
        return "(no sources cited)"
    lines = []
    for i, s in enumerate(sources, start=1):
        n = s.get("n", i)
        name = s.get("source_path") or s.get("name")
        text = s.get("text") if s.get("text") is not None else s.get("snippet", "")
        label = f"[{n}] ({name})" if name else f"[{n}]"
        lines.append(f"{label} {text}")
    return "\n\n".join(lines)


def judge_answer(q: dict, answer_text: str, sources: list[dict], rubric_text: str) -> dict | None:
    """One judge call -> ``{"faithfulness": int, "completeness": int,
    "citation_fidelity": int, "_served": str}``, or ``None`` on malformed/unparseable
    judge output (skipped by the caller, never guessed)."""
    sys.path.insert(0, str(_COMPARISON_DIR))
    import _common as JC

    src_block = _sources_block(sources)
    system = (
        "You are an impartial grader of ONE answer to a question about a person's own "
        "records. You are given the answer and the SOURCE TEXTS it cited. Judge ONLY "
        "from what is shown. For citation_fidelity you MUST check the cited source text "
        "actually contains the asserted fact. Asserting a listed wrong-subject distractor "
        "caps faithfulness at 1. A correct 'not in the corpus' for a truly-absent fact is "
        "full marks. Return STRICT JSON only: "
        '{"faithfulness":int,"completeness":int,"citation_fidelity":int}.\n\n' + rubric_text
    )
    user = (
        f"QUESTION: {q['question']}\n"
        f"EXPECTED COMPONENTS (for completeness): {q.get('expected_components') or '[]'}\n"
        f"CANONICAL ANSWER: {q.get('answer') or '(no single value)'}   "
        f"ACCEPTABLE VARIANTS: {q.get('answer_variants') or '[]'}\n"
        f"MUST-NOT-ASSERT (wrong-subject distractors): {q.get('distractors') or '[]'}\n"
        f"ANSWERABLE FROM CORPUS: {q.get('answerable', bool(q.get('answer')))}\n\n"
        f"ANSWER:\n{answer_text}\n\nCITED SOURCES:\n{src_block}\n"
    )
    r = JC.judge_complete(system, user, max_tokens=250)
    txt = r.text.strip()
    if txt.startswith("```"):
        txt = txt.strip("`").split("\n", 1)[-1].rsplit("```", 1)[0]
    try:
        obj = json.loads(txt[txt.index("{"): txt.rindex("}") + 1])
        return {
            "faithfulness": int(obj["faithfulness"]),
            "completeness": int(obj["completeness"]),
            "citation_fidelity": int(obj["citation_fidelity"]),
            "_served": r.served_model,
        }
    except (ValueError, KeyError, TypeError):
        return None


def judge_modal(q: dict, answer_text: str, sources: list[dict], *, n: int = 3) -> dict:
    """``n`` independent :func:`judge_answer` calls -> per-dim modal
    (``blind_judge.modal``: tie -> lower); loads the rubric text once. Malformed calls
    are dropped; if ALL ``n`` fail, returns ``{}`` (the runner records the dims as
    unjudged/``None``, never guessed)."""
    sys.path.insert(0, str(_COMPARISON_DIR))
    from blind_judge import DIMS, _rubric_text, modal

    rubric_text = _rubric_text()
    per_dim: dict[str, list[int]] = {d: [] for d in DIMS}
    served: set[str] = set()
    n_ok = 0
    for _ in range(n):
        j = judge_answer(q, answer_text, sources, rubric_text)
        if j is None:
            continue
        n_ok += 1
        for d in DIMS:
            per_dim[d].append(j[d])
        served.add(j["_served"])
    if n_ok == 0:
        return {}
    out: dict = {d: modal(per_dim[d]) for d in DIMS}
    out["_served"] = sorted(served)
    return out
