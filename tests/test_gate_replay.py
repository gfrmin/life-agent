"""The Δ2 gate baseline: the owner's outside option as a replayed raw-deliberative arm.

The comparator the §8 gate values arm B against becomes what the owner would actually do
without the agent — ask Claude with corpus access and act on what it says (owner decision
2026-08-06). Measured offline: the fair-fight run's stored answers replay as the arm; the
join is STRICT (a missing question is named, never silently dropped — no silent caps).

Run: uv run --project . python -m pytest tests/test_gate_replay.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import run_eval as RE


def _row(qid: str, text: str, *, declined: bool = False,
         status: str = "ok") -> dict[str, Any]:
    return {"question_id": qid, "text": text, "declined": declined, "status": status}


def _write_answers(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


# --- load_replay_answers -----------------------------------------------------------------

def test_load_replay_answers_from_jsonl(tmp_path: Path) -> None:
    p = _write_answers(tmp_path / "answers.jsonl",
                       [_row("q2-001", "P123 [doc.pdf]"), _row("q2-002", "x")])
    rows = RE.load_replay_answers(p)
    assert set(rows) == {"q2-001", "q2-002"}
    assert rows["q2-001"]["text"] == "P123 [doc.pdf]"


def test_load_replay_answers_from_run_dir(tmp_path: Path) -> None:
    _write_answers(tmp_path / "arms" / "deliberative" / "answers.jsonl",
                   [_row("q2-001", "P123")])
    rows = RE.load_replay_answers(tmp_path)
    assert set(rows) == {"q2-001"}


# --- _replay_response: the arm graded on the ONE common answer-level scale ---------------

def test_replay_report_graded_by_gold_containment() -> None:
    q = {"id": "q2-001", "answer": "P123", "answer_variants": [], "fuzzy": False}
    r = RE._replay_response(_row("q2-001", "the number is P123 [doc.pdf]"), q)
    assert r.action == "report"
    assert r.correct is True
    wrong = RE._replay_response(_row("q2-001", "the number is Q999 [doc.pdf]"), q)
    assert wrong.action == "report"
    assert wrong.correct is False


def test_replay_decline_is_an_abstention() -> None:
    q = {"id": "q2-001", "answer": "P123", "answer_variants": [], "fuzzy": False}
    r = RE._replay_response(
        _row("q2-001", "NOT_IN_CORPUS: nothing", declined=True), q)
    assert r.action == "abstain"
    assert r.correct is None


def test_replay_error_row_is_an_abstention() -> None:
    q = {"id": "q2-001", "answer": "P123", "answer_variants": [], "fuzzy": False}
    r = RE._replay_response(_row("q2-001", "", status="error"), q)
    assert r.action == "abstain"


def test_replay_blank_ok_row_is_an_abstention_not_a_confident_wrong() -> None:
    # rc=0 with an empty result is a degenerate run, not an assertion — grading it as a
    # report would mint a spurious confident-wrong (the A3 sign rested on 3 of those).
    q = {"id": "q2-001", "answer": "P123", "answer_variants": [], "fuzzy": False}
    assert RE._replay_response(_row("q2-001", ""), q).action == "abstain"
    assert RE._replay_response(_row("q2-001", "   "), q).action == "abstain"
    none_text = dict(_row("q2-001", ""), text=None)
    assert RE._replay_response(none_text, q).action == "abstain"


def test_typed_and_replay_responses_carry_realised_cost() -> None:
    # the run-6 spend term's data feed (plan item C, per the #67 review): the typed
    # arm's cost is the view's TOTAL metered spend (spend_usd — deliberate AND tiers,
    # never the deliberate-only decisions-v2 slot); the replay arm's is the ff run's
    # recorded usage.estimated_cost_usd; absent either way ⇒ 0.0.
    q = {"id": "q2-001", "answer": "P123", "answer_variants": [], "fuzzy": False}
    typed = RE._typed_response_executor(
        _exec_view(effector="report", asserted=["P123"], cost_usd=0.42,
                   spend_usd=0.432), q)
    assert typed.cost_usd == 0.432
    assert RE._typed_response_executor(_exec_view(), q).cost_usd == 0.0
    priced_row = dict(_row("q2-001", "the number is P123"),
                      usage={"estimated_cost_usd": 0.36})
    assert RE._replay_response(priced_row, q).cost_usd == 0.36
    assert RE._replay_response(_row("q2-001", "P123"), q).cost_usd == 0.0


def test_paired_dict_carries_the_cost_fields() -> None:
    # PR #67 review: paired.jsonl is the gate's replayable artifact — dropping cost_usd
    # would make every offline reanalysis silently recompute Δ with the spend term
    # zeroed (the §17.4/§17.5 replays were built from exactly this file).
    import life_agent.core.gate as GATE

    p = GATE.PairedOutcome(
        question_id="q2-001", answerable=True,
        typed=GATE.RealisedResponse(action="abstain", correct=None, cost_usd=0.31),
        mono=GATE.RealisedResponse(action="report", correct=True, cost_usd=0.36))
    d = RE._paired_to_dict(p, baseline="raw-deliberative-replay")
    assert d["typed"]["cost_usd"] == 0.31
    assert d["mono"]["cost_usd"] == 0.36


def test_paired_dict_names_its_baseline_arm() -> None:
    import life_agent.core.gate as GATE

    p = GATE.PairedOutcome(
        question_id="q2-001", answerable=True,
        typed=GATE.RealisedResponse(action="abstain", correct=None),
        mono=GATE.RealisedResponse(action="report", correct=True))
    d = RE._paired_to_dict(p, baseline="raw-deliberative-replay")
    assert d["baseline"] == "raw-deliberative-replay"
    assert RE._paired_to_dict(p)["baseline"] == "monolithic"


# --- gate_paired_outcomes with the replay baseline ----------------------------------------

class _FakeAsk:
    """The production path stub: typed pass answers; a families=False call would be the
    monolithic arm — with a replay baseline it must never fire."""

    ABSTENTION = "ABSTAIN-SENTINEL"

    def __init__(self) -> None:
        self.LOOKUP_LAST: Any = None
        self.NARRATIVE_LAST: Any = None
        self.calls: list[dict[str, Any]] = []

    def answer(self, conn: Any, question: str, k: int, **kw: Any) -> tuple[str, list, dict]:
        self.calls.append(kw)
        return self.ABSTENTION, [], {}


def _questions() -> list[dict[str, Any]]:
    return [{"id": "q2-001", "question": "value?", "answer": "P123",
             "answer_variants": [], "fuzzy": False, "answerable": True}]


def test_gate_pairs_typed_against_the_replay_arm(tmp_path: Path) -> None:
    replay = {"q2-001": _row("q2-001", "P123 [doc.pdf]")}
    paired = RE.gate_paired_outcomes(None, _questions(), 20, _FakeAsk(), replay=replay)
    (p,) = paired
    assert p.mono.action == "report"
    assert p.mono.correct is True
    assert p.typed.action == "abstain"


def test_gate_replay_never_runs_the_monolithic_pass(tmp_path: Path) -> None:
    fake = _FakeAsk()
    RE.gate_paired_outcomes(None, _questions(), 20, fake, replay={
        "q2-001": _row("q2-001", "P123")})
    assert all(c.get("families") is not False for c in fake.calls)
    assert not any("families" in c for c in fake.calls)


def test_gate_replay_missing_question_is_named_never_dropped() -> None:
    with pytest.raises(ValueError, match="q2-001"):
        RE.gate_paired_outcomes(None, _questions(), 20, _FakeAsk(), replay={})


# --- the executor typed arm (--gate-executor): the gate finally SEES the edge -------------

def _exec_view(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "effector": "abstain", "asserted": [], "candidates": ["P123"],
        "credences": [0.6], "p_none": 0.4, "eu": 0.0, "n_obs": 1,
        "hits": [], "route": {"construct": "passport number"},
        "instrument": "", "cost_usd": None, "latency_s": None,
        "instrument_value": None, "instrument_confidence": None,
        "instrument_lineage": None, "edge_events": [], "spend_usd": 0.0}
    base.update(overrides)
    return base


def test_typed_response_executor_grades_each_effector() -> None:
    q = {"id": "q1", "answer": "P123", "answer_variants": []}
    r = RE._typed_response_executor(_exec_view(effector="report", asserted=["P123"]), q)
    assert r.action == "report" and r.correct is True
    r = RE._typed_response_executor(_exec_view(effector="report", asserted=["WRONG"]), q)
    assert r.action == "report" and r.correct is False
    r = RE._typed_response_executor(
        _exec_view(effector="hedge", candidates=["X", "P123"]), q)
    assert r.action == "hedge" and r.correct is True
    r = RE._typed_response_executor(_exec_view(effector="ask_clarify"), q)
    assert r.action == "ask_clarify" and r.correct is None
    # the executor's miss (the local edge declined) asserted nothing — an abstention
    # on the gate's answer-level scale
    r = RE._typed_response_executor(_exec_view(effector="miss"), q)
    assert r.action == "abstain" and r.correct is None
    r = RE._typed_response_executor(_exec_view(effector="abstain"), q)
    assert r.action == "abstain" and r.correct is None


def _chunk_conn(chunk_ids: list[int]):
    """A minimal stand-in for the catalogue: the availability probe only ever reads
    ``artifact_chunks``, because retrieval itself is pure SQL over the catalogue (pkm SPEC
    §15.2) — it never opens a source file, so present CHUNKS, not present files, are what
    decide whether a question is answerable here."""
    import duckdb
    conn = duckdb.connect(":memory:")
    # artifact_cache_key + chunk_index ride too: they are the artifact_chunks PRIMARY KEY
    # and what corpus_digest hashes, so the note and both probe predicates read the same
    # table the real catalogue exposes.
    conn.execute(
        "CREATE TABLE artifact_chunks "
        "(chunk_id BIGINT, artifact_cache_key VARCHAR, chunk_index INTEGER)"
    )
    for cid in chunk_ids:
        conn.execute("INSERT INTO artifact_chunks VALUES (?, ?, ?)", [cid, f"key-{cid}", 0])
    return conn


def test_gold_available_reads_the_catalogue_not_the_filesystem() -> None:
    conn = _chunk_conn([100, 200])
    questions = [
        {"id": "here", "provenance": {"chunk_id": 100, "source_path": "/gone/x.pdf"}},
        {"id": "absent", "provenance": {"chunk_id": 999, "source_path": "/mnt/yo/y.pdf"}},
    ]
    avail = RE.gold_available(conn, questions)
    # the source file's path is irrelevant — "here" has no file yet answers fine, which is
    # exactly today's thinkpad (full catalogue, 0 of 16 Downloads sources on disk)
    assert avail == {"here": True, "absent": False}


def test_gold_available_prefers_the_content_addressed_pair_over_the_surrogate() -> None:
    """``chunk_id`` does not survive ``pkm rebuild-catalogue`` (it is a sequence surrogate,
    migration 0005); the ``(artifact_cache_key, chunk_index)`` PK does. When a corpus carries
    both, the pair decides — otherwise a rebuilt catalogue silently resolves the gold to a
    *different* chunk and the censoring rule reads as available on the wrong evidence."""
    conn = _chunk_conn([100])
    # the surrogate is stale (999 is absent) but the content-addressed pair is present:
    # available, because the chunk genuinely IS here under a re-issued id.
    q = [{"id": "rechunked",
          "provenance": {"chunk_id": 999, "artifact_cache_key": "key-100", "chunk_index": 0}}]
    assert RE.gold_available(conn, q) == {"rechunked": True}
    # and the converse: a live surrogate must not rescue a genuinely absent chunk.
    q = [{"id": "gone",
          "provenance": {"chunk_id": 100, "artifact_cache_key": "key-absent", "chunk_index": 0}}]
    assert RE.gold_available(conn, q) == {"gone": False}


def test_gold_available_falls_back_per_question_not_per_corpus() -> None:
    """A partly-backfilled corpus must degrade one question at a time, not wholesale."""
    conn = _chunk_conn([100, 200])
    questions = [
        {"id": "new", "provenance": {"chunk_id": 1, "artifact_cache_key": "key-200",
                                     "chunk_index": 0}},
        {"id": "old", "provenance": {"chunk_id": 100}},          # v1 shape, still works
        {"id": "old-absent", "provenance": {"chunk_id": 777}},
    ]
    assert RE.gold_available(conn, questions) == \
        {"new": True, "old": True, "old-absent": False}


def test_gold_available_fails_open_so_a_probe_error_never_censors() -> None:
    # censoring REMOVES evidence. A question we cannot check must stay in Δ — a broken
    # probe silently shrinking the corpus the gate is judged on is the failure mode that
    # would be hardest to notice and worst to have.
    conn = _chunk_conn([1])
    assert RE.gold_available(conn, [{"id": "no-prov"}]) == {"no-prov": True}
    assert RE.gold_available(conn, [{"id": "empty-prov", "provenance": {}}]) == \
        {"empty-prov": True}

    class _Broken:
        def execute(self, *a: Any, **kw: Any):
            raise RuntimeError("catalogue is gone")

    assert RE.gold_available(_Broken(), [{"id": "q", "provenance": {"chunk_id": 5}}]) == \
        {"q": True}


def test_corpus_note_records_which_corpus_the_reading_used() -> None:
    # no gate report has ever carried its corpus: "the digest held across all firings" was
    # an operator check, not a property of the artifact. This makes it one.
    conn = _chunk_conn([100])
    note = RE.corpus_note(conn, [{"id": "a", "provenance": {"chunk_id": 100}},
                                 {"id": "b", "provenance": {"chunk_id": 777}}])
    assert note.startswith("> **Corpus:** digest `")
    assert "1 of 2 question(s) unavailable here" in note


def test_corpus_note_degrades_rather_than_voiding_a_paid_reading() -> None:
    class _Broken:
        def execute(self, *a: Any, **kw: Any):
            raise RuntimeError("no catalogue")

    note = RE.corpus_note(_Broken(), [{"id": "a"}])
    assert "digest unavailable" in note


def test_corpus_identity_reports_unpinned_without_a_pin() -> None:
    """The digest is recorded whether or not a pin was demanded — recording never depends
    on checking, or an unpinned run would publish nothing."""
    c = RE.corpus_identity(_chunk_conn([100, 200]), pin=None)
    assert c["pin_status"] == "unpinned"
    assert len(c["digest"]) == 64
    assert (c["n_artifacts"], c["n_chunks"]) == (2, 2)


def test_corpus_identity_matches_and_mismatches_a_pin(tmp_path: Path,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    """The pin is what turns 'the corpus held' from a claim into a checked property."""
    monkeypatch.setenv("LIFE_AGENT_KB", str(tmp_path))
    conn = _chunk_conn([100, 200])
    live = RE.corpus_identity(conn, pin=None)["digest"]

    pins = tmp_path / "eval" / "corpus"
    pins.mkdir(parents=True)
    (pins / "good.json").write_text(json.dumps(
        {"corpus_digest": live, "artifacts": ["key-100", "key-200"], "n_chunks": 2}))
    (pins / "stale.json").write_text(json.dumps(
        {"corpus_digest": "0" * 64, "artifacts": ["key-100"], "n_chunks": 1}))

    assert RE.corpus_identity(conn, pin="good")["pin_status"] == "matched"
    bad = RE.corpus_identity(conn, pin="stale")
    assert bad["pin_status"] == "mismatched"
    # the payoff a manifest buys over a bare digest: not just THAT it moved, but what moved
    assert bad["diff_vs_pin"]["n_added"] == 1
    assert bad["diff_vs_pin"]["added_sample"] == ["key-200"]


def test_corpus_identity_names_a_missing_pin_instead_of_claiming_a_match() -> None:
    c = RE.corpus_identity(_chunk_conn([100]), pin="does-not-exist")
    assert c["pin_status"] == "error" and c["digest"]  # digest still recorded


def test_corpus_note_publishes_a_mismatch_loudly() -> None:
    """A knowingly off-corpus reading must be unmissable in the artifact a human reads."""
    conn = _chunk_conn([100])
    corpus = {"digest": "d" * 64, "snapshot": "full-2026-06-11",
              "pin_status": "mismatched", "n_artifacts": 1, "n_chunks": 1,
              "diff_vs_pin": {"n_added": 7, "n_removed": 0}, "note": None}
    note = RE.corpus_note(conn, [{"id": "a", "provenance": {"chunk_id": 100}}],
                          corpus=corpus)
    assert "CORPUS MISMATCH" in note and "+7/-0" in note
    assert "NOT comparable to the pinned series" in note


def test_paired_row_carries_run_and_corpus_identity() -> None:
    """§14 routes cross-run comparability THROUGH these artifacts. run_id was recoverable
    only from the filename and the corpus not at all, so a Δ series claiming one universe
    could not show it — `jq -s 'group_by(.corpus_digest)'` is now that check."""
    import life_agent.core.gate as GATE

    p = GATE.PairedOutcome(
        question_id="q2-001", answerable=True,
        typed=GATE.RealisedResponse(action="abstain", correct=None),
        mono=GATE.RealisedResponse(action="report", correct=True))
    row = RE._paired_to_dict(p, run_id="gate-20260817T000000",
                             corpus_digest="d" * 64, corpus_snapshot="full-2026-06-11")
    assert row["run_id"] == "gate-20260817T000000"
    assert row["corpus_digest"] == "d" * 64
    assert row["corpus_snapshot"] == "full-2026-06-11"


def test_withheld_reason_separates_the_three_causes() -> None:
    # foundations §14: the gate used to flatten every withholding into one `abstain`, which
    # is why run 5's 70 of them gave no direction. The three causes want opposite fixes —
    # reach (miss), threshold (dispersed), corpus (unavailable) — so the reading must be
    # able to tell them apart.
    import life_agent.core.gate as G
    q = {"id": "q1", "answer": "P123", "answer_variants": []}

    # no posterior ever existed: /extract grounded nothing, the daemon was never consulted
    r = RE._typed_response_executor(_exec_view(effector="miss", candidates=[]), q)
    assert r.withheld == G.WITHHELD_MISS
    # a posterior existed and lost the EU argmax
    r = RE._typed_response_executor(_exec_view(effector="abstain", candidates=["P9"]), q)
    assert r.withheld == G.WITHHELD_DISPERSED
    # unavailability DOMINATES: whatever the executor did, a corpus that cannot answer the
    # question says nothing about the policy
    r = RE._typed_response_executor(
        _exec_view(effector="abstain", candidates=["P9"]), q, available=False)
    assert r.withheld == G.WITHHELD_UNAVAILABLE
    # assertions carry no reason (there was no withholding to explain)
    r = RE._typed_response_executor(_exec_view(effector="report", asserted=["P123"]), q)
    assert r.withheld is None


def test_paired_row_carries_what_delta_was_computed_over() -> None:
    # the artifact must DETERMINE the published Δ (the cost_usd precedent): `withheld`
    # decides which rows counted, so a row without it cannot reproduce the number.
    import life_agent.core.gate as G
    p = G.PairedOutcome(
        question_id="q1", answerable=True,
        typed=G.RealisedResponse(action="abstain", withheld=G.WITHHELD_UNAVAILABLE),
        mono=G.RealisedResponse(action="report", correct=True))
    row = RE._paired_to_dict(p, baseline="raw-deliberative-replay")
    assert row["censored"] is True
    assert row["typed"]["withheld"] == G.WITHHELD_UNAVAILABLE
    assert row["mono"]["withheld"] is None


class _FakeExecutorAsk:
    """ask with the executor surface stubbed: answer_via_executor pops the scripted view
    into EXECUTOR_VIEW_LAST; the family path must never run under the executor arm."""

    ABSTENTION = "ABSTAIN-SENTINEL"

    def __init__(self, views: list[dict[str, Any] | None]) -> None:
        self._views = list(views)
        self.EXECUTOR_VIEW_LAST: dict[str, Any] | None = None
        self.EXECUTOR_HOLD_OUT_QUESTION_ID: str | None = None
        self.executor_calls: list[str] = []
        self.holdouts_seen: list[str | None] = []

    def answer_via_executor(self, question: str, k: int) -> tuple[str, list, dict]:
        self.executor_calls.append(question)
        self.holdouts_seen.append(self.EXECUTOR_HOLD_OUT_QUESTION_ID)
        self.EXECUTOR_VIEW_LAST = self._views.pop(0)
        return ("rendered", [], {})

    def answer(self, conn: Any, question: str, k: int, **kw: Any) -> tuple[str, list, dict]:
        raise AssertionError("the family path must not run under the executor arm")


def test_gate_executor_arm_pairs_the_view_against_replay() -> None:
    fake = _FakeExecutorAsk([_exec_view(effector="report", asserted=["P123"],
                                        instrument="deliberate@claude-opus-4-8",
                                        cost_usd=0.31)])
    replay = {"q2-001": _row("q2-001", "P123 [doc.pdf]")}
    paired = RE.gate_paired_outcomes(None, _questions(), 20, fake, replay=replay,
                                     typed_arm="executor")
    (p,) = paired
    assert p.typed.action == "report" and p.typed.correct is True
    assert p.mono.action == "report" and p.mono.correct is True
    assert fake.executor_calls == ["value?"]


def test_gate_executor_arm_collects_views_for_the_writer() -> None:
    view = _exec_view(effector="abstain", instrument="deliberate@claude-opus-4-8",
                      instrument_value="P123", instrument_confidence=0.85,
                      instrument_lineage="dk-1", cost_usd=0.31, latency_s=21.7,
                      edge_events=[{"edge": "deliberate@claude-opus-4-8",
                                    "value": "P123", "confidence": 0.85,
                                    "lineage": "dk-1"}])
    fake = _FakeExecutorAsk([view])
    out: list = []
    RE.gate_paired_outcomes(None, _questions(), 20, fake,
                            replay={"q2-001": _row("q2-001", "P123")},
                            typed_arm="executor", typed_views=out)
    ((q, v),) = out
    assert q["id"] == "q2-001" and v is view
    # the writer's rows build straight off the collected pair — the abstained act
    # still grades the edge's raw proposal
    (e,) = RE.edge_outcomes(q, v, run_id="r")
    assert e.grade == "CORRECT" and e.probability == 0.85


def test_judge_shadow_items_cover_every_graded_candidate_and_skip_ungradeable() -> None:
    # the shadow judge grades exactly what the matcher grades, WITH the matcher's own
    # semantics (PR #65 review): typed asserts one item PER VALUE (the gate's
    # realised_report is any-per-value — a joined string drifts both directions),
    # hedges one item per candidate (the gate grades hedge over view["candidates"]),
    # the replay arm's report text, and every gradeable edge firing. Skips mirror the
    # matcher's own: abstains, declined/blank replay rows, rows whose status is not
    # exactly "ok" (a MISSING status is an abstain in _replay_response, never graded),
    # gold-less questions, valueless or edge-less events.
    questions = [*_two_questions(),
                 {"id": "q2-003", "question": "no gold?", "answer": "",
                  "answer_variants": [], "fuzzy": False, "answerable": False},
                 {"id": "q2-004", "question": "hedged?", "answer": "X9",
                  "answer_variants": [], "fuzzy": False, "answerable": True},
                 {"id": "q2-005", "question": "no status?", "answer": "X9",
                  "answer_variants": [], "fuzzy": False, "answerable": True}]
    typed_views = [
        (questions[0], _exec_view(
            effector="report", asserted=["P123", "second claim"],
            edge_events=[{"edge": "extract@claude-haiku-4-5", "value": "P123",
                          "confidence": 0.7, "lineage": "jk-1"},
                         {"edge": "deliberate@claude-opus-4-8", "value": None,
                          "confidence": None, "lineage": "dk-d"},
                         {"value": "orphan", "confidence": 0.5}])),  # edge-less: skip
        (questions[1], _exec_view(effector="abstain")),  # no assert → no typed item
        (questions[2], _exec_view(effector="report", asserted=["whatever"])),  # no gold
        (questions[3], _exec_view(effector="hedge", candidates=["X9", "Q1"])),
        (questions[4], _exec_view(effector="abstain")),
    ]
    no_status = {"question_id": "q2-005", "text": "X9"}  # missing status ⇒ abstain
    replay = {"q2-001": _row("q2-001", "the number is P123 [doc.pdf]"),
              "q2-002": _row("q2-002", "NOT_IN_CORPUS", declined=True),
              "q2-003": _row("q2-003", "x"),
              "q2-004": _row("q2-004", "", status="error"),
              "q2-005": no_status}
    items = RE.judge_shadow_items(questions, typed_views, replay)
    assert [(i["question_id"], i["arm"], i["candidate"]) for i in items] == [
        ("q2-001", "typed", "P123"),
        ("q2-001", "typed", "second claim"),
        ("q2-001", "edge:extract@claude-haiku-4-5", "P123"),
        ("q2-004", "typed-hedge", "X9"),
        ("q2-004", "typed-hedge", "Q1"),
        ("q2-001", "mono", "the number is P123 [doc.pdf]")]
    assert items[0]["gold"] == "P123" and items[0]["question"] == "value?"


def test_gate_writer_flatmaps_tier_rows() -> None:
    # two questions, 1 + 2 firings → 3 rows: the writer walks every view's whole
    # attribution stream, so a run harvests the extract tiers alongside deliberate
    views = [
        _exec_view(edge_events=[{"edge": "extract@claude-haiku-4-5", "value": "P123",
                                 "confidence": 0.7, "lineage": "jk-1"}]),
        _exec_view(edge_events=[{"edge": "extract@claude-opus-4-8", "value": "X9",
                                 "confidence": 0.8, "lineage": "jk-2"},
                                {"edge": "deliberate@claude-opus-4-8", "value": "X9",
                                 "confidence": 0.9, "lineage": "dk-2"}]),
    ]
    fake = _FakeExecutorAsk(list(views))
    out: list = []
    RE.gate_paired_outcomes(None, _two_questions(), 20, fake,
                            replay={"q2-001": _row("q2-001", "P123"),
                                    "q2-002": _row("q2-002", "X9")},
                            typed_arm="executor", typed_views=out)
    rows = [e for q, v in out for e in RE.edge_outcomes(q, v, run_id="r")]
    assert [(r.question_id, r.instrument_identity["edge"], r.grade) for r in rows] == [
        ("q2-001", "extract@claude-haiku-4-5", "CORRECT"),
        ("q2-002", "extract@claude-opus-4-8", "CORRECT"),
        ("q2-002", "deliberate@claude-opus-4-8", "CORRECT")]


def test_gate_executor_arm_mid_run_down_is_loud() -> None:
    # a mid-run down stack must VOID the reading (raise, naming the question), never
    # silently convert the remaining questions into abstentions
    fake = _FakeExecutorAsk([None])
    with pytest.raises(RuntimeError, match="q2-001"):
        RE.gate_paired_outcomes(None, _questions(), 20, fake,
                                replay={"q2-001": _row("q2-001", "P123")},
                                typed_arm="executor")


def test_typed_views_accumulate_before_a_mid_run_failure() -> None:
    # the crash-salvage writer's load-bearing property (PR #63 review; the run-3 kill
    # precedent): completed questions' views are already on the out-param when a later
    # question voids the reading — their paid firings can still be graded and written.
    view = _exec_view(edge_events=[{"edge": "extract@claude-haiku-4-5", "value": "P123",
                                    "confidence": 0.7, "lineage": "jk-1"}])
    fake = _FakeExecutorAsk([view, None])
    out: list = []
    with pytest.raises(RuntimeError, match="q2-002"):
        RE.gate_paired_outcomes(None, _two_questions(), 20, fake,
                                replay={"q2-001": _row("q2-001", "P123"),
                                        "q2-002": _row("q2-002", "X9")},
                                typed_arm="executor", typed_views=out)
    ((q, v),) = out
    assert q["id"] == "q2-001" and v is view


def test_fresh_edge_rows_grades_collected_views_and_dedups_against_the_log(
        tmp_path: Path) -> None:
    # the one writer body shared by the normal post-run path and the crash-salvage
    # path: grade every collected firing, dedup against the log's already-written
    # §18.9 lineage, return (fresh, n_dup, prior).
    import life_agent.core.outcomes as O

    log = tmp_path / "outcomes.jsonl"
    q = _questions()[0]
    view = _exec_view(edge_events=[{"edge": "extract@claude-haiku-4-5", "value": "P123",
                                    "confidence": 0.7, "lineage": "jk-1"}])
    (row,) = RE.edge_outcomes(q, view, run_id="r0")
    O.append(log, row)  # a prior run already graded this artifact
    fresh, n_dup, prior = RE._fresh_edge_rows(
        [(q, view),
         (q, _exec_view(edge_events=[{"edge": "extract@claude-opus-4-8", "value": "P123",
                                      "confidence": 0.8, "lineage": "jk-2"}]))],
        run_id="r1", log=log)
    assert [r.instrument_identity["edge"] for r in fresh] == ["extract@claude-opus-4-8"]
    assert n_dup == 1
    assert len(prior) == 1


# --- --gate-loo: the run-4 held-out discipline (grouped leave-one-question-out) ----------

def _two_questions() -> list[dict[str, Any]]:
    return [*_questions(), {"id": "q2-002", "question": "other?", "answer": "X9",
                            "answer_variants": [], "fuzzy": False, "answerable": True}]


def test_gate_loo_holds_out_each_question_in_turn() -> None:
    # under loo=True the executor arm's curve fold must exclude the question being
    # asked — the hold-out is set BEFORE each call and cleared after the run, so a
    # question's decide never conditions on its own graded outcome (p3_gate precedent)
    fake = _FakeExecutorAsk([_exec_view(), _exec_view()])
    replay = {"q2-001": _row("q2-001", "P123"), "q2-002": _row("q2-002", "X9")}
    RE.gate_paired_outcomes(None, _two_questions(), 20, fake, replay=replay,
                            typed_arm="executor", loo=True)
    assert fake.holdouts_seen == ["q2-001", "q2-002"]
    assert fake.EXECUTOR_HOLD_OUT_QUESTION_ID is None


def test_gate_loo_off_never_touches_the_hold_out() -> None:
    # loo=False (the default, run 3's shape) must leave the live hold-out untouched —
    # the in-sample fold is run 3's DISCLOSED shape, not an accident of the new flag
    fake = _FakeExecutorAsk([_exec_view()])
    RE.gate_paired_outcomes(None, _questions(), 20, fake,
                            replay={"q2-001": _row("q2-001", "P123")},
                            typed_arm="executor", loo=False)
    assert fake.holdouts_seen == [None]


def test_gate_loo_resets_the_hold_out_when_the_run_voids() -> None:
    # a voided reading (mid-run down) must not leak the last question's hold-out into
    # the module state a later LIVE ask would fold under
    fake = _FakeExecutorAsk([None])
    with pytest.raises(RuntimeError, match="q2-001"):
        RE.gate_paired_outcomes(None, _questions(), 20, fake,
                                replay={"q2-001": _row("q2-001", "P123")},
                                typed_arm="executor", loo=True)
    assert fake.EXECUTOR_HOLD_OUT_QUESTION_ID is None


def test_gate_loo_on_the_family_arm_refuses() -> None:
    # the family arm folds no curves — a LOO reading over it would be a silent no-op
    # wearing the held-out label; refuse loudly
    with pytest.raises(ValueError, match="executor"):
        RE.gate_paired_outcomes(None, _questions(), 20, _FakeAsk(),
                                replay={"q2-001": _row("q2-001", "P123")}, loo=True)


def test_gate_loo_without_executor_flag_refuses(monkeypatch, capsys) -> None:
    # CLI precondition: --gate-loo without --gate-executor is refused BEFORE any state
    # is touched — there is no curve fold on the family arm to hold anything out of
    monkeypatch.setattr(sys, "argv", ["run_eval.py", "--gate", "--gate-loo"])
    assert RE.main() == 2
    assert "--gate-executor" in capsys.readouterr().out


def test_gate_loo_without_deliberate_flag_refuses(monkeypatch, capsys) -> None:
    # PR #58 review Major: with LIFE_AGENT_DELIBERATE unset, answer_via_executor never
    # folds curves at all (ask.py: transforms, curves = None, None) — a --gate-loo run
    # would complete and publish the held-out label over a TOTAL no-op, the §17.4
    # label-outruns-mechanics shape. Refused before any state is touched.
    monkeypatch.delenv("LIFE_AGENT_DELIBERATE", raising=False)
    monkeypatch.setattr(sys, "argv",
                        ["run_eval.py", "--gate", "--gate-executor", "--gate-loo"])
    monkeypatch.setattr(RE, "load_questions",
                        lambda p: (_ for _ in ()).throw(AssertionError("state touched")))
    assert RE.main() == 2
    assert "LIFE_AGENT_DELIBERATE" in capsys.readouterr().out


def test_executor_run_stats_summarise_spend_and_fired() -> None:
    views = [
        ({"id": "a"}, _exec_view(instrument="deliberate@claude-opus-4-8",
                                 cost_usd=0.31, spend_usd=0.322)),
        ({"id": "b"}, _exec_view(instrument="deliberate@claude-opus-4-8",
                                 cost_usd=0.0, spend_usd=0.0)),  # warm §18.9 replay
        ({"id": "c"}, _exec_view(spend_usd=0.004)),  # a tier fired; deliberate didn't
    ]
    s = RE.executor_run_stats(views)
    assert s["n"] == 3
    assert s["deliberate_fired"] == 2
    assert s["warm_hits"] == 1
    # spend is the TOTAL metered spend (tiers included, #67 review) — not the
    # deliberate slot's sum; question c pays without the deliberate edge ever firing
    assert s["spend_usd"] == pytest.approx(0.322 + 0.004)


# --- archive_gate_artifacts --------------------------------------------------------------

def test_archive_gate_artifacts_writes_run_id_suffixed_copies(tmp_path: Path) -> None:
    # the run-6 replayability invariant runs THROUGH the published artifacts (§14
    # pre-registration) — archiving is mechanical, not a manual ritual (missed on
    # runs 3 and 4; the PR #68 review's finding)
    (tmp_path / "report.md").write_text("# report body", encoding="utf-8")
    (tmp_path / "paired.jsonl").write_text('{"q": 1}\n', encoding="utf-8")
    (tmp_path / "run_meta.json").write_text('{"run_id": "x"}', encoding="utf-8")
    archived = RE.archive_gate_artifacts(tmp_path, run_id="gate-20260809T102018")
    assert (tmp_path / "report-gate-20260809T102018.md").read_text(
        encoding="utf-8") == "# report body"
    assert (tmp_path / "paired-gate-20260809T102018.jsonl").read_text(
        encoding="utf-8") == '{"q": 1}\n'
    # the identity sidecar archives with the reading it identifies — a run_meta left at the
    # fixed path would be clobbered by the next run, which is exactly how runs 3 and 4 lost
    # their artifacts
    assert (tmp_path / "run_meta-gate-20260809T102018.json").read_text(
        encoding="utf-8") == '{"run_id": "x"}'
    # the naming matches the pre-existing manual archives (report-gate-...md) so one
    # glob finds every run's artifacts regardless of which era archived them
    assert sorted(p.name for p in archived) == [
        "paired-gate-20260809T102018.jsonl", "report-gate-20260809T102018.md",
        "run_meta-gate-20260809T102018.json"]


def test_archive_gate_artifacts_skips_missing_files(tmp_path: Path) -> None:
    # a voided run may have written only one artifact — archive what exists, never raise
    (tmp_path / "report.md").write_text("partial", encoding="utf-8")
    archived = RE.archive_gate_artifacts(tmp_path, run_id="gate-x")
    assert [p.name for p in archived] == ["report-gate-x.md"]
