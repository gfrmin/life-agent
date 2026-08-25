"""D-2 — one reliability posterior behind the seam (r13, M3): reliability.py.

The one wire fold both instances bind: a Beta prior declared per (edge, cell) in ONE
table, conditioned over the wire on a 0/1 stream (Invariant 1: `condition` is the one
learning mechanism), read back exactly (`read_params`) or as a mean — never a host fold.

Run: uv run --project . python -m pytest tests/test_reliability.py
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from life_agent.core import brain as B
from life_agent.core import reliability as REL


class SeqTransport:
    """Scripted engine transport — records the RPC sequence, returns canned results."""

    def __init__(self) -> None:
        self.sent: list[dict] = []
        self._n = 0

    def send(self, line: str) -> None:
        self.sent.append(json.loads(line))

    def recv(self) -> str:
        req = self.sent[-1]
        if req["method"] == "create_state":
            self._n += 1
            result: object = {"state_id": f"s_{self._n}"}
        elif req["method"] == "condition":
            result = {"state_id": req["params"]["state_id"], "log_marginal": -0.1}
        elif req["method"] == "read_params":
            result = {"type": "beta", "alpha": 5.0, "beta": 6.0}
        elif req["method"] == "mean":
            result = {"mean": 0.45}
        else:
            result = "ok"
        return json.dumps({"jsonrpc": "2.0", "id": req["id"], "result": result})

    def close(self) -> None:
        pass


def test_the_prior_table_declares_both_edges_in_one_home() -> None:
    # the extractor's wide Beta(4,4) and the claim instrument's three audit cells —
    # the exact priors the two instances declared before the unification
    assert REL.PRIORS[("extract", "value")] == (4.0, 4.0)
    assert REL.PRIORS[("eval_claim", "verified")] == (3.0, 2.0)
    assert REL.PRIORS[("eval_claim", "unsupported")] == (1.0, 3.0)
    assert REL.PRIORS[("eval_claim", "unverifiable")] == (2.0, 2.0)
    assert len(REL.PRIORS) == 4


def test_reliability_is_the_wire_fold_read_back_exactly() -> None:
    t = SeqTransport()
    a, b = REL.reliability(B.Brain(t), "eval_claim", "verified",
                           [1.0, 0.0, 1.0])
    assert (a, b) == (5.0, 6.0)  # read_params relay, never a host a+=1
    methods = [r["method"] for r in t.sent]
    assert methods == ["create_state", "condition", "condition", "condition",
                       "read_params", "destroy_state"]
    assert t.sent[0]["params"] == {"type": "beta", "alpha": 3.0, "beta": 2.0}
    conditions = [r["params"] for r in t.sent if r["method"] == "condition"]
    assert [c["observation"] for c in conditions] == [1.0, 0.0, 1.0]
    assert all(c["kernel"] == {"type": "bernoulli"} for c in conditions)


def test_conditioned_state_serves_the_mean_readback_binding() -> None:
    t = SeqTransport()
    brain = B.Brain(t)
    sid = REL.conditioned_state(brain, "extract", "value", [1.0])
    try:
        assert brain.mean(sid) == 0.45
    finally:
        brain.destroy_state(sid)
    methods = [r["method"] for r in t.sent]
    assert methods == ["create_state", "condition", "mean", "destroy_state"]


def test_an_undeclared_edge_cell_is_loud() -> None:
    with pytest.raises(ValueError, match="nonsense"):
        REL.reliability(B.Brain(SeqTransport()), "extract", "nonsense", [])


def test_the_fold_lives_once() -> None:
    # drift gate (the M2 leaf-write pattern): the instruments BIND the one fold — no
    # reliability beta-create choreography left in lookup or narrative. Narrative keeps
    # exactly two beta creates, neither a D-2 fold: the coverage posterior (the
    # open-world tail is its own belief — amendment 3) and the per-claim cell-state
    # materialization (it re-instantiates an ALREADY-COMPUTED posterior (a, b) for the
    # EU decision — no prior + conditioning, so nothing to unify).
    src = Path(__file__).resolve().parent.parent / "src/life_agent/core"
    lookup_src = (src / "lookup.py").read_text(encoding="utf-8")
    narrative_src = (src / "narrative.py").read_text(encoding="utf-8")
    assert '"type": "beta"' not in lookup_src
    assert narrative_src.count('"type": "beta"') == 2
    assert "_COVERAGE_PRIOR[0]" in narrative_src          # 1: the open-world tail
    assert "a, b = cells_ab[cell]" in narrative_src       # 2: posterior re-materialized
