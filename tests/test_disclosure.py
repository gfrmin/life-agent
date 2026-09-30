"""The disclosure record (core/disclosure.py) — what left the machine, to which model.

Hermetic: every model is a fake; nothing touches $LIFE_AGENT_KB (rows go to tmp_path).
Synthetic values throughout.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from life_agent.core import decisions as DEC
from life_agent.core import deliberate as DL
from life_agent.core import disclosure as DISC
from life_agent.core import joint_extract as JE
from life_agent.core import lookup as LK
from life_agent.core import rerank as RR
from life_agent.core.llm import LLMResult
from pkm.transform import ModelResponse

Q = "what is my synthetic thing?"


@pytest.fixture
def root(tmp_path: Path) -> Path:
    (tmp_path / "cache").mkdir()
    (tmp_path / "logs").mkdir()
    return tmp_path


@pytest.fixture
def log(tmp_path: Path) -> Path:
    return tmp_path / "calibration" / "disclosures.jsonl"


def _keys(n: int) -> list[str]:
    return [f"{i:064x}" for i in range(n)]


def _hits(*texts: str) -> list[dict[str, Any]]:
    return [{"artifact_cache_key": k, "chunk_text": t, "origin": "/data/doc.pdf",
             "score": 1.0} for k, t in zip(_keys(len(texts)), texts, strict=True)]


# --- the row: construction, round trip, append-only --------------------------------------

def test_a_row_round_trips_through_the_log(log: Path) -> None:
    d = DISC.make("joint", question=Q, model="m-1", artifact_cache_keys=["b", "a", "b"],
                  n_chunks=2, n_chars=10, outcome="ok", run_id="r-1")
    DISC.record(log, d)
    assert DISC.read(log) == [d]
    assert d.artifact_cache_keys == ("b", "a")          # unique, first-seen order
    assert d.question_id == DEC.question_id(Q)
    raw = json.loads(log.read_text())
    assert raw["format_version"] == 1 and raw["artifact_cache_keys"] == ["b", "a"]
    assert Q not in log.read_text()                     # keys only, never the question


def test_unknown_path_or_outcome_is_refused() -> None:
    with pytest.raises(ValueError, match="path"):
        DISC.make("email", question=Q, model=None, artifact_cache_keys=[], n_chunks=0,
                  n_chars=0, outcome="ok")
    with pytest.raises(ValueError, match="outcome"):
        DISC.make("joint", question=Q, model=None, artifact_cache_keys=[], n_chunks=0,
                  n_chars=0, outcome="maybe")


def test_a_missing_log_reads_as_nothing_disclosed(log: Path) -> None:
    assert DISC.read(log) == []


def test_the_log_is_opened_in_append_mode_only(log: Path,
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    modes: list[str] = []
    real_open = Path.open

    def spy(self: Path, mode: str = "r", *a: Any, **k: Any) -> Any:
        if self == log:
            modes.append(mode)
        return real_open(self, mode, *a, **k)

    monkeypatch.setattr(Path, "open", spy)
    for i in range(2):
        DISC.record(log, DISC.make("rerank", question=Q, model="m", artifact_cache_keys=[str(i)],
                                   n_chunks=1, n_chars=1, outcome="ok"))
    assert modes == ["a", "a"]                          # writes only ever append
    assert len(DISC.read(log)) == 2                     # the second append kept the first


def test_the_sink_fills_a_missing_run_id_and_no_log_gives_no_sink(log: Path) -> None:
    sink = DISC.to_log(log, "run-7")
    assert sink is not None
    sink(DISC.make("joint", question=Q, model="m", artifact_cache_keys=[], n_chunks=0,
                   n_chars=0, outcome="ok"))
    assert DISC.read(log)[0].run_id == "run-7"
    assert DISC.to_log(None, "run-7") is None


# --- per-chunk extraction ----------------------------------------------------------------

class _Client:
    engine_version = "fake-1"

    def __init__(self, fail: bool = False) -> None:
        self.fail, self.calls = fail, 0

    def complete(self, prompt: str, schema: dict[str, Any]) -> ModelResponse:
        self.calls += 1
        if self.fail:
            raise RuntimeError("api down")
        return ModelResponse(
            raw_text=json.dumps({"found": True, "value": "SYN-1", "quote": "SYN-1"}),
            input_tokens=1, output_tokens=1, latency_ms=1, cost_usd=0.0)


def _collect() -> tuple[list[DISC.Disclosure], DISC.Sink]:
    rows: list[DISC.Disclosure] = []
    return rows, rows.append


def test_extract_writes_one_row_per_model_call_and_none_on_a_cache_hit(root: Path) -> None:
    rows, sink = _collect()
    hits = _hits("ref SYN-1 here", "other text")
    client = _Client()
    LK.observe_hits(root, Q, hits, client=client, disclose=sink)
    assert client.calls == 2 and len(rows) == 2
    assert [r.artifact_cache_keys for r in rows] == [(k,) for k in _keys(2)]
    assert [r.n_chars for r in rows] == [len("ref SYN-1 here"), len("other text")]
    assert all(r.path == "extract" and r.outcome == "ok" and r.n_chunks == 1
               and r.model == LK.LOOKUP_MODEL for r in rows)
    LK.observe_hits(root, Q, hits, client=client, disclose=sink)
    assert client.calls == 2 and len(rows) == 2          # warm replay: nothing crossed


def test_a_failing_extraction_leaves_a_failed_row_and_raises(root: Path) -> None:
    rows, sink = _collect()
    with pytest.raises(RuntimeError):
        LK.observe_hits(root, Q, _hits("ref SYN-1"), client=_Client(fail=True), disclose=sink)
    assert [(r.path, r.outcome, r.artifact_cache_keys) for r in rows] == [
        ("extract", "failed", (_keys(1)[0],))]


# --- the joint re-read -------------------------------------------------------------------

def _joint(ok: bool = True) -> JE.CompleteFn:
    def complete(system: str, user: str, model: str, max_tokens: int) -> LLMResult:
        if not ok:
            raise RuntimeError("api down")
        return LLMResult('{"value": "SYN-1", "confidence": 0.9, "as_of": null}', 9, 9, 0.0,
                         served_model=model)
    return complete


def test_joint_writes_one_row_with_the_pool_keys_and_none_on_replay(root: Path) -> None:
    rows, sink = _collect()
    hits = _hits("alpha", "beta")
    hits[1]["artifact_cache_key"] = hits[0]["artifact_cache_key"]   # one artifact, two chunks
    JE.extract_joint(root, Q, hits, model="claude-x-20260101", complete=_joint(),
                     disclose=sink)
    assert len(rows) == 1
    r = rows[0]
    assert (r.path, r.outcome, r.model) == ("joint", "ok", "claude-x-20260101")
    assert r.artifact_cache_keys == (_keys(1)[0],) and r.n_chunks == 2
    assert r.n_chars == len("alpha") + len("beta")
    JE.extract_joint(root, Q, hits, model="claude-x-20260101", complete=_joint(),
                     disclose=sink)
    assert len(rows) == 1


def test_a_failing_joint_leaves_a_failed_row_and_no_answer(root: Path) -> None:
    rows, sink = _collect()
    with pytest.raises(RuntimeError):
        JE.extract_joint(root, Q, _hits("alpha"), model="claude-x-20260101",
                         complete=_joint(ok=False), disclose=sink)
    assert [(r.path, r.outcome, r.artifact_cache_keys) for r in rows] == [
        ("joint", "failed", (_keys(1)[0],))]


# --- rerank ------------------------------------------------------------------------------

def _scripted(monkeypatch: pytest.MonkeyPatch, *, fail: bool = False) -> None:
    def complete(system: str, user: str, **kw: Any) -> LLMResult:
        if fail:
            raise RuntimeError("api down")
        return LLMResult("[2, 1]", 10, 2, 0.0, served_model=RR.RERANK_MODEL)
    monkeypatch.setattr(RR, "anthropic_complete", complete)


def test_rerank_writes_one_row_with_the_pool_and_none_on_replay(
        root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _scripted(monkeypatch)
    rows, sink = _collect()
    pool = _hits("one", "two", "three")
    RR.rerank(Q, pool, 2, root=root, disclose=sink)
    assert len(rows) == 1
    r = rows[0]
    assert (r.path, r.outcome, r.model) == ("rerank", "ok", RR.RERANK_MODEL)
    assert r.artifact_cache_keys == tuple(_keys(3)) and r.n_chunks == 3
    assert r.n_chars == len("one") + len("two") + len("three")
    RR.rerank(Q, pool, 2, root=root, disclose=sink)
    assert len(rows) == 1
    RR.rerank(Q, pool[:2], 2, root=root, disclose=sink)   # pool <= k: no call at all
    assert len(rows) == 1


def test_a_failing_rerank_leaves_a_failed_row_and_the_lexical_head(
        root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _scripted(monkeypatch, fail=True)
    rows, sink = _collect()
    pool = _hits("one", "two", "three")
    hits, cost = RR.rerank(Q, pool, 2, root=root, disclose=sink)
    assert hits == pool[:2] and cost == 0.0
    assert [(r.path, r.outcome) for r in rows] == [("rerank", "failed")]
    assert rows[0].artifact_cache_keys == tuple(_keys(3))


# --- the deliberate rung -----------------------------------------------------------------

def _search_row(*chunks: tuple[int, str, str, str]) -> dict[str, Any]:
    """A pkm tool-log ``search`` row: (chunk_id, artifact key, snippet shown, full text)."""
    return {"ts": "t", "tool": "search", "args": {"query": "q", "k": 10},
            "n_results": len(chunks),
            "results": [{"chunk_id": c, "artifact_cache_key": a, "source_path": "/d",
                         "score": 1.0, "snippet_shown": s, "chunk_text_full": f}
                        for c, a, s, f in chunks]}


def _extract_row(chunk_id: int, artifact: str, *texts: str) -> dict[str, Any]:
    """An ``extract`` row: the chunk, then its neighbours (same artifact)."""
    return {"ts": "t", "tool": "extract", "args": {"chunk_id": chunk_id, "neighbors": 1},
            "n_results": len(texts),
            "results": [{"chunk_id": chunk_id + i, "artifact_cache_key": artifact,
                         "source_path": "/d", "score": None, "snippet_shown": None,
                         "chunk_text_full": t} for i, t in enumerate(texts)]}


def test_the_tool_log_reduces_to_the_artifacts_it_touched() -> None:
    rows = [
        _search_row((1, "a", "snip1", "snip1 full text"), (5, "b", "snip2", "snip2 full")),
        _extract_row(1, "a", "snip1 full text", "neighbour"),     # chunk 1 again, chunk 2 new
        {"ts": "t", "tool": "search", "args": {}, "n_results": 0, "results": [],
         "error": "corpus locked"},
        {"tool": "search"},                                        # no results key at all
    ]
    reach = DL.tool_log_reach(rows)
    assert reach.artifact_cache_keys == ("a", "b")
    # chunks 1 and 5 from the search, chunk 2 (the extract's neighbour): three by id
    assert reach.n_chunks == 3
    # each distinct chunk counted once, at the most of it any call showed
    assert reach.n_chars == len("snip1 full text") + len("snip2") + len("neighbour")


def test_an_empty_tool_log_touched_nothing() -> None:
    reach = DL.tool_log_reach([])
    assert (reach.artifact_cache_keys, reach.n_chunks, reach.n_chars) == ((), 0, 0)


def _cli(text: str) -> str:
    return json.dumps({"result": text, "total_cost_usd": 0.1, "usage": {},
                       "session_id": "s", "is_error": False, "subtype": "success"})


def _cfg(tmp_path: Path) -> DL.DeliberateConfig:
    return DL.DeliberateConfig(claude_bin="claude", scratch_dir=tmp_path / "scratch",
                               pkm_config="/dev/null/pkm.yaml")


def _write_log(cmd: list[str], rows: list[dict[str, Any]]) -> None:
    cfg = json.loads(Path(cmd[cmd.index("--mcp-config") + 1]).read_text())
    args = cfg["mcpServers"]["pkm"]["args"]
    Path(args[args.index("--tool-log") + 1]).write_text(
        "".join(json.dumps(r) + "\n" for r in rows))


def test_a_successful_rung_writes_one_row_naming_what_it_touched(tmp_path: Path) -> None:
    rows, sink = _collect()

    def runner(cmd, env, cwd, timeout_s):  # type: ignore[no-untyped-def]
        _write_log(cmd, [_search_row((1, "a", "s", "s full"), (2, "b", "t", "t full"))])
        return _cli("SYN-1 [d]\nANSWER: SYN-1\nCREDENCE: 0.8"), "", 0, False

    r = DL.answer(Q, _cfg(tmp_path), run_once=runner, disclose=sink)
    assert r.status == "ok" and r.disclosed == 2
    assert len(rows) == 1
    d = rows[0]
    assert (d.path, d.outcome, d.model) == ("deliberate", "ok", "claude-opus-4-8")
    assert d.artifact_cache_keys == ("a", "b") and d.n_chunks == 2


def test_a_failed_rung_leaves_a_row_and_no_answer(tmp_path: Path) -> None:
    rows, sink = _collect()

    def runner(cmd, env, cwd, timeout_s):  # type: ignore[no-untyped-def]
        _write_log(cmd, [_search_row((1, "a", "s", "s full"))])
        return "", "boom", 1, False

    r = DL.answer(Q, _cfg(tmp_path), run_once=runner, disclose=sink)
    assert r.status == "error" and r.value is None and r.text == ""
    # two attempts, each a call that reached the corpus and each recorded
    assert [(d.outcome, d.artifact_cache_keys) for d in rows] == [
        ("failed", ("a",)), ("failed", ("a",))]
    assert r.disclosed == 1


def test_a_timed_out_rung_still_records_what_it_read(tmp_path: Path) -> None:
    rows, sink = _collect()

    def runner(cmd, env, cwd, timeout_s):  # type: ignore[no-untyped-def]
        _write_log(cmd, [_search_row((1, "a", "s", "s full"))])
        return "", "", None, True

    r = DL.answer(Q, _cfg(tmp_path), run_once=runner, disclose=sink)
    assert r.status == "timeout"
    assert [(d.outcome, d.artifact_cache_keys) for d in rows] == [("failed", ("a",))]


def test_a_refused_rung_with_no_tool_calls_records_an_empty_failed_row(
        tmp_path: Path) -> None:
    rows, sink = _collect()

    def runner(cmd, env, cwd, timeout_s):  # type: ignore[no-untyped-def]
        return _cli("NOT_IN_CORPUS: tools unavailable"), "", 0, False   # a blind decline

    r = DL.answer(Q, _cfg(tmp_path), run_once=runner, disclose=sink)
    assert r.status == "error"
    assert [(d.outcome, d.artifact_cache_keys, d.n_chunks) for d in rows] == [
        ("failed", (), 0), ("failed", (), 0)]


def test_a_runner_that_raises_still_leaves_a_failed_row(tmp_path: Path) -> None:
    rows, sink = _collect()

    def runner(cmd, env, cwd, timeout_s):  # type: ignore[no-untyped-def]
        _write_log(cmd, [_search_row((1, "a", "s", "s full"))])
        raise OSError("spawn failed")

    r = DL.answer(Q, _cfg(tmp_path), run_once=runner, disclose=sink)
    assert r.status == "error"
    assert [(d.outcome, d.artifact_cache_keys) for d in rows] == [("failed", ("a",))]


def test_the_count_survives_the_replay_record(tmp_path: Path, root: Path) -> None:
    from life_agent.core import derivations as D

    def runner(cmd, env, cwd, timeout_s):  # type: ignore[no-untyped-def]
        _write_log(cmd, [_search_row((1, "a", "s", "s full"))])
        return _cli("SYN-1 [d]\nANSWER: SYN-1\nCREDENCE: 0.8"), "", 0, False

    r = DL.answer(Q, _cfg(tmp_path), run_once=runner)
    key = D.deliberate_key(Q, "digest", model=r.model, prompt_template=DL.PROMPT_DELIB_V2,
                           max_turns=40)
    DL.record_answer(root, key, r)
    cached = D.lookup(root, key.cache_key)
    assert cached is not None and json.loads(cached)["disclosed"] == 1
