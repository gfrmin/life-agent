"""``scripts/fairfight/arm_claude.py`` — the deliberative reference arm (roadmap A1b).

The owner's ruling of 2026-07-19: the gold standard is Claude-Code-grade **deliberation**
— the session-level verify-first process — not a one-shot frontier API call (the
hermes-driven ``oracle`` arm is the FRONTIER BASELINE; this arm is the actual π*). This
module drives ``claude -p`` (Claude Code headless print mode) over the SAME pkm MCP
surface the hermes arms use, so a difference between this arm and the frontier baseline
is attributable to the *deliberative process* (multi-angle retrieval, subject/era
verification, refusal discipline), never to a different corpus surface.

Per question:

1. Write ``mcp-config.json`` under ``run_dir/arms/<arm>/workdir/`` pointing an MCP server
   named ``pkm`` at ``pkm serve --tool-log <run>/arms/<arm>/tool_calls/<qid>.jsonl`` —
   fresh per question, one clean tool log each (same discipline as
   ``arm_hermes.write_hermes_config``).
2. ``claude -p "<PROMPT_DELIB_V1>" --output-format json --model <m> --mcp-config <path>
   --strict-mcp-config --allowedTools mcp__pkm__search,mcp__pkm__extract --max-turns N``,
   cwd = the empty ``workdir`` (no repo CLAUDE.md leak). In headless mode tools outside
   ``--allowedTools`` are denied, so pkm search/extract is the arm's ONLY evidence
   channel — the enforced half of the prompt's "pkm tools only" rule. The permission
   mode is pinned to ``default`` explicitly: headless claude otherwise inherits the
   MACHINE's ambient default, and a restrictive one (e.g. "plan") silently denies even
   the allowed tools — rc=0, no error, zero evidence (PR-33 review CRITICAL).
3. Parse the single result-JSON line from stdout: ``result`` (the answer text),
   ``total_cost_usd``, ``num_turns``, ``usage`` (token counts), ``session_id``,
   ``is_error``/``subtype``. The parsed values are re-shaped into the SAME usage-dict
   vocabulary the hermes arms' ``--usage-file`` produces (``estimated_cost_usd``,
   ``input_tokens``, ``cache_read_tokens``, ``api_calls``, ``session_id``…) and written
   to ``usage/<qid>.json`` — the runner's economics/vector assembly then treats this arm
   identically to any ``records.EXTERNAL_ARMS`` member, no special-casing.
4. Timeout kills the whole process group (``start_new_session=True`` + ``killpg``, same
   deviation-1 rationale as arm_hermes: the MCP ``pkm serve`` grandchild must not be
   orphaned); one retry on a nonzero exit / empty or malformed stdout.

**Provenance caveat (named, not hidden):** ``claude -p`` runs with the machine's own
Claude Code configuration (user-level memory/settings) — that is deliberate: π* is
"Claude Code as it actually runs here", and the config is part of the reference policy.
The binary's version is recorded per run in run_meta (``claude_version``).

Never raises: every failure maps to ``status="error"``/``"timeout"`` on the returned
:class:`~scripts.fairfight.arm_hermes.CompetitorResult` (the shared result shape — this
arm reuses it verbatim so the runner's external-arm path needs no new branch).
"""
from __future__ import annotations

import contextlib
import json
import os
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .arm_baseline import RawAnswer
from .arm_hermes import _REPO_ROOT, CompetitorResult
from .grading import detect_decline

# Frozen prompt contract (sha256 into run_meta; wording edits are a NEW version).
# The SURFACE contract (cite files in [brackets]; a single "NOT_IN_CORPUS: " line for
# absence; no preamble) is deliberately identical to arm_hermes.PROMPT_V1 so grading and
# decline detection treat both arms the same — what differs is the DELIBERATION contract,
# which is the treatment under test.
PROMPT_DELIB_V1 = """You are answering ONE question about the owner's personal records, \
held in a private knowledge corpus you can search through the "pkm" tools you have been \
given. You are the deliberative reference: your job is to be RIGHT, or to say plainly \
that the corpus does not decide the answer. A confident wrong answer is the worst \
possible outcome — far worse than admitting absence.

Deliberation contract, in order:
- Use ONLY the pkm `search` and `extract` tools as evidence. Never outside knowledge, \
never a guess dressed as a fact.
- Search several ways before concluding anything: rephrase the question, try bare key \
terms, identifiers, and native-script forms of names/terms where the corpus may not be \
in English. One empty search is not evidence of absence.
- Verify before asserting, every time: (a) SUBJECT — the corpus names many people; \
confirm from the document itself whose value this is, never attribute by proximity; \
(b) CURRENCY — the corpus spans years and countries; prefer the most recent era's value \
and say when the evidence is dated; (c) CROSS-CHECK — where two independent documents \
can attest the value, read both; if they conflict, say so instead of picking one.
- Cite the source file in [square brackets] after every factual claim, exactly as the \
tool result reported it — never paraphrase, translate, or invent a citation.
- Be concise in the final answer: the value and its citation, no preamble, no restating \
the question.
- If the corpus does not contain (or does not decide) the answer, reply with a single \
line, and nothing else, starting exactly with "NOT_IN_CORPUS: " followed by a short \
description of what is missing or undecided.

QUESTION: {question}"""

_ALLOWED_TOOLS = "mcp__pkm__search,mcp__pkm__extract"


@dataclass(frozen=True)
class ClaudeArmConfig:
    """Everything ``answer_deliberative`` needs for one ``claude -p`` run. Scratch state
    nests under ``run_dir/arms/<arm_name>/`` (workdir/, tool_calls/, usage/), same layout
    contract as the hermes arms so the runner's cleanup/ingestion is shared."""

    claude_bin: str
    run_dir: Path
    pkm_config: str
    model: str = "claude-opus-4-8"
    timeout_s: int = 600  # deliberation is slower than a oneshot by design
    max_turns: int = 40  # the agentic-budget ceiling (recorded in run_meta)
    arm_name: str = "deliberative"


def _workdir(cfg: ClaudeArmConfig) -> Path:
    return cfg.run_dir / "arms" / cfg.arm_name / "workdir"


def write_mcp_config(cfg: ClaudeArmConfig, qid: str) -> tuple[Path, Path]:
    """Write the per-question MCP config json and return ``(config_path,
    tool_log_path)`` — a fresh ``--tool-log`` path per question, one clean log each."""
    workdir = _workdir(cfg)
    workdir.mkdir(parents=True, exist_ok=True)
    tool_log_path = cfg.run_dir / "arms" / cfg.arm_name / "tool_calls" / f"{qid}.jsonl"
    tool_log_path.parent.mkdir(parents=True, exist_ok=True)
    config = {
        "mcpServers": {
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
    config_path = workdir / "mcp-config.json"
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return config_path, tool_log_path


def _usage_path(cfg: ClaudeArmConfig, qid: str) -> Path:
    p = cfg.run_dir / "arms" / cfg.arm_name / "usage" / f"{qid}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _minimal_env() -> dict[str, str]:
    """HOME + PATH only: the claude CLI authenticates from its own state under $HOME —
    no API key is injected (unlike the hermes arms), and nothing else from this
    process's env should shape the reference run."""
    env: dict[str, str] = {}
    for key in ("HOME", "PATH"):
        val = os.environ.get(key)
        if val:
            env[key] = val
    return env


def _run_claude_once(
    cmd: list[str], env: dict[str, str], cwd: Path, timeout_s: float,
) -> tuple[str, str, int | None, bool]:
    """One attempt; ``(stdout, stderr, returncode, timed_out)``. Process-group kill on
    timeout (the MCP ``pkm serve`` grandchild must die with its parent)."""
    proc = subprocess.Popen(
        cmd, env=env, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, start_new_session=True,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout_s)
        return stdout, stderr, proc.returncode, False
    except subprocess.TimeoutExpired:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        stdout, stderr = proc.communicate()
        return stdout, stderr, proc.returncode, True


def _parse_result_json(stdout: str) -> dict[str, Any] | None:
    """The ``--output-format json`` result object, or None on anything malformed."""
    try:
        obj = json.loads(stdout.strip())
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def _usage_from_result(obj: dict[str, Any], model: str) -> dict[str, Any]:
    """Re-shape the claude CLI result object into the hermes usage-file vocabulary the
    runner's economics already speak — one shared external-arm ingestion path."""
    u = obj.get("usage") or {}
    return {
        "estimated_cost_usd": obj.get("total_cost_usd"),
        "model": model,
        "api_calls": obj.get("num_turns"),
        "input_tokens": u.get("input_tokens"),
        "output_tokens": u.get("output_tokens"),
        "cache_read_tokens": u.get("cache_read_input_tokens"),
        "cache_write_tokens": u.get("cache_creation_input_tokens"),
        "session_id": obj.get("session_id"),
        "duration_ms": obj.get("duration_ms"),
        "num_turns": obj.get("num_turns"),
        "subtype": obj.get("subtype"),
    }


def answer_deliberative(q: dict[str, Any], cfg: ClaudeArmConfig) -> CompetitorResult:
    """Answer one question by driving ``claude -p`` over the pkm MCP server. Never
    raises — any failure maps to ``status="error"`` (same convention as every arm)."""
    question_id = str(q["id"])
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
        mcp_config_path, tool_log_path = write_mcp_config(cfg, question_id)
        prompt = PROMPT_DELIB_V1.format(question=q["question"])
        env = _minimal_env()
        cmd = [
            cfg.claude_bin, "-p", prompt,
            "--output-format", "json",
            "--model", cfg.model,
            "--mcp-config", str(mcp_config_path),
            "--strict-mcp-config",
            "--allowedTools", _ALLOWED_TOOLS,
            # PR-33 review CRITICAL: headless claude inherits the MACHINE's ambient
            # permission-mode default (e.g. settings.json defaultMode "plan"), under
            # which the allowed MCP tools are silently DENIED — rc=0, is_error=false,
            # zero evidence gathered, and the apology text would grade as an ordinary
            # wrong answer. Pin the mode explicitly so the arm's behavior never depends
            # on the invoking machine's interactive configuration.
            "--permission-mode", "default",
            "--max-turns", str(cfg.max_turns),
        ]

        for attempt in range(1, 3):  # retry ONCE on failure (same policy as arm_hermes)
            # clean tool log per attempt — the file at this deterministic path persists
            # across invocations (arm_hermes final-review IMPORTANT-6, same hazard here)
            tool_log_path.unlink(missing_ok=True)
            stdout, stderr, rc, timed_out = _run_claude_once(
                cmd, env, _workdir(cfg), cfg.timeout_s)
            if timed_out:
                status = "timeout"
                notes_parts.append(
                    f"attempt {attempt}: timed out after {cfg.timeout_s}s; "
                    "process group killed")
                break
            obj = _parse_result_json(stdout)
            notes_parts.append(
                f"attempt {attempt}: rc={rc} parsed={obj is not None} "
                f"subtype={None if obj is None else obj.get('subtype')}")
            if rc == 0 and obj is not None and not obj.get("is_error"):
                text = str(obj.get("result") or "").strip()
                usage = _usage_from_result(obj, cfg.model)
                status = "ok"
                break
            if stderr.strip():
                notes_parts.append(f"attempt {attempt} stderr: {stderr.strip()[:500]}")
            if obj is not None:  # an is_error result still carries spend — keep it
                usage = _usage_from_result(obj, cfg.model)
            status = "error"  # overwritten above if the retry succeeds

        if usage is not None:
            _usage_path(cfg, question_id).write_text(
                json.dumps(usage, indent=2) + "\n", encoding="utf-8")

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
        tool_calls = len(tool_log_rows)
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
    lineage_keys: tuple[str, ...] = (str(session_id),) if session_id else ()
    effort = {"tool_calls": tool_calls, "gather_rounds": gather_rounds, "asks_issued": 0}
    latency_s = time.monotonic() - t0

    raw = RawAnswer(
        question_id=question_id, text=text, declined=declined, latency_s=latency_s,
        llm_calls=[], decision_view=None, lineage_keys=lineage_keys, status=status,
        notes="; ".join(notes_parts), effort=effort,
        cards=(),  # the retrieved set lives in tool_log rows, same as the hermes arms
    )
    return CompetitorResult(raw=raw, usage=usage, tool_log=tool_log_rows)
