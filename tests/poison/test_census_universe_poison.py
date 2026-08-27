"""Poison fixtures for K3's two rules — the CONSEQUENCES of the census-evasion class.

K2's adversary pass defeated 8 of 13 `resolved` rows. Eight of the eleven defeats were **a
census whose universe is a string**: a name, a literal, a docstring phrase, a set member.
r25 fixed the three defects that were live and deliberately did not patch the class, and the
owner ruled: convert, do not patch.

Two rules follow, both pure functions over synthetic source (r25's L8 lesson — a rule that
can only be exercised by mutating the real tree cannot be mutation-tested at all), then
applied to the real tree:

1. **A census may not take a whole MODULE as its universe.** `G.calls(LK, "x")` walks
   `inspect.getsource(LK)`, so a call anywhere in the module satisfies it — including a
   function that never runs. Demonstrated on the real tree at K3: with the deployed handler
   re-spelled to a divergent `sorted(...)` and the call moved to a dead helper, the module
   census still returned True.
2. **A control must DISCRIMINATE.** A test whose every assertion only checks that something
   EXISTS (`is not None`, a bare truthiness) proves nothing about what it holds.
   `assert r.returncode is not None` is true of every subprocess that completed, so the leg
   it "controls" could be deleted outright and the control would stay green.
"""
from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_TESTS = _ROOT / "tests"


# --- Rule 1: a census's universe may not be a whole module ---------------------------

def module_scoped_censuses(source: str, label: str = "") -> list[str]:
    """Every `calls(X, ...)` in ``source`` whose first argument is a BARE NAME.

    The discriminator is syntactic and needs no list of module aliases to keep current:
    `calls(EX.render_view, ...)` passes an `ast.Attribute` — a named function inside a
    module — while `calls(EX, ...)` passes an `ast.Name`, which for this helper can only be
    a module or a class, i.e. a universe wider than any one deployed code path.

    Fail-closed on purpose: a bare name that genuinely IS a function is flagged too, and
    must be spelled as an attribute or exempted in the open. The alternative — matching
    ALL-CAPS aliases — would be a census one alias wide, which is the defect this rule
    exists to stop.
    """
    out: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        fn = node.func
        name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
        if name != "calls":
            continue
        if isinstance(node.args[0], ast.Name):
            target = node.args[0].id
            out.append(f"{label}:{node.lineno}: calls({target}, ...)" if label
                       else f"calls({target}, ...)")
    return out


def test_poison_the_module_census_rule_reads_the_argument_not_the_alias() -> None:
    """K3 D-c. MUST FAIL if the rule is spelled against a list of known module aliases
    instead of the argument's syntax. Killed by restricting it to ALL-CAPS names: under
    that spelling the lowercase module below passes and the census stays module-wide."""
    synthetic = (
        "assert G.calls(EX.render_view, 'leader_order')\n"   # scoped — fine
        "assert G.calls(LK, 'leader_order')\n"               # module — offender
        "assert G.calls(lookup, 'leader_order')\n"           # module, lowercase — offender
    )
    assert module_scoped_censuses(synthetic) == [
        "calls(LK, ...)", "calls(lookup, ...)"], (
        "the rule missed a module-scoped census — if it only catches ALL-CAPS aliases its "
        "universe is a naming convention, not the argument"
    )


def test_poison_no_census_takes_a_whole_module_as_its_universe() -> None:
    """Rule 1. MUST FAIL when a guard censuses a whole module. Scope the assertion to the
    deployed function, or assert the behaviour. Killed by restoring
    `G.calls(BR, "leader_order")` in `tests/test_m7_register.py` — with the bridge handler
    re-spelled to a divergent sort and the call moved to a dead helper, that census
    returns True while the deployed path orders differently."""
    offenders: list[str] = []
    for py in _TESTS.rglob("*.py"):
        rel = py.relative_to(_TESTS).as_posix()
        if rel == "poison/test_census_universe_poison.py":   # this file quotes the shape
            continue
        offenders += module_scoped_censuses(py.read_text(), rel)
    assert not offenders, (
        f"census(es) whose universe is a whole module: {offenders} — a call in a branch "
        f"that never runs satisfies them while the deployed path diverges (K3 D-c). Scope "
        f"to the deployed function, or assert the behaviour."
    )


# --- Rule 2: a control must discriminate ---------------------------------------------

def _is_existence_only(test: ast.expr) -> bool:
    """True when an assertion's condition only checks that a name is BOUND.

    Narrowed twice against the real fixture set, both narrowings recorded because the
    discarded breadth is the interesting part — "this assertion cannot fail" depends on
    types the AST does not carry, so every formulation trades false positives for teeth:

      * bare truthiness included (`assert not offenders`) — flags **7** sound census
        fixtures. `assert not <computed collection>` claims the census returned EMPTY, which
        is a claim about a value the test derived. Rejected.
      * `is None` included — flags **1** sound fixture
        (`test_declared_binary_extensions_are_still_skipped`), where `is None` is the
        function's SPECIFIED return for a declared binary; it could have returned text or
        raised. A positive claim, not an existence check. Rejected.
      * `is not None` only — flags **0** on this tree, and would still have caught D-b,
        whose sole assertion was `assert r.returncode is not None` on a `CompletedProcess`.
        Adopted.

    **Known limitation, in the register too:** `is not None` is not vacuous in general — a
    function returning `Optional` is legitimately asserted this way. The house rule is
    narrower than the English: a test whose EVERY assertion is `is not None` is not
    discriminating, whatever the types. The escape is to assert a value as well.
    """
    if isinstance(test, ast.Compare) and len(test.ops) == 1:
        op, comparator = test.ops[0], test.comparators[0]
        if isinstance(comparator, ast.Constant) and comparator.value is None:
            return isinstance(op, ast.IsNot)
        return False                                          # ==, !=, <, in, is None …
    if isinstance(test, ast.BoolOp):
        return all(_is_existence_only(v) for v in test.values)
    return False


def existence_only_controls(source: str, label: str = "") -> list[str]:
    """Every test in ``source`` whose assertions are ALL `is not None`.

    A control has to distinguish a gate that rejected the planted violation from a gate that
    rejects everything, or was never reached. `assert r.returncode is not None` is true of
    every subprocess that completed, so the leg it "controls" could be deleted outright with
    the control still green — which is what happened (K3 D-b).
    """
    out: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if not (isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
                and node.name.startswith("test_")):
            continue
        tests = [n.test for n in ast.walk(node) if isinstance(n, ast.Assert)]
        if tests and all(_is_existence_only(t) for t in tests):
            out.append(f"{label}::{node.name}" if label else node.name)
    return out


def test_poison_the_discrimination_rule_keeps_its_two_narrowings() -> None:
    """K3 D-b. MUST FAIL if either discarded formulation is restored. Killed by widening
    `_is_existence_only` back to bare truthiness (the census below starts failing) or to
    `is None` (the specified-return case below starts failing) — each widening flagged
    sound fixtures on the real tree, and a rule that flags sound tests gets disabled."""
    synthetic = (
        "def test_vacuous():\n"
        "    assert r.returncode is not None\n"
        "    assert r.stdout is not None\n"
        "def test_discriminating():\n"
        "    assert r.returncode == 1\n"
        "def test_mixed():\n"
        "    assert r is not None\n"
        "    assert 'F401' in r.stdout\n"
        "def test_census():\n"
        "    assert not offenders\n"
        "def test_specified_none_return():\n"
        "    assert read_text_or_refuse(p, b) is None\n")
    assert existence_only_controls(synthetic) == ["test_vacuous"], (
        "the discrimination rule mis-classified. Asserting existence twice is no more "
        "discriminating than once; `assert not <computed collection>` and "
        "`assert f(x) is None` are both claims about values the test derived."
    )


def test_poison_every_control_discriminates() -> None:
    """Rule 2. MUST FAIL when a control's every assertion is `is not None`. Killed by
    restoring `assert r.returncode is not None` as the sole assertion of a control — the
    shape that let a gate leg be deleted outright with its control still green (K3 D-b).
    Flags zero fixtures today: it is a forward guard, not a backlog."""
    offenders: list[str] = []
    for py in (_TESTS / "poison").rglob("test_*.py"):
        rel = py.relative_to(_TESTS).as_posix()
        if rel == "poison/test_census_universe_poison.py":
            continue
        offenders += existence_only_controls(py.read_text(), rel)
    assert not offenders, (
        f"control(s) whose every assertion is `is not None`: {offenders} — such a test "
        f"cannot tell a gate that rejected the violation from one that rejects everything "
        f"or was never reached (K3 D-b). Assert a value as well."
    )
