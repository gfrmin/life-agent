"""r48 — hermetic pins for the re-earn instrument's load-bearing predicates (J7).

Nothing here spawns an engine: these pin the pure functions that decide what the reading
MEANS — the census dedup, the deployed-dataclass reconstruction, the frozen sweep
parameters, and the flip detection — so a mutation to any of them fails a test.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "scripts")

from membrane import reearn_audit as RA

from life_agent.membrane import categorical as CAT


def _row(k: int, codes: list[int], **kw: object) -> str:
    summary = {
        "k": k, "obs_codes": codes, "n_obs": len(codes), "n_obs_unmapped": 0,
        "daemon_map_index": 0, "era_split": False, "owner_scoped": True,
        "grow_pass": False,
    }
    summary.update(kw)  # type: ignore[arg-type]
    return json.dumps({"kind": "cat", "summary": summary, "action": "gather"})


def test_corpus_is_a_census_over_distinct_summaries_with_multiplicity(
    tmp_path: Path,
) -> None:
    """The dedup must COVER every row, not sample them — the multiplicity is what
    frequency-weighted statements are built from."""
    log = tmp_path / "shadow.jsonl"
    log.write_text("\n".join([
        _row(2, [1]), _row(2, [1]), _row(3, [1, 2]), _row(2, [1]),
        json.dumps({"kind": "decide", "summary": {"k": 9}}),   # not a cat row
        "{ not json",                                          # tolerated
    ]) + "\n")
    corpus = RA.load_cat_summaries(log)
    assert len(corpus) == 2
    assert sum(w for _, w in corpus) == 4
    weights = {rec["k"]: w for rec, w in corpus}
    assert weights == {2: 3, 3: 1}


def test_non_cat_rows_never_enter_the_corpus(tmp_path: Path) -> None:
    log = tmp_path / "shadow.jsonl"
    log.write_text(json.dumps({"kind": "decide", "summary": {"k": 2}}) + "\n")
    assert RA.load_cat_summaries(log) == []


def test_summary_reconstruction_is_field_for_field_the_deployed_dataclass() -> None:
    """The replay's input must be the RECORDED one — a re-derivation would measure
    something the ledger never saw."""
    rec = {"k": 3, "obs_codes": [1, 3, 1], "n_obs": 3, "n_obs_unmapped": 2,
           "daemon_map_index": 1, "era_split": True, "owner_scoped": False,
           "grow_pass": True}
    s = RA.summary_from_record(rec)
    assert isinstance(s, CAT.CatSummary)
    assert (s.k, s.obs_codes, s.n_obs) == (3, (1, 3, 1), 3)
    assert (s.n_obs_unmapped, s.daemon_map_index) == (2, 1)
    assert (s.era_split, s.owner_scoped, s.grow_pass) == (True, False, True)


def test_summary_reconstruction_carries_a_null_daemon_index() -> None:
    s = RA.summary_from_record({"k": 2, "obs_codes": [1], "n_obs": 1,
                                "daemon_map_index": None})
    assert s.daemon_map_index is None


def test_null_cap_is_the_engines_declared_constant() -> None:
    """R-D23's cap is `1/(K-1)`, quoted for J4's comparison and never recomputed into a
    decision. k=1 has no competing atom, so the cap cannot bind."""
    assert RA.null_cap(3) == pytest.approx(0.5)
    assert RA.null_cap(11) == pytest.approx(0.1)
    assert RA.null_cap(1) == float("inf")


def test_the_sweep_parameters_are_the_frozen_ones() -> None:
    """J3 froze the k set and the observation bound in the pre-registration; a silent
    change to either would make the 'no flip within the bound' reading mean something
    the pre-registration did not license."""
    assert RA.SWEEP_KS == (1, 2, 3, 5, 10)
    assert RA.SWEEP_MAX_OBS == 40


def test_sweep_codes_are_monotone_support_for_one_candidate() -> None:
    assert RA.sweep_codes(5, 0) == ()
    assert RA.sweep_codes(5, 3) == (1, 1, 1)
    assert all(c == 1 for c in RA.sweep_codes(9, 7))
