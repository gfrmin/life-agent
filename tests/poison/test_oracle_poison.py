"""Poison fixtures for the register pins and the replay oracle — r23, K1 G4.

The §6 register pinned one artefact by EXISTENCE alone and three more by the needle
``"def test_"``, satisfied by any test in the file. So `collapse_replay.main` could be made
to `return 0` unconditionally — an oracle that can no longer fail — with every pin green
and no CI step exercising it. These fixtures are the positive control: they require the
oracle to prove it can still speak.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from life_agent.collapse import compare as CMP

_ROOT = Path(__file__).resolve().parents[2]


# --- F12: the oracle must be able to FAIL --------------------------------------------

def test_poison_the_oracle_reports_a_planted_mismatch() -> None:
    """F12. A deliberately-mismatched pair MUST produce a diff. This is the standing
    positive control: a green replay is only worth reading from a comparator that has just
    demonstrated it can go red."""
    # DECLARED fields (compare_body flags anything unclassified, so a fixture built from
    # invented keys would "pass" for the wrong reason — found while writing this).
    expected = {"decision": {"effector": "report", "eu": 0.90, "n_obs": 5}}
    actual = {"decision": {"effector": "abstain", "eu": 0.10, "n_obs": 1}}
    diffs = CMP.compare_body(expected, actual)
    assert diffs, (
        "the replay comparator found NO difference between a report and an abstain — the "
        "oracle cannot speak, and every 314/314 reading taken with it is worthless"
    )
    assert CMP.compare_body(expected, dict(expected)) == [], (
        "the comparator reports a difference between a body and itself"
    )


def test_poison_the_oracle_can_still_exit_nonzero(tmp_path: Path) -> None:
    """F12, the BEHAVIOURAL control. `main` was made to `return 0` before doing anything
    and every gate leg stayed green, because no CI step runs this script.

    An earlier version of this fixture asserted the SHAPE of main's returns via AST and
    did NOT go red under that mutation — `main` has other non-zero returns (argument
    errors), so an unconditional early `return 0` slipped past it. Disclosed in r23. The
    replacement drives the real entry point: pointed at a directory that does not exist,
    the oracle must report non-zero. An oracle that always returns 0 cannot.
    """
    sys.path.insert(0, str(_ROOT / "scripts"))
    import collapse_replay

    rc = collapse_replay.main(["--checkpoint", "nope",
                              "--fixtures", str(tmp_path / "absent")])
    assert rc != 0, (
        "collapse_replay.main returned 0 for a fixture set that does not exist — the "
        "oracle has been made unable to fail, and its register pin would not notice"
    )


def test_poison_register_pins_carry_a_specific_needle() -> None:
    """F12. A pin whose needle is `""` or `"def test_"` is satisfied by any file with any
    test in it, so the specific clause the entry stands for can be deleted with the pin
    green. Every needle must name something specific to its entry."""
    sys.path.insert(0, str(_ROOT / "tests"))
    from test_m7_register import _REGISTER_PINS

    vacuous = {k: n for k, (_, n) in _REGISTER_PINS.items()
               if not n.strip() or n.strip() == "def test_"}
    assert not vacuous, (
        f"§6 register pins with a needle that names nothing specific: {sorted(vacuous)} — "
        f"an existence-only pin lets its artefact be gutted while the guard stays green"
    )


# --- F11: the amounts guard must not be an identity ----------------------------------
# `AMOUNTS_PRODUCERS = (_ExtractAmountsProducer.name,)` and a guard asserting
# `set(AMOUNTS_PRODUCERS) == {ExtractAmountsProducer.name}` are the SAME expression. It
# caught the original defect only because it was run against pre-fix code; afterwards it is
# vacuously true. The thing actually being checked is `artifacts.producer_name` AS ALREADY
# RECORDED, which nothing in tree reads — so the recorded name is pinned as a literal that
# a rename has to walk past on purpose.

RECORDED_PRODUCER_NAME = "extract_amounts"


def test_poison_the_recorded_producer_name_is_pinned() -> None:
    """F11. Renaming the producer class orphans every artifact already derived under the
    old name (`producer_name` enters the cache key), restoring the permanent-`underived`
    loop this guard was opened for. A rename is a MIGRATION, and must fail here first."""
    from pkm.transforms.extract_amounts import ExtractAmountsProducer

    assert ExtractAmountsProducer.name == RECORDED_PRODUCER_NAME, (
        f"the producer now records {ExtractAmountsProducer.name!r} but the catalogue holds "
        f"rows under {RECORDED_PRODUCER_NAME!r} — a rename orphans every derived artifact "
        f"and needs a migration, not an edit. Update this pin only alongside one."
    )


def test_poison_the_demand_log_names_the_same_transform() -> None:
    """F11's collateral: `project_amounts` hard-codes `transform_name=` in the demand log,
    so after a rename the log names one transform while the filter matches another."""
    src = (_ROOT / "src" / "life_agent" / "core" / "aggregate.py").read_text()
    assert f'transform_name="{RECORDED_PRODUCER_NAME}"' in src, (
        "the demand log's transform_name disagrees with the recorded producer name"
    )


@pytest.mark.parametrize("leg", ["ruff", "pii"])
def test_gate_legs_are_reachable(leg: str) -> None:
    """A cheap positive control on the gate itself: each leg must actually run and be
    capable of a non-zero exit. `--help` proves the entry point resolves."""
    cmd = {"ruff": [sys.executable, "-m", "ruff", "--version"],
           "pii": [sys.executable, str(_ROOT / ".githooks" / "pii_check.py"),
                   "--shapes-only", "--nonexistent-flag-probe"]}[leg]
    r = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert r.returncode is not None
