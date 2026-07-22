"""Hermetic tests for the E1 categorical shadow world (life_agent.membrane.categorical).

The categorical world (E1 stage 1, docs/candidates/e1-categorical-outcome.md §4) declares
`obs_arity = K + 1` — atoms 1..K are the tick's candidates in candidate order, atom 0 the
wire's own NULL emission — and runs ONE FRESH SESSION PER TICK (session-per-question,
OB-11's K-at-tick-0 shape): handshake, this question's own code-valued evidence ticks,
one decide, shutdown. No wire, no subprocess here: `_FakeClient` records every request
and scripts every reply; the utility sentence's semantics are pinned by a tiny host-side
S-expression evaluator rather than by prose.

Fixture values are synthetic (public repo, PRINCIPLES §12) — no owner data.
"""
from __future__ import annotations

from typing import Any

import pytest

from life_agent.membrane import categorical as C
from life_agent.membrane import world as W
from life_agent.membrane.client import MembraneError

# --- shared synthetic inputs -------------------------------------------------------------


def _u_bar() -> dict[str, float]:
    return {
        "u_correct": 1.0, "u_abstain": 0.0, "u_wrong": -9.0,
        "lambda_int": 0.1, "kappa_att": 0.02,
    }


def _payload(**kw: object) -> dict[str, Any]:
    """A synthetic /decide request body in the bridge's abstract-observation shape
    (bridge/observations.py: `reports` is the 0-based candidate index)."""
    defaults: dict[str, Any] = {
        "candidates": ["10,000", "12,500"],
        "observations": [
            {"reports": 0, "group": 0, "authority": 0.9,
             "subject_factor": 1.0, "time_factor": 1.0},
            {"reports": 1, "group": 1, "authority": 0.5,
             "subject_factor": 1.0, "time_factor": 0.8},
            {"reports": 0, "group": 0, "authority": 0.9,
             "subject_factor": 1.0, "time_factor": 1.0},
        ],
        "era_split": False,
        "owner_scoped": True,
    }
    defaults.update(kw)
    return defaults


def _dec(**kw: object) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "effector": "abstain", "credences": [0.55, 0.15], "p_none": 0.30,
    }
    defaults.update(kw)
    return defaults


# --- summary_from_payload_cat: the pure reduction ----------------------------------------


def test_summary_codes_are_one_based_in_arrival_order() -> None:
    s = C.summary_from_payload_cat(_payload(), _dec())
    assert s is not None
    assert s.k == 2
    assert s.obs_codes == (1, 2, 1)  # reports 0,1,0 -> codes 1,2,1 (atom 0 = NONE)
    assert s.n_obs == 3
    assert s.n_obs_unmapped == 0


def test_summary_excludes_out_of_range_reports_counted() -> None:
    p = _payload()
    p["observations"] = [
        {"reports": 0}, {"reports": 5}, {"reports": -1}, {"reports": True}, {},
    ]
    s = C.summary_from_payload_cat(p, _dec())
    assert s is not None
    assert s.obs_codes == (1,)
    assert s.n_obs == 5
    assert s.n_obs_unmapped == 4


def test_summary_none_when_no_candidates() -> None:
    assert C.summary_from_payload_cat(_payload(candidates=[]), _dec()) is None
    assert C.summary_from_payload_cat({}, {}) is None


def test_summary_daemon_map_index_is_argmax_or_none() -> None:
    s = C.summary_from_payload_cat(_payload(), _dec(credences=[0.2, 0.6]))
    assert s is not None and s.daemon_map_index == 1
    s2 = C.summary_from_payload_cat(_payload(), _dec(credences=[]))
    assert s2 is not None and s2.daemon_map_index is None


def test_summary_carries_context_flags() -> None:
    s = C.summary_from_payload_cat(
        _payload(era_split=True, owner_scoped=False, grow={"probe": "x"}), _dec(),
    )
    assert s is not None
    assert s.era_split is True
    assert s.owner_scoped is False
    assert s.grow_pass is True


# --- the handshake declaration -----------------------------------------------------------


def _summary(**kw: object) -> C.CatSummary:
    defaults: dict[str, object] = dict(
        k=3, obs_codes=(1, 3, 1), n_obs=3, n_obs_unmapped=0, daemon_map_index=0,
        era_split=False, owner_scoped=True, grow_pass=False,
    )
    defaults.update(kw)
    return C.CatSummary(**defaults)  # type: ignore[arg-type]


def test_handshake_declares_obs_arity_k_plus_one_and_the_value_indexed_grid() -> None:
    decl = C.handshake_decl_cat(_u_bar(), 3)
    world = decl["world"]
    assert decl["membrane"] == 1
    assert world["obs_arity"] == 4  # K=3 candidates + the NULL atom
    (menu_entry,) = world["menu"]
    assert menu_entry["name"] == W.ACT_NAME
    # abstain, gather, ask, respond_1..respond_3 — grid order normative, wait first
    assert menu_entry["grid"] == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]


def test_handshake_namespace_guards_and_disjointness() -> None:
    world = C.handshake_decl_cat(_u_bar(), 2)["world"]
    names = world["namespace"]
    guard_names = [g["name"] for g in world["guards"]]
    assert names[0] == "t"
    assert names[-1] == W.ACT_NAME
    # every guard is a singleton [0.5] over a namespace member; the writable name is
    # NEVER a guard (ruling D-b2 disjointness)
    assert all(g["grid"] == [0.5] for g in world["guards"])
    assert set(guard_names) <= set(names)
    assert W.ACT_NAME not in guard_names
    assert "t" not in guard_names


def test_handshake_rejects_k_below_one() -> None:
    with pytest.raises(ValueError):
        C.handshake_decl_cat(_u_bar(), 0)


def test_k1_declares_arity_two() -> None:
    # one candidate is still a lawful categorical world: arity 2 (the wire's K >= 2 floor)
    assert C.handshake_decl_cat(_u_bar(), 1)["world"]["obs_arity"] == 2


# --- the utility sentence: grammar subset + semantics ------------------------------------

_ALLOWED_HEADS = {"if", "=", ">", "+", "-", "*", "/", "log", "exp", "neg", "c", "var", "get"}


def _walk_heads(expr: object, heads: set[str]) -> None:
    if isinstance(expr, list) and expr and isinstance(expr[0], str):
        heads.add(expr[0])
        for sub in expr[1:]:
            _walk_heads(sub, heads)


def test_utility_sentence_stays_inside_the_shipped_grammar() -> None:
    heads: set[str] = set()
    _walk_heads(C.utility_said_cat(_u_bar()), heads)
    assert heads <= _ALLOWED_HEADS
    assert "<" not in heads  # the wire has no '<' codeword


def _eval_said(expr: Any, act: float, y: float) -> float:
    """A tiny host-side evaluator for the said grammar subset the sentence uses —
    the test's own oracle for the sentence's semantics."""

    def ev(e: Any) -> float:
        assert isinstance(e, list) and isinstance(e[0], str)
        head = e[0]
        if head == "c":
            return float(e[1])
        if head == "var":
            assert e[1] == 1  # only the outcome residue appears in this sentence
            return y
        if head == "get":
            assert e[1] == W.ACT_NAME
            return act
        if head == "+":
            return ev(e[1]) + ev(e[2])
        if head == "-":
            return ev(e[1]) - ev(e[2])
        if head == "*":
            return ev(e[1]) * ev(e[2])
        if head == "if":
            return ev(e[2]) if cond(e[1]) else ev(e[3])
        raise AssertionError(f"unexpected head {head!r}")

    def cond(e: Any) -> bool:
        head = e[0]
        if head == "=":
            return ev(e[1]) == ev(e[2])
        if head == ">":
            return ev(e[1]) > ev(e[2])
        raise AssertionError(f"unexpected condition {head!r}")

    return ev(expr)


def test_utility_sentence_semantics_match_the_declared_rows() -> None:
    u = _u_bar()
    sent = C.utility_said_cat(u)
    pairs = W.utility_by_action(u)
    ua = pairs["abstain"][0]
    g0, g1 = pairs["gather"]
    a0, a1 = pairs["ask"]
    uw, uc = pairs["respond"]
    k = 3
    for y in range(0, k + 1):
        # abstain: constant (gauge — u_abstain regardless of y, doc §4.3)
        assert _eval_said(sent, 1.0, y) == pytest.approx(ua)
        # the info rows: myopic perfect information, categorical translation — having
        # gathered you take the correct act: y=0 -> abstain-side, else correct-side
        assert _eval_said(sent, 2.0, y) == pytest.approx(g0 if y == 0 else g1)
        assert _eval_said(sent, 3.0, y) == pytest.approx(a0 if y == 0 else a1)
        # respond_j (grid value 3+j): u_correct iff y == j, else u_wrong
        for j in range(1, k + 1):
            expected = uc if y == j else uw
            assert _eval_said(sent, 3.0 + j, y) == pytest.approx(expected)


# --- act decoding ------------------------------------------------------------------------


def test_value_to_action_cat_decodes_the_full_grid() -> None:
    assert C.value_to_action_cat(1.0, 3) == ("abstain", None)
    assert C.value_to_action_cat(2.0, 3) == ("gather", None)
    assert C.value_to_action_cat(3.0, 3) == ("ask", None)
    assert C.value_to_action_cat(4.0, 3) == ("respond_1", 1)
    assert C.value_to_action_cat(6.0, 3) == ("respond_3", 3)


def test_value_to_action_cat_rejects_off_grid_values() -> None:
    assert C.value_to_action_cat(7.0, 3) is None  # beyond respond_K
    assert C.value_to_action_cat(4.5, 3) is None  # non-integral
    assert C.value_to_action_cat(0.0, 3) is None


# --- decide_categorical over a fake client: the exact wire sequence ----------------------


class _FakeClient:
    def __init__(self, replies: list[dict[str, Any]]) -> None:
        self.requests: list[dict[str, Any]] = []
        self._replies = replies
        self.shutdown_calls = 0

    def request(self, obj: dict[str, Any]) -> dict[str, Any]:
        self.requests.append(obj)
        return self._replies[len(self.requests) - 1]

    def shutdown(self) -> None:
        self.shutdown_calls += 1


def _ok_replies(n_evidence: int, act_value: float) -> list[dict[str, Any]]:
    hs = {"ok": True, "proto": 1, "models": 100, "namespace_bits": 3.0}
    ev = [{"observed": 1, "loss_bits": 1.0} for _ in range(n_evidence)]
    dec = {"act": {"act": act_value}, "p1": 0.4, "entropy_bits": 1.2}
    return [hs, *ev, dec]


def test_decide_categorical_wire_sequence_and_decode() -> None:
    s = _summary()  # K=3, codes (1, 3, 1)
    client = _FakeClient(_ok_replies(3, 5.0))
    choice = C.decide_categorical(client, _u_bar(), s)

    # [0] the handshake, with the categorical declaration
    assert client.requests[0]["world"]["obs_arity"] == 4
    # [1..3] one evidence tick per code, in arrival order, t advancing 0,1,2
    for i, code in enumerate(s.obs_codes):
        tick = client.requests[1 + i]["tick"]
        assert tick["evidence"] == code
        assert tick["features"]["t"] == float(i)
        assert "menu" not in tick
    # [4] the decide tick at t = n_evidence, menu = the one writable name
    decide = client.requests[4]["tick"]
    assert decide["menu"] == [W.ACT_NAME]
    assert decide["features"]["t"] == 3.0
    assert "evidence" not in decide

    assert choice.action == "respond_2"
    assert choice.j == 2
    assert choice.readouts["p1"] == 0.4
    assert choice.engine["models"] == 100


def test_decide_categorical_raises_on_handshake_refusal() -> None:
    client = _FakeClient([{"error": "bad hello"}])
    with pytest.raises(MembraneError):
        C.decide_categorical(client, _u_bar(), _summary())


def test_decide_categorical_raises_on_evidence_error() -> None:
    replies = _ok_replies(3, 4.0)
    replies[1] = {"error": "impossible evidence"}
    client = _FakeClient(replies)
    with pytest.raises(MembraneError):
        C.decide_categorical(client, _u_bar(), _summary())


def test_decide_categorical_raises_on_undeclared_act_value() -> None:
    client = _FakeClient(_ok_replies(3, 99.0))
    with pytest.raises(MembraneError):
        C.decide_categorical(client, _u_bar(), _summary())


def test_run_categorical_always_shuts_down_the_client() -> None:
    made: list[_FakeClient] = []

    def spawn(argv: list[str], *, read_timeout_s: float) -> _FakeClient:
        client = _FakeClient(_ok_replies(3, 1.0))
        made.append(client)
        return client

    choice = C.run_categorical(
        ["/x/engine"],  # PII-OK: synthetic placeholder path
        _u_bar(), _summary(), read_timeout_s=5.0, spawn=spawn,
    )
    assert choice.action == "abstain"
    assert made[0].shutdown_calls == 1


def test_run_categorical_shuts_down_even_when_the_session_raises() -> None:
    made: list[_FakeClient] = []

    def spawn(argv: list[str], *, read_timeout_s: float) -> _FakeClient:
        client = _FakeClient([{"error": "bad hello"}])
        made.append(client)
        return client

    with pytest.raises(MembraneError):
        C.run_categorical(
            ["/x/engine"],  # PII-OK: synthetic placeholder path
            _u_bar(), _summary(), spawn=spawn)
    assert made[0].shutdown_calls == 1


# --- cat_features: the reduced contextual vocabulary -------------------------------------


def test_cat_features_carries_t_obs_bucket_and_flags() -> None:
    s = _summary(era_split=True, owner_scoped=True, grow_pass=False)
    feats = C.cat_features(s, 2.0)
    assert feats["t"] == 2.0
    assert feats["n-obs=3plus"] == 1.0
    assert feats["era-split=1"] == 1.0
    assert feats["owner-scoped=1"] == 1.0
    assert "grow-pass=1" not in feats
    # every emitted indicator is a declared namespace member of the SAME declaration
    names = C.handshake_decl_cat(_u_bar(), s.k)["world"]["namespace"]
    assert set(feats) - {"t"} <= set(names)
