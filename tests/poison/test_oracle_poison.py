"""Poison fixtures for the register pins and the replay oracle — r23, K1 G4.

The §6 register pinned one artefact by EXISTENCE alone and three more by the needle
``"def test_"``, satisfied by any test in the file. So `collapse_replay.main` could be made
to `return 0` unconditionally — an oracle that can no longer fail — with every pin green
and no CI step exercising it. These fixtures are the positive control: they require the
oracle to prove it can still speak.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from life_agent.collapse import compare as CMP
from life_agent.collapse import fixture as FX

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


# --- K3 / D-b: a control must DISCRIMINATE ------------------------------------------
# This asserted `r.returncode is not None` — true of every subprocess that completed, so it
# could not fail for any input and proved nothing about either leg. `--version` and an
# unknown-flag probe do not exercise a gate; they exercise argument parsing. Each leg is now
# driven over a CLEAN input (must pass) and a PLANTED violation (must fail), which is the
# only pair that distinguishes a working gate from a gate that has been made unable to fail.

#: (leg, clean file body, violating file body, the marker the failure must carry).
_LEG_CASES: tuple[tuple[str, str, str, str], ...] = (
    ("ruff", "x = 1\n", "import os\nx = 1\n", "F401"),
    # A checksum-invalid, synthetic IL mobile in a labelled context — the shape layer's
    # job, and one that needs no private denylist, so this runs in CI.
    # PII-OK: synthetic all-zero mobile below, shape only — no real value, no name
    ("pii", "the number is withheld\n", "mobile: 050-000-0000\n",  # PII-OK: synthetic
     "pii_check BLOCKED"),
)


@pytest.mark.parametrize(("leg", "clean", "violating", "marker"), _LEG_CASES)
def test_gate_legs_discriminate(leg: str, clean: str, violating: str, marker: str,
                                tmp_path: Path) -> None:
    """D-b. Each gate leg must PASS a clean input and FAIL a planted violation.

    Verified RED by mutation before landing, and the result is narrower than the first
    attempt claimed — recorded here because the gap is the interesting part:

      * `ruff`  — disabling the selected rule set makes this RED.
      * `pii`   — the probe carries a LABELLED number, so it is the labelled IL-mobile
                  rule that is load-bearing. Neutering it: RED. Neutering the *bare*
                  IL-mobile rule alone: still green, because the labelled rule shadows
                  this probe. So this control proves the leg RUNS and CAN FAIL; it does
                  NOT prove every shape is live. Per-shape coverage is row 13's job
                  (`tests/poison/test_pii_poison.py` removes each of seven individually)
                  and is deliberately not duplicated here.

    The first mutation attempt reported a false ALL-CLEAR: its regex only reached rules
    whose pattern sits on the same line as `re.compile(`, so the two multi-line ones were
    never neutered and the control looked unkillable. The mutation was one spelling wide,
    not the control — but an incomplete mutation reads exactly like a dead guard, which is
    why each site is now neutered by name.
    """
    def _run(body: str) -> subprocess.CompletedProcess[str]:
        target = tmp_path / f"{leg}_probe.py"
        target.write_text(body, encoding="utf-8")
        cmd = {
            "ruff": [sys.executable, "-m", "ruff", "check", "--isolated",
                     "--select", "F", str(target)],
            "pii": [sys.executable, str(_ROOT / ".githooks" / "pii_check.py"),
                    "--shapes-only", str(target)],
        }[leg]
        return subprocess.run(cmd, capture_output=True, text=True, check=False,
                              cwd=str(_ROOT))

    ok = _run(clean)
    assert ok.returncode == 0, (
        f"the {leg} leg rejected a CLEAN input (exit {ok.returncode}) — it is not "
        f"discriminating, it is refusing everything:\n{ok.stdout}\n{ok.stderr}"
    )

    bad = _run(violating)
    assert bad.returncode != 0, (
        f"the {leg} leg accepted a planted violation — the leg has been made unable to "
        f"fail, and every green run of it means nothing:\n{bad.stdout}\n{bad.stderr}"
    )
    assert marker in (bad.stdout + bad.stderr), (
        f"the {leg} leg exited non-zero but never named {marker!r} — it failed for some "
        f"other reason (a crash, a bad path), not for the planted violation:\n"
        f"{bad.stdout}\n{bad.stderr}"
    )


# --- K3 / D-a: the oracle's WIRING, not just its parts -------------------------------
# The two controls above prove the comparator detects a planted mismatch (in isolation) and
# that `main` can return non-zero (at a missing directory — `collapse_replay.py:122`, three
# checks BEFORE the compare loop). Neither proves the two are connected. These mutations
# leave both green and still print "N/N fixtures replay identically":
#     diffs = []                     # inside the loop, discarding the comparison
#     if diffs: ...  ->  pass        # the comparison happens and is dropped
#     bad = len(errored)             # failures counted but not exited on
# So the control below drives the REAL entry point over a REAL fixture set. A `seam`-trace
# fixture needs no wire and no snapshot (`collapse_replay.replay_fixture` dispatches it
# straight to `drive_seam_unavailable`), and `provenance` without `python_hash_seed` skips
# the seed refusal — so the set can be built in a tmpdir and run anywhere, CI included.

_CONTROL_MATCH = "zzz-control-agrees"
_CONTROL_MISMATCH = "zzz-control-diverges"


def _seam_fixture(fixture_id: str, outputs: dict[str, Any]) -> FX.Fixture:
    return FX.Fixture(
        fixture_id=fixture_id, checkpoint="k3-control", trace="seam",
        classes=("terminal:abstain",), question="what is my declared control value?",
        question_id=fixture_id, inputs={}, outputs=outputs,
        # No `python_hash_seed`: this set is not hash-order dependent (no dedup runs), and
        # recording one would make the control refuse under any other seed.
        provenance={"engine_version": "control"},
    )


def _control_set(directory: Path) -> None:
    """One fixture that MUST agree and one that MUST NOT, in a fresh directory."""
    from life_agent.collapse import drive as DR

    truth = DR.drive_seam_unavailable("what is my declared control value?")
    FX.write(directory, _seam_fixture(_CONTROL_MATCH, truth))

    diverged = json.loads(json.dumps(truth))          # deep copy, no shared substructure
    diverged["log_decision"]["decision"]["effector"] = "report"
    diverged["log_decision"]["decision"]["eu"] = 0.99
    assert diverged != truth, "the control's planted divergence did not change the body"
    FX.write(directory, _seam_fixture(_CONTROL_MISMATCH, diverged))


def test_poison_the_oracle_detects_a_mismatch_end_to_end(tmp_path: Path,
                                                         capsys: pytest.CaptureFixture[str],
                                                         ) -> None:
    """D-a. Drives `collapse_replay.main` over a two-fixture set through the compare loop.

    Verified RED by mutation before landing, against all three survivable mutations named
    above: each one leaves the two older controls green and this one red.
    """
    sys.path.insert(0, str(_ROOT / "scripts"))
    import collapse_replay

    _control_set(tmp_path)
    rc = collapse_replay.main(["--checkpoint", "k3-control", "--fixtures", str(tmp_path)])
    out = capsys.readouterr().out

    assert rc == 1, (
        f"the oracle replayed a deliberately divergent fixture and exited {rc} — the "
        f"comparison never reached the exit code, and every N/N reading taken with this "
        f"oracle is worthless. Output:\n{out}"
    )
    assert _CONTROL_MISMATCH in out, (
        f"the oracle exited non-zero but never named the divergent fixture "
        f"{_CONTROL_MISMATCH!r} — it failed for some other reason. Output:\n{out}"
    )
    assert f"mismatched: {_CONTROL_MISMATCH}" in out, (
        f"the divergent fixture was not counted as MISMATCHED (it may have ERRORED, which "
        f"exits non-zero without the comparator having run). Output:\n{out}"
    )
    assert _CONTROL_MATCH not in out.split("mismatched:")[-1], (
        f"the agreeing fixture was also reported as mismatched — the comparator is "
        f"flagging identical bodies. Output:\n{out}"
    )
