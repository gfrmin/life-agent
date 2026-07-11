"""Unit tests for the fair-fight runner (``scripts/fairfight/run_fairfight.py``).

Hermetic: a tmp KB root (``LIFE_AGENT_KB`` monkeypatched — the kb-root seam
``run_eval._kb_root()`` reads fresh every call), every arm + the judge + the DuckDB
connection injected via ``run()``'s own seams (``arm_impls``/``judge_impl``/
``conn_factory``) — no real ``ask.py`` call, no real duckdb file, no real LLM call, no
real hermes subprocess anywhere in this file. Synthetic fixtures only (IDs shaped to
fail the Israeli-ID checksum, same convention as ``tests/test_fairfight_grading.py``).

Run from the repo root:
    uv run --project . python -m pytest ./tests/test_fairfight_runner.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from fairfight import arm_baseline as AB
from fairfight import arm_hermes as AH
from fairfight import grading as G
from fairfight import run_fairfight as RF

import life_agent.core.config as LCFG
from life_agent.core.llm import LLMResult
from life_agent.fairfight import records as REC

# --- fixtures / small builders --------------------------------------------------------


def _q(id_: str = "q-001", answer: str = "P123", question: str | None = None) -> dict[str, Any]:
    return {"id": id_, "question": question or f"what is the value for {id_}?", "answer": answer}


def _write_questions(kb_root: Path, questions: list[dict[str, Any]]) -> Path:
    path = kb_root / "eval" / "questions.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"questions": questions}), encoding="utf-8")
    return path


def _write_pkm_config(tmp_path: Path) -> Path:
    cfg = tmp_path / "pkm-config.yaml"
    cfg.write_text(yaml.safe_dump({"root_dir": str(tmp_path / "corpus")}), encoding="utf-8")
    return cfg


class _FakeFetchResult:
    def __init__(self, row: tuple[Any, ...]) -> None:
        self._row = row

    def fetchone(self) -> tuple[Any, ...]:
        return self._row


class _FakeConn:
    """A conn double good enough for the runner's own use (corpus-fingerprint queries);
    ``grading._answer_in_corpus`` is monkeypatched separately (autouse fixture below) so
    this never needs to support real FTS search."""

    def __init__(self) -> None:
        self.closed = False
        self.executed: list[str] = []

    def execute(self, sql: str, *a: object, **k: object) -> _FakeFetchResult:
        self.executed.append(sql)
        return _FakeFetchResult((3,))

    def close(self) -> None:
        self.closed = True


def _args(tmp_path: Path, **overrides: Any) -> argparse.Namespace:
    base: dict[str, Any] = dict(
        config=str(_write_pkm_config(tmp_path)), k=8, arms="inprocess",
        competitor_model="claude-sonnet-4-6", competitor_provider="anthropic",
        competitor_base_url=None, hermes_bin="/fake/hermes", timeout_s=300, limit=None,
        no_judge=False, run_id="ff-test",
    )
    base.update(overrides)
    return argparse.Namespace(**base)


def _raw(**overrides: Any) -> AB.RawAnswer:
    base: dict[str, Any] = dict(
        question_id="q-001", text="P123 [1]", declined=False, latency_s=0.5,
        llm_calls=[], decision_view=None, lineage_keys=(), status="ok", notes="",
        effort={}, cards=({"n": 1, "text": "the value for q-001 is P123", "origin": "a.txt"},),
    )
    base.update(overrides)
    return AB.RawAnswer(**base)


def _vector_for_summary(**overrides: Any) -> REC.OutcomeVector:
    """A full, validated ``OutcomeVector`` for ``RF._summarize_arm``-level tests
    (final-review CRITICAL-2) — every field defaulted, override only what a test cares
    about."""
    base: dict[str, Any] = dict(
        format_version=REC.FORMAT_VERSION, run_id="run-test", arm="inprocess",
        question_id="q-001", answerable=True,
        faithfulness=None, completeness=None, citation_fidelity=None,
        bucket="CORRECT", cause=None, asserted=True, asserted_correct=True,
        asserted_distractor=False, hallucinated=None, declined=False,
        correct_abstention=False, over_abstention=False,
        gold_in_topk=True, gold_in_corpus=True, gold_in_candidates=True,
        distractor_in_topk=False, n_retrieved=5,
        probability=None, p_none=None, p_none_correct=None, brier=None,
        cost_usd=0.01, cost_status="measured", in_tokens=100, out_tokens=50,
        cache_read_tokens=0, cache_write_tokens=0, latency_s=1.0,
        model_tier_mix={},
        gather_rounds=None, asks_issued=0, tool_calls=None, think_ticks=None,
        answer_sha256="a" * 64, answer_chars=10, lineage_keys=(), status="ok", notes="",
    )
    base.update(overrides)
    return REC.OutcomeVector(**base)


def _lookup_view(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = dict(
        family="lookup", construct="a number", action="report", asserted=True,
        scoped=False, scoped_value=None, as_of=None, asserted_values=["P123"],
        candidates=["P123"], credences=[0.9], p_none=0.05, n_hits=3, n_indeterminate=0,
        observations=[],
    )
    base.update(overrides)
    return base


def _fake_judge(faithfulness: int = 3, completeness: int = 3, citation_fidelity: int = 3
                ) -> Any:
    def _impl(q: dict, text: str, sources: list, *, n: int = 3) -> dict:
        return {"faithfulness": faithfulness, "completeness": completeness,
                "citation_fidelity": citation_fidelity, "_served": ["fake-judge"]}
    return _impl


def _snapshot(root: Path) -> set[Path]:
    return set(root.rglob("*")) if root.exists() else set()


@pytest.fixture(autouse=True)
def _no_real_corpus_membership_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """No test's fake conn supports real FTS search — grading.grade_channels only calls
    this when gold_in_topk is False and the question is answerable (test_fairfight_arms.py
    uses the same stub for the same reason)."""
    monkeypatch.setattr(G, "_answer_in_corpus", lambda conn, answer, variants: False)


def _kb(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    kb = tmp_path / "kb"
    monkeypatch.setenv("LIFE_AGENT_KB", str(kb))
    return kb


# --- run_meta.json: written first, pinned ----------------------------------------------


def test_run_meta_written_first_and_pinned(tmp_path: Path, monkeypatch: pytest.MonkeyPatch
                                            ) -> None:
    kb = _kb(tmp_path, monkeypatch)
    _write_questions(kb, [_q()])
    # pin the recorded env provenance regardless of the host machine's live services
    monkeypatch.delenv("LIFE_AGENT_GROW_LANE", raising=False)
    monkeypatch.delenv("LIFE_AGENT_BRIDGE_URL", raising=False)
    monkeypatch.setenv("ANSWER_BRAIN_URL", "http://127.0.0.1:9999")
    args = _args(tmp_path, arms="inprocess")

    result = RF.run(
        args, arm_impls={"inprocess": lambda q: _raw(question_id=q["id"])},
        judge_impl=_fake_judge(), conn_factory=lambda p: _FakeConn())

    meta = json.loads((result["run_dir"] / "run_meta.json").read_text())
    assert meta["format_version"] == RF.FORMAT_VERSION
    assert meta["run_id"] == "ff-test"
    assert meta["k"] == 8
    assert meta["judge_model"] == "gpt-5.1"
    assert meta["judge_n"] == 3
    assert meta["pricing_version"] == 1
    assert meta["arms"] == ["inprocess"]
    assert meta["arm_configs"]["inprocess"] == {
        "entrypoint": "ask.answer", "path": "inprocess", "gather": True}
    assert meta["pkm_config_path"] == args.config
    assert len(meta["questions_sha256"]) == 64  # a real sha256 hex digest
    # the real in-tree rubric — sha256 present, no note
    assert meta["rubric_sha256"] is not None and len(meta["rubric_sha256"]) == 64
    assert meta["rubric_note"] is None
    assert len(meta["prompt_v1_sha256"]) == 64
    # a real git checkout — best-effort provenance actually resolves here
    assert meta["life_agent_git"]["sha"] is None or len(meta["life_agent_git"]["sha"]) == 40
    # competitor not selected -> hermes provenance is honestly absent, not guessed
    assert meta["hermes_git"] == {
        "sha": None, "dirty": None, "version": None, "note": "competitor arm not selected"}
    assert meta["corpus_fingerprint"] == {"n_chunks": 3, "n_sources": 3, "note": None}
    # the exact env var names scripts/ask.py reads for EXECUTOR_BRIDGE/EXECUTOR_DAEMON —
    # which daemon the baseline arm hit is run provenance (null = unset, ask.py's
    # localhost defaults apply)
    assert meta["env_flags"] == {"LIFE_AGENT_GROW_LANE": "", "LIFE_AGENT_BRIDGE_URL": None,
                                 "ANSWER_BRAIN_URL": "http://127.0.0.1:9999"}
    assert (result["run_dir"] / "questions.sha256").read_text().strip() == \
        meta["questions_sha256"]


def test_run_meta_exists_even_if_an_arm_crashes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch
                                                 ) -> None:
    """run_meta.json is written BEFORE any arm runs — proven by a crashing arm still
    leaving it on disk."""
    kb = _kb(tmp_path, monkeypatch)
    _write_questions(kb, [_q()])
    args = _args(tmp_path, arms="inprocess", run_id="ff-crash-test")

    def _boom(q: dict) -> AB.RawAnswer:
        raise RuntimeError("an arm_impl that violates the never-raises convention")

    with pytest.raises(RuntimeError):
        RF.run(args, arm_impls={"inprocess": _boom}, judge_impl=_fake_judge(),
               conn_factory=lambda p: _FakeConn())

    run_dir = kb / "eval" / "fairfight" / "ff-crash-test"
    assert (run_dir / "run_meta.json").exists()


# --- directory layout --------------------------------------------------------------------


def test_directory_layout_all_four_arms(tmp_path: Path, monkeypatch: pytest.MonkeyPatch
                                         ) -> None:
    kb = _kb(tmp_path, monkeypatch)
    _write_questions(kb, [_q()])
    args = _args(tmp_path, arms="baseline,inprocess,synthesis,competitor")

    def _competitor(q: dict) -> AH.CompetitorResult:
        return AH.CompetitorResult(
            raw=_raw(question_id=q["id"], cards=()), usage={"estimated_cost_usd": 0.01},
            tool_log=[])

    result = RF.run(
        args,
        arm_impls={
            "baseline": lambda q: _raw(question_id=q["id"], cards=()),
            "inprocess": lambda q: _raw(question_id=q["id"]),
            "synthesis": lambda q: _raw(question_id=q["id"]),
            "competitor": _competitor,
        },
        judge_impl=_fake_judge(), conn_factory=lambda p: _FakeConn())

    run_dir = result["run_dir"]
    assert (run_dir / "run_meta.json").exists()
    assert (run_dir / "questions.sha256").exists()
    assert (run_dir / "summary.json").exists()
    assert (run_dir / "summary.md").exists()
    assert (run_dir / "judge" / "judge_meta.json").exists()
    for arm in ("baseline", "inprocess", "synthesis", "competitor"):
        assert (run_dir / "arms" / arm / "answers.jsonl").exists()
        assert (run_dir / "arms" / arm / "vectors.jsonl").exists()
        assert (run_dir / "judge" / f"{arm}_scores.jsonl").exists()


# --- vectors: one per (arm, question), correct arm names --------------------------------


def test_vectors_written_per_arm_and_question_with_correct_arm_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    kb = _kb(tmp_path, monkeypatch)
    _write_questions(kb, [_q("q-001"), _q("q-002")])
    args = _args(tmp_path, arms="inprocess,synthesis")

    result = RF.run(
        args,
        arm_impls={
            "inprocess": lambda q: _raw(question_id=q["id"]),
            "synthesis": lambda q: _raw(question_id=q["id"]),
        },
        judge_impl=_fake_judge(), conn_factory=lambda p: _FakeConn())

    for arm in ("inprocess", "synthesis"):
        lines = (result["run_dir"] / "arms" / arm / "vectors.jsonl").read_text().splitlines()
        assert len(lines) == 2
        rows = [json.loads(line) for line in lines]
        assert [r["arm"] for r in rows] == [arm, arm]
        assert [r["question_id"] for r in rows] == ["q-001", "q-002"]


# --- read_only=True -----------------------------------------------------------------------


def test_default_conn_factory_forces_read_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class _Stub:
        def execute(self, *a: object, **k: object) -> None:
            return None

    def fake_connect(path: str, **kwargs: object) -> _Stub:
        captured["path"] = path
        captured["kwargs"] = kwargs
        return _Stub()

    monkeypatch.setattr(RF.duckdb, "connect", fake_connect)
    RF.default_conn_factory(tmp_path / "catalogue.duckdb")
    assert captured["kwargs"].get("read_only") is True


# --- --no-judge -> every rubric dim None, judge never called -----------------------------


def test_no_judge_all_rubric_dims_none_and_judge_never_called(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    kb = _kb(tmp_path, monkeypatch)
    _write_questions(kb, [_q()])
    args = _args(tmp_path, arms="inprocess", no_judge=True)

    def _must_not_be_called(*a: object, **k: object) -> object:
        raise AssertionError("--no-judge must never call the judge")

    result = RF.run(
        args, arm_impls={"inprocess": lambda q: _raw(question_id=q["id"])},
        judge_impl=_must_not_be_called, conn_factory=lambda p: _FakeConn())

    vec = json.loads(
        (result["run_dir"] / "arms" / "inprocess" / "vectors.jsonl").read_text().splitlines()[0])
    assert vec["faithfulness"] is None
    assert vec["completeness"] is None
    assert vec["citation_fidelity"] is None
    assert vec["hallucinated"] is None

    scores = json.loads(
        (result["run_dir"] / "judge" / "inprocess_scores.jsonl").read_text().splitlines()[0])
    assert scores["judged"] is False
    assert scores["reason"] == "no_judge"


# --- status != "ok" excluded from judging but present in vectors ------------------------


def test_status_not_ok_excluded_from_judging_but_present_in_vectors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    kb = _kb(tmp_path, monkeypatch)
    _write_questions(kb, [_q("q-001"), _q("q-002")])
    args = _args(tmp_path, arms="inprocess")
    judged_ids: list[str] = []

    def _judge(q: dict, text: str, sources: list, *, n: int = 3) -> dict:
        judged_ids.append(str(q["id"]))
        return {"faithfulness": 3, "completeness": 3, "citation_fidelity": 3, "_served": ["j"]}

    def _impl(q: dict) -> AB.RawAnswer:
        if q["id"] == "q-002":
            return _raw(question_id="q-002", text="", status="error", notes="boom", cards=())
        return _raw(question_id="q-001")

    result = RF.run(
        args, arm_impls={"inprocess": _impl}, judge_impl=_judge,
        conn_factory=lambda p: _FakeConn())

    rows = [json.loads(line) for line in
            (result["run_dir"] / "arms" / "inprocess" / "vectors.jsonl").read_text().splitlines()]
    assert [r["question_id"] for r in rows] == ["q-001", "q-002"]
    assert rows[1]["status"] == "error"
    assert rows[1]["faithfulness"] is None
    assert rows[1]["hallucinated"] is None
    assert judged_ids == ["q-001"]  # the errored question was never judged


# --- a raising judge costs one question's dims, never the run ----------------------------


def test_judge_raising_systemexit_on_one_question_does_not_crash_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # judge_modal -> judge_complete -> openai_complete raises SystemExit on any HTTP/API
    # failure (core/llm.py's convention) — one transient judge error must be recorded and
    # skipped, with every other question still judged.
    kb = _kb(tmp_path, monkeypatch)
    _write_questions(kb, [_q("q-001"), _q("q-002"), _q("q-003")])
    args = _args(tmp_path, arms="inprocess", run_id="ff-judge-crash-test")

    def _judge(q: dict, text: str, sources: list, *, n: int = 3) -> dict:
        if q["id"] == "q-002":
            raise SystemExit("OpenAI API 529: overloaded")
        return {"faithfulness": 3, "completeness": 2, "citation_fidelity": 3, "_served": ["j"]}

    result = RF.run(
        args, arm_impls={"inprocess": lambda q: _raw(question_id=q["id"])},
        judge_impl=_judge, conn_factory=lambda p: _FakeConn())  # completes — no SystemExit

    vecs = [json.loads(line) for line in
            (result["run_dir"] / "arms" / "inprocess" / "vectors.jsonl").read_text().splitlines()]
    assert [v["question_id"] for v in vecs] == ["q-001", "q-002", "q-003"]
    assert vecs[1]["faithfulness"] is None      # the crashed question: dims stay None
    assert vecs[1]["hallucinated"] is None
    assert vecs[0]["faithfulness"] == 3         # its neighbours were still judged
    assert vecs[2]["faithfulness"] == 3

    scores = [json.loads(line) for line in
              (result["run_dir"] / "judge" / "inprocess_scores.jsonl").read_text().splitlines()]
    assert scores[1]["judged"] is False
    assert "judge error" in scores[1]["reason"]
    assert "SystemExit" in scores[1]["reason"]
    assert "529" in scores[1]["reason"]
    assert scores[0]["judged"] is True and scores[2]["judged"] is True


# --- cost_status mapping (direct unit tests against _economics) -------------------------


def _call(served_model: str, priced_ok: bool = True) -> LLMResult:
    model = served_model if priced_ok else "some-unlisted-local-model"
    return LLMResult(text="x", in_tokens=10, out_tokens=5, seconds=0.1, served_model=model)


def test_cost_status_baseline_arm_always_partial_even_if_fully_priced() -> None:
    raw = _raw(llm_calls=[_call("claude-sonnet-4-6")])
    econ = RF._economics("baseline", raw, None)
    assert econ["cost_status"] == "partial"
    assert econ["cost_usd"] is not None  # still sums whatever WAS priced


def test_cost_status_baseline_arm_partial_even_with_zero_metered_calls() -> None:
    # THE real baseline case: ask.answer_via_executor is a pure HTTP driver — the daemon's
    # spend is server-side, so llm_calls is [] on every question. That must read "partial"
    # (spend exists but is invisible from here), never "unavailable" (no cost signal at all).
    raw = _raw(llm_calls=[])
    econ = RF._economics("baseline", raw, None)
    assert econ["cost_status"] == "partial"
    assert econ["cost_usd"] is None
    assert econ["in_tokens"] == 0 and econ["out_tokens"] == 0
    assert econ["model_tier_mix"] == {}


def test_cost_status_inprocess_arm_measured_when_fully_priced() -> None:
    raw = _raw(llm_calls=[_call("claude-sonnet-4-6"), _call("claude-haiku-4-5")])
    econ = RF._economics("inprocess", raw, None)
    assert econ["cost_status"] == "measured"
    assert econ["cost_usd"] is not None


def test_cost_status_inprocess_arm_partial_on_one_unpriced_call() -> None:
    raw = _raw(llm_calls=[_call("claude-sonnet-4-6"), _call("qwen-local", priced_ok=False)])
    econ = RF._economics("inprocess", raw, None)
    assert econ["cost_status"] == "partial"


def test_cost_status_no_calls_is_unavailable() -> None:
    raw = _raw(llm_calls=[])
    econ = RF._economics("inprocess", raw, None)
    assert econ["cost_status"] == "unavailable"
    assert econ["cost_usd"] is None


def test_cost_status_competitor_estimated_when_usage_present() -> None:
    raw = _raw(llm_calls=[])
    econ = RF._economics("competitor", raw, {"estimated_cost_usd": 0.05, "model": "m",
                                              "api_calls": 2})
    assert econ["cost_status"] == "estimated"
    assert econ["cost_usd"] == 0.05
    assert econ["model_tier_mix"] == {"m": 2}


def test_cost_status_competitor_unavailable_when_usage_none() -> None:
    raw = _raw(llm_calls=[])
    econ = RF._economics("competitor", raw, None)
    assert econ["cost_status"] == "unavailable"
    assert econ["cost_usd"] is None
    assert econ["model_tier_mix"] == {}


# --- effort: gather_rounds mapping, per arm class (final-review IMPORTANT-5) -------------


def test_gather_rounds_missing_key_is_none_not_zero() -> None:
    raw = _raw(effort={})
    assert RF._gather_rounds("inprocess", raw) is None
    assert RF._gather_rounds("competitor", raw) is None


def test_gather_rounds_reads_the_competitor_shaped_key_verbatim() -> None:
    raw = _raw(effort={"tool_calls": 4, "gather_rounds": 2, "asks_issued": 0})
    assert RF._gather_rounds("competitor", raw) == 2


def test_gather_rounds_inprocess_arm_reads_gather_tiers_key() -> None:
    # final-review IMPORTANT-5 (revising seam resolution 4): "one corroboration tier
    # fired = one gather round" — mapped verbatim from the in-process arms' own
    # "gather_tiers" effort key.
    raw = _raw(effort={"retrieve_passes": 1, "gather_tiers": 1})
    assert RF._gather_rounds("inprocess", raw) == 1


def test_gather_rounds_synthesis_arm_also_reads_gather_tiers_key() -> None:
    raw = _raw(effort={"retrieve_passes": 1, "gather_tiers": 0})
    assert RF._gather_rounds("synthesis", raw) == 0


def test_gather_rounds_baseline_arm_always_none_not_derivable_from_the_view() -> None:
    # the daemon's own gather/grow round count is not observable in core.executor.py's
    # View (never edited to expose it) — even if `effort` happens to carry unrelated
    # keys, baseline never reads them for this axis.
    raw = _raw(effort={"gather_tiers": 3, "gather_rounds": 3})
    assert RF._gather_rounds("baseline", raw) is None


def test_tool_calls_only_populated_for_competitor() -> None:
    raw = _raw(effort={"tool_calls": 5})
    assert RF._tool_calls("competitor", raw) == 5
    assert RF._tool_calls("inprocess", raw) is None
    assert RF._tool_calls("baseline", raw) is None


def test_tool_calls_missing_key_is_none() -> None:
    raw = _raw(effort={})
    assert RF._tool_calls("competitor", raw) is None


# --- calibration: baseline/inprocess only, gated on a real lookup credence --------------


def _grades(**overrides: Any) -> G.ChannelGrades:
    base: dict[str, Any] = dict(
        bucket="CORRECT", cause=None, asserted=True, asserted_correct=True,
        asserted_distractor=False, declined=False, correct_abstention=False,
        over_abstention=False, gold_in_topk=True, gold_in_corpus=True,
        gold_in_candidates=True, distractor_in_topk=False, n_retrieved=5,
    )
    base.update(overrides)
    return G.ChannelGrades(**base)


def test_calibration_populated_for_inprocess_lookup_decision() -> None:
    raw = _raw(decision_view=_lookup_view(credences=[0.9], p_none=0.05))
    calib = RF._calibration("inprocess", raw, _grades(gold_in_candidates=True))
    assert calib["probability"] == 0.9
    assert calib["p_none"] == 0.05
    assert calib["p_none_correct"] is True  # p_none<0.5 and gold WAS in candidates
    assert calib["brier"] == pytest.approx((0.9 - 1.0) ** 2)


def test_calibration_none_for_synthesis_arm_even_with_a_lookup_view() -> None:
    # task dispatch §5 scopes calibration to baseline/inprocess only.
    raw = _raw(decision_view=_lookup_view())
    calib = RF._calibration("synthesis", raw, _grades())
    assert calib == RF._NO_CALIBRATION


def test_calibration_none_for_baseline_arm_when_decision_view_is_none() -> None:
    # e.g. a down/errored executor, or its narrative-fallback branch (arm_baseline.
    # _executor_decision returns None for it — see its own docstring).
    raw = _raw(decision_view=None)
    calib = RF._calibration("baseline", raw, _grades())
    assert calib == RF._NO_CALIBRATION


def test_calibration_populates_for_baseline_arm_with_a_real_typed_lookup_view() -> None:
    # final-review CRITICAL-1: since arm_baseline._executor_decision now builds a REAL
    # decision_view for the executor's typed-lookup decisions, the baseline arm's
    # calibration axis comes alive exactly like inprocess's — it is no longer
    # structurally always-None.
    raw = _raw(decision_view=_lookup_view(credences=[0.9], p_none=0.05))
    calib = RF._calibration("baseline", raw, _grades(gold_in_candidates=True))
    assert calib["probability"] == 0.9
    assert calib["p_none"] == 0.05
    assert calib["brier"] == pytest.approx((0.9 - 1.0) ** 2)


def test_calibration_none_for_narrative_family_no_real_credence() -> None:
    view = {"family": "narrative", "action": "report", "asserted": True,
            "asserted_values": ["x"], "candidates": ["x"], "credences": [0.9], "p_none": None}
    raw = _raw(decision_view=view)
    calib = RF._calibration("inprocess", raw, _grades())
    assert calib == RF._NO_CALIBRATION


def test_calibration_p_none_correct_none_when_gold_in_candidates_is_none() -> None:
    raw = _raw(decision_view=_lookup_view())
    calib = RF._calibration("inprocess", raw, _grades(gold_in_candidates=None))
    assert calib["p_none_correct"] is None


# --- calibration: probability/brier gated on an ASSERTING decision (IMPORTANT-4) --------


def test_calibration_probability_and_brier_none_when_declined_but_p_none_still_populates(
) -> None:
    # an abstain still carries a real max(credences) number (the posterior's leader) —
    # scoring THAT as if the arm reported it would grade a decision it never made.
    # p_none/p_none_correct are a different claim (the withholding decision's own
    # credence) and populate regardless.
    view = _lookup_view(action="abstain", asserted=False, credences=[0.3, 0.2], p_none=0.6)
    raw = _raw(decision_view=view)
    calib = RF._calibration(
        "inprocess", raw, _grades(asserted=False, gold_in_candidates=False))
    assert calib["probability"] is None
    assert calib["brier"] is None
    assert calib["p_none"] == 0.6
    assert calib["p_none_correct"] is True  # p_none>=0.5 and gold WAS NOT in candidates: agree


def test_calibration_probability_and_brier_populate_for_hedge_an_asserting_decision() -> None:
    # hedge IS an assertion-class act in this harness's convention (grades.asserted=True
    # for it) — its probability/brier populate exactly like a report's.
    view = _lookup_view(action="hedge", asserted=True, credences=[0.4, 0.35], p_none=0.25)
    raw = _raw(decision_view=view)
    calib = RF._calibration(
        "inprocess", raw, _grades(asserted=True, asserted_correct=False,
                                  gold_in_candidates=True))
    assert calib["probability"] == 0.4
    assert calib["brier"] == pytest.approx((0.4 - 0.0) ** 2)
    assert calib["p_none"] == 0.25
    assert calib["probability"] is not None  # everything else still populates


# --- calibration-write redirect (no production calibration/ contamination) ---------------


def test_redirect_decisions_log_points_inside_run_dir_and_restores(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    original = LCFG.DECISIONS_LOG
    with RF._redirect_decisions_log(run_dir) as shadow:
        assert shadow == run_dir / "shadow_calibration" / "decisions.jsonl"
        assert shadow == LCFG.DECISIONS_LOG
        assert original != LCFG.DECISIONS_LOG
    assert original == LCFG.DECISIONS_LOG


def test_redirect_decisions_log_restores_even_on_exception(tmp_path: Path) -> None:
    original = LCFG.DECISIONS_LOG
    with pytest.raises(RuntimeError), RF._redirect_decisions_log(tmp_path / "run"):
        raise RuntimeError("boom")
    assert original == LCFG.DECISIONS_LOG


# --- final-review IMPORTANT-3: the shadow seeds from real production content -----------


def test_redirect_decisions_log_seeds_shadow_from_existing_production_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    prod = tmp_path / "prod_decisions.jsonl"
    prod.write_text('{"a":1}\n{"a":2}\n', encoding="utf-8")
    monkeypatch.setattr(LCFG, "DECISIONS_LOG", prod)
    run_dir = tmp_path / "run"

    with RF._redirect_decisions_log(run_dir) as shadow:
        assert shadow.read_text() == prod.read_text()
        # a write during the run lands ONLY in the shadow — never flows back to prod.
        with shadow.open("a", encoding="utf-8") as f:
            f.write('{"a":3}\n')

    assert prod.read_text() == '{"a":1}\n{"a":2}\n'  # untouched by the run's own writes


def test_redirect_decisions_log_no_seed_when_production_file_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    absent_prod = tmp_path / "no-such-decisions.jsonl"
    monkeypatch.setattr(LCFG, "DECISIONS_LOG", absent_prod)
    run_dir = tmp_path / "run"

    with RF._redirect_decisions_log(run_dir) as shadow:
        assert not shadow.exists()  # nothing to seed from — same as before this fix


def test_run_writes_nothing_outside_the_run_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    kb = _kb(tmp_path, monkeypatch)
    _write_questions(kb, [_q()])
    before = _snapshot(kb)
    args = _args(tmp_path, arms="inprocess", run_id="ff-writes-test")

    RF.run(
        args, arm_impls={"inprocess": lambda q: _raw(question_id=q["id"])},
        judge_impl=_fake_judge(), conn_factory=lambda p: _FakeConn())

    after = _snapshot(kb)
    new_files = after - before
    run_dir = kb / "eval" / "fairfight" / "ff-writes-test"
    assert new_files, "expected the run to create new files"
    for f in new_files:
        # either the run dir itself / a file inside it, or a plain ancestor directory of
        # it (e.g. the freshly-created eval/fairfight/) — never a sibling or unrelated path
        assert f == run_dir or run_dir in f.parents or f in run_dir.parents
    assert not (kb / "calibration").exists()  # never touches production calibration/


# --- competitor: retry once on a tool_log error row ---------------------------------------


def test_competitor_retries_once_on_a_tool_log_error_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    kb = _kb(tmp_path, monkeypatch)
    _write_questions(kb, [_q()])
    args = _args(tmp_path, arms="competitor", run_id="ff-retry-test")
    calls = {"n": 0}

    def _competitor(q: dict) -> AH.CompetitorResult:
        calls["n"] += 1
        if calls["n"] == 1:
            tool_log = [{"tool": "search", "args": {}, "n_results": 0, "error": "locked"}]
            return AH.CompetitorResult(
                raw=_raw(question_id=q["id"], text="", cards=()),
                usage={"estimated_cost_usd": 0.01, "model": "m", "api_calls": 1},
                tool_log=tool_log)
        tool_log = [{"tool": "search", "args": {},
                     "results": [{"source_path": "a.txt", "chunk_text_full": "P123 here"}]}]
        return AH.CompetitorResult(
            raw=_raw(question_id=q["id"], text="P123 [a.txt]", cards=(), notes=""),
            usage={"estimated_cost_usd": 0.02, "model": "m", "api_calls": 1}, tool_log=tool_log)

    result = RF.run(
        args, arm_impls={"competitor": _competitor}, judge_impl=_fake_judge(),
        conn_factory=lambda p: _FakeConn())

    assert calls["n"] == 2
    answers_path = result["run_dir"] / "arms" / "competitor" / "answers.jsonl"
    row = json.loads(answers_path.read_text().splitlines()[0])
    assert "retried once" in row["notes"]
    assert row["usage"]["estimated_cost_usd"] == 0.02  # the retry's usage, not the first try's

    vectors_path = result["run_dir"] / "arms" / "competitor" / "vectors.jsonl"
    assert len(vectors_path.read_text().splitlines()) == 1  # exactly one row, not two


def test_competitor_stale_tool_calls_and_usage_dirs_cleared_at_run_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # final-review IMPORTANT-6 item 2: a stale tool_calls/<qid>.jsonl or usage/<qid>.json
    # left by a PRIOR run under the same --run-id (e.g. a run with a larger --limit) must
    # not survive into this run's directory.
    kb = _kb(tmp_path, monkeypatch)
    _write_questions(kb, [_q("q-001")])
    args = _args(tmp_path, arms="competitor", run_id="ff-stale-test")
    run_dir = kb / "eval" / "fairfight" / "ff-stale-test"
    stale_tool = run_dir / "arms/competitor/tool_calls/q-999-stale.jsonl"
    stale_usage = run_dir / "arms/competitor/usage/q-999-stale.json"
    stale_tool.parent.mkdir(parents=True, exist_ok=True)
    stale_usage.parent.mkdir(parents=True, exist_ok=True)
    stale_tool.write_text("stale\n", encoding="utf-8")
    stale_usage.write_text("{}", encoding="utf-8")

    def _competitor(q: dict) -> AH.CompetitorResult:
        return AH.CompetitorResult(
            raw=_raw(question_id=q["id"], cards=()),
            usage={"estimated_cost_usd": 0.01, "model": "m", "api_calls": 1}, tool_log=[])

    RF.run(args, arm_impls={"competitor": _competitor}, judge_impl=_fake_judge(),
           conn_factory=lambda p: _FakeConn())

    assert not stale_tool.exists()
    assert not stale_usage.exists()


# --- final-review CRITICAL-2: infra-failed rows excluded from every rate/summary count ---


def test_summarize_arm_excludes_error_rows_from_rates_and_reports_excluded_count() -> None:
    ok = _vector_for_summary(question_id="q-1", status="ok", bucket="CORRECT",
                              answerable=True, declined=False, latency_s=1.0, cost_usd=0.01)
    err = _vector_for_summary(question_id="q-2", status="error", bucket="CONFIDENT_WRONG",
                              answerable=True, declined=False, latency_s=0.0, cost_usd=None)
    judged = [
        {"faithfulness": 3, "completeness": 3, "citation_fidelity": 3, "hallucinated": False,
         "synthesis_pass": True, "abstained_correctly": None, "judged": True, "reason": None},
        {"faithfulness": None, "completeness": None, "citation_fidelity": None,
         "hallucinated": None, "synthesis_pass": None, "abstained_correctly": None,
         "judged": False, "reason": "status=error"},
    ]
    summary = RF._summarize_arm("inprocess", [ok, err], judged)
    assert summary["n_total"] == 2
    assert summary["n"] == 1                     # the scored population
    assert summary["n_excluded_infra"] == 1
    assert summary["n_error"] == 1
    # the error row's CONFIDENT_WRONG bucket must never reach a rate: 1/1 scored, not
    # 1/2 (which "confident_wrong" would silently be if the error row were counted).
    assert summary["confident_wrong"] == 0
    assert summary["confident_wrong_rate"] == 0.0
    assert summary["correct"] == 1
    assert summary["correct_rate"] == 1.0
    assert summary["cost"]["total_usd"] == pytest.approx(0.01)
