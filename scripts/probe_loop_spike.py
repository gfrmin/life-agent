"""Stage-0 govern+steer loop driver (THROWAWAY — superseded by the Julia answer-brain).

Exercises the permanent probe library (life_agent.core.probes) against the machinery
already wired — the credence skin (core.brain) + the lookup posterior (core.lookup) — to
MEASURE whether VOI-steered probing surfaces the true value over the distractor pile with
zero confident-wrong. Run manually on the live corpus (it calls the local extractor + the
skin); it is NOT a CI test. PII-free: it hardcodes no values and prints only what the
corpus yields, to the owner's own terminal.

The loop:
  1. retrieve (over-fetch) → route → extract ONCE (observe_hits, no covariates)
  2. price each unapplied re-weight probe by realized VOI = eu(state|probe) - eu(state)
     and apply the arg-max while positive (recency / subject; authority is baseline)
  3. optionally gather (corroborate) on the leader, then re-decide
  4. terminate on report (safe credence) / ask-leader / abstain

Decision model (candidate-SPECIFIC — the key Stage-0 finding): the existing
lookup.decide prices ask_clarify as a flat oracle price independent of WHICH candidate
leads, so sharpening the leader yields no VOI. The answer-brain must instead ask about the
leader: EU(ask "is it X?") = P(X)*u_correct + (1-P(X))*u_abstain - lambda_int, so a probe
that concentrates mass on the true leader raises ask's EU and VOI flows. Implemented here
in pure Python over the posterior weights; lookup.py is left frozen.

Usage:  uv run --project . python scripts/probe_loop_spike.py [k] ["question"]
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))  # import the sibling ask module

import ask

from life_agent import owner
from life_agent.core import lookup as LK
from life_agent.core import probes as P
from life_agent.core.decide import u_assert

DEFAULT_Q = "What is my mobile phone number?"


@dataclass(frozen=True)
class Decision:
    action: str
    eu: float
    leader: str
    leader_w: float
    p_none: float
    n_cand: int


def decide_candidate(cands: list[str], weights: list[float],
                     u_bar: dict[str, float]) -> Decision:
    """The candidate-specific decision over {report-leader, ask-leader, abstain}. ``weights``
    is the posterior over K candidates + NONE (last). EU(report) asserts the leader (right
    with prob = leader weight); EU(ask) confirms the leader with the oracle then asserts or
    abstains; EU(abstain) is the gauge zero. The arg-max is the chosen action, its EU the
    value(state) the VOI loop differences."""
    k = len(cands)
    p_none = weights[-1] if weights else 1.0
    if k == 0:
        return Decision("abstain", u_bar["u_abstain"], "—", 0.0, p_none, 0)
    j = max(range(k), key=lambda i: weights[i])
    w = weights[j]
    eu_report = w * u_assert(1.0, u_bar) + (1.0 - w) * u_assert(0.0, u_bar)
    eu_ask = (w * u_assert(1.0, u_bar) + (1.0 - w) * u_bar["u_abstain"]
              - u_bar["lambda_int"])
    eu_abstain = u_bar["u_abstain"]
    action, eu = max(
        (("report", eu_report), ("ask", eu_ask), ("abstain", eu_abstain)),
        key=lambda kv: kv[1])
    return Decision(action, eu, cands[j], w, p_none, k)


def evaluate(brain: Any, root: Path, question: str, hits: list[dict[str, Any]],
             cov: LK.HitCovariates, *, time_indexed: bool, rho: float,
             u_bar: dict[str, float]) -> tuple[Decision, list[tuple[str, float]]]:
    """Extract (cache-warm) under the given covariates → posterior → candidate decision.
    Returns (decision, candidates-with-credence sorted desc)."""
    obs, _ind = LK.observe_hits(root, question, hits, covariates=cov,
                                time_indexed=time_indexed)
    cands = LK.candidates_from(obs)
    if not cands:
        return Decision("abstain", u_bar["u_abstain"], "—", 0.0, 1.0, 0), []
    weights, state_id = LK.lookup_posterior(brain, obs, cands, rho)
    brain.destroy_state(state_id)
    ranked = sorted(zip(cands, weights[:-1], strict=True),
                    key=lambda kv: kv[1], reverse=True)
    return decide_candidate(cands, weights, u_bar), ranked


def _show(tag: str, d: Decision, ranked: list[tuple[str, float]]) -> None:
    head = ", ".join(f"{v}={w:.3f}" for v, w in ranked[:6])
    print(f"  {tag:18} → {d.action:7} eu={d.eu:+.3f}  leader={d.leader} ({d.leader_w:.3f})"
          f"  p_none={d.p_none:.3f}  n={d.n_cand}")
    print(f"  {'':18}   top: {head}")


def main() -> None:
    k = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    question = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_Q

    conn = ask.connect()
    root = ask._pkm_root()
    assert root is not None
    profile = owner.load_profile()

    hits = ask._retrieve_set(conn, question, k)
    hit_keys = [h["artifact_cache_key"] for h in hits]
    route = LK.route_question(root, question)
    if route is None:
        print("not routed as a lookup — narrative path owns this question")
        return
    ti = route.time_indexed
    print(f"Q: {question!r}\n   k={k} hits, route: construct={route.construct!r} "
          f"time_indexed={ti}\n")

    brain = LK.shared_brain()
    u_bar, _ver = LK.current_u_bar(brain)
    rho = LK.extractor_reliability()

    # the re-weight probe library (cheap reads); authority is already baseline in observe_hits
    print("projecting probes…")
    recency = P.probe_recency(conn, root, hit_keys)
    subject = P.probe_subject(conn, root, hit_keys, profile=profile)
    probe_cov = {
        "recency": LK.HitCovariates(doc_date=recency),
        "subject": LK.HitCovariates(subject_state=subject),
    }
    n_dated = sum(1 for v in recency.values() if v is not None)
    n_owner = sum(1 for v in subject.values() if v == "owner")
    print(f"  recency: {n_dated}/{len(recency)} hits dated · "
          f"subject: {n_owner} owner / {len(subject)} projected\n")

    print("=== baseline (authority only) ===")
    base = LK.HitCovariates()
    d0, r0 = evaluate(brain, root, question, hits, base, time_indexed=ti, rho=rho,
                      u_bar=u_bar)
    _show("baseline", d0, r0)

    # --- VOI loop over the re-weight probes (greedy, realized Δeu) ---------------------
    print("\n=== VOI loop (apply arg-max positive net-VOI) ===")
    applied: dict[str, Any] = {}
    remaining = dict(probe_cov)
    cur, cur_ranked = d0, r0
    while remaining:
        scored: list[tuple[float, str]] = []
        for name, cov in remaining.items():
            merged = LK.HitCovariates(
                subject_state={**applied.get("subject_state", {}),
                               **cov.subject_state},
                doc_date={**applied.get("doc_date", {}), **cov.doc_date})
            d, _ = evaluate(brain, root, question, hits, merged, time_indexed=ti,
                            rho=rho, u_bar=u_bar)
            voi = d.eu - cur.eu
            scored.append((voi, name))
            print(f"  probe {name:9}: realized VOI Δeu = {voi:+.3f}")
        scored.sort(reverse=True)
        best_voi, best = scored[0]
        if best_voi <= 1e-9:
            print("  → no probe has positive VOI; stop (would apply none)")
            break
        cov = remaining.pop(best)
        applied = {"subject_state": {**applied.get("subject_state", {}),
                                     **cov.subject_state},
                   "doc_date": {**applied.get("doc_date", {}), **cov.doc_date}}
        cur, cur_ranked = evaluate(
            brain, root, question, hits, LK.HitCovariates(**applied),
            time_indexed=ti, rho=rho, u_bar=u_bar)
        print(f"  ✓ apply {best} (VOI {best_voi:+.3f})")
        _show(f"+{best}", cur, cur_ranked)

    # --- gather: corroborate on the current leader -----------------------------------
    if cur.leader not in ("—",) and cur.action != "report":
        print(f"\n=== gather: corroborate on leader {cur.leader!r} ===")
        extra = P.probe_corroborate(conn, question, cur.leader, k=20,
                                    exclude_keys=set(hit_keys))
        print(f"  {len(extra)} new independent documents")
        if extra:
            allhits = hits + extra
            allkeys = hit_keys + [h["artifact_cache_key"] for h in extra]
            rec2 = P.probe_recency(conn, root, allkeys)
            cov2 = LK.HitCovariates(doc_date=rec2, subject_state=applied.get(
                "subject_state", {}))
            cur, cur_ranked = evaluate(brain, root, question, allhits, cov2,
                                       time_indexed=ti, rho=rho, u_bar=u_bar)
            _show("+corroborate", cur, cur_ranked)

    print(f"\n=== FINAL: {cur.action} · leader={cur.leader} ({cur.leader_w:.3f}) "
          f"· confident-wrong={'YES' if cur.action == 'report' and cur.leader_w < 0.5 else 'no'}")


if __name__ == "__main__":
    main()
