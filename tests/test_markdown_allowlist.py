"""
Every tracked ``.md`` file matches a line of ``.md-allowlist``; stray prose fails ``make check``.

A pattern is a path or a glob: ``*`` stays inside one path segment and ``**`` crosses segments.
Changing the allowlist is the owner's call, not a way to make this test pass.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ALLOWLIST = ROOT / ".md-allowlist"


def _pattern(glob: str) -> re.Pattern[str]:
    out: list[str] = []
    i = 0
    while i < len(glob):
        if glob.startswith("**", i):
            out.append(".*")
            i += 2
        elif glob[i] == "*":
            out.append("[^/]*")
            i += 1
        elif glob[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(glob[i]))
            i += 1
    return re.compile("".join(out) + r"\Z")


def patterns(text: str) -> list[re.Pattern[str]]:
    return [_pattern(line.strip()) for line in text.splitlines() if line.strip()]


def strays(paths: list[str], allowed: list[re.Pattern[str]]) -> list[str]:
    return sorted(p for p in paths if not any(a.match(p) for a in allowed))


def _tracked_markdown() -> list[str]:
    try:
        listed = subprocess.run(
            ["git", "ls-files", "-z", "--", "*.md"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        pytest.skip(f"not a git checkout, so tracked files cannot be listed: {exc}")
    return [p for p in listed.split("\0") if p]


def test_every_tracked_markdown_file_is_allowlisted() -> None:
    allowed = patterns(ALLOWLIST.read_text(encoding="utf-8"))
    assert strays(_tracked_markdown(), allowed) == [], (
        "tracked .md files outside .md-allowlist — move the prose into a docstring, "
        "CHANGELOG.md or archive/, or ask the owner to allowlist it"
    )


def test_the_matcher_rejects_stray_prose_and_honours_segments() -> None:
    """Negative control: the check can fail, and a single ``*`` does not cross a directory."""
    allowed = patterns("README.md\n.claude/rules/*.md\narchive/**\n")
    paths = [
        "README.md",
        ".claude/rules/approach.md",
        ".claude/rules/deeper/x.md",
        "archive/docs/kb-schema.md",
        "docs/kb-schema.md",
        "NOTES.md",
    ]
    assert strays(paths, allowed) == [
        ".claude/rules/deeper/x.md",
        "NOTES.md",
        "docs/kb-schema.md",
    ]
