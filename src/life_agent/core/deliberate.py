"""The deliberative answer edge — the A1b arm promoted to a production transformation.

Declared instrument (bayesian-foundations §2): **construct** = "the corpus-decided answer
to the question, cited"; **error-model class** = monolithic (free-form generation, the
widest class — population-calibrated only); **calibration route** = the outcomes log,
folded per-edge by :mod:`life_agent.core.calibration`. The measured basis for promotion
is the fair-fight A1b arm (92.3% correct over the 104-question corpus,
ff-v2-delib-20260719); the prompt contract below is its V2 — V1's deliberation and
surface contract plus one addition, the CREDENCE line.

The CREDENCE line is a **signal, never a score** (§1 M3: the LLM proposes; it never
infers at question time): :func:`parse_credence` strips it off the answer text, and the
executor folds it only through the per-edge reliability curve
(:func:`life_agent.core.calibration.curve_for` — pessimistic where evidence is thin),
never as the observation reliability directly.

Origin: ``scripts/fairfight/arm_claude.py`` (kept: the eval harness still runs the frozen
V1 arm). This module carries none of the eval world — no gold, no grading, no runner
state; the claude CLI invocation is injectable for hermetic tests.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import signal
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from life_agent.core import calibration as CAL
from life_agent.core import decisions as DEC
from life_agent.core import derivations as D

_REPO_ROOT = Path(__file__).resolve().parents[3]

_ALLOWED_TOOLS = "mcp__pkm__search,mcp__pkm__extract"

# (cmd, env, cwd, timeout_s) -> (stdout, stderr, returncode, timed_out) — the subprocess
# seam, injectable so tests never shell the CLI.
Runner = Callable[[list[str], dict[str, str], Path, float],
                  tuple[str, str, int | None, bool]]

# Frozen prompt contract (wording edits are a NEW version — V1 lives with the eval arm).
# The deliberation + surface contract is V1's verbatim; the delta is the CREDENCE line:
# a self-reported P(answer correct) the calibrated map consumes as a signal.
PROMPT_DELIB_V2 = """You are answering ONE question about the owner's personal records, \
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
- Otherwise, end your answer with exactly two final lines: "ANSWER: v" where v is the \
bare answer value alone (a number, an id, a date, a name — no sentence, no citation), \
then "CREDENCE: p" where p is a number in [0, 1] — your honest probability that the \
answer you gave is correct, given everything you read. Overstating it is the worst \
failure; calibration is graded.

QUESTION: {question}"""

# The final-line protocol: each line is matched only when it is the LAST non-empty line.
_CREDENCE_RE = re.compile(r"^CREDENCE:\s*(\S+)\s*$")
_ANSWER_RE = re.compile(r"^ANSWER:\s*(.+?)\s*$")


def _strip_final_line(text: str, pattern: re.Pattern[str]) -> tuple[str, str | None]:
    """Split off the final non-empty line when it matches a protocol pattern — protocol
    traffic never reaches the owner; a non-matching tail leaves the text untouched."""
    lines = text.splitlines()
    idx = len(lines) - 1
    while idx >= 0 and not lines[idx].strip():
        idx -= 1
    if idx < 0:
        return text, None
    m = pattern.match(lines[idx].strip())
    if m is None:
        return text, None
    return "\n".join(lines[:idx]).rstrip(), m.group(1)


def parse_credence(text: str) -> tuple[str, float | None]:
    """Split the answer text from its CREDENCE line. A recognisable credence attempt on
    the final non-empty line is always stripped; it yields a signal only when it parses
    to a number in [0, 1] — anything else is a protocol violation and folds as
    no-signal, never a clamp."""
    stripped, raw = _strip_final_line(text, _CREDENCE_RE)
    if raw is None:
        return stripped, None
    try:
        p = float(raw)
    except ValueError:
        return stripped, None
    return stripped, (p if 0.0 <= p <= 1.0 else None)


def parse_value(text: str) -> tuple[str, str | None]:
    """Split the answer text from its ANSWER line — the bare value the candidate-lattice
    join consumes (prose is for the owner; a join must never mint a sentence as a
    value)."""
    return _strip_final_line(text, _ANSWER_RE)


def detect_decline(text: str) -> bool:
    """True iff the edge declined by its own contract: a ``NOT_IN_CORPUS:`` line. (The
    eval harness's wider decline heuristics grade OTHER arms; this edge's decline is a
    protocol line, checked exactly.)"""
    return any(line.strip().startswith("NOT_IN_CORPUS:") for line in text.splitlines())


@dataclass(frozen=True)
class DeliberateConfig:
    """Everything one deliberative call needs. ``scratch_dir`` holds the per-question MCP
    config, tool logs, and workdir (the CLI's cwd — empty by design, no repo CLAUDE.md
    leak); it is scratch, never the ledger."""

    claude_bin: str
    scratch_dir: Path
    pkm_config: str
    model: str = "claude-opus-4-8"
    timeout_s: int = 600
    max_turns: int = 40


@dataclass(frozen=True)
class DeliberateResult:
    """One deliberative answer, fully priced. ``credence`` is the parsed self-report
    signal (None on declines, protocol violations, and failures); ``cost_usd`` is the
    CLI-reported spend — both travel to the decision log (§10 accounting), never only to
    an eval run dir."""

    question: str
    model: str
    text: str
    value: str | None
    credence: float | None
    declined: bool
    status: str  # ok | error | timeout
    notes: str
    cost_usd: float | None
    latency_s: float
    input_tokens: int | None
    output_tokens: int | None
    session_id: str | None
    tool_calls: int
    gather_rounds: int


def instrument(model: str) -> str:
    """The per-edge attribution name (calibration + decision log): one spelling."""
    return f"deliberate@{model}"


def calibrated_credence(result: DeliberateResult,
                        curves: dict[str, CAL.ReliabilityCurve]) -> float:
    """The Δ1 map: self-reported credence (a signal) → calibrated P(correct), through the
    edge's reliability curve. Cold start is the pessimistic Beta(1,3) prior everywhere —
    an unproven edge cannot clear the assertion floor on self-report alone (§16). A
    missing credence (protocol violation) maps at the curve's most pessimistic bin —
    no signal is never rewarded. Not meaningful for declines (nothing is asserted)."""
    curve = CAL.curve_for(curves, instrument(result.model))
    return curve.calibrate(result.credence if result.credence is not None else 0.0)


def _workdir(cfg: DeliberateConfig) -> Path:
    return cfg.scratch_dir / "workdir"


def write_mcp_config(cfg: DeliberateConfig, qid: str) -> tuple[Path, Path]:
    """Write the per-question MCP config json; return ``(config_path, tool_log_path)`` —
    a fresh ``--tool-log`` path per question, one clean log each."""
    workdir = _workdir(cfg)
    workdir.mkdir(parents=True, exist_ok=True)
    tool_log_path = cfg.scratch_dir / "tool_calls" / f"{qid}.jsonl"
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


def _minimal_env() -> dict[str, str]:
    """HOME + PATH only: the claude CLI authenticates from its own state under $HOME;
    nothing else from this process's env may shape the edge."""
    return {k: v for k in ("HOME", "PATH") if (v := os.environ.get(k))}


def _run_claude_once(cmd: list[str], env: dict[str, str], cwd: Path,
                     timeout_s: float) -> tuple[str, str, int | None, bool]:
    """One attempt; process-group kill on timeout (the MCP ``pkm serve`` grandchild must
    die with its parent)."""
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
    try:
        obj = json.loads(stdout.strip())
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def answer(question: str, cfg: DeliberateConfig, *,
           run_once: Runner = _run_claude_once) -> DeliberateResult:
    """Answer one question by driving ``claude -p`` over the pkm MCP surface. Never
    raises — any failure maps to ``status="error"``/``"timeout"`` (transient failures
    are never frozen: only ``status == "ok"`` results may be recorded)."""
    qid = DEC.question_id(question)
    t0 = time.monotonic()

    raw_text = ""
    status = "ok"
    notes_parts: list[str] = []
    usage: dict[str, Any] = {}
    tool_log_rows: list[dict[str, Any]] = []

    try:
        mcp_config_path, tool_log_path = write_mcp_config(cfg, qid)
        cmd = [
            cfg.claude_bin, "-p", PROMPT_DELIB_V2.format(question=question),
            "--output-format", "json",
            "--model", cfg.model,
            "--mcp-config", str(mcp_config_path),
            "--strict-mcp-config",
            "--allowedTools", _ALLOWED_TOOLS,
            # Pinned: headless claude otherwise inherits the MACHINE's ambient
            # permission default, under which the allowed MCP tools are silently
            # denied — rc=0, zero evidence (the eval arm's PR-33 CRITICAL).
            "--permission-mode", "default",
            "--max-turns", str(cfg.max_turns),
        ]
        for attempt in range(1, 3):  # retry ONCE on failure
            tool_log_path.unlink(missing_ok=True)  # clean log per attempt
            stdout, stderr, rc, timed_out = run_once(
                cmd, _minimal_env(), _workdir(cfg), cfg.timeout_s)
            if timed_out:
                status = "timeout"
                notes_parts.append(
                    f"attempt {attempt}: timed out after {cfg.timeout_s}s")
                break
            obj = _parse_result_json(stdout)
            notes_parts.append(
                f"attempt {attempt}: rc={rc} parsed={obj is not None} "
                f"subtype={None if obj is None else obj.get('subtype')}")
            if rc == 0 and obj is not None and not obj.get("is_error"):
                raw_text = str(obj.get("result") or "").strip()
                usage = obj
                status = "ok"
                break
            if stderr.strip():
                notes_parts.append(f"attempt {attempt} stderr: {stderr.strip()[:500]}")
            if obj is not None:  # an is_error result still carries spend — keep it
                usage = obj
            status = "error"  # overwritten above if the retry succeeds

        if tool_log_path.exists():
            for raw_line in tool_log_path.read_text().splitlines():
                if not raw_line.strip():
                    continue
                try:
                    tool_log_rows.append(json.loads(raw_line))
                except json.JSONDecodeError:
                    notes_parts.append("tool log: skipped one malformed JSONL line")
    except (Exception, SystemExit) as e:
        status = "error"
        notes_parts.append(f"{type(e).__name__}: {e}")
        raw_text = ""
        usage = {}
        tool_log_rows = []

    if status == "ok":
        text, credence = parse_credence(raw_text)
        text, value = parse_value(text)
    else:
        text, value, credence = raw_text, None, None
    declined = detect_decline(text)
    tokens = usage.get("usage") or {}
    return DeliberateResult(
        question=question, model=cfg.model, text=text,
        value=None if declined else value,
        credence=None if declined else credence, declined=declined,
        status=status, notes="; ".join(notes_parts),
        cost_usd=usage.get("total_cost_usd"),
        latency_s=time.monotonic() - t0,
        input_tokens=tokens.get("input_tokens"),
        output_tokens=tokens.get("output_tokens"),
        session_id=usage.get("session_id"),
        tool_calls=len(tool_log_rows),
        gather_rounds=sum(1 for r in tool_log_rows if r.get("tool") == "search"),
    )


def record_answer(root: Path, key: D.StageKey, result: DeliberateResult) -> bool:
    """Record one deliberative answer file-first (§18.9). Only successes: a transient
    CLI failure must never be frozen as the replayed result. Lineage is empty in v0 —
    the CLI tool log names searches, not artifact cache keys; the session identity and
    effort live in metadata, and the citation audit grounds the [file] citations
    downstream (a named gap, not a hidden one)."""
    if result.status != "ok":
        raise ValueError(f"only status='ok' results are recorded, got {result.status!r}")
    content = json.dumps({
        "format_version": 1, "question": result.question, "model": result.model,
        "text": result.text, "value": result.value, "credence": result.credence,
        "declined": result.declined,
        "cost_usd": result.cost_usd, "session_id": result.session_id,
        "tool_calls": result.tool_calls, "gather_rounds": result.gather_rounds,
    }, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return D.record(root, key, content, lineage=[], metadata={
        "session_id": result.session_id, "tool_calls": result.tool_calls,
        "gather_rounds": result.gather_rounds, "instrument": instrument(result.model),
    })
