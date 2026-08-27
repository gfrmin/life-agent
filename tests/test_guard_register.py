"""`docs/guards.md`'s headline count, RECOMPUTED from the rows it counts.

The sentence under the register used to be maintained by hand, and it had drifted twice:
it read *"thirteen resolved, nine instrumented"* while the rows said fifteen and ten, and
the report that last touched it said sixteen and nine. Three numbers, one register.

A count derived from somewhere other than the thing counted is the register's own entry 1,
and a register whose headline is wrong is worse than one with no headline: it is the number
a reader quotes. So the count is a guard.

Run: uv run --project . python -m pytest tests/test_guard_register.py
"""
from __future__ import annotations

import re
from pathlib import Path

_REGISTER = Path(__file__).resolve().parent.parent / "docs" / "guards.md"

#: A register row: `| 5b | Guard | claim | **state** | killed by |`. The id may carry a
#: letter suffix (2b, 5b), which is why this is not `\d+`.
_ROW = re.compile(r"^\| (\d+[a-z]?) \|.*?\*\*(unenforced|instrumented|resolved)\*\*")
_COUNT = re.compile(r"^\*\*(\d+) rows resolved, (\d+) instrumented\.\*\*", re.M)


def census(text: str) -> dict[str, list[str]]:
    """Row ids by declared state — the rows themselves, which are the register."""
    out: dict[str, list[str]] = {"unenforced": [], "instrumented": [], "resolved": []}
    for line in text.splitlines():
        m = _ROW.match(line)
        if m:
            out[m.group(2)].append(m.group(1))
    return out


def test_the_headline_count_equals_the_rows_it_counts() -> None:
    text = _REGISTER.read_text(encoding="utf-8")
    m = _COUNT.search(text)
    assert m, ("docs/guards.md has no machine-readable count line — it must read "
               "`**N rows resolved, M instrumented.**` so this test can recompute it")
    by_state = census(text)
    assert (int(m.group(1)), int(m.group(2))) == (
        len(by_state["resolved"]), len(by_state["instrumented"])), (
        f"the register's headline says {m.group(1)} resolved / {m.group(2)} instrumented, "
        f"but the rows say {len(by_state['resolved'])} / {len(by_state['instrumented'])} "
        f"(resolved: {by_state['resolved']}; instrumented: {by_state['instrumented']}). "
        f"Edit the rows, not the sentence.")


def test_every_row_id_is_unique() -> None:
    """Two rows sharing an id is how a row gets silently replaced rather than added."""
    text = _REGISTER.read_text(encoding="utf-8")
    ids = [i for group in census(text).values() for i in group]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    assert not dupes, f"duplicate register row id(s): {dupes}"


def test_every_resolved_row_names_a_kill() -> None:
    """*resolved* means a planted violation was demonstrated to kill the guard. A row that
    claims it without naming the mutation is the decoration this register exists to expose;
    the last column is where the mutation is named."""
    text = _REGISTER.read_text(encoding="utf-8")
    thin: list[str] = []
    for line in text.splitlines():
        m = _ROW.match(line)
        if not m or m.group(2) != "resolved":
            continue
        killed_by = line.rstrip().rstrip("|").rsplit("|", 1)[-1].strip()
        if len(killed_by) < 20:
            thin.append(f"{m.group(1)}: {killed_by!r}")
    assert not thin, (
        f"resolved row(s) naming no mutation: {thin} — *resolved* is a claim that someone "
        f"watched a planted violation die, and the last column is where that is recorded")
