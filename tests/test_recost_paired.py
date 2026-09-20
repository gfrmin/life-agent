"""scripts/recost_paired: an archived typed arm re-priced at the menu's declared prices."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import recost_paired as RP

from life_agent.core import pricing as PRC


def _fixture(*steps: list[str]) -> dict[str, Any]:
    wire: list[dict[str, Any]] = [
        {"seam": "http", "request": {"url": "http://b/retrieve", "payload": {"rerank": True}}}]
    wire += [{"seam": "http", "request": {"url": "http://b/decide",
                                          "payload": {"applied_probes": list(s)}}}
             for s in steps]
    return {"wire": wire}


def _row(qid: str, *, cost: float = 0.0) -> dict[str, Any]:
    return {"question_id": qid, "answerable": True,
            "typed": {"action": "report", "correct": True, "cost_usd": cost, "withheld": None},
            "mono": {"action": "report", "correct": True, "cost_usd": 0.4, "withheld": None}}


def test_applied_is_the_ordered_union_over_the_decides() -> None:
    fx = _fixture([], ["corroborate_haiku"], ["corroborate_haiku", "deliberate"])
    assert RP.applied_from_fixture(fx) == ["corroborate_haiku", "deliberate"]
    assert RP.applied_from_fixture({"wire": []}) == []


def test_recost_prices_the_typed_arm_at_the_menu_and_keeps_what_it_metered() -> None:
    rows = [_row("q2-001", cost=0.003)]
    out = RP.recost(rows, {"q2-001": ["corroborate_haiku", "deliberate"]})
    t = out[0]["typed"]
    assert t["cost_usd"] == pytest.approx(
        PRC.menu_price("corroborate_haiku") + PRC.menu_price("deliberate"))
    assert t["metered_usd"] == 0.003
    assert t["applied"] == ["corroborate_haiku", "deliberate"]
    assert out[0]["mono"] == rows[0]["mono"]  # the outside arm is untouched


def test_a_row_without_a_recorded_sequence_refuses_the_whole_file() -> None:
    with pytest.raises(KeyError, match="1 row"):
        RP.recost([_row("q2-001"), _row("q2-002")], {"q2-001": []})


def test_main_writes_the_priced_archive_beside_the_source(tmp_path: Path) -> None:
    src = tmp_path / "paired-gate-x.jsonl"
    src.write_text(json.dumps(_row("q2-001")) + "\n", encoding="utf-8")
    fx = tmp_path / "fx"
    fx.mkdir()
    (fx / "m-aloop-q2-001.json").write_text(json.dumps(_fixture(["retrieve_rerank"])),
                                            encoding="utf-8")
    assert RP.main([str(src), "--fixtures", str(fx)]) == 0
    out = tmp_path / "paired-gate-x-priced.jsonl"
    row = json.loads(out.read_text(encoding="utf-8").splitlines()[0])
    assert row["typed"]["applied"] == ["retrieve_rerank"]
    assert row["typed"]["cost_usd"] == pytest.approx(PRC.menu_price("retrieve_rerank"))
    assert RP.main([str(src), "--fixtures", str(fx)]) == 2  # never overwrites
