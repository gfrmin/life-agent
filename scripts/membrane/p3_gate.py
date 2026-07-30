"""p3_gate.py — the held-out actual-policy gate run (register §17.5).

The forecast the §17.4 seed (`lattice_replay.py`) could not give: `lattice_replay` folds every
question's own verdict before probing it (in-sample, +0.043 EU/q). P3 removes each scored
question's *entire* set of verdict ticks from the fold before probing it — grouped
leave-one-question-out (LOO) — so the priced commit policy is a genuine forecast. The
protocol, arms, bar, and decision rule are frozen blind in
`docs/membrane/p3-pre-registration.md` (committed before this ran).

Pure logic (hermetically tested in `tests/test_p3_gate.py`): the question-keyed verdict join,
the LOO grouping, per-tick pricing, question-level act aggregation, and the recomputed-hash
join to the credence baseline. The engine probe (`probe_heldout`) needs the real
`proplang-host` and is a scripted step, like `lattice_replay.main`.

Run: `uv run --project . python scripts/membrane/p3_gate.py`
"""
from __future__ import annotations

import argparse
import json
import statistics as st
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, "scripts")

import membrane.lattice_replay as LR
import membrane.report as R
from life_agent.core import config as C
from life_agent.core import decisions as DEC
from life_agent.membrane import shadow as SH
from life_agent.membrane import world as W
from life_agent.membrane.client import MembraneClient
from life_agent.membrane.session import verdict_y  # defined here; shadow only re-exports it

# --- question-keyed verdict replay (boot_snapshot's join, keeping the question id) --------


@dataclass(frozen=True)
class KeyedTick:
    """One verdict tick with its question identity kept (``boot_snapshot`` drops it)."""

    question_id: str
    summary: W.DecideSummary
    y: int


def keyed_verdict_replay(
    decisions: Sequence[Any], reactions: Sequence[Any], claude_verdicts: Sequence[Any],
) -> list[KeyedTick]:
    """Mirror :func:`shadow.boot_snapshot`'s ``decisions ⋈ reactions ⋈ claude_verdicts`` join
    exactly (owner precedence by source, latest-reaction-per-decision, ``verdict_y`` decode),
    but carry ``d.question_id`` on each tick. Deterministic order: owner segment, then Claude
    segment — the same order ``boot_snapshot`` replays, so the fold is byte-identical when a
    variant declares the full stream."""
    import life_agent.core.claude_verdicts as CV

    by_id = {d.decision_id: d for d in decisions if d.decision_id}
    latest_reaction: dict[str, Any] = {}
    for r in reactions:
        latest_reaction[r.decision_id] = r

    out: list[KeyedTick] = []
    for decision_id, r in latest_reaction.items():
        d = by_id.get(decision_id)
        if d is None:
            continue
        y = verdict_y(d.chosen_action, r.valence)
        if y is None:
            continue
        out.append(KeyedTick(d.question_id, W.summary_from_decision_event(asdict(d)), y))
    for decision_id, cv in CV.latest_by_decision(list(claude_verdicts)).items():
        d = by_id.get(decision_id)
        if d is None:
            continue
        r_owner = latest_reaction.get(decision_id)
        if r_owner is not None and verdict_y(d.chosen_action, r_owner.valence) is not None:
            continue  # owner's routable verdict overrules the Claude one (boot_snapshot's rule)
        out.append(KeyedTick(d.question_id, W.summary_from_decision_event(asdict(d)), CV.y(cv)))
    return out


def load_keyed_replay() -> list[KeyedTick]:
    """The keyed replay over the live ledger — the state the flip would ship under."""
    return keyed_verdict_replay(
        SH._read_decisions(C.DECISIONS_LOG),
        SH._read_reactions(C.REACTIONS_LOG),
        SH._read_claude_verdicts(C.CLAUDE_VERDICTS_LOG),
    )


def group_by_question(keyed: Sequence[KeyedTick]) -> dict[str, list[KeyedTick]]:
    """{question_id: its ticks}, insertion-ordered — the LOO grouping key."""
    groups: dict[str, list[KeyedTick]] = {}
    for t in keyed:
        groups.setdefault(t.question_id, []).append(t)
    return groups


# --- the held-out probe (needs the engine) -----------------------------------------------


@dataclass(frozen=True)
class HeldoutTick:
    """One scored row: a question's tick, probed against the fold that EXCLUDES that question."""

    question_id: str
    leader_credence: float | None
    p1: float | None
    y: int
    respond: bool


def probe_heldout(
    keyed: Sequence[KeyedTick], u_bar: Mapping[str, float], engine: str,
    families: Sequence[str] = tuple(LR.ALL_FAMILIES),
    *, log: Callable[[str], None] = lambda _m: None, read_timeout_s: float = 300.0,
) -> list[HeldoutTick]:
    """Grouped-LOO forecast: for each question, fold every OTHER question's ticks, then probe
    this question's leader-credence-bearing ticks and record the engine's commit
    (``respond`` iff ``commits_respond`` at the probed p1). One fresh engine per question."""
    groups = group_by_question(keyed)
    rows: list[HeldoutTick] = []
    for qi, (qid, my_ticks) in enumerate(groups.items(), 1):
        train = [t for t in keyed if t.question_id != qid]
        probe = [t for t in my_ticks if t.summary.leader_credence is not None]
        if not probe:
            continue
        client = MembraneClient.spawn([engine], log=lambda _m: None,
                                      read_timeout_s=read_timeout_s)
        try:
            hs = client.request(LR.handshake_for(u_bar, families))
            if not hs.get("ok"):
                log(f"[{qid}] handshake refused: {hs!r}")
                continue
            t = 0
            for tick in train:
                client.request({"tick": {
                    "features": LR.features_for(tick.summary, float(t), families),
                    "evidence": int(tick.y)}})
                t += 1
            for tick in probe:
                dec = client.request({"tick": {
                    "features": LR.features_for(tick.summary, float(t), families),
                    "menu": [W.ACT_NAME]}})
                p1 = LR._p1(dec)
                respond = p1 is not None and LR.commits_respond(u_bar, p1)
                rows.append(HeldoutTick(qid, tick.summary.leader_credence, p1, tick.y, respond))
        finally:
            client.shutdown()
        n_resp = sum(1 for r in rows if r.question_id == qid and r.respond)
        log(f"  [{qi}/{len(groups)}] {qid}: {len(probe)} tick(s) "
            f"(train={len(train)}, responded={n_resp})")
    return rows


# --- pricing A1 (pure) -------------------------------------------------------------------


def _tick_response(row: HeldoutTick) -> Any:
    """The realised act of one held-out tick, as a gate ``RealisedResponse`` (report iff the
    engine committed respond; graded correct by the tick's own label)."""
    import life_agent.core.gate as GATE

    if row.respond:
        return GATE.RealisedResponse("report", correct=bool(row.y))
    return GATE.RealisedResponse("abstain")


def price_at_u_bar(rows: Sequence[HeldoutTick], u_bar: Mapping[str, float],
                   *, oracle_p: float) -> dict[str, Any]:
    """A1 at Ū: EU/q for the actual commit policy vs the respond-all counterfactual vs abstain,
    with the per-leader-credence-bucket breakdown (the §17.4 curve, now held-out)."""
    import life_agent.core.gate as GATE

    u = dict(u_bar)
    policy = [GATE.realised_utility(_tick_response(r), u, oracle_p=oracle_p) for r in rows]
    respond_all = [
        GATE.realised_utility(GATE.RealisedResponse("report", correct=bool(r.y)), u,
                              oracle_p=oracle_p)
        for r in rows]
    n = len(rows)
    buckets = []
    for lo, hi, name in LR._CREDENCE_EDGES:
        g = [r for r in rows if r.leader_credence is not None and lo <= r.leader_credence < hi]
        if not g:
            continue
        ps = [r.p1 for r in g if r.p1 is not None]
        buckets.append({
            "bucket": name, "n": len(g),
            "correct": sum(r.y for r in g) / len(g),
            "mean_p1": st.mean(ps) if ps else None,
            "n_respond": sum(1 for r in g if r.respond),
            "policy_eu": st.mean(
                GATE.realised_utility(_tick_response(r), u, oracle_p=oracle_p) for r in g),
        })
    p1s = [r.p1 for r in rows if r.p1 is not None]
    return {
        "n": n,
        "policy_eu_per_q": (sum(policy) / n) if n else 0.0,
        "respond_all_eu_per_q": (sum(respond_all) / n) if n else 0.0,
        "p1_spread": (max(p1s) - min(p1s)) if p1s else 0.0,
        "n_respond": sum(1 for r in rows if r.respond),
        "buckets": buckets,
    }


def price_under_pu(rows: Sequence[HeldoutTick], posterior: Any, *, oracle_p: float,
                   n_draws: int, seed: int) -> tuple[float, float, float]:
    """A1's P(U) interval: EU/q of the policy integrated over the utility posterior — the
    same ``_sample_u`` sampler the gate and loss-ledger use. Returns (mean, q05, q95) of the
    per-draw EU/q."""
    import random

    import life_agent.core.gate as GATE

    resp = [_tick_response(r) for r in rows]
    n = len(rows)
    rng = random.Random(seed)
    per_draw: list[float] = []
    for _ in range(n_draws):
        u = GATE._sample_u(posterior, rng)
        per_draw.append(
            sum(GATE.realised_utility(r, u, oracle_p=oracle_p) for r in resp) / n if n else 0.0)
    per_draw.sort()
    return (sum(per_draw) / n_draws, per_draw[int(0.05 * n_draws)],
            per_draw[min(int(0.95 * n_draws), n_draws - 1)])


# --- A3 the differential gate: question-level acts + the hash join (pure) -----------------


def question_acts(rows: Sequence[HeldoutTick]) -> dict[str, Any]:
    """One realised act per question for the gate: report iff a majority of the question's
    ticks committed respond (tie → respond, the assertive side — the gate cannot be flattered
    by abstaining a tie). When it reports, correct = majority label over the RESPONDED ticks
    (tie → wrong, anti-flattering)."""
    import life_agent.core.gate as GATE

    by_q: dict[str, list[HeldoutTick]] = {}
    for r in rows:
        by_q.setdefault(r.question_id, []).append(r)
    acts: dict[str, Any] = {}
    for qid, ticks in by_q.items():
        responded = [t for t in ticks if t.respond]
        if 2 * len(responded) >= len(ticks):  # majority-respond, tie → respond
            n_right = sum(t.y for t in responded)
            correct = (2 * n_right > len(responded)) if responded else False  # tie → wrong
            acts[qid] = GATE.RealisedResponse("report", correct=correct)
        else:
            acts[qid] = GATE.RealisedResponse("abstain")
    return acts


def hash_to_qid(questions: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    """{question_id_hash: corpus_id} via ``DEC.question_id`` recompute — the deterministic join
    from the anonymous verdict hashes to the fair-fight baseline's ``q2-*`` ids."""
    return {DEC.question_id(q["question"]): str(q["id"]) for q in questions}


def build_paired(
    membrane_acts: Mapping[str, Any], h2q: Mapping[str, str],
    baseline_rows: Sequence[dict[str, Any]],
) -> tuple[list[Any], list[str], list[str]]:
    """A3 pairing: ``PairedOutcome(typed=membrane held-out act, mono=baseline realised act)``
    over the questions that (a) have a held-out membrane act, (b) map to a corpus id, and
    (c) appear in the baseline arm. Returns (paired, only_membrane_named, only_baseline_named)
    — unjoined questions are named, never silently dropped."""
    from fairfight import loss_ledger as LL

    import life_agent.core.gate as GATE

    by_qid = {str(r["question_id"]): r for r in baseline_rows}
    paired: list[Any] = []
    joined_corpus_ids: set[str] = set()
    for vhash, act in membrane_acts.items():
        qid = h2q.get(vhash)
        if qid is None or qid not in by_qid:
            continue
        brow = by_qid[qid]
        joined_corpus_ids.add(qid)
        paired.append(GATE.PairedOutcome(
            question_id=qid, answerable=bool(brow.get("answerable", bool(brow.get("answer", "")))),
            typed=act, mono=LL.actual_response(brow)))
    only_membrane = sorted(h for h in membrane_acts if h2q.get(h) not in by_qid)
    only_baseline = sorted(q for q in by_qid if q not in joined_corpus_ids)
    return paired, only_membrane, only_baseline


# --- the run (needs the engine + the baseline arm) ----------------------------------------


def _load_baseline_rows(run_dir: Path, arm: str) -> list[dict[str, Any]]:
    path = run_dir / "arms" / arm / "vectors.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def _load_v2_questions(path: Path) -> list[dict[str, Any]]:
    import yaml

    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    return doc["questions"] if isinstance(doc, dict) and "questions" in doc else doc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", default=LR.DEFAULT_ENGINE)
    parser.add_argument("--baseline-run", type=Path,
                        default=Path.home() / ".local/share/life-agent/eval/fairfight/"
                        "ff-v2-baseline-m3off")
    parser.add_argument("--baseline-arm", default="baseline")
    parser.add_argument("--questions-v2", type=Path,
                        default=Path.home() / ".local/share/life-agent/eval/questions_v2.yaml")
    parser.add_argument("--draws", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=8675309)
    parser.add_argument("--out", type=Path,
                        default=Path.home() / ".local/share/life-agent/eval/p3")
    args = parser.parse_args(argv)

    import life_agent.core.gate as GATE
    import life_agent.core.lookup as LK
    import life_agent.core.utility as UT
    from life_agent.core import config as LCFG

    keyed = load_keyed_replay()
    groups = group_by_question(keyed)
    u_bar = R.latest_boot_u_bar(R.load_shadow_records(C.membrane_shadow_log()), "said@1")
    if u_bar is None:
        print("no boot u_bar on the shadow log; cannot run.")
        return 1
    # the EFFECTIVE commit bar: the smallest p1 at which coarse._gather's restricted argmax
    # (gather deleted, ask + abstain kept) picks respond — NOT world.respond_threshold, which
    # is the full-menu bar (respond must also outbid gather, ≈0.994). The commit rule the flip
    # would run is the restricted one, so this is the number that governs.
    commit_bar = next((p / 1000 for p in range(1001)
                       if LR.commits_respond(u_bar, p / 1000)), None)
    full_bar = W.respond_threshold(u_bar)
    print(f"keyed replay: {len(keyed)} ticks / {len(groups)} questions; "
          f"commit bar (gather-exhausted, incl ask) p1 ≈ "
          f"{commit_bar:.4f}" if commit_bar is not None else "commit bar = n/a (never fires)")
    print(f"  (full-menu respond bar = "
          f"{full_bar:.4f} — includes gather, not the commit rule)"
          if full_bar is not None else "  (full-menu respond bar = n/a)")

    # A1 + A2: held-out actual policy, FULL vs the narrowed variants
    variants = {"FULL": tuple(LR.ALL_FAMILIES),
                "leader-credence-only": ("leader-credence",),
                "leader-credence+p-none": ("leader-credence", "p-none")}
    brain = LK.shared_brain()
    model = UT.load_model(LCFG.UTILITY_MODEL)
    evidence: list[UT.Evidence] = list(UT.load_elicitations(LCFG.UTILITY_ELICITATIONS, model))
    posterior = UT.posterior(brain, model, evidence)

    results: dict[str, Any] = {"variants": {}}
    full_rows: list[HeldoutTick] = []
    for name, fams in variants.items():
        print(f"\n=== A1/A2 held-out variant: {name} (families={list(fams)}) ===")
        rows = probe_heldout(keyed, u_bar, args.engine, fams, log=print)
        at_bar = price_at_u_bar(rows, u_bar, oracle_p=LK._ORACLE_P)
        mean, q05, q95 = price_under_pu(rows, posterior, oracle_p=LK._ORACLE_P,
                                        n_draws=args.draws, seed=args.seed)
        at_bar["pu_mean"], at_bar["pu_q05"], at_bar["pu_q95"] = mean, q05, q95
        results["variants"][name] = at_bar
        if name == "FULL":
            full_rows = rows
        print(f"  policy EU/q @Ū: {at_bar['policy_eu_per_q']:+.4f}  "
              f"(respond-all {at_bar['respond_all_eu_per_q']:+.4f}, abstain 0)")
        print(f"  P(U) EU/q: {mean:+.4f} [{q05:+.4f}, {q95:+.4f}]  ·  "
              f"p1 spread {at_bar['p1_spread']:.4f}  ·  "
              f"responded {at_bar['n_respond']}/{at_bar['n']}")
        for b in at_bar["buckets"]:
            mp1 = f"{b['mean_p1']:.4f}" if b["mean_p1"] is not None else "n/a"
            print(f"    {b['bucket']:>6} n={b['n']:>3} correct={b['correct']:.3f} "
                  f"mean_p1={mp1} respond={b['n_respond']:>3} EU/q={b['policy_eu']:+.3f}")

    # A3: the differential gate (FULL membrane held-out acts vs the credence baseline)
    print("\n=== A3 differential adoption gate: membrane (held-out, FULL) vs credence baseline ===")
    acts = question_acts(full_rows)
    h2q = hash_to_qid(_load_v2_questions(args.questions_v2))
    baseline_rows = _load_baseline_rows(args.baseline_run, args.baseline_arm)
    paired, only_m, only_b = build_paired(acts, h2q, baseline_rows)
    print(f"  joined {len(paired)} questions  ·  membrane-only (non-v2/live) {len(only_m)}  "
          f"·  baseline-only {len(only_b)}")
    gate = GATE.delta_posterior(paired, posterior, oracle_p=LK._ORACLE_P,
                                n_draws=args.draws, seed=args.seed)
    verdict = "PASS" if gate.passed else "FAIL"
    print(f"  verdict {verdict} · P(Δ>{gate.materiality_delta})={gate.p_delta_gt:.3f} "
          f"(gate ≥ {gate.level:.2f}) · Δ̄={gate.delta_mean:+.3f} "
          f"[{gate.delta_lo:+.3f}, {gate.delta_hi:+.3f}]")
    d = gate.diagnostics
    ar = lambda x: "n/a" if x is None else f"{x:.2f}"  # noqa: E731
    print(f"  answer rate: membrane {ar(d.typed_answer_rate)} · baseline {ar(d.mono_answer_rate)} "
          f"· disagreement {d.disagreement_n}/{d.n}")

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "a1_a2.json").write_text(json.dumps(results, indent=2, sort_keys=True) + "\n",
                                         encoding="utf-8")
    (args.out / "a3_gate.md").write_text(
        GATE.render_report(gate, run_id="p3-heldout", elapsed=0.0), encoding="utf-8")
    (args.out / "a3_paired.jsonl").write_text(
        "".join(json.dumps({"question_id": p.question_id, "answerable": p.answerable,
                            "typed": {"action": p.typed.action, "correct": p.typed.correct},
                            "mono": {"action": p.mono.action, "correct": p.mono.correct}},
                           sort_keys=True) + "\n" for p in paired), encoding="utf-8")
    (args.out / "unjoined.json").write_text(
        json.dumps({"membrane_only": only_m, "baseline_only": only_b}, indent=2) + "\n",
        encoding="utf-8")
    print(f"\nWrote → {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
