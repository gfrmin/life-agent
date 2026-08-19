"""The ``extract@<model>`` edge (core/joint_extract.py) — hermetic, no network.

A stub completion stands in for the cloud model so we can pin the edge's contract: cache-first
(a re-ask costs nothing), attribution-withhold (a null reply is a withhold, never a guess),
fail-safe parsing, and that the cache key tracks the ORDERED chunk-set (the early-cutoff hinge).
"""
from __future__ import annotations

import json
from pathlib import Path

from life_agent.core.joint_extract import JointResult, extract_joint
from life_agent.core.llm import LLMResult


class _Stub:
    """A scripted completion that counts calls — proves cache-first (no second call)."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.calls = 0

    def __call__(self, system: str, user: str, model: str, max_tokens: int) -> LLMResult:
        self.calls += 1
        return LLMResult(self.text, 120, 12, 0.0, served_model=model)


def _hits(*texts: str) -> list[dict[str, object]]:
    return [{"chunk_text": t, "artifact_cache_key": f"{i:064d}"} for i, t in enumerate(texts)]


def test_extract_joint_parses_and_is_cache_first(tmp_path: Path) -> None:
    stub = _Stub('{"value": "VAL", "confidence": 0.9, "as_of": "2024-01-01"}')
    hits = _hits("a document about the owner")
    r1 = extract_joint(tmp_path, "what is my X?", hits,
                       model="claude-opus-4-8-20260101", complete=stub)
    assert (r1.value, r1.confidence, r1.as_of) == ("VAL", 0.9, "2024-01-01")
    assert r1.in_tokens == 120 and stub.calls == 1
    # re-ask: cache hit, no second model call, zero spend
    r2 = extract_joint(tmp_path, "what is my X?", hits,
                       model="claude-opus-4-8-20260101", complete=stub)
    assert stub.calls == 1
    assert r2.value == "VAL" and r2.in_tokens == 0 and r2.cache_key == r1.cache_key


def test_null_value_is_a_withhold(tmp_path: Path) -> None:
    # the attribution case: the model declines (someone else's value) → null, zero confidence
    stub = _Stub('{"value": null, "confidence": 0.0, "as_of": null}')
    r = extract_joint(tmp_path, "what is my passport number?", _hits("a relative's passport"),
                      model="m-2026", complete=stub)
    assert r.value is None and r.confidence == 0.0


def test_garbled_reply_fails_safe(tmp_path: Path) -> None:
    r = extract_joint(tmp_path, "q?", _hits("x"), model="m-2026",
                      complete=_Stub("sorry, I could not produce JSON"))
    assert isinstance(r, JointResult)
    assert r.value is None and r.confidence == 0.0


def test_chunk_set_order_changes_the_key(tmp_path: Path) -> None:
    stub = _Stub('{"value": "V", "confidence": 0.5, "as_of": null}')
    a, b = "alpha document", "beta document"
    k_ab = extract_joint(tmp_path, "q", _hits(a, b), model="m-2026", complete=stub).cache_key
    k_ba = extract_joint(tmp_path, "q", _hits(b, a), model="m-2026", complete=stub).cache_key
    assert k_ab != k_ba  # the ordered chunk-set is the early-cutoff hinge


def test_model_snapshot_changes_the_key(tmp_path: Path) -> None:
    stub = _Stub('{"value": "V", "confidence": 0.5, "as_of": null}')
    hits = _hits("doc")
    k1 = extract_joint(tmp_path, "q", hits, model="claude-opus-4-8-20260101",
                       complete=stub).cache_key
    k2 = extract_joint(tmp_path, "q", hits, model="claude-opus-4-8-20260202",
                       complete=stub).cache_key
    assert k1 != k2  # a dated-snapshot roll must not serve a stale cache entry


def test_lineage_inputs_are_unique_first_occurrence_order(tmp_path: Path) -> None:
    """Several hits of one artefact ⇒ ONE lineage entry for it (§18.9: the catalogue's
    ``artifact_lineage`` key is (artifact, input) — a repeated input rolls the whole row
    back). Order of first occurrence is preserved (the pool order is the key's hinge)."""
    from life_agent.core import derivations as D
    stub = _Stub('{"value": "VAL", "confidence": 0.9, "as_of": "2024-01-01"}')
    hits = _hits("chunk one of A", "chunk of B", "chunk two of A", "chunk of C")
    hits[2]["artifact_cache_key"] = hits[0]["artifact_cache_key"]      # A twice
    r = extract_joint(tmp_path, "what is my X?", hits,
                      model="claude-opus-4-8-20260101", complete=stub)
    lineage = json.loads(D.lineage_file(tmp_path, r.cache_key).read_text())["inputs"]
    keys = [e["cache_key"] for e in lineage]
    assert keys == [hits[0]["artifact_cache_key"], hits[1]["artifact_cache_key"],
                    hits[3]["artifact_cache_key"]]
    assert {e["role"] for e in lineage} == {"joint_source"}
