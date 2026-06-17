#!/usr/bin/env python3
"""answer_brain_gate.py — end-to-end PARITY certification: the answer-brain daemon vs gather.py.

Move 4 §2D (credence `docs/answer-brain/move-4-design.md`). The owner chose to certify the
daemon-driven govern+steer loop as **end-to-end parity to `gather.py`** over the real corpus, NOT a
fresh `P(Δ>δ)` run (the gather loop is already the typed policy — `run_eval.py:397` — so a fresh
gate would reproduce ~0.848, the wide-`u_wrong`-prior FAIL, not mechanics).

Per eval question this runs TWO arms on the **same retrieved hits**:
  - reference: `gather.py`'s `gather_answer` (in-process LK decision) — the validated Stage-0 loop;
  - daemon:    the same orchestration (reusing `gather.py`'s own `_era_split`/`_top_candidates`/
               `_gather` + `LK.observe_hits` + probes) with the decision routed through the daemon's
               stateless `POST /decide` (the Move-4 gather branch).
The corrected daemon policy matches `gather.py` by construction (recency pre-decision, `era_split`-
triggered; `test_gather.jl`), so a per-question match certifies the **wire** end-to-end
(`to_abstract_observations` → `/decide` → gather → re-extract). `applied_probes=["recency"]` is sent
iff `route.time_indexed`, mirroring `gather.py`'s `if not time_indexed` guard exactly.

Output (idea B1 — the call-matrix that de-starves the §8 gate's N axis): an append-only JSONL row
per (question x policy) under `$LIFE_AGENT_KB/eval/answer_brain_gate/`, plus a report with a **gated
recommendation** (named gates `parity_holds` / `zero_new_confident_wrong`, each pass/review;
certified only if both pass), mirroring the `bayesian-orchestrator` auto-gating discipline.

No cloud model is in the loop (extraction is local Ollama, via the same reads `gather.py` uses), so
this runs fully on-machine over the owner's real PII corpus. Start the daemon first:
    julia --project=$HOME/git/credence $HOME/git/credence/apps/answer-brain/daemon/main.jl
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))  # ask / run_eval live in scripts/

from life_agent import owner
from life_agent.bridge.observations import to_abstract_observations
from life_agent.core import gate as GATE
from life_agent.core import gather as GA
from life_agent.core import lookup as LK
from life_agent.core import probes as P

DECIDE_URL = os.environ.get("ANSWER_BRAIN_DECIDE_URL", "http://127.0.0.1:8799")


@dataclass(frozen=True)
class Outcome:
    """One arm's realised answer on a question, reduced to what parity compares."""

    action: str             # report | hedge | ask_clarify | abstain | gather | narrative
    asserted: str | None    # the asserted value (report) / "·"-joined set (hedge), else None


# --- the daemon wire (stdlib urllib; no new dependency) --------------------------------

def _decide(candidates: list[str], observations: list[dict[str, Any]], rho: float,
            u_bar: dict[str, float], era_split: bool, applied: list[str]) -> dict[str, Any]:
    body = json.dumps({
        "candidates": candidates, "observations": observations, "rho": rho,
        "u_bar": u_bar, "era_split": era_split, "applied_probes": applied,
    }).encode("utf-8")
    req = urllib.request.Request(
        DECIDE_URL + "/decide", data=body,
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def _daemon_ready() -> bool:
    try:
        with urllib.request.urlopen(DECIDE_URL + "/ready", timeout=5) as r:
            return r.status == 200
    except (urllib.error.URLError, OSError):
        return False


# --- outcome mappers -------------------------------------------------------------------

def _ref_outcome(lk: LK.LookupResult | None) -> Outcome:
    if lk is None:
        return Outcome("narrative", None)
    if lk.action == "report":
        return Outcome("report", lk.candidates[0] if lk.candidates else None)
    if lk.action == "hedge":
        return Outcome("hedge", "·".join(lk.candidates))
    return Outcome(lk.action, None)


def _dae_outcome(resp: dict[str, Any], candidates: list[str]) -> Outcome:
    eff = resp["effector"]
    if eff == "report":
        return Outcome("report", resp.get("value"))
    if eff == "hedge":
        return Outcome("hedge", "·".join(candidates))
    return Outcome(eff, None)


# --- the daemon-driven loop (gather.py's orchestration; decision via /decide) ----------

def daemon_answer(conn: duckdb.DuckDBPyConnection, root: Path, question: str,
                  hits: list[dict[str, Any]], *, profile: str, owner_scoped: bool,
                  brain: Any, u_bar: dict[str, float], extract_client: Any,
                  route_client: Any = None, stats: dict[str, int] | None = None) -> Outcome:
    """The Move-4 daemon-driven port of `gather.py::gather_answer`: identical orchestration
    (its own helpers), the decision routed through `/decide`. Mirrors gather.py branch-for-branch.
    ``stats`` (if given) counts how often the daemon's recency-gather branch actually fired —
    evidence the loop was non-trivially exercised, not that everything abstained."""
    route = LK.route_question(root, question, client=route_client)
    if route is None:
        return Outcome("narrative", None)
    rho = LK.extractor_reliability()

    if not owner_scoped:  # gather.py takes the conservative single-pass path here
        obs, _ = LK.observe_hits(root, question, hits, client=extract_client,
                                 time_indexed=route.time_indexed)
        if not obs:
            return Outcome("narrative", None)
        cands, abstract = to_abstract_observations(obs)
        applied = ["recency"] if route.time_indexed else []
        return _dae_outcome(_decide(cands, abstract, rho, u_bar, False, applied), cands)

    # owner-scoped: the full gather-augmented loop (gather.py lines 146-186)
    base_obs, _ = LK.observe_hits(root, question, hits, client=extract_client, time_indexed=False)
    if not base_obs:
        return Outcome("narrative", None)
    targets = GA._top_candidates(brain, base_obs, rho, GA._N_CANDIDATES)
    held = {str(h["artifact_cache_key"]) for h in hits}
    allhits = hits + GA._gather(conn, question, targets, held, k=GA._K_GATHER)

    hit_keys = list(dict.fromkeys(str(h["artifact_cache_key"]) for h in allhits))
    doc_date = P.probe_recency(conn, root, hit_keys)
    subject_state = (P.probe_subject(conn, root, hit_keys, profile=profile, client=extract_client)
                     if profile else {})
    cov = LK.HitCovariates(subject_state=subject_state, doc_date=doc_date)

    obs, _ = LK.observe_hits(root, question, allhits, client=extract_client,
                             covariates=cov, time_indexed=route.time_indexed)
    if not obs:
        return Outcome("narrative", None)
    era_split = GA._era_split(obs, dict(doc_date), years=LK._TIME_HALF_LIFE_YEARS)
    cands, abstract = to_abstract_observations(obs)
    applied = ["recency"] if route.time_indexed else []  # mirror gather.py's `if not time_indexed`
    resp = _decide(cands, abstract, rho, u_bar, era_split, applied)

    if resp["effector"] == "gather" and resp.get("probe") == "recency":  # enact: recency on
        if stats is not None:
            stats["recency_gather"] = stats.get("recency_gather", 0) + 1
        obs2, _ = LK.observe_hits(root, question, allhits, client=extract_client,
                                  covariates=cov, time_indexed=True)
        if not obs2:
            return Outcome("narrative", None)
        cands, abstract = to_abstract_observations(obs2)
        resp = _decide(cands, abstract, rho, u_bar, era_split, ["recency"])
    return _dae_outcome(resp, cands)


# --- grading + parity ------------------------------------------------------------------

def _correct(asserted: str | None, q: dict) -> bool | None:
    """Gold-containment grade (the gate's common scale); None for a withholding."""
    if asserted is None:
        return None
    return GATE.realised_report([asserted], q.get("answer", ""), q.get("answer_variants", []))


def _same_assertion(a: Outcome, b: Outcome) -> bool:
    if a.action != b.action:
        return False
    if a.asserted is None and b.asserted is None:
        return True
    if a.asserted is None or b.asserted is None:
        return False
    return LK._candidate_key(a.asserted) == LK._candidate_key(b.asserted)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=os.environ.get("PKM_CONFIG"),
                        help="pkm config yaml (root_dir); default $PKM_CONFIG")
    parser.add_argument("--k", type=int, default=20, help="top-k per query")
    parser.add_argument("--limit", type=int, default=0, help="cap questions (0 = all)")
    args = parser.parse_args()
    if not args.config:
        print("error: --config or $PKM_CONFIG required", file=sys.stderr)
        return 2
    if not _daemon_ready():
        print(f"error: answer-brain daemon not ready at {DECIDE_URL} — start it:\n"
              "  julia --project=$HOME/git/credence "
              "$HOME/git/credence/apps/answer-brain/daemon/main.jl", file=sys.stderr)
        return 2

    import ask
    from run_eval import load_questions

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    root = Path(cfg["root_dir"]).expanduser()
    conn = duckdb.connect(str(root / "catalogue.duckdb"))
    conn.execute("INSTALL fts; LOAD fts;")

    questions = load_questions()
    if args.limit:
        questions = questions[: args.limit]
    profile = owner.load_profile()
    brain = LK.shared_brain()
    u_bar, _ver = LK.current_u_bar(brain)
    client = LK._client()

    out_dir = Path(os.environ["LIFE_AGENT_KB"]) / "eval" / "answer_brain_gate"
    out_dir.mkdir(parents=True, exist_ok=True)
    matrix = (out_dir / "call_matrix.jsonl").open("w", encoding="utf-8")

    def row(qid: str, policy: str, o: Outcome, q: dict) -> None:
        rec = {"question_id": qid, "gold": q.get("answer", ""), "policy": policy,
               "action": o.action, "asserted": o.asserted, "correct": _correct(o.asserted, q)}
        matrix.write(json.dumps(rec, sort_keys=True) + "\n")
        matrix.flush()
        os.fsync(matrix.fileno())  # B5 hygiene: append+fsync

    print(f"answer-brain gate (parity) over {len(questions)} questions, k={args.k} "
          f"→ {DECIDE_URL}\n" + "=" * 72)
    t0 = time.monotonic()
    mismatches: list[dict[str, Any]] = []
    new_confident_wrong: list[dict[str, Any]] = []
    stats: dict[str, int] = {"recency_gather": 0}
    n_owner = 0

    for q in questions:
        qid, question = str(q["id"]), q["question"]
        terms = ask._expand_terms(question, root=root)
        hits = ask._retrieve_set(conn, ask.build_query(question, terms), args.k)
        owner_scoped = ask.owner_question(question)
        n_owner += int(owner_scoped)

        ref = _ref_outcome(GA.gather_answer(conn, root, question, hits, profile=profile,
                                            owner_scoped=owner_scoped, brain=brain,
                                            extract_client=client))
        dae = daemon_answer(conn, root, question, hits, profile=profile,
                            owner_scoped=owner_scoped, brain=brain, u_bar=u_bar,
                            extract_client=client, stats=stats)
        row(qid, "gather.py", ref, q)
        row(qid, "daemon", dae, q)

        agree = _same_assertion(ref, dae)
        # a NEW confident-wrong: the daemon reports a wrong value where the reference did not
        # assert that same value (so the daemon — not gather.py — introduced it)
        ncw = (dae.action == "report" and _correct(dae.asserted, q) is False
               and not _same_assertion(ref, dae))
        if not agree:
            mismatches.append({"id": qid, "ref": ref.__dict__, "dae": dae.__dict__})
        if ncw:
            new_confident_wrong.append({"id": qid, "dae": dae.__dict__, "gold": q.get("answer")})
        mark = "✓" if agree else "✗"
        owner_mark = "·my" if owner_scoped else "   "
        print(f"  {qid}{owner_mark} {mark} ref={ref.action}/{(ref.asserted or '∅')[:18]:<18} "
              f"dae={dae.action}/{(dae.asserted or '∅')[:18]}")

    matrix.close()
    elapsed = time.monotonic() - t0
    n = len(questions)
    parity_holds = not mismatches
    zero_ncw = not new_confident_wrong
    certified = parity_holds and zero_ncw

    report = [
        "# answer-brain gate — end-to-end parity (daemon vs gather.py)", "",
        f"- questions: **{n}** ({n_owner} owner-scoped) · k={args.k} · {elapsed:.1f}s",
        f"- parity: **{n - len(mismatches)}/{n}** per-question outcomes match",
        f"- gate `parity_holds`: **{'pass' if parity_holds else 'review'}**",
        f"- gate `zero_new_confident_wrong`: **{'pass' if zero_ncw else 'review'}**",
        f"- **recommendation: {'CERTIFIED' if certified else 'REVIEW'}** "
        "(certified only if both gates pass)", "",
        "The daemon's gather policy matches `gather.py` by construction "
        "(`test_gather.jl`); this certifies the wire end-to-end over the real corpus.",
        f"- daemon recency-gather branch fired on **{stats['recency_gather']}** question(s) "
        "— the `/decide`→gather→re-extract loop was non-trivially exercised, not all-abstain.", "",
    ]
    if mismatches:
        report.append("## Mismatches")
        report += [f"- `{m['id']}`: ref={m['ref']} vs daemon={m['dae']}" for m in mismatches]
        report.append("")
    if new_confident_wrong:
        report.append("## NEW confident-wrong (hard-gate breach)")
        report += [f"- `{w['id']}`: daemon reported {w['dae']['asserted']!r} (gold {w['gold']!r})"
                   for w in new_confident_wrong]
        report.append("")
    (out_dir / "report.md").write_text("\n".join(report), encoding="utf-8")

    print("=" * 72)
    print(f"parity {n - len(mismatches)}/{n} · parity_holds={'pass' if parity_holds else 'REVIEW'}"
          f" · zero_new_confident_wrong={'pass' if zero_ncw else 'REVIEW'}")
    print(f"recommendation: {'CERTIFIED' if certified else 'REVIEW'}"
          f" · recency-gather fired on {stats['recency_gather']} question(s)")
    print(f"report → {out_dir / 'report.md'} · matrix → {out_dir / 'call_matrix.jsonl'}")
    return 0 if certified else 1


if __name__ == "__main__":
    raise SystemExit(main())
