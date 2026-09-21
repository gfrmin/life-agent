"""The porcelain stage matrix of scripts/ingest_sources.py.

Pins the interaction contract's porcelain rule: the composition owns sequencing
knowledge so the human doesn't have to — `--chunk` chains `rebuild-index` after
`chunk --backfill`, because a chunk pass whose FTS index is stale silently
misses the new content in search (invariant 3: nothing silent).
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import ingest_sources  # noqa: E402


def test_ingest_alone_only_registers() -> None:
    assert ingest_sources.stages(extract=False, chunk=False) == [["ingest"]]


def test_extract_appends_one_stage() -> None:
    assert ingest_sources.stages(extract=True, chunk=False) == [["ingest"], ["extract"]]


def test_chunk_chains_rebuild_index() -> None:
    assert ingest_sources.stages(extract=False, chunk=True) == [
        ["ingest"], ["chunk", "--backfill"], ["rebuild-index"]]


def test_full_promote_runs_all_stages_in_order() -> None:
    assert ingest_sources.stages(extract=True, chunk=True) == [
        ["ingest"], ["extract"], ["chunk", "--backfill"], ["rebuild-index"]]


# --- an absent root must not take the whole ingest down (foundations §14) ---------------


def _reg(tmp_path, availability: str):
    """A two-root registry: one present, one pointing at a path that isn't here."""
    from data_source_registry import load_registry

    present = tmp_path / "present"
    present.mkdir()
    (present / "a.md").write_text("hello", encoding="utf-8")
    reg = tmp_path / "r.yaml"
    reg.write_text(
        "version: 1\nroots:\n"
        f"  - {{id: present, kind: filetree, path: {present}}}\n"
        f"  - {{id: gone, kind: filetree, path: {tmp_path / 'gone'}, "
        f"availability: {availability}}}\n",
        encoding="utf-8")
    return load_registry(reg)


def test_enumerate_filetree_still_refuses_a_missing_path(tmp_path: Path) -> None:
    # the primitive is unchanged: absence is an error at this level. What changes is who
    # decides whether that error is fatal — the caller now knows the declared intent.
    import pytest
    from data_source_registry import RegistryError

    root = _reg(tmp_path, "required").roots[1]
    with pytest.raises(RegistryError, match="not a directory"):
        ingest_sources.enumerate_filetree(root)


def test_an_optional_absent_root_is_skipped_not_fatal(tmp_path: Path) -> None:
    # THE regression this exists for: one absent root used to raise out of
    # enumerate_filetree and abort every OTHER root's ingest, so a machine holding most of
    # the corpus could ingest none of it. The present root must still promote its files.
    registry = _reg(tmp_path, "optional")
    absent = [r for r in registry.roots
              if r.availability == "optional" and not r.resolves()]
    keep = [r for r in registry.roots if r.enabled and r not in absent]
    assert [r.id for r in absent] == ["gone"]
    assert [r.id for r in keep] == ["present"]
    entries = []
    for root in keep:
        entries.extend(ingest_sources.entries_for_root(root, dry_run=True))
    assert [Path(e["path"]).name for e in entries] == ["a.md"]


# --- The newcomer's two first errors: a store with no address, a registry with no roots.
# J3's bar is "reusable by a stranger", and both of these used to name a key the reader
# has never seen instead of the file to copy. The example files they point at are the
# ones SETUP.md §3 already tells them to copy, so the message and the doc cannot drift
# without this test noticing the file is gone.

def test_a_missing_pkm_config_names_the_example_to_copy(tmp_path: Path) -> None:
    """Killed by restoring the bare `has no string root_dir`, which fires on an absent
    file too and reads as a malformed config the reader never wrote."""
    import data_source_registry as REG
    try:
        ingest_sources._pkm_root(tmp_path / "nowhere" / "pkm.yaml")
    except REG.RegistryError as e:
        msg = str(e)
    else:                                            # pragma: no cover - the failure case
        raise AssertionError("an absent pkm config did not fail")
    assert "config/pkm.example.yaml" in msg and "cp " in msg
    assert (REPO / "config" / "pkm.example.yaml").is_file(), \
        "the error names an example file that is not in the tree"


def test_a_missing_registry_names_the_example_to_copy(tmp_path: Path) -> None:
    import data_source_registry as REG
    try:
        REG.load_registry(tmp_path / "kb" / "config" / "data-sources.yaml")
    except REG.RegistryError as e:
        msg = str(e)
    else:                                            # pragma: no cover - the failure case
        raise AssertionError("an absent registry did not fail")
    assert "config/data-sources.example.yaml" in msg and "cp " in msg
    assert (REPO / "config" / "data-sources.example.yaml").is_file(), \
        "the error names an example file that is not in the tree"



# --- the extractor preflight: drift is named BEFORE a pass over the corpus -------------
#
# `pkm extract`'s own guard is correct but per-producer and lazy, so it reports one
# drifted producer per full run. On 2026-09-20 three of five had drifted and each cost
# its own pass to find. These tests pin the preflight that reads them all up front.


def _cfg(tmp_path: Path, **versions: str) -> Path:
    p = tmp_path / "pkm.yaml"
    body = "root_dir: /nowhere\nextractors:\n" + "".join(
        f'  {name}:\n    version: "{v}"\n    config: {{}}\n'
        for name, v in versions.items())
    p.write_text(body, encoding="utf-8")
    return p


def test_a_matching_config_reports_no_drift(tmp_path: Path) -> None:
    """The discriminating control: the preflight must not fire when nothing moved."""
    cfg = _cfg(tmp_path, pandoc="3.10.2", email="1")
    probes = {"pandoc": lambda: "3.10.2", "email": lambda: "1"}
    assert ingest_sources.preflight(cfg, probes) == []


def test_every_drifted_producer_is_named_not_only_the_first(tmp_path: Path) -> None:
    """The whole reason this exists. Killed by returning on the first mismatch, which is
    what `pkm extract` effectively does and what turned one upgrade into three aborted
    runs."""
    cfg = _cfg(tmp_path, pandoc="3.10.2", docling="2.90.0",
               unstructured="0.22.21", tesseract="5.5.2", email="1")
    probes = {"pandoc": lambda: "3.10.2", "docling": lambda: "2.96.1",
              "unstructured": lambda: "0.22.31", "tesseract": lambda: "5.5.3",
              "email": lambda: "1"}
    drifts = ingest_sources.preflight(cfg, probes)
    assert [d.producer for d in drifts] == ["docling", "unstructured", "tesseract"]
    assert drifts[0] == ("docling", "2.90.0", "2.96.1")


def test_a_producer_the_config_does_not_declare_is_not_checked(tmp_path: Path) -> None:
    """pkm only requires config for the producers routing reaches, so an undeclared
    producer is not this run's business. Killed by iterating the probe table instead of
    the declaration, which would fail a pandoc-only corpus on a missing docling."""
    cfg = _cfg(tmp_path, pandoc="3.10.2")
    probes = {"pandoc": lambda: "3.10.2", "docling": lambda: "2.96.1"}
    assert ingest_sources.preflight(cfg, probes) == []


def test_a_probe_that_cannot_answer_is_drift_and_says_why(tmp_path: Path) -> None:
    """Declared but not installed is the same failure for this run as declared at the
    wrong version. Killed by letting the exception escape (the preflight becomes the
    outage it exists to prevent) or by swallowing it into a bare 'unavailable' that
    hides which import is missing."""
    def missing() -> str:
        raise ModuleNotFoundError("no docling here")

    cfg = _cfg(tmp_path, docling="2.96.1")
    (drift,) = ingest_sources.preflight(cfg, {"docling": missing})
    assert drift.producer == "docling"
    assert drift.installed.startswith(ingest_sources.UNAVAILABLE)
    assert "ModuleNotFoundError" in drift.installed


def test_a_drift_line_names_both_versions(tmp_path: Path) -> None:
    """The operator has to act on this line alone; a line that says only 'mismatch'
    sends them back to the config to find out what to type."""
    line = ingest_sources.Drift("docling", "2.90.0", "2.96.1").line()
    assert "docling" in line and "2.90.0" in line and "2.96.1" in line
