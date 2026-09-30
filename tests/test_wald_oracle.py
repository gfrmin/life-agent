"""wald as the argmax's auditor (CLAUDE.md "Engines are upstream"; MODEL.md law 2).

wald (gfrmin/wald, v0.2.1) is Bayesian decision theory as law, sharing no code with this repo
and acting in exact rationals. The same rows are declared as a wald World and compared on what
they choose:

* the states are the candidate indices plus NONE, carrying the mass the credences leave
  (``1 - sum``; a state of mass zero is not in Omega, so it is left out);
* every row of ``decide.options`` is a terminal act whose utility by state is linear: ``abstain``
  pays ``u_abstain`` everywhere; ``gather`` and ``ask`` pay ``u(y=1)`` (less the probe's cost) in
  the leader state, the first index of the maximum credence, and ``u(y=0)`` elsewhere; ``cite``
  pays ``u_cite_right`` in the states its document reports and ``u_cite_wrong`` elsewhere;
  ``respond(j)`` pays ``u_correct`` in state ``j`` and ``u_wrong`` elsewhere;
* the menu is ``options``' order, so wald's tie to the earlier entry (its J3) is ``choose``'s
  tie to the first-listed, by construction of two separate rule books.

Every float is converted with ``Fraction`` (exact), so wald's argmax is the exact one and
``choose``'s is float arithmetic. Where two rows are within ``NEAR`` of each other the float
argmax is not a fact, so the pair is compared only as both being near-maximal. Test-only: wald is
never the decider's runtime.
"""
from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from fractions import Fraction
from pathlib import Path

import pytest

from life_agent.core import decide as D
from life_agent.core import gather_row as GR
from life_agent.core import utility as U

wald = pytest.importorskip("wald", reason="the oracle group: `make check` syncs it")

NEAR = 1e-9
NONE = "none"
Group = tuple[int, Sequence[int]]
Gather = tuple[str, float]


class _Door(wald.Door):  # type: ignore[misc]
    """A World with no question: wald fires its first terminal and nothing is read."""

    def outcome(self, act):
        raise AssertionError(f"no question is declared, yet {act!r} was asked")

    def fire(self, act):
        pass


def _name(row: D.Option, i: int) -> str:
    return f"{i}:{row.action}:{row.target}"


def leader(credences: Sequence[float]) -> int | None:
    """The first index of the maximum credence; None with no candidate."""
    return max(range(len(credences)), key=lambda j: (credences[j], -j), default=None)


def world_spec(u_bar: Mapping[str, float], credences: Sequence[float],
               gathers: Sequence[Gather], groups: Sequence[Group]):
    """The rows of ``D.options`` as a wald World spec, and the menu of names in its order."""
    rows = D.options(u_bar, credences, gathers, groups)
    pairs = D.utility_by_action(u_bar)
    mass = {f"c{j}": Fraction(c) for j, c in enumerate(credences)}
    mass[NONE] = 1 - sum(mass.values())
    prior = {s: m for s, m in mass.items() if m > 0}  # a prior cell of zero is refused
    lead = leader(credences)
    lead_state = None if lead is None else f"c{lead}"

    def at_leader(u0: float, u1: float, cost: float = 0.0) -> dict[str, Fraction]:
        return {s: Fraction(u1 if s == lead_state else u0) - Fraction(cost) for s in prior}

    terminals: dict[str, dict[str, Fraction]] = {}
    gather_cost = {probe: cost for probe, cost in gathers}
    groups_by_id = dict(groups)
    for i, row in enumerate(rows):
        match row.action:
            case "abstain":
                u = {s: Fraction(pairs["abstain"][0]) for s in prior}
            case "gather":
                assert isinstance(row.target, str)
                u = at_leader(*pairs["gather"], cost=gather_cost[row.target])
            case "ask":
                u = at_leader(*pairs["ask"])
            case "cite":
                assert isinstance(row.target, int)
                c0, c1 = pairs["cite"]
                reported = {f"c{j}" for j in groups_by_id[row.target]}
                u = {s: Fraction(c1 if s in reported else c0) for s in prior}
            case "respond":
                u0, u1 = pairs["respond"]
                u = {s: Fraction(u1 if s == f"c{row.target}" else u0) for s in prior}
            case other:
                raise AssertionError(other)
        terminals[_name(row, i)] = u
    spec = {"prior": prior, "T": terminals, "O": {}, "N": 1, "d": 1, "closed": True,
            "table_sources": {"prior": "elicited", "utility": "elicited", "price": "elicited",
                              "horizon": "elicited", "depth": "elicited", "kernels": {}}}
    return spec, [_name(r, i) for i, r in enumerate(rows)], rows


def wald_first_act(u_bar, credences, gathers=(),
                   groups=()) -> tuple[str, list[str], list[D.Option]]:
    spec, menu, rows = world_spec(u_bar, credences, gathers, groups)
    return wald.run(wald.declare(spec), _Door()).acts[0], menu, rows


def agree(u_bar, credences, gathers=(), groups=()) -> bool:
    """wald's act is ``choose``'s; True when the row was not the float argmax's unique winner.

    wald acts in exact rationals, so its act is checked against the exact expected utilities
    (the first-listed of the exact maxima). ``choose`` is float arithmetic: where it names another
    row, both must be within ``NEAR`` of the best and ``choose``'s row must not be an exact tie of
    the best (it would then owe the first-listed): a difference made by rounding alone."""
    spec, menu, rows = world_spec(u_bar, credences, gathers, groups)
    act = wald.run(wald.declare(spec), _Door()).acts[0]
    exact = {n: sum(spec["prior"][s] * u for s, u in spec["T"][n].items()) for n in menu}
    top = max(exact.values())
    assert act == next(n for n in menu if exact[n] == top), (credences, act)
    ours = D.choose(rows)
    name = _name(ours, rows.index(ours))
    best = max(r.eu for r in rows)
    near = {_name(r, i) for i, r in enumerate(rows) if r.eu >= best - NEAR}
    if name != act:
        assert {name, act} <= near and exact[name] != top, (u_bar, credences, name, act)
    return len(near) > 1


# --- the draws -------------------------------------------------------------------------------

def draw_credences(rng: random.Random, n: int) -> list[float]:
    """A sub-probability vector on a dyadic grid, so the sums are exact: sometimes summing to
    exactly 1, sometimes with exact ties among the candidates."""
    if n == 0:
        return []
    den = rng.choice((8, 64, 1 << 20))
    shape = rng.choice(("free", "full", "tied", "tied-full"))
    if shape.startswith("tied"):
        k = rng.randint(1, den // n)
        ks = [k] * n
        if shape == "tied-full":
            ks[-1] = den - k * (n - 1)  # the rest, possibly a different size
    else:
        cuts = sorted(rng.randint(0, den) for _ in range(n))
        ks = [b - a for a, b in zip([0, *cuts[:-1]], cuts, strict=True)]
        if shape == "free":
            ks = [k * rng.randint(0, 1) if rng.random() < 0.3 else k for k in ks]
            ks = [k // 2 for k in ks] if rng.random() < 0.5 else ks
    rng.shuffle(ks)
    assert 0 <= sum(ks) <= den
    return [k / den for k in ks]


def draw_u_bar(rng: random.Random) -> dict[str, float]:
    if rng.random() < 0.1:
        return {}
    perturb = rng.random() < 0.6
    u_bar: dict[str, float] = {
        "u_correct": 1.0, "u_abstain": 0.0, "u_wrong": rng.uniform(-9.0, -1.0),
        "lambda_int": rng.uniform(0.0, 1.5), "kappa_att": rng.uniform(0.0, 0.5),
        "ask_recovery": rng.uniform(0.0, 1.0),
        "u_cite_right": rng.uniform(-1.0, 1.5), "u_cite_wrong": rng.uniform(-6.0, 0.5),
    }
    if perturb:
        u_bar.update({k: rng.uniform(0.0, 0.5) for k in GR.KEYS})
        if rng.random() < 0.5:  # an informative probe: it ends right far more often than wrong
            u_bar.update({"gather_right_if_right": rng.uniform(0.6, 1.0),
                          "gather_wrong_if_right": rng.uniform(0.0, 0.05),
                          "gather_right_if_wrong": rng.uniform(0.0, 0.5),
                          "gather_wrong_if_wrong": rng.uniform(0.0, 0.05)})
    else:
        u_bar.update(GR.PRIOR)
    return u_bar


def draw_menu(rng: random.Random, n: int) -> tuple[list[Gather], list[Group]]:
    gathers = [(f"p{i}", rng.uniform(0.0, 2.0)) for i in range(rng.randint(0, 3))]
    gathers = [(p, 0.0 if rng.random() < 0.15 else c) for p, c in gathers]
    groups: list[Group] = []
    for g in range(rng.randint(0, 3)):
        pool = list(range(n + 1))  # n is out of range: a report of a candidate that is not one
        groups.append((g, rng.sample(pool, rng.randint(0, len(pool)))))
    return gathers, groups


def _sweep(u_bars: Sequence[Mapping[str, float]], seed: int, per: int) -> tuple[int, int, dict]:
    rng = random.Random(seed)
    compared = near = 0
    by_action: dict[str, int] = {}
    for u_bar in u_bars:
        for _ in range(per):
            n = rng.randint(0, 6)
            credences = draw_credences(rng, n)
            gathers, groups = draw_menu(rng, n)
            near += agree(u_bar, credences, gathers, groups)
            won = D.bayes_act(u_bar, credences, gathers, groups).action
            by_action[won] = by_action.get(won, 0) + 1
            compared += 1
    return compared, near, by_action


# --- the tests -------------------------------------------------------------------------------

def test_wald_chooses_what_choose_chooses_over_random_states() -> None:
    """Law 2 against an independent kernel: over 3,000 seeded states (0-6 candidates, sub- and
    full probability vectors, exact ties, 0-3 gathers and groups, random gauges), wald's first act
    is ``choose``'s, named by row and target."""
    rng = random.Random(2026)
    u_bars = [draw_u_bar(rng) for _ in range(300)]
    compared, near, by_action = _sweep(u_bars, seed=930, per=10)
    assert compared == 3000
    # every row type was the winner somewhere, so no row went unaudited
    assert set(by_action) == set(D.ACTIONS), by_action
    assert near < compared // 4, (near, compared)  # near-ties are the exception, not the test


def test_wald_agrees_at_the_exact_defaults() -> None:
    compared, _, by_action = _sweep([{}], seed=77, per=1000)
    assert compared == 1000 and {"abstain", "respond"} <= set(by_action), by_action


def test_wald_agrees_under_the_shipped_example_models_folded_gauge() -> None:
    example = Path(__file__).resolve().parent.parent / "config/utility-model.example.yaml"
    model = U.load_model(example)
    u_bar = U.posterior(model, [], policy="all-to-date").u_bar()
    compared, _, _ = _sweep([u_bar], seed=11, per=400)
    assert compared == 400


def test_the_empty_state_is_the_abstain_gather_ask_menu() -> None:
    """No candidate: NONE carries all the mass and only abstain, gather and ask are rows."""
    rows = D.options({}, [], [("p", 0.0)], [(0, [])])
    assert [r.action for r in rows] == ["abstain", "gather", "ask", "cite"]
    assert not agree({}, [], [("p", 0.0)], [(0, [])])
    assert not agree({}, [], [], [])


@pytest.mark.parametrize(("u_bar", "credences", "gathers", "groups", "action"), [
    ({"lambda_int": 0.5}, [0.3], [], [], "abstain"),
    ({}, [0.99, 0.01], [], [], "respond"),
    ({"u_cite_right": 1.0, "u_cite_wrong": 0.0}, [0.4, 0.3], [], [(0, [0, 1])], "cite"),
    ({"ask_recovery": 1.0, "lambda_int": 0.05}, [0.5], [], [], "ask"),
    ({"gather_right_if_right": 1.0, "gather_wrong_if_right": 0.0, "gather_right_if_wrong": 0.0,
      "gather_wrong_if_wrong": 0.0, "kappa_att": 0.02}, [0.5], [("probe", 0.0)], [], "gather"),
], ids=["abstain", "respond", "cite", "ask", "gather"])
def test_each_row_is_the_unique_winner_somewhere(u_bar, credences, gathers, groups, action) -> None:
    rows = D.options(u_bar, credences, gathers, groups)
    ours = D.choose(rows)
    assert ours.action == action
    assert sorted(r.eu for r in rows)[-1] - sorted(r.eu for r in rows)[-2] > NEAR
    assert not agree(u_bar, credences, gathers, groups)


#: A gauge on which every crossing is an exact dyadic: u_wrong -7, the information rows flat
#: (slope zero), so respond meets abstain at 7/8 and every other row below it.
DYADIC = {"u_wrong": -7.0, "lambda_int": 0.125, "kappa_att": 0.0625, "ask_recovery": 0.0,
          "u_cite_right": -1.0, "u_cite_wrong": -1.0, **{k: 0.0 for k in GR.KEYS}}


def test_at_the_respond_threshold_the_tie_goes_to_the_earlier_row_in_both() -> None:
    """``respond`` wins STRICTLY: at p1 exactly on the bar it ties ``abstain`` and loses the tie,
    one step above it wins. wald, on exact rationals, agrees on both sides."""
    bar = D.respond_threshold(DYADIC)
    assert bar == 0.875
    at = [bar]
    assert D.bayes_act(DYADIC, at).action == "abstain"
    assert wald_first_act(DYADIC, at)[0].split(":")[1] == "abstain"
    above = [bar + 2.0**-20]
    assert D.bayes_act(DYADIC, above).action == "respond"
    assert wald_first_act(DYADIC, above)[0].split(":")[1] == "respond"
    assert agree(DYADIC, at)  # an exact tie: compared as both near-maximal, and the names above
    assert not agree(DYADIC, above)


@pytest.mark.parametrize("u_bar", [{}, DYADIC, {"u_wrong": -4.0, "ask_recovery": 0.9}],
                         ids=["defaults", "dyadic", "cheap-ask"])
def test_at_every_documented_crossing_wald_and_the_act_agree(u_bar) -> None:
    """``argmax_crossings`` and ``respond_threshold`` name the p1 at which the argmax changes; on
    each, and a step either side, wald and ``choose`` agree (or both are near-maximal)."""
    points = [*D.argmax_crossings(u_bar), *([t] if (t := D.respond_threshold(u_bar)) else [])]
    assert points or u_bar is DYADIC
    for p in points:
        for q in (p - 1e-6, p, p + 1e-6):
            agree(u_bar, [q], [("probe", 0.0)], [(0, [0])])
            agree(u_bar, [q, (1 - q) / 2], [("probe", 0.0)], [(0, [0, 1])])
