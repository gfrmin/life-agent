"""The calibration outcomes log — the third evidence stream (bayesian-foundations §8).

Append-only JSONL at :data:`life_agent.core.config.OUTCOMES_LOG`
(``$LIFE_AGENT_KB/calibration/outcomes.jsonl`` — the values are personal data, so the
log lives out of tree, PRINCIPLES §12). Each line is one graded outcome: a claim
attributed to the instrument that produced it, with the grader named. Three invariants,
all from the adopted foundations:

- **Append-only, never backfilled** (§8): an outcome not logged when it happened is
  evidence destroyed; reliability posteriors are folds of this log.
- **The fold is order-defined** (§2): file order — the append order — is the canonical
  replay order. ``read`` returns events in that order; nothing here sorts.
- **Closed vocabularies** (§18.8 discipline, self-applied): every grader declares its
  grade set in :data:`GRADERS`; an event outside it fails loudly at construction.

Scoring (§8): proper scoring rules over (asserted probability, realised correctness)
pairs — log score (proper and local; primary), Brier (secondary), and reliability-bin
data for the per-family diagrams. Events without an asserted probability (the current
monolithic pipeline asserts none — credences arrive with Ask v0 slice 2) are logged for
attribution and excluded from scoring, never imputed.
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

FORMAT_VERSION = 1

# Stated clamp for the log score: p in {0, 1} on the wrong outcome is -inf under the
# exact rule; the clamp keeps gate arithmetic finite and is part of the gate's stated
# definition (bayesian-foundations §8), not a hidden mercy.
SCORE_EPS = 1e-6

# Grader -> the closed grade vocabulary it may emit. Declared here so an outcome outside
# its grader's vocabulary is a loud construction error, never a silent new category.
GRADERS: dict[str, frozenset[str]] = {
    # scripts/run_eval.py grade_retrieval — the selection channel (M2 evidence)
    "eval_retrieval": frozenset({
        "PASS", "RETRIEVAL_MISS",
        "ABSENT_COVERAGE", "ABSENT_EXTRACTION", "ABSENT_UNSPECIFIED",
    }),
    # scripts/run_eval.py synthesis grader — the monolithic answer instrument
    "eval_synthesis": frozenset({"PASS", "WEAK", "HALLUCINATED", "ABSTAINED_OK"}),
    # scripts/run_eval.py lookup grader — per-claim grading of the typed family's
    # credence-bearing claims (each event carries the asserted probability)
    "eval_lookup": frozenset({"CORRECT", "INCORRECT"}),
    # §8 grader 2 — spot-check audits against source bytes (stratum declared now)
    "audit": frozenset({"correct", "incorrect"}),
    # §8 grader 3 — owner corrections; "unrouted" is the matcher's honest failure mode
    # (a correction it cannot ground stays at answer level, never mis-assigned)
    "owner": frozenset({"correct", "incorrect", "unrouted"}),
}

# Which grades count as "correct" for scoring, per grader. A drift gate in
# tests/test_outcomes.py asserts these are subsets of GRADERS.
CORRECT_GRADES: dict[str, frozenset[str]] = {
    "eval_retrieval": frozenset({"PASS"}),
    "eval_synthesis": frozenset({"PASS", "ABSTAINED_OK"}),
    "eval_lookup": frozenset({"CORRECT"}),
    "audit": frozenset({"correct"}),
    "owner": frozenset({"correct"}),
}


def now_iso() -> str:
    """Current UTC time, ISO 8601 with offset — the tx_time convention."""
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class OutcomeEvent:
    """One graded outcome (bayesian-foundations §8 schema, format_version 1).

    ``instrument_identity`` holds the schema-3 cache-key components where the instrument
    has them (producer_name/version, model identity, prompt/engine hashes) or a declared
    identity dict where it does not (e.g. the raw retrieval channel). ``lineage_keys``
    are the §18.9 stage cache keys of the answer this outcome grades — empty when the
    grader never touched the ask path. ``probability`` is the credence the system
    asserted for the claim; ``None`` means none was asserted (logged, not scored).
    """

    tx_time: str
    run_id: str
    question_id: str
    claim: str
    construct: str
    grade: str
    grader: str
    instrument_identity: dict[str, Any]
    lineage_keys: tuple[str, ...] = ()
    probability: float | None = None
    format_version: int = field(default=FORMAT_VERSION)

    def __post_init__(self) -> None:
        if self.grader not in GRADERS:
            raise ValueError(f"unknown grader {self.grader!r} (declared: {sorted(GRADERS)})")
        if self.grade not in GRADERS[self.grader]:
            raise ValueError(
                f"grade {self.grade!r} is not in grader {self.grader!r}'s vocabulary "
                f"{sorted(GRADERS[self.grader])}"
            )
        if self.probability is not None and not 0.0 <= self.probability <= 1.0:
            raise ValueError(f"probability {self.probability} outside [0, 1]")


def _to_line(event: OutcomeEvent) -> str:
    payload = asdict(event)
    payload["lineage_keys"] = list(event.lineage_keys)
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _from_line(line: str) -> OutcomeEvent:
    obj = json.loads(line)
    obj["lineage_keys"] = tuple(obj.get("lineage_keys", ()))
    return OutcomeEvent(**obj)


def append(path: Path, event: OutcomeEvent) -> None:
    """Append one outcome line, durably (flush + fsync — this is an evidence log).

    Append-only by construction: the file is opened in ``"a"`` and never rewritten.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(_to_line(event) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def read(path: Path) -> list[OutcomeEvent]:
    """Every outcome in file order — the canonical replay order (foundations §2).

    A malformed line raises: a corrupt evidence log is a loud failure, never a skip.
    Missing file means no evidence yet: an empty list.
    """
    if not path.exists():
        return []
    return [_from_line(line)
            for line in path.read_text(encoding="utf-8").splitlines() if line]


# --- proper scoring rules (bayesian-foundations §8) ------------------------------------

def log_score(p: float, *, correct: bool, eps: float = SCORE_EPS) -> float:
    """Log probability assigned to the realised outcome (<= 0; 0 is perfect).

    ``p`` is clamped into [eps, 1-eps] — the stated finite-gate convention.
    """
    p = min(max(p, eps), 1.0 - eps)
    return math.log(p if correct else 1.0 - p)


def brier_score(p: float, *, correct: bool) -> float:
    """Squared error of the asserted probability against the realised outcome
    (in [0, 1]; 0 is perfect)."""
    y = 1.0 if correct else 0.0
    return (p - y) ** 2


@dataclass(frozen=True)
class ScoreSummary:
    n: int
    mean_log: float | None
    mean_brier: float | None


def summarize_scores(pairs: list[tuple[float, bool]]) -> ScoreSummary:
    """Mean log score and Brier over (probability, correct) pairs; honest None on n=0."""
    if not pairs:
        return ScoreSummary(n=0, mean_log=None, mean_brier=None)
    logs = [log_score(p, correct=c) for p, c in pairs]
    briers = [brier_score(p, correct=c) for p, c in pairs]
    return ScoreSummary(n=len(pairs),
                        mean_log=sum(logs) / len(logs),
                        mean_brier=sum(briers) / len(briers))


@dataclass(frozen=True)
class ReliabilityBin:
    lo: float
    hi: float
    n: int
    mean_p: float | None
    frac_correct: float | None


def reliability_bins(pairs: list[tuple[float, bool]], *,
                     n_bins: int = 10) -> list[ReliabilityBin]:
    """Equal-width reliability bins over [0, 1] (the diagram data, foundations §8).

    Bin i covers [i/n, (i+1)/n), the last bin closed at 1.0. Empty bins are kept (with
    ``None`` stats) so the diagram's gaps are visible, never silently compacted.
    """
    buckets: list[list[tuple[float, bool]]] = [[] for _ in range(n_bins)]
    for p, c in pairs:
        i = min(int(p * n_bins), n_bins - 1)
        buckets[i].append((p, c))
    bins: list[ReliabilityBin] = []
    for i, bucket in enumerate(buckets):
        n = len(bucket)
        bins.append(ReliabilityBin(
            lo=i / n_bins, hi=(i + 1) / n_bins, n=n,
            mean_p=(sum(p for p, _ in bucket) / n) if n else None,
            frac_correct=(sum(1 for _, c in bucket if c) / n) if n else None,
        ))
    return bins


def scored_pairs(events: list[OutcomeEvent]) -> list[tuple[float, bool]]:
    """(probability, correct) pairs for the events that asserted a credence, in log
    order. Correctness comes from the grader's declared CORRECT_GRADES; events with no
    asserted probability are excluded from scoring, never imputed."""
    return [(e.probability, e.grade in CORRECT_GRADES[e.grader])
            for e in events if e.probability is not None]
