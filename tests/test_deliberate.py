"""The deliberative answer edge (core/deliberate.py) — the promoted A1b arm.

The edge is a declared monolithic-class instrument (bayesian-foundations §2): its
self-reported CREDENCE line is an observable *signal*, parsed off the answer text and
never folded as reliability directly (§1 M3). Hermetic: the claude CLI is injected as a
runner fake; no subprocess, no network.

Run: uv run --project . python -m pytest tests/test_deliberate.py
"""
from __future__ import annotations

from pathlib import Path

from life_agent.core import deliberate as DL
from life_agent.core import derivations as D

# --- parse_credence: the CREDENCE line is a signal, stripped from the answer text -------

def test_parse_credence_strips_wellformed_final_line() -> None:
    text, credence = DL.parse_credence("NIS 4,200 [lease.pdf]\nCREDENCE: 0.85")
    assert text == "NIS 4,200 [lease.pdf]"
    assert credence == 0.85


def test_parse_credence_absent_line_returns_none() -> None:
    text, credence = DL.parse_credence("NIS 4,200 [lease.pdf]")
    assert text == "NIS 4,200 [lease.pdf]"
    assert credence is None


def test_parse_credence_out_of_range_strips_but_yields_none() -> None:
    # A recognisable credence attempt is stripped (never rendered to the owner), but an
    # out-of-range value is a protocol violation — no signal, not a clamp.
    text, credence = DL.parse_credence("42 [doc.pdf]\nCREDENCE: 1.7")
    assert text == "42 [doc.pdf]"
    assert credence is None


def test_parse_credence_non_numeric_strips_but_yields_none() -> None:
    text, credence = DL.parse_credence("42 [doc.pdf]\nCREDENCE: high")
    assert text == "42 [doc.pdf]"
    assert credence is None


def test_parse_credence_only_matches_the_final_line() -> None:
    # A mid-text mention is answer content, not the protocol line.
    raw = "the form says CREDENCE: 0.5 verbatim [scan.pdf]\nCREDENCE: 0.9"
    text, credence = DL.parse_credence(raw)
    assert text == "the form says CREDENCE: 0.5 verbatim [scan.pdf]"
    assert credence == 0.9


# --- detect_decline: the edge's own NOT_IN_CORPUS contract ------------------------------

def test_decline_on_not_in_corpus_line() -> None:
    assert DL.detect_decline("NOT_IN_CORPUS: no salary document after 2024")


def test_no_decline_on_ordinary_answer() -> None:
    assert not DL.detect_decline("NIS 4,200 [lease.pdf]")


def test_decline_detected_on_any_line() -> None:
    assert DL.detect_decline("searched 4 ways\nNOT_IN_CORPUS: nothing decides it")


# --- the prompt contract (V2 = V1's surface contract + the credence line) ---------------

def test_prompt_v2_keeps_the_v1_surface_contract_and_adds_credence() -> None:
    assert "{question}" in DL.PROMPT_DELIB_V2
    assert "NOT_IN_CORPUS: " in DL.PROMPT_DELIB_V2
    assert "CREDENCE:" in DL.PROMPT_DELIB_V2


# --- the pre-call stage key (system-design §3: keyed before any model call) -------------

def test_deliberate_key_is_stable_and_input_sensitive() -> None:
    kw = dict(model="claude-opus-4-8", prompt_template=DL.PROMPT_DELIB_V2, max_turns=40)
    k1 = D.deliberate_key("what is my rent?", "corpus-digest-a", **kw)
    k2 = D.deliberate_key("what is my rent?", "corpus-digest-a", **kw)
    assert k1.cache_key == k2.cache_key
    assert k1.content_type == D.CONTENT_TYPE_DELIBERATE_ANSWER
    for other in (
        D.deliberate_key("what is my rent now?", "corpus-digest-a", **kw),
        D.deliberate_key("what is my rent?", "corpus-digest-b", **kw),
        D.deliberate_key("what is my rent?", "corpus-digest-a",
                         model="claude-sonnet-4-6",
                         prompt_template=DL.PROMPT_DELIB_V2, max_turns=40),
    ):
        assert other.cache_key != k1.cache_key


def test_deliberate_key_never_enters_retrieval() -> None:
    # SPEC §18.9 gate: a derived answer must not be chunk-eligible.
    from pkm.extract import CHUNKABLE_CONTENT_TYPES

    assert D.CONTENT_TYPE_DELIBERATE_ANSWER not in CHUNKABLE_CONTENT_TYPES


# --- answer(): the claude CLI orchestration, runner injected (hermetic) ------------------

def _cli_json(result_text: str, *, cost: float = 0.42, is_error: bool = False) -> str:
    import json

    return json.dumps({
        "result": result_text, "total_cost_usd": cost, "num_turns": 7,
        "usage": {"input_tokens": 1000, "output_tokens": 50,
                  "cache_read_input_tokens": 200, "cache_creation_input_tokens": 10},
        "session_id": "sess-1", "duration_ms": 2300,
        "is_error": is_error, "subtype": "success",
    })


def _cfg(tmp_path: Path) -> DL.DeliberateConfig:
    return DL.DeliberateConfig(claude_bin="claude", scratch_dir=tmp_path / "scratch",
                               pkm_config="/dev/null/pkm.yaml")


def test_answer_success_parses_text_credence_and_cost(tmp_path: Path) -> None:
    def runner(cmd, env, cwd, timeout_s):  # type: ignore[no-untyped-def]
        return _cli_json("NIS 4,200 [lease.pdf]\nCREDENCE: 0.85"), "", 0, False

    r = DL.answer("what is my rent?", _cfg(tmp_path), run_once=runner)
    assert r.status == "ok"
    assert r.text == "NIS 4,200 [lease.pdf]"
    assert r.credence == 0.85
    assert not r.declined
    assert r.cost_usd == 0.42
    assert r.session_id == "sess-1"
    assert r.latency_s >= 0.0
    assert r.model == "claude-opus-4-8"


def test_answer_counts_tool_log_rows(tmp_path: Path) -> None:
    import json

    def runner(cmd, env, cwd, timeout_s):  # type: ignore[no-untyped-def]
        # The real pkm server writes the tool log; the fake does the same, finding the
        # path exactly where the server would: in the mcp config the cmd names.
        mcp_config = json.loads(
            Path(cmd[cmd.index("--mcp-config") + 1]).read_text())
        args = mcp_config["mcpServers"]["pkm"]["args"]
        tool_log = Path(args[args.index("--tool-log") + 1])
        rows = [{"tool": "search"}, {"tool": "search"}, {"tool": "extract"}]
        tool_log.write_text("".join(json.dumps(x) + "\n" for x in rows))
        return _cli_json("42 [doc.pdf]\nCREDENCE: 0.6"), "", 0, False

    r = DL.answer("q", _cfg(tmp_path), run_once=runner)
    assert r.tool_calls == 3
    assert r.gather_rounds == 2


def test_answer_retries_once_then_succeeds(tmp_path: Path) -> None:
    calls: list[int] = []

    def runner(cmd, env, cwd, timeout_s):  # type: ignore[no-untyped-def]
        calls.append(1)
        if len(calls) == 1:
            return "", "boom", 1, False
        return _cli_json("42 [doc.pdf]\nCREDENCE: 0.7"), "", 0, False

    r = DL.answer("q", _cfg(tmp_path), run_once=runner)
    assert r.status == "ok"
    assert len(calls) == 2


def test_answer_error_after_two_failures(tmp_path: Path) -> None:
    def runner(cmd, env, cwd, timeout_s):  # type: ignore[no-untyped-def]
        return "not json", "", 1, False

    r = DL.answer("q", _cfg(tmp_path), run_once=runner)
    assert r.status == "error"
    assert r.text == ""
    assert r.credence is None


def test_answer_timeout_does_not_retry(tmp_path: Path) -> None:
    calls: list[int] = []

    def runner(cmd, env, cwd, timeout_s):  # type: ignore[no-untyped-def]
        calls.append(1)
        return "", "", None, True

    r = DL.answer("q", _cfg(tmp_path), run_once=runner)
    assert r.status == "timeout"
    assert len(calls) == 1


def test_answer_decline_has_no_credence(tmp_path: Path) -> None:
    def runner(cmd, env, cwd, timeout_s):  # type: ignore[no-untyped-def]
        return _cli_json("NOT_IN_CORPUS: no document decides it"), "", 0, False

    r = DL.answer("q", _cfg(tmp_path), run_once=runner)
    assert r.declined
    assert r.credence is None
    assert r.text.startswith("NOT_IN_CORPUS:")


def test_answer_pins_permission_mode_and_allowed_tools(tmp_path: Path) -> None:
    # PR-33 CRITICAL carried over: the ambient machine config must never shape the edge.
    seen: dict = {}

    def runner(cmd, env, cwd, timeout_s):  # type: ignore[no-untyped-def]
        seen["cmd"] = cmd
        seen["env"] = env
        return _cli_json("42 [d.pdf]\nCREDENCE: 0.9"), "", 0, False

    DL.answer("q", _cfg(tmp_path), run_once=runner)
    cmd = seen["cmd"]
    assert cmd[cmd.index("--permission-mode") + 1] == "default"
    assert "mcp__pkm__search" in cmd[cmd.index("--allowedTools") + 1]
    assert set(seen["env"]) <= {"HOME", "PATH"}


# --- record_answer: the §18.9 on-ledger artifact ------------------------------------------

def _ok_result(tmp_path: Path, question: str = "what is my rent?") -> DL.DeliberateResult:
    def runner(cmd, env, cwd, timeout_s):  # type: ignore[no-untyped-def]
        return _cli_json("NIS 4,200 [lease.pdf]\nCREDENCE: 0.85"), "", 0, False

    return DL.answer(question, _cfg(tmp_path), run_once=runner)


def test_record_answer_writes_file_first_and_is_write_once(tmp_path: Path) -> None:
    import json

    r = _ok_result(tmp_path)
    key = D.deliberate_key(r.question, "digest-a", model=r.model,
                           prompt_template=DL.PROMPT_DELIB_V2, max_turns=40)
    assert DL.record_answer(tmp_path, key, r) is True
    content = json.loads(D.lookup(tmp_path, key.cache_key).decode("utf-8"))
    assert content["question"] == r.question
    assert content["text"] == "NIS 4,200 [lease.pdf]"
    assert content["credence"] == 0.85
    assert content["declined"] is False
    assert DL.record_answer(tmp_path, key, r) is False  # write-once


# --- calibrated_credence: the signal→posterior map (Δ1 — never the raw self-report) ------

def test_calibrated_credence_cold_start_is_pessimistic(tmp_path: Path) -> None:
    # An unproven edge cannot clear the assertion floor on self-report alone (§16
    # safe-before-calibrated): Beta(1,3) cold start holds every bin at 0.25.
    r = _ok_result(tmp_path)  # self-reported 0.85
    assert DL.calibrated_credence(r, {}) == 0.25


def test_calibrated_credence_rises_with_graded_outcomes(tmp_path: Path) -> None:
    from life_agent.core import calibration as CAL

    r = _ok_result(tmp_path)  # self-reported 0.85
    curves = {DL.instrument(r.model): CAL.fit_reliability_curve(
        [CAL.Outcome(0.85, True)] * 40)}
    assert DL.calibrated_credence(r, curves) > 0.85


def test_calibrated_credence_without_signal_takes_the_lowest_bin(tmp_path: Path) -> None:
    from life_agent.core import calibration as CAL

    def runner(cmd, env, cwd, timeout_s):  # type: ignore[no-untyped-def]
        return _cli_json("42 [doc.pdf]"), "", 0, False  # protocol violation: no CREDENCE

    r = DL.answer("q", _cfg(tmp_path), run_once=runner)
    curves = {DL.instrument(r.model): CAL.fit_reliability_curve(
        [CAL.Outcome(0.9, True)] * 40)}
    # no signal ⇒ the curve's most pessimistic bin, never the fitted high bin
    assert DL.calibrated_credence(r, curves) == curves[DL.instrument(r.model)].calibrate(0.0)


def test_record_answer_refuses_failures(tmp_path: Path) -> None:
    import pytest

    def runner(cmd, env, cwd, timeout_s):  # type: ignore[no-untyped-def]
        return "not json", "", 1, False

    bad = DL.answer("q", DL.DeliberateConfig(
        claude_bin="claude", scratch_dir=tmp_path / "s", pkm_config="x"),
        run_once=runner)
    key = D.deliberate_key("q", "digest-a", model=bad.model,
                           prompt_template=DL.PROMPT_DELIB_V2, max_turns=40)
    with pytest.raises(ValueError, match="status"):
        DL.record_answer(tmp_path, key, bad)
