"""The drivers — ONE code path per trace, run either recording or replaying.

Record and replay differ only in which taps the :class:`Rig` carries: recording taps pass
through to the live seam and capture; replaying taps serve the capture and refuse anything
the record never saw. Sharing the driver is the point — a recorder and a replayer written
twice would drift, and a bisection oracle that drifts from the thing it oracles is worse
than none.

**Nothing here is on the decision path.** The drivers install their taps at module seams
that the decision path itself never rebinds (the §18.9 cache read, the process-shared skin,
the KB fold-input paths) and restore them on exit. `tests/test_collapse_record.py` drift-gates
the one seam that is not a parameter — :func:`life_agent.core.lookup.set_shared_brain`.

**The KB snapshot.** The utility fold, the extractor's reliability and the narrative cells
are folds over KB logs that grow with every run. A fixture that read them live would decay
into unreplayability within a day, so a checkpoint snapshots them once and every replay
folds over the snapshot — which also puts the fold itself under the comparator (what M3
moves).
"""
from __future__ import annotations

import contextlib
import dataclasses
import hashlib
import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from life_agent.collapse import fixture as FX
from life_agent.core import config as CFG
from life_agent.core import decisions as DEC
from life_agent.core import derivations as D
from life_agent.core import executor as EX
from life_agent.core import lookup as LK

# The KB logs a fold reads. Snapshotted per checkpoint; `decisions` and `reactions` are the
# reaction loop's inputs (utility.py §4.4), `outcomes` the extractor/cell folds', and the two
# utility files the model + elicitations.
SNAPSHOT_FILES: tuple[tuple[str, str], ...] = (
    ("utility_model", "utility/model.yaml"),
    ("utility_elicitations", "utility/elicitations.jsonl"),
    ("reactions", "calibration/reactions.jsonl"),
    ("decisions", "calibration/decisions.jsonl"),
    ("outcomes", "calibration/outcomes.jsonl"),
)


@dataclass(frozen=True)
class KBSnapshot:
    """The fold inputs a checkpoint pins, and the staging log every writer is pointed at."""

    directory: Path

    def path(self, name: str) -> Path:
        return self.directory / f"{name}.snapshot"

    def sha(self, name: str) -> str | None:
        p = self.path(name)
        return hashlib.sha256(p.read_bytes()).hexdigest()[:16] if p.exists() else None

    @property
    def staging(self) -> Path:
        return self.directory / "staging"

    def provenance(self) -> dict[str, Any]:
        return {name: self.sha(name) for name, _ in SNAPSHOT_FILES}


def take_snapshot(directory: Path, kb: Path) -> KBSnapshot:
    """Copy the fold inputs beside the fixtures, once per checkpoint. A missing source is
    recorded as absent rather than invented — the fold must see exactly what it saw."""
    directory.mkdir(parents=True, exist_ok=True)
    snap = KBSnapshot(directory)
    for name, rel in SNAPSHOT_FILES:
        src = kb / rel
        if src.exists():
            snap.path(name).write_bytes(src.read_bytes())
    snap.staging.mkdir(parents=True, exist_ok=True)
    return snap


@dataclass
class Rig:
    """The four taps plus the view holder the drivers stash their executor View in."""

    brain: Any
    post: Callable[[str, dict[str, Any]], dict[str, Any] | None]
    get: Callable[[str], dict[str, Any]]
    client: Any
    cache: Callable[[Any, str], bytes | None]
    last_view: dict[str, Any] | None = None


# Every seam that can leave the box. They are bound at IMPORT into their consumers
# (`from life_agent.core.llm import anthropic_complete`), so patching `llm` alone would miss
# them — each binding site is named here. Discovered the hard way at M0: gating only the
# schema-constrained instrument client left `joint_extract` and `/probe/deliberate` free to
# spend, which they did.
_SPEND_SEAMS: tuple[tuple[str, str], ...] = (
    ("life_agent.core.llm", "anthropic_complete"),
    ("life_agent.core.llm", "openai_complete"),
    ("life_agent.core", "anthropic_complete"),
    ("life_agent.core", "openai_complete"),
    ("life_agent.core.joint_extract", "anthropic_complete"),
    ("life_agent.core.rerank", "anthropic_complete"),
    ("life_agent.core.deliberate", "answer"),
)


@contextlib.contextmanager
def sealed(staging_root: Path, *, allow_spend: bool = False) -> Iterator[None]:
    """Seal the three ways a recording could reach past its own boundary.

    **Spend.** Every seam in :data:`_SPEND_SEAMS` raises
    :class:`~life_agent.collapse.taps.WouldSpendError` unless ``allow_spend``: a cold
    derivation becomes a NAMED absence rather than a silent charge on the owner's account.

    **The live pkm root.** ``derivations.record`` is redirected under ``staging_root``, so no
    §18.9 artefact this run computes can land in the live content-addressed cache — including
    the ones the bridge's own handlers write, which take the live root as an argument and
    would otherwise be invisible to any tap on the caller's side.

    **The append-only logs.** ``decisions.append`` and ``outcomes.append`` are redirected to
    sinks under ``staging_root``. Redirecting the *paths* is not enough: several writers take
    no path at all and fall through to ``config`` (the bridge's ``/narrative`` handler is one),
    and a decision appended at the configured path is mirrored onto the owner's unified stream
    by the C5 dual-write. Sinking the append itself is what makes the mirror's own
    "not the configured path" guard fire, and is the only form that covers a writer the
    recorder does not know about.
    """
    import importlib

    from life_agent.collapse.taps import WouldSpendError

    saved: list[tuple[Any, str, Any]] = []

    def _refuse(*a: Any, **kw: Any) -> Any:
        raise WouldSpendError(
            "a cold derivation reached a model seam under the recorder's no-spend seal "
            "(--allow-spend opts in deliberately)")

    if not allow_spend:
        for module_name, attr in _SPEND_SEAMS:
            try:
                mod = importlib.import_module(module_name)
            except Exception:      # pragma: no cover - a module that is not importable
                continue           # cannot be a live seam in this process either
            if hasattr(mod, attr):
                saved.append((mod, attr, getattr(mod, attr)))
                setattr(mod, attr, _refuse)

    staging_root.mkdir(parents=True, exist_ok=True)
    inner_record = D.record

    def _staged_record(root: Any, key: Any, content: bytes, **kw: Any) -> bool:
        return inner_record(staging_root, key, content, **kw)

    saved.append((D, "record", inner_record))
    D.record = _staged_record

    from life_agent.core import outcomes as _O

    _SINK["decisions"] = staging_root / "decisions.jsonl"
    _SINK["outcomes"] = staging_root / "outcomes.jsonl"
    saved.append((_SINK, "__cleared__", None))
    sinks: tuple[tuple[Any, str], ...] = ((DEC, "decisions.jsonl"),
                                          (_O, "outcomes.jsonl"))
    for module, sink_name in sinks:
        inner_append = module.append
        sink = staging_root / sink_name

        def _sunk(path: Any, event: Any, *, _inner: Any = inner_append,
                  _sink: Path = sink) -> Any:
            return _inner(_sink, event)

        saved.append((module, "append", inner_append))
        module.append = _sunk
    try:
        yield
    finally:
        for obj, name, value in reversed(saved):
            if obj is _SINK:
                _SINK.clear()
                continue
            setattr(obj, name, value)


@contextlib.contextmanager
def installed(rig: Rig, snapshot: KBSnapshot) -> Iterator[Rig]:
    """Install the taps that are not call parameters, and restore them on exit.

    Four bindings move: the §18.9 cache read (so replay needs no corpus), the process-shared
    skin (so the narrative leaf, which reaches it through ``shared_brain``, replays), the
    five KB fold paths (so folds see the snapshot, not today's logs), and
    ``executor.decide_via_loop`` (wrapped, never replaced — the loop still runs; the wrapper
    only keeps its returned View so the driver can record the act).
    """
    saved: list[tuple[Any, str, Any]] = []

    def _set(obj: Any, name: str, value: Any) -> None:
        saved.append((obj, name, getattr(obj, name)))
        setattr(obj, name, value)

    _set(D, "lookup", rig.cache)
    for attr, snap_name in (("UTILITY_MODEL", "utility_model"),
                            ("UTILITY_ELICITATIONS", "utility_elicitations"),
                            ("REACTIONS_LOG", "reactions"),
                            ("DECISIONS_LOG", "decisions"),
                            ("OUTCOMES_LOG", "outcomes")):
        _set(CFG, attr, snapshot.path(snap_name))

    inner_loop = EX.decide_via_loop

    def _capturing_loop(*a: Any, **kw: Any) -> dict[str, Any]:
        view = inner_loop(*a, **kw)
        rig.last_view = view
        return view

    _set(EX, "decide_via_loop", _capturing_loop)

    # r33 RC-1's second lesson, learned live: a PATH-LESS ledger writer (record_miss falls
    # through to config) appended into the checkpoint's decisions.snapshot on the first
    # replay of the r33 tree — the fold input every later run reads. Redirecting the
    # config PATH points reads at the snapshot, so it points path-less WRITES at it too;
    # `sealed`'s docstring names the covering form — sink the append itself. PATH-AWARE,
    # unlike `sealed`'s blanket sink: only a write aimed at the frozen snapshot file is
    # diverted to staging; the leaf drivers pass explicit tmp paths and READ THEM BACK
    # (`_last_event`), so those must land exactly where they were addressed.
    snapshot.staging.mkdir(parents=True, exist_ok=True)
    inner_dec_append = DEC.append
    frozen_decisions = snapshot.path("decisions")

    def _staged_append(path: Any, event: Any) -> Any:
        if Path(path) == frozen_decisions:
            return inner_dec_append(snapshot.staging / "decisions.jsonl", event)
        return inner_dec_append(path, event)

    _set(DEC, "append", _staged_append)

    prior_brain = LK._BRAIN
    prior_u_bar_raw, prior_u_bar_shaped = LK._U_BAR_RAW, LK._U_BAR_SHAPED
    LK.set_shared_brain(rig.brain)
    # the per-process Ū memo (both the engine-fold cache and its per-shape scalings — r30)
    # is keyed on a fold version, not a KB, so a snapshot swap must clear both.
    LK._U_BAR_RAW = None
    LK._U_BAR_SHAPED = {}
    try:
        yield rig
    finally:
        LK._U_BAR_RAW = prior_u_bar_raw
        LK._U_BAR_SHAPED = prior_u_bar_shaped
        LK.set_shared_brain(prior_brain)
        for obj, name, value in reversed(saved):
            setattr(obj, name, value)


# --- shaping a written DecisionEvent into the comparator's body -----------------------------

def body_from_event(event: DEC.DecisionEvent, *, question: str,
                    retrieval_keys: list[str]) -> dict[str, Any]:
    """The family leaves write a :class:`DecisionEvent` directly; the executor path posts a
    ``/log_decision`` body. Both are the same record — this shapes the former into the
    latter so ONE field-class list governs both (§7.2), and so M2's move of the leaves'
    writes into the one poster is a comparison, not a re-derivation."""
    ps = event.posterior_summary
    return {
        "question": question,
        "retrieval_keys": sorted(retrieval_keys),
        "decision": {
            "effector": event.chosen_action,
            "credences": list(ps.get("credences") or []),
            "candidates": list(ps.get("candidates") or []),
            "p_none": ps.get("p_none"),
            "eu": event.predicted_eu,
            "n_obs": ps.get("n_obs", 0),
            "n_indeterminate": ps.get("n_indeterminate", 0),
            "n_competing": ps.get("n_competing", 0),
            "instrument": event.instrument,
            "run_id": event.run_id,
            "cost_usd": event.cost_usd,
            "latency_s": event.latency_s,
            "regime": event.regime,
            "policy": event.policy,
        },
    }


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _last_event(path: Path) -> DEC.DecisionEvent | None:
    return DEC.read(path)[-1] if path.exists() else None


#: Where :func:`sealed` sinks decision appends. The drivers read the event they just caused
#: back from HERE, not from the path they handed the leaf — under the seal those differ, and
#: reading the handed path would silently find nothing.
_SINK: dict[str, Path] = {}


def decisions_sink(fallback_root: Path) -> Path:
    return _SINK.get("decisions", Path(fallback_root) / "decisions.jsonl")


# --- trace B: the in-process families (the terminals-only regime's leaves) --------------------

def drive_lookup_leaf(rig: Rig, snapshot: KBSnapshot, *, question: str,
                      hits: list[dict[str, Any]], covariates: LK.HitCovariates,
                      scope: str, root: Path, run_id: str) -> dict[str, Any]:
    """`LK.lookup_answer` end to end: route → observe (the grounding gate) → the correlated-
    evidence posterior → the EU decision → the recorded answer + logged decision. Pure in its
    hits given the rig; ``root`` is a STAGING root, so the §18.9 answer artefact this writes
    never lands in the live cache."""
    decisions_path = decisions_sink(root)
    lk = LK.lookup_answer(Path(root), question, hits, scope=scope, brain=rig.brain,
                          route_client=rig.client, extract_client=rig.client,
                          covariates=covariates, decisions_path=decisions_path,
                          run_id=run_id)
    if lk is None:
        # a declined route or zero grounded observations — a COVERAGE statement, and the
        # fixture records it as such (the narrative path answers; §2.2's "leaves")
        return {"effector": "miss", "asserted": [], "candidates": [], "credences": [],
                "p_none": None, "eu": None, "gate": None, "log_decision": None,
                "audit": {"fallthrough": "route declined or no grounded observation"}}
    event = _last_event(decisions_path)
    keys = list(dict.fromkeys(h["artifact_cache_key"] for h in hits))
    return {
        "effector": lk.action,
        "asserted": [lk.candidates[0]] if lk.action == "report" and lk.candidates else (
            [lk.scoped_value] if lk.action == "report_scoped" and lk.scoped_value else []),
        "candidates": list(lk.candidates),
        "credences": list(lk.credences),
        "p_none": lk.p_none,
        "eu": lk.eu,
        "gate": None,
        "regime": event.regime if event else None,
        "policy": event.policy if event else None,
        "log_decision": body_from_event(event, question=question, retrieval_keys=keys)
        if event else None,
        "audit": {"rendered_sha": _sha(lk.rendered),
                  "answer_cache_key": lk.answer_cache_key,
                  "utility_fold_version": lk.utility_fold_version,
                  "n_observations": len(lk.observations),
                  "n_indeterminate": lk.n_indeterminate,
                  "defaulted": list(event.defaulted) if event else None},
    }


def drive_narrative_leaf(rig: Rig, snapshot: KBSnapshot, *, question: str, text: str,
                         cards: list[Any], scope: str, root: Path,
                         run_id: str) -> dict[str, Any]:
    """`NARR.narrative_answer` over a recorded synthesize proposal: parse → audit cells →
    population credences → the per-claim inclusion decision under Ū.

    This is the ``report(claims)`` terminal's CONTENT computation (design §2.3, ruling Q9):
    the leaf specifies one terminal's claim set, and the fixture puts that set — which claims
    were included, at which credences — under the comparator rather than beside it.
    """
    from life_agent.core import narrative as NARR

    decisions_path = decisions_sink(root)
    nv = NARR.narrative_answer(Path(root), question, text, cards, scope=scope,
                               outcomes_path=snapshot.path("outcomes"),
                               decisions_path=decisions_path, run_id=run_id)
    event = _last_event(decisions_path)
    return {
        "effector": nv.action,
        # the terminal's CONTENT: which claims the leaf included, in posterior order
        "asserted": [c.text for c in nv.claims if c.included],
        "candidates": [c.text for c in nv.claims],
        "credences": [c.credence for c in nv.claims],
        "p_none": None,
        "eu": nv.eu,
        "gate": None,
        "regime": event.regime if event else None,
        "policy": event.policy if event else None,
        "log_decision": None,      # the narrative leaf writes its event directly (M2 moves it)
        "audit": {"rendered_sha": _sha(nv.rendered),
                  "answer_cache_key": nv.answer_cache_key,
                  "abstain_reason": nv.abstain_reason,
                  "coverage": list(nv.coverage), "coverage_n": nv.coverage_n,
                  "eu_include": [c.eu_include for c in nv.claims],
                  "cells": {k: list(v) for k, v in sorted(nv.cell_posteriors.items())}},
    }


# --- trace A: the executor path (the full regime) ---------------------------------------------

def drive_executor_loop(rig: Rig, snapshot: KBSnapshot, *, question: str, k: int,
                        run_id: str) -> dict[str, Any]:
    """The deployed reach-surface driver (`ask_client.answer`) over the tapped stack: the
    executor loop enacts the daemon's schedule and the surface posts the terminal decision.

    ``check_ready=False`` because readiness is the tap's business here, not the host's — the
    fixture is about what the loop DECIDES, and a readiness probe over a replayed cassette
    would be a liveness statement about nothing.
    """
    from life_agent.core import ask_client as AC

    rig.last_view = None
    posted: list[dict[str, Any]] = []

    def post(url: str, payload: dict[str, Any]) -> Any:
        # the POSTER'S OUTPUT — what §5.1's one-poster move changes — captured on the way
        # past, identically whether the tap under it is recording or replaying. Served
        # CANNED (r12 amendment 1): the poster's reply feeds no decision (the id is
        # audit-only), the body is what the comparator pins, and consulting the cassette
        # here would make every poster-shape checkpoint miss on its own registered change.
        if url.endswith("/log_decision"):
            posted.append(json.loads(json.dumps(payload)))
            return {"decision_id": "replayed"}
        return rig.post(url, payload)

    r = AC.drive(question, k, post=post, get=rig.get, check_ready=False)
    if r.down:
        rendered = AC.DOWN
    else:
        assert r.view is not None
        rendered = EX.render_view(r.view)
    decision_id = r.decision_id
    view: dict[str, Any] = rig.last_view or {}
    return {
        "effector": view.get("effector"),
        "asserted": list(view.get("asserted") or []),
        "candidates": list(view.get("candidates") or []),
        "credences": list(view.get("credences") or []),
        "p_none": view.get("p_none"),
        "eu": view.get("eu"),
        "gate": None,
        "log_decision": posted[-1] if posted else None,
        "audit": {"rendered_sha": _sha(rendered), "decision_id": decision_id,
                  "n_hits": len(view.get("hits") or []),
                  "n_obs": view.get("n_obs"),
                  "route": None if view.get("route") is None else "typed",
                  "spend_usd": view.get("spend_usd"),
                  "instrument": view.get("instrument"),
                  "run_id": run_id},
    }


def drive_ask_poster(question: str, view: dict[str, Any], *,
                     run_id: str | None) -> dict[str, Any]:
    """The ONE poster's body from a recorded view (`ask_client.post_decision` — since M2
    the CLI's `_log_executor_decision` and the reach surface's inline poster are this one
    function, r12 D2). Hermetic: it needs only a recorded View; the transport is a capture.
    r33 RC-1: a MISS view now appends a local ledger row through the poster, and this
    trace runs OUTSIDE `installed()`'s sink redirection — the append lands in a discarded
    temp sink, because a replay may never write the ambient ledger."""
    import tempfile

    from life_agent.core import ask_client as AC

    captured: list[dict[str, Any]] = []

    def _capture(url: str, payload: dict[str, Any]) -> dict[str, Any]:
        captured.append({"url": url, "payload": payload})
        return {"decision_id": "captured"}

    with tempfile.TemporaryDirectory(prefix="collapse-poster-") as tmp:
        prior = CFG.DECISIONS_LOG
        CFG.DECISIONS_LOG = Path(tmp) / "decisions.jsonl"
        try:
            AC.post_decision(_capture, "http://bridge", question, view, run_id=run_id)
        finally:
            CFG.DECISIONS_LOG = prior
    body = captured[-1]["payload"] if captured else None
    return {"effector": view.get("effector"), "asserted": list(view.get("asserted") or []),
            "candidates": list(view.get("candidates") or []),
            "credences": list(view.get("credences") or []),
            "p_none": view.get("p_none"), "eu": view.get("eu"), "gate": None,
            "log_decision": body,
            "audit": {"posted": bool(captured), "poster": "ask_client.post_decision"}}


# --- the seam: a commit with no engine available (§6.5) ------------------------------------

def drive_seam_unavailable(question: str) -> dict[str, Any]:
    """§6.5 driven end-to-end through the ONE driver's down path (M2, r12 D2): the seam
    commits the declared gate, the gate is mirrored (fail-open — nothing listens here),
    and the unavailability RECORD is appended — captured into a staging ledger, never the
    configured one.

    Pre-M2 truth (the recorded fixture): abstain from the declared observation alone, no
    decision_id, nothing on the ledger. Registered direction (DIR-2): the same situation
    becomes a RECORD carrying ``regime: unavailable`` with no ``decision_id`` — an
    unavailability event, never an abstain verdict (R-3 folds abstains as utility
    evidence)."""
    import tempfile

    from life_agent.core import ask_client as AC
    from life_agent.core import config as CFG
    from life_agent.core import seam as SEAM

    with tempfile.TemporaryDirectory(prefix="collapse-seam-") as tmp:
        sink = Path(tmp) / "decisions.jsonl"
        prior = CFG.DECISIONS_LOG
        CFG.DECISIONS_LOG = sink
        # This fixture models NO ENGINE AT ALL (§6.5). Since M5 the driver's down
        # branch first tries the terminals-only regime — and the replay box HAS the
        # in-process engine, so it must be made unavailable here or the driver would
        # honestly answer over T (the M5 behaviour, which is NOT this fixture's
        # situation) and touch the live store from inside the instrument.
        prior_term = AC._terminals_answer

        def _no_engine(question: str, k: int) -> tuple[str, str | None]:
            raise RuntimeError("no engine at all (the §6.5 fixture's situation)")

        AC._terminals_answer = _no_engine
        try:
            r = AC.drive(question, ready=lambda: False)
        finally:
            CFG.DECISIONS_LOG = prior
            AC._terminals_answer = prior_term
        assert r.down and r.decision_id is None
        # Read the event back through the seal-aware sink (_SINK's contract): under the
        # recorder's seal `decisions.append` itself is redirected, so the tempdir this
        # driver handed the leaf stays empty and reading it would silently find nothing
        # — exactly what the m5-base rehearsal caught (effector recorded None).
        event = _last_event(decisions_sink(Path(tmp)))
    body = (body_from_event(event, question=question, retrieval_keys=[])
            if event else None)
    return {"effector": event.chosen_action if event else None, "asserted": [],
            "candidates": [], "credences": [],
            "p_none": None, "eu": None, "gate": SEAM.GATE_EXECUTOR_DOWN,
            "regime": event.regime if event else None,
            "policy": event.policy if event else None,
            "log_decision": body,
            "audit": {"question_id": DEC.question_id(question),
                      "defaulted": list(event.defaulted) if event else None}}


def staging_deps(client: Any, staging: Path) -> Any:
    """A :class:`life_agent.bridge.server.BridgeDeps` that READS the live corpus and WRITES
    only under ``staging`` — the recorder never appends to a live calibration log (the
    brief's contamination rule, taken by routing rather than by marking)."""
    from life_agent.bridge import server as BR

    deps = BR.build_deps()
    staging.mkdir(parents=True, exist_ok=True)
    return dataclasses.replace(
        deps, client=client,
        decisions_path=staging / "decisions.jsonl",
        reactions_path=staging / "reactions.jsonl",
        gather_outcomes_path=staging / "gather_outcomes.jsonl",
        membrane=None)


def local_stack_post(deps: Any, daemon_base: str,
                     http_post: Callable[[str, dict[str, Any]], Any]
                     ) -> Callable[[str, dict[str, Any]], Any]:
    """Route the body's POSTs: the daemon over real HTTP (it is the ranking, and it is a
    separate process by design), everything else through the bridge's own ``dispatch`` in
    THIS process — which is what puts the bridge's leaves (extraction's grounding gate, the
    narrative leaf) inside the recorded envelope instead of behind an opaque socket."""
    from life_agent.bridge.server import dispatch

    def post(url: str, payload: dict[str, Any]) -> Any:
        if url.startswith(daemon_base):
            return http_post(url, payload)
        path = "/" + url.split("://", 1)[-1].split("/", 1)[1] if "://" in url else url
        status, reply = dispatch(deps, "POST", path,
                                 json.dumps(payload).encode("utf-8"))
        if status != 200:
            raise RuntimeError(f"bridge {path} -> {status}: {reply}")
        return reply

    return post


def local_stack_get(deps: Any) -> Callable[[str], Any]:
    from life_agent.bridge.server import dispatch

    def get(url: str) -> Any:
        path = "/" + url.split("://", 1)[-1].split("/", 1)[1] if "://" in url else url
        status, reply = dispatch(deps, "GET", path, b"")
        if status != 200:
            raise RuntimeError(f"bridge {path} -> {status}: {reply}")
        return reply

    return get


def fixture_from(fixture_id: str, checkpoint: str, trace: str, *, question: str,
                 classes: tuple[str, ...], inputs: dict[str, Any],
                 outputs: dict[str, Any], wire: list[FX.Exchange],
                 provenance: dict[str, Any],
                 expected_change: dict[str, Any] | None = None) -> FX.Fixture:
    return FX.Fixture(
        fixture_id=fixture_id, checkpoint=checkpoint, trace=trace,
        classes=tuple(sorted(set(classes))), question=question,
        question_id=DEC.question_id(question), inputs=inputs, outputs=outputs,
        wire=tuple(wire), provenance=provenance, expected_change=expected_change)
