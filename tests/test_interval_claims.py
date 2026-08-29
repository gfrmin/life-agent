"""r30b — the claim space: interval claims inside the argmax.

Frozen criteria live in `docs/unification/reports/r30b-interval-claims.md`; each test below
names the criterion it pins. The lever: a `quantity` question whose evidence disperses over
near-agreeing numeric candidates has no action that is both honest and useful (the crisp
report is 0-1 wrong, so the argmax correctly withholds). An INTERVAL claim is that action —
one tabular row per proposal, valued by the r21-frozen Winkler grade through the one assert
atom, ranked by the same `optimise` call as every other action.

Every quantity below is synthetic.  # PII-OK: synthetic quantities

Run: uv run --project . python -m pytest tests/test_interval_claims.py
"""
from __future__ import annotations

import pytest

from life_agent.core import answer_shape as AS
from life_agent.core import decide as DEC_ATOM
from life_agent.core import decisions as DEC
from life_agent.core import gate as G
from life_agent.core import lookup as LK

# u_assert(p) = 6p - 5 under this Ū — the arithmetic every expectation below is read against.
UB: dict[str, float] = {"u_correct": 1.0, "u_abstain": 0.0, "u_wrong": -5.0,
                        "u_wrong_scoped": -2.0, "u_hedged": 0.4, "lambda_int": 1.0,
                        "kappa_att": 0.05}

# A dispersed quantity posterior: two near-agreeing values carry the mass, one far outlier
# does not.  # PII-OK: synthetic quantities
FAR = ["10", "200", "210"]
FAR_W = [0.05, 0.5, 0.4, 0.05]          # candidates then NONE

# Two near-agreeing values — the class r29 measured as structurally abstained.
NEAR = ["1000", "1004"]
NEAR_W = [0.45, 0.45, 0.10]


def _eu(values: list[float], weights: list[float]) -> float:
    """The engine's expectation over a tabular row — the dot product `optimise` maximises."""
    return sum(v * w for v, w in zip(values, weights, strict=True))


def _by_name(candidates: list[str], shape: str = AS.QUANTITY) -> dict[str, object]:
    return {o.name: o for o in DEC_ATOM.interval_options(candidates, UB, shape=shape)}


# --- C7: one numeric parser --------------------------------------------------------------

@pytest.mark.parametrize(("text", "expected"), [
    ("210", 210.0), ("ILS 1,234.50", 1234.5), ("-4", -4.0), ("3 months", 3.0),
    ("no digits here", None), ("", None), (None, None),
])
def test_numeric_value_parses_the_first_number(text: object, expected: float | None) -> None:
    assert AS.numeric_value(text) == expected


def test_numeric_value_is_the_only_parser_the_graders_use(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """C7 — run_eval and aggregate_eval BIND the decision-side parser, never a second copy.

    Agreement is not enough: two identical regexes agree until one is edited. This drives the
    binding — a redefined parser must be visible through BOTH grading entry points, which is
    false the moment either holds a copy of its own."""
    import importlib
    run_eval = importlib.import_module("run_eval")
    agg = importlib.import_module("aggregate_eval")
    # aggregate_eval binds by IDENTITY — the strongest form; there is nothing to diverge.
    assert agg._numeric is AS.numeric_value
    # run_eval folds over gold + variants, so identity cannot hold; drive the binding instead.
    monkeypatch.setattr(AS, "numeric_value", lambda _text: 42.0)
    assert run_eval._numeric_gold("210", []) == 42.0


# --- C4: one loss ------------------------------------------------------------------------

def test_the_winkler_loss_has_one_home() -> None:
    """C4 — gate.realised_aggregate IS decide.realised_aggregate (identity, not a copy)."""
    assert G.realised_aggregate is DEC_ATOM.realised_aggregate


def test_the_winkler_constants_have_one_home() -> None:
    """C4 — a forked alpha/scale is a drift-gate failure, not a refinement."""
    assert G._WINKLER_ALPHA is DEC_ATOM._WINKLER_ALPHA
    assert G._WINKLER_SCALE is DEC_ATOM._WINKLER_SCALE


# --- C2: the shape gate ------------------------------------------------------------------

def test_no_interval_rows_off_shape() -> None:
    """C2 — a non-quantity question's action set is byte-identical to pre-r30b."""
    for shape in (AS.EXACT, AS.SET, AS.THRESHOLD):
        assert DEC_ATOM.interval_options(FAR, UB, shape=shape) == ()


def test_no_interval_rows_below_two_distinct_numeric_values() -> None:
    """C2 — an interval needs a range; one value (or none) cannot make one."""
    assert DEC_ATOM.interval_options(["200"], UB, shape=AS.QUANTITY) == ()
    assert DEC_ATOM.interval_options(["200", "200"], UB, shape=AS.QUANTITY) == ()
    assert DEC_ATOM.interval_options(["red", "blue"], UB, shape=AS.QUANTITY) == ()


def test_a_non_numeric_candidate_does_not_block_the_others() -> None:
    opts = DEC_ATOM.interval_options(["200", "later", "210"], UB, shape=AS.QUANTITY)
    assert len(opts) == 1
    assert (opts[0].lo, opts[0].hi) == (200.0, 210.0)


# --- D3: the proposal set ----------------------------------------------------------------

def test_proposals_are_the_non_degenerate_contiguous_ranges() -> None:
    """D3 — m(m-1)/2 rows; the degenerate range is report_j's claim, not an interval's."""
    opts = DEC_ATOM.interval_options(FAR, UB, shape=AS.QUANTITY)
    assert [(o.lo, o.hi) for o in opts] == [(10.0, 200.0), (10.0, 210.0), (200.0, 210.0)]
    assert all(o.lo < o.hi for o in opts)


def test_proposal_names_are_deterministic_value_ranks() -> None:
    opts = DEC_ATOM.interval_options(FAR, UB, shape=AS.QUANTITY)
    assert [o.name for o in opts] == ["interval_0_1", "interval_0_2", "interval_1_2"]
    assert all(n.startswith(DEC_ATOM.INTERVAL_PREFIX) for n in (o.name for o in opts))


def test_endpoint_labels_echo_the_candidate_display_string() -> None:
    """D7 — the render never reformats a value (no invented precision or currency)."""
    opts = DEC_ATOM.interval_options(["ILS 210", "ILS 200"], UB, shape=AS.QUANTITY)
    assert (opts[0].lo_label, opts[0].hi_label) == ("ILS 200", "ILS 210")


def test_the_proposal_grid_is_capped_and_posterior_blind() -> None:
    """D3 — a coarsened grid keeps both endpoints and never reads a credence."""
    values = [str(v) for v in range(100, 100 + 3 * 20, 3)]  # PII-OK: synthetic quantities
    opts = DEC_ATOM.interval_options(values, UB, shape=AS.QUANTITY)
    m = DEC_ATOM.MAX_INTERVAL_VALUES
    assert len(opts) == m * (m - 1) // 2
    assert opts[0].lo == 100.0 and max(o.hi for o in opts) == 157.0


# --- D1: the row arithmetic --------------------------------------------------------------

def test_the_row_is_u_assert_of_the_winkler_grade_at_every_atom() -> None:
    opt = _by_name(FAR)["interval_1_2"]          # [200, 210]
    expected = [DEC_ATOM.u_assert(DEC_ATOM.realised_aggregate(200.0, 210.0, g)[0], UB)
                for g in (10.0, 200.0, 210.0)] + [UB["u_wrong"]]
    assert list(opt.values) == pytest.approx(expected)


def test_none_and_non_numeric_atoms_pay_u_wrong() -> None:
    opts = DEC_ATOM.interval_options(["200", "later", "210"], UB, shape=AS.QUANTITY)
    assert opts[0].values[1] == UB["u_wrong"]     # the non-numeric candidate
    assert opts[0].values[-1] == UB["u_wrong"]    # NONE


def test_a_row_spans_every_atom_including_none() -> None:
    for o in DEC_ATOM.interval_options(FAR, UB, shape=AS.QUANTITY):
        assert len(o.values) == len(FAR) + 1


# --- C1: width pays INSIDE the action ----------------------------------------------------

def test_width_pays_inside_the_action_so_the_widest_does_not_dominate() -> None:
    """C1 — RED under `x := 1.0 if lo <= g <= hi else 0.0` (0-1 containment), where the
    widest proposal weakly dominates every narrower one. Here the tight covering interval
    must win, because widening is paid for inside the Winkler grade itself."""
    opts = _by_name(FAR)
    tight = _eu(list(opts["interval_1_2"].values), FAR_W)     # [200, 210]
    widest = _eu(list(opts["interval_0_2"].values), FAR_W)    # [10, 210]
    assert tight > widest
    assert tight == max(_eu(list(o.values), FAR_W) for o in opts.values())


def test_widening_over_a_covered_leader_strictly_costs() -> None:
    """C1 — the penalty is monotone in width once the mass is already covered."""
    a = DEC_ATOM.realised_aggregate(200.0, 210.0, 205.0)[0]
    b = DEC_ATOM.realised_aggregate(150.0, 260.0, 205.0)[0]
    assert a > b


def test_a_covering_interval_beats_a_crisp_report_on_near_agreement() -> None:
    """The lever's intended win: near-agreeing candidates make the interval the argmax,
    where every crisp report is below the assert bar and the decision is a withholding."""
    rows = LK.action_utilities(NEAR_W, UB,
                               intervals=DEC_ATOM.interval_options(NEAR, UB,
                                                                   shape=AS.QUANTITY))
    best = max(rows, key=lambda name: _eu(rows[name], NEAR_W))
    assert best.startswith(DEC_ATOM.INTERVAL_PREFIX)
    assert _eu(rows[best], NEAR_W) > _eu(rows["abstain"], NEAR_W)
    assert _eu(rows["report_0"], NEAR_W) < _eu(rows["abstain"], NEAR_W)


# --- C3 / C5: one declaration, two lanes; the vocabulary does not grow --------------------

def test_action_utilities_carries_the_options_verbatim() -> None:
    """C3 — lookup does not re-derive a row; it places what decide built."""
    opts = DEC_ATOM.interval_options(FAR, UB, shape=AS.QUANTITY)
    rows = LK.action_utilities(FAR_W, UB, intervals=opts)
    for o in opts:
        assert rows[o.name] == list(o.values)


def test_action_utilities_without_intervals_is_byte_identical() -> None:
    """C2 — the default path is unchanged."""
    assert LK.action_utilities(FAR_W, UB) == LK.action_utilities(FAR_W, UB, intervals=())


def test_the_response_vocabulary_does_not_grow() -> None:
    """C5 — an interval is a `report` at a different precision, not a new speech act."""
    assert frozenset({"report", "report_scoped", "hedge",
                      "ask_clarify", "abstain"}) == DEC.ACTIONS
    assert DEC.LOOKUP_ACTION_ORDER == ("report", "hedge", "ask_clarify", "abstain",
                                       "report_scoped")
    assert G.ASSERT_ACTIONS | G.WITHHOLD_ACTIONS == DEC.ACTIONS
    assert not any(a.startswith(DEC_ATOM.INTERVAL_PREFIX) for a in DEC.ACTIONS)


def test_an_interval_winner_maps_to_report_and_carries_its_claim() -> None:
    """C5/D5 — the wire name maps back to the one speech act plus the claim itself."""
    opts = DEC_ATOM.interval_options(FAR, UB, shape=AS.QUANTITY)
    assert DEC_ATOM.interval_by_name(opts, "interval_1_2") is opts[2]
    assert DEC_ATOM.interval_by_name(opts, "report_0") is None


# --- the lookup lane: decide → report + claim, and the render ----------------------------

class _ScriptedBrain:
    """A brain whose `optimise` returns a named action — the engine's choice, scripted, so the
    mapping from a winning row key back to the one speech act is pinned without a live skin."""

    def __init__(self, action: str) -> None:
        self.action = action
        self.rows: dict[str, list[float]] = {}

    def optimise(self, _state_id: str, *, actions: dict, preference: dict
                 ) -> tuple[str, float]:
        self.rows = {k: v["values"] for k, v in preference["actions"].items()}
        return self.action, 0.75

    def destroy_state(self, _state_id: str) -> None:
        return None


def test_decide_maps_an_interval_winner_to_report_with_its_claim() -> None:
    """C5/D5 — the engine picks `interval_a_b`; the caller receives the ONE speech act
    (`report`) plus the claim it names. The wire name never escapes the seam."""
    opts = DEC_ATOM.interval_options(FAR, UB, shape=AS.QUANTITY)
    brain = _ScriptedBrain("interval_1_2")
    action, eu, scoped_j, interval = LK.decide(brain, "s1", FAR_W, UB, intervals=opts)
    assert (action, scoped_j) == ("report", None)
    assert eu == 0.75
    assert interval is not None
    assert (interval.lo, interval.hi) == (200.0, 210.0)
    assert set(opts).issubset({*[o for o in opts]})           # the priced set is what it ranked
    assert "interval_1_2" in brain.rows


def test_decide_without_intervals_is_unchanged() -> None:
    """C2 — the default path ranks exactly the pre-r30b rows and returns no claim."""
    brain = _ScriptedBrain("report_0")
    action, _eu, scoped_j, interval = LK.decide(brain, "s1", FAR_W, UB)
    assert (action, scoped_j, interval) == ("report", None, None)
    assert not any(k.startswith(DEC_ATOM.INTERVAL_PREFIX) for k in brain.rows)


def test_render_states_the_interval_with_its_coverage_credence() -> None:
    """D7 — endpoints echo the candidate display strings; the credence is the claim's own
    coverage mass (display and record only, never a decision input — C8)."""
    opt = DEC_ATOM.interval_options(FAR, UB, shape=AS.QUANTITY)[2]     # [200, 210]
    result = LK.LookupResult(
        question="how much?", construct="amount", action="report", eu=0.75,
        candidates=("200", "210", "10"), credences=(0.5, 0.4, 0.05), p_none=0.05,
        observations=(), n_hits=3, n_indeterminate=0, utility_fold_version="v",
        answer_cache_key="k", rendered="", interval=opt, interval_p=0.9)
    body = LK.render(result)
    assert LK.GRAMMAR["report_interval"].format(lo="200", hi="210", p=0.9,
                                                cites="").rstrip() in body
    assert "decision report" in body           # the footer names the one speech act


def test_the_coverage_credence_is_the_covered_mass() -> None:
    """C8 — one derivation, and it is a SUM over the posterior, never an argmax."""
    assert LK.interval_coverage(("200", "210", "10"), (0.5, 0.4, 0.05),
                                lo=200.0, hi=210.0) == pytest.approx(0.9)
    assert LK.interval_coverage(("200", "210", "10"), (0.5, 0.4, 0.05),
                                lo=0.0, hi=1000.0) == pytest.approx(0.95)


# --- the executor lane: the same rows, on the wire ---------------------------------------

_Q_AMOUNT = "how much is the total?"          # classifies `quantity`
_HITS_Q = [{"artifact_cache_key": "d0", "chunk_text": "total 1000"},   # PII-OK: synthetic
           {"artifact_cache_key": "d1", "chunk_text": "total 1004"}]   # PII-OK: synthetic
_EXTRACT_Q = {
    "candidates": ["1000", "1004"],           # PII-OK: synthetic quantities
    "observations": [{"reports": 0, "group": 0, "authority": 0.9, "subject_factor": 1.0,
                      "time_factor": 1.0},
                     {"reports": 1, "group": 1, "authority": 0.9, "subject_factor": 1.0,
                      "time_factor": 1.0}],
    "rho": 0.7, "era_split": False, "indeterminate": 0, "half_life_years": 5.0}


_ABSTAIN = {"effector": "abstain", "value": None, "credences": [0.45, 0.45],
            "p_none": 0.10, "eu": 0.0, "n_extra_actions": 1}


def _executor_fake(decides: list[dict], **kw: object):
    """A scripted bridge + daemon. The withholding decides are supplied twice: the
    report-economy latch (r15 A5) offers the grow block once after a terminal withholding,
    which costs a second decide."""
    from tests.test_executor import FakeServices
    return FakeServices(route={"construct": "total", "time_indexed": False},
                        hits=_HITS_Q, extract=_EXTRACT_Q, decides=decides, **kw)


def _executor_loop(fake: object, question: str = _Q_AMOUNT) -> dict:
    from life_agent.core import executor as EX
    return EX.decide_via_loop(question, 20, bridge="http://bridge",
                              daemon="http://daemon", post=fake.post, get=fake.get)


def test_the_daemon_receives_the_same_rows_the_in_process_lane_ranks() -> None:
    """C3 — one declaration, two lanes: the wire's `extra_actions` are byte-identical to the
    rows `action_utilities` places, and the daemon supplies no utility arithmetic of its own."""
    fake = _executor_fake([_ABSTAIN, _ABSTAIN])
    _executor_loop(fake)
    posted = fake.posted("/decide")[0]
    expected = DEC_ATOM.interval_options(["1000", "1004"], fake.utility, shape=AS.QUANTITY)
    assert posted["extra_actions"] == [{"name": o.name, "act": "report",
                                        "values": list(o.values)} for o in expected]


def test_the_wire_is_unchanged_off_shape() -> None:
    """C2 — a non-quantity question posts no `extra_actions` key at all."""
    fake = _executor_fake([_ABSTAIN, _ABSTAIN])
    _executor_loop(fake, "what is my library card number?")
    assert "extra_actions" not in fake.posted("/decide")[0]


def test_an_interval_effector_becomes_a_report_carrying_its_claim() -> None:
    """C5/D6 — the wire name maps to the one speech act; the claim lands in the r21
    `aggregate.totals` shape the frozen grader already reads."""
    opts = DEC_ATOM.interval_options(["1000", "1004"], _executor_fake([]).utility,
                                     shape=AS.QUANTITY)
    fake = _executor_fake([{"effector": opts[0].name, "value": None,
                            "credences": [0.45, 0.45], "p_none": 0.10, "eu": 0.4,
                            "n_extra_actions": 1}])
    view = _executor_loop(fake)
    assert view["effector"] == "report"
    assert view["aggregate"]["claim"] == "interval"
    assert view["aggregate"]["totals"] == [{"lo": 1000.0, "hi": 1004.0, "point": 1002.0,
                                            "grid_coarsened": False}]
    assert view["asserted"] == ["1000", "1004"]


def test_a_non_interval_view_carries_no_aggregate_key() -> None:
    """D6 — every existing view is byte-identical: the key appears only when one was chosen."""
    fake = _executor_fake([_ABSTAIN, _ABSTAIN])
    assert "aggregate" not in _executor_loop(fake)


def test_the_gate_grades_an_interval_view_through_the_frozen_winkler_branch() -> None:
    """D5 — r21's already-frozen grading branch receives the claim with NO change: the
    action stays `report` and the continuous grade rides `RealisedResponse.x`."""
    import importlib
    run_eval = importlib.import_module("run_eval")
    view = {"effector": "report", "asserted": ["1000", "1004"], "candidates": ["1000"],
            "spend_usd": 0.0,
            "aggregate": {"claim": "interval",
                          "totals": [{"lo": 1000.0, "hi": 1004.0, "point": 1002.0}]}}
    resp = run_eval._typed_response_executor(view, {"answer": "1002"})   # PII-OK: synthetic
    assert (resp.action, resp.correct) == ("report", True)
    assert resp.x == pytest.approx(G.realised_aggregate(1000.0, 1004.0, 1002.0)[0])


def test_the_interval_excludes_gold_class_is_visible_from_birth() -> None:
    """C6 — the named wrong-commit class this lever can create: a confident range that does
    not contain the truth. It grades as an incorrect report and is countable by its own name."""
    view = {"effector": "report", "asserted": ["1000", "1004"], "candidates": ["1000"],
            "spend_usd": 0.0,
            "aggregate": {"claim": "interval",
                          "totals": [{"lo": 1000.0, "hi": 1004.0, "point": 1002.0}]}}
    import importlib
    run_eval = importlib.import_module("run_eval")
    resp = run_eval._typed_response_executor(view, {"answer": "2000"})   # PII-OK: synthetic
    assert resp.correct is False
    assert G.realised_aggregate(1000.0, 1004.0, 2000.0)[1] is True


def test_the_executor_renders_the_interval_in_the_shared_grammar() -> None:
    """D7 — one grammar across surfaces: the executor lane renders the SAME contract string
    the in-process family renders, so the owner sees one reply whichever path answered."""
    from life_agent.core import executor as EX
    view = {"effector": "report", "asserted": ["1000", "1004"],
            "candidates": ["1000", "1004"], "credences": [0.45, 0.45], "p_none": 0.10,
            "eu": 0.4, "n_obs": 2, "hits": _HITS_Q, "n_indeterminate": 0,
            "aggregate": {"claim": "interval", "p": 0.9,
                          "totals": [{"lo": 1000.0, "hi": 1004.0, "point": 1002.0}]}}
    body = EX.render_view(view)
    assert body.startswith(LK.GRAMMAR["report_interval"].format(
        lo="1000", hi="1004", p=0.9, cites="[1][2]").rstrip())


def test_the_executor_render_is_unchanged_without_a_claim() -> None:
    """C2 — a plain report renders exactly as before."""
    from life_agent.core import executor as EX
    view = {"effector": "report", "asserted": ["1000"], "candidates": ["1000"],
            "credences": [0.95], "p_none": 0.05, "eu": 0.9, "n_obs": 1, "hits": _HITS_Q,
            "n_indeterminate": 0}
    assert EX.render_view(view).startswith(
        LK.GRAMMAR["report"].format(value="1000", p=0.95, cites="[1]"))


def test_a_decider_that_cannot_rank_the_rows_fails_loud() -> None:
    """A daemon predating `extra_actions` ignores unknown keys, so the body would price rows
    nothing ranks and the reading would silently measure the pre-r30b action set. Silent
    degradation is the one outcome a gate reading cannot survive: it fails loud instead."""
    fake = _executor_fake([{"effector": "abstain", "value": None, "credences": [0.45, 0.45],
                            "p_none": 0.10, "eu": 0.0}])          # no `n_extra_actions` echo
    with pytest.raises(RuntimeError, match="extra_actions"):
        _executor_loop(fake)


def test_a_decider_that_ranks_them_is_accepted() -> None:
    fake = _executor_fake([{"effector": "abstain", "value": None, "credences": [0.45, 0.45],
                            "p_none": 0.10, "eu": 0.0, "n_extra_actions": 1},
                           {"effector": "abstain", "value": None, "credences": [0.45, 0.45],
                            "p_none": 0.10, "eu": 0.0, "n_extra_actions": 1}])
    assert _executor_loop(fake)["effector"] == "abstain"


def test_a_coarsened_grid_is_on_the_record_not_silent() -> None:
    """D3 — a bound cap that nothing records reads as "these were all the proposals". Every
    option built off a coarsened grid says so, and the claim's own record carries it."""
    small = DEC_ATOM.interval_options(FAR, UB, shape=AS.QUANTITY)
    assert all(not o.grid_coarsened for o in small)
    many = [str(v) for v in range(100, 100 + 3 * 20, 3)]   # PII-OK: synthetic quantities
    wide = DEC_ATOM.interval_options(many, UB, shape=AS.QUANTITY)
    assert all(o.grid_coarsened for o in wide)
    assert wide[0].claim()["grid_coarsened"] is True
    assert small[0].claim()["grid_coarsened"] is False


def test_an_interval_commit_does_not_trip_the_withhold_only_grow_latch() -> None:
    """An interval is a COMMIT, so the report-economy latch (r15 A5 — offer recall growth
    only after a withholding) must not fire on it. That is the same fact the wire's `act`
    field declares to the daemon's guards, checked here on the body's own loop."""
    opts = DEC_ATOM.interval_options(["1000", "1004"], _executor_fake([]).utility,
                                     shape=AS.QUANTITY)
    fake = _executor_fake([{"effector": opts[0].name, "value": None,
                            "credences": [0.45, 0.45], "p_none": 0.10, "eu": 0.4,
                            "n_extra_actions": 1}])          # exactly ONE decide is scripted
    view = _executor_loop(fake)
    assert view["effector"] == "report"
    assert len(fake.posted("/decide")) == 1
    assert all("grow" not in p for p in fake.posted("/decide"))


def test_the_rows_track_a_candidate_the_loop_mints() -> None:
    """The loop may APPEND a candidate mid-question (a strong re-read naming a new value).
    The priced rows span the K+1 atoms of the posterior they are ranked against, so they must
    be rebuilt on the NEW candidate list — a stale row spans the wrong space and the engine
    refuses it."""
    opts0 = DEC_ATOM.interval_options(["1000", "1004"], _executor_fake([]).utility,
                                      shape=AS.QUANTITY)
    fake = _executor_fake(
        [{"effector": "gather", "probe": "re_extract_strong", "value": None,
          "credences": [0.45, 0.45], "p_none": 0.10, "eu": 0.0, "n_extra_actions": 1},
         {"effector": "abstain", "value": None, "credences": [0.3, 0.3, 0.3],
          "p_none": 0.10, "eu": 0.0, "n_extra_actions": 3},
         {"effector": "abstain", "value": None, "credences": [0.3, 0.3, 0.3],
          "p_none": 0.10, "eu": 0.0, "n_extra_actions": 3}],
        corroborate={"observations": [], "new_candidate": "1010",   # PII-OK: synthetic
                     "gather_rho": 0.9, "confidence": 0.8})
    _executor_loop(fake)
    first, second = fake.posted("/decide")[0], fake.posted("/decide")[1]
    assert len(first["extra_actions"]) == len(opts0)
    assert all(len(r["values"]) == len(first["candidates"]) + 1
               for r in first["extra_actions"])
    assert all(len(r["values"]) == len(second["candidates"]) + 1
               for r in second["extra_actions"])
    assert len(second["extra_actions"]) > len(first["extra_actions"])
