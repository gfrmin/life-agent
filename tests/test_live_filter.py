"""One definition of live traffic: the production readout and the live readout agree."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import live_readout as LR
import production_readout as PR

ROWS = [{"run_id": "gate-20260901", "tx_time": "2026-09-01T00:00:00+00:00"},
        {"run_id": "collapse-20260901", "tx_time": "2026-09-01T00:00:00+00:00"},
        {"run_id": "ask", "tx_time": "2026-09-01T00:00:00+00:00"}]


def test_both_readouts_keep_only_the_ask_row() -> None:
    assert [LR.is_live(r) for r in ROWS] == [False, False, True]
    assert [PR._production(r, "2026-01-01") for r in ROWS] == [False, False, True]
    assert not hasattr(PR, "EXCLUDED_RUN_PREFIXES")
