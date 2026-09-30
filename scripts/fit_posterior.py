#!/usr/bin/env python3
"""fit_posterior — fit the posterior's channel constants by log score, and read what the fit
would decide. A measurement: nothing here changes a constant in ``core/pricing.py``.

``capture`` drives each question of a set through the live loop exactly as ``eval/run.py``
does, recording the last evidence-stage ``/decide`` request (the state the final act was taken
in) and its reply, with the truth labelled against the gold: the index of the first candidate
the gold matches, or NONE (-1). One JSONL row per question under
``$LIFE_AGENT_KB/eval/decide-states/``; the rows hold candidate text and never leave the KB.

``check`` recomputes each captured state's posterior at the stated constants and compares its
leader probability with the pinned archive row's ``typed.p1``.

``fit`` scores the stated constants and six fits (tempering, eta, tempering + A, all but
``P_NONE_PRIOR``, ``P_NONE_PRIOR`` alone, all five) by the mean log probability the posterior
gives the truth, in-sample and on the other set, then re-decides every state under each fit
with the evidence held fixed. Prints aggregates only.

    uv run python scripts/fit_posterior.py capture --questions Q.yaml --set generated
    uv run python scripts/fit_posterior.py check --states S.jsonl --archive A.jsonl
    uv run python scripts/fit_posterior.py fit --generated S1.jsonl --owner S2.jsonl
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import random
import statistics
import sys
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval import withheld as WH
from eval.calibration import Calibration, Pairs, calibrate, fmt_bins
from eval.grading import realised_report
from life_agent.core import config as CFG
from life_agent.core import decide as DEC
from life_agent.core import decisions as DCS
from life_agent.core import enact as EN
from life_agent.core import gather_row as GR
from life_agent.core import outcomes as OUT
from life_agent.core import posterior as POST
from life_agent.core import seam as SEAM

NONE = -1  # the truth label of a state whose gold is not among the candidates
TOL_FLAT = 0.01  # a parameter value is "as good as the best" within this mean log score

# --- the states ---------------------------------------------------------------------------


@dataclass(frozen=True)
class State:
    """One question's final evidence state: what the posterior is a function of, what the
    decider was offered, and the truth. ``truth`` is the first candidate the gold matches
    (``NONE`` when none does); ``matches`` is every candidate it matches."""

    question_id: str
    k: int
    observations: tuple[Mapping[str, Any], ...]
    rho: float
    applied: tuple[str, ...]
    transforms: tuple[Mapping[str, Any], ...]
    grow: Mapping[str, Any] | None
    truth: int
    matches: tuple[int, ...]
    weight: float = 1.0
    negative: bool = False   # from a withheld-source run: the answer is absent by construction

    def payload(self) -> dict[str, Any]:
        """The fields ``enact.gather_options`` reads."""
        return {"applied_probes": list(self.applied), "transforms": list(self.transforms),
                "grow": self.grow}


def label(candidates: Sequence[Any], gold: str, variants: Sequence[str]
          ) -> tuple[int, tuple[int, ...]]:
    """``(truth, matches)``: the first candidate the gold matches (``NONE`` if none) and all
    the candidates it matches, by the board's own grader."""
    hits = tuple(i for i, c in enumerate(candidates)
                 if realised_report([str(c)], gold, list(variants)))
    return (hits[0] if hits else NONE), hits


def state_from_row(row: Mapping[str, Any]) -> State:
    """A captured JSONL row, read back."""
    req = row["request"]
    return State(question_id=str(row["question_id"]), k=len(req["candidates"]),
                 observations=tuple(req["observations"]), rho=float(req["rho"]),
                 applied=tuple(str(a) for a in req.get("applied_probes") or []),
                 transforms=tuple(req.get("transforms") or []), grow=req.get("grow"),
                 truth=int(row["truth"]), matches=tuple(int(i) for i in row["matches"]))


def read_states(path: Path) -> list[State]:
    return [state_from_row(json.loads(line))
            for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_negatives(path: Path) -> tuple[list[State], int]:
    """The withheld-source states, leaks excluded: ``(states, leaks dropped)``. A leak is a
    row whose candidates matched the gold, so an attesting document got through and the truth
    is not absent."""
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]
    kept = [replace(state_from_row(r), negative=True) for r in rows if not r.get("leak")]
    return kept, len(rows) - len(kept)


def reweighted(states: Sequence[State], *, negative_weight: float) -> list[State]:
    """The same states with the negatives' likelihood weighted ``negative_weight``."""
    return [replace(s, weight=negative_weight) if s.negative else s for s in states]


# --- the score ----------------------------------------------------------------------------


def posterior_of(state: State, channel: POST.Channel) -> tuple[list[float], float]:
    return POST.candidate_posterior(state.k, list(state.observations), state.rho, channel)


def truth_prob(state: State, channel: POST.Channel) -> float:
    """The probability the posterior gives the truth: a candidate's credence, or NONE's."""
    credences, p_none = posterior_of(state, channel)
    return p_none if state.truth == NONE else credences[state.truth]


def truth_log(p: float) -> float:
    """Log probability of the truth, clamped as the board's log score is."""
    return math.log(min(max(p, OUT.SCORE_EPS), 1.0 - OUT.SCORE_EPS))


def leader_pair(state: State, credences: Sequence[float]) -> tuple[float, bool] | None:
    """``(p1, leader is right)``, the board's binary reading; ``None`` with no candidate."""
    if not credences:
        return None
    lead = DCS.leader_order(list(credences))[0]
    return float(credences[lead]), lead in state.matches


@dataclass(frozen=True)
class Score:
    n: int
    truth_log: float
    leader: Calibration


def score(states: Sequence[State], channel: POST.Channel) -> Score:
    posts = [posterior_of(s, channel) for s in states]
    logs = [truth_log(p_none if s.truth == NONE else cred[s.truth])
            for s, (cred, p_none) in zip(states, posts, strict=True)]
    pairs = [p for s, (cred, _) in zip(states, posts, strict=True)
             if (p := leader_pair(s, cred)) is not None]
    return Score(len(states), sum(logs) / len(logs), calibrate(Pairs(tuple(pairs))))


def truth_objective(states: Sequence[State]) -> Callable[[POST.Channel], float]:
    """The weighted mean log probability of the truth (every weight 1.0: the plain mean)."""
    total = sum(s.weight for s in states)

    def objective(channel: POST.Channel) -> float:
        return sum(s.weight * truth_log(truth_prob(s, channel)) for s in states) / total
    return objective


# --- the search ---------------------------------------------------------------------------


def arange(lo: float, hi: float, step: float) -> list[float]:
    n = round((hi - lo) / step)
    return [round(lo + i * step, 6) for i in range(n + 1)]


GRIDS: dict[str, list[float]] = {
    "beta_ancestry": arange(0.0, 1.0, 0.05),
    "beta_model": arange(0.0, 1.0, 0.05),
    "a_alternatives": [float(a) for a in range(2, 51)],
    "eta": arange(0.5, 4.0, 0.1),
    "p_none_prior": arange(0.02, 0.8, 0.02),
}

#: fit g's grid for ``A``: wide enough to show whether it has an interior optimum.
WIDE_A = [10.0, 20.0, 35.0, 50.0, 75.0, 100.0, 150.0, 200.0, 300.0, 500.0, 1000.0]
GRIDS_WIDE: dict[str, list[float]] = {**GRIDS, "a_alternatives": WIDE_A}
FIT_G = ("beta_model", "a_alternatives")

FITS: dict[str, tuple[str, ...]] = {
    "a tempering": ("beta_ancestry", "beta_model"),
    "b eta": ("eta",),
    "c tempering+A": ("beta_ancestry", "beta_model", "a_alternatives"),
    "d all but P_NONE": ("beta_ancestry", "beta_model", "a_alternatives", "eta"),
    "e P_NONE": ("p_none_prior",),
    "f all free": ("beta_ancestry", "beta_model", "a_alternatives", "eta", "p_none_prior"),
}


def ascend(objective: Callable[[POST.Channel], float], start: POST.Channel,
           free: Sequence[str], grids: Mapping[str, Sequence[float]] = GRIDS,
           max_sweeps: int = 30) -> POST.Channel:
    """Coordinate ascent over the grids of the ``free`` parameters: each sweep moves every
    parameter to its best grid value given the others, until a sweep moves nothing. A move
    needs a strict gain, so a tie keeps the current value."""
    best, best_v = start, objective(start)
    for _ in range(max_sweeps):
        moved = False
        for name in free:
            for v in grids[name]:
                cand = replace(best, **{name: v})
                cv = objective(cand)
                if cv > best_v + 1e-12:
                    best, best_v, moved = cand, cv, True
        if not moved:
            break
    return best


def starts(base: POST.Channel, free: Sequence[str],
           grids: Mapping[str, Sequence[float]] = GRIDS) -> list[POST.Channel]:
    """The baseline plus, for each of the grids' quartiles, every free parameter set there:
    a handful of deterministic starts, so a fit is not the baseline's nearest hill."""
    out = [base]
    for q in (0.25, 0.5, 0.75):
        out.append(replace(base, **{n: grids[n][round(q * (len(grids[n]) - 1))] for n in free}))
    return out


def fit(states: Sequence[State], base: POST.Channel, free: Sequence[str],
        grids: Mapping[str, Sequence[float]] = GRIDS) -> POST.Channel:
    """The best of the ascents from each start, by mean log probability of the truth."""
    objective = truth_objective(states)
    return max((ascend(objective, s, free, grids) for s in starts(base, free, grids)),
               key=objective)


def flatness(states: Sequence[State], best: POST.Channel, free: Sequence[str],
             grids: Mapping[str, Sequence[float]] = GRIDS, tol: float = TOL_FLAT
             ) -> dict[str, tuple[float, float]]:
    """Per free parameter, the lowest and highest grid value whose mean log probability of
    the truth is within ``tol`` of the best's, the others held at the best. A wide range is
    an ill-determined parameter (conditional on the rest, not a profile)."""
    objective = truth_objective(states)
    top = objective(best)
    out: dict[str, tuple[float, float]] = {}
    for name in free:
        ok = [v for v in grids[name] if objective(replace(best, **{name: v})) >= top - tol]
        out[name] = (min(ok), max(ok))
    return out


# --- what the fit would decide -------------------------------------------------------------


def act_at(state: State, channel: POST.Channel, u_bar: Mapping[str, float]) -> DEC.Option:
    """The Bayes act at this state under ``channel``, as ``decider.decide`` takes it."""
    credences, _ = posterior_of(state, channel)
    u = GR.at_step(u_bar, len(state.applied))
    return DEC.bayes_act(u, credences, EN.gather_options(state.payload()))


@dataclass(frozen=True)
class Consequence:
    """The respond decisions over a set's states, evidence held fixed. ``p1`` is, per
    responding state, the credence of the candidate named."""

    n: int
    responds: frozenset[int]        # indices of states whose act is respond
    right: frozenset[int]           # ... and the named candidate is the truth
    utility: float                  # mean utility per state at the gauge
    p1: Mapping[int, float]

    @property
    def wrong(self) -> frozenset[int]:
        return self.responds - self.right


def consequences_each(states: Sequence[State], channels: Sequence[POST.Channel],
                      u_bar: Mapping[str, float]) -> Consequence:
    """Each state decided under its own channel (a cross-validation's held-out fold)."""
    acts = [act_at(s, ch, u_bar) for s, ch in zip(states, channels, strict=True)]
    responds = frozenset(i for i, o in enumerate(acts) if o.action == "respond")
    right = frozenset(i for i in responds
                      if acts[i].target == states[i].truth and states[i].truth != NONE)
    u_right, u_wrong = float(u_bar.get("u_correct", 1.0)), float(u_bar.get("u_wrong", -9.0))
    util = (len(right) * u_right + (len(responds) - len(right)) * u_wrong) / len(states)
    p1 = {i: posterior_of(states[i], channels[i])[0][int(acts[i].target or 0)]
          for i in responds}
    return Consequence(len(states), responds, right, util, p1)


def consequences(states: Sequence[State], channel: POST.Channel,
                 u_bar: Mapping[str, float]) -> Consequence:
    return consequences_each(states, [channel] * len(states), u_bar)


def flips(base: Consequence, new: Consequence) -> tuple[int, int, int]:
    """``(newly respond, of which right, no longer respond)`` relative to ``base``."""
    gained = new.responds - base.responds
    return len(gained), len(gained & new.right), len(base.responds - new.responds)


# --- cross-validation ---------------------------------------------------------------------


def folds(groups: Sequence[str], n_folds: int, seed: int) -> list[int]:
    """A fold index per item, seeded and stratified by group: each group's items are shuffled
    and dealt round-robin, so every fold holds a near-equal share of every group."""
    rng = random.Random(seed)
    out = [0] * len(groups)
    for g in sorted(set(groups)):
        idx = [i for i, x in enumerate(groups) if x == g]
        rng.shuffle(idx)
        for j, i in enumerate(idx):
            out[i] = j % n_folds
    return out


def cross_validate(states: Sequence[State], fold_of: Sequence[int], base: POST.Channel,
                   free: Sequence[str], grids: Mapping[str, Sequence[float]] = GRIDS
                   ) -> list[POST.Channel]:
    """Per state, the channel fitted on every fold but its own: out-of-fold by construction."""
    by_fold = {f: fit([s for s, g in zip(states, fold_of, strict=True) if g != f],
                      base, free, grids) for f in sorted(set(fold_of))}
    return [by_fold[f] for f in fold_of]


def folds_by_question(ids: Sequence[str], groups: Sequence[str], n_folds: int, seed: int
                      ) -> list[int]:
    """A fold per state such that every state of one question shares it (a question's
    positive and withheld states never straddle train and test), stratified by ``groups``."""
    uniq = sorted(set(zip(ids, groups, strict=True)))
    fold = dict(zip((q for q, _ in uniq), folds([g for _, g in uniq], n_folds, seed),
                    strict=True))
    return [fold[q] for q in ids]


def score_each(states: Sequence[State], channels: Sequence[POST.Channel]) -> Score:
    posts = [posterior_of(s, ch) for s, ch in zip(states, channels, strict=True)]
    logs = [truth_log(p_none if s.truth == NONE else cred[s.truth])
            for s, (cred, p_none) in zip(states, posts, strict=True)]
    pairs = [p for s, (cred, _) in zip(states, posts, strict=True)
             if (p := leader_pair(s, cred)) is not None]
    return Score(len(states), sum(logs) / len(logs), calibrate(Pairs(tuple(pairs))))


def _mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else float("nan")


def cmd_cv(a: argparse.Namespace) -> int:
    from life_agent.core import lookup as LK

    sets = {"generated": read_states(Path(a.generated)), "owner": read_states(Path(a.owner))}
    base = POST.default_channel()
    pooled = [s for v in sets.values() for s in v]
    where = [n for n, v in sets.items() for _ in v]
    fold_of = folds(where, a.folds, a.seed)
    folded = LK.current_u_bar()[0]
    gauges = {f"folded u_wrong {folded['u_wrong']:.2f}": folded,
              "prior u_wrong -9": {**folded, "u_wrong": -9.0}}
    # fit g on its own (wide) grid; d on the standard one
    for n in sets:
        ss = sets[n]
        g = fit(ss, base, FIT_G, GRIDS_WIDE)
        fl = flatness(ss, g, FIT_G, GRIDS_WIDE)
        print(f"fit g on {n}: {_fmt_channel(g, FIT_G)}  score {truth_objective(ss)(g):+.4f}  "
              "flat " + "; ".join(f"{k} [{lo:g}, {hi:g}]" for k, (lo, hi) in fl.items()))
    g_all = fit(pooled, base, FIT_G, GRIDS_WIDE)
    print(f"fit g pooled: {_fmt_channel(g_all, FIT_G)} flat " + "; ".join(
        f"{k} [{lo:g}, {hi:g}]" for k, (lo, hi) in flatness(
            pooled, g_all, FIT_G, GRIDS_WIDE).items()))
    chans: dict[str, list[POST.Channel]] = {
        "baseline": [base] * len(pooled),
        "g": cross_validate(pooled, fold_of, base, FIT_G, GRIDS_WIDE),
        "d": cross_validate(pooled, fold_of, base, FITS["d all but P_NONE"])}
    print(f"\n{a.folds}-fold CV by question, seed {a.seed}, stratified by set; out-of-fold only")
    for m, cs in chans.items():
        sc = score_each(pooled, cs)
        print(f"[{m}] truth_log {sc.truth_log:+.4f} leader_log {sc.leader.mean_log:+.4f} "
              f"ECE {sc.leader.ece:.4f}")
        print("\n".join(fmt_bins(sc.leader)))
        for n in sets:
            ix = [i for i, w in enumerate(where) if w == n]
            s2 = score_each([pooled[i] for i in ix], [cs[i] for i in ix])
            print(f"  {n}: truth_log {s2.truth_log:+.4f} leader_log {s2.leader.mean_log:+.4f} "
                  f"ECE {s2.leader.ece:.4f}")
    for gname, u_bar in gauges.items():
        print(f"\n== decisions, out-of-fold, {gname}")
        views = {None: list(range(len(pooled)))} | {
            n: [i for i, w in enumerate(where) if w == n] for n in sets}
        for vname, ix in views.items():
            st = [pooled[i] for i in ix]
            b = consequences_each(st, [chans["baseline"][i] for i in ix], u_bar)
            print(f"[{vname or 'pooled'}] n={len(st)}")
            for m, cs in chans.items():
                c = consequences_each(st, [cs[i] for i in ix], u_bar)
                gained = c.responds - b.responds
                gr, gw = gained & c.right, gained - c.right
                print(f"  {m:<9} respond {len(c.responds)} right {len(c.right)} wrong "
                      f"{len(c.wrong)} U/q {c.utility:+.4f} · new {len(gained)} (right "
                      f"{len(gr)}, wrong {len(gw)}) mean p1 new right "
                      f"{_mean([c.p1[i] for i in gr]):.3f} new wrong "
                      f"{_mean([c.p1[i] for i in gw]):.3f} · stopped "
                      f"{len(b.responds - c.responds)}")
    return 0


# --- the withheld-source negatives -------------------------------------------------------

GRID_A_NEG = [2.0, 5.0, 10.0, 20.0, 35.0, 50.0, 75.0, 100.0, 150.0, 200.0, 300.0, 500.0, 1000.0]
GRIDS_NEG: dict[str, list[float]] = {**GRIDS, "a_alternatives": GRID_A_NEG}
NEG_FITS: dict[str, tuple[str, ...]] = {
    "g": FIT_G, "d": FITS["d all but P_NONE"], "f": FITS["f all free"]}


def _flat_text(flat: Mapping[str, tuple[float, float]]) -> str:
    return "; ".join(f"{k} [{lo:g}, {hi:g}]" for k, (lo, hi) in flat.items())


def _decisions(states: Sequence[State], channels: Sequence[POST.Channel],
               base: Sequence[POST.Channel], u_bar: Mapping[str, float]) -> str:
    c = consequences_each(states, channels, u_bar)
    b = consequences_each(states, base, u_bar)
    gained = c.responds - b.responds
    return (f"respond {len(c.responds)} right {len(c.right)} wrong {len(c.wrong)} "
            f"U/q {c.utility:+.4f} · new {len(gained)} (right {len(gained & c.right)})")


def cmd_neg(a: argparse.Namespace) -> int:
    from life_agent.core import lookup as LK

    pos = {"generated": read_states(Path(a.generated)), "owner": read_states(Path(a.owner))}
    neg, leaks = read_negatives(Path(a.negatives))
    base = POST.default_channel()
    folded = LK.current_u_bar()[0]
    gauges = {f"folded u_wrong {folded['u_wrong']:.2f}": folded,
              "prior u_wrong -9": {**folded, "u_wrong": -9.0}}
    print(f"positives {sum(map(len, pos.values()))} · negatives {len(neg)} "
          f"(leaks excluded {leaks}) · negatives with no candidate {sum(s.k == 0 for s in neg)}")
    # 1. the baseline on the negatives alone
    sc = score(neg, base)
    print(f"[baseline on negatives] log P(NONE) {sc.truth_log:+.4f}")
    pairs = Pairs(tuple((p, False) for s in neg if s.k
                        for p in [max(posterior_of(s, base)[0])]))
    print("\n".join(fmt_bins(calibrate(pairs))) + f"\n  mean p1 "
          f"{sum(p for p, _ in pairs.pairs) / max(len(pairs.pairs), 1):.3f}")
    for gname, u_bar in gauges.items():
        c = consequences(neg, base, u_bar)
        print(f"  {gname}: the act responds on {len(c.responds)} of {len(neg)}")
    # 2. cross-validation over positives + negatives
    states = [s for v in pos.values() for s in v] + neg
    where = [n for n, v in pos.items() for _ in v] + ["generated"] * len(neg)
    ids = [s.question_id for s in states]
    fold_of = folds_by_question(ids, where, a.folds, a.seed)
    subsets = {"pooled": [True] * len(states), "positives": [not s.negative for s in states],
               "negatives": [s.negative for s in states]}
    print("\nfull-data fits (plain weights)")
    full: dict[str, POST.Channel] = {}
    for m, free in NEG_FITS.items():
        full[m] = fit(states, base, free, GRIDS_NEG)
        print(f"  {m}: {_fmt_channel(full[m], free)} flat "
              + _flat_text(flatness(states, full[m], free, GRIDS_NEG)))
    chans = {"baseline": [base] * len(states)} | {
        m: cross_validate(states, fold_of, base, free, GRIDS_NEG)
        for m, free in NEG_FITS.items()}
    print(f"\n{a.folds}-fold CV by question, seed {a.seed}; out-of-fold only")
    for m, cs in chans.items():
        sc = score_each(states, cs)
        print(f"[{m}] truth_log {sc.truth_log:+.4f} leader_log {sc.leader.mean_log:+.4f} "
              f"ECE {sc.leader.ece:.4f}")
        print("\n".join(fmt_bins(sc.leader)))
        for sname, mask in list(subsets.items())[1:]:
            ix = [i for i, k in enumerate(mask) if k]
            s2 = score_each([states[i] for i in ix], [cs[i] for i in ix])
            ece = "—" if s2.leader.ece is None else f"{s2.leader.ece:.4f}"
            print(f"  {sname}: truth_log {s2.truth_log:+.4f} ECE {ece}")
    for gname, u_bar in gauges.items():
        print(f"\n== decisions, out-of-fold, {gname}")
        for sname, mask in subsets.items():
            ix = [i for i, k in enumerate(mask) if k]
            st = [states[i] for i in ix]
            print(f"[{sname}] n={len(st)}")
            for m, cs in chans.items():
                print(f"  {m:<9} " + _decisions(st, [cs[i] for i in ix],
                                               [chans["baseline"][i] for i in ix], u_bar))
    # 3. sensitivity of f to the negatives' weight
    print("\nfit f with the negatives weighted")
    for w in (0.5, 1.0, 2.0):
        ws = reweighted(states, negative_weight=w)
        ch = fit(ws, base, NEG_FITS["f"], GRIDS_NEG)
        print(f"  x{w:g}: {_fmt_channel(ch, NEG_FITS['f'])} flat "
              + _flat_text(flatness(ws, ch, NEG_FITS["f"], GRIDS_NEG)))
    return 0


# --- the capture --------------------------------------------------------------------------


def capture_one(question: str, k: int, *, run_id: str, inner_post: Callable[..., Any],
                drive: Callable[..., Any]) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Drive one question through the live loop; the last evidence-stage ``/decide`` request
    and its reply, or ``None`` when the question never reached one (declined at the route)."""
    seen: list[tuple[dict[str, Any], dict[str, Any]]] = []

    def post(url: str, payload: dict[str, Any]) -> Any:
        resp = inner_post(url, payload)
        if url.endswith("/decide") and payload.get("stage") != SEAM.STAGE_ROUTE:
            seen.append((copy.deepcopy(payload), copy.deepcopy(resp)))
        return resp

    drive(question, k, post=post, run_id=run_id)
    return seen[-1] if seen else None


def capture_row(q: Mapping[str, Any], request: Mapping[str, Any], reply: Mapping[str, Any],
                *, set_name: str, run_id: str, censored: bool,
                withheld: int | None = None) -> dict[str, Any]:
    """One captured state. With ``withheld`` (the number of artifacts taken out of retrieval)
    the answer is absent by construction, so the truth is ``NONE`` whatever the candidates;
    a candidate that does match the gold is a leak and is flagged, not believed."""
    truth, matches = label(request["candidates"], q.get("answer", ""),
                           q.get("answer_variants", []))
    row = {"question_id": str(q["id"]), "set": set_name, "run_id": run_id,
           "censored": censored, "truth": truth, "matches": list(matches),
           "request": dict(request), "reply": dict(reply)}
    if withheld is None:
        return row
    return {**row, "truth": NONE, "matches": [], "withheld": {"n_artifacts": withheld},
            **({"leak": True} if matches else {})}


def cmd_capture(a: argparse.Namespace) -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import ask

    from eval.run import gold_available, load_questions
    from life_agent.core import ask_client as AC

    if a.withhold_source:
        WH.force_deliberate_off()
    if not AC._ready():
        print(f"REFUSED: the bridge at {AC.BRIDGE} is not ready", file=sys.stderr)
        return 2
    questions = load_questions(a.questions)[:a.limit]
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    marker = "-withheld" if a.withhold_source else ""
    run_id = f"gate-posterior-capture{marker}-{stamp}"
    out = Path(a.out) if a.out else (CFG.KB / "eval" / "decide-states"
                                     / f"{a.set}{marker}-{stamp}.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    conn = ask.connect()
    try:
        available = gold_available(conn, questions)
        plans = ({str(q["id"]): WH.plan(conn, q) for q in questions}
                 if a.withhold_source else {})
    finally:
        conn.close()

    def drive(question: str, k: int, *, post: Callable[..., Any], run_id: str) -> Any:
        return AC.drive(question, k, bridge=AC.BRIDGE, post=post, run_id=run_id,
                        ready=AC._ready)

    tally: Counter[str] = Counter()
    with out.open("w", encoding="utf-8") as fh:
        for q in questions:
            qid = str(q["id"])
            post: Callable[..., Any] = AC.post_json
            if a.withhold_source:
                if plans[qid].skipped:
                    tally[f"skipped {plans[qid].skipped}"] += 1
                    continue
                post = WH.with_exclusion(post, plans[qid].keys)
            got = capture_one(q["question"], a.k, run_id=run_id, inner_post=post,
                              drive=drive)
            if got is None:
                tally["no evidence-stage decide"] += 1
                continue
            request, reply = got
            ok = available.get(str(q["id"]), True)
            row = capture_row(q, request, reply, set_name=a.set, run_id=run_id,
                              censored=not ok,
                              withheld=(len(plans[qid].keys) if a.withhold_source else None))
            fh.write(json.dumps(row) + "\n")
            fh.flush()
            tally["captured"] += 1
            tally["truth NONE" if row["truth"] == NONE else "truth a candidate"] += 1
            tally["censored"] += not ok
            if row.get("leak"):
                tally["LEAK"] += 1
    print(f"{a.set}: " + " · ".join(f"{k} {v}" for k, v in sorted(tally.items()))
          + f" of {len(questions)} → $LIFE_AGENT_KB/{out.relative_to(CFG.KB)}")
    return 0


# --- the reproduction check ---------------------------------------------------------------


def reproduction(rows: Sequence[Mapping[str, Any]], archive: Mapping[str, Mapping[str, Any]],
                 tol: float = 1e-9) -> dict[str, int]:
    """How the default-channel posterior of each captured state compares with its archive
    row: ``typed.p1`` within ``tol``, and the truth label against ``typed.leader_correct``."""
    tally: Counter[str] = Counter()
    base = POST.default_channel()
    for row in rows:
        arch = (archive.get(str(row["question_id"])) or {}).get("typed")
        if arch is None:
            tally["no archive row"] += 1
            continue
        s = state_from_row(row)
        credences, _ = posterior_of(s, base)
        pair = leader_pair(s, credences)
        if pair is None or arch.get("p1") is None:
            tally["no candidate"] += 1
            tally["no-candidate both"] += pair is None and arch.get("p1") is None
            continue
        tally["p1 match"] += abs(pair[0] - float(arch["p1"])) <= tol
        tally["p1 differ"] += abs(pair[0] - float(arch["p1"])) > tol
        tally["leader label agrees"] += pair[1] == bool(arch.get("leader_correct"))
        tally["leader label differs"] += pair[1] != bool(arch.get("leader_correct"))
        tally["truth label == first match (leader right)"] += (
            pair[1] and s.truth in s.matches)
    return dict(tally)


def cmd_check(a: argparse.Namespace) -> int:
    rows = [json.loads(line) for line in Path(a.states).read_text().splitlines() if line.strip()]
    archive = {str(r["question_id"]): r for r in
               (json.loads(line) for line in Path(a.archive).read_text().splitlines()
                if line.strip())}
    print(json.dumps(reproduction(rows, archive), sort_keys=True))
    return 0


# --- the report ---------------------------------------------------------------------------


def _fmt_channel(ch: POST.Channel, free: Sequence[str]) -> str:
    return " ".join(f"{n}={getattr(ch, n):g}" for n in free) or "(stated)"


def _line(name: str, sc: Score) -> str:
    return (f"    {name:<14} truth_log {sc.truth_log:+.4f}  leader_log "
            f"{sc.leader.mean_log:+.4f}  ECE {sc.leader.ece:.4f}")


def describe(states: Sequence[State]) -> list[str]:
    def five(xs: Sequence[float]) -> str:
        return f"{min(xs):.3g} / {statistics.median(xs):.3g} / {max(xs):.3g}"
    n_obs = [len(s.observations) for s in states]
    n_groups = [len({o["group"] for o in s.observations}) for s in states]
    return [f"  states {len(states)} · truth NONE {sum(s.truth == NONE for s in states)} · "
            f"k=0 {sum(s.k == 0 for s in states)} · >1 matching candidate "
            f"{sum(len(s.matches) > 1 for s in states)} · gathered before final "
            f"{sum(bool(s.applied) for s in states)}",
            f"  rho min/med/max {five([s.rho for s in states])}",
            f"  observations min/med/max {five(n_obs)} · groups min/med/max {five(n_groups)}"]


def cmd_fit(a: argparse.Namespace) -> int:
    from life_agent.core import lookup as LK

    sets = {"generated": read_states(Path(a.generated)), "owner": read_states(Path(a.owner))}
    base = POST.default_channel()
    u_bar = LK.current_u_bar()[0]
    print(f"u_correct {u_bar['u_correct']:g}  u_wrong {u_bar['u_wrong']:.3f}  "
          f"bar {DEC.respond_threshold(at_step0(u_bar)) or float('nan'):.4f}")
    overlap = ({s.question_id for s in sets["generated"]}
               & {s.question_id for s in sets["owner"]})
    print(f"question-id overlap between the sets: {len(overlap)}")
    for name, states in sets.items():
        print(f"[{name}]")
        print("\n".join(describe(states)))
        sc = score(states, base)
        print(_line("baseline", sc))
        print("\n".join(fmt_bins(sc.leader)))
    fits: dict[str, dict[str, POST.Channel]] = {n: {} for n in sets}
    for name, states in sets.items():
        other = sets["owner" if name == "generated" else "generated"]
        print(f"\n=== fit on {name}, test on {'owner' if name == 'generated' else 'generated'}")
        for fname, free in FITS.items():
            best = fit(states, base, free)
            fits[name][fname] = best
            flat = flatness(states, best, free)
            print(f"  {fname}: {_fmt_channel(best, free)}")
            print(_line("in-sample", score(states, best)))
            print(_line("cross-set", score(other, best)))
            print("    flat within 0.01: " + "; ".join(
                f"{n} [{lo:g}, {hi:g}]" for n, (lo, hi) in flat.items()))
    print("\n=== decisions, evidence held fixed (gauge u_wrong as above)")
    picks = ("a tempering", "d all but P_NONE", "f all free")
    for name, states in sets.items():
        other_name = "owner" if name == "generated" else "generated"
        b = consequences(states, base, u_bar)
        print(f"[{name}] n={b.n}")
        print(f"  baseline            respond {len(b.responds)} right {len(b.right)} "
              f"wrong {len(b.wrong)}  U/q {b.utility:+.4f}")
        for source, label_ in ((name, "in-sample"), (other_name, "from-other-set")):
            for fname in picks:
                ch = fits[source][fname]
                c = consequences(states, ch, u_bar)
                gained, gained_right, lost = flips(b, c)
                print(f"  {fname:<18} {label_:<14} respond {len(c.responds)} right "
                      f"{len(c.right)} wrong {len(c.wrong)}  U/q {c.utility:+.4f}  "
                      f"new respond {gained} (right {gained_right}, wrong "
                      f"{gained - gained_right}) · stopped {lost}")
    return 0


def at_step0(u_bar: Mapping[str, float]) -> dict[str, float]:
    return GR.at_step(u_bar, 0)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    cap = sub.add_parser("capture")
    cap.add_argument("--questions", required=True)
    cap.add_argument("--set", required=True)
    cap.add_argument("--k", type=int, default=20)
    cap.add_argument("--limit", type=int, default=None, help="only the first N questions")
    cap.add_argument("--withhold-source", action="store_true",
                     help="withhold every document attesting each answer (truth NONE for "
                          "every state; a matching candidate is flagged a leak)")
    cap.add_argument("--out", default=None)
    cap.set_defaults(func=cmd_capture)
    chk = sub.add_parser("check")
    chk.add_argument("--states", required=True)
    chk.add_argument("--archive", required=True)
    chk.set_defaults(func=cmd_check)
    ft = sub.add_parser("fit")
    ft.add_argument("--generated", required=True)
    ft.add_argument("--owner", required=True)
    ft.set_defaults(func=cmd_fit)
    cv_ = sub.add_parser("cv")
    cv_.add_argument("--generated", required=True)
    cv_.add_argument("--owner", required=True)
    cv_.add_argument("--folds", type=int, default=5)
    cv_.add_argument("--seed", type=int, default=20260930)
    cv_.set_defaults(func=cmd_cv)
    ng = sub.add_parser("neg")
    ng.add_argument("--generated", required=True)
    ng.add_argument("--owner", required=True)
    ng.add_argument("--negatives", required=True)
    ng.add_argument("--folds", type=int, default=5)
    ng.add_argument("--seed", type=int, default=20260930)
    ng.set_defaults(func=cmd_neg)
    a = ap.parse_args(argv)
    return int(a.func(a))


if __name__ == "__main__":
    raise SystemExit(main())
