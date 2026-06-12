"""The lookup family (life_agent.core.lookup) — foundations §4, hermetic.

The conftest autouse fixture stubs ``lookup.lookup_answer`` for every OTHER test; this
file binds the real functions by name at import time, which the attribute patch
deliberately does not reach. The local model is faked (the subject.py client pattern),
the brain is a scripted transport, and §18.9 records land under ``migrated_root``.

Run: uv run --project . python -m pytest tests/test_lookup.py
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pytest

from life_agent.core import config
from life_agent.core import decisions as DEC
from life_agent.core import lookup as LK
from life_agent.core.brain import Brain
from life_agent.core.lookup import (
    Observation,
    action_utilities,
    authority_for,
    candidates_from,
    lookup_answer,
    observation_densities,
    observe_hits,
    render,
    route_question,
    temper_scales,
)
from pkm.transform import ModelResponse


@pytest.fixture
def migrated_root(tmp_path: Path) -> Path:
    # §18.9 records are file-first (content → lineage → meta + pending queue); no
    # catalogue is touched, so bare cache/logs dirs suffice.
    (tmp_path / "cache").mkdir()
    (tmp_path / "logs").mkdir()
    return tmp_path


class FakeClient:
    """The subject.py fake-client pattern: scripted JSON replies, call counting."""

    engine_version = "fake-1"

    def __init__(self, replies: list[dict] | dict) -> None:
        self._replies = replies if isinstance(replies, list) else [replies]
        self.calls = 0

    def complete(self, prompt: str, schema: dict[str, Any]) -> ModelResponse:
        reply = self._replies[min(self.calls, len(self._replies) - 1)]
        self.calls += 1
        return ModelResponse(raw_text=json.dumps(reply), input_tokens=1,
                             output_tokens=1, latency_ms=1, cost_usd=0.0)


def _hit(key: str, chunk: str, origin: str = "/data/doc.pdf") -> dict[str, Any]:
    return {"artifact_cache_key": key, "chunk_text": chunk, "score": 9.0,
            "origin": origin}


# --- route (cached §18.9 verdict) ---------------------------------------------------------

def test_route_lookup_returns_construct_and_caches(migrated_root: Path) -> None:
    client = FakeClient({"lookup": True, "construct": "passport number"})
    c1 = route_question(migrated_root, "what is my passport number?", client=client)
    c2 = route_question(migrated_root, "what is my passport number?", client=client)
    assert c1 == c2 == "passport number"
    assert client.calls == 1  # replayed from cache


def test_route_non_lookup_is_none(migrated_root: Path) -> None:
    client = FakeClient({"lookup": False})
    assert route_question(migrated_root, "summarise my year", client=client) is None


# --- observe (grounding gate, caching, authority) -----------------------------------------

def test_observe_grounded_extraction(migrated_root: Path) -> None:
    chunk = "Passport No: P1234567 issued 2019"
    client = FakeClient({"found": True, "value": "P1234567",
                         "quote": "Passport No: P1234567"})
    obs, ind = observe_hits(migrated_root, "passport number?",
                            [_hit("a" * 64, chunk)], client=client)
    assert ind == 0 and len(obs) == 1
    assert obs[0].value_norm == "p1234567"
    assert obs[0].card_n == 1
    assert obs[0].authority_class == "document"


def test_ungrounded_quote_is_indeterminate_and_recorded(migrated_root: Path) -> None:
    client = FakeClient({"found": True, "value": "X99",
                         "quote": "this text is not in the chunk"})
    obs, ind = observe_hits(migrated_root, "q?", [_hit("a" * 64, "real content")],
                            client=client)
    assert obs == [] and ind == 1
    # the ⊥ observation is recorded (deterministic replay), so no second model call
    obs2, ind2 = observe_hits(migrated_root, "q?", [_hit("a" * 64, "real content")],
                              client=client)
    assert (obs2, ind2) == ([], 1)
    assert client.calls == 1


def test_not_found_is_indeterminate(migrated_root: Path) -> None:
    client = FakeClient({"found": False})
    obs, ind = observe_hits(migrated_root, "q?", [_hit("b" * 64, "irrelevant")],
                            client=client)
    assert obs == [] and ind == 1


def test_observation_cache_is_per_chunk(migrated_root: Path) -> None:
    client = FakeClient({"found": True, "value": "42", "quote": "42"})
    hits = [_hit("a" * 64, "the answer is 42"), _hit("b" * 64, "still 42 here")]
    observe_hits(migrated_root, "q?", hits, client=client)
    assert client.calls == 2
    observe_hits(migrated_root, "q?", hits, client=client)
    assert client.calls == 2  # both replayed


def test_extractor_reliability_learns_from_eval_outcomes(tmp_path: Path) -> None:
    from life_agent.core import outcomes as O

    log = tmp_path / "outcomes.jsonl"
    assert LK.extractor_reliability(log) == pytest.approx(0.5)  # the wide prior
    for grade in ("INCORRECT", "INCORRECT", "CORRECT"):
        O.append(log, O.OutcomeEvent(
            tx_time="t", run_id="r", question_id="q", claim="v", construct="c",
            grade=grade, grader="eval_lookup",
            instrument_identity={"producer_name": "life_agent.ask.lookup_answer"},
            probability=0.9))
    # the none-claim grades the posterior, not the instrument: excluded
    O.append(log, O.OutcomeEvent(
        tx_time="t", run_id="r", question_id="q", claim="(none of the retrieved)",
        construct="c", grade="CORRECT", grader="eval_lookup",
        instrument_identity={"producer_name": "life_agent.ask.lookup_answer"},
        probability=0.1))
    assert LK.extractor_reliability(log) == pytest.approx((4 + 1) / (8 + 3))


def test_authority_classes() -> None:
    # synthetic placeholder paths, never real corpus locations
    assert authority_for("/x/statement.pdf") == ("document", 0.95)  # PII-OK
    assert authority_for("/x/mail/cur/12345") == ("email", 0.90)  # PII-OK
    assert authority_for("/x/todo.md") == ("note", 0.80)  # PII-OK
    assert authority_for("/x/blob") == LK._AUTHORITY_DEFAULT  # PII-OK


# --- the posterior's pure parts -----------------------------------------------------------

def _obs(key: str, value: str, n: int = 1, authority: float = 0.95) -> Observation:
    return Observation(card_n=n, artifact_cache_key=key, obs_cache_key="o" * 64,
                       value_raw=value, value_norm=" ".join(value.split()).casefold(),
                       quote=value, authority_class="document", authority=authority)


def test_candidates_dedupe_by_normalised_value() -> None:
    obs = [_obs("a" * 64, "P 1234"), _obs("b" * 64, "p  1234"), _obs("c" * 64, "X9")]
    assert candidates_from(obs) == ["P 1234", "X9"]


def test_temper_scales_single_observation_is_unit() -> None:
    assert temper_scales([_obs("a" * 64, "v")]) == [1.0]


def test_temper_scales_same_ancestor_discounts_more_than_distinct() -> None:
    same = temper_scales([_obs("a" * 64, "v"), _obs("a" * 64, "v")])
    distinct = temper_scales([_obs("a" * 64, "v"), _obs("b" * 64, "v")])
    # same document: s_anc = (1+0.3)/2, one group so s_mod = 1
    assert same[0] == pytest.approx((1 + LK._BETA_ANCESTRY) / 2)
    # two documents: s_anc = 1, s_mod = (1+0.7)/2 — milder discount
    assert distinct[0] == pytest.approx((1 + LK._BETA_MODEL) / 2)
    assert distinct[0] > same[0]


def test_observation_densities_shape_and_orientation() -> None:
    o = _obs("a" * 64, "v1", authority=1.0)
    rows = observation_densities(o, ["v1", "v2"], rho=0.8, scale=1.0)
    assert len(rows) == 3 and all(len(r) == 2 for r in rows)  # K+1 rows, K targets
    r = 0.8
    log_match = math.log(r + (1 - r) / LK._A_ALTERNATIVES)
    log_miss = math.log((1 - r) / LK._A_ALTERNATIVES)
    assert rows[0] == pytest.approx([log_match, log_miss])  # V=v1 matches obs v1
    assert rows[1] == pytest.approx([log_miss, log_match])
    assert rows[2] == pytest.approx([log_miss, log_miss])   # NONE never matches
    half = observation_densities(o, ["v1", "v2"], rho=0.8, scale=0.5)
    assert half[0][0] == pytest.approx(0.5 * log_match)     # the temper scales logs


def test_action_utilities_under_u_bar() -> None:
    ub = {"u_correct": 1.0, "u_abstain": 0.0, "u_wrong": -5.0, "u_hedged": 0.4,
          "lambda_int": 1.0, "kappa_att": 0.05}
    u = action_utilities([0.7, 0.2, 0.1], ub)   # two candidates + NONE
    assert u["report"] == [1.0, -5.0, -5.0]     # MAP asserted; truth elsewhere → wrong
    assert u["hedge"] == [0.4, 0.4, -5.0]       # misleads only when truth is NONE
    assert u["ask_clarify"] == [pytest.approx(0.9 * 1.0 - 1.0)] * 3
    assert u["abstain"] == [0.0, 0.0, 0.0]


# --- render (the credence grammar) --------------------------------------------------------

def _result(action: str) -> LK.LookupResult:
    return LK.LookupResult(
        question="q?", construct="the value", action=action, eu=0.5,
        candidates=("V1", "V2"), credences=(0.7, 0.2), p_none=0.1,
        observations=(_obs("a" * 64, "V1", n=1), _obs("b" * 64, "V2", n=3)),
        n_hits=5, n_indeterminate=3, utility_fold_version="f" * 64,
        answer_cache_key="k" * 64, rendered="")


def test_render_report_carries_credence_citation_and_footer() -> None:
    text = render(_result("report"))
    assert "V1 — credence 0.700 [1]" in text
    assert "none-of-retrieved 0.100" in text
    assert "decision report (EU 0.50)" in text
    assert "5 hits → 2 grounded observations · 3 indeterminate" in text


def test_render_hedge_names_alternatives_with_credences() -> None:
    text = render(_result("hedge"))
    assert "V1 (0.700) [1]" in text and "V2 (0.200) [3]" in text


def test_render_abstain_names_closed_reason() -> None:
    assert LK.REASON_DISPERSED in render(_result("abstain"))


def test_grammar_templates_all_render() -> None:
    # drift gate: every template formats with its declared slots
    LK.GRAMMAR["report"].format(value="v", p=0.5, cites="[1]")
    LK.GRAMMAR["hedge"].format(alts="a")
    LK.GRAMMAR["ask_clarify"].format(alts="a")
    LK.GRAMMAR["abstain"].format(reason="r")
    LK.GRAMMAR["footer"].format(n_hits=1, n_obs=1, n_ind=0, p_none=0.1,
                                action="report", eu=0.5)
    LK.GRAMMAR["fallthrough"].format(reason="r")


# --- the family end to end (scripted brain) -----------------------------------------------

class ScriptedTransport:
    """create/condition/weights/destroy/optimise over scripted replies."""

    def __init__(self, optimise_action: float = 0.0) -> None:
        self.sent: list[dict] = []
        self._optimise_action = optimise_action

    def send(self, line: str) -> None:
        self.sent.append(json.loads(line))

    def recv(self) -> str:
        req = self.sent[-1]
        method = req["method"]
        if method == "create_state":
            n = sum(1 for r in self.sent if r["method"] == "create_state")
            result: object = {"state_id": f"s_{n}"}
        elif method == "condition":
            result = {"state_id": req["params"]["state_id"], "log_marginal": -0.1}
        elif method == "weights":
            creates = [r for r in self.sent if r["method"] == "create_state"]
            idx = int(req["params"]["state_id"].split("_")[1]) - 1
            n = len(creates[idx]["params"]["space"]["values"])
            result = {"weights": [1.0 / n] * n}
        elif method == "optimise":
            result = {"action": self._optimise_action, "eu": 0.42}
        else:
            result = "ok"
        return json.dumps({"jsonrpc": "2.0", "id": req["id"], "result": result})

    def close(self) -> None:
        pass


MODEL_YAML = """\
format_version: 1
gauge: {u_correct: 1.0, u_abstain: 0.0}
latents:
  u_wrong:    {grid: {lo: -10.0, hi: 0.0, n: 11}, prior: {type: gaussian, mu: -4.0, sigma: 3.0}}
  u_hedged:   {grid: {lo: -1.0, hi: 1.0, n: 5},  prior: {type: gaussian, mu: 0.4, sigma: 0.4}}
  lambda_int: {grid: {lo: -0.5, hi: 4.0, n: 10}, prior: {type: gaussian, mu: 1.0, sigma: 1.0}}
  kappa_att:  {grid: {lo: -0.2, hi: 1.0, n: 7},  prior: {type: gaussian, mu: 0.05, sigma: 0.1}}
tau: {grid: {lo: 0.5, hi: 2.0, n: 4}, prior: {type: gaussian, mu: 1.0, sigma: 0.5}}
endpoint_mass_warn: 0.01
"""


def test_lookup_answer_end_to_end(migrated_root: Path, tmp_path: Path,
                                  monkeypatch: pytest.MonkeyPatch) -> None:
    model_path = tmp_path / "model.yaml"
    model_path.write_text(MODEL_YAML, encoding="utf-8")
    monkeypatch.setattr(config, "UTILITY_MODEL", model_path)
    monkeypatch.setattr(config, "UTILITY_ELICITATIONS", tmp_path / "elicit.jsonl")
    monkeypatch.setattr(LK, "_U_BAR", None)  # no cross-test fold cache
    decisions_path = tmp_path / "decisions.jsonl"

    route = FakeClient({"lookup": True, "construct": "the ID"})
    extract = FakeClient({"found": True, "value": "12345", "quote": "ID 12345"})
    brain = Brain(ScriptedTransport(optimise_action=0.0))  # report
    hits = [_hit("a" * 64, "your ID 12345 is recorded")]

    result = lookup_answer(migrated_root, "what is my ID?", hits,
                           brain=brain, route_client=route, extract_client=extract,
                           decisions_path=decisions_path, run_id="test")
    assert result is not None
    assert result.action == "report" and result.candidates == ("12345",)
    assert "credence" in result.rendered
    assert len(result.utility_fold_version) == 64

    # the decision is logged — no EU decision unlogged
    logged = DEC.read(decisions_path)
    assert len(logged) == 1
    assert logged[0].family == "lookup" and logged[0].chosen_action == "report"
    assert logged[0].utility_fold_version == result.utility_fold_version

    # the answer artifact is on the ledger with observation lineage
    from pkm.cache import lineage_file, meta_file
    assert meta_file(migrated_root, result.answer_cache_key).exists()
    lineage = json.loads(lineage_file(migrated_root, result.answer_cache_key)
                         .read_text(encoding="utf-8"))["inputs"]
    assert [e["role"] for e in lineage] == ["observation"]


def test_lookup_answer_none_when_not_routed(migrated_root: Path) -> None:
    route = FakeClient({"lookup": False})
    assert lookup_answer(migrated_root, "summarise my week", [],
                         route_client=route) is None


def test_lookup_answer_none_on_zero_grounded_observations(
        migrated_root: Path) -> None:
    route = FakeClient({"lookup": True, "construct": "x"})
    extract = FakeClient({"found": False})
    out = lookup_answer(migrated_root, "what is x?",
                        [_hit("a" * 64, "nothing here")],
                        route_client=route, extract_client=extract)
    assert out is None  # coverage fallthrough — the narrative path answers
