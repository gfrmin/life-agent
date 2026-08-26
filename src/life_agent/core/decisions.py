"""The decision log — no EU decision is ever made unlogged (bayesian-foundations §8).

Append-only JSONL at :data:`life_agent.core.config.DECISIONS_LOG`
(``$LIFE_AGENT_KB/calibration/decisions.jsonl``). Owner reactions are readable as
*choices* — the §4.4 utility posterior's evidence — only against the decision context:
what the agent chose, among which actions, under which posterior, valuing them with
which utility fold. That context is recorded here and nowhere else, so the stream is
unbackfillable by the same option-value derivation as the outcomes log; it also feeds
§10's metareasoning accounting. Reactions join by ``question_id``.

Same discipline as :mod:`life_agent.core.outcomes`: append-only, file order is the
canonical replay order, closed vocabularies fail loudly at construction, appends are
durable. (Deliberate near-duplication of that module's mechanics — two event logs is
duplication, the third extracts a helper.)
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from life_agent.core import jsonl_log

# v2 (2026-08-06): + instrument / cost_usd / latency_s — the §10 metareasoning
# accounting lands on the ledger itself (which edge answered, at what price), and the
# per-edge calibration fold (core/calibration.EdgeOutcome) gains its attribution key.
# v1 lines replay with the fields defaulted (no instrument, unpriced).
# v3 (2026-08-19, module-collapse M0): + regime / policy / defaulted — WHICH decision space
# the act was ranked over (design §2.3) and WHICH evidence set valued it (§3.1). Both are
# facts ABOUT the record, never host choices; `defaulted` names the ones the writer filled
# in, so an assumption can never be read as a statement. v1/v2 lines replay at the declared
# defaults claiming nothing.
FORMAT_VERSION = 3

# Question families with an EU response layer. Grows by edit as families land
# (aggregate and thread join at bayesian-foundations §12 stages 2-3).
FAMILIES: frozenset[str] = frozenset({"lookup", "narrative"})

# The M4 response actions (bayesian-foundations §3). ask-about-U is deliberately absent
# — utility learning is passive until the governor (§4.4, a stated action-set
# coarsening). report_scoped is the time-scoped assertion ("as of <date>, X" — scoped-claims
# design): a true claim about the record, graded on attestation not currency, so it carries
# u_wrong_scoped (a citable misread) not the catastrophic current-value u_wrong.
ACTIONS: frozenset[str] = frozenset({"report", "report_scoped", "hedge",
                                     "ask_clarify", "abstain"})

# Per-family action subsets of ACTIONS — the single vocabulary, named once and imported by
# the families (never re-declared in a family module). The ordering is load-bearing: lookup
# maps brain.optimise's finite action indices through LOOKUP_ACTION_ORDER. NARRATIVE is the
# restricted set {report, abstain} — a *principled* restriction (hedge/report_scoped over a
# per-claim posterior are not yet defined; that is the deferred recency/u_hedged work), not an
# accident. The subset and partition invariants (these <= ACTIONS; LOOKUP - NARRATIVE == the
# lookup-only actions; gate's assert/withhold union == ACTIONS) are drift-gated in
# tests/test_decide.py.
LOOKUP_ACTION_ORDER: tuple[str, ...] = ("report", "hedge", "ask_clarify", "abstain",
                                        "report_scoped")
NARRATIVE_ACTION_ORDER: tuple[str, ...] = ("report", "abstain")

# The DECLARED DECISION SPACE the act was ranked over (module-collapse-design.md §2.3). One
# rule, two spaces: `full` = the transformations and the terminals (the daemon up),
# `terminals-only` = the terminals alone (the daemon unavailable — the skin ranks the same
# terminals over the same posterior and the same Ū). The regime is a FACT OF AVAILABILITY
# recorded on the decision, never a choice: nothing may prefer one regime when both are
# available, and a terminals-only decision is not a fallback lane — it is the same ranking
# with an empty transformation set, honestly recorded.
#
# `unavailable` is the third case and NOT an action (§6.5): when no optimiser is reachable
# there is no ranking to be inside of, so the record is an unavailability event. Keeping it
# in this vocabulary — rather than spelling it `abstain` — is what stops it folding as an
# abstain verdict, which reactions §4.4 reads as utility evidence.
REGIMES: frozenset[str] = frozenset({"full", "terminals-only", "unavailable"})
REGIME_DEFAULT = "full"

#: What ``defaulted`` says when a writer stated NEITHER field — the honest default, so a
#: producer predating v3 (and every family leaf until M2 folds them into the one poster)
#: discloses its silence instead of claiming a regime it never declared.
DEFAULTED_UNSTATED: tuple[str, ...] = ("policy", "regime")

# The evidence policy the utility posterior was folded under (design §3.1, Q-O5): the
# ranking's Ū conditions on everything to date, while the offline adoption gate freezes the
# elicitation set so runs stay comparable. Recorded as a REGIME INDICATOR on the decision —
# the same pattern the decision space uses — so a policy swap is visible in the record
# rather than inferable from which module wrote it.
POLICIES: frozenset[str] = frozenset({"all-to-date", "frozen-elicitations"})
POLICY_DEFAULT = "all-to-date"

QUESTION_ID_CHARS = 16


def question_id(question: str) -> str:
    """The ONE derivation of a decision's ``question_id`` from the question text: sha256
    of the raw text, first :data:`QUESTION_ID_CHARS` hex chars. Every producer of a
    ``DecisionEvent`` (``core/lookup.py``, ``core/narrative.py``, ``bridge/server.py``),
    every reaction writer (``scripts/ask.py``), and the membrane mirror
    (``core/shadow_mirror.py``'s callers) key on this — a second, hand-copied spelling
    anywhere silently splits the id namespace and every join across it reads as "no
    data" rather than as an error (exactly the bug the membrane shadow's grounded join
    shipped with). Drift-gated in ``tests/test_decisions.py``: no other site in ``src/``
    or ``scripts/`` may hash a question itself.

    NOT the same namespace as an eval/fair-fight CORPUS id (``q-001``, an
    ``OutcomeVector.question_id``). Bridging those two namespaces is a deliberate,
    named join through the questions file that assigned the corpus ids — see
    ``life_agent.membrane.shadow.warm_question_id_map``."""
    return hashlib.sha256(question.encode("utf-8")).hexdigest()[:QUESTION_ID_CHARS]


@dataclass(frozen=True)
class DecisionEvent:
    """One EU decision (bayesian-foundations §8 schema, format_version 2).

    ``posterior_summary`` is the answer-posterior digest the decision was taken under
    (claim credences, dispersion — enough to reconstruct *why* without the full
    artifacts, which the §18.9 lineage already holds). ``utility_fold_version`` pins
    exactly which utility posterior valued the actions
    (:func:`life_agent.core.utility.fold_version`). ``predicted_eu`` is the chosen
    action's expected utility at decision time — the quantity later reactions grade.
    ``decision_id`` is the **per-decision** join key the reaction loop binds verdicts to
    (§4.4): the answer's §18.9 cache key, content-addressed so two truly identical
    decisions coalesce. It is *not* ``run_id`` (per-*run* on the eval path — overloading it
    would give one field two cardinalities). Empty only on pre-reaction-loop lines, which
    no verdict joins.
    """

    tx_time: str
    run_id: str
    question_id: str
    family: str
    action_set: tuple[str, ...]
    posterior_summary: dict[str, Any]
    utility_fold_version: str
    chosen_action: str
    predicted_eu: float
    decision_id: str = ""
    # v2: the answer-proposing edge (one spelling — e.g. deliberate.instrument()) and
    # its realised price. "" / None on v1 lines and on paths not yet metered.
    instrument: str = ""
    cost_usd: float | None = None
    latency_s: float | None = None
    # v3: the declared decision space and evidence policy this act was ranked under, plus
    # the names of whichever of them the writer supplied for a caller that stated neither.
    regime: str = REGIME_DEFAULT
    policy: str = POLICY_DEFAULT
    # The DEFAULT is "this writer stated neither" — so a producer that predates the fields
    # (every v1/v2 line, and the family leaves until M2 folds them into the one poster)
    # discloses its silence rather than claiming a regime it never declared. The bridge
    # narrows it to whichever field the caller actually omitted.
    defaulted: tuple[str, ...] = DEFAULTED_UNSTATED
    format_version: int = field(default=FORMAT_VERSION)

    def __post_init__(self) -> None:
        if self.family not in FAMILIES:
            raise ValueError(f"unknown family {self.family!r} (declared: {sorted(FAMILIES)})")
        if not self.action_set:
            raise ValueError("action_set is empty — a decision needs alternatives")
        unknown = set(self.action_set) - ACTIONS
        if unknown:
            raise ValueError(
                f"action(s) {sorted(unknown)} not in the declared vocabulary {sorted(ACTIONS)}"
            )
        if self.chosen_action not in self.action_set:
            raise ValueError(
                f"chosen action {self.chosen_action!r} not in the action set "
                f"{list(self.action_set)}"
            )
        if self.regime not in REGIMES:
            raise ValueError(
                f"unknown regime {self.regime!r} (declared: {sorted(REGIMES)})")
        if self.policy not in POLICIES:
            raise ValueError(
                f"unknown policy {self.policy!r} (declared: {sorted(POLICIES)})")
        unknown_defaulted = set(self.defaulted) - {"regime", "policy"}
        if unknown_defaulted:
            raise ValueError(
                f"defaulted names non-defaultable field(s) {sorted(unknown_defaulted)}")


def _to_line(event: DecisionEvent) -> str:
    payload = asdict(event)
    payload["action_set"] = list(event.action_set)
    payload["defaulted"] = list(event.defaulted)
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _from_line(line: str) -> DecisionEvent:
    obj = json.loads(line)
    obj["action_set"] = tuple(obj.get("action_set", ()))
    # a line PREDATING v3 stated neither field; reading it as `()` would turn its silence
    # into a claim, which is the one thing this field exists to prevent
    obj["defaulted"] = (tuple(obj["defaulted"]) if "defaulted" in obj
                        else DEFAULTED_UNSTATED)
    return DecisionEvent(**obj)


def append(path: Path, event: DecisionEvent) -> None:
    """Append one decision line, durably (the shared append-only mechanics), then mirror it onto
    the unified stream (design §8 C5; legacy-append-first, never raises)."""
    jsonl_log.append_line(path, _to_line(event))
    from life_agent.ledger import mirror as _mirror  # C5 dual-write: after the legacy append
    _mirror.after_legacy_append("calibration.decisions", path)


def read(path: Path) -> list[DecisionEvent]:
    """Every decision in file order — the canonical replay order. Malformed lines
    raise; a missing file means no decisions yet."""
    return [_from_line(line) for line in jsonl_log.read_lines(path)]


def withhold_reason(*, effector: object, candidates: object,
                    available: bool = True) -> str:
    """D-5 (M5, r15): withhold-reason is ONE derivation over the decision record —
    ``unavailable ≻ miss ≻ dispersed``. ``unavailable`` dominates (no engine ranked, the
    row says nothing about the policy); ``miss`` means no posterior ever existed (the
    effector says so, or no candidate ever grounded); ``dispersed`` means a posterior
    existed and lost the EU argmax. The gate's ``WITHHELD_*`` labels, the eval's reason
    readout, and the render grammars' reason strings are all this function's callers —
    a second spelling of the chain is drift.
    """
    if not available:
        return "unavailable"
    if str(effector) == "miss" or not candidates:
        return "miss"
    return "dispersed"


def edge_id(kind: str, model: str) -> str:
    """D-12 (§5.3): THE per-edge attribution name — ``kind@model`` — one constructor
    for the calibration curves, the decision log's ``instrument`` field and every
    attribution key. ``executor.extract_edge`` and ``deliberate.instrument`` are
    bindings of it; a hand-built f-string at a call site would silently split the
    curve namespace."""
    return f"{kind}@{model}"


def leader_order(weights: list[float] | tuple[float, ...]) -> list[int]:
    """D-4 (§5.2): THE leader label-view — candidate indices by weight descending,
    stable on ties (original order). A VIEW for rendering and record conventions
    only; the argmax is the engine's, never re-derived from this ordering. The
    render/poster sites bind this; a fourth host ``sorted`` spelling would be a
    second view."""
    return sorted(range(len(weights)), key=lambda j: weights[j], reverse=True)
