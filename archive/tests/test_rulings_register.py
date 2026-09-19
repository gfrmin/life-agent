"""Arc 0 (r34) — the standing-ruling register's re-listing guard.

`docs/unification/RULINGS.md` exists so a session can answer "is this already ruled?" in
one read. That only holds while it is COMPLETE: a ruling taken in a conferral or report and
never registered is exactly the failure the register was built to prevent (two of conferral
1's rulings were carried to conferral 2 and dropped — the register's first finding).

The guard is a census: every document carrying a RULING/RULINGS section must be cited by
name in the register. Modelled on the §6 register's re-listing guard (r17/M7).
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REGISTER = REPO / "docs" / "unification" / "RULINGS.md"
_RULING_HEADING = re.compile(r"^#{1,3} .*\b(RULING|RULINGS|Rulings)\b", re.M)


def _documents_taking_rulings() -> list[Path]:
    """Every in-tree doc whose own headings record a ruling."""
    roots = [REPO / "docs" / "unification" / "conferrals",
             REPO / "docs" / "unification" / "reports"]
    found = []
    for root in roots:
        for p in sorted(root.glob("*.md")):
            if _RULING_HEADING.search(p.read_text(encoding="utf-8")):
                found.append(p)
    return found


def test_the_register_exists_and_declares_its_residue() -> None:
    assert REGISTER.exists(), "the standing-ruling register must exist (Arc 0 A0.1)"
    text = REGISTER.read_text(encoding="utf-8")
    for required in ("## §1 Method", "## §2 Delegation", "## §5 The residue"):
        assert required in text, f"the register must carry {required!r}"


def test_every_document_that_takes_a_ruling_is_registered() -> None:
    """The census. A doc with a RULING section that the register never cites is an
    unregistered ruling — the anti-relitigation function fails silently without this."""
    text = REGISTER.read_text(encoding="utf-8")
    missing = [p.name for p in _documents_taking_rulings()
               if p.stem not in text and p.name not in text]
    assert not missing, (
        "documents take rulings that docs/unification/RULINGS.md does not cite — register "
        f"them (or cite them in §6 as closed history): {missing}")


def test_the_census_can_actually_find_rulings() -> None:
    """Positive control: the guard is worthless if its heading pattern matches nothing."""
    docs = _documents_taking_rulings()
    assert len(docs) >= 20, (
        f"the ruling-section pattern found only {len(docs)} documents — the census pattern "
        "has drifted from how rulings are actually written")


def test_the_governance_log_is_unfoldable() -> None:
    """RULINGS M-14, r33's RC-1 rider applied prospectively: a reaction to a GOVERNANCE
    decision is not evidence about `u_wrong`. The structural guarantee is that no decide-path
    module can even see the log — no writer, no reader, no `decision_id`. `src/` referencing
    it at all is how a second stream quietly becomes a fold input (the r29 contamination,
    which was permanent in an append-only stream)."""
    log = REPO / "docs" / "unification" / "DECISIONS.md"
    assert log.exists(), "the governance decision log must exist (Arc 0 A0.3)"
    offenders = [str(p.relative_to(REPO)) for p in (REPO / "src").rglob("*.py")
                 if "DECISIONS.md" in p.read_text(encoding="utf-8")]
    assert not offenders, (
        "src/ must not reference the governance log — it is recorded, never folded "
        f"(RULINGS M-14): {offenders}")


def test_the_register_names_the_residue_as_exactly_one_class() -> None:
    """The delegation's whole content. If §5 grows a second class it must be a deliberate,
    reviewed change, not drift — this test is what makes that visible."""
    text = REGISTER.read_text(encoding="utf-8")
    residue = text.split("## §5 The residue")[1].split("## §6")[0]
    assert "Exactly one class" in residue, (
        "§5 must state the residue as exactly one class — changes to the objective")
    assert "changes to the objective" in residue.lower()
