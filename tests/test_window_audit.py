"""Window-determinism audit (scripts/window_audit.py, r08 / register §6.13) — hermetic.

The defect: pkm's FTS SQL cuts with `LIMIT` before any declared order runs, so a quantised
tie block larger than the over-fetch window makes the window a nondeterministic SAMPLE. What
these tests pin is that the instrument measures what r08's frozen criteria say — the draw
comparator, the saturation census, the commit-granularity wobble comparator and its
attribution split — before it reads anything (r05's lesson: audits measure the fix, not the
defect, unless the measures are tested first).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import window_audit as WA

# --- quantisation + fingerprints ---------------------------------------------------------

def test_quantise_collapses_ulp_noise_but_not_real_gaps():
    assert WA.quantise(31.5 + 1e-12) == WA.quantise(31.5 - 1e-12)
    assert WA.quantise(31.50000001) != WA.quantise(31.50000002)


def _hit(key="a" * 8, text="chunk", score=10.0):
    return {"artifact_cache_key": key, "chunk_text": text, "score": score}


def test_fingerprint_differs_on_each_semantic_component():
    base = WA.fingerprint(_hit())
    assert WA.fingerprint(_hit(key="b" * 8)) != base
    assert WA.fingerprint(_hit(text="other")) != base
    assert WA.fingerprint(_hit(score=11.0)) != base


def test_fingerprint_equal_under_ulp_score_noise():
    assert WA.fingerprint(_hit(score=10.0 + 1e-12)) == WA.fingerprint(_hit(score=10.0))


# --- the draw comparator (Read A's verdict) ----------------------------------------------

def test_draw_verdict_stable_when_all_calls_identical():
    draws = [["f1", "f2", "f3"]] * 5
    assert WA.draw_verdict(draws) == "stable"


def test_draw_verdict_order_when_same_rows_permuted():
    assert WA.draw_verdict([["f1", "f2", "f3"], ["f2", "f1", "f3"]]) == "order"


def test_draw_verdict_set_when_rows_differ():
    assert WA.draw_verdict([["f1", "f2", "f3"], ["f1", "f2", "f4"]]) == "set"


def test_draw_verdict_single_draw_is_stable():
    assert WA.draw_verdict([["f1"]]) == "stable"


# --- the saturation census (Read B / C4) -------------------------------------------------

def test_census_no_ties_does_not_straddle():
    scores = [9.0, 8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0]
    c = WA.census(scores, window=4)
    assert c["largest_block_in_window"] == 1
    assert c["straddles"] is False


def test_census_block_inside_window_does_not_straddle():
    scores = [9.0, 8.0, 8.0, 8.0, 7.0, 6.0, 5.0, 4.0]
    c = WA.census(scores, window=6)
    assert c["largest_block_in_window"] == 3
    assert c["straddles"] is False


def test_census_boundary_block_straddles():
    # window=4: the 4th row's score (7.0) continues past the cut — the window sampled it.
    scores = [9.0, 8.0, 7.0, 7.0, 7.0, 7.0, 6.0, 5.0]
    c = WA.census(scores, window=4)
    assert c["straddles"] is True
    assert c["boundary_block"] == 4


def test_census_fewer_rows_than_window_never_straddles():
    c = WA.census([9.0, 8.0], window=4)
    assert c["straddles"] is False


def test_census_quantises_before_grouping():
    # 1e-12 apart is the SAME quantised score — one block of 4 crossing a window of 2.
    scores = [7.0, 7.0 + 1e-12, 7.0 - 1e-12, 7.0]
    c = WA.census(scores, window=2)
    assert c["straddles"] is True
    assert c["boundary_block"] == 4


# --- the commit-granularity comparator (Read C / C5) -------------------------------------

def test_wobble_census_buckets():
    draws = [
        {"q1": {"action": "report", "n_obs": 5}, "q2": {"action": "report", "n_obs": 5},
         "q3": {"action": "abstain", "n_obs": 2}, "q4": None},
        {"q1": {"action": "report", "n_obs": 5}, "q2": {"action": "report", "n_obs": 3},
         "q3": None, "q4": None},
        {"q1": {"action": "report", "n_obs": 5}, "q2": {"action": "hedge", "n_obs": 5},
         "q3": {"action": "abstain", "n_obs": 2}, "q4": None},
    ]
    c = WA.wobble_census(draws)
    assert c["stable"] == ["q1"]
    assert c["wobble"] == ["q2"]      # readable everywhere, (action, n_obs) varies
    assert c["flap"] == ["q3"]        # readable in some draws, cold in others
    assert c["never"] == ["q4"]       # cold everywhere — not evidence either way


def test_attribute_splits_wobble_by_retrieval_instability():
    a = WA.attribute(wobble=["q2", "q7", "q9"], unstable=["q7", "q9", "q50"])
    assert a["retrieval_attributable"] == ["q7", "q9"]
    assert a["residue"] == ["q2"]


def test_rows_from_dump_maps_readable_cold_and_excluded(tmp_path):
    dump = {"excluded": ["q5 (cold-at-start, deliberate)", "q6/deployed (cold-mid-loop, x)"],
            "rows": [
                {"qid": "q1", "deployed": {"action": "report", "n_obs": 5, "leader": "v"}},
                {"qid": "q2", "deployed": None},
            ]}
    p = tmp_path / "rows.json"
    p.write_text(json.dumps(dump))
    d = WA.rows_from_dump(p)
    assert d["q1"] == {"action": "report", "n_obs": 5}
    assert d["q2"] is None
    assert d["q5"] is None
    assert d["q6"] is None


# --- the cross-process merge (C3) --------------------------------------------------------

def _live_blob(fp_window, fp_top):
    surfaces = {"base": {"window": {"verdict": "stable", "draws": fp_window},
                         "top": {"verdict": "stable", "draws": fp_top},
                         "census": {"rows_probed": 8, "largest_block_in_window": 1,
                                    "boundary_block": 1, "straddles": False}},
                "expanded": {"skipped": "expansion cold"},
                "pool": {"window": {"verdict": "stable", "draws": fp_window},
                         "top": {"verdict": "stable", "draws": fp_top},
                         "census": {"rows_probed": 8, "largest_block_in_window": 1,
                                    "boundary_block": 1, "straddles": False}}}
    return {"calls": 2, "questions": {"q1": surfaces}}


def _write(tmp_path, name, blob):
    p = tmp_path / name
    p.write_text(json.dumps(blob))
    return p


def test_merge_stability_stable_across_processes(tmp_path):
    a = _write(tmp_path, "a.json", _live_blob([["f1", "f2"]] * 2, [["f1"]] * 2))
    b = _write(tmp_path, "b.json", _live_blob([["f1", "f2"]] * 2, [["f1"]] * 2))
    m = WA.merge_stability([a, b])
    assert m["unstable"] == []
    assert m["per_question"]["q1"]["base"] == "stable"
    assert m["per_question"]["q1"]["expanded"] == "skipped"


def test_merge_stability_catches_cross_process_only_instability(tmp_path):
    # Each process is internally stable but they disagree — exactly M0.5's failure shape.
    a = _write(tmp_path, "a.json", _live_blob([["f1", "f2"]] * 2, [["f1"]] * 2))
    b = _write(tmp_path, "b.json", _live_blob([["f2", "f1"]] * 2, [["f1"]] * 2))
    m = WA.merge_stability([a, b])
    assert m["unstable"] == ["q1"]
    assert m["per_question"]["q1"]["base"] == "order"


def test_merge_stability_window_set_change_outranks_stable_top(tmp_path):
    # The deduped top-k can mask a sampled window — the window layer must still convict.
    a = _write(tmp_path, "a.json", _live_blob([["f1", "f2"]] * 2, [["f1"]] * 2))
    b = _write(tmp_path, "b.json", _live_blob([["f1", "f3"]] * 2, [["f1"]] * 2))
    m = WA.merge_stability([a, b])
    assert m["per_question"]["q1"]["base"] == "set"
    assert m["unstable"] == ["q1"]


def test_compare_draws_end_to_end(tmp_path):
    d1 = {"excluded": [], "rows": [
        {"qid": "q1", "deployed": {"action": "report", "n_obs": 5}},
        {"qid": "q2", "deployed": {"action": "report", "n_obs": 5}}]}
    d2 = {"excluded": ["q2 (cold-mid-loop, x)"], "rows": [
        {"qid": "q1", "deployed": {"action": "report", "n_obs": 3}}]}
    p1, p2 = _write(tmp_path, "d1.json", d1), _write(tmp_path, "d2.json", d2)
    stab = _write(tmp_path, "s.json", {"unstable": ["q1"]})
    r = WA.compare_draws([p1, p2], stab)
    assert r["wobble"] == ["q1"] and r["flap"] == ["q2"]
    assert r["retrieval_attributable"] == ["q1"] and r["residue"] == []
