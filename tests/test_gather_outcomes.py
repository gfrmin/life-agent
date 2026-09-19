"""The gather-outcome instrumentation + the grow menu (core/gather_outcomes.py).

The B half's data leg (docs/ask-as-connection.md §4 caveat 2): every enacted grow actuator
logs one (probe, sensor-context, recovered) row — the structure-observe stream the daemon's
gather structure-BMA warm-seeds from (`warm_counts` → `reconstruct_structure_prior_from_data`,
exact by order-independence). Sensors are BUCKETED strings (the structure-BMA needs finite
value-sets); `recovered` is the honest v0 proxy — the grown question ended in a report through
the exact 0-CW terminal threshold (verdict-joined refinement later). The menu (`GROW_ACTUATORS`)
is data: cold g-priors are hand-set Beta means (the demoted g-prior), sharpened by the counts.
"""
from __future__ import annotations

import json
from pathlib import Path

from life_agent.core import gather_outcomes as GO


def test_sensor_vocabulary_is_the_declared_bucketed_features() -> None:
    # The wire vocabulary: names + per-feature value-sets, in one declared order (the
    # daemon's context_from_features errors on drift — this is the single source).
    names = [n for n, _ in GO.SENSOR_FEATURES]
    assert names == ["extracted", "p_none", "indeterminate"]
    for _, values in GO.SENSOR_FEATURES:
        assert len(values) >= 2


def test_sensors_bucket_nothing_extracted_as_missing() -> None:
    s = GO.sensors_from(candidates=[], credences=[], p_none=None, indeterminate=0)
    assert s == {"extracted": "none", "p_none": "hi", "indeterminate": "none"}


def test_sensors_bucket_none_as_map_hypothesis_hi() -> None:
    # p_none >= the best present candidate ⇒ "hi" — the old _truth_likely_missing gate,
    # demoted to a FEATURE the gather BMA conditions on (the ruling: no control-flow branch).
    s = GO.sensors_from(candidates=["a", "b"], credences=[0.3, 0.2], p_none=0.5,
                        indeterminate=2)
    assert s == {"extracted": "some", "p_none": "hi", "indeterminate": "some"}


def test_sensors_bucket_confident_leader_lo() -> None:
    s = GO.sensors_from(candidates=["a"], credences=[0.9], p_none=0.1, indeterminate=0)
    assert s["p_none"] == "lo"


def test_sensors_bucket_mid_between() -> None:
    s = GO.sensors_from(candidates=["a", "b"], credences=[0.5, 0.2], p_none=0.3,
                        indeterminate=0)
    assert s["p_none"] == "mid"


def test_every_sensor_value_is_a_declared_bucket() -> None:
    vocab = dict(GO.SENSOR_FEATURES)
    for s in (GO.sensors_from(candidates=[], credences=[], p_none=None, indeterminate=0),
              GO.sensors_from(candidates=["a"], credences=[0.4], p_none=0.4, indeterminate=1)):
        for name, value in s.items():
            assert value in vocab[name]


def test_append_and_fold_warm_counts(tmp_path: Path) -> None:
    log = tmp_path / "gather_outcomes.jsonl"
    ctx_a = {"extracted": "some", "p_none": "hi", "indeterminate": "none"}
    ctx_b = {"extracted": "none", "p_none": "hi", "indeterminate": "none"}
    GO.append_outcome(log, "re_extract_strong", ctx_a, recovered=True)
    GO.append_outcome(log, "re_extract_strong", ctx_a, recovered=True)
    GO.append_outcome(log, "re_extract_strong", ctx_a, recovered=False)
    GO.append_outcome(log, "re_extract_strong", ctx_b, recovered=False)
    GO.append_outcome(log, "retrieve_expand", ctx_b, recovered=True)  # a different actuator
    wc = GO.warm_counts(log, "re_extract_strong")
    assert wc is not None
    by_ctx = {tuple(e["ctx"]): (e["n1"], e["n0"]) for e in wc["contexts"]}
    assert by_ctx[("some", "hi", "none")] == (2, 1)
    assert by_ctx[("none", "hi", "none")] == (0, 1)
    assert GO.warm_counts(log, "retrieve_rerank") is None  # no rows ⇒ cold prior daemon-side


def test_warm_counts_missing_log_is_cold(tmp_path: Path) -> None:
    assert GO.warm_counts(tmp_path / "absent.jsonl", "re_extract_strong") is None


def test_grow_block_carries_vocabulary_and_actuators(tmp_path: Path) -> None:
    log = tmp_path / "gather_outcomes.jsonl"
    ctx = {"extracted": "some", "p_none": "hi", "indeterminate": "none"}
    GO.append_outcome(log, "retrieve_rerank", ctx, recovered=True)
    block = GO.grow_block(log)
    assert block["features"]["names"] == ["extracted", "p_none", "indeterminate"]
    assert block["features"]["values"][0] == ["none", "some"]
    probes = [a["probe"] for a in block["actuators"]]
    assert probes == ["retrieve_rerank", "retrieve_expand", "re_extract_strong"]
    by_probe = {a["probe"]: a for a in block["actuators"]}
    assert by_probe["retrieve_rerank"]["warm_counts"] is not None       # counts accrued
    assert by_probe["re_extract_strong"]["warm_counts"] is None         # still cold
    for a in block["actuators"]:  # every actuator declares its cost + cold Beta g-prior
        assert a["cost"] > 0 and a["alpha0"] > 0 and a["beta0"] > 0


# --- the recovery rate: gather's measured price (J1 step 4) --------------------------------

def _rows(path: Path, rows: list[tuple[str, bool]]) -> None:
    path.write_text("".join(
        json.dumps({"probe": "retrieve_rerank", "ctx": ["some"], "recovered": rec,
                    "tx_time": f"{day}T00:00:00+00:00"}) + "\n" for day, rec in rows),
        encoding="utf-8")


def test_recovery_rate_is_the_pooled_beta_1_1_mean(tmp_path: Path) -> None:
    log = tmp_path / "gather_outcomes.jsonl"
    _rows(log, [("2026-08-21", True), ("2026-08-21", False), ("2026-08-25", False)])
    assert GO.recovery_rate(log, excluded_days=()) == (1 + 1) / (3 + 2)


def test_recovery_rate_skips_the_excluded_window(tmp_path: Path) -> None:
    log = tmp_path / "gather_outcomes.jsonl"
    _rows(log, [("2026-08-21", False), ("2026-08-26", True), ("2026-08-26", True)])
    assert GO.recovery_rate(log, excluded_days=("2026-08-26",)) == 1 / 3
    assert "2026-08-26" in GO.PRC.GATHER_EXCLUDED_DAYS  # run 17's window, by default


def test_recovery_rate_without_a_log_is_the_prior_mean(tmp_path: Path) -> None:
    assert GO.recovery_rate(tmp_path / "absent.jsonl") == 0.5
