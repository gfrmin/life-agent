"""Structural guard: derived/personal artifacts are written OUTSIDE the repo.

The repo holds only code; the corpus, eval set, and logs live under
``$LIFE_AGENT_KB``. This test pins that invariant on the scripts that actually
write, so a future change that targets a path inside the repo tree fails here
(and in review) rather than silently leaking data into a public repo.

Run in the pkm env:
    uv run --project ../pkm python -m pytest ./tests/test_output_gateway.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "scripts"))

import mail_bridge  # noqa: E402
import run_eval  # noqa: E402


def _outside_repo(p: Path) -> bool:
    resolved = p.expanduser().resolve()
    repo = _REPO.resolve()
    return repo != resolved and repo not in resolved.parents


def test_kb_root_is_outside_the_repo(monkeypatch) -> None:
    monkeypatch.delenv("LIFE_AGENT_KB", raising=False)
    assert _outside_repo(run_eval._kb_root())
    assert _outside_repo(mail_bridge._kb_root())


def test_eval_log_write_target_is_under_the_kb_not_the_repo(monkeypatch, tmp_path) -> None:
    # run_eval writes its only output to _kb_root() (writes eval/eval_log.md)
    monkeypatch.setenv("LIFE_AGENT_KB", str(tmp_path))
    out = run_eval._kb_root() / "eval/eval_log.md"
    assert _outside_repo(out)
