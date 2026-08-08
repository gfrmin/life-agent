"""The shadow correctness judge (scripts/eval_judge.py) — hermetic, no live API.

Run 5 discipline: the judge grades in PARALLEL with the token matcher, never instead of
it — the gate verdict stays matcher-graded and comparable to runs 3/4; adoption is
pre-registered for run 6 iff the disagreement audit clears. These tests pin the blind
prompt inputs, the modal-of-N vote semantics (a tie or thin vote is UNJUDGED, never a
coin flip), the append-only verdict cache (replay-deterministic, None never poisons it),
and the disagreement assembly the report publishes.

Run: uv run --project . python -m pytest tests/test_eval_judge.py
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import eval_judge as EJ


def _reply(text: str) -> SimpleNamespace:
    return SimpleNamespace(text=text, served_model="judge-x")


def _seq_complete(texts: list[str]):
    """A scripted judge: each call pops the next reply text; raises past the end."""
    replies = list(texts)

    def complete(system: str, user: str) -> SimpleNamespace:
        return _reply(replies.pop(0))
    return complete


# --- judge_key: content-addressed, version-bound ------------------------------------------

def test_judge_key_is_stable_and_content_bound() -> None:
    k1 = EJ.judge_key("q?", "P123", ["p-123"], "the number is P123")
    k2 = EJ.judge_key("q?", "P123", ["p-123"], "the number is P123")
    k3 = EJ.judge_key("q?", "P123", ["p-123"], "the number is Q999")
    assert k1 == k2
    assert k1 != k3
    assert len(k1) == 64  # sha256 hex


# --- vote parsing: strict, fail-safe --------------------------------------------------------

def test_parse_vote_strict_json_and_garbage() -> None:
    assert EJ._parse_vote('{"correct": true}') is True
    assert EJ._parse_vote('{"correct": false}') is False
    # JSON embedded in prose still parses (the joint_extract._parse precedent)
    assert EJ._parse_vote('Sure: {"correct": true} — done.') is True
    # garbage / missing / non-bool → None, never a guessed vote
    assert EJ._parse_vote("CORRECT") is None
    assert EJ._parse_vote('{"correct": "yes"}') is None
    assert EJ._parse_vote("{}") is None


# --- judge_correct: modal-of-N over VALID votes ---------------------------------------------

def test_judge_correct_majority_true_and_false() -> None:
    up = EJ.judge_correct("q?", "P123", [], "P123 it is",
                          complete=_seq_complete(['{"correct": true}',
                                                  '{"correct": false}',
                                                  '{"correct": true}']))
    assert up is True
    down = EJ.judge_correct("q?", "P123", [], "Q999",
                            complete=_seq_complete(['{"correct": false}',
                                                    '{"correct": false}',
                                                    '{"correct": true}']))
    assert down is False


def test_judge_correct_thin_or_tied_votes_are_unjudged() -> None:
    # fewer than 2 valid votes → None (one model's word is not a modal verdict)
    thin = EJ.judge_correct("q?", "P123", [], "x",
                            complete=_seq_complete(["garbled", "also garbled",
                                                    '{"correct": true}']))
    assert thin is None
    # a 1-1 split among valid votes → None, never a coin flip
    tied = EJ.judge_correct("q?", "P123", [], "x",
                            complete=_seq_complete(['{"correct": true}', "garbled",
                                                    '{"correct": false}']))
    assert tied is None


def test_judge_correct_survives_a_raising_judge() -> None:
    # fail-open per vote: a transport error is a None vote, never a crashed run
    def boom(system: str, user: str) -> SimpleNamespace:
        raise RuntimeError("judge down")
    assert EJ.judge_correct("q?", "P123", [], "x", complete=boom) is None


def test_judge_prompt_is_blind_to_arm_identity() -> None:
    # the user prompt carries question/gold/variants/candidate ONLY — never which arm
    # produced the candidate (the citation-shape-leak lesson, applied forward)
    seen: list[str] = []

    def spy(system: str, user: str) -> SimpleNamespace:
        seen.append(user)
        return _reply('{"correct": true}')
    EJ.judge_correct("what is my rent?", "NIS 4,200", ["4200"],
                     "NIS 4,200 [doc.pdf]", complete=spy)
    assert seen and all("typed" not in u and "mono" not in u and "deliberat" not in u
                        for u in seen)
    assert "NIS 4,200" in seen[0] and "what is my rent?" in seen[0]


# --- the verdict cache: append-only, replay-deterministic ------------------------------------

def test_verdict_cache_round_trip_and_zero_recalls(tmp_path: Path) -> None:
    path = tmp_path / "judge-verdicts.jsonl"
    calls: list[int] = []

    def counting(system: str, user: str) -> SimpleNamespace:
        calls.append(1)
        return _reply('{"correct": true}')
    cache: dict = {}
    v1 = EJ.judge_with_cache(cache, path, "q?", "P123", [], "P123!", complete=counting)
    assert v1 is True and len(calls) == 3  # modal-of-3, live
    # a FRESH process (cache reloaded from disk) replays with ZERO judge calls
    reloaded = EJ.load_verdicts(path)

    def boom(system: str, user: str) -> SimpleNamespace:
        raise AssertionError("cached verdict must not re-consult the judge")
    v2 = EJ.judge_with_cache(reloaded, path, "q?", "P123", [], "P123!", complete=boom)
    assert v2 is True


def test_unjudged_verdicts_are_never_cached(tmp_path: Path) -> None:
    # a garbled/transient run must not poison future replays with a frozen None
    path = tmp_path / "judge-verdicts.jsonl"
    cache: dict = {}

    def garbled(system: str, user: str) -> SimpleNamespace:
        return _reply("no json here")
    assert EJ.judge_with_cache(cache, path, "q?", "P123", [], "x",
                               complete=garbled) is None
    assert not path.exists() and cache == {}


# --- disagreement assembly + the report section ----------------------------------------------

def _item(candidate: str, arm: str = "typed") -> dict:
    return {"question_id": "q2-001", "arm": arm, "question": "value?",
            "gold": "P123", "variants": [], "candidate": candidate}


def test_shadow_disagreements_only_where_matcher_and_judge_differ() -> None:
    items = [_item("the number is P123"),      # matcher CORRECT
             _item("the number is Q999"),      # matcher INCORRECT
             _item("P-one-two-three (spelled out)"),  # matcher INCORRECT
             _item("unjudgeable")]
    verdicts = {"the number is P123": True,             # agree → no row
                "the number is Q999": True,             # judge True vs matcher INCORRECT → row
                "P-one-two-three (spelled out)": True,  # adjudication-shaped rescue → row
                "unjudgeable": None}                    # unjudged → counted, no row

    def judge(it: dict) -> bool | None:
        return verdicts[it["candidate"]]
    rows, stats = EJ.shadow_disagreements(items, judge=judge)
    assert [(r["candidate"], r["matcher"], r["judge"]) for r in rows] == [
        ("the number is Q999", "INCORRECT", "CORRECT"),
        ("P-one-two-three (spelled out)", "INCORRECT", "CORRECT")]
    assert stats == {"n_items": 4, "n_judged": 3, "n_unjudged": 1, "n_agree": 1}


def test_format_judge_shadow_section() -> None:
    rows, stats = EJ.shadow_disagreements([_item("the number is P123")],
                                          judge=lambda it: True)
    text = EJ.format_judge_shadow(rows, stats)
    assert "SHADOW" in text and "grading unchanged" in text
    assert "1/1" in text  # agreement over judged
    assert "no disagreements" in text
    rows2, stats2 = EJ.shadow_disagreements([_item("the number is Q999")],
                                            judge=lambda it: True)
    text2 = EJ.format_judge_shadow(rows2, stats2)
    assert "q2-001" in text2 and "typed" in text2
    assert "INCORRECT" in text2 and "CORRECT" in text2
