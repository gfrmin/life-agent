#!/usr/bin/env python3
"""``scripts/fairfight/run_fairfight.py`` — the fair-fight runner.

Drives every selected arm (``baseline`` = the credence executor daemon, ``inprocess`` =
the in-process typed-families path with gather on, ``synthesis`` = the same path with
gather off — mirroring ``run_eval.py --synthesis`` — and the two hermes-driven external
arms: ``competitor`` = the ceiling-model adversary, ``oracle`` = the frontier reference
policy π* at ``claude-opus-4-8`` by default, opt-in — roadmap A1) over the frozen eval
corpus, grades each answer with the EXISTING referee machinery
(``grading.grade_channels`` + ``judge.judge_modal``, never rebuilt), and writes
one ``OutcomeVector`` per (arm, question) plus per-arm summaries under
``$LIFE_AGENT_KB/eval/fairfight/<run_id>/``.

Usage::

    uv run --project . python scripts/fairfight/run_fairfight.py --config PATH \\
        [--k 20] [--arms baseline,inprocess,synthesis,competitor[,oracle]] \\
        [--competitor-model M] [--competitor-provider P] [--competitor-base-url URL] \\
        [--oracle-model M] [--oracle-provider P] [--oracle-base-url URL] \\
        [--hermes-bin PATH] [--timeout-s 300] [--limit N] [--no-judge] [--fresh] \\
        [--run-id ID]

``--fresh`` busts the derivation cache for the in-process arms (``ask.answer(...,
no_cache=True)``) so a warm cache can't mute the $ headline (zero model calls ->
``cost_status=unavailable``); it is a no-op for the out-of-process ``baseline`` arm
(``ask.answer_via_executor`` has no cache knob — its cache is server-side).

**Seam resolutions (landed-code realities this task adapted to, not the plan's guesses):**

1. **Retrieved texts, per arm.** ``arm_baseline.answer_baseline``/``arm_synthesis.
   answer_synthesis`` each call ``ask.answer``/``ask.answer_via_executor``, which return
   ``(text, cards, scores)`` — but the landed ``RawAnswer`` (tasks 8-9) discarded ``cards``
   as ``_cards``, leaving this runner with no way to grade retrieval or build a judge
   sources block. Rather than reconstruct retrieval from ``decision_view`` (whose
   ``candidates`` are short VALUES, not chunk text — verified against
   ``triage_answers.triage_one``, which uses ``[c.text for c in cards]`` for exactly this),
   ``RawAnswer`` gained a ``cards: tuple[dict, ...]`` field (``{"n","text","origin"}``,
   JSON-safe) in this task, threaded through all three in-process construction sites plus
   an explicit ``cards=()`` at ``arm_hermes.py``'s single call site. The competitor arm
   never had this problem: its retrieved set is ``chunk_text_full`` values across
   ``CompetitorResult.tool_log`` rows' ``results`` (the task brief's own instruction),
   already on hand.
2. **Calibration writes.** ``ask.answer(..., families=True)`` (the ``inprocess``/
   ``synthesis`` arms) routes through ``core.lookup.decide_and_record`` /
   ``core.narrative.narrative_answer``, and NEITHER function ``ask.answer`` ever threads a
   ``decisions_path`` override through — both default to
   ``life_agent.core.config.DECISIONS_LOG``, the PRODUCTION calibration log. That
   contradicts this task's "no production log contamination" requirement. Editing
   ``ask.answer`` to add the missing parameter is out of scope (a frozen, already-reviewed
   entrypoint). Since ``lookup.py``/``narrative.py`` resolve ``config.DECISIONS_LOG`` by
   module-attribute lookup at call time (``from life_agent.core import config``), this
   runner reassigns that ONE attribute to a shadow file under the run dir for the
   in-process arms' duration (:func:`_redirect_decisions_log`) and restores it afterward,
   even on failure. The ``baseline`` arm's out-of-process executor daemon is NOT reachable
   this way — its own decision/gather-outcome writes to the live calibration log are a
   disclosed, unfixable-from-here side effect of hitting the real daemon (matching
   ``arm_baseline.py``'s own "daemon spend invisible" disclosure for cost). (Final-review
   IMPORTANT-3: the shadow is SEEDED from production's real ``decisions.jsonl`` at redirect
   time — see :func:`_redirect_decisions_log`'s own docstring — so ``current_u_bar``'s fold
   of the owner's real g/b verdicts isn't silently reset to the un-narrowed prior for the
   run's duration; new writes still land only in the shadow.)
3. **Vector assembly is judge-first, not append-as-you-go.** The brief's numbered
   sequence lists "assemble the OutcomeVector -> append to vectors.jsonl" (step 2) BEFORE
   "judge pass batched per arm" (step 3) — but ``OutcomeVector.hallucinated`` and the
   three rubric dims are judge outputs (``core/outcomes.py``-style records document
   ``None`` as "not yet judged", not "never will be"). Writing a vector before judging and
   never revising it would strand every judged row at ``hallucinated=None`` forever,
   defeating the whole rubric axis (and task 11's dominance analysis, which reads these
   vectors directly). This runner therefore buffers each arm's (question, raw answer,
   channel grades) rows in memory across the FULL per-question loop, THEN runs the judge
   pass, THEN assembles and writes ``vectors.jsonl`` once per arm — still "one
   OutcomeVector per (arm, question), correct arm names," just not literally interleaved
   with judging. ``answers.jsonl`` (which needs no judge output) IS written incrementally,
   one line per question, as specified.
4. **``gather_rounds`` is arm-class-mapped by :func:`_gather_rounds` (final-review
   IMPORTANT-5, revising this seam's original "never alias" choice).** In-process arms
   (``inprocess``/``synthesis``) declare the semantic equivalence "one corroboration tier
   fired = one gather round" and map verbatim from ``effort["gather_tiers"]`` — the
   attention axis previously left them at ``None`` (contributing ~0 attention) next to the
   competitor's full ``search``-tool-call count, an unstated and misleading asymmetry
   ``scripts/dominance/pareto.py``'s Pareto frontier scored over. The ``competitor`` arm's
   own ``effort["gather_rounds"]`` (``arm_hermes.py``'s ``search``-call count) is unchanged.
   The ``baseline`` (executor) arm still reports ``gather_rounds=None``: the daemon's own
   gather/grow round count is genuinely not observable in the ``View``
   ``core/executor.py`` returns (confirmed against its return statements, never edited to
   expose them — out of this task's scope) — never a guessed 0.
5. **Calibration axis (probability/p_none/p_none_correct/brier) is scoped to the
   ``baseline``/``inprocess`` arms exactly as the dispatch specifies**, gated further on
   the decision view actually being a ``lookup`` family decision with real credences
   (``synthesis`` and ``competitor`` always report ``None`` — never imputed), and (final-
   review IMPORTANT-4) on the channel grade actually being an ASSERTING decision for
   probability/brier specifically (``_calibration``'s own docstring). Since final-review
   CRITICAL-1, ``baseline`` (the executor arm) DOES populate ``decision_view`` for its
   typed-lookup decisions (``arm_baseline._executor_decision``, over
   ``ask.EXECUTOR_VIEW_LAST``) — its calibration fields come alive whenever the executor
   decided via the typed-lookup family; they stay ``None`` for its narrative-fallback
   decisions (no structured credence data survives the executor's own narrative branch —
   see ``arm_baseline._executor_decision``'s docstring) and for a down/errored executor.

**Directory layout** (``$LIFE_AGENT_KB/eval/fairfight/<run_id>/``, per the plan):
``run_meta.json``, ``questions.sha256``, ``arms/<arm>/{answers,vectors}.jsonl``
(``arms/competitor/{tool_calls/<qid>.jsonl,usage/<qid>.json,hermes_home/}`` are
``arm_hermes.py``'s own outputs, not this module's), ``judge/<arm>_scores.jsonl``,
``judge/judge_meta.json``, ``summary.json``, ``summary.md``. Fairfight never writes
``$LIFE_AGENT_KB/calibration/`` (no new ``core.outcomes.GRADERS`` entry) — the run dir is
the self-contained evidence.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
from collections import Counter
from collections.abc import Callable, Iterator
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # scripts/: ask, run_eval
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "comparison"))  # _common etc.

import duckdb
from run_eval import _classify_synthesis, _kb_root, load_questions, synthesis_rates

import life_agent.core.config as LCFG
import life_agent.core.jsonl_log as JL
import life_agent.core.outcomes as OUT
import life_agent.core.pricing as PRICING
from fairfight import arm_baseline as AB
from fairfight import arm_claude as AC
from fairfight import arm_hermes as AH
from fairfight import arm_synthesis as AS
from fairfight import grading as G
from fairfight import judge as J
from life_agent.core.citation import audit as citation_audit
from life_agent.core.sources import SourceCard
from life_agent.fairfight import records as REC

FORMAT_VERSION = 1  # this module's own artifacts (run_meta.json/summary.json); independent
# of records.FORMAT_VERSION (the OutcomeVector schema version, carried per-vector already).

_REPO_ROOT = Path(__file__).resolve().parents[2]


# --- git / environment provenance (run_meta.json) ----------------------------------------


def _git_info(repo_dir: Path) -> dict[str, Any]:
    """Best-effort ``(sha, dirty)`` for a git checkout at ``repo_dir``. Never raises —
    a missing/broken git is a named ``note``, not a crashed run."""
    try:
        sha = subprocess.run(
            ["git", "-C", str(repo_dir), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "-C", str(repo_dir), "status", "--porcelain"],
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout
        return {"sha": sha, "dirty": bool(status.strip()), "note": None}
    except Exception as e:  # provenance is best-effort by contract
        return {"sha": None, "dirty": None, "note": f"{type(e).__name__}: {e}"}


def _hermes_repo_root(hermes_bin: str) -> Path | None:
    """Walk up from ``hermes_bin``'s resolved path looking for a ``.git`` — the hermes
    checkout, when the binary lives inside one (a dev checkout, not a system install)."""
    try:
        p = Path(hermes_bin).resolve()
    except OSError:
        return None
    for candidate in (p, *p.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def _hermes_version(hermes_bin: str) -> str | None:
    try:
        r = subprocess.run(
            [hermes_bin, "--version"], capture_output=True, text=True, timeout=5)
        out = (r.stdout or r.stderr or "").strip()
        return out or None
    except Exception:  # best-effort, never blocks the run
        return None


def _hermes_git_info(hermes_bin: str | None) -> dict[str, Any]:
    """``{"sha","dirty","version","note"}`` — every field ``None`` when the competitor
    arm isn't selected (``hermes_bin`` is ``None``) or no ``.git`` is found from its path."""
    if not hermes_bin:
        return {"sha": None, "dirty": None, "version": None,
                "note": "no external (hermes-driven) arm selected"}
    version = _hermes_version(hermes_bin)
    root = _hermes_repo_root(hermes_bin)
    if root is None:
        return {"sha": None, "dirty": None, "version": version,
                "note": "no git repo found walking up from --hermes-bin"}
    info = _git_info(root)
    return {"sha": info["sha"], "dirty": info["dirty"], "version": version, "note": info["note"]}


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


# --- corpus fingerprint (cheap read-only queries; failures -> nulls + note) --------------


def _corpus_fingerprint(conn: Any) -> dict[str, Any]:
    try:
        n_chunks = conn.execute("SELECT COUNT(*) FROM artifact_chunks").fetchone()[0]
        n_sources = conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
        return {"n_chunks": int(n_chunks), "n_sources": int(n_sources), "note": None}
    except Exception as e:  # a locked/unreachable catalogue is a note, not a crash
        return {"n_chunks": None, "n_sources": None, "note": f"{type(e).__name__}: {e}"}


# --- run_meta.json -------------------------------------------------------------------------


def _arm_configs(args: argparse.Namespace, arms: list[str], hermes_bin: str | None,
                  claude_bin: str | None = None) -> dict[str, dict[str, Any]]:
    cfgs: dict[str, dict[str, Any]] = {}
    fresh = bool(getattr(args, "fresh", False))
    if "baseline" in arms:
        # the executor path has no cache knob (ask.answer_via_executor is a pure HTTP
        # driver — its cache is server-side), so --fresh does not apply; recorded false.
        cfgs["baseline"] = {"entrypoint": "ask.answer_via_executor", "path": "executor",
                            "fresh": False}
    if "inprocess" in arms:
        cfgs["inprocess"] = {"entrypoint": "ask.answer", "path": "inprocess", "gather": True,
                             "fresh": fresh}
    if "synthesis" in arms:
        cfgs["synthesis"] = {"entrypoint": "ask.answer", "path": "inprocess", "gather": False,
                             "fresh": fresh}
    for ext in sorted(REC.HERMES_ARMS & set(arms)):
        model, provider, base_url = _external_model_args(args, ext)
        cfgs[ext] = {
            "model": model, "provider": provider,
            "base_url": base_url, "timeout_s": args.timeout_s,
            "hermes_bin": hermes_bin,
        }
    if "deliberative" in arms:
        cfgs["deliberative"] = {
            "entrypoint": "claude -p",
            "model": getattr(args, "deliberative_model", AC.ClaudeArmConfig.model),
            "timeout_s": int(getattr(args, "deliberative_timeout_s",
                                     AC.ClaudeArmConfig.timeout_s)),
            "max_turns": AC.ClaudeArmConfig.max_turns,
            "allowed_tools": AC._ALLOWED_TOOLS,
            "claude_bin": claude_bin,
        }
    return cfgs


def _external_model_args(args: argparse.Namespace, arm: str) -> tuple[str, str, str | None]:
    """The (model, provider, base_url) CLI coordinates for one external arm — the ONLY
    place the per-arm flag names are mapped, so the config block and the arm impl can
    never drift apart."""
    if arm == "oracle":
        return args.oracle_model, args.oracle_provider, args.oracle_base_url
    return args.competitor_model, args.competitor_provider, args.competitor_base_url


def _claude_version(claude_bin: str | None) -> str | None:
    """Best-effort ``claude --version`` provenance for the deliberative arm — the CLI's
    version (and the machine's Claude Code config it implies) is part of the reference
    policy's identity. Never raises."""
    if not claude_bin:
        return None
    try:
        out = subprocess.run([claude_bin, "--version"], capture_output=True, text=True,
                             timeout=30)
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def _build_run_meta(
    *, run_id: str, args: argparse.Namespace, arms: list[str], questions_path: Path,
    conn: Any, hermes_bin: str | None, claude_bin: str | None = None,
) -> dict[str, Any]:
    import _common as JC  # scripts/comparison/_common.py — the judge pin
    from blind_judge import RUBRIC

    rubric_sha256: str | None = None
    rubric_note: str | None = None
    try:
        rubric_sha256 = hashlib.sha256(RUBRIC.read_bytes()).hexdigest()
    except OSError as e:
        rubric_note = f"{type(e).__name__}: {e}"

    return {
        "format_version": FORMAT_VERSION,
        "run_id": run_id,
        "created_at": _now_iso(),
        "life_agent_git": _git_info(_REPO_ROOT),
        "hermes_git": _hermes_git_info(hermes_bin if REC.HERMES_ARMS & set(arms) else None),
        "claude_version": _claude_version(claude_bin if "deliberative" in arms else None),
        "prompt_delib_v1_sha256": hashlib.sha256(
            AC.PROMPT_DELIB_V1.encode("utf-8")).hexdigest(),
        "questions_path": str(questions_path),
        "questions_sha256": hashlib.sha256(questions_path.read_bytes()).hexdigest(),
        "rubric_path": str(RUBRIC),
        "rubric_sha256": rubric_sha256,
        "rubric_note": rubric_note,
        "judge_model": JC.JUDGE_MODEL,
        "judge_n": JC.JUDGE_N,
        "k": args.k,
        "pricing_version": PRICING.PRICING_VERSION,
        "prompt_v1_sha256": hashlib.sha256(AH.PROMPT_V1.encode("utf-8")).hexdigest(),
        "arms": arms,
        "arm_configs": _arm_configs(args, arms, hermes_bin, claude_bin),
        "corpus_fingerprint": _corpus_fingerprint(conn),
        "pkm_config_path": args.config,
        # LIFE_AGENT_BRIDGE_URL / ANSWER_BRAIN_URL are the exact names scripts/ask.py
        # reads for EXECUTOR_BRIDGE / EXECUTOR_DAEMON — they determine WHICH daemon the
        # baseline arm actually hit (null = unset, ask.py's localhost defaults apply).
        "env_flags": {
            "LIFE_AGENT_BRIDGE_URL": os.environ.get("LIFE_AGENT_BRIDGE_URL"),
            "ANSWER_BRAIN_URL": os.environ.get("ANSWER_BRAIN_URL"),
        },
        "no_judge": bool(args.no_judge),
        "limit": args.limit,
        "timeout_s": args.timeout_s,
    }


# --- calibration-write redirect (seam resolution 2, module docstring) --------------------


@contextlib.contextmanager
def _redirect_decisions_log(run_dir: Path) -> Iterator[Path]:
    """Redirect ``life_agent.core.config.DECISIONS_LOG`` to a shadow file under the run
    dir for the wrapped block, restoring it after (even on failure). See the module
    docstring's seam resolution 2 for why this is necessary and why it's sufficient for
    the in-process arms but NOT the out-of-process executor daemon.

    Final-review IMPORTANT-3: the shadow is SEEDED from the real production
    ``decisions.jsonl`` (a one-time copy, taken here before redirecting) when one exists.
    ``core.lookup.current_u_bar`` reads ``config.DECISIONS_LOG`` — a module-attribute
    lookup, at call time (``lookup.py``'s own ``current_u_bar`` -> ``R.load_reactions``) —
    to fold the owner's REAL g/b verdicts into u(wrong), the posterior that sets the
    in-process arms' assert/abstain threshold. An unseeded empty shadow would silently
    reset that fold to the wide, un-narrowed PRIOR for the whole run: a different (and
    undisclosed) threshold than production ever uses, contaminating exactly the
    calibration axis this harness measures. Every WRITE during the run still lands ONLY
    in the shadow (an append-only file, copied once, never read back into production) —
    production's own file is touched here exactly once, read-only."""
    shadow = run_dir / "shadow_calibration" / "decisions.jsonl"
    shadow.parent.mkdir(parents=True, exist_ok=True)
    original = LCFG.DECISIONS_LOG
    if original.exists():
        shutil.copyfile(original, shadow)
    LCFG.DECISIONS_LOG = shadow
    try:
        yield shadow
    finally:
        LCFG.DECISIONS_LOG = original


# --- JSONL / JSON file helpers (reuse the shared durable-append mechanics) ---------------


def _append_jsonl(path: Path, obj: dict[str, Any]) -> None:
    JL.append_line(path, json.dumps(obj, sort_keys=True, ensure_ascii=False))


def _write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _raw_answer_to_json(raw: AB.RawAnswer, *, usage: dict[str, Any] | None) -> dict[str, Any]:
    d = asdict(raw)  # recurses through llm_calls (LLMResult dataclasses) and cards (dicts)
    d["usage"] = usage
    return d


# --- per-arm retrieval / sources / structural-citation extraction ------------------------


def _answerable(q: dict[str, Any]) -> bool:
    return bool(q.get("answerable", bool(q.get("answer", ""))))


def _inprocess_retrieved_and_sources(
    raw: AB.RawAnswer,
) -> tuple[list[str], list[dict[str, Any]]]:
    cards = list(raw.cards)
    return [c["text"] for c in cards], cards


def _structural_unsupported_inprocess(raw: AB.RawAnswer) -> bool:
    cards = [SourceCard(n=c["n"], text=c["text"], origin=c.get("origin", "")) for c in raw.cards]
    return not citation_audit(raw.text, cards).ok


def _tool_log_has_error(tool_log: list[dict[str, Any]]) -> bool:
    return any(row.get("error") is not None for row in tool_log)


def _competitor_retrieved_texts(tool_log: list[dict[str, Any]]) -> list[str]:
    return [
        r["chunk_text_full"]
        for row in tool_log
        for r in (row.get("results") or [])
        if isinstance(r, dict) and r.get("chunk_text_full")
    ]


def _competitor_sources(tool_log: list[dict[str, Any]], k: int) -> list[dict[str, Any]]:
    """Deduped ``(source_path, text)`` pairs across every tool call's results, capped at
    ``k`` (mirroring the in-process arms' retrieval width) — the judge's cited-source
    block, built from ``chunk_text_full`` (the FULL chunk text, not the truncated
    ``snippet_shown`` KWIC — matching ``judge.py``'s own reasoning for needing full text)."""
    seen: set[tuple[Any, str]] = set()
    out: list[dict[str, Any]] = []
    for row in tool_log:
        for r in row.get("results") or []:
            if not isinstance(r, dict):
                continue
            text = r.get("chunk_text_full")
            if not text:
                continue
            key = (r.get("source_path"), text)
            if key in seen:
                continue
            seen.add(key)
            out.append({"n": len(out) + 1, "source_path": r.get("source_path"), "text": text})
            if len(out) >= k:
                return out
    return out


# --- calibration + economics + effort axes ------------------------------------------------


class _Calibration(TypedDict):
    probability: float | None
    p_none: float | None
    p_none_correct: bool | None
    brier: float | None


_NO_CALIBRATION: _Calibration = {
    "probability": None, "p_none": None, "p_none_correct": None, "brier": None}


def _calibration(arm: str, raw: AB.RawAnswer, grades: G.ChannelGrades) -> _Calibration:
    """probability/p_none/p_none_correct/brier — ``baseline``/``inprocess`` only (task
    dispatch §5), gated further on the decision view being a real lookup-family credence.
    Never imputed: any other arm, or a lookup-less decision, is all-``None``.

    Final-review IMPORTANT-4: ``probability``/``brier`` score a credence the arm actually
    STAKED on a value — populated only when ``grades.asserted`` (records.py's own
    contract: "None = the arm asserted no credence"). An abstain/ask_clarify decision
    still carries a real ``max(credences)`` number (the posterior's leader, computed
    whether or not it cleared the assert bar), but scoring THAT as if the arm reported it
    would grade a decision the arm never made. ``p_none``/``p_none_correct`` are NOT
    gated the same way: the none-of-the-retrieved posterior IS the withholding decision's
    own credence, meaningful whether or not the arm also asserted a value (a ``hedge`` is
    an assertion-class act here — see ``triage_answers._lookup_view`` — so it still gets
    probability/brier too)."""
    if arm not in ("baseline", "inprocess"):
        return _NO_CALIBRATION
    view = raw.decision_view
    if not view or view.get("family") != "lookup":
        return _NO_CALIBRATION
    credences = view.get("credences") or []
    p_none = view.get("p_none")
    if not credences or p_none is None:
        return _NO_CALIBRATION
    gold_in_candidates = grades.gold_in_candidates
    p_none_correct = (
        None if gold_in_candidates is None
        else (p_none >= 0.5) == (not gold_in_candidates)
    )
    if not grades.asserted:
        return {"probability": None, "p_none": p_none,
                "p_none_correct": p_none_correct, "brier": None}
    probability = max(credences)
    brier = OUT.brier_score(probability, correct=grades.asserted_correct)
    return {"probability": probability, "p_none": p_none,
            "p_none_correct": p_none_correct, "brier": brier}


def _economics(arm: str, raw: AB.RawAnswer, usage: dict[str, Any] | None) -> dict[str, Any]:
    if arm in REC.EXTERNAL_ARMS:
        usage = usage or {}
        estimated_cost = usage.get("estimated_cost_usd")
        model_tier_mix = (
            {str(usage["model"]): int(usage.get("api_calls") or 0)} if usage.get("model") else {}
        )
        # PR-21 MINOR: honor the hermes usage file's OWN cost_status when it reports one
        # AND it maps into the closed vocab {measured, estimated, partial, unavailable} —
        # never let an unknown value through (records.py's __post_init__ would reject it,
        # crashing the run). Fall back to the harness's derived status otherwise.
        reported_status = usage.get("cost_status")
        fallback_status = "estimated" if estimated_cost is not None else "unavailable"
        cost_status = (
            reported_status if reported_status in REC.COST_STATUSES else fallback_status)
        return {
            "cost_usd": float(estimated_cost) if estimated_cost is not None else None,
            "cost_status": cost_status,
            "in_tokens": int(usage.get("input_tokens") or 0),
            "out_tokens": int(usage.get("output_tokens") or 0),
            "cache_read_tokens": int(usage.get("cache_read_tokens") or 0),
            "cache_write_tokens": int(usage.get("cache_write_tokens") or 0),
            "model_tier_mix": model_tier_mix,
        }

    calls = raw.llm_calls
    if not calls and arm != "baseline":
        return {"cost_usd": None, "cost_status": "unavailable", "in_tokens": 0, "out_tokens": 0,
                "cache_read_tokens": 0, "cache_write_tokens": 0, "model_tier_mix": {}}
    costs = [PRICING.cost_usd(r) for r in calls]
    priced_costs = [c for c in costs if c is not None]
    if arm == "baseline":
        # The executor (credence answer-brain daemon) is a SEPARATE out-of-process
        # service — its own spend never reaches this in-process meter (arm_baseline.py's
        # own module docstring). Hard-coded "partial" regardless of what this process's
        # own meter shows — including the NORMAL case of zero local calls
        # (answer_via_executor is a pure HTTP driver): the daemon's real spend exists
        # either way, so "unavailable" (no cost signal at all) would misreport it.
        cost_status = "partial"
    elif len(priced_costs) < len(costs):
        cost_status = "partial"
    else:
        cost_status = "measured"
    return {
        "cost_usd": sum(priced_costs) if priced_costs else None,
        "cost_status": cost_status,
        "in_tokens": sum(r.in_tokens for r in calls),
        "out_tokens": sum(r.out_tokens for r in calls),
        "cache_read_tokens": sum(r.cache_read_tokens for r in calls),
        "cache_write_tokens": sum(r.cache_write_tokens for r in calls),
        "model_tier_mix": dict(Counter(r.served_model for r in calls)),
    }


def _asks_issued(decision_view: dict[str, Any] | None) -> int:
    return 1 if (decision_view or {}).get("action") == "ask_clarify" else 0


def _gather_rounds(arm: str, raw: AB.RawAnswer) -> int | None:
    """The attention axis's gather/tool-round count, per arm class (final-review
    IMPORTANT-5, revising the module docstring's seam resolution 4): in-process arms
    (``inprocess``/``synthesis``) declare the semantic equivalence "one corroboration
    tier fired = one gather round" and map verbatim from ``effort["gather_tiers"]`` — the
    counter ``ask.py``'s own gather loop increments (see ``ask.py``'s ``EFFORT_LAST``
    comment); this REPLACES the prior "always None for in-process arms" choice, which
    left them contributing ~0 attention next to the competitor's full tool-call count.
    The ``competitor`` arm already reports its own ``"gather_rounds"`` key
    (``arm_hermes.py``'s ``search``-tool-call count) — read verbatim, unchanged. The
    ``baseline`` (executor) arm's daemon-side gather/grow rounds are NOT observable in
    the ``View`` ``core/executor.py`` returns (confirmed against its return statements —
    never edited to expose them, per this task's own constraint), so it stays ``None``
    (never a guessed 0); its only attention contribution is ``asks_issued`` (now real,
    since CRITICAL-1 gives it a structured decision_view an ``ask_clarify`` can be read
    from)."""
    if arm in ("inprocess", "synthesis"):
        return raw.effort.get("gather_tiers")
    if arm in REC.EXTERNAL_ARMS:
        return raw.effort.get("gather_rounds")
    return None  # baseline: not derivable from the executor's View — see above


def _tool_calls(arm: str, raw: AB.RawAnswer) -> int | None:
    return raw.effort.get("tool_calls") if arm in REC.EXTERNAL_ARMS else None


# --- per-arm driver: answer + grade every question ----------------------------------------


def _run_arm(
    arm: str, questions: list[dict[str, Any]], *, run_dir: Path, conn: Any, k: int,
    arm_fn: Callable[[dict[str, Any]], Any],
) -> list[dict[str, Any]]:
    """Answer + grade every question for one arm. ``answers.jsonl`` is written
    incrementally (one line per question, as the brief specifies); the returned rows are
    what the judge pass and vector assembly need (see the module docstring's seam
    resolution 3 for why vectors.jsonl itself is written only after judging)."""
    answers_path = run_dir / "arms" / arm / "answers.jsonl"
    answers_path.parent.mkdir(parents=True, exist_ok=True)
    answers_path.unlink(missing_ok=True)  # fresh per run (defends a --run-id re-run)
    if arm in REC.EXTERNAL_ARMS:
        # Final-review IMPORTANT-6: clean arm_hermes.py's own per-qid scratch dirs at run
        # start too — a --run-id re-run (or a run with a smaller --limit than a prior run
        # under the same run_id) could otherwise leave a STALE tool_calls/<qid>.jsonl or
        # usage/<qid>.json for a question not in THIS run's set lying around.
        for sub in ("tool_calls", "usage"):
            shutil.rmtree(run_dir / "arms" / arm / sub, ignore_errors=True)

    rows: list[dict[str, Any]] = []
    for q in questions:
        usage: dict[str, Any] | None = None
        if arm in REC.EXTERNAL_ARMS:
            result = arm_fn(q)
            raw, usage, tool_log = result.raw, result.usage, result.tool_log
            if _tool_log_has_error(tool_log):  # item 8: retry ONCE on a locked-catalogue etc.
                result = arm_fn(q)
                raw, usage, tool_log = result.raw, result.usage, result.tool_log
                note = 'retried once: a tool_log row reported {"error": ...}'
                raw.notes = f"{raw.notes}; {note}" if raw.notes else note
            retrieved_texts = _competitor_retrieved_texts(tool_log)
            sources = _competitor_sources(tool_log, k)
            structural_unsupported = not G.hermes_citation_check(raw.text, tool_log)
        else:
            raw = arm_fn(q)
            retrieved_texts, sources = _inprocess_retrieved_and_sources(raw)
            structural_unsupported = _structural_unsupported_inprocess(raw)

        _append_jsonl(answers_path, _raw_answer_to_json(raw, usage=usage))
        grades = G.grade_channels(q, raw.text, retrieved_texts, raw.decision_view, conn)
        rows.append({"q": q, "raw": raw, "grades": grades, "sources": sources,
                     "structural_unsupported": structural_unsupported, "usage": usage})
    return rows


# --- judge pass (batched per arm, after that arm's answers) -------------------------------


def _judge_arm(
    arm: str, rows: list[dict[str, Any]], *, run_dir: Path,
    judge_fn: Callable[..., dict[str, Any]], judge_n: int, no_judge: bool,
) -> list[dict[str, Any]]:
    judged_path = run_dir / "judge" / f"{arm}_scores.jsonl"
    judged_path.parent.mkdir(parents=True, exist_ok=True)
    judged_path.unlink(missing_ok=True)

    out: list[dict[str, Any]] = []
    for row in rows:
        q, raw, grades = row["q"], row["raw"], row["grades"]
        base: dict[str, Any] = {
            "question_id": str(q["id"]), "faithfulness": None, "completeness": None,
            "citation_fidelity": None, "hallucinated": None, "synthesis_pass": None,
            "abstained_correctly": None, "judged": False, "reason": None,
        }
        if no_judge:
            base["reason"] = "no_judge"
        elif raw.status != "ok":
            base["reason"] = f"status={raw.status}"
        else:
            # Guarded like the arms' own answer calls: judge_modal → judge_complete →
            # openai_complete raises SystemExit on any HTTP/API failure (core/llm.py's
            # convention) — one transient judge error must cost one question's rubric
            # dims (recorded, dims stay None), never the whole multi-arm run.
            try:
                scores = judge_fn(q, raw.text, row["sources"], n=judge_n)
            except (Exception, SystemExit) as e:
                scores = {}
                base["reason"] = f"judge error: {type(e).__name__}: {e}"
            if not scores:
                if base["reason"] is None:  # all-N-malformed (judge_modal's own {} return)
                    base["reason"] = "judge_failed"
            else:
                cls = _classify_synthesis(
                    faithfulness=scores["faithfulness"],
                    citation_fidelity=scores["citation_fidelity"],
                    structural_unsupported=row["structural_unsupported"],
                    answerable=_answerable(q), declined=grades.declined)
                base.update(
                    faithfulness=scores["faithfulness"], completeness=scores["completeness"],
                    citation_fidelity=scores["citation_fidelity"],
                    served_models=scores.get("_served"), hallucinated=cls["hallucinated"],
                    synthesis_pass=cls["synthesis_pass"],
                    abstained_correctly=cls["abstained_correctly"], judged=True)
        out.append(base)
        _append_jsonl(judged_path, base)
    return out


# --- vector assembly + write ---------------------------------------------------------------


def _assemble_vectors(
    run_id: str, arm: str, rows: list[dict[str, Any]], judged: list[dict[str, Any]],
) -> list[REC.OutcomeVector]:
    vectors: list[REC.OutcomeVector] = []
    for row, j in zip(rows, judged, strict=True):
        q, raw, grades, usage = row["q"], row["raw"], row["grades"], row["usage"]
        calib = _calibration(arm, raw, grades)
        econ = _economics(arm, raw, usage)
        vectors.append(REC.OutcomeVector(
            format_version=REC.FORMAT_VERSION, run_id=run_id, arm=arm,
            question_id=str(q["id"]), answerable=_answerable(q),
            faithfulness=j["faithfulness"], completeness=j["completeness"],
            citation_fidelity=j["citation_fidelity"],
            bucket=grades.bucket, cause=grades.cause,
            asserted=grades.asserted, asserted_correct=grades.asserted_correct,
            asserted_distractor=grades.asserted_distractor,
            hallucinated=j["hallucinated"], declined=grades.declined,
            correct_abstention=grades.correct_abstention, over_abstention=grades.over_abstention,
            gold_in_topk=grades.gold_in_topk, gold_in_corpus=grades.gold_in_corpus,
            gold_in_candidates=grades.gold_in_candidates,
            distractor_in_topk=grades.distractor_in_topk, n_retrieved=grades.n_retrieved,
            probability=calib["probability"], p_none=calib["p_none"],
            p_none_correct=calib["p_none_correct"], brier=calib["brier"],
            cost_usd=econ["cost_usd"], cost_status=econ["cost_status"],
            in_tokens=econ["in_tokens"], out_tokens=econ["out_tokens"],
            cache_read_tokens=econ["cache_read_tokens"],
            cache_write_tokens=econ["cache_write_tokens"],
            latency_s=raw.latency_s, model_tier_mix=econ["model_tier_mix"],
            gather_rounds=_gather_rounds(arm, raw), asks_issued=_asks_issued(raw.decision_view),
            tool_calls=_tool_calls(arm, raw), think_ticks=None,
            answer_sha256=hashlib.sha256(raw.text.encode("utf-8")).hexdigest(),
            answer_chars=len(raw.text), lineage_keys=raw.lineage_keys,
            status=raw.status, notes=raw.notes,
        ))
    return vectors


def _write_vectors(run_dir: Path, arm: str, vectors: list[REC.OutcomeVector]) -> None:
    path = run_dir / "arms" / arm / "vectors.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    for v in vectors:
        _append_jsonl(path, REC.to_json(v))


# --- per-arm summary + the run's summary.json / summary.md --------------------------------


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * p
    f, c = math.floor(k), math.ceil(k)
    if f == c:
        return s[int(k)]
    return s[f] + (s[c] - s[f]) * (k - f)


def _summarize_arm(arm: str, vectors: list[REC.OutcomeVector], judged: list[dict[str, Any]]
                    ) -> dict[str, Any]:
    n_total = len(vectors)
    n_ok = sum(1 for v in vectors if v.status == "ok")
    n_error = sum(1 for v in vectors if v.status == "error")
    n_timeout = sum(1 for v in vectors if v.status == "timeout")

    # Final-review CRITICAL-2: every rate/mean/frontier-feeding number below is the
    # SCORED population only (records.py's own docstring contract — "status flags infra
    # failures (never graded, excluded from scoring)"), via `REC.scored`, the ONE
    # canonical filter. `judged` stays index-aligned with `vectors` (built via
    # `zip(..., strict=True)` upstream in `_judge_arm`); re-derive the same alignment
    # over the scored subset by object identity (OutcomeVector carries a `dict` field, so
    # it isn't hashable — identity is the correct, cheap correspondence here since
    # `REC.scored` returns the SAME instances, never copies).
    scored_vectors = REC.scored(vectors)
    scored_ids = {id(v) for v in scored_vectors}
    scored_pairs = [(v, j) for v, j in zip(vectors, judged, strict=True) if id(v) in scored_ids]
    n = len(scored_vectors)
    n_excluded_infra = n_total - n
    n_answerable = sum(1 for v in scored_vectors if v.answerable)
    n_unanswerable = n - n_answerable

    def rate(count: int, denom: int) -> float | None:
        return (count / denom) if denom else None

    costs = [v.cost_usd for v in scored_vectors if v.cost_usd is not None]
    latencies = [v.latency_s for v in scored_vectors]
    briers = [v.brier for v in scored_vectors if v.brier is not None]
    ece_pairs = [(v.probability, v.asserted_correct) for v in scored_vectors
                 if v.probability is not None]
    p_none_flags = [v.p_none_correct for v in scored_vectors if v.p_none_correct is not None]

    tier_mix: Counter[str] = Counter()
    for v in scored_vectors:
        tier_mix.update(v.model_tier_mix)

    rubric_means: dict[str, float | None] = {}
    for dim in ("faithfulness", "completeness", "citation_fidelity"):
        vals = [getattr(v, dim) for v in scored_vectors if getattr(v, dim) is not None]
        rubric_means[dim] = (sum(vals) / len(vals)) if vals else None

    # run_eval.synthesis_rates' shape (task dispatch §7): only over JUDGED rows — its
    # denominators are the judged population, honestly None/0 under --no-judge. Infra
    # rows are never judged (`_judge_arm` skips them via `j.get("judged")`), so this was
    # already scored-only; kept explicit here for the same reason as everything else.
    sr_rows = [
        {"answerable": v.answerable, "declined": v.declined,
         "synthesis_pass": j["synthesis_pass"], "hallucinated": j["hallucinated"],
         "abstained_correctly": j["abstained_correctly"]}
        for v, j in scored_pairs if j.get("judged")
    ]

    return {
        "arm": arm, "n": n, "n_total": n_total, "n_excluded_infra": n_excluded_infra,
        "n_answerable": n_answerable, "n_unanswerable": n_unanswerable,
        "n_ok": n_ok, "n_error": n_error, "n_timeout": n_timeout,
        "n_judged": sum(1 for j in judged if j.get("judged")),
        "correct": sum(1 for v in scored_vectors if v.bucket == "CORRECT"),
        "correct_rate": rate(sum(1 for v in scored_vectors if v.bucket == "CORRECT"), n),
        "confident_wrong": sum(1 for v in scored_vectors if v.bucket == "CONFIDENT_WRONG"),
        "confident_wrong_rate": rate(
            sum(1 for v in scored_vectors if v.bucket == "CONFIDENT_WRONG"), n),
        "scoped": sum(1 for v in scored_vectors if v.bucket == "SCOPED"),
        "declined": sum(1 for v in scored_vectors if v.declined),
        "declined_rate": rate(sum(1 for v in scored_vectors if v.declined), n),
        "correct_abstention": sum(1 for v in scored_vectors if v.correct_abstention),
        "correct_abstention_rate": rate(
            sum(1 for v in scored_vectors if v.correct_abstention), n_unanswerable),
        "over_abstention": sum(1 for v in scored_vectors if v.over_abstention),
        "over_abstention_rate": rate(
            sum(1 for v in scored_vectors if v.over_abstention), n_answerable),
        "recall_at_k": rate(
            sum(1 for v in scored_vectors if v.answerable and v.gold_in_topk), n_answerable),
        "cost": {
            "total_usd": sum(costs) if costs else None,
            "mean_usd": (sum(costs) / len(costs)) if costs else None,
            "n_priced": len(costs),
            "status_counts": dict(Counter(v.cost_status for v in scored_vectors)),
        },
        "latency_s": {
            "p50": _percentile(latencies, 0.50), "p95": _percentile(latencies, 0.95),
            "mean": (sum(latencies) / len(latencies)) if latencies else None,
        },
        "calibration": {
            "brier_mean": (sum(briers) / len(briers)) if briers else None,
            "n_scored": len(briers),
            "ece": OUT.ece(ece_pairs),
            "p_none_accuracy": rate(sum(1 for f in p_none_flags if f), len(p_none_flags)),
        },
        "model_tier_mix": dict(tier_mix),
        "rubric_means": rubric_means,
        "synthesis_rates": synthesis_rates(sr_rows),
    }


def _fmt_pct(x: float | None) -> str:
    return "—" if x is None else f"{x:.0%}"


def _fmt_num(x: float | None, nd: int = 3) -> str:
    return "—" if x is None else f"{x:.{nd}f}"


def _summary_md(run_id: str, summaries: dict[str, dict[str, Any]]) -> str:
    lines = [
        f"# fair-fight summary — {run_id}", "",
        # CRITICAL-2: `n` is the SCORED population (status="ok" only — REC.scored);
        # `excluded` names how many status != "ok" (infra failure) rows never reached any
        # rate below, of `n_total` answered — so a reader can't mistake a 0% CW rate on a
        # 2-row scored population for a clean 20-question run.
        "| arm | n (scored) | excluded (infra) | n_total | correct | CW | declined | "
        "recall@k | grounded | halluc. | cost($) | cost status | p50 lat(s) | brier | "
        "ece | P(NONE) acc |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for arm, s in summaries.items():
        sr = s["synthesis_rates"]
        lines.append(
            f"| {arm} | {s['n']} | {s['n_excluded_infra']} | {s['n_total']} | "
            f"{_fmt_pct(s['correct_rate'])} | {s['confident_wrong']} | "
            f"{_fmt_pct(s['declined_rate'])} | {_fmt_pct(s['recall_at_k'])} | "
            f"{_fmt_pct(sr.get('grounded_rate'))} | {_fmt_pct(sr.get('hallucination_rate'))} | "
            f"{_fmt_num(s['cost']['total_usd'], 4)} | {s['cost']['status_counts']} | "
            f"{_fmt_num(s['latency_s']['p50'], 2)} | {_fmt_num(s['calibration']['brier_mean'])} | "
            f"{_fmt_num(s['calibration']['ece'])} | "
            f"{_fmt_pct(s['calibration']['p_none_accuracy'])} |"
        )
    # PR-21 MINOR: recall@k is NOT one metric across arm classes — name the denominator
    # difference so the column isn't read as apples-to-apples.
    lines += [
        "",
        "_recall@k legend: for the in-process arms (baseline/inprocess/synthesis) recall@k "
        "= gold present in the k-card retrieval set; for the external arms "
        "(competitor/oracle) it = gold present in the UNION of that arm's own tool-call "
        "results (a different, self-chosen retrieval surface, not the same k cards) — the "
        "two are not directly comparable._",
    ]
    return "\n".join(lines) + "\n"


# --- CLI + the injectable core ---------------------------------------------------------


def _parse_arms(raw: str) -> list[str]:
    arms = [a.strip() for a in raw.split(",") if a.strip()]
    if not arms:
        raise SystemExit("--arms must name at least one arm")
    unknown = [a for a in arms if a not in REC.ARMS]
    if unknown:
        raise SystemExit(f"unknown arm(s) {unknown!r} — declared: {sorted(REC.ARMS)}")
    return arms


def default_conn_factory(db_path: Path) -> Any:
    """The ONE production connection factory — ``read_only=True`` always: a RW handle
    would lock out the competitor's own ``pkm serve`` (which opens read-only)."""
    conn = duckdb.connect(str(db_path), read_only=True)
    conn.execute("INSTALL fts; LOAD fts;")
    return conn


def default_arm_impls(args: argparse.Namespace) -> dict[str, Callable[[dict[str, Any]], Any]]:
    """The real per-arm callables, closed over ``--k``/``path`` — every one takes just
    ``(q)``, the uniform shape :func:`_run_arm` (and a test's injected replacements) use."""
    fresh = bool(getattr(args, "fresh", False))
    return {
        "baseline": lambda q: AB.answer_baseline(q, args.k, path="executor"),
        "inprocess": lambda q: AB.answer_baseline(q, args.k, path="inprocess", fresh=fresh),
        "synthesis": lambda q: AS.answer_synthesis(q, args.k, fresh=fresh),
    }


def run(
    args: argparse.Namespace, *,
    arm_impls: dict[str, Callable[[dict[str, Any]], Any]] | None = None,
    judge_impl: Callable[..., dict[str, Any]] | None = None,
    conn_factory: Callable[[Path], Any] | None = None,
) -> dict[str, Any]:
    """The runner's core, thin-``main``-friendly: everything ``main()`` needs is one call.
    ``arm_impls``/``judge_impl``/``conn_factory`` are test seams — when omitted, the real
    entrypoints run. See the module docstring for the write-ordering / redirect
    resolutions this function implements."""
    import yaml

    arms = _parse_arms(args.arms)
    hermes_bin: str | None = None
    hermes_arms = sorted(REC.HERMES_ARMS & set(arms))
    if hermes_arms:
        hermes_bin = args.hermes_bin or shutil.which("hermes")
        if not hermes_bin:
            raise SystemExit(
                f"the {'/'.join(hermes_arms)} arm(s) need a hermes binary: pass "
                "--hermes-bin or put 'hermes' on PATH (never hardcoded — see the CLI's "
                "own --hermes-bin help)")
    claude_bin: str | None = None
    if "deliberative" in arms:
        claude_bin = getattr(args, "claude_bin", None) or shutil.which("claude")
        if not claude_bin:
            raise SystemExit(
                "the deliberative arm needs the claude CLI: pass --claude-bin or put "
                "'claude' on PATH")

    kb_root = _kb_root()
    run_id = args.run_id or f"ff-{datetime.now(UTC):%Y%m%dT%H%M%SZ}"
    run_dir = kb_root / "eval" / "fairfight" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)  # nothing created above this point on a bad CLI arg

    # --questions selects an alternate corpus (e.g. the factory's questions_v2.yaml);
    # getattr tolerance for bare Namespaces mirrors the fresh flag. The SAME resolved
    # path feeds both load_questions and the run_meta sha256 pin — they must never
    # diverge (the pin is the run's provenance).
    questions_arg = getattr(args, "questions", None)
    questions_path = (Path(questions_arg).expanduser() if questions_arg
                      else kb_root / "eval" / "questions.yaml")
    questions = load_questions(questions_path)
    if args.limit is not None:
        questions = questions[: args.limit]

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    db_path = Path(cfg["root_dir"]).expanduser() / "catalogue.duckdb"
    conn = (conn_factory or default_conn_factory)(db_path)

    try:
        meta = _build_run_meta(
            run_id=run_id, args=args, arms=arms, questions_path=questions_path,
            conn=conn, hermes_bin=hermes_bin, claude_bin=claude_bin)
        _write_json(run_dir / "run_meta.json", meta)  # FIRST — before any arm runs
        (run_dir / "questions.sha256").write_text(meta["questions_sha256"] + "\n",
                                                    encoding="utf-8")

        judge_fn = judge_impl or J.judge_modal
        impls = dict(default_arm_impls(args))
        def _bind_external(cfg: AH.HermesArmConfig) -> Callable[[dict[str, Any]], Any]:
            # binds THIS iteration's cfg via the function parameter — a bare loop-body
            # closure over the loop variable would late-bind every external arm to the
            # last iteration's config.
            return lambda q: AH.answer_competitor(q, cfg)

        def _bind_deliberative(cfg: AC.ClaudeArmConfig) -> Callable[[dict[str, Any]], Any]:
            # typed binder, not a default-arg lambda — mypy cannot infer those (the
            # PR-26 CI lesson)
            return lambda q: AC.answer_deliberative(q, cfg)

        for ext in hermes_arms:
            assert hermes_bin is not None
            model, provider, base_url = _external_model_args(args, ext)
            impls[ext] = _bind_external(AH.HermesArmConfig(
                hermes_bin=hermes_bin, run_dir=run_dir, pkm_config=args.config,
                model=model, provider=provider, base_url=base_url,
                timeout_s=args.timeout_s, arm_name=ext,
            ))
        if "deliberative" in arms:
            assert claude_bin is not None
            delib_cfg = AC.ClaudeArmConfig(
                claude_bin=claude_bin, run_dir=run_dir, pkm_config=args.config,
                model=getattr(args, "deliberative_model", AC.ClaudeArmConfig.model),
                timeout_s=int(getattr(args, "deliberative_timeout_s",
                                      AC.ClaudeArmConfig.timeout_s)),
            )
            impls["deliberative"] = _bind_deliberative(delib_cfg)
        if arm_impls:
            impls.update(arm_impls)

        summaries: dict[str, dict[str, Any]] = {}
        with _redirect_decisions_log(run_dir):
            for arm in arms:
                rows = _run_arm(arm, questions, run_dir=run_dir, conn=conn, k=args.k,
                                arm_fn=impls[arm])
                judged = _judge_arm(arm, rows, run_dir=run_dir, judge_fn=judge_fn,
                                    judge_n=meta["judge_n"], no_judge=args.no_judge)
                vectors = _assemble_vectors(run_id, arm, rows, judged)
                _write_vectors(run_dir, arm, vectors)
                summaries[arm] = _summarize_arm(arm, vectors, judged)

        _write_json(run_dir / "judge" / "judge_meta.json", {
            "judge_model": meta["judge_model"], "judge_n": meta["judge_n"],
            "rubric_path": meta["rubric_path"], "rubric_sha256": meta["rubric_sha256"],
            "no_judge": bool(args.no_judge),
        })
        summary = {"format_version": FORMAT_VERSION, "run_id": run_id, "arms": summaries}
        _write_json(run_dir / "summary.json", summary)
        (run_dir / "summary.md").write_text(_summary_md(run_id, summaries), encoding="utf-8")
    finally:
        conn.close()

    return {"run_id": run_id, "run_dir": run_dir, "summaries": summaries}


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default=os.environ.get(
            "PKM_CONFIG", str(Path("~/.config/life-agent/pkm.yaml").expanduser())),
        help="pkm config.yaml (default: $PKM_CONFIG or ~/.config/life-agent/pkm.yaml)")
    parser.add_argument("--k", type=int, default=20, help="top-k per question")
    parser.add_argument(
        "--arms", default="baseline,inprocess,synthesis,competitor",
        help="comma list of arms to run (subset of baseline,inprocess,synthesis,"
             "competitor,oracle,deliberative; `oracle` — the FRONTIER BASELINE — and "
             "`deliberative` — the actual reference policy π* (claude -p, roadmap A1b) "
             "— are opt-in, never in the default set)")
    parser.add_argument("--competitor-model", default="claude-sonnet-4-6")
    parser.add_argument("--competitor-provider", default="anthropic")
    parser.add_argument("--competitor-base-url", default=None)
    parser.add_argument(
        "--oracle-model", default="claude-opus-4-8",
        help="the oracle (reference policy) arm's model — frontier by default; the arm "
             "shares the competitor's driver, prompt, and pkm-MCP toolset")
    parser.add_argument("--oracle-provider", default="anthropic")
    parser.add_argument("--oracle-base-url", default=None)
    parser.add_argument(
        "--hermes-bin", default=None,
        help="path to the hermes CLI (default: 'hermes' resolved off $PATH; required if "
             "unresolved and the competitor arm is selected — never a hardcoded path)")
    parser.add_argument(
        "--claude-bin", default=None,
        help="path to the claude CLI for the deliberative arm (default: 'claude' "
             "resolved off $PATH; required if unresolved and deliberative is selected)")
    parser.add_argument(
        "--deliberative-model", default="claude-opus-4-8",
        help="the deliberative (π*) arm's model — the claude CLI's --model value")
    parser.add_argument(
        "--deliberative-timeout-s", type=int, default=600,
        help="per-question wall clock for the deliberative arm (deliberation is slower "
             "than a oneshot by design; separate from --timeout-s)")
    parser.add_argument("--timeout-s", type=int, default=300)
    parser.add_argument("--limit", type=int, default=None, help="cap the question count")
    parser.add_argument(
        "--questions", default=None,
        help="alternate question corpus (e.g. $LIFE_AGENT_KB/eval/questions_v2.yaml — "
             "the factory output); default: $LIFE_AGENT_KB/eval/questions.yaml. The "
             "run_meta questions_path/sha256 pin follows whichever file is used.")
    parser.add_argument("--no-judge", action="store_true", help="skip the LLM judge entirely")
    parser.add_argument(
        "--fresh", action="store_true",
        help="bust the derivation cache for the in-process arms (inprocess/synthesis) via "
             "ask.answer(..., no_cache=True), so a warm cache can't mute the $ headline "
             "(zero model calls -> cost_status=unavailable). No effect on the baseline "
             "(executor) arm: ask.answer_via_executor has no cache knob (its cache is "
             "server-side).")
    parser.add_argument("--run-id", default=None, help="default: ff-<UTC timestamp>")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    result = run(args)
    print(f"fair-fight run {result['run_id']} -> {result['run_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
