"""wald audits the act in tests (tests/test_wald_oracle.py); the act never imports it."""
import re
from pathlib import Path


def test_nothing_under_src_imports_wald() -> None:
    src = Path(__file__).resolve().parent.parent / "src"
    use = re.compile(r"^\s*(import|from)\s+wald\b", re.MULTILINE)
    assert [p for p in src.rglob("*.py") if use.search(p.read_text(encoding="utf-8"))] == []
