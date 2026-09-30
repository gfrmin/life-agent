"""The code describes the code: no comment, docstring or string in `src/`, `eval/`, `scripts/` or
`tests/` cites a retired report, design document or system. History lives in git (CLAUDE.md).

The retired vocabulary: the `rNN` report numbers, `GD-` and `M-N` ids, the Julia daemon, the
membrane, the unification arc, fairfight, the conferrals, KICKOFF, RULINGS.md and the design
documents that were deleted, the pre-reset ledger (the GTD and trips event ledgers are live,
and keep the word), and any `docs/...md` path that is not in the tree.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCOPE = ("src", "eval", "scripts", "tests")

RETIRED = {
    "an rNN report": r"\br[0-9]{2}[a-z]?\b",
    "a GD- id": r"GD-",
    "an M-N id": r"\bM-[0-9]",
    "the daemon": r"daemon(?!=True)",  # `Thread(daemon=True)` is Python's
    "the membrane": r"membrane",
    "the unification arc": r"unification",
    "fairfight": r"fairfight",
    "a conferral": r"conferral",
    "KICKOFF": r"KICKOFF",
    "RULINGS.md": r"RULINGS\.md",
    "bayesian-foundations": r"bayesian-foundations",
    "module-collapse-design": r"module-collapse-design",
    "scoped-claims design": r"scoped-claims design",
    "system-design": r"system-design",
    "server.jl": r"server\.jl",
    "answer_brain.jl": r"answer_brain\.jl",
}
_RETIRED = {name: re.compile(rx, re.IGNORECASE if name in {
    "the daemon", "the membrane", "the unification arc", "fairfight", "a conferral"} else 0)
    for name, rx in RETIRED.items()}

# The word `ledger` names the GTD and trips event ledgers (`core/events.py`), so it stays in
# the files about them (and the upper-case names `TASKS_LEDGER` and `TRIPS_LEDGER`); anywhere
# else it is the retired unified decision ledger (the decision log is `decisions.jsonl`).
# `ledger.journal` is a synthetic file name in a registry fixture.
_LEDGER = re.compile(r"(?<![A-Z_])[Ll]edger(?!\.journal)")
_EVENT_LEDGER_FILES = ("tasks", "trips", "reach", "events", "gtd", "task", "web_server",
                       "output_gateway", "config", "conftest", "scripts/ask.py")
_DOC = re.compile(r"\bdocs/[\w./-]*\.md\b")


def _python_files() -> list[Path]:
    me = Path(__file__).resolve()
    return [p for d in SCOPE for p in sorted((ROOT / d).rglob("*.py")) if p.resolve() != me]


def _findings(path: Path) -> list[str]:
    rel = path.relative_to(ROOT).as_posix()
    out = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        found = [name for name, rx in _RETIRED.items() if rx.search(line)]
        if _LEDGER.search(line) and not any(f in rel for f in _EVENT_LEDGER_FILES):
            found.append("the pre-reset ledger")
        found += [f"a missing document ({m})" for m in _DOC.findall(line)
                  if not (ROOT / m).exists()]
        out += [f"{rel}:{n}: {name}: {line.strip()[:90]}" for name in found]
    return out


def test_no_comment_cites_a_retired_report_or_a_deleted_document() -> None:
    findings = [f for p in _python_files() for f in _findings(p)]
    assert not findings, f"{len(findings)} line(s) cite retired vocabulary:\n" + "\n".join(
        findings[:40])
