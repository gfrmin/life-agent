"""The decision log (bayesian-foundations §8) — no EU decision is ever made unlogged.

Mirrors the outcomes-log discipline: append-only JSONL, file order = canonical replay
order, closed vocabularies validated at construction, durable appends, loud corruption.

Run: uv run --project . python -m pytest tests/test_decisions.py
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from life_agent.core import decisions as D


def _event(**overrides: object) -> D.DecisionEvent:
    base: dict = dict(
        tx_time="2026-06-12T12:00:00+00:00",
        run_id="ask-test",
        question_id="q-001",
        family="lookup",
        action_set=("report", "hedge", "ask_clarify", "abstain"),
        posterior_summary={"top_claim_credence": 0.92, "n_claims": 1},
        utility_fold_version="a" * 64,
        chosen_action="report",
        predicted_eu=0.87,
    )
    base.update(overrides)
    return D.DecisionEvent(**base)  # type: ignore[arg-type]


# --- closed vocabularies -----------------------------------------------------------------

def test_unknown_family_rejected() -> None:
    with pytest.raises(ValueError, match="family"):
        _event(family="vibes")


def test_action_outside_vocabulary_rejected() -> None:
    with pytest.raises(ValueError, match="action"):
        _event(action_set=("report", "shrug"))


def test_chosen_action_must_be_in_action_set() -> None:
    with pytest.raises(ValueError, match="chosen"):
        _event(chosen_action="abstain", action_set=("report", "hedge"))


def test_empty_action_set_rejected() -> None:
    with pytest.raises(ValueError, match="action_set"):
        _event(action_set=())


# --- append-only round trip --------------------------------------------------------------

def test_round_trip_and_order(tmp_path: Path) -> None:
    log = tmp_path / "calibration" / "decisions.jsonl"
    first = _event(question_id="q-001")
    second = _event(question_id="q-002", chosen_action="abstain", predicted_eu=0.0)
    D.append(log, first)
    D.append(log, second)
    assert D.read(log) == [first, second]
    assert len(log.read_text(encoding="utf-8").splitlines()) == 2


def test_read_missing_is_empty(tmp_path: Path) -> None:
    assert D.read(tmp_path / "absent.jsonl") == []


def test_lines_are_canonical_json(tmp_path: Path) -> None:
    log = tmp_path / "decisions.jsonl"
    D.append(log, _event())
    line = log.read_text(encoding="utf-8").splitlines()[0]
    obj = json.loads(line)
    assert obj["format_version"] == D.FORMAT_VERSION
    assert line == json.dumps(obj, sort_keys=True, ensure_ascii=False,
                              separators=(",", ":"))


def test_pricing_and_instrument_fields_round_trip(tmp_path: Path) -> None:
    # §10 accounting on the ledger: the edge that answered, at what dollar/latency cost.
    log = tmp_path / "decisions.jsonl"
    priced = _event(instrument="deliberate@claude-opus-4-8",
                    cost_usd=0.42, latency_s=23.1)
    D.append(log, priced)
    (back,) = D.read(log)
    assert back.instrument == "deliberate@claude-opus-4-8"
    assert back.cost_usd == 0.42
    assert back.latency_s == 23.1


def test_pre_pricing_lines_still_read(tmp_path: Path) -> None:
    # Lines appended before format_version 2 carry no pricing keys — they must replay.
    log = tmp_path / "decisions.jsonl"
    D.append(log, _event())
    line = json.loads(log.read_text(encoding="utf-8"))
    for legacy_absent in ("instrument", "cost_usd", "latency_s"):
        line.pop(legacy_absent)
    line["format_version"] = 1
    log.write_text(json.dumps(line, sort_keys=True, separators=(",", ":")) + "\n",
                   encoding="utf-8")
    (back,) = D.read(log)
    assert back.instrument == ""
    assert back.cost_usd is None
    assert back.latency_s is None
    assert back.format_version == 1


def test_corrupt_line_is_loud(tmp_path: Path) -> None:
    log = tmp_path / "decisions.jsonl"
    log.write_text('{"oops": true}\n', encoding="utf-8")
    with pytest.raises((KeyError, TypeError, ValueError)):
        D.read(log)


# --- question_id: ONE derivation, drift-gated --------------------------------------------
#
# A second, hand-copied spelling of this hash silently SPLITS the id namespace, and every
# join across it then reads as "no data" rather than as an error. That is not hypothetical:
# the membrane shadow's grounded join shipped structurally impossible (always 0 rows) and
# the report narrated it as an under-powered sample, because the derivation was inline in
# four call sites and nothing gated a fifth.


def test_question_id_is_sha256_of_the_raw_text_truncated() -> None:
    import hashlib

    text = "What colour is the shed?"
    expected = hashlib.sha256(text.encode("utf-8")).hexdigest()[: D.QUESTION_ID_CHARS]
    assert D.question_id(text) == expected
    assert len(D.question_id(text)) == 16
    assert D.question_id("a") != D.question_id("b")


def test_no_other_site_hashes_a_question_itself() -> None:
    """The drift gate: nothing under src/ or scripts/ may hash question TEXT into an id
    except ``decisions.question_id``. The pattern matches a hash call applied to the bare
    ``question`` value — both spellings that were live before this was extracted
    (``hashlib.sha256(question.encode(...))`` in four modules, ``_sha(question)[:16]`` in
    two more, plus a fifth in ``scripts/verdict.py``), while leaving hashes of OTHER things
    (a questions FILE, an answer, a ledger) alone."""
    import re

    root = Path(__file__).resolve().parent.parent
    pattern = re.compile(r"(sha256|_sha)\(\s*question\s*[.)]")
    offenders = [
        f"{path.relative_to(root)}:{i}"
        for folder in ("src", "scripts")
        for path in (root / folder).rglob("*.py")
        if path != root / "src" / "life_agent" / "core" / "decisions.py"
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if pattern.search(line)
    ]
    assert offenders == [], (
        "these sites hash the question text themselves instead of deriving from "
        f"decisions.question_id(): {offenders}"
    )
