"""scripts/void_deliberate_poison.py — the blind-decline cache scan."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import void_deliberate_poison as V

import life_agent.core.derivations as D


def _record(root: Path, question: str, *, declined: bool, tool_calls: int) -> str:
    key = D.deliberate_key(question, "digest", model="m", prompt_template="p", max_turns=1)
    content = json.dumps({"format_version": 1, "question": question, "model": "m",
                          "text": "NOT_IN_CORPUS" if declined else "42", "value": None
                          if declined else "42", "credence": None if declined else 0.9,
                          "declined": declined, "cost_usd": 1.2, "session_id": "s",
                          "tool_calls": tool_calls, "gather_rounds": 0}).encode()
    assert D.record(root, key, content, lineage=[], metadata={})
    return key.cache_key


def test_scan_finds_only_declines_with_zero_tool_calls(tmp_path: Path) -> None:
    root = tmp_path / "root"
    poisoned = _record(root, "q-blind", declined=True, tool_calls=0)
    _record(root, "q-evidenced-decline", declined=True, tool_calls=3)
    _record(root, "q-answer", declined=False, tool_calls=0)
    rows = V.poisoned_records(root)
    assert [r["cache_key"] for r in rows] == [poisoned]
    assert rows[0]["question"] == "q-blind" and rows[0]["cost_usd"] == 1.2


def test_dry_run_removes_nothing(tmp_path: Path, capsys) -> None:
    root = tmp_path / "root"
    key = _record(root, "q-blind", declined=True, tool_calls=0)
    assert V.main(["--root", str(root), "--manifest-dir", str(tmp_path / "m")]) == 0
    assert D.lookup(root, key) is not None
    assert "dry-run" in capsys.readouterr().out
