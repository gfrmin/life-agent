"""Law 5: the decision, reaction, outcome, gather-outcome and disclosure logs are only ever
appended to. The guard is structural: the modules that own them open nothing for writing,
delete or rename nothing, and write through ``jsonl_log.append_line``; and no module in the
package opens a file in a mode other than append where the path names one of those logs."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src" / "life_agent"
OWNERS = ("outcomes", "decisions", "reactions", "gather_outcomes", "disclosure")
LOG_NAMES = ("DECISIONS_LOG", "REACTIONS_LOG", "OUTCOMES_LOG", "GATHER_OUTCOMES_LOG",
             "DISCLOSURES_LOG", "decisions_path", "reactions_path", "outcomes_path",
             "gather_outcomes_path", "disclosures_path")
MUTATORS = {"write_text", "write_bytes", "unlink", "replace", "rename", "truncate",
            "remove", "rmtree", "move"}


def _mode(call: ast.Call) -> str:
    """The mode an ``open``/``.open`` call asks for ("r" when it names none)."""
    f = call.func
    args = call.args[1:2] if isinstance(f, ast.Name) else call.args[:1]
    mode = args[0] if args else next((k.value for k in call.keywords if k.arg == "mode"),
                                     ast.Constant("r"))
    return str(mode.value) if isinstance(mode, ast.Constant) else "?"


def _opens(tree: ast.AST) -> list[ast.Call]:
    return [n for n in ast.walk(tree) if isinstance(n, ast.Call) and (
        (isinstance(n.func, ast.Name) and n.func.id == "open")
        or (isinstance(n.func, ast.Attribute) and n.func.attr == "open"))]


def _trees() -> dict[Path, tuple[str, ast.AST]]:
    out = {}
    for p in ROOT.rglob("*.py"):
        src = p.read_text(encoding="utf-8")
        out[p] = (src, ast.parse(src))
    return out


def test_the_log_owners_only_append_through_the_one_writer() -> None:
    for name in OWNERS:
        tree = ast.parse((ROOT / "core" / f"{name}.py").read_text(encoding="utf-8"))
        assert all(_mode(c) == "r" for c in _opens(tree)), name
        called = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call)
                  and isinstance(n.func, ast.Attribute)}
        assert not called & MUTATORS, (name, called & MUTATORS)
        assert "append_line" in called, name


def test_no_module_opens_a_log_for_anything_but_appending() -> None:
    for p, (src, tree) in _trees().items():
        for call in _opens(tree):
            if any(n in (ast.get_source_segment(src, call) or "") for n in LOG_NAMES):
                assert _mode(call) == "r", (p.name, call.lineno, _mode(call))
        for n in ast.walk(tree):
            if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and n.func.attr in MUTATORS and p.name != "jsonl_log.py"):
                seg = ast.get_source_segment(src, n) or ""
                assert not any(name in seg for name in LOG_NAMES), (p.name, n.lineno)


def test_the_one_writer_opens_append_and_nothing_else_does_to_a_calibration_log() -> None:
    tree = _trees()[ROOT / "core" / "jsonl_log.py"][1]
    assert [_mode(c) for c in _opens(tree)] == ["a"]
