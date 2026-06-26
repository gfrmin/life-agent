"""The gather-augmented lookup loop — the Stage-0 govern+steer driver (foundations §4,
the principled-RAG-agent plan).

The single-pass :func:`life_agent.core.lookup.lookup_answer` decides over exactly the
retrieval set the question's words found. That set is corroboration-biased toward whatever
the owner documented MOST — which, for a current-state fact, is often his *old* life: the
mobile case retrieves an email-only, stale-dominated set and the posterior pools by
corroboration count onto a superseded number. No read-side re-weighting reaches the
evidence the question's phrasing missed (a National-Insurance form *lists* the current
number; it never says "mobile phone number").

This loop GATHERS that missing evidence, then values it under the same posterior:

    route       reuse lookup.route_question (None ⇒ narrative path, as single-pass)
    observe     baseline grounded extraction over the question's hits → candidates
    gather      for the top candidates, probe_corroborate re-retrieves on each value to
                surface MORE independent documents (incl. the high-authority records the
                question phrasing missed) — the §4 lever from abstain to confident report
    re-weight   project doc_subject (whose-document — protects identity facts) and doc_date
                (recency — decays stale corroboration) over the UNION, read-side
    decide      reuse lookup.decide_and_record: tempered posterior → EU under Ū → recorded

Recency is DECOUPLED from the route's ``time_indexed`` (the local router mis-flags some
current-state values, e.g. "mobile phone number", as permanent): the loop turns recency on
whenever the candidates' supporting documents split across eras (``_era_split``) — the
precondition for a stale-vs-current confusion — regardless of the router's verdict. The
subject covariate stays active for owner-scoped questions, so an identity fact (whose ID)
is protected by whose-document even when recency is on.

Gather augments **only what whose-document can protect** — owner-scoped questions ("my X").
A relational or third-party question ("my partner's ID") has no available whose-document
discriminator (the owner-subject filter answers "is this the OWNER's", the wrong question),
so gathered corroboration would only amplify whatever entity is documented most — for a
personal corpus, the owner himself. (Measured: with the guard off, the gate's "my partner's
Israeli ID" asserted the owner's OWN id at credence 0.971 — a confident-wrong the single-pass
path safely abstained on.) So a non-owner-scoped question takes the conservative single-pass
decision; gather never amplifies a confound it cannot see.

The orchestration here is the throwaway Stage-0 driver — it ports to the Julia answer-brain
(Stage 1). The probes (:mod:`life_agent.core.probes`) and the posterior
(:mod:`life_agent.core.lookup`) it composes are permanent.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import duckdb

from life_agent.core import lookup as LK
from life_agent.core import probes as P
from life_agent.core.brain import Brain

# Stage-0 driver knobs (tunable; not channel priors). The candidate fan-out must be wide
# enough to include a true-but-under-corroborated value the question's words buried (the
# mobile truth sat at rank 7 of the baseline set), since only a gathered-on candidate gets
# its missing evidence surfaced.
_N_CANDIDATES = 8   # gather on this many top baseline candidates
_K_GATHER = 6       # fresh documents to seek per candidate


def _era_split(observations: list[LK.Observation],
               doc_date: dict[str, str | None], *, years: float) -> bool:
    """Delegates to :func:`life_agent.core.lookup.era_split` — promoted to a permanent home so the
    capability bridge can project this evidence shape for the string-blind body (move-4-design §2C),
    while gather.py (and the gate driver's ``GA._era_split``) keep this name."""
    return LK.era_split(observations, doc_date, years=years)


def _top_candidates(brain: Brain, observations: list[LK.Observation],
                    rho: tuple[float, float], n: int) -> list[str]:
    """The n highest-posterior candidate values over the baseline observations — the gather
    targets, ranked by the rho-marginalised V weights (wire-derived). Uses the real posterior
    weight (matching the de-risk), not raw corroboration count, so a high-authority single
    document can still be a target. (Target selection by weight is a means-ends heuristic — a
    VOI-driven gather is a separate change, like the master-plan residual risks.)"""
    candidates = LK.candidates_from(observations)
    weights, state_id = LK.lookup_posterior(brain, observations, candidates, rho)
    brain.destroy_state(state_id)
    ranked = sorted(zip(candidates, weights[:-1], strict=True),
                    key=lambda cv: cv[1], reverse=True)
    return [c for c, _ in ranked[:n]]


def _gather(conn: duckdb.DuckDBPyConnection, question: str, values: list[str],
            held: set[str], *, k: int) -> list[dict[str, Any]]:
    """Re-retrieve on each candidate value, accumulating only NEW documents (a chunk of a
    document already in hand adds no independent corroboration — probe_corroborate's
    ``exclude_keys`` enforces it, and ``held`` grows as we go so two candidates do not both
    claim the same fresh document)."""
    gathered: list[dict[str, Any]] = []
    for value in values:
        for h in P.probe_corroborate(conn, question, value, k=k, exclude_keys=held):
            key = str(h["artifact_cache_key"])
            if key in held:
                continue
            held.add(key)
            gathered.append(h)
    return gathered


def gather_answer(conn: duckdb.DuckDBPyConnection, root: Path, question: str,
                  hits: list[dict[str, Any]], *, profile: str, owner_scoped: bool,
                  brain: Brain | None = None,
                  route_client: Any | None = None,
                  extract_client: Any | None = None,
                  n_candidates: int = _N_CANDIDATES, k_gather: int = _K_GATHER,
                  decisions_path: Path | None = None, run_id: str = "ask",
                  today: date | None = None) -> LK.LookupResult | None:
    """Run the gather-augmented lookup family over the question's admitted hits. None ⇒ the
    narrative path answers (not a typed lookup, or zero grounded observations — the
    coverage statement the single-pass family also makes). The decision IS the answer; it
    is recorded and logged exactly as :func:`life_agent.core.lookup.lookup_answer`'s is
    (shared :func:`~life_agent.core.lookup.decide_and_record`), so the gate and the render
    treat it identically."""
    route = LK.route_question(root, question, client=route_client)
    if route is None:
        return None

    b = brain if brain is not None else LK.shared_brain()

    # gather augments only what whose-document protects (module docstring): a non-owner-
    # scoped question has no discriminator for the wrong-subject confound, so amplifying
    # corroboration would inflate the most-documented entity (the owner). Take the
    # conservative single-pass decision instead — gather never amplifies a confound it
    # cannot see.
    if not owner_scoped:
        return LK.lookup_answer(root, question, hits, brain=b,
                                route_client=route_client, extract_client=extract_client,
                                decisions_path=decisions_path, run_id=run_id)

    rho = LK.extractor_reliability(b)  # the rho Beta (alpha, β), wire-conditioned

    # baseline observations over the question's own hits → the candidates to gather on
    base_obs, _ = LK.observe_hits(root, question, hits, client=extract_client,
                                  time_indexed=False, today=today)
    if not base_obs:
        return None
    targets = _top_candidates(b, base_obs, rho, n_candidates)

    # gather independent corroboration for each target, then value the UNION
    held = {str(h["artifact_cache_key"]) for h in hits}
    allhits = hits + _gather(conn, question, targets, held, k=k_gather)

    # §4.1 covariates over the union, projected read-side (probes never derive): recency
    # (email-aware) always; whose-document only for owner-scoped questions (it protects an
    # identity fact, and is a no-op factor 1.0 otherwise)
    hit_keys = list(dict.fromkeys(str(h["artifact_cache_key"]) for h in allhits))
    doc_date = P.probe_recency(conn, root, hit_keys)
    subject_state: dict[str, str] = (
        P.probe_subject(conn, root, hit_keys, profile=profile, client=extract_client)
        if owner_scoped and profile else {})
    cov = LK.HitCovariates(subject_state=subject_state, doc_date=doc_date)

    # decouple recency from the router: apply the route's verdict, but turn recency on when
    # the candidates era-split (a stale-vs-current confusion the router may have missed)
    time_indexed = route.time_indexed
    obs, indeterminate = LK.observe_hits(root, question, allhits, client=extract_client,
                                         covariates=cov, time_indexed=time_indexed,
                                         today=today)
    if not obs:
        return None
    if not time_indexed and _era_split(obs, dict(doc_date),
                                       years=LK._TIME_HALF_LIFE_YEARS):
        time_indexed = True
        obs, indeterminate = LK.observe_hits(root, question, allhits,
                                             client=extract_client, covariates=cov,
                                             time_indexed=True, today=today)

    return LK.decide_and_record(root, question, route.construct, obs, indeterminate,
                                n_hits=len(allhits), time_indexed=time_indexed,
                                brain=b, decisions_path=decisions_path, run_id=run_id)
