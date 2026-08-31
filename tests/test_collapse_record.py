"""The instrument's own integrity (module-collapse-design.md §7, the M0 brief's
"gate-quality doctrine, applied to the gate-builder").

A comparator that has never failed is a green that cannot fail, so these tests corrupt
recorded fixtures on purpose and require the red. They also drift-gate the ONE seam the
instrument installs that is not a call parameter.

Run: uv run --project . python -m pytest tests/test_collapse_record.py
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from life_agent.collapse import compare as CMP
from life_agent.collapse import drive as DR
from life_agent.collapse import fixture as FX
from life_agent.core import decisions as DEC

SRC = Path(__file__).resolve().parents[1] / "src" / "life_agent"


def _fixture(**over: object) -> FX.Fixture:
    base = dict(
        fixture_id="m0-synthetic-1", checkpoint="m0", trace="B-lookup",
        classes=("terminal:report", "outcome:committed"),
        question="what is the synthetic serial?",  # PII-OK: synthetic question
        question_id="0123456789abcdef",
        inputs={"hits": [], "run_id": "collapse-m0"},
        outputs={"effector": "report", "asserted": ["A"], "candidates": ["A", "B"],
                 "credences": [0.9, 0.1], "p_none": 0.02, "eu": 0.6, "gate": None,
                 "regime": "full", "policy": "all-to-date",
                 "log_decision": {
                     "question": "what is the synthetic serial?",  # PII-OK: synthetic
                     "retrieval_keys": ["k1"],
                     "decision": {"effector": "report", "credences": [0.9, 0.1],
                                  "candidates": ["A", "B"], "p_none": 0.02, "eu": 0.6,
                                  "n_obs": 2, "n_indeterminate": 0, "n_competing": 0,
                                  "instrument": "", "run_id": "collapse-m0",
                                  "cost_usd": None, "latency_s": None,
                                  "regime": "full", "policy": "all-to-date"}},
                 "audit": {"rendered_sha": "abc"}},
        wire=(), provenance={"tree_sha": "deadbeef"},
    )
    base.update(over)
    return FX.Fixture(**base)  # type: ignore[arg-type]


# --- the self-kill: a corrupted fixture must go red ----------------------------------------

@pytest.mark.parametrize("path,value", [
    ("effector", "abstain"),
    ("credences", [0.5, 0.5]),
    ("eu", 0.61),
])
def test_a_corrupted_output_is_killed(path: str, value: object) -> None:
    fx = _fixture()
    corrupted = {**fx.outputs, path: value}
    diffs = CMP.compare_outputs(fx.outputs, corrupted)
    assert [d.path for d in diffs] == [path]


def test_a_corrupted_body_field_is_killed_inside_the_posted_body() -> None:
    fx = _fixture()
    body = json.loads(json.dumps(fx.outputs["log_decision"]))
    body["decision"]["n_obs"] = 99
    diffs = CMP.compare_outputs(fx.outputs, {**fx.outputs, "log_decision": body})
    assert [(d.path, d.reason) for d in diffs] == [("log_decision.decision.n_obs", "value")]


def test_an_identical_replay_is_green() -> None:
    fx = _fixture()
    assert CMP.compare_outputs(fx.outputs, json.loads(json.dumps(fx.outputs))) == []


# --- the fixture's own round trip ----------------------------------------------------------

def test_fixture_round_trips_through_json(tmp_path: Path) -> None:
    fx = _fixture(wire=(FX.Exchange("skin", {"method": "mean", "params": {}},
                                    {"result": {"mean": 0.5}}),))
    FX.write(tmp_path, fx)
    (back,) = FX.read_all(tmp_path)
    assert back == fx


def test_reading_a_malformed_fixture_raises_rather_than_skipping(tmp_path: Path) -> None:
    """A bisection oracle that silently skips a fixture is not an oracle."""
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        FX.read_all(tmp_path)


def test_an_unknown_trace_is_refused_at_construction() -> None:
    with pytest.raises(ValueError, match="unknown trace"):
        _fixture(trace="whatever")


# --- coverage: every declared class is named, present or absent -------------------------------

def test_coverage_names_absent_classes_rather_than_omitting_them() -> None:
    cov = FX.coverage([_fixture(classes=("terminal:report",))])
    assert cov["terminal:report"] == ["m0-synthetic-1"]
    for terminal in ("hedge", "abstain", "report(claims)", "miss"):
        assert cov[f"terminal:{terminal}"] == []      # named, never silently missing


def test_manifest_publishes_the_field_classes_it_was_compared_under() -> None:
    man = FX.manifest("m0", [_fixture()], {"tree_sha": "deadbeef"})
    assert man["field_classes"]["runtime_measured"] == sorted(FX.RUNTIME_MEASURED)
    assert man["field_classes"]["float_tolerance"] == FX.FLOAT_TOL
    assert man["n_fixtures"] == 1


# --- the event → body shaping the two record shapes share --------------------------------------

def test_body_from_event_carries_the_regime_and_policy_the_event_recorded() -> None:
    ev = DEC.DecisionEvent(
        tx_time="2026-08-19T00:00:00+00:00", run_id="collapse-m0", question_id="q",
        family="lookup", action_set=DEC.LOOKUP_ACTION_ORDER,
        posterior_summary={"candidates": ["A"], "credences": [1.0], "p_none": 0.0,
                           "n_obs": 1, "n_indeterminate": 0, "n_competing": 0},
        utility_fold_version="v", chosen_action="report", predicted_eu=0.5)
    body = DR.body_from_event(ev, question="q", retrieval_keys=["k2", "k1"])
    assert body["retrieval_keys"] == ["k1", "k2"]         # sorted, as the bridge sorts them
    assert body["decision"]["regime"] == DEC.REGIME_DEFAULT
    assert body["decision"]["policy"] == DEC.POLICY_DEFAULT
    # every field the shaping emits is CLASSIFIED — else the comparator would call it
    # unclassified on the first replay
    emitted = {"question", "retrieval_keys"} | {f"decision.{k}" for k in body["decision"]}
    assert emitted <= (FX.VALUE_COMPARED | FX.RUNTIME_MEASURED)


# --- the drift gate: the instrument seam is the instrument's, and nobody else's ----------------

def test_only_the_collapse_instrument_installs_a_shared_brain() -> None:
    """`lookup.set_shared_brain` swaps the engine under everything in the process. The one
    sanctioned caller is the off-path equivalence instrument; a second installer anywhere in
    `src/` would be a way to change the engine underneath a live decision — exactly the fork
    the one act seam exists to prevent."""
    callers = sorted(
        p.relative_to(SRC).as_posix()
        for p in SRC.rglob("*.py")
        if "set_shared_brain" in p.read_text(encoding="utf-8"))
    assert callers == ["collapse/drive.py", "core/lookup.py"]


def test_the_decision_path_never_imports_the_instrument() -> None:
    """The instrument is a consumer of the decision path, never a dependency of it — the
    import direction is what keeps "nothing here is on the decision path" checkable."""
    offenders = sorted(
        p.relative_to(SRC).as_posix()
        for p in SRC.rglob("*.py")
        if not p.as_posix().startswith(SRC.as_posix() + "/collapse")
        and any(line.lstrip().startswith(("import life_agent.collapse",
                                          "from life_agent.collapse"))
                for line in p.read_text(encoding="utf-8").splitlines()))
    assert offenders == []


# --- the seal: the recorder's two boundary claims, enforced rather than asserted -----------
# Learned at M0 the expensive way: gating only the schema-constrained instrument client left
# `joint_extract`, `rerank`, `expansion`, `synthesis` and `/probe/deliberate` free to reach
# Anthropic through their own import-bound bindings — and their §18.9 writes free to land in
# the LIVE content-addressed cache, since they take the root as an argument.

@pytest.mark.parametrize("module_name,attr", [
    ("life_agent.core.llm", "anthropic_complete"),
    ("life_agent.core.joint_extract", "anthropic_complete"),
    ("life_agent.core.rerank", "anthropic_complete"),
    ("life_agent.core.deliberate", "answer"),
])
def test_every_named_spend_seam_is_sealed(module_name: str, attr: str,
                                          tmp_path: Path) -> None:
    import importlib

    from life_agent.collapse.taps import WouldSpendError
    mod = importlib.import_module(module_name)
    with DR.sealed(tmp_path / "pkm"), pytest.raises(WouldSpendError):
        getattr(mod, attr)("a", "b")


def test_the_seal_covers_every_seam_it_declares() -> None:
    """A seam that vanishes from a module (a rename, a refactor) must not silently drop out
    of the seal — the list is the contract, and it is checked against reality."""
    import importlib
    for module_name, attr in DR._SPEND_SEAMS:
        mod = importlib.import_module(module_name)
        assert hasattr(mod, attr), f"{module_name}.{attr} no longer exists — update the seal"


def test_the_seal_routes_every_recorded_derivation_off_the_passed_root(
        tmp_path: Path) -> None:
    """The bridge's handlers take the LIVE root as an argument, so the redirect has to
    happen at `derivations.record` itself — a tap on the caller's side cannot see them."""
    from life_agent.core import derivations as D

    live, staging = tmp_path / "live", tmp_path / "staging"
    key = D.retrieve_key("q", "digest", k=8)  # PII-OK: synthetic question
    with DR.sealed(staging):
        D.record(live, key, b'{"hits": []}', lineage=[])
    assert not live.exists(), "a recording must never write the root it was pointed at"
    assert D.meta_file(staging, key.cache_key).exists()


def test_allow_spend_leaves_the_seams_alone(tmp_path: Path) -> None:
    """The opt-in is real: a deliberate, owner-executed recording of the priced lane needs
    the seams open — but the §18.9 redirect stays on regardless, because writing the live
    cache is never part of recording a baseline."""
    from life_agent.core import joint_extract as JE

    before = JE.anthropic_complete
    with DR.sealed(tmp_path / "pkm", allow_spend=True):
        assert JE.anthropic_complete is before
    assert JE.anthropic_complete is before


def test_the_seal_restores_every_binding_on_exit(tmp_path: Path) -> None:
    import importlib

    from life_agent.core import derivations as D
    before = {(m, a): getattr(importlib.import_module(m), a) for m, a in DR._SPEND_SEAMS}
    before[("D", "record")] = D.record
    with DR.sealed(tmp_path / "pkm"):
        pass
    for (m, a), fn in before.items():
        if m == "D":
            assert D.record is fn
        else:
            assert getattr(importlib.import_module(m), a) is fn


def test_the_seal_sinks_decision_appends_so_the_c5_mirror_never_fires(
        tmp_path: Path) -> None:
    """The leak this test exists for: the bridge's `/narrative` handler appends its decision
    with NO path argument, so it falls through to `config.DECISIONS_LOG` — and a decision
    appended at the configured path is mirrored onto the owner's unified stream by the C5
    dual-write. Redirecting config is not enough; the append itself has to be sunk, which is
    also what makes the mirror's own "not the configured path" guard fire."""
    from life_agent.core import config as CFG
    from life_agent.core import decisions as D2

    configured = tmp_path / "configured.jsonl"
    ev = D2.DecisionEvent(
        tx_time="2026-08-19T00:00:00+00:00", run_id="ask", question_id="q",
        family="narrative", action_set=D2.NARRATIVE_ACTION_ORDER, posterior_summary={},
        utility_fold_version="v", chosen_action="abstain", predicted_eu=0.0)
    prior = CFG.DECISIONS_LOG
    CFG.DECISIONS_LOG = configured
    try:
        with DR.sealed(tmp_path / "pkm"):
            D2.append(CFG.DECISIONS_LOG, ev)      # the pathless writer's fall-through
    finally:
        CFG.DECISIONS_LOG = prior
    assert not configured.exists(), "a sealed recording reached the configured log"
    assert D2.read(tmp_path / "pkm" / "decisions.jsonl") == [ev]


def test_the_seal_restores_the_append_functions_and_clears_its_sink(tmp_path: Path) -> None:
    from life_agent.core import decisions as D2
    from life_agent.core import outcomes as O2

    before = (D2.append, O2.append)
    with DR.sealed(tmp_path / "pkm"):
        assert D2.append is not before[0]
    assert (D2.append, O2.append) == before
    assert DR._SINK == {}


# M1 / R8 — the recorder writes one file per fixture and then GLOBS the directory to build its
# manifest, so a directory that already holds fixtures yields a manifest describing a mixture of
# two runs while presenting as a whole artefact. The hazard is a partial failure — an aborted
# recording leaves its predecessors behind, and nothing says so. Found at M0.5 (r03 A6, checked
# clean by hand that time), ruled at review into a guard that runs BEFORE the recording, since
# a recording is the expensive part and finding out afterwards is finding out too late.

def test_a_directory_holding_fixtures_is_named_as_unsafe_to_record_into(tmp_path: Path) -> None:
    FX.write(tmp_path, _fixture(fixture_id="m0-synthetic-1"))
    FX.write(tmp_path, _fixture(fixture_id="m0-synthetic-2"))
    assert FX.existing_fixtures(tmp_path) == ["m0-synthetic-1.json", "m0-synthetic-2.json"]


def test_an_absent_or_empty_directory_is_safe_to_record_into(tmp_path: Path) -> None:
    assert FX.existing_fixtures(tmp_path / "never-created") == []
    (tmp_path / "empty").mkdir()
    assert FX.existing_fixtures(tmp_path / "empty") == []


def test_a_manifest_alone_is_unsafe_because_the_recorder_republishes_it(tmp_path: Path) -> None:
    # a run that died between writing its manifest and being merged leaves exactly this shape.
    (tmp_path / "manifest.json").write_text("{}", encoding="utf-8")
    assert FX.existing_fixtures(tmp_path) == ["manifest.json"]


def test_a_snapshots_directory_alone_is_safe_because_the_recorder_refreshes_it(
        tmp_path: Path) -> None:
    # `take_snapshot` re-copies the fold inputs on every run, so their presence is not evidence
    # of a stale FIXTURE — refusing on it would refuse every legitimate re-record.
    (tmp_path / "snapshots").mkdir()
    (tmp_path / "snapshots" / "decisions.snapshot").write_text("x", encoding="utf-8")
    assert FX.existing_fixtures(tmp_path) == []


# --- spend metering on the manifest (stage-0 rider) -------------------------------------------

def test_manifest_derives_spent_usd_from_the_recorded_instrument_wire() -> None:
    paid = _fixture(wire=(
        FX.Exchange(seam="instrument", request={}, response={"raw_text": "{}",
                                                             "cost_usd": 0.03}),
        FX.Exchange(seam="instrument", request={}, response={"raw_text": "{}",
                                                             "cost_usd": 0.02}),
        FX.Exchange(seam="http", request={}, response={"cost_usd": 99.0}),  # not a model call
    ))
    free = _fixture(fixture_id="m0-synthetic-2")
    man = FX.manifest("m0", [paid, free], {"tree_sha": "deadbeef"})
    assert man["spent_usd"] == pytest.approx(0.05)   # derived from the fixtures, not asserted


def test_manifest_spent_usd_is_zero_for_an_unpriced_set() -> None:
    assert FX.manifest("m0", [_fixture()], {})["spent_usd"] == 0.0


def test_recorder_cli_carries_a_spend_cap_with_the_delegated_default() -> None:
    import importlib
    import sys as _sys
    _sys.path.insert(0, str(SRC.parents[1] / "scripts"))
    rec = importlib.import_module("collapse_record")
    args = rec._parser().parse_args(["--allow-spend"])
    assert args.max_usd == pytest.approx(8.0)   # the stage-0 delegation's hard cap


def test_seam_driver_reads_the_event_through_the_seal(tmp_path: Path) -> None:
    """The §6.5 seam driver must read the event it caused back through `decisions_sink`
    — under the recorder's seal, `decisions.append` itself is redirected to the seal's
    sink, and reading the tempdir the driver handed the leaf finds nothing (the m5-base
    rehearsal caught exactly this: the fixture recorded effector=None where the replay
    reads the event's 'abstain'; the m2-base record never exposed it because the
    pre-M2 tree appended no event on this path at all)."""
    with DR.sealed(tmp_path / "pkm"):
        out = DR.drive_seam_unavailable("the stack is down")  # PII-OK: synthetic
    assert out["effector"] == "abstain"
    assert out["regime"] == "unavailable"
    assert out["log_decision"] is not None


# --- r33 RC-1 write isolation: the poster driver may NEVER touch the ambient ledger -----

def test_drive_ask_poster_on_a_miss_view_leaves_the_ambient_ledger_untouched() -> None:
    """Since RC-1 a miss view appends a local regime="miss" row through the poster. The
    A-poster trace runs OUTSIDE `installed()`'s sink redirection, so without its own
    isolation a replay of a miss fixture would append to the LIVE decisions ledger —
    the one class of write a $0 replay is forbidden. The append lands in a discarded
    temp sink; the driver's outputs stay transport-side."""
    from life_agent.collapse import drive as DR
    from life_agent.core import config as CFG
    miss_view = {"effector": "miss", "asserted": [], "candidates": [], "credences": [],
                 "p_none": None, "eu": None, "n_obs": 0, "n_indeterminate": 1,
                 "hits": [{"artifact_cache_key": "d0", "chunk_text": "x"}],
                 "route": {"construct": "anything"}}
    out = DR.drive_ask_poster("q?", miss_view, run_id="collapse-test")
    assert out["log_decision"] is None            # a miss never posts a bridge body
    assert not CFG.DECISIONS_LOG.exists()         # ...and never writes the ambient ledger


def test_installed_sinks_a_pathless_ledger_append_into_staging(tmp_path: Path) -> None:
    """The replay boundary (RC-1's second lesson, learned live: the first m5-base replay
    of the r33 tree APPENDED a miss row into the checkpoint's decisions.snapshot — the
    fold input every later baseline run reads — because `installed()` redirected the
    CONFIG PATH and record_miss writes through it). `sealed`'s own docstring names the
    only covering form: sink the append itself. Under `installed()`, a path-less
    DEC.append lands in the snapshot's staging dir; the snapshot file stays byte-frozen."""
    from life_agent.collapse import drive as DR
    from life_agent.core import ask_client as AC
    from life_agent.core import decisions as DEC

    snapdir = tmp_path / "snapshots"
    snapdir.mkdir()
    frozen = b'{"pinned": "fold-input"}\n'
    (snapdir / "decisions.snapshot").write_bytes(frozen)
    snapshot = DR.KBSnapshot(snapdir)

    class _Dummy:
        def __call__(self, *a: object, **k: object) -> None:
            raise AssertionError("no wire may be touched by a local append")

    rig = DR.Rig(brain=object(), post=_Dummy(), get=_Dummy(),
                 client=object(), cache=_Dummy())
    miss_view = {"effector": "miss", "asserted": [], "candidates": [], "credences": [],
                 "p_none": None, "eu": None, "n_obs": 0, "n_indeterminate": 0,
                 "hits": [{"artifact_cache_key": "d0", "chunk_text": "x"}],
                 "route": {"construct": "anything"}}
    with DR.installed(rig, snapshot):
        did = AC.post_decision(_Dummy(), "http://bridge", "q?", miss_view, run_id="rp")
    assert did and did.startswith("ab-")
    assert (snapdir / "decisions.snapshot").read_bytes() == frozen   # byte-frozen
    staged = snapshot.staging / "decisions.jsonl"
    assert staged.exists() and b'"regime":"miss"' in staged.read_bytes().replace(b" ", b"")
    rows = DEC.read(staged)
    assert [r.regime for r in rows] == ["miss"]


def test_installed_leaves_explicitly_addressed_appends_where_the_driver_reads_them(
        tmp_path: Path) -> None:
    """The sink is PATH-AWARE: the leaf drivers append to explicit tmp paths and read
    them back (`_last_event`) to build the fixture's log_decision — a blanket sink would
    null every B-leaf fixture's body. Only the frozen snapshot file diverts."""
    from life_agent.collapse import drive as DR
    from life_agent.core import decisions as DEC

    snapdir = tmp_path / "snapshots"
    snapdir.mkdir()
    (snapdir / "decisions.snapshot").write_bytes(b"")
    snapshot = DR.KBSnapshot(snapdir)
    rig = DR.Rig(brain=object(), post=object(), get=object(),
                 client=object(), cache=object())
    explicit = tmp_path / "leaf" / "decisions.jsonl"
    event = DEC.DecisionEvent(
        tx_time="t", run_id="rp", question_id="q", family="lookup",
        action_set=DEC.LOOKUP_ACTION_ORDER, posterior_summary={"credences": [1.0]},
        utility_fold_version="fv", chosen_action="report", predicted_eu=0.5,
        decision_id="d1")
    with DR.installed(rig, snapshot):
        DEC.append(explicit, event)
    assert explicit.exists() and len(DEC.read(explicit)) == 1   # where it was addressed
    assert not (snapshot.staging / "decisions.jsonl").exists()  # nothing diverted
