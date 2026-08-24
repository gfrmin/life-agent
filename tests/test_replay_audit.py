"""Recorded-replay audit (scripts/replay_audit.py) — hermetic.

r06 read the replace branch from a gate run's own records and could not read three things:
which site fired FIRST, what the probes actually observed, and why its reconstruction and
the recorded terminal disagreed on 28% of the rows where its counterfactual was provably a
no-op. This instrument replays run 10's questions through the DEPLOYED path — the real
executor, the real bridge handlers, the live daemon — recording every call in firing order.

What these tests pin is that it measures what its frozen criteria say, and — r05's and r06's
shared lesson — that every mirror of the decision path is READ FROM the decision path rather
than hand-copied. The counterfactuals especially: RETIRE is *enacted* by rewriting a reply
into the shape the deployed guard already retires on, so the guard under test is
`executor._null_read` itself and never a copy of it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from life_agent.collapse.taps import WouldSpendError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import replay_audit as RP

import life_agent.core.executor as EX
import life_agent.core.lookup as LK


def _call(path, payload=None, reply=None, kind="bridge", n=0):
    return RP.Call(n=n, kind=kind, path=path, payload=dict(payload or {}),
                   reply=dict(reply or {}))


# --- criterion 2(d): the pin, and what makes truncation the right cut -----------------

def test_truncate_keeps_rows_at_or_before_the_cutoff(tmp_path):
    """`run_eval` appends a run's edge rows AFTER the run, so run 10's own rows are exactly
    what a fold during run 10 could not see. The cut is inclusive of the boundary."""
    src = tmp_path / "in.jsonl"
    src.write_text("\n".join(json.dumps(r) for r in [
        {"tx_time": "2026-08-20T10:00:00+00:00", "a": 1},
        {"tx_time": "2026-08-21T01:45:46Z", "a": 2},        # exactly the cutoff — kept
        {"tx_time": "2026-08-21T09:00:00+00:00", "a": 3},   # after — dropped
    ]) + "\n")
    dest = tmp_path / "out.jsonl"
    kept = RP.truncate_jsonl(src, dest, cutoff="2026-08-21T01:45:46Z")
    assert kept == 2
    assert [json.loads(x)["a"] for x in dest.read_text().splitlines()] == [1, 2]


def test_a_row_with_no_tx_time_is_kept_and_counted_never_silently_dropped(tmp_path):
    """A row the cut cannot place is a NAMED limitation, not a silent deletion — dropping it
    would shrink the evidence base the replay folds and bias every curve."""
    src = tmp_path / "in.jsonl"
    src.write_text(json.dumps({"a": 1}) + "\n")
    dest = tmp_path / "out.jsonl"
    kept = RP.truncate_jsonl(src, dest, cutoff="2026-08-21T01:45:46Z")
    assert kept == 1
    assert RP.UNDATED_KEPT, "the instrument must record that it kept an undated row"


# --- criterion 2(f): write isolation, the clause a rehearsal wrote into the live ledger --

def test_the_staging_root_never_symlinks_a_writable_stream(tmp_path):
    """DEVIATION 1: a rehearsal symlinked `ledger/` at the live KB and the ledger mirror
    rewrote the live manifest's legacy offset. Every directory a writer can reach must be
    the staging root's OWN."""
    live = tmp_path / "live"
    for name in ("ledger", "calibration", "utility", "eval"):
        (live / name).mkdir(parents=True)
    (live / "calibration" / "outcomes.jsonl").write_text("")
    (live / "calibration" / "gather_outcomes.jsonl").write_text("")
    dest = RP.build_staging_kb(live, tmp_path / "stage", cutoff="2026-08-21T01:45:46Z")
    for name in ("ledger", "calibration", "tmp"):   # named, NOT read from the constant:
        # iterating RP.NEVER_SYMLINKED would let a shrunk constant shrink the assertion with it
        assert name in RP.NEVER_SYMLINKED, f"{name} dropped out of the isolation set"
        assert (dest / name).exists(), name
        assert not (dest / name).is_symlink(), f"{name} must not point at the live KB"


def test_the_decision_and_reaction_sinks_are_empty_staging_files(tmp_path):
    live = tmp_path / "live"
    (live / "calibration").mkdir(parents=True)
    for n in ("outcomes.jsonl", "gather_outcomes.jsonl", "decisions.jsonl", "reactions.jsonl"):
        (live / "calibration" / n).write_text(
            json.dumps({"tx_time": "2026-01-01T00:00:00Z"}) + "\n")
    dest = RP.build_staging_kb(live, tmp_path / "stage", cutoff="2026-08-21T01:45:46Z")
    for n in ("decisions.jsonl", "reactions.jsonl"):
        assert (dest / "calibration" / n).read_text() == "", n
        assert not (dest / "calibration" / n).is_symlink(), n


def test_verify_pin_refuses_a_corpus_digest_mismatch():
    """A pin that fails is a NAMED REFUSAL, never a caveat (criterion 2)."""
    meta = {"life_agent_git": {"sha": "abc"}, "corpus": {"digest": "D"},
            "utility": {"elicitations_sha256": "E"}, "gate": {"loo": True, "k": 20}}
    assert RP.verify_pin(meta, src_sha="abc", corpus_digest="D", elicitations_sha="E") == []
    fails = RP.verify_pin(meta, src_sha="abc", corpus_digest="OTHER", elicitations_sha="E")
    assert len(fails) == 1 and "corpus" in fails[0]


def test_the_pin_compares_the_src_tree_object_and_not_the_commit(tmp_path):
    """Criterion 2(a) is byte-identity of `src/`, not commit identity — r05 and r06 committed
    documents only, so HEAD has moved while the decision path has not. Comparing commit shas
    would REFUSE a provably identical tree, which is as wrong as passing a different one."""
    same = "23398c1b6c5f63ad5a06748e06d1ae6c87a62b51"
    meta = {"life_agent_git": {"sha": same}, "corpus": {"digest": "D"},
            "utility": {"elicitations_sha256": "E"}, "gate": {"loo": True}}
    assert RP.verify_pin(meta, src_sha=same, corpus_digest="D", elicitations_sha="E") == []
    fails = RP.verify_pin(meta, src_sha="deadbeef", corpus_digest="D", elicitations_sha="E")
    assert any("src tree" in f for f in fails)


def test_src_tree_hash_is_empty_for_a_rev_this_checkout_does_not_have():
    """An unknown rev must not silently compare equal to nothing — main() refuses on it."""
    assert RP.src_tree_hash("0000000000000000000000000000000000000000") == ""
    assert RP.src_tree_hash("HEAD")


def test_an_acknowledged_src_drift_passes_the_pin_and_any_other_drift_still_refuses():
    """r08 Read C replays a run recorded BEFORE the fix commit, so the src trees differ by
    design. The pin may accept exactly one NAMED drift — the caller states the tree HEAD is
    expected to have — and any other mismatch still refuses. Silence is never an option:
    an empty acknowledgement must not weaken the pin."""
    # PII-OK: synthetic tree hashes
    meta = {"life_agent_git": {"sha": "a" * 40}, "corpus": {"digest": "D"},
            "utility": {"elicitations_sha256": "E"}, "gate": {"loo": True}}
    ok = RP.verify_pin(meta, src_sha="b" * 40, corpus_digest="D", elicitations_sha="E",
                       acknowledged_src="b" * 40)
    assert ok == []
    fails = RP.verify_pin(meta, src_sha="c" * 40, corpus_digest="D", elicitations_sha="E",
                          acknowledged_src="b" * 40)
    assert any("src tree" in f for f in fails)
    fails = RP.verify_pin(meta, src_sha="b" * 40, corpus_digest="D", elicitations_sha="E",
                          acknowledged_src="")
    assert any("src tree" in f for f in fails)


def test_verify_pin_refuses_when_the_run_did_not_hold_curves_out():
    """Criterion 2(e): the replay must fold curves the way the pinned run folded them. A run
    without `loo` is a different fold and the instrument may not silently adopt one."""
    meta = {"life_agent_git": {"sha": "abc"}, "corpus": {"digest": "D"},
            "utility": {"elicitations_sha256": "E"}, "gate": {"loo": False, "k": 20}}
    fails = RP.verify_pin(meta, src_sha="abc", corpus_digest="D", elicitations_sha="E")
    assert any("loo" in f for f in fails)


# --- criterion 4: the site is read from the PAYLOAD, which is what r06 could not do ----

def test_a_corroborate_tier_without_allow_new_is_s1():
    assert RP.site_of_call(_call("/probe/corroborate",
                                 {"reextract": True, "candidates": ["a"],
                                  "model": "claude-haiku-4-5"})) == "S1"


def test_allow_new_over_a_non_empty_candidate_set_is_s4_the_in_loop_re_extract():
    assert RP.site_of_call(_call("/probe/corroborate",
                                 {"reextract": True, "allow_new": True,
                                  "candidates": ["a"]})) == "S4"


def test_allow_new_over_an_empty_candidate_set_is_s5_the_k0_rescue_walk():
    """S5 is reached only when nothing grounded — an EMPTY candidate set is its signature,
    and it is what separates it from S4 in a stream where both spell `extract@<opus>`."""
    assert RP.site_of_call(_call("/probe/corroborate",
                                 {"reextract": True, "allow_new": True,
                                  "candidates": []})) == "S5"


def test_the_deliberate_probe_is_s3():
    assert RP.site_of_call(_call("/probe/deliberate", {"question": "q"})) == "S3"


def test_a_deliberate_call_carrying_allow_new_is_still_s3_because_the_path_decides_first():
    """The rehearsal's trap: `/probe/deliberate` is posted WITH `allow_new: True` and a
    non-empty candidate set — the exact shape criterion 4 assigns to S4. The endpoint is
    what names the site; the allow_new rules only ever apply to `/probe/corroborate`."""
    assert RP.site_of_call(_call("/probe/deliberate",
                                 {"question": "q", "allow_new": True,
                                  "candidates": ["a"]})) == "S3"


def test_only_a_retrieve_after_the_first_is_s2():
    """The base pass retrieves once; a SECOND retrieve is the grow — the site r06 reported
    as unmeasurable because it emits no attributed edge event."""
    calls = [_call("/retrieve", n=0), _call("/extract", n=1), _call("/retrieve", n=2)]
    assert RP.sites_in_order(calls) == ("S2",)


def test_a_non_site_call_attributes_to_nothing():
    assert RP.site_of_call(_call("/probe/subject", {"hit_keys": []})) is None
    assert RP.site_of_call(_call("/decide", {}, kind="daemon")) is None


def test_sites_in_order_preserves_repeats_because_the_tier_ladder_fires_three_times():
    """Order is the whole point of this checkpoint; a set would erase the ladder."""
    calls = [_call("/retrieve", n=0),
             _call("/probe/corroborate", {"reextract": True, "candidates": ["a"],
                                          "model": "claude-opus-4-8"}, n=1),
             _call("/probe/corroborate", {"reextract": True, "candidates": ["a"],
                                          "model": "claude-sonnet-4-6"}, n=2),
             _call("/probe/deliberate", {"question": "q"}, n=3)]
    assert RP.sites_in_order(calls) == ("S1", "S1", "S3")


# --- criterion 5: the channel trace, and what "attributed discarder" may claim ---------

def test_the_channel_trace_records_n_obs_after_every_firing():
    calls = [_call("/extract", reply={"observations": [1, 2, 3, 4, 5]}, n=0),
             _call("/probe/corroborate", {"reextract": True, "candidates": ["a"]},
                   {"observations": [], "read": "null"}, n=1),
             _call("/probe/corroborate", {"reextract": True, "candidates": ["a"]},
                   {"observations": [1], "read": "confirm"}, n=2)]
    assert RP.channel_trace(calls) == [("base", 5), ("S1", 5), ("S1", 1)]


def test_a_null_read_does_not_lower_the_channel_because_the_deployed_guard_retires_it():
    """The trace must model the DEPLOYED guard, not the wire: at S1 a null read leaves the
    channel standing. Read through `executor._null_read` so a guard change moves this."""
    reply = {"observations": [], "read": "null"}
    assert EX._null_read(reply)
    calls = [_call("/extract", reply={"observations": [1, 2]}, n=0),
             _call("/probe/corroborate", {"reextract": True, "candidates": ["a"]}, reply, n=1)]
    assert RP.channel_trace(calls) == [("base", 2), ("S1", 2)]


def test_s3_has_no_null_read_guard_so_an_empty_ok_reply_does_collapse_the_channel():
    """The §6.12 asymmetry, made explicit: the same empty reply retires at S1 and collapses
    at S3. If this ever passes with S3 keeping the channel, the executor grew a guard."""
    reply = {"observations": [], "status": "ok", "read": "null"}
    assert EX._null_read(reply), "the fixture must be one S1 WOULD retire on"
    calls = [_call("/extract", reply={"observations": [1, 2]}, n=0),
             _call("/probe/deliberate", {"question": "q"}, reply, n=1)]
    assert RP.channel_trace(calls) == [("base", 2), ("S3", 0)]
    # the same reply at S1 keeps the channel — that IS the asymmetry
    s1 = [_call("/extract", reply={"observations": [1, 2]}, n=0),
          _call("/probe/corroborate", {"reextract": True, "candidates": ["a"]}, reply, n=1)]
    assert RP.channel_trace(s1) == [("base", 2), ("S1", 2)]


def test_an_infrastructure_failure_at_s3_retires_fail_open():
    calls = [_call("/extract", reply={"observations": [1, 2]}, n=0),
             _call("/probe/deliberate", {"question": "q"},
                   {"observations": [], "status": "error"}, n=1)]
    assert RP.channel_trace(calls) == [("base", 2), ("S3", 2)]


def test_the_rescue_walk_only_grounds_the_channel_when_it_actually_mints():
    """S5 walks the menu until something grounds; a rung that mints nothing must leave the
    channel where it was, or every walked rung would read as evidence."""
    minted = [_call("/extract", reply={"observations": []}, n=0),
              _call("/probe/corroborate", {"reextract": True, "allow_new": True,
                                           "candidates": []},
                    {"observations": [1], "new_candidate": "v"}, n=1)]
    assert RP.channel_trace(minted) == [("base", 0), ("S5", 1)]
    barren = [_call("/extract", reply={"observations": []}, n=0),
              _call("/probe/corroborate", {"reextract": True, "allow_new": True,
                                           "candidates": []},
                    {"observations": [1]}, n=1)]     # observations, but nothing minted
    assert RP.channel_trace(barren) == [("base", 0), ("S5", 0)]


def test_the_attributed_discarder_is_the_firing_that_took_the_channel_to_its_committed_size():
    trace = [("base", 5), ("S1", 5), ("S1", 1), ("S4", 1)]
    assert RP.attributed_discarder(trace, committed_n_obs=1) == ("S1",)


def test_every_candidate_is_named_when_more_than_one_firing_could_have_done_it():
    """Ambiguity that survives the payload read is REPORTED as ambiguity (criterion 4). Here
    the channel falls to 2 twice — a later firing raised it and a later one took it back — so
    both firings are candidates and neither may be picked."""
    trace = [("base", 5), ("S1", 2), ("S4", 3), ("S3", 2)]
    assert RP.attributed_discarder(trace, committed_n_obs=2) == ("S1", "S3")


def test_a_replace_that_does_not_lower_the_channel_is_not_a_discarder():
    """S4 replacing 1 observation with 1 is a replace, but it discarded nothing — naming it
    would inflate every site's attributed count with size-preserving firings."""
    trace = [("base", 5), ("S1", 1), ("S4", 1)]
    assert RP.attributed_discarder(trace, committed_n_obs=1) == ("S1",)


def test_no_discarder_is_named_when_the_channel_never_fell():
    assert RP.attributed_discarder([("base", 3), ("S1", 3)], committed_n_obs=3) == ()


# --- criterion 7(a): RETIRE is ENACTED through the deployed guard, never reimplemented --

def test_retire_at_a_corroborate_site_yields_a_reply_the_deployed_guard_calls_null():
    out = RP.retire_reply("S1", {"observations": [1], "read": "confirm", "value": "v"})
    assert EX._null_read(out), "the rewrite must satisfy executor._null_read itself"


def test_retire_at_the_deliberate_edge_yields_a_status_the_executor_fails_open_on():
    out = RP.retire_reply("S3", {"observations": [1], "status": "ok", "value": "v"})
    assert out.get("status") != "ok"


def test_retire_at_the_rescue_walk_withholds_the_mint_because_s5_discards_nothing():
    """S5 has no channel to keep — retire-not-replace there can only mean the minted
    candidate does not enter (§6.12's table: it mints, never discards)."""
    out = RP.retire_reply("S5", {"observations": [1], "new_candidate": "v"})
    assert not out.get("new_candidate")


def test_retire_leaves_a_non_site_reply_untouched():
    reply = {"hits": [1, 2]}
    assert RP.retire_reply(None, reply) == reply


# --- criterion 7(b): JOIN pools through the DEPLOYED §5 dedup --------------------------

def test_the_dedup_key_is_absent_from_wire_observations_which_is_why_join_is_a_bound():
    """Criterion 7(b) as amended. `/extract` returns ABSTRACT observations and the corroborate
    handler synthesises one with no quote — §5 clusters on the quote, so its guard cannot reach
    the thing a JOIN would pool. A live predicate, not a comment: a wire that ever grows the key
    turns the deployed rule back on by itself."""
    assert not RP.dedup_key_available([{"reports": 0, "time_factor": 1.0}])
    assert RP.dedup_key_available([{"reports": 0, "quote": "x"}])


def test_join_calls_the_deployed_dedup_whenever_the_key_is_there(monkeypatch):
    """Where §5 CAN apply, it is `lookup.dedup_correlated` that applies it — never a copy."""
    seen: list[list] = []

    def _spy(obs):
        seen.append(list(obs))
        return list(obs)

    monkeypatch.setattr(LK, "dedup_correlated", _spy)
    RP.join_observations([{"quote": "a"}], [{"quote": "b"}])
    assert seen == [[{"quote": "a"}, {"quote": "b"}]]


def test_join_without_the_key_pools_raw_and_is_therefore_an_upper_bound(monkeypatch):
    """No key ⇒ no dedup ⇒ every forwarded copy counts as an independent witness. That is the
    most favourable case joining could ever have, and the instrument must not dress it as an
    estimate by quietly deduping on something else."""
    def _boom(obs):
        raise AssertionError("§5 must not be applied to observations it cannot cluster")

    monkeypatch.setattr(LK, "dedup_correlated", _boom)
    assert RP.join_observations([{"reports": 0}], [{"reports": 1}]) == [{"reports": 0},
                                                                        {"reports": 1}]


# --- criterion 6/8: the floor, and the bar r05 and r06 both used ----------------------

def test_excess_over_floor_is_reach_minus_what_the_noise_floor_predicts():
    assert RP.excess_over_floor(exposure=26, reach=11, floor=8 / 29) == 3.8


def test_a_site_under_the_bar_of_five_is_known_and_uncovered_not_a_buy():
    """The bar of 5 is inherited from r05 and r06 so all three checkpoints compare."""
    assert RP.verdict(excess=0.2, r06_above_floor=True)[0] == "KNOWN-AND-UNCOVERED"
    assert RP.verdict(excess=5.0, r06_above_floor=True)[0] == "BUILD+PRICE"


def test_r07_may_not_buy_a_site_r06_refused():
    """Owner ruling 2026-08-22: r06's criterion 8 is not reopened. r07 adds a reading; it
    cannot promote a site the earlier checkpoint left below its own floor."""
    assert RP.verdict(excess=9.0, r06_above_floor=False)[0] == "KNOWN-AND-UNCOVERED"


# --- criterion 9(c): exclusions are named, and cold-mid-loop is evidence ---------------

def test_cold_at_start_and_cold_mid_loop_are_counted_apart():
    """A derivation that goes cold AFTER the loop began means run 10 never made that call
    (a §18.9 record is written on success) — divergence, not merely an exclusion."""
    assert RP.cold_kind(n_calls_before=0) == "cold-at-start"
    assert RP.cold_kind(n_calls_before=7) == "cold-mid-loop"


# --- criterion 3: the spend tripwire ---------------------------------------------------

def test_a_reply_carrying_cost_aborts_the_read():
    import pytest
    meter = RP.SpendMeter()
    meter.observe({"cost_usd": 0.0})
    with pytest.raises(RP.WouldSpendError):
        meter.observe({"cost_usd": 0.01})


# --- the four defects the three-question rehearsal exposed, each pinned ------------------

def test_a_cold_deliberate_escapes_the_executors_blanket_exception_handler():
    """`run_pass` wraps its deliberate post in `except Exception` and treats a raise as an
    infrastructure fail-open. A refusal that inherits from Exception is therefore SWALLOWED and
    read as data. ColdDeliberate must be a BaseException so the exclusion survives the loop."""
    assert issubclass(RP.ColdDeliberate, BaseException)
    assert not issubclass(RP.ColdDeliberate, Exception)
    try:
        raise RP.ColdDeliberate("x")
    except Exception:                      # the executor's own handler shape
        raise AssertionError("the executor's handler would have swallowed it") from None
    except RP.ColdDeliberate:
        pass


def test_the_r06_gate_mirrors_r06s_published_verdict_and_not_a_re_reading_of_its_floor():
    """r06's criterion 8 bought S1, S3, S4 and S5 and left S2 NOT READ. The owner ruled that
    verdict closed; encoding my own re-reading of its floor here would reopen it sideways."""
    assert frozenset({"S1", "S3", "S4", "S5"}) == RP.R06_BOUGHT
    assert "S2" not in RP.R06_BOUGHT
    s2_gate = "S2" in RP.R06_BOUGHT
    assert RP.verdict(excess=99.0, r06_above_floor=s2_gate)[0] == "KNOWN-AND-UNCOVERED"


def test_cold_kind_needs_the_calls_that_already_happened_to_mean_anything():
    """The rehearsal read every failure as cold-at-start because the tape was reassigned by the
    call that raised. The caller owns the tape now; this pins the distinction it exists for."""
    assert RP.cold_kind(n_calls_before=0) != RP.cold_kind(n_calls_before=1)
    assert RP.cold_kind(n_calls_before=12) == "cold-mid-loop"


def test_replay_takes_the_tape_from_its_caller_so_a_raise_leaves_the_evidence_behind():
    import inspect
    sig = inspect.signature(RP.replay)
    assert "tape" in sig.parameters, "the tape must be the caller's, not a local"
    assert sig.return_annotation != "tuple[dict[str, Any], list[Call]]", (
        "returning the tape means a raise loses it")


def test_the_arms_of_one_question_share_a_retrieval_draw():
    """§6.13 makes at least one question's retrieval a lottery. An arm that differed because it
    DREW differently would be a confound and not a counterfactual, so the draw is memoised per
    (question, breadth) across a question's arms. The double run still draws afresh, which is
    where criterion 9(b) looks for instability."""
    import inspect
    assert "draws" in inspect.signature(RP.make_transport).parameters
    assert "draws" in inspect.signature(RP.replay).parameters
    src = inspect.getsource(RP.audit_rows)
    assert "draws: dict[str, Any] = {}" in src, "the memo must be per QUESTION, not global"


def test_the_renderer_refuses_to_emit_a_corpus_value():
    """Criterion 9(d) as a predicate, not an intention. A recorded reply carries corpus text and
    the report may never contain a value from it — so if one ever reaches the render, the render
    fails loudly rather than being scrubbed afterwards."""
    import pytest
    row = RP.Row(qid="q2-001", gold="ACME-1234")   # PII-OK: synthetic gold
    row.deployed = RP.Arm(action="report", leader="ACME-1234", n_obs=1, n_docs=1,
                          p_none=0.1, eu=0.5, credences=[0.9])
    ok = RP.render([row], [], run_id="r", k=20, pin_notes=["a clean note"],
                   modes=("deployed",), r06_floor_sites=frozenset(), unstable=[])
    assert "ACME-1234" not in ok
    # every free-text channel into the report is a leak channel; the pin notes are one
    with pytest.raises(AssertionError, match=r"9\(d\)"):
        RP.render([row], [], run_id="r", k=20, pin_notes=["staged from .../ACME-1234/x"],
                  modes=("deployed",), r06_floor_sites=frozenset(), unstable=[])


def test_the_transport_passes_a_null_reply_through_instead_of_inventing_one():
    """`/route` answers NULL for a question the lookup family does not route, and the executor
    branches on exactly that. A transport that coerces None to {} hands the loop a non-None
    empty dict; it proceeds and dies on the first field it reads. Found by the first full read,
    which crashed on `KeyError: 'time_indexed'` rather than routing to the narrative family."""
    seen: list = []

    class _Deps:
        pass

    def _dispatch(_deps, _method, path, _body):
        return (200, None) if path == "/route" else (200, {"ok": True})

    import life_agent.bridge.server as SRV
    real = SRV.dispatch
    SRV.dispatch = _dispatch
    try:
        post, _get = RP.make_transport(_Deps(), "http://d", RP.SpendMeter(), seen,
                                       mode="deployed")
        assert post("bridge:/route", {"question": "q"}) is None
        assert post("bridge:/extract", {}) == {"ok": True}
    finally:
        SRV.dispatch = real
    assert [c.path for c in seen] == ["/route", "/extract"]


# --- criterion 9(d): the leak check must not refuse every report it protects ------------

def test_a_one_character_gold_does_not_make_every_report_unpublishable():
    """A full battery's render refused on three values, all one to three characters: a
    substring test on a 1-char gold matches an `n_obs=1` in any report. Short and numeric
    values match on WORD BOUNDARIES instead — still catching a real emission."""
    row = RP.Row(qid="q2-001", gold="7")           # PII-OK: synthetic 1-char gold
    # the structured tables emit counts; a gold of 7 is indistinguishable from a count of 7
    assert RP.leak_check("the channel held n_obs=7 observations", [row], freetext="") == []
    # but the free-text channels are still checked for it
    assert RP.leak_check("report", [row], freetext="staged from .../7/x") != []


def test_a_distinctive_gold_is_still_caught_anywhere_in_the_text():
    row = RP.Row(qid="q2-002", gold="ACME-1234")   # PII-OK: synthetic gold
    # a distinctive value is checked against the WHOLE report, free text or not
    assert RP.leak_check("| q2-002 | ACME-1234 |", [row], freetext="") != []


def test_the_leak_failure_names_shapes_and_never_the_value():
    row = RP.Row(qid="q2-003", gold="ACME-1234")   # PII-OK: synthetic gold
    shapes = RP.leak_check("ACME-1234", [row], freetext="")
    assert shapes == ["len=9/alphanumeric"]
    assert not any("ACME" in s for s in shapes)


def test_rows_survive_a_render_that_raises():
    """dump_rows/load_rows exist so a criterion-9(d) refusal costs seconds, not an hour of
    replaying. Round-trip everything the report reads."""
    row = RP.Row(qid="q2-011", gold="g", variants=["v"])
    row.sites = ("S1", "S3")
    row.trace = [("base", 5), ("S3", 1)]
    row.discarder = ("S3",)
    row.cold_arms = ("retire",)
    row.deployed = RP.Arm(action="report", leader="g", n_obs=1, n_docs=1, p_none=0.1,
                          eu=0.5, credences=[0.9])
    row.recorded_action = "report"
    row.fidelity_agrees = True
    back, excl = RP.load_rows_from_text(RP.dump_rows([row], ["q2-007 (no gold)"]))
    assert excl == ["q2-007 (no gold)"]
    assert (back[0].qid, back[0].sites, back[0].trace, back[0].discarder,
            back[0].cold_arms) == (row.qid, row.sites, row.trace, row.discarder,
                                   row.cold_arms)
    assert back[0].deployed == row.deployed


def test_the_refusing_seam_covers_the_instruments_that_build_their_own_client(monkeypatch):
    """`deps.client` only covers the seams the bridge threads a client through. `core/subject`
    and `core/temporal_intent` import `instrument_client` by name and construct their OWN on a
    cache miss, so a replay that patches nothing is no-spend by LUCK — whichever refusal fires
    first — not by contract. Found live: a row that used to refuse at a cold §18.9 derivation
    warmed, ran on, and reached the subject seam, which tried to spend."""
    from life_agent.core import instrument as INSTR
    from life_agent.core import subject as SUBJ
    from life_agent.core import temporal_intent as TI

    for mod in (INSTR, SUBJ, TI):                     # restored by monkeypatch at teardown
        monkeypatch.setattr(mod, "instrument_client", mod.instrument_client)
    RP.refuse_live_instrument_seams("test-engine")

    for mod in (INSTR, SUBJ, TI):
        client = mod.instrument_client("any-model")
        assert client.engine_version == "test-engine"
        with pytest.raises(WouldSpendError):
            client.complete("prompt", {"type": "object"})
