"""§6.10 — a gate run must pin its TREE, not just its recipe.

Run 10 fired the run-9 recipe verbatim against a tree that had gained three further
decision-path changes, and no argument could say which of the four bought its one wrong
commit. The recipe was pinned; the tree it ran against was not. These tests pin the
instrument that closes that: a declared decision-path file set, hashed, recorded in
``run_meta.json``, and diffable against the comparison run's.

Hermetic: synthetic trees under tmp_path; no corpus, no KB, no network.

Run from the repo root:
    uv run --project . python -m pytest ./tests/test_gate_tree_pin.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import run_eval as RE


def _fake_repo(root: Path, *, extra: dict[str, str] | None = None) -> Path:
    """A tree with the shape the declaration names, plus decoys that must NOT be pinned."""
    files = {
        "src/life_agent/core/executor.py": "def decide(): ...\n",
        "src/life_agent/core/probes.py": "def probe_corroborate(): ...\n",
        "src/life_agent/core/retrieval.py": "def retrieve_set(): ...\n",
        "src/life_agent/bridge/server.py": "def log_decision(): ...\n",
        "scripts/eval_executor.py": "GROW = 1\n",
        "scripts/run_eval.py": "def main(): ...\n",
        # decoys: real files, none of them able to change a decision
        "src/life_agent/reach/telegram.py": "def send(): ...\n",
        "src/life_agent/tasks/store.py": "def apply(): ...\n",
        "src/life_agent/collapse/taps.py": "def replay(): ...\n",
        "docs/module-collapse-design.md": "# design\n",
        "src/life_agent/core/__pycache__/executor.cpython-313.pyc": "not source\n",
    }
    files.update(extra or {})
    for rel, body in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    return root


def test_the_tree_pins_the_decision_path_and_nothing_else(tmp_path: Path) -> None:
    tree = RE.decision_path_tree(_fake_repo(tmp_path))
    pinned = set(tree["files"])
    assert "src/life_agent/core/executor.py" in pinned
    assert "src/life_agent/core/probes.py" in pinned
    assert "src/life_agent/core/retrieval.py" in pinned
    assert "src/life_agent/bridge/server.py" in pinned
    assert "scripts/eval_executor.py" in pinned
    # the arm's harness shapes the run and is pinned with it
    assert "scripts/run_eval.py" in pinned
    # transport, act layer, the equivalence instrument and prose cannot change a decision
    assert not [p for p in pinned if p.startswith("src/life_agent/reach/")]
    assert not [p for p in pinned if p.startswith("src/life_agent/tasks/")]
    assert not [p for p in pinned if p.startswith("src/life_agent/collapse/")]
    assert not [p for p in pinned if p.endswith(".md")]
    assert not [p for p in pinned if "__pycache__" in p]


def test_the_digest_moves_when_a_decision_path_file_moves(tmp_path: Path) -> None:
    """The whole point: a one-character change anywhere on the declared path is visible."""
    before = RE.decision_path_tree(_fake_repo(tmp_path / "a"))
    after = RE.decision_path_tree(_fake_repo(
        tmp_path / "b", extra={"src/life_agent/core/probes.py": "def probe_corroborate(): pass\n"}))
    assert before["digest"] != after["digest"]
    assert before["files"]["src/life_agent/core/executor.py"] == \
        after["files"]["src/life_agent/core/executor.py"]


def test_the_digest_ignores_a_change_off_the_declared_path(tmp_path: Path) -> None:
    before = RE.decision_path_tree(_fake_repo(tmp_path / "a"))
    after = RE.decision_path_tree(_fake_repo(
        tmp_path / "b", extra={"src/life_agent/reach/telegram.py": "def send(x): ...\n"}))
    assert before["digest"] == after["digest"]


def test_the_diff_names_every_difference(tmp_path: Path) -> None:
    """A digest that differs is a refusal; the diff is what makes it actionable — run 10's
    report could say only 'something else changed'."""
    old = RE.decision_path_tree(_fake_repo(tmp_path / "a"))
    new = RE.decision_path_tree(_fake_repo(tmp_path / "b", extra={
        "src/life_agent/core/probes.py": "def probe_corroborate(): pass\n",   # changed
        "src/life_agent/core/newmod.py": "x = 1\n",                           # added
    }))
    (tmp_path / "b" / "src/life_agent/core/retrieval.py").unlink()            # removed
    new = RE.decision_path_tree(tmp_path / "b")

    d = RE.tree_diff(old, new)
    assert d["changed"] == ["src/life_agent/core/probes.py"]
    assert d["added"] == ["src/life_agent/core/newmod.py"]
    assert d["removed"] == ["src/life_agent/core/retrieval.py"]
    assert d["identical"] is False


def test_an_identical_tree_diffs_to_nothing(tmp_path: Path) -> None:
    old = RE.decision_path_tree(_fake_repo(tmp_path / "a"))
    new = RE.decision_path_tree(_fake_repo(tmp_path / "b"))
    d = RE.tree_diff(old, new)
    assert d == {"added": [], "removed": [], "changed": [], "identical": True}


def test_the_run_meta_carries_the_tree(tmp_path: Path) -> None:
    """Recorded in the sidecar written BEFORE the first question, like every other pin."""
    import argparse
    meta = RE.build_gate_run_meta(
        run_id="gate-test", args=argparse.Namespace(k=20), questions=[],
        questions_path=None, corpus={"digest": "d", "pin_status": "matched"},
        availability={}, baseline="monolithic")
    tree = meta["decision_path_tree"]
    assert tree["digest"] and tree["n"] > 0
    assert "src/life_agent/core/executor.py" in tree["files"]


def test_the_report_names_the_tree_difference(tmp_path: Path) -> None:
    """The diff is worthless in a sidecar nobody opens — run 10's FAIL was read from its
    report. Every difference is named there, in the report, above the verdict."""
    old = RE.decision_path_tree(_fake_repo(tmp_path / "a"))
    new = RE.decision_path_tree(_fake_repo(tmp_path / "b", extra={
        "src/life_agent/core/probes.py": "def probe_corroborate(): pass\n"}))
    section = RE.tree_pin_note(new, compare=old, compare_run_id="gate-earlier")

    assert "gate-earlier" in section
    assert "src/life_agent/core/probes.py" in section
    assert "changed" in section.lower()
    assert new["digest"][:16] in section


def test_the_report_says_so_when_the_tree_is_identical(tmp_path: Path) -> None:
    tree = RE.decision_path_tree(_fake_repo(tmp_path / "a"))
    section = RE.tree_pin_note(tree, compare=RE.decision_path_tree(_fake_repo(tmp_path / "b")),
                               compare_run_id="gate-earlier")
    assert "identical" in section.lower()
    assert "gate-earlier" in section


def test_an_undiffed_tree_is_named_not_silent(tmp_path: Path) -> None:
    """A run with no comparison is legitimate (the first of a series). Presenting it as if
    the background were pinned is not — that is precisely run 10's defect."""
    tree = RE.decision_path_tree(_fake_repo(tmp_path / "a"))
    section = RE.tree_pin_note(tree, compare=None, compare_run_id=None)
    assert "not diffed" in section.lower() or "no comparison" in section.lower()
    assert tree["digest"][:16] in section
    assert str(tree["n"]) in section


def _git(root: Path, *args: str) -> None:
    import subprocess
    subprocess.run(["git", "-C", str(root), *args], check=True,
                   capture_output=True, text=True)


def test_the_tree_reconstructs_from_a_recorded_clean_commit(tmp_path: Path) -> None:
    """Every run in the series predates this pin, and each recorded a git sha and a dirty
    flag. A clean sha IS the tree, so the whole back-series stays comparable — without
    this, §6.10 could only ever compare runs fired after itself."""
    root = _fake_repo(tmp_path / "repo")
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@example.invalid")  # PII-OK: synthetic git identity
    _git(root, "config", "user.name", "t")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "one")
    before = RE.decision_path_tree(root)

    (root / "src/life_agent/core/probes.py").write_text("def p(): pass\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "two")
    after = RE.decision_path_tree(root)

    assert RE.decision_path_tree_at(root, "HEAD~1") == before
    assert RE.decision_path_tree_at(root, "HEAD") == after
    assert RE.tree_diff(RE.decision_path_tree_at(root, "HEAD~1"), after)["changed"] == \
        ["src/life_agent/core/probes.py"]


def test_a_dirty_recorded_run_refuses_reconstruction(tmp_path: Path) -> None:
    """A run fired from a dirty tree is not its commit, and pretending otherwise would
    manufacture exactly the false 'nothing else changed' this entry exists to prevent."""
    meta = {"run_id": "gate-dirty", "life_agent_git": {"sha": "deadbeef", "dirty": True}}
    assert RE.comparison_tree(meta, root=tmp_path) is None

    meta_clean_but_unknown = {"run_id": "x", "life_agent_git": {"sha": None, "dirty": False}}
    assert RE.comparison_tree(meta_clean_but_unknown, root=tmp_path) is None


def test_a_recorded_tree_wins_over_reconstruction(tmp_path: Path) -> None:
    tree = RE.decision_path_tree(_fake_repo(tmp_path / "a"))
    meta = {"run_id": "x", "decision_path_tree": tree,
            "life_agent_git": {"sha": "deadbeef", "dirty": False}}
    assert RE.comparison_tree(meta, root=tmp_path) == tree


def test_the_note_separates_decision_logic_from_the_harness(tmp_path: Path) -> None:
    """A pin that fires on every run is a pin that gets ignored — the ignored-diff failure
    this entry warns about. The harness (`run_eval.py`) shapes a run and belongs in the
    digest, but a harness-only difference is not a decision change and must not read as
    one."""
    old = RE.decision_path_tree(_fake_repo(tmp_path / "a"))
    new = RE.decision_path_tree(_fake_repo(tmp_path / "b", extra={
        "scripts/run_eval.py": "def main(): pass\n"}))
    note = RE.tree_pin_note(new, compare=old, compare_run_id="gate-earlier")

    assert "harness" in note.lower()
    assert "scripts/run_eval.py" in note
    # no decision logic moved, so the note must not say the reading is unattributable
    assert "cannot be attributed" not in note.lower()


def test_the_note_flags_moved_decision_logic(tmp_path: Path) -> None:
    old = RE.decision_path_tree(_fake_repo(tmp_path / "a"))
    new = RE.decision_path_tree(_fake_repo(tmp_path / "b", extra={
        "src/life_agent/core/executor.py": "def decide(): pass\n"}))
    note = RE.tree_pin_note(new, compare=old, compare_run_id="gate-earlier")

    assert "decision logic" in note.lower()
    assert "src/life_agent/core/executor.py" in note
    # the honest claim: attributable only insofar as this list IS the intended change
    assert "intended change" in note.lower()


# --- r30b: the DECIDER's tree, not only the body's --------------------------------------

def test_the_run_meta_pins_the_decider_tree(monkeypatch, tmp_path: Path) -> None:
    """r30b: §6.10's declaration covers only this repo, but the gate's typed arm decides in
    the answer-brain daemon — a different tree. A run that cannot name the tree that produced
    its decisions cannot attribute its own reading, which is the whole point of §6.10."""
    import argparse
    import subprocess
    repo = tmp_path / "decider"
    repo.mkdir()
    (repo / "f.jl").write_text("x\n", encoding="utf-8")
    for cmd in (["init", "-q", "-b", "master"], ["add", "-A"]):
        subprocess.run(["git", "-C", str(repo), *cmd], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-qm", "x"], check=True)
    monkeypatch.setenv("CREDENCE_DIR", str(repo))
    meta = RE.build_gate_run_meta(
        run_id="gate-test", args=argparse.Namespace(k=20), questions=[],
        questions_path=None, corpus={"digest": "d", "pin_status": "matched"},
        availability={}, baseline="monolithic")
    assert len(meta["decider_git"]["sha"]) == 40
    assert meta["decider_git"]["dirty"] is False


def test_an_unlocatable_decider_is_named_not_silent(monkeypatch) -> None:
    """A missing checkout records a stated reason — never an absent key a reader would
    mistake for 'the decider did not move'."""
    import argparse
    monkeypatch.delenv("CREDENCE_DIR", raising=False)
    meta = RE.build_gate_run_meta(
        run_id="gate-test", args=argparse.Namespace(k=20), questions=[],
        questions_path=None, corpus={"digest": "d", "pin_status": "matched"},
        availability={}, baseline="monolithic")
    assert meta["decider_git"]["sha"] is None
    assert "CREDENCE_DIR" in meta["decider_git"]["note"]
