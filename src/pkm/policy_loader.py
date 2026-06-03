"""Load policy functions from ``<root>/policies/<name>.py`` (SPEC v0.2.0 §19.1).

Each policy module exports a single callable whose name matches the
module filename.  The loader uses ``importlib`` to import the file
directly, following the same pattern as the migration loader in
``catalogue.py``.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pkm.policy import PolicyCallable


def load_policy(root: Path, name: str) -> PolicyCallable:
    """Load a policy function from ``<root>/policies/<name>.py``.

    The module must contain a callable named ``<name>``.

    Raises:
        FileNotFoundError: Policy file does not exist.
        ImportError: Module cannot be loaded or lacks the expected callable.
    """
    policy_path = root / "policies" / f"{name}.py"
    if not policy_path.exists():
        raise FileNotFoundError(
            f"policy {name!r} not found at {policy_path}"
        )

    spec = importlib.util.spec_from_file_location(
        f"pkm._loaded_policies.{name}", policy_path,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load policy module {policy_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    fn = getattr(module, name, None)
    if fn is None or not callable(fn):
        raise ImportError(
            f"policy module {policy_path} has no callable {name!r}"
        )
    return fn  # type: ignore[no-any-return]
