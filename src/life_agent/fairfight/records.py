"""``OutcomeVector`` — the fair-fight harness's per-(arm x question) measurement row.

Phase 0 of the fair-fight harness drives three arms (baseline, in-process, synthesis
executors, plus a hermes-over-pkm-MCP competitor) over the frozen eval and logs one
``OutcomeVector`` per (arm, question) to JSONL under
``$LIFE_AGENT_KB/eval/fairfight/<run_id>/arms/<arm>/vectors.jsonl``. A later runner
constructs these vectors; a later dominance analysis (Pareto frontier + profile-scalarized
win map) consumes them. This module is only the record + its JSON codec.

**Axes stay separate.** There is no combined score/utility/welfare field — only a
downstream profile may weight the axes; folding them here would bake one weighting into
the measurement itself.

Six axis groups, in field order (each condensed from the design's field-by-field notes):

- **identity** -- format_version, run_id, arm, question_id, answerable.
- **rubric** (blind judge; ``None`` = not judged / judge failed) -- faithfulness,
  completeness, citation_fidelity.
- **decision channel** (``scripts/triage_grading.py`` vocabulary) -- bucket/cause cross
  the retrieval and decision channels; asserted/asserted_correct/asserted_distractor,
  hallucinated, declined, correct_abstention, over_abstention describe what the arm did.
- **retrieval channel** -- gold/distractor presence in the top-k and candidate pool;
  ``gold_in_candidates`` is ``None`` when the arm has no candidate stage (never imputed).
- **calibration** (``None`` = the arm asserted no credence; never imputed) -- probability,
  p_none, p_none_correct, brier.
- **economics** -- cost_usd/cost_status plus raw token/latency/model-tier counts, so cost
  is recomputable if pricing changes.
- **effort/attention** -- gather_rounds, asks_issued, tool_calls (``None`` where an arm
  has no such stage); ``think_ticks`` is a reserved axis, always ``None`` at
  format_version 1.
- **provenance** -- answer_sha256/answer_chars/lineage_keys identify and cite the answer;
  status flags infra failures (never graded, excluded from scoring -- enforced by
  :func:`scored`, the one canonical filter every scored population must pass through);
  notes is free text.

Closed vocabularies (``arm``, ``cost_status``, ``status``, ``bucket``) fail loudly at
construction -- the same discipline as ``core/outcomes.py``'s ``OutcomeEvent``.
``bucket``'s vocabulary is redeclared here, not imported: ``scripts/triage_grading.py``
is the canonical source, but ``src/`` must never import from ``scripts/``.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

FORMAT_VERSION = 1

# The harness's three life-agent read-paths plus the three externally-driven arms.
ARMS: frozenset[str] = frozenset(
    {"baseline", "inprocess", "synthesis", "competitor", "oracle", "deliberative"})

# The externally-driven subprocess arms (subset of ARMS -- drift-gated in tests): each
# produces the shared usage-dict + tool-log shape the runner's economics/vector assembly
# ingests. "competitor" is the fair-fight adversary at the in-process arms' own ceiling
# model; "oracle" is the FRONTIER BASELINE (one-shot frontier model, hermes-driven);
# "deliberative" is the actual reference policy pi* -- Claude-Code-grade deliberation via
# `claude -p` (owner ruling 2026-07-19: "YOU are the gold standard", roadmap A1b).
EXTERNAL_ARMS: frozenset[str] = frozenset({"competitor", "oracle", "deliberative"})

# The hermes-CLI-driven subset of EXTERNAL_ARMS: same driver, same frozen prompt -- an
# oracle/competitor difference is attributable to the model and its agentic budget,
# never to prompt drift. The deliberative arm is driven by arm_claude instead.
HERMES_ARMS: frozenset[str] = frozenset({"competitor", "oracle"})

# measured: a real dollar cost was computed (core.pricing found the model).
# estimated: no exact price but a placeholder cost was derived.
# partial: some but not all cost components could be priced.
# unavailable: no cost signal at all (e.g. a local model, or the arm never asked).
COST_STATUSES: frozenset[str] = frozenset({"measured", "estimated", "partial", "unavailable"})

# An infra outcome, never a grading outcome: timeouts/errors are flagged and excluded
# from scoring, not graded as wrong.
STATUSES: frozenset[str] = frozenset({"ok", "timeout", "error"})

# The triage vocabulary (canonical source: scripts/triage_grading.py `Triage.bucket`,
# `triage()`). Redeclared here, not imported -- src/ must not import from scripts/; keep
# in sync if that module's bucket vocabulary changes.
BUCKETS: frozenset[str] = frozenset(
    {"CORRECT", "CONFIDENT_WRONG", "RIGHTLY_WITHHELD", "WRONGLY_WITHHELD", "SCOPED"}
)


@dataclass(frozen=True)
class OutcomeVector:
    """One arm's measured outcome on one question (format_version 1).

    See the module docstring for the axis groups. Every field is required (no
    defaults): a partially-populated vector is a construction error, never a silent gap
    an aggregate could quietly average over.
    """

    format_version: int
    run_id: str
    arm: str
    question_id: str
    answerable: bool

    # rubric (blind judge; None = not judged / judge failed)
    faithfulness: int | None
    completeness: int | None
    citation_fidelity: int | None

    # decision channel (scripts/triage_grading.py vocabulary)
    bucket: str
    cause: str | None
    asserted: bool
    asserted_correct: bool
    asserted_distractor: bool
    hallucinated: bool | None
    declined: bool
    correct_abstention: bool
    over_abstention: bool

    # retrieval channel
    gold_in_topk: bool
    gold_in_corpus: bool
    gold_in_candidates: bool | None  # None: arm has no candidate stage
    distractor_in_topk: bool
    n_retrieved: int

    # calibration (None = arm asserted no credence; never imputed)
    probability: float | None
    p_none: float | None
    p_none_correct: bool | None
    brier: float | None

    # economics
    cost_usd: float | None
    cost_status: str  # measured | estimated | partial | unavailable
    in_tokens: int
    out_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    latency_s: float
    model_tier_mix: dict[str, int]

    # effort / attention
    gather_rounds: int | None
    asks_issued: int
    tool_calls: int | None
    think_ticks: None  # reserved axis; always None at format_version 1

    # provenance
    answer_sha256: str
    answer_chars: int
    lineage_keys: tuple[str, ...]
    status: str  # ok | timeout | error (infra failures flagged, not graded)
    notes: str

    def __post_init__(self) -> None:
        if self.arm not in ARMS:
            raise ValueError(f"unknown arm {self.arm!r} (declared: {sorted(ARMS)})")
        if self.cost_status not in COST_STATUSES:
            raise ValueError(
                f"unknown cost_status {self.cost_status!r} "
                f"(declared: {sorted(COST_STATUSES)})"
            )
        if self.status not in STATUSES:
            raise ValueError(f"unknown status {self.status!r} (declared: {sorted(STATUSES)})")
        if self.bucket not in BUCKETS:
            raise ValueError(f"unknown bucket {self.bucket!r} (declared: {sorted(BUCKETS)})")


def to_json(vector: OutcomeVector) -> dict[str, Any]:
    """A JSON-safe dict for one line of a ``vectors.jsonl`` file.

    ``asdict`` already deep-copies ``model_tier_mix`` (so the caller can mutate the
    returned dict without touching ``vector``); ``lineage_keys`` is converted tuple -> list,
    the one field JSON has no native equivalent for.
    """
    payload = asdict(vector)
    payload["lineage_keys"] = list(vector.lineage_keys)
    return payload


def from_json(obj: dict[str, Any]) -> OutcomeVector:
    """Reconstruct one vector from a parsed JSON object (the inverse of ``to_json``).

    Every field is required (defaults-free) -- a missing key raises, never silently
    defaults. ``lineage_keys`` converts back list -> tuple; ``model_tier_mix`` is copied
    so the built vector never aliases the caller's dict.
    """
    fields: dict[str, Any] = dict(obj)
    fields["lineage_keys"] = tuple(obj["lineage_keys"])
    fields["model_tier_mix"] = dict(obj["model_tier_mix"])
    return OutcomeVector(**fields)


def _status(v: OutcomeVector | dict[str, Any]) -> str:
    return v.status if isinstance(v, OutcomeVector) else str(v["status"])


def scored[V: (OutcomeVector, dict[str, Any])](vectors: list[V]) -> list[V]:
    """The ONE place ``status == "ok"`` is applied -- every scored population (rates,
    welfare sums, Pareto points, win-map cells, loss triage) filters out infra failures
    (``timeout``/``error``) through this, per this module's own docstring contract
    ("status flags infra failures (never graded, excluded from scoring)").

    Accepts EITHER ``OutcomeVector`` dataclass instances (``scripts/fairfight/
    run_fairfight.py``'s own in-memory per-arm list, built fresh each run) or JSON-safe
    dicts (``records.to_json`` shape -- ``scripts/dominance/``'s ``vectors.jsonl``-loaded
    rows) -- the two shapes both real consumers actually hold -- and returns the SAME
    shape it was given (a list of dicts in, a list of dicts out; dataclasses likewise),
    so this stays the one canonical filter instead of forcing either caller to round-trip
    through the other shape first.
    """
    return [v for v in vectors if _status(v) == "ok"]
