"""r32 — the commit-bar reading (conferral 2, ruling 1; $0).

**Criteria are frozen in `docs/unification/reports/r32-bar-reading-preregistration.md` and
were committed BEFORE this file existed.** The question: the deployed decision log records a
`report` at leader credence 0.875 against an owner-declared p* = 0.90. Is the indifference
point genuinely below 0.90 under the deployed pricing (PRICED), or does some path attenuate
the regret term without a licence (LEAK)?

The standing lesson binds this instrument: *a census must read the deployed rule end to end,
never re-implement the constant it prices.* So every constant comes from `src` as an imported
object — `decide.u_assert` (the one atom), `decide.shaped_u_bar` (the r30 units seam),
`lookup.action_utilities` (the tabular rows), `utility.posterior` (the fold). The ONE thing
computed host-side is the expectation over a tabular preference, which the engine would
otherwise do; it is validated against the record itself (C1: reproduced EU must equal the
recorded `predicted_eu`), so a re-implementation error cannot pass silently.

Reads artefacts already on disk. Buys nothing, writes nothing outside its own report.
"""
from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import life_agent.core.config as config
import life_agent.core.lookup as LK
import life_agent.core.reactions as R
import life_agent.core.utility as UT
from life_agent.core.decide import shaped_u_bar, u_assert

# The three boundary rows the pre-registration names, by recorded decision-id prefix.
BOUNDARY_PREFIXES = ("ab-fdf1550e", "ab-a302bef7", "ab-20aa6e94")

_TOL = 1e-9


class UnreadableRowError(Exception):
    """A recorded row whose posterior cannot be read as a distribution (C1: unreadable, not
    a verdict — a reading that cannot see the deployed rule may not conclude from it)."""


# --- the predicates (each pinned by tests/test_bar_audit.py, C5) -------------------------

def atom_probs(row: Mapping[str, object]) -> list[float]:
    """The recorded belief over the K+1 hypothesis atoms: the candidate credences in
    recorded order, then NONE. Refuses anything that is not a distribution."""
    ps = row.get("posterior_summary") or {}
    if not isinstance(ps, Mapping):
        raise UnreadableRowError(f"{row.get('decision_id')}: posterior_summary is not a mapping")
    creds = ps.get("credences")
    p_none = ps.get("p_none")
    if not isinstance(creds, list) or not creds or not isinstance(p_none, (int, float)):
        raise UnreadableRowError(f"{row.get('decision_id')}: no readable posterior")
    probs = [float(c) for c in creds] + [float(p_none)]
    total = sum(probs)
    if abs(total - 1.0) > 1e-6:
        raise UnreadableRowError(f"{row.get('decision_id')}: atoms sum to {total!r}, not 1")
    return probs


def indifference_point(u_bar: Mapping[str, float]) -> float:
    """p†, the deployed bar: the credence at which asserting is worth exactly abstaining.
    Found by BISECTING the imported `decide.u_assert` against the gauge zero — the atom is
    read, never re-derived, so a change to the deployed trade-off moves this number."""
    lo, hi = 0.0, 1.0
    target = float(u_bar["u_abstain"])
    if u_assert(lo, u_bar) > target:
        return 0.0
    if u_assert(hi, u_bar) < target:
        return 1.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if u_assert(mid, u_bar) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def reprice(probs: Sequence[float], u_bar: Mapping[str, float]) -> dict[str, float]:
    """EU per action under the recorded belief, over the DEPLOYED utility vectors
    (`lookup.action_utilities`). The expectation is the only host-side arithmetic."""
    table = LK.action_utilities(list(probs), dict(u_bar))
    return {name: sum(p * v for p, v in zip(probs, vec, strict=True))
            for name, vec in table.items()}


def argmax_action(eus: Mapping[str, float]) -> str:
    """The winner in the RECORDED action vocabulary: `report_j` collapses to `report`,
    `report_scoped_j` to `report_scoped` — the same mapping `lookup.decide` applies."""
    name = max(eus, key=lambda k: eus[k])
    if name.startswith("report_scoped_"):
        return "report_scoped"
    if name.startswith("report_"):
        return "report"
    return name


def consistent_with_bar(row: Mapping[str, object], p_dagger: float) -> bool:
    """C3: the recorded action must fall on the side of p† its leader credence implies."""
    lead = max(atom_probs(row)[:-1])
    asserted = str(row.get("chosen_action", "")).startswith("report")
    return asserted == (lead >= p_dagger)


# --- the fold as of a row (C1: the SAME Ū that priced it) --------------------------------

def u_bar_as_of(brain: Any, tx_time: str, *, shape: str | None = None
                ) -> tuple[dict[str, float], str, int]:
    """Fold the owner's utility model over exactly the evidence that existed when the row
    was written, through the deployed fold. Returns (Ū, fold_version, n_events); the caller
    checks that fold_version equals the version the row itself recorded."""
    model = UT.load_model(config.UTILITY_MODEL)
    events: list[UT.Evidence] = list(UT.load_elicitations(config.UTILITY_ELICITATIONS, model))
    events += R.load_reactions(config.REACTIONS_LOG, config.DECISIONS_LOG)
    events = [e for e in events if str(e.tx_time) <= tx_time]
    version = UT.fold_version(model, events, LK.U_BAR_POLICY)
    post = UT.posterior(brain, model, events, policy=LK.U_BAR_POLICY)
    raw = post.u_bar()
    from life_agent.core import answer_shape as AS
    return shaped_u_bar(raw, shape or AS.DEFAULT_SHAPE), version, len(events)


def u_bar_from(brain: Any, events: list[Any]) -> dict[str, float]:
    """Ū from an explicit evidence list — the same deployed fold, used to DECOMPOSE the
    bar's movement into what the model declares, what the elicitations said, and what the
    reaction stream did."""
    model = UT.load_model(config.UTILITY_MODEL)
    post = UT.posterior(brain, model, events, policy=LK.U_BAR_POLICY)
    from life_agent.core import answer_shape as AS
    return shaped_u_bar(post.u_bar(), AS.DEFAULT_SHAPE)


def scale_latents_present(u_bar: Mapping[str, float]) -> list[str]:
    """C2 attenuation candidate: any r30 units-lever scale the owner has opted in. An empty
    list means `shaped_u_bar` is the identity for EVERY shape, so the answer-shape route
    cannot have attenuated the regret term whatever shape the row carried."""
    return sorted(k for k in u_bar
                  if k.startswith("voi_scale_") or k.startswith("regret_scale_"))


def load_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


# --- the read ----------------------------------------------------------------------------

def main() -> int:
    rows = load_rows(config.DECISIONS_LOG)
    targets = [r for r in rows
               if any(str(r.get("decision_id", "")).startswith(p) for p in BOUNDARY_PREFIXES)]
    print(f"r32 — the commit-bar reading · {len(rows)} recorded rows · "
          f"{len(targets)} boundary rows named by the pre-registration")
    if len(targets) != len(BOUNDARY_PREFIXES):
        print("  ✗ C1 UNREADABLE: the named boundary rows are not all present")
        return 2

    brain = LK.shared_brain()
    results: list[dict[str, Any]] = []
    for row in sorted(targets, key=lambda r: -max(atom_probs(r)[:-1])):
        did = str(row["decision_id"])[:14]
        probs = atom_probs(row)
        lead = max(probs[:-1])
        u_bar, version, n_events = u_bar_as_of(brain, str(row["tx_time"]))
        version_ok = version == row.get("utility_fold_version")
        eus = reprice(probs, u_bar)
        got = argmax_action(eus)
        recorded = str(row["chosen_action"])
        eu_got = max(eus.values())
        eu_rec = float(row["predicted_eu"])
        p_dagger = indifference_point(u_bar)
        results.append({
            "id": did, "lead": lead, "recorded": recorded, "reproduced": got,
            "eu_recorded": eu_rec, "eu_reproduced": eu_got, "p_dagger": p_dagger,
            "u_wrong": u_bar["u_wrong"], "u_correct": u_bar["u_correct"],
            "version_ok": version_ok, "n_events": n_events,
            "action_ok": got == recorded,
            "eu_ok": abs(eu_got - eu_rec) <= max(_TOL, 1e-6 * abs(eu_rec)),
            "bar_ok": consistent_with_bar(row, p_dagger),
        })
        print(f"  {did}  lead={lead:.4f}  recorded={recorded:<8} reproduced={got:<8} "
              f"EU {eu_rec:+.6f} vs {eu_got:+.6f}  p†={p_dagger:.4f}  "
              f"fold={'MATCH' if version_ok else 'DIFFERS'} (n={n_events})")

    n = len(results)
    c1_version = sum(r["version_ok"] for r in results)
    c1_action = sum(r["action_ok"] for r in results)
    c1_eu = sum(r["eu_ok"] for r in results)
    c3 = sum(r["bar_ok"] for r in results)
    bars = {round(r["p_dagger"], 6) for r in results}
    print(f"\nC1  fold-version match {c1_version}/{n} · action {c1_action}/{n} · "
          f"EU {c1_eu}/{n}")
    print(f"C3  rows consistent with p† {c3}/{n} · p† = "
          + " · ".join(f"{b:.4f}" for b in sorted(bars)))
    print(f"    declared exchange rate ⇒ p* = 0.90 · deployed regret latent "
          f"u_wrong = {results[0]['u_wrong']:.4f} (prior mean is the model's, not this)")
    if c1_action < n or c1_eu < n:
        print("\nVERDICT: UNREADABLE (C1 not met) — no conclusion may be drawn.")
        return 2
    print("\nC1 met on all three conjuncts." if c1_version == n else
          "\nC1 met on action + EU; fold-version differs (disclosed).")

    # --- C2: the attenuation candidates, named and tested one by one -------------------
    model = UT.load_model(config.UTILITY_MODEL)
    elicits = list(UT.load_elicitations(config.UTILITY_ELICITATIONS, model))
    reacts = R.load_reactions(config.REACTIONS_LOG, config.DECISIONS_LOG)
    row0 = sorted(targets, key=lambda r: str(r["tx_time"]))[0]
    as_of = str(row0["tx_time"])
    u_prior = u_bar_from(brain, [])
    u_elicit = u_bar_from(brain, [e for e in elicits if str(e.tx_time) <= as_of])
    u_now, _v, n_now = u_bar_as_of(brain, "9999")
    scales = scale_latents_present(u_now)
    scoped_winner = any(r["reproduced"] == "report_scoped" for r in results)

    print("\nC2 — the attenuation candidates:")
    print(f"  units-lever scales opted in ....... {scales or 'NONE'} "
          f"⇒ shaped_u_bar is the identity for every shape")
    print(f"  scoped substitution in the winner . {'YES' if scoped_winner else 'NO'}")
    print(f"  fold-version mismatch ............ {'YES' if c1_version < n else 'NO'}")
    print(f"  defaulted latents on the rows .... "
          f"{sorted({d for r in targets for d in (r.get('defaulted') or [])}) or 'NONE'}")

    u_asof, _va, n_asof = u_bar_as_of(brain, as_of)
    print("\n    the bar, decomposed (same deployed fold, four evidence sets):")
    for label, ub, ne in (("model prior only", u_prior, 0),
                          ("+ elicitations", u_elicit, len(u_elicit) and len(elicits)),
                          ("+ reactions (as priced)", u_asof, n_asof),
                          ("+ reactions (today)", u_now, n_now)):
        print(f"      {label:<26} u_wrong={ub['u_wrong']:+.4f}  "
              f"p†={indifference_point(ub):.4f}  (n={ne})")
    print(f"      reaction events folded: {len(reacts)} of "
          f"{len(reacts) + len(elicits)} total")

    # --- the census: where the window's rows sit relative to both bars ------------------
    p_star, p_dag = 0.90, results[0]["p_dagger"]
    window = []
    for r in rows:
        if r.get("family") != "lookup" or str(r.get("tx_time", "")) < "2026-08-29":
            continue
        try:
            window.append((max(atom_probs(r)[:-1]), str(r["chosen_action"])))
        except UnreadableRowError:
            continue
    band = [lead for lead, act in window if p_dag <= lead < p_star]
    below = sorted(lead for lead, act in window if act == "abstain")
    print(f"\n  census — {len(window)} readable lookup rows since 2026-08-29 "
          f"({sum(1 for _, a in window if a.startswith('report'))} report / "
          f"{sum(1 for _, a in window if a == 'abstain')} abstain)")
    print(f"    leaders in the band [p†={p_dag:.4f}, p*={p_star:.2f}): {len(band)} "
          f"— admitted by the deployed bar, refused by the declared one")
    if below:
        print(f"    abstained leaders: max {below[-1]:.4f} · median "
              f"{below[len(below) // 2]:.4f} · min {below[0]:.4f}")
        print(f"    abstained leaders within 0.05 of p†: "
              f"{sum(1 for x in below if p_dag - 0.05 <= x < p_dag)}")

    leak = bool(scales) or scoped_winner or c1_version < n
    print(f"\nVERDICT: {'LEAK' if leak else 'PRICED'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
