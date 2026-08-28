"""The real-ask harvest: recovers what was actually asked, and never prints it.

Run: uv run --project . python -m pytest tests/test_harvest_real_asks.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import harvest_real_asks as H

from life_agent.core import decisions as DEC

_Q = "what is the synthetic serial?"          # PII-OK: synthetic question
_Q2 = "when does the synthetic policy renew?"  # PII-OK: synthetic question


def _cache(root: Path, question: str, producer: str, at: str, key: str) -> None:
    d = root / key[:2] / key[2:]
    d.mkdir(parents=True)
    (d / "meta.json").write_text(json.dumps({
        "producer_name": producer, "produced_at": at,
        "producer_metadata": {"inputs": {"question": question}},
    }), encoding="utf-8")


def test_a_question_is_recovered_from_the_cache(tmp_path: Path) -> None:
    """The decision row carries no text; the derivation's recorded inputs do."""
    cache = tmp_path / "cache"
    _cache(cache, _Q, "life_agent.ask.lookup_route", "2026-08-01T00:00:00", "aa" + "0" * 8)
    rows = H.harvest(cache, tmp_path / "missing.jsonl")
    assert [r["question"] for r in rows] == [_Q]
    assert rows[0]["producers"] == ["lookup_route"]


def test_the_question_id_is_the_deployed_derivation(tmp_path: Path) -> None:
    """The join key must be `DEC.question_id`, not a copy of its algorithm — a census that
    re-implements the constant it prices is this register's entry 1."""
    cache = tmp_path / "cache"
    _cache(cache, _Q, "life_agent.ask.expand", "2026-08-01T00:00:00", "bb" + "0" * 8)
    assert H.harvest(cache, tmp_path / "missing.jsonl")[0]["question_id"] == \
        DEC.question_id(_Q)


def test_non_ask_producers_and_questionless_inputs_are_ignored(tmp_path: Path) -> None:
    """The universe is the question-keyed ask namespace; an email or a pandoc artefact
    carries no question and must not become a row."""
    cache = tmp_path / "cache"
    _cache(cache, _Q, "email", "2026-08-01T00:00:00", "cc" + "0" * 8)
    _cache(cache, _Q2, "life_agent.ask.synthesize", "2026-08-02T00:00:00", "dd" + "0" * 8)
    assert [r["question"] for r in H.harvest(cache, tmp_path / "missing.jsonl")] == [_Q2]


def test_gate_rows_do_not_count_as_having_been_asked(tmp_path: Path) -> None:
    """A gate row is the AUTHORED corpus replaying. Letting it join would report the
    authored population back as if it were the asked one — the exact conflation this
    harvest exists to end."""
    cache = tmp_path / "cache"
    _cache(cache, _Q, "life_agent.ask.lookup_route", "2026-08-01T00:00:00", "ee" + "0" * 8)
    dec = tmp_path / "decisions.jsonl"
    dec.write_text(json.dumps({"question_id": DEC.question_id(_Q), "run_id": "gate-2026",
                               "family": "lookup", "chosen_action": "report",
                               "tx_time": "2026-08-01T00:00:00+00:00"}) + "\n",
                   encoding="utf-8")
    assert H.harvest(cache, dec)[0]["decided"] is False


def test_a_live_decision_joins_by_question_id(tmp_path: Path) -> None:
    """The discriminating half: the filter must reject gate rows WITHOUT rejecting live
    ones, or it is a join that joins nothing."""
    cache = tmp_path / "cache"
    _cache(cache, _Q, "life_agent.ask.lookup_route", "2026-08-01T00:00:00", "ff" + "0" * 8)
    dec = tmp_path / "decisions.jsonl"
    dec.write_text(json.dumps({"question_id": DEC.question_id(_Q), "run_id": "ask",
                               "family": "lookup", "chosen_action": "abstain",
                               "tx_time": "2026-08-01T00:00:00+00:00"}) + "\n",
                   encoding="utf-8")
    row = H.harvest(cache, dec)[0]
    assert row["decided"] is True and row["chosen_action"] == "abstain"


def test_the_rendered_summary_carries_no_question_text(tmp_path: Path) -> None:
    """C1, the binding property. Every harvested question is a real question about a real
    corpus and this repo is public. The summary is counts, mixes and a span — nothing that
    could reconstruct a question, and no count paired with an identifier."""
    cache = tmp_path / "cache"
    _cache(cache, _Q, "life_agent.ask.lookup_route", "2026-08-01T00:00:00", "aa" + "1" * 8)
    _cache(cache, _Q2, "life_agent.ask.synthesize", "2026-08-03T00:00:00", "bb" + "1" * 8)
    rows = H.harvest(cache, tmp_path / "missing.jsonl")
    text = H.render(H.summary(rows))
    for q in (_Q, _Q2):
        assert q not in text, "a whole question reached the summary"
        # Distinctive tokens only: a leak is a CONTENT word, and asserting on stopwords
        # would make this fire on "the" in "decided by the arm" — a nuisance guard gets
        # weakened, and a weakened guard is how the corpus reached the public tree once
        # already.
        for word in {w.strip("?.,").lower() for w in q.split() if len(w.strip("?.,")) > 4}:
            assert word not in text.lower(), (
                f"a content word from a real question reached the summary: {word!r}")
    assert "2 distinct" in text and "2026-08-01" in text and "2026-08-03" in text
