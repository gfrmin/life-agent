#!/usr/bin/env python3
"""Carrier audit — does *which document* represents duplicated text decide the answer?

`core/retrieval.retrieve_set` dedupes the over-fetched hits by `chunk_text` and keeps ONE.
That survivor's `artifact_cache_key` becomes the text's carrier for the whole decision:
`observe_hits` reads the §4.1 covariates per artifact, and `lookup_posterior` GROUPS the
observations by artifact — so the choice sets both the weight on an observation and the
correlation structure of the evidence. Byte-identical text scores identically, so the
survivor is in practice the lexicographically smallest content hash: a coin flip frozen by
R2's declared key, not resolved by it (design §6.11).

This audit measures whether that arbitrariness reaches the decision, at zero spend:
extractions are keyed on the chunk sha (`lookup_extract_key`), so re-carrying a
byte-identical chunk is a cache HIT.

FROZEN CRITERIA (stated before any result is read):

1. Scope — TWO surfaces, each read against these criteria separately, and each
   frozen before its own reading.

   (a) The arm's CHEAP FIRST PASS (`retrieve_set(question, k)`, no expansion, no rerank):
       what every question gets.

   (b) The CORROBORATE PROBE (`probes.probe_corroborate`), added to the scope before (a) was
       read, on a defect the code states outright rather than on any result. The registered
       instance of carrier identity was demonstrated on this path, not on (a) — it is where
       §6.9's declared key was convicted — and the mechanism here is strictly sharper: the
       probe ends in `_fresh_hits`, which drops a hit whose carrier is a document already in
       hand. So where a text's carriers STRADDLE the held set, the carrier choice does not
       merely re-weight the corroboration, it decides whether that corroboration EXISTS.
       Scoping to (a) alone would have measured a surface the defect was never shown on.

   Carriers in scope on both surfaces are those inside the caller's own over-fetch window
   (`search(k*4)`): a carrier the retrieval never surfaced could not have been chosen.
   Windows that saturate — where the carrier list may be truncated — are counted and
   reported, never assumed to be zero.

2. Exposure (multi-carried texts, and questions holding one) is REPORTED and is never a
   build bar on its own. The corroborate audit (2026-08-18) was refused after its ceiling
   of 40 turned out to count forwarded copies of one attestation; the standing rule from
   that refusal is that a lever's ceiling is the number of QUESTIONS whose committed answer
   would change — never the number of artifacts, chunks or texts it touches.

3. Load-bearing exposure = questions with >= 1 multi-carried text whose carriers DISAGREE
   on something the decision reads: the §4.1 covariate triple (authority class ·
   subject_state · doc_date), the document partition the observations group by, or — on
   surface (b) only — the text's SURVIVAL of `_fresh_hits`, where its carriers straddle the
   held set. Divergence-free duplication is a no-op and is counted separately.

4. The alternative carrier rule is NAMED HERE, before the measurement, so it cannot be
   chosen to win: the §5 max-covariate representative lifted one layer up — argmax over the
   text's carriers of authority·subject·time, ties broken by the declared key
   `(-round(score, 9), artifact_cache_key, chunk_text)`. This is the rule
   `lookup.dedup_correlated` already applies to the same duplicate-witness question one
   layer down. The adversarial worst-case carrier is computed only to BOUND exposure and is
   never a candidate rule.

5. Delivered reach = questions whose LOOKUP-FAMILY committed answer changes when the top-k
   is re-carried under rule 4. Both arms are recomputed here through the same live decision
   tail (`observe_hits` -> `lookup_posterior` -> `decide`) — the layer the carrier is chosen
   at, and the base decision the executor's menu prices its actions against. It is NOT the
   executor's final answer: rerank, gather and deliberate sit above it and are out of this
   instrument's scope (they spend). So this number informs the BUILD and PRICE decisions and
   is never a prediction of a gate reading — the gate stays the only reach oracle. The
   audited run supplies the question set and its recorded action for context; it is never
   used as one of the two arms. Split into repairs (a wrong commit becomes correct or
   withheld), regressions (a correct commit becomes wrong or withheld), and reach changes
   (a withholding commits, or the reverse).

6. NO SPEND. Every model call is served from cache or the question is excluded and named.
   An uncached owner verdict degrades a carrier's subject_state to `unclear` exactly as the
   live probe does; the count is reported as a limitation, not silently absorbed.

7. The verdict:
   - BUILD the invariance fix iff load-bearing exposure >= 5 questions AND regressions do
     not exceed repairs. Below 5 the defect is real but small: this entry converts to a
     standing known-and-uncovered source (§6.9's own fallback shape) and the arm keeps the
     declared key.
   - REFUSE iff regressions > repairs — the invariant rule would not be better, only
     different.
   - PRICE a gate run iff delivered reach >= 1: a changed commit is a behaviour change, and
     on this path the gate is the only oracle there is (the fixture set tapes the §18.9
     `cache` seam, so a replay never executes `retrieve_set`). At delivered reach 0 the fix
     is behaviour-preserving on this battery and lands on the hermetic
     permutation-invariance test alone, with no run bought.

8. Every excluded or unrecoverable row is named (the no-silent-caps rule).

Usage:
  uv run python scripts/carrier_audit.py --run-id gate-20260821T094545 \
      --paired $KB/eval/gate-outside-option/paired-gate-20260821T094545.jsonl \
      --questions $KB/eval/questions_v2.yaml [--k 20] [--out F.md] [--out-yaml F.yaml]
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gate_splice import load_paired
from run_eval import load_questions

import life_agent.core.lookup as LK
import life_agent.core.matching as MATCH
import life_agent.core.probes as PR
import life_agent.owner as owner
from life_agent.collapse.taps import RefusingClient, WouldSpendError
from life_agent.core import config as LCFG

_COMMITS = ("report", "report_scoped")


def declared_key(h: Any) -> tuple[float, str, str]:
    """R2's declared total order, verbatim — the one `retrieve_set` sorts by."""
    return (-round(h.score, 9), h.artifact_cache_key, h.chunk_text)


# One carrier's covariate identity: (origin, subject_state|None, date_projected, date|None).
# `date_projected` is load-bearing and NOT redundant with `date`: `observe_hits` distinguishes
# a key the probe never touched (factor 1.0) from one it projected without finding a date
# (the stated _A_TIME_UNKNOWN attenuation). Collapsing the two would misprice every undated hit.
CarrierCov = tuple[str, str | None, bool, str | None]


@dataclass
class Text:
    """One deduped chunk text in the top-k, with the carriers the dedup discarded."""
    chunk_text: str
    carriers: list[Any]                      # SearchResult, in declared order
    covariates: dict[str, CarrierCov] = field(default_factory=dict)

    @property
    def chosen(self) -> str:
        return str(self.carriers[0].artifact_cache_key)

    @property
    def n_carriers(self) -> int:
        return len(self.carriers)

    @property
    def tie_decided(self) -> bool:
        """True iff the survivor beat the runner-up on the content hash alone — the
        carriers' quantised scores are equal, so nothing substantive separated them."""
        return (self.n_carriers > 1
                and round(self.carriers[0].score, 9) == round(self.carriers[1].score, 9))

    def factors(self, key: str, *, time_indexed: bool, today: date
                ) -> tuple[float, float, float]:
        """What the posterior actually reads off a carrier: (authority, subject, time).
        NOT the provenance identity — two email copies at different paths share an
        authority class, so comparing paths would report divergence where the weight is
        bit-identical."""
        origin, subject_state, date_projected, doc_date = self.covariates[key]
        _, authority = LK.authority_for(origin)
        tf = (LK.time_factor(doc_date, time_indexed=time_indexed, today=today)
              if date_projected else 1.0)
        return (authority, LK.subject_factor(subject_state), tf)

    def divergent(self, *, time_indexed: bool, today: date) -> bool:
        """True iff the carriers disagree on the factor triple the posterior reads."""
        seen = {self.factors(str(c.artifact_cache_key),
                             time_indexed=time_indexed, today=today)
                for c in self.carriers}
        return len(seen) > 1


def texts_from_hits(hits: list[Any], k: int) -> list[Text]:
    """Mirror `retrieve_set`'s dedup exactly — same declared order, same first-wins keep —
    but KEEP the losers. Pure, so the mirror claim is testable against `retrieve_set`
    itself on one hit list rather than asserted in a comment."""
    by_text: dict[str, list[Any]] = {}
    for h in sorted(hits, key=declared_key):
        by_text.setdefault(h.chunk_text, []).append(h)
    return [Text(chunk_text=t, carriers=cs) for t, cs in list(by_text.items())[:k]]


def carrier_texts(conn: Any, question: str, k: int) -> tuple[list[Text], bool]:
    """The arm's cheap first pass, with the discarded carriers kept.
    Returns (top-k texts, over-fetch window saturated)."""
    import life_agent.core.retrieval as RET
    from pkm.retrieval import search
    hits = search(conn, RET.build_query(question, ""), k=k * 4)
    return texts_from_hits(hits, k), len(hits) >= k * 4


def hit_dicts(texts: list[Text], chooser: Any) -> list[dict[str, Any]]:
    """The retrieval-set dicts `observe_hits` consumes, carried by ``chooser(text)``."""
    out: list[dict[str, Any]] = []
    for t in texts:
        c = chooser(t)
        out.append({"artifact_cache_key": str(c.artifact_cache_key),
                    "chunk_text": t.chunk_text, "score": c.score,
                    "origin": c.source_path})
    return out


def carrier_covariate(t: Text, key: str, *, time_indexed: bool, today: date) -> float:
    """The §4.1 evidence covariate for one carrier — authority·subject·time, exactly the
    product `lookup._covariate` folds into the group channel. Built from `Text.factors` so
    the scalar the choosers rank by and the triple divergence is measured on cannot drift."""
    a, sf, tf = t.factors(key, time_indexed=time_indexed, today=today)
    return a * sf * tf


def max_covariate_chooser(time_indexed: bool, today: date) -> Any:
    """RULE 4, named before the measurement: argmax covariate, declared key within ties.
    ``max`` returns the FIRST maximal element and the carrier list is in declared order,
    so the tie-break is the declared key — the rule is total and order-free."""
    def choose(t: Text) -> Any:
        return max(t.carriers, key=lambda c: carrier_covariate(
            t, str(c.artifact_cache_key), time_indexed=time_indexed, today=today))
    return choose


def worst_covariate_chooser(time_indexed: bool, today: date) -> Any:
    """DIAGNOSTIC ONLY (rule 4): the adversarial carrier, to bound exposure. Never a
    candidate rule — a rule chosen to be worst is not a fix."""
    def choose(t: Text) -> Any:
        return min(t.carriers, key=lambda c: carrier_covariate(
            t, str(c.artifact_cache_key), time_indexed=time_indexed, today=today))
    return choose


def spread_chooser() -> Any:
    """DIAGNOSTIC ONLY: the assignment that makes the evidence look as INDEPENDENT as the
    carrier sets allow — prefer a document not already used. Added after the smoke test
    showed the covariate-adversarial permutation is a no-op wherever the carriers' factor
    triples tie, which is most of them: with equal covariates the arbitrariness that
    survives is not the WEIGHT but the GROUPING, and nothing above measured it. Never a
    candidate rule — a rule chosen to maximise apparent independence is the saturation
    §5 exists to prevent."""
    def choose(t: Text, used: set[str]) -> Any:
        for c in t.carriers:
            if str(c.artifact_cache_key) not in used:
                return c
        return t.carriers[0]
    return _stateful(choose)


def concentrate_chooser() -> Any:
    """DIAGNOSTIC ONLY: the mirror bound — prefer a document already used, so the evidence
    looks as CORRELATED as the carrier sets allow."""
    def choose(t: Text, used: set[str]) -> Any:
        for c in t.carriers:
            if str(c.artifact_cache_key) in used:
                return c
        return t.carriers[0]
    return _stateful(choose)


def _stateful(choose: Any) -> Any:
    """Thread the documents chosen so far through a chooser, in the texts' declared order,
    so both grouping bounds are deterministic functions of the carrier lists."""
    used: set[str] = set()

    def wrapped(t: Text) -> Any:
        c = choose(t, used)
        used.add(str(c.artifact_cache_key))
        return c
    return wrapped


def probe_texts(conn: Any, question: str, leader: str, k: int) -> tuple[list[Text], bool]:
    """Surface (b): `probes.probe_corroborate`'s own window, with the discarded carriers kept.
    Same query the probe builds (the leader value appended), same over-fetch, same declared
    rank, same first-wins dedup — `texts_from_hits` is that dedup, so the mirror is shared
    with surface (a) rather than written twice."""
    from pkm.retrieval import search
    hits = search(conn, f"{question} {leader}", k=k * 4)
    return texts_from_hits(hits, k), len(hits) >= k * 4


def straddles_held(t: Text, held: set[str]) -> bool:
    """The sharp case, and the reason surface (b) is in scope at all: some carriers of this
    text are documents already in hand and some are not, so `_fresh_hits` keeps the hit under
    one choice and drops it under another. The carrier choice decides whether this
    corroboration EXISTS — not how much it weighs."""
    keys = {str(c.artifact_cache_key) for c in t.carriers}
    return bool(keys & held) and bool(keys - held)


def straddle_side(t: Text, held: set[str]) -> str:
    """Which way a straddle falls TODAY, which is what decides how to read the count. The
    declared key is the same function on both surfaces and the carrier scores tie, so the
    probe re-picks the carrier the base pass already picked — meaning the straddle is
    normally resolved by DROPPING the hit, and an alternative carrier would ADD a second copy
    of text already in hand. "dropped" is the conservative side; "kept" is the one that can
    smuggle a duplicate past `_fresh_hits` as independent corroboration."""
    if not straddles_held(t, held):
        return "none"
    return "dropped" if t.chosen in held else "kept"


def fresh_hits(hits: list[dict[str, Any]], held: set[str]) -> list[dict[str, Any]]:
    """`probes._fresh_hits`, mirrored: corroboration counts only INDEPENDENT new documents."""
    return [h for h in hits if str(h["artifact_cache_key"]) not in held]


def assignment(hits: list[dict[str, Any]]) -> list[str]:
    """The text -> document assignment `lookup_posterior` groups by. A LIST, positionally:
    two assignments can share a key SET and still group the observations differently, so a
    set comparison silently under-reports the change."""
    return [str(h["artifact_cache_key"]) for h in hits]


def grouping(assign: list[str]) -> frozenset[frozenset[int]]:
    """The PARTITION the assignment induces — which texts share a document, which is what
    `lookup_posterior` conditions on (one `group_noisy_channel` per document). Relabelling a
    group is not a different partition; splitting or merging one is."""
    by_doc: dict[str, set[int]] = {}
    for i, key in enumerate(assign):
        by_doc.setdefault(key, set()).add(i)
    return frozenset(frozenset(v) for v in by_doc.values())


def partition_arbitrary(spread: list[dict[str, Any]],
                        concentrated: list[dict[str, Any]]) -> bool:
    """CRITERION 3's partition clause, read as it was frozen: do *the carriers* disagree on
    the document partition — not does one chosen rule move it. Rule-independent, like the
    clause's two siblings (covariate divergence and `_fresh_hits` survival). Bounded by the
    two grouping extremes, so it under-detects rather than over-detects: if max-independence
    and max-correlation induce the same partition, the grouping is effectively forced."""
    return grouping(assignment(spread)) != grouping(assignment(concentrated))


def partition_changed(now_hits: list[dict[str, Any]],
                      alt_hits: list[dict[str, Any]]) -> bool:
    return assignment(now_hits) != assignment(alt_hits)


@dataclass
class Arm:
    action: str
    leader: str
    n_obs: int
    n_docs: int
    p_none: float
    eu: float
    credences: list[float] = field(default_factory=list)


def decide_arm(root: Path, question: str, hits: list[dict[str, Any]],
               cov: LK.HitCovariates, *, time_indexed: bool, today: date,
               client: Any, brain: Any) -> Arm | None:
    """`decide_and_record`'s body with the two WRITES removed — the §18.9 answer record and
    the §8 decision line. Same shaper, same posterior, same EU decision under the same Ū: an
    audit must not mint answers or decisions, and reimplementing the model to avoid that
    would measure a different one. None ⇒ no grounded observation (the narrative path)."""
    observations, _indet = LK.observe_hits(root, question, hits, client=client,
                                           covariates=cov, time_indexed=time_indexed,
                                           today=today)
    if not observations:
        return None
    u_bar, _, _ = LK.current_u_bar(brain)
    rho = LK.extractor_reliability(brain)
    candidates = LK.candidates_from(observations)
    weights, state_id = LK.lookup_posterior(brain, observations, candidates, rho)
    try:
        scoped_opts = LK._scoped_options(
            brain, observations, candidates, rho, u_bar=u_bar, state_current=state_id,
            weights_current=weights, time_indexed=time_indexed)
        action, eu, scoped_j, _interval = LK.decide(
            brain, state_id, weights, u_bar,
            scoped={j: t[0] for j, t in scoped_opts.items()})
    finally:
        brain.destroy_state(state_id)
    order = sorted(range(len(candidates)), key=lambda i: -weights[i])
    scoped_value = candidates[scoped_j] if scoped_j is not None else None
    leader = (scoped_value or "") if action == "report_scoped" else (
        candidates[order[0]] if candidates else "")
    return Arm(action=action, leader=str(leader), n_obs=len(observations),
               n_docs=len({o.artifact_cache_key for o in observations}),
               p_none=float(weights[-1]), eu=float(eu),
               credences=[float(weights[i]) for i in order])


@dataclass
class Row:
    qid: str
    gold: str
    n_texts: int = 0
    n_multi: int = 0
    n_tie_decided: int = 0
    n_divergent: int = 0
    saturated: bool = False
    partition_changed: bool = False       # the NAMED RULE moves it (criterion 5's rule)
    partition_arbitrary: bool = False     # the CARRIERS admit a different one (criterion 3)
    now: Arm | None = None
    alt: Arm | None = None
    worst: Arm | None = None
    spread: Arm | None = None
    concentrated: Arm | None = None
    recorded_action: str = ""
    diverged_from_run: bool = False
    unclear_carriers: int = 0
    n_docs_now: int = 0
    n_docs_spread: int = 0
    n_docs_concentrated: int = 0
    # surface (b) — the corroborate probe
    probe_leader: str = ""
    n_probe_texts: int = 0
    n_probe_multi: int = 0
    n_probe_straddle: int = 0
    n_straddle_dropped: int = 0   # today drops it; another carrier would ADD a duplicate
    n_straddle_kept: int = 0      # today keeps it; another carrier would drop it
    n_probe_divergent: int = 0
    n_fresh_now: int = 0
    n_fresh_alt: int = 0
    fresh_set_changed: bool = False
    probe_saturated: bool = False
    probe_now: Arm | None = None
    probe_alt: Arm | None = None

    @property
    def load_bearing_base(self) -> bool:
        return self.n_divergent > 0 or self.partition_arbitrary

    @property
    def load_bearing_probe(self) -> bool:
        return self.n_probe_straddle > 0 or self.n_probe_divergent > 0

    @property
    def load_bearing(self) -> bool:
        return self.load_bearing_base or self.load_bearing_probe


def correct(arm: Arm | None, gold: str, variants: list[str]) -> bool:
    return (arm is not None and arm.action in _COMMITS
            and MATCH.answer_matches(gold, variants, arm.leader))


def committed(arm: Arm | None) -> bool:
    return arm is not None and arm.action in _COMMITS


def classify(row: Row, gold: str, variants: list[str]) -> str:
    """RULE 5's split, on the two recomputed arms."""
    now, alt = row.now, row.alt
    if (now is None and alt is None) or (
            committed(now) == committed(alt)
            and correct(now, gold, variants) == correct(alt, gold, variants)
            and (now.leader if now else "") == (alt.leader if alt else "")):
        return "unchanged"
    if committed(now) and not correct(now, gold, variants) and not (
            committed(alt) and not correct(alt, gold, variants)):
        return "repair"
    if correct(now, gold, variants) and not correct(alt, gold, variants):
        return "regression"
    if not committed(now) and committed(alt):
        return "reach-gain"
    if committed(now) and not committed(alt):
        return "reach-loss"
    return "changed-other"


def _run_date(run_id: str) -> date:
    """The audited run's own date, so both arms decay time exactly as it did. Reading
    today's clock instead would put a day of decay between the audit and the run it
    describes — small, and exactly the kind of small that moves a knife-edge row."""
    stamp = run_id.split("-", 1)[1].split("T", 1)[0]
    return date(int(stamp[0:4]), int(stamp[4:6]), int(stamp[6:8]))


def audit_rows(paired: dict[str, dict], questions: list[dict], conn: Any, root: Path, *,
               k: int, today: date, client: Any, brain: Any,
               profile: str) -> tuple[list[Row], list[str]]:
    by_id = {str(q["id"]): q for q in questions}
    rows: list[Row] = []
    excluded: list[str] = []
    for qid, p in sorted(paired.items()):
        q = by_id.get(qid)
        if q is None:
            excluded.append(f"{qid} (not in the questions file)")
            continue
        gold = str(q.get("answer") or "")
        if not gold:
            excluded.append(f"{qid} (unanswerable by construction — no gold)")
            continue
        question = str(q["question"])
        try:
            route = LK.route_question(root, question, client=client)
        except WouldSpendError:
            excluded.append(f"{qid} (route derivation cold — no-spend mode)")
            continue
        if route is None:
            excluded.append(f"{qid} (not routed as a lookup — the narrative family answers)")
            continue
        texts, saturated = carrier_texts(conn, question, k)
        if not texts:
            excluded.append(f"{qid} (no hits at k={k})")
            continue
        keys = list(dict.fromkeys(str(c.artifact_cache_key)
                                  for t in texts for c in t.carriers))
        doc_date = PR.probe_recency(conn, root, keys)
        try:
            subject_state = (PR.probe_subject(conn, root, keys, profile=profile,
                                              client=client) if profile else {})
        except WouldSpendError:
            excluded.append(f"{qid} (an owner verdict is cold — no-spend mode)")
            continue
        origin_of = {str(c.artifact_cache_key): str(c.source_path)
                     for t in texts for c in t.carriers}
        for t in texts:
            t.covariates = {ck: (origin_of[ck], subject_state.get(ck),
                                 ck in doc_date, doc_date.get(ck))
                            for ck in (str(c.artifact_cache_key) for c in t.carriers)}
        ti = route.time_indexed
        cov = LK.HitCovariates(subject_state=subject_state, doc_date=doc_date)
        row = Row(qid=qid, gold=gold,
                  n_texts=len(texts),
                  n_multi=sum(1 for t in texts if t.n_carriers > 1),
                  n_tie_decided=sum(1 for t in texts if t.tie_decided),
                  n_divergent=sum(1 for t in texts
                                  if t.divergent(time_indexed=ti, today=today)),
                  saturated=saturated,
                  recorded_action=str((p.get("typed") or {}).get("action") or ""),
                  unclear_carriers=sum(1 for ck in keys
                                       if subject_state.get(ck) == "unclear"))
        now_hits = hit_dicts(texts, lambda t: t.carriers[0])
        alt_hits = hit_dicts(texts, max_covariate_chooser(ti, today))
        worst_hits = hit_dicts(texts, worst_covariate_chooser(ti, today))
        spread_hits = hit_dicts(texts, spread_chooser())
        conc_hits = hit_dicts(texts, concentrate_chooser())
        row.partition_changed = partition_changed(now_hits, alt_hits)
        row.partition_arbitrary = partition_arbitrary(spread_hits, conc_hits)
        row.n_docs_now = len(set(assignment(now_hits)))
        row.n_docs_spread = len(set(assignment(spread_hits)))
        row.n_docs_concentrated = len(set(assignment(conc_hits)))
        try:
            row.now = decide_arm(root, question, now_hits, cov, time_indexed=ti,
                                 today=today, client=client, brain=brain)
            row.alt = decide_arm(root, question, alt_hits, cov, time_indexed=ti,
                                 today=today, client=client, brain=brain)
            row.worst = decide_arm(root, question, worst_hits, cov, time_indexed=ti,
                                   today=today, client=client, brain=brain)
            row.spread = decide_arm(root, question, spread_hits, cov, time_indexed=ti,
                                    today=today, client=client, brain=brain)
            row.concentrated = decide_arm(root, question, conc_hits, cov, time_indexed=ti,
                                          today=today, client=client, brain=brain)
        except WouldSpendError:
            excluded.append(f"{qid} (an extraction is cold — no-spend mode)")
            continue

        # --- surface (b): the corroborate probe, on each arm's OWN leader and held set,
        # because that is what the executor would have fired.
        if row.now is not None and row.now.leader:
            try:
                row.probe_leader = row.now.leader
                ptexts, row.probe_saturated = probe_texts(conn, question,
                                                          row.now.leader, k)
                pkeys = list(dict.fromkeys(str(c.artifact_cache_key)
                                           for t in ptexts for c in t.carriers))
                pdate = PR.probe_recency(conn, root, pkeys)
                psubj = (PR.probe_subject(conn, root, pkeys, profile=profile,
                                          client=client) if profile else {})
                porigin = {str(c.artifact_cache_key): str(c.source_path)
                           for t in ptexts for c in t.carriers}
                for t in ptexts:
                    t.covariates = {ck: (porigin[ck], psubj.get(ck),
                                         ck in pdate, pdate.get(ck))
                                    for ck in (str(c.artifact_cache_key)
                                               for c in t.carriers)}
                held_now = set(assignment(now_hits))
                held_alt = set(assignment(alt_hits))
                row.n_probe_texts = len(ptexts)
                row.n_probe_multi = sum(1 for t in ptexts if t.n_carriers > 1)
                sides = [straddle_side(t, held_now) for t in ptexts]
                row.n_probe_straddle = sum(1 for x in sides if x != "none")
                row.n_straddle_dropped = sum(1 for x in sides if x == "dropped")
                row.n_straddle_kept = sum(1 for x in sides if x == "kept")
                row.n_probe_divergent = sum(
                    1 for t in ptexts if t.divergent(time_indexed=ti, today=today))
                pnow = fresh_hits(hit_dicts(ptexts, lambda t: t.carriers[0]), held_now)
                palt = fresh_hits(hit_dicts(ptexts, max_covariate_chooser(ti, today)),
                                  held_alt)
                row.n_fresh_now, row.n_fresh_alt = len(pnow), len(palt)
                row.fresh_set_changed = ({h["chunk_text"] for h in pnow}
                                         != {h["chunk_text"] for h in palt})
                pcov = LK.HitCovariates(
                    subject_state={**subject_state, **psubj},
                    doc_date={**doc_date, **pdate})
                row.probe_now = decide_arm(root, question, now_hits + pnow, pcov,
                                           time_indexed=ti, today=today,
                                           client=client, brain=brain)
                row.probe_alt = decide_arm(root, question, alt_hits + palt, pcov,
                                           time_indexed=ti, today=today,
                                           client=client, brain=brain)
            except WouldSpendError:
                excluded.append(f"{qid} (probe surface: a derivation is cold — "
                                "no-spend mode; surface (a) still counted)")
        rows.append(row)
    return rows, excluded


def verdict(load_bearing: list[str], repairs: list[str], regressions: list[str],
            reach: list[str]) -> tuple[str, str]:
    """CRITERION 7, applied mechanically to the numbers above it — once per surface, since
    each surface's criteria were frozen before its own reading."""
    if len(regressions) > len(repairs):
        build = ("REFUSE — regressions exceed repairs: the invariant rule would not be "
                 "better, only different")
    elif len(load_bearing) >= 5:
        build = "BUILD the invariance fix"
    else:
        build = (f"NO-GO — load-bearing exposure {len(load_bearing)} < 5; this entry "
                 "converts to a standing known-and-uncovered source")
    delivered = len(set(repairs) | set(regressions) | set(reach))
    price = ("PRICE a gate run" if delivered >= 1 else
             "no run bought — behaviour-preserving on this battery at the lookup layer")
    return build, price


def render(rows: list[Row], excluded: list[str], run_id: str, k: int,
           today: date, *, only: str | None = None) -> str:
    classes: Counter[str] = Counter()
    repairs: list[str] = []
    regressions: list[str] = []
    reach: list[str] = []
    per_row: dict[str, str] = {}
    for r in rows:
        q_variants: list[str] = r_variants.get(r.qid, [])
        c = classify(r, r.gold, q_variants)
        per_row[r.qid] = c
        classes[c] += 1
        if c == "repair":
            repairs.append(r.qid)
        elif c == "regression":
            regressions.append(r.qid)
        elif c in ("reach-gain", "reach-loss", "changed-other"):
            reach.append(r.qid)
    load_bearing = [r.qid for r in rows if r.load_bearing]

    def _moved(a: Arm | None, b: Arm | None) -> bool:
        return a is not None and b is not None and (a.action, a.leader) != (b.action, b.leader)
    worst_changed = [r.qid for r in rows if _moved(r.worst, r.now)]
    group_changed = [r.qid for r in rows
                     if _moved(r.spread, r.now) or _moved(r.concentrated, r.now)]
    group_arbitrary = [r.qid for r in rows if r.n_docs_spread != r.n_docs_concentrated]
    build, price = verdict([r.qid for r in rows if r.load_bearing_base],
                           repairs, regressions, reach)
    # --- surface (b), scored against the same criteria, frozen before its own reading
    p_lb = [r.qid for r in rows if r.load_bearing_probe]
    p_repairs: list[str] = []
    p_regressions: list[str] = []
    p_reach: list[str] = []
    p_class: dict[str, str] = {}
    for r in rows:
        if r.probe_now is None and r.probe_alt is None:
            continue
        c = classify(Row(qid=r.qid, gold=r.gold, now=r.probe_now, alt=r.probe_alt),
                     r.gold, r_variants.get(r.qid, []))
        p_class[r.qid] = c
        if c == "repair":
            p_repairs.append(r.qid)
        elif c == "regression":
            p_regressions.append(r.qid)
        elif c in ("reach-gain", "reach-loss", "changed-other"):
            p_reach.append(r.qid)
    p_build, p_price = verdict(p_lb, p_repairs, p_regressions, p_reach)
    fresh_moved = [r.qid for r in rows if r.fresh_set_changed]
    o: list[str] = []
    o.append(f"# Carrier audit — {run_id} (k={k}, decay as of {today.isoformat()})\n")
    o.append("Zero spend: every extraction, route and owner verdict is served from the "
             "§18.9 cache or its question is excluded by name.\n")
    if only:
        o.append(f"**RESTRICTED RUN — `--only {only}`. Not a reading of the battery.**\n")
    o.append("## Exposure (criterion 2 — reported, never a bar on its own)\n")
    o.append(f"- questions audited: **{len(rows)}**")
    o.append(f"- deduped texts in the top-k: **{sum(r.n_texts for r in rows)}**")
    o.append(f"- multi-carried texts: **{sum(r.n_multi for r in rows)}** "
             f"in **{sum(1 for r in rows if r.n_multi)}** questions")
    o.append(f"- of those, decided by the content hash alone (quantised scores equal): "
             f"**{sum(r.n_tie_decided for r in rows)}**")
    o.append(f"- questions whose over-fetch window saturated (carrier lists may be "
             f"truncated — criterion 1): **{sum(1 for r in rows if r.saturated)}**\n")
    o.append("## Load-bearing exposure (criterion 3)\n")
    o.append(f"- texts whose carriers DISAGREE on the covariate triple: "
             f"**{sum(r.n_divergent for r in rows)}**")
    o.append(f"- **questions whose carriers admit a different document partition** "
             f"(criterion 3, rule-independent): "
             f"**{sum(1 for r in rows if r.partition_arbitrary)}**")
    o.append(f"- …of which the NAMED rule of criterion 4 actually moves: "
             f"**{sum(1 for r in rows if r.partition_changed)}**")
    o.append(f"- **load-bearing questions: {len(load_bearing)}** "
             f"({', '.join(load_bearing) if load_bearing else 'none'})")
    o.append(f"- carriers whose subject verdict was uncached and degraded to `unclear` "
             f"(criterion 6): **{sum(r.unclear_carriers for r in rows)}**\n")
    o.append("## Delivered reach at the lookup layer (criteria 4-5)\n")
    o.append("| class | n | questions |")
    o.append("|---|---|---|")
    for c in ("repair", "regression", "reach-gain", "reach-loss", "changed-other",
              "unchanged"):
        qs = sorted(q for q, k2 in per_row.items() if k2 == c)
        o.append(f"| {c} | {classes[c]} | {', '.join(qs) if qs else '—'} |")
    o.append("")
    o.append("### Diagnostic bounds (never candidate rules — criterion 4)\n")
    o.append(f"- the adversarial worst-covariate carrier changes the decision on "
             f"**{len(worst_changed)}** questions"
             + (f" ({', '.join(worst_changed)})" if worst_changed else "") + "")
    o.append(f"- the GROUPING is arbitrary — the carrier sets admit a different document "
             f"count — on **{len(group_arbitrary)}** questions"
             + (f" ({', '.join(group_arbitrary)})" if group_arbitrary else ""))
    o.append(f"- pushed to either extreme (max-independence / max-correlation) the decision "
             f"changes on **{len(group_changed)}** questions"
             + (f" ({', '.join(group_changed)})" if group_changed else "") + "\n")
    o.append("## Surface (b) — the corroborate probe (criterion 1b)\n")
    o.append(f"- questions that fire a probe (a leader exists): "
             f"**{sum(1 for r in rows if r.probe_leader)}**")
    o.append(f"- multi-carried texts in the probe window: "
             f"**{sum(r.n_probe_multi for r in rows)}** of "
             f"**{sum(r.n_probe_texts for r in rows)}**")
    n_straddle = sum(r.n_probe_straddle for r in rows)
    o.append(f"- **texts whose carriers STRADDLE the held set** — the carrier choice decides "
             f"whether the corroboration exists at all: **{n_straddle}** in "
             f"**{sum(1 for r in rows if r.n_probe_straddle)}** questions")
    o.append(f"  - of those, resolved TODAY by dropping the hit (the conservative side — "
             f"an alternative carrier would add a second copy of text already in hand): "
             f"**{sum(r.n_straddle_dropped for r in rows)}**; resolved by KEEPING it "
             f"(an alternative would drop it): **{sum(r.n_straddle_kept for r in rows)}**")
    o.append(f"- texts whose carriers diverge on the covariate triple: "
             f"**{sum(r.n_probe_divergent for r in rows)}**")
    o.append(f"- fresh corroboration found — now vs the named rule: "
             f"**{sum(r.n_fresh_now for r in rows)}** vs "
             f"**{sum(r.n_fresh_alt for r in rows)}** hits; the fresh SET differs on "
             f"**{len(fresh_moved)}** questions"
             + (f" ({', '.join(fresh_moved)})" if fresh_moved else ""))
    o.append(f"- **load-bearing questions on this surface: {len(p_lb)}** "
             f"({', '.join(p_lb) if p_lb else 'none'})")
    o.append("")
    o.append("Decision proxy — the base set UNION the probe's fresh hits, decided through the "
             "same tail. Named a proxy because the executor folds corroboration through an "
             "edge event, not by re-deciding on the union:\n")
    o.append("| class | n | questions |")
    o.append("|---|---|---|")
    for c in ("repair", "regression", "reach-gain", "reach-loss", "changed-other",
              "unchanged"):
        qs = sorted(q for q, k2 in p_class.items() if k2 == c)
        o.append(f"| {c} | {len(qs)} | {', '.join(qs) if qs else '—'} |")
    o.append("")
    o.append("## Verdict (criterion 7, applied mechanically, once per surface)\n")
    o.append("**Surface (a) — the cheap first pass**\n")
    o.append(f"- **{build}**")
    o.append(f"- **{price}**\n")
    o.append("**Surface (b) — the corroborate probe**\n")
    o.append(f"- **{p_build}**")
    o.append(f"- **{p_price}**\n")
    o.append("## Rows\n")
    o.append("| qid | texts | multi | tie | diverg | partition | docs n/s/c | now | alt "
             "| worst | spread | conc | class | probe multi/straddle | fresh n/a "
             "| probe class | run |")
    o.append("|---|" + "---|" * 16)
    for r in sorted(rows, key=lambda r: (not r.load_bearing, r.qid)):
        def _a(a: Arm | None) -> str:
            return "—" if a is None else f"{a.action}/{a.n_obs}o/{a.n_docs}d"
        o.append(f"| {r.qid} | {r.n_texts} | {r.n_multi} | {r.n_tie_decided} "
                 f"| {r.n_divergent} | {'yes' if r.partition_changed else ''} "
                 f"| {r.n_docs_now}/{r.n_docs_spread}/{r.n_docs_concentrated} "
                 f"| {_a(r.now)} | {_a(r.alt)} | {_a(r.worst)} | {_a(r.spread)} "
                 f"| {_a(r.concentrated)} | {per_row[r.qid]} "
                 f"| {r.n_probe_multi}/{r.n_probe_straddle} "
                 f"| {r.n_fresh_now}/{r.n_fresh_alt} "
                 f"| {p_class.get(r.qid, '—')} | {r.recorded_action} |")
    o.append("")
    o.append("## Excluded, by name (criterion 8)\n")
    o.extend(f"- {e}" for e in (excluded or ["none"]))
    o.append("")
    return "\n".join(o) + "\n"


# variants are needed by render's correctness test but do not belong on Row (which is
# serialised into the YAML): a module-level map keyed by qid, filled by main.
r_variants: dict[str, list[str]] = {}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--paired", required=True, type=Path)
    ap.add_argument("--questions", type=Path, default=None)
    ap.add_argument("--k", type=int, default=20)
    ap.add_argument("--only", default=None,
                    help="comma-separated qids (debug; the report names the restriction)")
    ap.add_argument("--today", default=None,
                    help="decay date (default: the audited run's own date)")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--out-yaml", type=Path, default=None)
    args = ap.parse_args(argv)

    questions = load_questions(args.questions) if args.questions else load_questions()
    paired = load_paired(args.paired)
    if args.only:
        want = {s.strip() for s in args.only.split(",") if s.strip()}
        paired = {q: v for q, v in paired.items() if q in want}
    root = LCFG.pkm_root()
    if root is None:
        print("REFUSED: no pkm root (PKM_CONFIG unresolvable)")
        return 2
    for q in questions:
        r_variants[str(q["id"])] = [str(v) for v in (q.get("answer_variants") or [])]
    today = (date.fromisoformat(args.today) if args.today
             else _run_date(args.run_id))

    import anthropic
    import duckdb
    client = RefusingClient(engine_version=str(anthropic.__version__))
    conn = duckdb.connect(str(root / "catalogue.duckdb"), read_only=True)
    brain = LK.shared_brain()
    try:
        rows, excluded = audit_rows(paired, questions, conn, root, k=args.k,
                                    today=today, client=client, brain=brain,
                                    profile=owner.load_profile())
    finally:
        conn.close()
    report = render(rows, excluded, args.run_id, args.k, today, only=args.only)
    print(report)
    if args.out:
        args.out.write_text(report, encoding="utf-8")
    if args.out_yaml:
        import yaml
        args.out_yaml.write_text(yaml.safe_dump(
            {"run_id": args.run_id, "k": args.k, "today": today.isoformat(),
             "excluded": excluded,
             "rows": [{**{f: v for f, v in r.__dict__.items()
                          if f not in ("now", "alt", "worst", "spread",
                                       "concentrated", "probe_now", "probe_alt")},
                       "probe_now": r.probe_now.__dict__ if r.probe_now else None,
                       "probe_alt": r.probe_alt.__dict__ if r.probe_alt else None,
                       "now": r.now.__dict__ if r.now else None,
                       "alt": r.alt.__dict__ if r.alt else None,
                       "worst": r.worst.__dict__ if r.worst else None,
                       "spread": r.spread.__dict__ if r.spread else None,
                       "concentrated": (r.concentrated.__dict__
                                        if r.concentrated else None)}
                      for r in rows]},
            sort_keys=True, allow_unicode=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
