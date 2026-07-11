"""``tests/test_fairfight_live.py`` — live-integration smokes for the fair-fight harness
(task 12, first half). Opt-in only: both tests below carry ``llm``/``system`` markers, which
``pyproject.toml``'s ``addopts`` skips by default — the hermetic suite (``uv run pytest``) is
unaffected. Run explicitly:

    uv run --project . pytest tests/test_fairfight_live.py -m 'llm or system' -q

Real API spend is authorized here: ONE judge call batch (``judge_modal``'s ``n=3``, gpt-5.1)
and ONE hermes oneshot session (claude-sonnet-4-6, ~1 API call) — nothing more. Every corpus
and scratch directory used by ``test_hermes_oneshot_smoke`` is ``tmp_path``; neither test ever
reads or writes the real ``$LIFE_AGENT_KB`` or the owner's real hermes home directory. Both
tests fetch credentials via ``life_agent.core.llm.secret`` (env then gnome-keyring) and skip,
by name, when a credential or the hermes binary is unavailable — never a hard failure on a
missing dependency.
"""
from __future__ import annotations

import shutil
import sqlite3
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from fairfight import arm_hermes as AH
from fairfight import judge as J

from life_agent.core import llm as LLM
from pkm.cli import main as pkm_main
from pkm.producers.pandoc import installed_pandoc_version

# --- llm: the real judge, one synthetic question/answer/sources triple --------------------


@pytest.mark.llm
def test_judge_one_answer() -> None:
    """``judge.judge_modal`` against the real cross-provider judge (gpt-5.1 via
    ``judge_complete`` — SPEC pin in ``scripts/comparison/_common.py``). One synthetic,
    PII-free Q/A/sources triple; ``n=3`` live calls (the authorized judge batch). Asserts only
    the documented output shape — three int dims in [0, 3] — never a specific score, since the
    judge's actual verdict is not this test's contract."""
    try:
        LLM.secret("OPENAI_API_KEY")
    except SystemExit as e:
        pytest.skip(f"OPENAI_API_KEY unavailable (env + keyring): {e}")

    q = {
        "id": "q-live-judge-001",
        "question": "What is the synthetic librarian's badge number?",
        "answer": "424242",
        "expected_components": ["badge_number"],
        "answerable": True,
    }
    answer_text = "The synthetic librarian's badge number is 424242 [lib-badge.txt]."
    sources = [{
        "n": 1, "source_path": "lib-badge.txt",
        "text": "The synthetic librarian's badge number is 424242.",
    }]

    out = J.judge_modal(q, answer_text, sources, n=3)

    assert out, "judge_modal returned {} — all 3 live judge calls failed to parse as strict JSON"
    for dim in ("faithfulness", "completeness", "citation_fidelity"):
        assert dim in out, f"missing dim {dim!r} in judge output: {out}"
        assert isinstance(out[dim], int), f"{dim}={out[dim]!r} is not an int"
        assert 0 <= out[dim] <= 3, f"{dim}={out[dim]} outside the rubric's 0-3 range"
    print(f"[test_judge_one_answer] live judge dims: {out}")


# --- system: the real hermes binary, one oneshot session over a tmp synthetic pkm corpus ---

_BADGE_FACT_VALUE = "424242"
_BADGE_DOC = (
    "# Library Records\n\n"
    "The synthetic librarian's badge number is 424242. This is recorded in the "
    "west wing archive of the fictional Fairfight Public Library.\n"
)
_DECOY_DOC = (
    "# Unrelated Notes\n\n"
    "The synthetic archivist's badge number is 010101 — a different person "
    "entirely, not the librarian.\n"
)
_FILLER_DOC = (
    "# Meeting Minutes\n\n"
    "Quarterly review of the synthetic reading room budget: 42 dollars allocated "
    "for new bookmarks.\n"
)


def _default_hermes_bin() -> Path:
    """The conventional sibling ``hermes-agent`` checkout's own venv console-script, at
    ``<git-checkouts-root>/hermes-agent/.venv/bin/hermes`` — built from ``Path.home()`` at
    runtime, one segment at a time, so no literal machine path ever appears in committed text
    (the repo's PII path-shape guard forbids ``$HOME``-rooted literals).

    Deliberately NOT the repo-root wrapper script (plain ``hermes-agent/hermes``): that file's
    shebang is bare ``#!/usr/bin/env python3`` and depends on whatever's on ``PATH``, which is
    NOT hermes-agent's own dependency set (confirmed live: it raises
    ``ModuleNotFoundError: rich`` under this harness's filtered subprocess env). The venv
    console-script's shebang instead points at its own interpreter directly, so it runs
    standalone exactly like ``arm_hermes.py``'s subprocess model expects (matching the
    fake-hermes stub convention in ``tests/test_fairfight_hermes.py``)."""
    return Path.home() / "git" / "hermes-agent" / ".venv" / "bin" / "hermes"


def _resolve_hermes_bin() -> str | None:
    """``HERMES_BIN`` env override, else ``shutil.which("hermes")``, else the conventional
    sibling-checkout venv script. ``None`` if nothing resolves — the caller skips by name."""
    import os

    env = os.environ.get("HERMES_BIN")
    if env:
        return env
    which = shutil.which("hermes")
    if which:
        return which
    fallback = _default_hermes_bin()
    return str(fallback) if fallback.exists() else None


def _build_synthetic_pkm_corpus(pkm_root: Path, pkm_config: Path, docs_dir: Path) -> None:
    """Build a real, tiny pkm corpus at ``pkm_root`` via the actual CLI pipeline (never a
    direct SQL seed — this must be genuinely searchable through the same path
    ``pkm serve``'s FTS uses): migrate -> ingest -> extract(pandoc) -> chunk --backfill ->
    rebuild-index. Mirrors ``scripts/bootstrap-sample.sh``'s real sequence, at CLI-``main()``
    level (no subprocess) since this step doesn't need to model the real hermes binary's
    process boundary the way ``pkm serve`` itself does."""
    (pkm_root / "cache").mkdir(parents=True)
    (pkm_root / "logs").mkdir()
    sources_dir = pkm_root / "sources"
    sources_dir.mkdir()

    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "lib-badge.md").write_text(_BADGE_DOC, encoding="utf-8")
    (docs_dir / "archivist.md").write_text(_DECOY_DOC, encoding="utf-8")
    (docs_dir / "minutes.md").write_text(_FILLER_DOC, encoding="utf-8")

    pandoc_version = installed_pandoc_version()
    pkm_config.write_text(
        f"root_dir: {pkm_root}\n"
        "extractors:\n"
        "  pandoc:\n"
        f"    version: \"{pandoc_version}\"\n"
        "    config: {}\n",
        encoding="utf-8",
    )
    entries = [{"path": str(p)} for p in sorted(docs_dir.glob("*.md"))]
    (sources_dir / "sources.yaml").write_text(
        yaml.safe_dump({"version": 1, "sources": entries}), encoding="utf-8")

    for args in (
        ["--config", str(pkm_config), "migrate"],
        ["--config", str(pkm_config), "ingest"],
        ["--config", str(pkm_config), "extract", "--producer", "pandoc"],
        ["--config", str(pkm_config), "chunk", "--backfill"],
        ["--config", str(pkm_config), "rebuild-index"],
    ):
        rc = pkm_main(args)
        assert rc == 0, f"pkm {' '.join(args)} failed with exit code {rc}"


def _assert_corpus_searchable(pkm_root: Path) -> None:
    """The corpus must be searchable via the SAME FTS path ``pkm serve``'s ``search`` tool
    uses (``pkm.mcp_server``), not just the CLI — this is the pre-flight check the task brief
    asks for before handing the corpus to hermes."""
    import pkm.mcp_server as ms

    ms.set_root(pkm_root)
    try:
        results = ms.search(_BADGE_FACT_VALUE, k=5)
    finally:
        ms.set_root(None)  # type: ignore[arg-type]
    assert results, "synthetic badge fact not retrievable via pkm FTS — corpus build is broken"
    assert any(_BADGE_FACT_VALUE in r["chunk_text"] for r in results)


def _pkm_log_line_count(pkm_root: Path) -> int:
    """Total lines across every ``pkm_root/logs/*.jsonl`` file (SPEC §10's per-day JSONL
    diagnostic log — every ``pkm`` CLI invocation, including a spawned ``pkm serve``,
    configures this logger via ``pkm.cli._configure_logging`` before dispatch). A weak signal
    on its own (a quiet, no-error, no-tool-call ``serve`` session may add zero lines even if
    it DID start), but a useful corroborating data point alongside the tool log and hermes'
    own session bookkeeping."""
    logs_dir = pkm_root / "logs"
    if not logs_dir.exists():
        return 0
    return sum(
        sum(1 for line in p.read_text(encoding="utf-8").splitlines() if line.strip())
        for p in logs_dir.glob("*.jsonl")
    )


def _session_tool_call_count(hermes_home: Path, session_id: str | None) -> int | None:
    """Read-only cross-check of ``state.db``'s ``sessions.tool_call_count`` for
    ``session_id`` — the SAME query ``arm_hermes._cross_check_state_db`` already runs.
    ``None`` when nothing is there to check (no session_id, no db, no matching row)."""
    if not session_id:
        return None
    db_path = hermes_home / "state.db"
    if not db_path.exists():
        return None
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        row = conn.execute(
            "SELECT tool_call_count FROM sessions WHERE id = ?", (session_id,)).fetchone()
    finally:
        conn.close()
    return int(row[0]) if row and row[0] is not None else None


@pytest.mark.system
def test_hermes_oneshot_smoke(tmp_path: Path) -> None:
    """One real ``hermes -z --toolsets pkm`` session, over a real (tiny, synthetic) pkm
    corpus served by a real ``pkm serve`` MCP subprocess, driven through the actual
    ``arm_hermes.answer_competitor`` competitor-arm code (not a re-implementation).

    Verifies, with real artifacts (never eyeballed transcript text): the answer is non-empty,
    the usage file was ingested, the pkm tool log is non-empty, the answer contains the
    synthetic fact or is an explicit decline (printed either way — a decline here is a
    FINDING), and reports what evidence is/isn't available for the ``--toolsets pkm``
    core-toolset-exclusion claim (Risk 3 of the task-12 plan)."""
    hermes_bin = _resolve_hermes_bin()
    if hermes_bin is None:
        pytest.skip(
            "hermes binary not found: shutil.which('hermes') is None, HERMES_BIN is unset, "
            "and the sibling hermes-agent checkout's venv console-script does not exist")
    try:
        LLM.secret("ANTHROPIC_API_KEY")
    except SystemExit as e:
        pytest.skip(f"ANTHROPIC_API_KEY unavailable (env + keyring): {e}")

    pkm_root = tmp_path / "pkm-root"
    pkm_config = tmp_path / "pkm-config.yaml"
    docs_dir = tmp_path / "docs"
    _build_synthetic_pkm_corpus(pkm_root, pkm_config, docs_dir)
    _assert_corpus_searchable(pkm_root)
    # Baseline: pkm's own SPEC §10 JSONL diagnostic log after the corpus build (our own
    # migrate/ingest/extract/chunk/rebuild-index calls), BEFORE hermes ever runs — so any
    # NEW lines afterwards can only have come from a `pkm serve` subprocess hermes spawned.
    pkm_log_lines_before = _pkm_log_line_count(pkm_root)

    cfg = AH.HermesArmConfig(
        hermes_bin=hermes_bin,
        run_dir=tmp_path / "run",
        pkm_config=str(pkm_config),
        # model/provider left at HermesArmConfig's own defaults (claude-sonnet-4-6 / anthropic).
        timeout_s=180,
    )
    q = {
        "id": "q-hermes-smoke-001",
        "question": "What is the synthetic librarian's badge number, per the corpus?",
    }

    result = AH.answer_competitor(q, cfg)

    # --- gather + print every diagnostic BEFORE any hard assertion can short-circuit the run:
    # each hermes session is a real, billed API call, so a single invocation should leave the
    # fullest possible evidence trail even when (especially when) something below fails.
    print(f"[test_hermes_oneshot_smoke] status={result.raw.status} notes={result.raw.notes!r}")
    print(f"[test_hermes_oneshot_smoke] usage: {result.usage}")
    text = result.raw.text
    if result.raw.declined:
        print(f"[test_hermes_oneshot_smoke] FINDING — hermes DECLINED: {text}")
    else:
        print(f"[test_hermes_oneshot_smoke] hermes ANSWERED: {text}")
    print(f"[test_hermes_oneshot_smoke] pkm tool_log rows: {len(result.tool_log)}")

    # --toolsets pkm restriction evidence (Risk 3) — three independent read-only signals:
    # 1. hermes' own toolset validator (hermes_cli/oneshot.py:_validate_explicit_toolsets)
    #    writes to the REAL stderr (captured into notes) BEFORE the run, when "pkm" fails to
    #    resolve against either a built-in toolset name or a configured MCP server name.
    notes = result.raw.notes
    toolset_name_rejected = (
        "did not contain any valid toolsets" in notes
        or "ignoring unknown --toolsets entries" in notes
    )
    # 2. state.db's sessions.tool_call_count is the agent-WIDE counter (incremented for every
    #    tool call regardless of toolset, per hermes_state.py) — cross-checked against the
    #    pkm-only tool log's own row count. Equal-or-less is CONSISTENT WITH (not proof of) no
    #    non-pkm tool call happening; a strictly greater db count is direct evidence a non-pkm
    #    tool fired despite --toolsets pkm.
    hermes_home = cfg.run_dir / "arms/competitor/hermes_home"
    session_id = (result.usage or {}).get("session_id")
    db_tool_calls = _session_tool_call_count(hermes_home, session_id)
    # 3. pkm's own SPEC §10 JSONL log line count, before vs after — a weak but free
    #    corroborating signal for whether a `pkm serve` subprocess ran at all (see
    #    _pkm_log_line_count's docstring for why this can't be a hard assertion on its own).
    pkm_log_lines_after = _pkm_log_line_count(pkm_root)
    print(
        f"[test_hermes_oneshot_smoke] toolset-restriction evidence: "
        f"toolset_name_rejected_by_hermes={toolset_name_rejected} "
        f"pkm_tool_log_rows={len(result.tool_log)} "
        f"state.db_tool_call_count={db_tool_calls} "
        f"pkm_own_log_lines_before={pkm_log_lines_before} after={pkm_log_lines_after}")
    if db_tool_calls is None:
        print(
            "[test_hermes_oneshot_smoke] toolset-restriction cross-check NOT ASSERTABLE: no "
            "session_id or no state.db row for it")

    # --- now the hard assertions (task-12-brief's required checks), in the brief's order ---
    assert result.raw.status == "ok", f"hermes run did not complete ok: {result.raw.notes}"
    assert result.raw.text.strip() != "", f"empty stdout answer; notes={result.raw.notes}"

    assert result.usage is not None, f"usage file was not ingested; notes={result.raw.notes}"
    api_calls = result.usage.get("api_calls")
    assert api_calls is not None and api_calls >= 1, f"usage.api_calls={api_calls!r}"

    assert not toolset_name_rejected, (
        f"hermes rejected --toolsets pkm as an unknown/invalid name: {notes}")

    if not result.raw.declined:
        assert _BADGE_FACT_VALUE in text, (
            f"answer neither declined nor contained the synthetic fact {_BADGE_FACT_VALUE!r}: "
            f"{text!r}")

    assert len(result.tool_log) > 0, (
        "pkm tool log is EMPTY — hermes never called the pkm search/extract MCP tools "
        f"(status=ok, declined={result.raw.declined}, api_calls={api_calls}, "
        f"state.db_tool_call_count={db_tool_calls}, "
        f"pkm_own_log_lines {pkm_log_lines_before}->{pkm_log_lines_after}); "
        f"see the arm_hermes.py module docstring's toolset-restriction notes. text={text!r}"
    )

    if db_tool_calls is not None:
        assert db_tool_calls <= len(result.tool_log), (
            f"state.db tool_call_count ({db_tool_calls}) EXCEEDS the pkm-only tool log row "
            f"count ({len(result.tool_log)}) — evidence a NON-pkm tool call happened despite "
            "--toolsets pkm; the restriction claim does not hold for this hermes version/mode"
        )
