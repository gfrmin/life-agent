"""life_agent.core.gather — the gather-augmented lookup loop (Stage-0 govern+steer driver).

The novel logic is the recency DECOUPLING: ``_era_split`` (pure) decides when the
candidates split across eras, and ``gather_answer`` turns recency on in that case even when
the local router flagged the value permanent. Both are tested hermetically — the probes are
stubbed (no catalogue), the local model is faked (the subject.py client pattern), and the
brain is a scripted transport (no Julia skin). §18.9 records land under ``migrated_root``.

Run: uv run --project . python -m pytest tests/test_gather.py
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from life_agent.core import config
from life_agent.core import lookup as LK
from life_agent.core import probes as P
from life_agent.core.brain import Brain
from life_agent.core.gather import _era_split, gather_answer
from life_agent.core.lookup import lookup_answer as _real_lookup_answer
from pkm.cache import content_file
from pkm.transform import ModelResponse


@pytest.fixture
def migrated_root(tmp_path: Path) -> Path:
    # §18.9 records are file-first; bare cache/logs dirs suffice (no catalogue touched).
    (tmp_path / "cache").mkdir()
    (tmp_path / "logs").mkdir()
    return tmp_path


def _obs(key: str, value: str) -> LK.Observation:
    return LK.Observation(card_n=1, artifact_cache_key=key, obs_cache_key="o" * 64,
                          value_raw=value, value_norm=value.casefold(), quote=value,
                          authority_class="email", authority=0.9)


# --- _era_split: the recency-discriminates predicate (pure) ----------------------------


def test_era_split_true_when_candidates_span_eras() -> None:
    """Two candidates whose newest supporting documents are >half-life apart → a
    stale-vs-current confusion is possible → recency discriminates (True)."""
    obs = [_obs("a", "STALE"), _obs("b", "FRESH")]
    doc_date = {"a": "2014-01-01", "b": "2026-01-01"}  # 12y apart
    assert _era_split(obs, doc_date, years=5.0) is True


def test_era_split_false_within_one_era() -> None:
    """Candidates dated close together → no stale-vs-current split → recency stays off
    (a permanent fact is never decayed by this path)."""
    obs = [_obs("a", "X"), _obs("b", "Y")]
    doc_date = {"a": "2025-01-01", "b": "2026-01-01"}  # 1y apart
    assert _era_split(obs, doc_date, years=5.0) is False


def test_era_split_false_with_fewer_than_two_dated_candidates() -> None:
    """One dated candidate (or none) → nothing to discriminate → False. An undated
    candidate (None / absent key) does not count."""
    obs = [_obs("a", "X"), _obs("b", "Y")]
    assert _era_split(obs, {"a": "2014-01-01", "b": None}, years=5.0) is False
    assert _era_split(obs, {}, years=5.0) is False
    # same canonical candidate dated in two eras is ONE candidate — no split
    same = [_obs("a", "12345"), _obs("b", "12345")]
    assert _era_split(same, {"a": "2014-01-01", "b": "2026-01-01"}, years=5.0) is False


# --- gather_answer: the loop fires the decoupling end to end ---------------------------


class _ChunkClient:
    """A fake extract client that reads the value out of the excerpt (VAL=<x>), so observe
    is deterministic regardless of call order (the FakeClient list-replay is too brittle
    once gathered chunks join the baseline)."""

    engine_version = "fake-1"

    def complete(self, prompt: str, schema: dict[str, Any]) -> ModelResponse:
        m = re.search(r"VAL=(\w+)", prompt)
        reply = ({"found": True, "value": m.group(1), "quote": f"VAL={m.group(1)}"}
                 if m else {"found": False})
        return ModelResponse(raw_text=json.dumps(reply), input_tokens=1,
                             output_tokens=1, latency_ms=1, cost_usd=0.0)


class _RouteClient:
    engine_version = "fake-1"

    def __init__(self, reply: dict[str, Any]) -> None:
        self._reply = reply

    def complete(self, prompt: str, schema: dict[str, Any]) -> ModelResponse:
        return ModelResponse(raw_text=json.dumps(self._reply), input_tokens=1,
                             output_tokens=1, latency_ms=1, cost_usd=0.0)


# the scripted brain (create/condition/weights/optimise) — the test_lookup pattern
class _ScriptedTransport:
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


_MODEL_YAML = """\
format_version: 1
gauge: {u_correct: 1.0, u_abstain: 0.0}
latents:
  u_wrong:    {grid: {lo: -10.0, hi: 0.0, n: 11}, prior: {type: gaussian, mu: -4.0, sigma: 3.0}}
  u_wrong_scoped: {grid: {lo: -6.0, hi: 0.0, n: 9}, prior: {type: gaussian, mu: -2.0, sigma: 1.0}}
  u_hedged:   {grid: {lo: -1.0, hi: 1.0, n: 5},  prior: {type: gaussian, mu: 0.4, sigma: 0.4}}
  lambda_int: {grid: {lo: -0.5, hi: 4.0, n: 10}, prior: {type: gaussian, mu: 1.0, sigma: 1.0}}
  kappa_att:  {grid: {lo: -0.2, hi: 1.0, n: 7},  prior: {type: gaussian, mu: 0.05, sigma: 0.1}}
tau: {grid: {lo: 0.5, hi: 2.0, n: 4}, prior: {type: gaussian, mu: 1.0, sigma: 0.5}}
endpoint_mass_warn: 0.01
"""


def _hit(key: str, val: str) -> dict[str, Any]:
    return {"artifact_cache_key": key, "chunk_text": f"VAL={val}", "score": 9.0,
            "origin": "/tmp/m.eml"}


def test_gather_answer_decouples_recency_from_the_router(
        migrated_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The route flags the value PERMANENT (time_indexed False — the mobile-class
    mis-flag), but the gathered candidates split across eras, so the loop turns recency on
    anyway: the recorded answer's ``time_indexed`` is True. Proves the decoupling fires end
    to end and the loop delegates to decide_and_record (a LookupResult comes back, logged)."""
    model_path = tmp_path / "model.yaml"
    model_path.write_text(_MODEL_YAML, encoding="utf-8")
    monkeypatch.setattr(config, "UTILITY_MODEL", model_path)
    monkeypatch.setattr(config, "UTILITY_ELICITATIONS", tmp_path / "elicit.jsonl")
    monkeypatch.setattr(config, "REACTIONS_LOG", tmp_path / "reactions.jsonl")
    monkeypatch.setattr(config, "DECISIONS_LOG", tmp_path / "decisions.jsonl")
    monkeypatch.setattr(LK, "_U_BAR", None)  # no cross-test fold cache

    a, b, ga, gb = "aa" * 32, "bb" * 32, "1a" * 32, "1b" * 32
    dates = {a: "2014-03-01", ga: "2013-09-01", b: "2026-01-01", gb: "2026-02-01"}
    gathered = [_hit(ga, "STALE"), _hit(gb, "FRESH")]

    def fake_corroborate(conn: Any, question: str, value: str, *, k: int,
                         exclude_keys: Any = ()) -> list[dict[str, Any]]:
        seen = set(exclude_keys)
        return [h for h in gathered if h["artifact_cache_key"] not in seen]

    def fake_recency(conn: Any, root: Path, hit_keys: list[str], *,
                     caller: str = "probe.recency") -> dict[str, str | None]:
        return {key: dates.get(key) for key in hit_keys}

    monkeypatch.setattr(P, "probe_corroborate", fake_corroborate)
    monkeypatch.setattr(P, "probe_recency", fake_recency)

    route = _RouteClient({"lookup": True, "construct": "mobile number",
                          "time_indexed": False})  # the mis-flag
    brain = Brain(_ScriptedTransport(optimise_action=0.0))  # report
    baseline = [_hit(a, "STALE"), _hit(b, "FRESH")]

    result = gather_answer(None, migrated_root, "what is my mobile number?", baseline,  # type: ignore[arg-type]
                           profile="", owner_scoped=True, brain=brain,
                           route_client=route, extract_client=_ChunkClient(),
                           today=date(2026, 6, 16))

    assert result is not None
    assert result.n_hits == 4  # baseline (2) + gathered (2)
    assert set(result.candidates) == {"STALE", "FRESH"}
    # the decoupling: route said permanent, the loop turned recency on (era split) and
    # recorded it — the answer artifact's time_indexed is True
    content = json.loads(content_file(migrated_root, result.answer_cache_key)
                         .read_text(encoding="utf-8"))
    assert content["time_indexed"] is True


def test_gather_answer_skips_gather_when_not_owner_scoped(
        migrated_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-owner-scoped question ("my partner's ID") has no whose-document discriminator,
    so the loop must NOT gather (it would amplify the most-documented entity into a
    confident-wrong) — it takes the single-pass decision. Proven by probe_corroborate never
    being called and the result spanning only the baseline hits."""
    model_path = tmp_path / "model.yaml"
    model_path.write_text(_MODEL_YAML, encoding="utf-8")
    monkeypatch.setattr(config, "UTILITY_MODEL", model_path)
    monkeypatch.setattr(config, "UTILITY_ELICITATIONS", tmp_path / "elicit.jsonl")
    monkeypatch.setattr(config, "REACTIONS_LOG", tmp_path / "reactions.jsonl")
    monkeypatch.setattr(config, "DECISIONS_LOG", tmp_path / "decisions.jsonl")
    monkeypatch.setattr(LK, "_U_BAR", None)
    # the autouse conftest stubs LK.lookup_answer to None for hermeticity; the fallback
    # path delegates to it, so restore the real one (the scripted brain keeps it hermetic)
    monkeypatch.setattr(LK, "lookup_answer", _real_lookup_answer)

    def forbidden(*a: Any, **k: Any) -> list[dict[str, Any]]:
        raise AssertionError("probe_corroborate must not run when not owner-scoped")

    monkeypatch.setattr(P, "probe_corroborate", forbidden)

    route = _RouteClient({"lookup": True, "construct": "partner ID",
                          "time_indexed": False})
    brain = Brain(_ScriptedTransport(optimise_action=0.0))
    baseline = [_hit("aa" * 32, "OWNER"), _hit("bb" * 32, "PARTNER")]
    result = gather_answer(None, migrated_root, "what is my partner's ID?", baseline,  # type: ignore[arg-type]
                           profile="", owner_scoped=False, brain=brain,
                           route_client=route, extract_client=_ChunkClient())
    assert result is not None
    assert result.n_hits == 2  # baseline only — gather was skipped


def test_gather_answer_none_when_not_routed(migrated_root: Path) -> None:
    route = _RouteClient({"lookup": False})
    assert gather_answer(None, migrated_root, "summarise my week", [],  # type: ignore[arg-type]
                         profile="", owner_scoped=False, route_client=route) is None


def test_gather_answer_none_on_zero_baseline_observations(migrated_root: Path) -> None:
    # owner-scoped, so the gather path runs; an empty chunk grounds nothing → no baseline
    # observations → None before any gather (the gather path's own coverage guard)
    route = _RouteClient({"lookup": True, "construct": "x"})
    brain = Brain(_ScriptedTransport())
    out = gather_answer(None, migrated_root, "what is my x?", [_hit("a" * 64, "")],  # type: ignore[arg-type]
                        profile="", owner_scoped=True, brain=brain,
                        route_client=route, extract_client=_ChunkClient())
    assert out is None  # coverage fallthrough — the narrative path answers
