"""The golden-replay harness (design §9) against a fully synthetic KB.

# PII-OK: synthetic — every value below is invented; the marker strings exist only to prove the
comparator output never prints record values."""
from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from life_agent.ledger import golden as G
from pkm.cache import content_file
from tests.conftest import LEDGER_MARKER

REPO = Path(__file__).resolve().parents[1]
MARKER = LEDGER_MARKER   # must never appear in harness output


ALL = list(G.ARTEFACTS)


def test_snapshot_then_compare_is_green_and_prints_no_values(
        ledger_kb: tuple[Path, G.Paths]) -> None:
    root, p = ledger_kb
    out = io.StringIO()
    d = G.snapshot(ALL, "T0", p, kb=root, out=out)
    assert (d / "manifest.json").exists() and all((d / f"{n}.json").exists() for n in ALL)
    ok, res = G.compare(ALL, "T0", p, kb=root, out=out)
    assert ok and all(res.values())
    text = out.getvalue()
    assert MARKER not in text
    assert "GREEN" in text and "RED" not in text
    # the criteria kinds are what §9 states
    kinds = {n: json.loads((d / f"{n}.json").read_text())["kind"] for n in ALL}
    assert kinds["gtd"] == kinds["trips"] == kinds["pkm-index"] == "semantic"
    assert kinds["state-md"] == "byte" and kinds["utility-fold-version"] == "byte"
    assert kinds["answers"] == "identity"


@pytest.mark.parametrize("seed", [s for s in G.SEEDS if G.SEEDS[s].category != "invariance"])
def test_each_kill_category_kills_what_section_9_claims(ledger_kb: tuple[Path, G.Paths],
                                                        seed: str) -> None:
    root, p = ledger_kb
    G.snapshot(ALL, "T0", p, kb=root, out=io.StringIO())
    out = io.StringIO()
    ok, res = G.compare(ALL, "T0", p, kb=root, seed=seed, out=out)
    assert not ok
    for claimed in G.SEEDS[seed].must_kill:
        assert res[claimed] is False, (seed, claimed, out.getvalue())
    assert "CLAIM MET" in out.getvalue()
    assert MARKER not in out.getvalue()


def test_invariance_fixture_stays_green(ledger_kb: tuple[Path, G.Paths]) -> None:
    root, p = ledger_kb
    G.snapshot(ALL, "T0", p, kb=root, out=io.StringIO())
    out = io.StringIO()
    ok, res = G.compare(ALL, "T0", p, kb=root, seed="unrouted-reaction", out=out)
    assert ok and all(res.values())
    assert "GREEN as required" in out.getvalue()


def test_two_route_counts_agree_on_the_synthetic_kb(ledger_kb: tuple[Path, G.Paths]) -> None:
    _root, p = ledger_kb
    c = G.counts(p)
    for sid, row in c.items():
        if row.get("exists"):
            assert row["parsed"] == row["nonempty_lines"] == row["raw_newlines"], sid
    assert c["pkm.artifact"]["meta_json_files"] == 1 and c["pkm.demand"]["lines"] == 1


def test_seed_never_touches_the_legacy_files(ledger_kb: tuple[Path, G.Paths]) -> None:
    root, p = ledger_kb
    before = {n: f.read_bytes() for n, f in p.legacy_files().items()}
    G.snapshot(ALL, "T0", p, kb=root, out=io.StringIO())
    for seed in G.SEEDS:
        G.compare(ALL, "T0", p, kb=root, seed=seed, out=io.StringIO())
    after = {n: f.read_bytes() for n, f in p.legacy_files().items()}
    assert before == after
    assert content_file(p.pkm_root, "a" * 64).read_bytes() == b'{"answer": "synthetic"}'  # type: ignore[arg-type]


def test_cli_smoke(ledger_kb: tuple[Path, G.Paths], monkeypatch: pytest.MonkeyPatch,
                   capsys: pytest.CaptureFixture[str]) -> None:
    root, p = ledger_kb
    monkeypatch.setattr(G.Paths, "from_config", classmethod(lambda cls: p))
    monkeypatch.setattr(G.config, "KB", root)
    assert G.main(["snapshot", "all", "--t0", "T1"]) == 0
    assert G.main(["compare", "all", "--t0", "T1"]) == 0
    assert G.main(["compare", "gtd", "--t0", "T1", "--seed-defect", "drop-task-disposed"]) == 1
    assert G.main(["counts"]) == 0
    assert MARKER not in capsys.readouterr().out


def test_v5_unrouted_claude_verdict_kills_exactly_a7(ledger_kb: tuple[Path, G.Paths]) -> None:
    """Kill 5 (V5): A7 red, everything else green — the routing-blind map vs the routing-gated
    join, pinned beside the invariance fixture."""
    root, p = ledger_kb
    G.snapshot(ALL, "T0", p, kb=root, out=io.StringIO())
    out = io.StringIO()
    ok, res = G.compare(ALL, "T0", p, kb=root, seed="unrouted-claude-verdict", out=out)
    assert not ok
    assert [n for n, v in res.items() if not v] == ["claude-verdicts"]
    assert "CLAIM MET [EXACT]" in out.getvalue()
    assert G.SEEDS["unrouted-claude-verdict"].exact


def test_v4_verdict_line_flags_exact_or_superset(ledger_kb: tuple[Path, G.Paths]) -> None:
    root, p = ledger_kb
    G.snapshot(ALL, "T0", p, kb=root, out=io.StringIO())
    for seed in G.SEEDS:
        if G.SEEDS[seed].category == "invariance":
            continue
        out = io.StringIO()
        G.compare(ALL, "T0", p, kb=root, seed=seed, out=out)
        line = next(ln for ln in out.getvalue().splitlines() if ln.startswith("verdict"))
        assert "[EXACT]" in line or "[SUPERSET collateral=" in line, line


def test_s8_work_dir_removed_on_claimed_kill_and_retained_otherwise(
        ledger_kb: tuple[Path, G.Paths], monkeypatch: pytest.MonkeyPatch) -> None:
    root, p = ledger_kb
    d = G.snapshot(ALL, "T0", p, kb=root, out=io.StringIO())
    snaps = {f.name: f.read_bytes() for f in d.iterdir() if f.is_file()}
    legacy = {n: f.read_bytes() for n, f in p.legacy_files().items()}
    # success: the working copy is scratch and goes away
    ok, _ = G.compare(ALL, "T0", p, kb=root, seed="drop-task-disposed", out=io.StringIO())
    assert not ok and not G.work_dir(d, "drop-task-disposed").exists()
    # a MISSED claim (a seed that changes nothing yet claims a kill): retained for diagnosis
    inert = G.Seed("inert", "kill-2 drop", ("gtd",), lambda paths, w: paths)
    monkeypatch.setitem(G.SEEDS, "inert", inert)
    out = io.StringIO()
    ok, _ = G.compare(ALL, "T0", p, kb=root, seed="inert", out=out)
    assert ok and "CLAIM MISSED" in out.getvalue()
    assert G.work_dir(d, "inert").exists()
    # nothing but work/<seed>/ was ever in the deletion path
    assert {f.name: f.read_bytes() for f in d.iterdir() if f.is_file()} == snaps
    assert {n: f.read_bytes() for n, f in p.legacy_files().items()} == legacy
    with pytest.raises(ValueError):
        G._remove_work(root / "not-a-work-dir")
    assert (root / "tasks").exists()
