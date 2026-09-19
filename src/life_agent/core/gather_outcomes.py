"""The gather-outcome instrumentation + the grow menu — the B half's data leg.

The conferred factoring (docs/ask-as-connection.md §4/§7): only the *gather* decision is
offloaded to the engine's structure-BMA — ``g = P(this actuator recovers the answer | sensors)``
— and the price of a *learned* g is instrumenting gather outcomes. This module is that leg,
body-side:

- ``SENSOR_FEATURES`` — the declared, BUCKETED sensor vocabulary (the structure-BMA needs
  finite value-sets). ``sensors_from`` buckets the candidate posterior's uncertainty summary:
  the old ``_truth_likely_missing`` gate (P(NONE) ≥ leader) survives only as the ``p_none="hi"``
  bucket — a *feature the belief conditions on*, never control flow (the ruling).
- ``GROW_ACTUATORS`` — the menu as data (autonomous-recall-design): each row a probe the body
  can enact, its cost-in-utility, and a hand-set cold Beta g-prior (the *demoted* g-prior —
  §4 caveat 1); the daemon's warm reconstruction sharpens it as counts accrue. Adding a recall
  strategy (``semantic``, …) is one row here + one bridge capability — the scheduler is untouched.
- ``append_outcome`` / ``warm_counts`` — the structure-observe stream: one JSONL row per enacted
  grow, folded to per-context ``(n1, n0)`` counts the daemon replays exactly
  (``reconstruct_structure_prior_from_data`` — Bayesian order-independence). ``recovered`` is the
  honest v0 outcome proxy: the grown question ended in a **report through the exact 0-CW terminal
  threshold** (not ground truth — the verdict join by decision_id refines this later; a g learned
  from this proxy can at worst over-try gathers, never mis-report, because reporting stays the
  exact app-side threshold).

The log lives under ``$LIFE_AGENT_KB`` (``config.GATHER_OUTCOMES_LOG``): outcome rows reference
the owner's questions' shape, so they are personal data (PRINCIPLES §12).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from life_agent.core import outcomes as O
from life_agent.core import pricing as PRC

# The declared sensor vocabulary — names + per-feature bucket sets, in ONE order (the daemon's
# `context_from_features` fails loud on drift; this list is the single source).
SENSOR_FEATURES: list[tuple[str, list[str]]] = [
    ("extracted", ["none", "some"]),        # did the local extraction ground any candidate?
    ("p_none", ["hi", "mid", "lo"]),        # the posterior's missing-mass bucket (hi ⇔ NONE is MAP)
    ("indeterminate", ["none", "some"]),    # hits whose subject verdict was indeterminate
]

# The grow menu is a BINDING of the one price table (core/pricing — M4, r14); the rows'
# rationale lives with the data. Same object, so a second spelling cannot drift.
GROW_ACTUATORS: list[dict[str, Any]] = PRC.GROW_ACTUATORS


def sensors_from(  # [§3.3 · GO-1] the sensor vocabulary (with M-9)
        *, candidates: list[str], credences: list[float],
                 p_none: float | None, indeterminate: int) -> dict[str, str]:
    """Bucket one decision view into the declared sensor vocabulary. Nothing extracted (or no
    posterior yet) reads as the missing-most context; ``p_none`` buckets against the best present
    candidate (hi ⇔ NONE is the MAP hypothesis) then an absolute floor (lo < 0.2)."""
    if not candidates or p_none is None:
        p_bucket = "hi"
    else:
        leader = max(credences) if credences else 0.0
        p_bucket = "hi" if p_none >= leader else ("lo" if p_none < 0.2 else "mid")
    return {
        "extracted": "some" if candidates else "none",
        "p_none": p_bucket,
        "indeterminate": "some" if indeterminate > 0 else "none",
    }


def _ctx_vector(sensors: dict[str, str]) -> list[str]:
    """The ordered context vector (the daemon's ``ctx`` shape), per SENSOR_FEATURES order."""
    return [sensors[name] for name, _ in SENSOR_FEATURES]


def append_outcome(path: Path, probe: str, sensors: dict[str, str], *,
                   recovered: bool) -> None:
    """Append one gather outcome (the structure-observe stream). Append-only JSONL; the fold
    (``warm_counts``) is a pure function of the log."""
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"tx_time": O.now_iso(), "probe": probe, "ctx": _ctx_vector(sensors),
           "recovered": bool(recovered)}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    from life_agent.ledger import mirror as _mirror  # C5 dual-write: after the legacy append
    _mirror.after_legacy_append("calibration.gather_outcomes", path)


def warm_counts(path: Path, probe: str) -> dict[str, Any] | None:
    """Fold the outcome log to one actuator's per-context ``(n1, n0)`` counts — the exact
    warm-seed shape ``reconstruct_structure_prior_from_data`` replays. No rows ⇒ ``None``
    (the daemon falls back to the actuator's declared cold Beta prior)."""
    if not path.exists():
        return None
    counts: dict[tuple[str, ...], list[int]] = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("probe") != probe:
                continue
            key = tuple(str(v) for v in row["ctx"])
            n = counts.setdefault(key, [0, 0])
            n[0 if row.get("recovered") else 1] += 1
    if not counts:
        return None
    return {"contexts": [{"ctx": list(k), "n1": n1, "n0": n0}
                         for k, (n1, n0) in sorted(counts.items())]}


def grow_block(path: Path) -> dict[str, Any]:
    """[§3.3 · GO-2] (cold prior: an actuator with no rows carries None ⇒ the
    daemon's declared cold prior — correct, declared.) The `/decide` grow block: the
    shared feature vocabulary + every menu actuator with its
    body-persisted warm counts (``None`` ⇒ the daemon uses the declared cold prior)."""
    return {
        "features": {"names": [n for n, _ in SENSOR_FEATURES],
                     "values": [v for _, v in SENSOR_FEATURES]},
        "actuators": [{**a, "warm_counts": warm_counts(path, str(a["probe"]))}
                      for a in GROW_ACTUATORS],
    }
