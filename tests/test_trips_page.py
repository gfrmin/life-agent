"""The trips page is a static asset; this guards the page↔server endpoint contract so a renamed
or dropped endpoint on either side fails a test rather than silently breaking the surface."""
from __future__ import annotations

from pathlib import Path

_PAGE = (Path(__file__).resolve().parents[1]
         / "src/life_agent/reach/trips/index.html").read_text(encoding="utf-8")


def test_page_is_html() -> None:
    assert _PAGE.startswith("<!DOCTYPE html>")
    assert "<title>Trips</title>" in _PAGE


def test_page_calls_every_server_endpoint() -> None:
    for endpoint in ("/api/timeline", "/api/now_next", "/api/search?q=", "/calendar.ics"):
        assert endpoint in _PAGE, f"page no longer references {endpoint}"


def test_page_renders_untrusted_fields_with_textcontent() -> None:
    # All reservation fields are untrusted; they must go through textContent (via el()), and
    # innerHTML may only ever clear a container to empty — never inject a value.
    import re
    assert "textContent" in _PAGE
    for assigned in re.findall(r"\.innerHTML\s*=\s*([^;]+);", _PAGE):
        assert assigned.strip() == '""', f"innerHTML assigned a non-empty value: {assigned!r}"
