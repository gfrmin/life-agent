"""r29's instrument — the answer-shape census.

The census classifies questions on two axes from surface form alone, splits the harvest's
eval-derived rows from the owner-origin ones, and prices the grow actuators' hand-set cold
priors against the realised gather-outcome stream. It reads; it adopts nothing.

The criteria these tests pin are frozen in ``docs/unification/reports/r29-answer-shape-census.md``
(committed before this file existed): C3 the conservative default, C4 the population split,
C5 the measured agreement, C7 the deployed constants read end to end, C8 the flip set.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "scripts" / "answer_shape_census.py"


def _load():
    spec = importlib.util.spec_from_file_location("answer_shape_census", _SRC)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["answer_shape_census"] = mod
    spec.loader.exec_module(mod)
    return mod


AC = _load()


# --- C3: the conservative default -------------------------------------------------------

def test_an_unmatched_question_falls_to_the_conservative_default() -> None:
    """No cue ⇒ exact + verbatim — the shape under which today's design is adequate."""
    assert AC.classify("What is the reference code on the form?") == {
        "space": "exact", "provenance": "verbatim"}


def test_the_default_is_the_strict_shape_on_both_axes() -> None:
    for text in ("Who signed it?", "Where is the office?", "What colour is it?"):
        c = AC.classify(text)
        assert (c["space"], c["provenance"]) == ("exact", "verbatim"), text


# --- axis 1: answer space, in the frozen precedence order --------------------------------

def test_quantity_cue_matches_a_magnitude_question() -> None:
    assert AC.answer_space("How many rows were surveyed?") == "quantity"
    assert AC.answer_space("What is the total amount shown?") == "quantity"


def test_set_cue_beats_a_quantity_cue() -> None:
    """Precedence is threshold > set > quantity > exact; a question carrying both cues
    takes the earlier rule, so the ordering is observable, not incidental."""
    assert AC.answer_space("List the total number of each entry") == "set"


def test_threshold_cue_beats_a_set_cue() -> None:
    assert AC.answer_space("List the entries with more than 5 items") == "threshold"


def test_a_yes_no_form_needs_a_numeric_token_to_read_as_threshold() -> None:
    assert AC.answer_space("Did the balance exceed 400?") == "threshold"
    assert AC.answer_space("Did the office move?") == "exact"


# --- axis 2: truth provenance ------------------------------------------------------------

def test_computed_requires_an_explicit_aggregation_marker() -> None:
    """A bare 'total' adjacent to a recorded field is NOT computed — that is the
    conservative default doing its work, and the reason axis 2 is not axis 1 restated."""
    assert AC.truth_provenance("What is the total figure listed on the record?") == "verbatim"
    assert AC.truth_provenance(
        "How much did they pay in total during that year?") == "computed"
    assert AC.truth_provenance("What did I earn across all payers?") == "computed"


def test_the_two_axes_are_independent() -> None:
    c = AC.classify("What is the total figure listed on the record?")
    assert (c["space"], c["provenance"]) == ("quantity", "verbatim")


# --- C4: the population split ------------------------------------------------------------

def test_every_eval_derived_ask_is_removed_from_the_owner_population() -> None:
    gate = [{"id": "g-1", "question": "What is the code?"}]
    asks = [{"question_id": "a", "question": "  what IS the code?  "},
            {"question_id": "b", "question": "Where do I live?"}]
    split = AC.split_populations(gate, asks)
    assert [r["question_id"] for r in split["eval_derived"]] == ["a"]
    assert [r["question_id"] for r in split["owner_origin"]] == ["b"]


def test_the_split_is_exhaustive() -> None:
    gate = [{"id": "g-1", "question": "Q one"}]
    asks = [{"question_id": str(i), "question": q}
            for i, q in enumerate(["Q one", "Q two", "Q three"])]
    split = AC.split_populations(gate, asks)
    assert len(split["eval_derived"]) + len(split["owner_origin"]) == len(asks)


# --- C5: measured agreement, with the direction of every disagreement --------------------

def test_agreement_reports_the_direction_of_every_disagreement() -> None:
    manual = [{"id": "1", "pop": "owner", "space": "quantity", "prov": "computed"},
              {"id": "2", "pop": "owner", "space": "exact", "prov": "verbatim"}]
    auto = {"1": {"space": "exact", "provenance": "verbatim"},
            "2": {"space": "exact", "provenance": "verbatim"}}
    rep = AC.agreement(manual, auto)
    assert rep["space"]["n"] == 2 and rep["space"]["agree"] == 1
    assert rep["provenance"]["agree"] == 1
    assert ("quantity", "exact") in {(d["manual"], d["auto"])
                                     for d in rep["space"]["disagreements"]}
    assert ("computed", "verbatim") in {(d["manual"], d["auto"])
                                        for d in rep["provenance"]["disagreements"]}


def test_agreement_below_the_bar_is_flagged_so_counts_publish_as_bounds() -> None:
    manual = [{"id": str(i), "pop": "owner", "space": "quantity",
               "prov": "verbatim"} for i in range(10)]
    auto = {str(i): {"space": "exact", "provenance": "verbatim"} for i in range(10)}
    rep = AC.agreement(manual, auto)
    assert rep["space"]["bounds_only"] is True
    assert rep["provenance"]["bounds_only"] is False


# --- read 2: the structural-abstention prediction ----------------------------------------

def test_abstention_rate_reads_decided_rows_only() -> None:
    rows = [{"question_id": "1", "decided": True, "chosen_action": "abstain"},
            {"question_id": "2", "decided": True, "chosen_action": "report"},
            {"question_id": "3", "decided": False, "chosen_action": None}]
    labels = {"1": {"space": "quantity", "provenance": "computed"},
              "2": {"space": "exact", "provenance": "verbatim"},
              "3": {"space": "quantity", "provenance": "computed"}}
    out = AC.abstention_by_provenance(rows, labels)
    assert out["computed"] == {"n": 1, "abstained": 1, "rate": 1.0}
    assert out["verbatim"] == {"n": 1, "abstained": 0, "rate": 0.0}
    assert out["undecided"] == 1


# --- C7: read 3 reads the deployed constants end to end ----------------------------------

def test_the_grow_gap_probes_are_exactly_the_deployed_actuators() -> None:
    from life_agent.core import pricing as PRC
    rows = AC.grow_prior_gap([], PRC.GROW_ACTUATORS)
    assert {r["probe"] for r in rows} == {str(a["probe"]) for a in PRC.GROW_ACTUATORS}


def test_the_grow_gap_prices_the_prior_against_the_realised_stream() -> None:
    actuators = [{"probe": "p", "cost": 0.01, "alpha0": 3.0, "beta0": 7.0}]
    stream = [{"probe": "p", "ctx": ["none", "hi", "none"], "recovered": True},
              {"probe": "p", "ctx": ["none", "hi", "none"], "recovered": False},
              {"probe": "p", "ctx": ["none", "hi", "none"], "recovered": False},
              {"probe": "p", "ctx": ["none", "hi", "none"], "recovered": False}]
    row = AC.grow_prior_gap(stream, actuators)[0]
    assert row["cold_prior_mean"] == pytest.approx(0.30)
    assert row["realised_rate"] == pytest.approx(0.25)
    assert row["n"] == 4
    # the warm posterior mean is the cold prior folded with the counts: 4/(10+4)
    assert row["warm_posterior_mean"] == pytest.approx(4 / 14)


def test_the_census_does_not_retype_a_grow_prior() -> None:
    """C7's mutation guard. The forbidden-literal universe is derived from the DEPLOYED
    table itself (guards.md entry 1: a checker whose universe comes from anywhere else
    misses exactly the site that drifted)."""
    from life_agent.core import pricing as PRC
    src = _SRC.read_text(encoding="utf-8")
    forbidden = {repr(a[k]) for a in PRC.GROW_ACTUATORS for k in ("cost", "alpha0", "beta0")}
    assert forbidden, "the deployed actuator table is empty — the guard would be vacuous"
    for lit in sorted(forbidden):
        assert lit not in src, f"the census retypes a deployed grow constant: {lit}"


# --- C8: the flip set, per row, beside the aggregate rate --------------------------------

def test_the_flip_set_pairs_by_question_id_and_names_direction() -> None:
    a = [{"question_id": "q1", "censored": False, "typed": {"action": "abstain", "cost_usd": 0.1}},
         {"question_id": "q2", "censored": False, "typed": {"action": "report", "cost_usd": 0.2}}]
    b = [{"question_id": "q1", "censored": False, "typed": {"action": "report", "cost_usd": 0.01}},
         {"question_id": "q2", "censored": False, "typed": {"action": "report", "cost_usd": 0.02}}]
    out = AC.flip_set(a, b)
    assert out["n_rows"] == 2
    assert [f["question_id"] for f in out["flips"]] == ["q1"]
    assert out["flips"][0]["from_b"] == "report" and out["flips"][0]["to_a"] == "abstain"
    assert out["mean_spend_a"] == pytest.approx(0.15)
    assert out["mean_spend_b"] == pytest.approx(0.015)


def test_the_flip_set_refuses_archives_that_do_not_cover_the_same_questions() -> None:
    a = [{"question_id": "q1", "censored": False, "typed": {"action": "abstain", "cost_usd": 0.1}}]
    b = [{"question_id": "q2", "censored": False, "typed": {"action": "report", "cost_usd": 0.1}}]
    with pytest.raises(ValueError, match="same question"):
        AC.flip_set(a, b)


def test_the_warm_fold_is_cross_checked_against_the_deployed_one() -> None:
    """C7's second half. The census folds counts itself (to price them per context), so it
    must AGREE with ``gather_outcomes.warm_counts`` — the deployed fold — and fail loud when
    it does not. A census that quietly re-implements the fold it prices is r05's defect."""
    stream = [{"probe": "p", "ctx": ["none", "hi", "none"], "recovered": True},
              {"probe": "p", "ctx": ["none", "hi", "none"], "recovered": False}]
    deployed = {"contexts": [{"ctx": ["none", "hi", "none"], "n1": 1, "n0": 1}]}
    AC.cross_check_warm_fold(stream, deployed, probe="p")  # agrees ⇒ silent
    drifted = {"contexts": [{"ctx": ["none", "hi", "none"], "n1": 2, "n0": 1}]}
    with pytest.raises(ValueError, match="warm fold"):
        AC.cross_check_warm_fold(stream, drifted, probe="p")


def test_every_published_block_is_json_serialisable() -> None:
    """The census's whole point is a written record; a block that cannot be serialised is a
    read that never lands. (Tuple keys in the direction tallies were exactly this defect.)"""
    import json
    manual = [{"id": "1", "pop": "owner", "space": "quantity", "prov": "computed"}]
    auto = {"1": {"space": "exact", "provenance": "verbatim"}}
    a = [{"question_id": "q1", "censored": False, "typed": {"action": "abstain", "cost_usd": 0.1}}]
    b = [{"question_id": "q1", "censored": False, "typed": {"action": "report", "cost_usd": 0.01}}]
    json.dumps({"agreement": AC.agreement(manual, auto), "flip": AC.flip_set(a, b)})


# --- read 3, extension: attributing the stream to the runs that wrote it -----------------
# Added AFTER the first reading, disclosed in the report's chronology: the first pass read
# the run windows off the run_id (which is LOCAL time) instead of run_meta's `created_at`
# (UTC), and so placed every gate run 8 hours away from its own rows.

def test_a_run_window_is_read_from_the_records_not_the_run_id() -> None:
    """The run_id's timestamp is local; `created_at` is UTC. A window derived from the id
    is wrong by the machine's offset, which is exactly the defect this pins."""
    meta = {"run_id": "gate-20260826T025059", "created_at": "2026-08-25T18:51:00Z"}
    label, start, end = AC.run_window(meta, "run_id=gate-20260826T025059  elapsed=100.0s  draws=1")
    assert label == "gate-20260826T025059"
    assert start.isoformat() == "2026-08-25T18:51:00+00:00"
    assert (end - start).total_seconds() == 100.0


def test_a_report_without_an_elapsed_is_refused() -> None:
    with pytest.raises(ValueError, match="elapsed"):
        AC.run_window({"run_id": "r", "created_at": "2026-08-25T18:51:00Z"}, "no timing here")


def test_window_attribution_splits_the_stream_by_who_wrote_it() -> None:
    def row(ts: str, rec: bool) -> dict[str, object]:
        return {"tx_time": ts, "probe": "p", "ctx": ["a"], "recovered": rec}
    stream = [row("2026-08-25T18:00:00+00:00", False), row("2026-08-25T18:51:30+00:00", True),
              row("2026-08-25T18:52:00+00:00", True), row("2026-08-25T20:00:00+00:00", False)]
    meta = {"run_id": "R", "created_at": "2026-08-25T18:51:00Z"}
    out = AC.window_attribution(stream, [AC.run_window(meta, "elapsed=120.0s")])
    assert out["windows"]["R"]["n"] == 2
    assert out["windows"]["R"]["n_recovered"] == 2
    assert out["windows"]["R"]["rate"] == pytest.approx(1.0)
    assert out["before_first"]["n"] == 1
    assert out["before_first"]["rate"] == pytest.approx(0.0)
    assert out["outside"]["n"] == 1


def test_window_attribution_reports_the_pre_window_rate_per_probe() -> None:
    """The rate a decision SAW is the rate before its own run wrote to the stream."""
    def row(ts: str, rec: bool) -> dict[str, object]:
        return {"tx_time": ts, "probe": "q", "ctx": ["a"], "recovered": rec}
    stream = [row("2026-08-25T10:00:00+00:00", True), row("2026-08-25T10:00:01+00:00", False),
              row("2026-08-25T18:51:30+00:00", True)]
    meta = {"run_id": "R", "created_at": "2026-08-25T18:51:00Z"}
    out = AC.window_attribution(stream, [AC.run_window(meta, "elapsed=120.0s")])
    assert out["before_first"]["by_probe"]["q"] == {"n": 2, "n_recovered": 1, "rate": 0.5}


def test_the_flip_set_publishes_each_arm_assert_count_beside_the_flips() -> None:
    """C8: a per-row flip and an aggregate answer rate are different quantities, and the
    report must carry both so neither can stand in for the other."""
    a = [{"question_id": "q1", "censored": False, "typed": {"action": "abstain", "cost_usd": 0.0}},
         {"question_id": "q2", "censored": False, "typed": {"action": "hedge", "cost_usd": 0.0}}]
    b = [{"question_id": "q1", "censored": False, "typed": {"action": "report", "cost_usd": 0.0}},
         {"question_id": "q2", "censored": False, "typed": {"action": "report", "cost_usd": 0.0}}]
    out = AC.flip_set(a, b)
    assert out["asserts_a"] == 1 and out["asserts_b"] == 2
    assert out["answer_rate_a"] == pytest.approx(0.5)
    assert out["answer_rate_b"] == pytest.approx(1.0)
