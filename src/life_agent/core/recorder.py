"""The one recorder (module-collapse design §5.1, landed at M2 — r12).

One ``/log_decision`` body, one place where a decision becomes two records (the §18.9
answer node and the calibration ledger row), and the §6.5 unavailability event. *No
accounting field is optional on the poster's side*: a firing that ran unpriced records
``cost_usd: 0.0`` with its instrument, never an absent key.

Three writers, one shape:

- :func:`record_via_bridge` — the executor path (trace A): the bridge owns the write and
  derives the content-addressed ``decision_id`` the owner reacts against.
- :func:`record_local` — the family leaves' tail (trace B): the §18.9 node then the ledger
  row, with the ``decision_id = akey.cache_key`` rule preserved verbatim. The leaf events
  keep their v2 defaults (``cost_usd: None`` = unmetered path) until the checkpoint that
  declares their regime (M5) — the §5.1 never-absent normalisation binds the *posted* body.
- :func:`record_unavailable` — §6.5: when no optimiser is reachable there is no ranking to
  be inside of; the record is an *unavailability event* (``regime: unavailable``, stated)
  with ``decision_id: ""`` so no verdict can ever bind — never a foldable abstain verdict.
  Appended locally: the stack is down by definition, so the bridge cannot be assumed
  reachable, and the client and the ledger share the box by deployment.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from life_agent.core import config
from life_agent.core import decisions as DEC
from life_agent.core import derivations as D
from life_agent.core import outcomes as O

#: The live default the bridge's poster already applies to an untagged decision — one
#: default, one poster (an in-gate run tags itself via ``run_id``).
RUN_ID_DEFAULT = "answer-brain"


def body(*, question: str, retrieval_keys: list[str], effector: str,
         credences: list[float], candidates: list[str], p_none: float | None,
         eu: float | None, n_obs: int, n_indeterminate: int, n_competing: int,
         instrument: str | None, cost_usd: float | None, latency_s: float | None,
         run_id: str | None, regime: str, policy: str) -> dict[str, Any]:
    """The ONE ``/log_decision`` body — every key present, the unpriced defaults honest
    (0.0 = ran unpriced / unmeasured, "" = no priced edge), ``regime``/``policy`` stated."""
    return {
        "question": question,
        "retrieval_keys": retrieval_keys,
        "decision": {
            "effector": effector,
            "credences": credences,
            "candidates": candidates,
            "p_none": p_none if p_none is not None else 0.0,
            "eu": eu if eu is not None else 0.0,
            "n_obs": n_obs,
            "n_indeterminate": n_indeterminate,
            "n_competing": n_competing,
            "instrument": instrument or "",
            "cost_usd": cost_usd if cost_usd is not None else 0.0,
            "latency_s": latency_s if latency_s is not None else 0.0,
            "run_id": run_id or RUN_ID_DEFAULT,
            "regime": regime,
            "policy": policy,
        },
    }


def record_via_bridge(post: Callable[[str, dict[str, Any]], dict[str, Any] | None],
                      bridge: str, payload: dict[str, Any]) -> str | None:
    """Post the one body; return the bridge's content-addressed ``decision_id``. The
    fail-open contract (a calibration write never breaks the answer) belongs to the
    caller — this function lets the transport's exception carry its own name."""
    resp = post(f"{bridge}/log_decision", payload)
    decision_id = (resp or {}).get("decision_id")
    return str(decision_id) if decision_id is not None else None


def record_local(root: Path, akey: Any, content: bytes, *,
                 lineage: list[dict[str, str]], decisions_path: Path,
                 event: DEC.DecisionEvent) -> None:
    """The family leaves' tail: the §18.9 answer node, then the ledger row. One call,
    two writes — the one place a leaf decision becomes its two records (§5.1)."""
    D.record(root, akey, content, lineage=lineage)
    DEC.append(decisions_path, event)


def record_miss(question: str, *, retrieval_keys: list[str],
                n_indeterminate: int = 0, run_id: str | None = None,
                decisions_path: Path | None = None) -> str:
    """The miss row (r33 RC-1): the engine was up, the lookup grounded NOTHING, the loop
    returned before ``/decide`` — for 69 measured asks this lane wrote no row at all, so
    the class was invisible to the reaction stream in both directions. One local
    ``lookup``-family row: ``regime: "miss"`` (a coverage failure, stated — and what keeps
    a verdict on it OUT of the utility fold), ``chosen_action: "abstain"`` (the §6.5
    precedent: the action vocabulary stays closed), an empty fold version (no fold ran),
    and a REAL content-addressed ``decision_id`` — the ONE rule, over the empty posterior —
    returned so the reply can name it and the owner's verdict can bind. Local append, not a
    bridge post: the bridge derives ids for RANKED decisions and stamps the CURRENT fold
    version, both wrong for a miss."""
    decision_id = DEC.decision_id_for(question, retrieval_keys, [], 0.0)
    DEC.append(
        decisions_path if decisions_path is not None else config.DECISIONS_LOG,
        DEC.DecisionEvent(
            tx_time=O.now_iso(), run_id=run_id or RUN_ID_DEFAULT,
            question_id=DEC.question_id(question),
            family="lookup", action_set=DEC.LOOKUP_ACTION_ORDER,
            posterior_summary={"candidates": [], "credences": [], "p_none": 0.0,
                               "n_obs": 0, "n_indeterminate": n_indeterminate,
                               "n_competing": 0},
            utility_fold_version="",  # no fold ran — the loop returned before /decide
            chosen_action="abstain", predicted_eu=0.0, decision_id=decision_id,
            instrument="", cost_usd=0.0, latency_s=0.0,
            regime="miss", policy=DEC.POLICY_DEFAULT,
            # the writer STATES the regime; it cannot state a policy no fold used
            defaulted=("policy",)))
    return decision_id


def record_unavailable(question: str, *, run_id: str | None = None,
                       decisions_path: Path | None = None) -> None:
    """The §6.5 unavailability event. Returns ``None`` — there is nothing to bind a
    verdict to (``decision_id: ""`` never joins a reaction; the bridge's ``/log_reaction``
    refuses an empty id)."""
    DEC.append(
        decisions_path if decisions_path is not None else config.DECISIONS_LOG,
        DEC.DecisionEvent(
            tx_time=O.now_iso(), run_id=run_id or RUN_ID_DEFAULT,
            question_id=DEC.question_id(question),
            family="lookup", action_set=DEC.LOOKUP_ACTION_ORDER,
            posterior_summary={"candidates": [], "credences": [], "p_none": 0.0,
                               "n_obs": 0, "n_indeterminate": 0, "n_competing": 0},
            utility_fold_version="",  # no fold ran — there was no engine to fold for
            chosen_action="abstain", predicted_eu=0.0, decision_id="",
            instrument="", cost_usd=0.0, latency_s=0.0,
            regime="unavailable", policy=DEC.POLICY_DEFAULT,
            # the writer STATES the regime; it cannot state a policy no fold used
            defaulted=("policy",)))
    return None
