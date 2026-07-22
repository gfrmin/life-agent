"""scripts/claude_verdict.py — the Claude verdict channel's capture CLI (hermetic)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import claude_verdict as CLI

from life_agent.core import claude_verdicts as CV
from life_agent.core import config
from life_agent.core import decisions as DEC
from life_agent.core import reactions as RX


@pytest.fixture
def kb(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(config, "KB", tmp_path)
    monkeypatch.setattr(config, "DECISIONS_LOG", tmp_path / "calibration" / "decisions.jsonl")
    monkeypatch.setattr(config, "REACTIONS_LOG", tmp_path / "calibration" / "reactions.jsonl")
    monkeypatch.setattr(
        config, "CLAUDE_VERDICTS_LOG", tmp_path / "calibration" / "claude_verdicts.jsonl")
    return tmp_path


def _decision(decision_id: str, question_id: str = "q1x", *,
              chosen_action: str = "abstain",
              candidates: list[str] | None = None) -> DEC.DecisionEvent:
    return DEC.DecisionEvent(
        tx_time="2026-07-22T00:00:00Z", run_id="ask", question_id=question_id,
        family="lookup",
        action_set=("report", "hedge", "ask_clarify", "abstain", "report_scoped"),
        posterior_summary={
            "candidates": candidates if candidates is not None else ["42"],
            "credences": [0.9], "p_none": 0.1, "n_obs": 3},
        utility_fold_version="fv1", chosen_action=chosen_action, predicted_eu=0.5,
        decision_id=decision_id)


def test_emit_appends_the_deliberated_record(kb: Path, capsys: pytest.CaptureFixture[str]) -> None:
    DEC.append(config.DECISIONS_LOG, _decision("dec-1"))
    rc = CLI.main(["emit", "dec-1", "--correct", "--complete", "1",
                   "--evidence", "bank.pdf p.3", "--note", "matches the statement"])
    assert rc == 0
    got = CV.read(config.CLAUDE_VERDICTS_LOG)
    assert len(got) == 1
    assert dict(got[0].dimensions) == {"correct": 1, "complete": 1}
    assert got[0].evidence == ("bank.pdf p.3",)
    assert got[0].issuer == "claude-code"
    assert "next boot" in capsys.readouterr().out


def test_emit_unknown_decision_fails_loudly(kb: Path) -> None:
    assert CLI.main(["emit", "dec-404", "--correct"]) == 1


def test_emit_names_owner_precedence_when_a_reaction_exists(
    kb: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    DEC.append(config.DECISIONS_LOG, _decision("dec-1"))
    RX.append(config.REACTIONS_LOG, RX.ReactionEvent(
        tx_time="t", question_id="q1x", decision_id="dec-1",
        kind="verdict", valence="good"))
    assert CLI.main(["emit", "dec-1", "--incorrect"]) == 0
    assert "SUPERSEDED" in capsys.readouterr().out
    assert len(CV.read(config.CLAUDE_VERDICTS_LOG)) == 1  # recorded regardless


def test_list_hides_verdicted_by_default_and_shows_with_all(
    kb: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    DEC.append(config.DECISIONS_LOG, _decision("dec-verdicted", "q1x"))
    DEC.append(config.DECISIONS_LOG, _decision("dec-open", "q2x"))
    assert CLI.main(["emit", "dec-verdicted", "--correct"]) == 0
    capsys.readouterr()
    assert CLI.main(["list"]) == 0
    out = capsys.readouterr().out
    assert "dec-open" in out and "dec-verdicted" not in out
    assert CLI.main(["list", "--all"]) == 0
    out = capsys.readouterr().out
    assert "dec-verdicted" in out and "[C]" in out


def test_narrative_rows_without_candidates_are_not_eligible(kb: Path) -> None:
    DEC.append(config.DECISIONS_LOG, DEC.DecisionEvent(
        tx_time="t", run_id="ask", question_id="q3x", family="narrative",
        action_set=("report", "abstain"),
        posterior_summary={"abstain_reason": "ALL_WITHHELD", "marginal_credence": 0.4},
        utility_fold_version="fv1", chosen_action="abstain", predicted_eu=0.0,
        decision_id="dec-narr"))
    assert CLI.main(["emit", "dec-narr", "--correct"]) == 1
