#!/usr/bin/env python3
"""ask — the dogfood "ask anything" REPL over the LIVE pkm catalogue, with citations.

Phase-1 dogfood interface. One command -> an `ask> ` loop that, per question:
retrieves top-k chunks from the whole live corpus (BM25 FTS, Hebrew-aware), has the
pinned answer model synthesise a concise answer that cites [n] into those chunks, then
captures a one-key good/bad verdict into a dated session log under
$LIFE_AGENT_KB. The captured misses are the FAILURES-driven spec for what to build next.

This is pure composition of the comparison harness: it is `phase1_answer.answer_one`
minus the frozen-snapshot filter (dogfood asks over the whole corpus, not a pinned S)
and minus the per-question hand-written search_queries (the raw question IS the query —
an honest "ask anything" test that surfaces retrieval gaps as signal).

Run (from the repo root, for pkm.retrieval + duckdb). One-shot argv is the SAME line
grammar as the REPL (docs/interaction-contract.md):
    bin/ask-live                                   # interactive REPL
    bin/ask-live "what is my ID?"                  # answer once, prompt for a verdict
    bin/ask-live "/since 2026-01-01 what invoices?"  # temporal predicate, same grammar
    bin/ask-live "/tell My name is …"              # record an authoritative owner fact
    bin/ask-live --k 12 "what is my ID?"           # wider retrieval context
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import logging
import os
import readline  # noqa: F401  -- enables line editing / history at the input() prompts
import sys
import urllib.request
from dataclasses import dataclass
from datetime import date as _date
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import citation_guard as guard  # sibling script: deterministic citation-faithfulness gate
import duckdb
import yaml

# Shared infra (metered LLM call, secret lookup, source rendering, the resolved KB /
# PKM_CONFIG paths) lives in the installed life_agent package (see life-agent's pyproject).
import life_agent.core as C
import life_agent.core.ask_client as AC
import life_agent.core.decisions as DEC
import life_agent.core.derivations as D
import life_agent.core.executor as EX
import life_agent.core.outcomes as O
import life_agent.core.reactions as R
import life_agent.owner as owner
import life_agent.tasks.events as ev
import life_agent.tasks.knowledge as knowledge
from life_agent.core import terminals as TERM

# The in-process family orchestration was ABSORBED into the package at M5 (r15,
# design §2.2/§2.3): life_agent.core.terminals is the terminals-only regime's body,
# reached by the one driver's down-branch and by this REPL. The bindings below keep
# this script's public names stable for the instrument arms and their tests; the
# canonical home of the state seams (*_LAST) is TERM.
from life_agent.core.retrieval import build_query  # noqa: F401 — probe-script surface

answer = TERM.answer
connect = TERM.connect
retrieve = TERM.retrieve
_retrieve_set = TERM._retrieve_set
_pkm_root = TERM._pkm_root
_is_lock_error = TERM._is_lock_error
_cards_from_set = TERM._cards_from_set
_narrative_scored = TERM._narrative_scored
_clean_terms = TERM._clean_terms
_expand_terms = TERM._expand_terms
_rerank_hits = TERM._rerank_hits
_corpus_digest = TERM._corpus_digest
EXPAND_SYSTEM = TERM.EXPAND_SYSTEM
EXPAND_MODEL = TERM.EXPAND_MODEL
RERANK_MODEL = TERM.RERANK_MODEL
RERANK_POOL = TERM.RERANK_POOL
RERANK_SYSTEM = TERM.RERANK_SYSTEM
ANSWER_SYSTEM = TERM.ANSWER_SYSTEM
TemporalReport = TERM.TemporalReport
owner_question = TERM.owner_question
reset_cache_stats = TERM.reset_cache_stats
cache_stats = TERM.cache_stats
temporal_footer = TERM.temporal_footer
subject_footer = TERM.subject_footer
INTENT_FOOTER = TERM.INTENT_FOOTER

DEFAULT_K = 8  # matches phase1_answer.py's synthesis-context default

# The synthesis path's frozen decline string. HISTORICAL since M5 (r15): B-4's
# weak-retrieval pre-emption died (S-1 split — weakness is belief, the ranking
# withholds by EU), so nothing PRODUCES this text any more; it stays because the
# graders (scripts/fairfight/grading.py, scripts/run_eval.py) classify RECORDED
# answers by exact match against it, and the records are append-only.
ABSTENTION = (
    "I don't have a strong enough source in your corpus to answer that confidently — retrieval "
    "surfaced nothing above the relevance floor. I'd rather say so than guess; the weak matches "
    "below are shown only so you can see what was near."
)

# Query expansion: a cheap model rewrites the natural-language question into concrete
# BM25 keywords. The dogfood loop showed FTS fails on vocabulary mismatch — "how do i
# make money" / "what is my employment status" miss the answer doc that "am i a
# contractor?" finds, because only the last shares surface words with the document.
# Expansion bridges the question's words to the documents' words. Light reasoning, so a
# cheap model (Haiku); synthesis stays on the pinned ANSWER_MODEL.
# Query expansion now lives in core (`life_agent.core.expansion`) so the answer-brain bridge
# and this
# REPL share ONE expander + ONE cache. These aliases keep ask.py's surface (and its cache key — the
# prompt template is byte-identical) unchanged; `_expand_terms` below stays the script-side wrapper.



# The ONE line grammar (docs/interaction-contract.md): identical in the REPL and in
# one-shot argv. Each entry is (form, meaning, example); the example is parsed by the
# drift-gate test, so an entry the parser stops accepting fails CI, not the owner.
GRAMMAR: tuple[tuple[str, str, str], ...] = (
    ("QUESTION", "cited answer over the live corpus",
     "what is my ID?"),
    ("/recent QUESTION", "rank dated sources newest-first (ranks only; excludes nothing)",
     "/recent any invoices?"),
    ("/since YYYY-MM-DD QUESTION", "only sources dated on/after (excluded are named)",
     "/since 2026-05-01 appointments"),
    ("/until YYYY-MM-DD QUESTION", "only sources dated on/before "
                                   "(combine with /since for a range)",
     "/until 2026-06-01 appointments"),
    ("/tell FACT", "record an authoritative owner fact",
     "/tell My name is Ada Lovelace"),
    ("/derive", "materialise the projections (doc_date, doc_subject) the last "
                 "answer named as underived",
     "/derive"),
    ("/react ID g|b", "verdict a past answer by its decision-id — a deferred "
                      "dogfood verdict (only abstain verdicts move the fold)",
     "/react 8af95b2f bad"),
    ("/q", "quit (also /quit, /exit, Ctrl-D)",
     "/q"),
)


def grammar_text() -> str:
    """Pure: the grammar table rendered for humans — the REPL banner, every usage
    error, and the --help epilog all print THIS, so they cannot disagree."""
    width = max(len(form) for form, _, _ in GRAMMAR)
    return "\n".join(f"  {form.ljust(width)}  {meaning}" for form, meaning, _ in GRAMMAR)


@dataclass(frozen=True)
class Parsed:
    """One parsed input line. ``kind`` dispatches; the rest is that kind's payload."""
    kind: str  # "ask" | "tell" | "derive" | "react" | "quit" | "empty" | "error"
    question: str = ""
    fact: str = ""
    since: _date | None = None
    until: _date | None = None
    recent: bool = False
    did: str = ""       # /react: the decision-id prefix to verdict
    valence: str = ""   # /react: the canonical verdict ("good" | "bad")
    error: str = ""


# /react takes a single bit — the same one-key verdict as the inline prompt, or its
# spelled-out form, normalised to the reactions.VALENCES vocabulary. No free text: the only
# expensive resource in the loop is the owner's prose, so we elicit only the bit.
_VALENCE_ALIASES: dict[str, str] = {"g": "good", "good": "good", "b": "bad", "bad": "bad"}


def _error(message: str) -> Parsed:
    return Parsed(kind="error", error=f"{message}\nthe grammar:\n{grammar_text()}")


def parse_line(line: str) -> Parsed:
    """Pure: parse one input line under the contract's composition rules.
    /since and /until are bounds (a range, each at most once); /recent is a ranking
    directive and stands alone (a bound already ranks newest-first — see
    life_agent.core.temporal.apply_temporal). Anything ambiguous or unknown is a
    loud ``error`` naming the rule — never silently reinterpreted (invariant 3)."""
    line = line.strip()
    if not line:
        return Parsed(kind="empty")
    if line in ("/q", "/quit", "/exit"):
        return Parsed(kind="quit")
    if line == "/derive":
        return Parsed(kind="derive")
    if line == "/tell" or line.startswith("/tell "):
        fact = line[len("/tell"):].strip()
        return Parsed(kind="tell", fact=fact) if fact else _error("usage: /tell FACT")
    if line == "/react" or line.startswith("/react "):
        parts = line[len("/react"):].strip().split()
        if len(parts) != 2:
            return _error("usage: /react DECISION_ID g|b")
        valence = _VALENCE_ALIASES.get(parts[1].lower())
        if valence is None:
            return _error(f"usage: /react DECISION_ID g|b "
                          f"(verdict must be g/b, got {parts[1]!r})")
        return Parsed(kind="react", did=parts[0], valence=valence)
    if not line.startswith("/"):
        return Parsed(kind="ask", question=line)

    tokens = line.split()
    since: _date | None = None
    until: _date | None = None
    recent = False
    i = 0
    while i < len(tokens) and tokens[i].startswith("/"):
        t = tokens[i]
        if t == "/recent":
            if recent:
                return _error("/recent may appear only once")
            recent = True
            i += 1
        elif t in ("/since", "/until"):
            if (t == "/since" and since) or (t == "/until" and until):
                return _error(f"{t} may appear only once — bounds form one range")
            if i + 1 >= len(tokens):
                return _error(f"usage: {t} YYYY-MM-DD QUESTION")
            try:
                bound = _date.fromisoformat(tokens[i + 1])
            except ValueError:
                return _error(f"usage: {t} YYYY-MM-DD QUESTION (got {tokens[i + 1]!r})")
            if t == "/since":
                since = bound
            else:
                until = bound
            i += 2
        else:
            return _error(f"unknown command {t!r}")
    if recent and (since or until):
        return _error("/recent with a bound is redundant — /since and /until already "
                      "rank newest-first; drop /recent")
    if since and until and since > until:
        return _error(f"empty range: /since {since} is after /until {until}")
    question = " ".join(tokens[i:])
    if not question:
        return _error("missing QUESTION after the temporal prefix")
    return Parsed(kind="ask", question=question, since=since, until=until, recent=recent)




# --- the executor read-path (--executor): the daemon decides, the body enacts --------- #
# PRINCIPLES §16/§4: drive the question through the credence answer-brain daemon's VOI schedule
# (core.executor) over the capability bridge, render the decision in the SAME credence grammar the
# in-process lookup family uses, and log the terminal lookup decision to the calibration log so the
# owner's g/b verdict folds into u(wrong) through the EXISTING reaction loop (the bridge's
# /log_decision owns the write, shaping it as the lookup family's own; the in-session verdict binds
# to its content-addressed id). Flag-gated; the default path is untouched.
EXECUTOR_BRIDGE = os.environ.get("LIFE_AGENT_BRIDGE_URL", "http://127.0.0.1:8798")
EXECUTOR_DAEMON = os.environ.get("ANSWER_BRAIN_URL", "http://127.0.0.1:8799")
EXECUTOR_DOWN = ("No answer asserted — the executor is unavailable (the answer-brain "
                 "daemon/bridge is not up; start it: bin/answer-brain).")
# the last executor decision's id (the bridge's content-addressed "ab-…") — the in-session g/b
# verdict binds to it (the executor analogue of LOOKUP_LAST.answer_cache_key); None when the last
# answer was a miss / narrative / daemon-down (nothing foldable to bind).
EXECUTOR_LAST: str | None = None
# the last executor decision's own structured View (life_agent.core.executor.View) — held so a
# downstream consumer (e.g. the fair-fight harness's scripts/fairfight/arm_baseline.py) can build
# a real decision_view instead of re-parsing the rendered free text: the rendered string alone
# does not let a consumer recognise the credence grammar's own withholding renderings, so a
# free-text decline detector reads every withholding as an assertion. Reset at the top of
# answer_via_executor like every other "*_LAST" seam; None when the last call never reached a
# decision (daemon down) — never a stale prior question's view.
EXECUTOR_VIEW_LAST: dict[str, Any] | None = None
# when set (the gate's executor arm), logged decisions carry this run_id so in-gate rows are
# distinguishable from live traffic in decisions.jsonl; None (live) posts no run_id and the
# bridge's default ("answer-brain") rules.
EXECUTOR_RUN_ID: str | None = None
# when set (the gate's --gate-loo executor arm), _edge_curves holds this question's own
# graded rows out of the fold — the held-out reading's discipline: a question's decide
# never conditions on evidence derived from itself (in-sample curves = §17.4's leakage
# re-enacted). None (live and run-3-shaped gates) folds the whole log.
EXECUTOR_HOLD_OUT_QUESTION_ID: str | None = None


def _http_post(url: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    # delegates to the ONE transport (ask_client.post_json), which carries the
    # bridge's error body in the raised HTTPError instead of discarding it
    return AC.post_json(url, payload)


def _http_get(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=300) as r:
        return cast("dict[str, Any]", json.loads(r.read()))


def _executor_ready() -> bool:
    """Both services must answer /ready. The body never falls back SILENTLY — a down stack is
    NAMED (interaction contract), never substituted with a different path's answer."""
    for base in (EXECUTOR_BRIDGE, EXECUTOR_DAEMON):
        try:
            urllib.request.urlopen(f"{base}/ready", timeout=3)
        except Exception:
            return False
    return True


def answer_via_executor(question: str, k: int
                        ) -> tuple[str, list[C.SourceCard], dict[int, float]]:
    """Ask's EXECUTOR-LANE SURFACE over the one driver
    (:func:`life_agent.core.ask_client.drive`): route → retrieve → probe → extract →
    /decide, then render in the shared credence grammar. The driver posts the one
    /log_decision body (design §5.1) and, on a down stack, commits the declared gate +
    appends the §6.5 unavailability record; this surface owns ask's concerns — the
    *_LAST globals, cards/scores, and the interaction contract's EXECUTOR_DOWN string —
    and is what run_eval's typed arm calls DIRECTLY (the full dispatch's in-process
    fallback must never silently switch a gate's arm — r13 amendment 4)."""
    global EXECUTOR_LAST, EXECUTOR_VIEW_LAST
    TERM.TEMPORAL_LAST = TERM.SUBJECT_LAST = TERM.INTENT_LAST = None
    TERM.LOOKUP_LAST = TERM.NARRATIVE_LAST = None
    TERM.STAGES_LAST = {}
    EXECUTOR_LAST = None
    EXECUTOR_VIEW_LAST = None
    # The daemon's own retrieve/grow rounds are not observable in the View it returns (and
    # core/executor.py must not be edited to expose them) — absent (not a guessed 0), so a
    # consumer can tell "not tracked here" apart from "zero rounds fired".
    TERM.EFFORT_LAST = {}
    r = AC.drive(question, k, bridge=EXECUTOR_BRIDGE, daemon=EXECUTOR_DAEMON,
                 post=_http_post, get=_http_get, run_id=EXECUTOR_RUN_ID,
                 ready=_executor_ready,
                 hold_out_question_id=EXECUTOR_HOLD_OUT_QUESTION_ID)
    if r.down:
        return (EXECUTOR_DOWN, [], {})
    if r.view is None:
        # the terminals-only regime answered (M5, §2.3): the leaf rendered the text
        # and recorded the decision; cards/scores live in TERM's travel state.
        EXECUTOR_LAST = r.decision_id
        return (r.text or "", [], {})
    view = r.view
    EXECUTOR_VIEW_LAST = view
    EXECUTOR_LAST = r.decision_id
    pairs = _cards_from_set(view["hits"])
    cards = [c for c, _ in pairs]
    scores = {c.n: s for c, s in pairs}
    return (EX.render_view(view), cards, scores)


# --- presentation --------------------------------------------------------- #
def _sources_inline(cards: list[C.SourceCard], scores: dict[int, float]) -> str:
    return ", ".join(f"{Path(c.origin).name}({scores.get(c.n, 0.0):.2f})" for c in cards)


def render(text: str, cards: list[C.SourceCard], scores: dict[int, float],
           audit: guard.CitationAudit | None = None, footer: str = "") -> None:
    print(f"\n{text}\n")
    if cards:
        print("sources:")
        for c in cards:
            print(f"  [{c.n}] {Path(c.origin).name}  ({scores.get(c.n, 0.0):.2f})")
    if footer:
        print(footer)  # temporal partition: nothing vanishes silently (D1)
    if audit is not None and not audit.ok:
        print(audit.footer())  # ⚠ unverified: a cited fact wasn't found in its source
    print()


# --- feedback capture (the dogfood signal) -------------------------------- #
def log_entry(question: str, text: str, cards: list[C.SourceCard],
              scores: dict[int, float], verdict: str, *, when: str,
              unverified: str = "") -> str:
    """Render one dogfood log block. Pure (no I/O, no clock) so it is unit-tested."""
    lines = [
        f"## {when}  {verdict}",
        f"Q: {question}",
        f"A: {text}",
    ]
    if cards:
        lines.append(f"sources: {_sources_inline(cards, scores)}")
    if unverified:  # citation-guard flagged a cited fact not present in its source
        lines.append(f"unverified: {unverified}")
    return "\n".join(lines) + "\n"


def append_log(entry: str) -> Path:
    """Append a block to today's dated dogfood log under $LIFE_AGENT_KB (never the repo).
    Writes the session header once when the file is first created."""
    log = C.KB / "eval" / f"dogfood-{datetime.now():%Y-%m-%d}.md"
    log.parent.mkdir(parents=True, exist_ok=True)
    new = not log.exists()
    with log.open("a", encoding="utf-8") as fh:
        if new:
            fh.write(f"# Dogfood session {datetime.now():%Y-%m-%d}\n\n")
        fh.write(entry + "\n")
    return log


def _unverified_summary(audit: guard.CitationAudit | None) -> str:
    """Compact one-line summary of a citation audit for the dogfood log ('' when clean)."""
    if audit is None or audit.ok:
        return ""
    parts = [f"[{n}] {claim}" for claim, n in audit.unsupported]
    if audit.dangling:
        parts.append("dangling " + ",".join(f"[{n}]" for n in audit.dangling))
    return "; ".join(parts)


def capture(question: str, text: str, cards: list[C.SourceCard], scores: dict[int, float],
            audit: guard.CitationAudit | None = None) -> None:
    """One-key good/bad verdict — a single bit, no free text (the only expensive resource in
    the loop is the owner's prose). Frictionless: `g`/`b` logs immediately; Enter skips. A
    citation-guard flag is logged regardless of verdict."""
    try:
        choice = input("[g]ood / [b]ad / Enter=next > ").strip().lower()
    except EOFError:
        print()
        return
    verdict = {"g": "GOOD", "b": "BAD"}.get(choice)
    if not verdict:
        return
    log = append_log(log_entry(question, text, cards, scores, verdict,
                               when=f"{datetime.now():%H:%M}",
                               unverified=_unverified_summary(audit)))
    print(f"→ logged {verdict} to {log}\n")
    _record_reaction(question, verdict)


def submit_reaction(event: R.ReactionEvent, *, reactions_path: Path,
                    post: Any = None) -> str:
    """Record ONE owner verdict — through the bridge's ``/log_reaction`` when it is reachable,
    by appending straight to the reaction log when it is not. Returns which path took it
    (``"bridge"`` / ``"direct"``), and never writes BOTH (the bridge owns the append on its
    own path).

    Why route it at all: ``bridge/server.py``'s ``/log_reaction`` is the ONLY caller of
    ``MembraneShadow.submit_reaction``, so a verdict appended directly here reaches the
    membrane shadow only at the NEXT boot's snapshot replay (`shadow.boot_snapshot`) — late,
    not lost. ask-live is the primary dogfood surface, so its verdicts go through the bridge
    like Jarvis's already do (`core/ask_client.react`), and the shadow's live evidence stream
    is the real one rather than a Jarvis-only sample.

    Fail-open, deliberately: the reaction log is the source of truth for the utility fold —
    a verdict must never be LOST because the bridge is down, misconfigured, or 404s on a
    decision it cannot see. Any bridge failure falls back to the direct append this function
    replaced. The bridge is skipped outright (no pointless round-trip) for an unbound verdict
    (empty ``decision_id`` — nothing for it to look up) and whenever the caller named a
    reaction log OTHER than the production one, since the bridge writes only its own."""
    post = post if post is not None else _http_post
    if event.decision_id and reactions_path == C.REACTIONS_LOG:
        try:
            post(f"{EXECUTOR_BRIDGE}/log_reaction",
                 {"decision_id": event.decision_id, "valence": event.valence})
            return "bridge"
        except Exception:
            pass  # fail-open: fall through to the direct append — never lose a verdict
    R.append(reactions_path, event)
    return "direct"


def _record_reaction(question: str, verdict: str) -> None:
    """§4.4 reaction loop: record the verdict (one bit) as a structured reaction, joined to
    the decision it grades by ``decision_id`` (the answer's cache key). The producer
    (`reactions.load_reactions`) decides what folds — v0 conditions u(wrong) only on clean
    lookup abstain-verdicts; everything else is recorded, not folded. Written through
    :func:`submit_reaction` (bridge-first, so the membrane shadow sees it live). Fail-open
    and named: a calibration-log write must never break the dogfood loop."""
    decision_id = (EXECUTOR_LAST if EXECUTOR_LAST
                   else TERM.LOOKUP_LAST.answer_cache_key if TERM.LOOKUP_LAST is not None
                   else TERM.NARRATIVE_LAST.answer_cache_key
                   if TERM.NARRATIVE_LAST is not None
                   else "")
    try:
        submit_reaction(R.ReactionEvent(
            tx_time=O.now_iso(), question_id=DEC.question_id(question),
            decision_id=decision_id, kind="verdict",
            valence={"GOOD": "good", "BAD": "bad"}[verdict]),
            reactions_path=C.REACTIONS_LOG)
    except Exception as e:  # fail-open by contract, reason printed
        print(f"  (reaction not recorded: {e})")


def react(did_prefix: str, valence: str,
          *, decisions_path: Path = C.DECISIONS_LOG,
          reactions_path: Path = C.REACTIONS_LOG) -> int:
    """Deferred dogfood verdict (interaction-contract `know` mode): bind a verdict the owner
    authors *now* to a decision recorded *earlier*, by content-addressed ``decision_id``
    prefix — no model recompute, so it grades the answer exactly as it stood. The prefix
    resolves git-style: a unique match is required; zero or several is a loud error naming the
    options (invariant 3), never a silent pick. On a match it appends the §4.4 ``ReactionEvent``
    the fold joins, copying the decision's own ``question_id`` for linkage. The verdict is one
    bit — good/bad, no free text (the owner's prose is the loop's only expensive resource).
    Returns 0 on success, 2 on a resolve error. The fold (`reactions.load_reactions`) still
    decides what *moves*: this only records the owner's verdict — a report decision is
    recorded-not-folded, named so here. (The owner authors the bit; this is transcription.)"""
    try:
        decisions = DEC.read(decisions_path)
    except Exception as e:
        print(f"cannot read the decisions log: {e}", file=sys.stderr)
        return 2
    ids = sorted({d.decision_id for d in decisions
                  if d.decision_id and d.decision_id.startswith(did_prefix)})
    if not ids:
        print(f"no decision matches id prefix {did_prefix!r} "
              f"({len(decisions)} decisions on file)", file=sys.stderr)
        return 2
    if len(ids) > 1:
        shown = ", ".join(i[:12] for i in ids[:8])
        print(f"ambiguous id prefix {did_prefix!r} matches {len(ids)} decisions: "
              f"{shown}{' …' if len(ids) > 8 else ''} — give more characters", file=sys.stderr)
        return 2
    did = ids[0]
    d = [dd for dd in decisions if dd.decision_id == did][-1]  # latest row; context shared
    try:
        submit_reaction(R.ReactionEvent(
            tx_time=O.now_iso(), question_id=d.question_id, decision_id=did,
            kind="verdict", valence=valence), reactions_path=reactions_path)
    except Exception as e:
        print(f"verdict not recorded: {e}", file=sys.stderr)
        return 2
    folds = d.chosen_action == "abstain" and valence in ("good", "bad")
    fate = ("folds into the utility posterior on the next gate run" if folds
            else "recorded — not folded (only abstain verdicts move the fold)")
    print(f"→ {valence.upper()} on {d.family}/{d.chosen_action} {did[:12]} — {fate}")
    return 0


# --- one question, end to end --------------------------------------------- #
def ask_once(conn: duckdb.DuckDBPyConnection, question: str, k: int,
             *, expand: bool = True, no_cache: bool = False,
             since: _date | None = None, until: _date | None = None,
             recent: bool = False) -> list[tuple[str, str]]:
    """Answer + render + capture. Returns the derive targets the answer's
    reports named as underived (doc_date and doc_subject alike — empty when
    neither filter ran) so the REPL can offer `/derive`. The credence answer-brain executor
    (the daemon decides) is the DEFAULT read-path; when its daemon/bridge is down it falls back
    to the TERMINALS-ONLY regime inside the driver (M5, §2.3 — the leaves answer over T
    with the regime recorded), NAMED when even that cannot run. The dispatch died at M5
    (B-1/B-5): availability decides, never a flag. Temporal scoping (/since …) is not
    yet wired into the executor, so a scoped question is NAMED and answered unscoped."""
    global EXECUTOR_LAST
    EXECUTOR_LAST = None  # clean per-question state; the dispatched path sets its own id
    if since is not None or until is not None or recent:
        print("  (executor path: temporal scoping not yet wired — answering unscoped)")
    text, cards, scores = answer_via_executor(question, k)
    audit = guard.audit(text, cards)  # pure and cheap — recomputed, never cached
    reports = [r for r in (TERM.TEMPORAL_LAST, TERM.SUBJECT_LAST) if r is not None]
    footer_lines = [r.footer for r in reports if r.footer]
    if TERM.INTENT_LAST is not None:
        footer_lines.append(INTENT_FOOTER.format(scope=TERM.INTENT_LAST))
    render(text, cards, scores, audit, footer="\n".join(footer_lines))
    capture(question, text, cards, scores, audit)
    return [t for r in reports for t in r.targets]


# --- /derive: explicit, demand-driven materialisation ---------------------- #
def run_derive(targets: list[tuple[str, str]]) -> None:
    """Materialise the named projection targets via pkm.derive (SPEC §18.11).
    The CALLER must have closed any read-only catalogue connection first — a
    reader and a writer cannot coexist on the DuckDB file. Fail-open: a held
    lock (an extraction running) prints and returns; nothing crashes the REPL."""
    from pkm.config import load_config as pkm_load_config
    from pkm.derive import derive as pkm_derive

    try:
        cfg = pkm_load_config(C.PKM_CONFIG)
    except Exception as e:
        print(f"derive unavailable (pkm config: {e})")
        return
    for decl, input_key in targets:
        try:
            result = pkm_derive(cfg.root_dir, cfg, decl,
                                input_cache_key=input_key,
                                caller="ask.derive")
        except duckdb.Error as e:
            if TERM._is_lock_error(str(e)):
                print("corpus locked by extraction — try /derive again in a moment")
                return
            print(f"derive failed  {decl}: {e}")
            continue
        except Exception as e:
            print(f"derive failed  {decl}: {e}")
            continue
        if result.status == "success":
            print(f"derived  {decl}  {result.target_cache_key}")
        else:
            print(f"{result.status}  {decl}: "
                  f"{result.error_message or result.approval_id}")


# --- GTD: the act ledger's knowledge projection, refreshed on demand ------- #
# system-design.md §5: before a question is answered, if the GTD ledger has
# moved past its projected state document, re-project and re-ingest it — the
# degenerate (deterministic, near-zero-cost) case of derive-when-stale, so the
# decision is simply "always derive". Nothing silent: the outcome is printed
# from this single-source table (drift-gated in tests/test_ask_gtd_refresh.py).
REFRESH_NOTES: dict[str, str] = {
    "refreshed": "gtd state refreshed @ event {n}",
    "failed": "gtd state refresh failed ({error}) — answering over the corpus as-is",
    "blocked": ("gtd state refresh blocked: {n} recorded derivation(s) still awaiting catalogue "
                "reconciliation — not extracting (an extract sweeps unregistered artefacts); "
                "answering over the corpus as-is"),
}


class _RefreshBlockedError(Exception):
    """The re-ingest refused to extract: registerable derivations are still pending
    reconciliation (SPEC §18.9) and pkm's extract would sweep them (§6.2)."""

    def __init__(self, n: int) -> None:
        super().__init__(n)
        self.n = n


def gtd_stale() -> bool:
    """Cheap staleness check — ledger bytes vs the stamp in the state doc.
    No ledger (GTD unused) is never stale; a missing or unstamped doc is."""
    if not C.TASKS_LEDGER.exists():
        return False
    try:
        sha = hashlib.sha256(C.TASKS_LEDGER.read_bytes()).hexdigest()
        text = C.TASKS_STATE.read_text(encoding="utf-8")
    except (OSError, ValueError):  # unreadable/corrupt (incl. UnicodeDecodeError) = stale
        return True
    return knowledge.parse_stamp(text) != (sha, knowledge.RENDER_VERSION)


def _ensure_declared(root: Path, state: Path) -> None:
    """Idempotently declare the state doc in the pkm manifest (SPEC §8.1)."""
    from pkm.ingest import sources_yaml_path

    manifest = sources_yaml_path(root)
    data: Any = None
    if manifest.exists():
        data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        data = {"version": 1, "sources": []}
    sources = data.setdefault("sources", [])
    declared = str(state)
    if any(isinstance(e, dict) and e.get("path") == declared for e in sources):
        return
    sources.append({"path": declared, "tags": ["gtd", "tasks"]})
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _reingest_state(root: Path, state: Path) -> None:
    """ingest → extract → rebuild-index for the one state document.
    The porcelain order is load-bearing (interaction contract invariant 3:
    a chunk pass whose index is stale silently misses new content)."""
    from pkm.catalogue import open_catalogue
    from pkm.config import load_config as pkm_load_config
    from pkm.extract import extract as pkm_extract
    from pkm.ingest import ingest_sources
    from pkm.retrieval import build_fts_index

    _ensure_declared(root, state)
    ingest_sources(root, only_paths=[state])
    cfg = pkm_load_config(C.PKM_CONFIG)
    prefix = hashlib.sha256(state.read_bytes()).hexdigest()[:16]
    # Reconcile-or-refuse (SPEC §18.9 meets §6.2): the extract's orphan sweep removes every
    # file-complete artefact whose catalogue row lags — the r03 loss. Register what is
    # registerable NOW (the startup reconcile does not cover the REPL's per-question refresh),
    # and if any registerable key is still pending, do not extract: the caller names it,
    # un-stamps the state doc, and the next ask retries.
    D.reconcile(root)
    n_pending = D.pending_registerable(root)
    if n_pending:
        raise _RefreshBlockedError(n_pending)
    pkm_extract(root, cfg, source_prefix=prefix)
    with open_catalogue(root) as wconn:
        build_fts_index(wconn)


def ensure_gtd_fresh() -> None:
    """Project + re-ingest the GTD state when stale; quiet no-op when fresh.
    The CALLER must hold no read-only catalogue connection (a writer and a
    reader cannot coexist — same contract as run_derive). Fail-open: never
    raises; the outcome is printed (REFRESH_NOTES), never silent."""
    if not gtd_stale():
        return
    try:
        events = ev.load(C.TASKS_LEDGER)
        knowledge.write_state(C.TASKS_LEDGER, C.TASKS_STATE)
        root = TERM._pkm_root()
        if root is None:
            raise FileNotFoundError(f"unresolvable pkm root (config: {C.PKM_CONFIG})")
        _reingest_state(root, C.TASKS_STATE)
        print(REFRESH_NOTES["refreshed"].format(n=len(events)))
    except _RefreshBlockedError as e:
        # refused, not failed: un-stamped (the next ask retries after another reconcile),
        # named with the count — never a silent extract over unregistered artefacts
        with contextlib.suppress(OSError):
            C.TASKS_STATE.unlink(missing_ok=True)
        print(REFRESH_NOTES["blocked"].format(n=e.n))
    except Exception as e:  # fail-open by contract (mirror run_derive)
        # The stamp is the freshness oracle and write_state runs BEFORE the
        # re-ingest, so a failure here must un-stamp the doc: a stamped doc
        # whose ingest failed would read as fresh, the retry would never
        # happen, and every answer in the window would silently serve stale
        # catalogue state. Un-stamped, the next question retries and the
        # failure is re-named each time — degraded, never silent.
        with contextlib.suppress(OSError):
            C.TASKS_STATE.unlink(missing_ok=True)
        print(REFRESH_NOTES["failed"].format(error=e))


# --- teaching: opportunistically record an authoritative owner fact ------- #
def remember(fact: str) -> None:
    """Append an owner-told fact ('My name is …') to the owner profile. This is identity
    ground truth, not corpus evidence — it is injected into every future answer, never ingested
    into pkm. Empty facts are ignored."""
    fact = fact.strip()
    if not fact:
        return
    path = owner.append_fact(fact, when=f"{datetime.now():%Y-%m-%d %H:%M}")
    print(f"→ remembered (owner profile: {path})\n")


# --- REPL ----------------------------------------------------------------- #
def repl(conn: duckdb.DuckDBPyConnection, k: int, *, expand: bool = True,
         no_cache: bool = False) -> None:
    print(f"ask anything about your life — the grammar:\n{grammar_text()}\n")
    derive_targets: list[tuple[str, str]] = []
    while True:
        try:
            line = input("ask> ")
        except EOFError:
            print()
            return
        p = parse_line(line)
        if p.kind == "empty":
            continue
        if p.kind == "quit":
            return
        if p.kind == "error":
            print(f"{p.error}\n")
            continue
        if p.kind == "tell":
            remember(p.fact)
            continue
        if p.kind == "react":
            react(p.did, p.valence)
            continue
        if p.kind == "derive":
            if not derive_targets:
                print("nothing to derive — ask a /recent or /since question first\n")
                continue
            # A reader and a writer cannot coexist (§18.9): close, write, reopen.
            conn.close()
            try:
                run_derive(derive_targets)
                derive_targets = []
            finally:
                try:
                    conn = connect()
                except duckdb.Error as e:
                    # An extraction grabbed the catalogue mid-derive: close with
                    # the named error (invariant 3), never a traceback.
                    if not TERM._is_lock_error(str(e)):
                        raise
                    print("corpus locked by extraction — REPL closing; "
                          "rerun bin/ask-live in a moment")
                    return
            print()
            continue
        assert p.kind == "ask", p.kind  # parse_line's kind space is closed
        if gtd_stale():
            # Same reader/writer dance as /derive: close, refresh, reopen.
            conn.close()
            try:
                ensure_gtd_fresh()
            finally:
                try:
                    conn = connect()
                except duckdb.Error as e:
                    if not TERM._is_lock_error(str(e)):
                        raise
                    print("corpus locked by extraction — REPL closing; "
                          "rerun bin/ask-live in a moment")
                    return
        derive_targets = ask_once(conn, p.question, k, expand=expand,
                                  no_cache=no_cache, since=p.since,
                                  until=p.until, recent=p.recent)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog=f"the line grammar (REPL and one-shot):\n"
                                        f"{grammar_text()}")
    ap.add_argument("question", nargs="*",
                    help="one line in the grammar below; omit for the REPL")
    ap.add_argument("--k", type=int, default=DEFAULT_K,
                    help=f"top-k retrieval context (default {DEFAULT_K})")
    ap.add_argument("--no-expand", action="store_true",
                    help="disable cheap-model query expansion (raw-question BM25 baseline)")
    ap.add_argument("--no-cache", action="store_true",
                    help="recompute every stage instead of replaying cached derivations "
                         "(recording stays write-once — existing derivations stand)")
    args = ap.parse_args(argv)
    expand = not args.no_expand

    # One-shot argv is the SAME grammar as a REPL line (invariant 1). The corpus-free
    # kinds are handled BEFORE any catalogue I/O: /tell works even while an extraction
    # holds the lock; a grammar error never costs a connection.
    p = parse_line(" ".join(args.question)) if args.question else None
    if p is not None and p.kind == "empty":
        p = None  # a blank argv question means the REPL, same as no question
    if p is not None:
        if p.kind == "error":
            print(p.error, file=sys.stderr)
            return 2
        if p.kind == "derive":
            print("/derive needs the targets a prior answer named — REPL only",
                  file=sys.stderr)
            return 2
        if p.kind == "tell":
            remember(p.fact)
            return 0
        if p.kind == "react":
            return react(p.did, p.valence)
        if p.kind == "quit":
            return 0

    # Opportunistic catalogue reconciliation (SPEC §18.9): insert the rows for any
    # file-first derivations recorded by earlier sessions, BEFORE our read-only connection
    # opens (a writer and a reader cannot coexist). A held lock just means next time.
    root = TERM._pkm_root()
    if root is not None:
        # best-effort by contract; on any failure the files stay authoritative — but a failure
        # of the pass itself is never silent (reconcile counts and WARNs per key; r00 Q2)
        try:
            D.reconcile(root)
        except Exception as e:
            logging.getLogger("ask").warning(
                "startup reconcile pass failed (%s) — files stay authoritative; retried next ask",
                type(e).__name__)

    # Demand-led GTD refresh (system-design.md §5), BEFORE the read-only
    # connection opens: a one-shot question and the REPL's first question both
    # see fresh act-layer state. Mid-REPL changes are caught per-question.
    ensure_gtd_fresh()

    try:
        conn = connect()
    except duckdb.Error as e:
        if TERM._is_lock_error(str(e)):
            print("corpus locked by extraction, retry in a moment", file=sys.stderr)
            return 2
        raise

    if p is not None:
        ask_once(conn, p.question, args.k, expand=expand,
                 no_cache=args.no_cache, since=p.since, until=p.until,
                 recent=p.recent)
    else:
        repl(conn, args.k, expand=expand, no_cache=args.no_cache)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
