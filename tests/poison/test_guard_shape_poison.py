"""Poison fixtures for the guard-shape rules — the CONSEQUENCES of r23's own findings.

r23 recorded six defects in its own fix work and drew no consequence from any of them
beyond prose. A report is a photograph. These fixtures are the film.

Two rules, both machine-checked on every CI run:

1. **A guard may not prove a call with a substring.** F10 was not one guard but a CLASS —
   `assert "<name>(" in inspect.getsource(X)` appeared nine more times after the one the
   adversary reported. A comment satisfies every one of them.
2. **A poison fixture must name the mutation that kills it.** A fixture that has never been
   shown to fail is exactly the decoration the ladder exists to detect, and the first
   version of r23's own oracle control passed its own mutation.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_TESTS = _ROOT / "tests"

# r27 (C9): this rule used to be a one-line REGEX matching exactly one spelling of the
# proof — a stripped line starting `assert`, a BARE quoted literal, `in`, then
# `inspect.getsource` or an EMPTY-paren `read_text()`. That form appears NOWHERE in tree,
# while at least seven other spellings of the identical proof are live: f-string needles,
# `not in`, `read_text(encoding=...)`, a variable holding the source text, `.count(x) == 1`,
# `re.search` over source, and comprehension filters that never say `assert` at all. The
# census caught 2 of 7 and was defeated with no plant.
#
# So the rule reads the AST and follows the TEXT, not the spelling: any comparison of a
# literal against text obtained from `inspect.getsource(...)`, `<path>.read_text(...)` or
# `open(...).read()` — directly or through a local variable — is a substring proof,
# wherever it appears inside a test function.

_SOURCE_TEXT_ATTRS = frozenset({"getsource", "read_text"})
_MATCHERS = frozenset({"search", "match", "fullmatch", "findall", "count", "startswith"})


def _mentions(node: ast.AST, names: frozenset[str]) -> bool:
    return any(isinstance(n, ast.Name) and n.id in names for n in ast.walk(node))


def _is_source_text(node: ast.expr, tainted: frozenset[str],
                    outputs: frozenset[str] = frozenset()) -> bool:
    """True if ``node`` evaluates to text read out of THIS REPO'S OWN SOURCE.

    ``outputs`` names values derived from the test's own parameters — `tmp_path` and the
    other fixtures. Reading a file the test just WROTE and asserting on its content is an
    ordinary behavioural test, not a proof-by-spelling about deployed code, and the
    distinction is the path's provenance: a fixture argument, or the repo root. Measured
    while writing this rule — without the split it flagged round-trip assertions in four
    unrelated modules, which is how an over-broad guard gets an exemption list instead of
    a fix.
    """
    if isinstance(node, ast.Name):
        return node.id in tainted
    if isinstance(node, ast.Call):
        fn = node.func
        if isinstance(fn, ast.Attribute):
            if fn.attr == "getsource":
                return True                      # inspect.getsource is always own-source
            if fn.attr == "read_text":
                return not _mentions(fn.value, outputs)
            if fn.attr == "read" and isinstance(fn.value, ast.Call):
                inner = fn.value.func
                return (getattr(inner, "id", "") == "open"
                        and not _mentions(fn.value, outputs))
        return False
    if isinstance(node, ast.BinOp):
        return (_is_source_text(node.left, tainted, outputs)
                or _is_source_text(node.right, tainted, outputs))
    return False


def _output_derived(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> frozenset[str]:
    """The test's own parameters, and every local transitively built from one. These are
    values the test PRODUCED, so text read through them is output, not source."""
    a = fn.args
    names = {p.arg for p in (*a.posonlyargs, *a.args, *a.kwonlyargs)}
    for extra in (a.vararg, a.kwarg):
        if extra is not None:
            names.add(extra.arg)
    for _ in range(8):
        grown = set(names)
        for node in ast.walk(fn):
            if isinstance(node, ast.Assign) and _mentions(node.value, frozenset(grown)):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        grown.add(t.id)
            elif (isinstance(node, ast.withitem)
                    and isinstance(node.optional_vars, ast.Name)
                    and _mentions(node.context_expr, frozenset(grown))):
                grown.add(node.optional_vars.id)
        if grown == set(names):
            break
        names = grown
    return frozenset(names)


def _tainted_names(fn: ast.AST, outputs: frozenset[str] = frozenset()
                   ) -> frozenset[str]:
    """Local names bound to source text. Iterated to a fixed point so `a = getsource(X)`
    followed by `b = a` taints both — a chain the previous rule could not see at all."""
    tainted: frozenset[str] = frozenset()
    for _ in range(8):
        grown = set(tainted)
        for node in ast.walk(fn):
            targets: list[ast.expr] = []
            value: ast.expr | None = None
            if isinstance(node, ast.Assign):
                targets, value = list(node.targets), node.value
            elif isinstance(node, ast.NamedExpr):
                targets, value = [node.target], node.value
            elif isinstance(node, ast.comprehension):
                # `for line in src.splitlines()` / `for p in ...` — the loop variable is
                # tainted when the iterable is source text or its split.
                it = node.iter
                base = it.func.value if (isinstance(it, ast.Call)
                                         and isinstance(it.func, ast.Attribute)) else it
                targets, value = [node.target], base  # type: ignore[list-item]
            if value is not None and _is_source_text(value, frozenset(grown), outputs):
                for t in targets:
                    if isinstance(t, ast.Name):
                        grown.add(t.id)
        if set(tainted) == grown:
            break
        tainted = frozenset(grown)
    return tainted


def _is_literal(node: ast.expr) -> bool:
    return (isinstance(node, ast.Constant) and isinstance(node.value, str)) or isinstance(
        node, ast.JoinedStr)


def substring_proofs(source: str, label: str = "") -> list[str]:
    """Every place in ``source`` where a test proves something by matching a literal
    against text read from a source file. Pure function over source text (r25 L8), so the
    rule itself is mutation-testable on synthetic input."""
    out: list[str] = []
    for fn in ast.walk(ast.parse(source)):
        if not (isinstance(fn, ast.FunctionDef | ast.AsyncFunctionDef)
                and fn.name.startswith("test_")):
            continue
        outputs = _output_derived(fn)
        tainted = _tainted_names(fn, outputs)
        for node in ast.walk(fn):
            hit = False
            if isinstance(node, ast.Compare):
                # `"x" in src` / `"x" not in src`, either operand order
                for op, right in zip(node.ops, node.comparators, strict=True):
                    if isinstance(op, ast.In | ast.NotIn):
                        hit = hit or (_is_literal(node.left)
                                      and _is_source_text(right, tainted, outputs))
                # `src.count("x") == 1`
                hit = hit or _matcher_over_source(node.left, tainted, outputs)
            elif isinstance(node, ast.Call):
                hit = _matcher_over_source(node, tainted, outputs)
            if hit:
                where = f"{label}::{fn.name}" if label else fn.name
                line = getattr(node, "lineno", 0)
                out.append(f"{where}:{line}")
    return sorted(set(out))


def _matcher_over_source(node: ast.expr, tainted: frozenset[str],
                         outputs: frozenset[str] = frozenset()) -> bool:
    """`src.count("x")`, `re.search(p, src)`, `pat.search(src)` — a matcher applied to
    source text with a literal or compiled pattern."""
    if not isinstance(node, ast.Call):
        return False
    fn = node.func
    if not isinstance(fn, ast.Attribute) or fn.attr not in _MATCHERS:
        return False
    if _is_source_text(fn.value, tainted, outputs):   # src.count("x") / src.startswith(…)
        return True
    return any(_is_source_text(a, tainted, outputs) for a in node.args)  # re.search(p, src)


# This file quotes and implements the pattern it forbids.
_EXEMPT = {"poison/test_guard_shape_poison.py"}

# r27 (C9): the sites live in tree when the AST rule landed. Pinned by EQUALITY, not by
# count and not as a skip list: an addition AND a removal both fail, so the list cannot
# rot the way an allowlist does, and converting a site is a deliberate edit. Converting
# them is K5's work (the census-method ruling), not this milestone's — recorded in
# `docs/guards.md` as known-and-uncovered rather than silently tolerated.
# Some entries below are document censuses (parsing `guards.md`, a produced ledger) rather
# than proofs about a CALL. Telling those apart is not statically decidable — a path
# constant's target is not knowable from the AST — and narrowing the rule until it matched
# intuition is precisely how every census in this register acquired a universe narrower
# than its property. For a RATCHET a false positive costs one pinned line; a false negative
# is a guard that cannot see the next violation. The measured set is pinned as measured.
_SUBSTRING_PROOF_BASELINE: frozenset[str] = frozenset({
    "poison/test_oracle_poison.py::test_poison_the_demand_log_names_the_same_transform:109",
    "test_collapse_record.py::test_only_the_collapse_instrument_installs_a_shared_brain:145",
    "test_guard_register.py::test_the_headline_count_equals_the_rows_it_counts:38",
    "test_k1_family_deletion.py::test_deleted_family_symbols_resolve_nowhere:43",
    "test_loss_ledger.py::test_write_outputs_lands_both_files_under_run_dir:195",
    "test_m5_absorption.py::test_ask_has_no_gather_fork:83",
    "test_m5_absorption.py::test_ask_has_no_weak_retrieval_predicate:100",
    "test_m5_absorption.py::test_ask_has_no_weak_retrieval_predicate:98",
    "test_m5_absorption.py::test_ask_has_no_weak_retrieval_predicate:99",
    "test_m5_absorption.py::test_ask_once_has_no_dispatch_choice:298",
    "test_m5_absorption.py::test_bridge_has_no_decide_live_endpoint:64",
    "test_m5_absorption.py::test_bridge_has_no_decide_live_endpoint:65",
    "test_m5_absorption.py::test_drive_has_no_live_branch:58",
    "test_m5_absorption.py::test_drive_has_no_live_branch:59",
    "test_m5_absorption.py::test_shadow_keeps_the_feed_not_the_live_half:70",
    "test_m5_absorption.py::test_shadow_keeps_the_feed_not_the_live_half:71",
    "test_m6_declaration.py::test_d11_the_lattice_join_is_one_declaration:26",
    "test_m6_declaration.py::test_d13_the_stack_urls_are_read_once:223",
    "test_m6_declaration.py::test_d13_the_stack_urls_are_read_once:224",
    "test_m6_declaration.py::test_d13_the_stack_urls_are_read_once:225",
    "test_m6_declaration.py::test_d13_the_stack_urls_are_read_once:226",
    "test_m6_declaration.py::test_d15_the_declaration_names_every_branch:138",
    "test_m6_declaration.py::test_d15_the_declaration_names_every_branch:139",
    "test_m6_declaration.py::test_d15_the_declaration_names_every_branch:140",
    "test_m6_declaration.py::test_d15_the_declaration_names_every_branch:141",
    "test_m7_register.py::test_d6_executor_withhold_derives_from_the_one_vocabulary:85",
    "test_m7_register.py::test_the_register_headings_equal_the_census:55",
    "test_pricing_table.py::test_lambda_usd_has_one_source_and_fails_loud:121",
    "test_pricing_table.py::test_no_priced_constant_is_declared_outside_the_table:93",
    "test_pricing_table.py::test_no_priced_constant_is_declared_outside_the_table:94",
    "test_pricing_table.py::test_realised_utility_report_branch_is_spelled_through_the_atom:102",
    "test_recorder.py::test_the_family_leaves_do_not_append_the_decision_ledger_themselves:134",
    "test_reliability.py::test_the_fold_lives_once:100",
    "test_reliability.py::test_the_fold_lives_once:101",
    "test_reliability.py::test_the_fold_lives_once:102",
    "test_reliability.py::test_the_fold_lives_once:103",
    "test_replay_audit.py::test_the_arms_of_one_question_share_a_retrieval_draw:442",
    "test_seam.py::test_only_the_seam_calls_optimise:136",
    "test_seam.py::test_only_the_seam_posts_decide:150",
})


def _tree_substring_proofs() -> list[str]:
    found: list[str] = []
    for root in (_TESTS, _ROOT / "scripts", _ROOT / "src"):
        for py in root.rglob("*.py"):
            try:
                rel = py.relative_to(_TESTS).as_posix()
            except ValueError:
                rel = py.relative_to(_ROOT).as_posix()
            if rel in _EXEMPT:
                continue
            found += substring_proofs(py.read_text(encoding="utf-8"), rel)
    return sorted(found)


def test_poison_no_guard_proves_a_call_with_a_substring() -> None:
    """Rule 1. MUST FAIL when a NEW guard proves a call by looking for its spelling in the
    source. Use `tests/_guard_ast.calls(obj, name)` instead: it resolves the call by AST, so
    a name in a comment or a docstring is not a call and cannot satisfy it. Killed by
    reintroducing `assert "leader_order(" in inspect.getsource(LK)` — and, unlike the regex
    this replaced, by any of the six other in-tree spellings of the same proof."""
    found = frozenset(_tree_substring_proofs())
    assert found == _SUBSTRING_PROOF_BASELINE, (
        f"substring-proof census moved.\n  added: {sorted(found - _SUBSTRING_PROOF_BASELINE)}"
        f"\n  removed: {sorted(_SUBSTRING_PROOF_BASELINE - found)}\n"
        f"A COMMENT satisfies a substring while the chain underneath is re-spelled to "
        f"disagree (r23 F10). Assert the call with _guard_ast.calls(), or assert the "
        f"behaviour. If you CONVERTED a site, update the baseline in the same commit."
    )


# r25 (L8): the rule is a PURE FUNCTION over a parsed module, so it can be mutation-tested
# on synthetic input. As a census over the real tests/ tree it could only be tested by
# mutating the real tree — which is why its previous defect (concatenating the MODULE
# docstring, so every fixture in a file whose header carried a trigger phrase passed
# regardless of its own text) survived undetected.

_MUTATION_PHRASE = re.compile(r"\bF\d+\b|MUST FAIL|kills it|goes red|is the seed")


def fixtures_missing_mutation(source: str, label: str = "") -> list[str]:
    """Every `test_poison_*` in ``source`` whose OWN docstring names no mutation."""
    tree = ast.parse(source)
    out: list[str] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
                and node.name.startswith("test_poison_")):
            continue
        if not _MUTATION_PHRASE.search(ast.get_docstring(node) or ""):
            out.append(f"{label}::{node.name}" if label else node.name)
    return out


def test_poison_the_mutation_rule_reads_the_fixtures_own_docstring() -> None:
    """L8. MUST FAIL if the rule consults anything but the fixture's own docstring. Killed
    by concatenating the module docstring — under that spelling the synthetic case below
    passes, because the module header carries a trigger phrase and the fixture does not."""
    synthetic = (
        '"""A module whose header says: each names the mutation that kills it."""\n'
        "def test_poison_named() -> None:\n"
        '    """MUST FAIL when x. Killed by y."""\n'
        "    pass\n"
        "def test_poison_unnamed() -> None:\n"
        '    """A fixture nobody has watched fail."""\n'
        "    pass\n")
    assert fixtures_missing_mutation(synthetic) == ["test_poison_unnamed"], (
        "the mutation rule accepted a fixture whose own docstring names no kill — it is "
        "reading the module docstring, so the census's universe is the FILE, not the "
        "fixture"
    )


def test_poison_every_fixture_names_the_mutation_that_kills_it() -> None:
    """Rule 2. MUST FAIL when a poison fixture names no kill. Every `test_poison_*` must
    say, in its OWN docstring, what planted violation makes it fail — a fixture nobody has
    watched fail is decoration, and its register row cannot honestly read `resolved`.
    Killed by adding a poison fixture whose docstring names no mutation."""
    missing: list[str] = []
    for py in (_TESTS / "poison").rglob("test_*.py"):
        missing += fixtures_missing_mutation(
            py.read_text(), py.relative_to(_TESTS).as_posix())
    assert not missing, (
        f"poison fixture(s) that do not name what kills them: {missing} — a fixture "
        f"nobody has watched fail proves nothing, and r23's own first oracle control "
        f"passed its own mutation"
    )


# --- r27 C9: the substring rule is a pure function, so it is mutation-testable ---------
# The regex this replaced could only be exercised against the real tree, so its narrowness
# was invisible: it matched ONE spelling, that spelling appeared nowhere, and it was
# defeated with no plant. These cases are the seven live spellings it could not see.

_SPELLINGS = {
    "bare_getsource": 'def test_a():\n src = inspect.getsource(LK)\n assert "f(" in src\n',
    "direct_getsource": 'def test_a():\n assert "f(" in inspect.getsource(LK)\n',
    "fstring_needle": 'def test_a():\n s = P.read_text()\n assert f"x={N}" in s\n',
    "negated": 'def test_a():\n s = P.read_text()\n assert "f(" not in s\n',
    "argumented_read": 'def test_a():\n assert "f(" in P.read_text(encoding="utf-8")\n',
    "count_compare": 'def test_a():\n s = inspect.getsource(M)\n assert s.count("f(") == 1\n',
    "regex_over_source": 'def test_a():\n s = P.read_text()\n assert re.search(r"f\\(", s)\n',
    "comprehension": ('def test_a():\n'
                      ' bad = [p for p in R.rglob("*.py") if "f(" in p.read_text()]\n'
                      ' assert not bad\n'),
    "aliased_chain": ('def test_a():\n src = inspect.getsource(M)\n t = src\n'
                      ' assert "f(" in t\n'),
    # `ast.walk` is breadth-FIRST, so the nested binding is visited AFTER the shallower
    # statement that consumes it. One pass leaves `text` untainted; only the fixed point
    # sees it. Without this case the iteration in `_tainted_names` is decoration — it was,
    # and its mutation left the whole file green until this case was added.
    "depth_ordered_chain": ('def test_a():\n if flag:\n  src = inspect.getsource(M)\n'
                            ' text = src\n assert "f(" in text\n'),
}


@pytest.mark.parametrize("name", sorted(_SPELLINGS))
def test_poison_the_substring_rule_sees_every_spelling(name: str) -> None:
    """r27 C9. MUST FAIL if the rule narrows back to one spelling. The regex it replaced
    matched a bare literal against `inspect.getsource` or an EMPTY-paren `read_text()` at
    the start of a stripped line — 2 of 7 live forms, and the one it caught was in tree
    zero times. Killed by dropping any arm of `_is_source_text`, `_matcher_over_source`
    or the taint fixed point."""
    assert substring_proofs(_SPELLINGS[name]), (
        f"the {name} spelling of a substring proof was not seen — the rule's universe is "
        f"a spelling again"
    )


def test_poison_the_substring_rule_does_not_flag_an_output_round_trip() -> None:
    """r27 C9. MUST FAIL if the rule stops telling a source read from an OUTPUT read.
    Asserting on a file the test just wrote is an ordinary behavioural test; flagging it
    would push four unrelated modules onto the baseline and turn the ratchet into an
    exemption list. Killed by dropping the `outputs` argument from `_is_source_text`."""
    produced = ('def test_a(tmp_path):\n'
                ' out = tmp_path / "report.md"\n'
                ' write_report(out)\n'
                ' assert "# Report" in out.read_text()\n')
    assert substring_proofs(produced) == [], (
        "a round-trip assertion on a produced artefact was called a substring proof"
    )
