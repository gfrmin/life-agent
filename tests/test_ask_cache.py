"""The cached ask DAG (scripts/ask.py + life_agent.core.derivations) — the north star's
literal correctness criterion, as tests:

    same question + unchanged corpus  → identical answer from cache at ZERO marginal cost
    a changed input                   → invalidation exactly as far as necessary, no further

Hermetic: counting fakes for the LLM and FTS, a tmp knowledge root, a controllable corpus
digest. No live catalogue, no API.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import ask

from life_agent import owner

HIT = {"artifact_cache_key": "1" * 64, "chunk_text": "salary is 100 [doc]",
       "score": 9.0, "origin": "/data/contract.pdf"}
OTHER_HIT = {"artifact_cache_key": "2" * 64, "chunk_text": "a different chunk",
             "score": 8.0, "origin": "/data/other.pdf"}


class Harness:
    """Counting fakes around answer(): every impure edge is observable."""

    def __init__(self) -> None:
        self.llm_calls: list[str] = []      # "expand" | "synthesize"
        self.search_calls = 0
        self.digest = "e" * 64
        self.hits = [dict(HIT)]
        self.profile = ""

    def llm(self, system: str, user: str, **kw: Any) -> SimpleNamespace:
        stage = "expand" if system == ask.EXPAND_SYSTEM else "synthesize"
        self.llm_calls.append(stage)
        text = "income salary invoice" if stage == "expand" else "the answer [1]"
        return SimpleNamespace(text=text, in_tokens=10, out_tokens=5, seconds=0.01)

    def retrieve_set(self, conn: Any, query: str, k: int) -> list[dict[str, Any]]:
        self.search_calls += 1
        return [dict(h) for h in self.hits]


@pytest.fixture
def h(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Harness:
    harness = Harness()
    monkeypatch.setattr(ask.TERM, "_pkm_root", lambda: tmp_path)
    monkeypatch.setattr(ask.TERM, "_corpus_digest", lambda conn: harness.digest)
    monkeypatch.setattr(ask.TERM, "_retrieve_set", harness.retrieve_set)
    monkeypatch.setattr(ask.C, "anthropic_complete", harness.llm)
    monkeypatch.setattr(owner, "load_profile", lambda: harness.profile)
    ask.reset_cache_stats()
    return harness


def _ask(question: str = "how do i make money", **kw: Any):
    return ask.answer(conn=None, question=question, k=8, **kw)


# --- the literal correctness criterion -------------------------------------- #

def test_replay_is_a_cache_hit_at_zero_marginal_cost(h: Harness, capsys) -> None:
    first = _ask()
    assert h.llm_calls == ["expand", "synthesize"]
    assert h.search_calls == 1

    second = _ask()
    # ZERO marginal cost: no new LLM call, no new FTS search
    assert h.llm_calls == ["expand", "synthesize"]
    assert h.search_calls == 1
    # identical answer, cards, and scores
    assert second == first
    assert ask.cache_stats() == {"expand.miss": 1, "retrieve.miss": 1, "synthesize.miss": 1,
                                 "expand.hit": 1, "retrieve.hit": 1, "synthesize.hit": 1}


# --- early cutoff at the retrieval boundary --------------------------------- #

def test_corpus_growth_with_unchanged_evidence_replays_the_answer(h: Harness) -> None:
    first = _ask()
    h.digest = "f" * 64  # the corpus changed (e.g. new mail ingested) ...
    second = _ask()      # ... but this question retrieves the same evidence

    # retrieve recomputed (new corpus state), synthesize replayed (same evidence)
    assert h.search_calls == 2
    assert h.llm_calls == ["expand", "synthesize"]  # no second synthesis
    assert second == first
    stats = ask.cache_stats()
    assert stats["retrieve.miss"] == 2 and stats["synthesize.hit"] == 1


# --- exact invalidation: each input invalidates its stage, nothing else ----- #

def test_profile_change_invalidates_only_synthesis(h: Harness) -> None:
    _ask()
    h.profile = "# Owner\nName: Ada Lovelace.\n"  # the owner taught a fact
    _ask()
    stats = ask.cache_stats()
    assert stats["expand.hit"] == 1        # question unchanged
    assert stats["retrieve.hit"] == 1      # corpus unchanged
    assert stats["synthesize.miss"] == 2   # identity lens changed → fresh synthesis
    assert h.llm_calls == ["expand", "synthesize", "synthesize"]


def test_question_change_invalidates_everything(h: Harness) -> None:
    _ask("how do i make money")
    _ask("what is my id number")
    stats = ask.cache_stats()
    assert stats == {"expand.miss": 2, "retrieve.miss": 2, "synthesize.miss": 2}
    assert h.search_calls == 2


def test_changed_evidence_invalidates_synthesis(h: Harness) -> None:
    _ask()
    h.digest = "f" * 64           # corpus changed ...
    h.hits = [dict(OTHER_HIT)]    # ... and this time the evidence actually differs
    _ask()
    stats = ask.cache_stats()
    assert stats["synthesize.miss"] == 2
    assert h.llm_calls == ["expand", "synthesize", "synthesize"]


# --- abstention -------------------------------------------------------------- #

def test_stages_last_exposes_this_answers_stage_keys(h: Harness) -> None:
    _ask()
    first = dict(ask.TERM.STAGES_LAST)
    assert set(first) == {"retrieve", "synthesize"}
    _ask()  # replay: the same derivation, so the same keys (hit or miss alike)
    assert first == ask.TERM.STAGES_LAST


def test_no_cache_recomputes_but_never_overwrites(h: Harness) -> None:
    first = _ask()
    second = _ask(no_cache=True)   # recompute every stage ...
    assert h.llm_calls == ["expand", "synthesize", "expand", "synthesize"]
    assert second == first         # ... same derivation either way (counting fake is stable)
    third = _ask()                 # the original recording still stands and replays
    assert h.llm_calls == ["expand", "synthesize", "expand", "synthesize"]
    assert third == first


def test_unresolvable_root_fails_open(h: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ask.TERM, "_pkm_root", lambda: None)
    first = _ask()
    second = _ask()
    assert second == first
    assert h.llm_calls == ["expand", "synthesize"] * 2  # computed fresh both times
    assert ask.cache_stats() == {}                      # caching genuinely off, not erroring


def test_failing_corpus_digest_disables_only_the_retrieve_stage(h: Harness) -> None:
    # digest unavailable (fail-open): retrieval can't be keyed, but the corpus-independent
    # expand stage and the content-keyed synthesize stage still cache
    h.digest = None  # type: ignore[assignment]
    first = _ask()
    second = _ask()
    assert second == first
    assert h.search_calls == 2  # retrieval recomputed each time (no key without a digest)
    stats = ask.cache_stats()
    assert stats["expand.hit"] == 1
    assert stats["synthesize.hit"] == 1
    assert "retrieve.hit" not in stats and "retrieve.miss" not in stats
