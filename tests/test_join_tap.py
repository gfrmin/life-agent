"""r37 — the value-join tap: the instrument that makes the LIVE firing surface readable.

r36 killed r34's lever on K3, an attribution conjunct, because the census that enumerated its
firing surface read RECORDED wire — m5-base cassettes frozen on an older tree — while a live
run re-derives its own trajectory. The recorded surface is a **lower bound, not an
enumeration** (`r37-live-census-preregistration.md`).

The tap closes that gap: off by default, one env flag, and — the whole safety argument —
**the decision is always the deployed predicate's, flag on or flag off**. These tests are
that argument.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from life_agent.bridge import server as BR
from life_agent.core import config as CFG
from life_agent.core import lookup as LK

# PII-OK: synthetic amounts and reference codes. The first pair is the round-8 three-spelling
# split shape — one declared key, two normal forms — which is exactly where the two identities
# disagree; the rest are joins, mints and refusals that must be untouched by an observer.
POPULATION: list[tuple[str, list[str], bool]] = [
    ("HKD 12,345.67", ["HKD 12345.67"], True),          # declared merges, deployed mints
    ("12345.67 HKD", ["HKD 12345.67"], True),           # same, other spelling
    ("  p123 ", ["Q999", "P123"], True),                # both join (case+space)
    ("HKD 99999.99", ["HKD 12345.67"], True),           # both mint — different numbers
    ("Z777", ["P123"], True),                           # both mint — nothing near
    ("Z777", ["P123"], False),                          # both refuse — no allow_new
    ("9999 8888", ["8888"], False),   # PII-OK: synthetic — competing shape refused
    ("", ["P123"], True),                               # degenerate input
]


@pytest.fixture
def tap_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The tap, armed, writing to a temp path. One flag; the path is the declared constant."""
    log = tmp_path / "join-tap.jsonl"
    monkeypatch.setattr(CFG, "JOIN_TAP_LOG", log)
    monkeypatch.setenv(BR._JOIN_TAP_ENV, "1")
    return log


def _rows(log: Path) -> list[dict]:
    return [json.loads(ln) for ln in log.read_text(encoding="utf-8").splitlines() if ln.strip()]


def test_the_declared_log_path_is_outside_the_calibration_fold() -> None:
    """M-14: the tap is a diagnostic stream — recorded, never folded. A path under
    `calibration/` is one `rebuild` away from being evidence about the owner."""
    assert "calibration" not in CFG.JOIN_TAP_LOG.parts, (
        f"the tap log must not live in the calibration fold: {CFG.JOIN_TAP_LOG}")


def test_the_tap_is_off_by_default_and_writes_nothing(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """L1. Absence of the flag is the off state — not a default value, not a config file."""
    log = tmp_path / "join-tap.jsonl"
    monkeypatch.setattr(CFG, "JOIN_TAP_LOG", log)
    monkeypatch.delenv(BR._JOIN_TAP_ENV, raising=False)

    for value, candidates, allow_new in POPULATION:
        BR._lattice_join(value, candidates, allow_new)

    assert not log.exists(), "the tap wrote with the flag unset"


def test_the_tap_never_changes_the_decision(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """L2, and the whole safety argument: paired equivalence over the population. The
    m5-base replay CANNOT verify this — it serves /probe/* from cassettes and never enters
    the join at all (GD-7, amendment 1)."""
    monkeypatch.delenv(BR._JOIN_TAP_ENV, raising=False)
    off = [BR._lattice_join(v, c, a) for v, c, a in POPULATION]

    monkeypatch.setattr(CFG, "JOIN_TAP_LOG", tmp_path / "join-tap.jsonl")
    monkeypatch.setenv(BR._JOIN_TAP_ENV, "1")
    on = [BR._lattice_join(v, c, a) for v, c, a in POPULATION]

    assert on == off, "the tap changed a decision — it observes, it does not decide"


def test_the_deployed_identity_is_still_norm_value() -> None:
    """The revert stays in force. The tap parameterises the key so the counterfactual runs
    the SAME rule rather than a second copy of it (M-7) — which makes the default the thing
    that now carries the deployed identity, so the default is what gets pinned."""
    import inspect

    default = inspect.signature(BR._lattice_join).parameters["key"].default
    assert default is LK._norm_value, (
        "the deployed value-join must still test identity with _norm_value — r36's revert")


def test_a_disagreement_is_recorded_as_a_firing(tap_log: Path) -> None:
    """The lever's own case: one declared key, two normal forms. Deployed mints a second
    atom; the declared key joins the first."""
    idx, minted = BR._lattice_join("HKD 12,345.67", ["HKD 12345.67"], True)  # PII-OK
    assert (idx, minted) == (1, "HKD 12,345.67"), "the deployed decision is unchanged"

    rows = _rows(tap_log)
    assert len(rows) == 1
    assert rows[0]["fires"] is True
    assert rows[0]["deployed"] == {"idx": 1, "minted": "HKD 12,345.67"}
    assert rows[0]["declared"] == {"idx": 0, "minted": None}


def test_an_agreement_is_recorded_as_a_non_firing(tap_log: Path) -> None:
    """A call where the two identities agree is still recorded — the covered set is what
    makes L3's 'the questions both cover' computable rather than asserted."""
    BR._lattice_join("  p123 ", ["Q999", "P123"], True)  # PII-OK

    rows = _rows(tap_log)
    assert len(rows) == 1 and rows[0]["fires"] is False
    assert rows[0]["deployed"] == rows[0]["declared"] == {"idx": 1, "minted": None}


def test_every_call_is_recorded_so_the_surface_has_a_denominator(tap_log: Path) -> None:
    """G-3: an instrument must name the universe it checked. A log of firings alone cannot
    say what was looked at."""
    for value, candidates, allow_new in POPULATION:
        BR._lattice_join(value, candidates, allow_new)

    rows = _rows(tap_log)
    assert len(rows) == len(POPULATION), "the tap must record non-firings too"
    assert sum(r["fires"] for r in rows) == 2, "exactly the two spelling variants fire"


def test_the_row_carries_no_decision_id_and_no_credence(tap_log: Path) -> None:
    """M-14, structurally. The stream is unfoldable because it has nothing to fold: the
    fields are an allow-list, so a later edit cannot quietly make it evidence."""
    BR._lattice_join("HKD 12,345.67", ["HKD 12345.67"], True)  # PII-OK

    assert set(_rows(tap_log)[0]) == {
        "question_id", "url", "fires", "allow_new", "n_candidates",
        "value", "candidates", "deployed", "declared"}


def test_the_question_is_recorded_as_its_declared_id_not_as_text(
        tap_log: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """L3 needs the covered-question set; it does not need the question. The key is
    `decisions.question_id` — the ONE declared derivation of a question's identity, which the
    m5-base fixtures already key on, so the two surfaces align without a second hash. The tap
    first grew its own sha256 and the drift gate in tests/test_decisions.py caught it."""
    question = "what is the reference on the renewal notice?"  # PII-OK: synthetic question
    token = BR._TAP_CONTEXT.set(("/probe/deliberate", question))
    try:
        BR._lattice_join("Z777", ["P123"], True)  # PII-OK
    finally:
        BR._TAP_CONTEXT.reset(token)

    from life_agent.core import decisions as DEC

    row = _rows(tap_log)[0]
    assert row["url"] == "/probe/deliberate"
    assert row["question_id"] and question not in row["question_id"]
    assert row["question_id"] == DEC.question_id(question), (
        "the tap must key on the ONE declared question identity, not a second hash")


def test_the_tap_never_raises_onto_the_decision_path(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A diagnostic that can take down the decide path is not a diagnostic. The failure is
    swallowed at the tap and nowhere else — the join's contract is unchanged."""
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("", encoding="utf-8")
    monkeypatch.setattr(CFG, "JOIN_TAP_LOG", blocker / "join-tap.jsonl")
    monkeypatch.setenv(BR._JOIN_TAP_ENV, "1")

    assert BR._lattice_join("  p123 ", ["Q999", "P123"], True) == (1, None)  # PII-OK


def test_the_dispatcher_is_what_supplies_the_context() -> None:
    """One home for the context, not two probe handlers wired separately: `dispatch` sets it
    from the request, so any endpoint that joins is covered without its own edit."""
    import _guard_ast as G

    assert G.calls(BR.dispatch, "_tap_context"), (
        "dispatch must set the tap context — a per-handler wiring is a second declaration")
