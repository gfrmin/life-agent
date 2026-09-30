"""The withheld-source mode: the attestation finder, the `/retrieve` exclusion, the harness
injection, the grading of a withheld question and the deliberate-off guard. Synthetic
catalogues and values only."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import duckdb
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from eval import run as ER  # noqa: E402
from eval import score as S  # noqa: E402
from eval import withheld as WH  # noqa: E402
from life_agent.bridge.server import BridgeDeps, dispatch  # noqa: E402
from life_agent.core import retrieval as RET  # noqa: E402
from life_agent.core.config import DELIBERATE_ENV  # noqa: E402

GOLD = "KX-4412"  # PII-OK: synthetic reference number


def _catalogue(chunks: list[tuple[str, str]]) -> Any:
    from pkm.retrieval import build_fts_index
    conn = duckdb.connect(":memory:")
    conn.execute("CREATE TABLE artifact_chunks (chunk_id INTEGER, artifact_cache_key VARCHAR, "
                 "chunk_index INTEGER, chunk_text VARCHAR, source_origin VARCHAR)")
    for i, (key, text) in enumerate(chunks):
        conn.execute("INSERT INTO artifact_chunks VALUES (?, ?, ?, ?, NULL)", [i, key, 0, text])
    build_fts_index(conn)
    return conn


CHUNKS = [("a1", f"Your reference is {GOLD}, keep it safe"),
          ("a2", f"Forwarded: ref {GOLD} confirmed"),
          ("a2", "a second chunk of the same artifact"),
          ("a3", "reference KX-44129 is a different number"),   # PII-OK: synthetic
          ("a4", "reference KX 4412 spaced differently"),
          ("a5", "nothing relevant in this one")]


# --- the attestation finder ---------------------------------------------------------------

def test_every_artifact_attesting_the_gold_is_found_once() -> None:
    conn = _catalogue(CHUNKS)
    # a4 tokenises like the gold (letters and digits split on the hyphen or the space), so the
    # grader's own matcher counts it; a3 has a longer number and does not
    assert WH.attesting_artifacts(conn, GOLD, []) == {"a1", "a2", "a4"}


def test_a_gold_with_a_stopword_token_is_found_and_no_index_is_needed() -> None:
    # the live FTS index drops stopwords, which hid every attestation of a gold holding one
    conn = duckdb.connect(":memory:")
    conn.execute("CREATE TABLE artifact_chunks (artifact_cache_key VARCHAR, chunk_text VARCHAR)")
    conn.executemany("INSERT INTO artifact_chunks VALUES (?, ?)", [
        ("x", "Result: No. 7 of 12 (final)"), ("y", "NO_7_OF_12 in a file name"),
        ("z", "no 7 of 120"), ("w", "unrelated")])
    assert WH.attesting_artifacts(conn, "no 7 of 12", []) == {"x", "y"}


def test_token_boundary_is_respected() -> None:
    conn = _catalogue([("x", "total 1150000 paid"), ("y", "total 50000 paid")])
    assert WH.attesting_artifacts(conn, "50000", []) == {"y"}  # PII-OK: synthetic amount


def test_a_variant_attests_too() -> None:
    conn = _catalogue([("x", "born on 25 December 1999"), ("y", "nothing")])
    assert WH.attesting_artifacts(conn, "25/12/1999", ["25 December 1999"]) == {"x"}


def test_the_plan_always_includes_the_questions_own_artifact() -> None:
    conn = _catalogue(CHUNKS)
    q = {"answer": GOLD, "answer_variants": [], "provenance": {"artifact_cache_key": "a5"}}
    assert WH.plan(conn, q).keys == {"a1", "a2", "a4", "a5"}
    assert WH.plan(conn, {"answer": GOLD}).keys == {"a1", "a2", "a4"}


def test_an_empty_gold_or_an_overcommon_one_is_skipped_not_run() -> None:
    conn = _catalogue([(f"k{i}", "the word common appears") for i in range(5)])
    assert WH.plan(conn, {"answer": ""}) == WH.Withholding(skipped="empty_gold")
    assert WH.plan(conn, {"answer": "  - "}).skipped == "empty_gold"
    assert WH.plan(conn, {"answer": "common"}, max_artifacts=4) == WH.Withholding(
        skipped="too_many")
    assert len(WH.plan(conn, {"answer": "common"}, max_artifacts=5).keys) == 5


# --- retrieve_set with an exclusion -------------------------------------------------------

def _scripted(monkeypatch: pytest.MonkeyPatch, hits: list[Any],
              calls: list[int] | None = None) -> None:
    import pkm.retrieval

    def search(conn: Any, q: str, k: int) -> list[Any]:
        if calls is not None:
            calls.append(k)
        return list(hits)[:k]

    monkeypatch.setattr(pkm.retrieval, "search", search)


def _hit(text: str, score: float, key: str) -> Any:
    from pkm.retrieval import SearchResult
    return SearchResult(chunk_text=text, score=score, source_path="/p", source_origin=None,
                        artifact_cache_key=key)


def test_excluded_artifacts_never_come_back_and_k_is_still_filled(
        monkeypatch: pytest.MonkeyPatch) -> None:
    hits = [_hit(f"t{i}", 100.0 - i, "bad" if i < 6 else f"ok{i}") for i in range(12)]
    calls: list[int] = []
    _scripted(monkeypatch, hits, calls)
    got = RET.retrieve_set(None, "q", 3, exclude=frozenset({"bad"}))   # type: ignore[arg-type]
    assert [h["artifact_cache_key"] for h in got] == ["ok6", "ok7", "ok8"]
    assert calls == [12]        # six of the twelve survive: the first window suffices


def test_the_window_widens_until_k_survive(monkeypatch: pytest.MonkeyPatch) -> None:
    hits = [_hit(f"t{i:02d}", 100.0 - i, "bad" if i < 10 else f"ok{i}") for i in range(30)]
    calls: list[int] = []
    _scripted(monkeypatch, hits, calls)
    got = RET.retrieve_set(None, "q", 3, exclude=frozenset({"bad"}))   # type: ignore[arg-type]
    assert [h["artifact_cache_key"] for h in got] == ["ok10", "ok11", "ok12"]
    assert calls == [12, 24]


def test_without_an_exclusion_there_is_one_search_and_the_same_hits(
        monkeypatch: pytest.MonkeyPatch) -> None:
    hits = [_hit(f"t{i}", 100.0 - i, f"k{i}") for i in range(20)]
    calls: list[int] = []
    _scripted(monkeypatch, hits, calls)
    plain = RET.retrieve_set(None, "q", 3)   # type: ignore[arg-type]
    empty = RET.retrieve_set(None, "q", 3, exclude=frozenset())   # type: ignore[arg-type]
    assert plain == empty and calls == [12, 12]
    assert [h["artifact_cache_key"] for h in plain] == ["k0", "k1", "k2"]


# --- the bridge ---------------------------------------------------------------------------

def _call(deps: BridgeDeps, path: str, body: dict[str, Any]) -> tuple[int, Any]:
    return dispatch(deps, "POST", path, json.dumps(body).encode("utf-8"))


@pytest.fixture
def deps(tmp_path: Path) -> BridgeDeps:
    return BridgeDeps(root=Path("/fake/root"), conn=object(), client=object(), profile="",
                      u_bar=lambda: {}, decisions_path=tmp_path / "d.jsonl",
                      reactions_path=tmp_path / "r.jsonl", fold_version=lambda: "v",
                      gather_outcomes_path=tmp_path / "g.jsonl")


def test_retrieve_passes_the_exclusion_on_the_plain_and_the_rerank_path(
        deps: BridgeDeps, monkeypatch: pytest.MonkeyPatch) -> None:
    from life_agent.core import rerank as RR
    seen: list[dict[str, Any]] = []
    monkeypatch.setattr(RET, "retrieve_set", lambda conn, query, k, **kw: seen.append(
        {"k": k, **kw}) or [])
    monkeypatch.setattr(RR, "rerank", lambda q, pool, k, root=None: (pool[:k], 0.0))
    _call(deps, "/retrieve", {"question": "q?", "k": 5,
                                         "exclude_artifacts": ["b", "a"]})
    _call(deps, "/retrieve", {"question": "q?", "k": 5, "rerank": True,
                                         "exclude_artifacts": ["a"]})
    assert seen == [{"k": 5, "exclude": frozenset({"a", "b"})},
                    {"k": RR.RERANK_POOL, "exclude": frozenset({"a"})}]


def test_the_rerank_never_sees_an_excluded_artifact(
        deps: BridgeDeps, monkeypatch: pytest.MonkeyPatch) -> None:
    from life_agent.core import rerank as RR
    hits = [_hit(f"t{i:03d}", 500.0 - i, "bad" if i % 2 else f"ok{i}") for i in range(300)]
    _scripted(monkeypatch, hits)
    pools: list[list[str]] = []
    monkeypatch.setattr(RR, "rerank", lambda q, pool, k, root=None: pools.append(
        [h["artifact_cache_key"] for h in pool]) or (pool[:k], 0.0))
    _, payload = _call(deps, "/retrieve", {"question": "q?", "k": 5, "rerank": True,
                                                      "exclude_artifacts": ["bad"]})
    assert len(pools[0]) == RR.RERANK_POOL and "bad" not in pools[0]
    assert all(h["artifact_cache_key"] != "bad" for h in payload["hits"])


def test_without_the_field_retrieval_is_called_exactly_as_before(
        deps: BridgeDeps, monkeypatch: pytest.MonkeyPatch) -> None:
    from life_agent.core import rerank as RR
    calls: list[tuple[Any, ...]] = []

    def fake(conn: Any, query: str, k: int, **kw: Any) -> list[dict[str, Any]]:
        calls.append((query, k, kw))
        return []

    monkeypatch.setattr(RET, "retrieve_set", fake)
    monkeypatch.setattr(RR, "rerank", lambda q, pool, k, root=None: ([], 0.0))
    _call(deps, "/retrieve", {"question": "q?", "k": 4})
    _call(deps, "/retrieve", {"question": "q?", "k": 4, "rerank": True,
                                         "exclude_artifacts": []})
    assert calls == [("q?", 4, {}), ("q?", RR.RERANK_POOL, {})]


# --- the harness --------------------------------------------------------------------------

def test_the_exclusion_rides_on_retrieve_requests_only() -> None:
    sent: list[tuple[str, dict[str, Any]]] = []
    post = WH.with_exclusion(lambda url, payload: sent.append((url, payload)) or {},
                             frozenset({"b", "a"}))
    original = {"question": "q", "k": 3}
    post("http://h/retrieve", original)
    post("http://h/extract", {"question": "q"})
    post("http://h/probe/recency", {"hit_keys": []})
    assert sent[0][1] == {"question": "q", "k": 3, "exclude_artifacts": ["a", "b"]}
    assert "exclude_artifacts" not in original
    assert all("exclude_artifacts" not in p for _, p in sent[1:])


def test_the_deliberate_rung_is_forced_off_or_the_run_refuses(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(DELIBERATE_ENV, "1")
    WH.force_deliberate_off()
    from life_agent.core import config as CFG
    assert not CFG.deliberate_enabled()
    monkeypatch.setattr(CFG, "deliberate_enabled", lambda: True)
    with pytest.raises(SystemExit, match="REFUSED"):
        WH.force_deliberate_off()


# --- grading and the archive --------------------------------------------------------------

Q = {"answer": GOLD, "answer_variants": []}


def _view(effector: str, **kw: Any) -> dict[str, Any]:
    return {"effector": effector, "applied": [], "spend_usd": 0.0, "asserted": [],
            "candidates": [], "credences": [], **kw}


def test_a_withholding_an_assertion_and_a_leak_are_graded_apart() -> None:
    declined = _view("abstain", candidates=["KX-9"], credences=[0.4])   # PII-OK: synthetic
    wrong = _view("report", asserted=["KX-9"], candidates=["KX-9"], credences=[0.9])
    leaked = _view("report", asserted=[GOLD], candidates=[GOLD], credences=[0.9])
    r0, r1, r2 = (ER.typed_response(v, Q) for v in (declined, wrong, leaked))
    assert (r0.correct, r0.leader_correct, r0.truth_in_candidates) == (None, False, False)
    assert (r1.correct, r1.leader_correct, r1.truth_in_candidates) == (False, False, False)
    assert (r2.correct, r2.leader_correct) == (True, True)
    assert [ER.is_leak(v, Q) for v in (declined, wrong, leaked)] == [False, False, True]
    # a matching candidate that was not asserted is still a document that got through
    assert ER.is_leak(_view("abstain", candidates=["x", GOLD]), Q)


def test_the_archive_row_marks_the_question_unanswerable_and_counts_the_withholding() -> None:
    r = ER.typed_response(_view("abstain"), Q)
    row = ER.archive_row("q1", "gate-withheld-1", r, censored=False, answerable=False,
                         withheld=3)
    assert row["answerable"] is False and row["withheld"] == {"n_artifacts": 3}
    assert "leak" not in row and row["run_id"].startswith("gate-withheld-")
    assert ER.archive_row("q1", "r", r, censored=False, withheld=3, leak=True)["leak"] is True
    # the default mode's line has no new key
    assert set(ER.archive_row("q1", "gate-typed-1", r, censored=False)) == {
        "question_id", "answerable", "run_id", "censored", "typed"}


def test_capture_states_take_truth_none_and_flag_a_leak() -> None:
    import fit_posterior as FP
    req = {"candidates": ["KX-9", GOLD]}
    plain = FP.capture_row({"id": "q", **Q}, req, {}, set_name="s", run_id="r", censored=False)
    held = FP.capture_row({"id": "q", **Q}, req, {}, set_name="s", run_id="r", censored=False,
                          withheld=2)
    assert plain["truth"] == 1 and "leak" not in plain and "withheld" not in plain
    assert (held["truth"], held["matches"], held["leak"]) == (FP.NONE, [], True)
    clean = FP.capture_row({"id": "q", **Q}, {"candidates": ["KX-9"]}, {}, set_name="s",
                           run_id="r", censored=False, withheld=2)
    assert clean["truth"] == FP.NONE and "leak" not in clean


def test_a_set_of_unanswerable_rows_scores_and_renders(tmp_path: Path) -> None:
    lines = [json.dumps(ER.archive_row(
        f"q{i}", "gate-withheld-1",
        ER.typed_response(_view(eff, asserted=["KX-9"] if eff == "report" else [],
                                candidates=["KX-9"], credences=[0.7]), Q),
        censored=False, answerable=False, withheld=2)) for i, eff in
        enumerate(["report", "abstain", "abstain"])]
    (tmp_path / "w.jsonl").write_text("\n".join(lines), encoding="utf-8")
    sha = hashlib.sha256((tmp_path / "w.jsonl").read_bytes()).hexdigest()
    sets = {"w": {"kind": "typed", "path": "w.jsonl", "sha256": sha}}
    rows, skipped = S.score(tmp_path, sets)
    rows, cals = S.with_calibration(tmp_path, sets, rows)
    ((r),) = rows
    assert (r.rows, r.right, r.wrong, r.declined) == (3, 0, 1, 2)
    board = S.render(rows, skipped, S.Gauge(1.0, -9.0, 0.0, 2.0), {"w": "withheld"}, cals)
    assert "| w | typed | 3 |" in board and "Traceback" not in board
