"""Manual acceptance against the real Kayak export (private, out-of-repo). Run:
    TRIPS_KAYAK_EXPORT=/path/to/kayak-trips-export.json uv run pytest \
        tests/trips/test_acceptance.py -m system -v
The export path is an env var — never a literal (public repo, PII)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from life_agent.trips import kayak, store


@pytest.mark.system
def test_full_export_imports_and_dedupes() -> None:
    src = os.environ.get("TRIPS_KAYAK_EXPORT")
    if not src:
        pytest.skip("set TRIPS_KAYAK_EXPORT to the real export to run acceptance")
    stats = kayak.import_export(Path(src).expanduser())
    # The design measured 260 events -> 259 identities (one true duplicate collapses).
    assert stats["reservations"] >= 250
    rows = store.timeline()
    assert len(rows) <= stats["reservations"]  # dedup never inflates
    # Re-import is a no-op.
    again = len(store.timeline())
    kayak.import_export(Path(src).expanduser())
    assert len(store.timeline()) == again
