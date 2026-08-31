"""r34 — the wire census over the value-join.

The lever changes `bridge/server._lattice_join`, which runs BRIDGE-SIDE: the collapse
fixtures record `/probe/*` as http exchanges with frozen responses, so a replay serves the
recorded answer and never runs the changed code (pre-registration §2b). The census is the
instrument that CAN read it — it lifts `(value, candidates, allow_new)` off the recorded wire
and replays them through the DEPLOYED join, so running it on two trees yields the lever's
firing surface exhaustively.

It imports `_lattice_join`; it never re-implements it (RULINGS M-7).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import join_census as JC

from life_agent.bridge import server as BR
from life_agent.core import decisions as DEC


def test_the_census_binds_the_deployed_join() -> None:
    """M-7: the constant it prices is imported, never re-spelled."""
    assert JC.engine_join is BR._lattice_join


def _fixture(tmp_path: Path, exchanges: list[dict]) -> Path:
    p = tmp_path / "fx-q9-999.json"
    p.write_text(json.dumps({"fixture_id": "fx-q9-999", "question_id": "q9-999",
                             "wire": exchanges}), encoding="utf-8")
    return tmp_path


def test_lifts_probe_exchanges_off_the_wire(tmp_path: Path) -> None:
    root = _fixture(tmp_path, [
        {"seam": "skin", "request": {}, "response": {}},
        {"seam": "http", "request": {"url": "/retrieve", "payload": {}}, "response": {}},
        {"seam": "http",
         "request": {"url": "/probe/deliberate",
                     "payload": {"candidates": ["P123"], "allow_new": True}},  # PII-OK: synthetic
         "response": {"value": "P123", "new_candidate": None}},
    ])
    rows = JC.census(root)
    assert len(rows) == 1, "only /probe/* exchanges carry a join"
    assert rows[0]["url"] == "/probe/deliberate"
    assert rows[0]["question_id"] == "q9-999"


def test_replays_the_join_and_records_its_verdict(tmp_path: Path) -> None:
    root = _fixture(tmp_path, [
        {"seam": "http",
         "request": {"url": "/probe/deliberate",
                     "payload": {"candidates": ["Q777", "P123"], "allow_new": True}},
         "response": {"value": "  p123 ", "new_candidate": None}},   # PII-OK: synthetic ids
    ])
    row = JC.census(root)[0]
    assert (row["idx"], row["minted"]) == (1, None), "whitespace+case already join under both keys"


def test_a_missing_value_is_skipped_not_guessed(tmp_path: Path) -> None:
    root = _fixture(tmp_path, [
        {"seam": "http",
         "request": {"url": "/probe/corroborate", "payload": {"candidates": ["P123"]}},
         "response": {"value": None}},
    ])
    assert JC.census(root) == [], "an exchange with no value carries no join to replay"


def test_diff_reports_only_changed_verdicts() -> None:
    old = [{"key": "a", "idx": None, "minted": "X"}, {"key": "b", "idx": 0, "minted": None}]
    new = [{"key": "a", "idx": 1, "minted": None}, {"key": "b", "idx": 0, "minted": None}]
    d = JC.diff(old, new)
    assert [x["key"] for x in d] == ["a"]
    assert d[0]["old"] == {"idx": None, "minted": "X", "joined_key": None}
    assert d[0]["new"] == {"idx": 1, "minted": None, "joined_key": None}


def test_diff_refuses_misaligned_arms() -> None:
    """Two arms must be the same census over the same corpus, or the diff is meaningless."""
    import pytest
    with pytest.raises(ValueError, match="arms disagree"):
        JC.diff([{"key": "a", "idx": 0, "minted": None}],
                [{"key": "z", "idx": 0, "minted": None}])


def test_c1_merge_only_classifies_each_difference() -> None:
    """C1's shape test: mint→join is the licensed direction; anything else is a violation."""
    assert JC.c1_violation({"old": {"idx": None, "minted": "X"},
                            "new": {"idx": 2, "minted": None}}) is None
    assert JC.c1_violation({"old": {"idx": 1, "minted": None},
                            "new": {"idx": 2, "minted": None}}) == "join→different-join"
    assert JC.c1_violation({"old": {"idx": 1, "minted": None},
                            "new": {"idx": None, "minted": "X"}}) == "join→mint"


# --- the C1 correction (see r34's chronology): identity, not index --------------------


def test_a_census_row_carries_the_joined_candidates_declared_key() -> None:
    """C1 must compare WHICH ANSWER was joined, not which slot. The lever's whole effect is
    to stop minting, which SHORTENS the lattice — so indices are not comparable across arms
    by construction, and a row must carry the declared key to be diffable at all."""
    import life_agent.core.lookup as LK

    rows = [{"candidates": ["Volume 358, 2008", "358(14)"], "value": "358 (14)"}]
    key = JC.joined_key(*JC.engine_join(rows[0]["value"], rows[0]["candidates"], True),
                        rows[0]["candidates"])
    assert key == LK._candidate_key("358(14)")


def test_joined_key_of_a_mint_is_the_minted_values_key() -> None:
    import life_agent.core.lookup as LK

    idx, minted = JC.engine_join("Z777", ["P123"], True)      # PII-OK: synthetic ids
    assert minted == "Z777"
    assert JC.joined_key(idx, minted, ["P123"]) == LK._candidate_key("Z777")


def test_joined_key_of_no_join_is_none() -> None:
    assert JC.joined_key(None, None, ["P123"]) is None        # PII-OK: synthetic id


def test_c1_identity_licenses_a_reindexed_join_of_the_same_answer() -> None:
    """The case that failed C1-as-frozen: the old arm minted at slot 3, the new arm joins
    slot 1, and both slots carry ONE declared key. Same answer, different slot — the merge
    showing up downstream, not a semantic change."""
    assert JC.c1_identity_violation(
        {"old": {"joined_key": "35814"}, "new": {"joined_key": "35814"}}) is None


def test_c1_identity_still_kills_a_real_change_of_answer() -> None:
    assert JC.c1_identity_violation(
        {"old": {"joined_key": "35814"}, "new": {"joined_key": "3582008"}}
    ) == "joined a DIFFERENT answer"
    assert JC.c1_identity_violation(
        {"old": {"joined_key": "35814"}, "new": {"joined_key": None}}
    ) == "joined answer became no-join"


# --- r37: the live half ------------------------------------------------------------------


def _tap_row(q: str, fires: bool, *, url: str = "/probe/deliberate") -> dict:
    dep = {"idx": 0, "minted": None}
    cf = {"idx": 1, "minted": "HKD 12,345.67"} if fires else {"idx": 0, "minted": None}
    return {"question_id": DEC.question_id(q), "url": url, "fires": fires,
            "allow_new": True, "n_candidates": 1,
            "value": "HKD 12,345.67", "candidates": ["HKD 12345.67"],  # PII-OK: synthetic
            "deployed": dep, "counterfactual": cf}


def _tap_log(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "join-tap.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return p


def test_no_second_question_hash_exists_on_either_side(tmp_path: Path) -> None:
    """L3 aligns the two surfaces BY QUESTION. Both sides key on `decisions.question_id` —
    the one declared derivation — so there is nothing to keep in step (M-7). The recorded
    side does not even compute it: the fixtures already carry it.

    Proved by AST and by behaviour, never by a source substring — `_join_tap` must CALL
    `DEC.question_id`, and no private digest helper may exist on either side."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import _guard_ast as G

    assert not hasattr(JC, "_question_digest") and not hasattr(BR, "_question_digest")
    assert G.calls(BR._join_tap, "question_id"), (
        "the tap must derive its key from decisions.question_id, not spell a hash itself")


def test_live_reads_the_tap_into_the_census_row_shape(tmp_path: Path) -> None:
    rows = JC.live(_tap_log(tmp_path, [_tap_row("a", True), _tap_row("b", False)]))
    assert len(rows) == 2
    assert sum(r["fires"] for r in rows) == 1
    assert rows[0]["joined_key"] is not None, "a mint's joined key is the minted value's"
    assert {"key", "question_id", "url", "idx", "minted",
            "counterfactual", "fires"} <= set(rows[0])


def test_superset_names_a_recorded_firing_absent_live(tmp_path: Path) -> None:
    """L3's kill direction. A firing the cassettes found but the live run did not means the
    two instruments disagree about the deployed rule."""
    recorded = [{"question_id": DEC.question_id("a"), "fires": True},
                {"question_id": DEC.question_id("b"), "fires": False}]
    observed = JC.live(_tap_log(tmp_path, [_tap_row("a", False), _tap_row("b", True)]))
    res = JC.superset(recorded, observed)
    assert res["missing_live"] == [DEC.question_id("a")]
    assert res["new_live"] == [DEC.question_id("b")]


def test_superset_passes_when_the_live_surface_is_strictly_larger(tmp_path: Path) -> None:
    """The registered expectation: the live surface is LARGER. That is a pass, and the
    growth is reported rather than swallowed."""
    recorded = [{"question_id": DEC.question_id("a"), "fires": True}]
    observed = JC.live(_tap_log(tmp_path, [_tap_row("a", True), _tap_row("b", True)]))
    res = JC.superset(recorded, observed)
    assert res["missing_live"] == []
    assert res["shared_questions"] == 1, "b is not shared — it is not held against either arm"


def test_superset_reports_an_empty_shared_set_rather_than_passing(tmp_path: Path) -> None:
    """G-3: a check whose universe is empty must not read as a pass."""
    recorded = [{"question_id": DEC.question_id("a"), "fires": True}]
    observed = JC.live(_tap_log(tmp_path, [_tap_row("z", True)]))
    assert JC.superset(recorded, observed)["shared_questions"] == 0


def test_equivalence_runs_the_population_through_both_flag_states(tmp_path: Path) -> None:
    """GD-7's added verifier. Every recorded triple, flag ON and OFF, byte-identical."""
    root = _fixture(tmp_path, [
        {"seam": "http",
         "request": {"url": "/probe/deliberate",
                     "payload": {"candidates": ["HKD 12345.67"], "allow_new": True}},
         "response": {"value": "HKD 12,345.67"}},          # PII-OK: synthetic amount
        {"seam": "http",
         "request": {"url": "/probe/corroborate",
                     "payload": {"candidates": ["Q777", "P123"], "allow_new": True}},
         "response": {"value": "  p123 "}},                 # PII-OK: synthetic id
    ])
    res = JC.equivalence(root)
    assert res == {"population": 2, "divergences": 0, "tap_rows_written": 2, "ok": True}


def test_equivalence_fails_on_an_empty_population(tmp_path: Path) -> None:
    """G-3's universe clause: nothing checked is not the same as nothing wrong."""
    res = JC.equivalence(tmp_path)
    assert res["ok"] is False and res["population"] == 0


def test_the_census_disarms_the_tap_before_it_runs(tmp_path: Path,
                                                   monkeypatch) -> None:
    """The census calls the deployed join. An armed tap would record the INSTRUMENT's own
    calls into the very surface it is measuring — r29's stream-contamination lesson, one
    layer down."""
    import os
    monkeypatch.setenv(BR._JOIN_TAP_ENV, "1")
    root = _fixture(tmp_path, [
        {"seam": "http",
         "request": {"url": "/probe/deliberate",
                     "payload": {"candidates": ["P123"], "allow_new": True}},
         "response": {"value": "P123"}},                    # PII-OK: synthetic id
    ])
    JC.main([str(root)])
    assert os.environ.get(BR._JOIN_TAP_ENV) is None


def test_census_rows_carry_the_firing_verdict(tmp_path: Path) -> None:
    """One pass reads both arms since r37 parameterised the join's identity — the census no
    longer needs two trees to say where the lever fires."""
    root = _fixture(tmp_path, [
        {"seam": "http",
         "request": {"url": "/probe/deliberate", "payload": {
             "question": "what is the amount?",             # PII-OK: synthetic question
             "candidates": ["HKD 12345.67"], "allow_new": True}},
         "response": {"value": "HKD 12,345.67"}},           # PII-OK: synthetic amount
    ])
    row = JC.census(root)[0]
    assert row["fires"] is True
    assert row["counterfactual"] == {"idx": 1, "minted": "HKD 12,345.67"}  # PII-OK
    assert row["question_id"] == "q9-999", (
        "the recorded side already carries the declared id — it computes no hash of its own")


def test_equivalence_actually_detects_a_divergence(tmp_path: Path, monkeypatch) -> None:
    """The comparison itself, verified. ON and OFF never diverge on the real join — which
    is the claim — so the only way to prove the check CAN fail is to inject a join that
    behaves differently under the flag and require it to be caught."""
    import os

    def flaky(value, candidates, allow_new, *, key=None):
        return (0, None) if os.environ.get(BR._JOIN_TAP_ENV) else (None, None)

    monkeypatch.setattr(JC, "engine_join", flaky)
    root = _fixture(tmp_path, [
        {"seam": "http",
         "request": {"url": "/probe/deliberate",
                     "payload": {"candidates": ["P123"], "allow_new": True}},
         "response": {"value": "P123"}},                    # PII-OK: synthetic id
    ])
    res = JC.equivalence(root)
    assert res["divergences"] == 1 and res["ok"] is False


def test_equivalence_restores_the_module_state_it_borrowed(tmp_path: Path) -> None:
    """`equivalence` arms the tap and points its declared path at a tempdir. Both are module
    state: left pointed at a deleted directory, the tap is silently disarmed for everything
    later in the process — a diagnostic that quietly stops recording is worse than one that
    was never armed."""
    import os

    from life_agent.core import config as CFG

    before = CFG.JOIN_TAP_LOG
    root = _fixture(tmp_path, [
        {"seam": "http",
         "request": {"url": "/probe/deliberate",
                     "payload": {"candidates": ["P123"], "allow_new": True}},
         "response": {"value": "P123"}},                    # PII-OK: synthetic id
    ])
    JC.equivalence(root)
    assert before == CFG.JOIN_TAP_LOG
    assert os.environ.get(BR._JOIN_TAP_ENV) is None


def test_one_walk_of_the_wire_feeds_both_readers(tmp_path: Path) -> None:
    """`census` and the equivalence population are the SAME population by construction. Two
    walks would be two definitions of 'what was recorded' — which is the defect r37 exists to
    repair, one level up."""
    root = _fixture(tmp_path, [
        {"seam": "http",
         "request": {"url": "/probe/deliberate",
                     "payload": {"candidates": ["P123"], "allow_new": True}},
         "response": {"value": "P123"}},                    # PII-OK: synthetic id
        {"seam": "http",                                    # no value: not a join
         "request": {"url": "/probe/corroborate", "payload": {"candidates": []}},
         "response": {"value": ""}},
    ])
    assert len(JC.census(root)) == len(list(JC.recorded_joins(root))) == 1
    assert JC.equivalence(root)["population"] == 1
