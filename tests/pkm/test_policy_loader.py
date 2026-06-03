"""Tests for ``pkm.policy_loader`` -- loading policy functions from disk."""

from __future__ import annotations

from pathlib import Path

import pytest

from pkm.policy import Allow
from pkm.policy_loader import load_policy


def _write_policy(root: Path, name: str, body: str) -> None:
    (root / "policies").mkdir(exist_ok=True)
    (root / "policies" / f"{name}.py").write_text(body, encoding="utf-8")


def test_load_policy_returns_callable(tmp_path: Path) -> None:
    _write_policy(
        tmp_path,
        "my_policy",
        "from pkm.policy import Allow\n"
        "def my_policy(transform_decl, sources, estimated_cost, context):\n"
        "    return Allow()\n",
    )
    fn = load_policy(tmp_path, "my_policy")
    assert callable(fn)
    result = fn(None, [], None, None)
    assert isinstance(result, Allow)


def test_load_missing_policy_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="no_such_policy"):
        load_policy(tmp_path, "no_such_policy")


def test_load_policy_wrong_function_name_raises(tmp_path: Path) -> None:
    _write_policy(
        tmp_path,
        "bad_name",
        "def something_else(td, s, ec, ctx):\n"
        "    pass\n",
    )
    with pytest.raises(ImportError, match="bad_name"):
        load_policy(tmp_path, "bad_name")
