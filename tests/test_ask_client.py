"""The reach→know client (core/ask_client.py) — hermetic.

Jarvis's `question` intent routes to the SAME executor read-path the terminal uses
(interaction-contract: asking about your life is *know*, whatever transport carried it):
one call answers (decide_via_loop → render_view), logs the terminal decision through the
bridge's /log_decision (so the one-bit verdict folds through the existing reaction loop),
and returns the decision_id the in-chat verdict binds to. `react` posts the verdict and
names the fold fate in ask-live's own vocabulary — never implying every verdict counts.
"""
from __future__ import annotations

import hashlib
from typing import Any

from life_agent.core import ask_client as AC
from life_agent.core import executor as EX


def _fake_view(effector: str = "report") -> dict[str, Any]:
    return {"effector": effector, "asserted": ["P123"] if effector == "report" else [],
            "candidates": ["P123"], "credences": [0.92], "p_none": 0.05, "eu": 0.8,
            "n_obs": 2, "hits": [{"artifact_cache_key": "d0", "chunk_text": "No: P123"}],
            "route": {"construct": "passport number"}}


def test_answer_renders_and_binds_the_decision(monkeypatch: Any) -> None:
    posted: list[tuple[str, dict[str, Any]]] = []
    monkeypatch.setattr(EX, "decide_via_loop", lambda *a, **k: _fake_view())

    def post(url: str, payload: dict[str, Any]) -> dict[str, Any]:
        posted.append((url, payload))
        assert url.endswith("/log_decision")
        return {"decision_id": "ab-cafe"}

    reply, decision_id = AC.answer("what is my passport number?",
                                   post=post, get=lambda u: {}, check_ready=False)
    assert "P123" in reply                       # the shared credence grammar rendering
    assert decision_id == "ab-cafe"              # the id the in-chat verdict binds to
    assert posted and posted[0][1]["decision"]["effector"] == "report"


def test_answer_narrative_or_miss_binds_nothing(monkeypatch: Any) -> None:
    view = _fake_view("miss")
    view["candidates"], view["credences"] = [], []
    monkeypatch.setattr(EX, "decide_via_loop", lambda *a, **k: view)
    reply, decision_id = AC.answer("q?", post=lambda u, p: {"decision_id": "x"},
                                   get=lambda u: {}, check_ready=False)
    assert decision_id is None                   # nothing foldable to bind
    assert reply                                 # still a named reply, never empty


def test_answer_wraps_post_for_the_shadow(monkeypatch: Any) -> None:
    # Jarvis's real traffic is a production caller of EX.decide_via_loop too — its post must
    # be shadow-wrapped exactly like scripts/ask.py's, unconditionally.
    calls: list[tuple[str, dict[str, Any]]] = []

    def bare_post(url: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        calls.append((url, payload))
        return {"effector": "report"} if url.endswith("/decide") else {"ok": True}

    captured: dict[str, Any] = {}

    def fake_decide_via_loop(question: str, k: int, **kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        kwargs["post"](f"{AC.DAEMON}/decide", {"candidates": ["P123"]})
        return _fake_view("miss")  # not a LOOKUP_ACTION_ORDER effector — no extra /log_decision

    monkeypatch.setattr(EX, "decide_via_loop", fake_decide_via_loop)
    AC.answer("what is my passport number?", post=bare_post, get=lambda u: {},
             check_ready=False)

    assert captured["post"] is not bare_post  # wrapped, never the bare transport
    urls = [u for u, _ in calls]
    assert urls == [f"{AC.DAEMON}/decide", f"{AC.BRIDGE}/decide-support"]
    mirror_body = calls[-1][1]
    assert mirror_body["payload"] == {"candidates": ["P123"]}
    assert mirror_body["dec"] == {"effector": "report"}
    assert mirror_body["question_id"] == hashlib.sha256(
        b"what is my passport number?").hexdigest()[:16]


def test_answer_mirror_failure_never_breaks_the_real_answer(monkeypatch: Any) -> None:
    def post(url: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        if url.endswith("/decide-support"):
            raise RuntimeError("shadow unreachable")
        if url.endswith("/decide"):
            return {"effector": "report"}
        return {"ok": True}

    def fake_decide_via_loop(question: str, k: int, **kwargs: Any) -> dict[str, Any]:
        assert kwargs["post"](f"{AC.DAEMON}/decide", {}) == {"effector": "report"}
        return _fake_view()

    monkeypatch.setattr(EX, "decide_via_loop", fake_decide_via_loop)
    reply, _decision_id = AC.answer("q?", post=post, get=lambda u: {}, check_ready=False)
    assert "P123" in reply  # the answer is unaffected by the mirror's failure


def test_answer_names_a_down_stack(monkeypatch: Any) -> None:
    monkeypatch.setattr(AC, "_ready", lambda: False)
    reply, decision_id = AC.answer("q?")
    assert "unavailable" in reply and decision_id is None


def test_react_names_the_fold_fate() -> None:
    def post_folds(url: str, payload: dict[str, Any]) -> dict[str, Any]:
        assert payload == {"decision_id": "ab-1", "valence": "good"}
        return {"valence": "good", "family": "lookup", "chosen_action": "abstain",
                "folds": True}

    assert "folds into the utility posterior" in AC.react("ab-1", "good", post=post_folds)

    def post_report(url: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {"valence": "bad", "family": "lookup", "chosen_action": "report",
                "folds": False}

    assert "recorded — not folded" in AC.react("ab-1", "bad", post=post_report)


def test_react_failure_is_named_not_silent() -> None:
    def post_boom(url: str, payload: dict[str, Any]) -> dict[str, Any]:
        raise OSError("connection refused")

    assert "not recorded" in AC.react("ab-1", "good", post=post_boom)
