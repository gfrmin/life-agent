"""The harness positive control — deliberately failing, by design.

Not named ``test_*.py``, so the ordinary suite never collects it. CI runs THIS FILE
explicitly as its first test step and **requires it to go red**. A green test step is
otherwise indistinguishable from a test step that ran nothing: an import error in a
conftest, a bad marker expression, a path typo, a runner that silently collected zero
items. This file makes the harness prove it can speak before any of its verdicts are
believed.

If this ever passes, the failure is in the runner, not here.
"""
from __future__ import annotations


def test_the_harness_can_report_a_failure() -> None:
    """MUST FAIL. CI asserts a non-zero exit from this file."""
    assert False, (  # noqa: B011
        "harness positive control — this failure is expected and required; a CI run in "
        "which this passes has a broken test runner, not a fixed test"
    )
