"""Poison fixtures for the structural PII guard — r23, from the K1 G4 adversary pass.

A poison fixture inverts an ordinary test. An ordinary test requires the CODE to pass;
these require the GUARD to FAIL, on a minimal violation of exactly the thing a finding
exploited, matched to a marker naming the specific tooth. A guard that starts passing its
poison has been weakened, and the build says so.

Every value here is SYNTHETIC and invented for this file. Lines carrying a shaped literal
end in ``# PII-OK: synthetic <what>`` — both the guard's own skip marker and a comment, the
convention `CLAUDE.md` declares. Nothing was copied from the corpus.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

_HOOKS = Path(__file__).resolve().parents[2] / ".githooks"
sys.path.insert(0, str(_HOOKS))

from pii_check import (  # noqa: E402
    DEFAULT_ALLOWED_DOMAINS,
    read_text_or_refuse,
    scan_text,
    skipped_paths,
)

D = DEFAULT_ALLOWED_DOMAINS


def _labels(text: str, **kw: object) -> list[str]:
    return [f.kind for f in scan_text("t", text, denylist=[], allowed_domains=D, **kw)]  # type: ignore[arg-type]


# --- F4: a NUL byte must be a REFUSAL, never a silent skip ---------------------------

def test_poison_nul_byte_does_not_unscan_a_file(tmp_path: Path) -> None:
    """F4. Binary-detection used as a SKIP is indistinguishable from a clean scan. One
    NUL byte took five findings to zero on the deployed guard."""
    clean = tmp_path / "a.md"
    poisoned = tmp_path / "b.md"
    body = "Tel: 2345 6789 and Mr Chan Tai Man\n"  # PII-OK: synthetic HK phone + name
    clean.write_text(body, encoding="utf-8")
    poisoned.write_bytes(body.encode() + b"\x00\n")

    assert _labels(clean.read_text(encoding="utf-8")), "control: the clean file must be flagged"

    with pytest.raises(ValueError, match="contains a NUL byte and was NOT scanned"):
        read_text_or_refuse(str(poisoned), poisoned.read_bytes())


def test_declared_binary_extensions_are_still_skipped(tmp_path: Path) -> None:
    """The refusal must not break the four tracked binaries (pdf/pptx test fixtures) —
    a guard that fires on every legitimate binary gets disabled, and a disabled guard is
    what let the 2026-08-18 leak through."""
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4\x00binary")
    assert read_text_or_refuse(str(pdf), pdf.read_bytes()) is None


# --- F5: skips are declared per PATH, never per basename -----------------------------

def test_poison_lockfile_basename_does_not_exempt_an_arbitrary_path() -> None:
    """F5. `_skip()` matched `os.path.basename`, so ANY path ending in one of nine
    lockfile names was exempt anywhere in the tree, forever — and lockfiles are text
    (a trailing TOML comment survives every `uv run`)."""
    assert skipped_paths(["uv.lock"]) == ["uv.lock"], "the real lockfile is still skipped"
    for sneaky in ("tests/fixtures/uv.lock", "docs/poetry.lock", "eval/yarn.lock"):
        assert skipped_paths([sneaky]) == [], (
            f"{sneaky} was skipped as a lockfile — skips are declared per PATH, not per "
            f"basename, and a skipped file is reported, never silent"
        )


# --- F6: seven forbidden shapes that had no rule at all ------------------------------

@pytest.mark.parametrize(("text", "kind", "what"), [
    ("Tel: 91234567 ext 4",  # PII-OK: synthetic
     "hk-phone-shape", "bare 8-digit HK phone, no separator"),
    ("Mobile: 054-123-4567",  # PII-OK: synthetic
     "israeli-mobile-shape", "IL mobile, two separators"),
    ("Call +972-54-123-4567",  # PII-OK: synthetic
     "israeli-mobile-shape", "IL mobile, international form"),
    ("Passport no. K1234567",  # PII-OK: synthetic
     "passport-shape", "single-letter passport prefix"),
    ("Account no. 12-345-678901",  # PII-OK: synthetic
     "account-number-shape", "account number"),
    ("Ref INV/2026/00042",  # PII-OK: synthetic
     "document-ref-shape", "document reference"),
    ("mail me at chan.taiman [at] example.test",  # PII-OK: synthetic
     "email (obfuscated separator)", "obfuscated email"),
])
def test_poison_forbidden_shape_is_caught(text: str, kind: str, what: str) -> None:
    """F6. Each of these is forbidden by name in CLAUDE.md and had NO rule. P2: a shape
    ships only with a fixture proving it kills a synthetic violation — a shape with no
    demonstrated kill is prose that looks like protection."""
    assert kind in _labels(text), f"{what} not caught: {text!r}"


# --- F7: an allowlisted ROOT exempts the root, not the segments under it -------------
# WITHDRAWN as a shape rule and recorded as known-and-uncovered instead. A personal-name
# segment and an ordinary kebab-case slug are structurally identical (`chan-tai-man` vs
# `life-agent`); the shape rule tried first fired on 20 legitimate paths in this tree. The
# gap is real, it is the private denylist's job, and the CI leg runs with an empty
# denylist — which is why F6's second half (announcing that) is the part that shipped.

def test_personal_segment_under_an_allowed_root_is_the_denylists_job() -> None:
    """F7. With a denylist loaded the personal segment IS caught, path and all — the
    denylist scans the whole line. This fixture pins that so a refactor cannot quietly
    make the denylist path-blind."""
    deny = [re.compile(r"chan-tai-man")]  # PII-OK: synthetic name
    line = "exports at /data/acme/chan-tai-man/2026-invoices.csv"  # PII-OK: synthetic path
    kinds = [f.kind for f in scan_text("t", line, denylist=deny, allowed_domains=D,
                                       path_allow=("/data/acme/",))]
    assert "private-denylist" in kinds, (
        "a personal segment under an allowlisted root escaped even the denylist"
    )


def test_shapes_only_cannot_see_a_personal_segment_and_must_say_so() -> None:
    """F7, the honest half: with no denylist the same line is invisible, because no shape
    distinguishes a name from a slug. The guard must therefore ANNOUNCE that its name
    layer did not run rather than print a bare pass — that announcement is the fixture."""
    line = "exports at /data/acme/chan-tai-man/2026-invoices.csv"  # PII-OK: synthetic path
    kinds = [f.kind for f in scan_text("t", line, denylist=[], allowed_domains=D,
                                       path_allow=("/data/acme/",))]
    assert kinds == [], "a shape rule for personal segments is back — it fired on 20 " \
                        "legitimate paths when tried; names are the denylist's job"


# --- F13: owner-specific literals in src/ --------------------------------------------

_SYNTH_HOST = '_OWNER_HOST = "examplebox.tail1a2b.ts.net"'  # PII-OK: synthetic host


@pytest.mark.parametrize(("text", "what", "kind"), [
    (_SYNTH_HOST, "tailnet hostname", "owner-specific host"),
    ("_OWNER_TELEGRAM_ID = 448120973",  # PII-OK: synthetic
     "9-digit personal id, non-IL-checksum", "owner-specific literal"),
])
def test_poison_owner_specific_literal_in_src_is_caught(text: str, what: str,
                                                        kind: str) -> None:
    """F13. MUST FAIL if src/ stops being checked for owner-specific hostnames and ids.
    CLAUDE.md forbids both hard-coded there. The 9-digit rule fired only on values passing
    the Israeli-ID checksum, so every other 9-digit personal id was unenforced by
    construction. Killed by removing either rule."""
    assert kind in " ".join(_labels(text, in_src=True)), f"{what} not caught: {text!r}"


def test_poison_the_host_rule_is_not_scoped_to_src() -> None:
    """K3 S2. MUST FAIL if the hostname rule is scoped back to `src/`.

    This test asserted the OPPOSITE until K3: the rule was src/-only on the reading that a
    hostname in prose is documentation. It is not — CLAUDE.md forbids owner-specific values
    "including in docs prose, §14 ledger entries, commit messages, and test fixtures", and
    25 occurrences of two host names had accumulated across reports, conferrals, a design
    doc and one poison fixture, with the hook armed the whole time, because nothing looked
    outside `src/`. Killed by restoring the `in_src and ...` gate on the host rule.
    """
    assert "owner-specific host" in " ".join(_labels(_SYNTH_HOST, in_src=False)), (
        "a tailnet hostname outside src/ was not caught — this is how 25 of them landed"
    )


def test_owner_id_rule_stays_scoped_to_src() -> None:
    """The ID rule matches an identity-shaped BINDING (`owner_id = 1234567`), which outside
    src/ is someone quoting code. Widening it is a separate change with its own
    false-positive question, deliberately not made here."""
    assert "owner-specific literal" not in " ".join(
        _labels("_OWNER_TELEGRAM_ID = 448120973", in_src=False))  # PII-OK: synthetic


# --- the CI leg's own universe -------------------------------------------------------

def test_shapes_only_reports_that_its_name_layer_is_empty() -> None:
    """F6, second half. `--shapes-only` — the flag CI uses — sets `denylist = []`, so the
    name layer runs against an empty pattern list. A check pointed at nothing cannot tell
    'clean' from 'not looking', so it must SAY so rather than print a bare pass."""
    out = subprocess.run(
        [sys.executable, str(_HOOKS / "pii_check.py"), "--shapes-only", __file__],
        capture_output=True, text=True, check=False)
    assert "name layer not run" in (out.stdout + out.stderr), (
        "the shapes-only leg reported a clean scan without saying its denylist is empty"
    )


# --- L6 (r25): the skip set is pinned whole, and every skip is announced ---------------

def test_poison_the_skip_set_is_pinned_whole() -> None:
    """L6. MUST FAIL if a path is added to `_SKIP_PATHS`. Adding one tracked prose file
    (`README.md`) exempted the repository's front page from the guard with all five gate
    legs green. Pinning membership of known-good names cannot see an ADDITION; only
    equality can. Killed by adding any path to the set."""
    from pii_check import _SKIP_PATHS

    assert frozenset({"uv.lock"}) == _SKIP_PATHS, (
        f"_SKIP_PATHS is {sorted(_SKIP_PATHS)} — a skip exempts a whole tracked file from "
        f"every shape rule, so the set is pinned by equality, not by membership"
    )


def test_poison_a_skip_is_announced(capsys: pytest.CaptureFixture[str]) -> None:
    """L6. MUST FAIL if a skipped file passes in silence — the property the F5 fixture's
    own message claimed ("a skipped file is reported, never silent") and which was never
    implemented. Killed by removing the announce_skips call from gather_paths."""
    from pii_check import announce_skips

    announce_skips(["uv.lock", "README.md"])
    err = capsys.readouterr().err
    assert "uv.lock" in err and "skipped" in err, (
        f"a declared skip was not announced: {err!r}"
    )


# --- K3 D-d: the PII-OK marker may not launder a REAL value --------------------------
# `scan_text` did `if MARKER in line: continue` before every check, so a line marked
# synthetic was never tested against the private denylist — the layer that knows real
# values. The marker's job is to permit a synthetic value with a REAL SHAPE; a synthetic
# value cannot contain a real NAME, so exempting the name layer buys nothing and cost a
# real host name being committed to a public repo under a `# PII-OK: synthetic` comment.

_DENY_PROBE = [re.compile(r"NOTAREALNAME")]  # PII-OK: synthetic denylist pattern


def test_poison_the_marker_does_not_exempt_the_name_layer() -> None:
    """K3 D-d. MUST FAIL if `PII-OK` suppresses a private-denylist hit. Killed by restoring
    the unconditional `if MARKER in line: continue` at the top of the scan loop — under
    that spelling this line is invisible to the guard, which is how a real host name was
    committed to a public tree marked as synthetic."""
    marked = "the box is NOTAREALNAME  # PII-OK: synthetic"
    kinds = [f.kind for f in scan_text("docs/x.md", marked,
                                       denylist=_DENY_PROBE, allowed_domains=D)]
    assert any("private-denylist" in k for k in kinds), (
        "a PII-OK line was exempted from the private denylist — the marker is a kill "
        "switch over the layer that knows real values, and laundering is free"
    )


def test_poison_the_marker_still_exempts_a_synthetic_shape() -> None:
    """K3 D-d's other half. MUST FAIL if the marker stops working for its legitimate use.
    A guard that rejects every marked line gets the marker deleted, and then real synthetic
    fixtures cannot exist at all. Killed by dropping the `if marked: continue` that follows
    the denylist pass."""
    marked_shape = "mobile: 050-000-0000  # PII-OK: synthetic"  # PII-OK: synthetic
    assert _labels(marked_shape) == [], (
        "a marked SYNTHETIC value with a real shape was still flagged — the marker's "
        "legitimate use is broken and it will be removed, taking the name layer with it"
    )
