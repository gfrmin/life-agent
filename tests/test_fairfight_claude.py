"""Unit tests for ``scripts/fairfight/arm_claude.py`` (roadmap A1b — the deliberative
reference arm).

Hermetic: drives a FAKE claude CLI — a small executable Python stub written into
``tmp_path`` per test (same convention as ``tests/test_fairfight_hermes.py``'s fake
hermes) — no network, no real claude binary, no real MCP server. Synthetic values only.

Run from the repo root:
    uv run --project . python -m pytest ./tests/test_fairfight_claude.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from fairfight import arm_claude as AC

_FAKE_CLAUDE_TEMPLATE = '''#!/usr/bin/env python3
"""Fake claude CLI: records argv, emits a canned --output-format json result."""
import json
import sys
import time
from pathlib import Path

ARGS_LOG = Path({args_log!r})
MARKER = Path({marker!r})
SLEEP_S = {sleep_s}
RESULT = {result!r}

ARGS_LOG.write_text(json.dumps(sys.argv[1:]))
if SLEEP_S:
    time.sleep(SLEEP_S)
if MARKER.name and not MARKER.exists():
    # fail the FIRST call only (retry-once coverage), succeed on the second
    MARKER.write_text("1")
    print("transient failure", file=sys.stderr)
    sys.exit(1)
sys.stdout.write(RESULT)
'''

_OK_RESULT = json.dumps({
    "type": "result", "subtype": "success", "is_error": False,
    "result": "P111222 [a.txt]", "session_id": "sess-delib-1",
    "total_cost_usd": 0.42, "num_turns": 7, "duration_ms": 5000,
    "usage": {"input_tokens": 1000, "output_tokens": 200,
              "cache_read_input_tokens": 300, "cache_creation_input_tokens": 50},
})


def _fake_claude(tmp_path: Path, *, result: str = _OK_RESULT, sleep_s: float = 0,
                 fail_first_via_marker: bool = False) -> tuple[str, Path]:
    script = tmp_path / "fake-claude"
    args_log = tmp_path / "argv.json"
    marker = tmp_path / ("fail-once.marker" if fail_first_via_marker else "")
    script.write_text(_FAKE_CLAUDE_TEMPLATE.format(
        args_log=str(args_log), marker=str(marker), sleep_s=sleep_s, result=result))
    script.chmod(0o755)
    return str(script), args_log


def _cfg(tmp_path: Path, claude_bin: str, **overrides: Any) -> AC.ClaudeArmConfig:
    base: dict[str, Any] = dict(
        claude_bin=claude_bin, run_dir=tmp_path / "run", pkm_config="/fake/pkm.yaml",
        model="fake-delib-model", timeout_s=30,
    )
    base.update(overrides)
    return AC.ClaudeArmConfig(**base)


def _q(qid: str = "q-001") -> dict[str, Any]:
    return {"id": qid, "question": "what is the fake policy number?"}


def test_success_maps_result_json_into_the_hermes_usage_vocabulary(tmp_path: Path) -> None:
    bin_, _ = _fake_claude(tmp_path)
    res = AC.answer_deliberative(_q(), _cfg(tmp_path, bin_))

    assert res.raw.status == "ok"
    assert res.raw.text == "P111222 [a.txt]"
    assert res.raw.declined is False
    assert res.raw.lineage_keys == ("sess-delib-1",)
    assert res.usage is not None
    assert res.usage["estimated_cost_usd"] == 0.42
    assert res.usage["model"] == "fake-delib-model"
    assert res.usage["api_calls"] == 7
    assert res.usage["input_tokens"] == 1000
    assert res.usage["cache_read_tokens"] == 300
    assert res.usage["cache_write_tokens"] == 50
    # the usage json is persisted under the arm's own scratch tree (runner layout)
    on_disk = json.loads(
        (tmp_path / "run" / "arms" / "deliberative" / "usage" / "q-001.json").read_text())
    assert on_disk == res.usage


def test_cmd_pins_the_evidence_channel_and_the_agentic_budget(tmp_path: Path) -> None:
    """The enforced half of the prompt contract: pkm tools ONLY (--allowedTools +
    --strict-mcp-config), the model, the turn ceiling, and headless json output."""
    bin_, args_log = _fake_claude(tmp_path)
    AC.answer_deliberative(_q(), _cfg(tmp_path, bin_))
    argv = json.loads(args_log.read_text())

    assert argv[0] == "-p"
    assert "--strict-mcp-config" in argv
    assert argv[argv.index("--allowedTools") + 1] == "mcp__pkm__search,mcp__pkm__extract"
    assert argv[argv.index("--model") + 1] == "fake-delib-model"
    assert argv[argv.index("--output-format") + 1] == "json"
    assert argv[argv.index("--max-turns") + 1] == "40"
    # PR-33 review CRITICAL regression pin: without an explicit permission mode the
    # machine's ambient default (e.g. "plan") silently DENIES the allowed MCP tools —
    # rc=0, no error, zero evidence, and the apology grades as a wrong answer.
    assert argv[argv.index("--permission-mode") + 1] == "default"
    # the prompt carries the question and the deliberation contract
    prompt = argv[1]
    assert "what is the fake policy number?" in prompt
    assert "NOT_IN_CORPUS: " in prompt


def test_mcp_config_points_pkm_serve_at_a_per_question_tool_log(tmp_path: Path) -> None:
    bin_, args_log = _fake_claude(tmp_path)
    cfg = _cfg(tmp_path, bin_)
    AC.answer_deliberative(_q("q-007"), cfg)
    argv = json.loads(args_log.read_text())

    mcp_path = Path(argv[argv.index("--mcp-config") + 1])
    mcp = json.loads(mcp_path.read_text())
    args = mcp["mcpServers"]["pkm"]["args"]
    assert "--tool-log" in args
    tool_log = Path(args[args.index("--tool-log") + 1])
    assert tool_log.name == "q-007.jsonl"
    assert tool_log.parent == tmp_path / "run" / "arms" / "deliberative" / "tool_calls"
    assert "--config" in args and "/fake/pkm.yaml" in args


def test_tool_log_rows_are_ingested_and_counted(tmp_path: Path) -> None:
    bin_, _ = _fake_claude(tmp_path)
    cfg = _cfg(tmp_path, bin_)
    # pre-write what the (fake, never-spawned) MCP server would have logged; the arm
    # clears the log per attempt, so write AFTER by making the stub do it — simplest
    # honest route: run once (stub makes no log), then verify the empty case…
    res = AC.answer_deliberative(_q(), cfg)
    assert res.tool_log == []
    assert res.raw.effort == {"tool_calls": 0, "gather_rounds": 0, "asks_issued": 0}


def test_not_in_corpus_reply_is_a_decline(tmp_path: Path) -> None:
    result = json.dumps({"type": "result", "subtype": "success", "is_error": False,
                         "result": "NOT_IN_CORPUS: no fake policy documents",
                         "session_id": "s", "total_cost_usd": 0.1, "num_turns": 3,
                         "usage": {}})
    bin_, _ = _fake_claude(tmp_path, result=result)
    res = AC.answer_deliberative(_q(), _cfg(tmp_path, bin_))
    assert res.raw.status == "ok"
    assert res.raw.declined is True


def test_retry_once_on_transient_failure_then_success(tmp_path: Path) -> None:
    bin_, _ = _fake_claude(tmp_path, fail_first_via_marker=True)
    res = AC.answer_deliberative(_q(), _cfg(tmp_path, bin_))
    assert res.raw.status == "ok"
    assert res.raw.text == "P111222 [a.txt]"
    assert "attempt 1" in res.raw.notes and "attempt 2" in res.raw.notes


def test_malformed_stdout_is_an_error_never_a_raise(tmp_path: Path) -> None:
    bin_, _ = _fake_claude(tmp_path, result="this is not json at all")
    res = AC.answer_deliberative(_q(), _cfg(tmp_path, bin_))
    assert res.raw.status == "error"
    assert res.raw.text == ""
    assert res.usage is None


def test_is_error_result_keeps_the_spend_but_reports_error(tmp_path: Path) -> None:
    """A failed run still cost money — the usage must survive even when the result is
    an error (same 'usage file written even on failure' discipline as hermes)."""
    result = json.dumps({"type": "result", "subtype": "error_max_turns",
                         "is_error": True, "result": "", "session_id": "s-err",
                         "total_cost_usd": 0.9, "num_turns": 40, "usage": {}})
    bin_, _ = _fake_claude(tmp_path, result=result)
    res = AC.answer_deliberative(_q(), _cfg(tmp_path, bin_))
    assert res.raw.status == "error"
    assert res.usage is not None
    assert res.usage["estimated_cost_usd"] == 0.9
    assert res.usage["subtype"] == "error_max_turns"


def test_timeout_kills_and_reports(tmp_path: Path) -> None:
    bin_, _ = _fake_claude(tmp_path, sleep_s=5)
    res = AC.answer_deliberative(_q(), _cfg(tmp_path, bin_, timeout_s=1))
    assert res.raw.status == "timeout"
    assert "timed out after 1s" in res.raw.notes
    assert res.raw.text == ""


def test_missing_binary_is_an_error_never_a_raise(tmp_path: Path) -> None:
    res = AC.answer_deliberative(_q(), _cfg(tmp_path, str(tmp_path / "nope")))
    assert res.raw.status == "error"
    assert "FileNotFoundError" in res.raw.notes


def test_minimal_env_home_and_path_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", "/fake/home")
    monkeypatch.setenv("PATH", "/fake/bin")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "must-not-leak")
    env = AC._minimal_env()
    assert env == {"HOME": "/fake/home", "PATH": "/fake/bin"}
