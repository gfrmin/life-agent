"""Poison fixtures for the register pins and the replay oracle — r23, K1 G4.

The §6 register pinned one artefact by EXISTENCE alone and three more by the needle
``"def test_"``, satisfied by any test in the file. So `collapse_replay.main` could be made
to `return 0` unconditionally — an oracle that can no longer fail — with every pin green
and no CI step exercising it. These fixtures are the positive control: they require the
oracle to prove it can still speak.
"""
from __future__ import annotations

import json
import os
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


_CONTROL_ERROR = "zzz-control-cannot-replay"


def _provenance() -> dict[str, Any]:
    """r27 (C4): the control records the SAME provenance keys a real fixture carries.

    It used to omit `python_hash_seed` — deliberately, to skip the seed refusal — which
    made every control fixture distinguishable from every real one by a field the compare
    loop can read. Gating the loop on that tell gave a full pass, exit 0 and a
    byte-identical transcript with a live defect in the tree. Recording the seed the
    process actually has satisfies the refusal under any seed while leaving no tell.
    """
    return {"python_hash_seed": os.environ.get("PYTHONHASHSEED"),
            "engine_version": "control"}


def _seam_fixture(fixture_id: str, outputs: dict[str, Any]) -> FX.Fixture:
    return FX.Fixture(
        fixture_id=fixture_id, checkpoint="k3-control", trace="seam",
        classes=("terminal:abstain",), question="what is my declared control value?",
        question_id=fixture_id, inputs={}, outputs=outputs,
        provenance=_provenance(),
    )


def _erroring_fixture() -> FX.Fixture:
    """A fixture that CANNOT be replayed: an `A-poster` trace with no recorded view, so
    `replay_fixture` raises before the comparator is reached. The control set had none, so
    the mirror of row 5b's named kill — counting only `failed` — left every control green
    while unreplayable fixtures exited 0."""
    return FX.Fixture(
        fixture_id=_CONTROL_ERROR, checkpoint="k3-control", trace="A-poster",
        classes=("terminal:abstain",), question="what is my declared control value?",
        question_id=_CONTROL_ERROR, inputs={}, outputs={},
        provenance=_provenance(),
    )


def _publish(directory: Path, fixtures: list[FX.Fixture]) -> None:
    """Write the set AND its manifest. r27 (C7): the replay reads the manifest, so a
    control set that did not publish one would be exempt from the very check being added
    — the control's own shape must not be the reason it passes."""
    for fx in fixtures:
        FX.write(directory, fx)
    man = FX.manifest("k3-control", fixtures, {"source": "poison control"})
    (directory / "manifest.json").write_text(json.dumps(man, indent=1, sort_keys=True),
                                             encoding="utf-8")


def _diverge(truth: dict[str, Any]) -> dict[str, Any]:
    diverged = json.loads(json.dumps(truth))          # deep copy, no shared substructure
    diverged["log_decision"]["decision"]["effector"] = "report"
    diverged["log_decision"]["decision"]["eu"] = 0.99
    assert diverged != truth, "the control's planted divergence did not change the body"
    return diverged


def _control_set(directory: Path) -> None:
    """One fixture that MUST agree and one that MUST NOT, in a fresh directory."""
    from life_agent.collapse import drive as DR

    truth = DR.drive_seam_unavailable("what is my declared control value?")
    _publish(directory, [_seam_fixture(_CONTROL_MATCH, truth),
                         _seam_fixture(_CONTROL_MISMATCH, _diverge(truth))])


def _agreeing_plus_erroring_set(directory: Path) -> None:
    """Every fixture either agrees or cannot run — so the ONLY thing that can make this
    set fail is counting the unreplayable one."""
    from life_agent.collapse import drive as DR

    truth = DR.drive_seam_unavailable("what is my declared control value?")
    _publish(directory, [_seam_fixture(_CONTROL_MATCH, truth), _erroring_fixture()])


def test_poison_the_oracle_detects_a_mismatch_end_to_end(tmp_path: Path,
                                                         capsys: pytest.CaptureFixture[str],
                                                         ) -> None:
    """D-a. MUST FAIL when the comparison never reaches the exit code. Drives
    `collapse_replay.main` over a two-fixture set — one agreeing, one deliberately
    divergent — through the real compare loop.

    Killed by each of the three survivable mutations named above, every one of which leaves
    the two older controls green while this one goes red:
    `diffs = []` in the loop; `if diffs:` -> `pass`; `bad = len(errored)`.
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


# --- r27 B: the oracle's accounting, its inputs, and its own set ----------------------
# G4 obtained a full pass with two live decision-path defects in the tree. The literal
# claim of row 5b (a planted mismatch reaches the exit code) held; what nothing covered was
# the machinery's INPUT — which fixtures the loop looks at, which fields the comparator
# values, and whether the set on disk is the set that was recorded.

def _replay(argv: list[str]) -> tuple[int, str]:
    sys.path.insert(0, str(_ROOT / "scripts"))
    import contextlib
    import io

    import collapse_replay
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        rc = collapse_replay.main(argv)
    return rc, buf.getvalue()


def test_poison_an_unreplayable_fixture_cannot_exit_zero(tmp_path: Path) -> None:
    """r27 C5. MUST FAIL if a fixture that could not be replayed counts as a pass. Every
    other fixture in this set AGREES, so the only thing that can fail it is counting the
    one that raised. Killed by `bad = len(failed)` — the mirror of the mutation row 5b
    names as its kill, which the old control set could not express because it contained no
    fixture that raises."""
    _agreeing_plus_erroring_set(tmp_path)
    rc, out = _replay(["--checkpoint", "k3-control", "--fixtures", str(tmp_path)])
    assert rc != 0, (
        f"a fixture that could not be replayed at all exited {rc} — 'errored' is being "
        f"read as 'fine'. Output:\n{out}")
    assert _CONTROL_ERROR in out, f"the unreplayable fixture was not named. Output:\n{out}"


def test_poison_a_skipped_fixture_cannot_be_reported_as_passing(tmp_path: Path) -> None:
    """r27 C4. MUST FAIL if the loop can decline to compare a fixture and still report a
    full pass. `total - bad` counted NOT-FAILED, not COMPARED, so any branch that skipped
    fixtures — gating on a control-only tell, on an id, on anything — printed N/N and
    exited 0. Killed by `continue`-ing any fixture before `compare_fixture`, and by
    dropping the compared-set reconciliation."""
    _control_set(tmp_path)
    rc, out = _replay(["--checkpoint", "k3-control", "--fixtures", str(tmp_path),
                       "--only", _CONTROL_MATCH])
    assert rc == 0 and "1/1" in out, (
        f"control: an explicit single-fixture selection must still pass. Output:\n{out}")
    assert "compared" in out, (
        f"the summary does not say how many fixtures were COMPARED, so a skipped fixture "
        f"is indistinguishable from a passing one. Output:\n{out}")


def test_poison_a_doctored_fixture_set_is_refused(tmp_path: Path) -> None:
    """r27 C7. MUST FAIL if the replay never checks the set it was handed against the set
    that was recorded. `read_all` globs `*.json` and explicitly skips `manifest.json`, and
    `n_fixtures`/`fixture_ids` were never compared to the glob — so a doctored set of the
    same size reported a full pass. Killed by removing the manifest reconciliation."""
    _control_set(tmp_path)
    swapped = tmp_path / f"{_CONTROL_MISMATCH}.json"
    body = swapped.read_text(encoding="utf-8").replace(_CONTROL_MISMATCH, "zzz-substitute")
    swapped.unlink()
    (tmp_path / "zzz-substitute.json").write_text(body, encoding="utf-8")

    rc, out = _replay(["--checkpoint", "k3-control", "--fixtures", str(tmp_path)])
    assert rc == 2, (
        f"a fixture set that does not match its own manifest exited {rc}; the oracle "
        f"compared whatever it was handed. Output:\n{out}")
    assert "manifest" in out.lower(), f"the refusal did not name the manifest. Output:\n{out}"


def test_poison_a_set_without_a_manifest_is_refused(tmp_path: Path) -> None:
    """r27 C7, the discriminating half (row 23). MUST FAIL if deleting the manifest is
    the way past the manifest check — a reconciliation whose evasion is `rm` reconciles
    nothing. Killed by treating an absent manifest as 'nothing to reconcile'."""
    _control_set(tmp_path)
    (tmp_path / "manifest.json").unlink()
    rc, out = _replay(["--checkpoint", "k3-control", "--fixtures", str(tmp_path)])
    assert rc == 2, (
        f"a fixture set with no manifest exited {rc} — deleting the manifest is the "
        f"cheapest possible evasion of a manifest check. Output:\n{out}")
