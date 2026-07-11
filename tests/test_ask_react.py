"""The deferred dogfood verdict — ``/react`` (docs/interaction-contract.md `know` mode).

Pins the contract: the line grammar parses the one-key or spelled verdict (and errors loudly
otherwise), the handler resolves a ``decision_id`` prefix git-style (unique match required),
records exactly the ``ReactionEvent`` the §4.4 fold joins (with the *owner's* valence, never a
default — the reaction-loop firewall), and names the report-vs-abstain fate rather than
implying every verdict folds. Same dependency-light style as tests/test_ask_temporal.py.

Run: uv run --project . python -m pytest tests/test_ask_react.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import ask

from life_agent.core import decisions as DEC
from life_agent.core import reactions as R

# --- the line grammar ------------------------------------------------------- #


def test_react_parses_one_key_verdict() -> None:
    p = ask.parse_line("/react 8af95b2f g")
    assert p.kind == "react"
    assert p.did == "8af95b2f"
    assert p.valence == "good"   # normalised to the reactions.VALENCES vocabulary


def test_react_parses_spelled_verdict() -> None:
    p = ask.parse_line("/react be618230 bad")
    assert (p.kind, p.did, p.valence) == ("react", "be618230", "bad")


def test_react_parse_errors_are_loud() -> None:
    assert ask.parse_line("/react").kind == "error"             # no id, no verdict
    assert ask.parse_line("/react 8af95b2f").kind == "error"    # missing verdict
    assert ask.parse_line("/react 8af95b2f n").kind == "error"  # 'n'/note is gone — one bit only
    # the verdict is a single bit: no trailing free text is accepted (it is not elicited)
    assert ask.parse_line("/react 8af95b2f bad stale").kind == "error"
    bad = ask.parse_line("/react 8af95b2f maybe")               # not g/b
    assert bad.kind == "error"
    assert "g/b" in bad.error


def test_react_is_in_the_single_grammar_source() -> None:
    forms = [form for form, _m, _e in ask.GRAMMAR]
    assert any(f.startswith("/react") for f in forms)


# --- fixtures: a tiny decisions log ----------------------------------------- #


def _decision(did: str, *, family: str = "lookup", action: str = "abstain",
              summary: dict | None = None) -> DEC.DecisionEvent:
    aset = (("report", "hedge", "ask_clarify", "abstain") if family == "lookup"
            else ("report", "abstain"))
    return DEC.DecisionEvent(
        tx_time="2026-06-14T00:00:00+00:00", run_id="r", question_id=f"q-{did[:6]}",
        family=family, action_set=aset,
        posterior_summary=summary if summary is not None else {"credences": [0.8]},
        utility_fold_version="fold-x", chosen_action=action, predicted_eu=0.0,
        decision_id=did)


def _seed(tmp_path: Path, *decisions: DEC.DecisionEvent) -> tuple[Path, Path]:
    dec_path = tmp_path / "decisions.jsonl"
    react_path = tmp_path / "reactions.jsonl"
    for d in decisions:
        DEC.append(dec_path, d)
    return dec_path, react_path


# --- the handler: record + fate --------------------------------------------- #


def test_lookup_abstain_verdict_is_recorded_and_folds(tmp_path: Path, capsys) -> None:
    did = "dead" + "b" * 60  # 64-hex-ish; prefix-addressable
    dec_path, react_path = _seed(tmp_path, _decision(did, family="lookup", action="abstain"))

    rc = ask.react("deadb", "bad", decisions_path=dec_path, reactions_path=react_path)
    assert rc == 0

    rows = R.read(react_path)
    assert len(rows) == 1
    r = rows[0]
    assert r.decision_id == did            # the prefix resolved to the full id
    assert (r.kind, r.valence) == ("verdict", "bad")   # the OWNER's valence (one bit), verbatim
    assert r.question_id == f"q-{did[:6]}"  # copied from the decision, not the prefix

    # an abstain verdict is fold-eligible — load_reactions emits utility evidence
    assert len(R.load_reactions(react_path, dec_path)) == 1
    assert "folds" in capsys.readouterr().out


def test_report_verdict_is_recorded_but_not_folded(tmp_path: Path, capsys) -> None:
    did = "beef" + "a" * 60
    dec_path, react_path = _seed(tmp_path, _decision(did, family="lookup", action="report"))

    rc = ask.react("beef", "good", decisions_path=dec_path, reactions_path=react_path)
    assert rc == 0
    assert len(R.read(react_path)) == 1                       # recorded
    assert R.load_reactions(react_path, dec_path) == []       # but not folded (report row)
    assert "not folded" in capsys.readouterr().out


def test_unknown_prefix_errors_and_writes_nothing(tmp_path: Path) -> None:
    did = "abc" + "0" * 61
    dec_path, react_path = _seed(tmp_path, _decision(did))
    rc = ask.react("ffffff", "bad", decisions_path=dec_path, reactions_path=react_path)
    assert rc == 2
    assert not react_path.exists() or R.read(react_path) == []   # no verdict authored


def test_ambiguous_prefix_errors_and_writes_nothing(tmp_path: Path) -> None:
    a, b = "ab" + "1" * 62, "ab" + "2" * 62  # share the prefix "ab"
    dec_path, react_path = _seed(tmp_path, _decision(a), _decision(b))
    rc = ask.react("ab", "bad", decisions_path=dec_path, reactions_path=react_path)
    assert rc == 2
    assert not react_path.exists() or R.read(react_path) == []


# --- I3: where a verdict is WRITTEN — through the bridge when it is up ------- #
#
# `bridge/server.py`'s /log_reaction is the ONLY caller of MembraneShadow.submit_reaction,
# so a verdict appended straight to the reaction log reaches the membrane shadow only at the
# NEXT boot's snapshot replay. ask-live is the primary dogfood surface; its verdicts now take
# the same route Jarvis's already do. The reaction log stays the source of truth, so the
# bridge leg is strictly fail-open: a verdict is never lost, and never written twice.


def _event(decision_id: str = "ab-123", valence: str = "good") -> R.ReactionEvent:
    return R.ReactionEvent(tx_time="2026-07-11T00:00:00+00:00", question_id="qid-1",
                           decision_id=decision_id, kind="verdict", valence=valence)


def test_submit_reaction_routes_through_the_bridge_and_does_not_double_write(
    tmp_path: Path, monkeypatch,
) -> None:
    react_path = tmp_path / "reactions.jsonl"
    monkeypatch.setattr(ask.C, "REACTIONS_LOG", react_path)
    calls: list[tuple[str, dict]] = []

    def post(url: str, payload: dict) -> dict:
        calls.append((url, payload))
        return {"folds": True, "chosen_action": "abstain"}

    via = ask.submit_reaction(_event(), reactions_path=react_path, post=post)

    assert via == "bridge"
    assert calls == [(f"{ask.EXECUTOR_BRIDGE}/log_reaction",
                      {"decision_id": "ab-123", "valence": "good"})]
    # the bridge owns the append on its own path — writing here too would DOUBLE-count the
    # owner's one bit in the utility fold
    assert not react_path.exists()


def test_submit_reaction_falls_back_to_a_direct_append_when_the_bridge_is_down(
    tmp_path: Path, monkeypatch,
) -> None:
    react_path = tmp_path / "reactions.jsonl"
    monkeypatch.setattr(ask.C, "REACTIONS_LOG", react_path)

    def post(_url: str, _payload: dict) -> dict:
        raise OSError("connection refused")

    via = ask.submit_reaction(_event(valence="bad"), reactions_path=react_path, post=post)

    assert via == "direct"
    rows = R.read(react_path)
    assert len(rows) == 1                      # the verdict is NEVER lost to a down bridge
    assert rows[0].valence == "bad"


def test_submit_reaction_skips_the_bridge_for_an_unbound_verdict(
    tmp_path: Path, monkeypatch,
) -> None:
    """No decision_id => the bridge has nothing to look up (it would 404). Skip the pointless
    round-trip and write directly, exactly as before."""
    react_path = tmp_path / "reactions.jsonl"
    monkeypatch.setattr(ask.C, "REACTIONS_LOG", react_path)
    calls: list[str] = []

    def post(url: str, _payload: dict) -> dict:
        calls.append(url)
        return {}

    via = ask.submit_reaction(_event(decision_id=""), reactions_path=react_path, post=post)
    assert via == "direct"
    assert calls == []
    assert len(R.read(react_path)) == 1


def test_submit_reaction_never_posts_when_the_caller_named_another_reaction_log(
    tmp_path: Path, monkeypatch,
) -> None:
    """The bridge writes only its OWN configured log, so a caller that explicitly named a
    different one (a test, an isolated run) must not have its verdict land somewhere else."""
    monkeypatch.setattr(ask.C, "REACTIONS_LOG", tmp_path / "production.jsonl")
    other = tmp_path / "isolated.jsonl"
    calls: list[str] = []

    def post(url: str, _payload: dict) -> dict:
        calls.append(url)
        return {}

    via = ask.submit_reaction(_event(), reactions_path=other, post=post)
    assert via == "direct"
    assert calls == []
    assert len(R.read(other)) == 1


def test_react_routes_its_verdict_through_submit_reaction(tmp_path: Path, monkeypatch) -> None:
    """The deferred `/react` path takes the same route (it is the same one-bit verdict)."""
    did = "dead" + "b" * 60
    dec_path, react_path = _seed(tmp_path, _decision(did, family="lookup", action="abstain"))
    monkeypatch.setattr(ask.C, "REACTIONS_LOG", react_path)
    posted: list[dict] = []

    def post(_url: str, payload: dict) -> dict:
        posted.append(payload)
        return {"folds": True, "chosen_action": "abstain"}

    monkeypatch.setattr(ask, "_http_post", post)
    rc = ask.react("deadb", "bad", decisions_path=dec_path, reactions_path=react_path)

    assert rc == 0
    assert posted == [{"decision_id": did, "valence": "bad"}]
