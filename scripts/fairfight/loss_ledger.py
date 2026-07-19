#!/usr/bin/env python3
"""The explicit loss ledger — per-question expected-utility regret under P(U).

Replaces bucket COUNTS (e.g. 7 correct / 1 confident-wrong / 10 wrongly-withheld) with the
EU regret each loss costs under the owner's utility posterior P(U), so "which loss class do
we attack next?" is answered in expected-utility units, not tallies.

For each graded question in a fair-fight arm's ``vectors.jsonl``:

* the **actual** act the arm took (report / abstain), read off the vector;
* an **oracle** reference act — corpus-omniscient: it reports the gold whenever the gold is
  knowable from the corpus, else it abstains;
* the **regret** = ``realised_utility(oracle) - realised_utility(actual)``, sampled over
  ``u ~ P(U)`` (the §4.4 utility posterior), priced by the SAME ``life_agent.core.gate``
  arithmetic the adoption gate uses — never reimplemented here;
* a deterministic **stage attribution** per question (``confident_wrong`` / ``retrieval_miss``
  / ``extraction_miss`` / ``pooling_loss`` / ``none`` / ``unattributed``), charging the regret
  mass to a fixable stage.

Quantiles are computed over the SAME per-sample totals (never quantile-of-means): a class's
``[q05, q95]`` is the spread of its per-sample regret sum, so utility uncertainty is
integrated correctly.

It reads only an arm's measured vectors plus the (personal, out-of-tree) utility model and
writes only under the run directory.
"""
from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from pathlib import Path

from life_agent.core.gate import RealisedResponse, _sample_u, realised_utility
from life_agent.core.utility import UtilityPosterior

FORMAT_VERSION = 1

# The modelling choices, printed verbatim into the report (the brief's discipline: every
# choice is on the page, not buried in code).
MODELLING_CHOICES: tuple[str, ...] = (
    "actual act: a SCOPED-bucket row is priced as a 'report_scoped' (correct = "
    "asserted_correct, which the graders compute over the scoped value); otherwise "
    "asserted=True is priced as a 'report' (correct = asserted_correct); anything else "
    "(declined) is an 'abstain'.",
    "hedges are folded into 'report' in v1 — the vectors carry buckets, not the fine "
    "action; refine later from decision_view.",
    "oracle: corpus-omniscient AND dominating — it reports the gold whenever the gold is "
    "knowable from the corpus (answerable AND gold_in_corpus) OR the arm itself proved the "
    "gold attainable (asserted_correct, even where the retrieval-channel proxy "
    "gold_in_corpus missed it); else it abstains. The oracle therefore dominates every "
    "realised act and regret is never negative — a negative sample would be a bug, not a "
    "finding. Reachability is handled by the stage attribution below, NOT by weakening "
    "the oracle.",
    "regret = realised_utility(oracle) - realised_utility(actual), priced by "
    "life_agent.core.gate.realised_utility under u ~ P(U); ask_clarify would be priced at "
    "oracle_p (life_agent.core.lookup._ORACLE_P), though neither act uses it in v1.",
)


# --- reading the vectors -----------------------------------------------------------------

def load_rows(path: Path) -> list[dict]:
    """The arm's measured vectors, one dict per JSONL line — parsed as plain dicts, since the
    ledger reads only the handful of fields it needs, never the full OutcomeVector schema."""
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def partition_scored(rows: list[dict]) -> tuple[list[dict], int]:
    """(scored rows, excluded count): ``status != "ok"`` is an infra failure, never a graded
    loss — excluded and counted, mirroring ``records.scored``."""
    scored = [r for r in rows if r.get("status") == "ok"]
    return scored, len(rows) - len(scored)


# --- the two acts + the stage label (pure) -----------------------------------------------

def actual_response(row: dict) -> RealisedResponse:
    """The act the arm actually took. A SCOPED row is a report_scoped (its asserted_correct
    is computed over the scoped value — grading.py's asserted_values for a scoped view);
    asserted → a report (graded by asserted_correct); anything else is a withholding,
    priced at the gauge (abstain)."""
    if row["bucket"] == "SCOPED":
        return RealisedResponse("report_scoped", correct=bool(row["asserted_correct"]))
    if row["asserted"]:
        return RealisedResponse("report", correct=bool(row["asserted_correct"]))
    return RealisedResponse("abstain")


def oracle_response(row: dict) -> RealisedResponse:
    """The corpus-omniscient, dominating reference: reports the gold whenever it is knowable
    from the corpus — or whenever the arm itself proved it attainable (asserted_correct,
    unconditionally: the graders never mark it true on an unanswerable or out-of-corpus
    question, but a row that somehow did would still be dominated, never negative-regret) —
    else abstains. Domination keeps regret non-negative by construction (MODELLING_CHOICES)."""
    if bool(row["asserted_correct"]) or (bool(row["answerable"])
                                         and bool(row["gold_in_corpus"])):
        return RealisedResponse("report", correct=True)
    return RealisedResponse("abstain")


def stage_class(row: dict) -> str:
    """The deterministic loss class charged with this question's regret (independent of the
    MC). WRONGLY_WITHHELD carries its retrieval/extraction/pooling ``cause``; a null cause is
    ``unattributed``, as is any bucket outside the known set (never crash — count it)."""
    bucket = row["bucket"]
    if bucket in ("CORRECT", "RIGHTLY_WITHHELD"):
        return "none"
    if bucket == "SCOPED":
        # an honest time-scoped non-answer: its regret (u_correct - u_hedged when the
        # scoped value matches gold, u_correct - u_wrong_scoped when it does not) is the
        # cost of scoping instead of asserting — its own lever, neither a withhold-cause
        # nor the cardinal sin.
        return "scoped"
    if bucket == "CONFIDENT_WRONG":
        return "confident_wrong"
    if bucket == "WRONGLY_WITHHELD":
        cause = row.get("cause")
        return str(cause) if cause else "unattributed"
    return "unattributed"


# --- the ledger record -------------------------------------------------------------------

@dataclass(frozen=True)
class QuestionRegret:
    question_id: str
    cls: str
    bucket: str
    cause: str | None
    mean: float
    q05: float
    q95: float


@dataclass(frozen=True)
class ClassRegret:
    cls: str
    n_questions: int
    question_ids: tuple[str, ...]
    mean: float
    q05: float
    q95: float


@dataclass(frozen=True)
class Ledger:
    run_id: str
    arm: str
    n_samples: int
    seed: int
    posterior_fold_version: str
    u_bar: dict[str, float]
    excluded_rows: int
    per_question: tuple[QuestionRegret, ...]
    per_class: tuple[ClassRegret, ...]
    total_mean: float
    total_q05: float
    total_q95: float


# --- aggregation (pure) ------------------------------------------------------------------

def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs)


def _quantiles(xs: list[float]) -> tuple[float, float, float]:
    """(mean, q05, q95) over the samples themselves — the gate's index convention, never a
    quantile of means."""
    n = len(xs)
    s = sorted(xs)
    return sum(xs) / n, s[int(0.05 * n)], s[min(int(0.95 * n), n - 1)]


def _sum_over_samples(lists: list[list[float]], n_samples: int) -> list[float]:
    """Per-sample sum of several per-question regret vectors: for each sample s, add the
    class's questions THEN quantile (the same-per-sample-totals rule)."""
    if not lists:
        return [0.0] * n_samples
    return [sum(v[s] for v in lists) for s in range(n_samples)]


# --- the Monte-Carlo (the one stateful part) ---------------------------------------------

def regret_samples(rows: list[dict], posterior: UtilityPosterior, *, oracle_p: float,
                   n_samples: int, seed: int) -> dict[str, list[float]]:
    """{question_id: [regret over samples]}. One RNG stream: reproducible from
    (seed, n_samples, posterior state)."""
    oracle = {r["question_id"]: oracle_response(r) for r in rows}
    actual = {r["question_id"]: actual_response(r) for r in rows}
    qids = [r["question_id"] for r in rows]
    per_q: dict[str, list[float]] = {qid: [] for qid in qids}
    rng = random.Random(seed)
    for _ in range(n_samples):
        u = _sample_u(posterior, rng)
        for qid in qids:
            per_q[qid].append(realised_utility(oracle[qid], u, oracle_p=oracle_p)
                              - realised_utility(actual[qid], u, oracle_p=oracle_p))
    return per_q


def build_ledger(rows: list[dict], excluded: int, posterior: UtilityPosterior, *,
                 run_id: str, arm: str, oracle_p: float, n_samples: int,
                 seed: int) -> Ledger:
    """Assemble the ledger from the scored rows and the MC regret samples."""
    per_q = regret_samples(rows, posterior, oracle_p=oracle_p, n_samples=n_samples, seed=seed)
    cls = {r["question_id"]: stage_class(r) for r in rows}
    bucket = {r["question_id"]: str(r["bucket"]) for r in rows}
    cause = {r["question_id"]: (str(r["cause"]) if r.get("cause") else None) for r in rows}

    per_question: list[QuestionRegret] = []
    for qid, samples in per_q.items():
        m, lo, hi = _quantiles(samples)
        per_question.append(QuestionRegret(qid, cls[qid], bucket[qid], cause[qid], m, lo, hi))
    per_question.sort(key=lambda qr: qr.mean, reverse=True)

    per_class: list[ClassRegret] = []
    for c in sorted(set(cls.values())):
        members = [qid for qid in per_q if cls[qid] == c]
        m, lo, hi = _quantiles(_sum_over_samples([per_q[qid] for qid in members], n_samples))
        ids = tuple(sorted(members, key=lambda qid: _mean(per_q[qid]), reverse=True))
        per_class.append(ClassRegret(c, len(members), ids, m, lo, hi))
    per_class.sort(key=lambda cr: cr.mean, reverse=True)

    tm, tlo, thi = _quantiles(_sum_over_samples(list(per_q.values()), n_samples))
    return Ledger(run_id=run_id, arm=arm, n_samples=n_samples, seed=seed,
                  posterior_fold_version=posterior.fold_version, u_bar=posterior.u_bar(),
                  excluded_rows=excluded, per_question=tuple(per_question),
                  per_class=tuple(per_class), total_mean=tm, total_q05=tlo, total_q95=thi)


def load_and_build(run_dir: Path, arm: str, posterior: UtilityPosterior, *, oracle_p: float,
                   n_samples: int, seed: int) -> Ledger:
    rows_all = load_rows(run_dir / "arms" / arm / "vectors.jsonl")
    rows, excluded = partition_scored(rows_all)
    return build_ledger(rows, excluded, posterior, run_id=run_dir.name, arm=arm,
                        oracle_p=oracle_p, n_samples=n_samples, seed=seed)


# --- outputs -----------------------------------------------------------------------------

def to_json_dict(ledger: Ledger) -> dict:
    """The machine round-trip record (``<arm>.json``)."""
    return {
        "format_version": FORMAT_VERSION,
        "run_id": ledger.run_id,
        "arm": ledger.arm,
        "n_samples": ledger.n_samples,
        "seed": ledger.seed,
        "posterior_fold_version": ledger.posterior_fold_version,
        "u_bar": ledger.u_bar,
        "excluded_rows": ledger.excluded_rows,
        "modelling_choices": list(MODELLING_CHOICES),
        "per_question": [
            {"question_id": qr.question_id, "class": qr.cls, "bucket": qr.bucket,
             "cause": qr.cause, "mean": qr.mean, "q05": qr.q05, "q95": qr.q95}
            for qr in ledger.per_question],
        "per_class": [
            {"class": cr.cls, "n_questions": cr.n_questions,
             "question_ids": list(cr.question_ids),
             "mean": cr.mean, "q05": cr.q05, "q95": cr.q95}
            for cr in ledger.per_class],
        "total": {"mean": ledger.total_mean, "q05": ledger.total_q05, "q95": ledger.total_q95},
    }


def render_md(ledger: Ledger) -> str:
    """The human report (``<arm>.md``)."""
    lines = [
        f"# Loss ledger — {ledger.arm} @ {ledger.run_id}",
        "",
        "Per-question expected-utility regret under the owner's utility posterior P(U): the EU "
        "cost of each loss versus a corpus-omniscient oracle, priced by life_agent.core.gate. "
        "Regret is in gauge units (u_correct = 1).",
        "",
        f"- samples: {ledger.n_samples}  ·  seed: {ledger.seed}  ·  "
        f"excluded (status != ok): {ledger.excluded_rows}",
        f"- posterior fold_version: {ledger.posterior_fold_version}",
        "",
        "## Utility posterior mean (Ū)",
        "",
        "```",
        *(f"{k} = {v:+.4f}" for k, v in sorted(ledger.u_bar.items())),
        "```",
        "",
        "## Modelling choices",
        "",
        *(f"- {c}" for c in MODELLING_CHOICES),
        "",
        "## Regret by stage (ranked by mean EU mass, descending)",
        "",
        "| stage | n | mean regret | [q05, q95] |",
        "| --- | ---: | ---: | --- |",
    ]
    lines += [f"| {cr.cls} | {cr.n_questions} | {cr.mean:+.3f} | "
              f"[{cr.q05:+.3f}, {cr.q95:+.3f}] |" for cr in ledger.per_class]
    lines += [
        "",
        "## Top losses (every question with mean regret > 0)",
        "",
        "| question | stage | bucket / cause | mean regret | [q05, q95] |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for qr in ledger.per_question:
        if qr.mean > 0:
            tag = f"{qr.bucket} / {qr.cause}" if qr.cause else qr.bucket
            lines.append(f"| {qr.question_id} | {qr.cls} | {tag} | "
                         f"{qr.mean:+.3f} | [{qr.q05:+.3f}, {qr.q95:+.3f}] |")
    lines += ["", "The ranking above is the explicit basis for 'what do we attack next'."]
    return "\n".join(lines) + "\n"


def write_outputs(run_dir: Path, ledger: Ledger) -> tuple[Path, Path]:
    out = run_dir / "loss_ledger"
    out.mkdir(parents=True, exist_ok=True)
    jpath, mpath = out / f"{ledger.arm}.json", out / f"{ledger.arm}.md"
    jpath.write_text(json.dumps(to_json_dict(ledger), indent=2, sort_keys=True) + "\n",
                     encoding="utf-8")
    mpath.write_text(render_md(ledger), encoding="utf-8")
    return jpath, mpath


def main() -> int:
    parser = argparse.ArgumentParser(description="the explicit loss ledger — per-question EU "
                                                 "regret under P(U)")
    parser.add_argument("--run-dir", required=True, type=Path,
                        help="a fair-fight run directory (holds arms/<arm>/vectors.jsonl)")
    parser.add_argument("--arm", default="baseline", help="which arm's vectors to score")
    parser.add_argument("--samples", type=int, default=4000, help="P(U) Monte-Carlo draws")
    parser.add_argument("--seed", type=int, default=7, help="RNG seed (reproducibility)")
    args = parser.parse_args()

    import life_agent.core.config as LCFG
    import life_agent.core.lookup as LK
    import life_agent.core.utility as UT

    # the FULL utility posterior, folded from the FROZEN model + elicitations (the same wiring
    # the adoption gate uses; blind discipline — untouched here)
    brain = LK.shared_brain()
    model = UT.load_model(LCFG.UTILITY_MODEL)
    evidence: list[UT.Evidence] = list(UT.load_elicitations(LCFG.UTILITY_ELICITATIONS, model))
    posterior = UT.posterior(brain, model, evidence)
    for warning in posterior.endpoint_warnings(model.endpoint_mass_warn):
        print(f"  ⚠ {warning}")

    ledger = load_and_build(args.run_dir, args.arm, posterior, oracle_p=LK._ORACLE_P,
                            n_samples=args.samples, seed=args.seed)
    _jpath, mpath = write_outputs(args.run_dir, ledger)
    print(f"Loss ledger → {mpath}")
    print(f"  posterior fold_version={posterior.fold_version[:12]}  "
          f"n_events={posterior.n_events}  excluded={ledger.excluded_rows}")
    for cr in ledger.per_class:
        print(f"  {cr.cls:<16} n={cr.n_questions:<3} mean={cr.mean:+.3f} "
              f"[{cr.q05:+.3f}, {cr.q95:+.3f}]")
    print(f"  TOTAL            mean={ledger.total_mean:+.3f} "
          f"[{ledger.total_q05:+.3f}, {ledger.total_q95:+.3f}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
