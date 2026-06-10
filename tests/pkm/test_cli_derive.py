"""CLI wiring for ``pkm derive`` (SPEC §18.11).

Mirrors ``tests/pkm/test_cli.py``: ``main(argv)`` is called directly with
``--config``; argparse usage errors surface as ``SystemExit(2)``. The
hermetic smoke is the missing-leaf failure path — no producer is ever
constructed, so no model machinery is touched.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from pkm.catalogue import run_migrations
from pkm.cli import main


def _setup(root: Path) -> tuple[str, Path]:
    """Declarations + config but NO extracted artifact."""
    run_migrations(root)
    for d in ("transforms", "prompts", "schemas"):
        (root / d).mkdir(parents=True, exist_ok=True)
    (root / "prompts" / "t_upper_v1.txt").write_text("p\n", encoding="utf-8")
    (root / "schemas" / "t_upper_v1.json").write_text(
        '{"type": "object"}', encoding="utf-8",
    )
    (root / "transforms" / "t_upper.yaml").write_text(
        "name: t_upper\n"
        "version: 0.1.0\n"
        "producer_class: tests.derive.t_upper\n"
        "model: {provider: ollama, model: test-model}\n"
        "prompt: {name: t_upper_v1, file: prompts/t_upper_v1.txt}\n"
        "output_schema: {name: t_upper_v1, file: schemas/t_upper_v1.json}\n"
        "policies: []\n"
        "input: {producer: email, role: source_text, required_status: success}\n",
        encoding="utf-8",
    )
    cfg = root / "config.yaml"
    cfg.write_text(f"root_dir: {root}\npolicies: {{}}\n", encoding="utf-8")
    return hashlib.sha256(b"no such source").hexdigest(), cfg


def test_cli_derive_missing_leaf_exits_1(
    tmp_root: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    sid, cfg = _setup(tmp_root)
    rc = main(["--config", str(cfg), "derive", "t_upper", "--source", sid])
    assert rc == 1
    out = capsys.readouterr().out
    assert "pkm extract" in out


def test_cli_derive_requires_exactly_one_input_form(tmp_root: Path) -> None:
    _, cfg = _setup(tmp_root)
    with pytest.raises(SystemExit) as exc:
        main(["--config", str(cfg), "derive", "t_upper"])
    assert exc.value.code == 2  # argparse: one of --source/--input required
