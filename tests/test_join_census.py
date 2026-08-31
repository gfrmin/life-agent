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
