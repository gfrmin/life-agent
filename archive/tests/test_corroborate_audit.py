"""Corroborate audit (scripts/corroborate_audit.py) — hermetic: the class vocabulary
and the frozen reading criteria are stated in the module docstring; these pin the
classifier, the mechanical verdict, the analytic append, and the synth rewrite."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import corroborate_audit as CA
from temper_audit import COMMIT_BAR


def _reply(kept: int = 0, *, n_base_groups: int = 1, grounded: int | None = None,
           dropped: int = 0, cost: float = 0.0) -> dict:
    obs = [{"reports": 0, "group": n_base_groups + i, "authority": 0.9,
            "subject_factor": 1.0, "time_factor": 1.0, "competition_factor": 1.0}
           for i in range(kept)]
    return {"observations": obs, "n_prefilter": kept + dropped,
            "n_grounded": kept + dropped if grounded is None else grounded,
            "n_correlated_dropped": dropped, "n_base_groups": n_base_groups,
            "cost_usd": cost}


def test_predicted_p_appends_and_tempers() -> None:
    base = 0.82
    one = CA.predicted_p(base, _reply(1)["observations"], 1, rho_base=0.7)
    two = CA.predicted_p(base, _reply(2)["observations"], 1, rho_base=0.7)
    assert one > base and two > one          # an agreeing witness only raises
    # the cross-group temper bites: the second witness adds less than the first
    lift1, lift2 = one - base, two - one
    assert lift2 < lift1
    # no confirms — the credence is untouched
    assert CA.predicted_p(base, [], 1, rho_base=0.7) == base


def _questions() -> list[dict]:
    return [
        {"id": "q-a", "question": "what is the fee?", "answer": "1,234,567",
         "answer_variants": []},
        {"id": "q-b", "question": "what is the tel?", "answer": "5550 0143",  # PII-OK
         "answer_variants": []},
        {"id": "q-c", "question": "what is the id?", "answer": "PL-900001",
         "answer_variants": []},
    ]


def _paired() -> dict[str, dict]:
    return {"q-a": {"typed": {"action": "abstain"}},
            "q-b": {"typed": {"action": "abstain"}},
            "q-c": {"typed": {"action": "abstain"}},
            "q-d": {"typed": {"action": "report"}}}   # asserted — never audited


def test_audit_rows_classes_and_named_exclusion() -> None:
    # q-a: gold leader, confirms at every m -> rescue
    # q-b: NON-gold leader with a grounded confirm -> wrong-rescue
    # q-c: no decision row -> no-leader, named excluded
    decisions = {
        CA._qhash("what is the fee?"): {"posterior_summary": {
            "candidates": ["1,234,567"], "credences": [0.82]}},
        CA._qhash("what is the tel?"): {"posterior_summary": {
            "candidates": ["9999 0000"], "credences": [0.75]}},  # PII-OK: synthetic phone shape
    }

    def probe(question: str, value: str, candidates: list[str]) -> dict[int, dict]:
        if "fee" in question:
            return {m: _reply(min(m, 2), cost=0.002) for m in CA._MS}
        return {m: _reply(1) for m in CA._MS}

    rows = CA.audit_rows(_paired(), decisions, _questions(), probe, rho_base=0.7)
    by = {r.qid: r for r in rows}
    assert set(by) == {"q-a", "q-b", "q-c"}            # the assert row never audited
    assert by["q-a"].klass == "rescue" and by["q-a"].gold_match is True
    assert by["q-b"].klass == "wrong-rescue" and by["q-b"].gold_match is False
    assert by["q-c"].klass == "no-leader" and by["q-c"].gold_match is None
    assert by["q-a"].cost_usd > 0


def test_verdict_is_mechanical_and_wrong_flip_blocks() -> None:
    def row(qid: str, klass: str, flips: dict[int, bool]) -> CA.Row:
        return CA.Row(qid=qid, action="abstain", leader="x", leader_p=0.8,
                      gold_match=klass == "rescue", klass=klass,
                      per_m={m: {"n_kept": 1, "n_grounded": 1,
                                 "n_correlated_dropped": 0,
                                 "p_prime": COMMIT_BAR + 0.01 if f else 0.5,
                                 "flips": f}
                             for m, f in flips.items()})

    rescues = [row(f"r{i}", "rescue", {1: True, 2: True, 3: True}) for i in range(6)]
    v = CA.verdict(rescues)
    assert v["go"] and v["frozen_m"] == 1              # m=1 already reaches 0.9x m=3
    # one wrong-rescue FLIP at the frozen m refuses the wiring
    v2 = CA.verdict([*rescues, row("w", "wrong-rescue", {1: True, 2: True, 3: True})])
    assert not v2["go"] and v2["wrong_confirms"] == ["w"]
    # a wrong-rescue that never flips does NOT block go (it lands withheld), but is
    # still named as a wrong-confirm for the tier criterion
    v3 = CA.verdict([*rescues, row("w2", "wrong-rescue", {1: False, 2: False, 3: False})])
    assert v3["go"] and v3["wrong_confirms"] == ["w2"]
    # under 5 predicted rescues -> no-go
    assert not CA.verdict(rescues[:4])["go"]


def test_synth_paired_rewrites_only_flips(tmp_path: Path) -> None:
    rows = [CA.Row(qid="q-a", action="abstain", leader="1,234,567", leader_p=0.82,
                   gold_match=True, klass="rescue", cost_usd=0.004,
                   per_m={2: {"n_kept": 1, "n_grounded": 1,
                              "n_correlated_dropped": 0, "p_prime": 0.95,
                              "flips": True}}),
            CA.Row(qid="q-b", action="abstain", leader="x", leader_p=0.5,
                   gold_match=False, klass="no-confirm", per_m={})]
    paired = {"q-a": {"typed": {"action": "abstain", "cost_usd": 0.01}},
              "q-b": {"typed": {"action": "abstain", "cost_usd": 0.01}}}
    out = CA.synth_paired(paired, rows, 2, tmp_path)
    synth = [json.loads(line) for line in out.read_text().splitlines()]
    by = {list(paired)[i]: s for i, s in enumerate(synth)}
    assert by["q-a"]["typed"]["action"] == "report"
    assert by["q-a"]["typed"]["correct"] is True
    assert by["q-a"]["typed"]["cost_usd"] == 0.01 + 0.004
    assert by["q-b"]["typed"]["action"] == "abstain"   # untouched
