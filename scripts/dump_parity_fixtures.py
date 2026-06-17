#!/usr/bin/env python3
"""Generate Stage-0 → answer-brain parity fixtures (the reference oracle).

The credence `answer-brain` app (Stage 1 of the principled-RAG-agent plan) re-implements
this repo's validated lookup decision core — the tempered candidate posterior
(:func:`life_agent.core.lookup.lookup_posterior`) and the EU decision
(:func:`~life_agent.core.lookup.decide`) — in native Julia. This script runs the Python
path (through the credence skin) on a battery of *synthetic* observation sets and dumps,
per case, the integer-indexed observations the brain consumes plus the reference
`(weights, p_none, action, eu)`. The Julia brain must reproduce them exactly.

The parity boundary (principled): the brain reasons over ABSTRACT candidates and evidence
groups. Candidate identity (string canon, `_candidate_key`) and covariate projection are
the body's job and stay in Python — so each emitted observation is pure integers/floats:
``{reports: <candidate idx>, group: <ancestry group idx>, authority, subject_factor,
time_factor}``. No PII: every value is a synthetic label.

Run (spawns the Julia skin — first run cold-compiles, minutes):
    uv run python scripts/dump_parity_fixtures.py --out /tmp/stage0_parity.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from life_agent.core import lookup as LK
from life_agent.core.brain import Brain

# A synthetic owner utility Ū. NOT the frozen priors — chosen per case below to exercise
# each terminal action's win region (report / hedge / ask_clarify / abstain), so parity
# covers every decision branch. kappa_att is narrative-only; lookup ignores it.
GAUGE = {"u_correct": 1.0, "u_abstain": 0.0}


def ubar(*, u_wrong: float, u_hedged: float, lambda_int: float) -> dict[str, float]:
    return {**GAUGE, "u_wrong": u_wrong, "u_hedged": u_hedged,
            "lambda_int": lambda_int, "kappa_att": 0.0}


# Each case: a list of observations (value_label, group_label, authority, subject_factor,
# time_factor), the extractor reliability rho, and Ū. Labels are arbitrary synthetic
# tokens; distinct value_labels are distinct candidates, shared group_labels share an
# ancestry group (one source document → §4.2 ancestry temper).
CASES: list[dict] = [
    {
        "name": "single-observation",
        "obs": [("A", "d0", 0.90, 1.0, 1.0)],
        "rho": 0.5, "ubar": ubar(u_wrong=-4.0, u_hedged=-0.5, lambda_int=0.05),
    },
    {
        "name": "ancestry-temper-two-chunks-one-doc",
        "obs": [("A", "d0", 0.95, 1.0, 1.0), ("A", "d0", 0.95, 1.0, 1.0)],
        "rho": 0.6, "ubar": ubar(u_wrong=-4.0, u_hedged=-0.5, lambda_int=0.05),
    },
    {
        "name": "model-temper-two-docs-agree",
        "obs": [("A", "d0", 0.95, 1.0, 1.0), ("A", "d1", 0.95, 1.0, 1.0)],
        "rho": 0.6, "ubar": ubar(u_wrong=-4.0, u_hedged=-0.5, lambda_int=0.05),
    },
    {
        "name": "covariates-subject-and-time-attenuate",
        "obs": [("A", "d0", 0.95, 0.05, 0.30), ("B", "d1", 0.90, 1.0, 1.0)],
        "rho": 0.6, "ubar": ubar(u_wrong=-4.0, u_hedged=-0.5, lambda_int=0.05),
    },
    {
        "name": "none-dominant-weak-single",
        "obs": [("A", "d0", 0.80, 1.0, 0.10)],
        "rho": 0.3, "ubar": ubar(u_wrong=-6.0, u_hedged=-0.5, lambda_int=0.20),
    },
    {
        "name": "dispersed-three-docs-disagree",
        "obs": [("A", "d0", 0.90, 1.0, 1.0), ("B", "d1", 0.90, 1.0, 1.0),
                ("C", "d2", 0.90, 1.0, 1.0)],
        "rho": 0.5, "ubar": ubar(u_wrong=-4.0, u_hedged=-0.5, lambda_int=0.40),
    },
    {
        "name": "clear-leader-ask-attractive",
        "obs": [("A", "d0", 0.95, 1.0, 1.0), ("A", "d1", 0.95, 1.0, 1.0),
                ("B", "d2", 0.90, 1.0, 1.0)],
        "rho": 0.55, "ubar": ubar(u_wrong=-9.0, u_hedged=-0.5, lambda_int=0.02),
    },
    {
        # high λ_int sinks ask_clarify below the gauge zero; a positive u_hedged on a
        # two-way near-tie with little NONE mass lets the named-set hedge win.
        "name": "hedge-wins-two-way-tie-costly-ask",
        "obs": [("A", "d0", 0.95, 1.0, 1.0), ("B", "d1", 0.95, 1.0, 1.0)],
        "rho": 0.7, "ubar": ubar(u_wrong=-4.0, u_hedged=0.70, lambda_int=1.0),
    },
    {
        # everything negative: dispersed posterior (report < 0), costly ask (λ_int > oracle
        # value, ask < 0), negative hedge — only abstain at the gauge zero survives.
        "name": "abstain-wins-dispersed-costly-ask",
        "obs": [("A", "d0", 0.90, 1.0, 1.0), ("B", "d1", 0.90, 1.0, 1.0),
                ("C", "d2", 0.90, 1.0, 1.0)],
        "rho": 0.5, "ubar": ubar(u_wrong=-4.0, u_hedged=-0.5, lambda_int=1.0),
    },
    {
        "name": "report-wins-sharp-posterior",
        "obs": [("A", "d0", 0.98, 1.0, 1.0), ("A", "d1", 0.98, 1.0, 1.0),
                ("A", "d2", 0.98, 1.0, 1.0), ("A", "d3", 0.98, 1.0, 1.0)],
        "rho": 0.9, "ubar": ubar(u_wrong=-1.0, u_hedged=-0.5, lambda_int=0.50),
    },
]


def _observation(i: int, value_label: str, group_label: str,
                 authority: float, subject_factor: float,
                 time_factor: float) -> LK.Observation:
    value_raw = f"VALUE_{value_label}"
    return LK.Observation(
        card_n=i + 1,
        artifact_cache_key=f"doc_{group_label}",
        obs_cache_key=f"obs_{i}",
        value_raw=value_raw,
        value_norm=LK._norm_value(value_raw),
        quote="",
        authority_class="synthetic",
        authority=authority,
        subject_factor=subject_factor,
        time_factor=time_factor,
    )


def build_case(brain: Brain, case: dict) -> dict:
    observations = [_observation(i, *spec) for i, spec in enumerate(case["obs"])]
    candidates = LK.candidates_from(observations)
    cand_index = {LK._candidate_key(c): j for j, c in enumerate(candidates)}
    group_order: dict[str, int] = {}
    for o in observations:
        group_order.setdefault(o.artifact_cache_key, len(group_order))

    rho = float(case["rho"])
    weights, state_id = LK.lookup_posterior(brain, observations, candidates, rho)
    try:
        action, eu = LK.decide(brain, state_id, weights, case["ubar"])
    finally:
        brain.destroy_state(state_id)

    emitted_obs = [
        {"reports": cand_index[LK._candidate_key(o.value_raw)],
         "group": group_order[o.artifact_cache_key],
         "authority": o.authority,
         "subject_factor": o.subject_factor,
         "time_factor": o.time_factor}
        for o in observations
    ]
    return {
        "name": case["name"],
        "k": len(candidates),
        "rho": rho,
        "u_bar": case["ubar"],
        "observations": emitted_obs,
        "expected": {
            "weights": [float(w) for w in weights],   # candidates then NONE (last)
            "p_none": float(weights[-1]),
            "action": action,
            "eu": float(eu),
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=None,
                    help="write the fixtures JSON here (default: stdout)")
    args = ap.parse_args()

    with Brain.spawn() as brain:
        brain.initialize()
        cases = [build_case(brain, c) for c in CASES]

    payload = {
        "schema": "answer-brain/parity/v1",
        "channel_params": {
            "A_alternatives": LK._A_ALTERNATIVES,
            "beta_ancestry": LK._BETA_ANCESTRY,
            "beta_model": LK._BETA_MODEL,
            "p_none_prior": LK._P_NONE_PRIOR,
            "oracle_p": LK._ORACLE_P,
            "prob_eps": LK._PROB_EPS,
        },
        "action_order": list(LK._ACTION_ORDER),
        "cases": cases,
    }
    text = json.dumps(payload, indent=2, sort_keys=False, ensure_ascii=False)
    if args.out is not None:
        args.out.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {len(cases)} cases → {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
