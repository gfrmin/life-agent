#!/usr/bin/env python3
"""r20's off-gate duplicate-pair measurement — component 3 read on the LIVE engine.

Runs :func:`life_agent.core.aggregate.same_entity_posterior` on the three labelled
``duplicate_pairs`` in ``$LIFE_AGENT_KB/eval/aggregate-questions.yaml``, over the live
credence engine (``LK.shared_brain()`` — the same seam the deployed path uses; never the
test oracle: a census must read the deployed rule end-to-end). $0 — no model calls.

The covariate mapping and the directions are FROZEN in r20's pre-registration (committed
before this script existed): real-duplicate → p_one > 0.5; both controls → p_one < 0.5.
Exit 1 on any directional miss — a miss is a STOP for an owner ruling.

    uv run --project . python scripts/dedup_pair_audit.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from life_agent.core import lookup as LK
from life_agent.core.aggregate import (
    UNREADABLE,
    PairCovariates,
    same_entity_posterior,
)

# The frozen mapping (r20 prereg): each labelled document pair induces the line-item
# pair of its principal addend; buckets come from the eval file's recorded evidence.
_MAPPING: dict[str, tuple[PairCovariates, bool]] = {
    "real-duplicate": (
        PairCovariates(period="same", amount=UNREADABLE, entity="same", kind="same"),
        True),
    "control-non-duplicate": (
        PairCovariates(period="adjacent", amount=UNREADABLE, entity="same",
                       kind="same"),
        False),
    "control-non-duplicate-readable": (
        PairCovariates(period="adjacent", amount="different", entity="same",
                       kind="same"),
        False),
}


def main() -> int:
    kb = os.environ.get("LIFE_AGENT_KB")
    if not kb:
        print("LIFE_AGENT_KB unset", file=sys.stderr)
        return 2
    eval_path = Path(kb) / "eval" / "aggregate-questions.yaml"
    pairs = yaml.safe_load(eval_path.read_text())["duplicate_pairs"]
    by_label = {p["label"]: p for p in pairs}
    missing = sorted(set(_MAPPING) - set(by_label))
    if missing:
        print(f"labelled pairs missing from {eval_path}: {missing}", file=sys.stderr)
        return 2

    brain = LK.shared_brain()
    misses = 0
    for label, (cov, want_one) in _MAPPING.items():
        assert by_label[label].get("same_transaction") is want_one, (
            f"{label}: eval label disagrees with the frozen direction")
        post = same_entity_posterior(brain, cov)
        got_one = post.p_one > 0.5
        verdict = "MET " if got_one is want_one else "MISS"
        misses += got_one is not want_one
        print(f"{verdict} {label}: p_one={post.p_one:.4f} p_two={post.p_two:.4f} "
              f"(direction: {'one' if want_one else 'two'}; "
              f"conditioned={list(post.conditioned)}, skipped={list(post.skipped)})")
    if misses:
        print(f"\n{misses} directional miss(es) — STOP for an owner ruling (r20).")
        return 1
    print("\nAll three pre-registered directions met.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
