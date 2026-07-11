"""``scripts/fairfight/arm_hermes.py`` — the ``hermes`` competitor arm.

Drives the external `hermes-agent <https://github.com/…/hermes-agent>`_ CLI headlessly
(``hermes -z``) over the **pkm MCP server** (``pkm serve``, SPEC §17) as its only source of
evidence, and wraps the result into this harness's shared raw-capture shape,
:class:`~scripts.fairfight.arm_baseline.RawAnswer` (never rebuilt here — same convention as
``arm_synthesis.py``). Unlike the in-process arms, hermes is a whole separate agent process
with its own tool loop, so this module is a driver + ingester, not an answer path.

**Verified facts about hermes** (traced in the sibling ``hermes-agent`` checkout, read-only,
per the task brief — not trusted from the plan alone):

- ``hermes -z "<prompt>" --usage-file <path> --toolsets pkm --model <m> --provider <p>``
  prints the agent's final text to stdout and auto-approves tools; ``--toolsets`` restricts
  the agent to exactly the named MCP servers from config.
- ``--usage-file`` (``hermes_cli/oneshot.py:_write_usage_file``) writes a JSON report EVEN ON
  FAILURE with (among others) ``estimated_cost_usd``, ``input_tokens``, ``output_tokens``,
  ``session_id``, ``completed``, ``failed`` — confirmed against the real writer, matching the
  brief's key list exactly.
- ``mcp_servers.<name> = {command, args}`` is the real stdio schema (``tools/mcp_tool.py``'s
  own docstring examples use exactly this shape — no ``type``/``transport`` key needed).
  ``tools/mcp_tool.py:_build_safe_env`` filters the env handed to MCP subprocesses to a safe
  baseline (``PATH``/``HOME``/``XDG_*``) plus only what the server config itself declares —
  confirming the brief's claim that env-var instrumentation cannot reach the ``pkm serve``
  subprocess; the tool-log path must ride the config's own ``args`` instead.
- Session state lives in SQLite at ``$HERMES_HOME/state.db``; ``hermes_state.py``'s
  ``sessions`` table DDL includes ``tool_call_count``, ``input_tokens``, ``output_tokens`` —
  the cross-check instrument's exact columns.

**Design deviations from the brief's literal code sketch** (disclosed, not hidden):

1. The brief's ``subprocess.run(..., timeout=cfg.timeout_s, start_new_session=True)`` sketch
   cannot itself satisfy "on timeout kill the whole process group": ``subprocess.run``'s own
   ``TimeoutExpired`` handling calls ``process.kill()`` on the immediate child ONLY (see
   CPython's ``subprocess.run`` source) and the raised exception carries no pid, so there is
   no way to reach ``os.killpg`` from the caller side of ``subprocess.run``. ``_run_hermes_once``
   below uses ``subprocess.Popen`` directly (same args otherwise) so the pgid is on hand,
   exactly the pattern the stdlib docs themselves recommend for a ``start_new_session=True``
   group kill.
2. The brief's example config's literal ``--project <life-agent checkout>`` value is
   illustrative, not a value to hardcode: it would (a) be wrong when this module runs from a
   worktree (as it does today), and (b) trip the repo's PII path-shape guard
   (``.githooks/pii_check.py`` — real machine paths are rejected outright). ``_REPO_ROOT``
   instead derives the project root this module itself lives under
   (``Path(__file__).resolve().parents[2]``), which is correct in both places and never a
   literal in committed text.

Every failure — a bad hermes binary, a config write failure, a corrupt usage file, a
``state.db`` that doesn't exist yet — is caught and mapped to ``status="error"``, mirroring
``arm_baseline``/``arm_synthesis``'s "never raises, the runner survives one bad question"
convention. ``llm_calls=[]`` and ``decision_view=None`` always: hermes's own spend is a
separate process this module cannot meter in-line (the usage file is the record), and hermes
returns free text with no structured decision object — graded as free text by
``grading.grade_channels``, same as any other raw-text arm.
"""
from __future__ import annotations

import contextlib
import json
import os
import signal
import sqlite3
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from life_agent.core import llm as LLM

from .arm_baseline import RawAnswer
from .grading import detect_decline

# The life-agent checkout this module itself lives under (worktree or main repo, whichever
# is running) — NOT a hardcoded machine path. `uv run --project <this>` is how the spawned
# MCP subprocess resolves the `pkm` console entrypoint.
_REPO_ROOT = Path(__file__).resolve().parents[2]

# Provider -> the env var life_agent.core.llm.secret resolves for it. A provider not in this
# map (e.g. "custom", for a local OpenAI-compatible endpoint like Ollama) gets no key at all
# — there is nothing to authenticate against localhost.
_PROVIDER_ENV_KEYS: dict[str, str] = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}

# Frozen prompt-contract template (v1) — sha256 goes into run_meta by a later task. Editing
# this string's wording is a NEW version (PROMPT_V2), never an in-place edit.
PROMPT_V1 = """You are answering ONE question about the owner's personal records, held in a \
private knowledge corpus you can search through the "pkm" tools you have been given.

Rules, in order of importance:
- Use ONLY the pkm `search` and `extract` tools as your evidence for this answer. Never use \
outside knowledge, general assumptions, or anything you know independently of what the tools \
return.
- Beware identity confusion: the corpus contains documents about people other than the owner, \
and a single document can name several people's values (amounts, dates, ID numbers) on the \
same page. Before citing any value as the owner's, confirm from the tool result which subject \
it actually belongs to.
- After every factual claim, cite the source file in [square brackets], exactly as the tool \
result reported it — do not paraphrase, translate, or invent a citation.
- Be concise: answer the question directly, with no preamble, hedging, or restating the \
question.
- If the corpus does not contain the answer, reply with a single line, and nothing else, \
starting exactly with "NOT_IN_CORPUS: " followed by a short description of what is missing.
- Never guess. An unsupported guess is worse than admitting the corpus lacks the answer.

QUESTION: {question}"""


@dataclass(frozen=True)
class HermesArmConfig:
    """Everything ``answer_competitor`` needs to drive one hermes run. ``run_dir`` is the
    fair-fight run's own output directory (a later task's concern) — this arm nests its own
    scratch state under ``run_dir/arms/competitor/``, never beside it."""

    hermes_bin: str
    run_dir: Path
    pkm_config: str
    model: str = "claude-sonnet-4-6"  # same ceiling model as the in-process arms' synthesis
    provider: str = "anthropic"
    base_url: str | None = None
    timeout_s: int = 300


@dataclass(frozen=True)
class CompetitorResult:
    """One question's raw hermes capture: the shared :class:`RawAnswer` shape plus the two
    hermes-specific artifacts a later grading/judge stage needs — the parsed usage-file JSON
    (cost accounting) and the parsed per-question tool log (citation-fidelity checking, via
    ``grading.hermes_citation_check``)."""

    raw: RawAnswer
    usage: dict[str, Any] | None
    tool_log: list[dict[str, Any]]


def _hermes_home(cfg: HermesArmConfig) -> Path:
    return cfg.run_dir / "arms/competitor/hermes_home"


def write_hermes_config(cfg: HermesArmConfig, qid: str) -> Path:
    """Rewrite ``$HERMES_HOME/config.yaml`` for question ``qid`` and return the tool-log path
    it points ``pkm serve --tool-log`` at. Each ``hermes -z`` invocation reloads config and
    spawns a fresh MCP subprocess, so rewriting this file per question — with a fresh
    ``--tool-log`` path baked into the ``pkm serve`` args — gives one clean, per-question tool
    log despite hermes filtering the env passed to MCP subprocesses (§ module docstring)."""
    hermes_home = _hermes_home(cfg)
    hermes_home.mkdir(parents=True, exist_ok=True)
    tool_log_path = cfg.run_dir / "arms/competitor/tool_calls" / f"{qid}.jsonl"
    tool_log_path.parent.mkdir(parents=True, exist_ok=True)

    model_cfg: dict[str, Any] = {"default": cfg.model, "provider": cfg.provider}
    if cfg.base_url:
        model_cfg["base_url"] = cfg.base_url

    config: dict[str, Any] = {
        "model": model_cfg,
        "mcp_servers": {
            "pkm": {
                "command": "uv",
                "args": [
                    "run", "--project", str(_REPO_ROOT),
                    "pkm", "--config", cfg.pkm_config,
                    "serve", "--tool-log", str(tool_log_path),
                ],
            },
        },
    }
    (hermes_home / "config.yaml").write_text(yaml.safe_dump(config, sort_keys=False))
    return tool_log_path


def _usage_path(cfg: HermesArmConfig, qid: str) -> Path:
    p = cfg.run_dir / "arms/competitor/usage" / f"{qid}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _minimal_env(cfg: HermesArmConfig, hermes_home: Path) -> tuple[dict[str, str], list[str]]:
    """The filtered subprocess env: HERMES_HOME + HOME + PATH + the provider's API key (fetched
    lazily via ``life_agent.core.llm.secret`` — never read from ``.env``), skipped for a
    provider with no key mapping (a local/custom OpenAI-compatible endpoint has nothing to
    authenticate). ``LLM.secret`` is called as a module attribute (not ``from ... import
    secret``) so a caller can monkeypatch ``life_agent.core.llm.secret`` and have it take
    effect here, per this harness's "never touch the real keyring in tests" convention."""
    notes: list[str] = []
    env: dict[str, str] = {"HERMES_HOME": str(hermes_home)}
    for key in ("HOME", "PATH"):
        val = os.environ.get(key)
        if val:
            env[key] = val
    key_name = _PROVIDER_ENV_KEYS.get(cfg.provider)
    if key_name is None:
        notes.append(f"provider {cfg.provider!r}: no API key env injected (custom/local)")
    else:
        try:
            env[key_name] = LLM.secret(key_name)
        except SystemExit as e:
            notes.append(f"{key_name} lookup failed: {e}")
    return env, notes


def _run_hermes_once(
    cmd: list[str], env: dict[str, str], cwd: Path, timeout_s: float,
) -> tuple[str, str, int | None, bool]:
    """Run one hermes attempt. Returns ``(stdout, stderr, returncode, timed_out)``.

    Uses ``subprocess.Popen`` directly (not ``subprocess.run``) so a timeout can kill the
    WHOLE process group, not just the immediate hermes process — ``start_new_session=True``
    makes the child its own session/group leader, and hermes' own MCP subprocess (``pkm
    serve``) is its grandchild; killing only the leader would orphan it (§ module docstring
    deviation 1)."""
    proc = subprocess.Popen(
        cmd, env=env, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, start_new_session=True,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout_s)
        return stdout, stderr, proc.returncode, False
    except subprocess.TimeoutExpired:
        with contextlib.suppress(ProcessLookupError):  # already gone
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        stdout, stderr = proc.communicate()  # reap + collect whatever was buffered
        return stdout, stderr, proc.returncode, True


def _cross_check_state_db(
    hermes_home: Path, session_id: str | None, usage: dict[str, Any] | None, notes: list[str],
) -> int | None:
    """Read-only cross-check of ``$HERMES_HOME/state.db``'s ``sessions`` row for
    ``session_id`` (opened URI-mode ``?mode=ro`` — this arm never writes to hermes' own
    state). Appends a note on a token-count mismatch against the usage-file JSON; returns the
    row's ``tool_call_count`` (the tool-log-missing fallback), or ``None`` when there's
    nothing to cross-check (no session_id, no db yet, or no matching row) — never raises, a
    missing/locked db is not this arm's failure."""
    if not session_id:
        return None
    db_path = hermes_home / "state.db"
    if not db_path.exists():
        return None
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            row = conn.execute(
                "SELECT tool_call_count, input_tokens, output_tokens FROM sessions "
                "WHERE id = ?",
                (session_id,),
            ).fetchone()
        finally:
            conn.close()
    except sqlite3.Error as e:
        notes.append(f"state.db cross-check failed: {type(e).__name__}: {e}")
        return None
    if row is None:
        return None
    tool_call_count, db_in, db_out = row
    if usage is not None:
        u_in, u_out = usage.get("input_tokens"), usage.get("output_tokens")
        if u_in is not None and db_in is not None and int(u_in) != int(db_in):
            notes.append(
                f"state.db cross-check: input_tokens mismatch (usage={u_in} db={db_in})")
        if u_out is not None and db_out is not None and int(u_out) != int(db_out):
            notes.append(
                f"state.db cross-check: output_tokens mismatch (usage={u_out} db={db_out})")
    return int(tool_call_count) if tool_call_count is not None else None


def answer_competitor(q: dict[str, Any], cfg: HermesArmConfig) -> CompetitorResult:
    """Answer one question by driving hermes headlessly over the pkm MCP server. Never
    raises — any failure (config write, a missing binary, a corrupt usage file, a `state.db`
    query error) is caught and mapped to ``status="error"``, same convention as
    ``arm_baseline.answer_baseline``/``arm_synthesis.answer_synthesis``."""
    question_id = str(q["id"])
    hermes_home = _hermes_home(cfg)
    t0 = time.monotonic()

    text = ""
    status = "ok"
    notes_parts: list[str] = []
    usage: dict[str, Any] | None = None
    tool_log_rows: list[dict[str, Any]] = []
    tool_calls = 0
    gather_rounds = 0
    session_id: str | None = None

    try:
        tool_log_path = write_hermes_config(cfg, question_id)
        uf = _usage_path(cfg, question_id)
        prompt = PROMPT_V1.format(question=q["question"])
        env, env_notes = _minimal_env(cfg, hermes_home)
        notes_parts.extend(env_notes)
        cmd = [
            cfg.hermes_bin, "-z", prompt, "--usage-file", str(uf),
            "--toolsets", "pkm", "--model", cfg.model, "--provider", cfg.provider,
        ]

        for attempt in range(1, 3):  # retry ONCE on nonzero exit or empty stdout
            stdout, stderr, rc, timed_out = _run_hermes_once(cmd, env, hermes_home, cfg.timeout_s)
            if timed_out:
                status = "timeout"
                notes_parts.append(
                    f"attempt {attempt}: timed out after {cfg.timeout_s}s; process group killed")
                break
            notes_parts.append(f"attempt {attempt}: rc={rc} stdout_len={len(stdout.strip())}")
            if rc == 0 and stdout.strip():
                text = stdout.strip()
                status = "ok"
                break
            if stderr.strip():
                notes_parts.append(f"attempt {attempt} stderr: {stderr.strip()[:500]}")
            status = "error"  # overwritten below if the retry succeeds

        try:
            usage = json.loads(uf.read_text())
        except (OSError, json.JSONDecodeError) as e:
            usage = None
            notes_parts.append(f"usage file unreadable: {type(e).__name__}: {e}")

        if tool_log_path.exists():
            for raw_line in tool_log_path.read_text().splitlines():
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    tool_log_rows.append(json.loads(raw_line))
                except json.JSONDecodeError:
                    notes_parts.append("tool log: skipped one malformed JSONL line")

        session_id = (usage or {}).get("session_id")
        db_tool_calls = _cross_check_state_db(hermes_home, session_id, usage, notes_parts)
        tool_calls = len(tool_log_rows) if tool_log_rows else (db_tool_calls or 0)
        gather_rounds = sum(1 for r in tool_log_rows if r.get("tool") == "search")
    except (Exception, SystemExit) as e:
        status = "error"
        notes_parts.append(f"{type(e).__name__}: {e}")
        text = ""
        usage = None
        tool_log_rows = []
        tool_calls = 0
        gather_rounds = 0
        session_id = None

    declined = detect_decline(text)
    lineage_keys: tuple[str, ...] = (session_id,) if session_id else ()
    effort = {"tool_calls": tool_calls, "gather_rounds": gather_rounds, "asks_issued": 0}
    latency_s = time.monotonic() - t0

    raw = RawAnswer(
        question_id=question_id, text=text, declined=declined, latency_s=latency_s,
        llm_calls=[], decision_view=None, lineage_keys=lineage_keys, status=status,
        notes="; ".join(notes_parts), effort=effort,
    )
    return CompetitorResult(raw=raw, usage=usage, tool_log=tool_log_rows)
