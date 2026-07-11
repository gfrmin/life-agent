"""Unit tests for the fair-fight hermes competitor arm (scripts/fairfight/arm_hermes.py).

Hermetic: drives a FAKE hermes — a small executable Python stub written into ``tmp_path`` per
test (never the real ``hermes`` binary, never a real pkm MCP subprocess, never the real
keyring). The stub prints canned stdout, writes a canned usage-file JSON to whatever
``--usage-file`` argv value it's given, can sleep on demand (to trigger a real timeout+kill),
and can fail its first invocation (a marker file written beside the stub itself, so state
survives across the two subprocess spawns one retry-once test drives) then succeed on retry.
``life_agent.core.llm.secret`` is monkeypatched everywhere — no test may reach the real
gnome-keyring.

Run from the repo root:
    uv run --project . python -m pytest ./tests/test_fairfight_hermes.py
"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from fairfight import arm_hermes as AH

from life_agent.core import llm as LLM

# --- fake hermes stub -------------------------------------------------------------------

_DEFAULT_USAGE: dict[str, Any] = {
    "estimated_cost_usd": 0.0123,
    "cost_status": "estimated",
    "cost_source": "usage",
    "input_tokens": 100,
    "output_tokens": 20,
    "cache_read_tokens": 0,
    "cache_write_tokens": 0,
    "reasoning_tokens": 0,
    "total_tokens": 120,
    "api_calls": 1,
    "model": "claude-sonnet-4-6",
    "provider": "anthropic",
    "session_id": "sess-1",
    "completed": True,
    "failed": False,
}

_FAKE_HERMES_TEMPLATE = '''#!/usr/bin/env python3
import json, sys, time
from pathlib import Path

MARKER = Path(__file__).with_name("_called_once")
SLEEP_S = {sleep_s!r}
FAIL_FIRST = {fail_first!r}
EXIT_CODE = {exit_code!r}
STDOUT_TEXT = {stdout_text!r}
WRITE_USAGE = {write_usage!r}
USAGE_PAYLOAD = {usage_payload!r}

argv = sys.argv[1:]
usage_file = None
if "--usage-file" in argv:
    usage_file = argv[argv.index("--usage-file") + 1]

if SLEEP_S:
    time.sleep(SLEEP_S)

first_call = not MARKER.exists()
if FAIL_FIRST and first_call:
    MARKER.write_text("1")
    if usage_file and WRITE_USAGE:
        Path(usage_file).parent.mkdir(parents=True, exist_ok=True)
        Path(usage_file).write_text(json.dumps({{"failed": True, "session_id": "sess-fail"}}))
    sys.stderr.write("simulated failure\\n")
    sys.exit(1)

if usage_file and WRITE_USAGE:
    Path(usage_file).parent.mkdir(parents=True, exist_ok=True)
    Path(usage_file).write_text(json.dumps(USAGE_PAYLOAD))

sys.stdout.write(STDOUT_TEXT)
sys.exit(EXIT_CODE)
'''


def _write_fake_hermes(
    dirpath: Path,
    *,
    stdout_text: str = "the ID number is 555 [a.txt]",
    exit_code: int = 0,
    sleep_s: float = 0.0,
    fail_first: bool = False,
    write_usage: bool = True,
    usage_payload: dict[str, Any] | None = None,
) -> Path:
    script = dirpath / "fake-hermes.py"
    payload = usage_payload if usage_payload is not None else dict(_DEFAULT_USAGE)
    script.write_text(_FAKE_HERMES_TEMPLATE.format(
        sleep_s=sleep_s, fail_first=fail_first, exit_code=exit_code,
        stdout_text=stdout_text, write_usage=write_usage, usage_payload=payload,
    ))
    script.chmod(0o755)
    return script


def _make_state_db(path: Path, *, session_id: str, tool_call_count: int, input_tokens: int,
                    output_tokens: int) -> None:
    conn = sqlite3.connect(str(path))
    try:
        conn.execute(
            "CREATE TABLE sessions (id TEXT PRIMARY KEY, tool_call_count INTEGER, "
            "input_tokens INTEGER, output_tokens INTEGER)")
        conn.execute(
            "INSERT INTO sessions (id, tool_call_count, input_tokens, output_tokens) "
            "VALUES (?, ?, ?, ?)", (session_id, tool_call_count, input_tokens, output_tokens))
        conn.commit()
    finally:
        conn.close()


def _q(id_: str = "q-001", question: str = "what is my ID number?") -> dict[str, Any]:
    return {"id": id_, "question": question}


@pytest.fixture(autouse=True)
def _no_real_keyring(monkeypatch: pytest.MonkeyPatch) -> None:
    """No test may reach the real gnome-keyring: any un-overridden secret() call returns a
    fake key so a test that forgets to stub it fails on a WRONG key, not a keyring prompt."""
    monkeypatch.setattr(LLM, "secret", lambda name: f"fake-{name}")


def _cfg(tmp_path: Path, hermes_bin: Path, **overrides: Any) -> AH.HermesArmConfig:
    base = dict(
        hermes_bin=str(hermes_bin), run_dir=tmp_path / "run",
        pkm_config=str(tmp_path / "pkm-config.yaml"), timeout_s=10,
    )
    base.update(overrides)
    return AH.HermesArmConfig(**base)


# --- PROMPT_V1 ------------------------------------------------------------------------------


def test_prompt_v1_has_question_slot_and_contract_lines() -> None:
    rendered = AH.PROMPT_V1.format(question="what is my passport number?")
    assert "what is my passport number?" in rendered
    assert rendered.rstrip().endswith("QUESTION: what is my passport number?")
    assert "NOT_IN_CORPUS: " in AH.PROMPT_V1
    assert "pkm" in AH.PROMPT_V1
    assert "identity confusion" in AH.PROMPT_V1


# --- write_hermes_config -------------------------------------------------------------------


def test_write_hermes_config_renders_parseable_yaml(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path, tmp_path / "hermes", model="m-1", provider="anthropic")
    tool_log_path = AH.write_hermes_config(cfg, "q-042")

    hermes_home = cfg.run_dir / "arms/competitor/hermes_home"
    config = yaml.safe_load((hermes_home / "config.yaml").read_text())

    assert config["model"] == {"default": "m-1", "provider": "anthropic"}
    assert "base_url" not in config["model"]
    server = config["mcp_servers"]["pkm"]
    assert server["command"] == "uv"
    assert server["args"][:3] == ["run", "--project", str(AH._REPO_ROOT)]
    assert server["args"][3:6] == ["pkm", "--config", cfg.pkm_config]
    assert server["args"][6:8] == ["serve", "--tool-log"]
    assert server["args"][8] == str(tool_log_path)
    assert tool_log_path == cfg.run_dir / "arms/competitor/tool_calls/q-042.jsonl"


def test_write_hermes_config_includes_base_url_when_set(tmp_path: Path) -> None:
    cfg = _cfg(
        tmp_path, tmp_path / "hermes", provider="custom", base_url="http://localhost:11434/v1")
    AH.write_hermes_config(cfg, "q-001")
    hermes_home = cfg.run_dir / "arms/competitor/hermes_home"
    config = yaml.safe_load((hermes_home / "config.yaml").read_text())
    assert config["model"]["base_url"] == "http://localhost:11434/v1"
    assert config["model"]["provider"] == "custom"


def test_write_hermes_config_tool_log_path_is_per_qid(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path, tmp_path / "hermes")
    p1 = AH.write_hermes_config(cfg, "q-001")
    p2 = AH.write_hermes_config(cfg, "q-002")
    assert p1 != p2
    assert p1.name == "q-001.jsonl"
    assert p2.name == "q-002.jsonl"


# --- happy path ------------------------------------------------------------------------------


def test_happy_path_captures_stdout_usage_and_tool_log(tmp_path: Path) -> None:
    hermes_bin = _write_fake_hermes(tmp_path, stdout_text="the ID number is 555 [a.txt]")
    cfg = _cfg(tmp_path, hermes_bin)
    q = _q()

    # Pre-populate the tool log at the exact path this qid will get, simulating the pkm MCP
    # subprocess (a grandchild of the fake hermes stub, never actually spawned in this test)
    # having written it as a side effect of `pkm serve --tool-log`.
    tool_log_path = AH.write_hermes_config(cfg, q["id"])
    tool_log_path.write_text(
        json.dumps({"tool": "search", "results": [{"source_path": "/data/a.txt"}]}) + "\n"
        + json.dumps({"tool": "extract", "results": [{"source_path": "/data/a.txt"}]}) + "\n"
    )

    result = AH.answer_competitor(q, cfg)

    assert result.raw.status == "ok"
    assert result.raw.text == "the ID number is 555 [a.txt]"
    assert result.raw.declined is False
    assert result.raw.llm_calls == []
    assert result.raw.decision_view is None
    assert result.raw.lineage_keys == ("sess-1",)
    assert result.raw.effort == {"tool_calls": 2, "gather_rounds": 1, "asks_issued": 0}
    assert result.usage is not None
    assert result.usage["session_id"] == "sess-1"
    assert len(result.tool_log) == 2


def test_happy_path_uses_hermes_bin_and_toolsets_pkm(tmp_path: Path) -> None:
    """The subprocess argv is exactly the locked shape: -z <prompt> --usage-file <path>
    --toolsets pkm --model <m> --provider <p>. Verified by having the fake stub itself
    assert this and fail loudly (nonzero exit + stderr) if it's wrong."""
    script = tmp_path / "argv-checking-hermes.py"
    script.write_text('''#!/usr/bin/env python3
import json, sys
from pathlib import Path
argv = sys.argv[1:]
assert argv[0] == "-z", argv
assert argv[2] == "--usage-file", argv
assert argv[4] == "--toolsets", argv
assert argv[5] == "pkm", argv
assert argv[6] == "--model", argv
assert argv[8] == "--provider", argv
uf = Path(argv[3])
uf.parent.mkdir(parents=True, exist_ok=True)
uf.write_text(json.dumps({"session_id": "sess-argv-ok"}))
sys.stdout.write("ok")
''')
    script.chmod(0o755)
    cfg = _cfg(tmp_path, script, model="m-x", provider="anthropic")
    result = AH.answer_competitor(_q(), cfg)
    assert result.raw.status == "ok", result.raw.notes
    assert result.raw.text == "ok"


def test_custom_provider_skips_api_key_lookup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(name: str) -> str:
        raise AssertionError(f"secret({name!r}) should not be called for provider=custom")

    monkeypatch.setattr(LLM, "secret", _boom)
    hermes_bin = _write_fake_hermes(tmp_path, stdout_text="answer [x.txt]")
    cfg = _cfg(tmp_path, hermes_bin, provider="custom", base_url="http://localhost:11434/v1")
    result = AH.answer_competitor(_q(), cfg)
    assert result.raw.status == "ok"
    assert any("no API key env injected" in n for n in result.raw.notes.split("; "))


# --- NOT_IN_CORPUS / decline -----------------------------------------------------------------


def test_not_in_corpus_answer_is_declined(tmp_path: Path) -> None:
    hermes_bin = _write_fake_hermes(
        tmp_path, stdout_text="NOT_IN_CORPUS: no passport document in the corpus")
    cfg = _cfg(tmp_path, hermes_bin)
    result = AH.answer_competitor(_q(), cfg)
    assert result.raw.status == "ok"
    assert result.raw.declined is True


# --- timeout ---------------------------------------------------------------------------------


def test_timeout_kills_process_group_and_sets_status(tmp_path: Path) -> None:
    hermes_bin = _write_fake_hermes(tmp_path, sleep_s=5.0)
    cfg = _cfg(tmp_path, hermes_bin, timeout_s=1)
    t0 = time.monotonic()
    result = AH.answer_competitor(_q(), cfg)
    elapsed = time.monotonic() - t0

    assert result.raw.status == "timeout"
    assert result.raw.text == ""
    # If the process group kill didn't actually happen, the sleeping child (and this call)
    # would run for the full 5s sleep. A short elapsed time is the end-to-end proof the kill
    # worked, not just that we intended to send it.
    assert elapsed < 4.0, f"took {elapsed:.1f}s — process group was not actually killed"


# --- retry-once --------------------------------------------------------------------------


def test_retry_once_on_failure_then_success(tmp_path: Path) -> None:
    hermes_bin = _write_fake_hermes(
        tmp_path, stdout_text="answer on retry [b.txt]", fail_first=True)
    cfg = _cfg(tmp_path, hermes_bin)
    result = AH.answer_competitor(_q(), cfg)

    assert result.raw.status == "ok"
    assert result.raw.text == "answer on retry [b.txt]"
    notes = result.raw.notes
    assert "attempt 1" in notes
    assert "attempt 2" in notes
    assert (tmp_path / "_called_once").exists()


def test_retry_once_gives_up_after_second_failure(tmp_path: Path) -> None:
    script = tmp_path / "always-fails.py"
    script.write_text('''#!/usr/bin/env python3
import sys
sys.stderr.write("boom\\n")
sys.exit(1)
''')
    script.chmod(0o755)
    cfg = _cfg(tmp_path, script)
    result = AH.answer_competitor(_q(), cfg)

    assert result.raw.status == "error"
    assert result.raw.text == ""
    assert "attempt 1" in result.raw.notes
    assert "attempt 2" in result.raw.notes


# --- usage missing / corrupt --------------------------------------------------------------


def test_usage_file_missing_is_noted_and_none(tmp_path: Path) -> None:
    hermes_bin = _write_fake_hermes(tmp_path, stdout_text="answer [c.txt]", write_usage=False)
    cfg = _cfg(tmp_path, hermes_bin)
    result = AH.answer_competitor(_q(), cfg)

    assert result.raw.status == "ok"
    assert result.usage is None
    assert "usage file unreadable" in result.raw.notes
    assert result.raw.lineage_keys == ()


# --- state.db cross-check -------------------------------------------------------------------


def test_state_db_cross_check_notes_token_mismatch(tmp_path: Path) -> None:
    hermes_bin = _write_fake_hermes(
        tmp_path, stdout_text="answer [d.txt]",
        usage_payload={**_DEFAULT_USAGE, "session_id": "sess-mismatch",
                       "input_tokens": 100, "output_tokens": 20})
    cfg = _cfg(tmp_path, hermes_bin)

    # state.db lives under $HERMES_HOME, created BEFORE the run (as if a prior process in
    # this same scratch home had already written it) with token counts that disagree with
    # what the usage file will report.
    hermes_home = cfg.run_dir / "arms/competitor/hermes_home"
    hermes_home.mkdir(parents=True, exist_ok=True)
    _make_state_db(
        hermes_home / "state.db", session_id="sess-mismatch", tool_call_count=3,
        input_tokens=999, output_tokens=20)

    result = AH.answer_competitor(_q(), cfg)

    assert result.raw.status == "ok"
    assert "mismatch" in result.raw.notes
    assert "input_tokens" in result.raw.notes


def test_state_db_tool_call_count_is_fallback_when_tool_log_missing(tmp_path: Path) -> None:
    hermes_bin = _write_fake_hermes(
        tmp_path, stdout_text="answer [e.txt]",
        usage_payload={**_DEFAULT_USAGE, "session_id": "sess-fallback"})
    cfg = _cfg(tmp_path, hermes_bin)

    hermes_home = cfg.run_dir / "arms/competitor/hermes_home"
    hermes_home.mkdir(parents=True, exist_ok=True)
    _make_state_db(
        hermes_home / "state.db", session_id="sess-fallback", tool_call_count=7,
        input_tokens=100, output_tokens=20)

    # No tool log file written at all for this qid (the pkm MCP subprocess never actually
    # ran under this fake hermes) — the arm must fall back to state.db's tool_call_count.
    result = AH.answer_competitor(_q(), cfg)

    assert result.raw.effort["tool_calls"] == 7
    assert result.tool_log == []


def test_state_db_absent_is_silently_skipped(tmp_path: Path) -> None:
    """No state.db at all (a from-scratch scratch home) must not be an error — just nothing
    to cross-check."""
    hermes_bin = _write_fake_hermes(tmp_path, stdout_text="answer [f.txt]")
    cfg = _cfg(tmp_path, hermes_bin)
    result = AH.answer_competitor(_q(), cfg)
    assert result.raw.status == "ok"
    assert "cross-check failed" not in result.raw.notes


# --- config rewritten per question, scratch home persists across questions -----------------


def test_hermes_home_is_shared_across_questions(tmp_path: Path) -> None:
    hermes_bin = _write_fake_hermes(tmp_path, stdout_text="a [g.txt]")
    cfg = _cfg(tmp_path, hermes_bin)
    AH.answer_competitor(_q(id_="q-001"), cfg)
    AH.answer_competitor(_q(id_="q-002"), cfg)
    hermes_home = cfg.run_dir / "arms/competitor/hermes_home"
    # Same scratch home dir for both — config.yaml just gets overwritten each time (the
    # tool-log path inside it changes; the directory itself is created once).
    assert hermes_home.exists()
    config = yaml.safe_load((hermes_home / "config.yaml").read_text())
    assert config["mcp_servers"]["pkm"]["args"][-1].endswith("q-002.jsonl")


# --- never raises on an unexpected internal failure -----------------------------------------


def test_unexpected_exception_maps_to_status_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(cfg: AH.HermesArmConfig, qid: str) -> Path:
        raise RuntimeError("config write blew up")

    monkeypatch.setattr(AH, "write_hermes_config", _boom)
    cfg = _cfg(tmp_path, tmp_path / "unused-hermes")
    result = AH.answer_competitor(_q(), cfg)

    assert result.raw.status == "error"
    assert "RuntimeError" in result.raw.notes
    assert result.raw.text == ""
    assert result.usage is None
    assert result.tool_log == []
