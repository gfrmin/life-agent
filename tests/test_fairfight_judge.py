"""Unit tests for the fair-fight rubric judge (scripts/fairfight/judge.py).

Hermetic: no live API — every test monkeypatches ``_common.judge_complete`` (the
same cross-provider judge indirection ``run_eval._synthesis_judge_once`` and
``blind_judge.judge_once`` use) with canned JSON replies. Synthetic fixtures only
(the "123456789" ID fails the Israeli-ID checksum by construction, same convention
as ``tests/test_fairfight_grading.py``'s ``_q()`` fixture — the PII hook's shape
guard passes it through).

Run from the repo root:
    uv run --project . python -m pytest ./tests/test_fairfight_judge.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "comparison"))

from fairfight import judge as J

# --- judge_answer: strict-JSON parse --------------------------------------------------


def test_judge_answer_parses_strict_json_three_dims(monkeypatch) -> None:
    import _common as JC

    monkeypatch.setattr(
        JC, "judge_complete",
        lambda s, u, **k: SimpleNamespace(
            text='{"faithfulness": 3, "completeness": 2, "citation_fidelity": 1}',
            served_model="gpt-x"),
    )
    out = J.judge_answer(
        {"question": "q", "answer": "x"}, "ans", [{"n": 1, "text": "x"}], "RUBRIC")
    assert out == {"faithfulness": 3, "completeness": 2, "citation_fidelity": 1,
                    "_served": "gpt-x"}


def test_judge_answer_strips_fenced_json(monkeypatch) -> None:
    import _common as JC

    fenced = '```json\n{"faithfulness": 2, "completeness": 3, "citation_fidelity": 1}\n```'
    monkeypatch.setattr(
        JC, "judge_complete",
        lambda s, u, **k: SimpleNamespace(text=fenced, served_model="gpt-y"),
    )
    out = J.judge_answer({"question": "q"}, "ans", [], "RUBRIC")
    assert out == {"faithfulness": 2, "completeness": 3, "citation_fidelity": 1,
                    "_served": "gpt-y"}


def test_judge_answer_malformed_non_json_returns_none(monkeypatch) -> None:
    import _common as JC

    monkeypatch.setattr(
        JC, "judge_complete",
        lambda s, u, **k: SimpleNamespace(text="I cannot comply with that request.",
                                           served_model="gpt-x"),
    )
    assert J.judge_answer({"question": "q"}, "ans", [], "RUBRIC") is None


def test_judge_answer_missing_dimension_key_returns_none(monkeypatch) -> None:
    import _common as JC

    monkeypatch.setattr(
        JC, "judge_complete",
        lambda s, u, **k: SimpleNamespace(
            text='{"faithfulness": 3, "completeness": 2}', served_model="gpt-x"),
    )
    # citation_fidelity missing — skipped, never guessed
    assert J.judge_answer({"question": "q"}, "ans", [], "RUBRIC") is None


def test_judge_answer_non_integer_score_returns_none(monkeypatch) -> None:
    import _common as JC

    monkeypatch.setattr(
        JC, "judge_complete",
        lambda s, u, **k: SimpleNamespace(
            text='{"faithfulness": "high", "completeness": 2, "citation_fidelity": 1}',
            served_model="gpt-x"),
    )
    assert J.judge_answer({"question": "q"}, "ans", [], "RUBRIC") is None


# --- judge_answer: prompt content (expected_components + source text) ----------------


def test_judge_answer_prompt_includes_expected_components_and_source_text(monkeypatch) -> None:
    captured: dict = {}

    def _stub(system: str, user: str, **kw: object) -> SimpleNamespace:
        captured["system"] = system
        captured["user"] = user
        return SimpleNamespace(
            text='{"faithfulness":3,"completeness":3,"citation_fidelity":3}',
            served_model="gpt-x")

    import _common as JC

    monkeypatch.setattr(JC, "judge_complete", _stub)

    q = {"question": "what is my ID?", "answer": "123456789",
         "expected_components": ["id_number_present"]}
    sources = [
        {"n": 1, "text": "ID card body SENTINEL-ALPHA"},
        # the real tool-log result shape (src/pkm/mcp_server.py): snippet_shown, not snippet
        {"source_path": "letter.txt", "snippet_shown": "letter body SENTINEL-BETA"},
    ]
    J.judge_answer(q, "Your ID is 123456789.", sources, "RUBRIC-MARKER")

    assert "id_number_present" in captured["user"]        # expected_components present
    assert "SENTINEL-ALPHA" in captured["user"]            # numbered-card source text
    assert "letter.txt" in captured["user"]                # competitor source name visible
    assert "SENTINEL-BETA" in captured["user"]             # competitor source text (snippet_shown)
    assert "RUBRIC-MARKER" in captured["system"]           # rubric text appended to system


def test_judge_answer_no_sources_renders_placeholder(monkeypatch) -> None:
    captured: dict = {}

    def _stub(system: str, user: str, **kw: object) -> SimpleNamespace:
        captured["user"] = user
        return SimpleNamespace(
            text='{"faithfulness":3,"completeness":3,"citation_fidelity":3}',
            served_model="gpt-x")

    import _common as JC

    monkeypatch.setattr(JC, "judge_complete", _stub)
    J.judge_answer({"question": "q"}, "ans", [], "RUBRIC")
    assert "no sources cited" in captured["user"]


# --- judge_modal: modal-of-N per dim, tie -> lower ------------------------------------


def test_judge_modal_per_dim_matches_blind_judge_modal_including_a_real_tie(monkeypatch) -> None:
    from blind_judge import modal as blind_modal

    replies = [
        {"faithfulness": 3, "completeness": 3, "citation_fidelity": 3},
        {"faithfulness": 3, "completeness": 2, "citation_fidelity": 2},
        {"faithfulness": 1, "completeness": 2, "citation_fidelity": 1},
        {"faithfulness": 1, "completeness": 1, "citation_fidelity": 0},
    ]
    # faithfulness is a genuine 2-vs-2 tie (3,3,1,1) — exercises modal's tie->lower path.
    assert [r["faithfulness"] for r in replies].count(3) == \
        [r["faithfulness"] for r in replies].count(1) == 2

    calls = iter(replies)

    def _stub(system: str, user: str, **kw: object) -> SimpleNamespace:
        return SimpleNamespace(text=json.dumps(next(calls)), served_model="gpt-x")

    import _common as JC

    monkeypatch.setattr(JC, "judge_complete", _stub)

    out = J.judge_modal({"question": "q", "answer": "a"}, "ans text",
                         [{"n": 1, "text": "src"}], n=4)

    for dim in ("faithfulness", "completeness", "citation_fidelity"):
        assert out[dim] == blind_modal([r[dim] for r in replies])
    assert out["faithfulness"] == 1  # tie(3,1) -> lower, spelled out explicitly


def test_judge_modal_drops_malformed_calls_and_keeps_the_rest(monkeypatch) -> None:
    replies = [
        '{"faithfulness": 2, "completeness": 2, "citation_fidelity": 2}',
        "not json at all",
        '{"faithfulness": 2, "completeness": 2, "citation_fidelity": 2}',
    ]
    calls = iter(replies)

    def _stub(system: str, user: str, **kw: object) -> SimpleNamespace:
        return SimpleNamespace(text=next(calls), served_model="gpt-x")

    import _common as JC

    monkeypatch.setattr(JC, "judge_complete", _stub)

    out = J.judge_modal({"question": "q"}, "ans", [], n=3)
    assert out == {"faithfulness": 2, "completeness": 2, "citation_fidelity": 2,
                    "_served": ["gpt-x"]}


def test_judge_modal_all_n_fail_returns_empty_dict(monkeypatch) -> None:
    import _common as JC

    monkeypatch.setattr(
        JC, "judge_complete",
        lambda s, u, **k: SimpleNamespace(text="nope", served_model="gpt-x"),
    )
    assert J.judge_modal({"question": "q"}, "ans", [], n=3) == {}
