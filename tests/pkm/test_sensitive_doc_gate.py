"""Tests for the ``sensitive_doc_gate`` policy function."""

from __future__ import annotations

from pathlib import Path

from pkm.policy import (
    Allow,
    CostEstimate,
    PolicyContext,
    RequireApproval,
    SourceRef,
)
from pkm.policy_loader import load_policy

_SENSITIVE_DOC_GATE_SOURCE = '''\
import fnmatch

from pkm.policy import Allow, RequireApproval


def sensitive_doc_gate(transform_decl, sources, estimated_cost, context):
    config = context.policy_config.get("sensitive_doc_gate", {})
    sensitive_tags = set(config.get("tags", ["sensitive"]))
    path_patterns = config.get("path_patterns", [])

    flagged = []
    for source in sources:
        if source.tags & sensitive_tags:
            flagged.append(source.source_id)
            continue
        for pattern in path_patterns:
            if fnmatch.fnmatch(source.path, pattern):
                flagged.append(source.source_id)
                break

    if flagged:
        return RequireApproval(
            reason=f"{len(flagged)} sensitive source(s) detected"
        )
    return Allow()
'''

_COST = CostEstimate(total_usd=1.0, per_source_usd=0.01, source_count=100)


def _setup(root: Path) -> None:
    (root / "policies").mkdir(exist_ok=True)
    (root / "policies" / "sensitive_doc_gate.py").write_text(
        _SENSITIVE_DOC_GATE_SOURCE, encoding="utf-8",
    )


def _ctx(
    root: Path, *, tags: list[str] | None = None,
) -> PolicyContext:
    return PolicyContext(
        root=root,
        policy_config={
            "sensitive_doc_gate": {
                "tags": tags or ["sensitive", "medical"],
                "path_patterns": [],
            },
        },
    )


def test_allows_normal_sources(tmp_path: Path) -> None:
    _setup(tmp_path)
    fn = load_policy(tmp_path, "sensitive_doc_gate")
    sources = [
        SourceRef(source_id="a" * 64, tags=frozenset(["legal"]), path="/doc.txt"),
    ]
    result = fn(None, sources, _COST, _ctx(tmp_path))  # type: ignore[arg-type]
    assert isinstance(result, Allow)


def test_requires_approval_for_sensitive_tag(tmp_path: Path) -> None:
    _setup(tmp_path)
    fn = load_policy(tmp_path, "sensitive_doc_gate")
    sources = [
        SourceRef(source_id="a" * 64, tags=frozenset(["sensitive"]), path="/doc.txt"),
        SourceRef(source_id="b" * 64, tags=frozenset(["legal"]), path="/other.txt"),
    ]
    result = fn(None, sources, _COST, _ctx(tmp_path))  # type: ignore[arg-type]
    assert isinstance(result, RequireApproval)
    assert "1 sensitive" in result.reason


def test_requires_approval_for_medical_tag(tmp_path: Path) -> None:
    _setup(tmp_path)
    fn = load_policy(tmp_path, "sensitive_doc_gate")
    sources = [
        SourceRef(source_id="a" * 64, tags=frozenset(["medical"]), path="/doc.txt"),
    ]
    result = fn(None, sources, _COST, _ctx(tmp_path))  # type: ignore[arg-type]
    assert isinstance(result, RequireApproval)


def test_requires_approval_for_path_pattern(tmp_path: Path) -> None:
    _setup(tmp_path)
    fn = load_policy(tmp_path, "sensitive_doc_gate")
    sources = [
        SourceRef(
            source_id="a" * 64,
            tags=frozenset(),
            path="/data/medical/report.txt",
        ),
    ]
    ctx = PolicyContext(
        root=tmp_path,
        policy_config={
            "sensitive_doc_gate": {
                "tags": ["sensitive"],
                "path_patterns": ["*/medical/*"],
            },
        },
    )
    result = fn(None, sources, _COST, ctx)  # type: ignore[arg-type]
    assert isinstance(result, RequireApproval)


def test_uses_default_tags_when_no_config(tmp_path: Path) -> None:
    _setup(tmp_path)
    fn = load_policy(tmp_path, "sensitive_doc_gate")
    sources = [
        SourceRef(source_id="a" * 64, tags=frozenset(["sensitive"]), path="/doc.txt"),
    ]
    ctx = PolicyContext(root=tmp_path, policy_config={})
    result = fn(None, sources, _COST, ctx)  # type: ignore[arg-type]
    assert isinstance(result, RequireApproval)
