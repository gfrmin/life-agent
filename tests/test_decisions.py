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


# --- regime + policy: the two fields the module collapse's record needs (M0) -------------

def test_regime_and_policy_are_closed_vocabularies() -> None:
    """Same discipline as `family` and `action_set`: junk fails at construction, never
    silently onto the ledger."""
    base = dict(tx_time="2026-08-19T00:00:00+00:00", run_id="r", question_id="q",
                family="lookup", action_set=D.LOOKUP_ACTION_ORDER,
                posterior_summary={}, utility_fold_version="v", chosen_action="abstain",
                predicted_eu=0.0)
    with pytest.raises(ValueError, match="regime"):
        D.DecisionEvent(**base, regime="fallback-lane")
    with pytest.raises(ValueError, match="policy"):
        D.DecisionEvent(**base, policy="vibes")


def test_regime_and_policy_default_to_the_declared_defaults() -> None:
    """A v1/v2 line replays at the honest default — the fold must never see an empty
    regime it has to guess about."""
    line = ('{"tx_time":"2026-08-19T00:00:00+00:00","run_id":"r","question_id":"q",'
            '"family":"lookup","action_set":["report","hedge","ask_clarify","abstain",'
            '"report_scoped"],"posterior_summary":{},"utility_fold_version":"v",'
            '"chosen_action":"abstain","predicted_eu":0.0,"format_version":2}')
    ev = D._from_line(line)
    assert ev.regime == D.REGIME_DEFAULT and ev.policy == D.POLICY_DEFAULT
    # a legacy line stated NEITHER field, and says so — the value is interpretable and the
    # claim is not overstated
    assert ev.defaulted == ("policy", "regime")


def test_unavailability_is_a_regime_not_an_action() -> None:
    """§6.5: when no optimiser is available there is no ranking to be inside of. The
    vocabulary carries `unavailable` as a REGIME so an unavailability can never fold as an
    abstain verdict (R-3 folds abstains as utility evidence)."""
    assert "unavailable" in D.REGIMES
    assert "unavailable" not in D.ACTIONS


# --- r31: an append-only stream outlives the vocabulary that wrote it --------------------

def test_retired_families_are_declared_and_disjoint() -> None:
    """R1 — the retired vocabulary is a CLOSED declared set, and a label cannot be both
    writable and retired."""
    assert D.RETIRED_FAMILIES
    assert not (D.FAMILIES & D.RETIRED_FAMILIES)
    assert "aggregate" in D.RETIRED_FAMILIES     # K1 deleted it; run 19 had already written it


def test_a_writer_still_cannot_emit_a_retired_family() -> None:
    """R2 — tolerance is READ-side only. Nothing may write one again."""
    with pytest.raises(ValueError, match="aggregate"):
        D.DecisionEvent(tx_time="2026-01-01T00:00:00Z", run_id="r", question_id="q",
                          family="aggregate", action_set=("report", "abstain"),
                          posterior_summary={}, utility_fold_version="v",
                          chosen_action="abstain", predicted_eu=0.0, decision_id="d")


def test_read_skips_a_retired_family_row_and_names_the_count(tmp_path, capsys) -> None:
    """R3 — two rows of history must not make a 3,391-row log unreadable. The skip is
    NAMED: a reader that silently drops rows is how a stream loses its own history."""
    p = tmp_path / "decisions.jsonl"
    good = {"format_version": 3, "tx_time": "2026-01-01T00:00:00Z", "run_id": "r",
            "question_id": "q1", "family": "lookup", "action_set": ["report", "abstain"],
            "posterior_summary": {}, "utility_fold_version": "v",
            "chosen_action": "abstain", "predicted_eu": 0.0, "decision_id": "d1"}
    retired = {**good, "question_id": "q2", "family": "aggregate", "decision_id": "d2"}
    p.write_text("\n".join(json.dumps(r) for r in (good, retired, good)) + "\n",
                 encoding="utf-8")
    rows = D.read(p)
    assert [r.family for r in rows] == ["lookup", "lookup"]
    assert "1" in capsys.readouterr().out          # the skipped count is named, not silent


def test_read_still_raises_on_a_genuinely_unknown_family(tmp_path) -> None:
    """R4 — tolerance is ENUMERATED. A typo or a corrupted row is still a hard error."""
    p = tmp_path / "decisions.jsonl"
    p.write_text(json.dumps(
        {"format_version": 3, "tx_time": "2026-01-01T00:00:00Z", "run_id": "r",
         "question_id": "q", "family": "lookkup", "action_set": ["report", "abstain"],
         "posterior_summary": {}, "utility_fold_version": "v",
         "chosen_action": "abstain", "predicted_eu": 0.0, "decision_id": "d"}) + "\n",
        encoding="utf-8")
    with pytest.raises(ValueError, match="lookkup"):
        D.read(p)
